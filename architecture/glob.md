# glob.py — Glob Pattern Matching

311 lines. Deterministic glob pattern matching with POSIX and Windows path separator support.

## Overview

Matches glob patterns against paths. `*` matches within a segment, `**` matches zero or more segments, `?` matches one character. Supports case-sensitive and case-insensitive matching.

## Key Exports

```python
from eggcalc.exact.glob import glob_match
```

## Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `glob_match(pattern, path, platform="posix", case_sensitive=True)` | `GlobMatchResult` | Matches a glob pattern against a path |

## TypedDict: GlobMatchResult

| Field | Type | Description |
|-------|------|-------------|
| `matches` | `bool` | Whether the pattern matches |
| `normalized_pattern` | `str` | Normalized pattern |
| `normalized_path` | `str` | Normalized path |
| `matched_segment` | `str \| None` | The segment that matched (for `*`) |
| `unmatched_segment` | `str \| None` | The segment that didn't match |

## Module Dependencies

- `re`, `typing`
