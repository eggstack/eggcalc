# unicode_tools.py — Script and Confusable Detection

Unicode script detection and confusable character identification.

## Table of Contents

- [Overview](#overview)
- [Type Definitions](#type-definitions)
- [Constants](#constants)
- [Functions](#functions)
  - [unicode_script](#unicode_script)
  - [unicode_scripts](#unicode_scripts)
  - [detect_mixed_scripts](#detect_mixed_scripts)
  - [detect_confusables](#detect_confusables)
  - [confusables_count](#confusables_count)
  - [reverse_confusables](#reverse_confusables)
- [Internal Helpers](#internal-helpers)
- [Supported Scripts](#supported-scripts)
- [Confusables Database](#confusables-database)
- [Dependencies](#dependencies)
- [Usage Example](#usage-example)

## Overview

Provides:

- Unicode script detection per character (Latin, Cyrillic, Greek, Arabic, Han, etc.)
- Mixed-script string detection (potential security issues)
- Confusable homoglyph identification (characters that look identical but have different codepoints)

## Type Definitions

### ScriptInfo (TypedDict)

```python
class ScriptInfo(TypedDict):
    index: int        # Index in string (0-based)
    char: str         # The character
    script: str       # Script name (e.g., "Latin", "Cyrillic")
    codepoint: str    # "U+XXXX" format
```

### ConfusableInfo (TypedDict)

```python
class ConfusableInfo(TypedDict):
    index: int             # Index in string (0-based)
    char: str              # The confusable character
    codepoint: str         # "U+XXXX" format
    name: str              # Unicode name (e.g., "LATIN SMALL LETTER A")
    confusable_with: str   # Character(s) it is confusable with (can be multi-character)
    confusable_name: str   # Unicode name(s) of the confusable character(s)
```

### MixedScriptsResult (TypedDict)

```python
class MixedScriptsResult(TypedDict):
    mixed_scripts: bool           # True if multiple scripts present (excluding Common/Inherited/Other)
    scripts: list[str]            # Distinct scripts found (sorted, excluding Common/Inherited/Other)
    positions: list[ScriptInfo]   # Position details for non-Common/Inherited/Other characters
```

## Constants

### `_SCRIPT_RANGES`

Heuristic codepoint ranges for script detection fallback. Used when `unicodedata.script()` is unavailable (Python < 3.14):

```python
_SCRIPT_RANGES: list[tuple[int, int, str]] = [
    (0x0041, 0x005A, "Latin"),
    (0x0061, 0x007A, "Latin"),
    (0x00C0, 0x00FF, "Latin"),
    (0x0100, 0x017F, "Latin"),
    (0x0180, 0x024F, "Latin"),
    (0x0400, 0x04FF, "Cyrillic"),
    (0x0500, 0x052F, "Cyrillic"),
    (0x0370, 0x03FF, "Greek"),
    (0x1F00, 0x1FFF, "Greek"),
    (0x4E00, 0x9FFF, "Han"),
    (0x3000, 0x303F, "CJK"),
    (0x3040, 0x309F, "Hiragana"),
    (0x30A0, 0x30FF, "Katakana"),
    (0x0600, 0x06FF, "Arabic"),
    (0x0590, 0x05FF, "Hebrew"),
    (0x0900, 0x097F, "Devanagari"),
    (0x0E00, 0x0E7F, "Thai"),
    (0xAC00, 0xD7AF, "Hangul"),
    (0x10A0, 0x10FF, "Georgian"),
    (0x0530, 0x058F, "Armenian"),
    (0x13A0, 0x13FF, "Cherokee"),
    (0x1400, 0x167F, "Canadian_Aboriginal"),
]
```

## Functions

### `unicode_script`

```python
def unicode_script(char: str) -> str
```

Determines the Unicode script of a single character.

```python
unicode_script("A")   # → "Latin"
unicode_script("А")   # → "Cyrillic"
unicode_script("α")   # → "Greek"
unicode_script("中")   # → "Han"
unicode_script("ב")   # → "Hebrew"
unicode_script("あ")   # → "Hiragana"
```

**Returns:** Script name (e.g., `"Latin"`, `"Cyrillic"`, `"Common"`, `"Inherited"`, `"Other"`). Returns `"Other"` for characters not matched by any known script.

**Algorithm:** Tries `unicodedata.script()` first (Python 3.14+), falls back to codepoint range heuristics via `_SCRIPT_RANGES`. Combining marks (category `M*`) are classified as `"Inherited"`.

**Raises:** `ValueError` if input is not a single character.

### `unicode_scripts`

```python
def unicode_scripts(s: str) -> list[str]
```

Returns the script for each character in the string (per-character analysis).

```python
unicode_scripts("Hello")     # → ["Latin", "Latin", "Latin", "Latin", "Latin"]
unicode_scripts("Привет")    # → ["Cyrillic", "Cyrillic", "Cyrillic", "Cyrillic", "Cyrillic", "Cyrillic"]
unicode_scripts("abc123")    # → ["Latin", "Latin", "Latin", "Other", "Other", "Other"]
```

**Note:** Returns a list with one script name per character, not a summary of distinct scripts. Digits, punctuation, and whitespace are classified as `"Common"` or `"Other"`. Use `detect_mixed_scripts()` for mixed-script detection.

### `detect_mixed_scripts`

```python
def detect_mixed_scripts(s: str) -> MixedScriptsResult
```

Detects if a string contains mixed scripts. Ignores `"Common"`, `"Inherited"`, and `"Other"` scripts for the mixed-script verdict.

```python
detect_mixed_scripts("HelloМир")
# → MixedScriptsResult(
#     mixed_scripts=True,
#     scripts=["Cyrillic", "Latin"],
#     positions=[
#         ScriptInfo(index=0, char='H', script='Latin', codepoint='U+0048'),
#         ...
#     ]
# )
```

```python
detect_mixed_scripts("Hello")      # → MixedScriptsResult(mixed_scripts=False, scripts=["Latin"], ...)
detect_mixed_scripts("café123")    # → mixed_scripts=False (digits are "Other")
```

**Security use case:** Detecting homoglyph attacks (e.g., using Cyrillic 'a' in a domain that should be Latin).

### `detect_confusables`

```python
def detect_confusables(s: str) -> list[ConfusableInfo]
```

Finds characters that might be confusable homoglyphs using the full Unicode confusables table (UTS #39) loaded from `confusables.py`.

```python
detect_confusables("pаypal")  # Cyrillic 'а' instead of Latin 'a'
# → [ConfusableInfo(
#     index=1, char='а', codepoint='U+0430',
#     name='CYRILLIC SMALL LETTER A',
#     confusable_with='a',
#     confusable_name='LATIN SMALL LETTER A'
# )]
```

### `confusables_count`

```python
def confusables_count(s: str) -> int
```

Fast helper to count confusable characters without building a full result list.

```python
confusables_count("access")  # → 0 (assuming no confusables in "access")
confusables_count("а")       # → 1 if Cyrillic 'а' is in the confusables table
```

### `reverse_confusables`

```python
def reverse_confusables(char: str) -> list[str]
```

Given a character, returns all characters from the confusables table that confusable-map **to** this character (i.e., characters that look like the given character and could be confused with it).

```python
reverse_confusables("O")  # → ["0"] if digit 0 looks like letter O
reverse_confusables("a")  # → ["а"] if Cyrillic 'а' looks like Latin 'a'
```

**Returns:** List of characters. Empty list if no confusables exist.

**Raises:** `ValueError` if input is not a single character.

## Internal Helpers

### `_get_script_heuristic(char: str) -> str`

Cached (LRU, maxsize=128) script detection using `unicodedata.script()` with range-based heuristic fallback. Not part of the public API.

### `_build_reverse_index() -> dict[str, list[str]]`

Cached (LRU, maxsize=1) function that builds an inverted index mapping target codepoints to source characters from the `CONFUSABLES` table. Used by `reverse_confusables()`.

## Supported Scripts

Heuristic detection covers these script ranges:

| Script | Example Characters | Codepoint Range |
|--------|-------------------|-----------------|
| Latin | A-Z, a-z, à-ÿ | U+0041–U+024F |
| Cyrillic | А-Я, а-я | U+0400–U+052F |
| Greek | α-ω, Α-Ω | U+0370–U+03FF, U+1F00–U+1FFF |
| Han | 中, 文 | U+4E00–U+9FFF |
| CJK | Various | U+3000–U+303F |
| Hiragana | あ, い, う | U+3040–U+309F |
| Katakana | ア, イ, ウ | U+30A0–U+30FF |
| Arabic | ا-ي | U+0600–U+06FF |
| Hebrew | א-ת | U+0590–U+05FF |
| Devanagari | अ-ह | U+0900–U+097F |
| Thai | ก-๛ | U+0E00–U+0E7F |
| Hangul | ㄱ, ㄴ | U+AC00–U+D7AF |
| Georgian | ა-ჰ | U+10A0–U+10FF |
| Armenian | Ա-Ֆ | U+0530–U+058F |
| Cherokee | Ꭰ-Ꮏ | U+13A0–U+13FF |
| Canadian Aboriginal | ᐀-ᗿ | U+1400–U+167F |

On Python 3.14+, `unicodedata.script()` is used first. The heuristic ranges serve as a fallback. Combining marks (category `M*`) are classified as `"Inherited"`. Characters not matching any range or known pattern are `"Other"`.

## Confusables Database

Uses `confusables.py` data file (~180KB) generated from the official Unicode `confusables.txt` file. Maps source codepoint strings to target codepoint strings. Values may contain multiple codepoints (multi-character substitutions).

Key confusables:

| Looks Like | Actual Character | Script |
|------------|------------------|--------|
| a | а (U+0430) | Cyrillic |
| A | А (U+0410) | Cyrillic |
| o | о (U+043E) | Cyrillic |
| e | е (U+0435) | Cyrillic |
| y | у (U+0443) | Cyrillic |
| p | р (U+0440) | Cyrillic |
| c | с (U+0441) | Cyrillic |
| B | В (U+0412) | Cyrillic |
| H | Н (U+041D) | Cyrillic |
| K | К (U+041A) | Cyrillic |
| M | М (U+041C) | Cyrillic |
| T | Т (U+0422) | Cyrillic |
| X | Х (U+0425) | Cyrillic |

## Data Source

The confusables table is derived from **Unicode Standard Annex #39** (https://www.unicode.org/reports/tr39/). The table in `confusables.py` was generated from the official `confusables.txt` file.

## Dependencies

```
unicode_tools.py
    └── confusables.py (CONFUSABLES data)
```

Standard library only (`functools`, `unicodedata`, `typing`) plus the `confusables.py` data file.

## Usage Example

```python
from eggcalc.exact import (
    unicode_script, unicode_scripts,
    detect_mixed_scripts, detect_confusables,
    confusables_count, reverse_confusables,
)

# Single character script
print(unicode_script("中"))  # "Han"

# Per-character scripts
print(unicode_scripts("Hello123"))
# ["Latin", "Latin", "Latin", "Latin", "Latin", "Other", "Other", "Other"]

# Mixed-script detection
text = "pаypal.com"  # Cyrillic 'а'
mixed = detect_mixed_scripts(text)
if mixed["mixed_scripts"]:
    print(f"WARNING: Mixed scripts: {mixed['scripts']}")

# Confusable detection
confusables = detect_confusables(text)
for c in confusables:
    print(f"Confusable: {c['char']} ({c['name']}) looks like {c['confusable_with']}")

# Reverse lookup
lookalikes = reverse_confusables("a")
print(f"Characters that look like 'a': {lookalikes}")
```
