# synthesis.py - Higher-Level Text Analysis

## Table of Contents

- [Purpose](#purpose)
- [Constants](#constants)
- [TypedDicts](#typeddicts)
- [Core Functions](#core-functions)
- [Internal Helper Functions](#internal-helper-functions)
- [Dependencies](#dependencies)

## Purpose

Combines primitives from `primitives.py`, `unicode_tools.py`, `diff.py`, and `measure.py` to provide higher-level text inspection, comparison, measurement, and editing operations.

## Constants

```python
MAX_TEXT_LENGTH = 100_000   # Maximum input length for most functions
MAX_DIFF_SPANS = 50         # Maximum diff spans in explain_diff
MAX_INSPECT_ITEMS = 100     # Maximum items in inspect_text results
MAX_PREVIEW_CHARS = 2000    # Maximum preview characters in text_replace_check
```

## TypedDicts

### NormalizationState
```python
class NormalizationState(TypedDict):
    """Unicode normalization state."""
    is_nfc: bool
    is_nfd: bool
    is_nfkc: bool
    is_nfkd: bool
```

### UnicodeRisks
```python
class UnicodeRisks(TypedDict):
    """Unicode risk signals."""
    contains_invisibles: bool
    contains_bidi_controls: bool
    mixed_scripts: bool
    scripts: list[str]
```

### MeasureTextResult
```python
class MeasureTextResult(TypedDict):
    """Complete text measurement result."""
    bytes_utf8: int
    codepoints: int
    graphemes: int
    words: int
    unique_words_casefolded: int
    lines: int
    nonempty_lines: int
    blank_lines: int
    max_line_length_codepoints: int
    chars_no_whitespace: int
    ascii: int
    non_ascii: int
    letters: int
    digits: int
    punctuation: int
    symbols: int
    spaces: int
    control_chars: int
    combining_marks: int
    invisible_chars: int
    newline_style: str
    ends_with_newline: bool
    normalization: NormalizationState
    unicode_risks: UnicodeRisks
    warnings: list[str]
```

### TextEqualResult
```python
class TextEqualResult(TypedDict):
    """Text equality comparison result."""
    equal: bool
    mode: dict[str, Any]
    raw_equal: bool
    nfc_equal: bool
    nfd_equal: bool
    nfkc_equal: bool
    nfkd_equal: bool
    casefold_equal: bool
    byte_equal: bool
    lengths: dict[str, int]
    first_difference: dict[str, Any] | None
    classification: str
```

### DiffInfo
```python
class DiffInfo(TypedDict):
    """A single diff span with detailed information."""
    kind: str
    a_span: list[int]
    b_span: list[int]
    a_text: str
    b_text: str
    a_visible: str
    b_visible: str
    a_codepoints: list[dict]
    b_codepoints: list[dict]
    note: str
```

### ExplainDiffResult
```python
class ExplainDiffResult(TypedDict):
    """Detailed diff explanation result."""
    equal: bool
    classification: str
    summary: dict[str, Any]
    a_metrics: dict[str, int]
    b_metrics: dict[str, int]
    diffs: list[DiffInfo]
    security_findings: list[dict]
    agent_instruction: str
```

### InspectTextNormalized
```python
class InspectTextNormalized(TypedDict):
    """Normalized text analysis."""
    form: str
    text: str
    safe_repr: str
    changed: bool
    diff: list[dict]
```

### NormalizationFinding
```python
class NormalizationFinding(TypedDict):
    """A finding from normalization analysis."""
    kind: str
    message: str
```

### InspectTextResult
```python
class InspectTextResult(TypedDict):
    """Complete text inspection result."""
    safe_repr: str
    metrics: MeasureTextResult
    normalization: dict[str, bool]
    normalization_diff: bool
    normals_repr: str | None
    invisibles: list[InvisibleCharInfo]
    bidi_controls: list[InvisibleCharInfo]
    mixed_scripts: MixedScriptsResult
    confusables: list[ConfusableInfo]
    warnings: list[dict]
    limits_applied: list[str]
    normalize: str
    compare_normalized: bool
    original: dict[str, Any]
    normalized: InspectTextNormalized | None
    normalization_findings: list[NormalizationFinding]
```

### CountCharsResult
```python
class CountCharsResult(TypedDict):
    """Character counting result."""
    target: str
    normalization: str
    count: int
    positions: list[int]
    text_length_codepoints: int
```

### ListCompareNearMatch
```python
class ListCompareNearMatch(TypedDict):
    """A near match between list items."""
    a: str
    b: str
    distance: int
    classification: str
```

### ListCompareResult
```python
class ListCompareResult(TypedDict):
    """List comparison result with near-match detection."""
    same_ordered: bool
    same_unordered: bool
    only_in_a: list[str]
    only_in_b: list[str]
    duplicates_a: list[str]
    duplicates_b: list[str]
    near_matches: list[ListCompareNearMatch]
```

### ListCompareOrderedResult
```python
class ListCompareOrderedResult(TypedDict):
    """Ordered list comparison result."""
    equal: bool
    first_diff_index: int | None
    equal_prefix_length: int
    aligned: list[dict]
```

### ListCompareSetResult
```python
class ListCompareSetResult(TypedDict):
    """Set-based list comparison result."""
    equal: bool
    only_in_a: list[str]
    only_in_b: list[str]
```

### ListCompareMultisetResult
```python
class ListCompareMultisetResult(TypedDict):
    """Multiset-based list comparison result."""
    equal: bool
    count_deltas: dict[str, int]
    only_in_a: list[str]
    only_in_b: list[str]
```

### TextWindowPosition
```python
class TextWindowPosition(TypedDict):
    """Position information in text_window."""
    byte_offset: int
    codepoint_index: int
    grapheme_index: int
    line: int
    column: int
```

### TextWindowResult
```python
class TextWindowResult(TypedDict):
    """Result of text_window operation."""
    position: TextWindowPosition
    line_text: str
    line_visible_repr: str
    before: list[dict]
    after: list[dict]
    newline_style: str
    at_codepoint: dict | None
    warnings: list[str]
```

### TextReplaceCheckResult
```python
class TextReplaceCheckResult(TypedDict):
    """Result of text_replace_check."""
    match_count: int
    unique_match: bool
    expected_count_met: bool
    would_change: bool
    positions: list[dict[str, int]]
    changed_text_fingerprint: str
    newline_style_before: str
    newline_style_after: str
    preview_before: str
    preview_after: str
    findings: list[dict[str, str]]
```

### LineRangeExtractResult
```python
class LineRangeExtractResult(TypedDict):
    """Result of line_range_extract."""
    line_count_total: int
    start_line: int
    end_line: int
    valid_range: bool
    text: str
    lines: list[dict[str, Any]]
    byte_start: int
    byte_end: int
    char_start: int
    char_end: int
    newline_style: str
    ends_with_newline: bool
    fingerprint: str
    findings: list[dict[str, str]]
```

### LineRangeCompareResult
```python
class LineRangeCompareResult(TypedDict):
    """Result of line_range_compare."""
    equal: bool
    left_fingerprint: str
    right_fingerprint: str
    diff_summary: str
    first_difference: dict[str, Any] | None
```

## Core Functions

### Text Measurement

#### `measure_text(text: str) -> MeasureTextResult`

Comprehensive text measurement combining multiple primitives: byte size, codepoint count, grapheme count, word metrics, line metrics, character categories, invisibles, mixed scripts, normalization state, and Unicode risk signals.

Generates warnings for combining marks, ZWJ sequences, variation selectors, regional indicator pairs, and emoji modifiers.

```python
>>> measure_text("hello world")
MeasureTextResult(bytes_utf8=11, codepoints=11, graphemes=11, words=2, ...)
```

**Raises:** `ValueError` if text exceeds `MAX_TEXT_LENGTH`.

### Text Comparison

#### `text_equal(a: str, b: str, normalization: str = "raw", casefold: bool = False, trim: bool = False, ignore_newline_style: bool = False, ignore_trailing_whitespace: bool = False, ignore_final_newline: bool = False) -> TextEqualResult`

Compare two strings under various equality modes. Reports equality under all normalization forms (NFC, NFD, NFKC, NFKD), casefold, and byte equality. Classifies the difference type.

Preprocessing order: `ignore_final_newline` -> `ignore_trailing_whitespace` -> `ignore_newline_style` -> `trim`.

Classification values: `exact_match`, `unicode_normalization_only`, `accent_or_diacritic_difference`, `case_only`, `length_only`, `invisible_character`, `ordinary_text_difference`.

```python
>>> text_equal("café", "cafe\u0301", normalization="NFC")
TextEqualResult(equal=True, classification='unicode_normalization_only', ...)
```

### Diff Explanation

#### `explain_diff(a: str, b: str, max_diffs: int = 20, include_codepoints: bool = True, include_context: bool = True, detail: str = "normal") -> ExplainDiffResult`

Explain why two strings differ with detailed evidence. Returns diff spans with codepoint details, security findings (invisible characters, confusables), edit distance, common prefix/suffix lengths, and an agent-facing instruction string.

The `detail` parameter controls truncation: `"summary"` limits to 5 diffs with 50 chars context; `"normal"` uses the full `max_diffs` with 200 chars context; `"full"` uses no equal-span truncation.

```python
>>> explain_diff("abc", "abd")
ExplainDiffResult(equal=False, classification='ordinary_text_difference', ...)
```

**Raises:** `ValueError` if either input exceeds `MAX_TEXT_LENGTH`.

### Text Inspection

#### `inspect_text(text: str, include_codepoints: bool = True, include_confusables: bool = True, detail: str = "normal", normalize: str = "none", compare_normalized: bool = False) -> InspectTextResult`

Inspect text for hidden characters, confusables, mixed scripts, and Unicode signals. Returns safe representation, complete metrics, invisibles/bidi controls, confusable characters, warnings, and optional normalized comparison.

The `detail` parameter controls maximum items returned: `"summary"` -> 10, `"normal"` and `"full"` -> `MAX_INSPECT_ITEMS` (100).

When `compare_normalized=True` and `normalize` is a valid form (`NFC`, `NFD`, `NFKC`, `NFKD`), returns both original and normalized analysis with diff entries showing character-by-character changes.

```python
>>> inspect_text("hello\u200Bworld")
InspectTextResult(safe_repr='hello\\u200Bworld', invisibles=[...], ...)
```

**Raises:** `ValueError` if text exceeds `MAX_TEXT_LENGTH`.

### Character Counting

#### `count_chars(text: str, target: str | None = None, normalization: str = "raw", count_mode: str = "codepoint") -> CountCharsResult | dict[str, int]`

Count character occurrences or return frequency table. When `target` is specified, returns `CountCharsResult` with count and positions. When `target` is `None`, returns a frequency dictionary.

**Count modes:**
- `"codepoint"`: count by codepoint identity
- `"grapheme"`: count by grapheme cluster (uses `list()` for segmentation)
- `"byte"`: count by UTF-8 byte sequence
- `"substring"`: count occurrences of `target` as a substring (overlapping)

```python
>>> count_chars("hello", target="l")
CountCharsResult(target='l', normalization='raw', count=2, positions=[2, 3], ...)
>>> count_chars("hello")
{'h': 1, 'e': 1, 'l': 2, 'o': 1}
```

**Raises:** `ValueError` if text exceeds `MAX_TEXT_LENGTH` or invalid `count_mode`.

### List Comparison

#### `list_compare(a: list[str], b: list[str], ignore_order: bool = True, casefold: bool = False, normalization: str = "NFC", trim: bool = False, treat_as_multiset: bool = True, include_near_matches: bool = False, near_match_threshold: int = 2) -> ListCompareResult`

Compare two lists with optional transformations. Supports casefold, Unicode normalization, and whitespace trimming on elements before comparison.

- `same_ordered`: True if lists are equal after transformation (or `ignore_order=True`)
- `same_unordered`: True if set/multiset equality holds
- `treat_as_multiset`: When True, duplicates don't affect set equality. When False, duplicate counts must match.
- `include_near_matches`: When True, performs O(N*M) Levenshtein comparison within `near_match_threshold`

```python
>>> list_compare(["Alice", "Bob"], ["alice", "bob"], casefold=True)
ListCompareResult(same_ordered=False, same_unordered=True, only_in_a=[], only_in_b=[], ...)
```

### Text Window

#### `text_window(text: str, position: dict, context_lines: int = 2, include_visible_repr: bool = True) -> TextWindowResult`

Get a window around a position in text with context lines. Supports multiple position kinds:

- `byte_offset`: byte offset into UTF-8 encoding
- `codepoint_index`: codepoint index (default)
- `grapheme_index`: grapheme cluster index
- `line_column`: 1-based line and column (requires `line` and `column` keys)

The `position` dict accepts `kind`, `value` (or kind-specific key), `line_base`, and `column_base`.

```python
>>> text_window("line1\nline2\nline3", {"kind": "codepoint_index", "value": 6})
TextWindowResult(position={...}, line_text='line2', before=[{'line': 1, 'text': 'line1'}], ...)
```

### Text Replace Check

#### `text_replace_check(text: str, old: str, new: str, mode: str = "exact", expected_count: int | None = None, allow_multiple: bool = False, newline_policy: str = "preserve", return_preview: bool = False, max_preview_chars: int = MAX_PREVIEW_CHARS) -> TextReplaceCheckResult`

Check whether a replacement would apply cleanly before editing. Reports match count, positions, findings (no match, count mismatch, ambiguous replacement), and optional before/after previews with SHA-256 fingerprints.

**Matching modes:** `exact`, `nfc`, `nfkc`, `casefold`, `whitespace_collapse`.

**Newline policies:** `preserve`, `normalize_lf`, `normalize_crlf`.

**Raises:** `ValueError` if text exceeds `MAX_TEXT_LENGTH`, invalid mode, invalid newline policy, or negative `max_preview_chars`.

### Line Range Extract

#### `line_range_extract(text: str, start_line: int, end_line: int, line_base: int = 1, include_line_numbers: bool = False, include_fingerprint: bool = True) -> LineRangeExtractResult`

Extract exact line ranges with stable byte/char offsets and SHA-256 fingerprint. Supports 0-based or 1-based line numbers via `line_base`.

Returns extracted text, per-line dicts, byte/char offsets, newline style, and findings for out-of-range access (clamps to valid range).

```python
>>> line_range_extract("line1\nline2\nline3", 1, 2)
LineRangeExtractResult(line_count_total=3, text='line1\nline2', ...)
```

**Raises:** `ValueError` if text exceeds `MAX_TEXT_LENGTH` or `start_line > end_line`.

### Line Range Compare

#### `line_range_compare(left_text: str, right_text: str, start_line: int, end_line: int, line_base: int = 1, comparison_mode: str = "exact") -> LineRangeCompareResult`

Compare a line range from two text inputs. Returns equality, SHA-256 fingerprints of both slices, diff summary, and first difference location.

**Comparison modes:** `exact`, `ignore_trailing_whitespace`, `normalize_newlines`.

**Raises:** `ValueError` if either input exceeds `MAX_TEXT_LENGTH` or invalid comparison mode.

## Internal Helper Functions

### `_classify_difference(raw_equal: bool, nfc_equal: bool, casefold_equal: bool, byte_equal: bool, length_diff: bool, first_diff: dict | None, invisibles_detected: bool) -> str`

Classifies the type of difference between two strings. Returns one of:
- `"exact_match"` — strings are identical
- `"unicode_normalization_only"` — NFC equal, byte-different
- `"accent_or_diacritic_difference"` — NFC equal but casefold differs
- `"case_only"` — casefold equal
- `"length_only"` — different lengths
- `"invisible_character"` — invisibles detected
- `"ordinary_text_difference"` — regular text difference

### `_codepoint_details(s: str, start: int, end: int) -> list[dict]`

Get codepoint details (char, codepoint, name) for a span of text.

### `_truncate_diff_spans(spans: list[DiffInfo], max_diffs: int, max_equal_context: int = 200) -> tuple[list[DiffInfo], bool, int]`

Truncate diff spans, limiting equal spans to `max_equal_context` characters and capping total spans at `max_diffs`. Returns (truncated_spans, truncated, total_diffs_exceeding_limit).

### `_generate_agent_instruction(classification: str, raw_equal: bool, nfc_equal: bool, byte_equal: bool) -> str`

Generate agent-facing instruction based on difference classification. Returns human-readable guidance on how to treat the strings.

### `_detect_special_sequences(s: str) -> dict[str, int]`

Detect sequences that cause codepoint/grapheme divergence. Returns counts of: `combining_marks`, `zwj_sequences`, `variation_selectors`, `regional_indicator_pairs`, `emoji_modifiers`.

## Dependencies

`synthesis.py` combines functions from:
- `primitives` — Basic text operations (measure, invisibles, normalization, casefold, graphemes, visible_repr)
- `unicode_tools` — Script detection (`detect_mixed_scripts`) and confusable detection (`detect_confusables`)
- `diff` — Diff algorithms (`diff_spans`, `first_diff`, `levenshtein_distance`, `common_prefix_suffix`)
- `measure` — Text metrics (`line_metrics`, `word_metrics`, `char_category_metrics`)

## Index

See [overview.md](overview.md) for the module index.
