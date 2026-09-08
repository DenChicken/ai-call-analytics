from dataclasses import dataclass


@dataclass(frozen=True)
class Segment:
    start_ms: int
    end_ms: int
    text: str


@dataclass(frozen=True)
class Analysis:
    call_type: str
    summary: str
    strengths: list[str]
    weaknesses: list[str]
    recommendations: list[str]
    scores: dict[str, int]


def render_plain(segments: list[Segment]) -> str:
    return " ".join(segment.text for segment in segments)
