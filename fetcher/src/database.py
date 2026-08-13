import json

import psycopg
from psycopg.rows import dict_row

from src.constants import STATUS_PENDING
from src.source import Agent, Call


class Database:
    def __init__(self, dsn: str):
        self._connection = psycopg.connect(dsn, row_factory=dict_row, autocommit=False)

    def close(self) -> None:
        self._connection.close()

    def get_source_id(self, name: str) -> int:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO sources (name) VALUES (%s)
                ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
                RETURNING id
                """,
                (name,),
            )
            row = cursor.fetchone()
        self._connection.commit()
        return row["id"]

    def get_cursor(self, source_id: int) -> str | None:
        with self._connection.cursor() as cursor:
            cursor.execute("SELECT cursor FROM sources WHERE id = %s", (source_id,))
            row = cursor.fetchone()
        return row["cursor"] if row else None

    def set_cursor(self, source_id: int, value: str) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                "UPDATE sources SET cursor = %s, updated_at = now() WHERE id = %s",
                (value, source_id),
            )
        self._connection.commit()

    def existing_external_ids(self, source_id: int, external_ids: list[str]) -> set[str]:
        if not external_ids:
            return set()
        with self._connection.cursor() as cursor:
            cursor.execute(
                "SELECT external_id FROM calls WHERE source_id = %s AND external_id = ANY(%s)",
                (source_id, external_ids),
            )
            return {row["external_id"] for row in cursor.fetchall()}

    def upsert_agent(self, source_id: int, agent: Agent) -> int:
        with self._connection.cursor() as cursor:
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
            row = cursor.fetchone()
        self._connection.commit()
        return row["id"]

    def reserve_call_id(self) -> int:
        with self._connection.cursor() as cursor:
            cursor.execute("SELECT nextval(pg_get_serial_sequence('calls', 'id')) AS id")
            row = cursor.fetchone()
        self._connection.commit()
        return row["id"]

    def insert_call_with_recording(
        self, call_id: int, source_id: int, call: Call, agent_id: int | None, file_path: str
    ) -> bool:
        with self._connection.transaction():
            with self._connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO calls (
                        id, source_id, external_id, agent_id, started_at, duration_seconds,
                        direction, client_number, subject, crm_link, raw
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                        json.dumps(call.raw, ensure_ascii=False),
                    ),
                )
                inserted = cursor.fetchone()
                if inserted is None:
                    return False

                cursor.execute(
                    "INSERT INTO recordings (call_id, file_path, status) VALUES (%s, %s, %s)",
                    (call_id, file_path, STATUS_PENDING),
                )
        return True
