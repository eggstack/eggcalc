# position.py — Text Position Conversion

499 lines. Converts between byte offsets, codepoint indices, line/column positions, and UTF-16 code unit offsets.

## Table of Contents

- [Overview](#overview)
- [Type Definitions](#type-definitions)
- [Constants / Limits](#constants--limits)
- [Public Functions](#public-functions)
  - [text_position](#text_position)
- [Internal Helpers](#internal-helpers)
- [Dependencies](#dependencies)
- [Security / DoS Notes](#security--dos-notes)
- [See Also](#see-also)
- [Usage Example](#usage-example)

## Overview

Deterministic, pure, no I/O — a single conversion entry point mapping any one position
locator (UTF-8 byte offset, Python codepoint index, line+column, or UTF-16 code-unit
offset) to all the others. The same text has four "positions" depending on the consumer:
byte offsets (editors/diffs), codepoint indices (Python strings), line/column (humans and
diagnostics), UTF-16 offsets (JavaScript/LSP tooling). Surrogate pairs outside the BMP
count as 2 UTF-16 code units. Newlines `\n`, `\r\n`, and lone `\r` all advance the line
counter.

Results are plain-dict TypedDicts — use `result["line"]`, never `result.line`.
Out-of-range locators do not raise (except multi-mode misuse, which returns
`valid=False`); they return `valid=False` with an `error` message.

## Type Definitions

### TextPositionResult (TypedDict)

Verified against `eggcalc/exact/position.py:14-30`:

```python
class TextPositionResult(TypedDict):
    valid: bool               # True iff the locator resolved inside the text
    byte_offset: int | None   # UTF-8 byte offset (None when invalid)
    codepoint_index: int | None  # Python string index (None when invalid)
    utf16_offset: int | None  # UTF-16 code-unit offset (None when invalid)
    line: int | None          # line in the requested line_base (None when invalid)
    column: int | None        # column in the requested column_base (None when invalid)
    line_base: int            # echo of the line_base argument (0 or 1)
    column_base: int          # echo of the column_base argument (0 or 1)
    char: str | None          # char at the position; None at end-of-text/invalid (""/None normalized)
    codepoint: str | None     # "U+XXXX" form of char; None at end-of-text/invalid
    name: str | None          # unicodedata.name(char, "<unknown>"); None at end-of-text/invalid
    line_text_preview: str | None  # containing line without trailing \r\n; None when invalid
    error: str | None         # failure reason; None on success
    summary: str              # "Line L, column C" on success, error summary otherwise
```

Note: at end-of-text (`codepoint_index == len(text)`), `char` is reported as `None`
(internal `""` normalized), `codepoint`/`name` are `None`, but the position is still
`valid=True` with a `line_text_preview` of the last line.

## Constants / Limits

No `MAX_*` cap and no module-level constant tables — all math is derived per call from
the input text (see Security notes for the unbounded-input implication).

`line_base` / `column_base` accept `1` (1-based, the default for humans/diagnostics) or
`0` (0-based, LSP-style). They apply symmetrically to input parsing and output rendering.

## Public Functions

### `text_position`

```python
def text_position(
    text: str,
    byte_offset: int | None = None,
    codepoint_index: int | None = None,
    line: int | None = None,
    column: int | None = None,
    utf16_offset: int | None = None,
    line_base: int = 1,
    column_base: int = 1,
) -> TextPositionResult
```

Exactly one locator mode must be provided: `byte_offset`, `codepoint_index`,
`line`+`column` (both required), or `utf16_offset`. Zero or multiple modes return
`valid=False` with `error="Exactly one locator mode must be provided: ..."`.

Verified examples:

```python
text_position("ab\ncd", codepoint_index=4)
# → {'valid': True, 'byte_offset': 4, 'codepoint_index': 4, 'utf16_offset': 4,
#     'line': 2, 'column': 2, 'char': 'd', 'codepoint': 'U+0064',
#     'name': 'LATIN SMALL LETTER D', 'line_text_preview': 'cd', 'error': None,
#     'summary': 'Line 2, column 2'}
text_position("ab\ncd", line=2, column=1)["codepoint_index"]  # → 3
text_position("ab\ncd", line=2, column=1)["char"]             # → 'c'
text_position("a😀b", codepoint_index=1)["utf16_offset"]      # → 1 (😀 starts at UTF-16 unit 1)
text_position("a😀b", codepoint_index=2)["utf16_offset"]      # → 3 (past the 2-unit surrogate pair)
text_position("hi", utf16_offset=1)["char"]                  # → 'i'
text_position("", codepoint_index=0)
# → {'valid': True, 'byte_offset': 0, ..., 'line': 1, 'column': 1, 'char': '',
#     'line_text_preview': '', 'summary': 'Empty text at start position'}
text_position("ab", byte_offset=0, codepoint_index=0)["error"]
# → 'Exactly one locator mode must be provided: byte_offset, codepoint_index, line+column, or utf16_offset'
```

**Byte-offset edge cases (verified on `"héllo"` — `h`=1B, `é`=2B at bytes 1–3):**

```python
text_position("héllo", byte_offset=0)["char"]  # → 'h' (valid)
text_position("héllo", byte_offset=1)["char"]  # → 'é' (valid: lands on the char boundary)
text_position("héllo", byte_offset=2)          # → valid=False, error='Byte offset falls inside multibyte character'
text_position("héllo", byte_offset=3)["char"]  # → 'l' (valid)
text_position("ab", byte_offset=-1)["error"]   # → 'Negative byte offset'
text_position("ab", byte_offset=99)["error"]   # → 'Byte offset exceeds text length'
```

**Other locator edge cases:**

- `codepoint_index`: `< 0` or `> len(text)` → `'Codepoint index out of bounds'`;
  `== len(text)` is valid end-of-text (`char=None`).
- `utf16_offset`: negative → `'Negative UTF-16 offset'`; past-end **clamps** to
  `len(text)` and reports `valid=True` at end-of-text (verified: `text_position("hi",
  utf16_offset=99)` → valid, `codepoint_index=2`, `char=None`, `line_text_preview='hi'`).
  Mid-surrogate offsets resolve to the containing character (`_utf16_offset_to_codepoint_index`
  returns the first index whose cumulative width exceeds the offset).
- `line`+`column`: both required (one missing → `'Both line and column must be provided...'`);
  `line < line_base` → `'Line L is less than minimum line ...'`; past last line →
  `'Line L exceeds maximum line ...'`; `column < column_base` → below-range error;
  past end-of-line → `'Column C exceeds line length ...'`. Note `line_base=0` shifts the
  valid window (e.g. `line=2` on a 2-line text with `line_base=0` exceeds max line 1).
- Empty text: any locator resolving to position 0 is valid; `byte_offset != 0` is rejected
  with `'Byte offset 0 is the only valid position for empty text'`.

## Internal Helpers

- `_utf16_offset_to_codepoint_index(text, utf16_offset)` — cumulative width walk
  (`<= 0xFFFF` → 1 unit, else 2); clamps past-end to `len(text)`.
- `_codepoint_index_to_utf16_offset(text, codepoint_index)` — prefix width sum.
- `_get_line_col(text, byte_offset=None, codepoint_index=None)` — `splitlines(keepends=True)`
  walk returning `(lines, line_num, col)` 0-based; negative byte offsets clamp to 0,
  over-long byte offsets clamp to `len(text)` (callers pre-validate, so clamping only
  matters for the valid path).
- `_is_valid_byte_offset(text, offset)` — boundary check: ASCII start bytes valid;
  continuation bytes (`0x80–0xBF` at `offset`) invalid; lead bytes require intact trailing
  continuation bytes; `offset == len(bytes)` valid.

## Dependencies

```
position.py
    └── stdlib only: unicodedata, typing (leaf module — no exact/ imports)
```

Stdlib-only; safe for the single-file build.

## Security / DoS Notes

- **No input caps:** text length is unbounded in code; every call re-encodes UTF-8
  (`text.encode("utf-8")`) and walks the full string, so per-call cost is O(n) time and
  O(n) transient bytes. Cap caller-side (e.g. reject > 1 MB positions requests) for
  untrusted input.
- No filesystem, subprocess, or network access; `unicodedata.name` failures degrade to
  `"<unknown>"` rather than raising.
- `line_text_preview` echoes a full source line — callers displaying it for untrusted
  documents should truncate (long minified lines can be megabytes).

## See Also

- [primitives.md](primitives.md) — `byte_offset_to_codepoint_index()`, `codepoint_index_to_byte_offset()`, `codepoint_index_to_line_column()`, `line_column_to_codepoint_index()` (raising variants of the same conversions)
- [exact.md](exact.md) — package-level overview

## Usage Example

```python
from eggcalc.exact.position import text_position

# Editor (bytes) → human (line/col) → JS (UTF-16)
r = text_position("ab\ncd", byte_offset=3)
print(r["line"], r["column"])      # 2 1
print(r["char"], r["codepoint"])   # c U+0063
print(r["utf16_offset"])           # 3

# Boundary-safe: check valid before indexing
mid = text_position("héllo", byte_offset=2)
print(mid["valid"], mid["error"])  # False Byte offset falls inside multibyte character

# LSP-style round trip (0-based)
z = text_position("a😀b", codepoint_index=2)
print(z["utf16_offset"])  # 3 (😀 consumed 2 units)
```

(End of file - total 499 lines implementation)
