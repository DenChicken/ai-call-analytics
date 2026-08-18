import re
from dataclasses import dataclass, replace

from src.config import Criterion
from src.constants import (
    CRITERIA_LINE_TEMPLATE,
    MILLISECONDS_PER_SECOND,
    ROLE_LABELS,
    SECONDS_PER_MINUTE,
    SEGMENT_LINE_TEMPLATE,
    TIME_FORMAT,
    TIME_PATTERN_TEXT,
    TURN_LINE_TEMPLATE,
)

TIME_PATTERN = re.compile(TIME_PATTERN_TEXT)


@dataclass(frozen=True)
class Word:
    start_ms: int
    end_ms: int
    text: str
    probability: float


@dataclass(frozen=True)
class Segment:
    start_ms: int
    end_ms: int
    text: str
    words: list[Word]
    no_speech_prob: float
    avg_logprob: float
    compression_ratio: float


@dataclass(frozen=True)
class Turn:
    role: str
    start_ms: int
    end_ms: int
    text: str


class TranscriptError(Exception):
    pass


def _format_timestamp(start_ms: int) -> str:
    total_seconds = start_ms // MILLISECONDS_PER_SECOND
    return TIME_FORMAT.format(
        minutes=total_seconds // SECONDS_PER_MINUTE,
        seconds=total_seconds % SECONDS_PER_MINUTE,
    )


def render_segments(segments: list[Segment]) -> str:
    return " ".join(
        SEGMENT_LINE_TEMPLATE.format(
            start=_format_timestamp(segment.start_ms),
            text=segment.text,
        )
        for segment in segments
    )


def render_dialog(turns: list[Turn]) -> str:
    return "\n".join(
        TURN_LINE_TEMPLATE.format(
            start=_format_timestamp(turn.start_ms),
            speaker=ROLE_LABELS[turn.role],
            text=turn.text,
        )
        for turn in turns
    )


def render_criteria(criteria: list[Criterion]) -> str:
    return "\n".join(
        CRITERIA_LINE_TEMPLATE.format(
            label=criterion.label,
            description=criterion.description,
        )
        for criterion in criteria
    )


def _parse_timestamp(value: str) -> int | None:
    match = TIME_PATTERN.fullmatch(value.strip())
    if match is None:
        return None
    minutes, seconds = int(match.group(1)), int(match.group(2))
    return (minutes * SECONDS_PER_MINUTE + seconds) * MILLISECONDS_PER_SECOND


def build_turns(spans: list, duration_ms: int) -> list[Turn]:
    if not spans:
        raise TranscriptError("model returned no turns")

    turns = []
    for span in spans:
        text = span.text.strip()
        if not text:
            continue
        start_ms = _parse_timestamp(span.time)
        if start_ms is None:
            start_ms = turns[-1].end_ms if turns else 0
        start_ms = min(start_ms, duration_ms)
        if turns and start_ms < turns[-1].start_ms:
            start_ms = turns[-1].start_ms
        if turns:
            turns[-1] = replace(turns[-1], end_ms=max(turns[-1].start_ms, start_ms))
        turns.append(Turn(role=span.role, start_ms=start_ms, end_ms=duration_ms, text=text))

    if not turns:
        raise TranscriptError("model returned only empty turns")
    return turns
