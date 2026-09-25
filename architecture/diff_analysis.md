# diff_analysis.py — Structural Diff Analysis

740 lines. Structural analysis of unified diffs: touched paths, hunk
ranges, headers, conflict markers, integrity validation.

## Table of Contents

- [Overview](#overview)
- [Type Definitions](#type-definitions)
- [Constants / Limits](#constants--limits)
- [Public Functions](#public-functions)
  - [diff_touched_paths](#diff_touched_paths)
  - [diff_hunk_ranges](#diff_hunk_ranges)
  - [diff_file_headers](#diff_file_headers)
  - [patch_conflict_markers_inspect](#patch_conflict_markers_inspect)
  - [unified_diff_validate](#unified_diff_validate)
- [Internal Helpers](#internal-helpers)
- [Dependencies](#dependencies)
- [Security Notes](#security-notes)
- [See Also](#see-also)

## Overview

Five pure functions over unified-diff text. Three parse via
`patch.parse_unified_diff` (touched paths, hunk ranges, file headers),
one scans raw text for merge-conflict markers, and one validates
structural integrity (parse success, hunk-header format, line-count
consistency). Never applies a patch — see `patch.py` for apply
simulation.

## Type Definitions

```python
class DiffTouchedPathsFile(TypedDict):
    path: str
    kind: str            # "added" | "deleted" | "renamed" | "modified"
    old_path: str | None
    new_path: str | None

class ModeChange(TypedDict):
    file: str
    old_mode: str | None
    new_mode: str | None

class DiffTouchedPathsResult(TypedDict):
    parse_ok: bool
    error: str | None
    added: list[str]
    deleted: list[str]
    renamed: list[DiffTouchedPathsFile]  # kind="renamed" entries with old/new paths
    modified: list[str]
    binary_files: list[str]
    mode_changes: list[ModeChange]
    total_files: int

class HunkDetail(TypedDict):
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    added_lines: int
    deleted_lines: int
    context_lines: int
    header_line: str       # raw "@@ -1,2 +1,2 @@" text

class DiffHunkRangesFile(TypedDict):
    old_file: str
    new_file: str
    hunks: list[HunkDetail]
    total_added: int
    total_deleted: int
    total_context: int

class DiffHunkRangesResult(TypedDict):
    parse_ok: bool
    error: str | None
    files: list[DiffHunkRangesFile]

class DiffFileHeaderEntry(TypedDict):
    old_file: str
    new_file: str
    diff_git_line: str | None
    index_line: str | None
    old_mode: str | None
    new_mode: str | None
    rename_from: str | None
    rename_to: str | None
    copy_from: str | None
    copy_to: str | None
    is_new_file: bool
    is_deleted_file: bool
    is_binary: bool
    hunks_count: int

class DiffFileHeadersResult(TypedDict):
    parse_ok: bool
    error: str | None
    files: list[DiffFileHeaderEntry]

class ConflictMarkerLocation(TypedDict):
    line: int              # 1-based
    kind: str              # "start" | "separator" | "end"

class PatchConflictMarkersResult(TypedDict):
    total_markers: int
    conflict_starts: int       # <<<<<<< count
    conflict_separators: int   # ======= count
    conflict_ends: int         # >>>>>>> count
    imbalanced: bool           # starts != ends
    nested: bool               # a start inside an open conflict
    locations: list[ConflictMarkerLocation]

class UnifiedDiffValidateResult(TypedDict):
    parse_ok: bool
    files_count: int
    hunks_total: int
    warnings: list[str]        # e.g. hunk line-count mismatches
    structure_valid: bool
```

## Constants / Limits

```python
_CONFLICT_START = re.compile(r"^<<<<<<<", re.MULTILINE)
_CONFLICT_SEP = re.compile(r"^=======$", re.MULTILINE)
_CONFLICT_END = re.compile(r"^>>>>>>>", re.MULTILINE)
```

Per-call `max_files=100` caps the files analyzed on the three
parse-based functions. Parse failures return `parse_ok=False` with an
`error` string — never raise.

## Public Functions

### `diff_touched_paths`

```python
def diff_touched_paths(patch_text: str, max_files: int = 100) -> DiffTouchedPathsResult
```

```python
PATCH = ("diff --git a/f.py b/f.py\n--- a/f.py\n+++ b/f.py\n"
         "@@ -1,2 +1,2 @@\n-old\n+new\n ctx\n")

diff_touched_paths(PATCH)
# → {"parse_ok": True, "error": None, "added": [], "deleted": [],
#     "renamed": [], "modified": ["b/f.py"], "binary_files": [],
#     "mode_changes": [], "total_files": 1}
```

### `diff_hunk_ranges`

```python
def diff_hunk_ranges(patch_text: str, max_files: int = 100) -> DiffHunkRangesResult
```

```python
diff_hunk_ranges(PATCH)["files"][0]
# → {"old_file": "a/f.py", "new_file": "b/f.py",
#     "hunks": [{"old_start": 1, "old_count": 2, "new_start": 1,
#                "new_count": 2, "added_lines": 1, "deleted_lines": 1,
#                "context_lines": 1, "header_line": "@@ -1,2 +1,2 @@"}],
#     "total_added": 1, "total_deleted": 1, "total_context": 1}
```

### `diff_file_headers`

```python
def diff_file_headers(patch_text: str, max_files: int = 100) -> DiffFileHeadersResult
```

Extracts `diff --git` / `index` / mode / rename-copy metadata per file
(with hunk counts and new/deleted/binary flags).

```python
diff_file_headers(PATCH)["files"][0]
# → {"old_file": "a/f.py", "new_file": "b/f.py",
#     "diff_git_line": "diff --git a/f.py b/f.py", "hunks_count": 1, ...}
```

### `patch_conflict_markers_inspect`

```python
def patch_conflict_markers_inspect(text: str) -> PatchConflictMarkersResult
```

Raw-text scan (no diff parsing): counts and locates `<<<<<<<` / `=======`
/ `>>>>>>>` markers, reports balance and nesting. Takes any text, not
just diffs.

```python
patch_conflict_markers_inspect("ok\n<<<<<<< HEAD\na\n=======\nb\n>>>>>>> branch\n")
# → {"total_markers": 3, "conflict_starts": 1, "conflict_separators": 1,
#     "conflict_ends": 1, "imbalanced": False, "nested": False,
#     "locations": [{"line": 2, "kind": "start"}, {"line": 4, "kind": "separator"},
#                   {"line": 6, "kind": "end"}]}
```

### `unified_diff_validate`

```python
def unified_diff_validate(
    patch_text: str, check_line_counts: bool = True
) -> UnifiedDiffValidateResult
```

```python
unified_diff_validate(PATCH)
# → {"parse_ok": True, "files_count": 1, "hunks_total": 1,
#     "warnings": [], "structure_valid": True}

unified_diff_validate("garbage")["structure_valid"]  # → False
```

With `check_line_counts=True`, hunk bodies whose `+`/`-`/` ` tallies
disagree with the `@@` header produce `warnings` entries (still parsed).

## Internal Helpers

| Helper | Role |
|--------|------|
| `_diff_normalize_line(line)` | Line-ending/whitespace normalization before classification |
| `_find_file_context(patch_text, match)` | Surrounding header lines for a hunk match |
| `_parse_hunk_header_simple(line)` | `@@ -a,b +c,d @@` → `(a,b,c,d)` or `None` |

## Dependencies

```
diff_analysis.py
    ├── re, typing        (stdlib)
    └── exact/patch.py    (parse_unified_diff)
```

Analysis only — `patch.py` owns parsing and apply simulation.

## Security Notes

- Diffs are untrusted input: paths, modes, and hunk counts are reported,
  never acted on. A `rename_from: /etc/passwd` entry is a string, not a
  filesystem operation — this module performs none.
- `max_files=100` bounds analysis cost on malicious thousand-file
  diffs; beyond the cap, later files are silently unreported, so check
  `total_files` before claiming full coverage.
- Conflict-marker scanning is purely lexical (`^<<<<<<<`): code that
  legitimately contains those bytes (tests, docs about merges) will
  flag — confirm with `imbalanced`/`locations` before failing a gate.

## See Also

- [patch.md](patch.md) — owns `parse_unified_diff`; apply simulation
- [diff.md](diff.md) — string diffing (first_diff, Levenshtein, LCS)
- [synthesis.md](synthesis.md) — `explain_diff` composes diff + confusables
