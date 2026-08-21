import reflex as rx

from src.constants import ROUTE_DASHBOARD, ROUTE_MANAGERS
from src.state.auth import AuthState

BRAND = "Аналитика звонков"
SIGN_OUT_LABEL = "Выйти"
SIDEBAR_WIDTH = "15rem"
CONTENT_PADDING = "1.5rem"
NAV_ICON_SIZE = 18
BRAND_ICON_SIZE = 20
FOOTER_ICON_SIZE = 16

NAV_ITEMS = (
    (ROUTE_DASHBOARD, "Дашборд", "layout-dashboard"),
    (ROUTE_MANAGERS, "Менеджеры", "users"),
)


def _nav_link(route: str, label: str, icon: str) -> rx.Component:
    return rx.link(
        rx.hstack(
            rx.icon(icon, size=NAV_ICON_SIZE),
            rx.text(label, size="2"),
            spacing="3",
            align="center",
            width="100%",
            padding="0.5rem 0.75rem",
            border_radius="var(--radius-3)",
        ),
        href=route,
        width="100%",
        underline="none",
        color="inherit",
    )


def _sidebar() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.icon("audio-lines", size=BRAND_ICON_SIZE),
            rx.text(BRAND, weight="bold", size="3"),
            spacing="2",
            align="center",
            padding="0.75rem",
        ),
        rx.vstack(
            *[_nav_link(route, label, icon) for route, label, icon in NAV_ITEMS],
            spacing="1",
            width="100%",
        ),
        rx.spacer(),
        rx.hstack(
            rx.icon("user", size=FOOTER_ICON_SIZE),
            rx.text(AuthState.session_login, size="2", color_scheme="gray"),
            spacing="2",
            align="center",
            padding="0.75rem",
        ),
        rx.button(
            rx.icon("log-out", size=FOOTER_ICON_SIZE),
            SIGN_OUT_LABEL,
            on_click=AuthState.sign_out,
            variant="soft",
            width="100%",
            size="2",
        ),
        width=SIDEBAR_WIDTH,
        height="100vh",
        padding=CONTENT_PADDING,
        spacing="4",
        border_right="1px solid var(--gray-a5)",
        position="sticky",
        top="0",
    )


def page_layout(*children: rx.Component, on_mount=None) -> rx.Component:
    return rx.hstack(
        _sidebar(),
        rx.box(
            *children,
            padding=CONTENT_PADDING,
            width="100%",
        ),
        spacing="0",
        align="start",
        width="100%",
        on_mount=on_mount if on_mount is not None else AuthState.require_session,
    )
