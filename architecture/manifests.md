# manifests.py — Manifest Inspection

868 lines. Deterministic manifest/package inspection without network or filesystem access.

## Overview

Lexical/structural inspection of project manifests: `pyproject.toml`, `package.json`, `requirements.txt`, `go.mod`, and lockfiles. Parses build backends, dependency counts, workspace configs, scripts, and produces structured findings.

## Key Exports

```python
from eggcalc.exact.manifests import (
    pyproject_inspect,
    package_json_inspect,
    requirements_inspect,
    go_mod_inspect,
    lockfile_summary,
)
```

**Note:** These functions are NOT re-exported from `eggcalc.exact.__init__`. Import directly from `eggcalc.exact.manifests`.

## Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `pyproject_inspect(text)` | `PyprojectInspectResult` | Inspects pyproject.toml: project metadata, build backend, dependencies, scripts |
| `package_json_inspect(text)` | `PackageJsonInspectResult` | Inspects package.json: name, version, scripts, dependency counts, engines |
| `requirements_inspect(text)` | `RequirementsInspectResult` | Inspects requirements.txt: package specs, editable refs, direct URLs, VCS refs |
| `go_mod_inspect(text)` | `GoModInspectResult` | Inspects go.mod: module path, go version, require count, replace/exclude |
| `lockfile_summary(text, kind="auto")` | `LockfileSummaryResult` | Produces a shallow summary of a lockfile: auto-detects kind, estimates package count |

## Module Dependencies

- `json`, `typing`

## See Also

- [cargo.md](cargo.md) — Cargo.toml inspection (IS re-exported from `__init__`)
