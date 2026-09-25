# path_tools.py — Path Lexical Analysis

611 lines. Deterministic path parsing without filesystem access.

## Table of Contents

- [Overview](#overview)
- [Type Definitions](#type-definitions)
- [Constants / Limits](#constants--limits)
- [Public Functions](#public-functions)
  - [path_analyze](#path_analyze)
  - [path_normalize](#path_normalize)
  - [path_compare](#path_compare)
  - [path_scope_check](#path_scope_check)
- [Internal Helpers](#internal-helpers)
- [Dependencies](#dependencies)
- [Security / DoS Notes](#security--dos-notes)
- [See Also](#see-also)
- [Usage Example](#usage-example)

## Overview

Deterministic, pure, no I/O — lexical path analysis only. Never calls `Path.exists`,
`resolve`, or any filesystem API (so symlinks are never resolved; see scope-check
caveats). Four entry points over POSIX and Windows syntax:

- `path_analyze`: components, extension/suffixes, hidden flag, traversal flag, parents, warnings, summary.
- `path_normalize`: dot-segment collapsing (`.`/`..`) with root-aware reconstruction.
- `path_compare`: normalized equality under explicit separator/case/dot rules.
- `path_scope_check`: lexically confines a target to a root (dotdot-aware, symlink-blind).

Results are plain-dict TypedDicts — use `result["components"]`, never `result.components`.

## Type Definitions

### PathAnalyzeResult (TypedDict)

Verified against `eggcalc/exact/path_tools.py:34-48`:

```python
class PathAnalyzeResult(TypedDict):
    input: str                 # echo of the path argument
    style: str                 # "posix" | "windows" (resolved from "auto" via _detect_windows_path)
    absolute: bool             # root present and absolute (drive-relative C:foo counts as NOT absolute)
    has_traversal: bool        # ".." in raw components
    components: list[str]      # segments AFTER root, INCLUDING "." and ".." (empties dropped)
    parent: str | None         # lexical parent (None for rootless single-component / empty paths)
    name: str | None           # last component (None when no components)
    stem: str | None           # name minus the FULL suffix chain (pathlib-compatible; None when nameless)
    suffix: str | None         # last suffix only (None when no suffix)
    suffixes: list[str]        # full chain, e.g. [".tar.gz", ".gz"]; [] for dotfiles / "." / ".."
    hidden: bool               # name startswith "." (excluding "." and ".." themselves)
    normalized_lexical: str    # root + sep.join(components); dot segments NOT collapsed here
    warnings: list[str]        # per-segment "." / ".." notes + confusables note
    summary: str               # e.g. "POSIX, absolute, 3 components, suffix '.txt'" or "empty path"
```

### PathNormalizeResult (TypedDict)

```python
class PathNormalizeResult(TypedDict):
    normalized: str          # collapsed path ("" possible for fully-popped relative paths)
    is_absolute: bool        # root-derived absoluteness
    components: list[str]    # collapsed segments (plus [""] sentinel when preserve_trailing_separator adds one)
    warnings: list[str]      # one "Collapsing dot segment" / "Collapsing dot-dot segment" per collapsed seg,
                             # plus "Path contains ..." notes when collapse_dot_segments=False
```

### PathCompareResult (TypedDict)

```python
class PathCompareResult(TypedDict):
    equal: bool                # normalized (and optionally case-folded) equality
    left_normalized: str       # path_normalize(left) under the call's rules
    right_normalized: str      # path_normalize(right) under the call's rules
    differences: list[str]     # [] when equal; else ["Normalized forms differ: 'L' vs 'R'"]
    findings: list[str]        # subset of: "Case-insensitive comparison used",
                               # "Separators normalized to platform default", "Dot segments collapsed"
```

### PathScopeCheckResult (TypedDict)

```python
class PathScopeCheckResult(TypedDict):
    inside_root: bool       # target (resolved against root when relative) == root or under root_prefix
    root_normalized: str    # path_normalize(root)
    target_normalized: str  # path_normalize(target) BEFORE root-joining (relative stays relative)
    relative_path: str      # target minus root_prefix when inside ("." when equal); "" when outside
    escapes_via_dotdot: bool  # ".." in the RAW pre-normalized target components
    absolute_target: str    # target_normalized when absolute; else root-joined + re-normalized
    findings: list[str]     # subset of: "Case-insensitive comparison used",
                            # "Target path contains parent traversal segments",
                            # "Target is relative, resolved against root",
                            # "Target is absolute but root is relative"
```

## Constants / Limits

```python
_MAX_SUFFIXES = 32  # cap on _get_suffixes chain length (bounds ".a.a.a..." names to 32 entries)
```

No `MAX_*` path-length cap is enforced — inputs are unbounded strings (see Security notes).

## Public Functions

### `path_analyze`

```python
def path_analyze(path: str, style: str = "auto") -> PathAnalyzeResult
```

`style="auto"` sniffs Windows syntax (`X:` drive, `\\` UNC prefix, or any `\`);
`"posix"`/`"windows"` force the grammar. Analysis does **not** collapse `.`/`..` —
they stay in `components` and `normalized_lexical`, flagged in `warnings`.

Verified examples:

```python
path_analyze("/a/b/c.txt")
# → {'input': '/a/b/c.txt', 'style': 'posix', 'absolute': True, 'has_traversal': False,
#     'components': ['a', 'b', 'c.txt'], 'parent': '/a/b', 'name': 'c.txt', 'stem': 'c',
#     'suffix': '.txt', 'suffixes': ['.txt'], 'hidden': False,
#     'normalized_lexical': '/a/b/c.txt', 'warnings': [],
#     'summary': "POSIX, absolute, 3 components, suffix '.txt'"}
path_analyze("a/../b/./c")["components"]  # → ['a', '..', 'b', '.', 'c'] (traversal preserved)
path_analyze("a/../b/./c")["warnings"]
# → ['Parent traversal segment at position 1', 'Redundant current directory segment at position 3']
path_analyze("archive.tar.gz")["suffixes"]  # → ['.tar.gz', '.gz'] (stem 'archive', suffix '.gz')
path_analyze(".bashrc")["suffixes"]         # → [] (leading dot is not an extension; hidden True)
path_analyze("")["summary"]                 # → 'POSIX, relative' (components [], parent/name/stem/suffix None)
path_analyze("/")["normalized_lexical"]     # → '/'
path_analyze("C:\\Users\\x\\file.txt")["style"]  # → 'windows' (auto-detected)
```

**Edge cases:** suffix rules are pathlib-compatible — `last_dot <= 0` yields no suffix
(dotfiles, `"."`, `".."` all → `[]`); stem strips the **full** chain (`"archive.tar.gz"` →
stem `"archive"`). Any confusable in the raw path appends
`"Path contains N confusable character(s)"`. Unknown `style` values other than
`"windows"` behave as POSIX (only `"windows"` branches).

### `path_normalize`

```python
def path_normalize(
    path: str,
    platform: str = "posix",
    collapse_dot_segments: bool = True,
    preserve_trailing_separator: bool = False,
) -> PathNormalizeResult
```

Unknown `platform` values fall back to `"posix"`. With collapsing on, `"."` is dropped
and `".."` pops the previous segment (or is kept for relative paths with nothing to
pop); absolute pops past root are absorbed. With collapsing off, segments pass through
and warnings note their presence instead.

Verified examples:

```python
path_normalize("/a/./b/../c/")  # → {'normalized': '/a/c', 'is_absolute': True, 'components': ['a', 'c'],
                                #     'warnings': ['Collapsing dot segment', 'Collapsing dot-dot segment']}
path_normalize("/a/./b/../c/", preserve_trailing_separator=True)["normalized"]  # → '/a/c/'
path_normalize("a/b/../..")     # → {'normalized': '', 'is_absolute': False, 'components': [],
                                #     'warnings': ['Collapsing dot-dot segment', 'Collapsing dot-dot segment']}
path_normalize("C:\\a\\..\\b", platform="windows")["normalized"]  # → 'C:\\b'
path_normalize("/a/./b", collapse_dot_segments=False)["warnings"]  # contains 'Path contains dot segments'
```

**Edge cases:** fully-popped relative paths normalize to `""` (not `"."`).
`preserve_trailing_separator` appends a `""` sentinel component (rendered as the trailing
sep) only when components are non-empty. Drive-relative `C:foo` keeps root `"C:"` with
`is_absolute=False`.

### `path_compare`

```python
def path_compare(
    left: str,
    right: str,
    platform: str = "posix",
    case_sensitive: bool = True,
    normalize_separators: bool = True,
    collapse_dot_segments: bool = True,
) -> PathCompareResult
```

Normalizes separators first (`\`↔`/` toward the platform default), then delegates to
`path_normalize`. Case folding is `.lower()` on the normalized forms (comparison-only;
reported forms keep case).

Verified examples:

```python
path_compare("/a/b", "/a/./b")["equal"]  # → True (dot segments collapsed)
path_compare("/A/B", "/a/b", case_sensitive=False)["equal"]  # → True
path_compare("/a/b", "/a/c")["differences"]  # → ["Normalized forms differ: '/a/b' vs '/a/c'"]
```

### `path_scope_check`

```python
def path_scope_check(
    root: str,
    target: str,
    platform: str = "posix",
    case_sensitive: bool = True,
) -> PathScopeCheckResult
```

Lexical confinement: both sides pre-normalized (separators) then `path_normalize`d;
relative targets join onto the root (`root/target` re-normalized) before the prefix test
(`target == root` or `startswith(root + sep)`). Symlinks are **not** resolved — a
lexically-inside path can still escape via symlinks at runtime.

Verified examples:

```python
path_scope_check("/root", "/root/a/b")
# → {'inside_root': True, 'root_normalized': '/root', 'target_normalized': '/root/a/b',
#     'relative_path': 'a/b', 'escapes_via_dotdot': False, 'absolute_target': '/root/a/b', 'findings': []}
path_scope_check("/root", "/root/../etc/passwd")
# → {'inside_root': False, 'escapes_via_dotdot': True, 'relative_path': '',
#     'findings': ['Target path contains parent traversal segments']}  (normalized to /etc/passwd)
path_scope_check("/root", "rel/path")["absolute_target"]  # → '/root/rel/path' (+ "Target is relative..." finding)
path_scope_check("/root", "/root")["relative_path"]       # → '.' (target == root counts as inside)
```

**Edge cases:** `escapes_via_dotdot` reflects the **raw** target (`".."` anywhere pre-collapse),
so even collapsed-inside targets (e.g. `/root/a/../../root/b` → `/root/b`, inside) still
flag the finding. Case-insensitive mode lowercases both sides for the prefix test only.

## Internal Helpers

- `_detect_windows_path(path)` — drive-letter / UNC / backslash sniff for `style="auto"`.
- `_split_posix_components(path)` / `_split_windows_components(path)` — root + components
  splitters (used by `path_analyze`'s component listing).
- `_parse_path_root(path, platform)` — canonical `(root_string, tail, is_absolute,
  root_kind)` used by `path_normalize`/`path_scope_check`; kinds: `none`/`drive`/`unc`/`posix_root`.
- `_get_suffixes(name)` — pathlib-compatible chain walk capped at `_MAX_SUFFIXES = 32`.

## Dependencies

```
path_tools.py
    ├── stdlib: re, typing
    └── exact: .unicode_tools.detect_confusables (path_analyze confusables warning only)
```

No filesystem, subprocess, or network imports; stdlib-only otherwise.

## Security / DoS Notes

- **No path-length cap:** all four entry points accept unbounded strings; work is linear
  in segment count except suffix extraction (capped at 32) — cap caller-side for untrusted
  input (long `a/a/a/...` chains allocate proportional lists).
- **Lexical ≠ safe:** `path_scope_check` does not resolve symlinks, hardlinks, or
  case-folding filesystems; use it as a pre-filter, then enforce with filesystem-aware
  checks (`realpath` + containment) before any write. `escapes_via_dotdot` is advisory
  (raw-syntax signal, not a verdict — normalized-inside targets still flag it).
- `path_compare(case_sensitive=False)` uses `.lower()`, not `casefold()` — inconsistent
  with Unicode case-insensitive filesystems for exotic characters; document the choice
  when comparing user-supplied names.
- Confusable warnings (`detect_confusables`) catch homoglyph directories (e.g. Cyrillic
  `а` in paths) — surface `path_analyze(... )["warnings"]` in security review UIs.

## See Also

- [glob.md](glob.md) — glob pattern matching over path strings (no scope enforcement)
- [unicode_tools.md](unicode_tools.md) — `detect_confusables` authority
- [shell.md](shell.md) — shell-quoting companion for embedding paths in commands
- [exact.md](exact.md) — package-level overview

## Usage Example

```python
from eggcalc.exact.path_tools import path_analyze, path_normalize, path_compare, path_scope_check

print(path_analyze("/var/log/app.log")["suffix"])  # '.log'
print(path_normalize("/a/./b/../c")["normalized"])  # '/a/c'
print(path_compare("/A/B", "/a/b", case_sensitive=False)["equal"])  # True

gate = path_scope_check("/srv/app", "/srv/app/../etc/passwd")
print(gate["inside_root"])         # False
print(gate["escapes_via_dotdot"])  # True
```

(End of file - total 611 lines implementation)
