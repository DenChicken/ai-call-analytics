import reflex as rx

from src.constants import PERIOD_LABELS, POSITIVE_SIGN, TRANSITION_ARROW

KPI_MIN_WIDTH = "12rem"
KPI_ICON_SIZE = 16
DELTA_POSITIVE_COLOR = "grass"
DELTA_NEGATIVE_COLOR = "tomato"
DELTA_NEUTRAL_COLOR = "gray"


def kpi_card(
    title: str, value: rx.Var | str, icon: str, note: rx.Component | None = None
) -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.icon(icon, size=KPI_ICON_SIZE, color="var(--gray-9)"),
                rx.text(title, size="2", color_scheme="gray"),
                spacing="2",
                align="center",
            ),
            rx.hstack(
                rx.heading(value, size="7"),
                note if note is not None else rx.fragment(),
                spacing="3",
                align="baseline",
            ),
            spacing="2",
        ),
        min_width=KPI_MIN_WIDTH,
        flex="1",
    )


def delta_text(points: rx.Var, label: rx.Var) -> rx.Component:
    return rx.text(
        label,
        size="2",
        color_scheme=rx.cond(
            points > 0,
            DELTA_POSITIVE_COLOR,
            rx.cond(points < 0, DELTA_NEGATIVE_COLOR, DELTA_NEUTRAL_COLOR),
        ),
    )


def signed_count(value: rx.Var) -> rx.Component:
    return rx.text(
        rx.cond(value > 0, f"{POSITIVE_SIGN}{value}", value.to_string()),
        size="2",
        color_scheme=rx.cond(
            value > 0,
            DELTA_POSITIVE_COLOR,
            rx.cond(value < 0, DELTA_NEGATIVE_COLOR, DELTA_NEUTRAL_COLOR),
        ),
    )


def period_picker(current: rx.Var, on_change) -> rx.Component:
    return rx.segmented_control.root(
        *[
            rx.segmented_control.item(label, value=code)
            for code, label in PERIOD_LABELS.items()
        ],
        value=current,
        on_change=on_change,
        size="1",
    )


def transition_text(before: rx.Var, after: rx.Var) -> rx.Component:
    return rx.text(
        f"{before}% {TRANSITION_ARROW} {after}%",
        size="1",
        color_scheme="gray",
    )


def section_card(title: str, *children: rx.Component) -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.text(title, size="2", weight="medium"),
            *children,
            spacing="3",
            width="100%",
        ),
        width="100%",
    )
