import reflex as rx

from src.components.common import (
    checkbox_menu,
    empty_state,
    kpi_card,
    period_picker,
    refresh_button,
    scrollable_table,
    section_card,
    signed_count,
    status_badge,
    truncated,
)
from src.components.layout import page_layout, sticky_header
from src.constants import (
    ROUTE_CALL,
    ROUTE_CALLS,
    ROUTE_MANAGER,
    SECTION_DASHBOARD,
    SHARE_MAX,
)
from src.state.dashboard import (
    CHART_AFTER_KEY,
    CHART_BEFORE_KEY,
    CHART_LABEL_KEY,
    DashboardState,
)

TITLE = SECTION_DASHBOARD
KPI_PROCESSED = "Звонков за период"
KPI_ANALYZED = "Проанализировано"
KPI_QUEUED = "В очереди"
KPI_BEST = "Лучший менеджер"
KPI_WORST = "Худший менеджер"
CRITERIA_TITLE = "Изменение критериев"
QUEUE_TITLE = "Очередь обработки"
RECENT_TITLE = "Завершённые анализы"
TYPES_LABEL = "Типы звонков"
ALL_CALLS_LABEL = "Все звонки"
EMPTY_QUEUE = "Очередь пуста"
EMPTY_RECENT = "Нет завершённых анализов"
EMPTY_CRITERIA = "Нет оценённых звонков за период"
FAILED_LABEL = "с ошибкой"

CHART_BAR_BEFORE = "var(--gray-8)"
CHART_BAR_AFTER = "var(--accent-9)"
LEGEND_BEFORE = "Прошлый период"
LEGEND_AFTER = "Текущий период"
EXPAND_CRITERIA_LABEL = "Показать все"
COLLAPSE_CRITERIA_LABEL = "Свернуть"
CHART_LABEL_WIDTH = 180
CHART_BAR_SIZE = 12
CHART_CATEGORY_GAP = 18
CHART_BAR_GAP = 2
TICK_COUNT = 6
CHART_MARGIN = {"left": 10, "right": 20}
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
                rx.text(
                    f"{DashboardState.failed} {FAILED_LABEL}",
                    size="2",
                    color_scheme="tomato",
                    white_space="nowrap",
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
    return rx.cond(
        DashboardState.criteria_chart.length() > 0,
        rx.vstack(
            rx.recharts.bar_chart(
                rx.recharts.bar(
                    data_key=CHART_BEFORE_KEY,
                    fill=CHART_BAR_BEFORE,
                    name=LEGEND_BEFORE,
                    bar_size=CHART_BAR_SIZE,
                ),
                rx.recharts.bar(
                    data_key=CHART_AFTER_KEY,
                    fill=CHART_BAR_AFTER,
                    name=LEGEND_AFTER,
                    bar_size=CHART_BAR_SIZE,
                ),
                rx.recharts.x_axis(
                    type_="number", domain=[0, SHARE_MAX], tick_count=TICK_COUNT
                ),
                rx.recharts.y_axis(
                    data_key=CHART_LABEL_KEY,
                    type_="category",
                    width=CHART_LABEL_WIDTH,
                    interval=0,
                ),
                rx.recharts.graphing_tooltip(),
                rx.recharts.legend(),
                rx.recharts.cartesian_grid(stroke_dasharray="3 3", horizontal=False),
                data=DashboardState.visible_criteria,
                layout="vertical",
                bar_category_gap=CHART_CATEGORY_GAP,
                bar_gap=CHART_BAR_GAP,
                height=DashboardState.criteria_chart_height,
                width="100%",
                margin=CHART_MARGIN,
            ),
            rx.cond(
                DashboardState.criteria_hidden_count > 0,
                rx.button(
                    rx.icon(
                        rx.cond(
                            DashboardState.criteria_expanded, "chevron-up", "chevron-down"
                        ),
                        size=LINK_ICON_SIZE,
                    ),
                    rx.cond(
                        DashboardState.criteria_expanded,
                        rx.text(COLLAPSE_CRITERIA_LABEL, size="1"),
                        rx.text(
                            f"{EXPAND_CRITERIA_LABEL} ({DashboardState.criteria_hidden_count})",
                            size="1",
                        ),
                    ),
                    on_click=DashboardState.toggle_criteria,
                    variant="ghost",
                    size="1",
                    color_scheme="gray",
                ),
                rx.fragment(),
            ),
            spacing="2",
            width="100%",
            align="center",
        ),
        empty_state(EMPTY_CRITERIA),
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
                        _all_calls_link(),
                        refresh_button(DashboardState.refresh),
                        spacing="2",
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
