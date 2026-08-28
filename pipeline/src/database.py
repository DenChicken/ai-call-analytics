import json
import logging
from collections.abc import Callable
from dataclasses import asdict, dataclass

import psycopg
from psycopg.rows import dict_row

from src.analysis import Analysis
from src.config import Reference
from src.constants import (
    CALL_TYPES_TABLE,
    CLAIMABLE_STATUSES,
    CLAIMED_STATUS,
    CRITERIA_TABLE,
    ERROR_STALE_CLAIM,
    MILLISECONDS_PER_SECOND,
    RELEASED_STATUS,
    STAGE_PRIORITY,
    STATUS_DONE,
    STATUS_FAILED,
    STATUS_TRANSCRIBED,
)
from src.transcript import Segment

SEGMENTS_KEY = "segments"
REFERENCE_TABLES = (CRITERIA_TABLE, CALL_TYPES_TABLE)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Task:
    call_id: int
    audio_path: str
    stage: str
    attempts: int


@dataclass(frozen=True)
class AnalysisMetadata:
    asr_model: str
    analysis_model: str
    prompt_label: str
    processing_seconds: int


class Database:
    def __init__(self, dsn: str):
        self._connection = psycopg.connect(dsn, row_factory=dict_row, autocommit=True)
        logger.info("connected to the database")

    def close(self) -> None:
        self._connection.close()

    def sync_reference(self, table: str, entries: list[Reference]) -> int:
        if table not in REFERENCE_TABLES:
            raise ValueError(f"unknown reference table: {table}")
        codes = [entry.code for entry in entries]
        with self._connection.transaction():
            with self._connection.cursor() as cursor:
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
                    f"UPDATE {table} SET enabled = FALSE WHERE enabled AND NOT (code = ANY(%s))",
                    (codes,),
                )
                return cursor.rowcount

    def enabled_reference(self, table: str) -> list[Reference]:
        if table not in REFERENCE_TABLES:
            raise ValueError(f"unknown reference table: {table}")
        with self._connection.cursor() as cursor:
            cursor.execute(
                f"SELECT code, label, description FROM {table} WHERE enabled ORDER BY position"
            )
            rows = cursor.fetchall()
        return [
            Reference(code=row["code"], label=row["label"], description=row["description"])
            for row in rows
        ]

    def reset_stale_claims(self, stale_seconds: float, max_attempts: int) -> int:
        released = 0
        with self._connection.transaction():
            with self._connection.cursor() as cursor:
                for claimed, stage in RELEASED_STATUS.items():
                    cursor.execute(
                        """
                        UPDATE processing_jobs
                        SET status = CASE WHEN attempts >= %s THEN %s ELSE %s END,
                            claimed_at = NULL,
                            error_code = CASE WHEN attempts >= %s THEN %s ELSE error_code END,
                            last_error = CASE WHEN attempts >= %s THEN %s ELSE last_error END,
                            updated_at = now()
                        WHERE status = %s
                          AND claimed_at < now() - make_interval(secs => %s)
                        """,
                        (
                            max_attempts,
                            STATUS_FAILED,
                            stage,
                            max_attempts,
                            ERROR_STALE_CLAIM,
                            max_attempts,
                            f"claim went stale after {stale_seconds}s",
                            claimed,
                            stale_seconds,
                        ),
                    )
                    if cursor.rowcount:
                        logger.trace(
                            "released %s jobs from %s back to %s",
                            cursor.rowcount,
                            claimed,
                            stage,
                        )
                    released += cursor.rowcount
        return released

    def claim_task(self, max_attempts: int) -> Task | None:
        with self._connection.transaction():
            with self._connection.cursor() as cursor:
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
                        claimed_at = now(), updated_at = now(),
                        error_code = NULL, last_error = NULL
                    WHERE call_id = %s
                    RETURNING attempts
                    """,
                    (CLAIMED_STATUS[row["status"]], row["call_id"]),
                )
                attempts = cursor.fetchone()["attempts"]

        logger.debug(
            "claimed call %s: %s -> %s, attempt %s of %s",
            row["call_id"],
            row["status"],
            CLAIMED_STATUS[row["status"]],
            attempts,
            max_attempts,
        )
        return Task(
            call_id=row["call_id"],
            audio_path=row["audio_path"],
            stage=row["status"],
            attempts=attempts,
        )

    def release_task(
        self,
        call_id: int,
        claimed_status: str,
        status: str,
        error_code: str | None,
        error: str | None,
        refund_attempt: bool = False,
    ) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE processing_jobs
                SET status = %s, claimed_at = NULL, error_code = %s, last_error = %s,
                    attempts = CASE WHEN %s THEN greatest(attempts - 1, 0) ELSE attempts END,
                    updated_at = now()
                WHERE call_id = %s AND status = %s
                """,
                (status, error_code, error, refund_attempt, call_id, claimed_status),
            )
            if not cursor.rowcount:
                logger.warning(
                    "call %s is no longer %s, leaving it untouched", call_id, claimed_status
                )

    def analysis_input(self, call_id: int) -> tuple[str | None, str | None]:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT r.plain, ag.display_name
                FROM calls c
                LEFT JOIN asr_results r ON r.call_id = c.id
                LEFT JOIN agents ag ON ag.id = c.agent_id
                WHERE c.id = %s
                """,
                (call_id,),
            )
            row = cursor.fetchone()
        if row is None:
            return None, None
        return row["plain"], row["display_name"]

    def save_asr_result(
        self,
        call_id: int,
        segments: list[Segment],
        plain: str,
        model: str,
        language: str,
        duration_seconds: float,
    ) -> None:
        payload = {SEGMENTS_KEY: [asdict(segment) for segment in segments]}
        with self._connection.transaction():
            with self._connection.cursor() as cursor:
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
                        call_id,
                        model,
                        language,
                        int(duration_seconds * MILLISECONDS_PER_SECOND),
                        plain,
                        json.dumps(payload, ensure_ascii=False),
                    ),
                )
                _advance(cursor, call_id, STATUS_TRANSCRIBED)
        logger.debug(
            "saved asr result for call %s: %s segments, plain %s chars",
            call_id,
            len(segments),
            len(plain),
        )

    def save_analysis(
        self,
        call_id: int,
        analysis: Analysis,
        metadata: AnalysisMetadata,
        audio_path: str,
        move_audio: Callable[[], None],
    ) -> None:
        with self._connection.transaction():
            with self._connection.cursor() as cursor:
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
                        call_id,
                        analysis.call_type,
                        analysis.summary,
                        json.dumps(analysis.strengths, ensure_ascii=False),
                        json.dumps(analysis.weaknesses, ensure_ascii=False),
                        json.dumps(analysis.recommendations, ensure_ascii=False),
                        metadata.asr_model,
                        metadata.analysis_model,
                        metadata.prompt_label,
                        metadata.processing_seconds,
                    ),
                )

                cursor.execute("DELETE FROM criterion_scores WHERE call_id = %s", (call_id,))
                cursor.executemany(
                    """
                    INSERT INTO criterion_scores (call_id, criterion_code, score)
                    VALUES (%s, %s, %s)
                    """,
                    [(call_id, code, score) for code, score in analysis.scores.items()],
                )

                cursor.execute(
                    "UPDATE calls SET audio_path = %s WHERE id = %s", (audio_path, call_id)
                )
                _advance(cursor, call_id, STATUS_DONE)
                move_audio()
        logger.debug(
            "saved analysis for call %s: type=%s, %s scores, audio at %s",
            call_id,
            analysis.call_type,
            len(analysis.scores),
            audio_path,
        )


def _advance(cursor, call_id: int, status: str) -> None:
    cursor.execute(
        """
        UPDATE processing_jobs
        SET status = %s, attempts = 0, claimed_at = NULL,
            error_code = NULL, last_error = NULL, updated_at = now()
        WHERE call_id = %s
        """,
        (status, call_id),
    )
    if not cursor.rowcount:
        raise RuntimeError(f"call {call_id} has no processing job to advance to {status}")
