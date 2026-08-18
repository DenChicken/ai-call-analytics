from dataclasses import dataclass

from src.config import Reference
from src.constants import CRITERIA_LINE_TEMPLATE, TRANSCRIPT_BREAK_TEMPLATE


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


def render_plain(segments: list[Segment]) -> str:
    return " ".join(segment.text for segment in segments)


def render_transcript(segments: list[Segment], break_silence_ms: int) -> str:
    lines = []
    previous_end_ms = None
    for segment in segments:
        if previous_end_ms is not None and segment.start_ms - previous_end_ms <= break_silence_ms:
            lines[-1] = f"{lines[-1]} {segment.text}"
        else:
            lines.append(segment.text)
        previous_end_ms = segment.end_ms
    return "\n".join(TRANSCRIPT_BREAK_TEMPLATE.format(text=line) for line in lines)


def render_criteria(criteria: list[Reference]) -> str:
    return "\n".join(
        CRITERIA_LINE_TEMPLATE.format(
            label=criterion.label,
            description=criterion.description,
        )
        for criterion in criteria
    )
