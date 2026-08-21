from datetime import date, datetime, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo

from src.constants import (
    DATETIME_FULL_TEMPLATE,
    DATETIME_LABEL_FORMAT,
    DAY_LABEL_FORMAT,
    DELTA_TEMPLATE,
    DURATION_TEMPLATE,
    EMPTY_VALUE,
    MILLISECONDS_PER_SECOND,
    NEGATIVE_SIGN,
    PERCENT_SCALE,
    PERIOD_DAYS,
    POSITIVE_SIGN,
    SCORE_FRACTION_TEMPLATE,
    SECONDS_PER_HOUR,
    SECONDS_PER_MINUTE,
    SHARE_PRECISION,
    UTC_OFFSET_TEMPLATE,
    WEEKDAY_NAMES,
)


def percent(ratio: float | None) -> int:
    return round((ratio or 0) * PERCENT_SCALE)


def share(ratio: float | None) -> float:
    return round(ratio or 0, SHARE_PRECISION)


def share_label(ratio: float | None, calls: int | None = None) -> str:
    if calls is not None and not calls:
        return EMPTY_VALUE
    return f"{share(ratio):.{SHARE_PRECISION}f}"


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
    return _clock(seconds)


def timestamp(milliseconds: int) -> str:
    return _clock(milliseconds // MILLISECONDS_PER_SECOND)


def _clock(seconds: int) -> str:
    return DURATION_TEMPLATE.format(
        minutes=seconds // SECONDS_PER_MINUTE, seconds=seconds % SECONDS_PER_MINUTE
    )


def zone(offset_hours: int) -> tzinfo:
    return timezone(timedelta(hours=offset_hours))


def offset_label(offset_hours: int) -> str:
    sign = POSITIVE_SIGN if offset_hours >= 0 else NEGATIVE_SIGN
    return UTC_OFFSET_TEMPLATE.format(sign=sign, hours=abs(offset_hours))


def default_offset(timezone_name: str) -> int:
    offset = datetime.now(ZoneInfo(timezone_name)).utcoffset() or timedelta()
    return int(offset.total_seconds() // SECONDS_PER_HOUR)


def moment(value: datetime | None, offset_hours: int) -> str:
    if value is None:
        return EMPTY_VALUE
    local = value.astimezone(zone(offset_hours))
    return DATETIME_FULL_TEMPLATE.format(
        moment=local.strftime(DATETIME_LABEL_FORMAT),
        weekday=WEEKDAY_NAMES[local.weekday()],
    )


def day_label(value: date) -> str:
    return value.strftime(DAY_LABEL_FORMAT)


def period_bounds(period: str, offset_hours: int) -> tuple[datetime, datetime]:
    now = datetime.now(zone(offset_hours))
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    since = start_of_day - timedelta(days=PERIOD_DAYS[period] - 1)
    return since, start_of_day + timedelta(days=1)


def previous_bounds(since: datetime, until: datetime) -> tuple[datetime, datetime]:
    span = until - since
    return since - span, since
