import logging
import secrets

import reflex as rx
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from src import context, formatting
from src.constants import (
    BROWSER_OFFSET_SCRIPT,
    FIELD_LOGIN,
    FIELD_PASSWORD,
    INTERNAL_ERROR_MESSAGE,
    LOAD_ERROR_MESSAGE,
    LOGIN_ERROR_MESSAGE,
    MAX_UTC_OFFSET,
    MIN_UTC_OFFSET,
    NEGATIVE_SIGN,
    OFFSET_COOKIE_NAME,
    RELOAD_SCRIPT,
    ROUTE_DASHBOARD,
    ROUTE_LOGIN,
    SESSION_COOKIE_NAME,
    SESSION_SAME_SITE,
    SESSION_TOKEN_BYTES,
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
FALLBACK_UTC_OFFSET = formatting.default_offset(context.config().display.timezone)


def _is_offset(value: str) -> bool:
    return value.lstrip(NEGATIVE_SIGN).isdigit()


def _clamped(hours: int) -> int:
    return max(MIN_UTC_OFFSET, min(hours, MAX_UTC_OFFSET))


class AuthState(rx.State):
    session_token: str = rx.Cookie(
        "",
        name=SESSION_COOKIE_NAME,
        max_age=session.max_age_seconds,
        secure=session.cookie_secure,
        same_site=SESSION_SAME_SITE,
    )

    offset_cookie: str = rx.Cookie(
        "",
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
    no_users: bool = False
    load_error: str = ""
    pending_offset: int = 0
    timezone_dialog_open: bool = False

    @rx.event
    def check_users(self):
        try:
            self.no_users = not context.database().users_count()
        except Exception:
            logger.exception("failed to count users")
            return
        if self.no_users:
            logger.warning("no users in the database, nobody can sign in")

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
        return _clamped(int(value)) if _is_offset(value) else FALLBACK_UTC_OFFSET

    @rx.event
    def detect_offset(self):
        if not _is_offset(str(self.offset_cookie)):
            return rx.call_script(
                BROWSER_OFFSET_SCRIPT, callback=AuthState.store_browser_offset
            )

    @rx.event
    def store_browser_offset(self, hours):
        if _is_offset(str(self.offset_cookie)):
            return
        detected = _clamped(int(hours))
        self.offset_cookie = str(detected)
        if detected != FALLBACK_UTC_OFFSET:
            return rx.call_script(RELOAD_SCRIPT)

    @rx.event
    def ask_utc_offset(self, label: str):
        hours = OFFSET_BY_LABEL.get(label)
        if hours is None or hours == self.utc_offset:
            return
        self.pending_offset = hours
        self.timezone_dialog_open = True

    @rx.event
    def close_timezone_dialog(self, is_open: bool):
        self.timezone_dialog_open = is_open

    @rx.event
    def confirm_utc_offset(self):
        self.offset_cookie = str(self.pending_offset)
        self.timezone_dialog_open = False
        return rx.call_script(RELOAD_SCRIPT)

    @rx.var
    def offset_label(self) -> str:
        return formatting.offset_label(self.utc_offset)

    @rx.var
    def pending_offset_label(self) -> str:
        return formatting.offset_label(self.pending_offset)

    @rx.var
    def offset_options(self) -> list[str]:
        return list(OFFSET_BY_LABEL)

    @rx.var(cache=False)
    def session_login(self) -> str:
        try:
            user = context.database().session_user(str(self.session_token))
        except Exception:
            logger.exception("failed to look up the session")
            return ""
        return user["login"] if user else ""

    @rx.event
    def sign_in(self, form_data: dict):
        self.busy = True
        yield

        login = str(form_data.get(FIELD_LOGIN, "")).strip()
        password = str(form_data.get(FIELD_PASSWORD, ""))

        try:
            token = _authenticate(login, password)
        except Exception:
            logger.exception("sign in failed for %r", login)
            self.busy = False
            self.error = INTERNAL_ERROR_MESSAGE
            return

        self.busy = False
        if token is None:
            logger.info("failed sign in attempt for %r", login)
            self.error = LOGIN_ERROR_MESSAGE
            return

        logger.info("user %s signed in", login)
        self.session_token = token
        self.error = ""
        return rx.redirect(ROUTE_DASHBOARD)

    @rx.event
    def sign_out(self):
        logger.info("user %s signed out", self.session_login)
        try:
            context.database().delete_session(str(self.session_token))
        except Exception:
            logger.exception("failed to delete the session")
        self.session_token = ""
        return rx.redirect(ROUTE_LOGIN)

    @rx.event
    def require_session(self):
        if not self.is_hydrated:
            return AuthState.require_session
        if not self.session_login:
            return rx.redirect(ROUTE_LOGIN)


def guarded(state: AuthState, action) -> None:
    try:
        action()
    except Exception:
        logger.exception("failed to load page data")
        state.load_error = LOAD_ERROR_MESSAGE
        return
    state.load_error = ""


def _authenticate(login: str, password: str) -> str | None:
    database = context.database()
    user = database.user_by_login(login) if login else None
    if user is None or not _password_matches(user["password_hash"], password):
        return None

    database.purge_sessions()
    token = secrets.token_urlsafe(SESSION_TOKEN_BYTES)
    database.create_session(token, user["id"], session.max_age_seconds)
    return token


def _password_matches(password_hash: str, password: str) -> bool:
    try:
        return hasher.verify(password_hash, password)
    except (VerifyMismatchError, ValueError):
        return False
