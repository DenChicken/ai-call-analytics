import reflex as rx

from src.components.common import empty_state
from src.constants import CHART_MARGIN, CHART_TICK_COUNT, SHARE_MAX
from src.criteria import CHART_AFTER_KEY, CHART_BEFORE_KEY, CHART_LABEL_KEY

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
