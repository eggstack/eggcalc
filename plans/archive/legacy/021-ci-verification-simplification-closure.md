# CI Simplification Correctness and Isolation Closure

Status: implementation handoff  
Repository: `eggstack/eggcalc`  
Baseline reviewed: `35ced34480e550506f9b366b06448d226826dc17`  
Date: 2026-07-28  
Depends on: `plans/020-ci-verification-and-manual-pypi-release-simplification.md`

## 1. Purpose and disposition

Plan 020 substantially achieved its governing objective. The repository now has one small required CI job, a manual-only compatibility workflow, no tag-triggered release workflow, explicit manual PyPI publication, and no active Releases 4–6 evidence state machine. The implementation removed the large matrix, workflow artifacts, custom lane summaries, workflow-linked inventories, release-evidence collection/finalization, and evidence-specific tests.

That simplification must be preserved.

The line of work is not yet fully closed because three narrow gaps remain:

1. `tests/typing/consumer.py` is no longer checked by any command even though the file states that strict mypy is its only verification mechanism.
2. The release-surface smoke script isolates ordinary wheel imports, but its MCP helper still unconditionally injects the repository into `PYTHONPATH`; the installed wheel console/MCP surfaces are not exercised, and generated single-file CLI/MCP probes can still resolve source-tree modules.
3. `AGENTS.override.md` retains stale plan-completion and fixed test-count claims that no longer describe the repository's active verification policy.

A final implementation pass must close only these gaps, verify the new one-job CI workflow, and stop. It must not reintroduce release evidence, CI artifact ledgers, broad strict-typing migration, automated publication, or a permanent compatibility matrix.

## 2. Governing constraints

The following decisions from Plan 020 remain authoritative:

- required CI consists of one `ubuntu-latest` / Python 3.11 job;
- required CI invokes repository-owned Make targets rather than duplicating commands in YAML;
- the complete pytest suite runs exactly once in required CI;
- compatibility testing is manual-only and non-required;
- GitHub Actions does not publish to PyPI, create GitHub Releases, push tags, or modify repository contents;
- PyPI publication is a direct maintainer action through Twine;
- historical release evidence is archival documentation only;
- routine correctness does not depend on Git ancestry, workflow run IDs, artifact IDs, candidate SHAs, performance records, or closure manifests;
- no product test may be removed merely to reduce wall-clock time;
- no new verification framework may be introduced to replace the deleted evidence framework.

The implementation agent must treat any apparent conflict in older plans, release documents, or comments as superseded by Plans 020 and 021.

## 3. Current state to preserve

The pass must preserve the current simplified topology:

```text
.github/workflows/ci.yml
  automatic: push main, pull_request main, workflow_dispatch
  jobs: verify
  runner: ubuntu-latest
  Python: 3.11
  commands: make check; make package-check

.github/workflows/compatibility.yml
  automatic: never
  trigger: workflow_dispatch only
  lanes: Windows 3.11; Ubuntu 3.14
```

It must preserve the current local interface:

```text
make check
make package-check
make release-check
make publish
make hooks
```

It must preserve removal of:

- `.github/workflows/release.yml`;
- `scripts/check_evidence_consistency.py`;
- `scripts/collect_ci_evidence.py`;
- `scripts/finalize_release_evidence.py`;
- `scripts/junit_to_lane_summary.py`;
- `scripts/release_inventory.py`;
- `scripts/verify_wheel_consumer.py`;
- evidence-specific tests;
- `mypy-strict.ini`;
- workflow artifact upload/download steps;
- lane-summary, lint-summary, inventory, and artifact-hash generation.

None of these may be restored, renamed, or replaced with equivalent machinery.

## 4. Non-goals

Do not:

- redesign the calculator, natural-language normalizer, units, exact tools, MCP server, registry, executor, configuration, or runtime context;
- broaden strict mypy to all source modules;
- recreate `mypy-strict.ini`;
- add pyright, basedpyright, tox, nox, hatch environments, or another task runner;
- add a required Windows, macOS, or Python-version matrix;
- add scheduled, nightly, release, tag, or workflow-run-triggered workflows;
- add automated PyPI trusted publishing;
- add GitHub Release creation;
- add coverage thresholds or benchmark gates;
- add JUnit conversion, custom summaries, artifact hashes, release inventories, or evidence manifests;
- change supported Python versions;
- bump the package version, create a tag, publish a package, or create a GitHub Release;
- reopen historical Releases 4–6 closure work;
- require a second evidence-only commit after implementation;
- retain stale behavior merely to minimize the diff.

## 5. Target state

At completion:

1. `make typecheck` verifies both the package and the strict external-consumer contract.
2. `make check` therefore protects the public typed API without restoring broad strict typing.
3. `make package-check` builds wheel and sdist, runs Twine validation, and exercises release surfaces from clean external environments.
4. Installed-wheel API, unit, console entry point, and MCP startup/tool-call probes run using the wheel environment with repository path injection disabled.
5. Generated single-file CLI and MCP probes run from a temporary directory with `PYTHONPATH` absent.
6. Virtual-environment interpreter and console-script discovery work on POSIX and Windows.
7. The manual Windows compatibility lane exercises the cross-platform package smoke path.
8. `AGENTS.override.md` contains no volatile plan-completion or historical test-count claim.
9. A push of the implementation commit produces one successful required CI job and no release/evidence side effects.

## 6. Workstream A — restore the strict external-consumer contract

### A1. Problem

`tests/typing/consumer.py` is excluded from pytest and contains no test functions. Its module documentation states that strict mypy is its only verification mechanism. The current `Makefile` runs only:

```make
mypy eggcalc --ignore-missing-imports
```

As a result, the public consumer type surface is currently unverified.

### A2. Required Makefile behavior

Update `typecheck` so it performs exactly two responsibilities:

1. ordinary package type checking;
2. strict checking of `tests/typing/consumer.py` as an external consumer.

Recommended shape:

```make
typecheck:
	mypy eggcalc --ignore-missing-imports
	mypy --strict --follow-imports=silent --ignore-missing-imports tests/typing/consumer.py
```

The exact ordering of command-line flags is not important. The semantic requirements are:

- strict mode applies to `tests/typing/consumer.py`;
- imported implementation modules are not pulled into a new repository-wide strict migration;
- errors in the consumer file are not ignored;
- the command returns nonzero for a real public type-contract regression;
- no separate configuration file is introduced solely for this command.

If `follow-imports=silent` is already inherited from an active root mypy configuration, it may be omitted from the command only when the resulting invocation remains explicit and reproducible.

### A3. Failure-mode proof

Before considering the work complete, temporarily introduce a local, uncommitted mismatch in `tests/typing/consumer.py`, such as assigning the result of `evaluate()` to `str`, and confirm the strict command fails. Revert the temporary change before committing.

Example temporary mutation:

```python
result: str = evaluate("5 + 3")
```

Expected result:

- strict consumer mypy exits nonzero;
- ordinary package mypy behavior is unchanged;
- after reverting the mutation, `make typecheck` passes.

Do not commit a deliberate type error or a golden error-output fixture.

### A4. Documentation alignment

Review `AGENTS.md` and `CONTRIBUTING.md` for the current description of `make check`. They may continue to describe `make check` at a high level, but any explicit type-check command must match the new canonical target.

Do not require contributors to invoke the consumer command separately if `make check` already includes it through `typecheck`.

### A5. Acceptance criteria

- `make typecheck` runs ordinary package mypy exactly once.
- `make typecheck` runs strict consumer mypy exactly once.
- `make check` includes both through the `typecheck` prerequisite.
- `tests/typing/consumer.py` remains excluded from pytest; it is not converted into artificial runtime tests merely to make it execute.
- no `mypy-strict.ini` or replacement strict configuration file is added.
- no unrelated source module is newly required to satisfy repository-wide strict mode.
- a temporary consumer annotation regression is detected.
- the unmodified consumer file passes.

## 7. Workstream B — centralize clean subprocess environments

### B1. Problem

`scripts/smoke_release_surfaces.py` has two subprocess paths:

- `_run()`, which can now remove `PYTHONPATH` through `use_source_path=False`;
- `_mcp_session()`, which directly constructs an environment containing `PYTHONPATH=<repository root>`.

This split allows MCP smoke tests to appear isolated while still importing from the checkout.

### B2. One environment authority

Introduce one small helper that constructs subprocess environments for both `_run()` and `_mcp_session()`.

A suitable design is:

```python
def _subprocess_env(
    *,
    use_source_path: bool,
    extra: dict[str, str] | None = None,
) -> dict[str, str]:
    run_env = os.environ.copy()
    if use_source_path:
        run_env["PYTHONPATH"] = str(REPO_ROOT)
    else:
        run_env.pop("PYTHONPATH", None)
    if extra:
        run_env.update(extra)
    return run_env
```

Then:

- `_run()` delegates environment construction to this helper;
- `_mcp_session()` delegates to the same helper;
- callers explicitly choose whether source-tree resolution is permitted;
- clean release-artifact probes always use `use_source_path=False`.

Equivalent naming and signatures are acceptable. Duplicate environment-building logic is not.

### B3. MCP helper contract

Extend `_mcp_session()` to accept at least:

- `cwd`;
- `use_source_path`;
- optional extra environment values.

Recommended shape:

```python
def _mcp_session(
    python: str,
    args: list[str],
    *,
    cwd: str | Path | None = None,
    use_source_path: bool,
    env: dict[str, str] | None = None,
    timeout: float = 15.0,
) -> dict[str, object]:
    ...
```

The helper should set `EGGCALC_NO_CONFIG=1` for deterministic smoke sessions unless a specific config-loading test intentionally exercises another mode.

Do not silently default release-artifact MCP calls to source access. Prefer an explicit required argument or a safe `False` default.

### B4. Acceptance criteria

- `_run()` and `_mcp_session()` use one environment-construction helper.
- `_mcp_session()` no longer unconditionally injects the repository root.
- release-artifact calls run with `PYTHONPATH` absent.
- source-package tests may opt into repository resolution explicitly.
- config suppression remains deterministic for MCP smoke sessions.
- no shell-specific environment manipulation is required.

## 8. Workstream C — portable virtual-environment executable resolution

### C1. Problem

The current wheel smoke assumes POSIX paths:

```python
venv_dir / "bin" / "pip"
venv_dir / "bin" / "python"
```

This is incorrect on Windows, where executables live under `Scripts` and commonly use `.exe` suffixes.

### C2. Required implementation

Use the virtual environment's Python interpreter as the primary authority and invoke pip as a module:

```text
<venv-python> -m pip install --no-deps <wheel>
```

This avoids direct `pip` script discovery.

Add one helper for virtual-environment executables. A suitable design is:

```python
def _venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _venv_console_script(venv_dir: Path, name: str) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / f"{name}.exe"
    return venv_dir / "bin" / name
```

Equivalent use of `sysconfig`, `venv.EnvBuilder`, or platform-aware path derivation is acceptable when it remains small and readable.

Do not add a portability dependency.

### C3. Acceptance criteria

- the script does not hard-code `bin/python` without a Windows branch;
- wheel installation uses `<venv-python> -m pip` rather than a direct pip executable;
- the installed `calc` console script is resolved portably;
- missing interpreter or console-script paths fail with a clear smoke-test failure;
- POSIX behavior remains functional;
- the manual Windows compatibility run exercises these paths.

## 9. Workstream D — complete installed-wheel smoke coverage

### D1. Build and install authority

`make package-check` must remain the authority that:

1. cleans stale artifacts;
2. runs `python -m build`;
3. runs `twine check dist/*`;
4. executes `scripts/smoke_release_surfaces.py`.

The smoke script must select exactly one wheel from `dist/` or fail clearly when the wheel set is ambiguous.

Recommended behavior:

- fail when no wheel exists;
- fail when more than one wheel exists after the clean build, unless selection is explicitly version-matched;
- install with `--no-deps` because the runtime package is dependency-free;
- use a temporary venv outside the repository;
- use a temporary working directory outside the repository;
- remove `PYTHONPATH`.

### D2. Installed import provenance

Retain and strengthen the current provenance assertion:

- `eggcalc.__file__` resolves under `site-packages` or `dist-packages` inside the temporary venv;
- `py.typed` exists in the installed package;
- the resolved package path is not under `REPO_ROOT`;
- the working directory is not `REPO_ROOT`.

Do not infer isolation solely from the string `site-packages`; compare resolved paths where practical.

### D3. Installed API and unit smoke

Using the temporary venv interpreter with a clean environment, verify:

```python
from eggcalc import evaluate
assert evaluate("2+2") == 4
```

and:

```python
from eggcalc.units import UnitValue
assert UnitValue(1, "m").convert_to("ft").value > 3
```

These are direct behavioral probes, not inventories.

### D4. Installed console entry point

Invoke the installed `calc` console script, not the source module:

```text
<venv-console-dir>/calc 2+2
```

Acceptance requires:

- exit code zero;
- result output contains the expected value in the project's established CLI format;
- execution occurs with `cwd` outside the repository;
- `PYTHONPATH` is absent.

A console-script failure must fail `make package-check` even when `python -m eggcalc` would succeed.

### D5. Installed MCP surface

Run MCP through the wheel interpreter:

```text
<venv-python> -m eggcalc --mcp
```

Use the existing deterministic initialize / initialized notification / tools-list / `math_eval` tool-call sequence.

Acceptance requires responses for:

- initialize request ID;
- tools/list request ID;
- tools/call request ID;
- `math_eval` result containing `4`.

The session must use:

- the venv Python interpreter;
- external temporary `cwd`;
- `use_source_path=False`;
- `EGGCALC_NO_CONFIG=1`;
- no network.

### D6. Do not substitute source-package smoke

The existing source-package API, CLI, and MCP probes may remain as fast sanity checks, but they do not satisfy installed-wheel acceptance criteria. The implementation must clearly distinguish labels such as:

```text
source package MCP
installed wheel MCP
single-file MCP
```

### D7. Editable-install test disposition

The current smoke script also performs an editable-install test. This is not a release-artifact requirement.

The implementation agent may either:

- retain it if it remains small, deterministic, portable, and cleanly isolated; or
- remove it from `package-check` to reduce unnecessary venv setup.

Do not add a new required workflow or target solely for editable-install verification. Editable-install success must not be used as a substitute for wheel verification.

### D8. Acceptance criteria

- wheel API probe passes from the installed wheel;
- wheel unit conversion probe passes from the installed wheel;
- installed `calc` console script probe passes;
- installed wheel MCP initialize/list/call probe passes;
- all wheel probes run outside the repository with `PYTHONPATH` removed;
- `py.typed` presence is asserted;
- a wheel missing its console entry point would fail the smoke;
- a wheel missing MCP package content would fail the smoke;
- no release inventory JSON or artifact hash is generated.

## 10. Workstream E — make generated single-file probes genuinely standalone

### E1. Problem

The current single-file tests execute `eggcalc.py` while the helper defaults to `PYTHONPATH=<repository root>`. The MCP helper also injects the repository root. A generated artifact can therefore accidentally import checkout modules and still pass.

### E2. Generate into a temporary directory

Prefer generating the single-file artifact directly into an external temporary directory:

```text
python build_single.py -o <temporary-directory>/eggcalc.py
```

This avoids leaving or reusing a repository-root `eggcalc.py` during release smoke.

The generated file must exist and be nonempty before probes begin.

### E3. Standalone CLI probes

Run the generated file using the current interpreter with:

- absolute artifact path;
- `cwd` set to its temporary directory;
- `use_source_path=False`;
- `EGGCALC_NO_CONFIG=1` where appropriate.

Verify at least:

```text
<python> <temp>/eggcalc.py 2+2
<python> <temp>/eggcalc.py "five plus three"
```

Both must produce expected results and exit zero.

### E4. Standalone MCP probe

Run:

```text
<python> <temp>/eggcalc.py --mcp
```

through the corrected `_mcp_session()` with no repository path injection.

Require initialize, tools/list, and `math_eval` tool-call success.

### E5. Source-leak negative proof

During implementation, prove that the artifact is not using the checkout. An acceptable uncommitted proof is:

- run the generated artifact from a temporary directory;
- remove `PYTHONPATH`;
- set `cwd` outside the repository;
- confirm the artifact succeeds;
- temporarily rename or make unavailable a source-only module in a disposable copy, or inspect child `sys.path` through a temporary diagnostic, and confirm no repository path is present.

Do not commit diagnostic output or modify production imports solely to expose `sys.path`.

### E6. Acceptance criteria

- the single file is generated into a temporary external directory;
- its CLI arithmetic and natural-language probes pass;
- its MCP initialize/list/call probe passes;
- no single-file probe receives repository `PYTHONPATH`;
- no single-file probe uses repository root as `cwd`;
- the smoke script does not depend on a preexisting root `eggcalc.py`;
- failures are reported by surface name.

## 11. Workstream F — exercise package portability in manual compatibility CI

### F1. Preserve manual-only status

`.github/workflows/compatibility.yml` must remain `workflow_dispatch` only and non-required.

Do not add `push`, `pull_request`, `schedule`, `workflow_run`, or tag triggers.

### F2. Windows lane responsibility

The Windows 3.11 lane should exercise the corrected package smoke path because it is the only hosted environment that proves `Scripts/python.exe`, `calc.exe`, temporary-path, and subprocess-environment behavior.

After the existing test suite, add a concise package validation step on the Windows lane:

```yaml
- name: Validate package surfaces
  if: runner.os == 'Windows'
  run: |
    python -m build
    python -m twine check dist/*
    python scripts/smoke_release_surfaces.py
```

Equivalent use of a dedicated Python command is acceptable. Do not call the current POSIX-oriented `make clean` on Windows unless the Makefile is separately made portable without shell complexity.

The Ubuntu 3.14 lane may retain the existing full tests and single-file validation. It does not need to repeat package smoke unless doing so materially simplifies the YAML.

### F3. Workflow constraints

The compatibility workflow must:

- retain `contents: read`;
- upload no artifacts;
- publish nothing;
- create no release or tag;
- generate no custom summary;
- remain optional in branch protection;
- run the full test suite at most once per lane.

### F4. Acceptance criteria

- manual Windows 3.11 run builds and validates wheel/sdist;
- manual Windows 3.11 run completes installed-wheel and standalone smoke probes;
- manual Ubuntu 3.14 run passes its declared checks;
- no automatic event starts the compatibility workflow;
- required CI remains one job on Ubuntu 3.11.

## 12. Workstream G — remove stale override guidance

### G1. Problem

`AGENTS.override.md` contains volatile statements such as:

- all implementation items have been verified as completed;
- plan files have been archived;
- a fixed historical count of passing tests.

These claims become false as soon as new plans or tests exist and contradict the active handoff state.

### G2. Required cleanup

Preserve useful, timeless implementation notes, including:

- build-single conventions;
- evaluator versus natural-language API distinctions;
- unit alias behavior;
- exact-module organization;
- verified architectural conventions that remain current.

Remove or rewrite:

- global claims that all plans are complete;
- global claims that all tests pass;
- fixed test counts;
- status language tied to May 2026 completion;
- instructions that conflict with `AGENTS.md` verification and release policy.

Add at most one short pointer:

```text
Verification and release policy is defined in AGENTS.md and docs/releasing.md.
```

Do not duplicate the full policy in the override file.

### G3. Acceptance criteria

- `AGENTS.override.md` contains no fixed passing-test count;
- it does not claim all plans are archived or completed;
- it does not describe release evidence as active policy;
- timeless architecture notes remain intact;
- policy authority points to `AGENTS.md` / `docs/releasing.md` rather than duplicating commands.

## 13. Workstream H — local and CI closure verification

### H1. Clean local environment

Run from a clean checkout and fresh virtual environment:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
make check
make package-check
```

On Windows, use the platform-appropriate activation command or directly invoke `.venv\Scripts\python.exe`.

### H2. Required command observations

Confirm from output:

- ordinary package mypy runs once;
- strict consumer mypy runs once;
- full pytest runs once under `make check`;
- `build_single.py --validate` runs once under `make check`;
- wheel and sdist are freshly built under `package-check`;
- Twine validation passes;
- installed wheel import provenance passes;
- installed console script passes;
- installed wheel MCP passes;
- standalone CLI passes;
- standalone MCP passes;
- no artifact inventory, evidence manifest, or performance comparison is written.

### H3. Repository reference audit

Run:

```bash
rg -n "check_evidence_consistency|collect_ci_evidence|finalize_release_evidence|junit_to_lane_summary|candidate-state|final-cross|lane-summary|lint-summary|artifact-hashes|release-inventory|workflow_run_id" \
  .github Makefile scripts tests AGENTS.md AGENTS.override.md CONTRIBUTING.md architecture docs/releasing.md
```

Expected result:

- no active workflow, Make target, script, test, or policy document depends on deleted machinery;
- historical release Markdown may contain old run IDs only under an explicit historical-record header;
- plans may mention retired components as history or prohibition.

### H4. Workflow topology audit

Run:

```bash
find .github/workflows -maxdepth 1 -type f -print
rg -n "upload-artifact|download-artifact|action-gh-release|twine upload|contents: write|push:.*tags|tags:" .github/workflows
```

Expected result:

```text
.github/workflows/ci.yml
.github/workflows/compatibility.yml
```

and no release/publish/artifact/write-permission matches.

### H5. Push verification

Push the implementation commit and confirm the automatic workflow for that exact commit:

- workflow name: CI;
- one job: `verify`;
- runner: Ubuntu;
- Python: 3.11;
- conclusion: success;
- `make check` succeeded;
- `make package-check` succeeded;
- no artifacts were uploaded;
- no release workflow started;
- no compatibility workflow started automatically.

This confirmation may be reported as a run URL or run ID in the handoff. Do not commit it into a synchronized manifest.

### H6. Manual compatibility verification

Manually dispatch the compatibility workflow for the implementation commit and record:

- Windows 3.11 conclusion;
- Ubuntu 3.14 conclusion;
- confirmation that Windows package smoke executed;
- confirmation that no artifact or publication action occurred.

A concise handoff note is sufficient. Do not add generated evidence files.

## 14. File-level implementation guide

### Modify

- `Makefile`
  - restore strict consumer checking inside `typecheck`;
  - keep existing target topology;
  - do not add release orchestration.

- `scripts/smoke_release_surfaces.py`
  - centralize subprocess environment construction;
  - make `_mcp_session()` environment/cwd aware;
  - add portable venv interpreter and console-script resolution;
  - test installed console and MCP surfaces;
  - generate and test the standalone file externally;
  - remove source-path leakage from artifact probes;
  - optionally remove the editable-install probe if it adds no release value.

- `.github/workflows/compatibility.yml`
  - retain manual-only triggers;
  - make the Windows lane execute package smoke;
  - retain read-only permissions and no artifacts.

- `AGENTS.override.md`
  - remove volatile completion/test-count claims;
  - retain timeless implementation constraints.

- `AGENTS.md` and `CONTRIBUTING.md`
  - change only if explicit type-check wording needs alignment.

### Add only if necessary

A small focused test file for new pure helper behavior may be added if actual package and compatibility smoke do not adequately exercise it. Do not add tests that mock GitHub, synthesize workflow evidence, or duplicate end-to-end smoke behavior.

### Do not add

- configuration files for a new typing regime;
- evidence, inventory, hash, or CI-summary files;
- release workflows;
- package-publishing credentials;
- permanent generated `eggcalc.py` as closure evidence;
- a plan registry unless the repository already has an active registry authority requiring it.

## 15. Recommended implementation sequence

Use one or two coherent implementation commits.

### Commit 1 — typed contract and artifact isolation

- update `Makefile` strict consumer check;
- refactor smoke subprocess environment handling;
- add portable venv path handling;
- add installed console/MCP probes;
- move standalone probes to an external temporary directory;
- update manual Windows compatibility package smoke;
- run `make check` and `make package-check`.

### Commit 2 — guidance cleanup, if kept separate

- clean `AGENTS.override.md`;
- align explicit commands in `AGENTS.md` / `CONTRIBUTING.md` only where needed;
- run repository reference audits;
- rerun `make check` if documentation generation or formatting is affected.

A single commit is preferable if the changes remain reviewable.

Do not create:

- an evidence-only child commit;
- a candidate/final commit pair;
- a post-evidence workflow commit;
- a performance-record commit;
- a plan-completion manifest.

## 16. Explicit closure criteria

This plan is complete only when every item below is true.

### Typed API contract

- [ ] `make typecheck` runs package mypy.
- [ ] `make typecheck` runs strict mypy on `tests/typing/consumer.py`.
- [ ] a temporary incompatible annotation in the consumer is detected.
- [ ] the clean consumer passes.
- [ ] no broad strict migration or replacement config is introduced.

### Wheel isolation

- [ ] wheel installation uses the temporary venv Python with `-m pip --no-deps`.
- [ ] wheel probes run outside the repository.
- [ ] wheel probes receive no repository `PYTHONPATH`.
- [ ] installed import resolves inside the temporary environment.
- [ ] `py.typed` exists in the wheel.
- [ ] package API probe passes.
- [ ] unit conversion probe passes.
- [ ] installed `calc` entry point probe passes.
- [ ] installed wheel MCP initialize/list/call probe passes.

### Single-file isolation

- [ ] the standalone artifact is generated into a temporary directory.
- [ ] standalone CLI arithmetic passes.
- [ ] standalone CLI natural-language evaluation passes.
- [ ] standalone MCP initialize/list/call passes.
- [ ] standalone probes receive no repository `PYTHONPATH`.
- [ ] standalone probes do not use repository root as `cwd`.
- [ ] a preexisting repository-root `eggcalc.py` is not required.

### Portability

- [ ] venv Python resolution supports POSIX and Windows.
- [ ] installed console-script resolution supports POSIX and Windows.
- [ ] the manual Windows lane executes package smoke successfully.
- [ ] the manual Ubuntu 3.14 lane passes.

### Policy consistency

- [ ] required CI remains one Ubuntu/Python 3.11 job.
- [ ] the full pytest suite runs once in required CI.
- [ ] compatibility remains manual-only.
- [ ] no release workflow exists.
- [ ] no workflow publishes, tags, creates a release, uploads evidence, or has write permission.
- [ ] manual PyPI policy remains unchanged.

### Guidance cleanup

- [ ] `AGENTS.override.md` has no fixed test count.
- [ ] `AGENTS.override.md` does not claim all plans are completed or archived.
- [ ] active documentation describes the strict consumer as part of canonical checking where explicit detail is given.
- [ ] historical evidence remains clearly archival.

### Final verification

- [ ] `make check` passes from a clean environment.
- [ ] `make package-check` passes from a clean environment.
- [ ] one required CI job passes for the implementation commit.
- [ ] manually dispatched compatibility passes on both retained lanes.
- [ ] no generated evidence or inventory files are committed.
- [ ] no publication, tag, or GitHub Release is created.

## 17. Required final handoff evidence

The implementing agent's final report should contain only:

- implementation commit SHA;
- concise file-change summary;
- `make check` result, including strict consumer success;
- `make package-check` result, including wheel console/MCP and standalone MCP success;
- required CI run URL or run ID and `verify` conclusion;
- manual compatibility run URL or run ID and lane conclusions;
- confirmation that no artifacts, publication, tag, or release were produced;
- any maintainer-only branch-protection action still required.

Do not add this information to a committed manifest or evidence directory.

## 18. Stop conditions

Stop and report rather than broadening scope if:

- strict consumer checking reveals a genuine public annotation defect that requires changing a public type contract;
- wheel isolation reveals missing package files or entry-point defects beyond smoke-script wiring;
- standalone isolation reveals that the generated artifact has a real undeclared dependency on the source package;
- Windows package smoke exposes a real product portability defect;
- branch protection still requires deleted matrix job names and cannot be changed through repository files;
- the GitHub Actions service does not start the new CI workflow despite valid workflow syntax.

In those cases:

- fix a direct, clearly scoped product defect only when the correction is small and required for the existing supported surface;
- otherwise document the blocker for maintainer action;
- do not restore the old matrix, evidence framework, release workflow, or artifact machinery as a workaround.

## 19. Final definition of done

This line of work is closed when the simplified verification system protects the actual distributable interfaces it claims to protect: one required CI job runs canonical correctness and package checks; the public typed-consumer contract is checked; wheel and standalone CLI/MCP probes cannot resolve the source checkout; Windows portability is exercised only through the manual compatibility workflow; documentation contains no stale global completion claims; and releases remain entirely manual through PyPI/Twine without GitHub CI release orchestration.