# version.py — Version Constraint Checking

Deterministic semver and Cargo version parsing and constraint satisfaction. Single SemVer parsing/precedence authority for the repo (see `authority_inventory.md`).

## Overview

Parses version strings and checks constraint satisfaction without external dependencies. Supports semver and Cargo-style caret (`^`), tilde (`~`), wildcard (`*`), and comparison (`>=`, `<`, `!=`, etc.) constraints. `version_compare(..., scheme="semver")` in `exact/validate.py` delegates here; `loose` comparison stays in `validate.py` by design.

## Key Exports

```python
from eggcalc.exact.version import (
    parse_version,
    compare_versions,
    check_version_constraint,
)
```

## Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `parse_version(version)` | `ParsedVersion \| None` | Parses a strict semver version string |
| `compare_versions(a, b)` | `int` | SemVer precedence: -1/0/1 (build ignored, pre-release sorts lower) |
| `version_less_than(a, b)` / `version_equal(a, b)` / `version_lte` / `version_gte` / `version_gt` | `bool` | Predicate helpers used by `compare_versions` and constraint checks |
| `check_version_constraint(version, constraint, scheme="semver")` | `VersionConstraintResult` | Checks whether a version satisfies a constraint |

## Schemes

| Scheme | Constraints |
|--------|-------------|
| `semver` | `>=`, `<=`, `>`, `<`, `=`, `!=`, `~`, `^`, `*` ranges |
| `cargo` | Cargo-style caret (`^`) and tilde (`~`) semantics |

Note: `^` and `~` are accepted regardless of the `scheme` argument and always evaluate with cargo semantics (the result reports `scheme: "cargo"`); `scheme` is a reporting hint for those operators, not a gate.

## Module Dependencies

- `re`, `typing`
