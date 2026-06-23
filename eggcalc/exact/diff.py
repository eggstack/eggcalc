"""
Diff and span primitives.

Provides low-level diff operations including Levenshtein distance,
first difference detection, common prefix/suffix, and diff_spans using
difflib.SequenceMatcher.
"""

from __future__ import annotations

import difflib
from typing import TypedDict

__all__ = [
    "FirstDiff",
    "CommonPrefixSuffix",
    "DiffSpan",
    "MAX_LEVENSHTEIN_LEN",
    "first_diff",
    "common_prefix_suffix",
    "levenshtein_distance",
    "longest_common_subsequence",
    "diff_spans",
]


class FirstDiff(TypedDict):
    """Information about the first difference between two strings."""

    a_index: int
    b_index: int
    a_char: str
    b_char: str
    a_codepoint: str
    b_codepoint: str


class CommonPrefixSuffix(TypedDict):
    """Common prefix and suffix lengths."""

    common_prefix_len: int
    common_suffix_len: int


class DiffSpan(TypedDict):
    """A span of difference between two strings."""

    kind: str
    a_span: list[int]
    b_span: list[int]
    a_text: str
    b_text: str


MAX_LEVENSHTEIN_LEN = 10000


def first_diff(a: str, b: str) -> FirstDiff | None:
    """Find the first difference between two strings.

    Args:
        a: First string.
        b: Second string.

    Returns:
        FirstDiff dict with indices, chars, and codepoints, or None if equal.
    """
    min_len = min(len(a), len(b))

    for i in range(min_len):
        if a[i] != b[i]:
            return FirstDiff(
                a_index=i,
                b_index=i,
                a_char=a[i],
                b_char=b[i],
                a_codepoint=f"U+{ord(a[i]):04X}",
                b_codepoint=f"U+{ord(b[i]):04X}",
            )

    if len(a) != len(b):
        return FirstDiff(
            a_index=min_len,
            b_index=min_len,
            a_char=a[min_len] if len(a) > min_len else "",
            b_char=b[min_len] if len(b) > min_len else "",
            a_codepoint=f"U+{ord(a[min_len]):04X}" if len(a) > min_len else "",
            b_codepoint=f"U+{ord(b[min_len]):04X}" if len(b) > min_len else "",
        )

    return None


def common_prefix_suffix(a: str, b: str) -> CommonPrefixSuffix:
    """Find common prefix and suffix lengths of two strings.

    Avoids overlapping prefix/suffix. If the entire string would be
    overlapped, both prefix and suffix are zero.

    Args:
        a: First string.
        b: Second string.

    Returns:
        Dictionary with common_prefix_len and common_suffix_len.

    Example:
        >>> common_prefix_suffix("prefix_middle_suffix", "xxx_middle_yyy")
        {'common_prefix_len': 0, 'common_suffix_len': 0}
        >>> common_prefix_suffix("hello world", "hello there")
        {'common_prefix_len': 6, 'common_suffix_len': 0}
        >>> common_prefix_suffix("testing", "ing")
        {'common_prefix_len': 0, 'common_suffix_len': 3}
    """
    # Find common prefix
    prefix_len = 0
    min_len = min(len(a), len(b))
    while prefix_len < min_len and a[prefix_len] == b[prefix_len]:
        prefix_len += 1

    # Find common suffix (working backwards from end)
    suffix_len = 0
    while (
        suffix_len < min_len - prefix_len
        and a[len(a) - 1 - suffix_len] == b[len(b) - 1 - suffix_len]
    ):
        suffix_len += 1

    return CommonPrefixSuffix(
        common_prefix_len=prefix_len,
        common_suffix_len=suffix_len,
    )


def levenshtein_distance(a: str, b: str, max_len: int = MAX_LEVENSHTEIN_LEN) -> int:
    """Calculate Levenshtein (edit) distance between two strings.

    Uses dynamic programming with memory optimization. Bounds input size.

    Args:
        a: First string.
        b: Second string.
        max_len: Maximum string length to process (default 10000).

    Returns:
        Edit distance as integer.

    Raises:
        ValueError: If either string exceeds max_len.
    """
    if len(a) > max_len or len(b) > max_len:
        raise ValueError(f"Input string exceeds max length {max_len}")

    # If one string is empty, distance is length of the other
    if not a:
        return len(b)
    if not b:
        return len(a)

    # Optimize memory by using two rows instead of full matrix
    # dp[j] = edit distance for a[:i] and b[:j]
    prev_row = list(range(len(b) + 1))
    curr_row = [0] * (len(b) + 1)

    for i in range(1, len(a) + 1):
        curr_row[0] = i
        for j in range(1, len(b) + 1):
            if a[i - 1] == b[j - 1]:
                curr_row[j] = prev_row[j - 1]
            else:
                curr_row[j] = 1 + min(
                    prev_row[j],  # deletion
                    curr_row[j - 1],  # insertion
                    prev_row[j - 1],  # substitution
                )
        prev_row, curr_row = curr_row, prev_row

    return prev_row[len(b)]


def longest_common_subsequence(a: str, b: str, max_len: int = MAX_LEVENSHTEIN_LEN) -> str:
    """Find the longest common subsequence of two strings.

    Args:
        a: First string.
        b: Second string.
        max_len: Maximum allowed length for either input string.

    Returns:
        The longest common subsequence as a string.

    Raises:
        ValueError: If either string exceeds max_len.
    """
    if not a or not b:
        return ""
    if len(a) > max_len or len(b) > max_len:
        raise ValueError(f"Input strings too long ({len(a)}, {len(b)}); max {max_len}")

    m, n = len(a), len(b)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    lcs_len = dp[m][n]
    result = []
    i, j = m, n
    while i > 0 and j > 0:
        if a[i - 1] == b[j - 1]:
            result.append(a[i - 1])
            i -= 1
            j -= 1
        elif dp[i - 1][j] > dp[i][j - 1]:
            i -= 1
        else:
            j -= 1

    return "".join(reversed(result))


def diff_spans(a: str, b: str, max_diffs: int = 50) -> list[DiffSpan]:
    """Find diff spans between two strings using SequenceMatcher.

    Args:
        a: First string.
        b: Second string.
        max_diffs: Maximum number of diff spans to return (default 50).
        Larger strings will have diffs truncated to this limit.

    Returns:
        List of DiffSpan dicts with kind (replace/insert/delete),
        a_span, b_span, a_text, b_text.
    """
    matcher = difflib.SequenceMatcher(None, a, b)
    spans: list[DiffSpan] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue

        kind = tag  # 'replace', 'insert', or 'delete'
        spans.append(
            DiffSpan(
                kind=kind,
                a_span=[i1, i2],
                b_span=[j1, j2],
                a_text=a[i1:i2],
                b_text=b[j1:j2],
            )
        )

        if len(spans) >= max_diffs:
            break

    return spans
