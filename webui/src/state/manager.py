import logging
from dataclasses import dataclass

import reflex as rx

from src import context, criteria, errors, formatting, urlstate
from src.constants import (
    DEFAULT_STATUS_COLOR,
    EMPTY_VALUE,
    PARAM_AGENT,
    PARAM_PERIOD,
    PARAM_TYPES,
    PERIOD_BY_CODE,
    ROUTE_CALLS,
    ROUTE_MANAGER,
    STATUS_COLORS,
    STATUS_LABELS,
)
from src.database import build_filters, build_window
from src.state.auth import AuthState, guarded
from src.state.period_filter import PeriodFilterState
from src.state.types_filter import TypesFilterState

logger = logging.getLogger(__name__)

CHART_DAY_KEY = "day"
CHART_SCORE_KEY = "score"
CHART_LABEL_KEY = "label"
CRITERION_LINE_COLORS = (
    "var(--indigo-9)",
    "var(--grass-9)",
    "var(--tomato-9)",
    "var(--amber-9)",
    "var(--cyan-9)",
    "var(--plum-9)",
    "var(--orange-9)",
    "var(--teal-9)",
    "var(--crimson-9)",
    "var(--brown-9)",
    "var(--blue-9)",
    "var(--gold-9)",
)
UNKNOWN_AGENT_ID = 0
FIRST_CRITERION_NUMBER = 1


def _as_id(value) -> int:
    text = str(value)
    return int(text) if text.isdigit() else UNKNOWN_AGENT_ID


@dataclass
class CriterionScore:
    code: str
    number: int
    label: str
    color: str
    score: float
    score_label: str


@dataclass
class CallRow:
    call_id: int
    started_at: str
    client: str
    duration: str
    score: str
    call_type: str
    status_label: str
    status_color: str
    error: str


@dataclass
class CriterionLine:
    code: str
    label: str
    color: str


@dataclass
class ManagerData:
    found: bool
    name: str
    email: str
    profile_link: str
    score: str
    calls: int
    analyzed: int
    best_call: str
    best_call_id: int
    worst_call: str
    worst_call_id: int
    criteria_scores: list[CriterionScore]
    criteria_deltas: list[criteria.CriterionDelta]
    score_points: int
    score_delta: str
    trend: list[dict]
    criteria_trend: list[dict]
    criteria_lines: list[CriterionLine]
    calls_rows: list[CallRow]
    calls_total: int


class ManagerState(PeriodFilterState, TypesFilterState, AuthState):
    found: bool = False
    name: str = EMPTY_VALUE
    email: str = ""
    profile_link: str = ""
    score: str = EMPTY_VALUE
    calls: int = 0
    analyzed: int = 0
    best_call: str = EMPTY_VALUE
    best_call_id: int = 0
    worst_call: str = EMPTY_VALUE
    worst_call_id: int = 0

    score_points: int = 0
    score_delta: str = ""

    criteria_scores: list[CriterionScore] = []
    criteria_deltas: list[criteria.CriterionDelta] = []
    criteria_chart: list[dict] = []
    criteria_expanded: bool = False
    radar: list[dict] = []
    trend: list[dict] = []
    criteria_trend: list[dict] = []
    criteria_lines: list[CriterionLine] = []
    hidden_lines: list[str] = []
    show_dots: bool = False
    calls_rows: list[CallRow] = []
    calls_total: int = 0

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

    @rx.event
    def toggle_line(self, code: str):
        hidden = {str(entry) for entry in self.hidden_lines}
        if code in hidden:
            hidden.discard(code)
        else:
            hidden.add(code)
        self.hidden_lines = sorted(hidden)

    @rx.event
    def show_all_lines(self):
        self.hidden_lines = []

    @rx.event
    def hide_all_lines(self):
        self.hidden_lines = [entry.code for entry in self.criteria_lines]

    @rx.event
    def toggle_dots(self, enabled: bool):
        self.show_dots = enabled

    current_agent_id: int = 0

    @rx.event
    def load(self):
        if not self.session_login:
            return AuthState.require_session
        self.current_agent_id = _as_id(self.agent_id)
        self._load_types()
        self._read_url()
        self._refresh()

    def _types_changed(self):
        self._refresh()
        return self._sync_url()

    def _period_changed(self):
        self._refresh()
        return self._sync_url()

    @rx.var
    def all_calls_link(self) -> str:
        return urlstate.query(
            ROUTE_CALLS,
            {
                PARAM_AGENT: str(self.current_agent_id),
                PARAM_PERIOD: self.period,
                PARAM_TYPES: self._types_param,
            },
        )

    def _read_url(self) -> None:
        params = self.router.url.query_parameters
        self._read_period(params)
        self._read_types(params)

    def _sync_url(self):
        return rx.redirect(
            urlstate.query(
                f"{ROUTE_MANAGER}/{self.current_agent_id}",
                {
                    PARAM_PERIOD: self.period,
                    PARAM_TYPES: self._types_param,
                },
            ),
            replace=True,
        )

    def _refresh(self) -> None:
        guarded(self, self._collect)

    def _collect(self) -> None:
        data = collect(
            self.current_agent_id,
            self.period,
            list(self.selected_types),
            self.utc_offset,
        )
        self.found = data.found
        self.name = data.name
        self.email = data.email
        self.profile_link = data.profile_link
        self.score = data.score
        self.calls = data.calls
        self.analyzed = data.analyzed
        self.best_call = data.best_call
        self.best_call_id = data.best_call_id
        self.worst_call = data.worst_call
        self.worst_call_id = data.worst_call_id
        self.score_points = data.score_points
        self.score_delta = data.score_delta
        self.criteria_scores = data.criteria_scores
        self.criteria_deltas = data.criteria_deltas
        self.criteria_chart = criteria.chart_points(data.criteria_deltas)
        self.radar = [
            {CHART_LABEL_KEY: str(entry.number), CHART_SCORE_KEY: entry.score}
            for entry in data.criteria_scores
        ]
        self.trend = data.trend
        self.criteria_trend = data.criteria_trend
        self.criteria_lines = data.criteria_lines
        self.calls_rows = data.calls_rows
        self.calls_total = data.calls_total


def collect(
    agent_id: int, period: str, types: list[str], offset_hours: int
) -> ManagerData:
    database = context.database()
    display = context.config().display

    since, until = formatting.period_bounds(period, offset_hours)
    previous_since, previous_until = formatting.previous_bounds(since, until)
    bucket = PERIOD_BY_CODE[period].bucket
    window = build_window(since, until, types, bucket, agent_id=agent_id)
    previous = build_window(
        previous_since, previous_until, types, bucket, agent_id=agent_id
    )
    filters = build_filters(since, until, types, agent_id, None)

    agent = database.agent(agent_id)
    totals = database.period_totals(window)
    previous_totals = database.period_totals(previous)
    extremes = database.extreme_calls(window)
    scores = _criteria(database, window)
    calls_rows, calls_total = _calls(
        database, filters, display.page_size, offset_hours
    )
    score_points = formatting.delta_points(
        previous_totals["ratio"] if previous_totals["calls"] else None,
        totals["ratio"] if totals["calls"] else None,
    )

    return ManagerData(
        found=agent is not None,
        name=agent["display_name"] if agent else EMPTY_VALUE,
        email=agent["email"] or "" if agent else "",
        profile_link=agent["profile_link"] or "" if agent else "",
        score=formatting.share_label(totals["ratio"], totals["calls"]),
        calls=calls_total,
        analyzed=totals["calls"],
        best_call=_extreme_label(extremes.get("best")),
        best_call_id=extremes["best"]["id"] if "best" in extremes else 0,
        worst_call=_extreme_label(extremes.get("worst")),
        worst_call_id=extremes["worst"]["id"] if "worst" in extremes else 0,
        criteria_scores=scores,
        criteria_deltas=criteria.deltas(database, window, previous),
        score_points=score_points,
        score_delta=formatting.delta_label(score_points),
        trend=_trend(database, window),
        criteria_trend=_criteria_trend(database, window, scores),
        criteria_lines=_criteria_lines(scores),
        calls_rows=calls_rows,
        calls_total=calls_total,
    )


def _extreme_label(row: dict | None) -> str:
    if row is None:
        return EMPTY_VALUE
    return formatting.fraction(row["met"], row["total"])


def _criteria(database, window: dict) -> list[CriterionScore]:
    labels = {row["code"]: row["label"] for row in database.criteria()}
    ratios = {row["code"]: row["ratio"] for row in database.criteria_ratios(window)}
    scored = [code for code in labels if code in ratios]
    return [
        CriterionScore(
            code=code,
            number=number,
            label=labels[code],
            color=CRITERION_LINE_COLORS[(number - 1) % len(CRITERION_LINE_COLORS)],
            score=formatting.share(ratios[code]),
            score_label=formatting.share_label(ratios[code]),
        )
        for number, code in enumerate(scored, start=FIRST_CRITERION_NUMBER)
    ]


def _criteria_lines(scores: list[CriterionScore]) -> list[CriterionLine]:
    return [
        CriterionLine(code=entry.code, label=entry.label, color=entry.color)
        for entry in scores
    ]


def _criteria_trend(
    database, window: dict, scores: list[CriterionScore]
) -> list[dict]:
    codes = [entry.code for entry in scores]
    days: dict[str, dict] = {}
    for row in database.criteria_bucket_ratios(window):
        day = formatting.bucket_label(row["day"], window["bucket"])
        point = days.setdefault(day, {CHART_DAY_KEY: day, **dict.fromkeys(codes)})
        point[row["code"]] = formatting.share(row["ratio"])
    return list(days.values())


def _trend(database, window: dict) -> list[dict]:
    return [
        {
            CHART_DAY_KEY: formatting.bucket_label(row["day"], window["bucket"]),
            CHART_SCORE_KEY: formatting.share(row["ratio"]),
        }
        for row in database.agent_bucket_ratios(window)
    ]


def _calls(
    database, filters: dict, limit: int, offset_hours: int
) -> tuple[list[CallRow], int]:
    rows = [
        CallRow(
            call_id=row["id"],
            started_at=formatting.moment(row["started_at"], offset_hours),
            client=row["client_number"] or EMPTY_VALUE,
            duration=formatting.duration(row["duration_seconds"]),
            score=formatting.fraction(row["met"], row["total"]),
            call_type=row["call_type_label"] or row["call_type"] or EMPTY_VALUE,
            status_label=STATUS_LABELS.get(row["status"], row["status"] or EMPTY_VALUE),
            status_color=STATUS_COLORS.get(row["status"], DEFAULT_STATUS_COLOR),
            error=errors.describe(row["error_code"]),
        )
        for row in database.calls_list(filters, limit, 0)
    ]
    return rows, database.calls_list_count(filters)
