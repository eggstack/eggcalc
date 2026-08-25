# Exact Text Module

The `eggcalc.exact` module provides **low-level Unicode text primitives and higher-level synthesis functions** for precise text inspection, comparison, and measurement. It's designed for security-conscious applications that need to handle untrusted text input.

## Purpose

Unlike the main calculator which evaluates math expressions, the exact module handles **text analysis without semantic interpretation**:

- Detect hidden/invisible Unicode characters
- Identify confusables and homoglyph attacks
- Measure text metrics (bytes, codepoints, words, lines)
- Compare strings with normalization options
- Validate JSON, brackets, and regex patterns
- Generate diffs with detailed codepoint information

All functions are **deterministic** - same input always produces same output. No LLM calls, no external dependencies.

## Architecture

The module follows a **layered design** where each layer builds on the previous:

```
┌─────────────────────────────────────────────┐
│           synthesis.py                      │  <- Highest level
│  measure_text, text_equal, explain_diff,     │
│  inspect_text, count_chars, list_compare    │
└─────────────────────────────────────────────┘
                      │
┌─────────────────────────┬─────────────────┐
│   unicode_tools.py     │    diff.py       │
│  unicode_script,       │  first_diff,     │
│  detect_mixed_scripts,  │  common_prefix_  │
│  detect_confusables     │  suffix,         │
└─────────────────────────┴─────────────────┘
                      │
┌─────────────────────────┬─────────────────┐
│    measure.py            │   validate.py    │
│  line_metrics,          │  check_brackets, │
│  word_metrics,          │  validate_json,  │
│  char_category_metrics  │  regex_test      │
└─────────────────────────┴─────────────────┘
                      │
┌─────────────────────────────────────────────┐
│           primitives.py                     │  <- Lowest level
│  utf8_bytes, codepoints, normalize_unicode,│
│  casefold_text, raw_equal, normalized_equal,│
│  measure_basic, find_invisibles, visible_repr
└─────────────────────────────────────────────┘
                      │
┌─────────────────────────────────────────────┐
│          confusables.py                     │  <- Data only
│  CONFUSABLES dict (UTS #39 homoglyphs)      │
└─────────────────────────────────────────────┘
```

## primitives.py - Core Unicode Operations

The foundation layer provides fundamental Unicode text operations.

### Basic Measurements

```python
from eggcalc.exact import measure_basic, utf8_bytes, codepoints

text = "Hello, 世界! 🌍"

# Raw UTF-8 bytes (returns a `bytes` object — use len() for the count)
utf8_bytes(text)  # b'Hello, \xe4\xb8\x96\xe7\x95\x8c! \xf0\x9f\x8c\x8d'
len(utf8_bytes(text))  # 19

# Detailed codepoint information (CodepointInfo named tuples)
for cp in codepoints("Hi世"):
    print(f"{cp.idx}: '{cp.char}' {cp.codepoint} ({cp.name})")
# 0: 'H' U+0048 (LATIN CAPITAL LETTER H)
# 1: 'i' U+0069 (LATIN SMALL LETTER I)
# 2: '世' U+4E16 (CJK UNIFIED IDEOGRAPH-4E16)

# Basic metrics (TypedDict — plain dict)
metrics = measure_basic(text)
# {
#   'bytes_utf8': 19,
#   'codepoints': 12,
#   'graphemes_estimate': 12,
#   'chars_no_whitespace': 10,
#   'ascii': 9,
#   'non_ascii': 3
# }
```

### String Comparison

```python
from eggcalc.exact import raw_equal, normalized_equal, casefold_text

# Exact byte-for-byte comparison
raw_equal("café", "café")        # True
raw_equal("café", "cafe\u0301") # False (different bytes)

# Unicode normalization comparison
normalized_equal("café", "cafe\u0301", "NFC")  # True (both normalize to NFC)
normalized_equal("café", "cafe\u0301", "NFD")  # True (both normalize to NFD)

# Case-insensitive comparison
casefold_text("ÜBER")  # "uber"
casefold_text("Σίσυφος")  # "σίσυφος" (Greek sigma final form)
```

### Invisible Character Detection

Zero-width characters, BOM markers, bidi controls, and other invisible text can indicate attacks:

```python
from eggcalc.exact import find_invisibles, visible_repr

# Zero-width space (commonly used in exploits)
text = "user\u200Bname"  # "user​name" (invisible ZWSP between user and name)
invisibles = find_invisibles(text)
# Returns a list of dicts, one per invisible character:
# [{'index': 4, 'char': '\u200b', 'codepoint': 'U+200B',
#   'name': 'ZERO WIDTH SPACE', 'category': 'Cf', 'display': 'ZWSP'}]

# Safe representation that shows invisible characters
visible_repr("hello\u200Bworld")
# 'hello⟦ZWSP⟧world' (ZWSP rendered as a visible marker)
```

**Common invisible characters detected:**

| Codepoint | Name | Risk |
|-----------|------|------|
| U+200B | Zero Width Space | Used to hide words in URLs |
| U+200C | Zero Width Non-Joiner | Bidirectional text manipulation |
| U+200D | Zero Width Joiner | Emoji manipulation |
| U+FEFF | Byte Order Mark | File encoding marker (shouldn't be in strings) |
| U+2066 | Left-to-Right Isolate | Bidi override |

## confusables.py - Homoglyph Detection

Uses the Unicode UTS #39 confusables table (~6500 entries) to detect lookalike characters from different scripts.

**Critical for security:** Attackers can register domains like "pаypal.com" (Cyrillic 'а' looks like Latin 'a') to deceive users.

```python
from eggcalc.exact.unicode_tools import detect_confusables

# Cyrillic 'а' confusable with Latin 'a'
result = detect_confusables("pаypal")
# Returns a list of ConfusableInfo dicts:
# [{'index': 1,
#   'char': 'а',
#   'codepoint': 'U+0430',
#   'name': 'CYRILLIC SMALL LETTER A',
#   'confusable_with': 'a',
#   'confusable_name': 'LATIN SMALL LETTER A'}]

# Note: confusable_with can match multi-character confusables (e.g., "ffi" → "m")
# Digits confusable with other characters
detect_confusables("10")  # May detect '0' confusable with 'O'
```

**Common confusable categories:**

| Script | Example | Confusable With |
|--------|---------|-----------------|
| Latin | a, A | Cyrillic а, А |
| Latin | c, C | Greek с, С |
| Latin | e, E | Cyrillic е, Е |
| Latin | o, O | digit 0, Cyrillic о |
| Latin | p, P | Greek р, Р |
| Latin | x, X | Greek х, Х |
| Digit | 0 | Latin O |
| Digit | 1 | Latin l, I |
| Digit | 2 | Cyrillic е |

## unicode_tools.py - Script Detection

Identify which Unicode script each character belongs to:

```python
from eggcalc.exact.unicode_tools import unicode_script, detect_mixed_scripts

# Single character script detection
unicode_script('A')   # 'Latin'
unicode_script('Д')   # 'Cyrillic'
unicode_script('ア')   # 'Hiragana'
unicode_script('3')   # 'Common'
unicode_script('🎉')   # 'Common' (emoji)

# Detect mixed scripts in text
# Note: Digits and punctuation (script='Other') are excluded from mixed-script detection
result = detect_mixed_scripts("HelloМир")  # Latin + Cyrillic
# TypedDict with keys:
# {
#   'mixed_scripts': True,
#   'scripts': ['Latin', 'Cyrillic'],
#   'positions': [
#     {'index': 0, 'char': 'H', 'script': 'Latin', 'codepoint': 'U+0048'},
#     ...
#   ]
# }
```

**Common scripts:** Latin, Cyrillic, Greek, Han (Chinese), Hiragana, Katakana, Arabic, Hebrew, Devanagari, Common (punctuation, digits, emoji)

**Note:** Characters with script='Other' (digits, punctuation, emoji) are excluded from the mixed_scripts verdict.

## measure.py - Text Metrics

### Line Metrics

```python
from eggcalc.exact.measure import line_metrics

text = "Line 1\nLine 2\r\nLine 3\rLine 4\n"

lm = line_metrics(text)
# TypedDict:
# {
#   'lines': 4,
#   'nonempty_lines': 4,
#   'blank_lines': 0,
#   'max_line_length_codepoints': 6,
#   'trailing_whitespace_lines': [],   # list of line numbers with trailing ws
#   'newline_style': 'mixed',          # LF, CRLF, and CR all present
#   'ends_with_newline': True
# }
```

### Word Metrics

```python
from eggcalc.exact.measure import word_metrics

wm = word_metrics("Hello world! This is a test. One two three.")
# {
#   'words': 9,
#   'unique_words_casefolded': 9,
#   'sentences_estimate': 3,
#   'paragraphs': 1,
#   'average_word_length': 3.89
# }
```

### Character Category Metrics

```python
from eggcalc.exact.measure import char_category_metrics

cm = char_category_metrics("Hello 123! @#$%")
# {
#   'letters': 5,
#   'digits': 3,
#   'punctuation': 4,
#   'symbols': 1,
#   'spaces': 2,
#   'control_chars': 0,
#   'combining_marks': 0
# }
```

## diff.py - Diff Operations

### Finding First Difference

```python
from eggcalc.exact.diff import first_diff

result = first_diff("hello", "hallo")
# TypedDict:
# {
#   'a_index': 1,
#   'b_index': 1,
#   'a_char': 'e',
#   'b_char': 'a',
#   'a_codepoint': 'U+0065',
#   'b_codepoint': 'U+0061'
# }
```

### Common Prefix/Suffix

```python
from eggcalc.exact.diff import common_prefix_suffix

result = common_prefix_suffix("hello world", "hello there")
# {
#   'common_prefix_len': 6,  # "hello "
#   'common_suffix_len': 0   # no common suffix
# }

result = common_prefix_suffix("prefix_middle_suffix", "xxx_middle_yyy")
# {
#   'common_prefix_len': 0,
#   'common_suffix_len': 0   # no common prefix or suffix
# }
```

### Levenshtein Distance

```python
from eggcalc.exact.diff import levenshtein_distance

levenshtein_distance("kitten", "sitting")  # 3 (kitten → sitten → sittin → sitting)
levenshtein_distance("hello", "hello")    # 0 (identical)
```

### Diff Spans

```python
from eggcalc.exact.diff import diff_spans

spans = diff_spans("abc", "axbc")
# [
#   {'kind': 'insert', 'a_span': [1, 1], 'b_span': [1, 2], 'a_text': '', 'b_text': 'x'}
# ]
```

## validate.py - Validation Functions

### Bracket Matching

Check if brackets are balanced with detailed error reporting:

```python
from eggcalc.exact.validate import check_brackets

# Balanced - returns balanced=True
result = check_brackets("(a + b) * [c - d]")
# {'balanced': True, 'unmatched_openers': [], 'unmatched_closers': []}

# Unbalanced - returns details about mismatches
result = check_brackets("(a + b]")  # Round vs square mismatch
# {
#   'balanced': False,
#   'unmatched_openers': [{'char': '(', 'index': 0, 'line': 1, 'column': 1}],
#   'unmatched_closers': [{'char': ']', 'index': 6, 'line': 1, 'column': 7}]
# }

# Nested brackets
result = check_brackets("{{{(a + b) / [c * {d}]}}}")
# {'balanced': True, 'unmatched_openers': [], 'unmatched_closers': []}
```

**Default bracket pairs:** `()` `[]` `{}` `<>`

### JSON Validation

```python
from eggcalc.exact.validate import validate_json

# Valid JSON
result = validate_json('{"name": "test", "count": 42}')
# ValidateJsonResult(
#   valid=True,
#   error=None,
#   line=None,
#   column=None,
#   position=None,
#   type=None,
#   top_level_keys=['name', 'count']
# )

# Invalid JSON with detailed error
result = validate_json('{"name": "test",}')
# ValidateJsonResult(
#   valid=False,
#   error="Expecting property name enclosed in double quotes",
#   line=1,
#   column=19,
#   position=18,
#   type='syntax',
#   top_level_keys=None
# )
```

### Regex Testing

```python
from eggcalc.exact.validate import regex_test

# Test pattern against samples
result = regex_test(
    r"(\d{3})-(\d{4})",  # Phone pattern
    ["123-4567", "hello", "555-1234"]
)
# {
#   'valid_pattern': True,
#   'error': None,
#   'flags_used': [],
#   'results': [
#     {'sample': '123-4567', 'matches': True, 'fullmatch': True, 'span': [0, 8],
#      'groups': ['123', '4567'], 'groupdict': {}},
#     {'sample': 'hello', 'matches': False, ...},
#     {'sample': '555-1234', 'matches': True, ...}
#   ]
# }

# Invalid regex
result = regex_test(r"[invalid", ["test"])
# {'valid_pattern': False, 'error': ..., 'flags_used': [], 'results': []}
```

## synthesis.py - High-Level Operations

The synthesis layer combines primitives into complete operations.

### measure_text - Complete Text Measurement

```python
from eggcalc.exact.synthesis import measure_text

result = measure_text("Hello, 世界!\nThis is line 2.\n")

# Returns comprehensive MeasureTextResult including:
# - Basic: bytes_utf8, codepoints, graphemes, ascii/non_ascii counts
# - Line: lines, max_line_length, newline_style, etc.
# - Word: words, unique_words, sentences_estimate, etc.
# - Char: letters, digits, punctuation, symbols, etc.
# - Normalization: is_nfc, is_nfd, is_nfkc, is_nfkd
# - UnicodeRisks: contains_invisibles, contains_bidi_controls, mixed_scripts
```

### text_equal - String Comparison with Evidence

Compare strings under different normalization modes with detailed evidence:

```python
from eggcalc.exact.synthesis import text_equal

# NFC vs NFD comparison (é can be represented two ways)
result = text_equal("café", "cafe\u0301", normalization="NFC")
# {
#   'equal': True,
#   'mode': {'normalization': 'NFC', 'casefold': False, 'trim': False, ...},
#   'raw_equal': False,
#   'byte_equal': False,
#   'nfc_equal': True,    # Both normalize to same NFC
#   'nfd_equal': True,    # Both normalize to same NFD
#   'classification': 'accent_or_diacritic_difference',
#   ...
# }

# With casefold and trim
result = text_equal("  Hello  ", "hello", casefold=True, trim=True)
# {'equal': True, ...}

# When not equal
result = text_equal("hello", "world")
# {
#   'equal': False,
#   'classification': 'ordinary_text_difference',
#   'first_difference': {'a_index': 0, 'b_index': 0, 'a_char': 'h', 'b_char': 'w', ...},
#   ...
# }
```

**Comparison modes:** `raw` (byte identity, default), `NFC`, `NFD`, `NFKC`, `NFKD`. Options: `casefold`, `trim`, `ignore_newline_style`, `ignore_trailing_whitespace`, `ignore_final_newline`.

### explain_diff - Detailed Diff with Security Findings

```python
from eggcalc.exact.synthesis import explain_diff

result = explain_diff("pаypal", "paypal")
# {
#   'equal': False,
#   'classification': 'ordinary_text_difference',
#   'summary': {
#     'raw_equal': False,
#     'byte_equal': False,
#     'nfc_equal': False,
#     'nfkc_equal': False,
#     'casefold_equal': False,
#     'same_length_codepoints': True,
#     'edit_distance': 1,
#     'common_prefix_len': 1,
#     'common_suffix_len': 4,
#     ...
#   },
#   'diffs': [
#     {
#       'kind': 'replace',
#       'a_span': [1, 2],
#       'b_span': [1, 2],
#       'a_text': 'а',
#       'b_text': 'a',
#       'a_codepoints': [{'char': 'а', 'codepoint': 'U+0430', 'name': 'CYRILLIC SMALL LETTER A'}],
#       'b_codepoints': [{'char': 'a', 'codepoint': 'U+0061', 'name': 'LATIN SMALL LETTER A'}],
#       'note': 'Different codepoints'
#     }
#   ],
#   'security_findings': [
#     {'kind': 'confusables', 'a_count': 1, 'b_count': 0}
#   ],
#   'agent_instruction': 'Strings are not byte-identical and differ in Unicode normalization. ...'
# }
```

### inspect_text - Complete Security Inspection

Comprehensive text inspection for hidden characters, confusables, and Unicode risks:

```python
from eggcalc.exact.synthesis import inspect_text

result = inspect_text("user\u200Bname")  # Contains zero-width space
# TypedDict (plain dict — use key access):
# {
#   'safe_repr': 'user⟦ZWSP⟧name',
#   'metrics': {...},
#   'normalization': {...},
#   'invisibles': [
#     {
#       'index': 4,
#       'char': '\u200B',
#       'codepoint': 'U+200B',
#       'name': 'ZERO WIDTH SPACE',
#       'category': 'Cf',
#       'display': 'ZWSP'
#     }
#   ],
#   'mixed_scripts': {'mixed_scripts': False, 'scripts': [...], 'positions': [...]},
#   'confusables': [],
#   'warnings': [
#     {'severity': 'warning', 'kind': 'invisible_character',
#      'message': 'Text contains ZERO WIDTH SPACE at index 4', 'codepoint': 'U+200B'},
#     ...
#   ],
#   ...  # see architecture/synthesis.md for the full field list
# }
```

### count_chars - Character Counting

```python
from eggcalc.exact.synthesis import count_chars

# Count specific character
result = count_chars("hello world", "l")
# {
#   'target': 'l',
#   'normalization': 'raw',
#   'count': 3,
#   'positions': [2, 3, 9],  # Indices where 'l' appears
#   'text_length_codepoints': 11
# }

# Full frequency table (no target specified)
result = count_chars("hello world")
# Returns dict: {'h': 1, 'e': 1, 'l': 3, 'o': 2, ' ': 1, 'w': 1, 'r': 1, 'd': 1}
```

### list_compare - List Comparison

Compare two lists with various options:

```python
from eggcalc.exact.synthesis import list_compare

result = list_compare(
    ["apple", "banana", "Cherry"],
    ["APPLE", "cherry", "date"],
    casefold=True,  # match ignoring case
)
# {
#   'same_ordered': True,      # bool: lists identical in order
#   'same_unordered': False,   # bool: same items ignoring order
#   'only_in_a': ['banana'],
#   'only_in_b': ['date'],
#   'duplicates_a': [],
#   'duplicates_b': [],
#   'near_matches': []         # only populated when include_near_matches=True
# }

# Default comparison is exact (casefold=False); ignore_order defaults to True.
result = list_compare(["a", "b", "c"], ["c", "b", "a"])
# {'same_ordered': False, 'same_unordered': True, 'only_in_a': [], 'only_in_b': [], ...}
```

## Usage Examples

All synthesis functions return TypedDicts (plain `dict` objects) — always use **key access** (`result["key"]`), not attribute access.

### Security: Validate User Input Against Spoofing

```python
from eggcalc.exact.synthesis import inspect_text

def validate_safe_text(text: str) -> tuple[bool, list[str]]:
    """Check text for Unicode spoofing risks."""
    result = inspect_text(text)

    warnings = []
    if result["confusables"]:
        warnings.append(f"Confusable characters detected: {len(result['confusables'])} found")
    if result["invisibles"]:
        warnings.append(f"Invisible characters detected: {len(result['invisibles'])} found")
    if result["mixed_scripts"]["mixed_scripts"]:
        warnings.append("Mixed Unicode scripts detected")

    is_safe = len(warnings) == 0
    return is_safe, warnings

# Usage
safe, warnings = validate_safe_text("p\u0430ypal")  # Cyrillic confusable
print(warnings)
# ["Confusable characters detected: 1 found"]
```

### Data Integrity: Compare Text with Unicode Edge Cases

```python
from eggcalc.exact import text_equal

def strings_are_equivalent(a: str, b: str) -> bool:
    """Check if two strings are equivalent under NFC normalization."""
    result = text_equal(a, b, normalization="NFC", casefold=False, trim=False)
    return result["equal"]

# These look different but are Unicode-equivalent
strings_are_equivalent("café", "cafe\u0301")  # True (both NFC normalize to "café")
strings_are_equivalent("Å", "\u212B")         # True (both NFC normalize to "Å")
```

### Text Processing: Detect Encoding and Normalization Issues

```python
from eggcalc.exact import measure_text

def check_text_health(text: str) -> dict:
    """Comprehensive text health check."""
    m = measure_text(text)

    issues = []

    if not m["normalization"]["is_nfc"]:
        issues.append("Text is not in NFC normalized form")

    if m["unicode_risks"]["contains_invisibles"]:
        issues.append("Text contains invisible characters")

    if m["unicode_risks"]["contains_bidi_controls"]:
        issues.append("Text contains bidirectional control characters")

    if m["unicode_risks"]["mixed_scripts"]:
        issues.append("Text contains mixed Unicode scripts")

    return {
        "issues": issues,
        "normalized": m["normalization"]["is_nfc"],
        "unicode_safe": len(issues) == 0
    }
```

## Performance Notes

- **Layered design** allows importing only what's needed
- **Primitive operations** are O(n) where n is text length
- **Confusables lookup** is O(1) dict lookup per character
- **Levenshtein distance** has a max length limit (10,000 chars) to prevent DoS
- All operations use only Python standard library - no external dependencies

## See Also

- [MCP Server](mcp.md) - AI agent integration using the exact module
- [Security](security.md) - Using exact module for security hardening
- [CLI](cli.md) - Text inspection tools via `calc inspect`, `calc count`, `calc regex`