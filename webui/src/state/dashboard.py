import asyncio
import logging
from dataclasses import dataclass

import reflex as rx

from src import context, errors, formatting, urlstate
from src.constants import (
    DEFAULT_STATUS_COLOR,
    EMPTY_VALUE,
    PARAM_PERIOD,
    PARAM_TYPES,
    PERIOD_BY_LABEL,
    PERIOD_DAYS,
    PERIOD_LABELS,
    PERIOD_TODAY,
    QUEUE_STATUSES,
    ROUTE_DASHBOARD,
    STATUS_COLORS,
    STATUS_FAILED,
    STATUS_LABELS,
    TYPES_SUMMARY_TEMPLATE,
)
from src.database import CallType, build_window
from src.state.auth import AuthState, guarded

logger = logging.getLogger(__name__)

CHART_LABEL_KEY = "label"
CHART_BEFORE_KEY = "before"
CHART_AFTER_KEY = "after"
CRITERIA_PREVIEW_COUNT = 6
CRITERIA_GROUP_HEIGHT = 52
CRITERIA_CHART_PADDING = 64


@dataclass
class CriterionDelta:
    code: str
    label: str
    before: float
    after: float
    points: int
    delta: str


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
    criteria_deltas: list[CriterionDelta]
    queue_rows: list[QueueRow]
    recent_rows: list[AnalysisRow]


class DashboardState(AuthState):
    period: str = PERIOD_TODAY
    selected_types: list[str] = []
    available_types: list[CallType] = []

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

    criteria_deltas: list[CriterionDelta] = []
    criteria_chart: list[dict] = []
    criteria_expanded: bool = False
    queue_rows: list[QueueRow] = []
    recent_rows: list[AnalysisRow] = []
    watching: bool = False

    @rx.event
    def load(self):
        if not self.session_login:
            return AuthState.require_session
        if not self.available_types:
            self.available_types = [
                CallType(code=row["code"], label=row["label"])
                for row in context.database().call_types()
            ]
            self.selected_types = [entry.code for entry in self.available_types]
        self._read_url()
        self._refresh()
        return DashboardState.auto_refresh

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
                self._refresh()

    @rx.event
    def toggle_criteria(self):
        self.criteria_expanded = not self.criteria_expanded

    @rx.var
    def visible_criteria(self) -> list[dict]:
        if self.criteria_expanded:
            return list(self.criteria_chart)
        return list(self.criteria_chart)[:CRITERIA_PREVIEW_COUNT]

    @rx.var
    def criteria_hidden_count(self) -> int:
        return max(len(self.criteria_chart) - CRITERIA_PREVIEW_COUNT, 0)

    @rx.var
    def criteria_chart_height(self) -> int:
        return len(self.visible_criteria) * CRITERIA_GROUP_HEIGHT + CRITERIA_CHART_PADDING

    @rx.var
    def period_label(self) -> str:
        return PERIOD_LABELS[self.period]

    @rx.var
    def types_summary(self) -> str:
        return TYPES_SUMMARY_TEMPLATE.format(
            selected=len(self.selected_types), total=len(self.available_types)
        )

    @rx.event
    def set_period(self, label: str):
        self.period = PERIOD_BY_LABEL.get(label, self.period)
        self._refresh()
        return self._sync_url()

    @rx.event
    def toggle_type(self, code: str, enabled: bool):
        codes = {str(entry) for entry in self.selected_types}
        if enabled:
            codes.add(code)
        else:
            codes.discard(code)
        self.selected_types = sorted(codes)
        self._refresh()
        return self._sync_url()

    def _read_url(self) -> None:
        params = self.router.url.query_parameters
        self.period = urlstate.read_choice(params, PARAM_PERIOD, PERIOD_DAYS, self.period)
        codes = [entry.code for entry in self.available_types]
        self.selected_types = urlstate.read_list(
            params, PARAM_TYPES, codes, self.selected_types
        )

    def _sync_url(self):
        codes = [entry.code for entry in self.available_types]
        return rx.redirect(
            urlstate.query(
                ROUTE_DASHBOARD,
                {
                    PARAM_PERIOD: self.period,
                    PARAM_TYPES: urlstate.write_list(self.selected_types, codes),
                },
            ),
            replace=True,
        )

    def _refresh(self) -> None:
        guarded(self, self._collect)

    def _collect(self) -> None:
        data = collect(self.period, self.selected_types, self.utc_offset)
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
        self.criteria_chart = [
            {
                CHART_LABEL_KEY: entry.label,
                CHART_BEFORE_KEY: entry.before,
                CHART_AFTER_KEY: entry.after,
            }
            for entry in data.criteria_deltas
        ]
        self.queue_rows = data.queue_rows
        self.recent_rows = data.recent_rows


def collect(period: str, types: list[str], offset_hours: int) -> DashboardData:
    database = context.database()
    display = context.config().display

    since, until = formatting.period_bounds(period, offset_hours)
    previous_since, previous_until = formatting.previous_bounds(since, until)
    window = build_window(since, until, types)
    previous = build_window(previous_since, previous_until, types)

    totals = database.period_totals(window)
    previous_totals = database.period_totals(previous)
    counts = database.queue_counts()
    best, worst = _extremes(database, window)

    return DashboardData(
        processed=totals["calls"],
        processed_delta=totals["calls"] - previous_totals["calls"],
        analyzed_today=database.analyses_count(since, until, types),
        queued=sum(
            counts.get(status, 0) for status in QUEUE_STATUSES if status != STATUS_FAILED
        ),
        failed=counts.get(STATUS_FAILED, 0),
        best_manager=best[0],
        best_manager_id=best[1],
        best_score=best[2],
        worst_manager=worst[0],
        worst_manager_id=worst[1],
        worst_score=worst[2],
        criteria_deltas=_criteria_deltas(database, window, previous),
        queue_rows=_queue_rows(database, types, display.queue_size, offset_hours),
        recent_rows=_recent_rows(database, types, display.queue_size, offset_hours),
    )


def _extremes(database, window: dict) -> tuple[tuple, tuple]:
    scored = [row for row in database.agent_totals(window) if row["ratio"] is not None]
    agents = sorted(scored, key=lambda row: row["ratio"])
    if not agents:
        empty = (EMPTY_VALUE, 0, "")
        return empty, empty
    worst, best = agents[0], agents[-1]
    return (
        (best["display_name"], best["agent_id"], formatting.share_label(best["ratio"])),
        (worst["display_name"], worst["agent_id"], formatting.share_label(worst["ratio"])),
    )


def _criteria_deltas(database, window: dict, previous: dict) -> list[CriterionDelta]:
    labels = {row["code"]: row["label"] for row in database.criteria()}
    current = {row["code"]: row["ratio"] for row in database.criteria_ratios(window)}
    earlier = {row["code"]: row["ratio"] for row in database.criteria_ratios(previous)}

    deltas = []
    for code, ratio in current.items():
        points = formatting.delta_points(earlier.get(code), ratio)
        deltas.append(
            CriterionDelta(
                code=code,
                label=labels.get(code, code),
                before=formatting.share(earlier.get(code)),
                after=formatting.share(ratio),
                points=points,
                delta=formatting.delta_label(points),
            )
        )
    return sorted(deltas, key=lambda entry: entry.points)


def _queue_rows(database, types: list[str], limit: int, offset_hours: int) -> list[QueueRow]:
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
        for row in database.queue_jobs(types, limit)
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
