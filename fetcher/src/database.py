import json
import logging

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from src.config import DatabaseConfig
from src.constants import STATUS_PENDING
from src.retry import retried
from src.source import Agent, Call

logger = logging.getLogger(__name__)

POOL_SIZE = 1

SELECT_SOURCE_ID = "SELECT id FROM sources WHERE name = %s"


class Database:
    def __init__(self, config: DatabaseConfig):
        self._config = config
        self._pool = ConnectionPool(
            config.dsn,
            min_size=POOL_SIZE,
            max_size=POOL_SIZE,
            timeout=config.connect_timeout,
            kwargs={"row_factory": dict_row, "autocommit": True},
            check=ConnectionPool.check_connection,
            open=True,
        )
        logger.info("database pool ready")

    def close(self) -> None:
        self._pool.close()

    @retried
    def get_source_id(self, name: str) -> int:
        with self._pool.connection() as connection, connection.cursor() as cursor:
            cursor.execute(SELECT_SOURCE_ID, (name,))
            row = cursor.fetchone()
            if row:
                return row["id"]

            cursor.execute(
                "INSERT INTO sources (name) VALUES (%s) ON CONFLICT (name) DO NOTHING RETURNING id",
                (name,),
            )
            row = cursor.fetchone()
            if row:
                logger.info("source %s registered as id %s", name, row["id"])
                return row["id"]

            cursor.execute(SELECT_SOURCE_ID, (name,))
            return cursor.fetchone()["id"]

    @retried
    def get_cursor(self, source_id: int) -> str | None:
        with self._pool.connection() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT cursor FROM sources WHERE id = %s", (source_id,))
            row = cursor.fetchone()
        return row["cursor"] if row else None

    @retried
    def set_cursor(self, source_id: int, value: str) -> None:
        with self._pool.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE sources SET cursor = %s, updated_at = now() WHERE id = %s",
                (value, source_id),
            )
        logger.debug("cursor for source %s set to %s", source_id, value)

    @retried
    def existing_external_ids(self, source_id: int, external_ids: list[str]) -> set[str]:
        if not external_ids:
            return set()
        with self._pool.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT external_id FROM calls WHERE source_id = %s AND external_id = ANY(%s)",
                (source_id, external_ids),
            )
            return {row["external_id"] for row in cursor.fetchall()}

    @retried
    def upsert_agent(self, source_id: int, agent: Agent) -> int:
        with self._pool.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO agents (
                    source_id, external_id, display_name, first_name,
                    last_name, second_name, email, profile_link
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (source_id, external_id) DO UPDATE
                SET display_name = EXCLUDED.display_name,
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    second_name = EXCLUDED.second_name,
                    email = EXCLUDED.email,
                    profile_link = EXCLUDED.profile_link,
                    synced_at = now()
                RETURNING id
                """,
                (
                    source_id,
                    agent.external_id,
                    agent.display_name,
                    agent.first_name,
                    agent.last_name,
                    agent.second_name,
                    agent.email,
                    agent.profile_link,
                ),
            )
            return cursor.fetchone()["id"]

    @retried
    def reserve_call_id(self) -> int:
        with self._pool.connection() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT nextval(pg_get_serial_sequence('calls', 'id')) AS id")
            return cursor.fetchone()["id"]

    @retried
    def insert_call_with_job(
        self,
        call_id: int,
        source_id: int,
        call: Call,
        agent_id: int | None,
        audio_path: str,
        cursor_value: str | None,
    ) -> bool:
        with self._pool.connection() as connection, connection.transaction():
            with connection.cursor() as cursor:
                if cursor_value is not None:
                    cursor.execute(
                        "UPDATE sources SET cursor = %s, updated_at = now() WHERE id = %s",
                        (cursor_value, source_id),
                    )
                cursor.execute(
                    """
                    INSERT INTO calls (
                        id, source_id, external_id, agent_id, started_at, duration_seconds,
                        direction, client_number, subject, crm_link, audio_path, raw
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (source_id, external_id) DO NOTHING
                    RETURNING id
                    """,
                    (
                        call_id,
                        source_id,
                        call.external_id,
                        agent_id,
                        call.started_at,
                        call.duration_seconds,
                        call.direction,
                        call.client_number,
                        call.subject,
                        call.crm_link,
                        audio_path,
                        json.dumps(call.raw, ensure_ascii=False),
                    ),
                )
                inserted = cursor.fetchone()
                if inserted is None:
                    logger.debug("call %s already stored, insert skipped", call.external_id)
                    return False

                cursor.execute(
                    "INSERT INTO processing_jobs (call_id, status) VALUES (%s, %s)",
                    (call_id, STATUS_PENDING),
                )
        logger.debug(
            "stored call %s as id %s, job queued, cursor moved to %s",
            call.external_id,
            call_id,
            cursor_value,
        )
        return True
