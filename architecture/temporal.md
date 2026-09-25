# temporal.py — Fixed-Offset Datetime and Cron Inspection

616 lines. Deterministic RFC3339/Unix conversion with exact nanosecond
precision plus bounded five-field cron inspection with corrected
DOM/DOW star-syntax semantics. **Standalone leaf: stdlib-only, no
`exact/` dependencies.**

## Table of Contents

- [Overview](#overview)
- [Type Definitions](#type-definitions)
- [Constants / Limits](#constants--limits)
- [Public Functions](#public-functions)
  - [datetime_convert](#datetime_convert)
  - [cron_inspect](#cron_inspect)
- [Internal Helpers](#internal-helpers)
- [Dependencies](#dependencies)
- [Security Notes](#security-notes)
- [See Also](#see-also)

## Overview

Pure, side-effect-free temporal math using signed integer nanoseconds as
the authoritative instant representation. No floating-point Unix
timestamps, no IANA timezone database, no system clock, no local
timezone lookup, no network or filesystem access.

Calendar arithmetic uses `date`/`timedelta` only for validity checks and
ordinal conversion; epoch math is integer-based so fractional digits 7–9
from RFC3339 input are preserved exactly. Cron search is strictly after
the reference instant at one-minute resolution over at most one
Gregorian 400-year cycle.

## Type Definitions

```python
class DatetimeComponents(TypedDict):
    year: int
    month: int
    day: int
    hour: int
    minute: int
    second: int
    nanosecond: int
    weekday: str             # "SUN".."SAT"

class DatetimeConvertResult(TypedDict):
    rfc3339: str             # selected-offset RFC3339 ("Z" for zero offset)
    utc_rfc3339: str         # UTC RFC3339 for the same instant
    unix_seconds: str        # floor-derived decimal string (e.g. -1ns → "-1")
    unix_milliseconds: str   # floor-derived decimal string
    unix_nanoseconds: str    # exact decimal string
    offset_seconds: int      # selected offset in seconds
    selected_offset: str     # canonical "Z" or "+HH:MM"/"-HH:MM"
    components: DatetimeComponents  # wall components in selected offset

class CronParsedValues(TypedDict):
    minute: list[int]        # 0..59
    hour: list[int]          # 0..23
    day_of_month: list[int]  # 1..31
    month: list[int]         # 1..12
    day_of_week: list[int]   # 0..6 (7 normalized to 0)

class CronInspectResult(TypedDict):
    expression: str              # original expression text
    normalized_expression: str   # explicit sorted numeric values per field
    parsed_values: CronParsedValues
    offset: str                  # canonical fixed offset from `after`
    offset_seconds: int
    satisfiable: bool            # False only after a full 400-year scan finds zero runs
    next_runs: list[str]         # strictly-later RFC3339 runs in the same offset
    count: int                   # actual entries in next_runs

class _CronField:                # internal (plain class, not TypedDict)
    allowed: set[int]
    minimum: int
    maximum: int
    star_syntax: bool
```

## Constants / Limits

```python
MAX_TEXT_INPUT_length = 100_000
_NS_PER_SECOND = 1_000_000_000
_NS_PER_MILLISECOND = 1_000_000
_SECONDS_PER_DAY = 86_400
_MAX_OFFSET_SECONDS = 86_400     # |offset| must be < 24h (hours 0-23, minutes 0-59)
_MAX_CRON_DAYS = 146_097         # one Gregorian 400-year cycle
_MAX_CRON_COUNT = 32             # count must be in 1..32 (default 5)
_EPOCH_ORDINAL = date(1970, 1, 1).toordinal()
_MIN_ORDINAL / _MAX_ORDINAL      # date(1,1,1) .. date(9999,12,31)
_WEEKDAY_NAMES = ("SUN", ..., "SAT")
_DATETIME_FORMATS = ("rfc3339", "unix_seconds", "unix_milliseconds", "unix_nanoseconds")
_OFFSET_RE / _DIGIT_CHARS
```

RFC3339 grammar (bounded): `YYYY-MM-DDTHH:MM:SS[.fraction]Z` or
`±HH:MM`, 1–9 fractional digits. Unix inputs: optional leading `-` with
ASCII digits only (no `+`, whitespace, exponents, decimal points, or
underscores). Calendar range years 1–9999; out-of-range fails explicitly.

## Public Functions

### `datetime_convert`

```python
def datetime_convert(
    value: str, format: str, output_offset: str | None = None
) -> DatetimeConvertResult
```

`format` names the **input** grammar. `output_offset` overrides only the
display offset, never the instant (default: the input's own offset for
RFC3339, UTC for Unix inputs).

```python
datetime_convert("2024-01-01T00:00:00Z", "rfc3339")["unix_seconds"]
# → "1704067200"

datetime_convert("0", "unix_seconds")["rfc3339"]
# → "1970-01-01T00:00:00Z"

datetime_convert("2024-01-01T00:00:00.123456789Z", "rfc3339")["unix_nanoseconds"]
# → "1704067200123456789"

datetime_convert("0", "unix_seconds", output_offset="+05:30")["rfc3339"]
# → "1970-01-01T05:30:00+05:30"
```

### `cron_inspect`

```python
def cron_inspect(expression: str, after: str, count: int = 5) -> CronInspectResult
```

Five fields only (`minute hour day-of-month month day-of-week`); macros
(`@daily`), six-field forms, and `CRON_TZ=`/`TZ=` prefixes are rejected.
Lists, inclusive nonwrapping ranges, and positive `/step` are supported;
month names `JAN`–`DEC` and weekday names `SUN`–`SAT` are ASCII
case-insensitive. A stepped single value such as `5/10` iterates from
the start through the field maximum.

Corrected DOM/DOW rule (after month matches): if either field has star
syntax (original text starts with `*`, including `*/n`), require both
predicates; otherwise allow either. Explicit full ranges such as `1-31`
are **not** star syntax.

```python
cron_inspect("*/5 * * * *", after="2024-01-01T00:00:00Z", count=2)
# → {"satisfiable": True,
#     "next_runs": ["2024-01-01T00:05:00Z", "2024-01-01T00:10:00Z"], ...}

cron_inspect("0 0 29 2 *", after="2024-01-01T00:00:00Z", count=1)
# → {"satisfiable": True, "next_runs": ["2024-02-29T00:00:00Z"], ...}
```

`count` outside 1–32 raises `ValueError`; hitting the 0001/9999 calendar
boundary before satisfying the request raises `ValueError`; a full
400-year scan with zero matches returns `satisfiable=False` with empty
runs.

## Internal Helpers

| Helper | Role |
|--------|------|
| `_check_text_length(value, name)` | Enforces `MAX_TEXT_INPUT_length` |
| `_parse_fixed_offset(text)` | `Z` / `±HH:MM` → `(offset_seconds, canonical)` |
| `_parse_rfc3339_to_ns(text)` | Bounded-grammar parse → `(unix_ns, input_offset)` |
| `_format_rfc3339_from_ns(unix_ns, offset_seconds)` | Integer math → RFC3339 text |
| `_unix_unit_floor(unix_ns)` | Floor-derived seconds/milliseconds + exact nanoseconds strings |
| `_datetime_components(unix_ns, offset_seconds)` | Wall components + `SUN`..`SAT` weekday |
| `_canonical_offset_text(offset_seconds)` | `0`→`"Z"`, else `±HH:MM` |
| `_check_unix_integer(value)` | Signed ASCII-digit validation |
| `_parse_cron_number(token, min, max, names)` | One numeric/name token → int |
| `_parse_cron_field(...)` | Lists/ranges/steps → `_CronField` (tracks star syntax) |
| `_parse_cron_expression(expression)` | Five fields → tuple of `_CronField` |
| `_cron_day_matches(...)` | Corrected DOM/DOW predicate |
| `_cron_search_next(...)` | 400-year minute-resolution scan |

## Dependencies

```
temporal.py
    └── (standard library only: re, dataclasses, datetime [date, timedelta], typing)
```

No `exact/` imports — fully standalone leaf.

## Security Notes

- Integer-only time: no float rounding anywhere in the pipeline, so
  scheduling comparisons on `unix_nanoseconds` strings are exact. Never
  convert through `float` downstream.
- Fixed offsets only: IANA zone names (`America/New_York`) are rejected,
  so DST-ambiguous local times cannot enter. Ambiguity is a parse error,
  not a guess.
- Cron scan is bounded (146,097 days, `count ≤ 32`) — adversarial
  expressions like `0 0 29 2 *` terminate quickly instead of spinning.

## See Also

- [encoding.md](encoding.md) — exact decimal strings, same no-float philosophy
- [network.md](network.md) — same fail-closed strict-grammar style
- [validate.md](validate.md) — adjacent deterministic validation surface
