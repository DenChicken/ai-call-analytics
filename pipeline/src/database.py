import json
from dataclasses import asdict, dataclass

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from src.config import Reference
from src.constants import (
    CALL_TYPES_TABLE,
    CLAIMABLE_STATUSES,
    CLAIMED_STATUS,
    CRITERIA_TABLE,
    MILLISECONDS_PER_SECOND,
    RELEASED_STATUS,
    STAGE_PRIORITY,
    STATUS_DONE,
    STATUS_TRANSCRIBED,
)
from src.transcript import Segment

SEGMENTS_KEY = "segments"
REFERENCE_TABLES = (CRITERIA_TABLE, CALL_TYPES_TABLE)


@dataclass(frozen=True)
class Task:
    call_id: int
    audio_path: str
    stage: str
    attempts: int


class Database:
    def __init__(self, dsn: str, pool_size: int):
        self._pool = ConnectionPool(
            dsn,
            min_size=1,
            max_size=pool_size,
            kwargs={"row_factory": dict_row, "autocommit": False},
            open=True,
        )

    def close(self) -> None:
        self._pool.close()

    def sync_reference(self, table: str, entries: list[Reference]) -> int:
        if table not in REFERENCE_TABLES:
            raise ValueError(f"unknown reference table: {table}")
        codes = [entry.code for entry in entries]
        with self._pool.connection() as connection:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.executemany(
                        f"""
                        INSERT INTO {table} (code, label, description, position, enabled)
                        VALUES (%s, %s, %s, %s, TRUE)
                        ON CONFLICT (code) DO UPDATE
                        SET label = EXCLUDED.label,
                            description = EXCLUDED.description,
                            position = EXCLUDED.position,
                            enabled = TRUE
                        """,
                        [
                            (e.code, e.label, e.description, position)
                            for position, e in enumerate(entries)
                        ],
                    )
                    cursor.execute(
                        f"UPDATE {table} SET enabled = FALSE "
                        "WHERE enabled AND NOT (code = ANY(%s))",
                        (codes,),
                    )
                    return cursor.rowcount

    def enabled_reference(self, table: str) -> list[Reference]:
        if table not in REFERENCE_TABLES:
            raise ValueError(f"unknown reference table: {table}")
        with self._pool.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"SELECT code, label, description FROM {table} WHERE enabled ORDER BY position"
                )
                rows = cursor.fetchall()
        return [
            Reference(code=row["code"], label=row["label"], description=row["description"])
            for row in rows
        ]

    def reset_interrupted(self) -> int:
        restored = 0
        with self._pool.connection() as connection:
            with connection.transaction():
                with connection.cursor() as cursor:
                    for interrupted, released in RELEASED_STATUS.items():
                        cursor.execute(
                            """
                            UPDATE processing_jobs
                            SET status = %s, claimed_at = NULL, updated_at = now()
                            WHERE status = %s
                            """,
                            (released, interrupted),
                        )
                        restored += cursor.rowcount
        return restored

    def claim_task(self, max_attempts: int) -> Task | None:
        with self._pool.connection() as connection:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT j.call_id, j.status, c.audio_path
                        FROM processing_jobs j
                        JOIN calls c ON c.id = j.call_id
                        WHERE j.status = ANY(%s) AND j.attempts < %s
                        ORDER BY array_position(%s, j.status), j.updated_at
                        FOR UPDATE OF j SKIP LOCKED
                        LIMIT 1
                        """,
                        (list(CLAIMABLE_STATUSES), max_attempts, list(STAGE_PRIORITY)),
                    )
                    row = cursor.fetchone()
                    if row is None:
                        return None

                    cursor.execute(
                        """
                        UPDATE processing_jobs
                        SET status = %s, attempts = attempts + 1,
                            claimed_at = now(), updated_at = now()
                        WHERE call_id = %s
                        RETURNING attempts
                        """,
                        (CLAIMED_STATUS[row["status"]], row["call_id"]),
                    )
                    attempts = cursor.fetchone()["attempts"]

        return Task(
            call_id=row["call_id"],
            audio_path=row["audio_path"],
            stage=row["status"],
            attempts=attempts,
        )

    def release_task(self, call_id: int, status: str, error: str | None = None) -> None:
        with self._pool.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE processing_jobs
                    SET status = %s, claimed_at = NULL, last_error = %s, updated_at = now()
                    WHERE call_id = %s
                    """,
                    (status, error, call_id),
                )

    def manager_name(self, call_id: int) -> str | None:
        with self._pool.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT a.display_name FROM calls c
                    JOIN agents a ON a.id = c.agent_id
                    WHERE c.id = %s
                    """,
                    (call_id,),
                )
                row = cursor.fetchone()
        return row["display_name"] if row else None

    def save_asr_result(
        self,
        call_id: int,
        segments: list[Segment],
        plain: str,
        transcript: str,
        model: str,
        language: str,
        duration_seconds: float,
    ) -> None:
        payload = {SEGMENTS_KEY: [asdict(segment) for segment in segments]}
        with self._pool.connection() as connection:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO asr_results (
                            call_id, model, language, duration_ms, plain, transcript, raw
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (call_id) DO UPDATE
                        SET model = EXCLUDED.model,
                            language = EXCLUDED.language,
                            duration_ms = EXCLUDED.duration_ms,
                            plain = EXCLUDED.plain,
                            transcript = EXCLUDED.transcript,
                            raw = EXCLUDED.raw,
                            created_at = now()
                        """,
                        (
                            call_id,
                            model,
                            language,
                            int(duration_seconds * MILLISECONDS_PER_SECOND),
                            plain,
                            transcript,
                            json.dumps(payload, ensure_ascii=False),
                        ),
                    )
                    _advance(cursor, call_id, STATUS_TRANSCRIBED)

    def load_plain(self, call_id: int) -> str | None:
        with self._pool.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT plain FROM asr_results WHERE call_id = %s", (call_id,))
                row = cursor.fetchone()
        return row["plain"] if row else None

    def save_analysis(
        self,
        call_id: int,
        analysis: dict,
        scores: dict[str, int],
        metadata: dict,
        audio_path: str,
    ) -> None:
        with self._pool.connection() as connection:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO analyses (
                            call_id, call_type, summary, strengths, weaknesses, recommendations,
                            asr_model, analysis_model, prompt_label, processing_seconds
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (call_id) DO UPDATE
                        SET call_type = EXCLUDED.call_type,
                            summary = EXCLUDED.summary,
                            strengths = EXCLUDED.strengths,
                            weaknesses = EXCLUDED.weaknesses,
                            recommendations = EXCLUDED.recommendations,
                            asr_model = EXCLUDED.asr_model,
                            analysis_model = EXCLUDED.analysis_model,
                            prompt_label = EXCLUDED.prompt_label,
                            processing_seconds = EXCLUDED.processing_seconds
                        """,
                        (
                            call_id,
                            analysis["call_type"],
                            analysis["summary"],
                            json.dumps(analysis["strengths"], ensure_ascii=False),
                            json.dumps(analysis["weaknesses"], ensure_ascii=False),
                            json.dumps(analysis["recommendations"], ensure_ascii=False),
                            metadata["asr_model"],
                            metadata["analysis_model"],
                            metadata["prompt_label"],
                            metadata["processing_seconds"],
                        ),
                    )

                    cursor.execute("DELETE FROM criterion_scores WHERE call_id = %s", (call_id,))
                    cursor.executemany(
                        """
                        INSERT INTO criterion_scores (call_id, criterion_code, score)
                        VALUES (%s, %s, %s)
                        """,
                        [(call_id, code, score) for code, score in scores.items()],
                    )

                    cursor.execute(
                        "UPDATE calls SET audio_path = %s WHERE id = %s", (audio_path, call_id)
                    )
                    _advance(cursor, call_id, STATUS_DONE)


def _advance(cursor, call_id: int, status: str) -> None:
    cursor.execute(
        """
        UPDATE processing_jobs
        SET status = %s, attempts = 0, claimed_at = NULL, last_error = NULL, updated_at = now()
        WHERE call_id = %s
        """,
        (status, call_id),
    )
