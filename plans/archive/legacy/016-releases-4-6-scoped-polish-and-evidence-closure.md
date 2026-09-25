# Releases 4–6 Scoped Polish and Evidence Closure

Status: implementation handoff  
Repository: `eggstack/eggcalc`  
Baseline reviewed: `9aceaddea91128319e1cbce5530e8a5c907afcd9`  
Depends on:

- `plans/014-releases-4-6-production-path-corrective-closure.md`
- `plans/015-releases-4-6-final-unit-authority-and-evidence-closure.md`

This is a narrowly scoped polish-and-proof pass. The production-path corrective implementation at `9aceadde` materially completed MCP ownership, atomic runtime configuration, executor reservation accounting, structural `UnitValue` arithmetic, module-manifest execution, typed-package metadata, and several new verification scripts. Do not reopen those architectures unless a focused regression test demonstrates a defect.

The remaining work is concentrated in four areas:

1. remove duplicated manually maintained unit semantics that remain earlier in `eggcalc/units.py`;
2. correct and exhaustively test bounded structural unit rendering/parsing;
3. make fixture, inventory, typing, and performance checks prove the actual released artifacts;
4. synchronize Release 4–6 evidence to one exact green implementation candidate.

Releases 4, 5, and 6 remain open until every final gate in this document is satisfied.

---

## 1. Preserve completed behavior

The implementation must preserve the following baseline behavior and architecture:

- instance-owned MCP registry/profile/list/call behavior;
- `RuntimeContext` as the active evaluator/configuration authority;
- atomic configuration replacement and in-flight context capture;
- permanent session ownership and fail-closed serverless production dispatch;
- bounded executor accounting with released reservations removed;
- declaration-built active `UnitRegistry`;
- structural `UnitValue` multiplication, division, reciprocal, power, conversion, and cancellation;
- affine compound-operation rejection;
- topological `MODULE_MANIFEST`-driven assembly;
- dynamic package version and protocol authorities;
- deterministic single-file generation;
- `py.typed` packaging;
- current supported Linux/macOS/Windows Python matrix;
- package and single-file command/MCP behavior.

No workstream in this plan may weaken these properties to simplify the remaining checks.

## 2. Non-goals

Do not add or redesign:

- MCP tools, profiles, transports, authentication, or protocol versions;
- evaluator grammar or evaluator timeout architecture;
- new unit families or aliases;
- server-configured custom units;
- symbolic algebra or fractional unit exponents;
- a third-party unit library;
- package public API names;
- the packaging backend;
- the supported Python matrix;
- repository-wide strict typing outside closure modules;
- speculative performance optimizations;
- new evidence identity schemes.

The existing custom-unit compatibility API may remain if it is already public, but this pass must not expand its behavior or use it to justify retaining duplicate built-in authorities.

## 3. Current residual defects at `9aceadde`

The implementation candidate still has these concrete closure blockers:

- `eggcalc/units.py` contains full manually maintained legacy `UNIT_BASE`, `UNIT_ALIASES`, temperature tables, category maps, and superseded helper implementations before the declaration-driven replacements;
- the source therefore has two readable semantic representations even though the later generated adapters win at runtime;
- `UnitSpec.base_canonical` is inferred from a second category-to-base mapping rather than being explicit in every declaration or generated from one family declaration authority;
- `render_expression()` silently truncates canonical output instead of rejecting an over-limit expression;
- the post-render length check cannot detect overflow because it observes the already truncated string;
- focused parser tests do not prove canonical-output bounds, finite-scale overflow/underflow, error-message bounds, direct-construction failures, or meaningful depth behavior;
- the committed legacy fixture test omits offset, display, and arithmetic-rendering comparison;
- fixture provenance is trusted from a metadata string rather than validated by a reproducible or hash-pinned process;
- single-file inventory obtains `__all__` from the package, masking generated-file public export divergence;
- inventory omits capability fields and does not prove the single-file namespace is self-contained;
- strict migrated-module mypy uses `follow_imports = skip`;
- source and installed-wheel consumers are not run under the intended strict contract;
- no current baseline/final architecture-cost artifacts are committed;
- Release 4–6 evidence files still contain old SHAs, old runs, approximate counts, and historical Windows failures presented in current-status sections;
- evidence consistency tests validate only synthetic temporary documents;
- CI does not execute the evidence validator against the repository evidence files;
- no independently recorded green workflow exists for the final current candidate.

---

# Workstream A — Remove duplicate built-in unit authorities

## A1. Delete superseded manually maintained built-in tables

Refactor `eggcalc/units.py` so built-in semantic literals exist only in the declaration section.

Remove manually maintained built-in definitions for:

- `UNIT_BASE`;
- `UNIT_ALIASES`;
- `UNIT_CATEGORIES`;
- `TEMPERATURE_CONVERSIONS`;
- `UNIT_CONVERSIONS`;
- `_CATEGORY_DIMENSIONS`;
- `_CATEGORY_NAME_TO_DIMENSION`;
- `_DERIVED_CATEGORIES` where it duplicates declaration/dimension semantics;
- old conversion/category/parser helper bodies that are later redefined.

Retain public compatibility names only as generated immutable adapters installed from the active declaration-built registry.

The final source should have one definition site for each public compatibility mapping. Do not rely on later redefinition to shadow an earlier literal.

### Required source-shape test

Add an AST/token-based test that asserts:

- exactly one top-level assignment/annotated assignment exists for each public compatibility map;
- each assignment is produced by the declaration/registry adapter installation path;
- no dictionary literal with built-in aliases/scales exists outside fixture/export tooling and `UNIT_DEFINITIONS` generation code;
- public semantic functions are defined once, except explicitly documented compatibility wrappers;
- `UnitValue` never calls a legacy string-semantic helper.

The check must not use a “latest definition wins” strategy. It must inspect the complete module.

## A2. Make family-base ownership singular

Choose one of these acceptable designs:

### Preferred design: explicit declaration field

Every `UnitSpec` explicitly supplies `base_canonical`. Remove the category fallback from `UnitSpec.__post_init__()`.

```python
UnitSpec(
    canonical="km",
    aliases=("km", "kilometer", "kilometers"),
    dimension=DIM_LENGTH,
    scale_to_base=1000.0,
    display="km",
    category="length",
    base_canonical="m",
)
```

### Acceptable alternative: one family declaration authority

Introduce an immutable `UnitFamilySpec` collection containing category, dimension, and base canonical, then mechanically generate each `UnitSpec.base_canonical` before registry validation. In this design:

- the family collection is the sole family-base authority;
- `UnitSpec.__post_init__()` must not contain its own category mapping;
- every generated `UnitSpec` is fully populated before registry construction;
- source-boundary checks prohibit additional category-to-base maps.

Do not infer bases from declaration order, scale `1.0`, canonical spelling, or category-specific conditionals distributed through the module.

## A3. Preserve generated compatibility behavior

After removing the old literals, verify exact compatibility adapters for:

- every alias and canonical;
- every family base and scale;
- categories;
- generated affine transformations;
- pairwise multiplicative compatibility table, if retained;
- custom-unit extension/rebuild behavior, if retained as public compatibility behavior.

The runtime conversion path must remain registry/expression-driven. Generated pairwise maps are introspection/compatibility data only.

### Workstream A acceptance criteria

- [ ] Built-in unit semantic literals exist in one declaration/family authority only.
- [ ] Public compatibility maps have one generated definition site each.
- [ ] No shadowed legacy map or shadowed semantic function remains.
- [ ] Every unit family base is explicitly owned by one authority.
- [ ] Registry construction consumes only completed declarations.
- [ ] Compatibility adapters remain immutable and behaviorally identical.
- [ ] Full-module authority checks fail if duplicate legacy semantics are reintroduced.

---

# Workstream B — Correct bounded unit rendering and parser invariants

## B1. Reject canonical-output overflow; never truncate

Change `render_expression()` so it constructs the complete bounded candidate and raises a bounded `ValueError` when the result exceeds `MAX_CANONICAL_UNIT_LENGTH`.

Incorrect behavior:

```python
return result[:MAX_CANONICAL_UNIT_LENGTH]
```

Required behavior:

```python
if len(result) > MAX_CANONICAL_UNIT_LENGTH:
    raise _unit_error(
        f"Canonical unit expression exceeds {MAX_CANONICAL_UNIT_LENGTH} characters"
    )
return result
```

No semantic unit name may be silently truncated.

`UnitExpression.__post_init__()` must validate rendering without recursive construction and without relying on a renderer that mutates/truncates output.

## B2. Enforce finite scale before and after expression operations

Add explicit checks around:

- atom powers;
- expression multiplication;
- expression division;
- expression powers;
- direct `UnitExpression` construction.

Reject:

- overflow to infinity;
- underflow to zero when scale must remain nonzero;
- NaN;
- invalid zero divisors;
- exponentiation that exceeds the allowed exponent before performing expensive work.

The error must be deterministic and bounded by `MAX_UNIT_ERROR_LENGTH`.

## B3. Make direct construction genuinely self-validating

Add negative tests proving direct construction rejects:

- unknown canonical factors;
- duplicate factors with an inconsistent supplied dimension/scale;
- invalid exponent type;
- exponent beyond bounds;
- excessive factor count;
- affine factor in a compound expression;
- dimension mismatch;
- scale mismatch;
- non-finite scale;
- zero scale;
- canonical rendering beyond the output bound.

Do not test only parser-produced instances. Direct construction is part of the invariant boundary.

## B4. Clarify and test depth semantics

The current grammar has no parenthesized recursion. Therefore choose one explicit policy:

- remove `MAX_COMPOUND_DEPTH` from the active parser contract and compatibility fixture because the grammar depth is fixed; or
- define depth as a concrete measurable property and enforce it with a test that can exceed the limit.

Do not retain a limit that is asserted only as `MAX_COMPOUND_DEPTH >= 1`.

The preferred approach for this release is to document fixed structural depth and remove the misleading dynamic-depth acceptance claim, while preserving the exported constant only as a deprecated compatibility constant if public compatibility requires it.

## B5. Expand focused parser/arithmetic tests

Add deterministic tests for:

- maximum accepted input length and first rejected length;
- maximum atom count and first rejected count;
- maximum exponent and first rejected exponent;
- maximum exponent digit count and first rejected count;
- complete input consumption;
- multiple division rejection;
- unknown atoms;
- `//` and `%` rejection;
- affine standalone acceptance;
- affine compound/power rejection;
- scale overflow and underflow;
- canonical output exact-bound acceptance and one-character-over rejection;
- bounded error message length;
- direct construction invariants;
- all `UnitValue` operators already migrated;
- package/single-file parity for all focused cases.

### Workstream B acceptance criteria

- [ ] Canonical unit output is never silently truncated.
- [ ] Every declared resource bound has a meaningful boundary test.
- [ ] Scale overflow, underflow, zero, NaN, and infinity are rejected.
- [ ] Direct construction enforces the same invariants as parser construction.
- [ ] Depth semantics are real and documented, not ceremonial.
- [ ] Affine and structural arithmetic behavior remains unchanged except for invalid-input rejection.

---

# Workstream C — Complete the legacy fixture and provenance proof

## C1. Compare every committed fixture field

Update the current fixture test to compare:

- exact alias set;
- alias-to-canonical mapping;
- normalized result;
- category;
- structural dimension;
- scale;
- offset;
- affine flag;
- display result;
- representative arithmetic result units;
- representative arithmetic display strings;
- exported limits that remain part of the compatibility contract.

Use explicit tolerances only for floating-point scale/offset data. Mapping, display, canonical, dimension, and arithmetic unit fields require exact equality.

## C2. Make fixture provenance reproducible

The committed fixture must contain:

- source commit `5a1bb34c9efa269ca6159217827f1742faa95d20`;
- exporter content SHA-256;
- Python version used;
- platform metadata;
- generation command;
- fixture schema version.

Add a verification mode to `scripts/export_unit_baseline.py` that:

1. validates the exporter hash recorded by the fixture;
2. validates fixture schema and required fields;
3. validates that the source commit field is exact and full length;
4. optionally regenerates from a caller-provided baseline checkout and compares bytes/normalized JSON.

CI does not need to create a Git worktree on every lane. It must at least run metadata/hash/schema verification and compare the current behavior to the committed fixture. A documented release-engineering command must reproduce the fixture from the exact baseline checkout.

## C3. Prevent fixture self-generation from migrated declarations

Add a source-boundary test proving the baseline exporter’s legacy mode does not import or iterate `UNIT_DEFINITIONS` to derive expected behavior. The fixture is an external behavioral oracle, not a serialization of the new declaration model.

### Workstream C acceptance criteria

- [ ] Every fixture field is compared by ordinary tests.
- [ ] Arithmetic fixture cases are exercised.
- [ ] Offset and display differences fail tests.
- [ ] Fixture schema and exporter hash are validated.
- [ ] Reproduction command uses the exact baseline commit.
- [ ] Baseline expectations are not generated from current `UNIT_DEFINITIONS`.

---

# Workstream D — Make release inventory prove the generated artifact

## D1. Derive single-file public API from the single-file namespace

Remove the package fallback used to supply `__all__` in single-file mode.

Single-file inventory must inspect the generated namespace directly:

- generated `__all__`, if present;
- otherwise the explicitly documented generated public export inventory;
- callable/public symbol existence for every exported name;
- absence of unexpected package-relative dependencies.

The single-file subprocess must not import `eggcalc` merely to manufacture expected public metadata.

Add a mutation test that removes one generated public export and proves inventory comparison fails.

## D2. Expand inventory coverage

Include exact normalized values for:

- version;
- protocol versions;
- public API exports and symbol types;
- command names, aliases, module targets, and symbols;
- unit declarations and all declaration fields;
- generated unit compatibility adapters;
- MCP tools, schemas, metadata, profiles;
- capability field names and stable values;
- evaluator policy names;
- mode-specific fields under an explicit allowlist.

Do not compare counts where exact content is available.

## D3. Prove fresh-process and source independence

For package and single-file modes:

- run in separate fresh subprocesses;
- use an unrelated temporary working directory;
- control `PYTHONPATH` deliberately;
- assert the loaded artifact identity;
- for generated mode, assert no `eggcalc.*` package modules are imported after inventory collection except explicitly allowed test harness modules;
- normalize nondeterministic paths/timestamps out of the result rather than omitting meaningful fields.

## D4. Commit release-candidate inventory evidence

Generate a normalized inventory artifact under `docs/release/` or `docs/evidence/` containing:

- candidate SHA;
- script SHA-256;
- package inventory hash;
- single-file inventory hash;
- explicit allowed differences;
- comparison result.

This artifact is evidence, not runtime authority.

### Workstream D acceptance criteria

- [ ] Generated public API is derived from the generated namespace.
- [ ] Single-file inventory cannot borrow package exports.
- [ ] Capabilities and policy authorities are included.
- [ ] Package and generated artifacts run in isolated subprocesses.
- [ ] A one-field mutation causes deterministic failure.
- [ ] Candidate inventory evidence records exact identities and hashes.

---

# Workstream E — Make source and wheel typing checks genuinely strict

## E1. Remove hidden dependency skipping for closure modules

Replace global `follow_imports = skip` in `mypy-strict.ini` with a configuration that analyzes imported closure dependencies normally.

Acceptable targeted exceptions must be narrow module overrides for known legacy modules and must not apply to:

- `eggcalc.units`;
- `eggcalc.mcp.server`;
- `eggcalc._protocol`;
- `eggcalc._version`;
- build-manifest code;
- the public consumer.

No `ignore_errors = true` or broad package exclusion is permitted.

## E2. Run the source consumer under the strict contract

Run:

```bash
python -m mypy --config-file mypy-strict.ini tests/typing/consumer.py
python tests/typing/consumer.py
```

The consumer must continue to exercise intended public package APIs. Do not simplify it merely to satisfy strict mode.

## E3. Run the installed-wheel consumer under the same contract

Update `scripts/verify_wheel_consumer.py` to:

- copy `mypy-strict.ini` or create an equivalent strict config in the temporary environment;
- run strict mypy against the copied consumer;
- keep the working directory outside the repository;
- remove repository paths from `PYTHONPATH` and `sys.path` where practical;
- assert package identity points into the temporary venv;
- assert `py.typed` is installed;
- execute the consumer;
- report the wheel filename and package version.

Add a negative test proving the verifier rejects source-tree leakage.

## E4. Keep ordinary typing green

The dedicated strict check supplements rather than replaces ordinary repository mypy. Both must pass.

### Workstream E acceptance criteria

- [ ] Closure modules are not hidden behind `follow_imports = skip`.
- [ ] Source consumer passes the strict configuration.
- [ ] Installed-wheel consumer passes the same strict contract.
- [ ] Wheel identity and `py.typed` presence are proven.
- [ ] Source-tree leakage produces a failing verifier result.
- [ ] Ordinary mypy remains green.

---

# Workstream F — Produce controlled architecture-cost evidence

## F1. Finalize one measurement script

Use `scripts/measure_architecture_costs.py` for both:

- baseline `b9df49173ecfc60312780aef998c003af0b000b6`;
- final implementation candidate.

Do not compare outputs from different script versions. Record the measurement-script SHA-256 in both result files.

Required cases:

- `import eggcalc`;
- `from eggcalc import evaluate`;
- CLI help;
- ordinary expression;
- exact command;
- MCP initialize;
- compact and full `tools/list`;
- unit-registry construction;
- normal unit parsing;
- maximum-bound unit parsing;
- representative compound `UnitValue` arithmetic;
- generated single-file startup;
- loaded module count;
- peak traced allocation.

## F2. Control the environment

Record and hold constant:

- OS and version;
- architecture;
- Python implementation/version;
- CPU identifier where available;
- power-mode caveat where applicable;
- sample count;
- warm-up count;
- command line;
- environment variables;
- commit SHA;
- script hash.

Run each timed sample in a fresh process. Use median as the primary comparison and retain mean and standard deviation.

## F3. Commit normalized results and interpretation

Commit:

- `docs/performance/release-6-baseline.json`;
- `docs/performance/release-6-final.json`;
- `docs/performance/release-6-comparison.md`.

The comparison must identify:

- absolute and percentage differences;
- import-boundary changes;
- module-count changes;
- peak-allocation changes;
- any stable regression above 15%;
- whether a regression is accepted, corrected, or blocks closure.

Do not fabricate cross-platform performance measurements. One controlled reference environment is sufficient for architecture-cost closure; CI correctness remains cross-platform.

### Workstream F acceptance criteria

- [ ] Baseline and final use the same script and environment.
- [ ] Full commit and script identities are recorded.
- [ ] All planned cost centers are measured.
- [ ] Normalized JSON and human interpretation are committed.
- [ ] No unexplained stable regression above 15% remains.
- [ ] Import-boundary regressions are treated as hard failures.

---

# Workstream G — Close CI and real evidence validation

## G1. Add focused polish checks to CI

CI must run:

- complete unit-authority source-shape checker;
- complete fixture metadata/hash/schema verification;
- committed fixture behavioral comparison;
- focused parser/render/invariant suite;
- package/single-file inventory comparison;
- strict source consumer;
- strict installed-wheel consumer;
- build-manifest validation and deterministic double build;
- actual repository evidence consistency validation after evidence exists;
- full supported test matrix.

Use portable Python comparison for deterministic build rather than shell-only assumptions where a step may later move across platforms.

## G2. Test the actual evidence documents

Expand `tests/test_evidence_consistency.py` so it contains both:

1. mutation/unit tests using temporary synthetic documents;
2. a repository test invoking `validate_documents()` on the default Release 4–6 evidence paths.

Before final evidence is committed, the repository-evidence test may be added in a deliberately expected-failure state only on a temporary implementation branch. It must be a normal passing test in the final candidate/evidence sequence.

CI must directly run:

```bash
python scripts/check_evidence_consistency.py
```

Do not rely solely on importing the validator in synthetic tests.

## G3. Freeze one implementation candidate

Before selecting `closure_code_sha`, commit all:

- production source polish;
- tests;
- checker scripts;
- workflow changes;
- fixture verification changes;
- inventory evidence;
- performance evidence;
- architecture/changelog corrections.

Any subsequent code, test, workflow, fixture, inventory, or performance change invalidates the candidate and requires a full rerun.

## G4. Obtain exact green workflow evidence

Run the complete workflow for the candidate and record:

- full 40-character SHA;
- workflow run ID;
- exact job names;
- conclusions;
- exact test totals per lane;
- skip and xfail totals/reasons;
- focused MCP/unit/polish suite totals;
- strict source/wheel consumer results;
- inventory/determinism results.

Do not infer green status from a commit message.

### Workstream G acceptance criteria

- [ ] CI executes all polish checks directly.
- [ ] Actual repository evidence documents are validated.
- [ ] One frozen implementation candidate receives a complete green workflow.
- [ ] Python 3.11 closure-focused suites pass on Linux, macOS, and Windows.
- [ ] Exact job and test totals are available for evidence authoring.

---

# Workstream H — Synchronize Release 4–6 closure evidence

## H1. Append final closure sections

Append `## Final Closure Evidence` to:

- `docs/release_4_evidence.md`;
- `docs/release_5_evidence.md`;
- `docs/release_6_evidence.md`.

Preserve historical sections, but label them explicitly as historical and superseded.

All three final sections must share:

- one `closure_code_sha` with 40 hexadecimal characters;
- one `closure_workflow_run_id`;
- exact date;
- exact job names and conclusions;
- exact lane totals in validator-compatible form;
- focused MCP, unit, parser, inventory, typing, and evidence totals;
- source and installed-wheel consumer results;
- deterministic-build result;
- package/single-file inventory identities;
- performance baseline/final identities and summary;
- retained compatibility adapters;
- explicit non-blocking deferrals, if any.

## H2. Correct stale current-status claims

The final sections must not contain:

- abbreviated SHAs;
- approximate counts such as `~3911`;
- “all tests pass” without numeric totals;
- old workflow runs presented as current;
- historical Windows failures presented as current;
- claims that runtime registry construction uses legacy maps;
- performance results from a different implementation candidate.

Historical records may remain above the final section when clearly labeled.

## H3. Evidence commit and post-evidence run

Use the established two-step identity model:

1. `closure_code_sha` is the exact implementation candidate tested by the full workflow;
2. evidence is committed as a documentation-only child;
3. a post-evidence workflow proves documentation and consistency checks remain green.

Do not repin evidence to its own documentation commit. Do not start another evidence-only SHA loop.

### Workstream H acceptance criteria

- [ ] Release 4–6 final sections share one exact candidate and workflow.
- [ ] Every count is numeric and arithmetically valid.
- [ ] Historical failures are clearly historical.
- [ ] Current architecture claims match the final source.
- [ ] Performance identities match committed artifacts.
- [ ] `scripts/check_evidence_consistency.py` passes against repository documents.
- [ ] Post-evidence CI passes without repinning.

---

## 4. Required focused tests

Create or expand these tests without duplicating the full suite unnecessarily:

### `tests/test_final_unit_authority.py`

Add:

- complete-module duplicate-authority inspection;
- exactly one generated compatibility-map definition site;
- explicit family-base ownership;
- exact fixture offset/display/arithmetic comparison;
- fixture metadata/hash/schema checks;
- generated adapter exact parity.

### `tests/test_final_unit_expression.py`

Add:

- canonical exact-bound acceptance;
- canonical over-bound rejection;
- finite-scale overflow and underflow;
- direct-construction invariant matrix;
- bounded error text;
- meaningful depth policy test/removal assertion;
- package/single-file focused parity.

### `tests/test_release_inventory.py`

Add mutations for:

- missing generated public export;
- changed protocol version;
- changed command target;
- changed unit offset;
- changed MCP profile;
- changed capability field.

### `tests/test_evidence_consistency.py`

Retain synthetic mutation tests and add a real default-document validation test.

### Wheel verification tests

Add a focused test or script self-test proving:

- wheel import identity succeeds outside the repository;
- `py.typed` is present;
- strict consumer succeeds;
- deliberate source-tree leakage is detected.

---

## 5. Required verification commands

Run from a clean checkout of the implementation candidate:

```bash
python -m ruff check .
python -m black --check .
python -m mypy eggcalc --ignore-missing-imports
python -m mypy --config-file mypy-strict.ini \
  eggcalc/units.py eggcalc/mcp/server.py eggcalc/_protocol.py \
  eggcalc/_version.py build_single.py tests/typing/consumer.py
python scripts/check_authority_boundaries.py
python scripts/export_unit_baseline.py --verify \
  --fixture tests/fixtures/units/legacy-5a1bb34c.json
python build_single.py --validate
python build_single.py -o /tmp/eggcalc-a.py
python build_single.py -o /tmp/eggcalc-b.py
python -c "from pathlib import Path; assert Path('/tmp/eggcalc-a.py').read_bytes() == Path('/tmp/eggcalc-b.py').read_bytes()"
python scripts/release_inventory.py --check
python scripts/generate_mcp_docs.py --check
python scripts/smoke_release_surfaces.py
python -m pytest tests/test_final_unit_authority.py -v
python -m pytest tests/test_final_unit_expression.py -v
python -m pytest tests/test_build_manifest_graph.py tests/test_release_inventory.py -v
python -m pytest tests/test_final_mcp_authority_closure.py -v
python -m pytest tests/ -v
python -m build
python scripts/verify_wheel_consumer.py dist/*.whl
python scripts/check_evidence_consistency.py
```

Also run the controlled baseline/final architecture-cost collection and commit its normalized results before candidate selection.

---

## 6. Recommended implementation commits

Keep the pass reviewable and bisectable.

1. `refactor(units): remove shadowed legacy built-in authorities`
2. `refactor(units): make family-base ownership explicit`
3. `fix(units): reject canonical rendering and scale bound violations`
4. `test(units): complete direct-construction and parser boundary coverage`
5. `test(units): verify full legacy fixture and provenance metadata`
6. `test(parity): derive generated public inventory from single-file namespace`
7. `chore(types): enforce strict source and installed-wheel consumers`
8. `perf: record controlled release 6 baseline and final architecture costs`
9. `ci: enforce scoped polish and real evidence checks`
10. `docs(evidence): synchronize releases 4-6 to final green candidate`

Do not combine source-authority deletion and evidence updates in the same commit.

---

## 7. Stop and rollback conditions

Stop and correct the active workstream if:

- removal of a legacy literal changes any fixture-covered public unit behavior;
- a compatibility map becomes mutable;
- registry construction begins reading generated compatibility adapters;
- custom registry/profile or MCP isolation tests regress;
- `RuntimeContext` or executor ownership is reopened without a failing regression test;
- canonical output is truncated rather than rejected;
- parser errors become unbounded;
- direct `UnitExpression` construction can bypass invariants;
- fixture expectations are regenerated from current declarations;
- single-file inventory imports package metadata to fill missing fields;
- strict typing is achieved through broad import skipping or ignores;
- wheel verification imports the source checkout;
- performance baseline and final use different scripts/environments;
- evidence is authored before the candidate workflow is green;
- evidence starts another self-referential SHA repin cycle.

---

## 8. Final closure checklist

### Unit source authority

- [ ] No manually maintained built-in `UNIT_BASE` literal remains.
- [ ] No manually maintained built-in `UNIT_ALIASES` literal remains.
- [ ] No manually maintained temperature/pairwise conversion table controls or duplicates built-in semantics.
- [ ] Shadowed old semantic function bodies are removed.
- [ ] Complete-module authority checker passes.
- [ ] Family-base ownership has one explicit authority.
- [ ] Generated adapters remain immutable and exact.

### Parser and structural invariants

- [ ] Canonical output overflow raises; it never truncates.
- [ ] Scale overflow, underflow, NaN, infinity, and zero are rejected.
- [ ] Direct construction enforces canonical/dimension/scale/affine invariants.
- [ ] Every advertised parser bound has a real boundary test.
- [ ] Error text is bounded.
- [ ] Depth semantics are concrete and documented.
- [ ] Existing valid arithmetic and affine behavior remains unchanged.

### Fixture and parity

- [ ] Exact alias/canonical/category/dimension/scale/offset/affine/display parity passes.
- [ ] Arithmetic fixture parity passes.
- [ ] Fixture exporter hash/schema/source identity are verified.
- [ ] Baseline reproduction procedure is documented.
- [ ] Generated inventory derives exports from the generated namespace.
- [ ] Package and single-file exact inventories match except explicit allowlist fields.
- [ ] Inventory mutation tests fail as expected.

### Typing and packaging

- [ ] Strict closure modules are not hidden by import skipping.
- [ ] Strict source consumer passes.
- [ ] Strict installed-wheel consumer passes outside the repository.
- [ ] Wheel identity and `py.typed` are proven.
- [ ] Ordinary mypy/Ruff/Black remain green.

### Performance and evidence

- [ ] Baseline and final architecture-cost JSON files are committed.
- [ ] Comparison uses one script/environment and exact identities.
- [ ] No unexplained stable regression above 15% remains.
- [ ] One exact implementation candidate has a complete green workflow.
- [ ] Release 4–6 final evidence shares that SHA and run ID.
- [ ] All lane/job/test counts are exact.
- [ ] Historical Windows failures are historical only.
- [ ] Actual repository evidence validator passes.
- [ ] Post-evidence CI passes without repinning.

## 9. Completion definition

This polish pass is complete when `eggcalc` has one readable built-in unit authority in source, bounded structural unit rendering that rejects rather than mutates invalid output, artifact-independent parity and typing proof, controlled architecture-cost evidence, and one exact synchronized cross-platform closure record for Releases 4–6.

Until every checklist item is satisfied, the implementation may be treated as a strong release candidate, but Releases 4, 5, and 6 remain open.
