import reflex as rx

from src.components.common import (
    empty_state,
    kpi_card,
    period_picker,
    scrollable_table,
    section_card,
    truncated,
)
from src.components.layout import page_layout, sticky_header
from src.constants import ROUTE_CALL, ROUTE_MANAGERS, SHARE_MAX
from src.state.manager import (
    CHART_DAY_KEY,
    CHART_LABEL_KEY,
    CHART_SCORE_KEY,
    ManagerState,
)

KPI_SCORE = "Средний балл"
KPI_CALLS = "Звонков"
KPI_BEST = "Лучший разговор"
KPI_WORST = "Худший разговор"
TREND_TITLE = "Средний балл по дням"
CRITERIA_TREND_TITLE = "Критерии по дням"
RADAR_TITLE = "Критерии за период"
CRITERIA_TITLE = "Средние оценки за период"
CALLS_TITLE = "Разговоры"
EMPTY_TREND = "Нет данных за период"
EMPTY_CALLS = "За период нет звонков"
CRM_LABEL = "Профиль в CRM"
OPEN_LABEL = "открыть"

CHART_HEIGHT = 260
CRITERIA_CHART_HEIGHT = 320
CRITERIA_BAR_SIZE = 16
CRITERIA_LABEL_WIDTH = 200
CHART_MARGIN = {"left": 10, "right": 20}
TICK_COUNT = 6
RADAR_OPACITY = 0.5
RADAR_OUTER_RADIUS = "78%"
RADAR_HEIGHT = 340
RADAR_LEGEND_WIDTH = "22rem"
LEGEND_ROW_PADDING = "0.2rem 0.25rem"
LEGEND_NUMBER_WIDTH = "1.4rem"
LEGEND_SCROLLBAR_GUTTER = "0.75rem"
BACK_ICON_SIZE = 16
CRM_ICON_SIZE = 14
NAME_MAX_WIDTH = "22rem"
BAR_COLOR = "var(--accent-9)"
LEGEND_WIDTH = "13rem"
LEGEND_DOT_SIZE = "0.6rem"
LEGEND_HIDDEN_OPACITY = 0.55
SHOW_ALL_LABEL = "Все"
HIDE_ALL_LABEL = "Ничего"
TOGGLE_TEXT_STYLE = {
    "overflow": "hidden",
    "text_overflow": "ellipsis",
    "white_space": "nowrap",
}

COLUMNS = ("Дата", "Клиент", "Длительность", "Балл", "Тип")


def _header() -> rx.Component:
    return sticky_header(
        rx.link(
            rx.icon("arrow-left", size=BACK_ICON_SIZE),
            href=ROUTE_MANAGERS,
            color_scheme="gray",
        ),
        truncated(ManagerState.name, size="5", weight="bold", max_width=NAME_MAX_WIDTH),
        rx.cond(
            ManagerState.profile_link != "",
            rx.link(
                rx.hstack(
                    rx.icon("external-link", size=CRM_ICON_SIZE),
                    rx.text(CRM_LABEL, size="1"),
                    spacing="1",
                    align="center",
                ),
                href=ManagerState.profile_link,
                is_external=True,
                underline="none",
                color_scheme="gray",
            ),
            rx.fragment(),
        ),
        rx.spacer(),
        period_picker(ManagerState.period_label, ManagerState.set_period),
    )


def _call_link(label: rx.Var, call_id: rx.Var) -> rx.Component:
    return rx.cond(
        call_id > 0,
        rx.link(rx.text(OPEN_LABEL, size="1"), href=f"{ROUTE_CALL}/{call_id}"),
        rx.fragment(),
    )


def _kpi_row() -> rx.Component:
    return rx.hstack(
        kpi_card(KPI_SCORE, ManagerState.score, "target"),
        kpi_card(KPI_CALLS, ManagerState.calls.to_string(), "phone"),
        kpi_card(
            KPI_BEST,
            ManagerState.best_call,
            "trending-up",
            _call_link(ManagerState.best_call, ManagerState.best_call_id),
        ),
        kpi_card(
            KPI_WORST,
            ManagerState.worst_call,
            "trending-down",
            _call_link(ManagerState.worst_call, ManagerState.worst_call_id),
        ),
        spacing="3",
        width="100%",
        wrap="wrap",
        align="stretch",
    )


def _score_chart() -> rx.Component:
    return rx.cond(
        ManagerState.trend.length() > 0,
        rx.recharts.bar_chart(
            rx.recharts.bar(data_key=CHART_SCORE_KEY, fill=BAR_COLOR),
            rx.recharts.x_axis(data_key=CHART_DAY_KEY),
            rx.recharts.y_axis(domain=[0, SHARE_MAX], tick_count=TICK_COUNT),
            rx.recharts.graphing_tooltip(),
            rx.recharts.cartesian_grid(stroke_dasharray="3 3", vertical=False),
            data=ManagerState.trend,
            height=CHART_HEIGHT,
            width="100%",
        ),
        empty_state(EMPTY_TREND),
    )


def _line_toggle(line) -> rx.Component:
    hidden = ManagerState.hidden_lines.contains(line.code)
    return rx.hstack(
        rx.box(
            width=LEGEND_DOT_SIZE,
            height=LEGEND_DOT_SIZE,
            border_radius="50%",
            background=rx.cond(hidden, "var(--gray-6)", line.color),
            flex_shrink="0",
        ),
        rx.text(
            line.label,
            size="1",
            color=rx.cond(hidden, "var(--gray-9)", "var(--gray-12)"),
            **TOGGLE_TEXT_STYLE,
        ),
        on_click=ManagerState.toggle_line(line.code),
        spacing="2",
        align="center",
        width="100%",
        padding="0.25rem 0.5rem",
        border_radius="var(--radius-2)",
        cursor="pointer",
        opacity=rx.cond(hidden, LEGEND_HIDDEN_OPACITY, 1),
        _hover={"background": "var(--gray-a3)"},
    )


def _line_panel() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.button(
                SHOW_ALL_LABEL,
                on_click=ManagerState.show_all_lines,
                variant="ghost",
                size="1",
                color_scheme="gray",
            ),
            rx.button(
                HIDE_ALL_LABEL,
                on_click=ManagerState.hide_all_lines,
                variant="ghost",
                size="1",
                color_scheme="gray",
            ),
            spacing="2",
            width="100%",
        ),
        rx.scroll_area(
            rx.vstack(
                rx.foreach(ManagerState.criteria_lines, _line_toggle),
                spacing="0",
                width="100%",
            ),
            height=CRITERIA_CHART_HEIGHT,
            type="auto",
            scrollbars="vertical",
            width="100%",
        ),
        spacing="2",
        width=LEGEND_WIDTH,
        flex_shrink="0",
    )


def _criteria_chart() -> rx.Component:
    return rx.cond(
        ManagerState.criteria_trend.length() > 0,
        rx.hstack(
            rx.box(
                rx.recharts.line_chart(
                    rx.foreach(
                        ManagerState.criteria_lines,
                        lambda line: rx.recharts.line(
                            data_key=line.code,
                            name=line.label,
                            stroke=line.color,
                            type_="monotone",
                            connect_nulls=False,
                            dot=True,
                            hide=ManagerState.hidden_lines.contains(line.code),
                        ),
                    ),
                    rx.recharts.x_axis(data_key=CHART_DAY_KEY),
                    rx.recharts.y_axis(domain=[0, SHARE_MAX], tick_count=TICK_COUNT),
                    rx.recharts.graphing_tooltip(),
                    rx.recharts.cartesian_grid(stroke_dasharray="3 3"),
                    data=ManagerState.criteria_trend,
                    height=CRITERIA_CHART_HEIGHT,
                    width="100%",
                ),
                width="100%",
            ),
            _line_panel(),
            spacing="3",
            width="100%",
            align="start",
        ),
        empty_state(EMPTY_TREND),
    )


def _criteria_bars() -> rx.Component:
    return rx.cond(
        ManagerState.criteria.length() > 0,
        rx.recharts.bar_chart(
            rx.recharts.bar(
                data_key=CHART_SCORE_KEY, fill=BAR_COLOR, bar_size=CRITERIA_BAR_SIZE
            ),
            rx.recharts.x_axis(type_="number", domain=[0, SHARE_MAX], tick_count=TICK_COUNT),
            rx.recharts.y_axis(
                data_key=CHART_LABEL_KEY,
                type_="category",
                width=CRITERIA_LABEL_WIDTH,
                interval=0,
            ),
            rx.recharts.graphing_tooltip(),
            rx.recharts.cartesian_grid(stroke_dasharray="3 3", horizontal=False),
            data=ManagerState.criteria_bars,
            layout="vertical",
            height=ManagerState.criteria_chart_height,
            width="100%",
            margin=CHART_MARGIN,
        ),
        empty_state(EMPTY_TREND),
    )


def _radar_legend_row(entry) -> rx.Component:
    return rx.hstack(
        rx.box(
            width=LEGEND_DOT_SIZE,
            height=LEGEND_DOT_SIZE,
            border_radius="50%",
            background=entry.color,
            flex_shrink="0",
        ),
        rx.text(
            entry.number,
            size="1",
            color_scheme="gray",
            flex_shrink="0",
            width=LEGEND_NUMBER_WIDTH,
            text_align="right",
        ),
        rx.text(entry.label, size="1", **TOGGLE_TEXT_STYLE),
        rx.spacer(),
        rx.text(entry.score_label, size="1", weight="medium", flex_shrink="0"),
        spacing="2",
        align="center",
        width="100%",
        padding=LEGEND_ROW_PADDING,
    )


def _radar_chart() -> rx.Component:
    return rx.cond(
        ManagerState.criteria.length() > 0,
        rx.hstack(
            rx.box(
                rx.recharts.radar_chart(
                    rx.recharts.radar(
                        data_key=CHART_SCORE_KEY,
                        stroke="var(--accent-9)",
                        fill="var(--accent-8)",
                        fill_opacity=RADAR_OPACITY,
                    ),
                    rx.recharts.polar_grid(),
                    rx.recharts.polar_angle_axis(data_key=CHART_LABEL_KEY),
                    rx.recharts.polar_radius_axis(
                        domain=[0, SHARE_MAX],
                        tick_count=TICK_COUNT,
                        axis_line=False,
                        tick=False,
                    ),
                    rx.recharts.graphing_tooltip(),
                    data=ManagerState.radar,
                    outer_radius=RADAR_OUTER_RADIUS,
                    height=RADAR_HEIGHT,
                    width="100%",
                ),
                width="100%",
                min_width="0",
            ),
            rx.scroll_area(
                rx.vstack(
                    rx.foreach(ManagerState.criteria, _radar_legend_row),
                    spacing="0",
                    width="100%",
                    padding_right=LEGEND_SCROLLBAR_GUTTER,
                ),
                height=RADAR_HEIGHT,
                type="always",
                scrollbars="vertical",
                width=RADAR_LEGEND_WIDTH,
                flex_shrink="0",
            ),
            spacing="4",
            width="100%",
            align="start",
        ),
        empty_state(EMPTY_TREND),
    )


def _call_row(row) -> rx.Component:
    return rx.table.row(
        rx.table.cell(
            rx.link(
                rx.text(row.started_at, size="2"),
                href=f"{ROUTE_CALL}/{row.call_id}",
            )
        ),
        rx.table.cell(rx.text(row.client, size="2")),
        rx.table.cell(rx.text(row.duration, size="2")),
        rx.table.cell(rx.badge(row.score)),
        rx.table.cell(rx.text(row.call_type, size="2")),
    )


def manager_page() -> rx.Component:
    return page_layout(
        rx.vstack(
            _kpi_row(),
            section_card(TREND_TITLE, _score_chart()),
            section_card(RADAR_TITLE, _radar_chart()),
            section_card(CRITERIA_TREND_TITLE, _criteria_chart()),
            section_card(CRITERIA_TITLE, _criteria_bars()),
            section_card(
                CALLS_TITLE,
                rx.cond(
                    ManagerState.calls_rows.length() > 0,
                    scrollable_table(
                        rx.table.header(
                            rx.table.row(
                                *[rx.table.column_header_cell(name) for name in COLUMNS]
                            )
                        ),
                        rx.table.body(rx.foreach(ManagerState.calls_rows, _call_row)),
                        ),
                    empty_state(EMPTY_CALLS),
                ),
            ),
            spacing="4",
            width="100%",
        ),
        header=_header(),
        on_mount=ManagerState.load,
    )
