"""ECMAScript date semantics with an explicit local time zone and integer milliseconds."""

import json
import re
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

DAY_MS = 86_400_000
PLAIN = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})")
ISO = re.compile(
    r"([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2})(?::([0-9]{2})(?:\.([0-9]+))?)?(Z|[+-][0-9]{2}:[0-9]{2})?"
)


def _days(year: int, month: int, day: int) -> int:
    # Proleptic Gregorian arithmetic also covers ECMAScript year zero.
    year -= month <= 2
    era, within = divmod(year, 400)
    shifted = month + (-3 if month > 2 else 9)
    ordinal = (153 * shifted + 2) // 5 + day - 1
    return era * 146097 + within * 365 + within // 4 - within // 100 + ordinal - 719468


def _civil(days: int) -> tuple[int, int, int]:
    era, within = divmod(days + 719468, 146097)
    year = (within - within // 1460 + within // 36524 - within // 146096) // 365
    ordinal = within - (365 * year + year // 4 - year // 100)
    shifted = (5 * ordinal + 2) // 153
    day = ordinal - (153 * shifted + 2) // 5 + 1
    month = shifted + (3 if shifted < 10 else -9)
    return year + era * 400 + (month <= 2), month, day


def _utc_ms(value: datetime) -> int:
    current = value.astimezone(UTC)
    return (
        _days(current.year, current.month, current.day) * DAY_MS
        + ((current.hour * 60 + current.minute) * 60 + current.second) * 1000
        + current.microsecond // 1000
    )


def _format(milliseconds: int) -> str:
    days, remainder = divmod(milliseconds, DAY_MS)
    year, month, day = _civil(days)
    hour, remainder = divmod(remainder, 3_600_000)
    minute, remainder = divmod(remainder, 60_000)
    second, milli = divmod(remainder, 1000)
    year_text = f"{year:04}" if 0 <= year <= 9999 else f"{year:+07}"
    return f"{year_text}-{month:02}-{day:02}T{hour:02}:{minute:02}:{second:02}.{milli:03}Z"


def _local_ms(
    year: int, month: int, day: int, hour: int, minute: int, second: int, milli: int, zone: ZoneInfo
) -> int:
    naive = _days(year, month, day) * DAY_MS + ((hour * 60 + minute) * 60 + second) * 1000 + milli
    normalized_year, normalized_month, normalized_day = _civil(naive // DAY_MS)
    if 1 <= normalized_year <= 9999:
        normalized_hour = (naive % DAY_MS) // 3_600_000
        wall = datetime(
            normalized_year,
            normalized_month,
            normalized_day,
            normalized_hour,
            minute,
            second,
            milli * 1000,
            tzinfo=zone,
            fold=0,
        )
    else:
        # Outside datetime's range, the boundary offset preserves the earliest/final zone rule.
        wall = (
            datetime(1, 1, 1, tzinfo=zone)
            if normalized_year < 1
            else datetime(9999, 12, 31, tzinfo=zone)
        )
    offset = wall.utcoffset() or timedelta()
    return naive - int(offset.total_seconds()) * 1000


def _invalid(value: str) -> ValueError:
    return ValueError(
        f"Invalid timestamp {json.dumps(value, ensure_ascii=False)}: expected an "
        "ISO 8601 date-time (2026-09-29T18:45:00Z) or a date (YYYY-MM-DD)."
    )


def _future(value: str) -> ValueError:
    return ValueError(
        f"Invalid timestamp {json.dumps(value, ensure_ascii=False)}: "
        "last-made cannot be in the future."
    )


def resolve_last_made_timestamp(value: str | None, *, now: datetime, zone: ZoneInfo) -> str:
    if now.tzinfo is None:
        raise ValueError("now must include a time zone.")
    now_ms = _utc_ms(now)
    if value is None:
        return _format(now_ms)
    if plain := PLAIN.fullmatch(value):
        year, month, day = map(int, plain.groups())
        try:
            if year < 100:
                raise ValueError()
            date(year, month, day)
        except ValueError:
            raise _invalid(value) from None
        noon = _local_ms(year, month, day, 12, 0, 0, 0, zone)
        roundtrip = (datetime(1970, 1, 1, tzinfo=UTC) + timedelta(milliseconds=noon)).astimezone(
            zone
        )
        if (roundtrip.year, roundtrip.month, roundtrip.day) != (year, month, day):
            raise _invalid(value)
        today = now.astimezone(zone)
        tomorrow = _civil(_days(today.year, today.month, today.day) + 1)
        if noon >= _local_ms(*tomorrow, 0, 0, 0, 0, zone):
            raise _future(value)
        return _format(min(noon, now_ms))
    match = ISO.fullmatch(value)
    if match is None:
        raise _invalid(value)
    y, m, d, h, minute, second, fraction, offset = match.groups()
    year, month, day, hour, minutes, seconds = (
        int(y),
        int(m),
        int(d),
        int(h),
        int(minute),
        int(second or 0),
    )
    if not 1 <= month <= 12 or not 1 <= day <= 31 or hour > 24 or minutes > 59 or seconds > 59:
        raise _invalid(value)
    if hour == 24 and (minutes or seconds or any(char != "0" for char in fraction or "")):
        raise _invalid(value)
    milli = int(((fraction or "") + "000")[:3])
    if offset is None:
        result = _local_ms(year, month, day, hour, minutes, seconds, milli, zone)
    else:
        offset_minutes = 0
        if offset != "Z":
            oh, om = int(offset[1:3]), int(offset[4:6])
            if oh > 23 or om > 59:
                raise _invalid(value)
            offset_minutes = (oh * 60 + om) * (1 if offset[0] == "+" else -1)
        result = (
            _days(year, month, day) * DAY_MS
            + ((hour * 60 + minutes) * 60 + seconds) * 1000
            + milli
            - offset_minutes * 60_000
        )
    if result > now_ms:
        raise _future(value)
    return _format(result)
