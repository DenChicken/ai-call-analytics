import logging
from datetime import datetime

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from src import queries
from src.constants import QUEUE_STATUSES

POOL_MIN_SIZE = 1
POOL_MAX_SIZE = 4
POOL_STARTUP_TIMEOUT_SECONDS = 10

logger = logging.getLogger(__name__)


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

    def user_by_login(self, login: str) -> dict | None:
        return self._fetch_one(queries.USER_BY_LOGIN, {"login": login})

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

    def calls_page(self, window: dict, limit: int, offset: int) -> list[dict]:
        return self._fetch(queries.CALLS_PAGE, {**window, "limit": limit, "offset": offset})

    def calls_count(self, window: dict) -> int:
        return self._fetch_one(queries.CALLS_COUNT, window)["total"]

    def extreme_calls(self, window: dict) -> dict[str, dict]:
        return {row["kind"]: row for row in self._fetch(queries.EXTREME_CALLS, window)}

    def queue_jobs(self, limit: int) -> list[dict]:
        return self._fetch(
            queries.QUEUE_JOBS, {"statuses": list(QUEUE_STATUSES), "limit": limit}
        )

    def queue_counts(self) -> dict[str, int]:
        return {row["status"]: row["total"] for row in self._fetch(queries.QUEUE_COUNTS)}

    def recent_analyses(self, limit: int) -> list[dict]:
        return self._fetch(queries.RECENT_ANALYSES, {"limit": limit})

    def agent(self, agent_id: int) -> dict | None:
        return self._fetch_one(queries.AGENT_BY_ID, {"agent_id": agent_id})

    def call_details(self, call_id: int) -> dict | None:
        return self._fetch_one(queries.CALL_DETAILS, {"call_id": call_id})

    def call_scores(self, call_id: int) -> list[dict]:
        return self._fetch(queries.CALL_SCORES, {"call_id": call_id})

    def call_segments(self, call_id: int) -> list[dict]:
        row = self._fetch_one(queries.CALL_SEGMENTS, {"call_id": call_id})
        return row["segments"] if row and row["segments"] else []


def build_window(
    since: datetime,
    until: datetime,
    types: list[str],
    timezone: str,
    agent_id: int | None = None,
) -> dict:
    return {
        "since": since,
        "until": until,
        "types": types,
        "timezone": timezone,
        "agent_id": agent_id,
    }
