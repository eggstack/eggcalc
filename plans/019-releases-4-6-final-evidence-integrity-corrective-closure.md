# Releases 4–6 Final Evidence-Integrity Corrective Closure

Status: implementation handoff  
Repository: `eggstack/eggcalc`  
Baseline reviewed: `e7665cc13104e0bc2bee181711c1bd31e7bf7f4a`  
Depends on:

- `plans/017-releases-4-6-final-correctness-and-evidence-closure.md`
- `plans/018-releases-4-6-candidate-completion-and-evidence-finalization.md`

## 1. Purpose and current disposition

The production and verification implementation is now substantially complete. The repository has:

- the normalized duplicate-exponent correctness fix;
- exact parser and renderer boundary coverage;
- genuine scale overflow/underflow coverage;
- package/generated-file differential testing;
- a frozen historical unit exporter and immutable fixture verification;
- isolated wheel/generated-file inventory;
- explicit strict typed-consumer checks;
- structured CI lane summaries;
- controlled measurement tooling;
- a green cross-platform workflow for code commit `c903a6aeffea9070a987125642b2c92e0f6f3af6`.

However, the final evidence commit `e7665cc1` is not authoritative and must not be treated as release closure. Its committed records combine incompatible identities:

- `docs/evidence/releases-4-6-final.json` names `71dd343e0f9876d972434101e90bdb5f88fd29e6` as `candidate_sha`;
- the same manifest names `c903a6aeffea9070a987125642b2c92e0f6f3af6` as `workflow_head_sha`;
- the manifest names successful workflow `30365241754`;
- `docs/evidence/releases-4-6-ci-run.json` instead records failed workflow `30307774419` for candidate `71dd343e...` with both Windows lanes failing;
- the release Markdown names `c903a6ae...` as closure code but names failed workflow `30307774419` as closure evidence;
- wheel, sdist, and generated-file hashes are annotated as coming from failed run `30307774419`;
- the committed candidate performance file identifies `71dd343e...`, not `c903a6ae...`, and records only five samples;
- the final validator does not cross-link these identities and CI invokes its permissive auto-detection mode.

This plan is a narrow evidence-integrity correction. It does not reopen production architecture, unit semantics, MCP ownership, runtime-context behavior, public APIs, packaging design, or release functionality.

Releases 4, 5, and 6 remain open until this plan produces a new frozen code candidate, a successful workflow for that exact candidate, a directly parented evidence-only commit, and a successful post-evidence workflow.

---

## 2. Preserve completed implementation

The corrective pass must preserve all completed behavior, including:

- `RuntimeContext` as the active evaluator/configuration authority;
- server-owned MCP registry, configuration, profile, executor, and session state;
- fail-closed production dispatch and stable in-flight context capture;
- exact executor reservation accounting and bounded bookkeeping;
- `UNIT_DEFINITIONS` as the built-in unit declaration authority;
- explicit `UnitSpec.base_canonical` ownership;
- declaration-built immutable `UnitRegistry` and generated compatibility adapters;
- structural `UnitValue` arithmetic;
- affine-unit compound rejection;
- post-merge normalized exponent validation;
- bounded unit parsing, rendering, and bounded errors;
- exact package/generated-file behavior parity;
- frozen historical fixture architecture;
- installed-wheel/generated-file inventory isolation;
- deterministic `MODULE_MANIFEST`-based single-file construction;
- strict source and installed-wheel typed consumers;
- current Linux, macOS, and Windows Python matrix;
- existing public package, wheel, console, module, REPL, single-file, MCP, and typing surfaces.

No corrective task may change unit conversion values, aliases, syntax, MCP tools, protocol versions, evaluator behavior, public API names, supported platforms, or packaging backend unless a regression introduced by the evidence work directly prevents an acceptance criterion.

---

## 3. Non-goals

Do not:

- redesign the evidence schema beyond what is needed for unambiguous identity and provenance;
- add new release features;
- broaden strict typing to unrelated modules;
- optimize runtime performance speculatively;
- modify unit inventories or conversion semantics;
- add new CI platforms or Python versions;
- create a release tag or bump the package version;
- preserve the current invalid final evidence as an approved record;
- amend or repurpose `c903a6ae...` as the new candidate after validator or CI changes.

The old green run for `c903a6ae...` is useful diagnostic evidence only. Because this corrective pass changes validation scripts and CI behavior, a new candidate SHA and new complete workflow are mandatory.

---

# 4. Mandatory replacement protocol

## 4.1 Invalidate the current closure state

The first corrective code sequence must remove the repository from final-evidence state.

Before designating a new candidate:

- remove `docs/evidence/releases-4-6-final.json`;
- remove `docs/evidence/releases-4-6-ci-run.json`;
- remove `docs/evidence/releases-4-6-inventory.json`;
- remove or relocate all current closure performance files that identify `71dd343e...` or use only five samples;
- replace each Release 4–6 final section with an explicit statement that the prior evidence was invalidated due to cross-record identity inconsistency and that final evidence is pending a new candidate;
- ensure `check_evidence_consistency.py --candidate-state` rejects any retained final manifest, CI snapshot, final inventory, or current-candidate performance file.

Historical audit information may remain only when clearly labeled as superseded and excluded from validation. No stale file may use `APPROVED`, `closed`, or equivalent current-release language.

### Acceptance criteria

- candidate-state validation succeeds after invalid evidence is removed;
- no final manifest or final CI/inventory snapshot exists in the candidate tree;
- no release Markdown claims Releases 4–6 are closed;
- no current closure file names `30307774419`, `30365241754`, `71dd343e...`, or `c903a6ae...` as active final evidence;
- invalid files are deleted rather than silently ignored by the validator.

## 4.2 Produce a new frozen code candidate

After all script, test, workflow, and candidate-state cleanup changes are complete, designate the final code commit as `NEW_CANDIDATE_SHA`.

`NEW_CANDIDATE_SHA` must contain:

- strict evidence validator corrections;
- evidence collection/finalization tooling;
- CI invocation corrections;
- all associated tests;
- removal of invalid current evidence and performance records;
- no final evidence values and no closure claim.

Push `NEW_CANDIDATE_SHA` and obtain a complete successful workflow run `NEW_CANDIDATE_RUN_ID` whose head SHA is exactly `NEW_CANDIDATE_SHA`.

After the workflow starts, the candidate is immutable. Any source, test, script, workflow, configuration, packaging, build, or plan change requires a new candidate SHA and full rerun.

## 4.3 Produce a directly parented evidence-only commit

Create `NEW_EVIDENCE_SHA` with exactly one parent: `NEW_CANDIDATE_SHA`.

The diff may modify only:

- `docs/release_4_evidence.md`;
- `docs/release_5_evidence.md`;
- `docs/release_6_evidence.md`;
- `docs/evidence/**`;
- `docs/performance/**`.

The evidence commit must not modify:

- `eggcalc/**`;
- `tests/**`;
- `scripts/**`;
- `.github/**`;
- `build_single.py`;
- `pyproject.toml`;
- `mypy-strict.ini`;
- lock files;
- plans;
- packaging metadata.

Run the complete workflow again on `NEW_EVIDENCE_SHA`. Closure requires both the candidate workflow and post-evidence workflow to conclude successfully.

---

# 5. Workstream A — make the final manifest internally singular

`docs/evidence/releases-4-6-final.json` must become the sole authoritative final record. Every other committed evidence document is either a referenced immutable input or a generated view.

## A1. Required identity fields

The final manifest must contain exactly one value for each of:

- repository;
- schema version;
- release set;
- candidate SHA;
- candidate parent SHA;
- candidate workflow run ID;
- candidate workflow attempt;
- workflow head SHA;
- workflow event;
- workflow conclusion;
- evidence parent SHA;
- evidence commit identity strategy;
- post-evidence workflow run ID and conclusion, when recorded after the run through a non-self-referential mechanism or a second proof record;
- final decision.

The following equality invariants are mandatory:

```text
manifest.candidate_sha
  == manifest.workflow_head_sha
  == ci_snapshot.candidate_sha
  == ci_snapshot.workflow_head_sha
  == every release Markdown closure_code_sha
  == git rev-parse HEAD^
  == performance_candidate.commit_sha
  == inventory.candidate_sha
```

```text
manifest.candidate_workflow_run_id
  == ci_snapshot.candidate_workflow_run_id
  == every release Markdown closure_workflow_run_id
  == every lane summary workflow_run_id
  == every artifact-provenance run_id
```

No field may use a different historical candidate or run while being described as current closure evidence.

## A2. Candidate parent identity

The validator must resolve the candidate commit and verify:

- `manifest.candidate_parent_sha` equals the actual first parent of `manifest.candidate_sha`;
- the candidate is an ancestor of the evidence commit;
- the evidence commit parent is exactly the candidate;
- no merge commit is used for evidence finalization unless explicitly supported and tested; the preferred and required default is one parent.

## A3. Final decision rules

`final_decision` may equal `APPROVED` only when all validator stages succeed. The generator must refuse to emit `APPROVED` when:

- workflow conclusion is not `success`;
- any required job is missing, duplicated, skipped at the job level, cancelled, timed out, or failed;
- any required lane is missing or unsuccessful;
- candidate/workflow identities differ;
- performance identity differs;
- artifact provenance differs;
- inventory identity differs;
- evidence parentage or diff allowlist fails.

### Acceptance criteria

- changing any one candidate SHA causes final validation to fail;
- changing any one run ID causes final validation to fail;
- changing workflow head SHA causes final validation to fail;
- changing candidate parent SHA causes final validation to fail;
- a failed CI snapshot cannot coexist with `APPROVED`;
- the manifest contains no conflicting candidate or run identity anywhere in nested data.

---

# 6. Workstream B — make the CI snapshot an actual successful-run snapshot

## B1. Generate, do not hand-author

Add or complete `scripts/collect_ci_evidence.py` so the CI snapshot is generated from the actual GitHub Actions run and downloaded artifacts.

Required inputs:

```bash
python scripts/collect_ci_evidence.py \
  --repository eggstack/eggcalc \
  --run-id "$NEW_CANDIDATE_RUN_ID" \
  --expected-sha "$NEW_CANDIDATE_SHA" \
  --output /tmp/releases-4-6-ci-run.json
```

The collector must fail unless:

- run ID is positive;
- run exists;
- run head SHA equals the expected SHA;
- run conclusion is `success`;
- run attempt is recorded;
- the workflow event is permitted by policy;
- all expected jobs exist exactly once;
- every required job conclusion is `success`;
- all expected lane-summary artifacts exist exactly once;
- each lane summary belongs to the same run/head/job;
- lane totals are arithmetically valid;
- every lane has `failed=0` and `errors=0`.

The collector must never transform a failed run into a successful snapshot based on a later run note.

## B2. Exact job and lane policy

Define the expected job/lane set in one code authority shared by collection and validation.

Required matrix lanes remain:

- Ubuntu: Python 3.11, 3.12, 3.13, 3.14;
- macOS: Python 3.11, 3.12;
- Windows: Python 3.11, 3.12.

Required package/static responsibilities must be explicitly represented through job or structured-step summaries, including:

- package build;
- Twine validation;
- installed-wheel smoke tests;
- installed-wheel strict consumer;
- isolated release inventory;
- artifact hashes;
- ordinary Ruff;
- strict Ruff;
- Black;
- ordinary mypy;
- migrated-module strict mypy;
- source-consumer strict mypy;
- authority-boundary validation;
- immutable historical fixture validation;
- deterministic build;
- focused MCP closure;
- focused unit closure;
- full pytest lane execution;
- release-surface smoke tests.

Conditionally skipped steps are acceptable only when the same responsibility is intentionally assigned to a specific documented lane. Required jobs themselves may not be skipped.

## B3. Snapshot schema

The snapshot must include:

- schema version;
- repository;
- candidate SHA;
- run ID and attempt;
- workflow name/path/event;
- workflow head SHA;
- status and conclusion;
- created/updated timestamps;
- exact jobs with IDs and conclusions;
- exact lane summaries;
- structured static-check summaries;
- artifact names and IDs;
- source URL or API provenance metadata.

### Acceptance criteria

- snapshot generation against failed run `30307774419` fails;
- snapshot generation with expected SHA `71dd343e...` against the green `c903a6ae...` run fails;
- snapshot generation against a green run with one omitted lane fails;
- manually changing a job conclusion causes final validation to fail;
- manually changing a lane run ID or head SHA causes final validation to fail;
- duplicate jobs or lanes fail;
- the committed snapshot records only the new successful candidate run.

---

# 7. Workstream C — artifact provenance must belong to the declared run

The current manifest accepts built-artifact hashes based on free-form notes and skips verification when a note contains `Built during`. Remove this behavior.

## C1. Structured artifact provenance

Each built artifact record must include structured fields:

```json
{
  "kind": "wheel",
  "name": "eggcalc-1.1.6-py3-none-any.whl",
  "sha256": "...",
  "workflow_run_id": 123,
  "workflow_attempt": 1,
  "workflow_head_sha": "<NEW_CANDIDATE_SHA>",
  "artifact_id": 456,
  "artifact_bundle_name": "release-artifacts",
  "source_summary_path": "artifact-hashes.json"
}
```

Do not encode provenance in `note` text. Notes may be retained as non-authoritative commentary but may never alter validation behavior.

## C2. Candidate workflow artifact bundle

The package job must upload a candidate artifact bundle containing:

- wheel;
- sdist;
- generated single file;
- `artifact-hashes.json` computed in the same job after all artifacts are built;
- canonical release inventory;
- wheel-consumer result;
- package/static summary.

`artifact-hashes.json` must include the current `${{ github.run_id }}`, `${{ github.run_attempt }}`, and `${{ github.sha }}` values.

The finalization collector must download the exact artifact bundle, recompute SHA-256 values for wheel, sdist, and generated file, and compare them with `artifact-hashes.json` before writing committed evidence.

## C3. Inventory provenance

`docs/evidence/releases-4-6-inventory.json` must include:

- candidate SHA;
- workflow run ID and attempt;
- wheel hash;
- generated-file hash;
- collector/exporter path and hash;
- inventory schema version;
- package/single result;
- allowed differences;
- complete normalized inventory.

The final validator must verify that inventory artifact hashes equal the manifest artifact hashes and that candidate/run identities equal the CI snapshot.

### Acceptance criteria

- no validator branch skips hash verification based on note text;
- a 64-character arbitrary string is not sufficient proof of a built artifact;
- changing the artifact run ID fails;
- changing the wheel or generated-file hash in either manifest or inventory fails;
- an inventory produced from a different candidate fails;
- missing artifact ID or bundle name fails;
- all final artifact records originate from `NEW_CANDIDATE_RUN_ID`.

---

# 8. Workstream D — performance evidence must measure the exact new candidate

The current `candidate-71dd343.json` and related comparison are invalid final evidence. They must not be reused.

## D1. Candidate-state cleanup

Delete or relocate as explicitly historical and non-closure:

- `docs/performance/candidate-71dd343.json`;
- the current comparison JSON/Markdown derived from that file;
- any baseline file that does not satisfy the new controlled protocol.

Candidate-state validation must reject closure performance files that claim to represent the current candidate before the candidate exists and is frozen.

## D2. Controlled remeasurement

After `NEW_CANDIDATE_SHA` receives a green workflow, measure:

- baseline commit `5a1bb34c9efa269ca6159217827f1742faa95d20`;
- exact `NEW_CANDIDATE_SHA`.

Use:

- the same physical/virtual host;
- the same Python executable and version;
- the same OS and architecture;
- identical environment variables;
- at least 5 warmups;
- at least 15 recorded samples per timing metric;
- clean worktrees;
- exact expected-SHA checks;
- raw samples and summary statistics.

Required candidate file naming:

```text
docs/performance/candidate-<NEW_CANDIDATE_SHORT_SHA>.json
```

The internal `commit_sha` must be the full new candidate SHA. File names do not establish identity.

## D3. Comparison and thresholds

Generate comparison JSON and Markdown covering every common required metric. Record:

- baseline and candidate full SHAs;
- environment identity;
- absolute and percentage deltas;
- sample and warmup counts;
- threshold result;
- explicit explanation for every stable regression greater than 15%;
- import-boundary module counts.

Performance files are added only in the evidence-only commit.

### Acceptance criteria

- final validation rejects sample count below 15;
- final validation rejects warmup count below 5;
- candidate performance SHA must equal manifest candidate SHA;
- comparison candidate SHA must equal manifest candidate SHA;
- baseline SHA must equal exact `5a1bb34c...`;
- baseline and candidate environments must match or closure fails;
- current five-sample `71dd343e...` data is absent from active evidence;
- every stable regression over 15% is explained or blocks closure.

---

# 9. Workstream E — final validator must fail closed

## E1. Remove permissive final auto-detection from CI

CI must not use:

```bash
python scripts/check_evidence_consistency.py
```

for final closure.

Use explicit modes:

Candidate tree:

```bash
python scripts/check_evidence_consistency.py --candidate-state
```

Evidence tree:

```bash
python scripts/check_evidence_consistency.py \
  --final \
  --candidate-sha "$(git rev-parse HEAD^)"
```

An equivalent cross-platform Python wrapper is acceptable. The validator itself must independently derive `HEAD` and `HEAD^`; the CLI argument is an additional assertion, not the source of truth.

The generic `validate_documents()` compatibility entry point may remain for external callers only if it cannot return success for contradictory final evidence. CI must never use it.

## E2. Cross-file validation

`--final` must load and cross-check:

- final manifest;
- CI run snapshot;
- final inventory;
- baseline performance file;
- candidate performance file;
- performance comparison;
- Release 4, 5, and 6 final sections;
- Git commit ancestry and diff;
- referenced fixture/exporter files and hashes.

It must verify all equality invariants in Workstream A.

## E3. Workflow validation

The validator must reject unless:

- CI snapshot conclusion is `success`;
- manifest workflow conclusion is `success`;
- all required jobs are successful;
- every configured lane exists and succeeds;
- all lane run IDs/head SHAs match;
- all lane totals add up;
- failed and errors are zero;
- no final evidence references a failed superseded run.

## E4. Evidence diff and ancestry

Final validation must always verify, without optional bypass in production mode:

- current HEAD is the evidence commit;
- HEAD has exactly one parent;
- HEAD parent equals manifest candidate SHA;
- CLI candidate SHA equals manifest candidate SHA;
- evidence diff is within the allowlist;
- no code/test/script/workflow/build/packaging/plan file changed.

Test helpers may disable Git checks only through explicit dependency injection or a clearly test-only parameter. The production CLI must not silently skip ancestry because Git is unavailable; it must fail.

## E5. Hash validation

Validate hashes for:

- committed CI snapshot;
- committed inventory;
- baseline performance;
- candidate performance;
- performance comparison JSON/Markdown when listed;
- historical fixture;
- frozen exporter;
- evidence generation script where recorded.

Built artifact hashes are validated through the downloaded workflow bundle provenance described in Workstream C, not through note-based exemptions.

### Acceptance criteria

- the exact current contradictory evidence set fails final validation;
- final validation fails when invoked without final files;
- candidate-state validation fails when final files are present;
- Git ancestry cannot be skipped by omitting `--candidate-sha`;
- missing Git metadata in production final mode fails;
- changing one nested identity or hash fails;
- adding one non-allowlisted file to the evidence commit fails;
- failed CI snapshot plus successful manifest fails;
- green CI snapshot with mismatched candidate SHA fails.

---

# 10. Workstream F — generate synchronized Markdown from the manifest

Release final sections must be generated, not independently hand-maintained.

Add or complete `scripts/finalize_release_evidence.py` so it:

1. validates all input snapshots and performance files before writing;
2. creates the authoritative manifest;
3. creates or copies the canonical CI snapshot and inventory;
4. generates Release 4, 5, and 6 final sections from the same in-memory manifest;
5. writes deterministic JSON and Markdown;
6. refuses to write `APPROVED` when any required field is missing or inconsistent.

Every release final section must contain:

- exact new candidate SHA;
- exact new candidate workflow run ID and attempt;
- evidence parent statement;
- complete exact lane totals;
- required job/check results;
- artifact hashes and provenance run;
- inventory path/hash;
- historical fixture source/exporter identity;
- baseline/candidate/comparison performance identities;
- explicit evidence-only commit statement;
- release decision.

### Acceptance criteria

- all three release final sections are byte-identical for shared closure data except release-specific contextual prose;
- changing Markdown without changing the manifest fails;
- changing the manifest without regenerating Markdown fails;
- no section names the failed run `30307774419`;
- no section names a candidate other than `NEW_CANDIDATE_SHA`;
- no approximate counts or generic “all tests passed” substitutes occur.

---

# 11. Workstream G — test the contradictions that escaped

Expand `tests/test_evidence_consistency.py` with explicit regressions for the current failure mode.

## Required identity-mismatch tests

1. manifest candidate `A`, workflow head `B` fails;
2. manifest candidate `A`, CI-snapshot candidate `B` fails;
3. manifest run `R1`, CI-snapshot run `R2` fails;
4. Markdown run differs from manifest run fails;
5. performance candidate differs from manifest candidate fails;
6. inventory candidate differs from manifest candidate fails;
7. artifact provenance run differs from manifest run fails;
8. CI snapshot conclusion `failure` with manifest conclusion `success` fails;
9. one Windows lane failure with all Markdown lanes shown successful fails;
10. failed superseded run referenced anywhere in active final evidence fails.

## Required provenance/hash tests

- arbitrary 64-character artifact hash without workflow provenance fails;
- note text cannot suppress validation;
- changed wheel hash fails;
- changed generated-file hash fails;
- changed inventory hash fails;
- changed performance hash fails;
- missing artifact ID fails;
- duplicate artifact records fail.

## Required Git tests

- evidence HEAD parent differs from candidate fails;
- evidence commit has code change fails;
- evidence commit changes a plan fails;
- merge evidence commit fails unless explicitly supported;
- final mode outside a Git checkout fails;
- CLI candidate differs from derived parent fails.

## Required performance tests

- candidate file with five samples fails;
- warmups below five fail;
- wrong candidate SHA fails;
- wrong baseline SHA fails;
- environment mismatch fails;
- unexplained >15% regression fails.

### Acceptance criteria

- a fixture reproducing the exact `e7665cc1` contradictions fails with multiple specific diagnostics;
- no test passes solely because values are internally well-formed strings;
- every negative test identifies the violated invariant;
- final happy-path fixture contains one candidate, one run, one successful workflow, and exact matching provenance throughout.

---

# 12. Workstream H — CI candidate and evidence gates

Update `.github/workflows/ci.yml` so evidence state is selected deterministically.

## H1. Candidate state

When no final manifest exists:

- run explicit `--candidate-state`;
- fail if final CI snapshot or inventory exists;
- fail if active closure performance files exist;
- fail if release docs claim approval;
- continue all existing correctness, typing, matrix, packaging, inventory, and artifact-summary checks.

## H2. Evidence state

When final manifest exists:

- run explicit strict final validation on Ubuntu/Python 3.12 or another single authoritative validation lane;
- derive expected candidate from `HEAD^`;
- require all final files;
- run the ordinary full matrix and package job unchanged;
- upload post-evidence validation output;
- do not mark final validation advisory;
- do not use `continue-on-error`.

## H3. Candidate artifact completeness

The new candidate workflow must upload:

- all eight lane summaries;
- static/type/authority summaries;
- wheel, sdist, generated file, and hash manifest;
- isolated inventory;
- wheel-consumer result;
- package job summary.

### Acceptance criteria

- candidate workflow fails with final evidence present;
- evidence workflow fails with any final file missing;
- evidence workflow fails on identity mismatch before approving closure;
- candidate and evidence workflows both run the full supported matrix;
- final validation output is visible as a required successful step;
- no required artifact upload is skipped on a successful candidate run.

---

# 13. Required execution sequence

Use the following sequence. Intermediate commits may be combined, but the final candidate/evidence boundary must remain exact.

1. `docs(evidence): invalidate contradictory releases 4-6 closure records`
   - remove current final manifest, CI snapshot, inventory, and invalid performance evidence;
   - restore explicit pending-evidence sections.

2. `fix(evidence): enforce singular candidate and workflow identities`
   - implement manifest/snapshot/Markdown cross-validation.

3. `fix(evidence): verify successful workflow jobs and lane provenance`
   - add collector and strict snapshot validation.

4. `fix(evidence): require structured artifact provenance`
   - remove note-based hash exemptions.

5. `fix(evidence): validate performance candidate and sample protocol`
   - enforce SHA, environment, warmup, and sample constraints.

6. `test(evidence): cover mixed candidate run artifact and performance identities`
   - add all current-regression negative cases.

7. `ci(evidence): use explicit candidate and strict final validation modes`
   - remove permissive CI invocation.

8. `fix(evidence): generate synchronized final records from one manifest`
   - complete deterministic finalization tooling.

9. Resolve any candidate CI failures without adding final evidence.

10. Designate the final code commit as `NEW_CANDIDATE_SHA`, push it, and obtain green `NEW_CANDIDATE_RUN_ID`.

11. Collect exact workflow artifacts and remeasure baseline/new candidate using the controlled protocol.

12. `docs(evidence): finalize releases 4-6 against candidate <new-short-sha>`
   - evidence-only direct child of the candidate.

13. Run the full post-evidence workflow and require success.

Do not reuse the old evidence commit as Phase 2. Do not amend the new candidate after its successful workflow starts.

---

# 14. Required verification commands

## 14.1 New candidate checkout

Run from a clean checkout of `NEW_CANDIDATE_SHA`:

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

pytest -q tests/test_evidence_consistency.py
pytest -q tests/test_final_unit_expression.py
pytest -q tests/test_final_unit_authority.py
pytest -q tests/test_release_inventory.py
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

Then push the exact candidate and require all jobs and all eight lanes to succeed.

## 14.2 Collect successful candidate evidence

```bash
python scripts/collect_ci_evidence.py \
  --repository eggstack/eggcalc \
  --run-id "$NEW_CANDIDATE_RUN_ID" \
  --expected-sha "$NEW_CANDIDATE_SHA" \
  --download-artifacts /tmp/eggcalc-candidate-artifacts \
  --output /tmp/releases-4-6-ci-run.json
```

Recompute and verify candidate artifact hashes from the downloaded bundle before continuing.

## 14.3 Controlled performance measurement

```bash
python scripts/measure_architecture_costs.py \
  --expected-sha 5a1bb34c9efa269ca6159217827f1742faa95d20 \
  --label baseline \
  --warmups 5 \
  --samples 15 \
  --output /tmp/eggcalc-baseline.json

python scripts/measure_architecture_costs.py \
  --expected-sha "$NEW_CANDIDATE_SHA" \
  --label candidate \
  --warmups 5 \
  --samples 15 \
  --single-file /tmp/eggcalc-candidate-artifacts/eggcalc.py \
  --output /tmp/eggcalc-candidate.json

python scripts/compare_architecture_costs.py \
  --baseline /tmp/eggcalc-baseline.json \
  --candidate /tmp/eggcalc-candidate.json \
  --json-output /tmp/eggcalc-comparison.json \
  --markdown-output /tmp/eggcalc-comparison.md
```

## 14.4 Finalization

```bash
python scripts/finalize_release_evidence.py \
  --candidate-sha "$NEW_CANDIDATE_SHA" \
  --candidate-run /tmp/releases-4-6-ci-run.json \
  --inventory /tmp/eggcalc-candidate-artifacts/releases-4-6-inventory.json \
  --artifact-hashes /tmp/eggcalc-candidate-artifacts/artifact-hashes.json \
  --baseline-performance /tmp/eggcalc-baseline.json \
  --candidate-performance /tmp/eggcalc-candidate.json \
  --performance-comparison /tmp/eggcalc-comparison.json

python scripts/check_evidence_consistency.py \
  --final \
  --candidate-sha "$NEW_CANDIDATE_SHA"
```

Before committing:

```bash
test "$(git rev-parse HEAD)" = "$NEW_CANDIDATE_SHA"
git status --short
```

Commit only evidence allowlist files. After committing:

```bash
test "$(git rev-parse HEAD^)" = "$NEW_CANDIDATE_SHA"
python scripts/check_evidence_consistency.py \
  --final \
  --candidate-sha "$NEW_CANDIDATE_SHA"
git diff --name-only HEAD^ HEAD
```

Finally, push `NEW_EVIDENCE_SHA` and require the complete post-evidence workflow to succeed.

---

# 15. Stop conditions

Stop and do not approve closure if any of the following is true:

- the final manifest contains more than one active candidate SHA;
- workflow head differs from candidate SHA;
- CI snapshot candidate or run differs from the manifest;
- release Markdown differs from the manifest;
- a failed run is referenced as current evidence;
- any Windows, macOS, or Linux lane is absent or unsuccessful;
- artifact hashes originate from a different run;
- artifact validation is skipped based on note text;
- inventory candidate/run/hash differs from manifest provenance;
- candidate performance file identifies another commit;
- performance measurements use fewer than 15 samples or fewer than 5 warmups;
- baseline/candidate environments differ materially;
- final CI uses permissive auto-detection instead of strict final mode;
- final validator can skip Git ancestry in production mode;
- evidence commit modifies a non-allowlisted file;
- candidate changes after its green run;
- post-evidence workflow is absent or unsuccessful;
- any generated final record requires hand-edited identity repair.

If a validator, collection, CI, or measurement defect is found after the new candidate run begins, discard the candidate evidence, fix the defect, produce a new candidate SHA, and rerun the complete protocol.

---

# 16. Final binary acceptance checklist

## Candidate state

- [ ] Current contradictory final manifest is removed.
- [ ] Current failed CI snapshot is removed.
- [ ] Current final inventory is removed.
- [ ] Five-sample `71dd343e...` candidate performance evidence is removed from active closure state.
- [ ] Release docs state final evidence is pending.
- [ ] Candidate-state validator passes.
- [ ] Candidate-state validator rejects premature final files.

## Validator correctness

- [ ] Manifest candidate equals workflow head.
- [ ] Manifest candidate equals CI snapshot candidate/head.
- [ ] Manifest run equals CI snapshot run.
- [ ] Manifest identities equal all release Markdown identities.
- [ ] Candidate equals evidence parent.
- [ ] Candidate parent equals actual candidate parent.
- [ ] CI snapshot conclusion must be success.
- [ ] Required jobs and lanes are unique and successful.
- [ ] Artifact provenance candidate/run equals manifest.
- [ ] Inventory candidate/run/hashes equal manifest.
- [ ] Performance candidate equals manifest.
- [ ] Performance protocol constraints are enforced.
- [ ] Evidence diff allowlist and Git ancestry always run in production final mode.
- [ ] Note text cannot bypass hash verification.

## Tests

- [ ] Exact current mixed-identity fixture fails.
- [ ] Candidate/head mismatch fails.
- [ ] Manifest/snapshot run mismatch fails.
- [ ] Failed snapshot with successful manifest fails.
- [ ] Windows failure masked by Markdown success fails.
- [ ] Artifact run/hash mismatch fails.
- [ ] Inventory candidate/hash mismatch fails.
- [ ] Performance candidate/sample mismatch fails.
- [ ] Non-allowlisted evidence change fails.
- [ ] Final happy path passes with one exact identity set.

## New candidate

- [ ] All corrective code, tests, scripts, and CI changes are committed before candidate designation.
- [ ] No final evidence exists in `NEW_CANDIDATE_SHA`.
- [ ] Candidate workflow head equals `NEW_CANDIDATE_SHA`.
- [ ] Candidate workflow conclusion is success.
- [ ] Package job succeeds.
- [ ] All eight matrix lanes succeed.
- [ ] Exact structured summaries are uploaded.
- [ ] Artifact bundle contains wheel, sdist, generated file, hashes, inventory, and consumer result.
- [ ] Candidate remains immutable after workflow start.

## New evidence

- [ ] CI snapshot is generated from `NEW_CANDIDATE_RUN_ID`.
- [ ] Snapshot contains no historical failed-run identities.
- [ ] Artifact hashes are recomputed from downloaded candidate artifacts.
- [ ] Inventory is the exact candidate workflow inventory.
- [ ] Baseline and candidate performance are remeasured under the controlled protocol.
- [ ] Candidate performance records at least 15 samples per timing metric.
- [ ] Final manifest contains one candidate and one candidate run.
- [ ] Release 4–6 Markdown is generated from the manifest.
- [ ] Evidence commit directly follows candidate.
- [ ] Evidence commit modifies only allowlisted evidence/performance files.
- [ ] Strict final validator passes on the evidence commit.
- [ ] Complete post-evidence workflow succeeds.

## Final decision

Releases 4, 5, and 6 may be marked closed only when every checkbox above is satisfied. The existence of a green historical candidate run is not sufficient. Closure requires one new frozen candidate, one successful workflow for that exact candidate, one internally singular and provenance-complete evidence set, one directly parented evidence-only commit, and one successful post-evidence workflow.
