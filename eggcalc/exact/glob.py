"""
Pattern matching with glob semantics.

Provides deterministic glob pattern matching with documented semantics.
Supports POSIX and Windows path separators with explicit behavior for
*, **, and ? wildcards.
"""

from __future__ import annotations

import re
from typing import TypedDict


class GlobMatchResult(TypedDict):
    """Result of glob pattern matching."""

    matches: bool
    normalized_pattern: str
    normalized_path: str
    matched_segment: str | None
    unmatched_segment: str | None
    summary: str


def _split_path_posix(path: str) -> list[str]:
    """Split POSIX path into segments."""
    if path == "":
        return []
    parts = path.split("/")
    return [p for p in parts if p]


def _split_path_windows(path: str) -> list[str]:
    """Split Windows path into segments, handling drive letters and UNC."""
    segments: list[str] = []

    if len(path) >= 2 and path[1] == ":":
        segments.append(path[:2])
        rest = path[2:]
        if rest:
            parts = re.split(r"[/\\]", rest)
            segments.extend([p for p in parts if p])
        return segments

    if path.startswith("\\\\"):
        parts = re.split(r"[/\\]", path)
        if len(parts) >= 4:
            segments.append("\\\\" + parts[1] + "\\" + parts[2])
            segments.extend([p for p in parts[3:] if p])
        else:
            segments.extend([p for p in parts if p])
        return segments

    parts = re.split(r"[/\\]", path)
    return [p for p in parts if p]


def _glob_casefold(s: str) -> str:
    """Casefold string for case-insensitive comparison."""
    return s.casefold()


def _fnmatch_segment(pattern: str, segment: str, case_sensitive: bool = True) -> bool:
    """Match pattern against a single path segment using fnmatch semantics.

    This implements standard fnmatch behavior:
    - * matches everything except /
    - ? matches exactly one character except /
    - [char] matches character classes

    Args:
        pattern: Glob pattern for one segment.
        segment: Path segment to match.
        case_sensitive: Whether to match case-sensitively.

    Returns:
        True if segment matches pattern.
    """
    if not case_sensitive:
        pattern = _glob_casefold(pattern)
        segment = _glob_casefold(segment)

    return re.match(_fnmatch_to_regex(pattern), segment) is not None


def _fnmatch_to_regex(pattern: str) -> str:
    """Convert fnmatch pattern to regex, keeping / as literal.

    Args:
        pattern: Glob pattern.

    Returns:
        Regex pattern string.
    """
    regex_parts = []
    i = 0
    n = len(pattern)

    while i < n:
        char = pattern[i]

        if char == "*":
            regex_parts.append("[^/]*")
            i += 1

        elif char == "?":
            regex_parts.append("[^/]")
            i += 1

        elif char == "[":
            j = i + 1
            if j < n and pattern[j] == "!":
                j += 1
            if j < n and pattern[j] == "]":
                j += 1
            while j < n and pattern[j] != "]":
                j += 1

            if j >= n:
                regex_parts.append(re.escape("["))
                i += 1
            else:
                char_class = pattern[i : j + 1]
                char_class = char_class.replace("!", "^", 1)
                regex_parts.append("[" + char_class[1:-1] + "]")
                i = j + 1

        elif char == "/":
            regex_parts.append("/")
            i += 1

        else:
            regex_parts.append(re.escape(char))
            i += 1

    return "^" + "".join(regex_parts) + "$"


def _match_double_star(
    pattern_parts: list[str],
    path_parts: list[str],
    p_idx: int,
) -> tuple[bool, int, int]:
    """Match ** pattern against path parts.

    ** matches zero or more full path segments.

    Args:
        pattern_parts: Pattern split into segments.
        path_parts: Path split into segments.
        p_idx: Index in pattern where ** begins.

    Returns:
        Tuple of (matched, next_pattern_idx, next_path_idx).
    """
    next_pattern_idx = p_idx + 1

    if next_pattern_idx >= len(pattern_parts):
        return True, next_pattern_idx, len(path_parts)

    path_idx = p_idx
    while path_idx <= len(path_parts):
        remaining_pattern = pattern_parts[next_pattern_idx:]
        remaining_path = path_parts[path_idx:] if path_idx < len(path_parts) else []

        matched, consumed_p, consumed_path = _match_segments(
            remaining_pattern, remaining_path, case_sensitive=True
        )

        if matched:
            return True, next_pattern_idx + consumed_p, path_idx + consumed_path

        if path_idx < len(path_parts):
            path_idx += 1
        else:
            break

    return False, p_idx, p_idx


def _match_segments(
    pattern_parts: list[str],
    path_parts: list[str],
    case_sensitive: bool = True,
) -> tuple[bool, int, int]:
    """Match pattern segments against path segments.

    Returns:
        Tuple of (matched, consumed_pattern_count, consumed_path_count).
    """
    p_idx = 0
    path_idx = 0

    while p_idx < len(pattern_parts) and path_idx < len(path_parts):
        pattern_seg = pattern_parts[p_idx]

        if pattern_seg == "**":
            matched, new_p_idx, new_path_idx = _match_double_star(pattern_parts, path_parts, p_idx)
            if not matched:
                return False, p_idx, path_idx
            p_idx = new_p_idx
            path_idx = new_path_idx

        elif "**" in pattern_seg:
            return False, p_idx, path_idx

        else:
            if not _fnmatch_segment(pattern_seg, path_parts[path_idx], case_sensitive):
                return False, p_idx, path_idx
            p_idx += 1
            path_idx += 1

    while p_idx < len(pattern_parts):
        if pattern_parts[p_idx] == "**":
            p_idx += 1
        else:
            return False, p_idx, path_idx

    return p_idx == len(pattern_parts), p_idx, path_idx


def glob_match(
    pattern: str,
    path: str,
    platform: str = "posix",
    case_sensitive: bool = True,
) -> GlobMatchResult:
    """Match a glob pattern against a path.

    Glob semantics:
    - `*` matches any characters within one path segment (not crossing /)
    - `**` matches zero or more full path segments
    - `?` matches exactly one character within a segment

    Note: Python's fnmatch has limitations around ** patterns. This
    implementation provides explicit ** handling as described above.

    Args:
        pattern: Glob pattern to match (e.g., "src/**/*.rs").
        path: Path string to match against.
        platform: "posix" or "windows". Controls path separator handling.
        case_sensitive: Whether to match case-sensitively.

    Returns:
        GlobMatchResult with matches boolean and normalized values.

    Examples:
        >>> glob_match("src/**/*.rs", "src/main.rs", "posix", True).matches
        True
        >>> glob_match("*.txt", "readme.txt", "posix", True).matches
        True
        >>> glob_match("src/**", "src/foo/bar/baz", "posix", True).matches
        True
    """
    normalized_pattern = pattern
    normalized_path = path

    if platform == "windows":
        path_parts = _split_path_windows(path)
    else:
        path_parts = _split_path_posix(path)

    pattern_parts: list[str] = []
    i = 0
    n = len(pattern)

    while i < n:
        if i + 1 < n and pattern[i : i + 2] == "**":
            if i + 2 < n and pattern[i + 2] == "/":
                pattern_parts.append("**")
                i += 3
            elif i + 2 == n:
                pattern_parts.append("**")
                i += 2
            else:
                pattern_parts.append("**")
                i += 2

        elif pattern[i] == "/":
            i += 1

        else:
            j = i
            while j < n and pattern[j] != "/" and not (j + 1 < n and pattern[j : j + 2] == "**"):
                j += 1
            pattern_parts.append(pattern[i:j])
            i = j

    matched, _, _ = _match_segments(pattern_parts, path_parts, case_sensitive)

    if matched:
        return GlobMatchResult(
            matches=True,
            normalized_pattern=normalized_pattern,
            normalized_path=normalized_path,
            matched_segment=None,
            unmatched_segment=None,
            summary="Pattern matches path",
        )
    else:
        return GlobMatchResult(
            matches=False,
            normalized_pattern=normalized_pattern,
            normalized_path=normalized_path,
            matched_segment=None,
            unmatched_segment=None,
            summary="Pattern does not match path",
        )
