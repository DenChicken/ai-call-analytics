import reflex as rx

from src.components.common import not_found
from src.components.layout import page_layout, sticky_header
from src.constants import (
    ROUTE_CALLS,
    ROUTE_DASHBOARD,
    ROUTE_MANAGERS,
    SECTION_CALLS,
    SECTION_DASHBOARD,
    SECTION_MANAGERS,
)

TITLE = "Страница не найдена"
MESSAGE = "Такой страницы нет"

DESTINATIONS = (
    (SECTION_DASHBOARD, ROUTE_DASHBOARD),
    (SECTION_CALLS, ROUTE_CALLS),
    (SECTION_MANAGERS, ROUTE_MANAGERS),
)


def not_found_page() -> rx.Component:
    return page_layout(
        not_found(MESSAGE, *DESTINATIONS),
        header=sticky_header(rx.heading(TITLE, size="6")),
    )
