# Release Polish Corrective Plan

## Context

This plan captures a targeted polish pass for `eggstack/eggcalc` after review of the current `main` branch. The repository is already in good working shape: it has standard-library-only packaging, a console-script entry point, CI across Python 3.10 through 3.14, lint/format/type checks, single-file build smoke coverage, AST-based evaluation, input/result limits, MCP-mode restrictions, cache accounting, and documented trust-boundary comments in code.

The remaining work is not a rewrite. The goal is to remove release-friction, tighten user-visible correctness claims, improve installer behavior, make documentation harder to drift, and add packaging validation. Treat this as a small corrective pass that should preserve current public behavior unless this plan explicitly calls out a change.

## Non-goals

Do not refactor the evaluator, normalizer, or unit registry into multiple modules during this pass. Those files are large, but splitting them now would create unnecessary regression risk.

Do not add runtime dependencies. The package’s no-dependency posture is a core property. Any Unicode or packaging validation work must use the Python standard library or dev-only tooling.

Do not change the CLI command name from `calc`.

Do not change the MCP protocol shape except where a documentation/tool-count parity test reveals a true mismatch.

## Priority 1: Grapheme correctness and documentation alignment

### Problem

`eggcalc/exact/primitives.py` exposes `count_graphemes()` and `truncate_to_grapheme()` as if they implement Unicode UAX #29 extended grapheme cluster rules. The implementation is a pragmatic approximation. The current comments claim that decomposed characters, emoji ZWJ sequences, and flags are counted as one grapheme, but the regional-indicator handling is likely wrong for odd-length RI runs and the implementation does not cover the full UAX #29 rule set.

This is user-visible because MCP docs describe `text_truncate` as truncating by grapheme clusters, meaning user-perceived characters. If the implementation is approximate, the docs should say so. If the docs keep claiming UAX #29 behavior, the implementation needs a more complete rule engine and test matrix.

### Preferred implementation

Use an explicit `best-effort` contract for now. Full UAX #29 support without dependencies is possible but not worth the risk for this release pass.

Update `eggcalc/exact/primitives.py` docstrings and any MCP documentation to describe these as approximate grapheme helpers that correctly handle common combining marks, variation selectors, many emoji ZWJ sequences, and regional-indicator flags, but are not a complete Unicode UAX #29 implementation.

Fix the regional-indicator logic so it counts RI pairs from the start of a run instead of pairing the next two RI characters after an already-consumed RI. Both `count_graphemes()` and `truncate_to_grapheme()` should share a helper or equivalent logic so count and truncation do not diverge.

Add tests for these cases:

```python
count_graphemes("a") == 1
count_graphemes("e\u0301") == 1
count_graphemes("🇺🇸") == 1
count_graphemes("🇺🇸🇨") == 2
count_graphemes("🇺🇸🇨🇦") == 2
truncate_to_grapheme("🇺🇸🇨", 1) == "🇺🇸"
truncate_to_grapheme("🇺🇸🇨", 2) == "🇺🇸🇨"
```

Add at least one test for a common ZWJ family emoji and one for variation-selector emoji. If the approximation does not handle a case, document the limitation and make the test assert the intended approximate behavior rather than a false UAX #29 guarantee.

### Files likely touched

`eggcalc/exact/primitives.py`

`tests/` grapheme/text primitive tests, likely an existing exact/primitives test file if present

`docs/mcp.md`

`README.md`

### Acceptance criteria

The docs no longer claim full UAX #29 compliance unless tests cover the expected behavior.

Regional-indicator odd-run behavior is fixed.

Count and truncate semantics are consistent for RI runs.

The new tests fail on the current implementation and pass after the fix.

No runtime dependency is added.

## Priority 2: MCP tool-count and docs parity

### Problem

`README.md` and `docs/mcp.md` claim the MCP server exposes 64 deterministic tools. Static numbers drift easily. The code has already changed across releases, and the changelog notes expansion from 59 to 64 tools. Without a parity check, the documentation can silently go stale.

### Implementation

Find the MCP tool registry or handler that backs `calc --mcp` / `tools/list`. Add a test that obtains the authoritative tool list from code and asserts either:

1. the documented count matches the registry count, or
2. the docs no longer contain a fixed numeric count.

The cleaner option is to remove the exact number from prose and replace it with phrasing such as “dozens of deterministic tools,” then keep the exact count in generated output or tests only. If a fixed number is retained, put it behind one source of truth.

Add a lightweight MCP smoke test that runs the tool-list path without invoking a long-lived subprocess when possible. If subprocess is necessary, keep it short and deterministic: start `python -m eggcalc --mcp`, send one JSON-RPC `tools/list` request, close stdin, and assert the response contains `math_eval` plus representative text/json/path tools.

### Files likely touched

`docs/mcp.md`

`README.md`

MCP server/registry files under `eggcalc/` once located

`tests/` MCP tests

### Acceptance criteria

Documentation cannot drift on the MCP tool count unnoticed.

The tool-list smoke test verifies the MCP server path, not only direct Python functions.

`math_eval` remains present.

The MCP determinism claim is qualified if any listed tool is intentionally nondeterministic or stateful outside MCP mode.

## Priority 3: Installer behavior and PATH cleanup

### Problem

`install.py` modifies shell profiles and then spawns an interactive shell after successful install. That behavior is surprising and hostile to scripted use. It should not happen by default.

`remove_from_path()` is harder than necessary to reason about because it looks for the export line and then tries to skip a following marker, while install writes the marker before the export line. The current behavior may remove orphan markers in practice, but the implementation/comment mismatch is fragile.

### Implementation

Change `install_calc()` so it never spawns an interactive shell by default. Add an explicit optional flag if this behavior should remain available:

```bash
python install.py --install --spawn-shell
```

Default post-install output should simply print the installed path and a clear instruction to open a new shell or run the displayed export command for the current session.

Simplify `remove_from_path()` to remove the exact two-line block written by `add_to_path()`:

```text
# Added by eggcalc install
export PATH="<install_dir>:$PATH"
```

Also remove older orphaned exact export lines for compatibility. Avoid broad substring matching that could delete unrelated PATH modifications.

Review `_validate_shell_path()`. Keep a conservative guard, but update comments to specify the exact quoting model. Do not overfit; the main goal is to prevent direct shell-profile injection in the line this script writes.

Add tests around installer PATH mutation using temporary files or monkeypatched home/profile paths. If direct tests are hard because paths are currently embedded inside functions, factor small pure helpers for block insertion/removal and test those helpers.

### Files likely touched

`install.py`

`tests/` installer tests

`README.md` install section

### Acceptance criteria

`python install.py --install` does not spawn an interactive shell.

If `--spawn-shell` is added, it is opt-in and documented.

Uninstall removes the exact PATH block created by install.

Uninstall does not remove unrelated PATH lines.

Tests cover install block insertion and removal.

## Priority 4: Config trust-boundary documentation

### Problem

`load_user_config()` imports `eggcalc_config.py` from the current working directory. The code correctly documents that this is arbitrary code execution if an attacker can place a malicious file in CWD. This warning is mostly in code comments/docstrings. It should be visible in user-facing documentation, especially because the project exposes MCP server mode.

### Implementation

Add a short “Configuration trust boundary” or “Security notes” section to `README.md`, and consider a matching note in `docs/mcp.md`.

Required content:

`eggcalc_config.py` is Python code, not a data-only config file.

It is loaded from the current working directory in normal CLI/library mode unless disabled.

Do not run eggcalc from untrusted writable directories if config loading is enabled.

For server/MCP deployments, run from a controlled working directory and/or set `EGGCALC_NO_CONFIG=1`.

MCP mode already disables user config loading where applicable; verify the docs reflect actual behavior.

### Files likely touched

`README.md`

`docs/mcp.md`

Potentially `docs/` security-related page if one exists

### Acceptance criteria

A user deploying eggcalc as an MCP server can find the CWD config-loading risk without reading source.

Docs mention `EGGCALC_NO_CONFIG=1`.

Docs distinguish Python-code config from TOML/JSON-style inert configuration.

## Priority 5: Packaging and release CI validation

### Problem

CI currently does lint, format, single-file build, smoke test, pytest coverage, and mypy. It does not appear to validate the sdist/wheel artifacts or install from a built wheel in a clean environment. This leaves a gap between tests passing in editable mode and an actual PyPI release working.

### Implementation

Add dev-only build validation to CI. Preferred commands:

```bash
python -m pip install --upgrade pip build twine
python -m build
python -m twine check dist/*
```

Then create a clean venv, install the generated wheel, and smoke test:

```bash
python -m venv /tmp/eggcalc-wheel-smoke
/tmp/eggcalc-wheel-smoke/bin/python -m pip install dist/*.whl
/tmp/eggcalc-wheel-smoke/bin/calc "five plus two"
/tmp/eggcalc-wheel-smoke/bin/python - <<'PY'
from eggcalc import evaluate_raw, EggCalcApp
assert evaluate_raw("five plus two") == 7
assert EggCalcApp(cache_size=2).calculate("5+3") == 8
PY
```

Keep this in one Python version lane, preferably 3.12, to avoid excessive matrix cost. Lint/test across versions can remain as-is.

If `twine` and `build` are added only in CI commands, they do not need to become runtime dependencies. Optionally add them to the `dev` extra if the project wants local release validation symmetry.

### Files likely touched

`.github/workflows/ci.yml`

`pyproject.toml` optional `dev` dependencies if desired

Potentially `README.md` release/development docs

### Acceptance criteria

CI builds both sdist and wheel.

CI runs `twine check`.

CI installs from the wheel in a clean venv and validates the console script plus library imports.

No runtime dependencies are added.

## Priority 6: README install/docs polish

### Problem

The README opens with a source-install paragraph before the PyPI section, despite PyPI being the recommended path. It also refers to `$path` instead of `$PATH`. This is minor but gives the wrong first impression for a release-ready package.

### Implementation

Reorder the installation guidance:

1. PyPI / pipx or pip install
2. `python -m eggcalc` usage
3. editable source install
4. advanced single-file install via `install.py`

Use `$PATH` capitalization.

Mention that `install.py` builds a single-file executable and can modify shell profile PATH entries, so users who do not want profile edits should use `--no-path`.

Ensure examples remain consistent with the current CLI behavior: `calc`, `python -m eggcalc`, `--json`, `--mcp`, and `EggCalcApp`.

### Files likely touched

`README.md`

### Acceptance criteria

The first install path is the standard package install path.

The single-file installer is documented as optional/advanced.

No stale `$path` wording remains.

The README install section matches actual `install.py` flags after Priority 3.

## Priority 7: Optional post-release architecture note

### Problem

`evaluator.py`, `normalize.py`, and `units.py` are large. The changelog explicitly notes multi-thousand-line growth. This is not a blocker for this pass, but it should be tracked so future hardening does not keep increasing module size indefinitely.

### Implementation

Create a separate future-facing plan only if desired after this corrective pass. Do not fold the refactor into this release-polish work.

Potential future split:

`evaluator.py` into cache, state/memory, function registry, safe numeric helpers, AST visitor, timeout/subprocess helpers.

`normalize.py` into lexical preprocessing, word-number parsing, function normalization, unit preprocessing, validation, and CLI.

`units.py` into unit registry data, conversion helpers, `UnitValue`, display formatting, and custom-unit rebuild logic.

### Acceptance criteria

No broad refactor is performed in this pass.

A short future note may be added to `plans/` only after the release-polish pass is complete.

## Test plan

Run the existing suite:

```bash
ruff check eggcalc tests
black --check eggcalc tests
pytest tests/ -v --cov=eggcalc --cov-report=term
mypy eggcalc --ignore-missing-imports
python build_single.py
python eggcalc.py "5+3"
```

Run the new targeted tests:

```bash
pytest tests/ -v -k "grapheme or truncate or mcp or installer or wheel"
```

Run packaging validation:

```bash
python -m pip install --upgrade build twine
rm -rf dist build *.egg-info
python -m build
python -m twine check dist/*
python -m venv /tmp/eggcalc-wheel-smoke
/tmp/eggcalc-wheel-smoke/bin/python -m pip install dist/*.whl
/tmp/eggcalc-wheel-smoke/bin/calc "five plus two"
```

For MCP smoke validation, if implemented as a subprocess test, ensure it has a timeout and closes stdin cleanly so CI cannot hang.

## Rollout order

Start with grapheme tests and implementation because it is the only likely correctness bug. Next fix MCP/docs parity so public claims match behavior. Then fix installer behavior because it changes user workflow but should be low-risk. Then update security/install docs. Finish by adding packaging CI validation.

Keep commits small and reviewable:

1. `Fix approximate grapheme RI handling and tests`
2. `Align MCP tool docs with registry`
3. `Make installer shell spawning opt-in`
4. `Document config trust boundary`
5. `Add packaging artifact CI smoke checks`
6. `Polish README installation guidance`

## Definition of done

All existing tests pass.

New tests cover grapheme RI odd/even runs, truncation consistency, installer PATH cleanup, MCP tool-list parity, and package wheel smoke behavior.

CI validates editable tests, single-file build, and wheel/sdist artifacts.

README and MCP docs no longer overclaim grapheme support or hard-code drift-prone tool counts unless those counts are test-enforced.

Installer no longer opens an interactive shell by default.

The config trust boundary is documented for CLI/library and MCP/server deployments.
