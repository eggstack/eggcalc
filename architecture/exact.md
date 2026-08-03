# exact/ — Unicode Text Primitives

Low-level deterministic Unicode text analysis tools. These modules are **independent** and **testable** without semantic interpretation or LLM calls.

## Table of Contents

- [Module Structure](#module-structure)
- [Public API](#exact__initpy--public-api)
- [primitives.py](#primitivespy--core-text-primitives)
- [unicode_tools.py](#unicode_toolspy--script-and-confusable-detection)
- [confusables.py](#confusablespy--homoglyph-data)
- [measure.py](#measurepy--text-metrics)
- [diff.py](#diffpy--string-comparison-algorithms)
- [diff_analysis.py](#diff_analysispy--structural-diff-analysis)
- [validate.py](#validatepy--format-validation)
- [synthesis.py](#synthesipy--higher-level-analysis)
- [transform.py](#transformpy--text-transformations)
- [identifier.py](#identifierpy--identifier-analysis)
- [identifier_inspect.py](#identifier_inspectpy--identifier-inspection)
- [position.py](#positionpy--text-position-conversion)
- [glob.py](#globpy--glob-pattern-matching)
- [config.py](#configpy--config-file-validation)
- [patch.py](#patchpy--unified-diff-parsing)
- [inspect_prompt.py](#inspect_promptpy--prompt-injection-detection)
- [markdown.py](#markdownpy--markdown-structure-analysis)
- [shell.py](#shellpy--shell-command-parsing)
- [unicode_policy.py](#unicode_policypy--unicode-safety-policies)
- [cargo.py](#cargopy--cargo-inspection)
- [version.py](#versionpy--version-constraint-checking)
- [llm_hygiene.py](#llm_hygienepy--llm-json-output-hygiene)
- [repo_audit.py](#repo_auditpy--repository-inventory)
- [manifests.py](#manifestspy--manifest-inspection)
- [Architecture Notes](#architecture-notes)
- [Testing](#testing)

## Module Structure

```
exact/
├── __init__.py            # Public API re-exports
├── primitives.py          # UTF-8, codepoints, normalization, invisibles
├── unicode_tools.py       # Script detection, confusables
├── confusables.py         # Homoglyph data (compressed payload, lazy decode)
├── measure.py             # Text metrics (words, lines, categories)
├── diff.py                # String diffing algorithms
├── diff_analysis.py       # Structural analysis of unified diffs and patches
├── validate.py            # JSON/bracket/regex/TOML validation, version comparison
├── synthesis.py           # Higher-level text analysis
├── glob.py                # Glob pattern matching
├── transform.py           # Text escaping, hashing, fingerprinting
├── identifier.py          # Identifier naming convention analysis
├── identifier_inspect.py  # Identifier collision detection
├── path_tools.py          # Path analysis and normalization
├── position.py            # Text position conversion
├── config.py              # .env and INI validation
├── patch.py               # Unified diff parsing and simulation
├── inspect_prompt.py      # Hidden char/ANSI/instruction detection
├── markdown.py            # Markdown structure analysis and link checking
├── shell.py               # Shell command parsing and argv comparison
├── unicode_policy.py      # Named Unicode safety policies
├── cargo.py               # Cargo.toml inspection
├── version.py             # Semver/cargo constraint checking
├── llm_hygiene.py         # LLM JSON output hygiene detection
├── repo_audit.py          # Repository file inventory analysis
└── manifests.py           # Manifest/package inspection (pyproject, package.json, etc.)
```

## exact/__init__.py — Public API

Re-exports all public functions from submodules:

```python
from eggcalc.exact import (
    # Primitives
    utf8_bytes, codepoints, normalize_unicode, casefold_text,
    raw_equal, normalized_equal, measure_basic, count_graphemes,
    truncate_to_grapheme, find_invisibles, visible_repr,

    # Unicode tools
    unicode_script, unicode_scripts, detect_mixed_scripts,
    detect_confusables, confusables_count, reverse_confusables,

    # Diff
    first_diff, common_prefix_suffix, levenshtein_distance,
    diff_spans, longest_common_subsequence,

    # Diff analysis
    diff_touched_paths, diff_hunk_ranges, diff_file_headers,
    patch_conflict_markers_inspect, unified_diff_validate,

    # Validate
    check_brackets, validate_json, validate_toml_text, toml_shape,
    validate_schema_light, regex_test, regex_finditer, regex_safety_check,
    json_extract, json_compare, json_shape,
    version_compare, list_dedupe, list_sort,

    # Measure
    line_metrics, word_metrics, char_category_metrics,

    # Position
    text_position,

    # Transform
    escape_text, unescape_text, text_hash, text_transform, text_fingerprint,

    # Synthesis
    measure_text, text_equal, inspect_text, explain_diff,
    count_chars, list_compare, text_replace_check,
    line_range_extract, line_range_compare, text_window,

    # Glob
    glob_match,

    # Identifier
    identifier_analyze, identifier_inspect, identifier_table_inspect,

    # Path
    path_analyze, path_normalize, path_compare, path_scope_check,

    # Config
    dotenv_validate, ini_validate,

    # Patch
    patch_apply_check, patch_summary,

    # Inspect Prompt
    prompt_input_inspect,

    # Markdown
    markdown_structure, code_fence_extract, markdown_link_check_lexical,

    # Shell
    shell_split, shell_quote_join, argv_compare,

    # Unicode Policy
    unicode_policy_check, canonicalize_text,

    # Cargo
    cargo_toml_inspect,

    # Version
    parse_version, check_version_constraint,

    # LLM Hygiene
    llm_json_output_check,

    # Repo Audit
    repo_file_inventory,

    # Prompt Inspection
    prompt_input_inspect,
)
```

**Note:** `regex_replace_preview`, `json_canonicalize`, and `json_query` exist in `validate.py` but are **not** re-exported from `__init__.py`. They are internal functions only.

---

## primitives.py — Core Text Primitives

Low-level operations built on Python's `unicodedata` module.

### Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `utf8_bytes(s)` | bytes | Raw UTF-8 encoded bytes |
| `codepoints(s)` | list[CodepointInfo] | Detailed codepoint information |
| `normalize_unicode(s, form)` | str | NFC/NFD/NFKC/NFKD normalization |
| `casefold_text(s)` | str | Case-insensitive comparison |
| `raw_equal(a, b)` | bool | Exact string equality |
| `normalized_equal(a, b, form)` | bool | Equality after normalization (default NFC) |
| `measure_basic(s)` | MeasureBasic | Basic text metrics |
| `count_graphemes(s)` | int | Grapheme cluster count |
| `truncate_to_grapheme(s, max_graphemes)` | str | Truncate to grapheme boundary |
| `find_invisibles(s)` | list[InvisibleCharInfo] | Detect hidden characters |
| `visible_repr(s)` | str | Display-safe representation |
| `byte_offset_to_codepoint_index(s, byte_offset)` | int | Convert UTF-8 byte offset to codepoint index |
| `codepoint_index_to_byte_offset(s, codepoint_index)` | int | Convert codepoint index to UTF-8 byte offset |
| `codepoint_index_to_line_column(s, codepoint_index)` | tuple[int, int] | Convert codepoint index to line/column |
| `line_column_to_codepoint_index(s, line, column)` | int | Convert line/column to codepoint index |
| `get_line_text(s, line, line_base)` | str | Extract text of a specific line |
| `get_surrounding_lines(s, line, context)` | str | Extract lines around a position |
| `detect_newline_style(s)` | str | Detect LF/CRLF/CR/mixed/none |

### CodepointInfo NamedTuple

```python
CodepointInfo(
    idx=int,        # Position in string (NOTE: field is "idx", not "index")
    char=str,       # The character
    codepoint=str,  # "U+XXXX" format
    name=str,       # Unicode name
    category=str    # Unicode category (Lu, Nd, Po, etc.)
)
```

### MeasureBasic TypedDict

```python
MeasureBasic(
    bytes_utf8=int,          # UTF-8 byte count
    codepoints=int,          # Codepoint count
    graphemes_estimate=int,  # Grapheme cluster estimate
    chars_no_whitespace=int, # Non-whitespace characters
    ascii=int,               # ASCII character count
    non_ascii=int            # Non-ASCII character count
)
```

### Invisible Characters Detected

```python
{
    "\u200b": "ZERO WIDTH SPACE (ZWSP)",
    "\u200c": "ZERO WIDTH NON-JOINER (ZWNJ)",
    "\u200d": "ZERO WIDTH JOINER (ZWJ)",
    "\u200e": "LEFT-TO-RIGHT MARK (LRM)",
    "\u200f": "RIGHT-TO-LEFT MARK (RLM)",
    "\ufeff": "ZERO WIDTH NO-BREAK SPACE (BOM)",
    "\u00a0": "NO-BREAK SPACE (NBSP)",
    "\u2028": "LINE SEPARATOR",
    "\u2029": "PARAGRAPH SEPARATOR",
    "\u202a": "LEFT-TO-RIGHT EMBEDDING (LRE)",
    "\u202b": "RIGHT-TO-LEFT EMBEDDING (RLE)",
    "\u202c": "POP DIRECTIONAL FORMATTING (PDF)",
    "\u202d": "LEFT-TO-RIGHT OVERRIDE (LRO)",
    "\u202e": "RIGHT-TO-LEFT OVERRIDE (RLO)",
    "\u2060": "WORD JOINER",
    "\u2066": "LEFT-TO-RIGHT ISOLATE (LRI)",
    "\u2067": "RIGHT-TO-LEFT ISOLATE (RLI)",
    "\u2068": "FIRST STRONG ISOLATE (FSI)",
    "\u2069": "POP DIRECTIONAL ISOLATE (PDI)",
    "\u00ad": "SOFT HYPHEN (SHY)",
    "\u180e": "MONGOLIAN VOWEL SEPARATOR (MVS)",
    "\u034f": "COMBINING GRAPHEME JOINER (CGJ)",
}
```

---

## unicode_tools.py — Script and Confusable Detection

### Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `unicode_script(char)` | str | Script of a character |
| `unicode_scripts(s)` | list[str] | Scripts for all characters |
| `detect_mixed_scripts(s)` | MixedScriptsResult | Find mixed-script runs |
| `detect_confusables(s)` | list[ConfusableInfo] | Find confusable homoglyphs |
| `confusables_count(s)` | int | Fast confusable count |
| `reverse_confusables(char)` | list[str] | Find chars that confusable-map TO this char |

### ScriptInfo TypedDict

```python
ScriptInfo(
    index=int,       # Position in string
    char=str,        # The character
    script=str,      # Script name (Latin, Cyrillic, etc.)
    codepoint=str,   # "U+XXXX" format
)
```

### ConfusableInfo TypedDict

```python
ConfusableInfo(
    index=int,              # Position in string
    char=str,               # The confusable character
    codepoint=str,          # "U+XXXX" format
    name=str,               # Unicode name
    confusable_with=str,    # Character(s) this is confusable with
    confusable_name=str,    # Unicode name(s) of confusable character(s)
)
```

### MixedScriptsResult TypedDict

```python
MixedScriptsResult(
    mixed_scripts=bool,     # True if multiple scripts present
    scripts=list[str],      # Distinct scripts found
    positions=list[ScriptInfo],  # Position details
)
```

### reverse_confusables

```python
reverse_confusables(char: str) -> list[str]
```

Given a character, returns all characters from the confusables table that confusable-map TO this character (i.e., characters that look like the given character).

```python
# Digit 0 looks like letter O
"0" in reverse_confusables("O")  # True
```

Returns an empty list if no characters confusable-map to the input.

---

## confusables.py — Homoglyph Data

**Auto-generated file** (~40KB) with a zlib-compressed base85 payload and lazy `_LazyConfusables` mapping (6565 entries). Data is decoded on first access, not at import time.

Source: Unicode confusables.txt (UTS #39), version 17.0.0. Regenerated with `scripts/generate_confusables.py`. Do not edit directly.

Data format: The file stores a zlib-compressed base85 payload and a `_LazyConfusables` class that decodes it on first access. The `CONFUSABLES` object is a `Mapping[str, str]` with the same key/value semantics as the former eager dict.
```

The table maps Unicode codepoint strings (e.g., `"U+0410"` for Cyrillic А) to their confusable substitution sequences. Names are derived at runtime via `unicodedata.name()`.

---

## measure.py — Text Metrics

### Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `char_category_metrics(s)` | CharCategoryMetrics | Metrics by Unicode category |
| `line_metrics(s)` | LineMetrics | Line count and newline style |
| `word_metrics(s)` | WordMetrics | Word count and boundaries |

Note: `measure_basic()` is defined in `primitives.py`, not `measure.py`.

### CharCategoryMetrics TypedDict

```python
CharCategoryMetrics(
    letters=int,          # Total letter characters
    digits=int,           # Total digit characters
    punctuation=int,      # Total punctuation characters
    symbols=int,          # Total symbol characters
    spaces=int,           # Total space/separator characters
    control_chars=int,    # Total control characters
    combining_marks=int,  # Total combining marks
)
```

### LineMetrics TypedDict

```python
LineMetrics(
    lines=int,                              # Total number of lines
    nonempty_lines=int,                     # Lines with content
    blank_lines=int,                        # Empty lines
    max_line_length_codepoints=int,         # Longest line length
    trailing_whitespace_lines=list[int],    # 1-based line numbers
    newline_style=str,                      # "LF", "CRLF", "CR", "mixed", "none"
    ends_with_newline=bool                  # Whether string ends with newline
)
```

### WordMetrics TypedDict

```python
WordMetrics(
    words=int,                          # Total word count
    unique_words_casefolded=int,        # Unique words after casefolding
    sentences_estimate=int,             # Estimated sentence count
    paragraphs=int,                     # Paragraph count
    average_word_length=float,          # Average word length
)
```

---

## diff.py — String Comparison Algorithms

### Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `first_diff(a, b)` | FirstDiff \| None | Position of first difference (None if equal) |
| `common_prefix_suffix(a, b)` | CommonPrefixSuffix | Longest common prefix/suffix lengths |
| `levenshtein_distance(a, b)` | int | Edit distance (capped at MAX_LEVENSHTEIN_LEN=10000) |
| `diff_spans(a, b)` | list[DiffSpan] | Spans that differ (max 50 spans) |
| `longest_common_subsequence(a, b)` | str | LCS via dynamic programming |

### DiffSpan TypedDict

```python
DiffSpan(
    kind=str,            # "equal", "insert", "delete", "replace"
    a_span=list[int],    # [start, end) in string a
    b_span=list[int],    # [start, end) in string b
    a_text=str,
    b_text=str,
)
```

### FirstDiff TypedDict

```python
FirstDiff(
    a_index=int,         # Position of first difference in string a
    b_index=int,         # Position of first difference in string b
    a_char=str,          # Character at position in string a
    b_char=str,          # Character at position in string b
    a_codepoint=str,     # "U+XXXX" format
    b_codepoint=str,     # "U+XXXX" format
)
```

### CommonPrefixSuffix TypedDict

```python
CommonPrefixSuffix(
    common_prefix_len=int,   # Length of common prefix
    common_suffix_len=int,   # Length of common suffix (non-overlapping)
)
```

---

## diff_analysis.py — Structural Diff Analysis

Structural analysis tools for unified diffs and patches. Depends on `patch.py` for `parse_unified_diff` and `MAX_PATCH_LENGTH`.

### Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `diff_touched_paths(patch_text)` | DiffTouchedPathsResult | Classify files as added/deleted/renamed/modified |
| `diff_hunk_ranges(patch_text)` | DiffHunkRangesResult | Extract hunk ranges with line counts |
| `diff_file_headers(patch_text)` | DiffFileHeadersResult | Extract metadata from diff headers |
| `patch_conflict_markers_inspect(text)` | PatchConflictMarkersResult | Detect conflict markers |
| `unified_diff_validate(patch_text)` | UnifiedDiffValidateResult | Validate diff structural integrity |

### DiffTouchedPathsResult TypedDict

```python
DiffTouchedPathsResult(
    parse_ok=bool,
    error=str | None,
    added=list[str],
    deleted=list[str],
    renamed=list[dict[str, str]],
    modified=list[str],
    binary_files=list[str],
    mode_changes=list[ModeChange],
    total_files=int,
)
```

### DiffHunkRangesResult TypedDict

```python
DiffHunkRangesResult(
    parse_ok=bool,
    error=str | None,
    files=list[DiffHunkRangesFile],
)
```

### DiffFileHeadersResult TypedDict

```python
DiffFileHeadersResult(
    parse_ok=bool,
    error=str | None,
    files=list[DiffFileHeaderEntry],
)
```

### PatchConflictMarkersResult TypedDict

```python
PatchConflictMarkersResult(
    total_markers=int,
    conflict_starts=int,
    conflict_separators=int,
    conflict_ends=int,
    imbalanced=bool,
    nested=bool,
    locations=list[ConflictMarkerLocation],
)
```

### UnifiedDiffValidateResult TypedDict

```python
UnifiedDiffValidateResult(
    parse_ok=bool,
    files_count=int,
    hunks_total=int,
    warnings=list[str],
    structure_valid=bool,
)
```

---

## validate.py — Format Validation

### Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `check_brackets(s)` | CheckBracketsResult | Balanced bracket check |
| `validate_json(s)` | ValidateJsonResult | JSON syntax validation |
| `validate_toml_text(s)` | ValidateTomlResult | TOML syntax validation |
| `toml_shape(s)` | TomlShapeResult | Analyze TOML structure |
| `validate_schema_light(data, schema)` | ValidateSchemaLightResult | JSON schema lightweight validation |
| `regex_test(pattern, samples)` | RegexTestResult | Test regex against samples |
| `regex_finditer(pattern, text)` | RegexFindIterResult | Find all regex matches with positions |
| `regex_safety_check(pattern)` | RegexSafetyResult | Check regex for catastrophic backtracking |
| `json_extract(json_str, path)` | JsonExtractResult | Extract data from JSON using path |
| `json_compare(a, b)` | JsonCompareResult | Compare two JSON documents |
| `json_shape(s)` | JsonShapeResult | Analyze JSON structure |
| `version_compare(a, b, scheme)` | VersionCompareResult | Compare version strings |
| `list_dedupe(lst)` | list | Remove duplicate items preserving order |
| `list_sort(lst, ...)` | list | Sort list with normalization |

**Internal functions (not exported from `__init__.py`):**
- `regex_replace_preview(pattern, replacement, text)` — Preview regex replacement
- `json_canonicalize(s)` — Canonicalize JSON with duplicate key detection
- `json_query(json_str, pointer)` — RFC 6901 JSON Pointer query

### CheckBracketsResult TypedDict

```python
CheckBracketsResult(
    balanced=bool,
    unmatched_openers=list[BracketError],
    unmatched_closers=list[BracketError],
)
```

Where `BracketError` contains: `char` (bracket character), `index` (position), `line`, `column` (1-based).

Handles bracket types: `()`, `[]`, `{}`, `<>`

### ValidateJsonResult TypedDict

```python
ValidateJsonResult(
    valid=bool,
    error=str | None,
    line=int | None,
    column=int | None,
    position=int | None,
    type=str | None,              # "null", "bool", "number", "string", "array", "object"
    top_level_keys=list[str] | None,
)
```

### ValidateTomlResult TypedDict

```python
ValidateTomlResult(
    valid=bool,
    error=str | None,
    line=int | None,
    column=int | None,
    position=int | None,
    type=str | None,
    top_level_keys=list[str] | None,
    tables=list[str] | None,
)
```

### RegexTestResult TypedDict

```python
RegexTestResult(
    valid_pattern=bool,
    results=list[RegexMatch],
    error=str | None,
)
```

### RegexMatch TypedDict

```python
RegexMatch(
    sample=str,
    matches=bool,
    fullmatch=bool,
    span=list[int] | None,
    groups=list[str],
    groupdict=dict[str, str],
)
```

### RegexFindIterResult TypedDict

```python
RegexFindIterResult(
    valid_pattern=bool,
    matches=list[RegexFindIterMatch],
    error=str | None,
)
```

### RegexFindIterMatch TypedDict

```python
RegexFindIterMatch(
    index=int,
    char_start=int,
    char_end=int,
    matched_text=str,
    groups=list[str],
    named_groups=dict[str, str],
)
```

### RegexSafetyResult TypedDict

```python
RegexSafetyResult(
    is_safe=bool,
    warnings=list[RegexSafetyFinding],
    pattern_category=str,            # "simple", "moderate", "complex", "potentially_unsafe"
    has_backreferences=bool,
    has_capture_counts=bool,
)
```

### JsonExtractResult TypedDict

```python
JsonExtractResult(
    found=bool,
    value=Any,
    value_type=str,
    preview=str,
    path=str,
)
```

### JsonCompareResult TypedDict

```python
JsonCompareResult(
    valid_json_a=bool,
    valid_json_b=bool,
    equal=bool,
    same_type=bool,
    diff_count=int,
    diffs=list[JsonCompareDiff],
    truncated=bool,
    summary=str,
)
```

### JsonShapeResult TypedDict

```python
JsonShapeResult(
    parse_ok=bool,
    type=str,
    top_level_keys=list[str],
    array_length=int | None,
    string_length=int | None,
    nesting_depth=int,
    error=str | None,
)
```

### VersionCompareResult TypedDict

```python
VersionCompareResult(
    equal=bool,
    comparison=int,  # -1, 0, or 1
    loose=bool,
)
```

---

## synthesis.py — Higher-Level Analysis

Combines primitives into higher-level tools.

### Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `measure_text(s)` | MeasureTextResult | Comprehensive text metrics |
| `text_equal(a, b, ...)` | TextEqualResult | String equality modes |
| `inspect_text(s, ...)` | InspectTextResult | Hidden char inspection |
| `explain_diff(a, b, ...)` | ExplainDiffResult | Detailed diff explanation |
| `count_chars(s, ...)` | CountCharsResult | Character counting |
| `list_compare(a, b, ...)` | ListCompareResult | Compare two lists (ordered/set/multiset/near-match) |
| `text_replace_check(text, old, new, ...)` | TextReplaceCheckResult | Check replacement before applying |
| `line_range_extract(text, start, end, ...)` | LineRangeExtractResult | Extract exact line ranges |
| `line_range_compare(left, right, ...)` | LineRangeCompareResult | Compare line ranges from two texts |
| `text_window(text, position, ...)` | TextWindowResult | Get window around a position |

### MeasureTextResult TypedDict

```python
MeasureTextResult(
    bytes_utf8=int,
    codepoints=int,
    graphemes=int,
    words=int,
    unique_words_casefolded=int,
    lines=int,
    nonempty_lines=int,
    blank_lines=int,
    max_line_length_codepoints=int,
    chars_no_whitespace=int,
    ascii=int,
    non_ascii=int,
    letters=int,
    digits=int,
    punctuation=int,
    symbols=int,
    spaces=int,
    control_chars=int,
    combining_marks=int,
    invisible_chars=int,
    newline_style=str,
    ends_with_newline=bool,
    normalization=NormalizationState,
    unicode_risks=UnicodeRisks,
    warnings=list[str],
)
```

### TextEqualResult TypedDict

```python
TextEqualResult(
    equal=bool,
    mode=dict[str, Any],
    raw_equal=bool,
    nfc_equal=bool,
    nfd_equal=bool,
    nfkc_equal=bool,
    nfkd_equal=bool,
    casefold_equal=bool,
    byte_equal=bool,
    lengths=dict[str, int],
    first_difference=dict[str, Any] | None,
    classification=str,
)
```

### InspectTextResult TypedDict

```python
InspectTextResult(
    safe_repr=str,
    metrics=MeasureTextResult,
    normalization=dict[str, bool],
    normalization_diff=bool,
    normals_repr=str | None,
    invisibles=list[InvisibleCharInfo],
    bidi_controls=list[InvisibleCharInfo],
    mixed_scripts=MixedScriptsResult,
    confusables=list[ConfusableInfo],
    warnings=list[dict],
    limits_applied=list[str],
    normalize=str,
    compare_normalized=bool,
    original=dict[str, Any],
    normalized=InspectTextNormalized | None,
    normalization_findings=list[NormalizationFinding],
)
```

### ListCompareResult TypedDict

```python
ListCompareResult(
    equal=bool,
    mode=dict[str, Any],
    ordered=list_compare (when mode="ordered"),
    set_result=list_compare (when mode="set"),
    multiset_result=list_compare (when mode="multiset"),
    near_match=list_compare (when mode="near-match"),
    ...
)
```

### NormalizationState TypedDict

```python
NormalizationState(
    is_nfc=bool,
    is_nfd=bool,
    is_nfkc=bool,
    is_nfkd=bool,
)
```

### UnicodeRisks TypedDict

```python
UnicodeRisks(
    contains_invisibles=bool,
    contains_bidi_controls=bool,
    mixed_scripts=bool,
    scripts=list[str],
)
```

### TextReplaceCheckResult TypedDict

```python
TextReplaceCheckResult(
    match_count=int,
    unique_match=bool,
    expected_count_met=bool,
    would_change=bool,
    positions=list[dict],
    preview_before=str,
    preview_after=str,
    findings=list[dict],
)
```

### LineRangeExtractResult TypedDict

```python
LineRangeExtractResult(
    line_count_total=int,
    start_line=int,
    end_line=int,
    valid_range=bool,
    text=str,
    byte_start=int,
    byte_end=int,
    char_start=int,
    char_end=int,
    newline_style=str,
    ends_with_newline=bool,
    fingerprint=str,
)
```

### TextWindowResult TypedDict

```python
TextWindowResult(
    position=int,
    window_size=int,
    start=int,
    end=int,
    text=str,
    truncated=bool,
    line_start=int,
    line_end=int,
)
```

---

## transform.py — Text Transformations

Deterministic text transformations and normalization.

### Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `text_transform(text, operations)` | TextTransformResult | Apply ordered list of normalization operations |
| `escape_text(text, mode)` | EscapeTextResult | Escape text for target format |
| `unescape_text(text, mode)` | UnescapeTextResult | Unescape text from format |
| `text_hash(text, algorithms)` | TextHashResult | Compute cryptographic hashes |
| `text_fingerprint(text)` | TextFingerprintResult | Compute deterministic text fingerprint |

### Supported transform operations

`normalize_nfc`, `normalize_nfd`, `normalize_nfkc`, `normalize_nfkd`, `casefold`, `trim`, `trim_trailing_whitespace`, `normalize_newlines_lf`, `ensure_final_newline`, `strip_final_newline`, `remove_zero_width`, `remove_bidi_controls`, `visible_repr`

### Supported escape modes

`json`, `python`, `rust`, `posix_shell_single`, `regex_literal`, `markdown_inline_code`, `markdown_code_block`, `html_text`, `url_component`

### TextFingerprintResult TypedDict

```python
TextFingerprintResult(
    sha256=str,
    bytes_utf8=int,
    codepoints=int,
    graphemes=int,
    newline_style=str,
    normalization=dict[str, str | bool],
    summary=str,
)
```

---

## identifier.py — Identifier Analysis

Classification and validation of identifier names for Python, Rust, JavaScript, and environment variable naming conventions.

### Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `identifier_analyze(text)` | IdentifierAnalyzeResult | Classify and validate an identifier |

### IdentifierAnalyzeResult TypedDict

```python
IdentifierAnalyzeResult(
    text=str,
    classification=str,          # "snake_case", "camelCase", "PascalCase", "kebab-case", etc.
    python_valid=bool,
    python_keyword=bool,
    rust_valid=bool | None,
    javascript_valid=bool | None,
    env_valid=bool,
    suggestions=dict[str, str],
    warnings=list[str],
    summary=str,
)
```

---

## identifier_inspect.py — Identifier Inspection

Collision detection for multiple identifiers, including confusables, normalization issues, and casefold collisions.

### Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `identifier_inspect(identifiers, ...)` | IdentifierInspectResult | Inspect list of identifiers for collisions |
| `identifier_table_inspect(identifiers, ...)` | IdentifierTableInspectResult | Inspect identifier table with style/keyword checks |

### IdentifierInspectResult TypedDict

```python
IdentifierInspectResult(
    identifiers=list[IdentifierInfo],
    collisions=list[CollisionInfo],
)
```

### IdentifierTableInspectResult TypedDict

```python
IdentifierTableInspectResult(
    collisions=list[TableCollisionInfo],
    reserved_hits=list[ReservedKeywordHit],
    mixed_style_groups=list[MixedStyleGroup],
    findings=list[str],
)
```

### CollisionInfo TypedDict

```python
CollisionInfo(
    kind=str,    # "casefold", "confusable", "normalization"
    a=str,
    b=str,
)
```

---

## position.py — Text Position Conversion

Converts between byte offsets, codepoint indices, line/column positions, and UTF-16 offsets.

### Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `text_position(text, ...)` | TextPositionResult | Convert between position systems |

### TextPositionResult TypedDict

```python
TextPositionResult(
    valid=bool,
    byte_offset=int | None,
    codepoint_index=int | None,
    utf16_offset=int | None,
    line=int | None,
    column=int | None,
    line_base=int,
    column_base=int,
    char=str | None,
    codepoint=str | None,
    name=str | None,
    line_text_preview=str | None,
    error=str | None,
    summary=str,
)
```

---

## glob.py — Glob Pattern Matching

Deterministic glob pattern matching with POSIX and Windows path separators.

### Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `glob_match(pattern, path)` | GlobMatchResult | Match path against glob pattern |

### GlobMatchResult TypedDict

```python
GlobMatchResult(
    matches=bool,
    normalized_pattern=str,
    normalized_path=str,
    matched_segment=str | None,
    unmatched_segment=str | None,
    summary=str,
)
```

---

## config.py — Config File Validation

Line-by-line parsers for `.env` and INI files.

### Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `dotenv_validate(text, ...)` | DotenvValidateResult | Validate .env-style key/value text |
| `ini_validate(text)` | IniValidateResult | Validate INI-style config |

### DotenvValidateResult TypedDict

```python
DotenvValidateResult(
    parse_ok=bool,
    entries=list[DotenvEntry],
    duplicates=list[dict[str, object]],
    invalid_lines=list[dict[str, object]],
    requires_quoting=list[str],
    contains_expansion_syntax=list[str],
    findings=list[str],
)
```

### IniValidateResult TypedDict

```python
IniValidateResult(
    parse_ok=bool,
    sections=list[str],
    keys_by_section=dict[str, list[str]],
    duplicates=list[dict[str, object]],
    invalid_lines=list[dict[str, object]],
    findings=list[str],
)
```

**Note:** Both result types include a `findings` list. `requires_quoting` is a list of keys that need quoting, not a boolean.

---

## patch.py — Unified Diff Parsing

### Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `patch_apply_check(original_text, patch_text)` | PatchApplyCheckResult | Validate and simulate a patch |
| `patch_summary(patch_text)` | PatchSummaryResult | Summarize a patch without applying |

### PatchApplyCheckResult TypedDict

```python
PatchApplyCheckResult(
    patch_parse_ok=bool,
    applies=bool,
    hunks_total=int,
    hunks_applied=int,
    hunks_failed=int,
    failed_hunks=list[FailedHunk],
    affected_line_ranges=list[dict[str, int]],
    newline_style_before=str,
    newline_style_after=str,
    result_fingerprint=str,
    result_text=str | None,
    findings=list[str],
)
```

### PatchSummaryResult TypedDict

```python
PatchSummaryResult(
    files_changed=int,
    hunks_total=int,
    additions=int,
    deletions=int,
    renames_detected=list[dict[str, str]],
    binary_patch_detected=bool,
    line_ranges_by_file=dict[str, list[dict[str, int]]],
    findings=list[str],
)
```

---

## inspect_prompt.py — Prompt Injection Detection

Scans text for hidden prompt content. Reports observable features only; does not infer intent.

### Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `prompt_input_inspect(text, checks)` | PromptInspectionResult | Scan for hidden prompt content |

### PromptInspectionResult TypedDict

```python
PromptInspectionResult(
    findings=list[PromptInspectionFinding],
    summary=str,
    risk_score=int,
    recommended_next_tool=str | list[str] | None,
    text_length=int,
    checks_run=list[str],
    findings_truncated=bool,
)
```

### Checks performed

- `unicode_hidden` — Zero-width, variation selectors, combining marks
- `bidi` — Bidirectional control characters
- `html_comments` — HTML comments (may hide instructions)
- `markdown_links` — Link text/target mismatches
- `ansi_escapes` — ANSI escape sequences
- `terminal_controls` — Terminal control sequences
- `base64_like_blobs` — Base64-encoded content
- `instruction_phrases` — Prompt injection phrases
- `long_minified_lines` — Very long single lines

---

## markdown.py — Markdown Structure Analysis

Regex-based line scanners (NOT full CommonMark parsers).

### Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `markdown_structure(text)` | MarkdownStructureResult | Parse markdown structure |
| `code_fence_extract(text, language)` | CodeFenceExtractResult | Extract fenced code blocks |
| `markdown_link_check_lexical(text, known_paths)` | MarkdownLinkCheckResult | Lexical link validation |

### MarkdownStructureResult TypedDict

```python
MarkdownStructureResult(
    headings=list[MarkdownHeading],
    code_fences=list[MarkdownCodeFence],
    links=list[MarkdownLink],
    html_comments=list[dict],
    frontmatter=MarkdownFrontmatter,
    tables_detected=bool,
    findings=list[str],
)
```

### MarkdownLinkCheckResult TypedDict

```python
MarkdownLinkCheckResult(
    total_links=int,
    malformed=list[MalformedLink],
    duplicate_anchors=list[DuplicateAnchor],
    unresolved_relatives=list[UnresolvedRelative],
    external_count=int,
    image_count=int,
)
```

---

## shell.py — Shell Command Parsing

POSIX-like lexical tokenization using Python's `shlex` module. NOT full shell evaluation.

### Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `shell_split(command)` | ShellSplitResult | Parse shell command into argv |
| `shell_quote_join(argv)` | ShellQuoteJoinResult | Safely quote argv into shell string |
| `argv_compare(left, right)` | ArgvCompareResult | Compare two command strings |

### ShellSplitResult TypedDict

```python
ShellSplitResult(
    parse_ok=bool,
    argv=list[str],
    argc=int,
    features=ShellFeatures,
    findings=list[str],
)
```

### ShellFeatures TypedDict

```python
ShellFeatures(
    has_pipe=bool,
    has_redirection=bool,
    has_command_substitution=bool,
    has_variable_expansion=bool,
    has_glob_pattern=bool,
    has_control_operator=bool,
    has_unbalanced_quotes=bool,
)
```

---

## unicode_policy.py — Unicode Safety Policies

Deterministic named policies for validating text against Unicode safety heuristics.

### Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `unicode_policy_check(text, policy)` | UnicodePolicyCheckResult | Apply named Unicode safety policy |
| `canonicalize_text(text, profile)` | CanonicalizeResultWithMapping | Apply canonicalization profile |

### Supported policies

- `identifier_strict` — Mixed scripts, bidi, zero-width, confusables
- `filename_safe` — Control chars, path separators, bidi, zero-width, Windows reserved
- `source_code` — Strict for code identifiers
- `human_text` — Less strict, primarily warnings
- `json_key` — JSON key safety checks
- `domain_like` — Domain/hostname-like text checks

### UnicodePolicyCheckResult TypedDict

```python
UnicodePolicyCheckResult(
    pass_=bool,
    policy=str,
    normalized_form=str,
    findings=list[PolicyFinding],
    summary=str,
)
```

---

## cargo.py — Cargo.toml Inspection

### Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `cargo_toml_inspect(text)` | CargoInspectResult | Analyze Cargo.toml structure |

### Notes

- `cargo_toml_inspect()` IS re-exported from `__init__.py`.
- `CargoInspectResult.findings` is `list[_Finding]` (structured, not `list[str]`). Uses the shared `_Finding` TypedDict from `manifests.py`.
- Virtual workspace handling: no `[package]` is intentional when `[workspace]` is present.
- Finding codes are stable identifiers: `CARGO_PARSE_ERROR`, `CARGO_MISSING_PACKAGE_NAME`, etc.
- Both `cargo.py` and `manifests.py` use the shared `_Finding` TypedDict for structured findings.
- Inspection is lexical/structural, not dependency resolution. Package-manager signals are heuristic.

### CargoInspectResult TypedDict

```python
CargoInspectResult(
    parse_ok=bool,
    package=CargoPackageInfo,
    workspace=CargoWorkspaceInfo,
    dependencies=CargoDepSection,
    path_dependencies=list[str],
    suspicious_dependency_names=list[str],
    duplicate_or_confusable_dependency_names=list[str],
    findings=list[_Finding],
)
```

---

## version.py — Semver/Version Constraint Checking

### Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `parse_version(version)` | ParsedVersion \| None | Parse strict semver version string |
| `check_version_constraint(version, constraint, scheme)` | VersionConstraintResult | Check if version satisfies constraint |

### Supported schemes

- **semver**: strict major.minor.patch with full pre-release ordering. Supports operators: `==`, `!=`, `>=`, `<=`, `>`, `<`, `=`, comma-separated ranges.
- **cargo**: semver with Rust/Cargo-style range operators: `^` (caret), `~` (tilde), `*` (wildcard). Full pre-release support.
- **pep440, loose**: not supported by constraint checking (use `version_compare` from validate.py for loose comparison).

### VersionConstraintResult TypedDict

```python
VersionConstraintResult(
    satisfies=bool,
    parsed_version=ParsedVersion | None,
    parsed_constraint=ParsedConstraint | None,
    scheme=str,
    explanation=str,
    findings=list[str],
)
```

---

## llm_hygiene.py — LLM JSON Output Hygiene

Detects common JSON output issues in LLM-generated text.

### Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `llm_json_output_check(text)` | LlmJsonCheckResult | Analyze LLM text for JSON issues |

### Detected issues

- Markdown fenced code blocks wrapping JSON
- Leading/trailing prose around JSON content
- JSON parse errors with location info
- Common JSON issues (trailing commas, single quotes, unquoted keys, comments)
- Multiple concatenated JSON objects
- BOM prefix

### LlmJsonCheckResult TypedDict

```python
LlmJsonCheckResult(
    has_fence=bool,
    fence_language=str,
    leading_prose=bool,
    trailing_prose=bool,
    parse_ok=bool,
    error_line=int | None,
    error_col=int | None,
    error_message=str | None,
    fix_hints=list[JsonFixHint],
    extracted_content=str | None,
    multiple_json_objects=bool,
    has_bom=bool,
    original_length=int,
    extracted_length=int,
)
```

---

## repo_audit.py — Repository Inventory

Deterministic analysis of file inventories for repo structure signals.

### Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `repo_file_inventory(paths)` | RepoInventoryResult | Analyze file path inventory |

### RepoInventoryResult TypedDict

```python
RepoInventoryResult(
    total_files=int,
    by_extension=dict[str, int],
    by_category=dict[str, int],
    language_signals=list[str],
    config_files_found=list[str],
    hidden_files=int,
    generated_candidates=list[str],
    vendor_candidates=list[str],
    suspicious_paths=list[str],
    largest_files=list[dict[str, Any]],
    duplicate_hashes=list[list[str]],
    total_size=int | None,
    truncation_warning=bool,
)
```

---

## manifests.py — Manifest Inspection

Lexical/structural inspection of project manifests without network or filesystem access.

**Note:** This module is NOT re-exported from `__init__.py`. Functions must be imported directly: `from eggcalc.exact.manifests import ...`

### Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `pyproject_inspect(text)` | PyprojectInspectResult | Inspect pyproject.toml content |
| `package_json_inspect(text)` | PackageJsonInspectResult | Inspect package.json content |
| `requirements_inspect(text)` | RequirementsInspectResult | Inspect requirements.txt content |
| `go_mod_inspect(text)` | GoModInspectResult | Inspect go.mod content |
| `lockfile_summary(text, kind)` | LockfileSummaryResult | Summarize a lockfile |

### TypedDicts

```python
class _Finding(TypedDict, total=False):
    code: str           # Stable identifier (e.g. TOML_PARSE_ERROR, INPUT_TOO_LONG)
    severity: str       # "error", "warning", or "info"
    message: str
    line: int
    column: int

class PyprojectInspectResult(TypedDict, total=False):
    parse_ok: bool
    project_name: str | None
    project_version: str | None
    build_backend: str | None        # From build-system.build-backend
    build_requirements: list[str]    # From build-system.requires
    build_backend_path: list[str] | None
    requires_python: str | None
    dependencies_count: int
    optional_dependency_groups: dict[str, int]
    scripts: dict[str, str]
    tool_sections: list[str]         # From nested data["tool"] dict
    package_manager_signals: list[str]
    dynamic: list[str] | None
    entry_points: dict[str, str] | None
    gui_scripts: dict[str, str] | None
    urls: dict[str, str] | None
    findings: list[_Finding]

class RequirementsInspectResult(TypedDict, total=False):
    parse_ok: bool
    total_lines: int
    package_specs: list[str]
    editable_refs: list[str]
    direct_urls: list[str]
    vcs_refs: list[str]
    comments: list[str]
    requirement_includes: list[str]   # -r/--requirement lines
    constraints_includes: list[str]   # -c/--constraint lines only
    index_options: list[str]          # --index-url, --find-links, --trusted-host
    hash_options: list[str]           # --hash=... lines
    environment_markers: list[str]
    suspicious_lines: list[str]
    findings: list[_Finding]
```

---

## Architecture Notes

```
┌─────────────────────────────────────────────────────────────┐
│                        synthesis.py                         │
│         (High-level tools combining primitives)            │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────┐ ┌────────────┐ ┌──────┐ ┌──────────┐       │
│  │diff.py   │ │measure.py  │ │validate│ │unicode_ │       │
│  │          │ │            │ │      │ │tools.py │       │
│  └────┬─────┘ └──────┬─────┘ └───┬──┘ └────┬─────┘       │
│       │               │           │          │              │
├───────┴───────────────┴───────────┴──────────┴────────────┤
│                      primitives.py                         │
│       (UTF-8, codepoints, normalization, invisibles)       │
└─────────────────────────────────────────────────────────────┘
```

### Key Conventions

1. **`utf8_bytes()` returns `bytes`** — Not an int count, returns actual UTF-8 encoded bytes
2. **`visible_repr()` display order matters** — Variation selector checks must come BEFORE combining mark checks
3. **`_get_script_heuristic()` benefits from caching** — Has `@functools.lru_cache` decorator
4. **Cf (format) characters excluded from `control_chars`** — Format characters are silently ignored per UTS #55
5. **`confusables_count()` helper** — Fast function to count confusables without building full list
6. **`CodepointInfo` uses `idx` field** — Not `index`. This is a NamedTuple, not a TypedDict.

### TypedDict vs NamedTuple

Architecture docs may show `@dataclass class Xxx(NamedTuple)` but code uses `class Xxx(TypedDict)` for consistency with Python 3.14+ typing patterns. `CodepointInfo` is the one exception — it is a NamedTuple.

### Input limits

| Module | Constant | Value |
|--------|----------|-------|
| `config.py` | `MAX_INPUT_LENGTH` | 100,000 |
| `validate.py` | `MAX_INPUT_LENGTH` | 100,000 |
| `validate.py` | `MAX_LIST_ITEMS` | 10,000 |
| `validate.py` | `MAX_PATTERN_LENGTH` | 1,000 |
| `validate.py` | `MAX_SAMPLE_LENGTH` | 10,000 |
| `validate.py` | `MAX_SCHEMA_DEPTH` | 50 |
| `validate.py` | `MAX_SCHEMA_ELEMENTS` | 100,000 |
| `patch.py` | `MAX_PATCH_LENGTH` | 200,000 |
| `patch.py` | `MAX_ORIGINAL_LENGTH` | 200,000 |
| `cargo.py` | `_MAX_INPUT_LENGTH` | 200,000 |
| `manifests.py` | `_MAX_INPUT_LENGTH` | 500,000 |
| `inspect_prompt.py` | `MAX_TEXT_LENGTH` | 100,000 |
| `inspect_prompt.py` | `MAX_FINDINGS` | 1,000 |
| `llm_hygiene.py` | `_MAX_INPUT_LENGTH` | 500,000 |
| `repo_audit.py` | `_MAX_PATHS` | 50,000 |
| `synthesis.py` | `MAX_TEXT_LENGTH` | 100,000 |
| `synthesis.py` | `MAX_DIFF_SPANS` | 50 |
| `shell.py` | `MAX_INPUT_LENGTH` | 100,000 |
| `shell.py` | `MAX_LIST_ITEMS` | 10,000 |
| `unicode_policy.py` | `MAX_TEXT_LENGTH` | 100,000 |
| `diff.py` | `MAX_LEVENSHTEIN_LEN` | 10,000 |

---

## Testing

All exact/ modules have deterministic behavior:
- No random operations
- No external dependencies (network, filesystem)
- No LLM calls
- Repeatable results for same input

See `tests/test_exact.py` for comprehensive tests.
