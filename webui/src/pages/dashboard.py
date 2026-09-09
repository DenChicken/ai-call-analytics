import reflex as rx

from src.components.charts import criteria_deltas_chart, top_managers_chart
from src.components.common import (
    HINT_CURSOR,
    checkbox_menu,
    empty_state,
    hint_icon,
    kpi_card,
    period_picker,
    rank_picker,
    refresh_button,
    scrollable_table,
    section_card,
    signed_count,
    status_badge,
    truncated,
)
from src.components.layout import page_layout, sticky_header
from src.constants import (
    ALL_CALLS_LABEL,
    MIN_ANALYZED_CALLS,
    MIN_ANALYZED_LABEL,
    RANK_HINTS,
    RANK_HINT_TITLE,
    ROUTE_CALL,
    ROUTE_CALLS,
    ROUTE_MANAGER,
    SECTION_DASHBOARD,
    TYPES_LABEL,
)
from src.state.dashboard import CHART_NAME_KEY, CHART_SCORE_KEY, DashboardState

TITLE = SECTION_DASHBOARD
TOP_MANAGERS_TITLE = "Лучшие менеджеры"
EMPTY_TOP_MANAGERS = "Нет оценённых звонков за период"
KPI_PROCESSED = "Состоялось звонков"
KPI_ANALYZED = "Проанализировано"
KPI_QUEUED = "В очереди"
KPI_BEST = "Лучший менеджер"
KPI_WORST = "Худший менеджер"
CRITERIA_TITLE = "Изменение критериев"
QUEUE_TITLE = "Очередь обработки"
RECENT_TITLE = "Завершённые анализы"
EMPTY_QUEUE = "Очередь пуста"
SHOW_FAILED_LABEL = "С ошибками"
EMPTY_RECENT = "Нет завершённых анализов"
EMPTY_CRITERIA = "Нет оценённых звонков за период"
FAILED_LABEL = "пропущено:"
FAILED_HINT = (
    "Звонки, которые не удалось проанализировать. "
    "Причина указана в статусе звонка."
)

LINK_ICON_SIZE = 14
NAME_MAX_WIDTH = "9rem"


def _header() -> rx.Component:
    return sticky_header(
        rx.heading(TITLE, size="6"),
        rx.spacer(),
        checkbox_menu(
            TYPES_LABEL,
            DashboardState.types_summary,
            DashboardState.available_types,
            lambda entry: DashboardState.selected_types.contains(entry.code),
            lambda entry, value: DashboardState.toggle_type(entry.code, value),
        ),
        period_picker(DashboardState.period_label, DashboardState.set_period),
    )


def _manager_kpi(title: str, name: rx.Var, manager_id: rx.Var, score: rx.Var, icon: str,
                 color: str) -> rx.Component:
    return kpi_card(
        title,
        rx.cond(
            manager_id > 0,
            rx.link(
                truncated(name, size="6", weight="bold", max_width=NAME_MAX_WIDTH),
                href=f"{ROUTE_MANAGER}/{manager_id}",
                underline="none",
                color="inherit",
            ),
            rx.heading(name, size="7"),
        ),
        icon,
        rx.cond(
            score != "",
            rx.text(score, size="2", color_scheme=color, white_space="nowrap"),
            rx.fragment(),
        ),
    )


def _kpi_row() -> rx.Component:
    return rx.hstack(
        kpi_card(
            KPI_PROCESSED,
            DashboardState.processed.to_string(),
            "phone",
            signed_count(DashboardState.processed_delta),
        ),
        kpi_card(
            KPI_ANALYZED,
            DashboardState.analyzed_today.to_string(),
            "circle-check",
        ),
        kpi_card(
            KPI_QUEUED,
            DashboardState.queued.to_string(),
            "inbox",
            rx.cond(
                DashboardState.failed > 0,
                rx.tooltip(
                    rx.text(
                        f"{FAILED_LABEL} {DashboardState.failed}",
                        size="2",
                        color_scheme="gray",
                        white_space="nowrap",
                        cursor=HINT_CURSOR,
                    ),
                    content=FAILED_HINT,
                ),
                rx.fragment(),
            ),
        ),
        _manager_kpi(
            KPI_BEST,
            DashboardState.best_manager,
            DashboardState.best_manager_id,
            DashboardState.best_score,
            "trending-up",
            "grass",
        ),
        _manager_kpi(
            KPI_WORST,
            DashboardState.worst_manager,
            DashboardState.worst_manager_id,
            DashboardState.worst_score,
            "trending-down",
            "tomato",
        ),
        spacing="3",
        width="100%",
        wrap="wrap",
        align="stretch",
    )


def _criteria_chart() -> rx.Component:
    return criteria_deltas_chart(DashboardState, EMPTY_CRITERIA)


def _top_managers_chart() -> rx.Component:
    return top_managers_chart(
        DashboardState, CHART_NAME_KEY, CHART_SCORE_KEY, EMPTY_TOP_MANAGERS
    )


def _top_managers_actions() -> rx.Component:
    return rx.hstack(
        rx.checkbox(
            MIN_ANALYZED_LABEL.format(count=MIN_ANALYZED_CALLS),
            checked=DashboardState.min_calls_only,
            on_change=DashboardState.toggle_min_calls,
            size="1",
        ),
        rank_picker(DashboardState.rank_label, DashboardState.set_rank_mode),
        hint_icon(RANK_HINT_TITLE, RANK_HINTS),
        spacing="3",
        align="center",
    )


def _manager_link(name: rx.Var, manager_id: rx.Var) -> rx.Component:
    return rx.cond(
        manager_id > 0,
        rx.link(
            truncated(name, size="2", max_width=NAME_MAX_WIDTH),
            href=f"{ROUTE_MANAGER}/{manager_id}",
        ),
        truncated(name, size="2", max_width=NAME_MAX_WIDTH),
    )


def _queue_row(row) -> rx.Component:
    return rx.table.row(
        rx.table.cell(
            rx.link(
                rx.text(row.started_at, size="2"),
                href=f"{ROUTE_CALL}/{row.call_id}",
            )
        ),
        rx.table.cell(_manager_link(row.agent_name, row.agent_id)),
        rx.table.cell(rx.text(row.client, size="2")),
        rx.table.cell(status_badge(row.status_label, row.status_color, row.error)),
    )


def _recent_row(row) -> rx.Component:
    return rx.table.row(
        rx.table.cell(
            rx.link(
                rx.text(row.started_at, size="2"),
                href=f"{ROUTE_CALL}/{row.call_id}",
            )
        ),
        rx.table.cell(rx.text(row.analyzed_at, size="2")),
        rx.table.cell(_manager_link(row.agent_name, row.agent_id)),
        rx.table.cell(rx.badge(row.score)),
    )


def _all_calls_link() -> rx.Component:
    return rx.link(
        rx.hstack(
            rx.text(ALL_CALLS_LABEL, size="1"),
            rx.icon("arrow-right", size=LINK_ICON_SIZE),
            spacing="1",
            align="center",
        ),
        href=ROUTE_CALLS,
        underline="none",
        color_scheme="gray",
    )


def _table(rows, columns: tuple, builder, empty: str) -> rx.Component:
    return rx.cond(
        rows.length() > 0,
        scrollable_table(
            rx.table.header(
                rx.table.row(*[rx.table.column_header_cell(name) for name in columns])
            ),
            rx.table.body(rx.foreach(rows, builder)),
        ),
        empty_state(empty),
    )


def dashboard_page() -> rx.Component:
    return page_layout(
        rx.vstack(
            _kpi_row(),
            section_card(
                TOP_MANAGERS_TITLE,
                _top_managers_chart(),
                actions=_top_managers_actions(),
            ),
            section_card(CRITERIA_TITLE, _criteria_chart()),
            rx.hstack(
                section_card(
                    QUEUE_TITLE,
                    _table(
                        DashboardState.queue_rows,
                        ("Звонок", "Менеджер", "Клиент", "Статус"),
                        _queue_row,
                        EMPTY_QUEUE,
                    ),
                    actions=rx.hstack(
                        rx.checkbox(
                            SHOW_FAILED_LABEL,
                            checked=DashboardState.queue_failed,
                            on_change=DashboardState.toggle_queue_failed,
                            size="1",
                        ),
                        _all_calls_link(),
                        refresh_button(DashboardState.refresh),
                        spacing="3",
                        align="center",
                    ),
                ),
                section_card(
                    RECENT_TITLE,
                    _table(
                        DashboardState.recent_rows,
                        ("Звонок", "Анализ", "Менеджер", "Балл"),
                        _recent_row,
                        EMPTY_RECENT,
                    ),
                    actions=rx.hstack(
                        _all_calls_link(),
                        refresh_button(DashboardState.refresh),
                        spacing="2",
                        align="center",
                    ),
                ),
                spacing="3",
                width="100%",
                align="stretch",
            ),
            spacing="4",
            width="100%",
        ),
        header=_header(),
        on_mount=DashboardState.load,
    )
