import logging
import time
from dataclasses import dataclass
from pathlib import Path

from src import shutdown
from src.analysis import analyze
from src.asr import Asr
from src.config import Config, storage_path
from src.constants import (
    CALL_TYPE_FIELD,
    CALL_TYPES_TABLE,
    CRITERIA_TABLE,
    DONE_DIR_TEMPLATE,
    METADATA_ANALYSIS_MODEL,
    METADATA_ASR_MODEL,
    METADATA_PROCESSING_SECONDS,
    METADATA_PROMPT_LABEL,
    STATUS_FAILED,
    STATUS_PENDING,
)
from src.database import Database, Task
from src.llm import Llm
from src.transcript import render_plain, render_transcript

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Models:
    asr: Asr
    llm: Llm


def run(config: Config, database: Database, models: Models) -> None:
    while not shutdown.is_stopping():
        task = database.claim_task(config.worker.max_attempts)
        if task is None:
            logger.debug("no tasks, sleeping %ss", config.worker.poll_interval_seconds)
            shutdown.sleep(config.worker.poll_interval_seconds)
            continue

        started = time.monotonic()
        logger.info("call %s claimed from %s (attempt %s)", task.call_id, task.stage, task.attempts)
        try:
            if task.stage == STATUS_PENDING:
                _transcribe(config, database, models, task, started)
            else:
                _analyze(config, database, models, task, started)
        except shutdown.ShutdownRequested:
            database.release_task(task.call_id, task.stage)
            raise
        except Exception as error:
            logger.exception(
                "call %s failed at stage %s after %ss",
                task.call_id,
                task.stage,
                int(time.monotonic() - started),
            )
            exhausted = task.attempts >= config.worker.max_attempts
            status = STATUS_FAILED if exhausted else task.stage
            database.release_task(task.call_id, status, str(error))
            logger.info(
                "call %s moved to %s after attempt %s of %s",
                task.call_id,
                status,
                task.attempts,
                config.worker.max_attempts,
            )
            shutdown.check()


def _transcribe(
    config: Config, database: Database, models: Models, task: Task, started: float
) -> None:
    audio_path = config.storage.root_dir / task.audio_path
    if not audio_path.is_file():
        raise FileNotFoundError(f"audio file not found: {audio_path}")

    segments, duration = models.asr.transcribe(audio_path)
    if not segments:
        raise ValueError("transcription produced no segments")

    database.save_asr_result(
        task.call_id,
        segments,
        plain=render_plain(segments),
        transcript=render_transcript(segments, config.asr.transcript.break_silence_ms),
        model=models.asr.model_name,
        language=config.asr.transcript.language,
        duration_seconds=duration,
    )
    logger.info(
        "call %s transcribed into %s segments in %ss",
        task.call_id,
        len(segments),
        int(time.monotonic() - started),
    )


def _analyze(
    config: Config, database: Database, models: Models, task: Task, started: float
) -> None:
    plain = database.load_plain(task.call_id)
    if not plain:
        raise ValueError("stored transcription is empty")

    criteria = database.enabled_reference(CRITERIA_TABLE)
    if not criteria:
        raise ValueError("no enabled criteria")

    call_types = database.enabled_reference(CALL_TYPES_TABLE)
    if not call_types:
        raise ValueError("no enabled call types")

    analysis, scores = analyze(
        config, models.llm, criteria, call_types, plain, database.manager_name(task.call_id)
    )

    source = config.storage.root_dir / task.audio_path
    target = _done_path(config, source)
    metadata = {
        METADATA_ASR_MODEL: models.asr.model_name,
        METADATA_ANALYSIS_MODEL: models.llm.model_name,
        METADATA_PROMPT_LABEL: config.prompt.label,
        METADATA_PROCESSING_SECONDS: int(time.monotonic() - started),
    }
    database.save_analysis(
        task.call_id,
        analysis,
        scores,
        metadata,
        storage_path(config.storage.root_dir, target),
    )
    if target != source:
        source.replace(target)
    logger.info(
        "call %s analyzed as %s in %ss",
        task.call_id,
        analysis[CALL_TYPE_FIELD],
        metadata[METADATA_PROCESSING_SECONDS],
    )


def _done_path(config: Config, source: Path) -> Path:
    if source.is_relative_to(config.storage.done_dir) or not source.is_file():
        return source
    target_dir = config.storage.done_dir / time.strftime(DONE_DIR_TEMPLATE)
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / source.name
