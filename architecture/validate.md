# validate.py - Validation Utilities

## Purpose

Provides validation utilities for checking brackets, JSON/TOML syntax, regex patterns, schema validation, and version comparison.

## Constants

```python
MAX_INPUT_LENGTH = 100_000       # Maximum input length for most functions
MAX_PATTERN_LENGTH = 1000        # Maximum regex pattern length
MAX_PATTERN_NESTING = 5          # Maximum regex nesting depth
MAX_SAMPLE_LENGTH = 10_000       # Maximum sample string length for regex_test
MAX_SCHEMA_VIOLATIONS = 100      # Maximum violations returned by validate_schema_light
MAX_TEXT_LENGTH_REGEX = 100_000  # Maximum text length for regex functions
MAX_PATTERN_LENGTH_REGEX = 1000  # Maximum pattern length for regex functions
MAX_MATCHES = 100                # Maximum matches returned by regex_finditer
MAX_GROUPS = 100                 # Maximum groups captured by regex_finditer

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

Check whether delimiters are structurally balanced.

```python
>>> check_brackets("({[]})")
CheckBracketsResult(balanced=True, unmatched_openers=[],
                    unmatched_closers=[])
>>> check_brackets("({]})")
CheckBracketsResult(balanced=False, unmatched_openers=[...],
                    unmatched_closers=[...])
```

### `validate_json(s: str) -> ValidateJsonResult`

Validate JSON syntax and report precise parse errors.

```python
>>> validate_json('{"hello": "world"}')
ValidateJsonResult(valid=True, error=None, position=None,
                   line=None, column=None, type='object')
>>> validate_json('{"hello": }')
ValidateJsonResult(valid=False, error='Expecting property name',
                   position=10, line=1,
                   column=10, type=None)
```

**Note:** `top_level_keys` is only populated for objects. For arrays and primitives, it returns `None`.

### `validate_toml_text(text: str) -> ValidateTomlResult`

Validate TOML string and return detailed structure information.

```python
>>> validate_toml_text('[package]\nname = "test"')
ValidateTomlResult(valid=True, error=None, tables=['package', 'package.name'], ...)
```

Requires Python 3.11+ (tomllib).

### `toml_shape(text: str, max_tables: int = 100) -> TomlShapeResult`

Analyze the structure of a TOML document.

```python
>>> toml_shape('[package]\nname = "test"')
TomlShapeResult(valid=True, tables=['package', 'package.name'], ...)
```

### `version_compare(a: str, b: str, scheme: str = "semver") -> VersionCompareResult`

Compare two version strings.

Supported schemes: `semver` (major.minor.patch, pre-release identifiers ignored in comparison), `loose` (numeric parts only). PEP 440 is not supported.

```python
>>> version_compare("1.2.3", "1.2.4")
VersionCompareResult(comparison=-1, valid=True, scheme='semver', summary='1.2.3 < 1.2.4')
>>> version_compare("1.2.3", "1.2.3")
VersionCompareResult(comparison=0, valid=True, scheme='semver', summary='1.2.3 == 1.2.3')
```

### `regex_test(pattern: str, samples: list[str], flags: list[str] | None = None, ...) -> RegexTestResult`

Test a Python regular expression against sample strings.

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
    ]
)
```

**Supported flags**: `IGNORECASE`, `MULTILINE`, `DOTALL`, `UNICODE`, `DEBUG`, `VERBOSE`

### `regex_replace_preview(pattern: str, replacement: str, samples: list[str], ...) -> dict`

Preview regex replacements on sample strings.

```python
>>> regex_replace_preview(r"(\d+)", r"#\1", ["abc123", "def456"])
{'valid_pattern': True, 'error': None, 'previews': [
    {'sample': 'abc123', 'original': 'abc123', 'replacement': 'abc#123', 'changed': True},
    {'sample': 'def456', 'original': 'def456', 'replacement': 'def#456', 'changed': True}
]}
```

### `list_dedupe(items: list[str], normalization: str = "NFC", casefold: bool = False, stable: bool = True) -> list[str]`

Remove duplicates from list while preserving order.

```python
>>> list_dedupe(["a", "b", "a", "c"])
['a', 'b', 'c']
```

### `list_sort(items: list[str], normalization: str = "NFC", casefold: bool = False, reverse: bool = False, stable: bool = True) -> list[str]`

Sort list of strings with normalization support.
The `stable` parameter is accepted for API compatibility; Python sorting is always stable.

```python
>>> list_sort(["banana", "Apple", "cherry"])
['Apple', 'banana', 'cherry']
>>> list_sort(["banana", "Apple", "cherry"], casefold=True)
['Apple', 'banana', 'cherry']
```

### `json_compare(a: str, b: str, ignore_object_order: bool = True, ...) -> JsonCompareResult`

Compare two JSON documents semantically.

```python
>>> json_compare('{"a": 1, "b": 2}', '{"b": 2, "a": 1}')
JsonCompareResult(equal=True, diff_count=0, ...)
>>> json_compare('{"a": 1}', '{"a": 2}')
JsonCompareResult(equal=False, diff_count=1, diffs=[...], ...)
```

Options: `ignore_object_order`, `ignore_array_order`, `numeric_string_equivalence`, `casefold_keys`, `treat_missing_null_as_equal`, `max_diffs`

### `json_extract(text: str, pointer: str = "", max_output_chars: int = 4000) -> JsonExtractResult`

Extract a value from JSON using RFC 6901 JSON Pointer.

```python
>>> json_extract('{"foo": {"bar": [1, 2, 3]}}', '/foo/bar/1')
JsonExtractResult(found=True, value=2, value_type='number', ...)
```

### `json_shape(text: str, max_depth: int = 4, max_keys: int = 100, max_array_items: int = 5) -> JsonShapeResult`

Analyze the structure of a JSON document without returning values.

```python
>>> json_shape('{"name": "test", "items": [1, 2, 3]}')
JsonShapeResult(valid=True, shape={'type': 'object', 'keys': {'name': {...}, 'items': {...}}}, ...)
```

### `regex_finditer(pattern: str, text: str, flags: list[str] | None = None, max_matches: int = 100, ...) -> RegexFindIterResult`

Find all regex matches in text with positions.

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

### `regex_safety_check(pattern: str) -> RegexSafetyResult`

Check regex pattern for potential catastrophic backtracking risks.

```python
>>> regex_safety_check(r"(\w+)+$")
RegexSafetyResult(
    valid_pattern=True,
    risk='high',
    findings=[{'kind': 'nested_quantifier', 'span': [1, 8], 'message': '...'}]
)
```

### `validate_schema_light(data: Any, schema: dict) -> ValidateSchemaLightResult`

Validate data against a simple schema format (NOT full JSON Schema).

Supported schema features: `type`, `required`, `properties`, `additional_properties`, `enum`, `min_length`, `max_length`, `min_items`, `max_items`, `pattern`, `items`.

```python
>>> validate_schema_light({"name": "test"}, {"type": "object", "required": ["name"]})
ValidateSchemaLightResult(valid=True, violations=[], ...)
```

### `json_canonicalize(text: str, sort_keys: bool = True, indent: int | None = None, ...) -> JsonCanonicalizeResult`

Canonicalize JSON with deterministic formatting and duplicate key detection.

```python
>>> json_canonicalize('{"b": 1, "a": 2}', sort_keys=True)
JsonCanonicalizeResult(
    valid=True,
    canonical='{"a": 1, "b": 2}',
    minified='{"a":1,"b":2}',
    sha256='...',
    duplicate_keys=[],
    ...
)
```

### `json_query(text: str, pointer: str = "") -> JsonQueryResult`

Query JSON using RFC 6901 JSON Pointer.

```python
>>> json_query('{"foo": {"bar": "baz"}}', '/foo/bar')
JsonQueryResult(found=True, value='baz', type='string', ...)
```

## Input Limits

Functions raise `ValueError` when input exceeds `MAX_INPUT_LENGTH`:
- `check_brackets()`, `validate_json()`, `validate_toml_text()`, `toml_shape()`, `json_extract()`, `json_shape()`, `json_canonicalize()`, `json_query()`

Functions use their own limits:
- `regex_test()`: `MAX_SAMPLE_LENGTH = 10_000` per sample
- `regex_finditer()`: `MAX_TEXT_LENGTH_REGEX = 100_000` for text, `MAX_PATTERN_LENGTH_REGEX = 1000` for pattern
- `validate_schema_light()`: `MAX_SCHEMA_VIOLATIONS = 100`

## Error Handling

All functions return TypedDict results with error information rather than raising exceptions:
- `check_brackets` returns `CheckBracketsResult` with `balanced=False` and unmatched entries
- `validate_json` returns `ValidateJsonResult` with `valid=False` and error details
- `regex_test` returns `RegexTestResult` with `valid_pattern=False` and error message
- `regex_safety_check` returns `RegexSafetyResult` with `risk` level and `findings`

## Index

See [overview.md](overview.md) for the module index.
