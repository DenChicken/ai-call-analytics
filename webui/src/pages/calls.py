import reflex as rx

from src.components.common import (
    SELECT_POSITION,
    checkbox_menu,
    empty_state,
    period_picker,
    refresh_button,
    scrollable_table,
    status_badge,
    truncated,
)
from src.components.layout import page_layout, sticky_header
from src.constants import (
    ROUTE_CALL,
    ROUTE_MANAGER,
    SECTION_CALLS,
    STATUSES_LABEL,
    TYPES_LABEL,
)
from src.state.calls import CallsState

TITLE = SECTION_CALLS
EMPTY_MESSAGE = "Нет звонков по выбранным фильтрам"
PAGE_SIZE_LABEL = "На странице"
PREVIOUS_LABEL = "Назад"
NEXT_LABEL = "Вперёд"
FIRST_PAGE_HINT = "Первая страница"
LAST_PAGE_HINT = "Последняя страница"
GO_TO_PAGE_PLACEHOLDER = "№"
GO_TO_PAGE_WIDTH = "4.5rem"
GO_TO_PAGE_ELEMENT_ID = "calls-page-input"
ENTER_KEY = "Enter"
BLUR_SCRIPT = "document.getElementById('{element}')?.blur()"
NAME_MAX_WIDTH = "11rem"
AGENT_SELECT_WIDTH = "14rem"
NAV_ICON_SIZE = 14

COLUMNS = ("Звонок", "Анализ", "Менеджер", "Клиент", "Длит.", "Тип", "Балл", "Статус")


def _header() -> rx.Component:
    return sticky_header(
        rx.heading(TITLE, size="6"),
        rx.spacer(),
        rx.select(
            CallsState.agents.map(lambda entry: entry.label),
            value=CallsState.agent_label,
            on_change=CallsState.set_agent_label,
            size="1",
            width=AGENT_SELECT_WIDTH,
            position=SELECT_POSITION,
        ),
        _type_filters(),
        _status_filters(),
        period_picker(CallsState.period_label, CallsState.set_period),
        refresh_button(CallsState.refresh),
    )


def _type_filters() -> rx.Component:
    return checkbox_menu(
        TYPES_LABEL,
        CallsState.types_summary,
        CallsState.available_types,
        lambda entry: CallsState.selected_types.contains(entry.code),
        lambda entry, value: CallsState.toggle_type(entry.code, value),
        CallsState.apply_types,
    )


def _status_filters() -> rx.Component:
    return checkbox_menu(
        STATUSES_LABEL,
        CallsState.statuses_summary,
        CallsState.statuses,
        lambda entry: CallsState.selected_statuses.contains(entry.code),
        lambda entry, value: CallsState.toggle_status(entry.code, value),
        CallsState.apply_statuses,
    )


def _row(row) -> rx.Component:
    return rx.table.row(
        rx.table.cell(
            rx.link(
                rx.text(row.started_at, size="2"),
                href=f"{ROUTE_CALL}/{row.call_id}",
            )
        ),
        rx.table.cell(rx.text(row.analyzed_at, size="2")),
        rx.table.cell(
            rx.cond(
                row.agent_id > 0,
                rx.link(
                    truncated(row.agent_name, size="2", max_width=NAME_MAX_WIDTH),
                    href=f"{ROUTE_MANAGER}/{row.agent_id}",
                ),
                truncated(row.agent_name, size="2", max_width=NAME_MAX_WIDTH),
            )
        ),
        rx.table.cell(rx.text(row.client, size="2")),
        rx.table.cell(rx.text(row.duration, size="2")),
        rx.table.cell(rx.text(row.call_type, size="2")),
        rx.table.cell(rx.badge(row.score)),
        rx.table.cell(status_badge(row.status_label, row.status_color, row.error)),
    )


def _pagination() -> rx.Component:
    return rx.hstack(
        rx.text(PAGE_SIZE_LABEL, size="1", color_scheme="gray"),
        rx.select(
            CallsState.page_size_options,
            value=CallsState.page_size.to_string(),
            on_change=CallsState.set_page_size,
            size="1",
        ),
        rx.spacer(),
        rx.text(CallsState.page_label, size="1", color_scheme="gray"),
        rx.input(
            placeholder=GO_TO_PAGE_PLACEHOLDER,
            id=GO_TO_PAGE_ELEMENT_ID,
            on_blur=CallsState.go_to_typed_page,
            on_key_down=lambda key: rx.cond(
                key == ENTER_KEY,
                rx.call_script(BLUR_SCRIPT.format(element=GO_TO_PAGE_ELEMENT_ID)),
                rx.noop(),
            ),
            width=GO_TO_PAGE_WIDTH,
            size="1",
        ),
        rx.tooltip(
            rx.button(
                rx.icon("chevrons-left", size=NAV_ICON_SIZE),
                on_click=CallsState.go_to_page(1),
                disabled=CallsState.page <= 1,
                variant="soft",
                size="1",
            ),
            content=FIRST_PAGE_HINT,
        ),
        rx.button(
            rx.icon("chevron-left", size=NAV_ICON_SIZE),
            PREVIOUS_LABEL,
            on_click=CallsState.go_to_page(CallsState.page - 1),
            disabled=CallsState.page <= 1,
            variant="soft",
            size="1",
        ),
        rx.button(
            NEXT_LABEL,
            rx.icon("chevron-right", size=NAV_ICON_SIZE),
            on_click=CallsState.go_to_page(CallsState.page + 1),
            disabled=CallsState.page >= CallsState.pages,
            variant="soft",
            size="1",
        ),
        rx.tooltip(
            rx.button(
                rx.icon("chevrons-right", size=NAV_ICON_SIZE),
                on_click=CallsState.go_to_page(CallsState.pages),
                disabled=CallsState.page >= CallsState.pages,
                variant="soft",
                size="1",
            ),
            content=LAST_PAGE_HINT,
        ),
        spacing="3",
        align="center",
        width="100%",
    )


def calls_page() -> rx.Component:
    return page_layout(
        rx.vstack(
            rx.cond(
                CallsState.rows.length() > 0,
                rx.card(
                    scrollable_table(
                        rx.table.header(
                            rx.table.row(
                                *[rx.table.column_header_cell(name) for name in COLUMNS]
                            )
                        ),
                        rx.table.body(rx.foreach(CallsState.rows, _row)),
                    ),
                    width="100%",
                ),
                empty_state(EMPTY_MESSAGE),
            ),
            _pagination(),
            spacing="4",
            width="100%",
        ),
        header=_header(),
        on_mount=CallsState.load,
    )
