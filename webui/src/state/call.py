import logging
from dataclasses import dataclass, field

import reflex as rx

from src import context, errors, formatting
from src.constants import (
    AUDIO_ELEMENT_ID,
    AUDIO_ROUTE,
    DEFAULT_STATUS_COLOR,
    EMPTY_VALUE,
    MILLISECONDS_PER_SECOND,
    STATUS_COLORS,
    STATUS_LABELS,
)
from src.state.auth import AuthState, guarded

logger = logging.getLogger(__name__)

UNKNOWN_CALL_ID = 0
SEGMENT_START_KEY = "start_ms"
SEGMENT_TEXT_KEY = "text"
SEEK_SCRIPT = (
    "const player = document.getElementById('{element}');"
    "if (player) {{ player.currentTime = {seconds}; player.play(); }}"
)


def _as_id(value) -> int:
    text = str(value)
    return int(text) if text.isdigit() else UNKNOWN_CALL_ID


@dataclass
class ScoreRow:
    code: str
    label: str
    met: bool
    enabled: bool


@dataclass
class SegmentRow:
    time: str
    seconds: int
    text: str


@dataclass
class CallData:
    found: bool
    status: str
    status_label: str
    status_color: str
    error: str
    agent_name: str
    manager_id: int
    client: str
    started_at: str
    duration: str
    call_type: str
    crm_link: str
    summary: str
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    scores: list[ScoreRow] = field(default_factory=list)
    score_label: str = EMPTY_VALUE
    segments: list[SegmentRow] = field(default_factory=list)
    audio_url: str = ""
    asr_model: str = EMPTY_VALUE
    analysis_model: str = EMPTY_VALUE
    prompt_label: str = EMPTY_VALUE
    processing_seconds: str = EMPTY_VALUE
    analyzed_at: str = EMPTY_VALUE


class CallState(AuthState):
    current_call_id: int = 0

    found: bool = False
    status: str = ""
    status_label: str = EMPTY_VALUE
    status_color: str = DEFAULT_STATUS_COLOR
    error: str = ""
    agent_name: str = EMPTY_VALUE
    manager_id: int = 0
    client: str = EMPTY_VALUE
    started_at: str = EMPTY_VALUE
    duration: str = EMPTY_VALUE
    call_type: str = EMPTY_VALUE
    crm_link: str = ""
    summary: str = ""
    strengths: list[str] = []
    weaknesses: list[str] = []
    recommendations: list[str] = []
    scores: list[ScoreRow] = []
    score_label: str = EMPTY_VALUE
    segments: list[SegmentRow] = []
    audio_url: str = ""
    asr_model: str = EMPTY_VALUE
    analysis_model: str = EMPTY_VALUE
    prompt_label: str = EMPTY_VALUE
    processing_seconds: str = EMPTY_VALUE
    analyzed_at: str = EMPTY_VALUE

    @rx.event
    def seek(self, seconds: int):
        return rx.call_script(SEEK_SCRIPT.format(element=AUDIO_ELEMENT_ID, seconds=seconds))

    @rx.event
    def load(self):
        if not self.session_login:
            return AuthState.require_session

        self.current_call_id = _as_id(self.call_id)
        if not guarded(self, self._collect):
            return

    def _collect(self) -> None:
        data = collect(self.current_call_id, self.utc_offset)

        self.found = data.found
        self.status = data.status
        self.status_label = data.status_label
        self.status_color = data.status_color
        self.error = data.error
        self.agent_name = data.agent_name
        self.manager_id = data.manager_id
        self.client = data.client
        self.started_at = data.started_at
        self.duration = data.duration
        self.call_type = data.call_type
        self.crm_link = data.crm_link
        self.summary = data.summary
        self.strengths = data.strengths
        self.weaknesses = data.weaknesses
        self.recommendations = data.recommendations
        self.scores = data.scores
        self.score_label = data.score_label
        self.segments = data.segments
        self.audio_url = data.audio_url
        self.asr_model = data.asr_model
        self.analysis_model = data.analysis_model
        self.prompt_label = data.prompt_label
        self.processing_seconds = data.processing_seconds
        self.analyzed_at = data.analyzed_at


def collect(call_id: int, offset_hours: int) -> CallData:
    database = context.database()

    details = database.call_details(call_id)
    if details is None:
        return CallData(
            found=False,
            status="",
            status_label=EMPTY_VALUE,
            status_color=DEFAULT_STATUS_COLOR,
            error="",
            agent_name=EMPTY_VALUE,
            manager_id=0,
            client=EMPTY_VALUE,
            started_at=EMPTY_VALUE,
            duration=EMPTY_VALUE,
            call_type=EMPTY_VALUE,
            crm_link="",
            summary="",
        )

    scores = [
        ScoreRow(
            code=row["code"],
            label=row["label"],
            met=bool(row["score"]),
            enabled=bool(row["enabled"]),
        )
        for row in database.call_scores(call_id)
    ]
    met = sum(1 for row in scores if row.met)
    status = details["status"] or ""

    return CallData(
        found=True,
        status=status,
        status_label=STATUS_LABELS.get(status, status or EMPTY_VALUE),
        status_color=STATUS_COLORS.get(status, DEFAULT_STATUS_COLOR),
        error=errors.describe(details.get("error_code")),
        agent_name=details["agent_name"] or EMPTY_VALUE,
        manager_id=details["agent_id"] or 0,
        client=details["client_number"] or EMPTY_VALUE,
        started_at=formatting.moment(details["started_at"], offset_hours),
        duration=formatting.duration(details["duration_seconds"]),
        call_type=details["call_type_label"] or details["call_type"] or EMPTY_VALUE,
        crm_link=details["crm_link"] or "",
        summary=details["summary"] or "",
        strengths=list(details["strengths"] or []),
        weaknesses=list(details["weaknesses"] or []),
        recommendations=list(details["recommendations"] or []),
        scores=scores,
        score_label=formatting.fraction(met, len(scores)),
        segments=_segments(database, call_id),
        audio_url=_audio_url(call_id, details["audio_path"]),
        asr_model=details["asr_model"] or EMPTY_VALUE,
        analysis_model=details["analysis_model"] or EMPTY_VALUE,
        prompt_label=details["prompt_label"] or EMPTY_VALUE,
        processing_seconds=formatting.duration(details["processing_seconds"]),
        analyzed_at=formatting.moment(details["analyzed_at"], offset_hours),
    )


def _segments(database, call_id: int) -> list[SegmentRow]:
    return [
        SegmentRow(
            time=formatting.timestamp(segment[SEGMENT_START_KEY]),
            seconds=segment[SEGMENT_START_KEY] // MILLISECONDS_PER_SECOND,
            text=segment[SEGMENT_TEXT_KEY],
        )
        for segment in database.call_segments(call_id)
    ]


def _audio_url(call_id: int, audio_path: str | None) -> str:
    if not audio_path or context.audio().locate(audio_path) is None:
        return ""
    return f"{context.config().server.api_url}{AUDIO_ROUTE}/{call_id}"
