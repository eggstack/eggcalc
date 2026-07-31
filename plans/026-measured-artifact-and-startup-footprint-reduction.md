# Measured Artifact and Startup Footprint Reduction

Status: implementation handoff  
Repository: `eggstack/eggcalc`  
Baseline reviewed: `8515579e9e64fcb49a3e5b46ac4f0c47e77d8ff1`  
Date: 2026-07-31  
Roadmap: `plans/022-correctness-simplification-and-footprint-roadmap.md`  
Depends on: `plans/025-mcp-and-configuration-authority-consolidation.md`

## 1. Purpose

Reduce eggcalc's generated single-file size, cold-start import cost, and eager runtime allocations without removing features, changing public APIs, adding runtime dependencies, or replacing the current distribution model.

This is a measured optimization pass, not a packaging rewrite.

The preferred targets are large eager data, eager compatibility tables, and eager MCP handler imports. The pass must stop after the highest-value low-complexity changes. It must not evolve into a compression framework, benchmark infrastructure, or alternate application format.

## 2. Governing constraints

The implementation must preserve:

- the complete current product scope;
- all public package imports;
- all CLI and MCP commands;
- all exact tools and Unicode/confusables behavior;
- all unit definitions and conversion behavior;
- all MCP schemas, tools, profiles, and protocol behavior;
- generated `eggcalc.py` as the supported single-file artifact;
- package/single-file behavioral parity;
- standard-library-only runtime;
- Python `>=3.11` support;
- required CI and manual PyPI release policy.

Do not:

- remove tools or data;
- replace `eggcalc.py` with a `.pyz`, native executable, compiled extension, or Rust backend in this line of work;
- ship two new competing single-file formats;
- add a runtime dependency;
- add a plugin loader or generic lazy-import framework;
- use pickle for shipped static data;
- add binary resources that cannot be regenerated from repository scripts;
- add permanent performance thresholds to CI;
- commit machine-specific benchmark histories;
- add scheduled benchmark workflows;
- optimize every module;
- trade clear code for tiny source-byte savings;
- change output formatting or public data values to improve compression.

## 3. Optimization stop rules

A candidate optimization may be implemented only when all conditions hold:

1. It preserves public behavior and symbols.
2. It works in both package and generated single-file modes.
3. It uses only Python's standard library.
4. It does not create a parallel architecture.
5. It is covered by focused parity/regression tests.
6. It demonstrates a material local benefit.
7. It does not measurably regress ordinary calculator startup.
8. It does not require CI or release-process expansion.

For this plan, a material benefit means at least one of:

- generated single-file size decreases by at least 10%;
- cold MCP startup median decreases by at least 15%;
- `import eggcalc` or `import eggcalc.mcp` peak Python allocation decreases by at least 15%;
- a large eager table with quadratic or pairwise construction is eliminated, with equivalent API behavior and a clear startup/allocation reduction.

These thresholds guide a one-time local decision. They are not CI gates.

Stop after at most three implemented optimization groups. If fewer candidates satisfy the rules, close the plan with fewer changes.

## 4. Workstream A — establish a small local baseline

### A1. Measurement scope

Measure only the surfaces relevant to this plan:

```text
source package size under eggcalc/
generated eggcalc.py byte size
wheel byte size
cold `import eggcalc`
cold `import eggcalc.mcp`
cold `calc --version`
cold MCP initialize + one tools/list response
peak Python allocations for import eggcalc and import eggcalc.mcp
number of eggcalc.exact modules loaded after import eggcalc
number of eggcalc.exact modules loaded after MCP startup before a tool call
```

Do not measure full test-suite time, network behavior, PyPI upload size, or every tool.

### A2. Measurement implementation

Use standard-library tools only:

- `time.perf_counter_ns()`;
- `subprocess`;
- `statistics.median`;
- `tracemalloc`;
- `pathlib`/`os`;
- `sys.modules` inspection;
- `zipfile` for wheel contents if needed.

A small `scripts/measure_footprint.py` is acceptable if it remains:

- optional;
- local-only;
- deterministic enough for before/after comparison on the same machine;
- under roughly 250 lines;
- free of external packages;
- absent from `make check`, `make package-check`, and CI.

A documented shell/Python command sequence is also acceptable if it is clearer than a script.

### A3. Sampling

Use a modest number of subprocess samples, for example:

- two warmups;
- seven measured runs;
- median as the reported value.

Do not add statistical significance calculations, confidence intervals, benchmark databases, or historical comparisons.

### A4. Recording results

Record before/after values in the implementation commit message, pull request description, or a short final section added to this plan during implementation.

Do not create a permanent directory of JSON benchmark records.

### A5. Acceptance criteria

- baseline commands are reproducible locally;
- measurements do not run in required CI;
- no runtime dependency is added;
- results identify whether eager exact imports, confusables data, unit tables, or schemas dominate.

## 5. Candidate priority order

Evaluate candidates in this order:

1. eliminate eager pairwise unit-conversion materialization;
2. lazily materialize/compress confusables data;
3. defer exact-tool imports until the relevant CLI/MCP handler is invoked;
4. remove redundant schema/materialized representations if measurement proves they matter;
5. simplify obsolete `build_single.py` special cases after Plans 023–025.

Do not begin candidate 4 or 5 unless earlier measurements show that they are worthwhile or earlier candidates are rejected by the stop rules.

## 6. Workstream B — replace eager pairwise unit conversions with a lazy mapping

### B1. Current cost

The unit system has a canonical declarative registry and also constructs compatibility adapters such as pairwise alias conversion mappings.

A pairwise `(source, target) -> factor` mapping scales with the number of aliases even though each value can be derived from the two canonical unit definitions.

This is unnecessary eager work if consumers use only a small subset.

### B2. Preserve the public surface

If `UNIT_CONVERSIONS` or an equivalent mapping is public, preserve:

- importability;
- mapping semantics;
- key shape;
- factor values;
- iteration behavior where documented or tested;
- read-only behavior if currently read-only.

Do not replace it with a function-only API.

### B3. Preferred implementation

Implement a small `collections.abc.Mapping` adapter backed by the canonical unit registry.

Conceptual behavior:

```python
class _UnitConversions(Mapping[tuple[str, str], float]):
    def __getitem__(self, key):
        source, target = key
        source_spec = resolve_unit(source)
        target_spec = resolve_unit(target)
        validate_compatible_non_affine_pair(source_spec, target_spec)
        return source_scale / target_scale
```

Iteration and length may derive keys lazily. If complete pairwise iteration is part of the public contract, generate keys on iteration without storing all values.

Temperature/affine conversions must preserve existing behavior. If the current pairwise mapping excludes affine units, retain that rule. Do not incorrectly represent affine conversions as one multiplicative factor.

### B4. Caching

Do not add an unbounded cache that recreates the full pairwise table over time.

A tiny bounded `functools.lru_cache` on canonical pair lookup is acceptable if measurement shows repeated lookup cost and the bound is explicit.

### B5. Tests

Verify:

- representative aliases produce identical factors;
- unknown units preserve current error behavior;
- incompatible dimensions preserve current error behavior;
- affine-unit behavior is unchanged;
- mapping iteration/length behavior remains compatible;
- no eager pairwise dictionary is allocated at import;
- package and single-file results match.

### B6. Acceptance criteria

- canonical unit definitions remain the only value authority;
- eager pairwise value materialization is removed;
- the public mapping API remains available;
- import/startup allocation improves measurably or the change is not retained;
- implementation remains small and standard-library-only.

## 7. Workstream C — lazy, regenerable confusables data

### C1. Current cost

`eggcalc/exact/confusables.py` contains thousands of generated UTS #39 entries and is one of the largest runtime source modules.

The wheel already benefits from ZIP compression, but the generated plaintext single-file artifact includes the expanded data. Importing confusables data also creates a large dictionary even when no Unicode-confusable tool is used.

### C2. Required compatibility

Preserve:

- UTS #39 data coverage currently shipped;
- deterministic generation;
- public `CONFUSABLES` import if currently public;
- mapping/get/iteration/length behavior used by the codebase;
- reverse lookup and count behavior;
- generated single-file support;
- no network access at runtime.

### C3. Preferred representation

Use a deterministic standard-library-compressed generated payload, decoded on first actual mapping access.

A suitable design uses:

```text
zlib
base64 or base85
UTF-8 or a compact deterministic binary record format
```

The generator remains the authority and must emit reproducible output from the checked-in source data or current generation inputs.

The runtime representation may be:

- a lazy `Mapping` object that materializes one dictionary on first use; or
- sorted compact integer records with binary search, if that implementation is clearly smaller and simpler.

Prefer the lazy mapping because it preserves dictionary-like behavior with less API churn.

### C4. Generated-module organization

Use the smallest maintainable organization.

Preferred option:

- `confusables.py` remains generated;
- it contains the encoded payload and a small lazy mapping implementation;
- `scripts/generate_confusables.py` emits the complete module deterministically;
- `AGENTS.md`/override notes are updated from “data-only dict” to the new generated-file rule.

Do not add multiple generated data shards or a resource-loading subsystem.

### C5. Lazy mapping requirements

The lazy mapping must:

- decode at most once per process;
- use a lock only if necessary for thread-safe first access;
- expose normal `Mapping` methods;
- not allow callers to mutate canonical data;
- fail clearly if the embedded payload is corrupt;
- avoid import-time decoding;
- avoid decoding for ordinary calculator use.

`functools.cached_property` is not directly applicable to module globals; use the simplest module-private cache.

### C6. Payload integrity

Do not add runtime cryptographic verification or evidence files.

Generator tests should prove:

- deterministic output;
- decoded entry count matches the source generation count;
- representative known mappings match;
- generated payload round-trips;
- corruption causes a clear error in a focused unit test if practical.

A single compile-time/check-time hash in the generator test is acceptable only if already part of generated-file drift checking. Do not create a new integrity subsystem.

### C7. Standard-library allowlist

If `zlib` and `base64`/`binascii` are new runtime imports, update `AGENTS.md` import constraints explicitly.

These remain standard-library imports and do not alter the dependency-free contract.

### C8. Acceptance criteria

- ordinary `import eggcalc` does not decode confusables data;
- MCP startup does not decode it before a relevant tool is called;
- first confusables use produces identical results;
- subsequent uses reuse the materialized data;
- generated output is deterministic;
- single-file size or eager allocation improves materially;
- the implementation does not create a general resource framework.

If compressed representation does not improve the generated single-file by at least 10% or causes disproportionate complexity, reject it and retain the current generated dictionary.

## 8. Workstream D — defer exact-tool imports with local imports

### D1. Current cost

Normal `import eggcalc` is already intentionally light, but MCP tool registration eagerly imports many `eggcalc.exact` implementation modules through `mcp/tools.py`.

`tools/list` needs schemas and metadata, not every implementation module.

### D2. Preferred approach

Use ordinary local imports inside existing handler functions or small category-level helper functions.

Example:

```python
def handle_unicode_inspect(arguments):
    from eggcalc.exact.unicode_tools import unicode_inspect
    return unicode_inspect(...)
```

This approach:

- uses normal Python import caching;
- requires no string-based plugin resolver;
- is easy for `build_single.py` to validate if local imports are already supported;
- keeps schemas eagerly available;
- defers implementation modules until tool invocation.

### D3. Grouping rule

Do not create one new module per handler.

Keep current handler organization and add local imports only where they remove meaningful eager imports.

A category-level import is acceptable when several handlers share one exact module.

### D4. Single-file constraint

Before retaining the change, prove that `build_single.py` correctly assembles and rewrites the local imports without a new parallel resolver.

If local imports require extensive builder special cases, reject this candidate.

At most one small general builder correction is acceptable if it improves import handling for all modules. Tool-specific rewrite tables are not.

### D5. Handler cache

Do not add a separate callable cache. Python's module cache is sufficient.

If resolving a function attribute repeatedly is measured as material, a module-private cached callable may be used, but only after measurement.

### D6. Tests

Verify:

- `tools/list` returns all current schemas without importing representative heavy exact modules;
- invoking a representative tool imports its implementation and returns the same result;
- tools in each major category still resolve;
- package and single-file MCP transcripts match;
- unknown tool and profile behavior is unchanged;
- handler exceptions retain current JSON-RPC mapping.

Use `sys.modules` assertions for a few representative modules, not every exact module.

### D7. Acceptance criteria

- schema listing remains eager and complete;
- heavy exact implementation modules are deferred until invocation;
- no generic plugin/lazy-loader framework is added;
- no tool name/schema/profile changes;
- cold MCP startup or peak allocation improves by at least 15%;
- single-file builder complexity does not materially increase.

If the threshold is not met, revert this candidate rather than retaining indirection for its own sake.

## 9. Workstream E — schema representation review

### E1. Decision gate

Inspect whether the runtime stores materially duplicated schema forms, such as precomputed compact, normal, and full copies.

If schema detail is derived on request from one canonical schema and metadata set, make no change.

If multiple full nested copies are eagerly retained, consolidate to one canonical frozen schema and derive reduced views when `tools/list` is called.

### E2. Constraints

Any implementation must preserve exact public JSON schema output for each detail mode.

Do not:

- replace schemas with a custom DSL;
- move schemas to a new external format solely for size;
- generate Python code from JSON at installation time;
- add a schema compiler;
- weaken schema validation.

### E3. Caching

Derived schema-detail views may be cached by the three bounded detail modes.

A three-entry cache is acceptable. An unbounded per-profile/per-request cache is not.

### E4. Acceptance criteria

Implement only if measurement shows material duplicated allocation.

If implemented:

- one canonical schema authority remains;
- detail outputs are byte/structure equivalent after normalization;
- memory improves measurably;
- code complexity remains lower than the removed duplication.

Otherwise, document “no change; schemas were already single-source” and stop this workstream.

## 10. Workstream F — simplify the single-file builder after consolidation

### F1. Preserve the artifact

The generated `eggcalc.py` remains the supported single-file artifact.

Do not adopt zipapp in this plan. A `.pyz` may be evaluated in a future separately approved packaging roadmap only if maintainers decide to change the public distribution contract.

### F2. Remove obsolete special cases

After Plans 023–025 and the retained optimizations, inspect `build_single.py` for special cases that reference:

- removed duplicate MCP paths;
- obsolete aliases;
- old eager imports;
- redundant module ordering exceptions;
- compatibility code no longer present.

Delete only rules proven obsolete by manifest validation and parity tests.

### F3. Do not rewrite the builder

The builder's manifest, dependency validation, import rewriting, and deterministic output remain.

Do not replace it with a new AST compiler, templating engine, bundler package, or multi-stage build system.

A source-concatenation builder is acceptable for this project's explicit single-file requirement. The goal is to make it smaller where prior simplification permits, not to prove that a different build architecture is theoretically cleaner.

### F4. Determinism and parity

Retain:

- deterministic generated output;
- manifest cycle/reachability checks;
- package/single-file CLI parity;
- package/single-file MCP transcript parity;
- direct execution on Python 3.11+.

### F5. Acceptance criteria

- obsolete special cases are removed;
- no new tool-specific import rewrite table is added;
- generated output remains deterministic;
- artifact behavior remains equivalent;
- builder source complexity does not increase overall.

## 11. Workstream G — scope and documentation closure

Update primary documentation to state clearly:

- eggcalc retains its current calculator, exact-tool, and MCP scope;
- runtime remains standard-library-only;
- generated `eggcalc.py` remains supported;
- large data may be materialized lazily but remains fully bundled offline;
- manual PyPI release remains authoritative;
- no feature was removed for footprint reduction.

Add a short portfolio-boundary note if appropriate:

```text
eggcalc is the canonical Python calculator/library and includes its existing MCP utility surface. eggsact is a separate Rust utility suite; neither is a runtime dependency or drop-in replacement for the other.
```

Do not add deprecation language or migration instructions.

Update `AGENTS.md` and `AGENTS.override.md` for any changed generated-data or local-import conventions.

## 12. Files expected to change

Possible runtime files:

```text
eggcalc/units.py
eggcalc/exact/confusables.py
eggcalc/mcp/tools.py
eggcalc/mcp/schemas.py
build_single.py
```

Generation/measurement files:

```text
scripts/generate_confusables.py
scripts/measure_footprint.py  # optional, local-only
```

Tests/docs:

```text
tests/test_units.py
tests/test_unicode_tools.py
tests/test_mcp_server.py
tests/test_mcp_stdio_smoke.py
tests/test_build_single.py
README.md
docs/architecture/overview.md
docs/architecture/build.md
AGENTS.md
AGENTS.override.md
```

This is a candidate set, not a requirement to touch every file.

Do not modify workflow files, release scripts, package dependencies, public tool membership, or unrelated exact algorithms.

## 13. Focused verification

Suggested focused checks depend on retained candidates:

```text
python -m pytest tests/test_units.py -q
python -m pytest tests/test_unicode_tools.py -q
python -m pytest tests/test_mcp_server.py -q
python -m pytest tests/test_mcp_stdio_smoke.py -q
python -m pytest tests/test_build_single.py -q
python build_single.py --validate
python build_single.py
python scripts/measure_footprint.py  # only if added
```

Final required verification remains:

```text
make check
make package-check
```

Do not add footprint measurement to these targets.

## 14. Required before/after report

The implementation handoff must report a compact table similar to:

| Metric | Before | After | Change |
|---|---:|---:|---:|
| generated `eggcalc.py` bytes | | | |
| wheel bytes | | | |
| cold `import eggcalc` median | | | |
| cold `import eggcalc.mcp` median | | | |
| MCP initialize + tools/list median | | | |
| peak allocation `import eggcalc.mcp` | | | |
| exact modules loaded before tool call | | | |

The report belongs in the commit/PR or a final appended plan section. Do not create a permanent evidence pipeline.

Machine, Python version, and sample count should be stated in one sentence.

## 15. Explicit negative tests

The implementation is incomplete unless tests prove:

1. `UNIT_CONVERSIONS` remains importable and behaviorally compatible.
2. ordinary calculator import does not materialize confusables data.
3. MCP `tools/list` does not require representative heavy exact modules after lazy-import work.
4. first invocation of a deferred tool returns the same result as before.
5. all confusables data remains available after lazy decode.
6. generated payload output is deterministic.
7. generated single-file CLI and MCP behavior remains equivalent to the package.
8. no runtime import resolves to a third-party package.
9. no new artifact format replaces `eggcalc.py`.
10. no benchmark or measurement command becomes a CI/release gate.

## 16. Final acceptance criteria

This plan is complete when:

1. a small local baseline identifies actual footprint/startup costs;
2. no more than three optimization groups are retained;
3. every retained optimization meets the material-benefit stop rule;
4. eager pairwise conversion materialization is removed if it is a measured cost and public mapping behavior is preserved;
5. confusables data is lazy/compact only if it materially improves the single-file or allocation footprint;
6. exact-tool imports are deferred only if ordinary local imports work cleanly in package and single-file modes;
7. schema representation changes only if real duplication is measured;
8. obsolete builder special cases are removed without a builder rewrite;
9. all current features, tools, schemas, profiles, constants, units, and public symbols remain available;
10. generated `eggcalc.py` remains supported and deterministic;
11. runtime remains standard-library-only;
12. ordinary calculator startup does not materially regress;
13. required CI and manual release policy remain unchanged;
14. before/after measurements are reported without creating permanent evidence machinery;
15. `make check` and `make package-check` pass.

The phase may also close successfully with fewer or no retained optimizations when candidates fail the stop rules. In that case, record the measured reason and stop. Do not force complexity into the codebase merely to claim a smaller artifact.
