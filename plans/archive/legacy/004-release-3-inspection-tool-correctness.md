# Release 3 Plan — Inspection-Tool Correctness

Status: ready for implementation handoff  
Depends on: Release 1 semantic baseline; may proceed largely in parallel with Release 2  
Roadmap: `plans/001-correctness-protocol-hardening-roadmap.md`

## 1. Release objective

Make manifest, requirements, lockfile, Cargo, and repository-inspection tools semantically reliable rather than merely tolerant of input.

The release addresses known defects in `pyproject_inspect()` and `requirements_inspect()`, then uses those fixes as the basis for a common inspection result contract and representative golden fixtures across supported ecosystems.

No new inspection tool categories should be added until this release is complete.

## 2. Scope

In scope:

- `eggcalc/exact/manifests.py`
- `eggcalc/exact/cargo.py`
- Relevant MCP wrappers and schemas
- Related generated tool documentation
- Manifest, requirements, Cargo, lockfile, and repository-audit tests
- Common finding shape and severity policy

Out of scope:

- Network package metadata lookup
- Dependency resolution
- Filesystem access from pure inspection primitives
- Full PEP 508 parser implementation
- Full TOML parser implementation
- New ecosystems beyond those already advertised

## 3. Required semantic contract

Inspection primitives must remain:

- Pure and side-effect-free.
- Network-free.
- Filesystem-free unless a separate explicitly scoped repository-inventory wrapper already owns file-list input.
- Deterministic for identical text input.
- Bounded by input length and finding count.
- Conservative: distinguish confirmed parse facts from lexical heuristics.

Every result should clearly separate:

- Parse success.
- Extracted metadata.
- Findings.
- Warnings about unsupported or ambiguous syntax.

## 4. Workstream A — Correct `pyproject_inspect()`

### A1. Build-system extraction

Correctly read:

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"
backend-path = ["build_backend"]
```

Return distinct fields:

```text
build_backend
build_requirements
build_backend_path
```

Do not derive `build_backend` from the first `requires` entry.

Update the result TypedDict and MCP output schema accordingly.

### A2. Tool-section extraction

`tomllib` produces nested dictionaries. Extract nested tool names from `data["tool"]`, not top-level keys prefixed with `tool.`.

Recommended output:

```text
tool_sections = ["tool.black", "tool.mypy", "tool.pytest", "tool.ruff"]
```

Sort output deterministically.

Handle malformed non-table `[tool]` values conservatively, although valid TOML should normally prevent such a shape.

### A3. Parse-error location

Correct error attribute access so line and column information is captured when exposed by the active Python version.

Finding fields should support:

```text
line
column
```

Do not depend on a misspelled or version-specific attribute without fallback handling.

### A4. Project metadata coverage

Review and test extraction for:

- `project.name`
- `project.version`
- `project.dynamic`
- `project.requires-python`
- `project.dependencies`
- `project.optional-dependencies`
- `project.scripts`
- `project.gui-scripts`
- `project.entry-points`
- `project.urls`
- `build-system.requires`
- `build-system.build-backend`
- `build-system.backend-path`

Do not over-expand the public result shape without use cases. At minimum, preserve current fields and add the fields needed to correct known defects.

### A5. Packaging-tool signals

Detect nested tables accurately for:

- Poetry
- PDM
- Hatch
- uv
- setuptools
- Flit

Clarify that these are signals, not a definitive package-manager selection. A project may legitimately contain multiple tool sections.

### A6. Findings policy

Use structured findings for:

- Missing project name.
- Missing static version when not declared dynamic.
- Missing build backend metadata.
- Conflicting packaging signals where genuinely meaningful.
- Invalid root/table shapes where parse succeeds but semantic types are unexpected.

Avoid treating common valid configurations as suspicious.

## 5. Workstream B — Correct requirements-file inspection

### B1. Replace broad suspicious-character matching

The current heuristic must not flag ordinary requirement syntax such as:

```text
requests[socks]>=2.32
uvicorn[standard]<1
package!=1.2.3
package~=2.0
```

Remove brackets and standard comparison operators from the blanket suspicious-character rule.

### B2. Implement a conservative lexical classifier

Classify lines in a deterministic order:

1. Empty/comment.
2. Continuation of previous line.
3. Requirement include.
4. Constraint include.
5. Editable requirement.
6. Index/find-links/trusted-host option.
7. Hash option or continuation.
8. VCS/direct URL.
9. Standard package requirement candidate.
10. Unknown option.
11. Suspicious/unrecognized line.

The standard package candidate recognizer should conservatively support:

- Distribution names.
- Extras.
- Version specifier lists.
- Environment markers.
- Direct references using `name @ URL`.
- Inline comments where valid and distinguishable.

Do not claim full PEP 508 parsing. Document the function as lexical inspection.

### B3. Preserve raw lines and categories

Where practical, return original normalized line strings without silently rewriting them.

Review result fields and consider separating:

```text
requirements
editable_refs
direct_references
vcs_refs
requirement_includes
constraint_includes
index_options
hash_options
environment_markers
unknown_options
suspicious_lines
```

Preserve backward-compatible aliases where needed or document migration.

### B4. Findings policy

Findings should be reserved for meaningful issues:

- Unrecognized pip option.
- Shell metacharacters outside accepted URL/marker contexts.
- Unbalanced extras or marker quoting.
- Embedded control/invisible characters.
- Unexpected line structure.
- Input truncation or finding truncation.

A valid version comparator or extras bracket is not a finding.

### B5. Multiline and hash fixtures

Add fixtures for compiled requirements:

```text
package==1.2.3 \
    --hash=sha256:... \
    --hash=sha256:...
```

Ensure continuation lines are associated or at least classified correctly without being marked as packages or suspicious fragments.

## 6. Workstream C — Common finding contract

### C1. Define shared finding type

Introduce a shared internal TypedDict, likely in a small inspection-common module or an existing appropriate primitives module:

```python
class InspectionFinding(TypedDict, total=False):
    code: str
    severity: str
    message: str
    line: int
    column: int
    path: str
    context: str
```

Use a closed severity vocabulary:

```text
error
warning
info
```

If `path` is unavailable because the primitive receives text only, omit it.

### C2. Migrate Cargo findings

`cargo_toml_inspect()` currently returns free-form strings. Migrate it to structured findings.

Provide stable codes for:

- TOML unavailable.
- TOML parse error.
- Missing package name.
- Missing package version.
- Missing or invalid edition.
- Invalid table shape.
- Suspicious dependency name.
- Confusable dependency names.
- Input too long.

Update TypedDicts, wrappers, schemas, documentation, and tests.

### C3. Standardize parse failure behavior

All inspectors should return:

```text
parse_ok = false
findings contains at least one error
metadata fields present with safe empty/null defaults according to the documented result schema
```

Avoid exceptions for ordinary malformed user input. Exceptions remain appropriate for programmer contract violations only if wrappers reject them first.

### C4. Standardize truncation

Use one shared finding cap and one stable truncation finding code where feasible.

Do not append a truncation marker in a way that exceeds the documented maximum without explicitly documenting that the marker is additional.

## 7. Workstream D — Cargo inspection correctness

### D1. Validate result shape

Review current Cargo extraction for:

- Package metadata.
- Virtual workspaces without `[package]`.
- Workspace-inherited package fields.
- Dependency table forms.
- Target-specific dependencies.
- Renamed packages using `package = "..."`.
- Workspace dependencies.
- Git/path/registry sources.
- Feature lists and `default-features`.

Do not flag a valid virtual workspace as missing package metadata when the absence of `[package]` is intentional.

### D2. Improve suspicious-name heuristics

Current name checks should distinguish:

- Valid crate names containing hyphens or underscores.
- Uppercase or punctuation anomalies.
- Unicode confusables.
- Dependency aliases versus actual package names.

Apply confusable checks to the appropriate identity fields and document whether aliases or resolved package names are compared.

### D3. TOML runtime behavior

Coordinate with Release 4’s Python minimum-version decision.

For Release 3, tests must explicitly cover both:

- Normal `tomllib` operation on supported interpreters.
- Defined unavailable behavior if Python 3.10 remains temporarily supported.

Do not silently skip semantic tests on the primary development runtime.

## 8. Workstream E — Lockfile and ecosystem fixtures

### E1. Fixture organization

Create a fixture tree such as:

```text
tests/fixtures/manifests/python/
tests/fixtures/manifests/cargo/
tests/fixtures/manifests/javascript/
tests/fixtures/manifests/go/
tests/fixtures/requirements/
tests/fixtures/lockfiles/
```

Fixtures should be minimal but representative and licensed/created for test use.

### E2. Required Python fixtures

Include:

- Setuptools static version.
- Setuptools dynamic version.
- Poetry project.
- Hatch project.
- PDM project.
- uv-managed project.
- Flit project.
- Multiple tool sections.
- Invalid TOML with line/column assertion.

### E3. Required requirements fixtures

Include:

- Plain requirements.
- Extras and specifiers.
- Environment markers.
- Direct references.
- VCS references.
- Editable paths.
- Requirement/constraint includes.
- Hash-pinned multiline output.
- Index options.
- Malformed extras.
- Shell metacharacter attack-like input.
- Unicode confusable package names.

### E4. Required Cargo fixtures

Include:

- Single package.
- Virtual workspace.
- Workspace package inheritance.
- Workspace dependencies.
- Target-specific dependencies.
- Renamed dependency.
- Git/path/registry dependency.
- Confusable aliases.
- Invalid TOML.

### E5. JavaScript, Go, and lockfile fixtures

Include representative:

- npm package and workspaces.
- pnpm/Yarn workspace shapes where current code claims support.
- Go module with require/replace/exclude blocks.
- package-lock.
- Poetry lock.
- Cargo lock.
- Unknown lockfile.

Each fixture must have explicit expected fields and findings.

## 9. Workstream F — Test quality and field coverage

### F1. Assert all major fields

Replace tests that only assert `parse_ok` with field-level assertions.

For every public result field, require at least one test where it is populated and one relevant empty/default case.

### F2. Add negative and boundary tests

Cover:

- Non-string input at wrapper boundaries.
- Empty input.
- Exact input limit.
- Limit plus one.
- Finding cap and truncation.
- Invalid encoding characters represented in Python strings.
- Deeply nested but valid TOML/JSON within resource bounds.
- Very large dependency tables near limits.

### F3. Add invariant tests

Examples:

- `parse_ok=False` implies at least one error finding.
- Finding severity is in the closed vocabulary.
- Tool sections are sorted and unique.
- Package-manager signals are sorted and unique.
- Counts equal the lengths of corresponding collections where both are exposed.
- Structured findings are JSON serializable.
- MCP wrapper result equals primitive result inside the success envelope.

### F4. Generated schema consistency

Ensure TypedDict/result changes are reflected in:

- MCP output schemas.
- Tool inventory.
- API docs.
- Architecture docs.
- Any single-file assembly exports.

Add or update drift tests if output schemas are generated.

## 10. Workstream G — Security and resource bounds

Confirm all inspectors:

- Enforce input length before parsing or expensive regex work.
- Bound findings and returned collection sizes where necessary.
- Avoid catastrophic regular expressions.
- Avoid network and filesystem access.
- Sanitize parse errors in MCP wrappers.
- Do not execute manifest contents.
- Treat URLs and VCS references as text only.
- Detect or visibly preserve control and invisible Unicode where security-relevant.

Add adversarial cases for:

- Long extras lists.
- Long marker expressions.
- Repeated separators.
- Huge dependency maps.
- Many malformed lines.
- Unicode confusable names.

## 11. Workstream H — Documentation and migration

Update:

- `README.md` where inspection capabilities are summarized.
- `docs/mcp.md` tool examples.
- `docs/tool_inventory.md` via generator.
- `architecture/exact.md`.
- Cargo/manifest-specific architecture documentation.
- `docs/mcp_resource_limits.md` if limits change.
- `AGENTS.md` field conventions.
- `CHANGELOG.md`.

Document:

- Inspection is lexical/structural, not dependency resolution.
- Package-manager signals are heuristic.
- Requirements inspection is conservative and not a full PEP 508 parser.
- Finding codes and severities.
- Result-shape migrations.

## 12. Validation commands

Run at minimum:

```bash
python -m pytest tests/test_manifest_inspect.py -v
python -m pytest tests/test_cargo_inspect.py -v
python -m pytest tests/test_mcp_resource_bounds.py -v
python -m pytest tests/ -v
ruff check eggcalc tests
black --check eggcalc tests
mypy eggcalc --ignore-missing-imports
python build_single.py
python scripts/generate_mcp_docs.py --check
python scripts/smoke_release_surfaces.py
```

Add fixture-based smoke calls through:

- Direct primitive API.
- MCP wrapper.
- Package MCP server.
- Generated single-file MCP server.

## 13. Acceptance criteria

Release 3 is complete when:

- `pyproject_inspect()` returns the actual build backend.
- Build requirements and backend are separate fields.
- Nested `tool.*` sections are reported accurately and deterministically.
- TOML parse findings include correct location data when available.
- Valid extras and ordinary version specifiers are not suspicious requirements lines.
- Requirements continuations and hash options are classified correctly.
- Cargo and generic manifest tools use structured findings with stable codes.
- Virtual Cargo workspaces are handled correctly.
- Golden fixtures cover all advertised ecosystems.
- Every major public result field has positive field-level assertions.
- Primitive, MCP wrapper, package server, and single-file server results agree.
- Full CI, generated documentation, type checking, and release-surface verification pass.

## 14. Recommended commit sequence

1. Add failing pyproject field assertions and fixtures.
2. Correct backend, build requirements, tool sections, and parse locations.
3. Add failing requirements extras/specifier/hash fixtures.
4. Replace suspicious-line logic with conservative lexical classification.
5. Introduce shared structured finding type and migrate generic manifest tools.
6. Migrate Cargo findings and fix virtual-workspace/dependency edge cases.
7. Add full golden fixture matrix and invariants.
8. Update MCP schemas, generated docs, architecture docs, changelog, and smoke tests.
