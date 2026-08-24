import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from src import queries
from src.constants import QUEUE_STATUSES, SECONDS_PER_MINUTE

POOL_MIN_SIZE = 1
POOL_MAX_SIZE = 4
POOL_STARTUP_TIMEOUT_SECONDS = 10
MINUTES_PER_HOUR = 60
ZONE_NAME_TEMPLATE = "{sign}{hours:02d}:{minutes:02d}"
ZONE_POSITIVE_SIGN = "+"
ZONE_NEGATIVE_SIGN = "-"

logger = logging.getLogger(__name__)


@dataclass
class CallType:
    code: str
    label: str


class Database:
    def __init__(self, dsn: str):
        self._pool = ConnectionPool(
            dsn,
            min_size=POOL_MIN_SIZE,
            max_size=POOL_MAX_SIZE,
            kwargs={"row_factory": dict_row, "autocommit": True},
            open=True,
        )
        self._pool.wait(timeout=POOL_STARTUP_TIMEOUT_SECONDS)
        logger.info("connected to the database")

    def close(self) -> None:
        self._pool.close()

    def _fetch(self, query: str, params: dict | None = None) -> list[dict]:
        with self._pool.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params or {})
                return cursor.fetchall()

    def _fetch_one(self, query: str, params: dict | None = None) -> dict | None:
        rows = self._fetch(query, params)
        return rows[0] if rows else None

    def _execute(self, query: str, params: dict | None = None) -> None:
        with self._pool.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params or {})

    def user_by_login(self, login: str) -> dict | None:
        return self._fetch_one(queries.USER_BY_LOGIN, {"login": login})

    def users_count(self) -> int:
        return self._fetch_one(queries.USERS_COUNT)["total"]

    def create_session(self, token: str, user_id: int, max_age_seconds: int) -> None:
        self._execute(
            queries.SESSION_CREATE,
            {"token": token, "user_id": user_id, "max_age": max_age_seconds},
        )

    def session_user(self, token: str) -> dict | None:
        if not token:
            return None
        return self._fetch_one(queries.SESSION_USER, {"token": token})

    def delete_session(self, token: str) -> None:
        self._execute(queries.SESSION_DELETE, {"token": token})

    def purge_sessions(self) -> None:
        self._execute(queries.SESSIONS_PURGE)

    def criteria(self) -> list[dict]:
        return self._fetch(queries.CRITERIA_ALL)

    def call_types(self) -> list[dict]:
        return self._fetch(queries.CALL_TYPES_ALL)

    def criteria_ratios(self, window: dict) -> list[dict]:
        return self._fetch(queries.CRITERIA_RATIOS, window)

    def criteria_daily_ratios(self, window: dict) -> list[dict]:
        return self._fetch(queries.CRITERIA_DAILY_RATIOS, window)

    def period_totals(self, window: dict) -> dict:
        return self._fetch_one(queries.PERIOD_TOTALS, window)

    def agent_totals(self, window: dict) -> list[dict]:
        return self._fetch(queries.AGENT_TOTALS, window)

    def agent_daily_ratios(self, window: dict) -> list[dict]:
        return self._fetch(queries.AGENT_DAILY_RATIOS, window)

    def extreme_calls(self, window: dict) -> dict[str, dict]:
        return {row["kind"]: row for row in self._fetch(queries.EXTREME_CALLS, window)}

    def queue_jobs(self, types: list[str], limit: int) -> list[dict]:
        return self._fetch(
            queries.QUEUE_JOBS,
            {
                "statuses": list(QUEUE_STATUSES),
                "types": [str(code) for code in types],
                "limit": limit,
            },
        )

    def queue_counts(self) -> dict[str, int]:
        return {row["status"]: row["total"] for row in self._fetch(queries.QUEUE_COUNTS)}

    def recent_analyses(self, types: list[str], limit: int) -> list[dict]:
        return self._fetch(
            queries.RECENT_ANALYSES,
            {"types": [str(code) for code in types], "limit": limit},
        )

    def analyses_count(self, since: datetime, until: datetime, types: list[str]) -> int:
        return self._fetch_one(
            queries.ANALYSES_TODAY,
            {"since": since, "until": until, "types": [str(code) for code in types]},
        )["total"]

    def calls_list(self, filters: dict, limit: int, offset: int) -> list[dict]:
        return self._fetch(queries.CALLS_LIST, {**filters, "limit": limit, "offset": offset})

    def calls_list_count(self, filters: dict) -> int:
        return self._fetch_one(queries.CALLS_LIST_COUNT, filters)["total"]

    def agents_with_calls(self) -> list[dict]:
        return self._fetch(queries.AGENTS_WITH_CALLS)

    def agent(self, agent_id: int) -> dict | None:
        return self._fetch_one(queries.AGENT_BY_ID, {"agent_id": agent_id})

    def call_details(self, call_id: int) -> dict | None:
        return self._fetch_one(queries.CALL_DETAILS, {"call_id": call_id})

    def call_scores(self, call_id: int) -> list[dict]:
        return self._fetch(queries.CALL_SCORES, {"call_id": call_id})

    def call_segments(self, call_id: int) -> list[dict]:
        row = self._fetch_one(queries.CALL_SEGMENTS, {"call_id": call_id})
        return row["segments"] if row and row["segments"] else []


def build_filters(
    since: datetime,
    until: datetime,
    types: list[str],
    agent_id: int | None,
    statuses: list[str] | None,
) -> dict:
    return {
        "since": since,
        "until": until,
        "types": [str(code) for code in types],
        "agent_id": agent_id,
        "statuses": [str(status) for status in statuses] if statuses else None,
    }


def build_window(
    since: datetime,
    until: datetime,
    types: list[str],
    agent_id: int | None = None,
) -> dict:
    return {
        "since": since,
        "until": until,
        "types": [str(code) for code in types],
        "timezone": _zone_name(since),
        "agent_id": agent_id,
    }


def _zone_name(value: datetime) -> str:
    offset = value.utcoffset() or timedelta()
    total_minutes = int(offset.total_seconds() // SECONDS_PER_MINUTE)
    sign = ZONE_POSITIVE_SIGN if total_minutes >= 0 else ZONE_NEGATIVE_SIGN
    return ZONE_NAME_TEMPLATE.format(
        sign=sign,
        hours=abs(total_minutes) // MINUTES_PER_HOUR,
        minutes=abs(total_minutes) % MINUTES_PER_HOUR,
    )
