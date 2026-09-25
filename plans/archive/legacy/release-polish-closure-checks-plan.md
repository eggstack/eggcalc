# Release Polish Closure Checks Plan

## Context

The release-polish and follow-up implementation passes have resolved the major identified issues in `eggstack/eggcalc`: packaging CI now uses the correct `UnitValue.convert_to()` API, grapheme helper documentation now describes the implementation as best-effort rather than full UAX #29, the MCP tool inventory is internally checked, and installer PATH cleanup handles multiple exact eggcalc-managed entries.

Two closure gaps remain before treating the release-polish line as complete:

1. prove that the MCP stdio server path works with a timeout-bound `tools/list` smoke test; and
2. prove that the latest repository state has a clean local and/or GitHub Actions verification run.

This plan is intentionally narrow. Do not reopen broad refactors or documentation rewrites unless they are required to make these checks pass.

## Priority 0: Add or confirm MCP stdio `tools/list` smoke coverage

### Problem

The current registry and inventory tests verify that `TOOL_HANDLERS`, schemas, metadata, fixtures, and `docs/tool_inventory.md` agree. That is valuable, but it does not exercise the actual MCP stdio JSON-RPC server path invoked by users through `calc --mcp` or `python -m eggcalc --mcp`.

A release-ready MCP server should have at least one subprocess smoke test that starts the server, sends a `tools/list` request, receives a valid JSON-RPC response, and exits without hanging.

### Implementation steps

First inspect the current MCP server framing.

Search these files/terms:

```bash
rg "def main|--mcp|tools/list|jsonrpc|TOOL_HANDLERS|stdin|stdout" eggcalc tests docs
```

Identify how the MCP server reads requests:

- one JSON object per line over stdin;
- `Content-Length` framed MCP messages;
- custom loop around JSON-RPC payloads; or
- another stdio protocol variant.

Then add a test under `tests/`, preferably `tests/test_mcp_stdio_smoke.py`, that matches the actual framing.

### Preferred test behavior

The test should:

- invoke the same entry path a user would use, preferably `[sys.executable, "-m", "eggcalc", "--mcp"]`;
- send a single `tools/list` JSON-RPC request using the server’s real framing;
- read one response;
- assert the response is JSON-RPC-shaped;
- assert at least `math_eval` and `text_inspect` appear in returned tools;
- use a timeout so CI cannot hang;
- ensure the process terminates cleanly or is killed in a `finally` block.

### Example for newline-delimited JSON-RPC

Use this only if the server really expects one JSON object per line:

```python
import json
import subprocess
import sys


def test_mcp_tools_list_subprocess_smoke():
    request = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    proc = subprocess.run(
        [sys.executable, "-m", "eggcalc", "--mcp"],
        input=json.dumps(request) + "\n",
        text=True,
        capture_output=True,
        timeout=5,
        check=True,
    )
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    assert lines, proc.stderr
    payload = json.loads(lines[0])
    assert payload["jsonrpc"] == "2.0"
    assert payload["id"] == 1
    names = {tool["name"] for tool in payload["result"]["tools"]}
    assert "math_eval" in names
    assert "text_inspect" in names
```

### Example for MCP `Content-Length` framing

Use this style only if the server expects MCP header framing:

```python
import json
import subprocess
import sys


def _frame(payload: dict) -> bytes:
    body = json.dumps(payload).encode("utf-8")
    return b"Content-Length: " + str(len(body)).encode("ascii") + b"\r\n\r\n" + body


def test_mcp_tools_list_subprocess_smoke():
    request = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    proc = subprocess.Popen(
        [sys.executable, "-m", "eggcalc", "--mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        stdout, stderr = proc.communicate(_frame(request), timeout=5)
    finally:
        if proc.poll() is None:
            proc.kill()
    assert proc.returncode == 0, stderr.decode("utf-8", errors="replace")
    # Parse according to the server's response framing.
```

If the MCP server intentionally remains open after stdin closes, do not require return code zero. Kill the process after receiving the response and assert the response payload instead.

### Files likely touched

`tests/test_mcp_stdio_smoke.py`

Possibly a tiny MCP test helper if there is already a test utilities module

### Acceptance criteria

`pytest tests/ -v -k "mcp and smoke"` runs the new smoke test.

The test exercises a subprocess entry path, not direct imports only.

The test has a timeout and cannot hang CI indefinitely.

The returned tool list includes `math_eval` and `text_inspect`.

The test is included in normal `pytest tests/` execution.

## Priority 1: Verify local full-suite health on the current branch

### Problem

Connector-level GitHub status inspection did not show workflow runs for the latest release-polish implementation commit. This may be a connector limitation, a workflow trigger issue, or Actions not running for direct commits. Either way, closure needs an explicit verification artifact from a real test run.

### Local verification commands

Run from a clean checkout of the latest `main`:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
ruff check eggcalc tests
black --check eggcalc tests
pytest tests/ -v --cov=eggcalc --cov-report=term
mypy eggcalc --ignore-missing-imports
python build_single.py
python eggcalc.py "5+3"
```

Then run targeted closure checks:

```bash
pytest tests/ -v -k "mcp or tool_inventory or grapheme or truncate or install"
```

### Packaging verification commands

Run:

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

### Acceptance criteria

All lint, format, test, type-check, single-file, and packaging commands pass locally.

If any command fails, capture the exact failure and fix only the minimal issue needed to close the release-polish line.

## Priority 2: Confirm GitHub Actions actually runs on the latest commit

### Problem

The workflow file now includes both a matrix test job and a package job, but no workflow run was visible through connector inspection for the latest implementation commit. Release closure should not rely only on local checks.

### Implementation steps

Check the repository Actions tab or GitHub CLI output:

```bash
gh run list --repo eggstack/eggcalc --limit 10
```

Confirm that the latest commit SHA has a workflow run. If it does not, inspect `.github/workflows/ci.yml` triggers. Verify that it includes the intended event types, for example:

```yaml
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
```

If workflow triggers are missing or overly narrow, update them so pushes to `main` and PRs against `main` run CI.

If Actions is disabled for the repository, enable it or document that only local verification is currently available.

### Required GitHub Actions jobs

The final workflow run should include:

- matrix test job for Python 3.10, 3.11, 3.12, 3.13, and 3.14;
- lint and format checks;
- single-file build and smoke test;
- pytest coverage;
- mypy on Python 3.12;
- package job on Python 3.12;
- `python -m build`;
- `twine check dist/*`;
- wheel install in a clean venv;
- wheel smoke test using `UnitValue.convert_to()`.

### Acceptance criteria

A GitHub Actions run exists for the latest commit.

All jobs pass.

If a workflow run cannot be produced, the closure notes explicitly state why and include the successful local verification output instead.

## Priority 3: Record closure status in plans or changelog notes

### Problem

Several handoff plans now exist. Future maintainers need a simple marker that the release-polish line was closed and which commit passed verification.

### Implementation options

Prefer a short closure note in `plans/`, for example:

`plans/release-polish-closure-status.md`

Include:

- final commit SHA verified;
- local verification commands run;
- GitHub Actions run URL or run ID if available;
- any intentionally deferred items;
- explicit statement that no broad evaluator/normalizer refactor was attempted.

Do not edit `CHANGELOG.md` unless the project is preparing an actual version release. If a release is imminent, add a concise unreleased entry only after the tests pass.

### Acceptance criteria

There is a durable handoff note identifying the verified state.

Deferred items, if any, are explicit and non-blocking.

## Deferred non-blockers

These are not required to close this pass:

- rewriting the noisy prior commit message that expanded `$PATH`;
- splitting `evaluator.py`, `normalize.py`, or `units.py`;
- implementing complete Unicode UAX #29 segmentation;
- replacing the MCP inventory fixture with a generated docs pipeline.

## Definition of done

The repository has a timeout-bound MCP stdio `tools/list` smoke test.

The full local verification suite passes.

Packaging build, `twine check`, clean wheel install, console-script smoke, and library smoke pass.

A GitHub Actions run for the latest commit exists and passes, or the absence of Actions is explicitly documented with local verification evidence.

A closure status note records the final verified commit and any non-blocking deferrals.
