import reflex as rx

from src.constants import (
    ROUTE_CALLS,
    ROUTE_DASHBOARD,
    ROUTE_MANAGERS,
    TIMEZONE_LABEL,
)
from src.state.auth import AuthState

BRAND = "Аналитика звонков"
SIGN_OUT_LABEL = "Выйти"
SIDEBAR_WIDTH = "15rem"
SIDEBAR_COLLAPSED_WIDTH = "4rem"
SIDEBAR_PADDING = "0.75rem"
CONTENT_PADDING = "1.5rem"
NAV_ICON_SIZE = 18
BRAND_ICON_SIZE = 20
FOOTER_ICON_SIZE = 16
HEADER_PADDING = "0.75rem 1.5rem"
CONTENT_MAX_WIDTH = "88rem"
NAV_ITEM_PADDING = "0.5rem 0.75rem"
NAV_ITEM_RADIUS = "var(--radius-3)"
NAV_HOVER_BACKGROUND = "var(--gray-a3)"
MUTED_COLOR = "var(--gray-9)"
BORDER_STYLE = "1px solid var(--gray-a5)"
HEADER_BACKGROUND = "var(--color-panel-solid)"
HEADER_Z_INDEX = "10"
FULL_HEIGHT = "100vh"

CHART_FOCUS_RESET = {
    "& .recharts-wrapper, & .recharts-surface, & .recharts-wrapper *": {
        "outline": "none",
    }
}

NAV_ITEMS = (
    (ROUTE_DASHBOARD, "Дашборд", "layout-dashboard"),
    (ROUTE_CALLS, "Звонки", "phone"),
    (ROUTE_MANAGERS, "Менеджеры", "users"),
)


def _nav_link(route: str, label: str, icon: str) -> rx.Component:
    return rx.link(
        rx.tooltip(
            rx.hstack(
                rx.icon(icon, size=NAV_ICON_SIZE, flex_shrink="0"),
                rx.cond(
                    AuthState.sidebar_collapsed,
                    rx.fragment(),
                    rx.text(label, size="2", white_space="nowrap"),
                ),
                spacing="3",
                align="center",
                width="100%",
                padding=NAV_ITEM_PADDING,
                border_radius=NAV_ITEM_RADIUS,
                _hover={"background": NAV_HOVER_BACKGROUND},
            ),
            content=label,
        ),
        href=route,
        width="100%",
        underline="none",
        color="inherit",
    )


def _sidebar() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.icon("audio-lines", size=BRAND_ICON_SIZE, flex_shrink="0"),
            rx.cond(
                AuthState.sidebar_collapsed,
                rx.fragment(),
                rx.text(BRAND, weight="bold", size="3", white_space="nowrap"),
            ),
            rx.spacer(),
            rx.icon_button(
                rx.icon(
                    rx.cond(
                        AuthState.sidebar_collapsed, "panel-left-open", "panel-left-close"
                    ),
                    size=FOOTER_ICON_SIZE,
                ),
                on_click=AuthState.toggle_sidebar,
                variant="ghost",
                size="1",
                color_scheme="gray",
            ),
            spacing="2",
            align="center",
            width="100%",
            padding=SIDEBAR_PADDING,
        ),
        rx.vstack(
            *[_nav_link(route, label, icon) for route, label, icon in NAV_ITEMS],
            spacing="1",
            width="100%",
        ),
        rx.spacer(),
        rx.cond(
            AuthState.sidebar_collapsed,
            rx.tooltip(
                rx.icon("globe", size=FOOTER_ICON_SIZE, color=MUTED_COLOR),
                content=AuthState.offset_label,
            ),
            rx.vstack(
                rx.hstack(
                    rx.icon("globe", size=FOOTER_ICON_SIZE, color=MUTED_COLOR),
                    rx.text(TIMEZONE_LABEL, size="1", color_scheme="gray"),
                    spacing="2",
                    align="center",
                ),
                rx.select(
                    AuthState.offset_options,
                    value=AuthState.offset_label,
                    on_change=AuthState.set_utc_offset,
                    size="1",
                    width="100%",
                ),
                spacing="1",
                width="100%",
            ),
        ),
        rx.cond(
            AuthState.sidebar_collapsed,
            rx.fragment(),
            rx.hstack(
                rx.icon("user", size=FOOTER_ICON_SIZE),
                rx.text(AuthState.session_login, size="2", color_scheme="gray"),
                spacing="2",
                align="center",
            ),
        ),
        rx.tooltip(
            rx.button(
                rx.icon("log-out", size=FOOTER_ICON_SIZE),
                rx.cond(AuthState.sidebar_collapsed, rx.fragment(), rx.text(SIGN_OUT_LABEL)),
                on_click=AuthState.sign_out,
                variant="soft",
                width="100%",
                size="2",
            ),
            content=SIGN_OUT_LABEL,
        ),
        width=rx.cond(AuthState.sidebar_collapsed, SIDEBAR_COLLAPSED_WIDTH, SIDEBAR_WIDTH),
        height=FULL_HEIGHT,
        padding=SIDEBAR_PADDING,
        spacing="3",
        border_right=BORDER_STYLE,
        position="sticky",
        top="0",
        flex_shrink="0",
        overflow="hidden",
    )


def sticky_header(*children: rx.Component) -> rx.Component:
    return rx.box(
        rx.hstack(
            *children,
            width="100%",
            align="center",
            spacing="3",
            wrap="wrap",
        ),
        position="sticky",
        top="0",
        z_index=HEADER_Z_INDEX,
        width="100%",
        padding=HEADER_PADDING,
        background=HEADER_BACKGROUND,
        border_bottom=BORDER_STYLE,
    )


def page_layout(
    *children: rx.Component, header: rx.Component | None = None, on_mount=None
) -> rx.Component:
    return rx.hstack(
        _sidebar(),
        rx.vstack(
            header if header is not None else rx.fragment(),
            rx.box(
                *children,
                padding=CONTENT_PADDING,
                width="100%",
                max_width=CONTENT_MAX_WIDTH,
                sx=CHART_FOCUS_RESET,
            ),
            spacing="0",
            width="100%",
            min_width="0",
            align="start",
        ),
        spacing="0",
        align="start",
        width="100%",
        on_mount=on_mount if on_mount is not None else AuthState.require_session,
    )
