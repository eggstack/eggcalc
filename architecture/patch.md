# patch.py — Unified Diff Parsing

641 lines. Parses unified diffs and simulates patch application on in-memory text.

## Overview

Parses unified diffs into structured data, checks whether patches apply cleanly to in-memory text without modifying files, and summarizes patch contents.

## Key Exports

```python
from eggcalc.exact.patch import (
    parse_unified_diff,
    check_patch_apply,
    patch_summary,
)
```

## Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `parse_unified_diff(patch_text)` | `PatchParseResult` | Parses a unified diff string into structured files and hunks |
| `check_patch_apply(patch_text, original_text, ...)` | `PatchApplyCheckResult` | Checks whether a patch applies cleanly to in-memory text |
| `patch_summary(patch_text)` | `PatchSummaryResult` | Summarizes a unified diff: files changed, hunks, additions/deletions |

## Module Dependencies

- `hashlib`, `re`, `typing`

## See Also

- [diff_analysis.md](diff_analysis.md) — Structural analysis of unified diffs
- [diff.md](diff.md) — String diffing algorithms
