# CI, Verification, and Manual PyPI Release Simplification

Status: implementation handoff  
Repository: `eggstack/eggcalc`  
Baseline reviewed: `4f9ce113d5a47d1fdfa0a4b52a803091332ddfa9`  
Date: 2026-07-28  
Supersedes as active policy: the release-evidence and CI-proof machinery introduced or expanded by plans 017–019

## 1. Purpose

`eggcalc` currently applies a release-verification apparatus that is disproportionate to the project and materially impedes iteration. Routine pull requests and pushes execute a large cross-platform matrix, repeat the full test suite, repeat static checks, generate CI-specific summary artifacts, construct release inventories and hashes, and enforce a bespoke Releases 4–6 evidence state machine.

The repository must return to a simpler operating model:

- application correctness remains protected by the full functional test suite;
- required CI runs once on one canonical environment;
- compatibility testing is narrow, optional, and manually dispatched;
- local Make targets are the authoritative interface for development, CI, package validation, and release preparation;
- PyPI publication is an explicit maintainer action;
- GitHub Actions never publishes to PyPI and never creates a GitHub Release;
- pushing a version tag has no automated publishing or release side effect;
- historical release evidence may remain as archived documentation, but it is not executable policy and does not participate in routine verification;
- verification must test the product, not continuously prove the integrity of previous verification records.

This is intentionally a reductive plan. Completion is measured partly by the amount of orchestration, evidence code, duplicate execution, and release coupling removed.

## 2. Governing decision

The maintainer has explicitly selected the following release policy:

> Releases are prepared and published manually to PyPI. GitHub CI is for current-code correctness only. GitHub Actions does not determine release cadence, publish distributions, create releases, or validate historical release evidence.

This policy is authoritative even where it conflicts with older release evidence documents, plans, comments, Make targets, agent instructions, or workflow assumptions.

The implementation agent must not preserve obsolete machinery merely because earlier plans described it as mandatory. Plans 017–019 are historical records of a superseded process, not constraints on this simplification pass.

## 3. Current problems to correct

### 3.1 Required CI repeats the same expensive work

The current `.github/workflows/ci.yml` contains:

- Ubuntu Python 3.11, 3.12, 3.13, and 3.14 lanes;
- macOS Python 3.11 and 3.12 lanes;
- Windows Python 3.11 and 3.12 lanes;
- a separate package job;
- full test-suite execution on all eight test lanes;
- repeated single-file builds on all lanes;
- repeated lint, format, and generated-document checks across Ubuntu lanes;
- repeated coverage execution on non-Windows lanes;
- separate focused closure suites followed by the full suite containing those tests;
- lane-summary and lint-summary generation after the primary checks;
- multiple artifact uploads used only by release-evidence machinery.

This creates long feedback cycles and makes CI failures harder to interpret.

### 3.2 CI embeds historical release-evidence policy

Routine CI currently invokes `scripts/check_evidence_consistency.py` and switches between candidate and final evidence states based on committed files. That validator enforces historical Release 4–6 identities, Git ancestry, workflow identities, lane counts, artifact provenance, hashes, performance records, and evidence-only commit allowlists.

This means a normal application change can fail because a historical evidence record, performance snapshot, workflow ID, or release document is in the wrong state. That coupling must be removed completely.

### 3.3 The evidence system has become a maintenance subsystem

The repository contains specialized scripts and tests for:

- collecting GitHub workflow evidence;
- converting JUnit XML to lane summaries;
- constructing release inventories;
- calculating and reconciling artifact hashes;
- finalizing synchronized release evidence;
- validating cross-record candidate, run, artifact, and performance identity;
- testing the evidence validator and its Git-dependent behavior.

Recent commits have needed to fix Windows paths, newline-normalized hashes, leaked validator globals, Git ancestry mocks, mismatched workflow identities, and CI-only environmental behavior. These are defects in the verification apparatus rather than the product.

### 3.4 Release automation conflicts with manual ownership

`.github/workflows/release.yml` automatically runs for `v*` tags, builds distributions, uploads workflow artifacts, and creates a GitHub Release. This conflicts with manual release cadence and grants write permission to automation that is not required.

The same workflow also exposes `workflow_dispatch` while deriving a release version from `GITHUB_REF_NAME` as though every run were tag-triggered, making its manual path internally inconsistent.

### 3.5 Local and CI interfaces disagree

The Makefile, `CONTRIBUTING.md`, `AGENTS.md`, pre-commit hooks, and GitHub Actions describe overlapping but different verification contracts. A contributor cannot infer the required checks from one canonical local command.

`make dev` also installs pre-commit and modifies the developer's Git hook configuration automatically. The pre-commit configuration runs mypy with `types-all`, which is expensive and unnecessary for every commit.

## 4. Target state

At completion, the repository must have the following verification architecture.

### 4.1 One required workflow

`.github/workflows/ci.yml` is the only automatically triggered workflow required for correctness.

It runs on:

- `pull_request` targeting `main`;
- `push` to `main`;
- optional `workflow_dispatch` for rerunning the same canonical job.

It contains exactly one required job on:

- `ubuntu-latest`;
- Python 3.11, the declared minimum supported interpreter.

The job installs development and release-check dependencies and invokes repository-owned Make targets. It does not reproduce the commands independently in YAML beyond setup and one or two target invocations.

The full test suite executes exactly once per workflow run.

### 4.2 Optional compatibility workflow

A second workflow is permitted only if it is manually dispatched and clearly non-required, for example `.github/workflows/compatibility.yml`.

The preferred minimal compatibility matrix is:

- `windows-latest`, Python 3.11;
- `ubuntu-latest`, Python 3.14.

This provides coverage for the two most meaningful compatibility boundaries:

- Windows path, executable, temporary-directory, and newline behavior;
- the newest declared Python version.

The compatibility workflow must:

- use `workflow_dispatch` only;
- have read-only permissions;
- run a concise compatibility target or the full tests once per selected lane;
- produce no release evidence;
- upload no artifacts unless a human has a concrete debugging need;
- not be a branch-protection requirement;
- not publish or create releases.

macOS is not required in hosted CI because the package is pure Python and the maintainer's normal development environment already supplies macOS coverage. A future real macOS-specific defect may justify a targeted regression test, not permanent matrix expansion by default.

If the implementation agent determines that even the optional workflow adds no present value, it may omit it. Required CI must remain one job regardless.

### 4.3 Canonical local command tiers

The Makefile must define the repository's verification contract. The intended tiers are:

#### Fast development

```bash
make test
make lint
make format
make typecheck
```

These targets are individually invocable and do not install hooks or build release artifacts.

#### Canonical correctness

```bash
make check
```

`make check` must run, once each:

1. ordinary Ruff lint;
2. Black format check;
3. ordinary package mypy;
4. strict typed external-consumer check, if retained;
5. generated MCP documentation drift check;
6. `build_single.py --validate`;
7. the complete pytest suite.

It must not:

- run coverage;
- run historical release-evidence validation;
- run a second special Ruff policy over selected files;
- run the same tests through focused closure suites first;
- generate workflow summaries;
- calculate artifact hashes;
- inspect Git ancestry;
- require GitHub access.

#### Package validation

```bash
make package-check
```

`make package-check` must:

1. clean old build outputs;
2. build wheel and sdist with `python -m build`;
3. run `python -m twine check dist/*`;
4. validate the generated single-file build;
5. install the wheel in a clean temporary virtual environment outside the repository;
6. unset or exclude repository `PYTHONPATH` during the installed-wheel probe;
7. smoke-test the installed package API, console entry point, unit conversion, and MCP startup/tool call;
8. smoke-test the generated single-file CLI and MCP surface.

It must not generate inventories, evidence manifests, workflow-linked hashes, or performance comparisons.

#### Release preparation

```bash
make release-check
```

`make release-check` is exactly:

- `make check`;
- followed by `make package-check`.

It must be network-free except for dependency installation performed before the target. It must not publish anything.

#### Publication

```bash
make publish
```

`make publish` is an explicit maintainer action that uploads already validated distributions with Twine. It must never be called by GitHub Actions.

The implementation may choose either of these safe designs:

1. `publish` depends on `release-check`, ensuring a fresh rebuild immediately before upload; or
2. `publish` refuses to run unless `dist/` exists and documentation instructs the maintainer to run `make release-check` immediately beforehand.

Design 1 is preferred because it minimizes stale-artifact risk.

The command should remain visibly consequential. Do not hide it behind a generic `release` target that also tags, pushes, or creates GitHub resources.

### 4.4 Manual PyPI release procedure

Add `docs/releasing.md` with the authoritative process:

1. choose the version and update `eggcalc/_version.py`;
2. update `CHANGELOG.md`;
3. commit the release metadata;
4. ensure the working tree is clean;
5. run `make release-check`;
6. inspect `dist/` and confirm filenames and version;
7. create the local version tag on the exact checked commit;
8. run `make publish` or `python -m twine upload dist/*`;
9. push `main` and the tag manually;
10. optionally create a GitHub Release manually.

The document must state explicitly:

- PyPI versions are immutable;
- a failed or incorrect publication requires a new version number;
- GitHub Actions does not publish;
- tag pushes do not trigger publication or GitHub Release creation;
- TestPyPI is optional and manual, not a required release gate;
- credentials are supplied through normal Twine/PyPI mechanisms and are never stored in repository files.

No release step may depend on a CI run ID, artifact ID, candidate SHA record, evidence-only commit, performance baseline, or generated closure manifest.

## 5. Scope

### 5.1 In scope

The implementation must review and modify as required:

- `.github/workflows/ci.yml`;
- `.github/workflows/release.yml`;
- optional new `.github/workflows/compatibility.yml`;
- `Makefile`;
- `pyproject.toml` development/release dependencies;
- `.pre-commit-config.yaml`;
- `CONTRIBUTING.md`;
- `AGENTS.md`;
- `AGENTS.override.md` where it contains stale verification claims;
- `docs/releasing.md`;
- historical release evidence documentation and its active-policy references;
- evidence-only scripts;
- CI summary scripts;
- release inventory/hash machinery that has no remaining product-level consumer;
- evidence-specific tests;
- package and smoke-test scripts needed to provide a small replacement;
- branch-protection documentation or maintainer notes if required check names change.

### 5.2 Product behavior to preserve

The pass must preserve:

- calculator evaluation behavior;
- natural-language normalization;
- unit parsing and conversion semantics;
- CLI behavior and output format;
- Python package public API;
- typed consumer compatibility;
- MCP protocol behavior, tools, profiles, and resource limits;
- generated single-file functionality;
- supported Python declaration `>=3.11` through 3.14;
- wheel and sdist buildability;
- `py.typed` inclusion;
- existing functional regression tests unless a test exists solely to enforce deleted verification machinery.

### 5.3 Non-goals

Do not:

- redesign evaluator, unit, exact-tool, or MCP architecture;
- reduce application test coverage merely to make CI faster;
- remove tests because they are numerous when they protect actual behavior;
- introduce a new CI framework, task runner, release service, or third-party publishing action;
- add automated PyPI trusted publishing;
- add GitHub release automation under a different workflow name;
- add changelog generation automation;
- add coverage thresholds;
- add benchmark gates;
- add nightly schedules;
- add release candidate state machines;
- replace deleted evidence tooling with a new manifest schema;
- preserve obsolete files through compatibility wrappers unless an active product API imports them;
- create a release, tag, or version bump as part of this plan.

## 6. Workstream A — establish a deletion and dependency inventory

Before editing, search the repository for every reference to the following concepts and files:

- `release.yml`;
- `check_evidence_consistency`;
- `collect_ci_evidence`;
- `finalize_release_evidence`;
- `junit_to_lane_summary`;
- `lane-summary`;
- `lint-summary`;
- `artifact-hashes`;
- `release-inventory`;
- `release_inventory.py`;
- `workflow_run_id` in release documents and validators;
- `candidate-state`;
- `final-cross`;
- `Final Closure Evidence`;
- `releases-4-6-final.json`;
- `releases-4-6-ci-run.json`;
- `releases-4-6-inventory.json`;
- candidate performance JSON files;
- `mypy-strict.ini`;
- `smoke_release_surfaces.py`;
- `verify_wheel_consumer.py`;
- `release-check` and `publish` Make targets.

Classify each match as one of:

1. application correctness;
2. package correctness;
3. historical documentation;
4. CI orchestration;
5. release-evidence machinery;
6. test of deleted machinery.

Only categories 1 and 2 justify continued active enforcement.

### Acceptance criteria

- a written implementation note or commit summary identifies all deleted and retained components;
- no evidence-only file is retained because of a circular reference from another evidence-only file;
- product-facing scripts are distinguished from workflow-proof scripts;
- deletion decisions are made from actual references, not filename guesses.

## 7. Workstream B — make the Makefile authoritative

Refactor `Makefile` before simplifying YAML so CI can delegate to stable local targets.

### B1. Development setup

Change `make dev` so it installs development dependencies only. It must not automatically run `pre-commit install` or modify `.git/hooks`.

Provide an explicit optional target such as:

```make
hooks:
	python -m pre_commit install
```

A developer who does not want hooks must be able to run `make dev` without side effects outside the virtual environment.

### B2. Check targets

Retain or introduce these explicit targets:

```text
install
dev
test
test-cov
lint
format
format-check
typecheck
docs-check
check
clean
build
package-check
release-check
publish
hooks
```

`test-cov` remains opt-in and is not part of `check` or required CI.

### B3. Remove duplicate static policies

The repository currently runs ordinary Ruff and a second strict selected-file Ruff invocation. Select one repository policy.

Preferred resolution:

- retain the ordinary Ruff configuration in `pyproject.toml`;
- remove the selected-file strict Ruff invocation from CI;
- do not add a second Make target that reproduces it.

For typing:

- retain one ordinary package mypy invocation;
- retain one strict external-consumer invocation if it protects the installed public typing surface;
- remove separate strict migrated-module invocations unless they enforce a concrete public contract not covered by ordinary package mypy and tests;
- delete or simplify `mypy-strict.ini` if it becomes unused;
- do not run type checking in pre-commit.

### B4. Package isolation

Correct the release smoke path so installed-wheel tests cannot accidentally import the source checkout.

The replacement probe must:

- create a temporary directory outside the repository;
- create a virtual environment there;
- install the wheel with `--no-deps`;
- run with `PYTHONPATH` absent;
- use a working directory outside the repository;
- assert the imported `eggcalc.__file__` is under the temporary environment's site-packages or dist-packages;
- assert `py.typed` exists;
- invoke the installed `calc` entry point;
- invoke package API evaluation and a representative unit conversion;
- exercise a minimal MCP initialize, tools/list, and math tool call;
- fail with concise diagnostic output.

The generated single-file smoke may run from another temporary directory and must not rely on imports from the source tree.

### B5. Expected target relationship

The dependency graph should be simple:

```text
check
  ├─ lint
  ├─ format-check
  ├─ typecheck
  ├─ docs-check
  ├─ build manifest validation
  └─ test

package-check
  ├─ clean
  ├─ build
  ├─ twine check
  └─ isolated release-surface smoke

release-check
  ├─ check
  └─ package-check

publish
  └─ explicit Twine upload, preferably after release-check
```

### Acceptance criteria

- `make dev` does not install Git hooks;
- `make check` is network-free and runs each required check once;
- `make check` does not inspect Git history or GitHub state;
- `make package-check` proves wheel and generated-file isolation;
- `make release-check` produces validated wheel and sdist files;
- `make publish` is not invoked by any workflow;
- `make test-cov` remains available but optional;
- there is no duplicate Ruff policy or duplicate full-suite execution in the Make dependency graph.

## 8. Workstream C — replace required CI with one canonical job

Rewrite `.github/workflows/ci.yml` rather than incrementally pruning the current matrix.

A representative target shape is:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
          cache-dependency-path: pyproject.toml
      - name: Install verification dependencies
        run: python -m pip install -e ".[dev]"
      - name: Verify
        run: make check
      - name: Validate packages
        run: make package-check
```

The implementation may keep actions pinned to commit SHAs if that is existing repository policy. Pinning style is not the objective; job count and responsibility are.

### C1. Remove matrix behavior

Required CI must have no `strategy.matrix`.

### C2. Remove summary and artifact machinery

Delete from required CI:

- JUnit XML generation used only for lane summaries;
- lane summary generation;
- lane summary uploads;
- repeated lint summary generation;
- lint summary uploads;
- coverage XML generation and upload;
- release inventory generation;
- artifact hash generation;
- artifact hash upload;
- evidence validator invocation;
- candidate/final state branching;
- focused closure suite reruns;
- repeated single-file deterministic builds in separate lanes.

If deterministic single-file generation remains a product invariant, test it once in the existing build tests or package-check path. Do not represent it as a workflow artifact.

### C3. Failure readability

A failure should map directly to one Make target and one product-facing command. Avoid `if: always()` post-processing steps that can replace the original failure with a missing-file or parser error.

### C4. Required check identity

Use a stable job name such as `verify` so branch protection can require one check. Document any maintainer action needed to remove old matrix job names from branch protection.

### Acceptance criteria

- automatically triggered CI contains exactly one job;
- required CI uses exactly one Python version;
- the full pytest suite executes exactly once;
- Ruff executes exactly once;
- Black check executes exactly once;
- package mypy executes exactly once;
- generated-doc drift validation executes exactly once;
- package build executes once through the package-check path;
- no workflow artifact is uploaded;
- no workflow writes repository contents;
- no required step refers to Releases 4–6 evidence;
- a grep for `candidate-state`, `final-cross`, `lane-summary`, `lint-summary`, `artifact-hashes`, and `release-inventory` in active workflow files returns no matches;
- branch protection, if configured, can require a single `CI / verify` result.

## 9. Workstream D — add optional compatibility testing only if justified

If retained, create `.github/workflows/compatibility.yml` with `workflow_dispatch` as its sole trigger.

Recommended shape:

```yaml
name: Compatibility

on:
  workflow_dispatch:

permissions:
  contents: read

jobs:
  test:
    strategy:
      fail-fast: false
      matrix:
        include:
          - os: windows-latest
            python-version: "3.11"
          - os: ubuntu-latest
            python-version: "3.14"
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: python -m pip install -e ".[dev]"
      - run: python -m pytest tests/ -q
      - run: python build_single.py --validate
      - run: python build_single.py
      - run: python eggcalc.py "5+3"
```

Cross-platform Make support may be used instead if all commands are portable. Do not force Unix-only shell assumptions onto Windows.

### Acceptance criteria

- the compatibility workflow never runs automatically;
- it is not referenced as a required branch-protection check;
- it contains no publishing permissions or release steps;
- it contains no evidence or artifact-summary steps;
- macOS is not added merely to recreate the old matrix;
- no more than two lanes are present without a newly documented product-specific reason.

## 10. Workstream E — delete automated release behavior

Delete `.github/workflows/release.yml` in full.

Do not replace it with:

- a PyPI publishing workflow;
- a GitHub Release workflow;
- a reusable release workflow;
- a tag validation workflow;
- a workflow that uploads release distributions for later manual retrieval.

A tag push must become an ordinary Git operation with no release automation.

### E1. Remove stale Make messaging

Remove output such as:

```text
Ready to release! Run: git tag vX.Y.Z && git push --tags
```

unless it appears in the manual release documentation with the correct full sequence and clear separation from publication.

Avoid a `release` target that ambiguously means check, publish, tag, or GitHub release. Prefer the explicit names `release-check` and `publish`.

### E2. Add Twine to a reproducible dependency group

The current `dev` extra contains `build` but not Twine. Add Twine either to:

- the `dev` extra; or
- a new `release` extra such as `.[release]`.

A separate `release` extra is cleaner if documentation installs both as needed, but minimizing dependency groups is also reasonable. The chosen approach must make `make package-check` and `make publish` reproducible.

### E3. Manual documentation

Create `docs/releasing.md` and link it from an appropriate contributor or project document. Do not make release instructions depend on reading old evidence plans.

### Acceptance criteria

- `.github/workflows/release.yml` does not exist;
- no workflow triggers on `v*` tags for release purposes;
- no workflow has `contents: write` for publishing or release creation;
- no repository workflow invokes Twine upload;
- no repository workflow invokes a GitHub Release action;
- `docs/releasing.md` clearly states manual PyPI ownership;
- the documented publication command is reproducibly available;
- pushing a tag cannot create a GitHub Release or publish a package.

## 11. Workstream F — retire active release-evidence machinery

The evidence machinery must be removed from active code, tests, CI, and agent policy.

### F1. Delete evidence-only scripts

Delete scripts whose only purpose is proving or finalizing Releases 4–6 workflow evidence, including as applicable after the dependency inventory:

- `scripts/check_evidence_consistency.py`;
- `scripts/collect_ci_evidence.py`;
- `scripts/finalize_release_evidence.py`;
- `scripts/junit_to_lane_summary.py`.

Also delete helper modules used only by those scripts.

### F2. Decide the release inventory by product value

`scripts/release_inventory.py` currently constructs a deep synchronized inventory of package and generated-file public API, units, MCP schemas, metadata, profiles, artifact hashes, and candidate/run identity.

Do not retain this full inventory generator merely because evidence tests refer to it.

Preferred resolution:

- replace the useful behavioral portion with the lean isolated package smoke described in Workstream B;
- keep ordinary package/generated-file parity tests where they protect actual behavior;
- delete inventory JSON generation, hash fields, workflow identity, and evidence integration;
- delete the script entirely if no non-evidence consumer remains.

### F3. Preserve useful smoke behavior without preserving the framework

`scripts/smoke_release_surfaces.py` may be simplified and retained, or replaced by a smaller script. The result should test behavior, not enumerate or serialize the entire architecture.

A useful smoke script should answer only:

- does the package import from the installed wheel?;
- does the installed console script work?;
- does a representative calculation work?;
- does unit conversion work?;
- does MCP initialize and answer a representative call?;
- does the generated single file expose the equivalent basic surfaces?;

It should not emit closure manifests, inventories, hashes, or workflow provenance.

### F4. Delete evidence-specific tests

Delete tests that exist only to verify deleted release-evidence machinery, including as applicable:

- strict evidence-integrity validator tests;
- evidence consistency tests;
- CI evidence collector tests;
- finalizer tests;
- lane-summary conversion tests;
- release inventory tests whose only assertions concern hashes, workflow identity, candidate identity, or serialized inventory shape.

Do not delete:

- functional unit tests;
- MCP tests;
- build-single tests;
- installed-wheel behavior tests;
- public API typing tests;
- package/generated-file parity tests that directly compare behavior;
- Windows regression tests for actual path or newline behavior.

### F5. Archive historical documents without active enforcement

Historical `docs/release_4_evidence.md`, `docs/release_5_evidence.md`, and `docs/release_6_evidence.md` may remain in place or move under `docs/archive/`. The preferred minimal-change choice is to retain them with a header such as:

```text
Historical record. This document is not an active release gate. The project now uses manual PyPI publication and product-focused CI as defined in docs/releasing.md.
```

Remove generated final-state JSON, CI snapshot, inventory, and candidate performance files when they have no ongoing documentation value. Do not retain them in active paths merely to satisfy old validators that are being deleted.

Historical benchmark reports may remain as ordinary benchmark records if clearly labeled and disconnected from release approval.

### F6. Remove agent-policy coupling

Replace the `AGENTS.md` “Release Evidence Integrity Protocol” section with a concise “Verification and Release Policy” section stating:

- `make check` is canonical correctness verification;
- `make package-check` validates distributable surfaces;
- `make release-check` combines them;
- publication is manual through Twine/PyPI;
- GitHub Actions never publishes;
- historical evidence files are non-authoritative archives.

Update the documented CI order to match the actual one-job workflow.

Remove stale statements that the current Linux/macOS/Windows matrix or evidence protocol must be preserved.

### Acceptance criteria

- active code contains no Releases 4–6 candidate/final state machine;
- active tests do not mock Git ancestry for release evidence;
- active tests do not require workflow run IDs or artifact IDs;
- active CI does not read `docs/evidence/**`;
- deleting or editing a historical evidence document cannot fail application CI;
- no application change requires an evidence-only follow-up commit;
- product parity and package isolation remain directly tested;
- `AGENTS.md` reflects the new policy rather than plans 017–019.

## 12. Workstream G — simplify pre-commit and contributor workflow

### G1. Make hooks optional and fast

Remove the pre-commit mypy hook and its `types-all` dependency.

A suitable hook set is:

- trailing whitespace;
- end-of-file fixer;
- YAML/TOML syntax checks;
- merge-conflict and case-conflict checks;
- large-file check;
- debug-statements check;
- Black;
- Ruff.

The hook configuration may apply autofixes, but it must not run the full test suite, build distributions, generate documentation, inspect GitHub, or run release checks.

### G2. Align contributor documentation

Update `CONTRIBUTING.md` so the standard sequence is:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
make check
```

Hooks are optional:

```bash
make hooks
```

Package-affecting changes should additionally run:

```bash
make package-check
```

### G3. Remove contradictory checklists

The PR checklist should refer to `make check` rather than separately listing commands that may drift. Add `make package-check` only for changes affecting packaging, entry points, generated single-file output, MCP startup, version metadata, or public exports.

### Acceptance criteria

- pre-commit does not run mypy or install `types-all`;
- `make dev` does not install hooks;
- contributor documentation identifies one canonical verification command;
- CI and contributor documentation invoke the same repository-owned targets;
- no contributor instruction mentions evidence finalization or required workflow artifacts.

## 13. Workstream H — verify the simplified system

### H1. Local verification

Run from a clean environment:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
make check
make package-check
```

If release dependencies are separated:

```bash
python -m pip install -e ".[dev,release]"
```

### H2. Isolation verification

Prove the wheel test is not resolving the source checkout:

- temporarily make a harmless source-only sentinel unavailable in the built wheel or inspect `eggcalc.__file__`;
- run the installed-wheel probe outside the repository;
- confirm the import path belongs to the temporary virtual environment;
- confirm the probe succeeds with `PYTHONPATH` unset;
- confirm the probe fails if the wheel is intentionally malformed or a required package file is removed.

Do not commit a deliberately malformed wheel.

### H3. Workflow inspection

Verify mechanically:

```bash
find .github/workflows -maxdepth 1 -type f -print
rg -n "upload-artifact|download-artifact|softprops/action-gh-release|twine upload|candidate-state|final-cross|lane-summary|lint-summary|artifact-hashes|release-inventory|workflow_run_id" .github/workflows
```

Expected result:

- only `ci.yml` and optional manual `compatibility.yml` exist;
- the search returns no active release/evidence matches;
- `upload-artifact` and `download-artifact` are absent unless a narrowly justified manual compatibility debugging feature remains, which should normally be omitted.

### H4. Reference cleanup

Run repository-wide searches:

```bash
rg -n "check_evidence_consistency|collect_ci_evidence|finalize_release_evidence|junit_to_lane_summary|candidate-state|final-cross|releases-4-6-final|release-inventory|lane-summary|lint-summary|artifact-hashes"
```

Remaining matches are permitted only in:

- archived historical plans;
- clearly labeled historical release documentation;
- this plan.

No active script, test, Make target, workflow, contributor guide, or agent instruction may depend on them.

### H5. CI verification

Push the implementation commit and confirm:

- one automatic workflow starts;
- one required job appears;
- the job runs `make check` and `make package-check`;
- the full test suite appears once in logs;
- no artifact uploads appear;
- no release workflow starts;
- no historical evidence state is evaluated.

### Acceptance criteria

- `make check` passes;
- `make package-check` passes;
- required CI passes as one job;
- optional compatibility workflow, if retained and manually invoked, passes on its declared lanes;
- no product test was removed solely to reduce wall-clock time;
- no evidence-specific failure remains possible in routine CI;
- no tag-triggered workflow exists;
- no publishing credential is required by CI.

## 14. File-level implementation guide

The implementation agent should expect the following disposition, subject to the dependency inventory.

### Delete

- `.github/workflows/release.yml`;
- evidence-only validator/collector/finalizer scripts;
- lane-summary conversion script;
- evidence-specific tests;
- generated current-final evidence JSON and CI/inventory snapshots that serve no archival purpose;
- stale current-candidate performance comparison artifacts used only for approval;
- unused strict mypy configuration if no retained command consumes it.

### Rewrite substantially

- `.github/workflows/ci.yml`;
- `Makefile`;
- `.pre-commit-config.yaml`;
- release-surface smoke tooling;
- `AGENTS.md` release and CI sections;
- `CONTRIBUTING.md`;
- historical release documents' status headers.

### Add

- `docs/releasing.md`;
- optional `.github/workflows/compatibility.yml` only if justified;
- a lean isolated wheel/single-file smoke script if simplifying the existing one is less clear.

### Preserve unless direct cleanup is required

- application source under `eggcalc/**`;
- functional tests under `tests/**`;
- `build_single.py` product logic;
- unit baseline fixtures used to prove application behavior rather than release identity;
- package metadata and public entry points;
- benchmark tooling as opt-in developer tooling, provided it is not a release gate.

## 15. Commit sequencing

Use a small number of coherent commits. A recommended sequence is:

### Commit 1 — local verification contract

- refactor Makefile targets;
- correct isolated package smoke behavior;
- add Twine dependency;
- add or update tests for the lean smoke path.

Required before proceeding:

- `make check` passes;
- `make package-check` passes locally.

### Commit 2 — CI and release workflow simplification

- rewrite `ci.yml` to one job;
- delete `release.yml`;
- optionally add manual compatibility workflow;
- remove workflow summary, artifact, evidence, and matrix behavior.

### Commit 3 — evidence retirement

- delete evidence-only scripts and tests;
- remove active final evidence JSON/inventory/performance approval files;
- simplify or delete release inventory tooling;
- mark retained Markdown evidence as historical.

### Commit 4 — policy and contributor documentation

- add `docs/releasing.md`;
- update `AGENTS.md`, `AGENTS.override.md`, and `CONTRIBUTING.md`;
- simplify pre-commit;
- perform repository-wide stale-reference cleanup.

A smaller implementation may combine commits 2–4 if reviewability remains good. Do not create a long chain of evidence-only closure commits for this plan.

## 16. Explicit closure criteria

This plan is complete only when every item below is true.

### CI topology

- [ ] Exactly one automatically triggered correctness workflow exists.
- [ ] Required CI has exactly one job.
- [ ] Required CI uses Ubuntu and Python 3.11.
- [ ] Required CI has read-only repository permissions.
- [ ] Required CI has no test matrix.
- [ ] Required CI runs the full suite once.
- [ ] Required CI uploads no artifacts.
- [ ] Required CI generates no custom summaries.
- [ ] Required CI reads no release evidence.
- [ ] Optional compatibility CI, if present, is manual-only and non-required.

### Release ownership

- [ ] `.github/workflows/release.yml` is deleted.
- [ ] No workflow triggers publication or GitHub Release creation from tags.
- [ ] No workflow invokes `twine upload`.
- [ ] No workflow has release-oriented write permissions.
- [ ] `docs/releasing.md` documents manual PyPI publication.
- [ ] The documentation states PyPI versions are immutable.
- [ ] `make publish` is explicit and never invoked by CI.

### Local verification

- [ ] `make check` is the canonical correctness command.
- [ ] `make package-check` validates wheel, sdist, and single-file surfaces.
- [ ] `make release-check` combines correctness and package validation.
- [ ] Wheel smoke runs outside the repository with `PYTHONPATH` unset.
- [ ] The installed import path is asserted to come from the temporary environment.
- [ ] Coverage remains opt-in.
- [ ] Hooks remain opt-in.

### Complexity reduction

- [ ] Historical candidate/final evidence validation is removed from active code.
- [ ] CI evidence collection is removed.
- [ ] Lane and lint summary generation is removed.
- [ ] Workflow-linked artifact hashing is removed.
- [ ] Evidence-specific tests are removed.
- [ ] Release inventory serialization is removed or reduced to direct behavioral smoke tests.
- [ ] Performance records are not release gates.
- [ ] Git ancestry is not part of ordinary verification.
- [ ] Workflow run IDs and artifact IDs are not part of ordinary verification.

### Correctness preservation

- [ ] Full functional pytest suite passes.
- [ ] Ruff passes.
- [ ] Black check passes.
- [ ] Package mypy passes.
- [ ] Retained strict typed consumer passes.
- [ ] Generated documentation drift check passes.
- [ ] `build_single.py --validate` passes.
- [ ] Wheel and sdist pass Twine validation.
- [ ] Installed wheel API, CLI, unit, and MCP smoke tests pass.
- [ ] Generated single-file CLI and MCP smoke tests pass.
- [ ] No public product behavior or supported Python declaration is intentionally reduced.

### Documentation consistency

- [ ] `AGENTS.md` describes the simplified policy.
- [ ] `CONTRIBUTING.md` points to `make check`.
- [ ] Pre-commit is optional and does not run mypy.
- [ ] Historical evidence documents are clearly non-authoritative.
- [ ] No active documentation instructs agents to finalize evidence from a GitHub run.
- [ ] No active documentation claims automated GitHub release behavior.

## 17. Evidence required for handoff completion

The implementing agent's final handoff should contain only concise, current evidence:

- implementation commit SHA;
- list of deleted workflows/scripts/tests;
- final workflow file list;
- output summary for `make check`;
- output summary for `make package-check`;
- required CI run URL or run ID and its single job conclusion;
- optional compatibility run result if manually executed;
- confirmation that no tag-triggered release workflow exists;
- confirmation that no publication occurred.

Do not create a new synchronized closure manifest, evidence-only commit, artifact hash registry, candidate performance record, or post-evidence workflow requirement. The successful product-focused CI run and local command results are sufficient.

## 18. Stop conditions

Stop and report rather than broadening scope if:

- a supposedly evidence-only component is imported by a documented public API;
- wheel isolation reveals a real packaging defect unrelated to the old evidence framework;
- deletion exposes an actual application correctness gap;
- branch protection cannot be changed by repository code and still requires obsolete matrix job names;
- the full suite cannot run once on Ubuntu Python 3.11 due to a real supported-platform failure.

In those cases, fix only the direct blocker or document the required maintainer action. Do not restore the historical evidence architecture, expand the matrix, or add replacement orchestration without explicit maintainer approval.

## 19. Final definition of done

The repository is in the intended state when a normal code change receives one readable, product-focused CI result; developers can reproduce that result with `make check` and validate distributions with `make package-check`; releases are prepared with `make release-check` and published manually to PyPI; and no GitHub workflow, evidence state machine, artifact ledger, or historical release record controls release cadence or routine iteration.
