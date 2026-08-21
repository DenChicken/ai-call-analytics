from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from src.constants import (
    DATETIME_LABEL_FORMAT,
    DAY_LABEL_FORMAT,
    DELTA_TEMPLATE,
    DURATION_TEMPLATE,
    EMPTY_VALUE,
    MILLISECONDS_PER_SECOND,
    PERCENT_SCALE,
    PERIOD_DAYS,
    POSITIVE_SIGN,
    SCORE_FRACTION_TEMPLATE,
    SECONDS_PER_MINUTE,
)


def percent(ratio: float | None) -> int:
    return round((ratio or 0) * PERCENT_SCALE)


def fraction(met: int | None, total: int | None) -> str:
    if not total:
        return EMPTY_VALUE
    return SCORE_FRACTION_TEMPLATE.format(met=met or 0, total=total)


def delta_points(before: float | None, after: float | None) -> int:
    return percent(after) - percent(before)


def delta_label(points: int) -> str:
    sign = POSITIVE_SIGN if points > 0 else ""
    return DELTA_TEMPLATE.format(sign=sign, value=points)


def duration(seconds: int | None) -> str:
    if not seconds:
        return EMPTY_VALUE
    return DURATION_TEMPLATE.format(
        minutes=seconds // SECONDS_PER_MINUTE, seconds=seconds % SECONDS_PER_MINUTE
    )


def timestamp(milliseconds: int) -> str:
    seconds = milliseconds // MILLISECONDS_PER_SECOND
    return DURATION_TEMPLATE.format(
        minutes=seconds // SECONDS_PER_MINUTE, seconds=seconds % SECONDS_PER_MINUTE
    )


def moment(value: datetime | None, timezone: str) -> str:
    if value is None:
        return EMPTY_VALUE
    return value.astimezone(ZoneInfo(timezone)).strftime(DATETIME_LABEL_FORMAT)


def day_label(value: date) -> str:
    return value.strftime(DAY_LABEL_FORMAT)


def period_bounds(period: str, timezone: str) -> tuple[datetime, datetime]:
    zone = ZoneInfo(timezone)
    now = datetime.now(zone)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    since = start_of_day - timedelta(days=PERIOD_DAYS[period] - 1)
    return since, start_of_day + timedelta(days=1)


def previous_bounds(since: datetime, until: datetime) -> tuple[datetime, datetime]:
    span = until - since
    return since - span, since
