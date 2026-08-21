import reflex as rx

from src.components.common import kpi_card, period_picker, section_card
from src.components.layout import page_layout
from src.constants import ROUTE_CALL, ROUTE_MANAGERS
from src.state.manager import (
    CHART_DAY_KEY,
    CHART_LABEL_KEY,
    CHART_SCORE_KEY,
    ManagerState,
)

KPI_SCORE = "Средний балл за период"
KPI_CALLS = "Звонков"
KPI_BEST = "Лучший разговор"
KPI_WORST = "Худший разговор"
TREND_TITLE = "Изменение среднего балла"
RADAR_TITLE = "Радар по критериям"
CRITERIA_TITLE = "Средние оценки по критериям"
CALLS_TITLE = "Разговоры"
EMPTY_TREND = "Нет данных за период"
EMPTY_CALLS = "За период нет звонков"
BACK_LABEL = "К списку менеджеров"

CHART_HEIGHT = 260
PROGRESS_MAX = 100
RADAR_OPACITY = 0.5
BACK_ICON_SIZE = 16

COLUMNS = ("Дата", "Клиент", "Длительность", "Балл", "Тип")


def _header() -> rx.Component:
    return rx.vstack(
        rx.link(
            rx.hstack(
                rx.icon("arrow-left", size=BACK_ICON_SIZE),
                rx.text(BACK_LABEL, size="2"),
                spacing="2",
                align="center",
            ),
            href=ROUTE_MANAGERS,
            underline="none",
            color_scheme="gray",
        ),
        rx.hstack(
            rx.vstack(
                rx.heading(ManagerState.name, size="7"),
                rx.cond(
                    ManagerState.email != "",
                    rx.text(ManagerState.email, size="2", color_scheme="gray"),
                    rx.fragment(),
                ),
                spacing="1",
                align="start",
            ),
            rx.spacer(),
            period_picker(ManagerState.period, ManagerState.set_period),
            width="100%",
            align="center",
        ),
        spacing="3",
        width="100%",
        align="start",
    )


def _kpi_row() -> rx.Component:
    return rx.hstack(
        kpi_card(KPI_SCORE, ManagerState.score, "target"),
        kpi_card(KPI_CALLS, ManagerState.calls.to_string(), "phone"),
        kpi_card(
            KPI_BEST,
            ManagerState.best_call,
            "trending-up",
            rx.cond(
                ManagerState.best_call_id > 0,
                rx.link(
                    rx.text("открыть", size="1"),
                    href=f"{ROUTE_CALL}/{ManagerState.best_call_id}",
                ),
                rx.fragment(),
            ),
        ),
        kpi_card(
            KPI_WORST,
            ManagerState.worst_call,
            "trending-down",
            rx.cond(
                ManagerState.worst_call_id > 0,
                rx.link(
                    rx.text("открыть", size="1"),
                    href=f"{ROUTE_CALL}/{ManagerState.worst_call_id}",
                ),
                rx.fragment(),
            ),
        ),
        spacing="3",
        width="100%",
        wrap="wrap",
    )


def _trend_chart() -> rx.Component:
    return rx.cond(
        ManagerState.trend.length() > 0,
        rx.recharts.line_chart(
            rx.recharts.line(
                data_key=CHART_SCORE_KEY,
                stroke="var(--accent-9)",
                type_="monotone",
                connect_nulls=False,
            ),
            rx.recharts.x_axis(data_key=CHART_DAY_KEY),
            rx.recharts.y_axis(domain=[0, PROGRESS_MAX]),
            rx.recharts.graphing_tooltip(),
            rx.recharts.cartesian_grid(stroke_dasharray="3 3"),
            data=ManagerState.trend,
            height=CHART_HEIGHT,
            width="100%",
        ),
        rx.text(EMPTY_TREND, size="2", color_scheme="gray"),
    )


def _radar_chart() -> rx.Component:
    return rx.recharts.radar_chart(
        rx.recharts.radar(
            data_key=CHART_SCORE_KEY,
            stroke="var(--accent-9)",
            fill="var(--accent-8)",
            fill_opacity=RADAR_OPACITY,
        ),
        rx.recharts.polar_grid(),
        rx.recharts.polar_angle_axis(data_key=CHART_LABEL_KEY),
        data=ManagerState.radar,
        height=CHART_HEIGHT,
        width="100%",
    )


def _criterion_row(entry) -> rx.Component:
    return rx.hstack(
        rx.text(entry.label, size="2", width="14rem", flex_shrink="0"),
        rx.progress(value=entry.score, max=PROGRESS_MAX, width="100%"),
        rx.text(entry.score_label, size="2", width="3rem", text_align="right"),
        spacing="3",
        align="center",
        width="100%",
    )


def _call_row(row) -> rx.Component:
    return rx.table.row(
        rx.table.cell(rx.link(row.started_at, href=f"{ROUTE_CALL}/{row.call_id}")),
        rx.table.cell(row.client),
        rx.table.cell(row.duration),
        rx.table.cell(rx.badge(row.score)),
        rx.table.cell(row.call_type),
    )


def manager_page() -> rx.Component:
    return page_layout(
        rx.vstack(
            _header(),
            _kpi_row(),
            rx.hstack(
                section_card(TREND_TITLE, _trend_chart()),
                section_card(RADAR_TITLE, _radar_chart()),
                spacing="3",
                width="100%",
                align="start",
                wrap="wrap",
            ),
            section_card(
                CRITERIA_TITLE,
                rx.vstack(
                    rx.foreach(ManagerState.criteria, _criterion_row),
                    spacing="2",
                    width="100%",
                ),
            ),
            section_card(
                CALLS_TITLE,
                rx.cond(
                    ManagerState.calls_rows.length() > 0,
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(
                                *[rx.table.column_header_cell(name) for name in COLUMNS]
                            )
                        ),
                        rx.table.body(rx.foreach(ManagerState.calls_rows, _call_row)),
                        width="100%",
                        size="2",
                    ),
                    rx.text(EMPTY_CALLS, size="2", color_scheme="gray"),
                ),
            ),
            spacing="4",
            width="100%",
        ),
        on_mount=ManagerState.load,
    )
