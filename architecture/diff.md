# diff.py - String Diffing Algorithms

## Purpose

Provides algorithms for computing differences between strings, including edit distance calculation, first difference detection, and diff span generation.

## Core Functions

### `levenshtein_distance(a: str, b: str) -> int`

Calculate the Levenshtein (edit) distance between two strings.

The edit distance is the minimum number of operations (insertions, deletions, substitutions) required to transform `a` into `b`.

```python
>>> levenshtein_distance("kitten", "sitting")
3
>>> levenshtein_distance("hello", "hello")
0
```

**Algorithm**: Uses dynamic programming with O(mn) time and O(min(m,n)) space optimization.

### `first_diff(a: str, b: str) -> FirstDiff | None`

Find the first difference between two strings.

```python
class FirstDiff(TypedDict):
    a_index: int
    b_index: int
    a_char: str
    b_char: str
    a_codepoint: str
    b_codepoint: str
```

Returns `None` if strings are identical.

```python
>>> first_diff("hello", "hallo")
FirstDiff(a_index=1, b_index=1, a_char='e', b_char='a',
         a_codepoint='U+0065', b_codepoint='U+0061')
>>> first_diff("hello", "hello")
None
```

### `common_prefix_suffix(a: str, b: str) -> CommonPrefixSuffix`

Find common prefix and suffix lengths between two strings.

```python
>>> common_prefix_suffix("hello", "yo")
{'common_prefix_len': 0, 'common_suffix_len': 1}
>>> common_prefix_suffix("testing", "ing")
{'common_prefix_len': 0, 'common_suffix_len': 3}
```

### `longest_common_subsequence(a: str, b: str) -> str`

Find the longest common subsequence of two strings using dynamic programming.

```python
>>> longest_common_subsequence("abcde", "ace")
'ace'
>>> longest_common_subsequence("abc", "def")
''
```

### `diff_spans(a: str, b: str, max_diffs: int = 50) -> list[DiffSpan]`

Generate a list of diff spans between two strings.

```python
class DiffSpan(TypedDict):
    kind: str
    a_span: list[int]
    b_span: list[int]
    a_text: str
    b_text: str
```

### FirstDiff (TypedDict)

```python
class FirstDiff(TypedDict):
    a_index: int
    b_index: int
    a_char: str
    b_char: str
    a_codepoint: str
    b_codepoint: str
```

### CommonPrefixSuffix (TypedDict)

```python
class CommonPrefixSuffix(TypedDict):
    common_prefix_len: int
    common_suffix_len: int
```

**Algorithm**: Uses difflib.SequenceMatcher to compute optimal edit script, then converts to diff spans.

```python
>>> list(diff_spans("hello", "hallo"))
[DiffSpan(kind='replace', a_span=[1, 2], b_span=[1, 2], a_text='e', b_text='a')]
```

## Data Structures

### `FirstDiff`

TypedDict containing:
- `a_index`: Position in first string
- `b_index`: Position in second string  
- `a_char`: Character at position in first string
- `b_char`: Character at position in second string
- `a_codepoint`: Codepoint of character at position in first string (U+XXXX format)
- `b_codepoint`: Codepoint of character at position in second string

### `DiffSpan`

TypedDict containing:
- `kind`: Type of diff ("equal", "insert", "delete", "replace")
- `a_span`: [start, end) indices in string a
- `b_span`: [start, end) indices in string b
- `a_text`: The text from string a in this span
- `b_text`: The text from string b in this span

### `CommonPrefixSuffix`

TypedDict containing:
- `common_prefix_len`: Length of common prefix
- `common_suffix_len`: Length of common suffix

## Algorithm Details

### Levenshtein Distance

Uses dynamic programming with the recurrence:

```
dp[i][j] = min(
    dp[i-1][j] + 1,           # deletion
    dp[i][j-1] + 1,           # insertion
    dp[i-1][j-1] + (0 if a[i-1] == b[j-1] else 1)  # substitution
)
```

### Diff Span Generation

1. Uses `difflib.SequenceMatcher` to compute optimal edit script
2. Converts SequenceMatcher opcodes to diff spans
3. Skips equal (unchanged) segments

## Index

See [overview.md](overview.md) for the module index.