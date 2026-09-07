import json
import logging
from dataclasses import asdict, dataclass

import psycopg
from psycopg.rows import dict_row

from src import shutdown
from src.analysis import Analysis
from src.config import Config, Reference
from src.constants import (
    MILLISECONDS_PER_SECOND,
    STAGE_PRIORITY,
    STATUS_DONE,
    STATUS_FAILED,
    STATUS_TRANSCRIBED,
)
from src.errors import FatalError
from src.transcript import Segment

SEGMENTS_KEY = "segments"

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Task:
    call_id: int
    audio_path: str
    stage: str
    attempts: int


class Database:
    def __init__(self, config: Config):
        self._config = config
        self._connection = self._connect()
        logger.info("database connected")

    def _connect(self) -> psycopg.Connection:
        database = self._config.database
        delay = database.backoff_base_seconds
        for attempt in range(1, database.max_retries + 1):
            try:
                return psycopg.connect(
                    self._config.dsn,
                    connect_timeout=database.connect_timeout,
                    row_factory=dict_row,
                    autocommit=True,
                )
            except psycopg.Error as error:
                if attempt == database.max_retries:
                    raise FatalError(f"database is unreachable: {error}") from error
                logger.warning("database connection failed (%s), retrying in %.0fs", error, delay)
                shutdown.sleep(delay)
                delay = min(delay * 2, database.backoff_max_seconds)
        raise FatalError("database is unreachable")

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, *exception) -> None:
        self.close()

    def _cursor(self) -> psycopg.Cursor:
        if self._connection.closed:
            logger.warning("database connection was lost, reconnecting")
            self._connection = self._connect()
        return self._connection.cursor()

    def sync_references(self, entries: dict[str, list[Reference]]) -> None:
        with self._cursor() as cursor:
            for table, references in entries.items():
                cursor.execute(f"UPDATE {table} SET enabled = FALSE")
                for position, entry in enumerate(references):
                    cursor.execute(
                        f"""
                        INSERT INTO {table} (code, label, description, position, enabled)
                        VALUES (%s, %s, %s, %s, TRUE)
                        ON CONFLICT (code) DO UPDATE
                        SET label = EXCLUDED.label,
                            description = EXCLUDED.description,
                            position = EXCLUDED.position,
                            enabled = TRUE
                        """,
                        (entry.code, entry.label, entry.description, position),
                    )
                logger.info("%s synced: %s enabled", table, len(references))

    def enabled_references(self, table: str) -> list[Reference]:
        with self._cursor() as cursor:
            cursor.execute(
                f"SELECT code, label, description FROM {table} "
                "WHERE enabled ORDER BY position, code"
            )
            return [Reference(**row) for row in cursor.fetchall()]

    def next_task(self) -> Task | None:
        with self._cursor() as cursor:
            cursor.execute(
                """
                SELECT j.call_id, j.status, j.attempts,
                       (SELECT c.audio_path FROM calls c WHERE c.id = j.call_id) AS audio_path
                FROM processing_jobs j
                WHERE j.status = ANY(%s) AND j.attempts < %s
                ORDER BY array_position(%s, j.status), j.updated_at
                LIMIT 1
                """,
                (
                    list(STAGE_PRIORITY),
                    self._config.worker.max_attempts,
                    list(STAGE_PRIORITY),
                ),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        return Task(
            call_id=row["call_id"],
            audio_path=row["audio_path"],
            stage=row["status"],
            attempts=row["attempts"],
        )

    def start_attempt(self, task: Task) -> None:
        with self._cursor() as cursor:
            cursor.execute(
                "UPDATE processing_jobs SET attempts = attempts + 1, updated_at = now() "
                "WHERE call_id = %s",
                (task.call_id,),
            )

    def fail_task(self, task: Task, code: str, message: str) -> None:
        exhausted = task.attempts + 1 >= self._config.worker.max_attempts
        status = STATUS_FAILED if exhausted else task.stage
        with self._cursor() as cursor:
            cursor.execute(
                """
                UPDATE processing_jobs
                SET status = %s, error_code = %s, last_error = %s, updated_at = now()
                WHERE call_id = %s
                """,
                (status, code, message, task.call_id),
            )
        logger.info("call %s moved to %s (%s)", task.call_id, status, code)

    def save_transcript(
        self, task: Task, segments: list[Segment], plain: str, duration_seconds: float
    ) -> None:
        payload = {SEGMENTS_KEY: [asdict(segment) for segment in segments]}
        with self._connection.transaction(), self._cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO asr_results (call_id, model, language, duration_ms, plain, raw)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (call_id) DO UPDATE
                SET model = EXCLUDED.model,
                    language = EXCLUDED.language,
                    duration_ms = EXCLUDED.duration_ms,
                    plain = EXCLUDED.plain,
                    raw = EXCLUDED.raw,
                    created_at = now()
                """,
                (
                    task.call_id,
                    self._config.asr.repo_id,
                    self._config.asr.transcript.language,
                    int(duration_seconds * MILLISECONDS_PER_SECOND),
                    plain,
                    json.dumps(payload, ensure_ascii=False),
                ),
            )
            _advance(cursor, task.call_id, STATUS_TRANSCRIBED)

    def transcript_of(self, call_id: int) -> tuple[str | None, str | None]:
        with self._cursor() as cursor:
            cursor.execute(
                """
                SELECT r.plain, a.display_name
                FROM calls c
                LEFT JOIN asr_results r ON r.call_id = c.id
                LEFT JOIN agents a ON a.id = c.agent_id
                WHERE c.id = %s
                """,
                (call_id,),
            )
            row = cursor.fetchone()
        return (row["plain"], row["display_name"]) if row else (None, None)

    def save_analysis(
        self, task: Task, analysis: Analysis, audio_path: str, seconds: int
    ) -> None:
        with self._connection.transaction(), self._cursor() as cursor:
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
                    processing_seconds = EXCLUDED.processing_seconds,
                    created_at = now()
                """,
                (
                    task.call_id,
                    analysis.call_type,
                    analysis.summary,
                    json.dumps(analysis.strengths, ensure_ascii=False),
                    json.dumps(analysis.weaknesses, ensure_ascii=False),
                    json.dumps(analysis.recommendations, ensure_ascii=False),
                    self._config.asr.repo_id,
                    self._config.llm.repo_id,
                    self._config.prompt_label,
                    seconds,
                ),
            )
            cursor.execute("DELETE FROM criterion_scores WHERE call_id = %s", (task.call_id,))
            cursor.executemany(
                "INSERT INTO criterion_scores (call_id, criterion_code, score) VALUES (%s, %s, %s)",
                [(task.call_id, code, score) for code, score in analysis.scores.items()],
            )
            cursor.execute(
                "UPDATE calls SET audio_path = %s WHERE id = %s", (audio_path, task.call_id)
            )
            _advance(cursor, task.call_id, STATUS_DONE)


def _advance(cursor: psycopg.Cursor, call_id: int, status: str) -> None:
    cursor.execute(
        """
        UPDATE processing_jobs
        SET status = %s, attempts = 0,
            error_code = NULL, last_error = NULL, updated_at = now()
        WHERE call_id = %s
        """,
        (status, call_id),
    )
