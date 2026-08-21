import logging
from dataclasses import dataclass

import reflex as rx

from src import context, errors, formatting
from src.constants import (
    PERIOD_BY_LABEL,
    PERIOD_LABELS,
    DEFAULT_STATUS_COLOR,
    EMPTY_VALUE,
    PAGE_SIZES,
    PERIOD_MONTH,
    STATUS_COLORS,
    STATUS_LABELS,
    STATUS_ORDER,
    STATUSES_SUMMARY_TEMPLATE,
)
from src.database import build_filters
from src.state.auth import AuthState

logger = logging.getLogger(__name__)

ALL_AGENTS = "0"
ALL_AGENTS_LABEL = "Все менеджеры"
FIRST_PAGE = 1
PAGE_LABEL_TEMPLATE = "Страница {page} из {pages}, всего {total}"


@dataclass
class CallRow:
    call_id: int
    started_at: str
    analyzed_at: str
    agent_id: int
    agent_name: str
    client: str
    duration: str
    call_type: str
    score: str
    status_label: str
    status_color: str
    error: str


@dataclass
class AgentOption:
    value: str
    label: str


@dataclass
class StatusOption:
    code: str
    label: str


class CallsState(AuthState):
    period: str = PERIOD_MONTH
    agent_filter: str = ALL_AGENTS
    selected_statuses: list[str] = []
    page: int = FIRST_PAGE
    page_size: int = 0

    rows: list[CallRow] = []
    total: int = 0
    agents: list[AgentOption] = []
    statuses: list[StatusOption] = []

    @rx.event
    def load(self):
        if not self.session_login:
            return AuthState.require_session
        if not self.page_size:
            self.page_size = context.config().display.page_size
        if not self.statuses:
            self.statuses = [
                StatusOption(code=code, label=STATUS_LABELS[code]) for code in STATUS_ORDER
            ]
            self.selected_statuses = list(STATUS_ORDER)
        self.agents = [AgentOption(value=ALL_AGENTS, label=ALL_AGENTS_LABEL)] + [
            AgentOption(value=str(row["id"]), label=row["display_name"])
            for row in context.database().agents_with_calls()
        ]
        self._refresh()

    @rx.event
    def refresh(self):
        self._refresh()

    @rx.var
    def period_label(self) -> str:
        return PERIOD_LABELS[self.period]

    @rx.event
    def set_period(self, label: str):
        self.period = PERIOD_BY_LABEL.get(label, self.period)
        self.page = FIRST_PAGE
        self._refresh()

    @rx.event
    def set_agent_label(self, label: str):
        self.agent_filter = next(
            (entry.value for entry in self.agents if entry.label == label), ALL_AGENTS
        )
        self.page = FIRST_PAGE
        self._refresh()

    @rx.var
    def agent_label(self) -> str:
        return next(
            (entry.label for entry in self.agents if entry.value == self.agent_filter),
            ALL_AGENTS_LABEL,
        )

    @rx.var
    def statuses_summary(self) -> str:
        return STATUSES_SUMMARY_TEMPLATE.format(
            selected=len(self.selected_statuses), total=len(self.statuses)
        )

    @rx.event
    def toggle_status(self, code: str, enabled: bool):
        codes = {str(entry) for entry in self.selected_statuses}
        if enabled:
            codes.add(code)
        else:
            codes.discard(code)
        self.selected_statuses = [status for status in STATUS_ORDER if status in codes]
        self.page = FIRST_PAGE
        self._refresh()

    @rx.event
    def set_page_size(self, value: str):
        self.page_size = int(value)
        self.page = FIRST_PAGE
        self._refresh()

    @rx.event
    def go_to_page(self, page: int):
        self.page = max(FIRST_PAGE, min(page, self.pages))
        self._refresh()

    @rx.var
    def pages(self) -> int:
        if not self.page_size or not self.total:
            return FIRST_PAGE
        return -(-self.total // self.page_size)

    @rx.var
    def page_label(self) -> str:
        return PAGE_LABEL_TEMPLATE.format(page=self.page, pages=self.pages, total=self.total)

    @rx.var
    def page_size_options(self) -> list[str]:
        return [str(size) for size in PAGE_SIZES]

    def _refresh(self) -> None:
        rows, total = collect(
            self.period,
            self.agent_filter,
            list(self.selected_statuses),
            self.page,
            self.page_size,
            self.utc_offset,
        )
        self.rows = rows
        self.total = total


def collect(
    period: str,
    agent_filter: str,
    statuses: list[str],
    page: int,
    page_size: int,
    offset_hours: int,
) -> tuple[list[CallRow], int]:
    database = context.database()

    since, until = formatting.period_bounds(period, offset_hours)
    types = [row["code"] for row in database.call_types()]
    agent_id = int(agent_filter) if agent_filter != ALL_AGENTS else None
    filters = build_filters(since, until, types, agent_id, statuses or None)

    total = database.calls_list_count(filters)
    row_offset = (max(page, FIRST_PAGE) - 1) * page_size
    rows = [
        CallRow(
            call_id=row["id"],
            started_at=formatting.moment(row["started_at"], offset_hours),
            analyzed_at=formatting.moment(row["analyzed_at"], offset_hours),
            agent_id=row["agent_id"] or 0,
            agent_name=row["agent_name"] or EMPTY_VALUE,
            client=row["client_number"] or EMPTY_VALUE,
            duration=formatting.duration(row["duration_seconds"]),
            call_type=row["call_type_label"] or row["call_type"] or EMPTY_VALUE,
            score=formatting.fraction(row["met"], row["total"]),
            status_label=STATUS_LABELS.get(row["status"], row["status"] or EMPTY_VALUE),
            status_color=STATUS_COLORS.get(row["status"], DEFAULT_STATUS_COLOR),
            error=errors.describe(row["error_code"]),
        )
        for row in database.calls_list(filters, page_size, row_offset)
    ]
    return rows, total
