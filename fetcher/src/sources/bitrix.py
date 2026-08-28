import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.config import (
    FetchConfig,
    NetworkConfig,
    SourceConfig,
    read_secret_file,
    require_option,
    resolve_inside,
)
from src.constants import (
    DIRECTION_CALLBACK,
    DIRECTION_INBOUND,
    DIRECTION_OUTBOUND,
    DIRECTION_UNKNOWN,
)
from src.source import NAME_SEPARATOR, Agent, Call, CallBatch, Source, sanitize_name_part
from src.sources.bitrix_client import BitrixClient

METHOD_STATISTIC = "voximplant.statistic.get"
METHOD_FILE_GET = "disk.file.get"
METHOD_USER_GET = "user.get"
METHOD_ACTIVITY_GET = "crm.activity.get"

DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"
FILE_NAME_TIME_FORMAT = "%Y%m%d%H%M%S"
AUDIO_EXTENSION = ".mp3"
UNKNOWN_AGENT_PART = "unknown"
EMPTY_ID = "0"

CALL_TYPE_DIRECTIONS = {
    "1": DIRECTION_OUTBOUND,
    "2": DIRECTION_INBOUND,
    "3": DIRECTION_INBOUND,
    "4": DIRECTION_CALLBACK,
    "5": DIRECTION_UNKNOWN,
}

ENTITY_PATHS = {
    "LEAD": "lead",
    "DEAL": "deal",
    "CONTACT": "contact",
    "COMPANY": "company",
}

RAW_FIELDS = (
    "CALL_ID",
    "CALL_TYPE",
    "CALL_FAILED_CODE",
    "CALL_FAILED_REASON",
    "CRM_ENTITY_TYPE",
    "CRM_ENTITY_ID",
    "CRM_ACTIVITY_ID",
    "PORTAL_USER_ID",
    "PORTAL_NUMBER",
    "RECORD_FILE_ID",
    "RECORD_DURATION",
    "SESSION_ID",
    "COST",
    "COST_CURRENCY",
)

logger = logging.getLogger(__name__)


class BitrixSource(Source):
    def __init__(self, source_config: SourceConfig, network: NetworkConfig, fetch: FetchConfig):
        self._name = source_config.name
        self._initial_lookback_days = fetch.initial_lookback_days
        self._max_records_per_cycle = fetch.max_records_per_cycle
        self._min_duration_seconds = fetch.min_call_duration_seconds
        self._max_duration_seconds = fetch.max_call_duration_seconds
        self._portal_url = str(require_option(source_config, "portal_url")).rstrip("/")
        self._client = BitrixClient(
            read_secret_file(
                resolve_inside(
                    source_config.secrets_dir,
                    require_option(source_config, "rest_url_file"),
                    "rest_url_file",
                    f"source '{source_config.name}'",
                )
            ),
            network,
        )
        self._agents: dict[str, Agent] = {}

    @property
    def name(self) -> str:
        return self._name

    def close(self) -> None:
        self._client.close()

    def list_calls(self, cursor: str | None) -> CallBatch:
        records = self._fetch_statistics(cursor)
        if not records:
            return CallBatch(calls=[], cursor=None)

        no_recording = 0
        too_short = 0
        too_long = 0
        usable = []
        for record in records:
            duration = int(record.get("CALL_DURATION") or 0)
            if not record.get("RECORD_FILE_ID"):
                no_recording += 1
            elif duration < self._min_duration_seconds:
                too_short += 1
            elif duration > self._max_duration_seconds:
                too_long += 1
                logger.warning(
                    "call %s skipped: %ss exceeds max_call_duration_seconds of %ss",
                    record.get("CALL_ID"),
                    duration,
                    self._max_duration_seconds,
                )
            else:
                usable.append(record)

        if no_recording or too_short or too_long:
            logger.info(
                "skipped %s records: %s without recording, %s too short, %s too long",
                no_recording + too_short + too_long,
                no_recording,
                too_short,
                too_long,
            )

        agents = self._resolve_agents(usable)
        subjects = self._resolve_subjects(usable)

        calls = []
        for record in usable:
            logger.trace(
                "record %s: call %s, %ss, type %s",
                record.get("ID"),
                record.get("CALL_ID"),
                record.get("CALL_DURATION"),
                record.get("CALL_TYPE"),
            )
            call_id = record.get("CALL_ID")
            if not call_id:
                logger.warning("record without CALL_ID skipped: %s", record.get("ID"))
                continue
            calls.append(
                Call(
                    external_id=str(call_id),
                    cursor=str(record["ID"]),
                    started_at=datetime.strptime(record["CALL_START_DATE"], DATE_FORMAT),
                    duration_seconds=int(record.get("CALL_DURATION") or 0),
                    direction=CALL_TYPE_DIRECTIONS.get(
                        str(record.get("CALL_TYPE")), DIRECTION_UNKNOWN
                    ),
                    agent=agents.get(str(record.get("PORTAL_USER_ID"))),
                    client_number=record.get("PHONE_NUMBER"),
                    subject=subjects.get(str(record.get("CRM_ACTIVITY_ID"))),
                    crm_link=self._build_crm_link(record),
                    raw={key: record.get(key) for key in RAW_FIELDS if record.get(key) is not None},
                )
            )
        return CallBatch(calls=calls, cursor=str(max(int(r["ID"]) for r in records)))

    def build_file_name(self, call: Call, call_id: int) -> str:
        agent_part = sanitize_name_part(call.agent.external_id) if call.agent else ""
        parts = (
            str(call_id),
            call.started_at.astimezone(timezone.utc).strftime(FILE_NAME_TIME_FORMAT),
            agent_part or UNKNOWN_AGENT_PART,
        )
        return NAME_SEPARATOR.join(parts) + AUDIO_EXTENSION

    def download_audio(self, call: Call, target: Path) -> None:
        file_id = call.raw.get("RECORD_FILE_ID")
        if not file_id:
            raise ValueError(f"call {call.external_id} has no RECORD_FILE_ID")
        body = self._client.call(METHOD_FILE_GET, {"id": file_id})
        result = body.get("result")
        download_url = result.get("DOWNLOAD_URL") if isinstance(result, dict) else None
        if not download_url:
            raise ValueError(f"no DOWNLOAD_URL for file {file_id}")
        self._client.download(download_url, target)

    def _fetch_statistics(self, cursor: str | None) -> list[dict]:
        if cursor is None:
            since = datetime.now(timezone.utc) - timedelta(days=self._initial_lookback_days)
            call_filter = {">=CALL_START_DATE": since.strftime(DATE_FORMAT)}
        else:
            call_filter = {">ID": cursor}

        records = []
        start = 0
        while len(records) < self._max_records_per_cycle:
            body = self._client.call(
                METHOD_STATISTIC,
                {"FILTER": call_filter, "SORT": "ID", "ORDER": "ASC", "start": start},
            )
            page = body.get("result")
            if not isinstance(page, list):
                logger.warning("statistics returned %s instead of a list", type(page).__name__)
                break
            records.extend(page)
            next_start = body.get("next")
            if next_start is None or not page:
                break
            start = next_start
        logger.info("fetched %s call records", len(records))
        logger.debug("filter used: %s", call_filter)
        return records

    def _resolve_agents(self, records: list[dict]) -> dict[str, Agent]:
        wanted = {
            str(record["PORTAL_USER_ID"])
            for record in records
            if record.get("PORTAL_USER_ID")
        }
        missing = sorted(wanted - self._agents.keys())
        if missing:
            commands = {
                user_id: f"{METHOD_USER_GET}?ID={user_id}" for user_id in missing
            }
            for user_id, result in self._client.call_batch(commands).items():
                entries = result if isinstance(result, list) else [result]
                if not entries or not entries[0]:
                    continue
                self._agents[user_id] = self._build_agent(user_id, entries[0])
        return {user_id: self._agents[user_id] for user_id in wanted if user_id in self._agents}

    def _build_agent(self, user_id: str, data: dict) -> Agent:
        parts = [data.get("LAST_NAME"), data.get("NAME"), data.get("SECOND_NAME")]
        display_name = " ".join(part for part in parts if part) or f"user {user_id}"
        return Agent(
            external_id=user_id,
            display_name=display_name,
            first_name=data.get("NAME"),
            last_name=data.get("LAST_NAME"),
            second_name=data.get("SECOND_NAME"),
            email=data.get("EMAIL"),
            profile_link=f"{self._portal_url}/company/personal/user/{user_id}/",
        )

    def _resolve_subjects(self, records: list[dict]) -> dict[str, str]:
        activity_ids = {
            str(record["CRM_ACTIVITY_ID"])
            for record in records
            if str(record.get("CRM_ACTIVITY_ID") or EMPTY_ID) != EMPTY_ID
        }
        if not activity_ids:
            return {}
        commands = {
            activity_id: f"{METHOD_ACTIVITY_GET}?ID={activity_id}"
            for activity_id in sorted(activity_ids)
        }
        subjects = {}
        for activity_id, result in self._client.call_batch(commands).items():
            if isinstance(result, dict) and result.get("SUBJECT"):
                subjects[activity_id] = result["SUBJECT"]
        return subjects

    def _build_crm_link(self, record: dict) -> str | None:
        entity_path = ENTITY_PATHS.get(str(record.get("CRM_ENTITY_TYPE")))
        entity_id = record.get("CRM_ENTITY_ID")
        if not entity_path or not entity_id:
            return None
        return f"{self._portal_url}/crm/{entity_path}/details/{entity_id}/"
