import logging
from dataclasses import dataclass

import reflex as rx

from src import context, formatting
from src.constants import PERIOD_WEEK
from src.database import build_window
from src.state.auth import AuthState

logger = logging.getLogger(__name__)

SORT_NAME = "name"
SORT_CALLS = "calls"
SORT_SCORE = "score"
SORT_DELTA = "delta"
SORT_LAST_CALL = "last_call"

SORT_LABELS = {
    SORT_NAME: "Имя",
    SORT_CALLS: "Звонков",
    SORT_SCORE: "Средний балл",
    SORT_DELTA: "Изменение",
    SORT_LAST_CALL: "Последний звонок",
}


@dataclass
class ManagerRow:
    agent_id: int
    name: str
    calls: int
    score: int
    score_label: str
    points: int
    delta: str
    last_call: str
    last_call_key: float


class ManagersState(AuthState):
    period: str = PERIOD_WEEK
    search: str = ""
    sort_by: str = SORT_SCORE
    descending: bool = True

    rows: list[ManagerRow] = []

    @rx.event
    def load(self):
        if not self.session_login:
            return AuthState.require_session
        self._refresh()

    @rx.event
    def set_period(self, period: str | list[str]):
        self.period = period if isinstance(period, str) else period[0]
        self._refresh()

    @rx.event
    def set_search(self, value: str):
        self.search = value
        self._refresh()

    @rx.event
    def sort(self, column: str):
        if self.sort_by == column:
            self.descending = not self.descending
        else:
            self.sort_by = column
            self.descending = column != SORT_NAME
        self._refresh()

    def _refresh(self) -> None:
        rows = collect(self.period)
        self.rows = sorted_rows(
            filtered_rows(rows, self.search), self.sort_by, self.descending
        )


def collect(period: str) -> list[ManagerRow]:
    database = context.database()
    timezone = context.config().display.timezone

    since, until = formatting.period_bounds(period, timezone)
    previous_since, previous_until = formatting.previous_bounds(since, until)
    types = [entry["code"] for entry in database.call_types()]

    window = build_window(since, until, types, timezone)
    previous = build_window(previous_since, previous_until, types, timezone)
    earlier = {row["agent_id"]: row["ratio"] for row in database.agent_totals(previous)}

    rows = []
    for row in database.agent_totals(window):
        points = formatting.delta_points(earlier.get(row["agent_id"]), row["ratio"])
        rows.append(
            ManagerRow(
                agent_id=row["agent_id"],
                name=row["display_name"],
                calls=row["calls"],
                score=formatting.percent(row["ratio"]),
                score_label=f"{formatting.percent(row['ratio'])}%",
                points=points,
                delta=formatting.delta_label(points),
                last_call=formatting.moment(row["last_call"], timezone),
                last_call_key=row["last_call"].timestamp() if row["last_call"] else 0,
            )
        )
    return rows


def filtered_rows(rows: list[ManagerRow], search: str) -> list[ManagerRow]:
    query = search.strip().casefold()
    if not query:
        return rows
    return [row for row in rows if query in row.name.casefold()]


def sorted_rows(rows: list[ManagerRow], column: str, descending: bool) -> list[ManagerRow]:
    keys = {
        SORT_NAME: lambda row: row.name.casefold(),
        SORT_CALLS: lambda row: row.calls,
        SORT_SCORE: lambda row: row.score,
        SORT_DELTA: lambda row: row.points,
        SORT_LAST_CALL: lambda row: row.last_call_key,
    }
    return sorted(rows, key=keys[column], reverse=descending)
