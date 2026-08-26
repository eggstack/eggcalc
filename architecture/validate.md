# validate.py - Validation Utilities

## Table of Contents

- [Purpose](#purpose)
- [Constants](#constants)
- [TypedDicts](#typeddicts)
- [Core Functions](#core-functions)
- [Input Limits](#input-limits)
- [Error Handling](#error-handling)

## Purpose

Provides validation utilities for checking brackets, JSON/TOML syntax, regex patterns, schema validation, version comparison, JSON comparison/extraction/canonicalization, and list operations.

## Constants

```python
MAX_TEXT_INPUT_LENGTH = 100_000        # Maximum input length for most functions
MAX_LIST_ITEMS = 10_000           # Maximum list items for list_dedupe/list_sort
MAX_PATTERN_LENGTH = 1000         # Maximum regex pattern length
MAX_PATTERN_NESTING = 5           # Maximum regex nesting depth
MAX_SAMPLE_LENGTH = 10_000        # Maximum sample string length for regex_test
MAX_SCHEMA_DEPTH = 50             # Maximum nesting depth for schema validation
MAX_SCHEMA_ELEMENTS = 100_000     # Maximum elements walked during schema validation
MAX_SCHEMA_VIOLATIONS = 100       # Maximum violations returned by validate_schema_light
MAX_TEXT_LENGTH_REGEX = 100_000   # Maximum text length for regex_finditer
MAX_PATTERN_LENGTH_REGEX = 1000   # Maximum pattern length for regex_finditer
MAX_MATCHES = 100                 # Maximum matches returned by regex_finditer
MAX_GROUPS = 100                  # Maximum groups captured by regex_finditer

DEFAULT_BRACKET_PAIRS: dict[str, str] = {
    "(": ")",
    "[": "]",
    "{": "}",
    "<": ">",
}
```

## TypedDicts

### BracketError
```python
class BracketError(TypedDict):
    """Information about an unmatched bracket."""
    char: str
    index: int
    line: int
    column: int
```

### CheckBracketsResult
```python
class CheckBracketsResult(TypedDict):
    """Result of bracket checking."""
    balanced: bool
    unmatched_openers: list[BracketError]
    unmatched_closers: list[BracketError]
```

### ValidateJsonResult
```python
class ValidateJsonResult(TypedDict):
    """Result of JSON validation."""
    valid: bool
    error: str | None
    line: int | None
    column: int | None
    position: int | None
    type: str | None
    top_level_keys: list[str] | None
```

### ValidateTomlResult
```python
class ValidateTomlResult(TypedDict):
    """Result of TOML validation."""
    valid: bool
    error: str | None
    line: int | None
    column: int | None
    position: int | None
    type: str | None
    top_level_keys: list[str] | None
    tables: list[str] | None
```

### TomlShapeResult
```python
class TomlShapeResult(TypedDict):
    """Result of TOML shape analysis."""
    valid: bool
    top_level_keys: list[str] | None
    tables: list[str] | None
    truncated: bool
    summary: str
```

### VersionCompareResult
```python
class VersionCompareResult(TypedDict):
    """Result of version comparison."""
    comparison: int
    valid: bool
    scheme: str
    summary: str
```

### RegexMatchPreview
```python
class RegexMatchPreview(TypedDict):
    """Preview of a regex replacement."""
    sample: str
    original: str
    replacement: str
    changed: bool
```

### RegexFlags
```python
class RegexFlags(TypedDict):
    """Structured regex flags."""
    ignore_case: bool
    multiline: bool
    dotall: bool
    ascii: bool
```

### RegexMatch
```python
class RegexMatch(TypedDict):
    """Result of a single regex match."""
    sample: str
    matches: bool
    fullmatch: bool
    span: list[int] | None
    groups: list[str]
    groupdict: dict[str, str]
```

### RegexTestResult
```python
class RegexTestResult(TypedDict):
    """Result of regex testing."""
    valid_pattern: bool
    results: list[RegexMatch]
    error: str | None
    flags_used: RegexFlags
```

### JsonCompareDiff
```python
class JsonCompareDiff(TypedDict):
    """A single difference between two JSON documents."""
    path: str
    kind: str
    a_type: str | None
    b_type: str | None
    a_preview: str | None
    b_preview: str | None
```

### JsonCompareResult
```python
class JsonCompareResult(TypedDict):
    """Result of JSON comparison."""
    valid_json_a: bool
    valid_json_b: bool
    equal: bool
    same_type: bool
    diff_count: int
    diffs: list[JsonCompareDiff]
    truncated: bool
    summary: str
```

### JsonExtractResult
```python
class JsonExtractResult(TypedDict):
    """Result of JSON extraction using RFC 6901 JSON Pointer."""
    valid_json: bool
    found: bool
    pointer: str
    value_type: str | None
    value: Any | None
    preview: str | None
    child_keys: list[str] | None
    array_length: int | None
    truncated: bool
    missing_at: str | None
    reason: str | None
    available_keys: list[str] | None
    error: str | None
    line: int | None
    column: int | None
    summary: str
```

### SchemaViolation
```python
class SchemaViolation(TypedDict):
    """A single schema validation violation."""
    path: str
    message: str
    value_type: str | None
    expected_type: str | None
```

### ValidateSchemaLightResult
```python
class ValidateSchemaLightResult(TypedDict):
    """Result of light schema validation."""
    valid: bool
    violations: list[SchemaViolation]
    truncated: bool
    summary: str
```

### JsonShapeKey
```python
class JsonShapeKey(TypedDict):
    """A single key in json_shape result."""
    type: str
    keys: dict[str, "JsonShapeKey"] | None
    key_count: int | None
    item_types: list[str] | None
    item_count: int | None
```

### JsonShapeResult
```python
class JsonShapeResult(TypedDict):
    """Result of JSON shape analysis."""
    valid: bool
    shape: JsonShapeKey | None
    truncated: bool
    summary: str
```

### RegexFindIterMatch
```python
class RegexFindIterMatch(TypedDict, total=False):
    """A single regex match found by regex_finditer."""
    match: str
    span: list[int]
    line: int
    column: int
    groups: list[str]
    groupdict: dict[str, str]
```

### RegexFindIterResult
```python
class RegexFindIterResult(TypedDict):
    """Result of regex_finditer."""
    valid_pattern: bool
    matches: list[RegexFindIterMatch]
    truncated: bool
    match_count: int
    error: str | None
```

### RegexSafetyFinding
```python
class RegexSafetyFinding(TypedDict):
    """A single safety finding for a regex pattern."""
    kind: str
    span: list[int]
    message: str
```

### RegexSafetyResult
```python
class RegexSafetyResult(TypedDict):
    """Result of regex safety check."""
    valid_pattern: bool
    risk: str
    findings: list[RegexSafetyFinding]
```

### JsonCanonicalizeResult
```python
class JsonCanonicalizeResult(TypedDict):
    """Result of JSON canonicalization."""
    valid: bool
    canonical: str | None
    minified: str | None
    sha256: str | None
    duplicate_keys: list[str]
    top_level_type: str | None
    top_level_keys: list[str] | None
    error: str | None
    line: int | None
    column: int | None
```

### JsonQueryResult
```python
class JsonQueryResult(TypedDict):
    """Result of JSON query using RFC 6901 JSON Pointer."""
    found: bool
    pointer: str
    value: Any | None
    type: str | None
    missing_at: str | None
    reason: str | None
    error: str | None
    line: int | None
    column: int | None
```

## Core Functions

### `check_brackets(s: str, pairs: dict[str, str] | None = None) -> CheckBracketsResult`

Check whether delimiters are structurally balanced. Tracks unmatched openers and closers with line/column positions.

```python
>>> check_brackets("({[]})")
CheckBracketsResult(balanced=True, unmatched_openers=[],
                    unmatched_closers=[])
>>> check_brackets("({]})")
CheckBracketsResult(balanced=False, unmatched_openers=[...],
                    unmatched_closers=[...])
```

**Raises:** `ValueError` if input exceeds `MAX_TEXT_INPUT_LENGTH`.

### `validate_json(s: str) -> ValidateJsonResult`

Validate JSON syntax and report precise parse errors.

```python
>>> validate_json('{"hello": "world"}')
ValidateJsonResult(valid=True, error=None, position=None,
                   line=None, column=None, type='object',
                   top_level_keys=['hello'])
>>> validate_json('{"hello": }')
ValidateJsonResult(valid=False, error='Expecting property name',
                   position=10, line=1, column=10, type=None,
                   top_level_keys=None)
```

**Note:** `top_level_keys` is only populated for objects. For arrays and primitives, it returns `None`. **Raises:** `ValueError` if input exceeds `MAX_TEXT_INPUT_LENGTH`.

### `validate_toml_text(text: str) -> ValidateTomlResult`

Validate TOML string and return detailed structure information. Requires Python 3.11+ (tomllib).

```python
>>> validate_toml_text('[package]\nname = "test"')
ValidateTomlResult(valid=True, error=None, tables=['package', 'package.name'], ...)
```

**Raises:** `ValueError` if input exceeds `MAX_TEXT_INPUT_LENGTH`.

### `toml_shape(text: str, max_tables: int = 100) -> TomlShapeResult`

Analyze the structure of a TOML document without returning values.

```python
>>> toml_shape('[package]\nname = "test"')
TomlShapeResult(valid=True, tables=['package', 'package.name'], ...)
```

**Raises:** `ValueError` if input exceeds `MAX_TEXT_INPUT_LENGTH`.

### `version_compare(a: str, b: str, scheme: str = "semver") -> VersionCompareResult`

Compare two version strings. Supported schemes: `semver` (strict major.minor.patch comparison; pre-release identifiers parsed but ignored), `loose` (extract all numeric parts and compare sequentially). PEP 440 is not supported (no packaging library).

```python
>>> version_compare("1.2.3", "1.2.4")
VersionCompareResult(comparison=-1, valid=True, scheme='semver', summary='1.2.3 < 1.2.4')
>>> version_compare("1.2.3", "1.2.3")
VersionCompareResult(comparison=0, valid=True, scheme='semver', summary='1.2.3 == 1.2.3')
```

**Raises:** `ValueError` if either input exceeds `MAX_TEXT_INPUT_LENGTH`.

### `list_dedupe(items: list[str], normalization: str = "NFC", casefold: bool = False, stable: bool = True) -> list[str]`

Remove duplicates from list while preserving first-occurrence order.

```python
>>> list_dedupe(["a", "b", "a", "c"])
['a', 'b', 'c']
```

The `stable` parameter is accepted for API compatibility; deduplication always preserves first occurrence order. **Raises:** `ValueError` if items list exceeds `MAX_LIST_ITEMS`.

### `list_sort(items: list[str], normalization: str = "NFC", casefold: bool = False, reverse: bool = False, stable: bool = True) -> list[str]`

Sort list of strings with normalization support. The `stable` parameter is accepted for API compatibility; Python's `sorted()` is always stable.

```python
>>> list_sort(["banana", "Apple", "cherry"])
['Apple', 'banana', 'cherry']
>>> list_sort(["banana", "Apple", "cherry"], casefold=True)
['Apple', 'banana', 'cherry']
```

**Raises:** `ValueError` if items list exceeds `MAX_LIST_ITEMS`.

### `regex_test(pattern: str, samples: list[str], flags: list[str] | None = None, ignore_case: bool = False, multiline: bool = False, dotall: bool = False, ascii: bool = False) -> RegexTestResult`

Test a Python regular expression against sample strings. Uses `search()` for match detection and `fullmatch()` for fullmatch reporting.

```python
>>> regex_test(r"^\d+$", ["123", "abc", "12a"])
RegexTestResult(
    valid_pattern=True,
    error=None,
    results=[
        RegexMatch(sample='123', matches=True, fullmatch=True,
                   span=[0, 3], groups=[], groupdict={}),
        RegexMatch(sample='abc', matches=False, fullmatch=False,
                   span=None, groups=[], groupdict={}),
        RegexMatch(sample='12a', matches=True, fullmatch=False,
                   span=[0, 2], groups=[], groupdict={})
    ],
    flags_used=RegexFlags(ignore_case=False, multiline=False, dotall=False, ascii=False)
)
```

**Supported string flags:** `IGNORECASE`, `MULTILINE`, `DOTALL`, `UNICODE`, `DEBUG`, `VERBOSE`

Pattern complexity is checked before compilation (ReDoS prevention): rejects patterns exceeding `MAX_PATTERN_LENGTH`, exceeding `MAX_PATTERN_NESTING` depth, containing nested quantifiers, or containing adjacent quantifiers.

### `regex_replace_preview(pattern: str, replacement: str, samples: list[str], ignore_case: bool = False, multiline: bool = False, dotall: bool = False, ascii: bool = False) -> dict`

Preview regex replacements on sample strings.

```python
>>> regex_replace_preview(r"(\d+)", r"#\1", ["abc123", "def456"])
{'valid_pattern': True, 'error': None, 'previews': [
    {'sample': 'abc123', 'original': 'abc123', 'replacement': 'abc#123', 'changed': True},
    {'sample': 'def456', 'original': 'def456', 'replacement': 'def#456', 'changed': True}
]}
```

**Raises:** `ValueError` if samples list exceeds `MAX_LIST_ITEMS` or pattern exceeds `MAX_PATTERN_LENGTH`.

### `regex_finditer(pattern: str, text: str, flags: list[str] | None = None, max_matches: int = MAX_MATCHES, include_line_column: bool = True, include_groups: bool = True) -> RegexFindIterResult`

Find all regex matches in text with positions. Returns line/column for each match start. Uses `compiled.finditer()` internally.

```python
>>> regex_finditer(r"\d+", "abc123def456", max_matches=2)
RegexFindIterResult(
    valid_pattern=True,
    matches=[
        {'match': '123', 'span': [3, 6], 'line': 1, 'column': 4, 'groups': [], 'groupdict': {}},
        {'match': '456', 'span': [6, 9], 'line': 1, 'column': 7, 'groups': [], 'groupdict': {}}
    ],
    truncated=False,
    match_count=2,
    error=None
)
```

**Supported flags:** `IGNORECASE`, `MULTILINE`, `DOTALL`, `UNICODE`, `VERBOSE`. **Raises:** `ValueError` if text exceeds `MAX_TEXT_LENGTH_REGEX`. Groups are capped at `MAX_GROUPS` per match.

### `regex_safety_check(pattern: str) -> RegexSafetyResult`

Check regex pattern for potential catastrophic backtracking risks. This is a heuristic check and does not guarantee safety.

```python
>>> regex_safety_check(r"(\w+)+$")
RegexSafetyResult(
    valid_pattern=True,
    risk='high',
    findings=[{'kind': 'nested_quantifier', 'span': [1, 8], 'message': '...'}]
)
```

**Risk levels:** `low` (no findings), `medium` (backreferences or ambiguous patterns), `high` (complexity violations or nested quantifiers). **Finding kinds:** `complexity`, `nested_quantifier`, `backreference`, `ambiguous_dot_star`.

### `json_compare(a: str, b: str, ignore_object_order: bool = True, ignore_array_order: bool = False, numeric_string_equivalence: bool = False, casefold_keys: bool = False, treat_missing_null_as_equal: bool = False, max_diffs: int = 50) -> JsonCompareResult`

Compare two JSON documents semantically. Reports parse errors for invalid inputs.

```python
>>> json_compare('{"a": 1, "b": 2}', '{"b": 2, "a": 1}')
JsonCompareResult(equal=True, diff_count=0, ...)
>>> json_compare('{"a": 1}', '{"a": 2}')
JsonCompareResult(equal=False, diff_count=1, diffs=[...], ...)
```

Diff kinds: `parse_error_a`, `parse_error_b`, `type_changed`, `value_changed`, `key_missing_in_b`, `key_missing_in_a`, `array_length_changed`. **Raises:** `ValueError` if either input exceeds `MAX_TEXT_INPUT_LENGTH`.

### `json_extract(text: str, pointer: str = "", max_output_chars: int = 4000) -> JsonExtractResult`

Extract a value from JSON using RFC 6901 JSON Pointer. Empty pointer returns the whole document.

```python
>>> json_extract('{"foo": {"bar": [1, 2, 3]}}', '/foo/bar/1')
JsonExtractResult(found=True, value=2, value_type='number', ...)
```

**Missing-value reasons:** `invalid_json`, `key_not_found`, `index_out_of_range`, `invalid_pointer_syntax`. Returns `available_keys` for missing object keys, `array_length` for out-of-range array access. **Raises:** `ValueError` if input exceeds `MAX_TEXT_INPUT_LENGTH`.

### `json_shape(text: str, max_depth: int = 4, max_keys: int = 100, max_array_items: int = 5) -> JsonShapeResult`

Analyze the structure of a JSON document without returning values.

```python
>>> json_shape('{"name": "test", "items": [1, 2, 3]}')
JsonShapeResult(valid=True, shape=JsonShapeKey(type='object', keys={...}, ...), ...)
```

**Raises:** `ValueError` if input exceeds `MAX_TEXT_INPUT_LENGTH`.

### `json_canonicalize(text: str, sort_keys: bool = True, indent: int | None = None, ensure_ascii: bool = False, detect_duplicate_keys: bool = True, trailing_newline: bool = False) -> JsonCanonicalizeResult`

Canonicalize JSON with deterministic formatting and duplicate key detection. Returns canonical form, minified form, and SHA-256 hash of canonical output.

```python
>>> json_canonicalize('{"b": 1, "a": 2}', sort_keys=True)
JsonCanonicalizeResult(
    valid=True,
    canonical='{"a": 1, "b": 2}',
    minified='{"a":1,"b":2}',
    sha256='...',
    duplicate_keys=[],
    top_level_type='object',
    top_level_keys=['b', 'a'],
    ...
)
```

When `detect_duplicate_keys=True`, uses a custom `object_pairs_hook` to track duplicate keys during parsing. **Raises:** `ValueError` if input exceeds `MAX_TEXT_INPUT_LENGTH`.

### `json_query(text: str, pointer: str = "") -> JsonQueryResult`

Query JSON using RFC 6901 JSON Pointer. Simpler than `json_extract` — returns the raw value without preview/truncation logic.

```python
>>> json_query('{"foo": {"bar": "baz"}}', '/foo/bar')
JsonQueryResult(found=True, value='baz', type='string', ...)
```

**Missing-value reasons:** `invalid_json`, `key_not_found`, `index_out_of_range`, `invalid_pointer_syntax`. **Raises:** `ValueError` if input exceeds `MAX_TEXT_INPUT_LENGTH`.

### `validate_schema_light(data: Any, schema: dict) -> ValidateSchemaLightResult`

Validate data against a simple schema format (NOT full JSON Schema). This is a lightweight internal schema validator.

Supported schema features:
- `type`: object, array, string, number, integer, boolean, null
- `required`: list of required keys
- `properties`: nested property definitions
- `additional_properties`: false to disallow extra keys
- `enum`: list of allowed values
- `min_length`, `max_length`: for strings
- `min_items`, `max_items`: for arrays
- `pattern`: regex pattern for strings (checked for safety via `_check_pattern_complexity`)
- `items`: schema for array items (nested validation)

```python
>>> validate_schema_light({"name": "test"}, {"type": "object", "required": ["name"]})
ValidateSchemaLightResult(valid=True, violations=[], truncated=False, summary='Data is valid')
```

**Limits:** `MAX_SCHEMA_VIOLATIONS` (100) violations returned, `MAX_SCHEMA_ELEMENTS` (100,000) elements walked, `MAX_SCHEMA_DEPTH` (50) nesting depth.

## Internal Helper Functions

### `_check_pattern_complexity(pattern: str) -> tuple[bool, str | None]`

Check if regex pattern is too complex (ReDoS prevention). Detects excessive nesting depth, nested quantifiers, and adjacent quantifiers.

### `_decode_pointer_token(token: str) -> str`

Decode RFC 6901 escape sequences (`~1` -> `/`, `~0` -> `~`).

### `_encode_pointer_token(token: str) -> str`

Encode a key for use in a JSON pointer (`/` -> `~1`, `~` -> `~0`).

### `_get_json_type(value: Any) -> str`

Get type string for a JSON value (`null`, `boolean`, `integer`, `float`, `string`, `array`, `object`).

### `_build_newline_index(s: str) -> list[int]`

Build a sorted list of newline positions for O(log N) line/column lookup.

### `_get_line_column_from_index(newlines: list[int], index: int) -> tuple[int, int]`

Get 1-based line and column using a precomputed newline index.

### `_get_line_column(s: str, index: int) -> tuple[int, int]`

Get 1-based line and column for a string index (linear scan).

### `_sort_json_keys(obj: Any) -> Any`

Recursively sort object keys in JSON-compatible data for canonicalization.

### `_extract_tables(d: dict, prefix: str = "") -> list[str]`

Recursively extract all table names from parsed TOML (e.g., `['package', 'package.name']`).

## Input Limits

Functions raise `ValueError` when input exceeds `MAX_TEXT_INPUT_LENGTH`:
- `check_brackets()`, `validate_json()`, `validate_toml_text()`, `toml_shape()`, `json_extract()`, `json_shape()`, `json_canonicalize()`, `json_query()`, `version_compare()`

Functions use their own limits:
- `list_dedupe()`, `list_sort()`: `MAX_LIST_ITEMS = 10_000`
- `regex_test()`: `MAX_SAMPLE_LENGTH = 10_000` per sample, `MAX_LIST_ITEMS` for samples list
- `regex_finditer()`: `MAX_TEXT_LENGTH_REGEX = 100_000` for text, `MAX_PATTERN_LENGTH_REGEX = 1000` for pattern, `MAX_MATCHES = 100`, `MAX_GROUPS = 100`
- `regex_replace_preview()`: `MAX_LIST_ITEMS` for samples, `MAX_SAMPLE_LENGTH` per sample
- `validate_schema_light()`: `MAX_SCHEMA_VIOLATIONS = 100`, `MAX_SCHEMA_ELEMENTS = 100_000`, `MAX_SCHEMA_DEPTH = 50`

## Error Handling

Most functions return TypedDict results with error information rather than raising exceptions:
- `check_brackets` returns `CheckBracketsResult` with `balanced=False` and unmatched entries
- `validate_json` returns `ValidateJsonResult` with `valid=False` and error details
- `validate_toml_text` returns `ValidateTomlResult` with `valid=False` and error details
- `regex_test` returns `RegexTestResult` with `valid_pattern=False` and error message
- `regex_finditer` returns `RegexFindIterResult` with `valid_pattern=False` and error message
- `regex_safety_check` returns `RegexSafetyResult` with `risk` level and `findings`
- `json_compare` returns `JsonCompareResult` with parse errors for invalid inputs

Functions that raise `ValueError`: `check_brackets`, `validate_json`, `validate_toml_text`, `toml_shape`, `json_extract`, `json_shape`, `json_canonicalize`, `json_query`, `version_compare`, `list_dedupe`, `list_sort`, `regex_replace_preview`.

## Index

See [overview.md](overview.md) for the module index.
