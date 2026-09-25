# glob.py — Glob Pattern Matching

309 lines. Deterministic glob pattern matching with POSIX and Windows path separator support.

## Table of Contents

- [Overview](#overview)
- [Type Definitions](#type-definitions)
- [Constants / Limits](#constants--limits)
- [Public Functions](#public-functions)
  - [glob_match](#glob_match)
- [Internal Helpers](#internal-helpers)
- [Dependencies](#dependencies)
- [Security / DoS Notes](#security--dos-notes)
- [See Also](#see-also)
- [Usage Example](#usage-example)

## Overview

Deterministic, pure, no I/O. Matches a glob pattern against a path string lexically
(no filesystem access). Glob semantics:

- `*` matches any characters **within one path segment** (never crosses `/`)
- `**` matches **zero or more full path segments** (the only cross-separator wildcard)
- `?` matches exactly one character within a segment
- `[...]` character classes with `!` negation (fnmatch-style; see below)
- `platform="posix"` splits on `/`; `platform="windows"` splits on `/` and `\` with
  drive-letter (`C:`) and UNC (`\\server\share`) roots

Results are plain-dict TypedDicts — use `result["matches"]`, never `result.matches`.

## Type Definitions

### GlobMatchResult (TypedDict)

Verified against `eggcalc/exact/glob.py:15-23`:

```python
class GlobMatchResult(TypedDict):
    matches: bool              # True iff the pattern matches the whole path
    normalized_pattern: str    # echo of the pattern argument (NOT rewritten)
    normalized_path: str       # echo of the path argument (NOT rewritten)
    matched_segment: str | None    # always None in the current implementation
    unmatched_segment: str | None  # always None in the current implementation
    summary: str               # "Pattern matches path" | "Pattern does not match path"
```

Despite the field names, `matched_segment` / `unmatched_segment` are never populated —
both branches of `glob_match` return `None`. The `normalized_*` fields echo their inputs
verbatim (no separator folding or case normalization is applied to them).

## Constants / Limits

No `MAX_*` cap and no module constant tables — behavior is fully determined by the
pattern/path arguments (see Security notes for ReDoS-relevant detail).

## Public Functions

### `glob_match`

```python
def glob_match(
    pattern: str,
    path: str,
    platform: str = "posix",
    case_sensitive: bool = True,
) -> GlobMatchResult
```

Splits both pattern and path into segments, then requires the **entire** segment list to
match (`_match_segments` must consume all pattern and all path parts, except trailing
`**` which matches the empty tail).

Verified examples:

```python
glob_match("*.txt", "readme.txt")["matches"]              # → True
glob_match("*.txt", "a/b.txt")["matches"]                 # → False (* never crosses /)
glob_match("src/**/*.rs", "src/main.rs")["matches"]       # → True (** matches zero segments)
glob_match("src/**/*.rs", "src/a/b/c.rs")["matches"]      # → True
glob_match("src/*.rs", "src/a/b.rs")["matches"]           # → False (one * = one segment)
glob_match("file?.txt", "file1.txt")["matches"]           # → True
glob_match("file?.txt", "file12.txt")["matches"]          # → False (? = exactly one char)
glob_match("**", "anything/at/all")["matches"]            # → True
glob_match("src/**", "src/foo/bar")["matches"]            # → True
glob_match("a/**/b", "a/b")["matches"]                    # → True (** = zero segments)
glob_match("a/**/b", "a/x/y/b")["matches"]                # → True
glob_match("a/**", "a")["matches"]                        # → True (trailing ** matches empty tail)
glob_match("**/x", "y")["matches"]                        # → False
glob_match("[abc].txt", "a.txt")["matches"]               # → True
glob_match("a/b", "a/B")["matches"]                       # → False (case-sensitive default)
glob_match("a/b", "a/B", case_sensitive=False)["matches"] # → True
glob_match("*.TXT", "readme.txt")["matches"]              # → False
glob_match("src/*.py", "src\\main.py", platform="windows")["matches"]  # → True
```

**Segment-splitting edge cases:**

- POSIX: `""` → `[]`; leading/trailing/repeated `/` are dropped (`"/a//b/"` → `["a", "b"]`).
- Windows: drive prefix kept as a segment (`"C:\\a\\b"` → `["C:", "a", "b"]`);
  UNC root collapsed (`"\\\\srv\\share\\a"` → `["\\\\srv\\share", "a"]`); `/` and `\`
  are interchangeable separators.
- Unknown `platform` values (e.g. `"bogus"`) fall through to the POSIX branch — no error.
- Empty pattern matches only the empty path (`glob_match("", "")` → True; `glob_match("", "a")` → False).

**Wildcard edge cases:**

- A segment **containing** `**` but not equal to it (e.g. `"a**b"`) never matches —
  `_match_segments` returns `(False, ...)` immediately. Only a bare `"**"` segment is special.
- Unbalanced `[` degrades to a literal (`"a[b"` matches the literal path `"a[b"`).
- `[!...]` negates inside classes (`"[!a].txt"` matches `"b.txt"`, not `"a.txt"`).
- `?` and `*` never match `/` (compiled as `[^/]` / `[^/]*`); matching is full-segment
  anchored (`^...$`).

## Internal Helpers

- `_split_path_posix(path)` — `""` → `[]`; else `split("/")` minus empties.
- `_split_path_windows(path)` — drive-letter / UNC / mixed-separator splitter described above.
- `_glob_casefold(s)` — `str.casefold()` applied to both pattern and segment when `case_sensitive=False`.
- `_fnmatch_segment(pattern, segment, case_sensitive=True)` — single-segment `re.match` gate.
- `_fnmatch_to_regex(pattern)` — `*` → `[^/]*`, `?` → `[^/]`, `[...]` class (with `!` → `^`),
  `/` literal, everything else `re.escape`d; anchored `^...$`.
- `_match_segments(pattern_parts, path_parts, case_sensitive)` — sequential matcher with
  `**`-delegation and trailing-`**` acceptance; returns `(matched, consumed_p, consumed_path)`.
- `_match_double_star(pattern_parts, path_parts, p_idx)` — greedy tail search for the
  segments after `**`; terminal `**` matches everything remaining. Note: the recursive
  `_match_segments` call inside hardcodes `case_sensitive=True`, so mid-pattern `**`
  backtracking after the `**` is effectively case-sensitive even when the top-level call
  passes `case_sensitive=False` (first-segment matches before the `**` still honor the flag).

## Dependencies

```
glob.py
    └── stdlib only: re, typing (leaf module — no exact/ imports)
```

Stdlib-only; safe for the single-file build.

## Security / DoS Notes

- **No input caps:** pattern and path are unbounded strings; each non-`**` segment compiles
  a fresh regex per comparison (`_fnmatch_to_regex` + `re.match`). Callers matching
  untrusted patterns/paths at scale should cap both lengths and cache results.
- Character classes come from the pattern and are spliced into a regex character class
  (`"[" + inner + "]"`) — `re.escape` is **not** applied inside `[...]`, so a hostile
  pattern controls regex syntax there (bounded risk: single class, no quantifiers, but
  still caller-controlled regex). Prefer allow-listing pattern sources.
- No filesystem access means no traversal risk from `..` (treated as a literal segment);
  scope enforcement belongs in [path_tools.md](path_tools.md) (`path_scope_check`), not here.
- `matched_segment` / `unmatched_segment` are always `None` — do not build diagnostics on them.

## See Also

- [path_tools.md](path_tools.md) — lexical path analysis, normalization, comparison, scope checks
- [diff.md](diff.md) — string-similarity companion (no glob semantics)
- [exact.md](exact.md) — package-level overview

## Usage Example

```python
from eggcalc.exact.glob import glob_match

print(glob_match("src/**/*.rs", "src/a/b/c.rs")["matches"])  # True
print(glob_match("src/*.rs", "src/a/b.rs")["matches"])       # False (* stays in-segment)
print(glob_match("*.txt", "readme.txt")["summary"])          # 'Pattern matches path'

# Case-insensitive Windows match
r = glob_match("src/*.py", "SRC\\Main.PY", platform="windows", case_sensitive=False)
print(r["matches"])  # True
```

(End of file - total 309 lines implementation)
