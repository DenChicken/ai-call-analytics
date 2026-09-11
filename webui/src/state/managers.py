import logging
from dataclasses import dataclass

import reflex as rx

from src import context, formatting, urlstate
from src.constants import (
    PARAM_DESC,
    PARAM_PERIOD,
    PARAM_SEARCH,
    PARAM_SORT,
    PARAM_TYPES,
    PERIOD_BY_CODE,
    ROUTE_MANAGERS,
)
from src.database import build_window
from src.state.auth import AuthState, guarded
from src.state.period_filter import PeriodFilterState
from src.state.types_filter import TypesFilterState

logger = logging.getLogger(__name__)

SORT_NAME = "name"
SORT_CALLS = "calls"
SORT_ANALYZED = "analyzed"
SORT_SCORE = "score"
SORT_DELTA = "delta"
SORT_LAST_CALL = "last_call"

SORT_LABELS = {
    SORT_NAME: "Имя",
    SORT_CALLS: "Звонков",
    SORT_ANALYZED: "Проанализировано",
    SORT_SCORE: "Средний балл",
    SORT_DELTA: "Изменение",
    SORT_LAST_CALL: "Последний звонок",
}

DEFAULT_SORT = SORT_SCORE
DEFAULT_DESCENDING = True
DESCENDING_VALUES = {True: "1", False: "0"}


@dataclass
class ManagerRow:
    agent_id: int
    name: str
    calls: int
    analyzed: int
    score: float
    score_label: str
    points: int
    delta: str
    last_call: str
    last_call_key: float


class ManagersState(PeriodFilterState, TypesFilterState, AuthState):
    search: str = ""
    sort_by: str = DEFAULT_SORT
    descending: bool = DEFAULT_DESCENDING

    rows: list[ManagerRow] = []

    @rx.event
    def load(self):
        if not self.session_login:
            return AuthState.require_session
        self._load_types()
        self._read_url()
        self._refresh()

    def _types_changed(self):
        self._refresh()
        return self._sync_url()

    def _period_changed(self):
        self._refresh()
        return self._sync_url()

    @rx.event
    def set_search(self, value: str):
        self.search = value
        self._refresh()

    @rx.event
    def commit_search(self):
        return self._sync_url()

    @rx.event
    def sort(self, column: str):
        if self.sort_by == column:
            self.descending = not self.descending
        else:
            self.sort_by = column
            self.descending = column != SORT_NAME
        self._refresh()
        return self._sync_url()

    def _read_url(self) -> None:
        params = self.router.url.query_parameters
        self._read_period(params)
        self.search = urlstate.read(params, PARAM_SEARCH)
        self.sort_by = urlstate.read_choice(params, PARAM_SORT, SORT_LABELS, self.sort_by)
        self.descending = urlstate.read_flag(params, PARAM_DESC, self.descending)
        self._read_types(params)

    def _sync_url(self):
        return rx.redirect(
            urlstate.query(
                ROUTE_MANAGERS,
                {
                    PARAM_PERIOD: self.period,
                    PARAM_SEARCH: self.search,
                    PARAM_SORT: "" if self.sort_by == DEFAULT_SORT else self.sort_by,
                    PARAM_DESC: (
                        ""
                        if bool(self.descending) == DEFAULT_DESCENDING
                        else DESCENDING_VALUES[bool(self.descending)]
                    ),
                    PARAM_TYPES: self._types_param,
                },
            ),
            replace=True,
        )

    def _refresh(self) -> None:
        guarded(self, self._collect)

    def _collect(self) -> None:
        rows = collect(self.period, list(self.selected_types), self.utc_offset)
        self.rows = sorted_rows(
            filtered_rows(rows, self.search), self.sort_by, self.descending
        )


def collect(period: str, types: list[str], offset_hours: int) -> list[ManagerRow]:
    database = context.database()

    since, until = formatting.period_bounds(period, offset_hours)
    previous_since, previous_until = formatting.previous_bounds(since, until)

    bucket = PERIOD_BY_CODE[period].bucket
    window = build_window(since, until, types, bucket)
    previous = build_window(previous_since, previous_until, types, bucket)
    earlier = {row["agent_id"]: row["ratio"] for row in database.agent_totals(previous)}

    rows = []
    for row in database.agent_totals(window):
        points = formatting.delta_points(earlier.get(row["agent_id"]), row["ratio"])
        rows.append(
            ManagerRow(
                agent_id=row["agent_id"],
                name=row["display_name"],
                calls=row["calls"],
                analyzed=row["analyzed"],
                score=formatting.share(row["ratio"]),
                score_label=formatting.share_label(row["ratio"], row["analyzed"]),
                points=points,
                delta=formatting.delta_label(points),
                last_call=formatting.moment(row["last_call"], offset_hours),
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
        SORT_ANALYZED: lambda row: row.analyzed,
        SORT_SCORE: lambda row: row.score,
        SORT_DELTA: lambda row: row.points,
        SORT_LAST_CALL: lambda row: row.last_call_key,
    }
    return sorted(rows, key=keys[column], reverse=descending)
