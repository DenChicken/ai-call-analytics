from dataclasses import dataclass

from src import formatting

CHART_LABEL_KEY = "label"
CHART_BEFORE_KEY = "before"
CHART_AFTER_KEY = "after"
PREVIEW_COUNT = 6
GROUP_HEIGHT = 52
CHART_PADDING = 64


@dataclass
class CriterionDelta:
    code: str
    label: str
    before: float
    after: float
    points: int
    delta: str


def deltas(database, window: dict, previous: dict) -> list[CriterionDelta]:
    labels = {row["code"]: row["label"] for row in database.criteria()}
    current = {row["code"]: row["ratio"] for row in database.criteria_ratios(window)}
    earlier = {row["code"]: row["ratio"] for row in database.criteria_ratios(previous)}

    entries = []
    for code, ratio in current.items():
        points = formatting.delta_points(earlier.get(code), ratio)
        entries.append(
            CriterionDelta(
                code=code,
                label=labels.get(code, code),
                before=formatting.share(earlier.get(code)),
                after=formatting.share(ratio),
                points=points,
                delta=formatting.delta_label(points),
            )
        )
    return sorted(entries, key=lambda entry: entry.points)


def chart_points(entries: list[CriterionDelta]) -> list[dict]:
    return [
        {
            CHART_LABEL_KEY: entry.label,
            CHART_BEFORE_KEY: entry.before,
            CHART_AFTER_KEY: entry.after,
        }
        for entry in entries
    ]


def visible(points: list[dict], expanded: bool) -> list[dict]:
    return list(points) if expanded else list(points)[:PREVIEW_COUNT]


def hidden_count(points: list[dict]) -> int:
    return max(len(points) - PREVIEW_COUNT, 0)


def chart_height(points: list[dict]) -> int:
    return len(points) * GROUP_HEIGHT + CHART_PADDING
