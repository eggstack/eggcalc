# position.py — Text Position Conversion

503 lines. Converts between byte offsets, codepoint indices, line/column positions, and UTF-16 code unit offsets.

## Overview

Provides a single conversion entry point that maps any one position locator (byte offset, codepoint index, line/column, or UTF-16 offset) to all the others. This matters because the same text has four different "positions" depending on the consumer: byte offsets (editors/diffs), codepoint indices (Python strings), line/column (humans and diagnostics), and UTF-16 offsets (JavaScript/JSON tooling). All conversion is lexical — no filesystem access, fully deterministic. Surrogate pairs outside the BMP count as 2 UTF-16 code units.

## Key Exports

```python
from eggcalc.exact.position import text_position
```

## Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `text_position(text, byte_offset=None, codepoint_index=None, line=None, column=None, utf16_offset=None, line_base=1, column_base=1)` | `TextPositionResult` | Convert between position systems |

Exactly one locator mode (`byte_offset`, `codepoint_index`, `line`+`column`, or `utf16_offset`) should be provided. `line_base`/`column_base` select 0-based or 1-based line/column conventions for both input and output.

## TypedDict: TextPositionResult

| Field | Type | Description |
|-------|------|-------------|
| `valid` | `bool` | Whether the requested position resolved inside the text |
| `byte_offset` | `int \| None` | UTF-8 byte offset of the position |
| `codepoint_index` | `int \| None` | Python string index of the position |
| `utf16_offset` | `int \| None` | UTF-16 code unit offset |
| `line` / `column` | `int \| None` | Line and column in the requested base |
| `line_base` / `column_base` | `int` | Bases actually used (echoed back) |
| `char` | `str \| None` | The character at the position |
| `codepoint` | `str \| None` | `U+XXXX` form of the character |
| `name` | `str \| None` | Unicode name of the character |
| `line_text_preview` | `str \| None` | Preview of the containing line |
| `error` | `str \| None` | Error message when invalid |
| `summary` | `str` | Human-readable summary |

Out-of-range locators do not raise; they return `valid=False` with an `error` message (negative byte offsets clamp toward the start, offsets past end-of-text resolve there).

## Module Dependencies

- `unicodedata`, `typing` (stdlib only; leaf module — no other exact/ imports)

## See Also

- [primitives.md](primitives.md) — related helpers: `byte_offset_to_codepoint_index()`, `codepoint_index_to_byte_offset()`, `codepoint_index_to_line_column()`, `line_column_to_codepoint_index()`
- [exact.md](exact.md) — package-level overview
- [overview.md](overview.md) — architecture index
