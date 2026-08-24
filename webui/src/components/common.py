import reflex as rx

from src.constants import PERIOD_LABELS, POSITIVE_SIGN

KPI_MIN_WIDTH = "12rem"
KPI_ICON_SIZE = 16
TABLE_SIZE = "1"
PERIOD_WIDTH = "7.5rem"
MENU_ICON_SIZE = 12
MENU_MAX_HEIGHT = "18rem"
MENU_LABEL_PADDING = "0.25rem 0.5rem"
MENU_ITEM_PADDING = "0.35rem 0.5rem"
REFRESH_ICON_SIZE = 14
CARD_HEADER_PADDING = "0.75rem 1rem"
CARD_BODY_PADDING = "1rem"
DELTA_POSITIVE_COLOR = "grass"
DELTA_NEGATIVE_COLOR = "tomato"
DELTA_NEUTRAL_COLOR = "gray"
MUTED_COLOR = "var(--gray-9)"
EMPTY_ICON = "inbox"
EMPTY_ICON_SIZE = 28
EMPTY_ICON_COLOR = "var(--gray-7)"
EMPTY_PADDING = "2.5rem 1rem"
NOT_FOUND_ICON = "search-x"
NOT_FOUND_ICON_SIZE = 40
NOT_FOUND_PADDING = "4rem 1rem"
CARD_HEADER_BACKGROUND = "var(--gray-a2)"
CARD_BORDER = "1px solid var(--gray-a5)"
CRUMB_SEPARATOR = "/"
CRUMB_SEPARATOR_COLOR = "var(--gray-8)"
CRUMB_SPACING = "2"
CRUMB_MAX_WIDTH = "20rem"
CRUMB_PARENT_SIZE = "2"
CRUMB_CURRENT_SIZE = "5"
TRUNCATE_STYLE = {
    "overflow": "hidden",
    "text_overflow": "ellipsis",
    "white_space": "nowrap",
}


def truncated(value: rx.Var | str, **props) -> rx.Component:
    return rx.text(value, **TRUNCATE_STYLE, **props)


def breadcrumbs(parent: tuple[str, str], current: rx.Var | str) -> rx.Component:
    label, route = parent
    return rx.hstack(
        rx.link(
            rx.text(label, size=CRUMB_PARENT_SIZE, white_space="nowrap"),
            href=route,
            color_scheme="gray",
            underline="hover",
            flex_shrink="0",
        ),
        rx.text(
            CRUMB_SEPARATOR,
            size=CRUMB_PARENT_SIZE,
            color=CRUMB_SEPARATOR_COLOR,
            flex_shrink="0",
        ),
        rx.heading(
            current, size=CRUMB_CURRENT_SIZE, **TRUNCATE_STYLE, max_width=CRUMB_MAX_WIDTH
        ),
        spacing=CRUMB_SPACING,
        align="baseline",
        min_width="0",
    )


def kpi_card(
    title: str, value: rx.Var | str, icon: str, note: rx.Component | None = None
) -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.icon(icon, size=KPI_ICON_SIZE, color=MUTED_COLOR),
                rx.text(title, size="2", color_scheme="gray"),
                spacing="2",
                align="center",
            ),
            rx.hstack(
                rx.heading(value, size="7", **TRUNCATE_STYLE),
                note if note is not None else rx.fragment(),
                spacing="3",
                align="baseline",
                width="100%",
            ),
            spacing="2",
            height="100%",
            justify="between",
        ),
        min_width=KPI_MIN_WIDTH,
        flex="1",
    )


def delta_text(points: rx.Var, label: rx.Var) -> rx.Component:
    return rx.text(
        label,
        size="2",
        white_space="nowrap",
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
        white_space="nowrap",
        color_scheme=rx.cond(
            value > 0,
            DELTA_POSITIVE_COLOR,
            rx.cond(value < 0, DELTA_NEGATIVE_COLOR, DELTA_NEUTRAL_COLOR),
        ),
    )


def period_picker(current: rx.Var, on_change) -> rx.Component:
    return rx.select(
        list(PERIOD_LABELS.values()),
        value=current,
        on_change=on_change,
        size="1",
        width=PERIOD_WIDTH,
    )


def checkbox_menu(
    label: str, summary: rx.Var, items: rx.Var, checked, on_change
) -> rx.Component:
    return rx.menu.root(
        rx.menu.trigger(
            rx.button(
                rx.icon("list-filter", size=MENU_ICON_SIZE),
                rx.text(summary, size="1", white_space="nowrap"),
                rx.icon("chevron-down", size=MENU_ICON_SIZE),
                variant="soft",
                size="1",
                color_scheme="gray",
            )
        ),
        rx.menu.content(
            rx.text(label, size="1", color_scheme="gray", padding=MENU_LABEL_PADDING),
            rx.foreach(
                items,
                lambda entry: rx.box(
                    rx.checkbox(
                        entry.label,
                        checked=checked(entry),
                        on_change=lambda value: on_change(entry, value),
                        size="1",
                    ),
                    padding=MENU_ITEM_PADDING,
                    width="100%",
                ),
            ),
            max_height=MENU_MAX_HEIGHT,
            overflow_y="auto",
        ),
    )


def empty_state(message: str, icon: str = EMPTY_ICON) -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.icon(icon, size=EMPTY_ICON_SIZE, color=EMPTY_ICON_COLOR),
            rx.text(message, size="2", color_scheme="gray"),
            spacing="3",
            align="center",
        ),
        width="100%",
        padding=EMPTY_PADDING,
    )


def not_found(message: str, *destinations: tuple[str, str]) -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.icon(NOT_FOUND_ICON, size=NOT_FOUND_ICON_SIZE, color=EMPTY_ICON_COLOR),
            rx.text(message, size="3", color_scheme="gray"),
            rx.hstack(
                *[
                    rx.link(
                        rx.button(label, variant="soft", size="2", color_scheme="gray"),
                        href=route,
                        underline="none",
                    )
                    for label, route in destinations
                ],
                spacing="3",
            ),
            spacing="4",
            align="center",
        ),
        width="100%",
        padding=NOT_FOUND_PADDING,
    )


def scrollable_table(*children: rx.Component, size: str = TABLE_SIZE) -> rx.Component:
    return rx.box(
        rx.table.root(*children, width="100%", size=size),
        width="100%",
        overflow_x="auto",
    )


def status_badge(label: rx.Var, color: rx.Var, error: rx.Var) -> rx.Component:
    return rx.cond(
        error != "",
        rx.tooltip(rx.badge(label, color_scheme=color), content=error),
        rx.badge(label, color_scheme=color),
    )


def refresh_button(on_click) -> rx.Component:
    return rx.icon_button(
        rx.icon("refresh-cw", size=REFRESH_ICON_SIZE),
        on_click=on_click,
        variant="ghost",
        size="1",
        color_scheme="gray",
    )


def section_card(
    title: str, *children: rx.Component, actions: rx.Component | None = None
) -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.text(title, size="2", weight="bold"),
                rx.spacer(),
                actions if actions is not None else rx.fragment(),
                width="100%",
                align="center",
                padding=CARD_HEADER_PADDING,
                border_bottom=CARD_BORDER,
                background=CARD_HEADER_BACKGROUND,
            ),
            rx.box(
                rx.vstack(*children, spacing="3", width="100%"),
                padding=CARD_BODY_PADDING,
                width="100%",
            ),
            spacing="0",
            width="100%",
        ),
        padding="0",
        width="100%",
        overflow="hidden",
    )
