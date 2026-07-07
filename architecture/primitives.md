# primitives.py — Core Unicode Primitives

Low-level Unicode text primitives built on Python's `unicodedata` module. These are the **building blocks** for all other `exact/` modules.

## Table of Contents

- [Overview](#overview)
- [Type Definitions](#type-definitions)
- [Constants](#constants)
- [Public Functions](#public-functions)
  - [utf8_bytes](#utf8_bytes)
  - [codepoints](#codepoints)
  - [normalize_unicode](#normalize_unicode)
  - [casefold_text](#casefold_text)
  - [raw_equal](#raw_equal)
  - [normalized_equal](#normalized_equal)
  - [measure_basic](#measure_basic)
  - [find_invisibles](#find_invisibles)
  - [visible_repr](#visible_repr)
  - [count_graphemes](#count_graphemes)
  - [truncate_to_grapheme](#truncate_to_grapheme)
  - [byte_offset_to_codepoint_index](#byte_offset_to_codepoint_index)
  - [codepoint_index_to_byte_offset](#codepoint_index_to_byte_offset)
  - [codepoint_index_to_line_column](#codepoint_index_to_line_column)
  - [line_column_to_codepoint_index](#line_column_to_codepoint_index)
  - [get_line_text](#get_line_text)
  - [get_surrounding_lines](#get_surrounding_lines)
  - [detect_newline_style](#detect_newline_style)
- [Internal Helpers](#internal-helpers)
- [Dependencies](#dependencies)

## Overview

Provides low-level deterministic operations for:

- UTF-8 encoding
- Codepoint iteration and inspection
- Unicode normalization and case folding
- Invisible character detection
- Text measurement (bytes, codepoints, graphemes, whitespace, ASCII)
- Grapheme cluster counting and truncation
- Byte/codepoint/line-column index conversions
- Newline style detection

**Key principle:** No semantic interpretation, no LLM calls, deterministic results.

## Type Definitions

### CodepointInfo (NamedTuple)

```python
class CodepointInfo(NamedTuple):
    idx: int        # Position in string (0-indexed)
    char: str       # The character itself
    codepoint: str  # "U+XXXX" hex format
    name: str       # Unicode name (e.g., "LATIN SMALL LETTER A")
    category: str   # Unicode category (e.g., "Ll", "Lu", "Nd")
```

### MeasureBasic (TypedDict)

```python
class MeasureBasic(TypedDict):
    bytes_utf8: int              # Length in UTF-8 bytes
    codepoints: int              # Number of codepoints
    graphemes_estimate: int      # Estimated grapheme clusters
    chars_no_whitespace: int     # Non-whitespace characters
    ascii: int                   # ASCII characters (codepoint < 128)
    non_ascii: int               # Non-ASCII characters
```

### InvisibleCharInfo (TypedDict)

```python
class InvisibleCharInfo(TypedDict):
    index: int           # Position in string
    char: str            # The invisible character
    codepoint: str       # "U+XXXX" format
    name: str            # Unicode name
    category: str        # Unicode category
    display: str         # Short display name (e.g., "ZWSP", "CTRL", "CM")
```

## Constants

### `_INVISIBLE_CHARS`

Dictionary mapping invisible characters to `(full_name, short_display)` tuples:

```python
_INVISIBLE_CHARS: dict[str, tuple[str, str]] = {
    "\u200b": ("ZERO WIDTH SPACE", "ZWSP"),
    "\u200c": ("ZERO WIDTH NON-JOINER", "ZWNJ"),
    "\u200d": ("ZERO WIDTH JOINER", "ZWJ"),
    "\u200e": ("LEFT-TO-RIGHT MARK", "LRM"),
    "\u200f": ("RIGHT-TO-LEFT MARK", "RLM"),
    "\ufeff": ("ZERO WIDTH NO-BREAK SPACE", "BOM"),
    "\u00a0": ("NO-BREAK SPACE", "NBSP"),
    "\u2028": ("LINE SEPARATOR", "LINE SEP"),
    "\u2029": ("PARAGRAPH SEPARATOR", "PARA SEP"),
    "\u202a": ("LEFT-TO-RIGHT EMBEDDING", "LRE"),
    "\u202b": ("RIGHT-TO-LEFT EMBEDDING", "RLE"),
    "\u202c": ("POP DIRECTIONAL FORMATTING", "PDF"),
    "\u202d": ("LEFT-TO-RIGHT OVERRIDE", "LRO"),
    "\u202e": ("RIGHT-TO-LEFT OVERRIDE", "RLO"),
    "\u2066": ("LEFT-TO-RIGHT ISOLATE", "LRI"),
    "\u2067": ("RIGHT-TO-LEFT ISOLATE", "RLI"),
    "\u2068": ("FIRST STRONG ISOLATE", "FSI"),
    "\u2069": ("POP DIRECTIONAL ISOLATE", "PDI"),
    "\u2060": ("WORD JOINER", "WORD JOINER"),
    "\u00ad": ("SOFT HYPHEN", "SHY"),
    "\u180e": ("MONGOLIAN VOWEL SEPARATOR", "MVS"),
    "\u034f": ("COMBINING GRAPHEME JOINER", "CGJ"),
}
```

### `_VARIATION_SELECTORS`

Set of codepoints U+FE00 through U+FE0F:

```python
_VARIATION_SELECTORS = set(range(0xFE00, 0xFE10))
```

## Public Functions

### `utf8_bytes`

```python
def utf8_bytes(s: str) -> bytes
```

Returns raw UTF-8 encoded bytes of the string.

```python
utf8_bytes("hello")        # → b'hello'
utf8_bytes("こんにちは")   # → b'\xe3\x81\x93...'
utf8_bytes("")             # → b''
```

**Returns:** `bytes` object, not an int count.

### `codepoints`

```python
def codepoints(s: str) -> list[CodepointInfo]
```

Returns detailed information about each codepoint in the string.

```python
codepoints("Hi")
# → [
#     CodepointInfo(idx=0, char='H', codepoint='U+0048', name='LATIN CAPITAL LETTER H', category='Lu'),
#     CodepointInfo(idx=1, char='i', codepoint='U+0069', name='LATIN SMALL LETTER I', category='Ll')
# ]
```

### `normalize_unicode`

```python
def normalize_unicode(s: str, form: str) -> str
```

Normalizes Unicode string to the specified form.

```python
normalize_unicode("café", "NFC")        # → "café" (composed)
normalize_unicode("cafe\u0301", "NFC")  # → "café" (same as above)
normalize_unicode("café", "NFD")        # → "cafe\u0301" (decomposed)
```

**Valid forms:** `NFC`, `NFD`, `NFKC`, `NFKD` (case-insensitive).

**Raises:** `ValueError` if form is not a recognized normalization form.

### `casefold_text`

```python
def casefold_text(s: str) -> str
```

Returns casefolded version for case-insensitive comparison.

```python
casefold_text("HELLO")   # → "hello"
casefold_text("Straße")  # → "strasse" (German ß → ss)
```

### `raw_equal`

```python
def raw_equal(a: str, b: str) -> bool
```

Checks exact byte equality (identity comparison).

```python
raw_equal("abc", "abc")           # → True
raw_equal("abc", "ABC")           # → False
raw_equal("café", "cafe\u0301")  # → False (different representations)
```

### `normalized_equal`

```python
def normalized_equal(a: str, b: str, form: str = "NFC") -> bool
```

Checks equality after Unicode normalization.

```python
normalized_equal("café", "cafe\u0301")  # → True
normalized_equal("ABC", "abc")           # → False (case-sensitive)
normalized_equal("café", "cafe\u0301", form="NFD")  # → True
```

**Default form:** `NFC`.

### `measure_basic`

```python
def measure_basic(s: str) -> MeasureBasic
```

Returns basic text metrics.

```python
measure_basic("Hello World")
# → MeasureBasic(
#     bytes_utf8=11, codepoints=11, graphemes_estimate=11,
#     chars_no_whitespace=10, ascii=11, non_ascii=0
# )
```

### `find_invisibles`

```python
def find_invisibles(s: str) -> list[InvisibleCharInfo]
```

Finds all invisible or control characters in the string. Detects:

- Known invisible characters (`_INVISIBLE_CHARS` dict)
- Variation selectors (U+FE00–U+FE0F)
- Format characters (U+2061–U+2065)
- BIDI controls (U+2066–U+206F)
- Combining marks (category `M*`)
- Other control characters (category `C*`, excluding `\n`, `\t`, `\r`)

```python
find_invisibles("hello\u200bworld")
# → [InvisibleCharInfo(
#     index=5, char='\u200b', codepoint='U+200B',
#     name='ZERO WIDTH SPACE', category='Cf', display='ZWSP'
# )]
```

### `visible_repr`

```python
def visible_repr(s: str) -> str
```

Returns a display-safe representation of the string. Maps invisible or ambiguous characters to visible markers.

**Replacement mapping:**

| Character | Output |
|-----------|--------|
| Space (U+0020) | `␠` |
| Tab (U+0009) | `␉` |
| Newline (U+000A) | `␊` |
| Carriage return (U+000D) | `␍` |
| `_INVISIBLE_CHARS` members | `⟦{display}⟧` (e.g., `⟦ZWSP⟧`) |
| Variation selectors (U+FE00–U+FE0F) | `⟦VS⟧` |
| Combining marks (category `M*`) | `◌{char}` |
| Format chars (U+2061–U+2065) | `⟦FORMAT:{label}⟧` |
| BIDI controls (U+2066–U+206F) | `⟦{name}⟧` (e.g., `⟦LRI⟧`, `⟦PDF⟧`) |

**Detection order:** Whitespace → `_INVISIBLE_CHARS` → variation selectors → combining marks → format chars → BIDI controls → pass through.

```python
visible_repr("hello\u200bworld")  # → 'hello⟦ZWSP⟧world'
visible_repr("hi")                # → 'hi'
```

### `count_graphemes`

```python
def count_graphemes(s: str) -> int
```

Counts approximate user-visible grapheme clusters. Handles common combining marks, variation selectors, emoji ZWJ sequences, and regional-indicator flag pairs. **Not** a complete UAX #29 implementation.

```python
count_graphemes("hello")       # → 5
count_graphemes("café")        # → 4 (é as single grapheme)
count_graphemes("👨‍👩‍👧‍👦")    # → 1 (family emoji is ZWJ sequence)
count_graphemes("🇺🇸")          # → 1 (flag = 2 regional indicators)
```

### `truncate_to_grapheme`

```python
def truncate_to_grapheme(s: str, max_graphemes: int) -> str
```

Truncates a string to at most `max_graphemes` grapheme clusters, preserving grapheme integrity. Best-effort; not a complete UAX #29 implementation.

```python
truncate_to_grapheme("Hello World", 5)  # → "Hello"
truncate_to_grapheme("café", 3)         # → "caf"
truncate_to_grapheme("👋🌍", 1)          # → "👋"
truncate_to_grapheme("hello", 0)        # → ""
```

Returns `""` if `max_graphemes <= 0`. Returns `s` unchanged if `len(s) == 0`.

### `byte_offset_to_codepoint_index`

```python
def byte_offset_to_codepoint_index(s: str, byte_offset: int) -> int
```

Converts a UTF-8 byte offset (0-based) to a codepoint index (0-based).

**Raises:** `ValueError` if `byte_offset` is out of range or falls inside a multi-byte character.

```python
byte_offset_to_codepoint_index("abc", 0)   # → 0
byte_offset_to_codepoint_index("你好", 3)   # → 1 (first char is 3 bytes)
```

### `codepoint_index_to_byte_offset`

```python
def codepoint_index_to_byte_offset(s: str, codepoint_index: int) -> int
```

Converts a codepoint index (0-based) to a UTF-8 byte offset (0-based).

**Raises:** `ValueError` if `codepoint_index` is out of range.

```python
codepoint_index_to_byte_offset("abc", 0)  # → 0
codepoint_index_to_byte_offset("你好", 1)  # → 3
```

### `codepoint_index_to_line_column`

```python
def codepoint_index_to_line_column(
    s: str, codepoint_index: int, line_base: int = 1, column_base: int = 1
) -> tuple[int, int]
```

Converts a codepoint index to (line, column). Both line and column are 1-based by default.

**Raises:** `ValueError` if `codepoint_index` is out of range.

```python
codepoint_index_to_line_column("ab\ncd", 4)  # → (2, 1)
```

### `line_column_to_codepoint_index`

```python
def line_column_to_codepoint_index(
    s: str, line: int, column: int, line_base: int = 1, column_base: int = 1
) -> int
```

Converts line and column to a codepoint index. Both are 1-based by default.

**Raises:** `ValueError` if line or column is out of range.

```python
line_column_to_codepoint_index("ab\ncd", 2, 1)  # → 3
```

### `get_line_text`

```python
def get_line_text(s: str, line: int, line_base: int = 1) -> str
```

Extracts the text of a specific line (without the trailing newline). Returns `""` if the line does not exist.

```python
get_line_text("ab\ncd\nef", 2)  # → "cd"
get_line_text("ab\ncd", 5)      # → ""
```

### `get_surrounding_lines`

```python
def get_surrounding_lines(
    s: str, line: int, context_lines: int, line_base: int = 1
) -> tuple[list[tuple[int, str]], list[tuple[int, str]]]
```

Returns lines before and after a given line, each as a list of `(line_number, text)` tuples. The target line itself is excluded.

```python
get_surrounding_lines("a\nb\nc\nd\ne", 3, 1)
# → ([(2, 'b')], [(4, 'd')])
```

### `detect_newline_style`

```python
def detect_newline_style(s: str) -> str
```

Returns the newline style of a string: `"CRLF"`, `"LF"`, `"CR"`, or `"mixed"`. Defaults to `"LF"` if no newlines are found.

```python
detect_newline_style("a\nb")      # → "LF"
detect_newline_style("a\r\nb")    # → "CRLF"
detect_newline_style("a\rb")      # → "CR"
detect_newline_style("a\n\rb")    # → "mixed"
```

## Internal Helpers

These private functions support grapheme cluster segmentation:

### `_advance_grapheme(s, i, n) -> int`

Advances past one grapheme cluster starting at position `i`. Handles regional indicator pairs (GB12/GB13), extend characters (GB9), and emoji ZWJ sequences (GB11).

### `_is_extend_char(char) -> bool`

Checks if a character is an Extend-class character for grapheme segmentation: combining marks (category `M*`), ZWNJ (U+200C), or variation selectors (U+FE00–U+FE0F). ZWJ (U+200D) is **not** included here.

### `_is_extended_pictographic(char) -> bool`

Checks if a character is Extended Pictographic for emoji ZWJ sequences. Uses codepoint range heuristics for common emoji blocks (U+1F300–U+1F9FF, U+2600–U+26FF, U+2700–U+27BF) and `So` category name matching.

## Dependencies

```
primitives.py
    └── (standard library only: unicodedata, typing)
```

No external dependencies.

## Usage Example

```python
from eggcalc.exact import (
    utf8_bytes, codepoints, normalize_unicode, casefold_text,
    measure_basic, count_graphemes, find_invisibles, visible_repr,
    truncate_to_grapheme, detect_newline_style,
)

# Basic measurements
text = "Café naïve"
metrics = measure_basic(text)
print(f"UTF-8 bytes: {metrics['bytes_utf8']}")
print(f"Codepoints: {metrics['codepoints']}")
print(f"Graphemes: {count_graphemes(text)}")

# Normalization comparison
raw = "café"
decomposed = "cafe\u0301"
print(f"Raw equal: {raw == decomposed}")            # False
print(f"NFC equal: {normalize_unicode(raw, 'NFC') == normalize_unicode(decomposed, 'NFC')}")  # True

# Case-insensitive comparison
print(casefold_text("Straße") == "strasse")         # True

# Invisible detection
hidden = "password\u200b123"
invisibles = find_invisibles(hidden)
if invisibles:
    print(f"Found {len(invisibles)} invisible characters!")
print(visible_repr(hidden))                          # 'password⟦ZWSP⟧123'

# Newline detection
print(detect_newline_style("a\r\nb"))               # 'CRLF'
```
