import logging
import time
from pathlib import Path

import psycopg
from licensing.license import License
from licensing.verify_runtime import is_expired

from src import shutdown
from src.analysis import analyze
from src.asr import Asr
from src.config import Config, storage_path
from src.constants import (
    CALL_TYPES_TABLE,
    CRITERIA_TABLE,
    DONE_DIR_TEMPLATE,
    ERROR_ASR_EMPTY,
    ERROR_AUDIO_MISSING,
    ERROR_NO_CALL_TYPES,
    ERROR_NO_CRITERIA,
    ERROR_TRANSCRIPT_EMPTY,
    STATUS_PENDING,
)
from src.db import Database, Task
from src.errors import CallError, FatalError, error_code
from src.llm import Llm
from src.transcript import render_plain

logger = logging.getLogger(__name__)


def run(config: Config, database: Database, asr: Asr, llm: Llm, license: License) -> None:
    while not shutdown.is_stopping():
        if is_expired(license):
            raise shutdown.LicenseExpired(f"license expired on {license.expires}")

        task = database.next_task()
        if task is None:
            logger.debug("no tasks, sleeping %ss", config.worker.poll_interval_seconds)
            shutdown.sleep(config.worker.poll_interval_seconds)
            continue

        _process(config, database, asr, llm, task)


def _process(config: Config, database: Database, asr: Asr, llm: Llm, task: Task) -> None:
    started = time.monotonic()
    audio_path = config.paths.data_dir / task.audio_path
    logger.info(
        "call %s at stage %s, attempt %s of %s",
        task.call_id,
        task.stage,
        task.attempts + 1,
        config.worker.max_attempts,
    )
    logger.trace("call %s audio at %s", task.call_id, audio_path)

    database.start_attempt(task)
    try:
        if task.stage == STATUS_PENDING:
            _transcribe(database, asr, task, audio_path)
        else:
            _analyze(config, database, llm, task, audio_path, started)
    except (shutdown.ShutdownRequested, FatalError):
        raise
    except psycopg.Error as error:
        raise FatalError(f"database failed while processing call {task.call_id}: {error}") from error
    except CallError as error:
        logger.error("call %s failed: %s", task.call_id, error)
        database.fail_task(task, error.code, str(error))
    except Exception as error:
        logger.exception("call %s failed unexpectedly", task.call_id)
        database.fail_task(task, error_code(error), str(error))
        shutdown.check()


def _transcribe(database: Database, asr: Asr, task: Task, audio_path: Path) -> None:
    if not audio_path.is_file():
        raise CallError(ERROR_AUDIO_MISSING, f"audio file not found: {audio_path}")

    segments, duration = asr.transcribe(audio_path)
    if not segments:
        raise CallError(ERROR_ASR_EMPTY, "transcription produced no segments")

    database.save_transcript(task, segments, render_plain(segments), duration)
    logger.info("call %s transcribed into %s segments", task.call_id, len(segments))


def _analyze(
    config: Config,
    database: Database,
    llm: Llm,
    task: Task,
    audio_path: Path,
    started: float,
) -> None:
    plain, manager_name = database.transcript_of(task.call_id)
    if not plain:
        raise CallError(ERROR_TRANSCRIPT_EMPTY, "stored transcription is empty")

    criteria = database.enabled_references(CRITERIA_TABLE)
    if not criteria:
        raise CallError(ERROR_NO_CRITERIA, "no enabled criteria")

    call_types = database.enabled_references(CALL_TYPES_TABLE)
    if not call_types:
        raise CallError(ERROR_NO_CALL_TYPES, "no enabled call types")

    if not audio_path.is_file():
        raise CallError(ERROR_AUDIO_MISSING, f"audio file not found: {audio_path}")

    logger.trace(
        "call %s: transcript %s chars, criteria %s, types %s",
        task.call_id,
        len(plain),
        [entry.code for entry in criteria],
        [entry.code for entry in call_types],
    )

    analysis = analyze(config, llm, criteria, call_types, plain, manager_name)

    stored_path = _move_to_done(config, audio_path)
    database.save_analysis(
        task,
        analysis,
        storage_path(config.paths.data_dir, stored_path),
        int(time.monotonic() - started),
    )
    logger.info(
        "call %s analyzed as %s in %ss",
        task.call_id,
        analysis.call_type,
        int(time.monotonic() - started),
    )


def _move_to_done(config: Config, source: Path) -> Path:
    if source.is_relative_to(config.done_dir):
        return source
    target_dir = config.done_dir / time.strftime(DONE_DIR_TEMPLATE)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / source.name
    source.replace(target)
    logger.trace("moved %s to %s", source.name, target.parent)
    return target
