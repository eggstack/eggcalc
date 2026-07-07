"""
Text validation primitives.

Provides validation for JSON, brackets, and regex patterns.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any, Literal, TypedDict, cast

MAX_INPUT_LENGTH = 100_000
MAX_LIST_ITEMS = 10_000
MAX_PATTERN_LENGTH = 1000
MAX_PATTERN_NESTING = 5
MAX_SAMPLE_LENGTH = 10_000
MAX_SCHEMA_DEPTH = 50
MAX_SCHEMA_ELEMENTS = 100_000


class BracketError(TypedDict):
    """Information about an unmatched bracket."""

    char: str
    index: int
    line: int
    column: int


class CheckBracketsResult(TypedDict):
    """Result of bracket checking."""

    balanced: bool
    unmatched_openers: list[BracketError]
    unmatched_closers: list[BracketError]


class ValidateJsonResult(TypedDict):
    """Result of JSON validation."""

    valid: bool
    error: str | None
    line: int | None
    column: int | None
    position: int | None
    type: str | None
    top_level_keys: list[str] | None


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


class RegexMatchPreview(TypedDict):
    """Preview of a regex replacement."""

    sample: str
    original: str
    replacement: str
    changed: bool


class RegexFlags(TypedDict):
    """Structured regex flags."""

    ignore_case: bool
    multiline: bool
    dotall: bool
    ascii: bool


class RegexMatch(TypedDict):
    """Result of a single regex match."""

    sample: str
    matches: bool
    fullmatch: bool
    span: list[int] | None
    groups: list[str]
    groupdict: dict[str, str]


class RegexTestResult(TypedDict):
    """Result of regex testing."""

    valid_pattern: bool
    results: list[RegexMatch]
    error: str | None
    flags_used: RegexFlags


class JsonCompareDiff(TypedDict):
    """A single difference between two JSON documents."""

    path: str
    kind: str
    a_type: str | None
    b_type: str | None
    a_preview: str | None
    b_preview: str | None


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


# Default bracket pairs
DEFAULT_BRACKET_PAIRS: dict[str, str] = {
    "(": ")",
    "[": "]",
    "{": "}",
    "<": ">",
}


def _build_newline_index(s: str) -> list[int]:
    """Build a sorted list of newline positions for O(log N) line/column lookup.

    Args:
        s: Input string.

    Returns:
        List of character indices where newlines occur.
    """
    return [i for i, ch in enumerate(s) if ch == "\n"]


def _get_line_column_from_index(newlines: list[int], index: int) -> tuple[int, int]:
    """Get 1-based line and column using a precomputed newline index.

    Args:
        newlines: Sorted list of newline positions (from _build_newline_index).
        index: Character index.

    Returns:
        Tuple of (line, column), both 1-based.
    """
    import bisect

    line = bisect.bisect_right(newlines, index) + 1
    if line == 1:
        column = index + 1
    else:
        # Column is offset from the previous newline
        prev_newline = newlines[line - 2]
        column = index - prev_newline
        # If index points to a newline character itself, it belongs to the
        # end of the previous line (column = line length), but since we
        # cannot know the line length here without the text, return the
        # column as 1 (start of next line) which is the standard convention.
        if column == 0:
            column = 1
    return line, column


def _get_line_column(s: str, index: int) -> tuple[int, int]:
    """Get 1-based line and column for a string index.

    Args:
        s: Input string.
        index: Character index.

    Returns:
        Tuple of (line, column), both 1-based.
    """
    line = 1
    column = 1
    for i in range(index):
        if s[i] == "\n":
            line += 1
            column = 1
        else:
            column += 1
    return line, column


def check_brackets(
    s: str,
    pairs: dict[str, str] | None = None,
) -> CheckBracketsResult:
    """Check if brackets are balanced in the string.

    Tracks unmatched openers and closers with positions.

    Args:
        s: Input string.
        pairs: Bracket pair mapping (default: () [] {} <>).

    Returns:
        Dictionary with balanced (bool), unmatched_openers (list),
        and unmatched_closers (list).

    Raises:
        ValueError: If input exceeds MAX_INPUT_LENGTH.
    """
    if len(s) > MAX_INPUT_LENGTH:
        raise ValueError(f"Input length {len(s)} exceeds MAX_INPUT_LENGTH {MAX_INPUT_LENGTH}")

    if pairs is None:
        pairs = DEFAULT_BRACKET_PAIRS

    openers = set(pairs.keys())
    closers = set(pairs.values())
    opener_to_closer = pairs.copy()

    # Precompute newline index for O(log N) line/column lookup
    newline_index = _build_newline_index(s)

    def _lc(idx: int) -> tuple[int, int]:
        return _get_line_column_from_index(newline_index, idx)

    stack: list[tuple[str, int]] = []  # (char, index)
    unmatched_openers: list[BracketError] = []
    unmatched_closers: list[BracketError] = []

    for index, char in enumerate(s):
        if char in openers:
            stack.append((char, index))
        elif char in closers:
            if stack:
                opener, opener_index = stack.pop()
                if opener_to_closer.get(opener) != char:
                    # Mismatch - treat as both unmatched
                    line, column = _lc(opener_index)
                    unmatched_openers.append(
                        BracketError(
                            char=opener,
                            index=opener_index,
                            line=line,
                            column=column,
                        )
                    )
                    line, column = _lc(index)
                    unmatched_closers.append(
                        BracketError(
                            char=char,
                            index=index,
                            line=line,
                            column=column,
                        )
                    )
            else:
                # No matching opener
                line, column = _lc(index)
                unmatched_closers.append(
                    BracketError(
                        char=char,
                        index=index,
                        line=line,
                        column=column,
                    )
                )

    # Remaining openers are unmatched
    for opener, opener_index in stack:
        line, column = _lc(opener_index)
        unmatched_openers.append(
            BracketError(
                char=opener,
                index=opener_index,
                line=line,
                column=column,
            )
        )

    return CheckBracketsResult(
        balanced=len(unmatched_openers) == 0 and len(unmatched_closers) == 0,
        unmatched_openers=unmatched_openers,
        unmatched_closers=unmatched_closers,
    )


def validate_json(s: str) -> ValidateJsonResult:
    """Validate JSON string and return detailed error information.

    Args:
        s: Input string.

    Returns:
        Dictionary with valid (bool), error message (if invalid),
        line, column, position (if invalid), and type/top_level_keys (if valid).

    Raises:
        ValueError: If input exceeds MAX_INPUT_LENGTH.
    """
    if len(s) > MAX_INPUT_LENGTH:
        raise ValueError(f"Input length {len(s)} exceeds MAX_INPUT_LENGTH {MAX_INPUT_LENGTH}")

    try:
        parsed = json.loads(s)

        # Determine the type
        if isinstance(parsed, dict):
            type_str = "object"
            keys = list(parsed.keys())
        elif isinstance(parsed, list):
            type_str = "array"
            keys = None
        else:
            type_str = type(parsed).__name__
            keys = None

        return ValidateJsonResult(
            valid=True,
            error=None,
            line=None,
            column=None,
            position=None,
            type=type_str,
            top_level_keys=keys,
        )

    except json.JSONDecodeError as e:
        return ValidateJsonResult(
            valid=False,
            error=e.msg,
            line=e.lineno,
            column=e.colno,
            position=e.pos,
            type=None,
            top_level_keys=None,
        )


def _extract_tables(d: dict, prefix: str = "") -> list[str]:
    """Recursively extract all table names from parsed TOML."""
    tables: list[str] = []
    for key, value in d.items():
        full_name = f"{prefix}{key}" if prefix else key
        tables.append(full_name)
        if isinstance(value, dict):
            tables.extend(_extract_tables(value, f"{full_name}."))
    return tables


def validate_toml_text(text: str) -> ValidateTomlResult:
    """Validate TOML string and return detailed structure information.

    Args:
        text: Input string.

    Returns:
        Dictionary with valid (bool), error message (if invalid),
        line, column, position (if invalid), type, top_level_keys,
        and tables (table paths like 'package', 'dependencies.dev').

    Raises:
        ValueError: If input exceeds MAX_INPUT_LENGTH.
    """
    try:
        import tomllib
    except ImportError:
        return ValidateTomlResult(
            valid=False,
            error="tomllib not available - Python 3.11+ required",
            line=None,
            column=None,
            position=None,
            type=None,
            top_level_keys=None,
            tables=None,
        )

    if len(text) > MAX_INPUT_LENGTH:
        raise ValueError(f"Input length {len(text)} exceeds MAX_INPUT_LENGTH {MAX_INPUT_LENGTH}")

    try:
        parsed = tomllib.loads(text)

        top_level = list(parsed.keys())
        tables = _extract_tables(parsed)

        return ValidateTomlResult(
            valid=True,
            error=None,
            line=None,
            column=None,
            position=None,
            type="document",
            top_level_keys=top_level,
            tables=tables,
        )

    except (ValueError, KeyError, TypeError, AttributeError) as e:
        # TOML decode errors are typically ValueError or its subclasses.
        # KeyError/TypeError/AttributeError can occur from malformed structure.
        err_str = str(e)
        line = getattr(e, 'lineno', None)
        col = getattr(e, 'colno', None)
        pos = getattr(e, 'pos', None)

        return ValidateTomlResult(
            valid=False,
            error=err_str,
            line=line,
            column=col,
            position=pos,
            type=None,
            top_level_keys=None,
            tables=None,
        )


class TomlShapeResult(TypedDict):
    """Result of TOML shape analysis."""

    valid: bool
    top_level_keys: list[str] | None
    tables: list[str] | None
    truncated: bool
    summary: str


class VersionCompareResult(TypedDict):
    """Result of version comparison."""

    comparison: int
    valid: bool
    scheme: str
    summary: str


def toml_shape(text: str, max_tables: int = 100) -> TomlShapeResult:
    """Analyze the structure of a TOML document.

    Args:
        text: TOML document string.
        max_tables: Maximum tables to return (default 100).

    Returns:
        Dictionary with valid (bool), top_level_keys, tables, and summary.

    Raises:
        ValueError: If input exceeds MAX_INPUT_LENGTH.
    """
    try:
        import tomllib
    except ImportError:
        return TomlShapeResult(
            valid=False,
            top_level_keys=None,
            tables=None,
            truncated=False,
            summary="tomllib not available - Python 3.11+ required",
        )

    if len(text) > MAX_INPUT_LENGTH:
        raise ValueError(f"Input length {len(text)} exceeds MAX_INPUT_LENGTH {MAX_INPUT_LENGTH}")

    try:
        parsed = tomllib.loads(text)
        top_level = list(parsed.keys())
        tables = _extract_tables(parsed)

        truncated = len(tables) > max_tables
        if truncated:
            tables = tables[:max_tables]

        return TomlShapeResult(
            valid=True,
            top_level_keys=top_level,
            tables=tables,
            truncated=truncated,
            summary=f"Valid TOML with {len(top_level)} top-level keys and {len(tables)} tables",
        )
    except Exception as e:
        return TomlShapeResult(
            valid=False,
            top_level_keys=None,
            tables=None,
            truncated=False,
            summary=f"Error: {str(e)}",
        )


def version_compare(a: str, b: str, scheme: str = "semver") -> VersionCompareResult:
    """Compare two version strings.

    Args:
        a: First version string.
        b: Second version string.
        scheme: Version scheme ("semver" or "loose").
            - semver: strict major.minor.patch comparison; pre-release
              identifiers are parsed but ignored in comparison (simplified).
            - loose: extract all numeric parts and compare sequentially.

    Returns:
        Dictionary with comparison (-1, 0, 1), valid (bool), scheme,
        and summary.

    Raises:
        ValueError: If either input string exceeds MAX_INPUT_LENGTH.
    """
    if len(a) > MAX_INPUT_LENGTH:
        raise ValueError(f"Input 'a' length {len(a)} exceeds maximum {MAX_INPUT_LENGTH}")
    if len(b) > MAX_INPUT_LENGTH:
        raise ValueError(f"Input 'b' length {len(b)} exceeds maximum {MAX_INPUT_LENGTH}")
    if scheme == "semver":
        return _semver_compare(a, b)
    elif scheme == "pep440":
        return VersionCompareResult(
            comparison=0,
            valid=False,
            scheme="pep440",
            summary="PEP 440 is not supported (no packaging library; use semver or loose scheme)",
        )
    elif scheme == "loose":
        return _loose_version_compare(a, b)
    else:
        return VersionCompareResult(
            comparison=0,
            valid=False,
            scheme=scheme,
            summary=f"Unknown scheme: {scheme}",
        )


def _parse_semver(version: str) -> tuple[int, int, int] | None:
    """Parse semver string into (major, minor, patch).

    Args:
        version: Version string like "1.2.3" or "1.2.3-beta".

    Returns:
        Tuple of (major, minor, patch) or None if invalid.
    """
    import re

    match = re.match(r'^(\d+)\.(\d+)\.(\d+)', version.strip())
    if not match:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def _semver_compare(a: str, b: str) -> VersionCompareResult:
    """Compare two semver versions.

    Args:
        a: First version string.
        b: Second version string.

    Returns:
        VersionCompareResult with comparison, valid, scheme, summary.
    """
    parsed_a = _parse_semver(a)
    parsed_b = _parse_semver(b)

    if parsed_a is None:
        return VersionCompareResult(
            comparison=0,
            valid=False,
            scheme="semver",
            summary=f"Invalid semver: '{a}'",
        )
    if parsed_b is None:
        return VersionCompareResult(
            comparison=0,
            valid=False,
            scheme="semver",
            summary=f"Invalid semver: '{b}'",
        )

    if parsed_a < parsed_b:
        comparison = -1
        summary = f"{a} < {b}"
    elif parsed_a > parsed_b:
        comparison = 1
        summary = f"{a} > {b}"
    else:
        comparison = 0
        summary = f"{a} == {b}"

    return VersionCompareResult(
        comparison=comparison,
        valid=True,
        scheme="semver",
        summary=summary,
    )


def _loose_version_compare(a: str, b: str) -> VersionCompareResult:
    """Compare two versions using loose parsing.

    Extracts numeric parts and compares them sequentially.

    Args:
        a: First version string.
        b: Second version string.

    Returns:
        VersionCompareResult with comparison, valid, scheme, summary.
    """
    import re

    def extract_parts(version: str) -> list[int]:
        parts = re.findall(r'\d+', version)
        return [int(p) for p in parts]

    parts_a = extract_parts(a)
    parts_b = extract_parts(b)

    max_len = max(len(parts_a), len(parts_b))
    for i in range(max_len):
        val_a = parts_a[i] if i < len(parts_a) else 0
        val_b = parts_b[i] if i < len(parts_b) else 0
        if val_a < val_b:
            return VersionCompareResult(
                comparison=-1,
                valid=True,
                scheme="loose",
                summary=f"{a} < {b}",
            )
        elif val_a > val_b:
            return VersionCompareResult(
                comparison=1,
                valid=True,
                scheme="loose",
                summary=f"{a} > {b}",
            )

    return VersionCompareResult(
        comparison=0,
        valid=True,
        scheme="loose",
        summary=f"{a} == {b}",
    )


def list_dedupe(
    items: list[str],
    normalization: str = "NFC",
    casefold: bool = False,
    stable: bool = True,
) -> list[str]:
    """Remove duplicates from list while preserving order.

    Args:
        items: List of strings to dedupe.
        normalization: Unicode normalization form.
        casefold: Apply casefolding before comparison.
        stable: Accepted for API compatibility; deduplication preserves first occurrence order.

    Returns:
        List with duplicates removed.

    Raises:
        ValueError: If items list is too large.
    """
    if len(items) > MAX_LIST_ITEMS:
        raise ValueError(f"Items count {len(items)} exceeds maximum {MAX_LIST_ITEMS}")
    seen: set[str] = set()
    result: list[str] = []

    for item in items:
        if casefold:
            compare_val = item.casefold()
        else:
            compare_val = item

        if normalization != "raw":
            compare_val = unicodedata.normalize(
                cast(Literal["NFC", "NFD", "NFKC", "NFKD"], normalization), compare_val
            )

        if compare_val not in seen:
            seen.add(compare_val)
            result.append(item)

    return result


def list_sort(
    items: list[str],
    normalization: str = "NFC",
    casefold: bool = False,
    reverse: bool = False,
    stable: bool = True,
) -> list[str]:
    """Sort list of strings with normalization support.

    Args:
        items: List of strings to sort.
        normalization: Unicode normalization form.
        casefold: Apply casefolding for sorting.
        reverse: Sort in descending order.
        stable: Accepted for API compatibility. Python's sorted() is always stable,
            so this parameter has no effect on the sort behavior.

    Returns:
        Sorted list.

    Raises:
        ValueError: If items list is too large.
    """
    if len(items) > MAX_LIST_ITEMS:
        raise ValueError(f"Items count {len(items)} exceeds maximum {MAX_LIST_ITEMS}")

    def transform(s: str) -> str:
        if casefold:
            s = s.casefold()
        if normalization != "raw":
            s = unicodedata.normalize(cast(Literal["NFC", "NFD", "NFKC", "NFKD"], normalization), s)
        return s

    return sorted(items, key=transform, reverse=reverse)


def _check_pattern_complexity(pattern: str) -> tuple[bool, str | None]:
    """Check if regex pattern is too complex (ReDoS prevention).

    Detects:
    - Excessive nesting depth (MAX_PATTERN_NESTING)
    - Nested quantifiers (e.g., (a+)+, (a*)*) which cause catastrophic backtracking
    - Adjacent quantifiers (e.g., a++, a**)

    Args:
        pattern: Regular expression pattern.

    Returns:
        Tuple of (is_safe, error_message).
    """
    if len(pattern) > MAX_PATTERN_LENGTH:
        return False, f"Pattern length {len(pattern)} exceeds maximum {MAX_PATTERN_LENGTH}"

    nesting_depth = 0
    max_nesting = 0
    in_char_class = False
    # Per-group state: whether a quantifier was seen directly in this group's content
    group_stack: list[bool] = []
    # Whether the immediately-preceding group had a quantifier in its content
    prev_group_had_quantifier = False
    i = 0

    while i < len(pattern):
        char = pattern[i]

        if char == '\\' and i + 1 < len(pattern):
            prev_group_had_quantifier = False
            i += 2
            continue

        if char == '[':
            nesting_depth += 1
            max_nesting = max(max_nesting, nesting_depth)
            in_char_class = True
        elif char == ']':
            nesting_depth -= 1
            in_char_class = False
        elif char == '(' and not in_char_class:
            nesting_depth += 1
            max_nesting = max(max_nesting, nesting_depth)
            group_stack.append(False)
            prev_group_had_quantifier = False
        elif char == ')' and not in_char_class:
            nesting_depth -= 1
            if nesting_depth < 0:
                return False, f"Unmatched closing '{char}' at position {i}"
            if group_stack:
                inner_had_quantifier = group_stack.pop()
                # OR the inner group's state into the parent group
                if group_stack:
                    group_stack[-1] = group_stack[-1] or inner_had_quantifier
                prev_group_had_quantifier = inner_had_quantifier
            else:
                prev_group_had_quantifier = False
        elif char in ('+', '*', '?') and not in_char_class:
            # ? after ( is group syntax ((?: ), (?= ), (?! ), (?<= ), (?<! )),
            # not a quantifier on a preceding element.
            if char == '?' and i > 0 and pattern[i - 1] == '(':
                prev_group_had_quantifier = False
            else:
                # Check if previous char was also a quantifier (e.g., ++)
                if i > 0 and pattern[i - 1] in ('+', '*', '?'):
                    return False, f"Adjacent quantifiers detected at position {i}"
                # Check if a group with inner quantifier was just closed
                if prev_group_had_quantifier:
                    return False, (
                        f"Nested quantifiers detected at position {i}: "
                        "quantifier after group with internal quantifier"
                    )
                # Mark current group as having a quantifier
                if group_stack:
                    group_stack[-1] = True
                prev_group_had_quantifier = False
        elif char == '{' and not in_char_class:
            # Check if this is a {n,m} quantifier
            j = i + 1
            if j < len(pattern) and pattern[j].isdigit():
                # Scan for {digits,digits} or {digits} or {digits,}
                k = j
                while k < len(pattern) and pattern[k].isdigit():
                    k += 1
                if k < len(pattern) and pattern[k] == ',':
                    k += 1
                    while k < len(pattern) and pattern[k].isdigit():
                        k += 1
                    if k < len(pattern) and pattern[k] == '}':
                        # This is a {n,m} quantifier -- check for nested quantifiers
                        if prev_group_had_quantifier:
                            return False, (
                                f"Nested quantifiers detected at position {i}: "
                                "{{n,m}} quantifier after group with internal quantifier"
                            )
                        if group_stack:
                            group_stack[-1] = True
                        prev_group_had_quantifier = False
                        i = k  # skip past the closing }
                elif k < len(pattern) and pattern[k] == '}':
                    # {n} quantifier
                    if prev_group_had_quantifier:
                        return False, (
                            f"Nested quantifiers detected at position {i}: "
                            "{{n}} quantifier after group with internal quantifier"
                        )
                    if group_stack:
                        group_stack[-1] = True
                    prev_group_had_quantifier = False
                    i = k  # skip past the closing }
            else:
                prev_group_had_quantifier = False
        else:
            prev_group_had_quantifier = False

        i += 1

    if max_nesting > MAX_PATTERN_NESTING:
        return False, f"Pattern nesting depth {max_nesting} exceeds maximum {MAX_PATTERN_NESTING}"

    return True, None


def regex_test(
    pattern: str,
    samples: list[str],
    flags: list[str] | None = None,
    ignore_case: bool = False,
    multiline: bool = False,
    dotall: bool = False,
    ascii: bool = False,
) -> RegexTestResult:
    """Test a Python regular expression against sample strings.

    Args:
        pattern: Regular expression pattern.
        samples: List of strings to test against.
        flags: List of flag names (e.g., ["IGNORECASE", "MULTILINE"]).
        ignore_case: Use IGNORECASE flag.
        multiline: Use MULTILINE flag.
        dotall: Use DOTALL flag.
        ascii: Use ASCII flag.

    Returns:
        Dictionary with valid_pattern (bool), results, and flags_used.
    """
    flags_used = RegexFlags(
        ignore_case=ignore_case,
        multiline=multiline,
        dotall=dotall,
        ascii=ascii,
    )
    if not isinstance(pattern, str):
        return RegexTestResult(
            valid_pattern=False,
            results=[],
            error=f"Pattern must be a string, got {type(pattern).__name__}",
            flags_used=flags_used,
        )
    if not isinstance(samples, list):
        return RegexTestResult(
            valid_pattern=False,
            results=[],
            error=f"Samples must be a list, got {type(samples).__name__}",
            flags_used=flags_used,
        )
    if flags is not None and not isinstance(flags, list):
        return RegexTestResult(
            valid_pattern=False,
            results=[],
            error=f"Flags must be a list, got {type(flags).__name__}",
            flags_used=flags_used,
        )
    non_str_flags = (
        [] if flags is None else [i for i, flag in enumerate(flags) if not isinstance(flag, str)]
    )
    if non_str_flags:
        return RegexTestResult(
            valid_pattern=False,
            results=[],
            error=f"All flags must be strings; non-string items at indices {non_str_flags[:5]}",
            flags_used=flags_used,
        )
    if len(samples) > MAX_LIST_ITEMS:
        return RegexTestResult(
            valid_pattern=False,
            results=[],
            error=f"Samples count {len(samples)} exceeds maximum {MAX_LIST_ITEMS}",
            flags_used=flags_used,
        )
    non_str_samples = [i for i, sample in enumerate(samples) if not isinstance(sample, str)]
    if non_str_samples:
        return RegexTestResult(
            valid_pattern=False,
            results=[],
            error=f"All samples must be strings; non-string items at indices {non_str_samples[:5]}",
            flags_used=flags_used,
        )
    long_samples = [i for i, sample in enumerate(samples) if len(sample) > MAX_SAMPLE_LENGTH]
    if long_samples:
        return RegexTestResult(
            valid_pattern=False,
            results=[],
            error=f"Sample(s) at indices {long_samples[:5]} exceed MAX_SAMPLE_LENGTH {MAX_SAMPLE_LENGTH}",
            flags_used=flags_used,
        )

    is_safe, error_msg = _check_pattern_complexity(pattern)
    if not is_safe:
        return RegexTestResult(
            valid_pattern=False,
            results=[],
            error=error_msg,
            flags_used=flags_used,
        )

    flag_values = 0
    flag_map = {
        "IGNORECASE": re.IGNORECASE,
        "MULTILINE": re.MULTILINE,
        "DOTALL": re.DOTALL,
        "UNICODE": re.UNICODE,
        "DEBUG": re.DEBUG,
        "VERBOSE": re.VERBOSE,
    }
    if flags:
        for flag_name in flags:
            if flag_name in flag_map:
                flag_values |= flag_map[flag_name]
    if ignore_case:
        flag_values |= re.IGNORECASE
    if multiline:
        flag_values |= re.MULTILINE
    if dotall:
        flag_values |= re.DOTALL
    if ascii:
        flag_values |= re.ASCII

    try:
        compiled = re.compile(pattern, flag_values)
    except re.error as e:
        return RegexTestResult(
            valid_pattern=False,
            results=[],
            error=str(e),
            flags_used=flags_used,
        )

    results: list[RegexMatch] = []
    for sample in samples:
        match = compiled.search(sample)
        if match is None:
            results.append(
                RegexMatch(
                    sample=sample,
                    matches=False,
                    fullmatch=False,
                    span=None,
                    groups=[],
                    groupdict={},
                )
            )
        else:
            full_match = compiled.fullmatch(sample)
            span = list(match.span()) if match else None
            groups = list(match.groups())
            groupdict = match.groupdict() if match else {}

            results.append(
                RegexMatch(
                    sample=sample,
                    matches=True,
                    fullmatch=full_match is not None,
                    span=span,
                    groups=groups,
                    groupdict=groupdict,
                )
            )

    return RegexTestResult(
        valid_pattern=True,
        results=results,
        error=None,
        flags_used=flags_used,
    )


def regex_replace_preview(
    pattern: str,
    replacement: str,
    samples: list[str],
    ignore_case: bool = False,
    multiline: bool = False,
    dotall: bool = False,
    ascii: bool = False,
) -> dict:
    """Preview regex replacements on sample strings.

    Args:
        pattern: Regular expression pattern.
        replacement: Replacement string.
        samples: List of strings to test.
        ignore_case: Use IGNORECASE flag.
        multiline: Use MULTILINE flag.
        dotall: Use DOTALL flag.
        ascii: Use ASCII flag.

    Returns:
        Dictionary with previews of replacements.

    Raises:
        ValueError: If samples list exceeds MAX_LIST_ITEMS or pattern
            exceeds MAX_PATTERN_LENGTH.
    """
    if len(samples) > MAX_LIST_ITEMS:
        raise ValueError(f"Samples count {len(samples)} exceeds maximum {MAX_LIST_ITEMS}")
    long_samples = [
        i for i, s in enumerate(samples) if not isinstance(s, str) or len(s) > MAX_SAMPLE_LENGTH
    ]
    if long_samples:
        raise ValueError(
            f"Sample(s) at indices {long_samples[:5]} exceed MAX_SAMPLE_LENGTH {MAX_SAMPLE_LENGTH}"
        )
    is_safe, error_msg = _check_pattern_complexity(pattern)
    if not is_safe:
        return {
            "valid_pattern": False,
            "error": error_msg,
            "previews": [],
        }

    flag_values = 0
    if ignore_case:
        flag_values |= re.IGNORECASE
    if multiline:
        flag_values |= re.MULTILINE
    if dotall:
        flag_values |= re.DOTALL
    if ascii:
        flag_values |= re.ASCII

    try:
        compiled = re.compile(pattern, flag_values)
    except re.error as e:
        return {
            "valid_pattern": False,
            "error": str(e),
            "previews": [],
        }

    previews: list[RegexMatchPreview] = []
    for sample in samples:
        try:
            new_text, count = compiled.subn(replacement, sample)
            previews.append(
                RegexMatchPreview(
                    sample=sample,
                    original=sample,
                    replacement=new_text,
                    changed=count > 0,
                )
            )
        except Exception:
            previews.append(
                RegexMatchPreview(
                    sample=sample,
                    original=sample,
                    replacement=sample,
                    changed=False,
                )
            )

    return {
        "valid_pattern": True,
        "error": None,
        "previews": previews,
    }


def _get_json_type(value: Any) -> str:
    """Get type string for a JSON value."""
    if value is None:
        return "null"
    elif isinstance(value, bool):
        return "boolean"
    elif isinstance(value, int):
        return "integer"
    elif isinstance(value, float):
        return "float"
    elif isinstance(value, str):
        return "string"
    elif isinstance(value, list):
        return "array"
    elif isinstance(value, dict):
        return "object"
    else:
        return type(value).__name__


def _value_preview(value: Any, max_len: int = 30) -> str | None:
    """Create a preview string for a JSON value."""
    if value is None:
        return "null"
    elif isinstance(value, bool):
        return "true" if value else "false"
    elif isinstance(value, (int, float)):
        s = str(value)
        return s if len(s) <= max_len else s[: max_len - 3] + "..."
    elif isinstance(value, str):
        if len(value) <= max_len:
            return f'"{value}"'
        else:
            return f'"{value[:max_len - 3]}..."'
    elif isinstance(value, list):
        return f"[{len(value)} items]"
    elif isinstance(value, dict):
        return f"{{{len(value)} keys}}"
    return str(type(value).__name__)


def _is_serializable(value: Any) -> bool:
    """Check if a value can be serialized for comparison."""
    if value is None:
        return True
    elif isinstance(value, (bool, int, float, str)):
        return True
    elif isinstance(value, dict):
        return all(isinstance(k, str) for k in value.keys()) and all(
            _is_serializable(v) for v in value.values()
        )
    elif isinstance(value, list):
        return all(_is_serializable(v) for v in value)
    return False


def _canonicalize_for_compare(value: Any) -> Any:
    """Convert value to canonical form for comparison."""
    if value is None:
        return None
    elif isinstance(value, bool):
        return value
    elif isinstance(value, (int, float)):
        return value
    elif isinstance(value, str):
        return value
    elif isinstance(value, dict):
        return {k: _canonicalize_for_compare(v) for k, v in sorted(value.items())}
    elif isinstance(value, list):
        return [_canonicalize_for_compare(v) for v in value]
    return value


def json_compare(
    a: str,
    b: str,
    ignore_object_order: bool = True,
    ignore_array_order: bool = False,
    numeric_string_equivalence: bool = False,
    casefold_keys: bool = False,
    treat_missing_null_as_equal: bool = False,
    max_diffs: int = 50,
) -> JsonCompareResult:
    """Compare two JSON documents semantically.

    Args:
        a: First JSON document string.
        b: Second JSON document string.
        ignore_object_order: Sort object keys for comparison.
        ignore_array_order: Sort arrays if all items are serializable.
        numeric_string_equivalence: Treat numeric strings as numbers.
        casefold_keys: Casefold object keys before comparison.
        treat_missing_null_as_equal: Treat missing and null as equal.
        max_diffs: Maximum number of differences to report.

    Returns:
        Dictionary with comparison results including diffs and summary.

    Raises:
        ValueError: If either input string exceeds MAX_INPUT_LENGTH.
    """
    if len(a) > MAX_INPUT_LENGTH:
        raise ValueError(f"Input 'a' length {len(a)} exceeds maximum {MAX_INPUT_LENGTH}")
    if len(b) > MAX_INPUT_LENGTH:
        raise ValueError(f"Input 'b' length {len(b)} exceeds maximum {MAX_INPUT_LENGTH}")
    diffs: list[JsonCompareDiff] = []
    valid_json_a = True
    valid_json_b = True
    parsed_a: Any = None
    parsed_b: Any = None
    equal = False
    type_match = True

    try:
        parsed_a = json.loads(a)
    except json.JSONDecodeError as e:
        valid_json_a = False
        diffs.append(
            JsonCompareDiff(
                path="",
                kind="parse_error_a",
                a_type=None,
                b_type=None,
                a_preview=f"Line {e.lineno}, Col {e.colno}: {e.msg}",
                b_preview=None,
            )
        )

    try:
        parsed_b = json.loads(b)
    except json.JSONDecodeError as e:
        valid_json_b = False
        diffs.append(
            JsonCompareDiff(
                path="",
                kind="parse_error_b",
                a_type=None,
                b_type=None,
                a_preview=None,
                b_preview=f"Line {e.lineno}, Col {e.colno}: {e.msg}",
            )
        )

    if not valid_json_a or not valid_json_b:
        return JsonCompareResult(
            valid_json_a=valid_json_a,
            valid_json_b=valid_json_b,
            equal=False,
            same_type=False,
            diff_count=len(diffs),
            diffs=diffs[:max_diffs],
            truncated=len(diffs) > max_diffs,
            summary="One or both inputs are not valid JSON",
        )

    def _normalize_key(key: str) -> str:
        return key.casefold() if casefold_keys else key

    def _types_equal(a_val: Any, b_val: Any) -> bool:
        a_type = _get_json_type(a_val)
        b_type = _get_json_type(b_val)
        if a_type != b_type:
            return False
        if numeric_string_equivalence and a_type == "string":
            try:
                float(a_val)
                return True
            except (ValueError, TypeError):
                pass
        return True

    def _compare_values(path: str, a_val: Any, b_val: Any, _depth: int = 0) -> None:
        nonlocal type_match
        if _depth > 100:
            return
        if len(diffs) >= max_diffs:
            return

        if treat_missing_null_as_equal:
            if a_val is None or b_val is None:
                return

        a_type = _get_json_type(a_val)
        b_type = _get_json_type(b_val)

        if numeric_string_equivalence and a_type != b_type:
            if (a_type == "string" and b_type in ("integer", "float")) or (
                b_type == "string" and a_type in ("integer", "float")
            ):
                try:
                    num_a = float(a_val)
                    num_b = float(b_val)
                    if num_a == num_b:
                        return
                    type_match = False
                    diffs.append(
                        JsonCompareDiff(
                            path=path,
                            kind="value_changed",
                            a_type=a_type,
                            b_type=b_type,
                            a_preview=_value_preview(a_val),
                            b_preview=_value_preview(b_val),
                        )
                    )
                    return
                except (ValueError, TypeError):
                    pass

        if a_type != b_type:
            if treat_missing_null_as_equal:
                a_is_null = a_val is None
                b_is_null = b_val is None
                if not (a_is_null or b_is_null):
                    type_match = False
                    diffs.append(
                        JsonCompareDiff(
                            path=path,
                            kind="type_changed",
                            a_type=a_type,
                            b_type=b_type,
                            a_preview=_value_preview(a_val),
                            b_preview=_value_preview(b_val),
                        )
                    )
                    return
            else:
                type_match = False
                diffs.append(
                    JsonCompareDiff(
                        path=path,
                        kind="type_changed",
                        a_type=a_type,
                        b_type=b_type,
                        a_preview=_value_preview(a_val),
                        b_preview=_value_preview(b_val),
                    )
                )
                return

        if numeric_string_equivalence and a_type == "string" and b_type == "string":
            try:
                num_a = float(a_val)
                num_b = float(b_val)
                if num_a == num_b:
                    return
            except (ValueError, TypeError):
                pass

        if a_type == "object":
            a_keys = set(a_val.keys())
            b_keys = set(b_val.keys())

            if casefold_keys:
                a_keys = {_normalize_key(k) for k in a_keys}
                b_keys = {_normalize_key(k) for k in b_keys}

            keys_a = {_normalize_key(k): k for k in a_val.keys()}
            keys_b = {_normalize_key(k): k for k in b_val.keys()}

            if not ignore_object_order:
                a_key_order = list(a_val.keys())
                b_key_order = list(b_val.keys())
                len_a = len(a_key_order)
                len_b = len(b_key_order)
                min_len = min(len_a, len_b)
                for i in range(min_len):
                    a_key = a_key_order[i]
                    b_key = b_key_order[i]
                    if _normalize_key(a_key) != _normalize_key(b_key):
                        type_match = False
                        diffs.append(
                            JsonCompareDiff(
                                path=f"{path}/{a_key}" if path else f"/{a_key}",
                                kind="key_missing_in_b",
                                a_type=_get_json_type(a_val[a_key]),
                                b_type=None,
                                a_preview=_value_preview(a_val[a_key]),
                                b_preview=None,
                            )
                        )
                        break
                if len_a != len_b:
                    type_match = False
                    longer = a_key_order if len_a > len_b else b_key_order
                    diffs.append(
                        JsonCompareDiff(
                            path=path,
                            kind="array_length_changed",
                            a_type="object",
                            b_type="object",
                            a_preview=f"{len_a} keys",
                            b_preview=f"{len_b} keys",
                        )
                    )
                return

            for key in sorted(a_keys - b_keys):
                orig_key = keys_a[key]
                if treat_missing_null_as_equal:
                    if a_val[orig_key] is not None:
                        type_match = False
                        diffs.append(
                            JsonCompareDiff(
                                path=f"{path}/{orig_key}" if path else f"/{orig_key}",
                                kind="key_missing_in_b",
                                a_type=_get_json_type(a_val[orig_key]),
                                b_type=None,
                                a_preview=_value_preview(a_val[orig_key]),
                                b_preview=None,
                            )
                        )
                else:
                    type_match = False
                    diffs.append(
                        JsonCompareDiff(
                            path=f"{path}/{orig_key}" if path else f"/{orig_key}",
                            kind="key_missing_in_b",
                            a_type=_get_json_type(a_val[orig_key]),
                            b_type=None,
                            a_preview=_value_preview(a_val[orig_key]),
                            b_preview=None,
                        )
                    )

            for key in sorted(b_keys - a_keys):
                orig_key = keys_b[key]
                if treat_missing_null_as_equal:
                    if b_val[orig_key] is not None:
                        type_match = False
                        diffs.append(
                            JsonCompareDiff(
                                path=f"{path}/{orig_key}" if path else f"/{orig_key}",
                                kind="key_missing_in_a",
                                a_type=None,
                                b_type=_get_json_type(b_val[orig_key]),
                                a_preview=None,
                                b_preview=_value_preview(b_val[orig_key]),
                            )
                        )
                else:
                    type_match = False
                    diffs.append(
                        JsonCompareDiff(
                            path=f"{path}/{orig_key}" if path else f"/{orig_key}",
                            kind="key_missing_in_a",
                            a_type=None,
                            b_type=_get_json_type(b_val[orig_key]),
                            a_preview=None,
                            b_preview=_value_preview(b_val[orig_key]),
                        )
                    )

            common_keys = a_keys & b_keys
            for key in sorted(common_keys):
                orig_key_a = keys_a[key]
                orig_key_b = keys_b[key]
                new_path = f"{path}/{orig_key_a}" if path else f"/{orig_key_a}"
                if orig_key_a != orig_key_b:
                    new_path = f"{path}/{orig_key_a}->{orig_key_b}"
                _compare_values(new_path, a_val[orig_key_a], b_val[orig_key_b], _depth + 1)

        elif a_type == "array":
            if len(a_val) != len(b_val):
                type_match = False
                diffs.append(
                    JsonCompareDiff(
                        path=path,
                        kind="array_length_changed",
                        a_type=a_type,
                        b_type=b_type,
                        a_preview=f"{len(a_val)} items",
                        b_preview=f"{len(b_val)} items",
                    )
                )
                return

            if ignore_array_order and _is_serializable(a_val) and _is_serializable(b_val):
                norm_a = sorted(_canonicalize_for_compare(v) for v in a_val)
                norm_b = sorted(_canonicalize_for_compare(v) for v in b_val)
                if norm_a == norm_b:
                    return
                for i in range(len(norm_a)):
                    _compare_values(f"{path}/[{i}]", norm_a[i], norm_b[i], _depth + 1)
            else:
                for i, (item_a, item_b) in enumerate(zip(a_val, b_val)):
                    _compare_values(f"{path}/[{i}]", item_a, item_b, _depth + 1)

        else:
            if a_val != b_val:
                type_match = False
                diffs.append(
                    JsonCompareDiff(
                        path=path,
                        kind="value_changed",
                        a_type=a_type,
                        b_type=b_type,
                        a_preview=_value_preview(a_val),
                        b_preview=_value_preview(b_val),
                    )
                )

    _compare_values("", parsed_a, parsed_b)
    truncated = len(diffs) >= max_diffs
    diffs = diffs[:max_diffs]
    equal = len(diffs) == 0

    if equal:
        summary = "JSON documents are equal"
    else:
        summary = f"JSON documents differ at {len(diffs)} path{'s' if len(diffs) != 1 else ''}"

    return JsonCompareResult(
        valid_json_a=True,
        valid_json_b=True,
        equal=equal,
        same_type=type_match,
        diff_count=len(diffs),
        diffs=diffs,
        truncated=truncated,
        summary=summary,
    )


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


class SchemaViolation(TypedDict):
    """A single schema validation violation."""

    path: str
    message: str
    value_type: str | None
    expected_type: str | None


class ValidateSchemaLightResult(TypedDict):
    """Result of light schema validation."""

    valid: bool
    violations: list[SchemaViolation]
    truncated: bool
    summary: str


def _decode_pointer_token(token: str) -> str:
    """Decode RFC 6901 escape sequences in a pointer token.

    Args:
        token: Encoded token from JSON pointer.

    Returns:
        Decoded token with ~1 -> / and ~0 -> ~
    """
    return token.replace("~1", "/").replace("~0", "~")


def _encode_pointer_token(token: str) -> str:
    """Encode a key for use in a JSON pointer.

    Args:
        token: Raw token string.

    Returns:
        Encoded token with / -> ~1 and ~ -> ~0
    """
    return token.replace("~", "~0").replace("/", "~1")


def json_extract(text: str, pointer: str = "", max_output_chars: int = 4000) -> JsonExtractResult:
    """Extract a value from JSON using RFC 6901 JSON Pointer.

    Args:
        text: JSON document string.
        pointer: RFC 6901 JSON Pointer path (e.g., "/foo/bar/0").
                 Empty string means the whole document.
        max_output_chars: Maximum characters for preview string.

    Returns:
        Dictionary with extraction result including value, type, preview,
        and for missing values: reason, available_keys, and missing_at.

    Raises:
        ValueError: If input exceeds MAX_INPUT_LENGTH.
    """
    if len(text) > MAX_INPUT_LENGTH:
        raise ValueError(f"Input length {len(text)} exceeds MAX_INPUT_LENGTH {MAX_INPUT_LENGTH}")

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        return JsonExtractResult(
            valid_json=False,
            found=False,
            pointer=pointer,
            value_type=None,
            value=None,
            preview=None,
            child_keys=None,
            array_length=None,
            truncated=False,
            missing_at=None,
            reason="invalid_json",
            available_keys=None,
            error=e.msg,
            line=e.lineno,
            column=e.colno,
            summary=f"Invalid JSON: {e.msg} at line {e.lineno}, column {e.colno}",
        )

    if pointer == "":
        return _build_found_result(parsed, pointer, max_output_chars)

    tokens = pointer.split("/")
    if tokens and tokens[0] == "":
        tokens = tokens[1:]

    current = parsed
    path_so_far = ""

    for i, token in enumerate(tokens):
        decoded = _decode_pointer_token(token)
        path_so_far = "/" + "/".join(_encode_pointer_token(t) for t in tokens[: i + 1])

        if isinstance(current, dict):
            if decoded in current:
                current = current[decoded]
            else:
                return JsonExtractResult(
                    valid_json=True,
                    found=False,
                    pointer=pointer,
                    value_type="object",
                    value=None,
                    preview=None,
                    child_keys=None,
                    array_length=None,
                    truncated=False,
                    missing_at=path_so_far,
                    reason="key_not_found",
                    available_keys=list(current.keys()),
                    error=None,
                    line=None,
                    column=None,
                    summary=f"Key '{decoded}' not found in object at {path_so_far}",
                )
        elif isinstance(current, list):
            try:
                index = int(decoded)
            except ValueError:
                return JsonExtractResult(
                    valid_json=True,
                    found=False,
                    pointer=pointer,
                    value_type="array",
                    value=None,
                    preview=None,
                    child_keys=None,
                    array_length=len(current),
                    truncated=False,
                    missing_at=path_so_far,
                    reason="invalid_pointer_syntax",
                    available_keys=None,
                    error=None,
                    line=None,
                    column=None,
                    summary=f"Array index expected at {path_so_far}, got non-integer '{decoded}'",
                )

            if index < 0 or index >= len(current):
                return JsonExtractResult(
                    valid_json=True,
                    found=False,
                    pointer=pointer,
                    value_type="array",
                    value=None,
                    preview=None,
                    child_keys=None,
                    array_length=len(current),
                    truncated=False,
                    missing_at=path_so_far,
                    reason="index_out_of_range",
                    available_keys=None,
                    error=None,
                    line=None,
                    column=None,
                    summary=f"Index {index} out of range for array of length {len(current)} at {path_so_far}",
                )
            current = current[index]
        else:
            return JsonExtractResult(
                valid_json=True,
                found=False,
                pointer=pointer,
                value_type=type(current).__name__,
                value=None,
                preview=None,
                child_keys=None,
                array_length=None,
                truncated=False,
                missing_at=path_so_far,
                reason="invalid_pointer_syntax",
                available_keys=None,
                error=None,
                line=None,
                column=None,
                summary=f"Cannot index into {type(current).__name__} at {path_so_far}",
            )

    return _build_found_result(current, pointer, max_output_chars)


def _build_found_result(value: Any, pointer: str, max_output_chars: int) -> JsonExtractResult:
    """Build a found result for a value."""
    if isinstance(value, dict):
        child_keys = list(value.keys())
        preview = json.dumps(value, ensure_ascii=False)[:max_output_chars]
        truncated = len(json.dumps(value, ensure_ascii=False)) > max_output_chars
        return JsonExtractResult(
            valid_json=True,
            found=True,
            pointer=pointer,
            value_type="object",
            value=value,
            preview=preview,
            child_keys=child_keys,
            array_length=None,
            truncated=truncated,
            missing_at=None,
            reason=None,
            available_keys=None,
            error=None,
            line=None,
            column=None,
            summary=f"Object with {len(child_keys)} keys" + (" (truncated)" if truncated else ""),
        )
    elif isinstance(value, list):
        preview = json.dumps(value, ensure_ascii=False)[:max_output_chars]
        truncated = len(json.dumps(value, ensure_ascii=False)) > max_output_chars
        return JsonExtractResult(
            valid_json=True,
            found=True,
            pointer=pointer,
            value_type="array",
            value=value,
            preview=preview,
            child_keys=None,
            array_length=len(value),
            truncated=truncated,
            missing_at=None,
            reason=None,
            available_keys=None,
            error=None,
            line=None,
            column=None,
            summary=f"Array of {len(value)} elements" + (" (truncated)" if truncated else ""),
        )
    elif isinstance(value, str):
        return JsonExtractResult(
            valid_json=True,
            found=True,
            pointer=pointer,
            value_type="string",
            value=value,
            preview=value[:max_output_chars],
            child_keys=None,
            array_length=None,
            truncated=len(value) > max_output_chars,
            missing_at=None,
            reason=None,
            available_keys=None,
            error=None,
            line=None,
            column=None,
            summary=f"String: \"{value[:50]}{'...' if len(value) > 50 else ''}\"",
        )
    elif isinstance(value, bool):
        return JsonExtractResult(
            valid_json=True,
            found=True,
            pointer=pointer,
            value_type="boolean",
            value=value,
            preview=str(value).lower(),
            child_keys=None,
            array_length=None,
            truncated=False,
            missing_at=None,
            reason=None,
            available_keys=None,
            error=None,
            line=None,
            column=None,
            summary=f"Boolean: {str(value).lower()}",
        )
    elif value is None:
        return JsonExtractResult(
            valid_json=True,
            found=True,
            pointer=pointer,
            value_type="null",
            value=None,
            preview="null",
            child_keys=None,
            array_length=None,
            truncated=False,
            missing_at=None,
            reason=None,
            available_keys=None,
            error=None,
            line=None,
            column=None,
            summary="null",
        )
    else:
        return JsonExtractResult(
            valid_json=True,
            found=True,
            pointer=pointer,
            value_type="number",
            value=value,
            preview=str(value),
            child_keys=None,
            array_length=None,
            truncated=False,
            missing_at=None,
            reason=None,
            available_keys=None,
            error=None,
            line=None,
            column=None,
            summary=f"Number: {value}",
        )


MAX_SCHEMA_VIOLATIONS = 100


class JsonShapeKey(TypedDict):
    """A single key in json_shape result."""

    type: str
    keys: dict[str, JsonShapeKey] | None
    key_count: int | None
    item_types: list[str] | None
    item_count: int | None


class JsonShapeResult(TypedDict):
    """Result of JSON shape analysis."""

    valid: bool
    shape: JsonShapeKey | None
    truncated: bool
    summary: str


def json_shape(
    text: str, max_depth: int = 4, max_keys: int = 100, max_array_items: int = 5
) -> JsonShapeResult:
    """Analyze the structure of a JSON document without returning values.

    Args:
        text: JSON document string.
        max_depth: Maximum depth for nested structure (default 4).
        max_keys: Maximum keys to show per object (default 100).
        max_array_items: Maximum array item previews (default 5).

    Returns:
        Dictionary with valid (bool), shape (nested structure), and truncated (bool).

    Raises:
        ValueError: If input exceeds MAX_INPUT_LENGTH.
    """
    if len(text) > MAX_INPUT_LENGTH:
        raise ValueError(f"Input length {len(text)} exceeds MAX_INPUT_LENGTH {MAX_INPUT_LENGTH}")

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        return JsonShapeResult(
            valid=False,
            shape=None,
            truncated=False,
            summary=f"Invalid JSON: {e.msg} at line {e.lineno}, column {e.colno}",
        )

    def _analyze_shape(value: Any, depth: int) -> JsonShapeKey:
        """Recursively analyze shape of a value."""
        if isinstance(value, dict):
            key_count = len(value)
            if depth >= max_depth:
                return JsonShapeKey(
                    type="object",
                    keys=None,
                    key_count=key_count,
                    item_types=None,
                    item_count=None,
                )

            keys: dict[str, JsonShapeKey] = {}
            shown_keys = 0

            for k, v in value.items():
                if shown_keys >= max_keys:
                    break
                keys[k] = _analyze_shape(v, depth + 1)
                shown_keys += 1

            return JsonShapeKey(
                type="object",
                keys=keys if keys else None,
                key_count=key_count if key_count > len(keys) else None,
                item_types=None,
                item_count=None,
            )
        elif isinstance(value, list):
            item_count = len(value)
            if depth >= max_depth:
                return JsonShapeKey(
                    type="array",
                    keys=None,
                    key_count=None,
                    item_types=None,
                    item_count=item_count,
                )

            item_types: list[str] = []
            shown_items = 0

            for item in value:
                if shown_items >= max_array_items:
                    break
                item_types.append(_analyze_shape(item, depth + 1)["type"])
                shown_items += 1

            return JsonShapeKey(
                type="array",
                keys=None,
                key_count=None,
                item_types=item_types if item_types else None,
                item_count=item_count,
            )
        else:
            type_name = _get_json_type(value)
            return JsonShapeKey(
                type=type_name,
                keys=None,
                key_count=None,
                item_types=None,
                item_count=None,
            )

    shape = _analyze_shape(parsed, 0)
    truncated = False

    return JsonShapeResult(
        valid=True,
        shape=shape,
        truncated=truncated,
        summary=_build_shape_summary(shape),
    )


def _build_shape_summary(shape: JsonShapeKey) -> str:
    """Build a human-readable summary of the shape."""
    shape_type = shape["type"]
    if shape_type == "object":
        keys = shape.get("keys")
        key_count = shape.get("key_count") or (len(keys) if keys else 0)
        if keys:
            sub_summaries = []
            for k, v in list(keys.items())[:3]:
                sub_summaries.append(f"{k}: {_build_shape_summary(v)}")
            if len(keys) > 3:
                return f"object with {key_count} keys ({{{', '.join(sub_summaries)}, ...}})"
            return f"object with {key_count} keys ({{{', '.join(sub_summaries)}}})"
        return f"object with {key_count} keys"
    elif shape_type == "array":
        item_types = shape.get("item_types")
        item_count = shape.get("item_count") or (len(item_types) if item_types else 0)
        if item_types:
            unique_types = list(dict.fromkeys(item_types))
            if len(unique_types) == 1:
                return f"array of {unique_types[0]} with {item_count} items"
            return f"array with {item_count} items ([{', '.join(unique_types)}, ...])"
        return f"array with {item_count} items"
    else:
        return shape_type


MAX_TEXT_LENGTH_REGEX = 100_000
MAX_PATTERN_LENGTH_REGEX = 1000
MAX_MATCHES = 100
MAX_GROUPS = 100


class RegexFindIterMatch(TypedDict, total=False):
    """A single regex match found by regex_finditer."""

    match: str
    span: list[int]
    line: int
    column: int
    groups: list[str]
    groupdict: dict[str, str]


class RegexFindIterResult(TypedDict):
    """Result of regex_finditer."""

    valid_pattern: bool
    matches: list[RegexFindIterMatch]
    truncated: bool
    match_count: int
    error: str | None


def _get_line_column_for_index(text: str, index: int) -> tuple[int, int]:
    """Get 1-based line and column for a string index.

    Uses precomputed newline index for O(log N) lookup.

    Args:
        text: Input string.
        index: Character index.

    Returns:
        Tuple of (line, column), both 1-based.
    """
    newlines = _build_newline_index(text)
    return _get_line_column_from_index(newlines, index)


def regex_finditer(
    pattern: str,
    text: str,
    flags: list[str] | None = None,
    max_matches: int = MAX_MATCHES,
    include_line_column: bool = True,
    include_groups: bool = True,
) -> RegexFindIterResult:
    """Find all regex matches in text with positions.

    Args:
        pattern: Regular expression pattern.
        text: Input string to search.
        flags: List of flag names (IGNORECASE, MULTILINE, DOTALL, etc.).
        max_matches: Maximum number of matches to return (default 100).
        include_line_column: Include line and column info (default True).
        include_groups: Include capture groups (default True).

    Returns:
        Dictionary with valid_pattern (bool), matches (list), truncated (bool),
        match_count (int), and error (str if invalid).

    Raises:
        ValueError: If text exceeds MAX_TEXT_LENGTH_REGEX.
    """
    if len(text) > MAX_TEXT_LENGTH_REGEX:
        raise ValueError(
            f"Text length {len(text)} exceeds MAX_TEXT_LENGTH_REGEX {MAX_TEXT_LENGTH_REGEX}"
        )

    if len(pattern) > MAX_PATTERN_LENGTH_REGEX:
        return RegexFindIterResult(
            valid_pattern=False,
            matches=[],
            truncated=False,
            match_count=0,
            error=f"Pattern length {len(pattern)} exceeds maximum {MAX_PATTERN_LENGTH_REGEX}",
        )

    is_safe, error_msg = _check_pattern_complexity(pattern)
    if not is_safe:
        return RegexFindIterResult(
            valid_pattern=False,
            matches=[],
            truncated=False,
            match_count=0,
            error=error_msg,
        )

    flag_values = 0
    flag_map = {
        "IGNORECASE": re.IGNORECASE,
        "MULTILINE": re.MULTILINE,
        "DOTALL": re.DOTALL,
        "UNICODE": re.UNICODE,
        "VERBOSE": re.VERBOSE,
    }
    if flags:
        for flag_name in flags:
            if flag_name in flag_map:
                flag_values |= flag_map[flag_name]

    try:
        compiled = re.compile(pattern, flag_values)
    except re.error as e:
        return RegexFindIterResult(
            valid_pattern=False,
            matches=[],
            truncated=False,
            match_count=0,
            error=str(e),
        )

    matches: list[RegexFindIterMatch] = []
    match_count = 0
    truncated = False

    for match in compiled.finditer(text):
        match_count += 1
        if len(matches) >= max_matches:
            truncated = True
            continue

        span = list(match.span())
        groups = list(match.groups()) if include_groups else []
        groupdict = match.groupdict() if include_groups else {}

        if len(groups) > MAX_GROUPS:
            groups = groups[:MAX_GROUPS]

        match_dict: RegexFindIterMatch = RegexFindIterMatch(
            match=match.group(),
            span=span,
            groups=groups,
            groupdict=groupdict,
        )

        if include_line_column:
            line, column = _get_line_column_for_index(text, match.start())
            match_dict["line"] = line
            match_dict["column"] = column

        matches.append(match_dict)

    return RegexFindIterResult(
        valid_pattern=True,
        matches=matches,
        truncated=truncated,
        match_count=match_count,
        error=None,
    )


class RegexSafetyFinding(TypedDict):
    """A single safety finding for a regex pattern."""

    kind: str
    span: list[int]
    message: str


class RegexSafetyResult(TypedDict):
    """Result of regex safety check."""

    valid_pattern: bool
    risk: str
    findings: list[RegexSafetyFinding]


def regex_safety_check(pattern: str) -> RegexSafetyResult:
    """Check regex pattern for potential catastrophic backtracking risks.

    This is a heuristic check and does not guarantee safety.

    Args:
        pattern: Regular expression pattern to check.

    Returns:
        Dictionary with valid_pattern (bool), risk (low/medium/high), and findings (list).
    """
    findings: list[RegexSafetyFinding] = []

    try:
        re.compile(pattern)
    except re.error:
        return RegexSafetyResult(
            valid_pattern=False,
            risk="low",
            findings=[],
        )

    is_safe, error_msg = _check_pattern_complexity(pattern)
    if not is_safe:
        findings.append(
            RegexSafetyFinding(
                kind="complexity",
                span=[0, len(pattern)],
                message=error_msg or "Pattern is too complex",
            )
        )
        return RegexSafetyResult(
            valid_pattern=True,
            risk="high",
            findings=findings,
        )

    i = 0
    paren_depth = 0
    has_inner_quantifier = False
    last_paren_end = -1

    while i < len(pattern):
        char = pattern[i]

        if char == '\\' and i + 1 < len(pattern):
            i += 2
            continue

        if char == '[':
            i += 1
            while i < len(pattern):
                if pattern[i] == '\\' and i + 1 < len(pattern):
                    i += 2
                    continue
                if pattern[i] == ']':
                    break
                i += 1
            i += 1
            continue

        if char == '(':
            paren_depth += 1
            has_inner_quantifier = False
            i += 1
            continue

        if char == ')':
            last_paren_end = i
            paren_depth -= 1
            i += 1
            continue

        if char in '+*':
            j = i + 1
            while j < len(pattern) and pattern[j] == char:
                j += 1
            if j < len(pattern) and pattern[j] == '?':
                j += 1

            if paren_depth > 0:
                if has_inner_quantifier:
                    findings.append(
                        RegexSafetyFinding(
                            kind="nested_quantifier",
                            span=[i, j],
                            message="Nested quantifiers may cause catastrophic backtracking",
                        )
                    )
                has_inner_quantifier = True
            elif paren_depth == 0 and last_paren_end > 0:
                if has_inner_quantifier:
                    findings.append(
                        RegexSafetyFinding(
                            kind="nested_quantifier",
                            span=[i, j],
                            message="Quantifier after group with quantifier may cause catastrophic backtracking",
                        )
                    )

            i = j
            continue

        if char == '{':
            j = i + 1
            while j < len(pattern) and pattern[j] != '}':
                j += 1
            if j < len(pattern):
                j += 1

            if paren_depth > 0:
                if has_inner_quantifier:
                    findings.append(
                        RegexSafetyFinding(
                            kind="nested_quantifier",
                            span=[i, j],
                            message="Nested quantifiers may cause catastrophic backtracking",
                        )
                    )
                has_inner_quantifier = True

            i = j
            continue

        i += 1

    backref_pattern = re.compile(r'\\([1-9])|\\g<')
    if backref_pattern.search(pattern):
        findings.append(
            RegexSafetyFinding(
                kind="backreference",
                span=[0, len(pattern)],
                message="Backreferences can cause exponential matching in some cases",
            )
        )

    ambiguous_dot = re.compile(r'\.\*')
    for match in ambiguous_dot.finditer(pattern):
        span = list(match.span())
        findings.append(
            RegexSafetyFinding(
                kind="ambiguous_dot_star",
                span=span,
                message="Ambiguous dot-star pattern",
            )
        )

    if findings:
        high_risk = any(f["kind"] in ("nested_quantifier",) for f in findings)
        risk = "high" if high_risk else "medium"
    else:
        risk = "low"

    return RegexSafetyResult(
        valid_pattern=True,
        risk=risk,
        findings=findings,
    )


def _get_type_name(value: Any) -> str:
    """Get type name for schema validation."""
    if value is None:
        return "null"
    elif isinstance(value, bool):
        return "boolean"
    elif isinstance(value, int):
        return "integer"
    elif isinstance(value, float):
        return "number"
    elif isinstance(value, str):
        return "string"
    elif isinstance(value, list):
        return "array"
    elif isinstance(value, dict):
        return "object"
    else:
        return type(value).__name__


def validate_schema_light(data: Any, schema: dict) -> ValidateSchemaLightResult:
    """Validate data against a simple schema format.

    This is NOT full JSON Schema - it's a simple internal schema format.

    Supported schema features:
    - type: object, array, string, number, integer, boolean, null
    - required: list of required keys
    - properties: nested property definitions
    - additional_properties: false to disallow extra keys
    - enum: list of allowed values
    - min_length, max_length: for strings
    - min_items, max_items: for arrays
    - pattern: regex pattern for strings
    - items: schema for array items (nested validation)

    Args:
        data: Data to validate (already parsed JSON).
        schema: Schema definition dict.

    Returns:
        Dictionary with valid (bool), violations (list), truncated (bool),
        and summary (str).
    """
    violations: list[SchemaViolation] = []
    _walk_count = 0

    def _add_violation(
        path: str, message: str, value_type: str | None = None, expected_type: str | None = None
    ) -> None:
        if len(violations) < MAX_SCHEMA_VIOLATIONS:
            violations.append(
                SchemaViolation(
                    path=path,
                    message=message,
                    value_type=value_type,
                    expected_type=expected_type,
                )
            )

    def _validate(path: str, value: Any, schema_def: dict, depth: int = 0) -> None:
        nonlocal _walk_count
        _walk_count += 1
        if _walk_count > MAX_SCHEMA_ELEMENTS:
            return
        if len(violations) >= MAX_SCHEMA_VIOLATIONS:
            return
        if depth > MAX_SCHEMA_DEPTH:
            _add_violation(
                path,
                f"schema nesting depth {depth} exceeds maximum {MAX_SCHEMA_DEPTH}",
                _get_type_name(value),
                None,
            )
            return

        expected_type = schema_def.get("type")

        if expected_type is not None:
            actual_type = _get_type_name(value)
            type_map = {
                "object": "object",
                "array": "array",
                "string": "string",
                "number": ("number", "integer"),
                "integer": "integer",
                "boolean": "boolean",
                "null": "null",
            }
            allowed_types = type_map.get(expected_type, (expected_type,))
            if actual_type not in allowed_types and not (
                expected_type == "number" and actual_type == "integer"
            ):
                _add_violation(
                    path,
                    f"expected {expected_type}, got {actual_type}",
                    actual_type,
                    expected_type,
                )
                return

        if expected_type == "object" and isinstance(value, dict):
            required = schema_def.get("required", [])
            for req_key in required:
                if req_key not in value:
                    _add_violation(
                        f"{path}/{req_key}" if path else f"/{req_key}",
                        f"missing required key '{req_key}'",
                        None,
                        "object",
                    )

            additional_props = schema_def.get("additional_properties")
            if additional_props is False:
                props = schema_def.get("properties", {})
                for key in value:
                    if key not in props:
                        _add_violation(
                            f"{path}/{key}" if path else f"/{key}",
                            f"additional property '{key}' not allowed",
                            "string",
                            None,
                        )

            properties = schema_def.get("properties", {})
            for prop_name, prop_schema in properties.items():
                if prop_name in value:
                    new_path = f"{path}/{prop_name}" if path else f"/{prop_name}"
                    _validate(new_path, value[prop_name], prop_schema, depth + 1)

        elif expected_type == "array" and isinstance(value, list):
            min_items = schema_def.get("min_items")
            max_items = schema_def.get("max_items")
            if min_items is not None and len(value) < min_items:
                _add_violation(
                    path,
                    f"array has {len(value)} items, minimum is {min_items}",
                    "array",
                    None,
                )
            if max_items is not None and len(value) > max_items:
                _add_violation(
                    path,
                    f"array has {len(value)} items, maximum is {max_items}",
                    "array",
                    None,
                )

            items_schema = schema_def.get("items")
            if items_schema is not None:
                for i, item in enumerate(value):
                    item_path = f"{path}/[{i}]"
                    _validate(item_path, item, items_schema, depth + 1)

        elif expected_type == "string" and isinstance(value, str):
            min_len = schema_def.get("min_length")
            max_len = schema_def.get("max_length")
            if min_len is not None and len(value) < min_len:
                _add_violation(
                    path,
                    f"string has length {len(value)}, minimum is {min_len}",
                    "string",
                    None,
                )
            if max_len is not None and len(value) > max_len:
                _add_violation(
                    path,
                    f"string has length {len(value)}, maximum is {max_len}",
                    "string",
                    None,
                )

            pattern = schema_def.get("pattern")
            if pattern is not None:
                is_safe, err_msg = _check_pattern_complexity(pattern)
                if not is_safe:
                    _add_violation(
                        path,
                        f"pattern '{pattern}' is unsafe: {err_msg}",
                        "string",
                        None,
                    )
                else:
                    try:
                        if not re.match(pattern, value):
                            _add_violation(
                                path,
                                f"string '{value}' does not match pattern '{pattern}'",
                                "string",
                                None,
                            )
                    except re.error:
                        pass

        enum_values = schema_def.get("enum")
        if enum_values is not None:
            if value not in enum_values:
                _add_violation(
                    path,
                    f"value {value!r} is not in enum {enum_values}",
                    _get_type_name(value),
                    None,
                )

    _validate("", data, schema)

    truncated = len(violations) >= MAX_SCHEMA_VIOLATIONS or _walk_count > MAX_SCHEMA_ELEMENTS

    if not violations:
        if truncated:
            summary = (
                f"Validation truncated after {_walk_count} elements (limit {MAX_SCHEMA_ELEMENTS})"
            )
        else:
            summary = "Data is valid"
    elif truncated:
        summary = f"Schema violations detected (truncated, {len(violations)} shown)"
    else:
        summary = f"Schema violations detected: {len(violations)} issue{'s' if len(violations) != 1 else ''}"

    return ValidateSchemaLightResult(
        valid=len(violations) == 0,
        violations=violations,
        truncated=truncated,
        summary=summary,
    )


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


def json_canonicalize(
    text: str,
    sort_keys: bool = True,
    indent: int | None = None,
    ensure_ascii: bool = False,
    detect_duplicate_keys: bool = True,
    trailing_newline: bool = False,
) -> JsonCanonicalizeResult:
    """Canonicalize JSON with deterministic formatting and duplicate key detection.

    Args:
        text: Input JSON string.
        sort_keys: Sort object keys alphabetically.
        indent: Indentation spaces (None for minified).
        ensure_ascii: Use ASCII escaping for non-ASCII characters.
        detect_duplicate_keys: Report duplicate keys in the input.
        trailing_newline: Add a trailing newline to the canonical form.

    Returns:
        Dictionary with canonical form, minified form, SHA256 hash,
        duplicate_keys, top_level_type, and top_level_keys.
    """
    if len(text) > MAX_INPUT_LENGTH:
        raise ValueError(f"Input length {len(text)} exceeds MAX_INPUT_LENGTH {MAX_INPUT_LENGTH}")

    duplicate_keys: list[str] = []
    parsed: Any = None

    if detect_duplicate_keys:

        class DuplicateKeyChecker:
            def __init__(self) -> None:
                self.keys: list[str] = []
                self.duplicate_found: list[str] = []

            def object_pairs_hook(self, pairs: list[tuple[str, Any]]) -> dict:
                seen: set[str] = set()
                for key, value in pairs:
                    if key in seen:
                        self.duplicate_found.append(key)
                    else:
                        seen.add(key)
                    self.keys.append(key)
                return dict(pairs)

        checker = DuplicateKeyChecker()
        try:
            parsed = json.loads(text, object_pairs_hook=checker.object_pairs_hook)
            duplicate_keys = checker.duplicate_found
        except json.JSONDecodeError as e:
            return JsonCanonicalizeResult(
                valid=False,
                canonical=None,
                minified=None,
                sha256=None,
                duplicate_keys=[],
                top_level_type=None,
                top_level_keys=None,
                error=e.msg,
                line=e.lineno,
                column=e.colno,
            )
    else:
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as e:
            return JsonCanonicalizeResult(
                valid=False,
                canonical=None,
                minified=None,
                sha256=None,
                duplicate_keys=[],
                top_level_type=None,
                top_level_keys=None,
                error=e.msg,
                line=e.lineno,
                column=e.colno,
            )

    if isinstance(parsed, dict):
        top_level_type = "object"
        top_level_keys = list(parsed.keys())
    elif isinstance(parsed, list):
        top_level_type = "array"
        top_level_keys = None
    else:
        top_level_type = type(parsed).__name__
        top_level_keys = None

    if sort_keys:
        canonical_data = _sort_json_keys(parsed)
    else:
        canonical_data = parsed

    canonical = json.dumps(
        canonical_data, ensure_ascii=ensure_ascii, indent=indent, sort_keys=False
    )
    if trailing_newline:
        canonical += "\n"

    if indent is None:
        minified = json.dumps(
            canonical_data,
            ensure_ascii=ensure_ascii,
            indent=None,
            separators=(",", ":"),
            sort_keys=False,
        )
    else:
        minified = json.dumps(
            canonical_data, ensure_ascii=ensure_ascii, indent=indent, sort_keys=False
        )

    sha256_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    return JsonCanonicalizeResult(
        valid=True,
        canonical=canonical,
        minified=minified,
        sha256=sha256_hash,
        duplicate_keys=duplicate_keys,
        top_level_type=top_level_type,
        top_level_keys=top_level_keys,
        error=None,
        line=None,
        column=None,
    )


def _sort_json_keys(obj: Any) -> Any:
    """Recursively sort object keys in JSON-compatible data."""
    if isinstance(obj, dict):
        return {key: _sort_json_keys(obj[key]) for key in sorted(obj.keys())}
    elif isinstance(obj, list):
        return [_sort_json_keys(item) for item in obj]
    else:
        return obj


def json_query(text: str, pointer: str = "") -> JsonQueryResult:
    """Query JSON using RFC 6901 JSON Pointer.

    Args:
        text: JSON document string.
        pointer: RFC 6901 JSON Pointer path (e.g., "/foo/bar/0").
                 Empty string means the whole document.

    Returns:
        Dictionary with found (bool), value, type, and for missing values:
        missing_at, reason, and available information.
    """
    if len(text) > MAX_INPUT_LENGTH:
        raise ValueError(f"Input length {len(text)} exceeds MAX_INPUT_LENGTH {MAX_INPUT_LENGTH}")

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        return JsonQueryResult(
            found=False,
            pointer=pointer,
            value=None,
            type=None,
            missing_at=None,
            reason="invalid_json",
            error=e.msg,
            line=e.lineno,
            column=e.colno,
        )

    if pointer == "":
        return _build_json_query_result(parsed, pointer)

    tokens = pointer.split("/")
    if tokens and tokens[0] == "":
        tokens = tokens[1:]

    current = parsed
    path_so_far = ""

    for i, token in enumerate(tokens):
        decoded = _decode_pointer_token(token)
        path_so_far = "/" + "/".join(_encode_pointer_token(t) for t in tokens[: i + 1])

        if isinstance(current, dict):
            if decoded in current:
                current = current[decoded]
            else:
                return JsonQueryResult(
                    found=False,
                    pointer=pointer,
                    value=None,
                    type="object",
                    missing_at=path_so_far,
                    reason="key_not_found",
                    error=None,
                    line=None,
                    column=None,
                )
        elif isinstance(current, list):
            try:
                index = int(decoded)
            except ValueError:
                return JsonQueryResult(
                    found=False,
                    pointer=pointer,
                    value=None,
                    type="array",
                    missing_at=path_so_far,
                    reason="invalid_pointer_syntax",
                    error=None,
                    line=None,
                    column=None,
                )

            if index < 0 or index >= len(current):
                return JsonQueryResult(
                    found=False,
                    pointer=pointer,
                    value=None,
                    type="array",
                    missing_at=path_so_far,
                    reason="index_out_of_range",
                    error=None,
                    line=None,
                    column=None,
                )
            current = current[index]
        else:
            return JsonQueryResult(
                found=False,
                pointer=pointer,
                value=None,
                type=type(current).__name__,
                missing_at=path_so_far,
                reason="invalid_pointer_syntax",
                error=None,
                line=None,
                column=None,
            )

    return _build_json_query_result(current, pointer)


def _build_json_query_result(value: Any, pointer: str) -> JsonQueryResult:
    """Build a query result for a value."""
    if isinstance(value, dict):
        return JsonQueryResult(
            found=True,
            pointer=pointer,
            value=value,
            type="object",
            missing_at=None,
            reason=None,
            error=None,
            line=None,
            column=None,
        )
    elif isinstance(value, list):
        return JsonQueryResult(
            found=True,
            pointer=pointer,
            value=value,
            type="array",
            missing_at=None,
            reason=None,
            error=None,
            line=None,
            column=None,
        )
    elif isinstance(value, str):
        return JsonQueryResult(
            found=True,
            pointer=pointer,
            value=value,
            type="string",
            missing_at=None,
            reason=None,
            error=None,
            line=None,
            column=None,
        )
    elif isinstance(value, bool):
        return JsonQueryResult(
            found=True,
            pointer=pointer,
            value=value,
            type="boolean",
            missing_at=None,
            reason=None,
            error=None,
            line=None,
            column=None,
        )
    elif value is None:
        return JsonQueryResult(
            found=True,
            pointer=pointer,
            value=None,
            type="null",
            missing_at=None,
            reason=None,
            error=None,
            line=None,
            column=None,
        )
    else:
        return JsonQueryResult(
            found=True,
            pointer=pointer,
            value=value,
            type="number",
            missing_at=None,
            reason=None,
            error=None,
            line=None,
            column=None,
        )
