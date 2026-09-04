# Temporal and Cron Utility Parity

Status: planned  
Repository: `eggstack/eggcalc`  
Baseline reviewed: `07e0d66c29bdc7a9ab6d5a41033b372b4cec1994`  
Date: 2026-09-04  
Depends on: `plans/029-eggsact-deterministic-utility-parity-roadmap.md`

## 1. Purpose

Implement the two temporal utilities added to eggsact:

- `datetime_convert`
- `cron_inspect`

This is the only technically nontrivial part of the six-tool parity line because Python's `datetime` type has microsecond precision while the eggsact contract exposes nanoseconds, and because cron semantics must be implemented directly to preserve the standard-library-only rule.

The goal is a small deterministic fixed-offset temporal module, not a general datetime/scheduling framework.

## 2. Governing constraints

- Runtime remains Python standard-library-only.
- No `croniter`, `dateutil`, `pytz`, or other package is added.
- No network, filesystem, environment, locale, system clock, or local timezone lookup occurs.
- No IANA timezone database is required or consulted.
- Do not use floating-point Unix timestamps as the authoritative representation.
- Preserve exact signed nanoseconds across parse/format conversion.
- Cron evaluation is fixed-offset only and strictly bounded.
- Do not add scheduler execution, background tasks, timers, or persistence.
- Do not broaden grammar beyond the reviewed eggsact feature contract.

## 3. File ownership

Create:

```text
eggcalc/exact/temporal.py
```

Keep all temporal helpers private to this module unless an existing exact primitive is already the natural authority. Do not add a general-purpose datetime package tree.

Recommended private decomposition:

```text
_parse_fixed_offset()
_parse_rfc3339_to_ns()
_format_rfc3339_from_ns()
_unix_unit_floor()
_datetime_components()

_parse_cron_number()
_parse_cron_field()
_parse_cron_expression()
_cron_day_matches()
_cron_search_next()
```

Names may vary to fit repository conventions; the architectural boundary should not.

## 4. Workstream A - canonical instant representation

### A1. Use signed integer nanoseconds

Represent every parsed instant internally as:

```text
unix_ns: int
selected_offset_seconds: int
```

This avoids precision loss from Python `datetime.timestamp()` and preserves eggsact's Unix nanosecond contract.

Do not round to microseconds and do not silently drop fractional digits 7-9 from RFC3339 input.

### A2. Epoch conversion without floats

Convert calendar timestamps to epoch nanoseconds using integer arithmetic.

A safe approach is:

1. parse validated year/month/day/hour/minute/second;
2. construct a `date` or `datetime` only for calendar validity checks;
3. derive whole days from the Unix epoch using ordinal/date arithmetic;
4. add whole seconds within the day;
5. subtract the supplied fixed offset seconds;
6. multiply whole seconds by `1_000_000_000`;
7. add parsed nanoseconds.

Reverse conversion should use floor-safe `divmod(unix_ns, 1_000_000_000)` so the fractional remainder is always non-negative even for pre-epoch instants.

### A3. Supported calendar range

Use the range representable by Python's proleptic Gregorian `datetime`/`date` implementation (years 1 through 9999) unless the reviewed eggsact behavior is narrower for a specific conversion.

Inputs outside the supported calendar range must fail explicitly. Do not wrap, clamp, or fall back to platform C-library time functions.

## 5. Workstream B - RFC3339 parsing and formatting

### B1. Accepted input shape

Support the bounded RFC3339 forms needed by eggsact:

```text
YYYY-MM-DDTHH:MM:SSZ
YYYY-MM-DDTHH:MM:SS+HH:MM
YYYY-MM-DDTHH:MM:SS-HH:MM
YYYY-MM-DDTHH:MM:SS.fractionZ
YYYY-MM-DDTHH:MM:SS.fraction+HH:MM
```

Fractional seconds may contain 1 through 9 decimal digits and must be preserved exactly by padding to nanoseconds internally.

Use a small explicit regex/parser rather than relying solely on `datetime.fromisoformat()`, because the public grammar and nanosecond preservation must be controlled deliberately.

Reject malformed separators, missing timezone offsets, excess fractional precision, invalid calendar dates/times, and unsupported offset forms.

### B2. Fixed offsets

Accept only:

```text
Z
+HH:MM
-HH:MM
```

Hours must be 0..23 and minutes 0..59. The absolute offset must remain less than 24 hours.

No named zones, abbreviations, `UTC+4`, military zones, locale names, or timezone database lookups.

### B3. Canonical formatting

Output RFC3339 using:

- `Z` for zero offset;
- `+HH:MM` / `-HH:MM` otherwise;
- no fractional component when nanoseconds are exactly zero;
- otherwise a fractional component that preserves the exact nanosecond value while trimming only unnecessary trailing zeroes if that matches the reviewed eggsact formatting behavior.

Add fixed vectors so canonical formatting is stable and not accidentally changed by a Python minor-version formatting helper.

## 6. Workstream C - `datetime_convert`

### C1. Input contract

Required:

```text
value: str
format: one of
    rfc3339
    unix_seconds
    unix_milliseconds
    unix_nanoseconds
```

Optional:

```text
output_offset: Z or +/-HH:MM
```

Unix values are signed decimal integer strings. Reject whitespace, `+` unless the reviewed eggsact grammar accepts it, exponent notation, decimal points, underscores, and non-ASCII digits.

The reviewed eggsact parser accepts a leading minus and otherwise decimal digits; preserve that narrow contract.

### C2. Offset selection

For RFC3339 input:

- default output offset is the input's own fixed offset;
- `output_offset` overrides only the display offset, not the instant.

For Unix input:

- default output offset is UTC;
- optional `output_offset` changes only the display offset.

Do not infer local timezone.

### C3. Output fields

Return:

```text
rfc3339
utc_rfc3339
unix_seconds
unix_milliseconds
unix_nanoseconds
offset_seconds
selected_offset
components
```

`unix_seconds` and `unix_milliseconds` are decimal strings derived using floor/Euclidean division, matching eggsact for negative fractional instants.

Required regression:

```text
unix_nanoseconds = -1
unix_seconds      = "-1"
unix_milliseconds = "-1"
```

`components` should include at least:

```text
year
month
day
hour
minute
second
nanosecond
weekday
```

Weekday values should use stable `SUN`..`SAT` names matching eggsact.

### C4. Exactness tests

Include:

- Unix epoch;
- one nanosecond before epoch;
- one nanosecond after epoch;
- millisecond boundaries;
- nine-digit RFC3339 fractional seconds;
- offset-preserving parse/format;
- offset conversion to `Z` and nonzero offsets;
- leap year day;
- invalid leap day;
- year-range boundaries supported by Python.

## 7. Workstream D - cron field representation

Use a compact immutable/private structure for each field containing:

```text
allowed values
minimum
maximum
star_syntax: bool
```

A tuple/frozenset plus a small dataclass is sufficient. Do not introduce a scheduler object hierarchy.

`star_syntax` is syntactic metadata, not derivable merely from the final allowed value set. It must record whether the original field starts with `*`, including `*/n`.

This distinction is required for Vixie/Cronie DOM/DOW behavior.

## 8. Workstream E - cron grammar

### E1. Five fields only

Require exactly five whitespace-delimited fields:

```text
minute hour day-of-month month day-of-week
```

Reject:

- `@daily`, `@weekly`, or any `@...` macro;
- six- or seven-field forms;
- `CRON_TZ=...` and `TZ=...` prefixes;
- empty expressions.

### E2. Numeric ranges and names

Ranges:

```text
minute        0..59
hour          0..23
day-of-month  1..31
month         1..12
day-of-week   0..7
```

Names:

```text
JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC
SUN MON TUE WED THU FRI SAT
```

Names are ASCII case-insensitive. Normalize Sunday 7 to 0 in the allowed set.

### E3. Lists, ranges, steps

Support comma lists, inclusive nonwrapping ranges, and positive integer `/step` syntax.

Examples:

```text
*/15
1-10/2
MON-FRI
1,15,30
```

For a stepped single starting value such as `5/10`, preserve eggsact semantics: iterate from the parsed start through the field maximum.

Reject:

- zero step;
- negative step;
- multiple `/` separators;
- empty list items;
- wrapping ranges such as `FRI-MON`;
- values outside field range;
- values that produce an empty allowed set.

## 9. Workstream F - corrected DOM/DOW semantics

This is an acceptance-critical compatibility point. Implement the post-correction eggsact rule, not generic remembered cron semantics.

After month has matched:

```text
DOM matches = day_of_month allows current date.day
DOW matches = day_of_week allows current weekday
```

Then:

```text
if DOM.star_syntax or DOW.star_syntax:
    day matches = DOM matches AND DOW matches
else:
    day matches = DOM matches OR DOW matches
```

Required cases:

```text
0 0 * * MON
    Mondays only

0 0 1 * *
    first day of month only

0 0 1 * MON
    first day of month OR Monday

0 0 1-31 * MON
    explicit full DOM range is not star syntax; OR semantics

0 0 */1 * MON
    `*/1` retains star syntax; Mondays only

0 0 */2 * MON
    only Mondays whose DOM also matches the */2 set

0 0 1 * */1
    first of month only
```

Do not simplify a full range/list to wildcard semantics based on set equality.

## 10. Workstream G - bounded cron search

### G1. Reference instant

`cron_inspect` requires an RFC3339 `after` timestamp. Parse it using the same fixed-offset nanosecond authority as `datetime_convert`.

Results are strictly later than `after`; a schedule occurrence exactly equal to `after` must not be returned.

### G2. Minute resolution

Cron resolution is one minute. Candidate seconds/nanoseconds are zero.

Search by date, then allowed hour, then allowed minute. Do not iterate minute-by-minute across 400 years if a simple date/allowed-value loop can avoid it.

### G3. Fixed offset

Every candidate uses the same fixed offset present on the `after` timestamp. Do not apply DST transitions or timezone database rules.

### G4. Bound

Search at most 146,097 days (one 400-year Gregorian cycle) from the starting date.

Requested `count`:

- defaults to 5;
- minimum 1;
- maximum 32.

If the search reaches the supported calendar boundary before satisfying the request, return the repository's normal invalid/bounded-search failure instead of wrapping.

### G5. Satisfiability

Return a `satisfiable` boolean consistent with the same grammar/day predicates used for search.

Avoid performing a second full 400-year scan if the implementation can derive satisfiability while searching for `next_runs`. One authority for day matching and one bounded search path are preferred.

## 11. Workstream H - `cron_inspect` output

Return:

```text
expression
normalized_expression
parsed_values
offset
offset_seconds
satisfiable
next_runs
count
```

`normalized_expression` should contain explicit sorted numeric allowed values for each field, joined by commas and spaces, matching the eggsact intent.

`parsed_values` should expose the sorted normalized integer sets for:

```text
minute
hour
day_of_month
month
day_of_week
```

The returned `count` is the actual number of entries in `next_runs`, not merely the requested count.

## 12. Resource and cancellation behavior

The direct exact function remains deterministic and bounded by its own 400-year/count limits.

At MCP integration time, `cron_inspect` should receive the repository's moderate-cost timeout/budget treatment; `datetime_convert` is cheap.

Do not add threads, processes, async workers, or bespoke cancellation primitives inside `exact/temporal.py`. The existing MCP executor owns timeout/cancellation policy.

## 13. Tests

Keep tests focused around semantic boundaries rather than implementation details.

Required datetime vectors:

- `0` Unix seconds -> epoch `Z`;
- `-1` Unix nanosecond floor semantics;
- exact nine-digit fraction round trip;
- `2026-09-03T11:00:00-04:00` converted to `Z` -> `2026-09-03T15:00:00Z`;
- offset bounds;
- invalid fractional precision;
- invalid calendar values;
- leap-day behavior.

Required cron vectors:

- `0 9 * * MON-FRI` after Thursday -> Friday 09:00 at same fixed offset;
- names case-insensitive;
- Sunday `0` and `7` equivalence;
- lists/ranges/steps;
- strict-after behavior;
- impossible date combinations such as February 31 do not produce invalid dates;
- aliases/six-field/timezone prefix rejection;
- count 1 and 32;
- count 0/33 rejection;
- all DOM/DOW star-syntax cases in section 9;
- a search near supported date upper bound fails cleanly rather than overflowing.

Static fixtures should record the reviewed eggsact commit IDs. Do not invoke eggsact from tests.

## 14. Completion gate

Plan 031 is complete when:

- `eggcalc/exact/temporal.py` exists;
- `datetime_convert` retains nanosecond precision without float timestamps;
- all supported offsets are explicit and fixed;
- no timezone database/system clock behavior is introduced;
- `cron_inspect` supports exactly the reviewed five-field grammar;
- corrected star-syntax DOM/DOW semantics are covered by regression tests;
- search is strictly-after and bounded to one Gregorian 400-year cycle;
- no dependency is added;
- no scheduling/execution machinery is introduced;
- focused tests pass.

MCP schema/handler registration, single-file manifest integration, generated documentation, and final package/single-file parity are owned by Plan 032.
