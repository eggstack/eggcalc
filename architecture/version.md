# version.py — Version Constraint Checking

545 lines. Deterministic semver and Cargo version parsing and constraint satisfaction.

## Overview

Parses version strings and checks constraint satisfaction without external dependencies. Supports semver and Cargo-style caret (`^`), tilde (`~`), wildcard (`*`), and comparison (`>=`, `<`, `!=`, etc.) constraints.

## Key Exports

```python
from eggcalc.exact.version import (
    parse_version,
    check_version_constraint,
)
```

## Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `parse_version(version)` | `ParsedVersion \| None` | Parses a semver version string |
| `check_version_constraint(version, constraint, scheme="semver")` | `VersionConstraintResult` | Checks whether a version satisfies a constraint |

## Schemes

| Scheme | Constraints |
|--------|-------------|
| `semver` | `>=`, `<=`, `>`, `<`, `=`, `!=`, `~`, `^`, `*` ranges |
| `cargo` | Cargo-style caret (`^`) and tilde (`~`) semantics |

## Module Dependencies

- `re`, `typing`
