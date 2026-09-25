# manifests.py — Manifest Inspection

875 lines. Deterministic manifest/package inspection without network or
filesystem access. Owns the shared `_Finding` TypedDict reused by
`cargo.py`.

## Table of Contents

- [Overview](#overview)
- [Type Definitions](#type-definitions)
- [Constants / Limits](#constants--limits)
- [Public Functions](#public-functions)
  - [pyproject_inspect](#pyproject_inspect)
  - [package_json_inspect](#package_json_inspect)
  - [requirements_inspect](#requirements_inspect)
  - [go_mod_inspect](#go_mod_inspect)
  - [lockfile_summary](#lockfile_summary)
- [Internal Helpers](#internal-helpers)
- [Dependencies](#dependencies)
- [Security Notes](#security-notes)
- [See Also](#see-also)

## Overview

Lexical/structural inspection of five manifest families plus shallow
lockfile summaries:

- `pyproject_inspect()` — `pyproject.toml` via stdlib `tomllib`:
  project name/version, build backend, `requires-python`, dependency
  counts, optional groups, scripts/entry points, tool sections.
- `package_json_inspect()` — `package.json` via `json`: name, version,
  private/type, script keys, dep/dev/peer/optional counts, engines,
  package manager, workspaces.
- `requirements_inspect()` — `requirements.txt` line grammar: package
  specs, `-e` editable refs, direct URLs, VCS refs, `-r`/`-c` includes,
  `--index-url`/`--hash` options, environment markers, suspicious lines.
- `go_mod_inspect()` — `go.mod` line grammar: module path, go/toolchain
  versions, require count, replace/exclude directives.
- `lockfile_summary()` — shallow kind detection + approximate package
  count for 9 lockfile ecosystems (no full parse).

**Not re-exported** from `eggcalc.exact.__init__` — import directly from
`eggcalc.exact.manifests`. Never raises on bad input: parse failures
return `parse_ok=False` with findings.

## Type Definitions

```python
class _Finding(TypedDict, total=False):   # SHARED with cargo.py
    code: str        # e.g. "TOML_PARSE_ERROR", "MISSING_PROJECT_NAME"
    severity: str    # "error" | "warning" | "info"
    message: str
    line: int        # default 0
    column: int      # default 0

class PyprojectInspectResult(TypedDict, total=False):
    parse_ok: bool
    project_name: str | None
    project_version: str | None
    build_backend: str | None
    build_requirements: list[str]
    build_backend_path: list[str] | None
    requires_python: str | None
    dependencies_count: int
    optional_dependency_groups: list[str]
    scripts: dict[str, str]
    tool_sections: list[str]
    package_manager_signals: list[str]
    dynamic: list[str]
    entry_points: dict[str, dict[str, str]]
    gui_scripts: dict[str, str]
    urls: dict[str, str]
    findings: list[_Finding]

class PackageJsonInspectResult(TypedDict, total=False):
    parse_ok: bool
    name: str | None
    version: str | None
    private: bool
    package_type: str | None        # "module" | "commonjs" | ...
    scripts_keys: list[str]
    dependencies_count: int
    dev_dependencies_count: int
    peer_dependencies_count: int
    optional_dependencies_count: int
    engines: dict[str, str]
    package_manager: str | None
    workspaces: list[str] | None
    findings: list[_Finding]

class RequirementsInspectResult(TypedDict, total=False):
    parse_ok: bool
    total_lines: int
    package_specs: list[str]        # e.g. ["requests==2.0"]
    editable_refs: list[str]        # `-e ...` lines
    direct_urls: list[str]          # bare http(s) URLs
    vcs_refs: list[str]             # git+/hg+/svn+ lines
    comments: list[str]
    requirement_includes: list[str] # `-r ...` lines
    constraints_includes: list[str] # `-c ...` lines
    index_options: list[str]        # --index-url / --extra-index-url
    hash_options: list[str]         # --hash=...
    environment_markers: list[str]  # specs with `;` markers
    suspicious_lines: list[str]
    findings: list[_Finding]

class GoModInspectResult(TypedDict, total=False):
    parse_ok: bool
    module_path: str | None
    go_version: str | None
    toolchain: str | None
    require_count: int
    replace_directives: list[dict[str, str]]  # {"old","new"}
    exclude_directives: list[dict[str, str]]  # {"module","version"}
    findings: list[_Finding]

class LockfileSummaryResult(TypedDict, total=False):
    parse_ok: bool
    detected_kind: str     # "package-lock" | "cargo-lock" | ... | "unknown"
    ecosystem: str | None  # "npm" | "cargo" | ... (None when unknown)
    approximate_package_count: int
    warnings: list[str]
    findings: list[_Finding]
```

## Constants / Limits

```python
_MAX_INPUT_length = 500_000   # over-limit → parse_ok=False + INPUT_TOO_LONG
_MAX_FINDINGS = 200           # _truncate_findings cap (appends truncation notice)

_KNOWN_PIP_OPTIONS = frozenset({...})  # recognized --index-url/--hash/... flags

_LOCKFILE_SIGNATURES = [      # (filename probe, kind, ecosystem)
    ("package-lock.json", "package-lock", "npm"),
    ("pnpm-lock.yaml", "pnpm-lock", "pnpm"),
    ("yarn.lock", "yarn-lock", "yarn"),
    ("poetry.lock", "poetry-lock", "poetry"),
    ("uv.lock", "uv-lock", "uv"),
    ("Cargo.lock", "cargo-lock", "cargo"),
    ("go.sum", "go-sum", "go"),
    ("Pipfile.lock", "pipenv", "pipenv"),
    ("composer.lock", "composer", "php"),
]
_KIND_TO_ECOSYSTEM = {k: eco for _, k, eco in _LOCKFILE_SIGNATURES}
```

Finding codes (verified): `INVALID_INPUT`, `INPUT_TOO_LONG`,
`TOML_PARSE_ERROR` (with tomllib line/col), `JSON_PARSE_ERROR`,
`MISSING_PROJECT_NAME` (warning), `MISSING_PROJECT_VERSION` (info),
`UNKNOWN_LOCKFILE` (info).

## Public Functions

### `pyproject_inspect`

```python
def pyproject_inspect(text: str) -> PyprojectInspectResult
```

```python
pyproject_inspect('[project]\nname = "demo"\nversion = "0.1.0"\n'
                  'dependencies = ["requests"]\n')
# → {"parse_ok": True, "project_name": "demo",
#     "project_version": "0.1.0", "dependencies_count": 1, ...}

pyproject_inspect("not toml [[[")["findings"][0]["code"]
# → "TOML_PARSE_ERROR"
```

### `package_json_inspect`

```python
def package_json_inspect(text: str) -> PackageJsonInspectResult
```

```python
package_json_inspect('{"name": "demo", "version": "1.0.0",'
                     ' "dependencies": {"react": "^18"}}')
# → {"parse_ok": True, "name": "demo", "dependencies_count": 1, ...}

package_json_inspect("{bad json")["findings"][0]["code"]
# → "JSON_PARSE_ERROR"
```

### `requirements_inspect`

```python
def requirements_inspect(text: str) -> RequirementsInspectResult
```

```python
requirements_inspect("requests==2.0\n-e .\ngit+https://github.com/x/y\n")
# → {"parse_ok": True, "total_lines": 3,
#     "package_specs": ["requests==2.0"], "editable_refs": ["-e ."],
#     "vcs_refs": ["git+https://github.com/x/y"], ...}

requirements_inspect("requests==2.0; python_version > \"2.7\"\n")["environment_markers"]
# → ['requests==2.0; python_version > "2.7"']
```

### `go_mod_inspect`

```python
def go_mod_inspect(text: str) -> GoModInspectResult
```

```python
go_mod_inspect("module example.com/demo\n\ngo 1.21\n")
# → {"parse_ok": True, "module_path": "example.com/demo",
#     "go_version": "1.21", "require_count": 0, ...}
```

Single-line and parenthesized `require`/`replace`/`exclude` blocks both
count; `replace a => b v1.0.0` yields `{"old": ..., "new": ...}`.

### `lockfile_summary`

```python
def lockfile_summary(text: str, kind: str = "auto") -> LockfileSummaryResult
```

Shallow only: `kind` must be the canonical kind (`"cargo-lock"`,
`"package-lock"`, `"poetry-lock"`, …) — filename-style values like
`"Cargo.lock"` echo back with count 0. `"auto"` probes content for
filename markers, then content signatures (`"lockfileVersion"` → npm,
`[metadata]`+`lock-version` → poetry, …), else `"unknown"`.

```python
lockfile_summary('[[package]]\nname = "a"\n[[package]]\nname = "b"\n',
                 kind="cargo-lock")
# → {"parse_ok": True, "detected_kind": "cargo-lock",
#     "ecosystem": "cargo", "approximate_package_count": 2, ...}

lockfile_summary('{"lockfileVersion": 3, "packages": {"a": {}}}', kind="auto")
# → {"detected_kind": "package-lock", "ecosystem": "npm",
#     "approximate_package_count": 1, ...}
```

Counting is heuristic per kind (`name = "` occurrences for
cargo/poetry/uv, `packages`/`dependencies` keys for npm, quote-quarter
for yarn, non-blank lines for go.sum).

## Internal Helpers

| Helper | Role |
|--------|------|
| `_finding(code, severity, message, line=0, column=0)` | Builds a `_Finding` (shared with `cargo.py`) |
| `_truncate_findings(findings)` | Caps at `_MAX_FINDINGS` with truncation notice |
| `_extract_workspaces(data)` | `package.json` workspaces (list or `{"packages": [...]}`) |
| `_check_req_suspicious(...)` | Flags suspicious requirement lines |
| `_parse_go_replace(line)` / `_parse_go_replace_inline(line)` | `replace` directives (block vs inline) |
| `_parse_go_exclude(line)` / `_parse_go_exclude_inline(line)` | `exclude` directives (block vs inline) |

## Dependencies

```
manifests.py
    └── (standard library only: json, tomllib, re, typing)
```

No `exact/` imports. `cargo.py` imports *from* here
(`_Finding`, `_finding`, `_truncate_findings`) — the dependency runs
one way only.

## Security Notes

- Findings over exceptions: every malformed input returns data, so
  agents can triage hostile manifests without try/except scaffolding.
  Only non-`str` input to `lockfile_summary` is a shape edge
  (`parse_ok=False`, `INVALID_INPUT`).
- Counts are approximate by design — `approximate_package_count` must
  not gate billing, policy, or "fully locked" claims; re-parse with a
  real lockfile parser for enforcement.
- Requirement/VCS/URL extraction is lexical: `--index-url` exfiltration
  hosts, `git+ssh` refs, and `-e` local paths are *reported* for review,
  never fetched or resolved.

## See Also

- [cargo.md](cargo.md) — reuses `_Finding`; Cargo.toml inspection (IS re-exported)
- [config.md](config.md) — `.env`/INI validation, same findings style
- [version.md](version.md) — SemVer authority for interpreting version strings found here
