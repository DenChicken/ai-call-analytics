import asyncio
import logging
from dataclasses import dataclass

import reflex as rx

from src import context, criteria, errors, formatting, ranking, urlstate
from src.constants import (
    DEFAULT_STATUS_COLOR,
    EMPTY_VALUE,
    MIN_ANALYZED_CALLS,
    PARAM_MIN_CALLS,
    PARAM_PERIOD,
    PARAM_QUEUE_FAILED,
    PARAM_RANK,
    PARAM_TYPES,
    PERIOD_BY_CODE,
    QUEUE_FAILED_STATUSES,
    QUEUE_STATUSES,
    RANK_BY_LABEL,
    RANK_LABELS,
    RANK_SMOOTHED,
    ROUTE_DASHBOARD,
    STATUS_COLORS,
    STATUS_FAILED,
    STATUS_LABELS,
)
from src.database import build_window
from src.state.auth import AuthState, guarded
from src.state.period_filter import PeriodFilterState
from src.state.types_filter import TypesFilterState

logger = logging.getLogger(__name__)

TOP_MANAGERS_LIMIT = 10
CHART_NAME_KEY = "name"
CHART_SCORE_KEY = "score"
FIRST_MANAGER_NUMBER = 1


@dataclass
class TopManagerRow:
    agent_id: int
    number: int
    name: str
    score: float
    score_label: str
    analyzed: int


@dataclass
class QueueRow:
    call_id: int
    status_label: str
    status_color: str
    agent_id: int
    agent_name: str
    client: str
    started_at: str
    error: str


@dataclass
class AnalysisRow:
    call_id: int
    agent_id: int
    agent_name: str
    client: str
    score: str
    started_at: str
    analyzed_at: str


@dataclass
class DashboardData:
    processed: int
    processed_delta: int
    analyzed_today: int
    queued: int
    failed: int
    best_manager: str
    best_manager_id: int
    best_score: str
    worst_manager: str
    worst_manager_id: int
    worst_score: str
    criteria_deltas: list[criteria.CriterionDelta]
    top_managers: list[TopManagerRow]
    queue_rows: list[QueueRow]
    recent_rows: list[AnalysisRow]


class DashboardState(PeriodFilterState, TypesFilterState, AuthState):
    rank_mode: str = RANK_SMOOTHED
    min_calls_only: bool = False
    queue_failed: bool = False

    processed: int = 0
    processed_delta: int = 0
    analyzed_today: int = 0
    queued: int = 0
    failed: int = 0
    best_manager: str = EMPTY_VALUE
    best_manager_id: int = 0
    best_score: str = ""
    worst_manager: str = EMPTY_VALUE
    worst_manager_id: int = 0
    worst_score: str = ""

    criteria_deltas: list[criteria.CriterionDelta] = []
    criteria_chart: list[dict] = []
    criteria_expanded: bool = False
    top_managers: list[TopManagerRow] = []
    top_managers_chart: list[dict] = []
    queue_rows: list[QueueRow] = []
    recent_rows: list[AnalysisRow] = []
    watching: bool = False

    @rx.event
    def load(self):
        if not self.session_login:
            return AuthState.require_session
        self._load_types()
        self._read_url()
        self._refresh()
        return DashboardState.auto_refresh

    def _types_changed(self):
        self._refresh()
        return self._sync_url()

    def _period_changed(self):
        self._refresh()
        return self._sync_url()

    @rx.event
    def refresh(self):
        self._refresh()

    @rx.event(background=True)
    async def auto_refresh(self):
        async with self:
            if self.watching:
                return
            self.watching = True

        interval = context.config().display.refresh_seconds
        while True:
            await asyncio.sleep(interval)
            async with self:
                if not self.session_login:
                    self.watching = False
                    return
                if self._auto_refresh and not self.filter_menu_open:
                    self._refresh()

    @rx.event
    def toggle_criteria(self):
        self.criteria_expanded = not self.criteria_expanded

    @rx.var
    def visible_criteria(self) -> list[dict]:
        return criteria.visible(self.criteria_chart, self.criteria_expanded)

    @rx.var
    def criteria_hidden_count(self) -> int:
        return criteria.hidden_count(self.criteria_chart)

    @rx.var
    def criteria_chart_height(self) -> int:
        return criteria.chart_height(self.visible_criteria)

    @rx.var
    def rank_label(self) -> str:
        return RANK_LABELS[self.rank_mode]

    @rx.event
    def set_rank_mode(self, label: str):
        self.rank_mode = RANK_BY_LABEL.get(label, self.rank_mode)
        self._refresh()
        return self._sync_url()

    @rx.event
    def toggle_min_calls(self, enabled: bool):
        self.min_calls_only = enabled
        self._refresh()
        return self._sync_url()

    @rx.event
    def toggle_queue_failed(self, enabled: bool):
        self.queue_failed = enabled
        self._refresh()
        return self._sync_url()

    def _read_url(self) -> None:
        params = self.router.url.query_parameters
        self._read_period(params)
        self.rank_mode = urlstate.read_choice(params, PARAM_RANK, RANK_LABELS, self.rank_mode)
        self.min_calls_only = urlstate.read_flag(params, PARAM_MIN_CALLS, self.min_calls_only)
        self.queue_failed = urlstate.read_flag(params, PARAM_QUEUE_FAILED, self.queue_failed)
        self._read_types(params)

    def _sync_url(self):
        return rx.redirect(
            urlstate.query(
                ROUTE_DASHBOARD,
                {
                    PARAM_PERIOD: self.period,
                    PARAM_TYPES: self._types_param,
                    PARAM_RANK: "" if self.rank_mode == RANK_SMOOTHED else self.rank_mode,
                    PARAM_MIN_CALLS: "1" if self.min_calls_only else "",
                    PARAM_QUEUE_FAILED: "1" if self.queue_failed else "",
                },
            ),
            replace=True,
        )

    def _refresh(self) -> None:
        guarded(self, self._collect)

    def _collect(self) -> None:
        data = collect(
            self.period,
            list(self.selected_types),
            self.utc_offset,
            self.rank_mode,
            MIN_ANALYZED_CALLS if self.min_calls_only else 0,
            QUEUE_FAILED_STATUSES if self.queue_failed else QUEUE_STATUSES,
        )
        self.processed = data.processed
        self.processed_delta = data.processed_delta
        self.analyzed_today = data.analyzed_today
        self.queued = data.queued
        self.failed = data.failed
        self.best_manager = data.best_manager
        self.best_manager_id = data.best_manager_id
        self.best_score = data.best_score
        self.worst_manager = data.worst_manager
        self.worst_manager_id = data.worst_manager_id
        self.worst_score = data.worst_score
        self.criteria_deltas = data.criteria_deltas
        self.criteria_chart = criteria.chart_points(data.criteria_deltas)
        self.top_managers = data.top_managers
        self.top_managers_chart = [
            {
                CHART_NAME_KEY: str(entry.number),
                CHART_SCORE_KEY: entry.score,
            }
            for entry in data.top_managers
        ]
        self.queue_rows = data.queue_rows
        self.recent_rows = data.recent_rows


def collect(
    period: str,
    types: list[str],
    offset_hours: int,
    rank_mode: str,
    minimum: int,
    queue_statuses: tuple[str, ...],
) -> DashboardData:
    database = context.database()
    display = context.config().display

    since, until = formatting.period_bounds(period, offset_hours)
    previous_since, previous_until = formatting.previous_bounds(since, until)
    bucket = PERIOD_BY_CODE[period].bucket
    window = build_window(since, until, types, bucket)
    previous = build_window(previous_since, previous_until, types, bucket)

    totals = database.period_totals(window)
    previous_totals = database.period_totals(previous)
    counts = database.queue_counts()
    scored = [row for row in database.agent_totals(window) if row["ratio"] is not None]
    best, worst = _extremes(scored)

    return DashboardData(
        processed=totals["calls"],
        processed_delta=totals["calls"] - previous_totals["calls"],
        analyzed_today=database.analyses_count(since, until, types),
        queued=sum(counts.get(status, 0) for status in QUEUE_STATUSES),
        failed=counts.get(STATUS_FAILED, 0),
        best_manager=best[0],
        best_manager_id=best[1],
        best_score=best[2],
        worst_manager=worst[0],
        worst_manager_id=worst[1],
        worst_score=worst[2],
        criteria_deltas=criteria.deltas(database, window, previous),
        top_managers=_top_managers(scored, rank_mode, minimum),
        queue_rows=_queue_rows(
            database, types, display.queue_size, offset_hours, queue_statuses
        ),
        recent_rows=_recent_rows(database, types, display.queue_size, offset_hours),
    )


def _extremes(scored: list[dict]) -> tuple[tuple, tuple]:
    agents = sorted(scored, key=lambda row: row["ratio"])
    if not agents:
        empty = (EMPTY_VALUE, 0, "")
        return empty, empty
    worst, best = agents[0], agents[-1]
    return (
        (best["display_name"], best["agent_id"], formatting.share_label(best["ratio"])),
        (worst["display_name"], worst["agent_id"], formatting.share_label(worst["ratio"])),
    )


def _top_managers(scored: list[dict], mode: str, minimum: int) -> list[TopManagerRow]:
    base = ranking.baseline(scored)
    best = ranking.order(scored, mode, minimum)[:TOP_MANAGERS_LIMIT]
    return [
        TopManagerRow(
            agent_id=row["agent_id"],
            number=number,
            name=row["display_name"],
            score=formatting.share(ranking.displayed(row, base, mode)),
            score_label=formatting.share_label(ranking.displayed(row, base, mode)),
            analyzed=row["analyzed"],
        )
        for number, row in enumerate(best, start=FIRST_MANAGER_NUMBER)
    ]


def _queue_rows(
    database,
    types: list[str],
    limit: int,
    offset_hours: int,
    statuses: tuple[str, ...],
) -> list[QueueRow]:
    return [
        QueueRow(
            call_id=row["call_id"],
            status_label=STATUS_LABELS.get(row["status"], row["status"]),
            status_color=STATUS_COLORS.get(row["status"], DEFAULT_STATUS_COLOR),
            agent_id=row["agent_id"] or 0,
            agent_name=row["agent_name"] or EMPTY_VALUE,
            client=row["client_number"] or EMPTY_VALUE,
            started_at=formatting.moment(row["started_at"], offset_hours),
            error=errors.describe(row["error_code"]),
        )
        for row in database.queue_jobs(types, limit, statuses)
    ]


def _recent_rows(database, types: list[str], limit: int, offset_hours: int) -> list[AnalysisRow]:
    return [
        AnalysisRow(
            call_id=row["id"],
            agent_id=row["agent_id"] or 0,
            agent_name=row["agent_name"] or EMPTY_VALUE,
            client=row["client_number"] or EMPTY_VALUE,
            score=formatting.fraction(row["met"], row["total"]),
            started_at=formatting.moment(row["started_at"], offset_hours),
            analyzed_at=formatting.moment(row["created_at"], offset_hours),
        )
        for row in database.recent_analyses(types, limit)
    ]
