import logging

import reflex as rx
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from src import context, formatting
from src.constants import (
    FIELD_LOGIN,
    FIELD_PASSWORD,
    LOGIN_ERROR_MESSAGE,
    MAX_UTC_OFFSET,
    MIN_UTC_OFFSET,
    NEGATIVE_SIGN,
    OFFSET_COOKIE_NAME,
    ROUTE_DASHBOARD,
    ROUTE_LOGIN,
    SESSION_COOKIE_NAME,
    SESSION_SAME_SITE,
    SIDEBAR_COLLAPSED_VALUE,
    SIDEBAR_COOKIE_NAME,
)

logger = logging.getLogger(__name__)

hasher = PasswordHasher()
session = context.config().session

OFFSET_BY_LABEL = {
    formatting.offset_label(hours): hours
    for hours in range(MIN_UTC_OFFSET, MAX_UTC_OFFSET + 1)
}
DEFAULT_UTC_OFFSET = formatting.default_offset(context.config().display.timezone)


def _is_offset(value: str) -> bool:
    return value.lstrip(NEGATIVE_SIGN).isdigit()


class AuthState(rx.State):
    session_login: str = rx.Cookie(
        "",
        name=SESSION_COOKIE_NAME,
        max_age=session.max_age_seconds,
        secure=session.cookie_secure,
        same_site=SESSION_SAME_SITE,
    )

    offset_cookie: str = rx.Cookie(
        str(formatting.default_offset(context.config().display.timezone)),
        name=OFFSET_COOKIE_NAME,
        max_age=session.max_age_seconds,
        secure=session.cookie_secure,
        same_site=SESSION_SAME_SITE,
    )

    sidebar_cookie: str = rx.Cookie(
        "",
        name=SIDEBAR_COOKIE_NAME,
        max_age=session.max_age_seconds,
        secure=session.cookie_secure,
        same_site=SESSION_SAME_SITE,
    )

    error: str = ""
    busy: bool = False

    @rx.var
    def sidebar_collapsed(self) -> bool:
        return str(self.sidebar_cookie) == SIDEBAR_COLLAPSED_VALUE

    @rx.event
    def toggle_sidebar(self):
        self.sidebar_cookie = (
            "" if self.sidebar_collapsed else SIDEBAR_COLLAPSED_VALUE
        )

    @rx.var
    def utc_offset(self) -> int:
        value = str(self.offset_cookie)
        return int(value) if _is_offset(value) else DEFAULT_UTC_OFFSET

    @rx.event
    def set_utc_offset(self, label: str):
        self.offset_cookie = str(OFFSET_BY_LABEL.get(label, DEFAULT_UTC_OFFSET))

    @rx.var
    def offset_label(self) -> str:
        return formatting.offset_label(self.utc_offset)

    @rx.var
    def offset_options(self) -> list[str]:
        return list(OFFSET_BY_LABEL)

    @rx.event
    def sign_in(self, form_data: dict):
        self.busy = True
        yield

        login = str(form_data.get(FIELD_LOGIN, "")).strip()
        password = str(form_data.get(FIELD_PASSWORD, ""))
        user = context.database().user_by_login(login) if login else None

        self.busy = False
        if user is None or not _password_matches(user["password_hash"], password):
            logger.info("failed sign in attempt for %r", login)
            self.error = LOGIN_ERROR_MESSAGE
            return

        logger.info("user %s signed in", login)
        self.session_login = user["login"]
        self.error = ""
        return rx.redirect(ROUTE_DASHBOARD)

    @rx.event
    def sign_out(self):
        logger.info("user %s signed out", self.session_login)
        self.session_login = ""
        return rx.redirect(ROUTE_LOGIN)

    @rx.event
    def require_session(self):
        if not self.session_login:
            return rx.redirect(ROUTE_LOGIN)


def _password_matches(password_hash: str, password: str) -> bool:
    try:
        return hasher.verify(password_hash, password)
    except (VerifyMismatchError, ValueError):
        return False
