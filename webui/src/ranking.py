from dataclasses import dataclass
from statistics import median

from src.constants import RANK_BY_CALLS, RANK_PLAIN, RANK_SMOOTHED


@dataclass(frozen=True)
class Baseline:
    mean: float
    weight: float


def _calls(row: dict) -> int:
    return row["analyzed"] or 0


def _ratio(row: dict) -> float:
    return row["ratio"] or 0.0


def baseline(rows: list[dict]) -> Baseline:
    counts = [_calls(row) for row in rows if _calls(row)]
    if not counts:
        return Baseline(mean=0.0, weight=0.0)
    total = sum(counts)
    return Baseline(
        mean=sum(_ratio(row) * _calls(row) for row in rows) / total,
        weight=median(counts),
    )


def score(row: dict, base: Baseline) -> float:
    calls = _calls(row)
    weight = base.weight
    if not calls + weight:
        return 0.0
    return (_ratio(row) * calls + base.mean * weight) / (calls + weight)


def order(rows: list[dict], mode: str, minimum: int) -> list[dict]:
    eligible = [row for row in rows if _calls(row) >= minimum]
    if mode == RANK_BY_CALLS:
        return sorted(eligible, key=_calls, reverse=True)
    if mode == RANK_PLAIN:
        return sorted(eligible, key=_ratio, reverse=True)
    base = baseline(rows)
    return sorted(eligible, key=lambda row: score(row, base), reverse=True)


def displayed(row: dict, base: Baseline, mode: str) -> float:
    return score(row, base) if mode == RANK_SMOOTHED else _ratio(row)
