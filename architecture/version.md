# version.py — Version Constraint Checking

580 lines. Deterministic SemVer parsing, precedence, and constraint
satisfaction. Single SemVer parsing/precedence authority for the repo
(see `authority_inventory.md`).

## Table of Contents

- [Overview](#overview)
- [Type Definitions](#type-definitions)
- [Constants / Limits](#constants--limits)
- [Public Functions](#public-functions)
  - [parse_version](#parse_version)
  - [compare_versions (+ predicates)](#compare_versions--predicates)
  - [check_version_constraint](#check_version_constraint)
- [Internal Helpers](#internal-helpers)
- [Dependencies](#dependencies)
- [Security Notes](#security-notes)
- [See Also](#see-also)

## Overview

Strict SemVer parsing plus constraint satisfaction without external
dependencies. Supports comparison operators (`>=`, `<=`, `>`, `<`, `=`,
`!=`, bare `1.2.3`), Cargo caret (`^`) and tilde (`~`) ranges, `N.*`
wildcards, and comma-separated intersections (`>=1.0.0, <2.0.0`).
`^`/`~` always evaluate with Cargo semantics and report `scheme: "cargo"`
regardless of the `scheme` argument; `scheme` is a reporting hint for
those operators, not a gate.

Repo authority note: `version_compare(..., scheme="semver")` in
`exact/validate.py` delegates here; `loose` comparison stays in
`validate.py` by design.

## Type Definitions

```python
class ParsedVersion(TypedDict):
    major: int
    minor: int
    patch: int
    pre_release: list[str]   # [] when absent; e.g. ["alpha", "1"]
    build: str               # "" when absent (ignored in precedence)
    raw: str                 # original input text

class ParsedConstraintComponent(TypedDict):
    operator: str            # ">=" | "<" | ... (caret/tilde expand to pairs)
    version: ParsedVersion

class ParsedConstraint(TypedDict):
    raw: str                 # original constraint text
    scheme: str              # "semver" | "cargo"
    components: list[ParsedConstraintComponent]
    type: str                # "comparison" | "caret" | "tilde" | "wildcard"

class VersionConstraintResult(TypedDict, total=False):
    satisfies: bool
    parsed_version: ParsedVersion | None
    parsed_constraint: ParsedConstraint | None
    scheme: str
    explanation: str         # e.g. "1.2.3 satisfies >=1.0.0"
    findings: list[str]
```

## Constants / Limits

```python
_SEMVER_RE      # strict ^MAJOR.MINOR.PATCH(-pre)?(\+build)?$  (no leading zeroes)
_SEMVER_LAX_RE  # accepts partial "1.2" → 1.2.0 (used by _parse_version_lax only)
_NUMERIC_IDENTIFIER / _PRE_RELEASE_IDENTIFIER / _PRE_RELEASE / _BUILD
```

Strictness facts (verified): `"1.2"` → `None`, `"v1.2.3"` → `None`,
`"1.2.3.4"` → `None`, `"01.2.3"` → `None`, but surrounding whitespace is
tolerated (`" 1.2.3 "` parses). No numeric caps — components are plain
ints.

## Public Functions

### `parse_version`

```python
def parse_version(version: str) -> ParsedVersion | None
```

Strict SemVer only; returns `None` (never raises) on mismatch.

```python
parse_version("1.2.3")
# → {"major": 1, "minor": 2, "patch": 3, "pre_release": [],
#     "build": "", "raw": "1.2.3"}

parse_version("1.2.3-alpha+build")["pre_release"]  # → ["alpha"]

parse_version("1.2")    # → None (use check_version_constraint for ranges)
parse_version("v1.2")   # → None
```

### `compare_versions (+ predicates)`

```python
def compare_versions(a: ParsedVersion, b: ParsedVersion) -> int
def version_less_than(a: ParsedVersion, b: ParsedVersion) -> bool
def version_equal(a: ParsedVersion, b: ParsedVersion) -> bool
def version_lte(a: ParsedVersion, b: ParsedVersion) -> bool
def version_gte(a: ParsedVersion, b: ParsedVersion) -> bool
def version_gt(a: ParsedVersion, b: ParsedVersion) -> bool
```

SemVer precedence: numeric `major/minor/patch`, then pre-release
(absent > present; numeric < alphanumeric identifiers), build metadata
ignored. Returns `-1` / `0` / `1`.

```python
compare_versions(parse_version("1.2.3"), parse_version("1.2.4"))  # → -1
version_less_than(parse_version("1.0.0-alpha"), parse_version("1.0.0"))  # → True
compare_versions(parse_version("1.2.3+a"), parse_version("1.2.3+b"))     # → 0
```

### `check_version_constraint`

```python
def check_version_constraint(
    version: str,
    constraint: str,
    scheme: str = "semver",
) -> VersionConstraintResult
```

Never raises on bad input: unparseable versions/constraints yield
`satisfies=False` with `parsed_*=None` and an explanatory `findings`
entry. Verified grammar notes:

- Comma-separated intersections work (`">=1.0.0, <2.0.0"`); bare
  space-separated ranges do **not** (`">=1.0.0 <2.0.0"` → invalid).
- Bare versions mean equality (`"1.2.3"` ≡ `"=1.2.3"`).
- Wildcards are `N.*` (`"1.*"` satisfies `1.2.3`); lone `"*"` is invalid
  in both schemes; `"1.x"` is invalid (use `"1.*"`).
- `^`/`~` report `scheme: "cargo"` even when called with
  `scheme="semver"`.

```python
check_version_constraint("1.2.3", ">=1.0.0")["satisfies"]  # → True

check_version_constraint("2.0.0", "^1.0.0")
# → {"satisfies": False, "scheme": "cargo",
#     "explanation": "2.0.0 does not satisfy ^1.0.0", ...}

check_version_constraint("1.2.3", "~1.2.0")["satisfies"]   # → True
check_version_constraint("1.2.3", "1.*", scheme="cargo")["satisfies"]  # → True
check_version_constraint("bad", ">=1.0.0")["explanation"]
# → "Invalid version: 'bad'"
```

## Internal Helpers

| Helper | Role |
|--------|------|
| `_make_version(major, minor, patch, pre, build, raw)` | Builds `ParsedVersion` from regex groups |
| `_parse_pre_release_identifiers(ident)` | Splits `alpha.1` → `["alpha","1"]` |
| `_compare_pre_release(a, b)` | SemVer §11 ordering (−1/0/1) |
| `_sort_pre_release_key(ident)` | Sort key helper (numeric < alphanumeric) |
| `_parse_version_lax(version)` | Partial `"1.2"` → `1.2.0`; **not** used by `parse_version` (kept for constraint bounds) |
| `_parse_comparison_constraint(constraint)` | Splits one `op + version` component |
| `_cargo_caret_range(version)` | `^M.m.p` → `[>=M.m.p, <next-breaking)` (0-major aware) |
| `_cargo_tilde_range(version)` | `~M.m.p` → `[>=M.m.p, <M.(m+1).0)` |
| `_cargo_wildcard_range(constraint)` | `N.*` → `[>=N.0.0, <(N+1).0.0)` |
| `_evaluate_component(ver, op, bound)` | Single `op` test via the predicate helpers |
| `_range_constraint_result(...)` | Assembles `VersionConstraintResult` for range types |

## Dependencies

```
version.py
    └── (standard library only: re, typing)
```

No `exact/` imports — fully standalone leaf and the repo's SemVer
authority.

## Security Notes

- Fail-closed on garbage: unparseable input never raises, never returns
  `satisfies=True` — always `False` with an explanation. Safe to use in
  gates without try/except.
- Pre-release semantics follow SemVer strictly (`1.0.0-alpha < 1.0.0`);
  dependency-range checks that ignore pre-releases must filter them
  before calling — the module will not do it for you.
- No network, no package-manager queries: constraint strings are matched
  against one version at a time; "latest satisfying" resolution lives
  outside this module.

## See Also

- [validate.md](validate.md) — `version_compare` delegates here (`semver`); `loose` stays there
- [manifests.md](manifests.md) — `requires_python` / dependency strings are *not* resolved here
- [cargo.md](cargo.md) — `version = "..."` strings in Cargo.toml can be fed to `parse_version`
