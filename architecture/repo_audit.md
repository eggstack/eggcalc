# repo_audit.py — Repository File Inventory

422 lines. Deterministic repository file inventory analysis.

## Overview

Analyzes file inventories for repo structure signals without filesystem access: extension counts, category classification, language/ecosystem detection, config file identification, vendor/generated/suspicious path detection, duplicate hash detection.

## Key Exports

```python
from eggcalc.exact.repo_audit import repo_file_inventory
```

## Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `repo_file_inventory(paths, sizes=None, hashes=None)` | `RepoInventoryResult` | Analyzes file inventory: language detection, category counts, suspicious/vendor/generated paths, duplicate detection |

## Module Dependencies

- `os`, `collections`, `typing`
