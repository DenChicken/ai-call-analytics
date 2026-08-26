from dataclasses import dataclass


@dataclass(frozen=True)
class Segment:
    start_ms: int
    end_ms: int
    text: str


def render_plain(segments: list[Segment]) -> str:
    return " ".join(segment.text for segment in segments)
