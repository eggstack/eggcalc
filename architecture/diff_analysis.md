# diff_analysis.py — Structural Diff Analysis

736 lines. Structural analysis tools for unified diffs and patches.

## Overview

Five pure functions that classify touched files, extract hunk ranges, extract file header metadata, detect conflict markers, and validate diff structural integrity. Depends on `patch.py` for `parse_unified_diff`.

## Key Exports

```python
from eggcalc.exact.diff_analysis import (
    diff_touched_paths,
    diff_hunk_ranges,
    diff_file_headers,
    patch_conflict_markers_inspect,
    unified_diff_validate,
)
```

## Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `diff_touched_paths(patch_text, max_files=100)` | `DiffTouchedPathsResult` | Classifies files as added/deleted/renamed/modified; detects binary diffs and mode changes |
| `diff_hunk_ranges(patch_text, max_files=100)` | `DiffHunkRangesResult` | Extracts hunk ranges per file with added/deleted/context line counts |
| `diff_file_headers(patch_text, max_files=100)` | `DiffFileHeadersResult` | Extracts metadata from diff file headers: git diff lines, index hashes, mode changes, rename/copy directives |
| `patch_conflict_markers_inspect(text)` | `PatchConflictMarkersResult` | Detects conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`); reports counts, balance, nesting, line locations |
| `unified_diff_validate(patch_text, check_line_counts=True)` | `UnifiedDiffValidateResult` | Validates structural integrity: parse success, hunk header format, line count consistency |

## TypedDict Classes

- `DiffTouchedPathsResult` — `parse_ok`, `error`, `added`, `deleted`, `renamed`, `modified`, `binary_files`, `mode_changes`, `total_files`
- `DiffHunkRangesResult` — `parse_ok`, `error`, `files` (list of `DiffHunkRangesFile`)
- `DiffFileHeadersResult` — `parse_ok`, `error`, `files` (list of `DiffFileHeaderEntry`)
- `PatchConflictMarkersResult` — `total_markers`, `imbalanced`, `nested`, `locations`
- `UnifiedDiffValidateResult` — `parse_ok`, `files_count`, `hunks_total`, `warnings`, `structure_valid`

## Module Dependencies

- `re`, `typing`
- `.patch` (`parse_unified_diff`)

## See Also

- [diff.md](diff.md) — String diffing algorithms (first_diff, Levenshtein, LCS)
- [patch.md](patch.md) — Unified diff parsing and simulation
