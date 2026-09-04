# temporal.py — Fixed-Offset Datetime and Cron Inspection

Deterministic RFC3339/Unix conversion with exact nanosecond precision plus bounded five-field cron inspection with corrected DOM/DOW star-syntax semantics.

## Overview

Pure, side-effect-free temporal math using signed integer nanoseconds as the authoritative instant representation. No floating-point Unix timestamps, no IANA timezone database, no system clock, no local timezone lookup, no network or filesystem access.

Calendar arithmetic uses `date`/`timedelta` only for validity checks and ordinal conversion; epoch math is integer-based so fractional digits 7–9 from RFC3339 input are preserved exactly.

## Key Exports

```python
from eggcalc.exact.temporal import (
    datetime_convert,
    cron_inspect,
)
```

## Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `datetime_convert(value, format, output_offset=None)` | `DatetimeConvertResult` | Convert between `rfc3339` and `unix_seconds`/`unix_milliseconds`/`unix_nanoseconds` with fixed-offset display |
| `cron_inspect(expression, after, count=5)` | `CronInspectResult` | Parse five-field cron, check satisfiability, list strictly-later runs in the reference fixed offset |

## DatetimeConvertResult TypedDict

```python
DatetimeConvertResult(
    rfc3339=str,            # Selected-offset RFC3339 (Z for zero offset)
    utc_rfc3339=str,        # UTC RFC3339 for the same instant
    unix_seconds=str,       # Floor-derived decimal string (e.g. -1ns -> "-1")
    unix_milliseconds=str,  # Floor-derived decimal string
    unix_nanoseconds=str,   # Exact decimal string
    offset_seconds=int,     # Selected offset in seconds
    selected_offset=str,    # Canonical "Z" or "+HH:MM"/"-HH:MM"
    components=DatetimeComponents,  # Wall components in selected offset
)
```

```python
DatetimeComponents(
    year=int,
    month=int,
    day=int,
    hour=int,
    minute=int,
    second=int,
    nanosecond=int,
    weekday=str,            # SUN..SAT
)
```

RFC3339 grammar is bounded: `YYYY-MM-DDTHH:MM:SS[.fraction]Z` or `+/-HH:MM` with 1–9 fractional digits. Offsets are fixed (`Z`, `+HH:MM`, `-HH:MM` with hours 0–23, minutes 0–59, absolute under 24 hours). Unix inputs accept an optional leading `-` with ASCII digits only (no `+`, whitespace, exponents, decimal points, or underscores). Supported calendar range is years 1–9999; out-of-range inputs fail explicitly.

## CronInspectResult TypedDict

```python
CronInspectResult(
    expression=str,             # Original expression text
    normalized_expression=str,  # Explicit sorted numeric values per field
    parsed_values=CronParsedValues,  # Sorted lists per field
    offset=str,                 # Canonical fixed offset from `after`
    offset_seconds=int,
    satisfiable=bool,           # False only after a full 400-year scan finds zero runs
    next_runs=list[str],        # Strictly-later RFC3339 runs in the same offset
    count=int,                  # Actual entries in next_runs
)
```

```python
CronParsedValues(
    minute=list[int],       # 0..59
    hour=list[int],         # 0..23
    day_of_month=list[int], # 1..31
    month=list[int],        # 1..12
    day_of_week=list[int],  # 0..6 (7 normalized to 0)
)
```

Five fields only (`minute hour day-of-month month day-of-week`); macros (`@daily`), six-field forms, and `CRON_TZ=`/`TZ=` prefixes are rejected. Lists, inclusive nonwrapping ranges, and positive `/step` syntax are supported; month names `JAN`–`DEC` and weekday names `SUN`–`SAT` are ASCII case-insensitive. A stepped single value such as `5/10` iterates from the start through the field maximum.

Corrected DOM/DOW rule (after month matches): if either field has star syntax (original text starts with `*`, including `*/n`), require both predicates; otherwise allow either. Explicit full ranges such as `1-31` are not star syntax. Search is strictly after the reference instant at one-minute resolution, reuses the reference fixed offset, caps `count` at 1–32 (default 5), and scans at most 146,097 days (one Gregorian 400-year cycle). Hitting the 0001/9999 calendar boundary before satisfying the request raises `ValueError`; a full 400-year scan with zero matches returns `satisfiable=False` with empty runs.

## Module Dependencies

- `re`, `dataclasses`, `datetime` (`date`, `timedelta`), `typing`
