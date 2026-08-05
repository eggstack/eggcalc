# Correctness, Simplification, and Footprint Roadmap

Status: completed  
Repository: `eggstack/eggcalc`  
Baseline reviewed: `8515579e9e64fcb49a3e5b46ac4f0c47e77d8ff1`  
Date: 2026-07-31  
Depends on: `plans/020-ci-verification-and-manual-pypi-release-simplification.md`, `plans/021-ci-simplification-correctness-and-isolation-closure.md`

## 1. Purpose

This roadmap converts the July 2026 repository review into a bounded implementation sequence.

The repository already accomplishes its documented product goal: it is a standard-library-only natural-language calculator, unit engine, Python library, CLI, single-file distribution, and MCP utility server. The objective is not to reduce that scope or split the product. The objective is to correct several semantic and trust-boundary defects, remove avoidable internal duplication, and reduce artifact/startup footprint where doing so is demonstrably simpler than the current implementation.

The governing constraints are:

- retain the current public feature set;
- retain the Python library, CLI, MCP server, exact-text tools, and single-file distribution;
- keep runtime code standard-library-only;
- do not introduce a compiled extension, Rust backend, vendored dependency, generated native binary, or optional runtime package;
- do not transfer or remove tools merely because comparable tools exist in `eggsact`;
- do not redesign the product around a new plugin framework;
- do not expand CI, release automation, evidence collection, or compatibility matrices;
- keep manual PyPI release policy unchanged;
- prefer local, focused regression tests over new verification infrastructure;
- make each phase independently reviewable and releasable.

This roadmap is intentionally corrective and reductive. It does not authorize adjacent feature work.

## 2. Product boundary decision

`eggcalc` remains the complete product currently documented by the repository.

That means this line of work must preserve:

- natural-language arithmetic and expression normalization;
- structural unit conversion and unit-aware arithmetic;
- constants, memory, variables, registered constants, and registered functions;
- sync, cached, async, and timeout evaluation surfaces;
- the `calc` CLI and REPL;
- exact text, Unicode, JSON, regex, path, shell, manifest, patch, and repository analysis commands already exposed;
- all current MCP tool names, schemas, profiles, protocol versions, and stdio behavior;
- the installable package, console entry point, and generated single-file program;
- Python `>=3.11` support;
- the dependency-free runtime contract.

The overlap with `eggsact` is a portfolio-level ownership concern, not permission to remove functionality here. During this roadmap:

- no existing eggcalc tool is deprecated or deleted;
- no compatibility shim is removed;
- no repository is made a runtime dependency of another;
- no cross-repository RPC or subprocess coupling is introduced;
- new utility categories are frozen unless they are required to correct an existing eggcalc behavior.

A short documentation note may clarify that `eggcalc` is the canonical Python calculator/library implementation while `eggsact` is a separate Rust utility suite. That note must not claim that either project replaces the other.

## 3. Current findings addressed by this roadmap

### 3.1 CLI and trust-boundary defects

The current CLI loads cwd-local `eggcalc_config.py` before argument dispatch. As a result, non-evaluation invocations such as help, version, capabilities, and MCP startup may execute local configuration code before the selected mode is known.

The text-command dispatcher also uses one integer result for both “not handled” and “handled with an error,” allowing recognized command errors to fall through into calculator evaluation. A shell-glob heuristic rejects any argument that happens to name an existing path, which can block legitimate text commands. Several compatibility flags and constant aliases are documented more strongly than their actual behavior supports.

These issues are handled by Plan 023.

### 3.2 Unit semantics at function boundaries

The evaluator currently unwraps `UnitValue` arguments to raw numeric values for most functions. This silently discards dimensions and permits invalid or misleading operations such as logarithms of mass, square roots that lose dimensions, incompatible-unit reducers, and degree values interpreted as radians.

The correction requires explicit dimensional contracts for the existing function registry. It does not require a symbolic mathematics engine or an unbounded dimension-system rewrite.

Timeout evaluation also constructs a fresh evaluator process without carrying equivalent state, and custom unit registration can accept category declarations that do not match the base unit dimension.

These issues are handled by Plan 024.

### 3.3 MCP/configuration duplication

The MCP implementation contains both instance-oriented server/session/executor paths and global compatibility paths. Configuration has overlapping parsing, freezing, snapshot, candidate, and manager mechanisms. Some public compatibility surfaces are necessary, but the implementation should have one authoritative dispatch path and one authoritative validation/freezing path.

This is handled by Plan 025. The plan preserves protocol behavior, public names, tools, profiles, and compatibility adapters.

### 3.4 Artifact and startup footprint

The runtime has no third-party dependencies, but the generated single-file artifact and MCP startup path eagerly carry large data and handler imports. The largest obvious opportunities are:

- lazy materialization of confusables data;
- avoiding eager pairwise unit-conversion tables;
- reducing eager MCP handler imports where this remains compatible with the single-file builder;
- avoiding redundant schema/data representations;
- removing obsolete builder special cases after internal consolidation.

These optimizations must be measurement-led. They are not permission to add a second packaging system, create binary blobs that are difficult to audit, or replace the current single-file contract with an incompatible format.

This is handled by Plan 026.

## 4. Governing engineering rules

### 4.1 Standard-library-only means runtime-only and absolute

All modules under `eggcalc/`, all generated single-file runtime code, and all runtime resource decoding must use the Python standard library only.

Development dependencies already used for linting, typing, testing, building, and publication may remain development-only. This roadmap must not add a runtime dependency to `pyproject.toml`.

New standard-library imports are allowed when necessary, but they must be:

- explicitly documented in `AGENTS.md` if the repository continues to maintain an import allowlist;
- supported by Python 3.11;
- compatible with package and single-file execution;
- justified by a net simplification or measurable footprint improvement.

### 4.2 Preserve public behavior unless correcting a bug

A behavior change is allowed only when one of the following is true:

1. current behavior violates the documented trust boundary;
2. current behavior silently produces dimensionally invalid results;
3. current behavior contradicts CLI documentation or command selection;
4. current behavior differs between ordinary and timeout evaluation without disclosure;
5. current behavior accepts invalid custom configuration;
6. an internal compatibility path bypasses canonical validation or lifecycle rules.

For each such correction, add a focused regression test that demonstrates the old failure mode and the intended result.

Do not add broad snapshot suites, full-output golden files, generated evidence manifests, or cross-product parity matrices.

### 4.3 Simplification must reduce authorities

Internal simplification is successful only when it reduces the number of authoritative paths.

Examples:

- one CLI mode-selection point;
- one text-command dispatch result type;
- one function-contract registry;
- one MCP request executor;
- one config parser;
- one recursive freeze/thaw implementation;
- one source of public tool schemas;
- one generated single-file manifest.

Moving code into more wrappers without deleting or delegating the prior authority does not count as simplification.

### 4.4 Optimization must have a stop rule

No optimization phase may continue solely because a smaller artifact might be possible.

A footprint change must satisfy all of the following:

- no feature or public symbol is removed;
- package and single-file behavior remain equivalent for the touched surface;
- the change uses only the standard library;
- the implementation is smaller or comparably sized in source complexity;
- a repeatable local measurement shows a material benefit;
- required CI remains unchanged except for ordinary regression coverage;
- no permanent benchmark gate or historical baseline ledger is introduced.

If a candidate optimization fails these conditions, document the result briefly and stop without implementing it.

## 5. Roadmap phases

## Phase 1 — CLI dispatch and trust-boundary correction

Plan: `plans/023-cli-dispatch-and-trust-boundary-correction.md`

Primary outcomes:

- parse and classify CLI mode before loading cwd-local configuration;
- load user configuration only for evaluation/REPL paths that require it;
- keep MCP, help, version, capabilities, and exact-text command discovery free of cwd config execution;
- introduce an explicit handled/not-handled command result;
- prevent recognized text-command errors from being re-evaluated as math;
- remove or sharply narrow the filesystem-existence glob heuristic;
- resolve constant/unit alias documentation and import-time warning behavior;
- align compatibility flags and CI-platform claims with actual behavior.

Why first:

- it closes an executable trust-boundary defect;
- it is isolated mostly to CLI dispatch and documentation;
- it establishes clearer command ownership before evaluator/MCP changes.

Completion gate:

- all focused CLI regressions pass;
- existing CLI, package, and single-file tests pass;
- no new command mode or runtime dependency is added.

## Phase 2 — Unit-aware function contracts and evaluator state parity

Plan: `plans/024-unit-aware-function-contracts-and-timeout-state-parity.md`

Primary outcomes:

- replace generic unit unwrapping with explicit contracts for existing built-in functions;
- reject dimensionally invalid operations rather than silently discarding dimensions;
- support bounded, well-defined angle and compatible-unit behavior;
- preserve units for supported unit-preserving operations;
- define square-root and reducer behavior without introducing general symbolic algebra;
- carry supported evaluator state into timeout workers or fail clearly for unsupported custom callables;
- validate custom unit category/dimension consistency;
- document the bounded angle model and reject unsupported compound-angle cases rather than misrepresenting them.

Why second:

- it is the most important numerical-correctness work;
- it depends on stable evaluation entry points but not on MCP simplification;
- downstream MCP math behavior then inherits corrected evaluator semantics.

Completion gate:

- all existing valid calculator/unit expressions remain valid;
- newly invalid expressions fail with clear evaluation errors;
- no function silently strips units;
- ordinary and timeout evaluation agree for supported state;
- no symbolic algebra framework is added.

## Phase 3 — MCP and configuration authority consolidation

Plan: `plans/025-mcp-and-configuration-authority-consolidation.md`

Primary outcomes:

- keep one canonical server/session/registry/executor implementation;
- retain module-level compatibility functions as thin delegates;
- route all configuration replacement through one parser and validator;
- use one recursive ownership freeze/thaw implementation;
- make snapshot immutability claims true;
- remove internal duplicate config construction paths;
- document compatibility aliases such as equivalent policy values rather than maintaining duplicate branches;
- preserve every current tool, profile, schema, protocol version, and lifecycle rule.

Why third:

- it reduces maintenance cost after evaluator behavior is settled;
- it creates a simpler base for any lazy-loading work;
- it avoids mixing protocol refactoring with numerical semantics.

Completion gate:

- public MCP transcripts remain equivalent;
- compatibility functions delegate to the canonical path;
- invalid configuration cannot bypass parsing;
- duplicate freeze/config authorities are removed;
- no new server abstraction, plugin framework, or protocol layer is introduced.

## Phase 4 — Measured artifact and startup footprint reduction

Plan: `plans/026-measured-artifact-and-startup-footprint-reduction.md`

Primary outcomes:

- establish a small, local, non-gating measurement script or documented commands;
- implement only the highest-value low-complexity footprint changes;
- prioritize lazy large-data materialization and elimination of eager compatibility tables;
- consider MCP lazy handler resolution only if it does not require a parallel package/single-file architecture;
- retain the current generated single-file `.py` contract;
- remove builder special cases made obsolete by prior consolidation;
- record final before/after measurements in the implementation commit or PR description, not a permanent evidence subsystem.

Why last:

- correctness and authority consolidation should precede optimization;
- measurements taken after prior simplification are more meaningful;
- it prevents optimizing duplicate paths that should first be removed.

Completion gate:

- at least one material footprint/startup improvement is demonstrated, or the phase closes with a documented no-change decision because candidates failed the stop rules;
- no feature reduction or runtime dependency occurs;
- single-file/package parity remains intact;
- CI and release policy remain unchanged.

## 6. Verification policy for all phases

Plans 020 and 021 remain authoritative.

Required verification remains:

```text
make check
make package-check
```

Do not add:

- a required operating-system or Python-version matrix;
- benchmark thresholds in CI;
- coverage thresholds;
- release evidence;
- generated implementation inventories;
- Git-history validation;
- artifact upload/download choreography;
- nightly or scheduled workflows;
- automatic PyPI publication;
- a second test runner;
- property-testing or fuzzing dependencies.

Each phase should add only focused regression tests for the behaviors it changes. Existing broad tests should be reused where they already cover the surface.

The manual compatibility workflow may be run after a phase that touches Windows path handling, multiprocessing behavior, executable discovery, or Python-version-sensitive internals. It remains optional and non-required.

## 7. Expected file touch boundaries

The detailed plans may touch the following areas:

```text
eggcalc/cli.py
eggcalc/evaluator.py
eggcalc/units.py
eggcalc/__init__.py
eggcalc/mcp/server.py
eggcalc/mcp/tools.py
eggcalc/mcp/schemas.py
eggcalc/exact/confusables.py
scripts/generate_confusables.py
build_single.py
tests/
docs/
README.md
AGENTS.md
AGENTS.override.md
```

This is not a blanket authorization to edit all listed files. Each implementation plan narrows its own touch set.

Avoid changes to unrelated exact tools, protocol versions, public schemas, release workflows, and packaging metadata unless the specific plan requires them.

## 8. Cross-phase compatibility requirements

Throughout the roadmap:

- `from eggcalc import evaluate` remains valid;
- `python -m eggcalc` remains valid;
- the installed `calc` entry point remains valid;
- `calc --mcp` remains the stdio MCP entry point;
- generated `eggcalc.py` remains directly executable;
- current tool profiles retain their names and membership unless a membership entry is demonstrably erroneous;
- current JSON-RPC error classes and request lifecycle remain stable;
- `handle_request()` compatibility remains available, though it may delegate internally;
- `ConfigSnapshot`, `ConfigManager`, `EvaluationPolicy`, and other public MCP types remain importable;
- runtime remains dependency-free.

## 9. Risk controls

### 9.1 Do not combine all phases into one implementation commit

The roadmap is ordered so defects can be isolated. The preferred implementation sequence is one phase per reviewable commit or pull request.

A single implementation commit covering CLI dispatch, evaluator semantics, MCP refactoring, and data compression would be difficult to validate and revert. Planning files may land together; implementation should not.

### 9.2 Prefer delegation before deletion

Where a public compatibility API exists, first route it through the canonical implementation. Delete only duplicate private implementation code after tests demonstrate delegation parity.

### 9.3 Reject unsupported dimensional cases explicitly

Do not silently preserve old numeric behavior merely to avoid a breaking change. A clear `EvaluationError` is preferable to a plausible but dimensionally false result.

Do not attempt to support every theoretically valid physical dimension. The plan defines the supported bounded cases.

### 9.4 Keep optimization reversible

Footprint work should be separable from correctness changes. A failed optimization must be removable without reverting semantic fixes.

## 10. Definition of complete

This line of work is complete when:

1. Plans 023–026 have been implemented in order or explicitly closed by their stop criteria.
2. Non-evaluation CLI modes do not execute cwd-local configuration.
3. Recognized text-command failures do not fall through into math evaluation.
4. Existing filesystem names do not cause false shell-glob rejection.
5. Function calls no longer silently discard units.
6. Timeout evaluation has defined state semantics and matches ordinary evaluation for supported state.
7. Invalid custom unit category/dimension combinations are rejected.
8. MCP compatibility APIs delegate to one canonical runtime path.
9. Configuration construction uses one validation and recursive-freezing authority.
10. Public tools, profiles, schemas, protocol versions, and package surfaces remain available.
11. Runtime remains standard-library-only.
12. Required CI remains one Ubuntu/Python 3.11 job using the existing Make targets.
13. Publication remains manual through PyPI/Twine.
14. Artifact/startup optimization either demonstrates a material low-complexity benefit or closes without implementation under the documented stop rules.
15. Documentation describes actual CLI flags, constants, supported CI platforms, timeout semantics, and product boundary.

After these conditions are met, stop. Do not use this roadmap as a basis for a new release-evidence cycle, broad utility expansion, symbolic mathematics engine, plugin ecosystem, or packaging rewrite.

## 11. Completion note

All 14 conditions in §10 are satisfied. Plans 023–027 have been implemented. The roadmap is closed.
