import logging
import threading
import time

from src.analysis import assign_roles, build_analysis_model, speaker_labels, to_result
from src.config import Config
from src.database import Database, QueueItem
from src.models import Analyzer, Transcriber
from src.storage import move_back_to_pending, move_to_done, move_to_processing

logger = logging.getLogger(__name__)


def process_item(
    config: Config,
    database: Database,
    transcriber: Transcriber,
    analyzer: Analyzer,
    item: QueueItem,
) -> None:
    started = time.monotonic()
    working_path = move_to_processing(config.storage, item.file_path)

    segments = transcriber.transcribe(working_path)
    if not segments:
        raise ValueError("transcription produced no segments")

    schema = build_analysis_model(config.llm.criteria, speaker_labels(segments))
    payload = analyzer.analyze(segments, schema)
    result = to_result(payload)
    segments = assign_roles(segments, result.agent_speaker)

    final_path = move_to_done(config.storage, working_path, item.started_at)
    database.save_analysis(
        item=item,
        result=result,
        segments=segments,
        asr_model=transcriber.name,
        llm_model=analyzer.name,
        prompt_version=config.llm.prompt_version,
        processing_seconds=int(time.monotonic() - started),
        file_path=final_path,
    )
    logger.info("call %s analyzed in %.0fs", item.call_id, time.monotonic() - started)


def run_worker(
    name: str,
    config: Config,
    database: Database,
    transcriber: Transcriber,
    analyzer: Analyzer,
    stop: threading.Event,
) -> None:
    logger.info("worker %s started", name)
    while not stop.is_set():
        item = database.claim_next()
        if item is None:
            stop.wait(config.worker.poll_interval_seconds)
            continue

        logger.info("worker %s took call %s (attempt %s)", name, item.call_id, item.attempts)
        try:
            process_item(config, database, transcriber, analyzer, item)
        except Exception as error:
            logger.exception("worker %s failed on call %s", name, item.call_id)
            move_back_to_pending(config.storage, config.storage.processing_dir / item.file_path.name)
            database.mark_failed(item, str(error), config.worker.max_attempts)
    logger.info("worker %s stopped", name)
