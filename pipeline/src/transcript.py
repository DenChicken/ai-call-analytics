from dataclasses import dataclass, replace

from src.config import Criterion
from src.constants import (
    CRITERIA_LINE_TEMPLATE,
    MILLISECONDS_PER_SECOND,
    NUMBERED_LINE_TEMPLATE,
    ROLE_LABELS,
    SECONDS_PER_MINUTE,
    TRANSCRIPT_LINE_TEMPLATE,
    TRANSCRIPT_TIME_FORMAT,
    UNKNOWN_ROLE_LABEL,
)


@dataclass(frozen=True)
class Segment:
    start_ms: int
    end_ms: int
    text: str
    role: str | None = None


def _format_timestamp(start_ms: int) -> str:
    total_seconds = start_ms // MILLISECONDS_PER_SECOND
    return TRANSCRIPT_TIME_FORMAT.format(
        minutes=total_seconds // SECONDS_PER_MINUTE,
        seconds=total_seconds % SECONDS_PER_MINUTE,
    )


def render_numbered_transcript(segments: list[Segment]) -> str:
    return "\n".join(
        NUMBERED_LINE_TEMPLATE.format(
            index=index,
            start=_format_timestamp(segment.start_ms),
            text=segment.text,
        )
        for index, segment in enumerate(segments)
    )


def render_transcript(segments: list[Segment]) -> str:
    return "\n".join(
        TRANSCRIPT_LINE_TEMPLATE.format(
            start=_format_timestamp(segment.start_ms),
            speaker=ROLE_LABELS.get(segment.role, UNKNOWN_ROLE_LABEL),
            text=segment.text,
        )
        for segment in segments
    )


def render_criteria(criteria: list[Criterion]) -> str:
    return "\n".join(
        CRITERIA_LINE_TEMPLATE.format(
            label=criterion.label,
            description=criterion.description,
        )
        for criterion in criteria
    )


def with_roles(segments: list[Segment], roles: list[str]) -> list[Segment]:
    return [replace(segment, role=role) for segment, role in zip(segments, roles)]
