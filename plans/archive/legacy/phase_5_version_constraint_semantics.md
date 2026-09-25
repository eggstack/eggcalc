# Phase 5 Plan — Version and Constraint Semantics Tightening

## Objective

Make version comparison and version-constraint behavior explicit, deterministic, stdlib-only, and safe for agent use. The priority is to avoid silently incorrect behavior, especially around Python/PEP 440-style versions.

This phase should not add runtime dependencies. In particular, do not add `packaging` as a dependency. If PEP 440 support is implemented, it must be a deliberate stdlib-only subset with clear documented limitations.

## Background

The repo has version-oriented MCP tools such as `version_compare` and `version_constraint_check`. Existing docs indicate support for semver, loose numeric comparison, and deferred PEP 440. Since `eggcalc` itself is a Python package and includes manifest inspection tools, unclear PEP 440 behavior is a correctness risk for agents.

A clear unsupported error is better than a comparator that accepts Python versions and sorts them incorrectly.

## Constraints

Runtime remains stdlib-only.

Do not add `packaging` or any other dependency.

Do not expand the MCP tool inventory.

Do not silently change semver behavior without regression tests.

Do not claim full PEP 440 support unless the implemented behavior is tested against representative cases.

## Recommended strategy

Use a two-stage approach.

Stage A is mandatory and should be completed first: make current support boundaries explicit and test unsupported PEP 440 constructs.

Stage B is optional and should only be done if maintainers want a stdlib-only PEP 440 subset now.

## Stage A — Explicit support boundaries

### Desired behavior

Supported schemes should be named precisely. Unsupported schemes or unsupported constructs should fail with clear `invalid_arguments`, `unsupported_scheme`, or similar structured errors rather than producing misleading comparison results.

Examples that should not be silently mis-sorted if PEP 440 is deferred:

- `1!2.0`
- `1.0.dev1`
- `1.0a1`
- `1.0b1`
- `1.0rc1`
- `1.0.post1`
- `1.0+local`
- `2024.1`
- `1.0~=style` if constraints are parsed from user text

Exact accepted/rejected examples should be based on current parser behavior after inspection.

### Implementation steps

1. Inspect current implementation.

Review:

- `eggcalc/exact/version.py`
- MCP wrappers in `eggcalc/mcp/tools.py`
- schemas for `version_compare` and `version_constraint_check`
- tests covering version behavior
- docs mentioning semver, loose, or PEP 440

2. Define supported schemes.

Document what each scheme means:

- `semver`: strict or tolerant semantic versioning; define whether leading `v`, prerelease, build metadata, and missing patch are supported.
- `loose`: numeric-part comparison; define treatment of non-numeric suffixes.
- `pep440`: either unsupported/deferred or limited support.

3. Tighten validation.

If `pep440` is currently accepted but incomplete, change behavior to one of:

- reject `pep440` with a clear unsupported message, or
- accept only a documented narrow subset and reject everything else.

If semver or loose modes currently accept surprising input, either document that behavior or reject it clearly.

4. Update schemas.

Schema descriptions should not imply full PEP 440 support if it is deferred. If the schema enum includes `pep440`, the description must make the limitation obvious.

5. Update docs.

Update:

- `docs/mcp.md`
- `docs/tool_inventory.md` through generator/source metadata
- `docs/api.md` if public API exposes version helpers
- README only if it mentions version tools directly

6. Add tests.

Add table-driven tests for:

- semver equality and ordering
- semver prerelease/build metadata if supported
- loose numeric comparison
- unsupported PEP 440 constructs
- invalid constraints
- error envelope consistency through MCP wrappers

### Stage A acceptance criteria

- Docs and schemas do not overclaim PEP 440 support.
- Unsupported version constructs fail clearly.
- Semver and loose behavior are covered by table-driven tests.
- MCP wrappers return structured errors for unsupported or invalid inputs.
- No runtime dependency is added.

## Stage B — Optional stdlib-only PEP 440 subset

Only proceed with this stage if Stage A is complete and maintainers explicitly want more Python packaging support.

### Scope recommendation

Implement a bounded public-version subset rather than full packaging semantics.

Potentially supported:

- epoch: `N!`
- release segment: `N(.N)*`
- pre-release: `aN`, `bN`, `rcN`
- post-release: `.postN`
- dev-release: `.devN`
- local segment: `+local` for equality/tie-break only if implemented carefully

Potentially out of scope:

- arbitrary whitespace normalization
- legacy versions
- full local-version ordering nuances
- environment markers
- compatible-release operator semantics unless already implemented deliberately

### Parser design

Use a small regex-based parser in stdlib.

Return a structured internal representation such as:

```python
@dataclass(frozen=True)
class Pep440Version:
    epoch: int
    release: tuple[int, ...]
    pre: tuple[str, int] | None
    post: int | None
    dev: int | None
    local: tuple[str | int, ...] | None
```

If dataclasses are already allowed in runtime imports, use them. If not, use tuples or TypedDict according to existing style constraints.

Define ordering carefully before coding. PEP 440 ordering is subtle: dev releases sort before pre-releases, pre-releases sort before final releases, post releases sort after finals, and local versions have special handling.

### Test fixtures

Add fixtures for representative ordering:

- `1.0.dev1 < 1.0a1`
- `1.0a1 < 1.0b1`
- `1.0b1 < 1.0rc1`
- `1.0rc1 < 1.0`
- `1.0 < 1.0.post1`
- `1!0.1 > 999.0`
- release segment normalization such as `1.0 == 1.0.0` only if intentionally supported

Include rejection tests for unsupported forms.

### Stage B acceptance criteria

- Implemented subset is documented precisely.
- Unsupported PEP 440 forms fail clearly.
- Ordering tests cover epoch, release, pre, post, dev, and local handling if local is supported.
- No external dependency is introduced.
- MCP schema descriptions match implementation.

## Constraint-check semantics

Inspect `version_constraint_check` separately from raw version comparison.

Document and test supported operators:

- `==`
- `!=`
- `<`
- `<=`
- `>`
- `>=`
- caret or tilde if currently supported
- comma/AND constraints if currently supported
- wildcard constraints if currently supported

If a constraint syntax is not supported, reject it clearly. Avoid accepting syntax that is common in one ecosystem but not implemented correctly.

For semver, define prerelease behavior. For example, decide whether `1.0.0-alpha` satisfies `>=1.0.0` or not. If prerelease behavior is not implemented, reject prerelease constraints or document simple lexical behavior.

## Documentation updates

Docs should include a compact support matrix:

| Scheme | Compare support | Constraint support | Notes |
|---|---:|---:|---|
| semver | yes | yes/partial | define strictness |
| loose | yes | yes/partial | numeric parts only |
| pep440 | deferred/partial | deferred/partial | define exactly |

Also include examples of unsupported input and the expected error style.

## Validation commands

Run:

```bash
ruff check eggcalc tests
black --check eggcalc tests
python build_single.py
python scripts/generate_mcp_docs.py --check
pytest tests/ -v
mypy eggcalc --ignore-missing-imports
```

Manual MCP smoke examples:

- valid semver compare
- valid loose compare
- unsupported PEP 440 compare
- valid supported constraint
- invalid unsupported constraint

## Acceptance criteria

- Version behavior is explicit and tested.
- Unsupported PEP 440 constructs are not silently mis-sorted.
- Constraint syntax support is documented and tested.
- MCP schemas and docs match implementation.
- Runtime remains stdlib-only.
- CI remains green.

## Handoff notes

Prefer Stage A unless there is a direct need for PEP 440 support now. A precise limitation is safer than a rushed partial parser. If Stage B is implemented, keep it small, heavily table-tested, and honest in docs.
