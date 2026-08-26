# diff.py - Diff and Span Primitives

## Table of Contents

- [Purpose](#purpose)
- [Constants](#constants)
- [Types](#types)
  - [FirstDiff](#firstdiff)
  - [CommonPrefixSuffix](#commonprefixsuffix)
  - [DiffSpan](#diffspan)
- [Functions](#functions)
  - [first_diff](#first_diffa-str-b-str-firstdiff--none)
  - [common_prefix_suffix](#common_prefix_suffixa-str-b-str-commonprefixsuffix)
  - [levenshtein_distance](#levenshtein_distancea-str-b-str-max_len-int--int)
  - [longest_common_subsequence](#longest_common_subsequencea-str-b-str-max_len-int--str)
  - [diff_spans](#diff_spansa-str-b-str-max_diffs-int--listdiffspan)
- [Algorithm Details](#algorithm-details)
- [Index](#index)

## Purpose

Provides low-level diff operations including Levenshtein distance, first difference detection, common prefix/suffix, longest common subsequence, and diff spans using `difflib.SequenceMatcher`.

## Constants

```python
MAX_LEVENSHTEIN_LEN = 10000
```

Maximum string length allowed for `levenshtein_distance` and `longest_common_subsequence`. Both functions raise `ValueError` if either input exceeds this limit.

## Types

### FirstDiff

```python
class FirstDiff(TypedDict):
    a_index: int
    b_index: int
    a_char: str
    b_char: str
    a_codepoint: str
    b_codepoint: str
```

### CommonPrefixSuffix

```python
class CommonPrefixSuffix(TypedDict):
    common_prefix_len: int
    common_suffix_len: int
```

### DiffSpan

```python
class DiffSpan(TypedDict):
    kind: str           # "replace", "insert", or "delete"
    a_span: list[int]   # [start, end) indices in string a
    b_span: list[int]   # [start, end) indices in string b
    a_text: str         # text from string a in this span
    b_text: str         # text from string b in this span
```

## Functions

### `first_diff(a: str, b: str) -> FirstDiff | None`

Find the first difference between two strings.

```python
>>> first_diff("hello", "hallo")
FirstDiff(a_index=1, b_index=1, a_char='e', b_char='a',
         a_codepoint='U+0065', b_codepoint='U+0061')
>>> first_diff("hello", "hello")
None
```

**Parameters:**
- `a`: First string.
- `b`: Second string.

**Returns:** `FirstDiff` with indices, characters, and codepoint representations, or `None` if strings are identical.

**Edge cases:**
- When strings differ only in length, the differing character is at position `min(len(a), len(b))` and the shorter string's char/codepoint fields are empty strings.
- Indices are always equal (both `a_index` and `b_index` hold the same value) since comparison is positional.

### `common_prefix_suffix(a: str, b: str) -> CommonPrefixSuffix`

Find common prefix and suffix lengths of two strings. Avoids overlapping prefix and suffix.

```python
>>> common_prefix_suffix("hello world", "hello there")
{'common_prefix_len': 6, 'common_suffix_len': 0}
>>> common_prefix_suffix("testing", "ing")
{'common_prefix_len': 0, 'common_suffix_len': 3}
```

**Parameters:**
- `a`: First string.
- `b`: Second string.

**Returns:** `CommonPrefixSuffix` with `common_prefix_len` and `common_suffix_len`.

**Edge cases:**
- If prefix and suffix would overlap (i.e., `prefix_len + suffix_len > min_len`), the suffix is truncated to `min_len - prefix_len`. In the extreme case where the entire shorter string is a prefix, both are zero.

### `levenshtein_distance(a: str, b: str, max_len: int = MAX_LEVENSHTEIN_LEN) -> int`

Calculate the Levenshtein (edit) distance between two strings.

```python
>>> levenshtein_distance("kitten", "sitting")
3
>>> levenshtein_distance("hello", "hello")
0
```

**Parameters:**
- `a`: First string.
- `b`: Second string.
- `max_len`: Maximum string length to process (default `MAX_LEVENSHTEIN_LEN`, 10000).

**Returns:** Edit distance as a non-negative integer.

**Raises:** `ValueError` if either string exceeds `max_len`.

**Algorithm:** Dynamic programming with O(mn) time and O(min(m,n)) space (two-row optimization).

### `longest_common_subsequence(a: str, b: str, max_len: int = MAX_LEVENSHTEIN_LEN) -> str`

Find the longest common subsequence of two strings.

```python
>>> longest_common_subsequence("abcde", "ace")
'ace'
>>> longest_common_subsequence("abc", "def")
''
```

**Parameters:**
- `a`: First string.
- `b`: Second string.
- `max_len`: Maximum allowed length for either input string (default `MAX_LEVENSHTEIN_LEN`, 10000).

**Returns:** The longest common subsequence as a string.

**Raises:** `ValueError` if either string exceeds `max_len`.

**Algorithm:** Hirschberg's O(mn)-time, O(min(m,n))-space divide-and-conquer reconstruction. Returns empty string for empty inputs before checking length limits.

### `diff_spans(a: str, b: str, max_diffs: int = 50) -> list[DiffSpan]`

Find diff spans between two strings using `difflib.SequenceMatcher`.

```python
>>> diff_spans("hello", "hallo")
[DiffSpan(kind='replace', a_span=[1, 2], b_span=[1, 2], a_text='e', b_text='a')]
```

**Parameters:**
- `a`: First string.
- `b`: Second string.
- `max_diffs`: Maximum number of diff spans to return (default 50). Larger strings will have diffs truncated to this limit.

**Returns:** List of `DiffSpan` dicts. Each span has `kind` (`"replace"`, `"insert"`, or `"delete"`), `a_span` and `b_span` as `[start, end)` index pairs, and `a_text` / `b_text` as the corresponding substrings. Equal (unchanged) segments are omitted.

**Edge cases:**
- `max_diffs` caps output early; spans beyond the limit are silently dropped.
- `"insert"` spans have `a_span` where `a_span[0] == a_span[1]` (zero-width in a).
- `"delete"` spans have `b_span` where `b_span[0] == b_span[1]` (zero-width in b).

## Algorithm Details

### Levenshtein Distance

Two-row DP optimization: maintains `prev_row` and `curr_row` of length `len(b)+1`. Swaps rows each iteration.

```
dp[i][j] = min(
    dp[i-1][j] + 1,           # deletion
    dp[i][j-1] + 1,           # insertion
    dp[i-1][j-1] + (0 if a[i-1] == b[j-1] else 1)  # substitution
)
```

### Longest Common Subsequence

Full O(mn) DP table with traceback from `dp[m][n]` back to `dp[0][0]`. The result is built by reversing the collected characters.

### Diff Span Generation

1. `difflib.SequenceMatcher(None, a, b)` computes the optimal edit script.
2. Opcodes with tag `"equal"` are skipped.
3. Remaining tags (`"replace"`, `"insert"`, `"delete"`) become `DiffSpan` entries.
4. Processing stops when `max_diffs` spans have been collected.

## Index

See [overview.md](overview.md) for the module index.
