# measure.py - Text Metrics

## Table of Contents

- [Purpose](#purpose)
- [Types](#types)
  - [LineMetrics](#linemetrics)
  - [WordMetrics](#wordmetrics)
  - [CharCategoryMetrics](#charchategorymetrics)
- [Functions](#functions)
  - [line_metrics](#line_metricstext-str-linemetrics)
  - [word_metrics](#word_metricstext-str-wordmetrics)
  - [char_category_metrics](#char_category_metricstext-str-charchategorymetrics)
- [Newline Style Detection](#newline-style-detection)
- [Index](#index)

## Purpose

Provides higher-level text measurement functions including line metrics, word metrics, and combined character categorization metrics.

## Types

### LineMetrics

```python
class LineMetrics(TypedDict):
    lines: int
    nonempty_lines: int
    blank_lines: int
    max_line_length_codepoints: int
    trailing_whitespace_lines: list[int]
    newline_style: str  # "LF", "CRLF", "CR", "mixed", "none"
    ends_with_newline: bool
```

### WordMetrics

```python
class WordMetrics(TypedDict):
    words: int
    unique_words_casefolded: int
    sentences_estimate: int
    paragraphs: int
    average_word_length: float
```

### CharCategoryMetrics

```python
class CharCategoryMetrics(TypedDict):
    letters: int
    digits: int
    punctuation: int
    symbols: int
    spaces: int
    control_chars: int
    combining_marks: int
```

## Functions

### `line_metrics(s: str) -> LineMetrics`

Calculate line-level metrics for a string.

Splits input on line boundaries and reports line counts, trailing whitespace, max line length in codepoints, and newline style.

```python
>>> line_metrics("hello\nworld\n")
LineMetrics(lines=2, nonempty_lines=2, blank_lines=0,
            max_line_length_codepoints=5, trailing_whitespace_lines=[],
            newline_style='LF', ends_with_newline=True)
```

**Parameters:**
- `s`: Input string. Empty/falsy string returns zero metrics.

**Returns:** `LineMetrics` with all fields populated.

**Edge cases:**
- Empty string returns all zeros with `newline_style="none"` and `ends_with_newline=False`.
- `trailing_whitespace_lines` contains 1-based line numbers where trailing whitespace was detected.
- `max_line_length_codepoints` counts codepoints (not bytes or grapheme clusters).

### `word_metrics(s: str) -> WordMetrics`

Calculate word-level metrics for a string.

Splits on whitespace, filters to word-like tokens (those containing at least one alphabetic character), and estimates sentences and paragraphs.

```python
>>> word_metrics("hello world hello")
WordMetrics(words=3, unique_words_casefolded=2,
            sentences_estimate=0, paragraphs=1,
            average_word_length=5.0)
```

**Parameters:**
- `s`: Input string. Empty/falsy string returns zero metrics.

**Returns:** `WordMetrics` with all fields populated.

**Word definition:** Tokens from `s.split()` that contain at least one character where `c.isalpha()` is true. Tokens consisting solely of digits or punctuation are excluded.

**Edge cases:**
- `average_word_length` is rounded to 2 decimal places.
- `sentences_estimate` uses a regex heuristic counting sentence-ending punctuation (`[.!?]+`) followed by whitespace, end of string, or an uppercase letter. It is not a robust NLP sentence boundary detector.
- `paragraphs` counts contiguous runs of lines with content separated by blank lines. If there is alphabetic content but no paragraph breaks, returns 1.
- `unique_words_casefolded` is case-insensitive via `str.casefold()`.

### `char_category_metrics(s: str) -> CharCategoryMetrics`

Calculate character category metrics.

Categorizes each character by Unicode general category via `unicodedata.category()`.

```python
>>> char_category_metrics("Hello World! 123")
CharCategoryMetrics(letters=10, digits=3, punctuation=1,
                   symbols=0, spaces=2, control_chars=0,
                   combining_marks=0)
```

**Parameters:**
- `s`: Input string. Empty/falsy string returns all zeros.

**Returns:** `CharCategoryMetrics` with counts per category.

**Category mapping:**

| Field | Unicode category prefix | Notes |
|-------|------------------------|-------|
| `letters` | `L` | All letter subcategories (Lu, Ll, Lt, Lm, Lo) |
| `digits` | `N` | Numbers including Nd, Nl, No |
| `punctuation` | `P` | All punctuation subcategories |
| `symbols` | `S` | All symbol subcategories |
| `spaces` | `Z` | Separators (Zs, Zl, Zp) |
| `control_chars` | `C` | Excludes `Cf` (format characters) per UTS #55 |
| `combining_marks` | `M` | Spacing and non-spacing marks |

**Edge cases:**
- Format characters (`Cf`, e.g. U+FEFF BOM, zero-width joiners) are excluded from `control_chars`.
- All other `C` subcategories (`Cc` control, `Co` private use, `Cn` unassigned) count as `control_chars`.

## Newline Style Detection

The `newline_style` field in `LineMetrics` is determined by the private `_detect_newline_style(s)` helper.

| Style | Description |
|-------|-------------|
| `"LF"` | Unix-style `\n` only |
| `"CRLF"` | Windows-style `\r\n` only |
| `"CR"` | Old Mac-style `\r` only |
| `"mixed"` | Multiple newline types present |
| `"none"` | No newlines in input |

**Detection algorithm:**

1. If `\r\n` is present AND there are standalone `\r` or standalone `\n` → `"mixed"`
2. If there are both standalone `\r` AND standalone `\n` (regardless of `\r\n`) → `"mixed"`
3. If `\r\n` is present (and no standalone `\r` or `\n`) → `"CRLF"`
4. If standalone `\r` only → `"CR"`
5. If standalone `\n` only → `"LF"`
6. Otherwise → `"none"`

The standalone counts are computed as:
- `standalone_cr = s.count("\r") - s.count("\r\n")`
- `standalone_lf = s.count("\n") - s.count("\r\n")`

## Index

See [overview.md](overview.md) for the module index.
