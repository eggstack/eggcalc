"""Import boundary tests for Release 6 architecture.

Verifies that the import graph respects module boundaries:
- Core imports (import eggcalc, from eggcalc import evaluate) do not load
  exact-tool implementations or MCP modules.
- Evaluator and units do not import CLI dispatch.
- CLI dispatch (eggcalc.cli) loads exact tools only when invoked.
- Normalization (eggcalc.normalize) does not import argparse, exact, or MCP.

These tests run as subprocess checks to ensure clean import states.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap


def _run_import_check(code: str, timeout: int = 15) -> subprocess.CompletedProcess:
    """Run a Python import check in a fresh subprocess."""
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


class TestCoreImportBoundaries:
    """Verify that core imports don't pull in exact or MCP modules."""

    def test_import_eggcalc_no_exact(self):
        """import eggcalc must not load any eggcalc.exact.* implementation modules."""
        code = textwrap.dedent("""\
            import sys
            import eggcalc
            exact_mods = [m for m in sys.modules if m.startswith("eggcalc.exact.")]
            # Allow eggcalc.exact itself (the package __init__), but not submodules
            impl_mods = [m for m in exact_mods if m != "eggcalc.exact"]
            assert not impl_mods, f"Unexpected exact modules loaded: {impl_mods}"
        """)
        result = _run_import_check(code)
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"

    def test_import_eggcalc_no_mcp(self):
        """import eggcalc must not load any eggcalc.mcp.* modules."""
        code = textwrap.dedent("""\
            import sys
            import eggcalc
            mcp_mods = [m for m in sys.modules if m.startswith("eggcalc.mcp")]
            assert not mcp_mods, f"Unexpected MCP modules loaded: {mcp_mods}"
        """)
        result = _run_import_check(code)
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"

    def test_import_evaluate_no_cli(self):
        """from eggcalc import evaluate must not load CLI dispatch."""
        code = textwrap.dedent("""\
            import sys
            from eggcalc import evaluate
            # cli module should not be loaded by core imports
            assert "eggcalc.cli" not in sys.modules, (
                f"eggcalc.cli loaded unexpectedly. Modules: "
                f"{[m for m in sys.modules if 'cli' in m]}"
            )
        """)
        result = _run_import_check(code)
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"

    def test_evaluator_no_argparse(self):
        """eggcalc.evaluator must not import argparse."""
        code = textwrap.dedent("""\
            import sys
            import eggcalc.evaluator
            # argparse should not be loaded by evaluator
            assert "argparse" not in sys.modules, (
                "argparse loaded by evaluator"
            )
        """)
        result = _run_import_check(code)
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"

    def test_units_no_argparse(self):
        """eggcalc.units must not import argparse."""
        code = textwrap.dedent("""\
            import sys
            import eggcalc.units
            assert "argparse" not in sys.modules, (
                "argparse loaded by units"
            )
        """)
        result = _run_import_check(code)
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"


class TestNormalizeBoundaries:
    """Verify that normalization module has correct import boundaries."""

    def test_normalize_no_argparse(self):
        """eggcalc.normalize must not import argparse (moved to cli)."""
        code = textwrap.dedent("""\
            import sys
            import eggcalc.normalize
            assert "argparse" not in sys.modules, (
                "argparse loaded by normalize"
            )
        """)
        result = _run_import_check(code)
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"

    def test_normalize_no_exact_imports(self):
        """eggcalc.normalize must not import exact-tool implementation modules."""
        code = textwrap.dedent("""\
            import sys
            import eggcalc.normalize
            exact_impls = [
                m for m in sys.modules
                if m.startswith("eggcalc.exact.") and m != "eggcalc.exact"
            ]
            assert not exact_impls, f"Unexpected exact modules loaded: {exact_impls}"
        """)
        result = _run_import_check(code)
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"


class TestCLIBoundaries:
    """Verify that CLI module loads correctly and has expected boundaries."""

    def test_cli_loads_exact_on_import(self):
        """eggcalc.cli imports exact tools at module level (needed for text commands)."""
        code = textwrap.dedent("""\
            import sys
            import eggcalc.cli
            # cli imports exact tools at the top level for text commands
            exact_impls = [
                m for m in sys.modules
                if m.startswith("eggcalc.exact.") and m != "eggcalc.exact"
            ]
            assert exact_impls, "CLI should load exact tools at import time"
        """)
        result = _run_import_check(code)
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"

    def test_cli_has_main(self):
        """eggcalc.cli exposes main() entry point."""
        code = textwrap.dedent("""\
            from eggcalc.cli import main
            assert callable(main)
        """)
        result = _run_import_check(code)
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"

    def test_backward_compat_main_from_normalize(self):
        """from eggcalc.normalize import main still works (re-export)."""
        code = textwrap.dedent("""\
            from eggcalc.normalize import main
            assert callable(main)
        """)
        result = _run_import_check(code)
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"

    def test_backward_compat_print_help_from_normalize(self):
        """from eggcalc.normalize import print_help still works (re-export)."""
        code = textwrap.dedent("""\
            from eggcalc.normalize import print_help
            assert callable(print_help)
        """)
        result = _run_import_check(code)
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"


class TestPackageAPI:
    """Verify documented public API remains importable."""

    def test_all_core_exports(self):
        """All documented __all__ exports are importable from eggcalc."""
        code = textwrap.dedent("""\
            import eggcalc
            for name in eggcalc.__all__:
                assert hasattr(eggcalc, name), f"Missing export: {name}"
        """)
        result = _run_import_check(code)
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"

    def test_evaluate_works(self):
        """Basic evaluation works through the public API."""
        code = textwrap.dedent("""\
            from eggcalc import evaluate
            result = evaluate("5 + 3")
            assert result == 8
        """)
        result = _run_import_check(code)
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"

    def test_evaluate_raw_works(self):
        """Natural language evaluation works through the public API."""
        code = textwrap.dedent("""\
            from eggcalc import evaluate_raw
            result = evaluate_raw("five plus three")
            assert result == 8
        """)
        result = _run_import_check(code)
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"


class TestReverseImportOrder:
    """Verify that importing in various orders doesn't break."""

    def test_import_exact_then_evaluate(self):
        """Importing exact modules first doesn't break evaluation."""
        code = textwrap.dedent("""\
            import eggcalc.exact
            from eggcalc import evaluate
            assert evaluate("2 + 2") == 4
        """)
        result = _run_import_check(code)
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"

    def test_import_cli_then_evaluate(self):
        """Importing cli first doesn't break evaluation."""
        code = textwrap.dedent("""\
            import eggcalc.cli
            from eggcalc import evaluate
            assert evaluate("2 + 2") == 4
        """)
        result = _run_import_check(code)
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
