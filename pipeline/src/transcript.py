from dataclasses import dataclass

from src.config import Criterion
from src.constants import (
    CRITERIA_LINE_TEMPLATE,
    MILLISECONDS_PER_SECOND,
    SECONDS_PER_MINUTE,
    TRANSCRIPT_LINE_TEMPLATE,
    TRANSCRIPT_TIME_FORMAT,
)


@dataclass(frozen=True)
class Word:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class Turn:
    start: float
    end: float
    speaker: str


@dataclass(frozen=True)
class Segment:
    speaker: str
    start_ms: int
    end_ms: int
    text: str


def _overlap(start: float, end: float, turn: Turn) -> float:
    return max(0.0, min(end, turn.end) - max(start, turn.start))


def assign_speaker(word: Word, turns: list[Turn]) -> str:
    best = max(turns, key=lambda turn: _overlap(word.start, word.end, turn))
    if _overlap(word.start, word.end, best) > 0.0:
        return best.speaker
    center = (word.start + word.end) / 2
    nearest = min(turns, key=lambda turn: max(turn.start - center, center - turn.end, 0.0))
    return nearest.speaker


def build_segments(words: list[Word], turns: list[Turn]) -> list[Segment]:
    segments = []
    current_speaker = None
    current_words: list[Word] = []

    for word in words:
        speaker = assign_speaker(word, turns)
        if speaker != current_speaker and current_words:
            segments.append(_make_segment(current_speaker, current_words))
            current_words = []
        current_speaker = speaker
        current_words.append(word)

    if current_words:
        segments.append(_make_segment(current_speaker, current_words))
    return segments


def _make_segment(speaker: str, words: list[Word]) -> Segment:
    return Segment(
        speaker=speaker,
        start_ms=int(words[0].start * MILLISECONDS_PER_SECOND),
        end_ms=int(words[-1].end * MILLISECONDS_PER_SECOND),
        text=" ".join(word.text.strip() for word in words).strip(),
    )


def _format_timestamp(start_ms: int) -> str:
    total_seconds = start_ms // MILLISECONDS_PER_SECOND
    return TRANSCRIPT_TIME_FORMAT.format(
        minutes=total_seconds // SECONDS_PER_MINUTE,
        seconds=total_seconds % SECONDS_PER_MINUTE,
    )


def render_transcript(segments: list[Segment]) -> str:
    return "\n".join(
        TRANSCRIPT_LINE_TEMPLATE.format(
            start=_format_timestamp(segment.start_ms),
            speaker=segment.speaker,
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


def speaker_labels(segments: list[Segment]) -> list[str]:
    seen = []
    for segment in segments:
        if segment.speaker not in seen:
            seen.append(segment.speaker)
    return seen
