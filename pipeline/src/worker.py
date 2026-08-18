import logging
import time
from dataclasses import dataclass
from pathlib import Path

from src import shutdown
from src.analysis import analyze
from src.asr import Asr
from src.config import Config
from src.constants import DONE_DIR_TEMPLATE, STATUS_FAILED, STATUS_PENDING
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
            shutdown.sleep(config.worker.poll_interval_seconds)
            continue

        started = time.monotonic()
        logger.info("call %s claimed from %s (attempt %s)", task.call_id, task.stage, task.attempts)
        try:
            if task.stage == STATUS_PENDING:
                _transcribe(config, database, models, task)
            else:
                _analyze(config, database, models, task, started)
        except shutdown.ShutdownRequested:
            database.release_task(task.call_id, task.stage)
            raise
        except Exception as error:
            logger.exception("call %s failed", task.call_id)
            exhausted = task.attempts >= config.worker.max_attempts
            status = STATUS_FAILED if exhausted else task.stage
            database.release_task(task.call_id, status, str(error))
            logger.info("call %s moved to %s after attempt %s", task.call_id, status, task.attempts)
            shutdown.check()


def _transcribe(config: Config, database: Database, models: Models, task: Task) -> None:
    audio_path = Path(task.audio_path)
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
    logger.info("call %s transcribed into %s segments", task.call_id, len(segments))


def _analyze(
    config: Config, database: Database, models: Models, task: Task, started: float
) -> None:
    plain = database.load_plain(task.call_id)
    if not plain:
        raise ValueError("stored transcription is empty")

    criteria = database.enabled_criteria()
    if not criteria:
        raise ValueError("no enabled criteria")

    analysis, scores = analyze(
        config, models.llm, criteria, plain, database.manager_name(task.call_id)
    )

    source = Path(task.audio_path)
    target = _done_path(config, source)
    metadata = {
        "asr_model": models.asr.model_name,
        "analysis_model": models.llm.model_name,
        "prompt_label": config.prompt.label,
        "processing_seconds": int(time.monotonic() - started),
    }
    database.save_analysis(task.call_id, analysis, scores, metadata, str(target))
    if target != source:
        source.replace(target)
    logger.info("call %s analyzed as %s", task.call_id, analysis["call_type"])


def _done_path(config: Config, source: Path) -> Path:
    if source.is_relative_to(config.storage.done_dir) or not source.is_file():
        return source
    target_dir = config.storage.done_dir / time.strftime(DONE_DIR_TEMPLATE)
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / source.name
