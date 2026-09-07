import logging
import time
from pathlib import Path

from licensing.license import License
from licensing.verify_runtime import is_expired

from src import shutdown
from src.analysis import analyze
from src.asr import Asr
from src.config import Config, storage_path
from src.constants import (
    CALL_TYPES_TABLE,
    CLAIMED_STATUS,
    CRITERIA_TABLE,
    DONE_DIR_TEMPLATE,
    ERROR_ASR_EMPTY,
    ERROR_AUDIO_MISSING,
    ERROR_NO_CALL_TYPES,
    ERROR_NO_CRITERIA,
    ERROR_TRANSCRIPT_EMPTY,
    STATUS_FAILED,
    STATUS_PENDING,
)
from src.database import AnalysisMetadata, Database, Task
from src.errors import StageError, UnrecoverableError, classify
from src.llm import Llm
from src.transcript import render_plain

logger = logging.getLogger(__name__)


def run(config: Config, database: Database, asr: Asr, llm: Llm, license: License) -> None:
    worker = config.worker
    while not shutdown.is_stopping():
        if is_expired(license):
            logger.error("license expired on %s, stopping", license.expires)
            raise shutdown.LicenseExpired()

        task = database.claim_task(worker.max_attempts)
        if task is None:
            released = database.reset_stale_claims(
                worker.stale_claim_seconds, worker.max_attempts
            )
            if released:
                logger.info("released %s stale claims", released)
                continue
            logger.debug("no tasks, sleeping %ss", worker.poll_interval_seconds)
            shutdown.sleep(worker.poll_interval_seconds)
            continue

        started = time.monotonic()
        audio_path = config.storage.data_dir / task.audio_path
        logger.info("call %s claimed from %s (attempt %s)", task.call_id, task.stage, task.attempts)
        logger.trace("call %s audio at %s", task.call_id, audio_path)
        try:
            if task.stage == STATUS_PENDING:
                _transcribe(config, database, asr, task, audio_path, started)
            else:
                _analyze(config, database, asr, llm, task, audio_path, started)
        except shutdown.ShutdownRequested:
            _release(database, task, task.stage, None)
            raise
        except UnrecoverableError as error:
            logger.error(
                "call %s returned to the queue, the environment is unusable: %s",
                task.call_id,
                error,
            )
            _release(database, task, task.stage, None)
            raise
        except Exception as error:
            logger.exception(
                "call %s failed at stage %s after %ss",
                task.call_id,
                task.stage,
                int(time.monotonic() - started),
            )
            exhausted = task.attempts >= worker.max_attempts
            _release(database, task, STATUS_FAILED if exhausted else task.stage, error)
            shutdown.check()


def _release(database: Database, task: Task, status: str, error: Exception | None) -> None:
    claimed = CLAIMED_STATUS[task.stage]
    code = classify(error) if error else None
    try:
        database.release_task(
            task.call_id,
            claimed,
            status,
            code,
            str(error) if error else None,
            refund_attempt=error is None,
        )
    except Exception:
        logger.exception("could not release call %s, leaving it claimed", task.call_id)
        return
    logger.info("call %s moved to %s (%s)", task.call_id, status, code or "interrupted")


def _transcribe(
    config: Config, database: Database, asr: Asr, task: Task, audio_path: Path, started: float
) -> None:
    if not audio_path.is_file():
        raise StageError(ERROR_AUDIO_MISSING, f"audio file not found: {audio_path}")

    segments, duration = asr.transcribe(audio_path)
    if not segments:
        raise StageError(ERROR_ASR_EMPTY, "transcription produced no segments")

    database.save_asr_result(
        task.call_id,
        segments,
        plain=render_plain(segments),
        model=asr.model_name,
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
    config: Config,
    database: Database,
    asr: Asr,
    llm: Llm,
    task: Task,
    audio_path: Path,
    started: float,
) -> None:
    plain, manager_name = database.analysis_input(task.call_id)
    if not plain:
        raise StageError(ERROR_TRANSCRIPT_EMPTY, "stored transcription is empty")

    criteria = database.enabled_reference(CRITERIA_TABLE)
    if not criteria:
        raise StageError(ERROR_NO_CRITERIA, "no enabled criteria")

    call_types = database.enabled_reference(CALL_TYPES_TABLE)
    if not call_types:
        raise StageError(ERROR_NO_CALL_TYPES, "no enabled call types")

    logger.trace(
        "call %s: transcript %s chars, criteria %s, types %s",
        task.call_id,
        len(plain),
        [entry.code for entry in criteria],
        [entry.code for entry in call_types],
    )

    if not audio_path.is_file():
        raise StageError(ERROR_AUDIO_MISSING, f"audio file not found: {audio_path}")

    analysis = analyze(config, llm, criteria, call_types, plain, manager_name)

    target = _done_path(config, audio_path)
    database.save_analysis(
        task.call_id,
        analysis,
        AnalysisMetadata(
            asr_model=asr.model_name,
            analysis_model=llm.model_name,
            prompt_label=config.prompt.label,
            processing_seconds=int(time.monotonic() - started),
        ),
        storage_path(config.storage.data_dir, target),
        lambda: audio_path.replace(target),
    )
    logger.info(
        "call %s analyzed as %s in %ss",
        task.call_id,
        analysis.call_type,
        int(time.monotonic() - started),
    )


def _done_path(config: Config, source: Path) -> Path:
    if source.is_relative_to(config.storage.done_dir):
        return source
    target_dir = config.storage.done_dir / time.strftime(DONE_DIR_TEMPLATE)
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / source.name
