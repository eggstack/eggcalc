# Surface Consolidation and Maintainability Roadmap

Status: planned  
Repository: `eggstack/eggcalc`  
Baseline reviewed: `55993e58b438f4548c58569248cdada52c099030`  
Date: 2026-09-08  
Depends on: completed utility parity work through Plan 032, current stdlib-only production policy, existing single-file distribution and MCP profile model

## 1. Purpose

The current repository is functionally broad and well tested, but feature growth has increased change amplification. The main risks are no longer missing primitives or runtime dependencies. They are overlapping semantic authorities, duplicated process-control infrastructure, very large adapter/registry surfaces, stale authority documentation, and a support matrix that is broader than the continuously exercised CI matrix.

This roadmap closes those gaps without redesigning eggcalc or expanding its product boundary.

The desired end state is:

- one implementation authority for each semantic concept;
- compatibility aliases retained only where they are useful and thin;
- shared low-level lifecycle machinery for subprocess-backed safety paths;
- fewer manually synchronized registries where one can be derived safely;
- support claims backed by recurring CI evidence;
- a deterministic way to inspect the normalization pipeline when debugging natural-language/unit parsing;
- no new runtime dependencies;
- no broad module decomposition merely to reduce line counts;
- no expansion of the current MCP/tool scope.

## 2. Non-negotiable constraints

All work under this roadmap must preserve the following:

- production runtime remains Python standard-library-only;
- `dependencies = []` remains true in `pyproject.toml`;
- the calculator, Python API, CLI, MCP server, exact utilities, and generated single-file distribution remain supported;
- current public behavior is preserved unless a plan explicitly defines a deprecation/consolidation path;
- no new network I/O, filesystem I/O, clock dependence, local timezone dependence, service process, daemon, plugin framework, or external schema library is introduced;
- no large-scale clean-architecture rewrite;
- no splitting of `evaluator.py`, `normalize.py`, or `units.py` solely because they are large;
- no removal of useful composite/preflight tools simply because they reuse lower-level primitives;
- no new MCP tools unless explicitly required for normalization observability and approved by the implementation plan; default outcome is library/CLI observability only;
- keep CI bounded and understandable rather than adding a full OS × Python Cartesian matrix.

## 3. Findings driving the roadmap

### 3.1 Real semantic overlap

`eggcalc.exact.validate` currently exposes both `json_query()` and `json_extract()` for RFC 6901 JSON Pointer lookup. MCP metadata already treats `json_query` as deprecated while still exposing it prominently. The implementation should converge on `json_extract` as the canonical operation while retaining a compatibility wrapper as needed.

Version semantics are also split. `exact.validate.version_compare()` contains independent SemVer-like comparison logic, while `exact.version` is the dedicated SemVer/Cargo parsing and constraint module. The dedicated module should own SemVer semantics.

### 3.2 Internal machinery duplication

`evaluator.py` and `mcp/tools.py` each contain bounded multiprocessing spawn/permit/cleanup logic. This is difficult platform-sensitive code. The policy values may remain separate, but the low-level lifecycle implementation should not be independently maintained in two places.

`exact/__init__.py` also maintains a large lazy import registry plus a parallel explicit public export list. Where observable ordering/compatibility permits, derive one from the other.

### 3.3 Documentation authority drift

`eggcalc/_protocol.py` is now the code-level source of truth for supported MCP protocol versions. `capabilities.py` and `mcp/server.py` import from it. `architecture/authority_inventory.md` still describes `mcp/server.py` as authoritative and `capabilities.py` as an intentional duplicate. The authority inventory therefore contradicts the code and must be corrected.

Other architecture/test documentation should receive a focused drift check, but this is not authorization for a broad documentation rewrite.

### 3.4 Compatibility evidence gap

The README promises Python 3.11+, Linux, macOS, and Windows with the complete capability set. Normal push/PR CI runs Ubuntu/Python 3.11. A manually triggered compatibility workflow covers Windows 3.11 and Ubuntu 3.14, but not macOS and not recurring automated evidence.

The target is a small recurring compatibility matrix that proves the support claim without making CI expensive.

### 3.5 Normalization observability gap

`normalize.py` is a large transformation pipeline and has historically produced edge-case defects at stage boundaries. The public API gives callers the final normalized expression but not a structured explanation of material rewrites.

A bounded deterministic normalization trace would improve debugging, regression tests, issue reports, and agent reasoning without adding parsing features.

## 4. Workstream structure

### Plan 034 — Semantic authority consolidation

File: `plans/034-semantic-authority-consolidation.md`

Scope:

- make `json_extract` the RFC 6901 implementation authority;
- retain `json_query` only as a compatibility facade if compatibility requires it;
- remove deprecated `json_query` from default MCP exposure while preserving explicit compatibility access where appropriate;
- make `exact.version` authoritative for SemVer parsing/comparison used by `version_compare`;
- preserve the existing `loose` comparison mode if still public;
- correct authority documentation and add drift tests where inexpensive.

Primary objective: reduce duplicate semantics without breaking callers.

### Plan 035 — Shared lifecycle and registry maintainability

File: `plans/035-shared-lifecycle-and-registry-maintainability.md`

Scope:

- factor only the common multiprocessing permit/context/cleanup primitives that are genuinely shared by evaluator and MCP timeout paths;
- preserve independent evaluator/MCP policy constants and error contracts;
- derive the exact package public export list from one authoritative lazy registry if compatibility permits;
- add invariant tests preventing registry/build/export drift;
- avoid broad changes to evaluator, MCP server architecture, or exact module boundaries.

Primary objective: reduce maintenance of tricky duplicated implementation machinery.

### Plan 036 — Compatibility evidence, documentation closure, and normalization observability

File: `plans/036-compatibility-evidence-and-normalization-observability.md`

Scope:

- add a deliberately small recurring compatibility workflow for supported platforms/runtime edges;
- include macOS evidence and keep Windows/latest-runtime evidence automatic at a low cadence or targeted trigger;
- align README/support documentation with actual evidence;
- repair known authority/test documentation drift;
- add a deterministic structured normalization trace API and a minimal CLI discovery/explanation surface;
- do not widen natural-language grammar or add more calculator features.

Primary objective: make support claims evidence-backed and make the most failure-prone transformation pipeline inspectable.

## 5. Deliberately retained overlap

The following are not consolidation targets under this roadmap:

- `text_inspect` versus security/composite inspection functions;
- `command_preflight`, `config_preflight`, `edit_preflight`, and `structured_data_compare` versus their lower-level components;
- `text_hash` versus `text_fingerprint`;
- direct `evaluate()` versus user-facing `evaluate_raw()`;
- CLI surface versus MCP surface;
- package distribution versus generated single-file distribution.

These represent distinct abstraction levels or user contracts. Simplification must not remove useful orchestration.

## 6. Implementation order

Implement Plans 034, 035, and 036 in order unless a concrete dependency discovered during implementation requires a smaller reorder.

Plan 034 should land first because it establishes semantic ownership and may simplify generated metadata/tests used later.

Plan 035 should land second because its changes are internal and benefit from the semantic authorities being stable.

Plan 036 should land last because CI/docs should describe the resulting architecture rather than an intermediate state, and normalization observability should be evaluated against the final authority model.

Each plan must be independently reviewable and leave `main` green.

## 7. Acceptance criteria

The roadmap is complete when all of the following are true:

1. `json_extract` is the sole implementation authority for RFC 6901 extraction behavior; any `json_query` compatibility path delegates rather than reimplements.
2. SemVer comparison has one parser/comparison authority in `exact.version`; `version_compare` does not independently define SemVer precedence.
3. Deprecated tool exposure is not preferred over its replacement in default MCP profiles.
4. Common multiprocessing lifecycle primitives are not independently implemented in evaluator and MCP tool code.
5. The exact lazy export/public export registry has one practical source of truth, or a documented reason and invariant test exists if full derivation proves incompatible.
6. `architecture/authority_inventory.md` matches the actual code authorities, including `_protocol.py`.
7. Supported OS/runtime claims have recurring automated evidence including Linux, Windows, macOS, Python 3.11, and the current upper supported Python boundary, without an excessive matrix.
8. A deterministic normalization trace can show the material stages leading from raw input to evaluator-ready expression without changing normal evaluation semantics.
9. Package and generated single-file parity remain green.
10. No runtime dependency is added.
11. `make check` and `make package-check` pass after the final implementation.

## 8. Verification philosophy

Prefer invariant and parity tests over additional layers of framework code.

Useful invariants include:

- compatibility wrapper result equals canonical implementation result;
- `version_compare(..., scheme="semver")` agrees with the dedicated version parser/comparator corpus;
- public exact exports resolve through the lazy registry;
- shared spawn permit always releases on normal return, exception, timeout, and cleanup paths;
- package and single-file normalization traces are identical for a representative corpus;
- documentation generation/checks fail on tool/profile inventory drift;
- CI support matrix is explicit and small.

Do not create an internal dependency injection framework, generalized process supervisor, generic registry framework, or test DSL to satisfy these requirements.

## 9. Explicit non-goals

This roadmap does not authorize:

- adding dependencies;
- adding new arithmetic domains, symbolic algebra, arbitrary precision decimal packages, currencies, finance feeds, or scientific databases;
- adding new network-aware exact tools;
- adding timezone database/DST behavior;
- mirroring all 83 MCP tools into CLI subcommands;
- deleting compatibility APIs solely for tidiness;
- reorganizing all modules by category;
- replacing TypedDict-based result contracts with a new object hierarchy;
- replacing the MCP implementation with an external SDK;
- introducing generated source files merely to replace simple Python registries;
- comprehensive benchmark infrastructure;
- release automation changes unrelated to compatibility verification.

The line of work should end once semantic ownership, duplicated lifecycle machinery, compatibility evidence, documentation authority, and normalization observability are in a stable and low-maintenance state.
