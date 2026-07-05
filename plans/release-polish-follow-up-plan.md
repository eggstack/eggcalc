# Release Polish Follow-Up Plan

## Context

A release-polish implementation pass landed after `plans/release-polish-corrective-plan.md`. It addressed most of the intended scope: grapheme regional-indicator handling was refactored, MCP tool-count prose was moved into `docs/tool_inventory.md`, installer shell spawning became opt-in, config trust-boundary documentation was added, README install guidance was reordered, and a packaging CI job was added.

This follow-up plan covers the remaining closure items found in review of that implementation. The most important item is a newly introduced CI bug in the packaging smoke test. The rest are documentation precision, inventory consistency, and small hardening checks.

## Priority 0: Fix packaging CI smoke test failure

### Problem

The new packaging CI job installs the built wheel into a clean venv and then runs:

```bash
/tmp/test-venv/bin/python -c "from eggcalc.units import UnitValue; assert UnitValue(1, 'm').to('ft').value > 3, 'unit conversion failed'"
```

`UnitValue` does not expose `.to()`. The public conversion method is `.convert_to()`. As written, the packaging job should fail with `AttributeError` even though the package may otherwise be valid.

### Implementation

Update `.github/workflows/ci.yml` to use the real API:

```bash
/tmp/test-venv/bin/python -c "from eggcalc.units import UnitValue; assert UnitValue(1, 'm').convert_to('ft').value > 3, 'unit conversion failed'"
```

Consider using `evaluate_raw("1m in ft")` as an additional smoke path if the goal is to test the installed console/library path rather than the low-level `UnitValue` API alone:

```bash
/tmp/test-venv/bin/python - <<'PY'
from eggcalc import evaluate_raw
result = evaluate_raw("1m in ft")
assert "ft" in str(result)
assert float(str(result).split()[0]) > 3
PY
```

Keep the smoke test short. The package job is not a replacement for the full test matrix.

### Files likely touched

`.github/workflows/ci.yml`

### Acceptance criteria

The clean-wheel smoke test no longer calls a nonexistent method.

The package job validates wheel installation, basic library import, and at least one unit-conversion path.

The command remains portable on Linux CI.

## Priority 1: Weaken grapheme wording to match implementation scope

### Problem

`eggcalc/exact/primitives.py` now uses a shared `_advance_grapheme()` helper, which is a good structural improvement. It handles common combining-mark, ZWJ-emoji, and regional-indicator-pair cases. However, the docstring still says it handles GB9, GB11, and GB12/GB13 “per UAX #29.” That still overstates the implementation because it is not a complete extended grapheme cluster implementation.

This matters because downstream docs and MCP users may assume fully conformant Unicode segmentation.

### Implementation

Update the docstrings in `eggcalc/exact/primitives.py` to describe this as a dependency-free, best-effort subset. Suggested wording:

```python
"""Count approximate user-visible grapheme clusters.

This dependency-free helper handles common combining marks, variation
selectors, emoji ZWJ sequences, and regional-indicator flag pairs. It is
not a complete implementation of Unicode UAX #29 extended grapheme cluster
segmentation.
"""
```

Apply equivalent wording to `truncate_to_grapheme()` and any docs that call `text_truncate` “grapheme-aware.” Prefer “best-effort grapheme-aware” or “common grapheme sequence preserving.”

Update `docs/tool_inventory.md` row 50 if needed from “Grapheme-aware truncation” to “Best-effort grapheme-aware truncation.”

### Files likely touched

`eggcalc/exact/primitives.py`

`docs/mcp.md`

`docs/tool_inventory.md`

Potentially README text if it mentions grapheme semantics

### Acceptance criteria

No user-facing doc claims full UAX #29 compliance.

The public behavior remains unchanged.

Existing grapheme tests continue to pass.

## Priority 2: Verify and, if needed, complete grapheme test coverage

### Problem

The implementation commit claims to add 20 grapheme tests, but connector code search did not readily find the expected grapheme tests by simple query. Before treating this work as closed, verify the tests exist and are included in normal `pytest tests/` discovery.

### Implementation

Locate the test file that covers `count_graphemes()` and `truncate_to_grapheme()`.

At minimum, assert these cases:

```python
from eggcalc.exact.primitives import count_graphemes, truncate_to_grapheme

assert count_graphemes("a") == 1
assert count_graphemes("e\u0301") == 1
assert count_graphemes("🇺🇸") == 1
assert count_graphemes("🇺🇸🇨") == 2
assert count_graphemes("🇺🇸🇨🇦") == 2
assert truncate_to_grapheme("🇺🇸🇨", 1) == "🇺🇸"
assert truncate_to_grapheme("🇺🇸🇨", 2) == "🇺🇸🇨"
```

Also include one common emoji ZWJ sequence and one variation-selector sequence. If the helper intentionally approximates a case, test and document the chosen approximation.

If tests already exist, ensure their filenames match pytest discovery patterns (`test_*.py`) and are not accidentally skipped.

### Files likely touched

Existing or new `tests/test_*grapheme*.py`, `tests/test_*primitives*.py`, or equivalent

### Acceptance criteria

`pytest tests/ -k "grapheme or truncate"` runs the intended tests.

Regional-indicator odd/even runs are covered.

Count and truncate stay consistent.

The tests reflect the intentionally approximate contract, not a false full-UAX contract.

## Priority 3: Fix tool inventory internal inconsistency

### Problem

`docs/tool_inventory.md` now declares 64 total tools and says all 64 have tests. In the table, `version_compare` is marked `Tests: no`, while the summary says `Have tests | 64` and `Missing tests | 0`. Either the row is wrong, or the summary is wrong.

The current inventory test checks the total count and row count, but may not verify the internal yes/no summary counts.

### Implementation

Inspect the actual tests for `version_compare`.

If `version_compare` is tested, change the table row to `yes`.

If it is not tested, either add tests and keep the summary as 64/0, or change the summary to 63/1 and explicitly list the missing test. Prefer adding the missing test because this is a stable deterministic version utility and should have coverage.

Extend `tests/test_tool_inventory.py` so the summary counts in `docs/tool_inventory.md` are mechanically checked against the table rows. For example:

- parse the inventory table rows;
- count rows with `Tests | yes`;
- assert the “Have tests” summary equals that count;
- assert the “Missing tests” summary equals total minus that count.

Do the same for `README` and `docs/mcp.md` columns only if it remains simple and low-risk.

### Files likely touched

`docs/tool_inventory.md`

`tests/test_tool_inventory.py`

Potentially version tests if `version_compare` is genuinely missing coverage

### Acceptance criteria

The inventory row for `version_compare` and the summary table agree.

The inventory test catches future yes/no summary drift.

If `version_compare` lacked tests, it now has at least basic comparison coverage.

## Priority 4: Verify MCP subprocess smoke coverage

### Problem

The previous plan asked for a lightweight MCP `tools/list` smoke test. The implementation commit says one was added, but connector search did not readily find `tools/list` or subprocess MCP smoke coverage. The registry fixture tests are useful but not equivalent to exercising the stdio JSON-RPC server path.

### Implementation

Search the repo locally for `tools/list`, `--mcp`, `subprocess`, and MCP smoke tests.

If a subprocess smoke test exists, verify it:

- starts the installed/current Python module in MCP mode;
- sends a JSON-RPC `tools/list` request;
- closes stdin or terminates cleanly;
- uses a timeout;
- asserts `math_eval` and at least one non-math tool are present.

If it does not exist, add one. Keep it robust and short. Example structure:

```python
import json
import subprocess
import sys


def test_mcp_tools_list_subprocess_smoke():
    proc = subprocess.run(
        [sys.executable, "-m", "eggcalc", "--mcp"],
        input=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}) + "\n",
        text=True,
        capture_output=True,
        timeout=5,
        check=True,
    )
    payload = json.loads(proc.stdout.splitlines()[0])
    names = {tool["name"] for tool in payload["result"]["tools"]}
    assert "math_eval" in names
    assert "text_inspect" in names
```

Adjust output parsing to the actual server framing if needed.

### Files likely touched

MCP smoke test file under `tests/`

### Acceptance criteria

The MCP stdio path is tested, not only imported registries.

The test cannot hang indefinitely.

The test is included in default `pytest tests/`.

## Priority 5: Installer cleanup edge case

### Problem

`remove_from_path()` now matches the marker-first block written by `add_to_path()`, which is an improvement. It also handles a legacy exact export line without a preceding marker. However, the legacy branch is guarded by `and not found_export`, so if a shell profile contains both a marker block and an additional stale export-only line, only the first match will be removed.

This is minor, but cleanup should remove all exact eggcalc-managed PATH lines for the target install dir while preserving unrelated PATH lines.

### Implementation

Change `remove_from_path()` so it removes every exact marker/export block and every exact legacy export-only line for the target `install_dir`. Avoid broad substring matching that could remove unrelated custom PATH entries.

Add a test with this input:

```text
pre
# Added by eggcalc install
export PATH="/custom/bin:$PATH"
mid
export PATH="/custom/bin:$PATH"
post
```

Expected output should preserve `pre`, `mid`, `post` and remove both `/custom/bin` export lines plus the marker.

Also add a negative test preserving a different PATH line:

```text
export PATH="/other/bin:$PATH"
```

### Files likely touched

`install.py`

`tests/test_install.py`

### Acceptance criteria

All exact eggcalc-managed target PATH entries are removed.

Unrelated PATH entries are preserved.

Existing install/uninstall tests still pass.

## Priority 6: Clean up release-polish commit message note if desired

### Problem

The implementation commit message includes a local expanded `$PATH` string because `$PATH` was likely interpolated in the commit message. This does not affect code, but it is noisy in history.

### Recommendation

Do not rewrite public history unless this repository’s workflow permits force-push cleanup. If avoiding history rewrites, ignore it. Future commits should use quoted commit messages that prevent shell expansion, or avoid including `$PATH` in commit messages.

### Acceptance criteria

No code change required.

If history is not rewritten, note this as cosmetic only.

## Verification commands

Run the full normal suite:

```bash
ruff check eggcalc tests
black --check eggcalc tests
pytest tests/ -v --cov=eggcalc --cov-report=term
mypy eggcalc --ignore-missing-imports
python build_single.py
python eggcalc.py "5+3"
```

Run targeted tests:

```bash
pytest tests/ -v -k "grapheme or truncate or tool_inventory or mcp or install"
```

Run packaging validation locally:

```bash
python -m pip install --upgrade build twine
rm -rf dist build *.egg-info
python -m build
python -m twine check dist/*
python -m venv /tmp/eggcalc-wheel-smoke
/tmp/eggcalc-wheel-smoke/bin/python -m pip install dist/*.whl
/tmp/eggcalc-wheel-smoke/bin/calc "five plus two"
/tmp/eggcalc-wheel-smoke/bin/python - <<'PY'
from eggcalc import evaluate, evaluate_raw, EggCalcApp
from eggcalc.units import UnitValue
assert evaluate('2+2') == 4
assert evaluate_raw('five plus two') == 7
assert EggCalcApp(cache_size=2).calculate('5+3') == 8
assert UnitValue(1, 'm').convert_to('ft').value > 3
PY
```

Check GitHub Actions after pushing:

- confirm the matrix test job runs for Python 3.10 through 3.14;
- confirm the new package job runs;
- confirm the package job reaches the clean-wheel smoke test;
- confirm there are no skipped tests caused by bad file names or markers.

## Recommended commit order

1. `Fix wheel smoke test conversion API`
2. `Clarify approximate grapheme segmentation contract`
3. `Close tool inventory summary drift`
4. `Add or verify MCP stdio smoke test`
5. `Tighten installer PATH cleanup edge case`

Keep these as small commits so a CI failure can be traced to one concern.

## Definition of done

The package CI job no longer calls nonexistent APIs.

All GitHub Actions jobs run and pass on the final commit.

No docs claim full UAX #29 grapheme compliance.

Grapheme count/truncate tests cover RI odd/even cases and common emoji/variation cases.

`docs/tool_inventory.md` is internally consistent and tested for future drift.

The MCP stdio `tools/list` path has a timeout-bound smoke test.

Installer PATH cleanup removes all exact eggcalc-managed target entries without touching unrelated PATH lines.
