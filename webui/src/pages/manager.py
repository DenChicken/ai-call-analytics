import reflex as rx

from src.components.common import (
    breadcrumbs,
    empty_state,
    kpi_card,
    not_found,
    period_picker,
    scrollable_table,
    section_card,
    status_badge,
)
from src.components.layout import page_layout, sticky_header
from src.constants import (
    ALL_CALLS_LABEL,
    CHART_MARGIN,
    CHART_TICK_COUNT,
    CRM_ICON_SIZE,
    PARAM_AGENT,
    PARAM_PERIOD,
    ROUTE_CALL,
    ROUTE_CALLS,
    ROUTE_MANAGERS,
    SECTION_MANAGERS,
    SHARE_MAX,
)
from src.state.manager import (
    CHART_DAY_KEY,
    CHART_LABEL_KEY,
    CHART_SCORE_KEY,
    ManagerState,
)

KPI_SCORE = "Средний балл"
KPI_CALLS = "Звонков"
KPI_ANALYZED_HINT = "проанализировано:"
KPI_BEST = "Лучший разговор"
KPI_WORST = "Худший разговор"
TREND_TITLE = "Средний балл по дням"
CRITERIA_TREND_TITLE = "Критерии по дням"
RADAR_TITLE = "Критерии за период"
CRITERIA_TITLE = "Средние оценки за период"
CALLS_TITLE = "Последние разговоры"
ALL_CALLS_HINT = "всего за период:"
NOT_FOUND_MANAGER = "Менеджер не найден"
EMPTY_TREND = "Нет данных за период"
EMPTY_CALLS = "За период нет звонков"
CRM_LABEL = "Профиль в CRM"
OPEN_LABEL = "открыть"

CHART_HEIGHT = 260
CRITERIA_CHART_HEIGHT = 320
CRITERIA_BAR_SIZE = 16
CRITERIA_LABEL_WIDTH = 200
RADAR_OPACITY = 0.5
RADAR_OUTER_RADIUS = "78%"
RADAR_HEIGHT = 340
BAR_COLOR = "var(--accent-9)"
SHOW_ALL_LABEL = "Все"
HIDE_ALL_LABEL = "Ничего"

LEGEND_TEXT_SIZE = "1"
LEGEND_ROW_SPACING = "2"
LEGEND_ROW_PADDING = "0.25rem 0.5rem"
LEGEND_ROW_RADIUS = "var(--radius-2)"
LEGEND_SCROLLBAR_GUTTER = "0.75rem"
LEGEND_SCROLLBAR_TYPE = "always"
LEGEND_DOT_SIZE = "0.6rem"
LEGEND_DOT_OFFSET = "0.25rem"
LEGEND_NUMBER_WIDTH = "1.4rem"
LEGEND_HIDDEN_OPACITY = 0.55
LEGEND_HIDDEN_DOT_COLOR = "var(--gray-6)"
LEGEND_HIDDEN_TEXT_COLOR = "var(--gray-9)"
LEGEND_TEXT_COLOR = "var(--gray-12)"
LEGEND_HOVER_BACKGROUND = "var(--gray-a3)"
TREND_LEGEND_WIDTH = "15rem"
RADAR_LEGEND_WIDTH = "22rem"

COLUMNS = ("Дата", "Клиент", "Длительность", "Балл", "Тип", "Статус")


def _header() -> rx.Component:
    return sticky_header(
        breadcrumbs((SECTION_MANAGERS, ROUTE_MANAGERS), ManagerState.name),
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
        kpi_card(
            KPI_CALLS,
            ManagerState.calls.to_string(),
            "phone",
            rx.text(
                f"{KPI_ANALYZED_HINT} {ManagerState.analyzed}",
                size="2",
                color_scheme="gray",
                white_space="nowrap",
            ),
        ),
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
            rx.recharts.y_axis(domain=[0, SHARE_MAX], tick_count=CHART_TICK_COUNT),
            rx.recharts.graphing_tooltip(),
            rx.recharts.cartesian_grid(stroke_dasharray="3 3", vertical=False),
            data=ManagerState.trend,
            height=CHART_HEIGHT,
            width="100%",
        ),
        empty_state(EMPTY_TREND),
    )


def _legend_dot(color) -> rx.Component:
    return rx.box(
        width=LEGEND_DOT_SIZE,
        height=LEGEND_DOT_SIZE,
        border_radius="50%",
        background=color,
        flex_shrink="0",
        margin_top=LEGEND_DOT_OFFSET,
    )


def _legend_row(*children: rx.Component, **props) -> rx.Component:
    return rx.hstack(
        *children,
        spacing=LEGEND_ROW_SPACING,
        align="start",
        width="100%",
        padding=LEGEND_ROW_PADDING,
        border_radius=LEGEND_ROW_RADIUS,
        **props,
    )


def _legend_panel(rows, width: str, height: int) -> rx.Component:
    return rx.scroll_area(
        rx.vstack(
            rows,
            spacing="0",
            width="100%",
            padding_right=LEGEND_SCROLLBAR_GUTTER,
        ),
        height=height,
        type=LEGEND_SCROLLBAR_TYPE,
        scrollbars="vertical",
        width=width,
        flex_shrink="0",
    )


def _line_toggle(line) -> rx.Component:
    hidden = ManagerState.hidden_lines.contains(line.code)
    return _legend_row(
        _legend_dot(rx.cond(hidden, LEGEND_HIDDEN_DOT_COLOR, line.color)),
        rx.text(
            line.label,
            size=LEGEND_TEXT_SIZE,
            color=rx.cond(hidden, LEGEND_HIDDEN_TEXT_COLOR, LEGEND_TEXT_COLOR),
        ),
        on_click=ManagerState.toggle_line(line.code),
        cursor="pointer",
        opacity=rx.cond(hidden, LEGEND_HIDDEN_OPACITY, 1),
        _hover={"background": LEGEND_HOVER_BACKGROUND},
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
        _legend_panel(
            rx.foreach(ManagerState.criteria_lines, _line_toggle),
            width="100%",
            height=CRITERIA_CHART_HEIGHT,
        ),
        spacing="2",
        width=TREND_LEGEND_WIDTH,
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
                    rx.recharts.y_axis(domain=[0, SHARE_MAX], tick_count=CHART_TICK_COUNT),
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
            rx.recharts.x_axis(
                type_="number", domain=[0, SHARE_MAX], tick_count=CHART_TICK_COUNT
            ),
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
    return _legend_row(
        _legend_dot(entry.color),
        rx.text(
            entry.number,
            size=LEGEND_TEXT_SIZE,
            color_scheme="gray",
            flex_shrink="0",
            width=LEGEND_NUMBER_WIDTH,
            text_align="right",
        ),
        rx.text(entry.label, size=LEGEND_TEXT_SIZE, flex="1"),
        rx.text(
            entry.score_label,
            size=LEGEND_TEXT_SIZE,
            weight="medium",
            flex_shrink="0",
        ),
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
                        tick_count=CHART_TICK_COUNT,
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
            _legend_panel(
                rx.foreach(ManagerState.criteria, _radar_legend_row),
                width=RADAR_LEGEND_WIDTH,
                height=RADAR_HEIGHT,
            ),
            spacing="4",
            width="100%",
            align="start",
        ),
        empty_state(EMPTY_TREND),
    )


def _calls_actions() -> rx.Component:
    return rx.hstack(
        rx.text(
            f"{ALL_CALLS_HINT} {ManagerState.calls_total}",
            size="1",
            color_scheme="gray",
            white_space="nowrap",
        ),
        rx.link(
            rx.hstack(
                rx.text(ALL_CALLS_LABEL, size="1"),
                rx.icon("arrow-right", size=CRM_ICON_SIZE),
                spacing="1",
                align="center",
            ),
            href=f"{ROUTE_CALLS}?{PARAM_AGENT}={ManagerState.current_agent_id}"
            f"&{PARAM_PERIOD}={ManagerState.period}",
            underline="none",
            color_scheme="gray",
        ),
        spacing="3",
        align="center",
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
        rx.table.cell(status_badge(row.status_label, row.status_color, row.error)),
    )


def _found_view() -> rx.Component:
    return rx.vstack(
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
            actions=_calls_actions(),
        ),
        spacing="4",
        width="100%",
    )


def manager_page() -> rx.Component:
    return page_layout(
        rx.cond(
            ManagerState.found,
            _found_view(),
            not_found(NOT_FOUND_MANAGER, (SECTION_MANAGERS, ROUTE_MANAGERS)),
        ),
        header=_header(),
        on_mount=ManagerState.load,
    )
