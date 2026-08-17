import json
from dataclasses import dataclass

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from src.config import Criterion
from src.constants import (
    CLAIMABLE_STATUSES,
    CLAIMED_STATUS,
    RELEASED_STATUS,
    STAGE_PRIORITY,
    STATUS_DONE,
    STATUS_TRANSCRIBED,
)
from src.transcript import Segment


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

    def sync_criteria(self, criteria: list[Criterion]) -> int:
        codes = [criterion.code for criterion in criteria]
        with self._pool.connection() as connection:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.executemany(
                        """
                        INSERT INTO criteria (code, label, description, enabled)
                        VALUES (%s, %s, %s, TRUE)
                        ON CONFLICT (code) DO UPDATE
                        SET label = EXCLUDED.label,
                            description = EXCLUDED.description,
                            enabled = TRUE
                        """,
                        [(c.code, c.label, c.description) for c in criteria],
                    )
                    cursor.execute(
                        "UPDATE criteria SET enabled = FALSE WHERE enabled AND NOT (code = ANY(%s))",
                        (codes,),
                    )
                    return cursor.rowcount

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

    def enabled_criteria(self) -> list[Criterion]:
        with self._pool.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT code, label, description FROM criteria WHERE enabled ORDER BY code"
                )
                rows = cursor.fetchall()
        return [
            Criterion(code=row["code"], label=row["label"], description=row["description"])
            for row in rows
        ]

    def save_transcript(self, call_id: int, segments: list[Segment]) -> None:
        with self._pool.connection() as connection:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "DELETE FROM transcript_segments WHERE call_id = %s", (call_id,)
                    )
                    cursor.executemany(
                        """
                        INSERT INTO transcript_segments
                            (call_id, idx, role, start_ms, end_ms, text)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        [
                            (call_id, idx, s.role, s.start_ms, s.end_ms, s.text)
                            for idx, s in enumerate(segments)
                        ],
                    )
                    cursor.execute(
                        """
                        UPDATE processing_jobs
                        SET status = %s, attempts = 0, claimed_at = NULL,
                            last_error = NULL, updated_at = now()
                        WHERE call_id = %s
                        """,
                        (STATUS_TRANSCRIBED, call_id),
                    )

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
                            call_id, summary, strengths, weaknesses, asr_model,
                            roles_model, analysis_model, prompt_label, processing_seconds
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (call_id) DO UPDATE
                        SET summary = EXCLUDED.summary,
                            strengths = EXCLUDED.strengths,
                            weaknesses = EXCLUDED.weaknesses,
                            asr_model = EXCLUDED.asr_model,
                            roles_model = EXCLUDED.roles_model,
                            analysis_model = EXCLUDED.analysis_model,
                            prompt_label = EXCLUDED.prompt_label,
                            processing_seconds = EXCLUDED.processing_seconds,
                            created_at = now()
                        """,
                        (
                            call_id,
                            analysis["summary"],
                            json.dumps(analysis["strengths"], ensure_ascii=False),
                            json.dumps(analysis["weaknesses"], ensure_ascii=False),
                            metadata["asr_model"],
                            metadata["roles_model"],
                            metadata["analysis_model"],
                            metadata["prompt_label"],
                            metadata["processing_seconds"],
                        ),
                    )

                    cursor.execute(
                        "DELETE FROM criterion_scores WHERE call_id = %s", (call_id,)
                    )
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
                    cursor.execute(
                        """
                        UPDATE processing_jobs
                        SET status = %s, claimed_at = NULL, last_error = NULL, updated_at = now()
                        WHERE call_id = %s
                        """,
                        (STATUS_DONE, call_id),
                    )

    def load_transcript(self, call_id: int) -> list[Segment]:
        with self._pool.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT role, start_ms, end_ms, text FROM transcript_segments
                    WHERE call_id = %s ORDER BY idx
                    """,
                    (call_id,),
                )
                rows = cursor.fetchall()
        return [
            Segment(
                role=row["role"],
                start_ms=row["start_ms"],
                end_ms=row["end_ms"],
                text=row["text"],
            )
            for row in rows
        ]

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

    def save_roles(self, call_id: int, segments: list[Segment]) -> None:
        with self._pool.connection() as connection:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.executemany(
                        "UPDATE transcript_segments SET role = %s WHERE call_id = %s AND idx = %s",
                        [(s.role, call_id, idx) for idx, s in enumerate(segments)],
                    )
