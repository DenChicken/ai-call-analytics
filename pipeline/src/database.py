from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from src.analysis import AnalysisResult, TranscriptSegment
from src.config import Criterion
from src.constants import STATUS_DONE, STATUS_FAILED, STATUS_PENDING, STATUS_PROCESSING


@dataclass(frozen=True)
class QueueItem:
    recording_id: int
    call_id: int
    file_path: Path
    attempts: int
    started_at: datetime


class Database:
    def __init__(self, dsn: str):
        self._connection = psycopg.connect(dsn, row_factory=dict_row, autocommit=False)

    def close(self) -> None:
        self._connection.close()

    def sync_criteria(self, criteria: tuple[Criterion, ...]) -> list[str]:
        codes = [criterion.code for criterion in criteria]
        with self._connection.cursor() as cursor:
            cursor.execute(
                "SELECT code FROM criteria WHERE code = ANY(%s) AND NOT is_active", (codes,)
            )
            revived = [row["code"] for row in cursor.fetchall()]

            for criterion in criteria:
                cursor.execute(
                    """
                    INSERT INTO criteria (code, title) VALUES (%s, %s)
                    ON CONFLICT (code) DO UPDATE
                    SET title = EXCLUDED.title, is_active = TRUE, synced_at = now()
                    """,
                    (criterion.code, criterion.title),
                )

            cursor.execute(
                "UPDATE criteria SET is_active = FALSE, synced_at = now() "
                "WHERE NOT code = ANY(%s) AND is_active",
                (codes,),
            )
        self._connection.commit()
        return revived

    def release_stale(self, timeout_seconds: int, max_attempts: int) -> int:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE recordings
                SET status = CASE WHEN attempts >= %s THEN %s ELSE %s END,
                    claimed_at = NULL,
                    updated_at = now()
                WHERE status = %s
                  AND claimed_at < now() - make_interval(secs => %s)
                """,
                (max_attempts, STATUS_FAILED, STATUS_PENDING, STATUS_PROCESSING, timeout_seconds),
            )
            released = cursor.rowcount
        self._connection.commit()
        return released

    def claim_next(self) -> QueueItem | None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE recordings
                SET status = %s, claimed_at = now(), attempts = attempts + 1, updated_at = now()
                WHERE id = (
                    SELECT id FROM recordings
                    WHERE status = %s
                    ORDER BY id
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                RETURNING id, call_id, file_path, attempts,
                          (SELECT started_at FROM calls WHERE calls.id = recordings.call_id)
                          AS started_at
                """,
                (STATUS_PROCESSING, STATUS_PENDING),
            )
            row = cursor.fetchone()
        self._connection.commit()
        if row is None:
            return None
        return QueueItem(
            recording_id=row["id"],
            call_id=row["call_id"],
            file_path=Path(row["file_path"]),
            attempts=row["attempts"],
            started_at=row["started_at"],
        )

    def save_analysis(
        self,
        item: QueueItem,
        result: AnalysisResult,
        segments: list[TranscriptSegment],
        asr_model: str,
        llm_model: str,
        prompt_version: str,
        processing_seconds: int,
        file_path: Path,
    ) -> None:
        with self._connection.transaction():
            with self._connection.cursor() as cursor:
                cursor.execute("DELETE FROM analyses WHERE call_id = %s", (item.call_id,))
                cursor.execute(
                    """
                    INSERT INTO analyses (
                        call_id, summary, strengths, weaknesses, recommendations,
                        asr_model, llm_model, prompt_version, processing_seconds
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        item.call_id,
                        result.summary,
                        result.strengths,
                        result.weaknesses,
                        result.recommendations,
                        asr_model,
                        llm_model,
                        prompt_version,
                        processing_seconds,
                    ),
                )
                analysis_id = cursor.fetchone()["id"]

                cursor.executemany(
                    "INSERT INTO criterion_scores (analysis_id, criterion_code, score) "
                    "VALUES (%s, %s, %s)",
                    [(analysis_id, code, score) for code, score in result.scores.items()],
                )

                cursor.executemany(
                    "INSERT INTO transcript_segments "
                    "(analysis_id, idx, speaker, start_ms, end_ms, text) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    [
                        (analysis_id, idx, s.speaker, s.start_ms, s.end_ms, s.text)
                        for idx, s in enumerate(segments)
                    ],
                )

                cursor.execute(
                    "UPDATE recordings SET status = %s, file_path = %s, claimed_at = NULL, "
                    "last_error = NULL, updated_at = now() WHERE id = %s",
                    (STATUS_DONE, str(file_path), item.recording_id),
                )

    def mark_failed(self, item: QueueItem, error: str, max_attempts: int) -> None:
        status = STATUS_FAILED if item.attempts >= max_attempts else STATUS_PENDING
        with self._connection.cursor() as cursor:
            cursor.execute(
                "UPDATE recordings SET status = %s, claimed_at = NULL, last_error = %s, "
                "updated_at = now() WHERE id = %s",
                (status, error, item.recording_id),
            )
        self._connection.commit()
