# Next Pass Plan — Config Policy, CI Visibility, and Release-Surface Verification

## Objective

Perform a narrow corrective pass after the stdlib production-hardening Phases 1–5. The repo is substantially improved, but the next pass should close the remaining ambiguity around library/API config loading, strengthen regression tests so they prove actual subprocess behavior, and add a clear release-surface verification path.

This plan is intentionally conservative. Do not add new MCP tool families. Do not add runtime dependencies. Keep the project pure stdlib at runtime.

## Current assessment

The recent implementation commits completed most of the roadmap through Phase 5:

- Import-time `eggcalc_config.py` execution was removed from `import eggcalc`.
- CLI config loading was moved into `maybe_load_cli_config()`.
- MCP config loading remains blocked by `EGGCALC_NO_CONFIG=1`.
- MCP resource bounds were documented and tightened, including `MAX_PAIRWISE_ITEMS` for O(N²) paths.
- Profile docs/tests were improved and generated inventory was regenerated.
- Evaluation-path terminology was corrected across docs.
- Version comparison semantics no longer overclaim PEP 440 support.

The remaining concerns are not broad architecture problems. They are verification and policy gaps:

1. The library import path is now safe, but full-pipeline API calls may still lazily load cwd-local `eggcalc_config.py` through `_ensure_config_loaded()`.
2. At least one config regression test appears structurally weak because it can pass without actually importing `eggcalc` in the temp directory.
3. Remote GitHub Actions status was not visible for the implementation commits during review, so local-check claims in commit messages should be backed by a visible CI run or an explicit workflow-dispatch/check strategy.
4. Release-surface smoke tests should cover installed wheel, editable install, CLI, package MCP mode, and single-file MCP mode.

## Non-goals

- Do not add runtime dependencies.
- Do not add new agent tools.
- Do not implement PEP 440 in this pass.
- Do not change MCP profile defaults unless a specific compatibility decision is made separately.
- Do not introduce network access into deterministic tools.
- Do not make MCP tools filesystem-mutating.
- Do not rely on long wall-clock sleeps for tests.

## Workstream 1 — Decide and enforce API config-loading policy

### Problem

The recent safety fix removed import-time config execution, but commit notes indicate API config loading still happens lazily on first `evaluate_raw()` or related full-pipeline call. This is safer than import-time execution, but still surprising for library users and agents. A library call that evaluates user-facing math should not execute arbitrary Python from cwd unless explicitly opted in.

### Target policy

Prefer this policy for production safety:

- `import eggcalc`: never loads cwd config.
- `evaluate()`: never loads cwd config.
- `evaluate_raw()`, `evaluate_cached()`, `evaluate_async()`, and `evaluate_with_timeout()` default to no cwd config loading.
- CLI loads cwd config by default for backward compatibility, unless `EGGCALC_NO_CONFIG=1`.
- Explicit `load_user_config()` remains available for library users.
- Optional explicit API opt-in may be supported via `EGGCALC_LOAD_CONFIG=1` or an API flag, but implicit lazy API loading should be removed.
- MCP never loads cwd config.

If maintainers intentionally want API lazy config loading preserved for backward compatibility, document that as a conscious choice and add explicit tests proving it is disabled under `EGGCALC_NO_CONFIG=1`. However, the safer recommendation is to require explicit opt-in outside CLI.

### Implementation tasks

1. Inspect `_ensure_config_loaded()` and all callers in `evaluator.py`.
2. Identify which public APIs invoke `_ensure_config_loaded()`.
3. Choose one of two paths:

   **Preferred path:** change `_ensure_config_loaded()` so library/API calls do not load cwd config unless explicitly opted in.

   **Compatibility path:** keep lazy API config loading but rename/document it as intentional and add prominent warnings.

4. If using preferred path, add an explicit opt-in mechanism. Options:

   - `load_user_config()` manual call only.
   - `EGGCALC_LOAD_CONFIG=1` enables lazy API config loading.
   - `EggCalcApp(load_config=True)` if `EggCalcApp` is the right place for explicit app-level behavior.

5. Keep CLI behavior isolated in `maybe_load_cli_config()`.
6. Keep MCP behavior blocked regardless of opt-in env vars.

### Tests required

Use subprocess tests, not only in-process monkeypatch tests.

Required subprocess cases:

- `python -c "import eggcalc"` from a cwd containing malicious `eggcalc_config.py` does not create a sentinel file.
- `python -c "from eggcalc import evaluate_raw; evaluate_raw('five plus three')"` from a cwd containing malicious `eggcalc_config.py` does not create a sentinel file under the preferred policy.
- `python -c "from eggcalc import load_user_config; load_user_config()"` does create a sentinel file.
- `python -m eggcalc "myconst"` or an equivalent CLI expression proves CLI config is loaded when allowed.
- `EGGCALC_NO_CONFIG=1 python -m eggcalc ...` proves CLI config is disabled.
- MCP package mode proves config is not loaded.
- Single-file CLI and single-file MCP modes match the intended behavior.

Use sentinel files rather than `sys.modules` sentinels where possible. A subprocess can reliably check filesystem side effects after exit.

### Acceptance criteria

- API config policy is explicit in code, docs, and tests.
- No cwd-local Python executes during import.
- No cwd-local Python executes during API full-pipeline evaluation unless explicit opt-in is intentionally chosen.
- CLI customization remains available or any compatibility break is documented.
- MCP cannot be made to load cwd config by accidental env interaction.

## Workstream 2 — Strengthen config regression tests

### Problem

Some existing tests appear to validate source-code shape or callable existence rather than exercising the actual behavior in a fresh process. For config-loading safety, in-process tests are not enough because module cache state and prior imports can mask failures.

### Implementation tasks

1. Replace weak tests with subprocess-backed tests.
2. Add a small helper in tests for creating a temporary malicious config:

```python
def write_sentinel_config(tmp_path, marker_name="loaded.txt"):
    marker = tmp_path / marker_name
    (tmp_path / "eggcalc_config.py").write_text(
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('loaded')\n"
        "CUSTOM_CONSTANTS = {'myconst': 123}\n"
    )
    return marker
```

3. Add a subprocess runner helper that sets `cwd=tmp_path`, controls env, and runs with the current interpreter.
4. Ensure tests use the package under test, not an accidentally installed system package. Set `PYTHONPATH` to the repo root if needed.
5. Add package and single-file variants only where the single-file artifact is already built in the test flow, or gate single-file-specific tests behind build fixture setup.
6. Avoid brittle source-string tests except as supplementary guardrails.

### Suggested test names

- `test_import_does_not_execute_cwd_config_subprocess`
- `test_evaluate_raw_does_not_execute_cwd_config_without_opt_in_subprocess`
- `test_explicit_load_user_config_executes_cwd_config_subprocess`
- `test_cli_loads_cwd_config_by_default_subprocess`
- `test_cli_no_config_env_blocks_cwd_config_subprocess`
- `test_package_mcp_blocks_cwd_config_subprocess`
- `test_single_file_cli_config_policy_subprocess`
- `test_single_file_mcp_blocks_cwd_config_subprocess`

### Acceptance criteria

- The tests fail if config loading is accidentally reintroduced into `__init__.py`.
- The tests fail if API evaluation executes cwd config without opt-in under the preferred policy.
- The tests fail if MCP config hardening regresses.
- The tests are subprocess-isolated and not dependent on module cache state.

## Workstream 3 — CI visibility and workflow confirmation

### Problem

Commit messages claim local checks passed, but workflow-run lookup did not show GitHub Actions runs for the implementation commits during review. Before release, the repo should have visible CI confirmation for `main` or an explicit reason why Actions did not trigger.

### Implementation tasks

1. Inspect `.github/workflows/ci.yml` and confirm triggers include pushes to `main` and pull requests.
2. Confirm repository Actions are enabled and branch name is `main`.
3. Check whether commits were pushed in a way that bypassed Actions or whether the GitHub connector cannot see runs.
4. If Actions are not running, fix workflow triggering.
5. If Actions are running but not visible to the connector, document how maintainers should verify them manually.
6. Consider adding a simple `workflow_dispatch` trigger so maintainers can manually run CI on demand.
7. Ensure status checks cover:

   - Python 3.10–3.14 test matrix
   - ruff
   - black check
   - build_single.py
   - generated-doc check
   - pytest coverage
   - mypy
   - wheel build and install smoke test

### Acceptance criteria

- A fresh commit or manual dispatch produces a visible GitHub Actions run.
- The latest `main` commit has a clear pass/fail CI state.
- If connector visibility remains limited, the verification path is documented in `RELEASE.md` or equivalent.

## Workstream 4 — Release-surface smoke tests

### Problem

CI already validates much of the package, but the release surfaces should be explicitly smoked in a way that matches user consumption:

- editable install
- wheel install in clean venv
- CLI entry point
- `python -m eggcalc`
- package MCP server
- single-file CLI
- single-file MCP server

### Implementation tasks

1. Add a stdlib-only smoke test script, for example `scripts/smoke_release_surfaces.py`.
2. Keep it deterministic and network-free.
3. Use `subprocess`, `json`, `tempfile`, and `venv` only.
4. Test at least:

   Package/API:
   - `from eggcalc import evaluate; assert evaluate('2+2') == 4`
   - `from eggcalc import evaluate_raw; assert evaluate_raw('five plus three') == 8`

   CLI:
   - `python -m eggcalc "2+2"`
   - installed `calc "2+2"` if available in venv

   MCP package mode:
   - start `calc --mcp` or module-equivalent command
   - send `initialize`
   - send `tools/list` with compact schema
   - send `tools/call` for `math_eval`
   - terminate cleanly

   Single-file:
   - run `python build_single.py`
   - `python eggcalc.py "2+2"`
   - `python eggcalc.py --mcp` with initialize/list/math_eval sequence

5. Add config-safety smoke cases from Workstreams 1–2 if not already covered by unit tests.
6. Wire the script into CI only if runtime is reasonable. Otherwise add it to `make release-check`.

### Acceptance criteria

- Release smoke script exists and is documented.
- It validates package and single-file behavior.
- It validates MCP stdio behavior without external dependencies.
- It catches config-loading regressions in user-facing surfaces.
- It can be run locally before tagging.

## Workstream 5 — Documentation finalization

### Implementation tasks

Update docs to match the final config policy and release verification path:

- README security/config section
- `docs/api.md`
- `docs/cli.md`
- `docs/mcp.md`
- `AGENTS.md`
- `architecture/api.md`
- `architecture/cli.md`
- `architecture/evaluator.md`
- `RELEASE.md` or `docs/release.md`

Docs should clearly state:

- whether library API calls load cwd config by default
- how to opt into config loading from library code
- how to disable CLI config loading
- that MCP never loads cwd config
- how to run release-surface smoke checks
- how to verify GitHub Actions status before release

Regenerate generated docs after schema/doc metadata changes:

```bash
python scripts/generate_mcp_docs.py
python scripts/generate_mcp_docs.py --check
```

### Acceptance criteria

- Docs do not contradict the final config policy.
- Release verification steps are explicit.
- Generated docs pass drift checks.

## Suggested execution order

1. Decide API config policy.
2. Implement the policy with minimal code changes.
3. Replace weak config tests with subprocess-backed tests.
4. Add release-surface smoke script.
5. Wire smoke script into `make release-check` or CI as appropriate.
6. Confirm GitHub Actions visibility or add `workflow_dispatch`.
7. Update docs and regenerate generated docs.
8. Run full local verification.
9. Push and confirm CI.

## Validation commands

Run the existing full check set:

```bash
ruff check eggcalc tests
black --check eggcalc tests
python build_single.py
python scripts/generate_mcp_docs.py --check
pytest tests/ -v
mypy eggcalc --ignore-missing-imports
```

Run release-surface smoke checks once added:

```bash
python scripts/smoke_release_surfaces.py
```

If a Make target is added:

```bash
make release-check
```

Also verify package build:

```bash
python -m build
twine check dist/*
```

## Final acceptance criteria

This next pass is complete when:

- API config-loading behavior is intentionally safe and documented.
- Subprocess-backed tests prove import/API/CLI/MCP config policy.
- Single-file config behavior is tested.
- Release-surface smoke tests cover package, CLI, MCP, and single-file mode.
- GitHub Actions visibility is resolved or documented with a reliable manual path.
- Runtime remains pure stdlib.
- Full local checks and visible CI pass.

## Handoff notes

The most important judgment call is whether `evaluate_raw()` and related library APIs should load cwd config lazily. For production agent safety, prefer explicit opt-in. If backward compatibility wins, document that decision prominently and make sure every agent-facing path sets `EGGCALC_NO_CONFIG=1` or equivalent before importing/evaluating.
