import reflex as rx

from src.components.common import empty_state, truncated
from src.constants import (
    CHART_AXIS_HEIGHT,
    CHART_MARGIN,
    CHART_TICK_COUNT,
    CHART_TICK_INTERVAL,
    CHART_TICK_SIZE,
    ROUTE_MANAGER,
    SHARE_MAX,
)
from src.criteria import CHART_AFTER_KEY, CHART_BEFORE_KEY, CHART_LABEL_KEY

TOP_BAR_COLOR = "var(--accent-9)"
TOP_CHART_HEIGHT = 260
TOP_BAR_SIZE = 28
TOP_LEGEND_WIDTH = "20rem"
TOP_LEGEND_SPACING = "2"
TOP_LEGEND_PADDING = "0.25rem 0.5rem"
TOP_LEGEND_RADIUS = "var(--radius-2)"
TOP_LEGEND_NUMBER_WIDTH = "1.4rem"
TOP_LEGEND_HOVER_BACKGROUND = "var(--gray-a3)"
TOP_LEGEND_TEXT_SIZE = "1"
TOP_LEGEND_ANALYZED_WIDTH = "3.5rem"
TOP_LEGEND_SCORE_WIDTH = "2.2rem"
TOP_ANALYZED_TEMPLATE = "{count} зв."

BAR_BEFORE_COLOR = "var(--gray-8)"
BAR_AFTER_COLOR = "var(--accent-9)"
LEGEND_BEFORE = "Прошлый период"
LEGEND_AFTER = "Текущий период"
EXPAND_LABEL = "Показать все"
COLLAPSE_LABEL = "Свернуть"
LABEL_WIDTH = 180
BAR_SIZE = 12
CATEGORY_GAP = 18
BAR_GAP = 2
TOGGLE_ICON_SIZE = 14


def _toggle(expanded, hidden_count, on_click) -> rx.Component:
    return rx.cond(
        hidden_count > 0,
        rx.button(
            rx.icon(
                rx.cond(expanded, "chevron-up", "chevron-down"), size=TOGGLE_ICON_SIZE
            ),
            rx.cond(
                expanded,
                rx.text(COLLAPSE_LABEL, size="1"),
                rx.text(f"{EXPAND_LABEL} ({hidden_count})", size="1"),
            ),
            on_click=on_click,
            variant="ghost",
            size="1",
            color_scheme="gray",
        ),
        rx.fragment(),
    )


def _top_manager_row(entry) -> rx.Component:
    return rx.link(
        rx.hstack(
            rx.text(
                entry.number,
                size=TOP_LEGEND_TEXT_SIZE,
                color_scheme="gray",
                flex_shrink="0",
                width=TOP_LEGEND_NUMBER_WIDTH,
                text_align="right",
            ),
            truncated(
                entry.name,
                size=TOP_LEGEND_TEXT_SIZE,
                flex="1",
                min_width="0",
            ),
            rx.text(
                TOP_ANALYZED_TEMPLATE.format(count=entry.analyzed),
                size=TOP_LEGEND_TEXT_SIZE,
                color_scheme="gray",
                white_space="nowrap",
                flex_shrink="0",
                width=TOP_LEGEND_ANALYZED_WIDTH,
                text_align="right",
            ),
            rx.text(
                entry.score_label,
                size=TOP_LEGEND_TEXT_SIZE,
                weight="medium",
                flex_shrink="0",
                width=TOP_LEGEND_SCORE_WIDTH,
                text_align="right",
            ),
            spacing=TOP_LEGEND_SPACING,
            align="center",
            width="100%",
            padding=TOP_LEGEND_PADDING,
            border_radius=TOP_LEGEND_RADIUS,
            _hover={"background": TOP_LEGEND_HOVER_BACKGROUND},
        ),
        href=f"{ROUTE_MANAGER}/{entry.agent_id}",
        underline="none",
        color="inherit",
        width="100%",
    )


def top_managers_chart(state, name_key: str, score_key: str, empty: str) -> rx.Component:
    return rx.cond(
        state.top_managers.length() > 0,
        rx.hstack(
            rx.box(
                rx.recharts.bar_chart(
                    rx.recharts.bar(
                        data_key=score_key, fill=TOP_BAR_COLOR, bar_size=TOP_BAR_SIZE
                    ),
                    rx.recharts.x_axis(
                        data_key=name_key,
                        interval=CHART_TICK_INTERVAL,
                        tick_size=CHART_TICK_SIZE,
                        height=CHART_AXIS_HEIGHT,
                    ),
                    rx.recharts.y_axis(
                        domain=[0, SHARE_MAX], tick_count=CHART_TICK_COUNT
                    ),
                    rx.recharts.graphing_tooltip(),
                    rx.recharts.cartesian_grid(stroke_dasharray="3 3", vertical=False),
                    data=state.top_managers_chart,
                    height=TOP_CHART_HEIGHT,
                    width="100%",
                    margin=CHART_MARGIN,
                ),
                width="100%",
                min_width="0",
            ),
            rx.vstack(
                rx.foreach(state.top_managers, _top_manager_row),
                spacing="0",
                width=TOP_LEGEND_WIDTH,
                flex_shrink="0",
            ),
            spacing="4",
            width="100%",
            align="start",
        ),
        empty_state(empty),
    )


def criteria_deltas_chart(state, empty: str) -> rx.Component:
    return rx.cond(
        state.criteria_chart.length() > 0,
        rx.vstack(
            rx.recharts.bar_chart(
                rx.recharts.bar(
                    data_key=CHART_BEFORE_KEY,
                    fill=BAR_BEFORE_COLOR,
                    name=LEGEND_BEFORE,
                    bar_size=BAR_SIZE,
                ),
                rx.recharts.bar(
                    data_key=CHART_AFTER_KEY,
                    fill=BAR_AFTER_COLOR,
                    name=LEGEND_AFTER,
                    bar_size=BAR_SIZE,
                ),
                rx.recharts.x_axis(
                    type_="number", domain=[0, SHARE_MAX], tick_count=CHART_TICK_COUNT
                ),
                rx.recharts.y_axis(
                    data_key=CHART_LABEL_KEY,
                    type_="category",
                    width=LABEL_WIDTH,
                    interval=0,
                ),
                rx.recharts.graphing_tooltip(),
                rx.recharts.legend(),
                rx.recharts.cartesian_grid(stroke_dasharray="3 3", horizontal=False),
                data=state.visible_criteria,
                layout="vertical",
                bar_category_gap=CATEGORY_GAP,
                bar_gap=BAR_GAP,
                height=state.criteria_chart_height,
                width="100%",
                margin=CHART_MARGIN,
            ),
            _toggle(
                state.criteria_expanded,
                state.criteria_hidden_count,
                state.toggle_criteria,
            ),
            spacing="2",
            width="100%",
            align="center",
        ),
        empty_state(empty),
    )
