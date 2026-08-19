# cargo.py — Cargo.toml Inspection

508 lines. Deterministic Cargo.toml parsing and analysis.

## Overview

Parses and analyzes Cargo.toml content without network or filesystem access. Extracts package metadata, workspace member analysis, dependency form parsing (version/path/git/workspace/inline), suspicious name detection, and duplicate/confusable name detection.

## Key Exports

```python
from eggcalc.exact.cargo import cargo_toml_inspect
```

## Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `cargo_toml_inspect(text, check_workspace=True, check_dependencies=True)` | `CargoInspectResult` | Inspects Cargo.toml text: parses package, workspace, dependencies; detects suspicious/confusable names |

## Module Dependencies

- `re`, `unicodedata`, `typing`
- `eggcalc.exact.manifests` (`_Finding`, `_finding`, `_truncate_findings`)

## See Also

- [manifests.md](manifests.md) — pyproject.toml, package.json, requirements.txt inspection
