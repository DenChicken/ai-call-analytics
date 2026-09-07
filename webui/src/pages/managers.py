import reflex as rx

from src.components.common import (
    checkbox_menu,
    delta_text,
    empty_state,
    period_picker,
    scrollable_table,
    truncated,
)
from src.components.layout import page_layout, sticky_header
from src.constants import ROUTE_MANAGER, SECTION_MANAGERS, TYPES_LABEL
from src.state.managers import (
    SORT_ANALYZED,
    SORT_CALLS,
    SORT_DELTA,
    SORT_LABELS,
    SORT_LAST_CALL,
    SORT_NAME,
    SORT_SCORE,
    ManagersState,
)

TITLE = SECTION_MANAGERS
SEARCH_PLACEHOLDER = "Поиск менеджера"
EMPTY_MESSAGE = "За выбранный период нет звонков"
SEARCH_WIDTH = "18rem"
SORT_ICON_SIZE = 14
NAME_MAX_WIDTH = "16rem"

COLUMNS = (
    (SORT_NAME, "left"),
    (SORT_CALLS, "right"),
    (SORT_ANALYZED, "right"),
    (SORT_SCORE, "right"),
    (SORT_DELTA, "right"),
    (SORT_LAST_CALL, "right"),
)


def _header_cell(column: str, align: str) -> rx.Component:
    return rx.table.column_header_cell(
        rx.hstack(
            rx.text(SORT_LABELS[column], size="2"),
            rx.cond(
                ManagersState.sort_by == column,
                rx.icon(
                    rx.cond(ManagersState.descending, "chevron-down", "chevron-up"),
                    size=SORT_ICON_SIZE,
                ),
                rx.fragment(),
            ),
            spacing="1",
            align="center",
            justify="end" if align == "right" else "start",
        ),
        on_click=ManagersState.sort(column),
        cursor="pointer",
    )


def _row(row) -> rx.Component:
    return rx.table.row(
        rx.table.cell(
            rx.link(
                truncated(row.name, size="2", max_width=NAME_MAX_WIDTH),
                href=f"{ROUTE_MANAGER}/{row.agent_id}",
            ),
        ),
        rx.table.cell(row.calls, text_align="right"),
        rx.table.cell(row.analyzed, text_align="right"),
        rx.table.cell(row.score_label, text_align="right"),
        rx.table.cell(delta_text(row.points, row.delta), text_align="right"),
        rx.table.cell(
            rx.text(row.last_call, size="2"), text_align="right"
        ),
    )


def managers_page() -> rx.Component:
    return page_layout(
        rx.vstack(
            rx.cond(
                ManagersState.rows.length() > 0,
                scrollable_table(
                    rx.table.header(
                        rx.table.row(
                            *[_header_cell(column, align) for column, align in COLUMNS]
                        )
                    ),
                    rx.table.body(rx.foreach(ManagersState.rows, _row)),
                ),
                empty_state(EMPTY_MESSAGE),
            ),
            spacing="4",
            width="100%",
        ),
        header=sticky_header(
            rx.heading(TITLE, size="6"),
            rx.input(
                placeholder=SEARCH_PLACEHOLDER,
                value=ManagersState.search,
                on_change=ManagersState.set_search,
                on_blur=ManagersState.commit_search,
                width=SEARCH_WIDTH,
                size="1",
            ),
            rx.spacer(),
            checkbox_menu(
                TYPES_LABEL,
                ManagersState.types_summary,
                ManagersState.available_types,
                lambda entry: ManagersState.selected_types.contains(entry.code),
                lambda entry, value: ManagersState.toggle_type(entry.code, value),
            ),
            period_picker(ManagersState.period_label, ManagersState.set_period),
        ),
        on_mount=ManagersState.load,
    )
