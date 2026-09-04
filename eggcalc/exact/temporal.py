"""Deterministic fixed-offset temporal and cron inspection tools.

Provides pure, side-effect-free conversion between RFC3339 timestamps and
Unix time units with exact nanosecond precision, plus bounded five-field
cron inspection with corrected Vixie/Cronie DOM/DOW star-syntax semantics.

No network I/O, filesystem access, system clock lookup, local timezone
lookup, IANA timezone database, or floating-point Unix timestamps are used.
All instants are represented internally as signed integer nanoseconds.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import TypedDict

MAX_TEXT_INPUT_LENGTH = 100_000

_NS_PER_SECOND = 1_000_000_000
_NS_PER_MILLISECOND = 1_000_000
_SECONDS_PER_DAY = 86_400
_MAX_OFFSET_SECONDS = 86_400
_MAX_CRON_DAYS = 146_097
_MAX_CRON_COUNT = 32

_EPOCH_ORDINAL = date(1970, 1, 1).toordinal()
_MIN_ORDINAL = date(1, 1, 1).toordinal()
_MAX_ORDINAL = date(9999, 12, 31).toordinal()

_WEEKDAY_NAMES = ("SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT")

_MONTH_NAMES: dict[str, int] = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}

_DOW_NAMES: dict[str, int] = {
    "SUN": 0,
    "MON": 1,
    "TUE": 2,
    "WED": 3,
    "THU": 4,
    "FRI": 5,
    "SAT": 6,
}

_DATETIME_FORMATS = (
    "rfc3339",
    "unix_seconds",
    "unix_milliseconds",
    "unix_nanoseconds",
)

_RFC3339_RE = re.compile(
    r"^([0-9]{4})-([0-9]{2})-([0-9]{2})"
    r"T([0-9]{2}):([0-9]{2}):([0-9]{2})"
    r"(?:\.([0-9]{1,9}))?"
    r"(Z|[+-][0-9]{2}:[0-9]{2})$"
)

_OFFSET_RE = re.compile(r"^(Z|[+-][0-9]{2}:[0-9]{2})$")

_DIGIT_CHARS = frozenset("0123456789")


class DatetimeComponents(TypedDict):
    """Calendar components of an instant in the selected fixed offset."""

    year: int
    month: int
    day: int
    hour: int
    minute: int
    second: int
    nanosecond: int
    weekday: str


class DatetimeConvertResult(TypedDict):
    """Result of converting between RFC3339 and Unix time units."""

    rfc3339: str
    utc_rfc3339: str
    unix_seconds: str
    unix_milliseconds: str
    unix_nanoseconds: str
    offset_seconds: int
    selected_offset: str
    components: DatetimeComponents


class CronParsedValues(TypedDict):
    """Sorted normalized integer sets for each cron field."""

    minute: list[int]
    hour: list[int]
    day_of_month: list[int]
    month: list[int]
    day_of_week: list[int]


class CronInspectResult(TypedDict):
    """Result of inspecting a five-field cron expression."""

    expression: str
    normalized_expression: str
    parsed_values: CronParsedValues
    offset: str
    offset_seconds: int
    satisfiable: bool
    next_runs: list[str]
    count: int


@dataclass(frozen=True)
class _CronField:
    """Compact immutable representation of one parsed cron field."""

    allowed: frozenset[int]
    minimum: int
    maximum: int
    star_syntax: bool


def _check_text_length(value: str, name: str) -> None:
    """Reject inputs beyond the shared exact text ceiling."""
    if len(value) > MAX_TEXT_INPUT_LENGTH:
        raise ValueError(
            f"Input {name} length {len(value)} exceeds maximum {MAX_TEXT_INPUT_LENGTH}"
        )


def _parse_fixed_offset(text: str) -> tuple[int, str]:
    """Parse a fixed offset (``Z`` or ``+/-HH:MM``) to seconds and canonical text.

    Hours must be 0..23 and minutes 0..59 with absolute value below 24 hours.
    A zero offset canonicalizes to ``"Z"``.
    """
    if not isinstance(text, str):
        raise ValueError(f"offset must be a string, got {type(text).__name__}")
    _check_text_length(text, "'output_offset'")
    if _OFFSET_RE.match(text) is None:
        raise ValueError(f"invalid fixed offset (expected Z or +/-HH:MM): {text!r}")
    if text == "Z":
        return (0, "Z")
    sign = 1 if text[0] == "+" else -1
    hours = int(text[1:3])
    minutes = int(text[4:6])
    if hours > 23 or minutes > 59:
        raise ValueError(f"invalid fixed offset out of range: {text!r}")
    total = sign * (hours * 3600 + minutes * 60)
    if abs(total) >= _MAX_OFFSET_SECONDS:
        raise ValueError(f"invalid fixed offset (must be under 24 hours): {text!r}")
    if total == 0:
        return (0, "Z")
    return (total, text)


def _parse_rfc3339_to_ns(text: str) -> tuple[int, int]:
    """Parse bounded RFC3339 to ``(unix_ns, offset_seconds)`` with integer math.

    Fractional seconds (1..9 digits) are padded to nanoseconds exactly.
    Calendar validity is checked via ``date`` construction; no float
    timestamps are used.
    """
    if not isinstance(text, str):
        raise ValueError(f"value must be a string, got {type(text).__name__}")
    _check_text_length(text, "'value'")
    match = _RFC3339_RE.match(text)
    if match is None:
        raise ValueError(f"invalid RFC3339 timestamp: {text!r}")
    year = int(match.group(1))
    month = int(match.group(2))
    day = int(match.group(3))
    hour = int(match.group(4))
    minute = int(match.group(5))
    second = int(match.group(6))
    frac = match.group(7)
    tz = match.group(8)
    if month < 1 or month > 12:
        raise ValueError(f"invalid RFC3339 month: {text!r}")
    if hour > 23 or minute > 59 or second > 59:
        raise ValueError(f"invalid RFC3339 time: {text!r}")
    try:
        current = date(year, month, day)
    except ValueError as exc:
        raise ValueError(f"invalid RFC3339 calendar date: {text!r}") from exc
    offset_seconds, _ = _parse_fixed_offset(tz)
    nanoseconds = int(frac.ljust(9, "0")) if frac is not None else 0
    days = current.toordinal() - _EPOCH_ORDINAL
    whole_seconds_utc = days * _SECONDS_PER_DAY + hour * 3600 + minute * 60 + second
    whole_seconds_utc -= offset_seconds
    unix_ns = whole_seconds_utc * _NS_PER_SECOND + nanoseconds
    return (unix_ns, offset_seconds)


def _format_rfc3339_from_ns(unix_ns: int, offset_seconds: int) -> str:
    """Format an instant as canonical RFC3339 in the given fixed offset.

    Uses ``Z`` for zero offset, omits the fraction when nanoseconds are zero,
    and otherwise trims only trailing zeroes from the nine-digit fraction.
    """
    if abs(offset_seconds) >= _MAX_OFFSET_SECONDS:
        raise ValueError(f"offset_seconds out of range: {offset_seconds!r}")
    whole_seconds, nanoseconds = divmod(unix_ns, _NS_PER_SECOND)
    wall_seconds = whole_seconds + offset_seconds
    wall_days, secs_in_day = divmod(wall_seconds, _SECONDS_PER_DAY)
    wall_ordinal = _EPOCH_ORDINAL + wall_days
    if wall_ordinal < _MIN_ORDINAL or wall_ordinal > _MAX_ORDINAL:
        raise ValueError("instant outside supported calendar range 0001..9999")
    current = date.fromordinal(wall_ordinal)
    hour = secs_in_day // 3600
    minute = (secs_in_day % 3600) // 60
    second = secs_in_day % 60
    base = (
        f"{current.year:04d}-{current.month:02d}-{current.day:02d}"
        f"T{hour:02d}:{minute:02d}:{second:02d}"
    )
    if nanoseconds != 0:
        fraction = f"{nanoseconds:09d}".rstrip("0")
        base += f".{fraction}"
    if offset_seconds == 0:
        return base + "Z"
    sign = "+" if offset_seconds > 0 else "-"
    abs_offset = abs(offset_seconds)
    return base + f"{sign}{abs_offset // 3600:02d}:{(abs_offset % 3600) // 60:02d}"


def _unix_unit_floor(unix_ns: int) -> tuple[str, str, str]:
    """Derive floor/Euclidean Unix seconds, milliseconds, and nanoseconds."""
    seconds = unix_ns // _NS_PER_SECOND
    milliseconds = unix_ns // _NS_PER_MILLISECOND
    return (str(seconds), str(milliseconds), str(unix_ns))


def _datetime_components(unix_ns: int, offset_seconds: int) -> DatetimeComponents:
    """Return calendar components of an instant in the selected offset."""
    whole_seconds, nanoseconds = divmod(unix_ns, _NS_PER_SECOND)
    wall_seconds = whole_seconds + offset_seconds
    wall_days, secs_in_day = divmod(wall_seconds, _SECONDS_PER_DAY)
    wall_ordinal = _EPOCH_ORDINAL + wall_days
    if wall_ordinal < _MIN_ORDINAL or wall_ordinal > _MAX_ORDINAL:
        raise ValueError("instant outside supported calendar range 0001..9999")
    current = date.fromordinal(wall_ordinal)
    hour = secs_in_day // 3600
    minute = (secs_in_day % 3600) // 60
    second = secs_in_day % 60
    weekday = _WEEKDAY_NAMES[(current.weekday() + 1) % 7]
    return DatetimeComponents(
        year=current.year,
        month=current.month,
        day=current.day,
        hour=hour,
        minute=minute,
        second=second,
        nanosecond=nanoseconds,
        weekday=weekday,
    )


def _canonical_offset_text(offset_seconds: int) -> str:
    """Return canonical offset text (``Z`` for zero, else ``+/-HH:MM``)."""
    if offset_seconds == 0:
        return "Z"
    sign = "+" if offset_seconds > 0 else "-"
    abs_offset = abs(offset_seconds)
    return f"{sign}{abs_offset // 3600:02d}:{(abs_offset % 3600) // 60:02d}"


def _check_unix_integer(value: str) -> int:
    """Validate narrow signed-decimal Unix grammar and return its int value."""
    if not isinstance(value, str):
        raise ValueError(f"value must be a string, got {type(value).__name__}")
    _check_text_length(value, "'value'")
    if value == "" or value == "-":
        raise ValueError(f"invalid unix integer: {value!r}")
    body = value[1:] if value[0] == "-" else value
    if not body or any(ch not in _DIGIT_CHARS for ch in body):
        raise ValueError(f"invalid unix integer: {value!r}")
    if len(body) > 25:
        raise ValueError(f"unix value outside supported calendar range: {value!r}")
    return int(value)


def datetime_convert(
    value: str, format: str, output_offset: str | None = None
) -> DatetimeConvertResult:
    """Convert between RFC3339 and Unix seconds/milliseconds/nanoseconds.

    Args:
        value: Timestamp text. RFC3339 input uses the bounded
            ``YYYY-MM-DDTHH:MM:SS[.fraction]Z`` / ``+/-HH:MM`` grammar with
            1..9 fractional digits; Unix inputs are signed decimal integer
            strings with an optional leading ``-`` and ASCII digits only.
        format: One of ``"rfc3339"``, ``"unix_seconds"``,
            ``"unix_milliseconds"``, ``"unix_nanoseconds"``.
        output_offset: Optional fixed display offset (``Z`` or ``+/-HH:MM``).
            For RFC3339 input the default is the input's own offset; for Unix
            input the default is UTC. Overrides only the display offset, not
            the instant.

    Returns:
        DatetimeConvertResult with selected-offset ``rfc3339``, ``utc_rfc3339``,
        floor-derived ``unix_seconds``/``unix_milliseconds`` decimal strings,
        exact ``unix_nanoseconds`` decimal string, ``offset_seconds``,
        canonical ``selected_offset``, and ``components`` (year, month, day,
        hour, minute, second, nanosecond, weekday ``SUN``..``SAT``) in the
        selected offset.

    Raises:
        ValueError: If the format, value grammar, offset, calendar date/time,
            or resulting calendar range is invalid.

    Examples:
        >>> datetime_convert("0", "unix_seconds")["rfc3339"]
        '1970-01-01T00:00:00Z'
        >>> datetime_convert("-1", "unix_nanoseconds")["unix_seconds"]
        '-1'
    """
    if format not in _DATETIME_FORMATS:
        raise ValueError(
            f"unsupported format: {format!r} " f"(expected one of {', '.join(_DATETIME_FORMATS)})"
        )
    selected: int | None = None
    if output_offset is not None:
        if not isinstance(output_offset, str):
            raise ValueError(f"output_offset must be a string, got {type(output_offset).__name__}")
        selected, _ = _parse_fixed_offset(output_offset)
    if format == "rfc3339":
        unix_ns, input_offset = _parse_rfc3339_to_ns(value)
        offset_seconds = selected if selected is not None else input_offset
    elif format == "unix_seconds":
        magnitude = _check_unix_integer(value)
        unix_ns = magnitude * _NS_PER_SECOND
        offset_seconds = selected if selected is not None else 0
    elif format == "unix_milliseconds":
        magnitude = _check_unix_integer(value)
        unix_ns = magnitude * _NS_PER_MILLISECOND
        offset_seconds = selected if selected is not None else 0
    else:
        unix_ns = _check_unix_integer(value)
        offset_seconds = selected if selected is not None else 0
    try:
        rfc3339 = _format_rfc3339_from_ns(unix_ns, offset_seconds)
        utc_rfc3339 = _format_rfc3339_from_ns(unix_ns, 0)
        components = _datetime_components(unix_ns, offset_seconds)
    except ValueError as exc:
        raise ValueError(f"timestamp outside supported calendar range: {value!r}") from exc
    unix_seconds, unix_milliseconds, unix_nanoseconds = _unix_unit_floor(unix_ns)
    return DatetimeConvertResult(
        rfc3339=rfc3339,
        utc_rfc3339=utc_rfc3339,
        unix_seconds=unix_seconds,
        unix_milliseconds=unix_milliseconds,
        unix_nanoseconds=unix_nanoseconds,
        offset_seconds=offset_seconds,
        selected_offset=_canonical_offset_text(offset_seconds),
        components=components,
    )


def _parse_cron_number(token: str, minimum: int, maximum: int, names: dict[str, int] | None) -> int:
    """Parse one cron numeric or name token to its raw integer value."""
    if not token:
        raise ValueError("empty cron value")
    if names is not None and token.upper() in names:
        return names[token.upper()]
    if not token.isascii() or any(ch not in _DIGIT_CHARS for ch in token):
        raise ValueError(f"invalid cron value: {token!r}")
    number = int(token)
    if number < minimum or number > maximum:
        raise ValueError(f"cron value {number} outside range {minimum}..{maximum}")
    return number


def _parse_cron_field(
    field: str,
    minimum: int,
    maximum: int,
    names: dict[str, int] | None,
    normalize_sunday: bool = False,
) -> _CronField:
    """Parse one cron field supporting lists, ranges, and positive steps."""
    if not isinstance(field, str):
        raise ValueError(f"cron field must be a string, got {type(field).__name__}")
    if field == "":
        raise ValueError("empty cron field")
    star_syntax = field.startswith("*")
    allowed: set[int] = set()
    for item in field.split(","):
        if item == "":
            raise ValueError(f"empty list item in cron field: {field!r}")
        if item.count("/") > 1:
            raise ValueError(f"multiple '/' in cron item: {item!r}")
        has_step = "/" in item
        if has_step:
            base, _, step_text = item.partition("/")
            if base == "" or step_text == "":
                raise ValueError(f"invalid step syntax in cron item: {item!r}")
            if not step_text.isascii() or any(ch not in _DIGIT_CHARS for ch in step_text):
                raise ValueError(f"invalid cron step: {step_text!r}")
            step = int(step_text)
            if step <= 0:
                raise ValueError(f"cron step must be positive: {step_text!r}")
        else:
            base = item
            step = 1
        if base == "*":
            start = minimum
            end = maximum
            values = range(start, end + 1, step)
            for raw in values:
                allowed.add(0 if (normalize_sunday and raw == 7) else raw)
        elif "-" in base:
            if base.count("-") != 1:
                raise ValueError(f"invalid cron range: {base!r}")
            start_text, _, end_text = base.partition("-")
            if start_text == "" or end_text == "":
                raise ValueError(f"invalid cron range: {base!r}")
            start_raw = _parse_cron_number(start_text, minimum, maximum, names)
            end_raw = _parse_cron_number(end_text, minimum, maximum, names)
            if start_raw > end_raw:
                raise ValueError(f"wrapping cron range rejected: {base!r}")
            for raw in range(start_raw, end_raw + 1, step):
                allowed.add(0 if (normalize_sunday and raw == 7) else raw)
        else:
            start_raw = _parse_cron_number(base, minimum, maximum, names)
            if not has_step:
                allowed.add(0 if (normalize_sunday and start_raw == 7) else start_raw)
            else:
                for raw in range(start_raw, maximum + 1, step):
                    allowed.add(0 if (normalize_sunday and raw == 7) else raw)
    if not allowed:
        raise ValueError(f"cron field produces empty value set: {field!r}")
    for value in allowed:
        low = minimum if not normalize_sunday else 0
        high = 6 if normalize_sunday else maximum
        if value < low or value > high:
            raise ValueError(f"cron value {value} outside normalized range")
    return _CronField(
        allowed=frozenset(allowed),
        minimum=minimum,
        maximum=maximum,
        star_syntax=star_syntax,
    )


def _parse_cron_expression(expression: str) -> tuple[_CronField, ...]:
    """Parse a five-field cron expression to immutable field structures."""
    if not isinstance(expression, str):
        raise ValueError(f"expression must be a string, got {type(expression).__name__}")
    _check_text_length(expression, "'expression'")
    if expression.strip() == "":
        raise ValueError("empty cron expression")
    stripped = expression.lstrip()
    if stripped.startswith("@"):
        raise ValueError(f"cron macros are rejected: {expression!r}")
    if "=" in expression:
        raise ValueError(f"cron timezone prefixes are rejected: {expression!r}")
    parts = expression.split()
    if len(parts) != 5:
        raise ValueError(
            f"invalid cron expression (expected exactly 5 fields, got {len(parts)}): "
            f"{expression!r}"
        )
    minute = _parse_cron_field(parts[0], 0, 59, None)
    hour = _parse_cron_field(parts[1], 0, 23, None)
    day_of_month = _parse_cron_field(parts[2], 1, 31, None)
    month = _parse_cron_field(parts[3], 1, 12, _MONTH_NAMES)
    day_of_week = _parse_cron_field(parts[4], 0, 7, _DOW_NAMES, normalize_sunday=True)
    return (minute, hour, day_of_month, month, day_of_week)


def _cron_day_matches(
    dom_field: _CronField, dow_field: _CronField, day: int, dow_cron: int
) -> bool:
    """Apply corrected star-syntax DOM/DOW semantics for one calendar date."""
    dom_matches = day in dom_field.allowed
    dow_matches = dow_cron in dow_field.allowed
    if dom_field.star_syntax or dow_field.star_syntax:
        return dom_matches and dow_matches
    return dom_matches or dow_matches


def _cron_search_next(
    fields: tuple[_CronField, ...],
    after_unix_ns: int,
    offset_seconds: int,
    count: int,
) -> tuple[list[str], bool]:
    """Search strictly after ``after_unix_ns`` for up to ``count`` runs.

    Returns ``(next_runs, satisfiable)``. Raises ``ValueError`` when the
    supported calendar boundary is reached before satisfying the request.
    A full 400-year scan with zero matches returns ``([], False)``.
    """
    whole_seconds, _ = divmod(after_unix_ns, _NS_PER_SECOND)
    wall_seconds = whole_seconds + offset_seconds
    wall_days, _ = divmod(wall_seconds, _SECONDS_PER_DAY)
    start_ordinal = _EPOCH_ORDINAL + wall_days
    if start_ordinal < _MIN_ORDINAL or start_ordinal > _MAX_ORDINAL:
        raise ValueError("reference instant outside supported calendar range")
    try:
        start_date = date.fromordinal(start_ordinal)
    except ValueError as exc:
        raise ValueError("reference instant outside supported calendar range") from exc
    minute_field, hour_field, dom_field, month_field, dow_field = fields
    sorted_minutes = sorted(minute_field.allowed)
    sorted_hours = sorted(hour_field.allowed)
    next_runs: list[str] = []
    for day_offset in range(_MAX_CRON_DAYS):
        try:
            current = start_date + timedelta(days=day_offset)
        except OverflowError as exc:
            raise ValueError("cron search reached supported calendar boundary") from exc
        if current.year < 1 or current.year > 9999:
            raise ValueError("cron search reached supported calendar boundary")
        if current.month not in month_field.allowed:
            continue
        dow_cron = (current.weekday() + 1) % 7
        if not _cron_day_matches(dom_field, dow_field, current.day, dow_cron):
            continue
        base_days = current.toordinal() - _EPOCH_ORDINAL
        for hour in sorted_hours:
            for minute in sorted_minutes:
                whole_utc = (
                    base_days * _SECONDS_PER_DAY + hour * 3600 + minute * 60
                ) - offset_seconds
                candidate_ns = whole_utc * _NS_PER_SECOND
                if candidate_ns > after_unix_ns:
                    next_runs.append(_format_rfc3339_from_ns(candidate_ns, offset_seconds))
                    if len(next_runs) >= count:
                        return (next_runs, True)
    if next_runs:
        return (next_runs, True)
    return ([], False)


def cron_inspect(expression: str, after: str, count: int = 5) -> CronInspectResult:
    """Inspect a five-field cron expression and list strictly-later runs.

    Args:
        expression: Five whitespace-delimited fields
            (minute hour day-of-month month day-of-week) supporting comma
            lists, inclusive nonwrapping ranges, and positive ``/step``
            syntax. Month names ``JAN``..``DEC`` and weekday names
            ``SUN``..``SAT`` are ASCII case-insensitive; Sunday ``7`` is
            normalized to ``0``. Macros (``@daily``), six-field forms, and
            ``CRON_TZ=``/``TZ=`` prefixes are rejected.
        after: RFC3339 reference instant (same bounded grammar as
            :func:`datetime_convert`). Results are strictly later than this
            instant and reuse its fixed offset.
        count: Requested run count, an integer in 1..32 (default 5).

    Returns:
        CronInspectResult with the original ``expression``,
        ``normalized_expression`` (explicit sorted numeric values per field),
        ``parsed_values`` (sorted lists for minute/hour/day_of_month/month/
        day_of_week), ``offset``/``offset_seconds`` from ``after``,
        ``satisfiable``, strictly-later ``next_runs`` in the same fixed
        offset, and ``count`` (actual entries in ``next_runs``).

    Raises:
        ValueError: If the expression grammar, ``after`` timestamp, count, or
            calendar bounds are invalid, or the calendar boundary is reached
            before satisfying the request.

    Examples:
        >>> cron_inspect("0 9 * * MON-FRI", "2026-09-03T00:00:00Z", count=1)["next_runs"]
        ['2026-09-04T09:00:00Z']
    """
    if not isinstance(count, int) or isinstance(count, bool):
        raise ValueError("count must be an integer in 1..32")
    if count < 1 or count > _MAX_CRON_COUNT:
        raise ValueError(f"count must be an integer in 1..{_MAX_CRON_COUNT}")
    fields = _parse_cron_expression(expression)
    after_unix_ns, offset_seconds = _parse_rfc3339_to_ns(after)
    next_runs, satisfiable = _cron_search_next(fields, after_unix_ns, offset_seconds, count)
    minute_field, hour_field, dom_field, month_field, dow_field = fields

    def _normalized(field: _CronField) -> str:
        return ",".join(str(v) for v in sorted(field.allowed))

    normalized_expression = " ".join(
        _normalized(field)
        for field in (minute_field, hour_field, dom_field, month_field, dow_field)
    )
    parsed_values = CronParsedValues(
        minute=sorted(minute_field.allowed),
        hour=sorted(hour_field.allowed),
        day_of_month=sorted(dom_field.allowed),
        month=sorted(month_field.allowed),
        day_of_week=sorted(dow_field.allowed),
    )
    return CronInspectResult(
        expression=expression,
        normalized_expression=normalized_expression,
        parsed_values=parsed_values,
        offset=_canonical_offset_text(offset_seconds),
        offset_seconds=offset_seconds,
        satisfiable=satisfiable,
        next_runs=next_runs,
        count=len(next_runs),
    )
