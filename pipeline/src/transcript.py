from dataclasses import dataclass


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
