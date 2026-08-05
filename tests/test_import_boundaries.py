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

    def test_cli_does_not_load_exact_on_import(self):
        """eggcalc.cli must NOT load exact tool modules at import time."""
        code = textwrap.dedent("""\
            import sys
            import eggcalc.cli
            exact_impls = [
                m for m in sys.modules
                if m.startswith("eggcalc.exact.") and m != "eggcalc.exact"
            ]
            assert not exact_impls, f"CLI loaded exact modules at import time: {exact_impls}"
        """)
        result = _run_import_check(code)
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"

    def test_cli_help_loads_no_exact_modules(self):
        """Invoking CLI help (--help) must not load any exact modules."""
        code = textwrap.dedent("""\
            import sys
            from eggcalc.cli import main
            sys.argv = ["calc", "--help"]
            main()
            exact_impls = [
                m for m in sys.modules
                if m.startswith("eggcalc.exact.") and m != "eggcalc.exact"
            ]
            assert not exact_impls, f"CLI help loaded exact modules: {exact_impls}"
        """)
        result = _run_import_check(code)
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"

    def test_calculator_only_loads_no_exact_modules(self):
        """A calculator-only invocation must not load any exact modules."""
        code = textwrap.dedent("""\
            import sys
            from eggcalc.cli import main
            sys.argv = ["calc", "5+3"]
            main()
            exact_impls = [
                m for m in sys.modules
                if m.startswith("eggcalc.exact.") and m != "eggcalc.exact"
            ]
            assert not exact_impls, f"Calculator invocation loaded exact modules: {exact_impls}"
        """)
        result = _run_import_check(code)
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"

    def test_text_command_loads_its_defining_module(self):
        """Invoking a text command loads only its defining exact module."""
        code = textwrap.dedent("""\
            import sys
            from eggcalc.cli import main
            sys.argv = ["calc", "inspect", "hello"]
            main()
            assert "eggcalc.exact.synthesis" in sys.modules, (
                f"inspect should load eggcalc.exact.synthesis. Modules: "
                f"{[m for m in sys.modules if 'eggcalc.exact' in m]}"
            )
        """)
        result = _run_import_check(code)
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"

    def test_text_command_does_not_load_unrelated_modules(self):
        """Invoking inspect must not load patch, shell, markdown, or config modules."""
        code = textwrap.dedent("""\
            import sys
            from eggcalc.cli import main
            sys.argv = ["calc", "inspect", "hello"]
            main()
            unrelated = [
                m for m in sys.modules
                if m in (
                    "eggcalc.exact.patch",
                    "eggcalc.exact.shell",
                    "eggcalc.exact.markdown",
                    "eggcalc.exact.config",
                )
            ]
            assert not unrelated, f"inspect loaded unrelated modules: {unrelated}"
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


class TestCommandRegistry:
    """Verify the declarative command registry is well-formed."""

    def test_no_duplicate_names(self):
        """Command names are unique across the registry."""
        code = textwrap.dedent("""\
            from eggcalc.cli import COMMANDS
            names = [c["name"] for c in COMMANDS]
            assert len(names) == len(set(names)), f"Duplicate names: {[n for n in names if names.count(n) > 1]}"
        """)
        result = _run_import_check(code)
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"

    def test_no_alias_collisions(self):
        """Command aliases don't collide with other command names."""
        code = textwrap.dedent("""\
            from eggcalc.cli import COMMANDS
            all_names = set()
            for c in COMMANDS:
                assert c["name"] not in all_names, f"Duplicate: {c['name']}"
                all_names.add(c["name"])
                for alias in c.get("aliases", ()):
                    assert alias not in all_names, f"Alias collision: {alias}"
                    all_names.add(alias)
        """)
        result = _run_import_check(code)
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"

    def test_all_handlers_resolvable(self):
        """Every handler name in the registry maps to a callable."""
        code = textwrap.dedent("""\
            from eggcalc.cli import COMMANDS, _get_handler
            for c in COMMANDS:
                h = c["handler"]
                handler = _get_handler(h)
                assert callable(handler), f"Handler {h!r} not callable"
        """)
        result = _run_import_check(code)
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"

    def test_all_commands_have_required_fields(self):
        """Every command spec has name, description, usage, min_args, handler."""
        code = textwrap.dedent("""\
            from eggcalc.cli import COMMANDS
            required = ("name", "description", "usage", "min_args", "handler")
            for c in COMMANDS:
                for field in required:
                    assert field in c, f"Command {c.get('name', '?')} missing {field}"
        """)
        result = _run_import_check(code)
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"


class TestDeferredExactImport:
    """Regression: deferred exact imports survive Python 3.11 collisions.

    Commit ec7816d changed MCP handler imports from package-level re-exports
    to explicit implementation submodules after Python 3.11 exposed
    module/function name collisions. These tests prove the fix holds.
    """

    def test_mcp_tool_handlers_callable(self):
        """Collision-prone handlers resolve and execute after deferred import."""
        code = textwrap.dedent("""\
            import sys
            # Force clean state
            for mod in list(sys.modules):
                if mod.startswith("eggcalc.mcp"):
                    del sys.modules[mod]
            # Populate package attributes through the same-named implementation
            # modules that triggered the Python 3.11 collision.
            import eggcalc.exact.identifier_inspect
            import eggcalc.exact.validate
            from eggcalc.mcp.server import TOOL_HANDLERS
            handler = TOOL_HANDLERS.get("identifier_inspect")
            assert handler is not None, "identifier_inspect handler not found"
            assert callable(handler), "identifier_inspect handler not callable"
            handler2 = TOOL_HANDLERS.get("validate_brackets")
            assert handler2 is not None, "validate_brackets handler not found"
            assert callable(handler2), "validate_brackets handler not callable"
            identifier_result = handler(["alpha", "beta"], check_confusables=False)
            brackets_result = handler2("([])")
            for result in (identifier_result, brackets_result):
                assert isinstance(result, dict)
                assert result.get("ok") is True
                assert result.get("tool")
                assert "result" in result
        """)
        result = _run_import_check(code)
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"

    def test_exact_module_not_loaded_at_mcp_startup(self):
        """import eggcalc.mcp must not eagerly load exact implementation modules."""
        code = textwrap.dedent("""\
            import sys
            for mod in list(sys.modules):
                if mod.startswith("eggcalc.mcp"):
                    del sys.modules[mod]
            import eggcalc.mcp
            exact_impls = [
                m for m in sys.modules
                if m.startswith("eggcalc.exact.") and m != "eggcalc.exact"
            ]
            assert not exact_impls, (
                f"MCP startup eagerly loaded exact modules: {exact_impls}"
            )
        """)
        result = _run_import_check(code)
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
