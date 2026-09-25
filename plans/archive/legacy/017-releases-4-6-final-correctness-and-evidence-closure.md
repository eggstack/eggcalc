# Releases 4–6 Final Correctness and Evidence Closure

Status: implementation handoff  
Repository: `eggstack/eggcalc`  
Baseline reviewed: `d6854d96bfe96e31da1f5613ca01992fe8c93c05`  
Supersedes the incomplete closure claims produced by:

- `plans/015-releases-4-6-final-unit-authority-and-evidence-closure.md`
- `plans/016-releases-4-6-scoped-polish-and-evidence-closure.md`

This is a narrowly scoped correctness-and-proof pass. The implementation at `d6854d96` successfully removed the duplicated built-in unit tables, made family bases explicit, moved runtime behavior onto the declaration-built registry, corrected silent canonical rendering truncation, and substantially improved the verification surface. Do not reopen the MCP ownership, runtime-context, executor, module-manifest, or general unit architecture.

The remaining blockers are specific:

1. one normalized `UnitExpression` exponent invariant is not enforced after duplicate-factor merging;
2. several tests claim exact boundary or artifact parity coverage without exercising the named boundary or comparing the actual artifacts;
3. the committed unit fixture is no longer independent from the migrated declaration authority;
4. release inventory does not yet prove an isolated wheel and isolated generated single file, and mutation tests do not mutate an artifact;
5. strict typing is not applied to the actual source and copied wheel-consumer identities;
6. performance artifacts are attached to the plan commit and do not compare the historical baseline with the implementation candidate;
7. Release 4–6 evidence uses the plan SHA, a placeholder workflow ID, incomplete lane data, and stale current-status prose.

Releases 4, 5, and 6 remain open until the two-phase candidate/evidence protocol and every final gate in this document are complete.

---

## 1. Preserve completed architecture

The implementation must preserve all of the following:

- instance-owned MCP registry, profile, configuration, executor, and session behavior;
- `RuntimeContext` as the sole active evaluator/configuration authority;
- atomic configuration publication and stable in-flight context capture;
- permanent session ownership and fail-closed production dispatch;
- exact executor reservation accounting with bounded live bookkeeping;
- `UNIT_DEFINITIONS` as the built-in unit semantic authority;
- explicit `UnitSpec.base_canonical` values;
- declaration-built `UnitRegistry` and immutable generated compatibility adapters;
- structural `UnitValue` arithmetic and affine compound rejection;
- bounded unit parser and renderer;
- topological `MODULE_MANIFEST`-driven single-file assembly;
- deterministic single-file generation;
- dynamic version/protocol authorities;
- `py.typed` wheel packaging;
- current Linux, macOS, and Windows Python matrix;
- package, wheel, console, module, single-file, and MCP compatibility surfaces.

No workstream may reintroduce manually maintained unit tables, category fallbacks, string-based public unit arithmetic, module-global MCP authority, or placeholder evidence.

## 2. Non-goals

Do not add or redesign:

- unit families, aliases, syntax, fractional exponents, or symbolic algebra;
- custom-unit semantics beyond preserving already documented compatibility behavior;
- MCP tools, profiles, transports, authentication, or protocol versions;
- evaluator grammar, cache architecture, or timeout architecture;
- public package API names;
- package/build backend;
- supported Python versions or operating systems;
- repository-wide strict typing outside the explicitly migrated modules and public consumer;
- speculative performance optimization;
- new release phases after this closure pass.

This pass fixes false-positive verification and records defensible release evidence. It is not a feature release.

---

# 3. Required two-phase closure protocol

The implementation must use two distinct commits.

## Phase 1 — Immutable code candidate

Create a code candidate commit, referred to below as `CANDIDATE_SHA`, containing only:

- production correctness fixes;
- test corrections;
- verifier/inventory/exporter/measurement tooling;
- CI workflow changes;
- removal of the invalid placeholder final-evidence sections;
- documentation explaining how final evidence is produced.

`CANDIDATE_SHA` must not contain:

- `0000000000` or another placeholder workflow ID;
- guessed lane counts;
- performance output labeled as the candidate without having run at `CANDIDATE_SHA`;
- a final Release 4–6 evidence manifest;
- claims that Releases 4–6 are closed.

Push `CANDIDATE_SHA` and obtain a real successful GitHub Actions workflow run, referred to as `CANDIDATE_RUN_ID`.

The code candidate is frozen after that run. Any code, test, script, workflow, or configuration change invalidates the candidate and requires a new candidate SHA and run.

## Phase 2 — Evidence-only finalization

Create one evidence-only commit, referred to below as `EVIDENCE_SHA`, whose parent is exactly `CANDIDATE_SHA`.

The diff from `CANDIDATE_SHA` to `EVIDENCE_SHA` may modify only this allowlist:

- `docs/release_4_evidence.md`;
- `docs/release_5_evidence.md`;
- `docs/release_6_evidence.md`;
- `docs/evidence/**`;
- `docs/performance/**`;
- generated evidence indexes explicitly documented by this plan.

It must not modify:

- Python source;
- tests;
- scripts;
- CI workflows;
- packaging files;
- build files;
- lock files.

The evidence commit records:

- exact full `CANDIDATE_SHA`;
- exact positive `CANDIDATE_RUN_ID`;
- run/job snapshot proving required jobs concluded `success` for `CANDIDATE_SHA`;
- exact per-lane test totals;
- baseline and candidate performance identities and hashes;
- wheel/single-file inventory identities and hashes;
- exact evidence generation commands.

The evidence validator must verify that `EVIDENCE_SHA^` equals `CANDIDATE_SHA` and that the candidate-to-evidence diff is evidence-only.

### Two-phase acceptance criteria

- [ ] A code candidate is green before final evidence is written.
- [ ] No placeholder final evidence exists in the code candidate.
- [ ] The evidence commit has the code candidate as its direct parent.
- [ ] The evidence commit changes only the evidence allowlist.
- [ ] Any post-candidate code change forces a new candidate/run.

---

# Workstream A — Close the normalized exponent invariant

## A1. Recheck exponent bounds after factor merging

`UnitExpression.__post_init__()` currently validates each incoming exponent before combining duplicate canonicals. A caller can therefore provide duplicate entries whose individual exponents are legal but whose normalized sum exceeds `MAX_ABS_UNIT_EXPONENT`.

Required sequence:

1. validate factor tuple shape and individual exponent type;
2. combine duplicate canonical names;
3. remove zero exponents;
4. validate every normalized exponent against `MAX_ABS_UNIT_EXPONENT`;
5. validate normalized factor count;
6. derive dimension/scale and validate the supplied values;
7. validate canonical rendering.

Required logic:

```python
combined[canonical] = combined.get(canonical, 0) + exponent

normalized = tuple(
    sorted((name, exponent) for name, exponent in combined.items() if exponent)
)
for canonical, exponent in normalized:
    if abs(exponent) > MAX_ABS_UNIT_EXPONENT:
        raise _unit_error(
            f"Normalized exponent for {canonical!r} exceeds {MAX_ABS_UNIT_EXPONENT}"
        )
```

Do not clamp, split, or silently preserve an out-of-range normalized exponent.

## A2. Add direct-construction regression tests

Add tests for:

- `(("m", 16), ("m", 1))` rejecting normalized exponent `17`;
- `(("m", -16), ("m", -1))` rejecting normalized exponent `-17`;
- `(("m", 16), ("m", -16))` normalizing to dimensionless and succeeding only with dimension `DIM_DIMENSIONLESS` and scale `1.0`;
- duplicate factors summing to exactly `MAX_ABS_UNIT_EXPONENT` succeeding;
- duplicate factors whose supplied dimension or scale describes the pre-normalized rather than normalized result rejecting;
- boolean exponents rejecting even though `bool` is an `int` subclass.

Tests must construct `UnitExpression` directly. Parser tests alone are insufficient.

### Workstream A acceptance criteria

- [ ] Normalized exponents are checked after duplicate merging.
- [ ] Positive and negative overflow cases reject deterministically.
- [ ] Exact normalized exponent bound succeeds.
- [ ] Cancellation to a dimensionless expression is validated correctly.
- [ ] Error text remains within `MAX_UNIT_ERROR_LENGTH`.

---

# Workstream B — Replace nominal boundary tests with real boundary proofs

## B1. Exact input-length boundary

The test named `test_maximum_accepted_input_length_and_first_rejected` must prove both sides of the boundary.

Use a test-only registry or a temporary custom declaration containing:

- one valid alias whose length is exactly `MAX_UNIT_STRING_LENGTH`;
- one otherwise equivalent alias whose length is `MAX_UNIT_STRING_LENGTH + 1`.

Run the real parser against both:

- exact maximum parses successfully;
- first-over maximum rejects with bounded deterministic text.

Do not use repeated `"m"` characters and call the test complete when only the over-limit branch is exercised.

The preferred test mechanism is a context manager that temporarily replaces the private module registry and restores it in `finally`. It must not mutate `UNIT_DEFINITIONS` or leak state across tests.

## B2. Exact canonical-output boundary

Create a test registry with valid canonical tokens whose rendered expression is:

- exactly `MAX_CANONICAL_UNIT_LENGTH` characters;
- exactly one character over the limit.

Construct a valid `UnitExpression` through the same registry.

Assert:

- exact-bound rendering returns the complete unmodified string;
- one-over rendering raises;
- no prefix/truncation is returned;
- direct construction invokes the same bound.

The test must calculate the canonical string length from the test data rather than hardcoding an approximate expression.

## B3. Exact atom and exponent boundaries

For each bound, test the maximum accepted value and first rejected value:

- `MAX_COMPOUND_ATOMS` and `MAX_COMPOUND_ATOMS + 1`;
- `MAX_ABS_UNIT_EXPONENT` and `MAX_ABS_UNIT_EXPONENT + 1`;
- `MAX_EXPONENT_DIGITS` and `MAX_EXPONENT_DIGITS + 1`, while distinguishing digit-count rejection from value-bound rejection.

Where the exponent numeric bound is smaller than the digit-count bound, use a parser-level tokenization helper or test-only configured bound so that the named digit boundary is actually reached. Do not claim exact digit-bound acceptance when every value at that width is rejected earlier for magnitude.

## B4. Resolve depth semantics cleanly

The grammar has no recursive parentheses, so dynamic compound depth is fixed at one.

Required action:

- remove `depth` and the unreachable `depth > MAX_COMPOUND_DEPTH` condition from the parser;
- retain `MAX_COMPOUND_DEPTH` only if public compatibility requires it;
- mark the constant as a deprecated compatibility value in code and documentation;
- test that the active parser has no dynamic-depth branch;
- do not call `MAX_COMPOUND_DEPTH` an enforced recursion limit in current evidence.

## B5. Real package/single-file differential tests

The current focused parity test compares package parser output with only the single-file CLI exit code. Replace it with a true differential harness.

For each focused case, execute fresh subprocesses that emit the same canonical JSON structure:

```json
{
  "ok": true,
  "factors": [["m", 1], ["s", -2]],
  "dimension": [1, 0, -2, 0, 0, 0, 0, 0, 0],
  "scale_to_base": 1.0,
  "rendered": "m/s**2"
}
```

For rejected inputs, emit:

```json
{
  "ok": false,
  "error_type": "ValueError",
  "error": "bounded deterministic message"
}
```

Compare package and generated single-file JSON exactly, allowing only explicitly documented floating-point normalization.

Cases must include:

- normal atom;
- product;
- division and power;
- dimensionless cancellation;
- standalone affine unit;
- affine compound rejection;
- unknown atom;
- multiple division rejection;
- maximum accepted input;
- first-over input;
- maximum accepted canonical rendering;
- first-over canonical rendering;
- normalized duplicate exponent overflow.

The single-file artifact must be built into a temporary directory during the test. Do not use a potentially stale checked-in `eggcalc.py` without rebuilding it.

### Workstream B acceptance criteria

- [ ] Every named exact boundary exercises both accepted and rejected sides.
- [ ] Canonical exact-bound tests use valid registered canonicals.
- [ ] Parser depth documentation matches the actual non-recursive grammar.
- [ ] Package and generated single-file outputs are compared, not just exit codes.
- [ ] Focused negative behavior is also differential-tested.

---

# Workstream C — Restore an independent historical unit oracle

## C1. Separate historical export from current verification

The current `scripts/export_unit_baseline.py` reads current generated maps and `UNIT_DEFINITIONS`. That cannot serve as an independent pre-migration oracle.

Split responsibilities:

### Frozen historical exporter

Add a frozen exporter under a path such as:

`tests/fixtures/units/exporters/export_legacy_5a1bb34c.py`

Requirements:

- designed to run with `PYTHONPATH` pointed at an exact checkout of `5a1bb34c9efa269ca6159217827f1742faa95d20`;
- reads only APIs/tables that existed at that commit;
- contains no reference to `UNIT_DEFINITIONS`, `UnitSpec`, or declaration-built registry APIs introduced later;
- has a committed SHA-256 recorded in fixture metadata;
- produces deterministic normalized JSON;
- never imports the current checkout while exporting the historical checkout.

### Current fixture verifier

Convert `scripts/export_unit_baseline.py` into a verifier/reproduction coordinator, or replace it with clearly named scripts:

- `scripts/verify_unit_baseline_fixture.py`;
- optional `scripts/regenerate_unit_baseline_fixture.py`.

The ordinary verifier must:

- validate fixture schema and metadata;
- validate the frozen exporter hash;
- validate exact source commit identity;
- compare current public behavior against the committed fixture;
- never regenerate expected values from current `UNIT_DEFINITIONS`.

The optional regeneration command must require an explicit baseline checkout path and verify:

```bash
git -C "$BASELINE_CHECKOUT" rev-parse HEAD
```

equals the exact source SHA before executing the frozen exporter.

## C2. Expand fixture metadata

The fixture metadata must include:

```json
{
  "schema_version": 1,
  "source_commit": "5a1bb34c9efa269ca6159217827f1742faa95d20",
  "source": "legacy public runtime behavior",
  "exporter_path": "tests/fixtures/units/exporters/export_legacy_5a1bb34c.py",
  "exporter_sha256": "...",
  "python_version": "...",
  "platform": "...",
  "generation_command": "..."
}
```

The Python/platform fields describe provenance and are not grounds to weaken cross-platform current-behavior comparison.

## C3. Compare the complete oracle

Ordinary tests must compare every fixture field:

- exact alias inventory;
- canonical mapping;
- normalization;
- category;
- dimension;
- scale;
- offset;
- affine flag;
- display;
- arithmetic result unit;
- arithmetic result display;
- retained public resource limits.

Use approximate comparison only for floating-point scale and offset values. Everything else is exact.

## C4. Add anti-self-oracle tests

Add AST/text tests proving:

- the frozen historical exporter does not mention `UNIT_DEFINITIONS`, `UnitSpec`, or current registry construction;
- the current verifier does not call its own current exporter to compute expected alias semantics;
- changing a current declaration without changing the fixture causes parity failure;
- changing the fixture exporter hash causes metadata verification failure;
- changing the fixture source commit causes verification failure.

### Workstream C acceptance criteria

- [ ] Historical expectations are generated only from the exact historical checkout.
- [ ] Ordinary CI uses the committed fixture as an external oracle.
- [ ] The historical exporter has no current declaration dependency.
- [ ] Fixture metadata is complete and hash-pinned.
- [ ] Coordinated current-authority mutations cannot rewrite both sides and pass unnoticed.

---

# Workstream D — Make release inventory inspect actual isolated artifacts

## D1. Inventory an installed wheel, not the source package

Extend `scripts/release_inventory.py` to operate on explicit artifacts:

```bash
python scripts/release_inventory.py \
  --wheel dist/eggcalc-*.whl \
  --single-file /tmp/eggcalc.py \
  --check
```

The script must:

1. create an isolated temporary virtual environment;
2. install only the supplied wheel plus minimal verifier dependencies;
3. run package inventory from an unrelated temporary working directory;
4. assert `eggcalc.__file__` resolves under that environment’s `site-packages`/`dist-packages`;
5. run generated single-file inventory in a separate fresh process;
6. avoid adding the repository root to `PYTHONPATH` for either artifact process;
7. fail if source checkout modules satisfy an import.

A source-mode developer option may remain, but release CI and evidence must use wheel mode.

## D2. Prove generated single-file isolation

Run the generated file with isolated interpreter semantics where supported, for example `python -I`, from an unrelated temporary directory.

After collection, assert:

- no `eggcalc` package was imported to manufacture metadata;
- no `eggcalc.*` package module exists in `sys.modules`;
- every exported public name exists in the generated namespace;
- symbol kinds match the wheel inventory (`function`, `class`, `constant`, `module-lazy-export`, etc.);
- generated `__all__` is read from the generated namespace only.

## D3. Expand inventory fields

The normalized inventory must contain exact values for:

- version;
- author/public metadata intentionally part of the release surface;
- protocol versions;
- public export names and symbol kinds;
- CLI command names, aliases, module targets, and symbols;
- capability field names and stable values;
- evaluator policy names;
- unit declaration fields;
- generated unit compatibility adapters;
- MCP tool names, schemas, metadata, and profiles;
- artifact identity (`wheel_sha256`, `single_file_sha256`);
- Python implementation/version used for collection.

Nondeterministic paths and timestamps must be normalized, not used as a reason to omit meaningful fields.

## D4. Mutate artifacts, then rerun inventory

Replace dictionary-only mutation tests with artifact mutation tests.

Required mutations:

1. remove one name from the generated file’s `__all__` assignment;
2. change one generated protocol version literal;
3. change one generated command target;
4. change one generated unit offset;
5. change one generated MCP profile entry;
6. remove or change one generated capability field;
7. remove one exported symbol while leaving its `__all__` entry.

For each mutation:

- copy the generated artifact to a temporary path;
- apply one deterministic textual/AST mutation;
- rerun the inventory collector against the mutated artifact;
- assert the comparison fails for the expected path;
- assert the verifier does not merely crash before producing a useful mismatch.

At least one wheel mutation test should unpack a wheel, change `eggcalc/__init__.py` or another inventory-bearing file, repack it deterministically, and prove wheel/single comparison detects the divergence.

## D5. Produce a machine-readable candidate inventory artifact

After `CANDIDATE_SHA` is frozen and its wheel/single file are built, produce:

`docs/evidence/releases-4-6-inventory.json`

It must contain:

- `candidate_sha`;
- wheel filename and SHA-256;
- single-file SHA-256;
- collector script SHA-256;
- normalized wheel inventory hash;
- normalized single-file inventory hash;
- explicit allowed differences;
- result `match: true`.

This file belongs in `EVIDENCE_SHA`, not `CANDIDATE_SHA`.

### Workstream D acceptance criteria

- [ ] Release inventory compares an isolated installed wheel with an isolated generated file.
- [ ] Repository `PYTHONPATH` is absent from release inventory subprocesses.
- [ ] Public symbol existence and kinds are checked.
- [ ] Capabilities and policy names are inventoried.
- [ ] Mutation tests modify artifacts and rerun the real collector.
- [ ] Candidate inventory evidence is hash-pinned.

---

# Workstream E — Apply strict typing to the actual checked identities

## E1. Source consumer must run in strict mode

Change CI from:

```bash
mypy --config-file pyproject.toml tests/typing/consumer.py
```

to an explicit strict command using normal import resolution, for example:

```bash
mypy \
  --strict \
  --follow-imports=normal \
  --ignore-missing-imports \
  tests/typing/consumer.py
```

If a config file is used, its module override must match `tests.typing.consumer` and CI must invoke the file as that module identity.

Do not rely on global `strict = false` plus a module override that the actual invocation does not match.

## E2. Wheel consumer must run with explicit `--strict`

The copied temporary consumer is a top-level module named `consumer`, not `tests.typing.consumer`.

Required wheel command:

```bash
python -m mypy \
  --strict \
  --follow-imports=normal \
  --ignore-missing-imports \
  /tmp/.../consumer.py
```

Alternatively, generate a wheel-specific config containing `[mypy-consumer] strict = true` and verify the effective mypy configuration in a test. Explicit `--strict` is preferred.

The wheel verifier must continue to prove:

- import path is under the isolated environment;
- `py.typed` exists;
- source root is not importable;
- consumer executes successfully after type checking.

## E3. Migrated module import policy

For these modules:

- `eggcalc/units.py`;
- `eggcalc/mcp/server.py`;
- `eggcalc/_protocol.py`;
- `eggcalc/_version.py`;
- `build_single.py`;

use normal import resolution for their public/imported types. Do not use `follow_imports = skip` or `silent` as the sole reason errors disappear.

Legacy dependencies may have targeted per-module `ignore_errors = true` overrides if necessary, but:

- their symbols must still resolve;
- imported values must not degrade closure modules to untracked `Any` without an explicit narrow annotation;
- every new ignore must be justified and `warn_unused_ignores` must remain enabled.

## E4. Add command-contract tests

Add tests that inspect or execute the exact CI/wheel commands and fail if:

- source consumer loses `--strict`;
- wheel consumer loses `--strict`;
- either consumer uses `follow-imports=skip`;
- copied wheel consumer relies on the unmatched `[mypy-tests.typing.consumer]` override;
- wheel source-isolation probe is removed.

### Workstream E acceptance criteria

- [ ] Actual source consumer invocation is strict.
- [ ] Actual copied wheel consumer invocation is strict.
- [ ] Migrated modules use normal type resolution.
- [ ] Strictness is not inferred from an unmatched module override.
- [ ] Wheel type/runtime verification remains source-isolated.

---

# Workstream F — Produce controlled historical-versus-candidate performance evidence

## F1. Pin identities

Use:

- historical baseline: `5a1bb34c9efa269ca6159217827f1742faa95d20`;
- final implementation: exact `CANDIDATE_SHA`.

Do not use the plan commit as either identity.

The measurement runner must record the actual checkout SHA by executing `git rev-parse HEAD`; it must not accept an arbitrary label as proof of identity.

## F2. Use matched environments

Measure baseline and candidate on the same:

- physical/virtual host;
- CPU architecture;
- OS version;
- Python executable and version;
- environment variables;
- dependency set where compatible;
- sample/warmup configuration.

Record all environment metadata.

Recommended minimum:

- 5 warmup executions per surface;
- 20 measured executions per surface;
- median, mean, standard deviation, minimum, maximum;
- peak traced memory where supported;
- loaded module counts for import/MCP surfaces.

If the historical checkout cannot use the exact current dependency lock, document the precise dependency difference and avoid claiming causality for small deltas.

## F3. Required surfaces

Measure at least:

- `import eggcalc`;
- `from eggcalc import evaluate`;
- ordinary expression evaluation;
- CLI help;
- one exact command;
- unit registry initialization;
- normal unit parse;
- maximum-bound unit parse;
- representative `UnitValue` arithmetic;
- MCP initialize;
- compact tools/list;
- full tools/list;
- generated single-file startup for the candidate.

## F4. Generate three evidence files

Under `docs/performance/`, commit in `EVIDENCE_SHA`:

- `releases-4-6-baseline.json`;
- `releases-4-6-candidate.json`;
- `releases-4-6-comparison.json`.

The comparison must contain for every shared surface:

- baseline median;
- candidate median;
- absolute delta;
- percentage delta;
- memory delta where available;
- module-count delta where available;
- threshold result;
- explanation for any median time or memory regression above 15%.

The files currently named `baseline.json` and `single_file.json` and tied to `80083219` must be removed, renamed as non-closure exploratory data, or replaced. They cannot remain labeled as final baseline/candidate evidence.

## F5. Validate performance identities

The evidence validator must verify:

- baseline file SHA is the pinned historical commit;
- candidate file SHA equals `CANDIDATE_SHA`;
- comparison references hashes of the exact two source files;
- sample counts meet the minimum;
- environment identity matches between baseline and candidate except explicitly allowed fields;
- every >15% regression has a non-empty explanation;
- no file contains the plan SHA as candidate identity.

### Workstream F acceptance criteria

- [ ] Historical and candidate measurements use exact real commit identities.
- [ ] Measurements are made in a controlled matched environment.
- [ ] Sample counts are sufficient for a closure record.
- [ ] Comparison is machine-readable and complete.
- [ ] Significant regressions are explained rather than hidden.

---

# Workstream G — Replace marker-based evidence with verifiable run evidence

## G1. Remove invalid placeholder final sections

In `CANDIDATE_SHA`, remove the current `## Final Closure Evidence` sections that contain:

- plan SHA `800832196439558383d22300ef36870c997437da`;
- workflow ID `0000000000`;
- guessed single-lane totals.

Replace them with an unambiguous note such as:

> Final closure evidence is intentionally absent until the code candidate receives a successful workflow. Historical sections below/above are retained for audit history and are not current release status.

The ordinary evidence validator must support an unfinalized code-candidate state without accepting placeholders as final evidence.

## G2. Add one machine-readable final evidence authority

Create in `EVIDENCE_SHA`:

`docs/evidence/releases-4-6-final.json`

Required fields:

```json
{
  "schema_version": 1,
  "candidate_sha": "<40 hex>",
  "candidate_run_id": 123456789,
  "candidate_run_url": "https://github.com/eggstack/eggcalc/actions/runs/123456789",
  "evidence_parent_sha": "<same candidate sha>",
  "required_jobs": [],
  "test_lanes": [],
  "inventory_file": "docs/evidence/releases-4-6-inventory.json",
  "performance_baseline_file": "docs/performance/releases-4-6-baseline.json",
  "performance_candidate_file": "docs/performance/releases-4-6-candidate.json",
  "performance_comparison_file": "docs/performance/releases-4-6-comparison.json",
  "generation_commands": [],
  "generated_at_utc": "..."
}
```

The three Markdown release records must be generated from or validated against this manifest. They are presentation adapters, not independent authorities.

## G3. Capture actual workflow run/job data

Add a release-engineering script that consumes GitHub API/CLI output and writes a normalized snapshot, for example:

`docs/evidence/releases-4-6-ci-run.json`

It must include:

- run ID and URL;
- head SHA;
- event;
- status and conclusion;
- workflow name;
- run attempt;
- every required job name;
- job conclusion;
- matrix OS/Python identity where available;
- exact test totals extracted from a structured artifact or lane summary.

Preferred collection flow:

```bash
gh api repos/eggstack/eggcalc/actions/runs/$CANDIDATE_RUN_ID

gh api repos/eggstack/eggcalc/actions/runs/$CANDIDATE_RUN_ID/jobs --paginate
```

Do not rely on prose copied from the Actions UI.

## G4. Emit structured lane summaries in CI

Modify CI so each test lane writes a small JSON summary artifact containing:

- candidate SHA;
- OS runner;
- Python version;
- collected;
- passed;
- skipped;
- xfailed;
- failed;
- pytest exit code.

Use a deterministic pytest reporting hook or post-process JUnit XML. Do not scrape verbose console prose when a structured report is available.

Upload lane summaries with unique matrix names. The finalization script downloads/combines them for `test_lanes`.

Required lanes:

- Ubuntu Python 3.11, 3.12, 3.13, 3.14;
- macOS Python 3.11, 3.12;
- Windows Python 3.11, 3.12;
- package job;
- any dedicated closure/evidence job added by this pass.

## G5. Strengthen the evidence validator

The validator must reject:

- missing final manifest in strict final mode;
- all-zero or otherwise placeholder workflow IDs;
- candidate SHA equal to a known plan commit;
- candidate SHA not equal to `EVIDENCE_SHA^`;
- candidate run head SHA not equal to candidate SHA;
- run/job conclusion other than `success`;
- missing required matrix lanes;
- missing required jobs;
- lane totals that do not add up;
- failed lanes or jobs;
- approximate counts;
- performance files with mismatched identities/hashes;
- inventory file with mismatched candidate/artifact hashes;
- Markdown final sections diverging from the manifest;
- candidate-to-evidence diff outside the evidence allowlist;
- stale current-status claims that say the registry is built from legacy tables;
- historical Windows failures presented as current candidate results.

Provide modes:

```bash
python scripts/check_evidence_consistency.py --candidate-state
python scripts/check_evidence_consistency.py --final --candidate-sha "$CANDIDATE_SHA"
```

Candidate-state mode requires no placeholders and no false final claim. Final mode requires the complete manifest and proof set.

## G6. Rewrite Release 4–6 evidence status cleanly

Preserve old results only under clearly labeled `Historical Evidence` sections.

Add one generated/validated final section to each release record containing:

- exact candidate SHA;
- exact run ID/link;
- exact complete lane table;
- required job conclusions;
- inventory hash/result;
- baseline/candidate/comparison hashes;
- release-specific acceptance summary;
- explicit statement that historical failures/counts are not current.

Correct stale Release 6 statements, including:

- registry source is `UNIT_DEFINITIONS`, not `UNIT_BASE`/`UNIT_ALIASES`/temperature tables;
- parser has fixed non-recursive structural depth;
- current performance identities and counts replace approximate older claims.

### Workstream G acceptance criteria

- [ ] Placeholder final evidence is removed before the candidate run.
- [ ] One JSON manifest is the final evidence authority.
- [ ] Workflow/run/job data is captured from GitHub, not guessed.
- [ ] Every supported matrix lane has exact structured totals.
- [ ] Validator checks ancestry, diff allowlist, run identity, jobs, lanes, inventory, and performance.
- [ ] Markdown records match the manifest and clearly separate history from current status.

---

# Workstream H — CI wiring and finalization safety

## H1. Code-candidate CI

`CANDIDATE_SHA` CI must run:

```bash
ruff check eggcalc tests scripts build_single.py
black --check eggcalc tests scripts build_single.py
mypy eggcalc --ignore-missing-imports
mypy --config-file mypy-strict.ini \
  eggcalc/units.py eggcalc/mcp/server.py eggcalc/_protocol.py eggcalc/_version.py build_single.py
mypy --strict --follow-imports=normal --ignore-missing-imports tests/typing/consumer.py
python scripts/check_authority_boundaries.py
python scripts/verify_unit_baseline_fixture.py tests/fixtures/units/legacy-5a1bb34c.json
python build_single.py --validate
python build_single.py -o /tmp/eggcalc-a.py
python build_single.py -o /tmp/eggcalc-b.py
cmp /tmp/eggcalc-a.py /tmp/eggcalc-b.py
python scripts/check_evidence_consistency.py --candidate-state
pytest tests/ ...
```

The package job must:

- build wheel and sdist;
- run `twine check`;
- run release inventory using the built wheel and freshly generated single file;
- run installed-wheel strict consumer;
- run release-surface smoke tests.

## H2. Evidence-finalization validation

On `EVIDENCE_SHA`, CI must additionally run:

```bash
python scripts/check_evidence_consistency.py --final \
  --candidate-sha "$(git rev-parse HEAD^)"
```

It must verify the evidence-only diff allowlist before accepting final closure.

## H3. Avoid self-referential run IDs

Do not attempt to record the workflow run ID of `EVIDENCE_SHA` inside `EVIDENCE_SHA`.

The recorded run is the successful run for immutable `CANDIDATE_SHA`. The evidence commit’s own CI validates the already recorded candidate run snapshot and the evidence-only diff.

## H4. Failure behavior

If any candidate lane fails:

- do not create final evidence;
- fix code/tests/scripts;
- create a new candidate SHA;
- rerun the full matrix;
- discard measurements and artifacts from the invalid candidate.

If final evidence validation fails without code changes:

- correct evidence-only files in a new evidence commit whose parent relationship is still explicitly validated;
- if direct-parent strictness is lost, squash/recreate the evidence commit on the candidate rather than weakening the validator.

### Workstream H acceptance criteria

- [ ] Candidate CI validates code without requiring nonexistent final evidence.
- [ ] Final evidence CI requires the complete proof set.
- [ ] Package job uses the built wheel in inventory and strict-consumer checks.
- [ ] Evidence does not attempt to record its own future run ID.
- [ ] Failed candidates cannot be finalized.

---

# 4. File-by-file implementation map

## Production code

### `eggcalc/units.py`

- add normalized post-merge exponent validation;
- remove unreachable dynamic-depth state/branch;
- retain compatibility constant/documentation only if required;
- preserve all declaration/registry/generated-adapter behavior.

No other production module should require semantic changes.

## Tests

### `tests/test_final_unit_expression.py`

- replace nominal exact-bound tests with true exact-bound fixtures;
- add normalized duplicate exponent matrix;
- add real package/single-file JSON differential harness;
- remove tests that assert only process success while claiming parity.

### `tests/test_final_unit_authority.py`

- validate expanded fixture metadata;
- validate frozen exporter independence;
- compare complete fixture behavior;
- remove misleading test names/assertions that do not test `UNIT_DEFINITIONS` independence.

### `tests/test_release_inventory.py`

- build/mutate actual artifacts;
- rerun collector for each mutation;
- test isolated wheel/single-file identity;
- test capability/policy/public-symbol inventory.

### `tests/test_evidence_consistency.py`

- add candidate-state tests;
- add strict-final manifest tests;
- reject placeholders and plan SHAs;
- test ancestry and diff allowlist in temporary Git repositories;
- test run/job/lane/performance/inventory mismatch cases;
- test repository evidence only after finalization manifest exists.

### Add focused tests as needed

Suggested files:

- `tests/test_unit_baseline_fixture.py`;
- `tests/test_strict_consumer_contract.py`;
- `tests/test_evidence_finalization.py`.

## Scripts

### `scripts/export_unit_baseline.py`

- replace current self-oracle behavior with verification/reproduction coordination;
- or split into clearly named verifier/regenerator scripts.

### `tests/fixtures/units/exporters/export_legacy_5a1bb34c.py`

- add frozen historical exporter.

### `scripts/release_inventory.py`

- add explicit wheel and single-file artifact inputs;
- isolate subprocesses;
- collect expanded inventory and artifact hashes.

### `scripts/verify_wheel_consumer.py`

- invoke mypy with explicit `--strict --follow-imports=normal`;
- preserve source isolation.

### `scripts/measure_architecture_costs.py`

- derive commit identity from checkout;
- add warmup/sample controls and complete metadata;
- support normalized comparison generation.

### `scripts/check_evidence_consistency.py`

- add candidate/final modes;
- validate manifest, Git history, diff allowlist, run snapshot, jobs, lanes, performance, inventory, and Markdown parity.

### Suggested new scripts

- `scripts/compare_architecture_costs.py`;
- `scripts/collect_ci_evidence.py`;
- `scripts/finalize_release_evidence.py`;
- `scripts/verify_unit_baseline_fixture.py`.

## CI

### `.github/workflows/ci.yml`

- emit per-lane structured test summaries;
- use strict source-consumer command;
- keep package inventory/wheel consumer on actual built artifacts;
- use candidate-state evidence validation for ordinary code commits;
- use strict-final validation when final manifest exists.

## Documentation/evidence

### `docs/release_4_evidence.md`
### `docs/release_5_evidence.md`
### `docs/release_6_evidence.md`

- remove placeholder final sections in candidate commit;
- clearly label historical evidence;
- generate/validate final sections from manifest in evidence commit;
- correct stale architecture claims.

### `docs/evidence/releases-4-6-final.json`
### `docs/evidence/releases-4-6-ci-run.json`
### `docs/evidence/releases-4-6-inventory.json`

- add only in evidence finalization commit.

### `docs/performance/**`

- replace mislabeled plan-commit files with baseline/candidate/comparison artifacts tied to real identities.

---

# 5. Required verification commands

## Candidate checkout

Run from a clean checkout of `CANDIDATE_SHA`:

```bash
python -m pip install -e '.[dev]'

ruff check eggcalc tests scripts build_single.py
black --check eggcalc tests scripts build_single.py

mypy eggcalc --ignore-missing-imports
mypy --config-file mypy-strict.ini \
  eggcalc/units.py \
  eggcalc/mcp/server.py \
  eggcalc/_protocol.py \
  eggcalc/_version.py \
  build_single.py
mypy --strict --follow-imports=normal --ignore-missing-imports \
  tests/typing/consumer.py

python scripts/check_authority_boundaries.py
python scripts/verify_unit_baseline_fixture.py \
  tests/fixtures/units/legacy-5a1bb34c.json

python build_single.py --validate
python build_single.py -o /tmp/eggcalc-a.py
python build_single.py -o /tmp/eggcalc-b.py
cmp /tmp/eggcalc-a.py /tmp/eggcalc-b.py

python scripts/check_evidence_consistency.py --candidate-state

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
  --check
python scripts/verify_wheel_consumer.py dist/eggcalc-*.whl
python scripts/smoke_release_surfaces.py
```

Then push and require the complete GitHub Actions matrix to conclude successfully.

## Historical fixture reproduction

From a separate exact baseline checkout:

```bash
BASELINE_CHECKOUT=/path/to/eggcalc-5a1bb34c

test "$(git -C "$BASELINE_CHECKOUT" rev-parse HEAD)" = \
  "5a1bb34c9efa269ca6159217827f1742faa95d20"

PYTHONPATH="$BASELINE_CHECKOUT" \
python tests/fixtures/units/exporters/export_legacy_5a1bb34c.py \
  --output /tmp/legacy-5a1bb34c.json

python scripts/verify_unit_baseline_fixture.py \
  tests/fixtures/units/legacy-5a1bb34c.json \
  --regenerated /tmp/legacy-5a1bb34c.json
```

## Performance collection

Use separate worktrees on the same host:

```bash
python scripts/measure_architecture_costs.py \
  --label baseline \
  --warmups 5 \
  --samples 20 \
  --output /tmp/releases-4-6-baseline.json

python scripts/measure_architecture_costs.py \
  --label candidate \
  --warmups 5 \
  --samples 20 \
  --output /tmp/releases-4-6-candidate.json

python scripts/compare_architecture_costs.py \
  --baseline /tmp/releases-4-6-baseline.json \
  --candidate /tmp/releases-4-6-candidate.json \
  --output /tmp/releases-4-6-comparison.json
```

## Evidence finalization

After a green `CANDIDATE_RUN_ID`:

```bash
python scripts/collect_ci_evidence.py \
  --run-id "$CANDIDATE_RUN_ID" \
  --candidate-sha "$CANDIDATE_SHA" \
  --output /tmp/releases-4-6-ci-run.json

python scripts/finalize_release_evidence.py \
  --candidate-sha "$CANDIDATE_SHA" \
  --run-id "$CANDIDATE_RUN_ID" \
  --ci-run /tmp/releases-4-6-ci-run.json \
  --inventory /tmp/releases-4-6-inventory.json \
  --performance-baseline /tmp/releases-4-6-baseline.json \
  --performance-candidate /tmp/releases-4-6-candidate.json \
  --performance-comparison /tmp/releases-4-6-comparison.json

python scripts/check_evidence_consistency.py \
  --final \
  --candidate-sha "$CANDIDATE_SHA"
```

---

# 6. Recommended commit sequence

## Candidate implementation commits

1. `fix(units): enforce normalized expression exponent bounds`
2. `test(units): replace nominal parser and renderer boundary cases`
3. `test(single): add real package single-file unit differential harness`
4. `test(units): restore frozen historical baseline oracle`
5. `fix(inventory): inspect isolated wheel and generated artifacts`
6. `test(inventory): mutate real release artifacts`
7. `fix(types): enforce strict source and wheel consumer commands`
8. `fix(evidence): add candidate and final evidence validation modes`
9. `ci: emit structured lane summaries and verify release artifacts`
10. `docs(evidence): remove placeholder closure claims`

Squash or retain these as appropriate, but the final code candidate must be one immutable SHA before measurement/finalization.

## Evidence finalization commit

11. `docs(evidence): finalize releases 4-6 against candidate <short-sha>`

This commit must be evidence-only and directly parented by the green code candidate.

---

# 7. Stop and rollback conditions

Stop and do not finalize if any of the following is true:

- normalized duplicate exponents can exceed the configured bound;
- any exact-bound test exercises only the rejected side;
- package/single differential tests compare only return codes;
- fixture expected data is regenerated from current `UNIT_DEFINITIONS`;
- inventory subprocesses import from the source checkout;
- mutation tests alter only in-memory dictionaries;
- source or wheel consumer runs without explicit strict mode;
- performance candidate identity is the plan or evidence commit;
- baseline and candidate measurements use materially different environments without disclosure;
- workflow ID is missing, zero, guessed, or not tied to the candidate SHA;
- any required job/lane is absent or non-successful;
- evidence commit changes code/tests/scripts/workflow files;
- Release 6 still states that the registry is built from legacy adapters;
- historical failures are presented as current candidate failures;
- evidence validator passes a deliberately mutated run, lane, inventory, or performance identity.

When a code defect is found after candidate measurement, discard the candidate evidence, fix the defect, create a new candidate SHA, and rerun the complete protocol. Do not repin evidence around a changed code candidate.

---

# 8. Final binary closure checklist

## Correctness

- [ ] Duplicate factors cannot normalize beyond the exponent bound.
- [ ] Positive, negative, exact-bound, and cancellation cases are tested directly.
- [ ] Input, atom, exponent, digit, and canonical-output bounds test maximum accepted and first rejected values.
- [ ] Dynamic-depth claims are removed from the non-recursive parser.
- [ ] Package and freshly generated single-file unit behavior matches exactly for focused positive and negative cases.

## Historical oracle

- [ ] Frozen exporter runs against exact commit `5a1bb34c9efa269ca6159217827f1742faa95d20`.
- [ ] Frozen exporter does not reference current declaration APIs.
- [ ] Fixture metadata includes schema, source SHA, exporter path/hash, environment, and command.
- [ ] Ordinary tests compare every fixture field.
- [ ] Current declarations cannot regenerate expected values in ordinary verification.

## Artifacts and typing

- [ ] Inventory compares an installed wheel and isolated generated file.
- [ ] Artifact subprocesses do not use repository `PYTHONPATH`.
- [ ] Public symbol existence/types, capabilities, policies, units, CLI, protocol, and MCP surfaces are inventoried.
- [ ] Mutation tests modify artifacts and rerun the collector.
- [ ] Source consumer is explicitly strict.
- [ ] Copied wheel consumer is explicitly strict.
- [ ] Migrated modules use normal import resolution.

## Performance

- [ ] Historical baseline uses exact `5a1bb34c...` identity.
- [ ] Candidate measurements use exact frozen code candidate identity.
- [ ] Environment and sample counts satisfy the controlled protocol.
- [ ] Comparison file reports every delta.
- [ ] Every >15% regression is explained.
- [ ] No final performance file identifies `80083219` as the candidate.

## CI and evidence

- [ ] Placeholder closure sections are absent from the code candidate.
- [ ] Complete candidate matrix is green.
- [ ] Exact positive workflow run ID is recorded.
- [ ] Run head SHA equals candidate SHA.
- [ ] Every required job concludes success.
- [ ] Every required OS/Python lane has exact structured totals.
- [ ] Final JSON manifest is authoritative.
- [ ] Release 4–6 Markdown records match the manifest.
- [ ] Evidence commit directly follows candidate and changes evidence files only.
- [ ] Final validator checks ancestry, diff allowlist, CI, lane, inventory, and performance identities.
- [ ] Stale Release 6 unit-authority and parser-depth statements are corrected.

## Final release decision

Releases 4, 5, and 6 may be marked closed only when every checkbox above is satisfied and the evidence-only finalization commit passes strict final validation. A green code candidate without final evidence is a release candidate, not a closed release. Internally consistent placeholders, guessed counts, or prose claims are not release evidence.
