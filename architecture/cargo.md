# cargo.py — Cargo.toml Inspection

498 lines. Deterministic Cargo.toml parsing and analysis.

## Table of Contents

- [Overview](#overview)
- [Type Definitions](#type-definitions)
- [Constants / Limits](#constants--limits)
- [Public Functions](#public-functions)
  - [cargo_toml_inspect](#cargo_toml_inspect)
- [Internal Helpers](#internal-helpers)
- [Dependencies](#dependencies)
- [Security Notes](#security-notes)
- [See Also](#see-also)

## Overview

Parses and analyzes `Cargo.toml` text with no network or filesystem
access (TOML via stdlib `tomllib`). One entry point returns package
metadata, workspace members, structured dependency forms (`version` /
`path` / `git` / `workspace` / inline table), path-dependency values,
suspicious names, and normalized duplicate/confusable names — all as
data plus shared `_Finding` items imported from `manifests.py`.

## Type Definitions

```python
class CargoPackageInfo(TypedDict, total=False):
    name: str | None
    version: str | None
    edition: str | None
    license: str | None
    repository: str | None
    readme: str | None

class CargoWorkspaceInfo(TypedDict):
    present: bool
    members: list[str]
    exclude: list[str]

class CargoDependencyForm(TypedDict, total=False):
    version: str | None
    path: str | None
    git: str | None
    workspace: bool         # `serde = { workspace = true }`
    inline_table: bool      # True for `{ ... }` forms, False for `"1.0"`
    registry: str | None
    branch: str | None
    tag: str | None
    features: list[str]
    optional: bool
    default_features: bool  # from `default-features` key

class CargoDepSection(TypedDict):
    dependencies: dict[str, CargoDependencyForm]
    dev_dependencies: dict[str, CargoDependencyForm]
    build_dependencies: dict[str, CargoDependencyForm]
    target_specific: dict[str, dict[str, CargoDependencyForm]]
    # e.g. {"cfg(windows)": {"winapi": {...}}}

class CargoInspectResult(TypedDict):
    parse_ok: bool
    package: CargoPackageInfo
    workspace: CargoWorkspaceInfo
    dependencies: CargoDepSection
    path_dependencies: list[str]             # collected `path = "..."` values
    suspicious_dependency_names: list[str]
    duplicate_or_confusable_dependency_names: list[str]
    findings: list[_Finding]                # shared manifests._Finding shape
```

`_Finding` (`code`, `severity ∈ {error, warning, info}`, `message`,
`line`, `column`) is owned by `manifests.py` and reused here unchanged.

## Constants / Limits

```python
_MAX_CARGO_INPUT_LENGTH = 200_000   # over-limit → parse_ok=False (no raise)

_CARGO_PACKAGE_FIELDS = {"name", "version", "edition", "license",
                         "repository", "readme"}
_EDITION_VALUES = {"2015", "2018", "2021", "2024"}

_SUSPICIOUS_NAME_PATTERNS = [   # any match → suspicious_dependency_names
    re.compile(r"^\d"),         # leading digit
    re.compile(r"_{2,}"),       # double underscore
    re.compile(r"--"),          # double dash
    re.compile(r"\."),          # dot in name
]
_CARGO_TOML_PATH_RE  # ^[a-zA-Z0-9_\-]+(?:/[a-zA-Z0-9_\-]+)*\.toml$
```

## Public Functions

### `cargo_toml_inspect`

```python
def cargo_toml_inspect(
    text: str,
    check_workspace: bool = True,
    check_dependencies: bool = True,
) -> CargoInspectResult
```

Never raises on bad input: TOML parse errors and over-limit inputs
return `parse_ok=False` with findings. Missing `[package] edition`
yields an info `CARGO_MISSING_EDITION` finding.

```python
cargo_toml_inspect('[package]\nname = "demo"\nversion = "0.1.0"\nedition = "2021"\n')
# → {"parse_ok": True,
#     "package": {"name": "demo", "version": "0.1.0", "edition": "2021"},
#     "findings": [], ...}

cargo_toml_inspect('[package]\nname = "demo"\nversion = "0.1.0"\n'
                   '[dependencies]\nserde = "1"\nfoo = { git = "https://x" }\n'
                   )["dependencies"]["dependencies"]
# → {"serde": {"version": "1", "inline_table": False, "workspace": False},
#     "foo": {"inline_table": True, "git": "https://x", "workspace": False}}

cargo_toml_inspect("not toml [[ [")["findings"][0]["code"]
# → "TOML_PARSE_ERROR"

cargo_toml_inspect('[workspace]\nmembers = ["a", "b"]\nexclude = ["x"]\n')["workspace"]
# → {"present": True, "members": ["a", "b"], "exclude": ["x"]}
```

## Internal Helpers

| Helper | Role |
|--------|------|
| `_is_cargo_toml_path(path)` | Lexical `*.toml` path check (no filesystem) |
| `_has_confusable_unicode(name)` | Lazy `unicode_tools.detect_confusables` probe |
| `_detect_suspicious_name(name)` | Pattern hits → `_Finding` list (distinct codes) |
| `_normalize_ident(name)` | NFKC + casefold + collapse `[-_.]+`→`_` for dupe grouping |
| `_detect_duplicates(names)` | Names sharing a normalized key (typosquats, `foo-bar` vs `foo_bar`) |
| `_parse_dep_value(raw)` | String vs inline-table → `CargoDependencyForm` |
| `_collect_path_deps(deps)` | Collects `path = "..."` values |

## Dependencies

```
cargo.py
    ├── re, unicodedata, typing, tomllib   (stdlib)
    ├── exact/manifests.py                 (_Finding, _finding, _truncate_findings)
    └── exact/unicode_tools.py             (detect_confusables — lazy import inside helper)
```

## Security Notes

- Dependency confusion surface is reported, not blocked: `git`/`path`/
  `registry` forms, `workspace = true` inheritance, and
  `duplicate_or_confusable_dependency_names` (NFKC/casefold/separator
  normalized) flag typosquat candidates for human review.
- Findings are capped/truncated via manifests' `_truncate_findings`
  (200 max) — a huge manifest stays bounded but may hide tail items.
- TOML parsing is stdlib `tomllib` (no `exec`, no code execution), but
  duplicate TOML keys are a parse error, not a merge — fractured inputs
  surface as `TOML_PARSE_ERROR`, never silent first-wins.

## See Also

- [manifests.md](manifests.md) — owns `_Finding`; pyproject/package.json/requirements/go.mod
- [unicode_tools.md](unicode_tools.md) — confusable detection behind name checks
- [version.md](version.md) — SemVer authority for interpreting `version = "..."` strings
