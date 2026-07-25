# Releases 4–6 Candidate Completion and Evidence Finalization

Status: implementation handoff  
Repository: `eggstack/eggcalc`  
Baseline reviewed: `e2180ee80c6805884133d8ef003ef8446caf11eb`  
Depends on: `plans/017-releases-4-6-final-correctness-and-evidence-closure.md`

## 1. Purpose

The implementation at `e2180ee8` correctly closes the normalized duplicate-exponent bypass, removes fabricated final evidence, introduces separate candidate/final evidence modes, and corrects stale unit-authority and parser-depth documentation. It is nevertheless an incomplete Phase 1 candidate.

This plan closes only the remaining defects:

1. exact canonical-output acceptance is not tested;
2. scale underflow is not genuinely exercised;
3. package/single-file unit parity compares exit status rather than results;
4. the committed unit fixture is still generated from current declarations and generated adapters;
5. release inventory still executes against the repository source tree rather than an installed wheel and isolated generated artifact;
6. inventory mutation tests mutate Python dictionaries rather than release artifacts;
7. source and wheel consumers are not invoked with explicit strict mypy settings;
8. architecture-cost files still identify the earlier plan commit as the candidate;
9. CI emits no structured per-lane proof artifacts;
10. final evidence validation does not verify Git ancestry, evidence-only diffs, workflow identity, job conclusions, lane artifacts, inventory hashes, or performance identities;
11. no real green code candidate and directly parented evidence-only finalization commit exist.

This is a verification and release-proof pass. Do not reopen completed production architecture.

Releases 4, 5, and 6 remain open until every acceptance criterion and the final binary checklist in this plan are satisfied.

---

## 2. Preserve completed architecture

The implementation must preserve:

- `RuntimeContext` as the sole active evaluator/configuration authority;
- server-owned MCP registry, profile, configuration, executor, and session state;
- atomic configuration publication and stable in-flight context capture;
- permanent session ownership and fail-closed production dispatch;
- exact executor reservation accounting and bounded bookkeeping;
- `UNIT_DEFINITIONS` as the sole built-in unit semantic declaration inventory;
- explicit `UnitSpec.base_canonical` values;
- declaration-built immutable `UnitRegistry` and generated compatibility adapters;
- structural `UnitValue` arithmetic;
- affine-unit compound rejection;
- normalized exponent validation after duplicate-factor merging;
- bounded parser and renderer behavior;
- topological `MODULE_MANIFEST`-driven single-file construction;
- deterministic single-file generation;
- `_version.py` and `_protocol.py` as package authorities;
- `py.typed` wheel packaging;
- the current Linux, macOS, and Windows Python matrix;
- package, wheel, console, module, REPL, single-file, MCP, and typed-consumer surfaces.

No change may reintroduce manually maintained built-in unit maps, category-based compatibility fallback, public string-based unit arithmetic, process-global MCP authority, placeholder evidence, or evidence generated from an unfrozen candidate.

---

## 3. Non-goals

Do not add or redesign:

- unit families, aliases, conversion values, syntax, fractional exponents, or symbolic algebra;
- custom-unit semantics beyond preserving existing compatibility behavior;
- MCP tools, profiles, transports, authentication, or protocol versions;
- evaluator grammar, cache architecture, timeout architecture, or execution model;
- public package API names;
- supported Python versions or operating systems;
- the package/build backend;
- repository-wide strict typing outside the migrated modules and public consumer;
- speculative performance optimizations;
- a new release phase after this pass.

Any unrelated defect discovered during implementation must be recorded separately unless it blocks a required acceptance criterion.

---

# 4. Mandatory closure protocol

The work must end with two distinct commits.

## 4.1 Phase 1: frozen code candidate

Create a new code candidate commit named `CANDIDATE_SHA`. It must contain all production fixes, tests, scripts, CI changes, and removal of invalid performance/evidence artifacts.

The candidate must include no final evidence manifest and no claim that Releases 4–6 are closed.

The candidate must not contain:

- `0000000000` or any other placeholder workflow ID;
- `800832196439558383d22300ef36870c997437da` labeled as a current candidate;
- guessed test counts or job conclusions;
- candidate performance output recorded before `CANDIDATE_SHA` exists;
- a final closure section with unverified data.

Push `CANDIDATE_SHA` and obtain a real successful GitHub Actions run named `CANDIDATE_RUN_ID` whose `head_sha` is exactly `CANDIDATE_SHA`.

After that workflow starts, the candidate is immutable. Any change to source, tests, scripts, CI, packaging, build files, configuration, or lock files invalidates the candidate and requires a new candidate SHA and full rerun.

## 4.2 Phase 2: evidence-only finalization

Create one commit named `EVIDENCE_SHA` whose sole parent is `CANDIDATE_SHA`.

The diff `CANDIDATE_SHA..EVIDENCE_SHA` may modify only:

- `docs/release_4_evidence.md`;
- `docs/release_5_evidence.md`;
- `docs/release_6_evidence.md`;
- `docs/evidence/**`;
- `docs/performance/**`;
- a generated evidence index under `docs/` explicitly listed in the final manifest.

It must not modify:

- `eggcalc/**`;
- `tests/**`;
- `scripts/**`;
- `.github/**`;
- `build_single.py`;
- `pyproject.toml`;
- `mypy-strict.ini`;
- lock files;
- packaging metadata;
- plans.

The evidence commit must record actual candidate identities, actual workflow results, artifact hashes, inventory results, and controlled performance measurements. It must then pass strict final validation in CI.

---

# 5. Workstream A — finish exact unit-boundary proof

## A1. Preserve the normalized exponent fix

The post-merge normalized exponent check added at `e2180ee8` must remain.

### Acceptance criteria

- `("m", 16), ("m", 1)` is rejected after normalization;
- `("m", -16), ("m", -1)` is rejected after normalization;
- `("m", 15), ("m", 1)` normalizes to `("m", 16)` and succeeds;
- `("m", 16), ("m", -16)` normalizes to dimensionless and succeeds only with dimensionless dimension and scale `1.0`;
- boolean and non-integer exponents are rejected;
- no pre-merge-only check can bypass the post-merge invariant.

## A2. Test the actual canonical rendering limit

Replace the nominal `"m*m"` exact-bound test with deterministic inputs whose rendered strings are exactly:

- `MAX_CANONICAL_UNIT_LENGTH` characters;
- `MAX_CANONICAL_UNIT_LENGTH + 1` characters.

Use the internal render-only `_UncheckedUnitExpression` test seam where necessary. The test is for `render_expression()` itself; synthetic canonical tokens are acceptable because the renderer does not perform registry lookup.

The test helper must calculate the expected rendered length, not rely on a hand-maintained magic string.

### Required cases

1. empty factors render `None`;
2. exactly 256 characters are returned unchanged;
3. 257 characters raise `ValueError`;
4. the error string is bounded by `MAX_UNIT_ERROR_LENGTH`;
5. no prefix of the over-limit output is returned;
6. denominator formatting is included in at least one boundary case.

### Acceptance criteria

- the accepted test asserts `len(result) == MAX_CANONICAL_UNIT_LENGTH`;
- the rejected test asserts the unbounded expected representation would be exactly one character over;
- the production renderer never slices or truncates output;
- mutation test: replacing the raise with slicing causes the boundary suite to fail.

## A3. Test genuine floating-point underflow

Replace the current scale-mismatch test mislabeled as underflow.

A valid example is a direct expression using distinct small-scale length canonicals such as:

```python
factors = (("fermi", 16), ("nm", 16))
dimension = DIM_LENGTH ** 32
```

The expected scale multiplication crosses below the representable non-zero float range and becomes zero. Each individual normalized exponent remains within the configured bound.

### Required cases

- actual overflow to infinity;
- actual underflow to zero;
- finite but incorrect caller-supplied scale mismatch;
- exact smallest tested non-zero finite scale succeeds when it matches;
- multiplication/division helper paths also reject non-finite or zero scales.

### Acceptance criteria

- the underflow test proves the internally calculated scale equals zero or triggers the explicit zero-scale branch;
- it does not pass merely because the caller supplied an unrelated scale;
- the overflow and underflow tests fail if the finite/non-zero checks are removed;
- all error strings remain bounded.

---

# 6. Workstream B — real package/generated-file differential testing

The existing focused parity test compares package structural output with only the generated CLI return code. Replace it with one shared JSON probe executed in two isolated modes:

1. package mode against the source package during focused tests;
2. generated mode against a freshly built temporary single-file artifact using `runpy.run_path()` or an equivalent isolated loader.

Do not use the checked-in `eggcalc.py` as the sole tested artifact. Build a fresh temporary file within the test.

## B1. Positive probe output

For each input, emit canonical JSON containing:

- success boolean;
- normalized factors;
- full dimension tuple;
- scale-to-base using a deterministic numeric representation;
- rendered expression;
- affine status where applicable;
- resulting `UnitValue` value and unit for arithmetic cases.

Required positive cases:

- `m`;
- `m/s`;
- `m/s**2`;
- `kg*m/s**2`;
- `m*m`;
- `m**16`;
- cancellation to dimensionless;
- `km/h`;
- `C`, `F`, `K`, and `Ra` as standalone affine units;
- `1 m + 100 cm`;
- `2 m * 3 m`;
- `10 m / 2 s`;
- `5 m / 2 m`;
- `68 F -> C`;
- compatible floor division and modulo.

## B2. Negative probe output

For each invalid input, emit:

- failure class;
- stable normalized error category;
- bounded error text length.

Required negative cases:

- unknown unit;
- `m//s`;
- `m%s`;
- repeated division;
- exponent greater than 16;
- duplicate normalized exponent greater than 16;
- affine compound and affine power;
- input length 257;
- canonical rendering length 257;
- scale overflow and underflow.

Do not require byte-identical English wording if the public contract does not promise exact text. Compare stable exception type and explicit error category instead.

### Acceptance criteria

- package and fresh generated-file JSON are exactly equal for every positive case;
- package and generated-file error categories are exactly equal for every negative case;
- the test compares values, factors, dimensions, scales, units, and errors—not only exit codes;
- the generated subprocess asserts it did not import any `eggcalc` package module from the repository;
- removing or altering one generated unit definition makes the differential test fail;
- the test has no conditional skip when the repository is correctly configured.

---

# 7. Workstream C — restore an independent historical unit oracle

The current `scripts/export_unit_baseline.py` is a self-oracle because it imports current `UNIT_DEFINITIONS` and generated compatibility adapters. Replace this design.

## C1. Add a frozen historical exporter

Add:

`tests/fixtures/units/exporters/export_legacy_5a1bb34c.py`

This script must be written to run against a clean checkout at exact commit:

`5a1bb34c9efa269ca6159217827f1742faa95d20`

It may use only public or historical APIs available at that commit. It must not import or reference:

- `UNIT_DEFINITIONS`;
- `UnitSpec`;
- `UnitRegistry` if absent from or semantically different at the baseline;
- current generated adapters that did not exist at the baseline;
- current source files by path;
- the candidate checkout through `PYTHONPATH`.

At startup it must verify:

- imported `eggcalc` resolves under the supplied baseline checkout;
- `git rev-parse HEAD` for that checkout equals the exact source SHA;
- the current working tree used for export is clean, or the command explicitly records a dirty state and refuses production fixture generation.

## C2. Deterministic fixture schema

The fixture must include:

```json
{
  "metadata": {
    "schema_version": 1,
    "source_commit": "5a1bb34c9efa269ca6159217827f1742faa95d20",
    "exporter_path": "tests/fixtures/units/exporters/export_legacy_5a1bb34c.py",
    "exporter_sha256": "...",
    "python_implementation": "cpython",
    "python_version": "...",
    "platform": "...",
    "generation_command": "..."
  },
  "aliases": {},
  "arithmetic": {},
  "limits": {}
}
```

Do not include nondeterministic timestamps in the canonical fixture unless they are explicitly excluded from semantic comparison.

For every alias record:

- canonical;
- normalized representation;
- category;
- dimension or historical structural equivalent;
- scale-to-base;
- offset-to-base;
- affine flag;
- display value.

Arithmetic records must include unit and display for the existing cases plus addition, temperature conversion, floor division, and modulo.

## C3. Separate ordinary verification from reproduction

Add `scripts/verify_unit_baseline_fixture.py`.

Ordinary CI verification must:

- read the committed fixture as immutable expected data;
- compare the candidate runtime against every field;
- validate metadata and exporter hash;
- never regenerate expected values;
- never import the frozen exporter as a current-runtime oracle;
- never update the fixture.

Historical reproduction must be a separate command that:

- runs the frozen exporter against the exact baseline checkout;
- writes a temporary JSON file;
- compares temporary bytes or normalized content with the committed fixture;
- fails on any difference.

### Acceptance criteria

- the frozen exporter contains no `UNIT_DEFINITIONS` reference;
- changing current declarations cannot change expected fixture data;
- the ordinary verifier compares all alias fields, arithmetic fields, and limits;
- fixture generation from any commit other than the exact baseline fails;
- exporter hash mismatch fails;
- reproduction from a clean baseline checkout produces the committed fixture;
- CI runs ordinary verification on every candidate;
- a documented manual or dedicated workflow reproduces the fixture from the baseline checkout.

---

# 8. Workstream D — isolated release inventory

Rewrite `scripts/release_inventory.py` to compare actual release artifacts.

## D1. Explicit artifact inputs

Required interface:

```bash
python scripts/release_inventory.py \
  --wheel dist/eggcalc-*.whl \
  --single-file /tmp/eggcalc-release.py \
  --output /tmp/inventory.json \
  --check
```

The script must not silently fall back to the source package in `--check` mode.

## D2. Installed-wheel isolation

For wheel mode:

1. create a clean virtual environment;
2. install the exact supplied wheel;
3. run the inventory probe from a temporary directory outside the repository;
4. clear repository paths from `PYTHONPATH` and `sys.path`;
5. assert `eggcalc.__file__` is under the venv site-packages directory;
6. assert `py.typed` exists;
7. record wheel SHA-256 and installed package path;
8. close any MCP server deterministically.

## D3. Generated-file isolation

For single-file mode:

1. copy the exact supplied generated file to a temporary directory;
2. run it with repository `PYTHONPATH` removed;
3. load through `runpy.run_path()` or a dedicated probe mode;
4. record file SHA-256;
5. assert no `eggcalc.*` package modules were imported;
6. assert no path under the repository was imported;
7. inspect the generated namespace directly.

## D4. Canonical inventory contents

Inventory both artifacts for:

- artifact kind and SHA-256;
- package version;
- supported protocol versions;
- complete `__all__` list;
- existence and coarse type classification of every public export;
- CLI command name, aliases, module, symbol, category, minimum arguments, and usage;
- runtime capability field names and serialized value types;
- evaluator policy names and effective boolean ceilings;
- all unit definitions and all fields;
- generated alias/category/base/conversion adapter content or canonical hashes;
- MCP tool names;
- schemas;
- metadata;
- profiles;
- initialization protocol/capability fields;
- package/single-file documented allowed differences.

Normalize platform-dependent capability values only through an explicit allowed-difference rule. Do not omit a field merely because it differs by artifact mode.

### Acceptance criteria

- wheel and single-file inventory subprocesses run outside the repository;
- neither mode relies on repository `PYTHONPATH`;
- every public name in `__all__` exists;
- unexpected public names fail;
- protocol, CLI, unit, MCP, capability, and policy inventories match except for explicit documented differences;
- inventory JSON is deterministic and canonical;
- artifact hashes are present;
- a missing generated export fails;
- a changed protocol value fails;
- a changed unit offset fails;
- a changed MCP profile fails;
- a changed capability field fails;
- an imported source-tree package fails.

## D5. Real artifact mutation tests

Replace in-memory dictionary mutation assertions.

Required mutation classes:

1. build a temporary generated file, alter one public export or protocol value in the file, and rerun the collector;
2. build a temporary wheel from a copied source tree containing one controlled public-surface mutation, install that wheel, and rerun the collector;
3. alter one unit offset in a temporary generated artifact or temporary build source, rebuild, and rerun;
4. alter one MCP profile or schema in a temporary build source, rebuild, and rerun.

Each mutation test must assert that the actual collector or `--check` command returns non-zero. An assertion that two manually edited dictionaries differ is not an acceptable mutation test.

---

# 9. Workstream E — genuinely strict typed consumers

## E1. Source consumer

CI must run exactly or equivalently:

```bash
mypy \
  --strict \
  --follow-imports=normal \
  --ignore-missing-imports \
  tests/typing/consumer.py
```

Do not use `pyproject.toml` ordinary settings for this consumer.

Run the consumer from the repository root after type checking.

## E2. Installed-wheel consumer

`verify_wheel_consumer.py` must invoke the copied temporary consumer with explicit flags:

```bash
<venv-python> -m mypy \
  --strict \
  --follow-imports=normal \
  --ignore-missing-imports \
  /tmp/.../consumer.py
```

Do not depend on the module name matching `[mypy-tests.typing.consumer]`.

The script must additionally assert:

- `eggcalc` resolves under venv site-packages;
- `py.typed` exists;
- no repository path is present in the child `sys.path`;
- the consumer runs successfully after type checking;
- the check works on POSIX and Windows venv layouts.

## E3. Migrated modules

Run migrated modules with normal import resolution:

```bash
mypy --config-file mypy-strict.ini --follow-imports=normal \
  eggcalc/units.py \
  eggcalc/mcp/server.py \
  eggcalc/_protocol.py \
  eggcalc/_version.py \
  build_single.py
```

If imported non-migrated modules require scoped configuration, add explicit per-module non-strict sections. Do not globally return to `follow_imports=skip` or silently hide the migrated modules' imported types.

### Acceptance criteria

- source consumer uses explicit `--strict`;
- wheel consumer uses explicit `--strict`;
- both use `--follow-imports=normal`;
- removing an exported annotation or making a documented return type incompatible makes both checks fail;
- temporary consumer module naming cannot weaken strictness;
- no broad `ignore_errors = true` or unqualified `# type: ignore` is added;
- existing documented public consumer behavior still runs successfully.

---

# 10. Workstream F — controlled architecture-cost evidence

The existing `docs/performance/baseline.json` and `docs/performance/single_file.json` are invalid current evidence because they identify the earlier plan commit as the candidate. Remove them in the Phase 1 candidate unless they are clearly relocated and labeled as historical, non-closure data.

Do not commit new candidate performance output until `CANDIDATE_SHA` is frozen and green.

## F1. Measurement script requirements

Update `scripts/measure_architecture_costs.py` to record:

- exact `git rev-parse HEAD` from the measured checkout;
- dirty/clean state;
- label;
- command line;
- Python implementation and full version;
- OS, release, and architecture;
- CPU identifier where available;
- sample and warmup counts;
- timestamp as informational metadata only;
- every raw sample;
- median, mean, standard deviation, minimum, maximum;
- peak allocation and loaded module counts where applicable.

The script must refuse candidate output when:

- the checkout is dirty;
- the supplied expected SHA differs from `HEAD`;
- sample count is below 15;
- warmup count is below 5.

## F2. Required surfaces

Measure at minimum:

- `import eggcalc`;
- `from eggcalc import evaluate`;
- normal evaluation;
- exact command;
- CLI help;
- unit registry initialization;
- normal unit parsing;
- maximum-length unit parsing;
- `UnitValue` arithmetic;
- MCP initialization;
- compact tool listing;
- full tool listing;
- generated single-file startup;
- loaded eggcalc/exact/MCP module counts;
- peak allocation.

## F3. Baseline and candidate protocol

Use two clean worktrees on the same host and same Python executable:

- baseline: `5a1bb34c9efa269ca6159217827f1742faa95d20`;
- candidate: exact `CANDIDATE_SHA`.

Use identical environment variables, commands, warmups, samples, and machine load controls.

Add `scripts/compare_architecture_costs.py` producing canonical JSON and Markdown with:

- baseline SHA;
- candidate SHA;
- environment identity;
- per-metric baseline and candidate statistics;
- absolute and percentage deltas;
- threshold status;
- explanation field for any stable regression greater than 15%.

### Acceptance criteria

- no final performance artifact identifies `80083219` as the candidate;
- baseline and candidate files identify exact 40-character SHAs;
- baseline and candidate environment identities match or differences are explicitly disclosed;
- every required metric is present in both files;
- comparison covers every common metric;
- every stable regression over 15% has a concrete explanation or blocks closure;
- import-boundary regressions that load exact or MCP modules during plain import block closure;
- performance files are added only in the evidence-only commit.

---

# 11. Workstream G — structured CI proof artifacts

## G1. Per-lane test summaries

Each matrix lane must produce a canonical JSON summary from pytest JUnit XML or another deterministic first-party parser. Do not scrape human console prose.

Required fields:

- workflow run ID;
- workflow run attempt;
- workflow head SHA;
- job ID and job name;
- OS runner label;
- Python version;
- collected;
- passed;
- skipped;
- xfailed;
- xpassed;
- failed;
- errors;
- duration;
- conclusion.

Upload each as a uniquely named artifact, for example:

`lane-summary-ubuntu-3.12.json`

## G2. Static and artifact job summaries

Produce structured JSON for:

- ordinary Ruff;
- strict Ruff;
- Black;
- ordinary mypy;
- migrated-module strict mypy;
- source-consumer strict mypy;
- authority-boundary check;
- historical-fixture ordinary verification;
- deterministic build;
- isolated inventory;
- installed-wheel consumer;
- package build and Twine;
- release-surface smoke tests;
- focused MCP closure;
- focused unit closure.

The package job must upload:

- wheel and sdist hashes;
- generated single-file hash;
- canonical release inventory;
- wheel consumer result.

## G3. Candidate workflow gate

A candidate run is acceptable only when:

- `head_sha == CANDIDATE_SHA`;
- all required jobs exist;
- every required job concludes `success`;
- every matrix lane exists for the configured OS/Python matrix;
- every lane has `failed=0` and `errors=0`;
- all lane totals add up;
- artifacts are complete and parseable;
- no required job was skipped;
- the workflow file in the run is the workflow committed at `CANDIDATE_SHA`.

### Acceptance criteria

- CI uploads machine-readable summaries for every lane;
- duplicate or missing lanes fail evidence collection;
- non-success job conclusions fail evidence collection;
- summary head SHA mismatch fails;
- arithmetic mismatch in totals fails;
- the code candidate cannot pass candidate validation while retaining final evidence data.

---

# 12. Workstream H — authoritative evidence manifest and validator

## H1. Final manifest

The evidence-only commit must add:

`docs/evidence/releases-4-6-final.json`

This is the authoritative closure record. Markdown evidence files are generated views.

Required top-level fields:

- schema version;
- repository;
- release set `[4, 5, 6]`;
- candidate SHA;
- candidate parent SHA;
- candidate workflow run ID and attempt;
- workflow head SHA;
- evidence SHA or a documented self-identity strategy that does not require repinning;
- evidence parent SHA;
- complete job inventory and conclusions;
- complete lane inventory and totals;
- artifact names, IDs, and SHA-256 values;
- wheel, sdist, and generated-file hashes;
- release inventory path and hash;
- historical fixture path, source SHA, exporter path, and exporter hash;
- performance baseline, candidate, and comparison paths/hashes;
- retained compatibility shims;
- explicit deferrals, which must be empty for mandatory closure work;
- final decision.

Do not store the evidence commit's own SHA inside a file in a way that requires a self-referential repin loop. The validator may derive `EVIDENCE_SHA` from Git and verify parentage.

## H2. CI run snapshot

Add:

`docs/evidence/releases-4-6-ci-run.json`

It must be generated from the actual workflow run API/artifacts and contain no guessed values.

Add:

`docs/evidence/releases-4-6-inventory.json`

It must be the canonical isolated wheel/generated-file inventory from the candidate artifacts.

## H3. Final validator

Expand `scripts/check_evidence_consistency.py --final` to verify:

### Git identity

- current `HEAD` is `EVIDENCE_SHA`;
- `HEAD^` is exactly the manifest candidate SHA;
- candidate is an ancestor of evidence;
- evidence diff matches the evidence-only allowlist;
- candidate tree for code/tests/scripts/workflow is unchanged in evidence commit.

### Workflow identity

- run ID is positive and non-placeholder;
- run head SHA equals candidate SHA;
- run attempt matches;
- all required jobs exist once;
- all required conclusions are success;
- all configured lanes exist;
- lane JSON head SHA/job identity matches the run;
- lane totals add up and report zero failures/errors.

### Artifact identity

- manifest artifact hashes match committed evidence files;
- inventory hashes match candidate wheel and generated file;
- performance hashes match committed files;
- fixture/exporter hashes match committed files;
- duplicate or omitted artifacts fail.

### Markdown parity

- Release 4, 5, and 6 final sections are generated from the manifest;
- candidate SHA and workflow run ID are identical across all files;
- exact job names and conclusions match;
- exact lane totals match;
- performance and inventory identities match;
- no approximate counts appear;
- historical Windows failures are clearly historical;
- Release 6 states declaration-built registry authority and fixed-depth parser semantics;
- no stale placeholder or plan-candidate claims remain.

## H4. Candidate-state validator

`--candidate-state` must additionally reject:

- any final manifest;
- any final CI snapshot;
- any final inventory snapshot;
- final performance files claiming the current checkout as candidate;
- any release document claiming Releases 4–6 are closed;
- stale performance artifacts identifying `80083219` as the current candidate.

### Acceptance criteria

- candidate-state validation passes only before final evidence exists;
- final validation fails on candidate checkout;
- final validation passes only on a directly parented evidence-only commit;
- changing one manifest SHA fails;
- changing one workflow run ID fails;
- changing one job conclusion fails;
- deleting one lane fails;
- changing one lane count fails;
- adding a code change to evidence commit fails;
- changing one artifact hash fails;
- changing one performance identity fails;
- changing one Markdown count while leaving JSON unchanged fails.

---

# 13. Workstream I — Release 4–6 document cleanup and generation

## I1. Candidate commit

During Phase 1:

- keep historical sections for audit value;
- clearly label old workflow runs and Windows failures as historical snapshots;
- remove or retain only the explicit statement that final evidence is intentionally absent;
- remove invalid current performance files;
- do not claim Releases 4–6 are complete.

## I2. Evidence commit

During Phase 2:

Generate final closure sections in all three documents from `releases-4-6-final.json`.

Each final section must contain:

- exact candidate SHA;
- exact workflow run ID and attempt;
- exact evidence parent relation;
- complete job list and conclusions;
- exact per-lane totals for every configured lane;
- focused test suite totals;
- wheel/generated artifact hashes;
- inventory path/hash;
- historical fixture source/exporter identity;
- performance baseline/candidate/comparison identity;
- retained compatibility shims;
- explicit statement that the evidence commit is documentation/evidence-only;
- release decision.

### Acceptance criteria

- Release 4, 5, and 6 final sections are synchronized;
- no approximate test counts occur in final sections;
- no old workflow is presented as current closure evidence;
- no Windows failure is presented as current unless it occurred in the candidate run;
- no stale claim says UnitRegistry is built from legacy adapters;
- no stale claim describes recursive parser depth;
- generated Markdown exactly matches the authoritative manifest.

---

# 14. Required tests

Add or correct focused tests with these responsibilities.

## `tests/test_final_unit_expression.py`

- normalized exponent positive/negative overflow;
- exact normalized bound;
- cancellation;
- exact canonical length accepted;
- one-character-over canonical length rejected;
- genuine scale overflow;
- genuine scale underflow;
- finite scale mismatch distinguished from underflow;
- bounded errors;
- fresh generated-file differential results and errors.

## `tests/test_final_unit_authority.py`

- immutable fixture comparison for every field;
- frozen exporter source scan rejects current declaration APIs;
- metadata schema and hashes;
- exact baseline source SHA;
- reproduction comparator behavior.

## `tests/test_release_inventory.py`

- installed-wheel isolation;
- generated-file isolation;
- public export existence/type inventory;
- capability and policy fields;
- artifact hashes;
- real generated-file mutations;
- real temporary-wheel mutations;
- source-tree leakage rejection.

## `tests/test_evidence_consistency.py`

- candidate state with no final files succeeds;
- candidate state with final files fails;
- placeholder SHA/run fails;
- final manifest happy path;
- wrong candidate parent fails;
- non-evidence file in evidence diff fails;
- missing job/lane fails;
- unsuccessful conclusion fails;
- lane arithmetic mismatch fails;
- artifact hash mismatch fails;
- performance identity mismatch fails;
- Markdown/JSON mismatch fails.

## `tests/typing/consumer.py`

Preserve the documented public consumer. Do not weaken annotations or remove API usage merely to make mypy pass.

### Test-quality acceptance criteria

- no mandatory test conditionally skips due to missing checked-in/generated artifacts;
- tests named `exact_bound`, `underflow`, `parity`, `mutation`, `isolated`, or `final` exercise the named condition directly;
- mutation tests execute the real checker after mutating a release artifact or temporary build source;
- tests do not assert only that two manually edited Python values differ;
- negative tests assert the expected failure category.

---

# 15. CI implementation requirements

Update `.github/workflows/ci.yml` so the candidate run performs:

1. ordinary Ruff;
2. strict migrated-module Ruff;
3. Black;
4. ordinary mypy;
5. migrated-module strict mypy with normal imports;
6. source-consumer explicit strict mypy;
7. source consumer runtime execution;
8. authority-boundary validation;
9. immutable historical fixture verification;
10. candidate-state evidence validation;
11. build manifest validation;
12. deterministic double build;
13. focused MCP closure tests;
14. focused unit closure tests;
15. full test matrix;
16. JUnit generation and per-lane summary upload;
17. package/sdist/wheel build;
18. Twine validation;
19. fresh generated single-file build;
20. isolated wheel/generated inventory;
21. installed-wheel strict consumer;
22. release-surface smoke tests;
23. artifact hashes and summary uploads.

The evidence commit run must execute the same code checks and additionally run strict final evidence validation.

Use a deterministic condition such as the presence of `docs/evidence/releases-4-6-final.json` to select candidate versus final validation. The candidate path must reject a premature final file; the final path must require the complete evidence set.

### Acceptance criteria

- every matrix lane creates one summary artifact;
- package job creates inventory and artifact-hash artifacts;
- candidate workflow cannot succeed with final evidence present;
- evidence workflow cannot succeed with missing final evidence;
- final validator runs in CI on the evidence commit;
- no required closure check is advisory or `continue-on-error`;
- Windows and macOS lanes run the focused unit/MCP closure tests on Python 3.11 as required by the existing matrix policy.

---

# 16. Required verification commands

## 16.1 Candidate checkout

Run from a clean checkout of the future `CANDIDATE_SHA`:

```bash
python -m pip install -e '.[dev]'

ruff check eggcalc tests scripts build_single.py
black --check eggcalc tests scripts build_single.py

mypy eggcalc --ignore-missing-imports
mypy --config-file mypy-strict.ini --follow-imports=normal \
  eggcalc/units.py \
  eggcalc/mcp/server.py \
  eggcalc/_protocol.py \
  eggcalc/_version.py \
  build_single.py
mypy --strict --follow-imports=normal --ignore-missing-imports \
  tests/typing/consumer.py
python tests/typing/consumer.py

python scripts/check_authority_boundaries.py
python scripts/verify_unit_baseline_fixture.py \
  tests/fixtures/units/legacy-5a1bb34c.json
python scripts/check_evidence_consistency.py --candidate-state

python build_single.py --validate
python build_single.py -o /tmp/eggcalc-a.py
python build_single.py -o /tmp/eggcalc-b.py
cmp /tmp/eggcalc-a.py /tmp/eggcalc-b.py

pytest -q tests/test_final_unit_expression.py
pytest -q tests/test_final_unit_authority.py
pytest -q tests/test_release_inventory.py
pytest -q tests/test_evidence_consistency.py
pytest -q tests/test_final_mcp_authority_closure.py
pytest -q tests/

python -m build
python -m twine check dist/*
python build_single.py -o /tmp/eggcalc-release.py
python scripts/release_inventory.py \
  --wheel dist/eggcalc-*.whl \
  --single-file /tmp/eggcalc-release.py \
  --output /tmp/releases-4-6-inventory.json \
  --check
python scripts/verify_wheel_consumer.py dist/eggcalc-*.whl
python scripts/smoke_release_surfaces.py
```

Then push the exact candidate and require the complete GitHub Actions run to succeed.

## 16.2 Historical fixture reproduction

From a separate clean baseline worktree:

```bash
BASELINE_CHECKOUT=/path/to/eggcalc-5a1bb34c

test "$(git -C "$BASELINE_CHECKOUT" rev-parse HEAD)" = \
  "5a1bb34c9efa269ca6159217827f1742faa95d20"
test -z "$(git -C "$BASELINE_CHECKOUT" status --porcelain)"

PYTHONPATH="$BASELINE_CHECKOUT" \
python tests/fixtures/units/exporters/export_legacy_5a1bb34c.py \
  --baseline-checkout "$BASELINE_CHECKOUT" \
  --output /tmp/legacy-5a1bb34c.json

python scripts/verify_unit_baseline_fixture.py \
  tests/fixtures/units/legacy-5a1bb34c.json \
  --regenerated /tmp/legacy-5a1bb34c.json
```

## 16.3 Performance collection after green candidate

Use the same host and Python executable for both worktrees:

```bash
python scripts/measure_architecture_costs.py \
  --expected-sha 5a1bb34c9efa269ca6159217827f1742faa95d20 \
  --label baseline \
  --warmups 5 \
  --samples 15 \
  --output /tmp/eggcalc-baseline.json

python scripts/measure_architecture_costs.py \
  --expected-sha "$CANDIDATE_SHA" \
  --label candidate \
  --warmups 5 \
  --samples 15 \
  --single-file /tmp/eggcalc-release.py \
  --output /tmp/eggcalc-candidate.json

python scripts/compare_architecture_costs.py \
  --baseline /tmp/eggcalc-baseline.json \
  --candidate /tmp/eggcalc-candidate.json \
  --json-output /tmp/eggcalc-comparison.json \
  --markdown-output /tmp/eggcalc-comparison.md
```

## 16.4 Evidence finalization

After collecting actual workflow and artifact data:

```bash
python scripts/collect_ci_evidence.py \
  --run-id "$CANDIDATE_RUN_ID" \
  --expected-sha "$CANDIDATE_SHA" \
  --output /tmp/releases-4-6-ci-run.json

python scripts/finalize_release_evidence.py \
  --candidate-sha "$CANDIDATE_SHA" \
  --ci-run /tmp/releases-4-6-ci-run.json \
  --inventory /tmp/releases-4-6-inventory.json \
  --baseline-performance /tmp/eggcalc-baseline.json \
  --candidate-performance /tmp/eggcalc-candidate.json \
  --performance-comparison /tmp/eggcalc-comparison.json

python scripts/check_evidence_consistency.py \
  --final \
  --candidate-sha "$CANDIDATE_SHA"
```

Commit only the evidence allowlist and verify:

```bash
test "$(git rev-parse HEAD^)" = "$CANDIDATE_SHA"
git diff --name-only HEAD^ HEAD
python scripts/check_evidence_consistency.py --final --candidate-sha "$CANDIDATE_SHA"
```

---

# 17. Recommended implementation sequence

Use independently reviewable commits, then designate the last code commit as the frozen candidate.

1. `test(units): prove exact canonical bound and true scale underflow`
2. `test(single): compare package and freshly generated unit semantics`
3. `test(fixtures): add frozen legacy unit exporter`
4. `fix(fixtures): separate immutable verification from reproduction`
5. `fix(inventory): inspect installed wheel and isolated generated file`
6. `test(inventory): mutate real release artifacts`
7. `fix(types): enforce explicit strict source and wheel consumers`
8. `fix(perf): add controlled identity-aware measurement and comparison`
9. `fix(evidence): validate candidate ancestry artifacts and final manifest`
10. `ci: emit structured lane and release-artifact summaries`
11. `docs(evidence): remove invalid current performance remnants`

The final commit in this sequence becomes `CANDIDATE_SHA`. Do not amend it after the successful candidate workflow.

After the green run and measurements:

12. `docs(evidence): finalize releases 4-6 against candidate <short-sha>`

Commit 12 must be evidence-only and directly parented by the candidate.

---

# 18. Stop and rollback conditions

Stop and do not finalize if any of the following is true:

- canonical exact-bound acceptance still tests a short expression;
- the underflow test is only a caller-supplied scale mismatch;
- package/single parity compares only process return codes;
- the generated parity test uses only the checked-in single file;
- fixture expected values can be regenerated from current `UNIT_DEFINITIONS`;
- the frozen exporter imports current declaration APIs;
- inventory uses repository `PYTHONPATH` for artifact modes;
- inventory tests mutate only in-memory dictionaries;
- source consumer lacks explicit `--strict`;
- wheel consumer lacks explicit `--strict`;
- migrated modules use skipped imports;
- candidate performance identity is a plan or evidence commit;
- sample/warmup requirements are not met;
- candidate and baseline environments differ materially without disclosure;
- candidate workflow ID is absent, zero, guessed, or points to a different SHA;
- any required job or lane is absent, skipped, cancelled, or unsuccessful;
- lane totals do not add up;
- evidence commit modifies code, tests, scripts, CI, build, packaging, or plan files;
- final validator does not verify direct parentage and diff allowlist;
- one mutated workflow, lane, artifact, inventory, performance, or Markdown identity still passes validation;
- Release 6 contains stale legacy-authority or recursive-depth claims;
- historical failures are presented as current candidate results.

If a code or tooling defect is found after the candidate run, discard all candidate measurements and draft evidence, fix the defect, produce a new candidate SHA, and rerun the entire protocol. Do not repin evidence around changed code.

---

# 19. Final binary acceptance checklist

## Correctness and tests

- [ ] Normalized exponent bounds remain enforced post-merge.
- [ ] Canonical rendering accepts exactly 256 characters.
- [ ] Canonical rendering rejects exactly 257 characters.
- [ ] No canonical output is truncated.
- [ ] Genuine scale overflow is tested.
- [ ] Genuine scale underflow to zero is tested.
- [ ] Scale mismatch remains a distinct test.
- [ ] Package and freshly generated single-file positive results match exactly.
- [ ] Package and generated-file negative error categories match exactly.
- [ ] Differential tests compare data, not only return codes.

## Historical oracle

- [ ] Frozen exporter exists under `tests/fixtures/units/exporters/`.
- [ ] Frozen exporter runs only against exact commit `5a1bb34c...`.
- [ ] Frozen exporter contains no current declaration API references.
- [ ] Fixture metadata contains schema, source SHA, exporter path/hash, environment, and command.
- [ ] Ordinary verification reads but never regenerates expected data.
- [ ] Every alias, arithmetic, and limit field is compared.
- [ ] Clean-baseline reproduction matches the committed fixture.

## Artifact inventory

- [ ] Inventory requires explicit wheel and single-file inputs.
- [ ] Wheel is installed into an isolated venv.
- [ ] Generated file is loaded outside the repository.
- [ ] Repository `PYTHONPATH` is absent in artifact probes.
- [ ] Artifact hashes are recorded.
- [ ] Every public export exists and has expected type classification.
- [ ] Capabilities and evaluator policies are inventoried.
- [ ] Units, CLI, protocol, and MCP surfaces are inventoried.
- [ ] Real generated-file mutations fail the checker.
- [ ] Real temporary-wheel mutations fail the checker.

## Typing

- [ ] Source consumer uses explicit strict mypy.
- [ ] Wheel consumer uses explicit strict mypy.
- [ ] Both use normal import following.
- [ ] Temporary module naming cannot weaken strictness.
- [ ] `py.typed` is present in the installed wheel.
- [ ] No source-tree package leaks into the wheel check.

## Performance

- [ ] Invalid plan-commit performance files are removed from candidate state.
- [ ] Baseline measurement identifies exact `5a1bb34c...`.
- [ ] Candidate measurement identifies exact frozen candidate SHA.
- [ ] Both use the same controlled environment.
- [ ] At least 5 warmups and 15 samples are recorded.
- [ ] Raw samples and summary statistics are present.
- [ ] Comparison covers every required metric.
- [ ] Every stable regression over 15% is explained or blocks closure.
- [ ] Plain import boundaries do not regress.

## CI candidate

- [ ] Candidate-state validator passes.
- [ ] No final manifest exists in candidate.
- [ ] Complete matrix is green.
- [ ] Workflow head SHA equals candidate SHA.
- [ ] Every required job concludes success.
- [ ] Every required OS/Python lane exists.
- [ ] Every lane has exact machine-readable totals.
- [ ] Package artifacts, hashes, inventory, and wheel consumer results are uploaded.
- [ ] Candidate is frozen after the successful run.

## Evidence finalization

- [ ] Evidence commit directly follows candidate.
- [ ] Evidence diff is limited to the documented allowlist.
- [ ] Final JSON manifest is authoritative.
- [ ] CI run snapshot is derived from the actual run.
- [ ] Inventory snapshot matches candidate artifacts.
- [ ] Performance files match baseline and candidate identities.
- [ ] Release 4, 5, and 6 Markdown is generated from the manifest.
- [ ] Exact workflow, job, lane, inventory, fixture, and performance identities match.
- [ ] Final validator checks Git ancestry and diff allowlist.
- [ ] Final validator fails every required mutation test.
- [ ] Evidence commit CI passes strict final validation.

## Release decision

Releases 4, 5, and 6 may be marked closed only when every checkbox above is satisfied. A code candidate without a verified green workflow is not a release candidate. A green candidate without the directly parented evidence-only commit is not a closed release. Internally consistent placeholders, source-coupled inventories, self-generated baselines, nominal boundary tests, and prose-only claims are not acceptable evidence.
