import logging

from src import shutdown
from src.config import Config
from src.constants import TEMP_FILE_SUFFIX
from src.database import Database
from src.source import Source

logger = logging.getLogger(__name__)


def run_once(config: Config, database: Database, source: Source) -> None:
    source_id = database.get_source_id(source.name)
    cursor = database.get_cursor(source_id)

    batch = source.list_calls(cursor, config.fetch.min_call_duration_seconds)
    if batch.cursor is None:
        logger.info("source %s: nothing new since cursor %s", source.name, cursor)
        return

    calls = batch.calls
    known = database.existing_external_ids(source_id, [call.external_id for call in calls])
    new_calls = [call for call in calls if call.external_id not in known]
    logger.info(
        "source %s: %s calls listed, %s already stored, %s to fetch",
        source.name,
        len(calls),
        len(known),
        len(new_calls),
    )

    if not new_calls:
        database.set_cursor(source_id, batch.cursor)
        logger.info("source %s: nothing to fetch, cursor moved to %s", source.name, batch.cursor)
        return

    stored = 0
    skipped = False
    for call in new_calls:
        shutdown.check()
        agent_id = database.upsert_agent(source_id, call.agent) if call.agent else None

        call_id = database.reserve_call_id()
        file_name = source.build_file_name(call, call_id)
        temp_path = config.storage.temp_dir / (file_name + TEMP_FILE_SUFFIX)
        final_path = config.storage.pending_dir / file_name

        try:
            source.download_audio(call, temp_path)
            temp_path.replace(final_path)
        except shutdown.ShutdownRequested:
            temp_path.unlink(missing_ok=True)
            raise
        except Exception as error:
            logger.error("failed to download call %s: %s", call.external_id, error)
            temp_path.unlink(missing_ok=True)
            skipped = True
            continue

        try:
            cursor_value = None if skipped else call.cursor
            inserted = database.insert_call_with_recording(
                call_id, source_id, call, agent_id, str(final_path), cursor_value
            )
        except Exception as error:
            logger.error("failed to store call %s: %s", call.external_id, error)
            final_path.unlink(missing_ok=True)
            skipped = True
            continue

        if inserted:
            stored += 1
        else:
            logger.info("call %s stored by another run, removing file", call.external_id)
            final_path.unlink(missing_ok=True)

        if config.fetch.download_cooldown_seconds:
            shutdown.sleep(config.fetch.download_cooldown_seconds)

    logger.info("source %s: stored %s new calls", source.name, stored)
