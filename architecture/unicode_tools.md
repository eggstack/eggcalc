# unicode_tools.py — Script and Confusable Detection

Unicode script detection and confusable character identification.

## File: `eggcalc/exact/unicode_tools.py`

## Overview

Detects:
- Unicode scripts (Latin, Cyrillic, Greek, Arabic, Han, etc.)
- Mixed-script strings (potential security issues)
- Confusable homoglyphs (characters that look identical but have different code points)

## Type Definitions

### ScriptInfo (TypedDict)

```python
class ScriptInfo(TypedDict):
    index: int        # Index in string
    char: str         # The character
    script: str       # Script name (e.g., "Latin", "Cyrillic")
    codepoint: str    # "U+XXXX" format
```

### ConfusableInfo (TypedDict)

```python
class ConfusableInfo(TypedDict):
    index: int             # Index in string
    char: str              # The confusable character
    codepoint: str         # "U+XXXX" format
    name: str              # Unicode name
    confusable_with: str   # What it might be confused with (can be multi-character)
    confusable_name: str    # Confusing character's name
```

## Functions

### `unicode_script(char: str) -> str`

Returns the script of a single character.

```python
unicode_script("A")      # → "Latin"
unicode_script("А")       # → "Cyrillic"
unicode_script("α")       # → "Greek"
unicode_script("中")      # → "Han"
unicode_script("ב")       # → "Hebrew"
unicode_script("あ")      # → "Hiragana"
```

**Returns:** Script name or "Unknown" if not determinable.

**Algorithm**: Tries `unicodedata.script()` first (Python 3.14+), falls back to codepoint range heuristics.

### `unicode_scripts(s: str) -> list[str]`

Returns script for each character in the string (per-character analysis).

**Note:** This function returns a list with one script name per character, not a summary. For example, `"abc123"` returns `["Latin", "Latin", "Latin", "Latin", "Latin", "Latin"]` (digits are classified as "Latin" via the script heuristics). Use `detect_mixed_scripts()` if you need to detect mixed-script strings.

```python
unicode_scripts("Hello")     # → ["Latin", "Latin", "Latin", "Latin", "Latin"]
unicode_scripts("Привет")    # → ["Cyrillic", ...]
unicode_scripts("abc123")    # → ["Latin", "Latin", "Latin", "Latin", "Latin", "Latin"]
```

### `detect_mixed_scripts(s: str) -> dict`

Detects runs of mixed scripts in a string.

```python
{
    "mixed_scripts": bool,      # True if multiple scripts present
    "scripts": list[str],       # Distinct scripts (excluding Common/Inherited)
    "positions": list[ScriptInfo]  # Positions of non-Common/Inherited/Other chars
}
```

```python
detect_mixed_scripts("HelloМир")
# → {'mixed_scripts': True, 'scripts': ['Latin', 'Cyrillic'],
#    'positions': [ScriptInfo(index=0, char='H', script='Latin', ...), ...]}
```

**Note**: Ignores `"Common"` and `"Inherited"` scripts for the mixed-script verdict.

**Security use case:** Detecting homoglyph attacks (e.g., "p@ypass.com" using Cyrillic 'a')

### `detect_confusables(s: str) -> list[ConfusableInfo]`

Finds characters that might be confusable homoglyphs.

```python
detect_confusables("pаypal")  # Cyrillic 'а' instead of Latin 'a'
# → [{'index': 1, 'char': 'а', 'codepoint': 'U+0430',
#     'name': 'CYRILLIC SMALL LETTER A',
#     'confusable_with': 'a',
#     'confusable_name': 'LATIN SMALL LETTER A'}]
```

### `confusables_count(s: str) -> int`

Fast helper to count confusables without building full list.

```python
confusables_count("access")  # → 0 or more depending on confusables present
confusables_count("а")       # → 1 if Cyrillic 'а' looks like Latin 'a'
```

### `reverse_confusables(char: str) -> list[str]`

Given a character, returns all characters from the confusables table that confusable-map TO this character (i.e., characters that look like the given character and could be confused with it).

```python
reverse_confusables("O")   # → ["0"] if digit 0 is confusable with letter O
reverse_confusables("a")   # → ["а"] if Cyrillic 'а' is confusable with Latin 'a'
```

**Returns:** List of characters that are confusable with the input. Empty list if no confusables exist.

**Raises:** `ValueError` if input is not a single character.

## Supported Scripts

| Script | Example Characters | Codepoint Range |
|--------|-------------------|-----------------|
| Latin | A-Z, a-z | U+0041-U+024F |
| Cyrillic | А-Я, а-я | U+0400-U+052F |
| Greek | α-ω, Α-Ω | U+0370-U+03FF, U+1F00-U+1FFF |
| Arabic | ا-ي | U+0600-U+06FF |
| Hebrew | א-ת | U+0590-U+05FF |
| Han | 中, 文 | U+4E00-U+9FFF |
| Hiragana | あ, い, う | U+3040-U+309F |
| Katakana | ア, イ, ウ | U+30A0-U+30FF |
| Hangul | ㄱ, ㄴ | U+AC00-U+D7AF |
| Thai | ก-๛ | U+0E00-U+0E7F |
| Devanagari | अ-ह | U+0900-U+097F |
| Georgian | ა-ჰ | U+10A0-U+10FF |
| Armenian | Ա-Ֆ | U+0530-U+058F |
| Cherokee | Ꭰ-Ꮏ | U+13A0-U+13FF |
| Canadian Aboriginal | ᐀-ᗿ | U+1400-U+167F |
| CJK | Various | U+3000-U+303F |

**Note:** The `unicode_scripts()` function returns per-character script analysis (a list with one entry per character), not a list of distinct scripts. See `unicode_scripts()` documentation for details.

## Confusables Database

Uses `confusables.py` data file (~180KB) which maps characters to their confusable equivalents. Values may contain multiple codepoints (multi-character substitutions).

Key confusables:
| Looks Like | Actual Character | Script |
|------------|------------------|--------|
| a | а | Cyrillic |
| A | А | Cyrillic |
| o | о | Cyrillic |
| e | е | Cyrillic |
| y | у | Cyrillic |
| p | р | Cyrillic |
| c | с | Cyrillic |
| B | В | Cyrillic |
| H | Н | Cyrillic |
| K | К | Cyrillic |
| M | М | Cyrillic |
| T | Т | Cyrillic |
| X | Х | Cyrillic |

## Data Source

The confusables table is derived from **Unicode Standard Annex #39** (https://www.unicode.org/reports/tr39/). The table in `confusables.py` was generated from the official `confusables.txt` file.

## Dependencies

```
unicode_tools.py
    └── confusables.py (CONFUSABLES data)
```

Uses only standard library (`functools`, `unicodedata`, `typing`) plus the `confusables.py` data file.

## Security Applications

### Homoglyph Attack Detection

```python
def detect_potential_homoglyph_attack(domain: str) -> bool:
    """Check if domain might be using confusable characters."""
    confusables = detect_confusables(domain)
    return len(confusables) > 0
```

Note: `check_domain_safety()` is not an exported function. Use `detect_mixed_scripts()` directly for domain safety checks.

## Usage Example

```python
from eggcalc.exact import (
    unicode_script, unicode_scripts,
    detect_mixed_scripts, detect_confusables
)

# Check a string for security issues
text = "p@ypal.com"

# Check for mixed scripts
mixed = detect_mixed_scripts(text)
if mixed:
    print("WARNING: Mixed scripts detected!")

# Check for confusables
confusables = detect_confusables(text)
for c in confusables:
    print(f"Confusable: {c['char']} ({c['name']}) looks like {c['confusable_with']}")
```

## Testing

Test cases should include:
- Pure ASCII (no mixed scripts, no confusables)
- Single non-Latin script (no mixed scripts)
- Mixed scripts (Latin + Cyrillic common in attacks)
- Confusable characters in isolation
- Emoji and ZWJ sequences (should not trigger confusable alerts)
- Empty string

## Index

- `unicode_script()`
- `unicode_scripts()`
- `detect_mixed_scripts()`
- `detect_confusables()`
- `confusables_count()`
- `reverse_confusables()`

See [overview.md](overview.md) for the module index.
