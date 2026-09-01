import reflex as rx

from src.constants import FIELD_LOGIN, FIELD_PASSWORD, FULL_HEIGHT
from src.state.auth import AuthState

TITLE = "Аналитика звонков"
SUBTITLE = "Вход в систему"
LOGIN_LABEL = "Логин"
PASSWORD_LABEL = "Пароль"
SUBMIT_LABEL = "Войти"
CARD_WIDTH = "22rem"
NO_USERS_MESSAGE = "Пользователей нет. Создайте первого:"
USER_COMMAND = "python scripts/user.py add <логин> -d <файл с dsn>"


def login_page() -> rx.Component:
    return rx.center(
        rx.card(
            rx.form(
                rx.vstack(
                    rx.heading(TITLE, size="6"),
                    rx.text(SUBTITLE, color_scheme="gray", size="2"),
                    rx.cond(
                        AuthState.license_expired,
                        rx.callout(
                            AuthState.license_notice,
                            color_scheme="red",
                            size="1",
                            width="100%",
                        ),
                        rx.fragment(),
                    ),
                    rx.input(
                        placeholder=LOGIN_LABEL,
                        name=FIELD_LOGIN,
                        width="100%",
                        auto_focus=True,
                    ),
                    rx.input(
                        placeholder=PASSWORD_LABEL,
                        name=FIELD_PASSWORD,
                        type="password",
                        width="100%",
                    ),
                    rx.cond(
                        AuthState.no_users,
                        rx.callout(
                            rx.vstack(
                                rx.text(NO_USERS_MESSAGE, size="1"),
                                rx.code(USER_COMMAND, size="1"),
                                spacing="2",
                                align="start",
                            ),
                            color_scheme="amber",
                            size="1",
                            width="100%",
                        ),
                        rx.fragment(),
                    ),
                    rx.cond(
                        AuthState.error != "",
                        rx.callout(AuthState.error, color_scheme="red", size="1", width="100%"),
                    ),
                    rx.button(
                        SUBMIT_LABEL,
                        type="submit",
                        width="100%",
                        loading=AuthState.busy,
                        disabled=AuthState.no_users | AuthState.license_expired,
                    ),
                    spacing="4",
                    width="100%",
                ),
                on_submit=AuthState.sign_in,
                width="100%",
            ),
            width=CARD_WIDTH,
        ),
        height=FULL_HEIGHT,
        on_mount=AuthState.check_users,
    )
