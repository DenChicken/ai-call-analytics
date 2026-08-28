import reflex as rx

from src.constants import (
    FULL_HEIGHT,
    MUTED_COLOR,
    ROUTE_CALLS,
    ROUTE_DASHBOARD,
    ROUTE_MANAGERS,
    SECTION_CALLS,
    SECTION_DASHBOARD,
    SECTION_MANAGERS,
    TIMEZONE_DIALOG_CANCEL,
    TIMEZONE_DIALOG_CONFIRM,
    TIMEZONE_DIALOG_TEXT,
    TIMEZONE_DIALOG_TITLE,
    TIMEZONE_LABEL,
)
from src.state.auth import AuthState

BRAND = "Аналитика звонков"
SIGN_OUT_LABEL = "Выйти"
COLLAPSE_LABEL = "Свернуть панель"
EXPAND_LABEL = "Развернуть панель"
SIGN_OUT_VARIANT = "soft"
TOGGLE_VARIANT = "ghost"
SIDEBAR_WIDTH = "15rem"
SIDEBAR_COLLAPSED_WIDTH = "4rem"
SIDEBAR_PADDING = "0.75rem"
CONTENT_PADDING = "1.5rem"
LOADING_HEIGHT = "100vh"
NAV_ICON_SIZE = 18
BRAND_ICON_SIZE = 20
FOOTER_ICON_SIZE = 16
HEADER_PADDING = "0.75rem 1.5rem"
CONTENT_MAX_WIDTH = "88rem"
NAV_ITEM_PADDING = "0.5rem 0.75rem"
NAV_ITEM_RADIUS = "var(--radius-3)"
NAV_HOVER_BACKGROUND = "var(--gray-a3)"
BORDER_STYLE = "1px solid var(--gray-a5)"
HEADER_BACKGROUND = "var(--color-panel-solid)"
HEADER_Z_INDEX = "10"
FOOTER_ICON_PADDING = "0.25rem"
DIALOG_MAX_WIDTH = "26rem"
DIALOG_ACTIONS_MARGIN = "1rem"

CHART_FOCUS_RESET = {
    "& .recharts-wrapper, & .recharts-surface, & .recharts-wrapper *": {
        "outline": "none",
    }
}

NAV_ITEMS = (
    (ROUTE_DASHBOARD, SECTION_DASHBOARD, "layout-dashboard"),
    (ROUTE_CALLS, SECTION_CALLS, "phone"),
    (ROUTE_MANAGERS, SECTION_MANAGERS, "users"),
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


def _footer_button(icon, label, on_click, variant: str) -> rx.Component:
    return rx.tooltip(
        rx.button(
            rx.icon(icon, size=FOOTER_ICON_SIZE, flex_shrink="0"),
            rx.cond(
                AuthState.sidebar_collapsed,
                rx.fragment(),
                rx.text(label, size="2", white_space="nowrap"),
            ),
            on_click=on_click,
            variant=variant,
            color_scheme="gray",
            size="2",
            width="100%",
            justify=rx.cond(AuthState.sidebar_collapsed, "center", "start"),
        ),
        content=label,
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
            spacing="2",
            align="center",
            justify=rx.cond(AuthState.sidebar_collapsed, "center", "start"),
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
                rx.center(
                    rx.icon("globe", size=FOOTER_ICON_SIZE, color=MUTED_COLOR),
                    width="100%",
                    padding=FOOTER_ICON_PADDING,
                ),
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
                    on_change=AuthState.ask_utc_offset,
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
        _footer_button("log-out", SIGN_OUT_LABEL, AuthState.sign_out, SIGN_OUT_VARIANT),
        _footer_button(
            rx.cond(AuthState.sidebar_collapsed, "chevrons-right", "chevrons-left"),
            rx.cond(AuthState.sidebar_collapsed, EXPAND_LABEL, COLLAPSE_LABEL),
            AuthState.toggle_sidebar,
            TOGGLE_VARIANT,
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
        on_mount=AuthState.detect_offset,
    )


def _timezone_dialog() -> rx.Component:
    return rx.alert_dialog.root(
        rx.alert_dialog.content(
            rx.alert_dialog.title(TIMEZONE_DIALOG_TITLE),
            rx.alert_dialog.description(
                f"{AuthState.offset_label} → {AuthState.pending_offset_label}. "
                f"{TIMEZONE_DIALOG_TEXT}",
                size="2",
            ),
            rx.hstack(
                rx.alert_dialog.cancel(
                    rx.button(
                        TIMEZONE_DIALOG_CANCEL,
                        variant="soft",
                        color_scheme="gray",
                        size="2",
                    )
                ),
                rx.alert_dialog.action(
                    rx.button(
                        TIMEZONE_DIALOG_CONFIRM,
                        on_click=AuthState.confirm_utc_offset,
                        size="2",
                    )
                ),
                spacing="3",
                justify="end",
                width="100%",
                margin_top=DIALOG_ACTIONS_MARGIN,
            ),
            max_width=DIALOG_MAX_WIDTH,
        ),
        open=AuthState.timezone_dialog_open,
        on_open_change=AuthState.close_timezone_dialog,
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
    return rx.cond(
        AuthState.is_hydrated & (AuthState.session_login != ""),
        rx.hstack(
            _timezone_dialog(),
            _sidebar(),
            rx.vstack(
                header if header is not None else rx.fragment(),
                rx.box(
                    rx.cond(
                        AuthState.load_error != "",
                        rx.callout(
                            AuthState.load_error,
                            color_scheme="red",
                            size="1",
                            width="100%",
                            margin_bottom=CONTENT_PADDING,
                        ),
                        rx.fragment(),
                    ),
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
        ),
        rx.center(
            rx.spinner(size="3"),
            width="100%",
            height=LOADING_HEIGHT,
            on_mount=AuthState.require_session,
        ),
    )
