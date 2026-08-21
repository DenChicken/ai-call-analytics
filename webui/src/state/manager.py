import logging
from dataclasses import dataclass

import reflex as rx

from src import context, formatting
from src.constants import EMPTY_VALUE, PERIOD_MONTH
from src.database import build_window
from src.state.auth import AuthState

logger = logging.getLogger(__name__)

CHART_DAY_KEY = "day"
CHART_SCORE_KEY = "score"
CHART_LABEL_KEY = "label"
PARAM_AGENT_ID = "agent_id"
UNKNOWN_AGENT_ID = 0


def _route_agent_id(params: dict) -> int:
    value = params.get(PARAM_AGENT_ID)
    return int(value) if value and str(value).isdigit() else UNKNOWN_AGENT_ID


@dataclass
class CriterionScore:
    code: str
    label: str
    score: int
    score_label: str


@dataclass
class CallRow:
    call_id: int
    started_at: str
    client: str
    duration: str
    score: str
    call_type: str


@dataclass
class ManagerData:
    name: str
    email: str
    profile_link: str
    score: str
    calls: int
    best_call: str
    best_call_id: int
    worst_call: str
    worst_call_id: int
    criteria: list[CriterionScore]
    trend: list[dict]
    calls_rows: list[CallRow]


class ManagerState(AuthState):
    period: str = PERIOD_MONTH

    name: str = EMPTY_VALUE
    email: str = ""
    profile_link: str = ""
    score: str = EMPTY_VALUE
    calls: int = 0
    best_call: str = EMPTY_VALUE
    best_call_id: int = 0
    worst_call: str = EMPTY_VALUE
    worst_call_id: int = 0

    criteria: list[CriterionScore] = []
    radar: list[dict] = []
    trend: list[dict] = []
    calls_rows: list[CallRow] = []

    current_agent_id: int = 0

    @rx.event
    def load(self):
        if not self.session_login:
            return AuthState.require_session
        self.current_agent_id = _route_agent_id(self.router.page.params)
        self._refresh()

    @rx.event
    def set_period(self, period: str | list[str]):
        self.period = period if isinstance(period, str) else period[0]
        self._refresh()

    def _refresh(self) -> None:
        data = collect(self.current_agent_id, self.period)
        self.name = data.name
        self.email = data.email
        self.profile_link = data.profile_link
        self.score = data.score
        self.calls = data.calls
        self.best_call = data.best_call
        self.best_call_id = data.best_call_id
        self.worst_call = data.worst_call
        self.worst_call_id = data.worst_call_id
        self.criteria = data.criteria
        self.radar = [
            {CHART_LABEL_KEY: entry.label, CHART_SCORE_KEY: entry.score}
            for entry in data.criteria
        ]
        self.trend = data.trend
        self.calls_rows = data.calls_rows


def collect(agent_id: int, period: str) -> ManagerData:
    database = context.database()
    display = context.config().display
    timezone = display.timezone

    since, until = formatting.period_bounds(period, timezone)
    types = [entry["code"] for entry in database.call_types()]
    window = build_window(since, until, types, timezone, agent_id=agent_id)

    agent = database.agent(agent_id)
    totals = database.period_totals(window)
    extremes = database.extreme_calls(window)

    return ManagerData(
        name=agent["display_name"] if agent else EMPTY_VALUE,
        email=agent["email"] or "" if agent else "",
        profile_link=agent["profile_link"] or "" if agent else "",
        score=f"{formatting.percent(totals['ratio'])}%" if totals["calls"] else EMPTY_VALUE,
        calls=totals["calls"],
        best_call=_extreme_label(extremes.get("best")),
        best_call_id=extremes["best"]["id"] if "best" in extremes else 0,
        worst_call=_extreme_label(extremes.get("worst")),
        worst_call_id=extremes["worst"]["id"] if "worst" in extremes else 0,
        criteria=_criteria(database, window),
        trend=_trend(database, window),
        calls_rows=_calls(database, window, display.page_size, timezone),
    )


def _extreme_label(row: dict | None) -> str:
    if row is None:
        return EMPTY_VALUE
    return formatting.fraction(row["met"], row["total"])


def _criteria(database, window: dict) -> list[CriterionScore]:
    labels = {row["code"]: row["label"] for row in database.criteria() if row["enabled"]}
    ratios = {row["code"]: row["ratio"] for row in database.criteria_ratios(window)}
    return [
        CriterionScore(
            code=code,
            label=label,
            score=formatting.percent(ratios.get(code)),
            score_label=f"{formatting.percent(ratios.get(code))}%",
        )
        for code, label in labels.items()
    ]


def _trend(database, window: dict) -> list[dict]:
    return [
        {
            CHART_DAY_KEY: formatting.day_label(row["day"]),
            CHART_SCORE_KEY: formatting.percent(row["ratio"]),
        }
        for row in database.agent_daily_ratios(window)
    ]


def _calls(database, window: dict, limit: int, timezone: str) -> list[CallRow]:
    return [
        CallRow(
            call_id=row["id"],
            started_at=formatting.moment(row["started_at"], timezone),
            client=row["client_number"] or EMPTY_VALUE,
            duration=formatting.duration(row["duration_seconds"]),
            score=formatting.fraction(row["met"], row["total"]),
            call_type=row["call_type_label"] or row["call_type"] or EMPTY_VALUE,
        )
        for row in database.calls_page(window, limit, 0)
    ]
