import reflex as rx

from src.components.common import (
    delta_text,
    kpi_card,
    period_picker,
    section_card,
    signed_count,
    transition_text,
)
from src.components.layout import page_layout
from src.constants import ROUTE_CALL
from src.state.dashboard import DashboardState

TITLE = "Дашборд"
KPI_PROCESSED = "Обработано звонков"
KPI_QUEUED = "В очереди обработки"
KPI_BEST = "Лучший менеджер"
KPI_WORST = "Худший менеджер"
CRITERIA_TITLE = "Изменение критериев"
QUEUE_TITLE = "Очередь обработки"
RECENT_TITLE = "Завершённые анализы"
TYPES_TITLE = "Типы звонков"
EMPTY_QUEUE = "Очередь пуста"
EMPTY_RECENT = "Пока нет завершённых анализов"
EMPTY_CRITERIA = "Нет оценённых звонков за период"
FAILED_LABEL = "с ошибкой"
PROGRESS_MAX = 100


def _kpi_row() -> rx.Component:
    return rx.hstack(
        kpi_card(
            KPI_PROCESSED,
            DashboardState.processed.to_string(),
            "circle-check",
            signed_count(DashboardState.processed_delta),
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
                ),
                rx.fragment(),
            ),
        ),
        kpi_card(KPI_BEST, DashboardState.best_manager, "trending-up",
                 rx.text(DashboardState.best_score, size="2", color_scheme="grass")),
        kpi_card(KPI_WORST, DashboardState.worst_manager, "trending-down",
                 rx.text(DashboardState.worst_score, size="2", color_scheme="tomato")),
        spacing="3",
        width="100%",
        wrap="wrap",
    )


def _criteria_row(entry) -> rx.Component:
    return rx.hstack(
        rx.text(entry.label, size="2", width="16rem", flex_shrink="0"),
        rx.progress(value=entry.after, max=PROGRESS_MAX, width="100%"),
        transition_text(entry.before, entry.after),
        delta_text(entry.points, entry.delta),
        spacing="3",
        align="center",
        width="100%",
    )


def _queue_row(row) -> rx.Component:
    return rx.table.row(
        rx.table.cell(rx.link(row.call_id, href=f"{ROUTE_CALL}/{row.call_id}")),
        rx.table.cell(row.started_at),
        rx.table.cell(row.agent_name),
        rx.table.cell(rx.badge(row.status_label, color_scheme=row.status_color)),
        rx.table.cell(rx.text(row.error, size="1", color_scheme="gray")),
    )


def _recent_row(row) -> rx.Component:
    return rx.table.row(
        rx.table.cell(rx.link(row.call_id, href=f"{ROUTE_CALL}/{row.call_id}")),
        rx.table.cell(row.finished_at),
        rx.table.cell(row.agent_name),
        rx.table.cell(rx.badge(row.score)),
    )


def _type_filters() -> rx.Component:
    return rx.hstack(
        rx.text(TYPES_TITLE, size="2", color_scheme="gray"),
        rx.foreach(
            DashboardState.available_types,
            lambda entry: rx.checkbox(
                entry.label,
                checked=DashboardState.selected_types.contains(entry.code),
                on_change=lambda checked: DashboardState.toggle_type(entry.code, checked),
                size="2",
            ),
        ),
        spacing="4",
        align="center",
        wrap="wrap",
    )


def dashboard_page() -> rx.Component:
    return page_layout(
        rx.vstack(
            rx.hstack(
                rx.heading(TITLE, size="7"),
                rx.spacer(),
                period_picker(DashboardState.period, DashboardState.set_period),
                width="100%",
                align="center",
            ),
            _type_filters(),
            _kpi_row(),
            section_card(
                CRITERIA_TITLE,
                rx.cond(
                    DashboardState.criteria_deltas.length() > 0,
                    rx.vstack(
                        rx.foreach(DashboardState.criteria_deltas, _criteria_row),
                        spacing="2",
                        width="100%",
                    ),
                    rx.text(EMPTY_CRITERIA, size="2", color_scheme="gray"),
                ),
            ),
            rx.hstack(
                section_card(
                    QUEUE_TITLE,
                    rx.cond(
                        DashboardState.queue_rows.length() > 0,
                        rx.table.root(
                            rx.table.body(
                                rx.foreach(DashboardState.queue_rows, _queue_row)
                            ),
                            width="100%",
                            size="1",
                        ),
                        rx.text(EMPTY_QUEUE, size="2", color_scheme="gray"),
                    ),
                ),
                section_card(
                    RECENT_TITLE,
                    rx.cond(
                        DashboardState.recent_rows.length() > 0,
                        rx.table.root(
                            rx.table.body(
                                rx.foreach(DashboardState.recent_rows, _recent_row)
                            ),
                            width="100%",
                            size="1",
                        ),
                        rx.text(EMPTY_RECENT, size="2", color_scheme="gray"),
                    ),
                ),
                spacing="3",
                width="100%",
                align="start",
            ),
            spacing="4",
            width="100%",
        ),
        on_mount=DashboardState.load,
    )
