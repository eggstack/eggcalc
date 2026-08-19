# path_tools.py — Path Lexical Analysis

615 lines. Deterministic path parsing without filesystem access.

## Overview

Analyzes path components, extensions, hidden status, traversal, normalization, comparison, and scope checking for POSIX and Windows paths. No filesystem operations — purely lexical.

## Key Exports

```python
from eggcalc.exact.path_tools import (
    path_analyze,
    path_normalize,
    path_compare,
    path_scope_check,
)
```

## Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `path_analyze(path, style="auto")` | `PathAnalyzeResult` | Lexically analyzes path components, extensions, hidden status, traversal |
| `path_normalize(path, platform="posix", ...)` | `PathNormalizeResult` | Lexically normalizes a path by collapsing dot segments |
| `path_compare(left, right, platform="posix", ...)` | `PathCompareResult` | Lexically compares two paths under explicit normalization rules |
| `path_scope_check(root, target, platform="posix", ...)` | `PathScopeCheckResult` | Determines whether a target path stays inside a declared root |

## Module Dependencies

- `re`, `typing`
- `.unicode_tools` (`detect_confusables`)
