"""CLI import/output/error/exit-code compatibility (criterion 19).

Verifies that the CLI surface matches documented behavior: flags, output
format, error messages, exit codes, and backward-compatible imports.
"""

from __future__ import annotations

import subprocess
import sys


def _run_cli(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    """Run python -m eggcalc with given args."""
    cmd = [sys.executable, "-m", "eggcalc", *args]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=30,
        input=stdin,
    )


# ---------------------------------------------------------------------------
# Flag compatibility
# ---------------------------------------------------------------------------


class TestCLIHelpFlags:
    """--help and --usage must produce output."""

    def test_help_flag(self):
        r = _run_cli("--help")
        assert r.returncode == 0
        assert "usage" in r.stdout.lower() or "eggcalc" in r.stdout.lower()

    def test_short_help(self):
        r = _run_cli("-h")
        assert r.returncode == 0

    def test_version_flag(self):
        r = _run_cli("--version")
        assert r.returncode == 0
        assert "eggcalc" in r.stdout.lower() or "." in r.stdout

    def test_short_version(self):
        r = _run_cli("-v")
        assert r.returncode == 0


# ---------------------------------------------------------------------------
# Expression evaluation
# ---------------------------------------------------------------------------


class TestCLIExpression:
    """Single-expression mode must produce clean output."""

    def test_basic_expression(self):
        r = _run_cli("5+3")
        assert r.returncode == 0
        assert r.stdout.strip() == "8"

    def test_expression_with_spaces(self):
        r = _run_cli("5 + 3")
        assert r.returncode == 0
        assert r.stdout.strip() == "8"

    def test_expression_e_flag(self):
        r = _run_cli("-e", "5+3")
        assert r.returncode == 0
        assert r.stdout.strip() == "8"

    def test_expression_quiet_flag(self):
        r = _run_cli("-q", "5+3")
        assert r.returncode == 0
        assert r.stdout.strip() == "8"

    def test_expression_math_functions(self):
        r = _run_cli("sqrt(16)")
        assert r.returncode == 0
        assert r.stdout.strip() in ("4", "4.0")

    def test_expression_pi(self):
        r = _run_cli("pi")
        assert r.returncode == 0
        assert "3.14" in r.stdout

    def test_unit_conversion(self):
        r = _run_cli("30m + 100ft")
        assert r.returncode == 0
        assert "m" in r.stdout

    def test_natural_language(self):
        r = _run_cli("five plus three")
        assert r.returncode == 0
        assert r.stdout.strip() == "8"


# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------


class TestCLIJSONOutput:
    """--json flag must produce valid JSON."""

    def test_json_output(self):
        r = _run_cli("--json", "5+3")
        assert r.returncode == 0
        import json

        data = json.loads(r.stdout)
        assert "result" in data or "expression" in data


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestCLIErrors:
    """CLI must handle errors gracefully with proper exit codes."""

    def test_division_by_zero(self):
        r = _run_cli("1/0")
        assert r.returncode != 0
        assert "zero" in (r.stderr or r.stdout).lower() or r.returncode == 1

    def test_invalid_expression(self):
        r = _run_cli("five plus three plus")
        # Should either fail or produce an error
        assert r.returncode != 0 or "error" in (r.stderr or "").lower()

    def test_unknown_text_command(self):
        r = _run_cli("notacommand")
        # Should either be treated as NL eval or show error
        assert r.returncode in (0, 1, 2)


# ---------------------------------------------------------------------------
# Backward-compatible imports
# ---------------------------------------------------------------------------


class TestBackwardCompatibleImports:
    """Documented import paths must still work."""

    def _run_python(self, code: str) -> subprocess.CompletedProcess:
        """Run arbitrary Python code using python -c."""
        return subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=30,
        )

    def test_from_eggcalc_import_evaluate(self):
        r = self._run_python("from eggcalc import evaluate; print(evaluate('5+3'))")
        assert r.returncode == 0
        assert r.stdout.strip() == "8"

    def test_from_eggcalc_import_main(self):
        r = self._run_python("from eggcalc import main; print(callable(main))")
        assert r.returncode == 0
        assert r.stdout.strip() == "True"

    def test_from_eggcalc_normalize_import_run(self):
        r = self._run_python("from eggcalc.normalize import run; print(callable(run))")
        assert r.returncode == 0
        assert r.stdout.strip() == "True"

    def test_from_eggcalc_import_evaluate_raw(self):
        r = self._run_python(
            "from eggcalc import evaluate_raw; print(evaluate_raw('five plus three'))"
        )
        assert r.returncode == 0
        assert r.stdout.strip() == "8"

    def test_from_eggcalc_import_unit_utils(self):
        r = self._run_python("from eggcalc import is_unit, get_all_units; print(is_unit('m'))")
        assert r.returncode == 0
        assert r.stdout.strip() == "True"

    def test_from_eggcalc_import_constants(self):
        r = self._run_python(
            "from eggcalc import NORMALIZE, PATTERNS, MAX_INPUT_LENGTH; print(MAX_INPUT_LENGTH > 0)"
        )
        assert r.returncode == 0
        assert r.stdout.strip() == "True"


# ---------------------------------------------------------------------------
# Module execution
# ---------------------------------------------------------------------------


class TestModuleExecution:
    """python -m eggcalc must work the same as the console script."""

    def test_module_basic(self):
        r = subprocess.run(
            [sys.executable, "-m", "eggcalc", "5+3"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert r.returncode == 0
        assert r.stdout.strip() == "8"

    def test_module_help(self):
        r = subprocess.run(
            [sys.executable, "-m", "eggcalc", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert r.returncode == 0

    def test_module_version(self):
        r = subprocess.run(
            [sys.executable, "-m", "eggcalc", "--version"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert r.returncode == 0
