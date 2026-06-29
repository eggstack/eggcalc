# exact/ — Unicode Text Primitives

Low-level deterministic Unicode text analysis tools. These modules are **independent** and **testable** without semantic interpretation or LLM calls.

## Module Structure

```
exact/
├── __init__.py            # Public API re-exports
├── primitives.py          # UTF-8, codepoints, normalization, invisibles
├── unicode_tools.py       # Script detection, confusables
├── confusables.py         # Homoglyph identification (auto-generated data)
├── measure.py             # Text metrics (words, lines, categories)
├── diff.py                # String diffing algorithms
├── validate.py            # JSON/bracket/regex/TOML validation, version comparison
├── synthesis.py           # Higher-level text analysis
├── glob.py                # Glob pattern matching
├── transform.py           # Text escaping, hashing, fingerprinting
├── identifier.py          # Identifier analysis
├── identifier_inspect.py  # Identifier inspection and collision detection
├── path_tools.py          # Path analysis and normalization
├── position.py            # Text position operations
├── config.py              # .env and INI validation
├── patch.py               # Unified diff parsing and application
├── inspect_prompt.py      # Hidden char/ANSI/instruction detection
├── markdown.py            # Markdown structure analysis
├── shell.py               # Shell command parsing and argv comparison
├── unicode_policy.py      # Named Unicode safety policies
├── cargo.py               # Cargo.toml inspection
└── version.py             # Semver/PEP440 parsing and comparison
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

    # Validate
    check_brackets, validate_json, validate_toml_text, toml_shape,
    validate_schema_light, regex_test, regex_finditer, regex_safety_check,
    regex_replace_preview, json_extract, json_compare, json_shape,
    json_canonicalize, json_query, version_compare, list_dedupe, list_sort,

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
    markdown_structure, code_fence_extract,

    # Shell
    shell_split, shell_quote_join, argv_compare,

    # Unicode Policy
    unicode_policy_check, canonicalize_text,

    # Cargo
    cargo_toml_inspect,

    # Version
    parse_version, check_version_constraint,
)
```

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
| `normalized_equal(a, b)` | bool | Equality after NFC normalization |
| `measure_basic(s)` | MeasureBasic | Basic text metrics |
| `count_graphemes(s)` | int | Grapheme cluster count |
| `truncate_to_grapheme(s, max_graphemes)` | str | Truncate to grapheme boundary |
| `find_invisibles(s)` | list[InvisibleCharInfo] | Detect hidden characters |
| `visible_repr(s)` | str | Display-safe representation |

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
    ...
}
```

### CodepointInfo NamedTuple

```python
CodepointInfo(
    index=int,      # Position in string
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

---

## unicode_tools.py — Script and Confusable Detection

### Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `unicode_script(char)` | str | Script of a character |
| `unicode_scripts(s)` | list[str] | Scripts for all characters |
| `detect_mixed_scripts(s)` | list[ScriptInfo] | Find mixed-script runs |
| `detect_confusables(s)` | list[ConfusableInfo] | Find confusable homoglyphs |
| `confusables_count(s)` | int | Fast confusable count |
| `reverse_confusables(char)` | list[str] | Find chars that confusable-map TO this char |

### Script Detection

Scripts include: Latin, Greek, Cyrillic, Arabic, Hebrew, Han (Chinese), Japanese (Hiragana/Katakana), Korean (Hangul), Thai, etc.

### Confusable Detection

Identifies characters that appear identical but have different Unicode code points:

```python
# Latin 'a' vs Cyrillic 'а'
detect_confusables("access")  # Returns confusables in Latin 'a' → Cyrillic 'а'
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

## measure.py — Text Metrics

### Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `char_category_metrics(s)` | CharCategoryMetrics | Metrics by Unicode category |
| `line_metrics(s)` | LineMetrics | Line count and newline style |
| `word_metrics(s)` | WordMetrics | Word count and boundaries |

Note: `measure_basic()` is defined in `primitives.py`, not `measure.py`.

### CharCategoryMetrics

Groups characters by Unicode category:

| Category | Description | Example |
|----------|-------------|---------|
| Lu | Letter, uppercase | A-Z (Latin) |
| Ll | Letter, lowercase | a-z (Latin) |
| Nd | Number, decimal digit | 0-9 |
| Po | Punctuation, other | . , ! ? |
|Zs | Separator, space | Space, NBSP |
| ... | | |

### LineMetrics

```python
LineMetrics(
    lines=int,                      # Total number of lines
    nonempty_lines=int,             # Lines with content
    blank_lines=int,                # Empty lines
    max_line_length_codepoints=int, # Longest line length
    trailing_whitespace_lines=list[int],  # Indices of lines with trailing whitespace
    newline_style=str,              # "LF", "CRLF", "CR", "mixed", "none"
    ends_with_newline=bool          # Whether string ends with newline
)
```

---

## diff.py — String Comparison Algorithms

### Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `first_diff(a, b)` | FirstDiff | Position of first difference |
| `common_prefix_suffix(a, b)` | CommonPrefixSuffix | Longest common prefix/suffix lengths |
| `levenshtein_distance(a, b)` | int | Edit distance |
| `diff_spans(a, b)` | list[DiffSpan] | Spans that differ |
| `longest_common_subsequence(a, b)` | str | LCS via dynamic programming |

### DiffSpan

```python
DiffSpan(
    kind=str,            # "equal", "insert", "delete", "replace"
    a_span=list[int],    # [start, end) in string a
    b_span=list[int],    # [start, end) in string b
    a_text=str,
    b_text=str,
)
```

### FirstDiff

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

### CommonPrefixSuffix

```python
CommonPrefixSuffix(
    common_prefix_len=int,   # Length of common prefix
    common_suffix_len=int,   # Length of common suffix (non-overlapping)
)
```

### Examples

```python
first_diff("hello", "hallo")
# → FirstDiff(a_index=1, b_index=1, a_char='e', b_char='a', ...)

common_prefix_suffix("abc123", "abc456")
# → CommonPrefixSuffix(common_prefix_len=3, common_suffix_len=0)
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
| `validate_schema_light(s)` | ValidateSchemaLightResult | JSON schema lightweight validation |
| `regex_test(pattern, samples)` | RegexTestResult | Test regex against samples |
| `regex_finditer(pattern, text)` | RegexFindIterResult | Find all regex matches with positions |
| `regex_safety_check(pattern)` | RegexSafetyResult | Check regex for catastrophic backtracking |
| `regex_replace_preview(pattern, replacement, text)` | RegexReplaceResult | Preview regex replacement |
| `json_extract(json_str, path)` | JsonExtractResult | Extract data from JSON using path |
| `json_compare(a, b)` | JsonCompareResult | Compare two JSON documents |
| `json_shape(s)` | JsonShapeResult | Analyze JSON structure |
| `json_canonicalize(s)` | JsonCanonicalizeResult | Canonicalize JSON with duplicate key detection |
| `json_query(json_str, pointer)` | JsonQueryResult | RFC 6901 JSON Pointer query |
| `version_compare(v1, v2)` | VersionCompareResult | Compare version strings |
| `list_dedupe(lst)` | list | Remove duplicate items preserving order |
| `list_sort(lst, normalization, casefold, reverse, stable)` | list | Sort list with normalization; `stable` is accepted for compatibility because Python sorting is always stable |

### CheckBracketsResult

```python
CheckBracketsResult(
    balanced=bool,
    unmatched_openers=list[BracketError],  # Opening brackets without matching close
    unmatched_closers=list[BracketError]    # Closing brackets without matching open
)
```

Where `BracketError` contains: `char` (the bracket character), `position` (index in string).

Handles bracket types: `()`, `[]`, `{}`, `<>`

### RegexTestResult

```python
RegexTestResult(
    valid_pattern=bool,      # Whether regex pattern is valid
    results=list[RegexMatch],  # List of per-sample match results
    error=str | None         # Error message if pattern invalid
)
```

### RegexMatch

```python
RegexMatch(
    sample=str,              # The input sample string
    matches=bool,            # Whether pattern matched (anywhere)
    fullmatch=bool,          # Whether entire string matched
    span=list[int] | None,   # (start, end) of match if any
    groups=list[str],        # Captured groups
    groupdict=dict[str, str] # Named groups dict
)
```

### RegexFindIterResult

```python
RegexFindIterResult(
    valid_pattern=bool,
    matches=list[RegexFindIterMatch],  # index, char_start, char_end, matched_text, groups, named_groups
    error=str | None,
)
```

### RegexSafetyResult

```python
RegexSafetyResult(
    is_safe=bool,
    warnings=list[RegexSafetyFinding],  # code, message, position
    pattern_category=str,  # "simple", "moderate", "complex", "potentially_unsafe"
    has_backreferences=bool,
    has_capture_counts=bool,
)
```

### JsonExtractResult

```python
JsonExtractResult(
    found=bool,
    value=Any,           # The extracted value (unbounded - caution with large JSON)
    value_type=str,      # "null", "bool", "number", "string", "array", "object"
    preview=str,         # Truncated preview (max_output_chars limit)
    path=str,            # The JSON pointer path used
)
```

### JsonShapeResult

```python
JsonShapeResult(
    parse_ok=bool,
    type=str,           # "null", "bool", "number", "string", "array", "object"
    top_level_keys=list[str],  # Only populated for objects
    array_length=int | None,
    string_length=int | None,
    nesting_depth=int,
    error=str | None,
)
```

### VersionCompareResult

```python
VersionCompareResult(
    equal=bool,
    comparison=int,  # -1, 0, or 1
    loose=bool,     # Whether version strings were parsed in loose mode
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
| `list_compare(a, b, ...)` | ListCompareResult | Compare two lists (ordered/set/multiset) |
| `text_replace_check(text, old, new, ...)` | TextReplaceResult | Check replacement before applying |
| `line_range_extract(text, start, end, ...)` | LineRangeResult | Extract exact line ranges |
| `line_range_compare(left, right, ...)` | LineRangeCompareResult | Compare line ranges from two texts |
| `text_window(text, position, ...)` | TextWindowResult | Get window around a position |

### MeasureTextResult

Combines: basic metrics + category metrics + line metrics + word metrics + invisible detection + mixed script detection

```python
MeasureTextResult(
    basic=MeasureBasic,
    categories=CharCategoryMetrics,
    lines=LineMetrics,
    words=WordMetrics,
    invisibles=list[InvisibleCharInfo],
    mixed_scripts=list[ScriptInfo],
    ...
)
```

### TextEqualResult

```python
TextEqualResult(
    raw_equal=bool,
    nfc_equal=bool,
    nfd_equal=bool,
    nfkc_equal=bool,
    nfkd_equal=bool,
    casefold_equal=bool,
    trim_equal=bool,
    ...
)
```

### InspectTextResult

```python
InspectTextResult(
    codepoints=list[CodepointInfo],
    invisibles=list[InvisibleCharInfo],
    confusables=list[ConfusableInfo],
    mixed_scripts=list[ScriptInfo],
    visible_repr=str,
    normalization=str,  # Current normalization form
    ...
)
```

### ListCompareResult

```python
ListCompareResult(
    equal=bool,
    ordered=bool,
    left_only=list[str],
    right_only=list[str],
    common=list[str],
    first_difference=dict,  # index, left, right
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

### TextReplaceResult TypedDict

```python
TextReplaceResult(
    match_count=int,
    unique_match=bool,
    expected_count_met=bool,
    would_change=bool,
    positions=list[dict],  # byte_start, char_start, line, column
    preview_before=str,
    preview_after=str,
    findings=list[dict],
)
```

### LineRangeResult TypedDict

```python
LineRangeResult(
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

---

## confusables.py — Homoglyph Data

**Auto-generated data file** (~180KB, ~6500 lines).

Contains mapping of confusable character pairs:
- Latin/Cyrillic confusables
- Latin/Greek confusables
- Latin/Arabic confusables
- etc.

Data format:
```python
CONFUSABLES: dict[str, list[str]] = {
    "A": ["А", "Α", "А", "𝒜"],  # Latin A vs Cyrillic А, Greek Α, etc.
    "a": ["а", "ɑ", "α", "а"],
    ...
}
```

---

## config.py — Config File Validation

### Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `dotenv_validate(text)` | DotenvValidateResult | Validate .env-style key/value text |
| `ini_validate(text)` | IniValidateResult | Validate INI-style config |

### DotenvValidateResult

```python
DotenvValidateResult(
    parse_ok=bool,
    entries=list[DotenvEntry],  # key, value_present, quote_style, line
    duplicates=list[dict],     # key, lines
    invalid_lines=list[dict],   # line, error
    requires_quoting=bool,
    contains_expansion_syntax=bool,
)
```

### IniValidateResult

```python
IniValidateResult(
    parse_ok=bool,
    sections=list[str],
    keys_by_section=dict[str, list[str]],
    duplicates=list[dict],     # section, key, lines
    invalid_lines=list[dict],   # line, error
)
```

---

## patch.py — Unified Diff Parsing

### Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `patch_apply_check(original_text, patch_text)` | PatchApplyResult | Validate and simulate a patch |
| `patch_summary(patch_text)` | PatchSummaryResult | Summarize a patch without applying |

### PatchApplyResult

```python
PatchApplyResult(
    patch_parse_ok=bool,
    applies=bool,
    hunks_total=int,
    hunks_applied=int,
    hunks_failed=int,
    failed_hunks=list[dict],
    affected_line_ranges=list[dict],
    result_fingerprint=str,
)
```

### PatchSummaryResult

```python
PatchSummaryResult(
    files_changed=int,
    hunks_total=int,
    additions=int,
    deletions=int,
    binary_patch_detected=bool,
)
```

---

## inspect_prompt.py — Prompt Injection Detection

### Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `prompt_input_inspect(text, checks)` | PromptInspectResult | Scan for hidden prompt content |

### PromptInspectResult

```python
PromptInspectResult(
    findings=list[PromptFinding],
    summary=str,
    risk_level=str,  # "none", "low", "medium", "high"
)
```

Detects: unicode hidden chars, bidi controls, HTML comments, markdown link mismatch, ANSI escapes, base64 blobs, instruction phrases.

---

## markdown.py — Markdown Structure Analysis

### Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `markdown_structure(text)` | MarkdownStructureResult | Parse markdown structure |
| `code_fence_extract(text, language)` | CodeFenceResult | Extract fenced code blocks |

### MarkdownStructureResult

```python
MarkdownStructureResult(
    headings=list[dict],     # level, text, line, slug
    code_fences=list[dict], # language, start_line, end_line, closed
    links=list[dict],        # visible_text, target, line, mismatch_flags
    html_comments=list[int], # line numbers
    frontmatter=dict,        # present, format, line_range
    tables_detected=int,
)
```

---

## shell.py — Shell Command Parsing

### Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `shell_split(command)` | ShellSplitResult | Parse shell command into argv |
| `shell_quote_join(argv)` | ShellQuoteResult | Safely quote argv into shell string |
| `argv_compare(left, right)` | ArgvCompareResult | Compare two command strings |

### ShellSplitResult

```python
ShellSplitResult(
    parse_ok=bool,
    argv=list[str],
    argc=int,
    features=dict,  # has_pipe, has_redirection, etc.
)
```

---

## unicode_policy.py — Unicode Safety Policies

### Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `unicode_policy_check(text, policy)` | UnicodePolicyResult | Apply named Unicode safety policy |
| `canonicalize_text(text, profile)` | CanonicalizeResult | Apply canonicalization profile |

### Policies

- `identifier_strict` — Warn on mixed scripts, bidi, zero-width, confusables
- `filename_safe` — Control chars, path separators, bidi, zero-width
- `source_code` — Strict for code identifiers
- `human_text` — Less strict, primarily warnings

---

## cargo.py — Cargo.toml Inspection

### Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `cargo_toml_inspect(text)` | CargoInspectResult | Analyze Cargo.toml structure |

### CargoInspectResult

```python
CargoInspectResult(
    parse_ok=bool,
    package=dict,       # name, version, edition, license, repository
    workspace=dict,     # present, members, exclude
    dependencies=dict,  # by section
    path_dependencies=list[str],
    suspicious_dependency_names=list[str],
)
```

---

## version.py — Semver/Version Comparison

### Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `parse_version(version)` | VersionInfo | Parse a version string |
| `check_version_constraint(version, constraint, scheme)` | VersionConstraintResult | Check if version satisfies constraint |

### VersionConstraintResult

```python
VersionConstraintResult(
    satisfies=bool,
    parsed_version=VersionInfo,
    parsed_constraint=dict,
    scheme=str,
    explanation=str,
)
```

---

## Architecture Notes

```
┌─────────────────────────────────────────────────────────────┐
│                        synthesis.py                         │
│         (High-level tools combining primitives)            │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────┐ ┌────────────┐ ┌──────┐ ┌──────────┐     │
│  │diff.py   │ │measure.py   │ │validate│ │unicode_ │     │
│  │          │ │            │ │      │ │tools.py │     │
│  └────┬─────┘ └──────┬─────┘ └───┬──┘ └────┬─────┘     │
│       │               │           │          │            │
├───────┴───────────────┴───────────┴──────────┴────────────┤
│                      primitives.py                           │
│         (UTF-8, codepoints, normalization, invisibles)      │
└─────────────────────────────────────────────────────────────┘
```

### Key Conventions

1. **`utf8_bytes()` returns `bytes`** — Not an int count, returns actual UTF-8 encoded bytes
2. **`visible_repr()` display order matters** — Variation selector checks must come BEFORE combining mark checks
3. **`_get_script_heuristic()` benefits from caching** — Now has `@functools.lru_cache` decorator
4. **Cf (format) characters excluded from `control_chars`** — Format characters are silently ignored per UTS #55
5. **`confusables_count()` helper** — Fast function to count confusables without building full list

### TypedDict vs NamedTuple

Architecture docs may show `@dataclass class Xxx(NamedTuple)` but code uses `class Xxx(TypedDict)` for consistency with Python 3.14+ typing patterns.

---

## Testing

All exact/ modules have deterministic behavior:
- No random operations
- No external dependencies (network, filesystem)
- No LLM calls
- Repeatable results for same input

See `tests/test_exact.py` for comprehensive tests.
