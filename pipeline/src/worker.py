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
from src.diarization import Diarization
from src.llm import Llm
from src.transcript import build_segments

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Models:
    asr: Asr
    diarization: Diarization
    llm: Llm


def run(config: Config, database: Database, models: Models) -> None:
    while not shutdown.is_stopping():
        task = database.claim_task(config.worker.max_attempts)
        if task is None:
            shutdown.sleep(config.worker.poll_interval_seconds)
            continue

        started = time.monotonic()
        logger.info(
            "call %s claimed from %s (attempt %s)", task.call_id, task.stage, task.attempts
        )
        try:
            if task.stage == STATUS_PENDING:
                _transcribe(database, models, task)
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


def _transcribe(database: Database, models: Models, task: Task) -> None:
    audio_path = Path(task.audio_path)
    if not audio_path.is_file():
        raise FileNotFoundError(f"audio file not found: {audio_path}")

    words = models.asr.transcribe(audio_path)
    if not words:
        raise ValueError("transcription produced no words")

    turns = models.diarization.diarize(audio_path)
    if not turns:
        raise ValueError("diarization produced no speaker turns")

    segments = build_segments(words, turns)
    database.save_transcript(task.call_id, segments)
    logger.info("call %s transcribed into %s segments", task.call_id, len(segments))


def _analyze(
    config: Config, database: Database, models: Models, task: Task, started: float
) -> None:
    segments = database.load_transcript(task.call_id)
    if not segments:
        raise ValueError("stored transcript is empty")

    criteria = database.enabled_criteria()
    if not criteria:
        raise ValueError("no enabled criteria")

    analysis, scores = analyze(config, models.llm, criteria, segments)
    final_path = _move_to_done(config, task)
    metadata = {
        "asr_model": models.asr.model_name,
        "llm_model": models.llm.model_name,
        "prompt_label": config.prompt.label,
        "processing_seconds": int(time.monotonic() - started),
    }
    database.save_analysis(task.call_id, analysis, scores, metadata, str(final_path))
    logger.info("call %s analyzed and stored", task.call_id)


def _move_to_done(config: Config, task: Task) -> Path:
    source = Path(task.audio_path)
    if source.is_relative_to(config.storage.done_dir) or not source.is_file():
        return source
    target_dir = config.storage.done_dir / time.strftime(DONE_DIR_TEMPLATE)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / source.name
    source.replace(target)
    return target
