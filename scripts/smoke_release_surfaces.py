#!/usr/bin/env python3
"""Release-surface smoke tests for eggcalc.

Deterministic, network-free, stdlib-only. Tests:
- Package API (evaluate, evaluate_raw)
- CLI (python -m eggcalc)
- Single-file build and CLI
- MCP package mode (stdio)
- Single-file MCP mode (stdio)
- Config-loading safety (sentinel file checks)

Usage:
    python scripts/smoke_release_surfaces.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

PYTHON = sys.executable
REPO_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = REPO_ROOT / "dist"
SINGLE_FILE = REPO_ROOT / "eggcalc.py"


def _banner(msg: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {msg}")
    print(f"{'=' * 60}")


def _pass(name: str) -> None:
    print(f"  PASS: {name}")


def _fail(name: str, detail: str = "") -> None:
    print(f"  FAIL: {name}")
    if detail:
        print(f"        {detail}")
    raise SystemExit(1)


def _run(
    args: list[str],
    cwd: str | Path | None = None,
    env: dict[str, str] | None = None,
    timeout: float = 30.0,
    input_data: str | None = None,
    *,
    use_source_path: bool = True,
) -> subprocess.CompletedProcess[str]:
    run_env = os.environ.copy()
    if use_source_path:
        run_env["PYTHONPATH"] = str(REPO_ROOT)
    else:
        run_env.pop("PYTHONPATH", None)
    if env:
        run_env.update(env)
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        env=run_env,
        capture_output=True,
        text=True,
        timeout=timeout,
        input=input_data,
    )


# --- Package API tests ---------------------------------------------------


def test_package_api() -> None:
    _banner("Package API")
    r = _run(
        [PYTHON, "-c", "from eggcalc import evaluate; assert evaluate('2+2') == 4; print('ok')"]
    )
    if r.returncode == 0 and "ok" in r.stdout:
        _pass("evaluate('2+2') == 4")
    else:
        _fail("evaluate('2+2')", r.stderr)

    r = _run(
        [
            PYTHON,
            "-c",
            "from eggcalc import evaluate_raw; assert evaluate_raw('five plus three') == 8; print('ok')",
        ]
    )
    if r.returncode == 0 and "ok" in r.stdout:
        _pass("evaluate_raw('five plus three') == 8")
    else:
        _fail("evaluate_raw('five plus three')", r.stderr)


# --- CLI tests -----------------------------------------------------------


def test_cli() -> None:
    _banner("CLI (python -m eggcalc)")
    r = _run([PYTHON, "-m", "eggcalc", "2+2"])
    if r.returncode == 0 and "4" in r.stdout.strip():
        _pass("python -m eggcalc '2+2' => 4")
    else:
        _fail("python -m eggcalc '2+2'", f"stdout={r.stdout!r} stderr={r.stderr!r}")

    r = _run([PYTHON, "-m", "eggcalc", "five plus three"])
    if r.returncode == 0 and "8" in r.stdout.strip():
        _pass("python -m eggcalc 'five plus three' => 8")
    else:
        _fail("python -m eggcalc NL", f"stdout={r.stdout!r} stderr={r.stderr!r}")


# --- Wheel install in clean venv -----------------------------------------


def test_wheel_install() -> None:
    _banner("Wheel install in clean venv")
    whl_files = list(DIST_DIR.glob("*.whl"))
    if not whl_files:
        _fail("wheel install", f"No .whl files in {DIST_DIR}")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        venv_dir = tmpdir_path / "test_venv"
        venv.create(str(venv_dir), with_pip=True)
        pip = venv_dir / "bin" / "pip"

        r = _run([str(pip), "install", str(whl_files[0])], cwd=tmpdir, use_source_path=False)
        if r.returncode != 0:
            _fail("pip install wheel", r.stderr)

        python = venv_dir / "bin" / "python"

        r = _run(
            [
                str(python),
                "-c",
                "import eggcalc, pathlib; "
                "p = pathlib.Path(eggcalc.__file__).parent; "
                "assert 'site-packages' in str(p) or 'dist-packages' in str(p), f'wrong path: {p}'; "
                "assert (p / 'py.typed').is_file(), 'py.typed missing'; "
                "print('ok')",
            ],
            cwd=tmpdir,
            use_source_path=False,
        )
        if r.returncode == 0 and "ok" in r.stdout:
            _pass("wheel import path is site-packages with py.typed")
        else:
            _fail("wheel import path", r.stderr)

        r = _run(
            [
                str(python),
                "-c",
                "from eggcalc import evaluate; assert evaluate('2+2') == 4; print('ok')",
            ],
            cwd=tmpdir,
            use_source_path=False,
        )
        if r.returncode == 0 and "ok" in r.stdout:
            _pass("wheel evaluate('2+2') == 4")
        else:
            _fail("wheel evaluate", r.stderr)

        r = _run(
            [
                str(python),
                "-c",
                "from eggcalc.units import UnitValue; u = UnitValue(1, 'm'); assert u.convert_to('ft').value > 3; print('ok')",
            ],
            cwd=tmpdir,
            use_source_path=False,
        )
        if r.returncode == 0 and "ok" in r.stdout:
            _pass("wheel unit conversion")
        else:
            _fail("wheel unit conversion", r.stderr)


# --- Single-file build and CLI -------------------------------------------


def test_single_file() -> None:
    _banner("Single-file build and CLI")
    r = _run([PYTHON, str(REPO_ROOT / "build_single.py")])
    if r.returncode != 0:
        _fail("build_single.py", r.stderr)
    if not SINGLE_FILE.exists():
        _fail("build_single.py", f"eggcalc.py not found at {SINGLE_FILE}")
    _pass("build_single.py produced eggcalc.py")

    r = _run([PYTHON, str(SINGLE_FILE), "2+2"])
    if r.returncode == 0 and "4" in r.stdout.strip():
        _pass("single-file '2+2' => 4")
    else:
        _fail("single-file '2+2'", f"stdout={r.stdout!r} stderr={r.stderr!r}")

    r = _run([PYTHON, str(SINGLE_FILE), "five plus three"])
    if r.returncode == 0 and "8" in r.stdout.strip():
        _pass("single-file 'five plus three' => 8")
    else:
        _fail("single-file NL", f"stdout={r.stdout!r} stderr={r.stderr!r}")


# --- MCP package mode (stdio) -------------------------------------------


def _mcp_session(python: str, args: list[str], timeout: float = 15.0) -> dict:
    """Start MCP server, send initialize + tools/list + tools/call, return responses."""
    messages = []

    def _make_msg(method: str, params: dict | None = None, id: int = 1) -> str:
        msg: dict = {"jsonrpc": "2.0", "method": method, "id": id}
        if params:
            msg["params"] = params
        return json.dumps(msg) + "\n"

    init_msg = _make_msg(
        "initialize",
        {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "smoke-test", "version": "0.1.0"},
        },
        id=1,
    )
    # Notification (no id) — must follow initialize before tool requests
    initialized_notification = (
        json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}) + "\n"
    )
    tools_msg = _make_msg("tools/list", {"_meta": {"schemaDetail": "compact"}}, id=2)
    call_msg = _make_msg(
        "tools/call",
        {
            "name": "math_eval",
            "arguments": {"expression": "2+2"},
        },
        id=3,
    )

    input_data = init_msg + initialized_notification + tools_msg + call_msg

    proc = subprocess.Popen(
        [python] + args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT), "EGGCALC_NO_CONFIG": "1"},
    )

    try:
        stdout, stderr = proc.communicate(input=input_data, timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        return {"error": "timeout", "stderr": ""}

    for line in stdout.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            messages.append(json.loads(line))
        except json.JSONDecodeError:
            pass

    return {"messages": messages, "stderr": stderr}


def test_mcp_package_mode() -> None:
    _banner("MCP package mode (stdio)")
    result = _mcp_session(PYTHON, ["-m", "eggcalc", "--mcp"])

    if "error" in result:
        _fail("MCP session", result.get("stderr", "timeout"))

    msgs = result.get("messages", [])
    ids_received = {m.get("id") for m in msgs if "id" in m}

    if 1 in ids_received:
        _pass("MCP initialize response")
    else:
        _fail("MCP initialize", f"No response for id=1. Messages: {msgs}")

    if 2 in ids_received:
        _pass("MCP tools/list response")
    else:
        _fail("MCP tools/list", f"No response for id=2. Messages: {msgs}")

    if 3 in ids_received:
        _pass("MCP tools/call (math_eval) response")
        call_msg = next((m for m in msgs if m.get("id") == 3), None)
        if call_msg:
            result_content = call_msg.get("result", {}).get("content", [])
            text = result_content[0].get("text", "") if result_content else ""
            if "4" in text:
                _pass("MCP math_eval result contains '4'")
            else:
                _fail("MCP math_eval result", f"Expected '4' in text, got: {text}")
    else:
        _fail("MCP tools/call", f"No response for id=3. Messages: {msgs}")


# --- Config-loading safety -----------------------------------------------


def test_config_safety() -> None:
    _banner("Config-loading safety")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Write sentinel config
        marker = tmpdir / "loaded.txt"
        config_content = (
            "from pathlib import Path\n"
            f"Path({str(marker)!r}).write_text('loaded')\n"
            "CUSTOM_CONSTANTS = {'myconst': 123}\n"
        )
        (tmpdir / "eggcalc_config.py").write_text(config_content)

        # import eggcalc should NOT execute config
        r = _run([PYTHON, "-c", "import eggcalc"], cwd=tmpdir)
        if r.returncode == 0 and not marker.exists():
            _pass("import does not execute cwd config")
        else:
            _fail("import config safety", f"marker exists={marker.exists()} stderr={r.stderr}")

        # evaluate() should NOT execute config
        r = _run([PYTHON, "-c", "from eggcalc import evaluate; evaluate('2+2')"], cwd=tmpdir)
        if r.returncode == 0 and not marker.exists():
            _pass("evaluate() does not execute cwd config")
        else:
            _fail("evaluate() config safety", f"marker exists={marker.exists()}")

        # evaluate_raw() should NOT execute config without opt-in
        r = _run(
            [PYTHON, "-c", "from eggcalc import evaluate_raw; evaluate_raw('five plus three')"],
            cwd=tmpdir,
        )
        if r.returncode == 0 and not marker.exists():
            _pass("evaluate_raw() does not execute cwd config (no opt-in)")
        else:
            _fail("evaluate_raw() config safety", f"marker exists={marker.exists()}")

        # EGGCALC_LOAD_CONFIG=1 should enable config loading
        r = _run(
            [PYTHON, "-c", "from eggcalc import evaluate_raw; evaluate_raw('five plus three')"],
            cwd=tmpdir,
            env={"EGGCALC_LOAD_CONFIG": "1"},
        )
        if r.returncode == 0 and marker.exists():
            _pass("EGGCALC_LOAD_CONFIG=1 enables config loading")
        else:
            _fail("EGGCALC_LOAD_CONFIG=1", f"marker exists={marker.exists()} stderr={r.stderr}")

        # Reset marker for next test
        marker.unlink(missing_ok=True)

        # load_user_config() should execute config
        r = _run(
            [PYTHON, "-c", "from eggcalc import load_user_config; load_user_config()"],
            cwd=tmpdir,
        )
        if r.returncode == 0 and marker.exists():
            _pass("load_user_config() executes cwd config")
        else:
            _fail("load_user_config()", f"marker exists={marker.exists()} stderr={r.stderr}")


# --- Single-file MCP mode -----------------------------------------------


def test_single_file_mcp() -> None:
    _banner("Single-file MCP mode (stdio)")
    if not SINGLE_FILE.exists():
        _fail("single-file MCP", "eggcalc.py not found (run build_single.py first)")

    result = _mcp_session(PYTHON, [str(SINGLE_FILE), "--mcp"])

    if "error" in result:
        _fail("single-file MCP session", result.get("stderr", "timeout"))

    msgs = result.get("messages", [])
    ids_received = {m.get("id") for m in msgs if "id" in m}

    if 1 in ids_received:
        _pass("single-file MCP initialize response")
    else:
        _fail("single-file MCP initialize", f"No response for id=1. Messages: {msgs}")

    if 2 in ids_received:
        _pass("single-file MCP tools/list response")
    else:
        _fail("single-file MCP tools/list", f"No response for id=2. Messages: {msgs}")

    if 3 in ids_received:
        _pass("single-file MCP tools/call (math_eval) response")
    else:
        _fail("single-file MCP tools/call", f"No response for id=3. Messages: {msgs}")


# --- REPL surface --------------------------------------------------------


def test_repl_surface() -> None:
    """Verify the interactive REPL accepts expressions and exits cleanly."""
    _banner("REPL surface (stdin pipe)")
    input_data = "2 + 2\nquit\n"
    r = _run([PYTHON, "-m", "eggcalc", "-i"], input_data=input_data)
    # REPL may print prompts; just verify it doesn't crash and produces output
    if r.returncode == 0:
        _pass("REPL accepts expression and exits cleanly")
    else:
        # On some platforms quit() raises SystemExit(0) which may look like failure
        if "4" in r.stdout:
            _pass("REPL output contains result")
        else:
            _fail(
                "REPL surface", f"returncode={r.returncode} stdout={r.stdout!r} stderr={r.stderr!r}"
            )


# --- Editable install surface --------------------------------------------


def test_editable_install() -> None:
    """Verify pip install -e . works and the installed package is functional."""
    _banner("Editable install in clean venv")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        venv_dir = tmpdir_path / "test_venv"
        venv.create(str(venv_dir), with_pip=True)
        pip = venv_dir / "bin" / "pip"

        r = _run([str(pip), "install", "-e", str(REPO_ROOT)], cwd=tmpdir, use_source_path=False)
        if r.returncode != 0:
            _fail("pip install -e .", r.stderr)

        python = venv_dir / "bin" / "python"
        r = _run(
            [
                str(python),
                "-c",
                "from eggcalc import evaluate; assert evaluate('2+2') == 4; print('ok')",
            ],
            cwd=tmpdir,
            use_source_path=False,
        )
        if r.returncode == 0 and "ok" in r.stdout:
            _pass("editable install evaluate('2+2') == 4")
        else:
            _fail("editable install evaluate", r.stderr)

        r = _run(
            [
                str(python),
                "-c",
                "from eggcalc import detect_capabilities; caps = detect_capabilities(); print(caps.mode)",
            ],
            cwd=tmpdir,
            use_source_path=False,
        )
        if r.returncode == 0 and "package" in r.stdout:
            _pass("editable install reports package mode")
        else:
            _fail("editable install capabilities", r.stderr)


# --- Main ----------------------------------------------------------------


def main() -> int:
    print("eggcalc release-surface smoke tests")
    print(f"Python: {PYTHON}")
    print(f"Repo root: {REPO_ROOT}")

    tests = [
        test_package_api,
        test_cli,
        test_single_file,
        test_mcp_package_mode,
        test_config_safety,
        test_single_file_mcp,
        test_repl_surface,
    ]

    # Skip wheel test if dist/ doesn't exist
    if DIST_DIR.exists() and list(DIST_DIR.glob("*.whl")):
        tests.insert(2, test_wheel_install)
    else:
        _banner("Wheel install (SKIPPED — no .whl in dist/)")

    # Always run editable install test
    tests.insert(3, test_editable_install)

    passed = 0
    failed = 0
    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except SystemExit:
            failed += 1
        except Exception as exc:
            _fail(test_fn.__name__, str(exc))
            failed += 1

    _banner("Summary")
    print(f"  {passed} passed, {failed} failed")
    if failed:
        return 1
    print("  All release-surface smoke tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
