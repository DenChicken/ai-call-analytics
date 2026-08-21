import logging

import reflex as rx
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from src import context
from src.constants import (
    FIELD_LOGIN,
    FIELD_PASSWORD,
    LOGIN_ERROR_MESSAGE,
    ROUTE_DASHBOARD,
    ROUTE_LOGIN,
    SESSION_COOKIE_NAME,
    SESSION_SAME_SITE,
)

logger = logging.getLogger(__name__)

hasher = PasswordHasher()
session = context.config().session


class AuthState(rx.State):
    session_login: str = rx.Cookie(
        "",
        name=SESSION_COOKIE_NAME,
        max_age=session.max_age_seconds,
        secure=session.cookie_secure,
        same_site=SESSION_SAME_SITE,
    )

    error: str = ""
    busy: bool = False

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
