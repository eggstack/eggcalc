"""Regression tests for safe configuration loading.

Verifies that:
- ``import eggcalc`` does NOT execute cwd-local Python
- ``evaluate()`` does NOT load cwd config (direct AST only)
- ``evaluate_raw()`` does NOT load cwd config by default
- ``EGGCALC_LOAD_CONFIG=1`` enables lazy config loading for library APIs
- CLI startup loads config by default
- ``EGGCALC_NO_CONFIG=1`` disables CLI config loading
- MCP server never loads cwd config
- ``load_user_config()`` explicitly loads cwd config
"""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

PYTHON = sys.executable
REPO_ROOT = str(Path(__file__).resolve().parent.parent)


def _write_sentinel_config(tmp_path: Path, marker_name: str = "loaded.txt") -> Path:
    """Write a malicious eggcalc_config.py that creates a sentinel file."""
    marker = tmp_path / marker_name
    marker_str = str(marker).replace("\\", "\\\\")
    (tmp_path / "eggcalc_config.py").write_text(
        "from pathlib import Path\n"
        f"Path({marker_str!r}).write_text('loaded')\n"
        "CUSTOM_CONSTANTS = {'myconst': 123}\n"
    )
    return marker


def _run_in_cwd(
    args: list[str],
    cwd: Path,
    env: dict[str, str] | None = None,
    timeout: float = 15.0,
) -> subprocess.CompletedProcess[str]:
    """Run a command in a subprocess with the given cwd and env."""
    run_env = os.environ.copy()
    run_env["PYTHONPATH"] = REPO_ROOT
    run_env.pop("EGGCALC_LOAD_CONFIG", None)
    run_env.pop("EGGCALC_NO_CONFIG", None)
    if env:
        run_env.update(env)
    return subprocess.run(
        args,
        cwd=str(cwd),
        env=run_env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


# ---------------------------------------------------------------------------
# C01: import eggcalc must NOT trigger load_user_config
# ---------------------------------------------------------------------------
class TestImportDoesNotLoadConfig:
    """import eggcalc must not execute cwd-local Python."""

    def test_init_no_load_user_config_call(self):
        """__init__.py must not contain a bare load_user_config() call at module level."""
        init_source = importlib.util.find_spec("eggcalc").origin
        with open(init_source) as f:
            lines = f.readlines()

        in_def_or_class = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(("def ", "class ")):
                in_def_or_class = True
            elif not line.startswith((" ", "\t")) and not stripped.startswith("#"):
                in_def_or_class = False

            if not in_def_or_class and stripped == "load_user_config()":
                pytest.fail(
                    "load_user_config() is called at module level in __init__.py. "
                    "Library import must not execute cwd-local Python."
                )

    def test_import_does_not_execute_cwd_config_subprocess(self, tmp_path):
        """Importing eggcalc from a dir with malicious config must not execute it."""
        marker = _write_sentinel_config(tmp_path)
        result = _run_in_cwd(
            [PYTHON, "-c", "import eggcalc"],
            cwd=tmp_path,
        )
        assert result.returncode == 0, f"import failed: {result.stderr}"
        assert not marker.exists(), "Sentinel file created — import executed cwd-local config"


# ---------------------------------------------------------------------------
# C02: evaluate() must NOT load cwd config (direct AST evaluation)
# ---------------------------------------------------------------------------
class TestEvaluateNoConfig:
    """evaluate() performs direct AST evaluation and never loads cwd config."""

    def test_evaluate_does_not_execute_cwd_config_subprocess(self, tmp_path):
        """evaluate('2+2') must not trigger config loading from cwd."""
        marker = _write_sentinel_config(tmp_path)
        result = _run_in_cwd(
            [PYTHON, "-c", "from eggcalc import evaluate; assert evaluate('2+2') == 4"],
            cwd=tmp_path,
        )
        assert result.returncode == 0, f"evaluate failed: {result.stderr}"
        assert not marker.exists(), "Sentinel file created — evaluate() loaded cwd config"


# ---------------------------------------------------------------------------
# C03: evaluate_raw() must NOT load cwd config without opt-in
# ---------------------------------------------------------------------------
class TestEvaluateRawNoConfig:
    """evaluate_raw() does not load cwd config by default."""

    def test_evaluate_raw_does_not_execute_cwd_config_subprocess(self, tmp_path):
        """evaluate_raw('five plus three') must not trigger config loading."""
        marker = _write_sentinel_config(tmp_path)
        result = _run_in_cwd(
            [
                PYTHON,
                "-c",
                "from eggcalc import evaluate_raw; assert evaluate_raw('five plus three') == 8",
            ],
            cwd=tmp_path,
        )
        assert result.returncode == 0, f"evaluate_raw failed: {result.stderr}"
        assert (
            not marker.exists()
        ), "Sentinel file created — evaluate_raw() loaded cwd config without opt-in"

    def test_evaluate_raw_with_load_config_opt_in(self, tmp_path):
        """EGGCALC_LOAD_CONFIG=1 enables lazy config loading for evaluate_raw()."""
        marker = _write_sentinel_config(tmp_path)
        result = _run_in_cwd(
            [PYTHON, "-c", "from eggcalc import evaluate_raw; evaluate_raw('five plus three')"],
            cwd=tmp_path,
            env={"EGGCALC_LOAD_CONFIG": "1"},
        )
        assert result.returncode == 0, f"evaluate_raw failed: {result.stderr}"
        assert (
            marker.exists()
        ), "Sentinel file not created — EGGCALC_LOAD_CONFIG=1 did not enable config loading"


# ---------------------------------------------------------------------------
# C04: Explicit load_user_config() must load cwd config
# ---------------------------------------------------------------------------
class TestExplicitLoadConfig:
    """load_user_config() explicitly loads cwd config when called."""

    def test_explicit_load_user_config_executes_cwd_config_subprocess(self, tmp_path):
        """Calling load_user_config() directly must load cwd config."""
        marker = _write_sentinel_config(tmp_path)
        result = _run_in_cwd(
            [PYTHON, "-c", "from eggcalc import load_user_config; load_user_config()"],
            cwd=tmp_path,
        )
        assert result.returncode == 0, f"load_user_config failed: {result.stderr}"
        assert (
            marker.exists()
        ), "Sentinel file not created — load_user_config() did not load cwd config"


# ---------------------------------------------------------------------------
# C05: CLI loads config by default
# ---------------------------------------------------------------------------
class TestCLILoadsConfig:
    """CLI startup loads config by default."""

    def test_cli_loads_cwd_config_by_default_subprocess(self, tmp_path):
        """python -m eggcalc 'myconst' should see custom constant from cwd config."""
        marker = _write_sentinel_config(tmp_path)
        result = _run_in_cwd(
            [PYTHON, "-m", "eggcalc", "myconst"],
            cwd=tmp_path,
        )
        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert marker.exists(), "Sentinel file not created — CLI did not load cwd config"
        assert "123" in result.stdout, f"Expected '123' in output, got: {result.stdout}"

    def test_cli_no_config_env_blocks_cwd_config_subprocess(self, tmp_path):
        """EGGCALC_NO_CONFIG=1 prevents CLI from loading cwd config."""
        marker = _write_sentinel_config(tmp_path)
        result = _run_in_cwd(
            [PYTHON, "-m", "eggcalc", "2+2"],
            cwd=tmp_path,
            env={"EGGCALC_NO_CONFIG": "1"},
        )
        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert (
            not marker.exists()
        ), "Sentinel file created — EGGCALC_NO_CONFIG=1 did not block CLI config"


# ---------------------------------------------------------------------------
# C06: MCP hardening preserved
# ---------------------------------------------------------------------------
class TestMCPHardening:
    """MCP server config suppression behavior."""

    def test_server_no_import_time_env_mutation(self):
        """mcp/server.py does NOT set EGGCALC_NO_CONFIG at import time."""
        import subprocess

        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import os; before = dict(os.environ); "
                "import eggcalc.mcp.server; after = dict(os.environ); "
                "added = {k for k in after if k not in before}; "
                "print('\\n'.join(sorted(added)))",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert result.stdout.strip() == "", (
            f"Import added env vars: {result.stdout.strip()}"
        )

    def test_server_hard_sets_no_config_in_main(self):
        """mcp/server.py mcp_main() hard-sets EGGCALC_NO_CONFIG=1."""
        server_source_path = os.path.join(
            os.path.dirname(__file__), "..", "eggcalc", "mcp", "server.py"
        )
        with open(server_source_path) as f:
            content = f.read()

        assert 'os.environ["EGGCALC_NO_CONFIG"] = "1"' in content

    def test_package_mcp_blocks_cwd_config_subprocess(self, tmp_path):
        """MCP server mode must not load cwd config."""
        marker = _write_sentinel_config(tmp_path)
        result = _run_in_cwd(
            [
                PYTHON,
                "-c",
                "import os; os.environ['EGGCALC_NO_CONFIG'] = '1'; " "import eggcalc.mcp.server",
            ],
            cwd=tmp_path,
        )
        assert result.returncode == 0, f"MCP import failed: {result.stderr}"
        assert not marker.exists(), "Sentinel file created — MCP mode loaded cwd config"


# ---------------------------------------------------------------------------
# C07: _mcp_mode guard
# ---------------------------------------------------------------------------
class TestMCPModeGuard:
    """load_user_config() must not load config when _mcp_mode is True."""

    def test_mcp_mode_prevents_loading(self):
        """load_user_config() returns early when _mcp_mode is True."""
        import eggcalc.evaluator as ev

        old_mcp_mode = ev._mcp_mode
        old_config_loaded = ev._config_loaded
        ev._mcp_mode = True
        ev._config_loaded = False
        try:
            from eggcalc.evaluator import load_user_config

            load_user_config()
            assert ev._config_loaded is True
        finally:
            ev._mcp_mode = old_mcp_mode
            ev._config_loaded = old_config_loaded


# ---------------------------------------------------------------------------
# C08: EGGCALC_NO_CONFIG guard on load_user_config
# ---------------------------------------------------------------------------
class TestNoConfigEnvGuard:
    """load_user_config() respects EGGCALC_NO_CONFIG."""

    def test_load_user_config_no_config_env(self, monkeypatch):
        """load_user_config returns early when EGGCALC_NO_CONFIG is set."""
        monkeypatch.setenv("EGGCALC_NO_CONFIG", "1")
        import eggcalc.evaluator as ev

        old_config_loaded = ev._config_loaded
        ev._config_loaded = False
        try:
            from eggcalc.evaluator import load_user_config

            load_user_config()
            assert ev._config_loaded is True
        finally:
            ev._config_loaded = old_config_loaded


# ---------------------------------------------------------------------------
# C09: Import-error precision (Workstream F)
# ---------------------------------------------------------------------------
class TestImportErrorPrecision:
    """load_user_config must only suppress missing eggcalc_config, not errors inside it."""

    def test_syntax_error_in_config_propagates(self, tmp_path):
        """Syntax errors inside eggcalc_config.py must propagate."""
        (tmp_path / "eggcalc_config.py").write_text("def broken(\n")
        result = _run_in_cwd(
            [
                PYTHON,
                "-c",
                "from eggcalc.evaluator import load_user_config; load_user_config()",
            ],
            cwd=tmp_path,
        )
        assert result.returncode != 0
        assert "SyntaxError" in result.stderr

    def test_runtime_error_in_config_propagates(self, tmp_path):
        """Runtime exceptions inside eggcalc_config.py must propagate."""
        (tmp_path / "eggcalc_config.py").write_text("raise RuntimeError('config init failed')\n")
        result = _run_in_cwd(
            [
                PYTHON,
                "-c",
                "from eggcalc.evaluator import load_user_config; load_user_config()",
            ],
            cwd=tmp_path,
        )
        assert result.returncode != 0
        assert "RuntimeError" in result.stderr
        assert "config init failed" in result.stderr

    def test_missing_config_module_is_silent(self, tmp_path):
        """Missing eggcalc_config.py is silently ignored (no error)."""
        result = _run_in_cwd(
            [
                PYTHON,
                "-c",
                "from eggcalc.evaluator import load_user_config; load_user_config(); print('ok')",
            ],
            cwd=tmp_path,
        )
        assert result.returncode == 0
        assert "ok" in result.stdout

    def test_internal_import_error_in_config_propagates(self, tmp_path):
        """ImportError raised inside eggcalc_config.py must propagate."""
        (tmp_path / "eggcalc_config.py").write_text(
            "from nonexistent_module_xyz import something\n"
        )
        result = _run_in_cwd(
            [
                PYTHON,
                "-c",
                "from eggcalc.evaluator import load_user_config; load_user_config()",
            ],
            cwd=tmp_path,
        )
        assert result.returncode != 0
        assert "ModuleNotFoundError" in result.stderr or "ImportError" in result.stderr
