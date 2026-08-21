import logging
from dataclasses import dataclass

import reflex as rx

from src import context, formatting
from src.constants import (
    DEFAULT_STATUS_COLOR,
    EMPTY_VALUE,
    PERIOD_TODAY,
    QUEUE_STATUSES,
    STATUS_COLORS,
    STATUS_FAILED,
    STATUS_LABELS,
)
from src.database import build_window
from src.state.auth import AuthState

logger = logging.getLogger(__name__)


@dataclass
class CriterionDelta:
    code: str
    label: str
    before: int
    after: int
    points: int
    delta: str


@dataclass
class QueueRow:
    call_id: int
    status: str
    status_label: str
    status_color: str
    agent_name: str
    started_at: str
    error: str


@dataclass
class AnalysisRow:
    call_id: int
    agent_name: str
    score: str
    finished_at: str


@dataclass
class CallType:
    code: str
    label: str


class DashboardState(AuthState):
    period: str = PERIOD_TODAY
    selected_types: list[str] = []
    available_types: list[CallType] = []

    processed: int = 0
    processed_delta: int = 0
    queued: int = 0
    failed: int = 0
    best_manager: str = EMPTY_VALUE
    best_score: str = EMPTY_VALUE
    worst_manager: str = EMPTY_VALUE
    worst_score: str = EMPTY_VALUE

    criteria_deltas: list[CriterionDelta] = []
    queue_rows: list[QueueRow] = []
    recent_rows: list[AnalysisRow] = []

    loaded: bool = False

    @rx.event
    def load(self):
        if not self.session_login:
            return AuthState.require_session

        database = context.database()
        if not self.available_types:
            self.available_types = [
                CallType(code=row["code"], label=row["label"])
                for row in database.call_types()
            ]
            self.selected_types = [entry.code for entry in self.available_types]

        self._refresh()
        self.loaded = True

    @rx.event
    def set_period(self, period: str | list[str]):
        self.period = period if isinstance(period, str) else period[0]
        self._refresh()

    @rx.event
    def toggle_type(self, code: str, enabled: bool):
        codes = {str(entry) for entry in self.selected_types}
        if enabled:
            codes.add(code)
        else:
            codes.discard(code)
        self.selected_types = sorted(codes)
        self._refresh()

    def _refresh(self) -> None:
        data = collect(self.period, self.selected_types)
        self.processed = data.processed
        self.processed_delta = data.processed_delta
        self.queued = data.queued
        self.failed = data.failed
        self.best_manager = data.best_manager
        self.best_score = data.best_score
        self.worst_manager = data.worst_manager
        self.worst_score = data.worst_score
        self.criteria_deltas = data.criteria_deltas
        self.queue_rows = data.queue_rows
        self.recent_rows = data.recent_rows


@dataclass
class DashboardData:
    processed: int
    processed_delta: int
    queued: int
    failed: int
    best_manager: str
    best_score: str
    worst_manager: str
    worst_score: str
    criteria_deltas: list[CriterionDelta]
    queue_rows: list[QueueRow]
    recent_rows: list[AnalysisRow]


def collect(period: str, types: list[str]) -> DashboardData:
    database = context.database()
    display = context.config().display
    timezone = display.timezone

    since, until = formatting.period_bounds(period, timezone)
    previous_since, previous_until = formatting.previous_bounds(since, until)
    window = build_window(since, until, types, timezone)
    previous = build_window(previous_since, previous_until, types, timezone)

    totals = database.period_totals(window)
    previous_totals = database.period_totals(previous)
    counts = database.queue_counts()
    best_manager, best_score, worst_manager, worst_score = _extremes(database, window)

    return DashboardData(
        processed=totals["calls"],
        processed_delta=totals["calls"] - previous_totals["calls"],
        queued=sum(
            counts.get(status, 0) for status in QUEUE_STATUSES if status != STATUS_FAILED
        ),
        failed=counts.get(STATUS_FAILED, 0),
        best_manager=best_manager,
        best_score=best_score,
        worst_manager=worst_manager,
        worst_score=worst_score,
        criteria_deltas=_criteria_deltas(database, window, previous),
        queue_rows=_queue_rows(database, display.queue_size, timezone),
        recent_rows=_recent_rows(database, display.queue_size, timezone),
    )


def _extremes(database, window: dict) -> tuple[str, str, str, str]:
    agents = sorted(database.agent_totals(window), key=lambda row: row["ratio"])
    if not agents:
        return EMPTY_VALUE, EMPTY_VALUE, EMPTY_VALUE, EMPTY_VALUE
    worst, best = agents[0], agents[-1]
    return (
        best["display_name"],
        f"{formatting.percent(best['ratio'])}%",
        worst["display_name"],
        f"{formatting.percent(worst['ratio'])}%",
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
                before=formatting.percent(earlier.get(code)),
                after=formatting.percent(ratio),
                points=points,
                delta=formatting.delta_label(points),
            )
        )
    return sorted(deltas, key=lambda entry: entry.points)


def _queue_rows(database, limit: int, timezone: str) -> list[QueueRow]:
    return [
        QueueRow(
            call_id=row["call_id"],
            status=row["status"],
            status_label=STATUS_LABELS.get(row["status"], row["status"]),
            status_color=STATUS_COLORS.get(row["status"], DEFAULT_STATUS_COLOR),
            agent_name=row["agent_name"] or EMPTY_VALUE,
            started_at=formatting.moment(row["started_at"], timezone),
            error=(row["last_error"] or "").splitlines()[0] if row["last_error"] else "",
        )
        for row in database.queue_jobs(limit)
    ]


def _recent_rows(database, limit: int, timezone: str) -> list[AnalysisRow]:
    return [
        AnalysisRow(
            call_id=row["id"],
            agent_name=row["agent_name"] or EMPTY_VALUE,
            score=formatting.fraction(row["met"], row["total"]),
            finished_at=formatting.moment(row["created_at"], timezone),
        )
        for row in database.recent_analyses(limit)
    ]
