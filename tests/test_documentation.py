"""Verify documentation claims match implementation (criterion 50)."""

from __future__ import annotations

import inspect
import textwrap

# ---------------------------------------------------------------------------
# Public API surface
# ---------------------------------------------------------------------------


class TestPublicAPISurface:
    """Verify __all__ exports and function signatures match api.md claims."""

    def test_all_names_are_importable(self):
        import eggcalc

        for name in eggcalc.__all__:
            assert hasattr(eggcalc, name), f"__all__ contains {name!r} but not importable"

    def test_version_is_string(self):
        import eggcalc

        assert isinstance(eggcalc.__version__, str)
        assert eggcalc.__version__  # non-empty

    def test_author_is_string(self):
        import eggcalc

        assert isinstance(eggcalc.__author__, str)
        assert eggcalc.__author__  # non-empty

    def test_evaluate_callable(self):
        from eggcalc import evaluate

        assert callable(evaluate)
        sig = inspect.signature(evaluate)
        assert "expression" in sig.parameters

    def test_evaluate_raw_callable(self):
        from eggcalc import evaluate_raw

        assert callable(evaluate_raw)
        sig = inspect.signature(evaluate_raw)
        assert "expression" in sig.parameters

    def test_evaluate_cached_callable(self):
        from eggcalc import evaluate_cached

        assert callable(evaluate_cached)

    def test_evaluate_async_callable(self):
        from eggcalc import evaluate_async

        assert callable(evaluate_async)

    def test_evaluate_with_timeout_callable(self):
        from eggcalc import evaluate_with_timeout

        assert callable(evaluate_with_timeout)
        sig = inspect.signature(evaluate_with_timeout)
        assert "timeout" in sig.parameters

    def test_register_constant_callable(self):
        from eggcalc import register_constant

        assert callable(register_constant)

    def test_register_function_callable(self):
        from eggcalc import register_function

        assert callable(register_function)

    def test_get_default_evaluator_callable(self):
        from eggcalc import get_default_evaluator

        assert callable(get_default_evaluator)

    def test_load_user_config_callable(self):
        from eggcalc import load_user_config

        assert callable(load_user_config)

    def test_memory_functions_callable(self):
        from eggcalc import (
            memory_add,
            memory_clear,
            memory_list,
            memory_recall,
            memory_store,
            memory_subtract,
        )

        assert callable(memory_store)
        assert callable(memory_recall)
        assert callable(memory_add)
        assert callable(memory_subtract)
        assert callable(memory_clear)
        assert callable(memory_list)

    def test_variable_functions_callable(self):
        from eggcalc import clearvars, delvar, getvar, listvars, setvar

        assert callable(setvar)
        assert callable(getvar)
        assert callable(delvar)
        assert callable(listvars)
        assert callable(clearvars)

    def test_normalize_expression_callable(self):
        from eggcalc import normalize_expression

        assert callable(normalize_expression)

    def test_normalize_text_callable(self):
        from eggcalc import normalize_text

        assert callable(normalize_text)

    def test_run_callable(self):
        from eggcalc import run

        assert callable(run)

    def test_unit_utils_callable(self):
        from eggcalc import (
            are_units_compatible,
            get_all_units,
            get_conversion_factor,
            get_unit_category,
            is_unit,
            normalize_unit,
        )

        assert callable(normalize_unit)
        assert callable(get_conversion_factor)
        assert callable(get_all_units)
        assert callable(is_unit)
        assert callable(get_unit_category)
        assert callable(are_units_compatible)

    def test_egg_calc_app_class_exists(self):
        from eggcalc import EggCalcApp

        assert inspect.isclass(EggCalcApp)

    def test_evaluation_error_exists(self):
        from eggcalc import EvaluationError

        assert issubclass(EvaluationError, Exception)

    def test_timeout_error_exists(self):
        from eggcalc import TimeoutError as EggTimeout

        assert issubclass(EggTimeout, Exception)

    def test_unit_value_class_exists(self):
        from eggcalc import UnitValue

        assert inspect.isclass(UnitValue)

    def test_lazy_main_not_loaded_at_import(self):
        import sys

        before = set(sys.modules.keys())

        after = set(sys.modules.keys())
        loaded = after - before
        assert "eggcalc.cli" not in loaded, "CLI should not be loaded at import time"

    def test_lazy_main_accessible(self):
        from eggcalc import main

        assert callable(main)


# ---------------------------------------------------------------------------
# Security constants
# ---------------------------------------------------------------------------


class TestSecurityConstants:
    """Verify security constants match evaluator.md claims."""

    def test_max_exponent(self):
        from eggcalc import MAX_EXPONENT

        assert MAX_EXPONENT == 10000

    def test_max_factorial(self):
        from eggcalc import MAX_FACTORIAL

        assert MAX_FACTORIAL == 1000

    def test_max_nesting_depth(self):
        from eggcalc import MAX_NESTING_DEPTH

        assert MAX_NESTING_DEPTH == 100

    def test_max_result_value(self):
        from eggcalc import MAX_RESULT_VALUE

        assert MAX_RESULT_VALUE == 1e308

    def test_default_cache_size(self):
        from eggcalc import DEFAULT_CACHE_SIZE

        assert DEFAULT_CACHE_SIZE == 1024

    def test_max_input_length(self):
        from eggcalc import MAX_INPUT_LENGTH

        assert isinstance(MAX_INPUT_LENGTH, int)
        assert MAX_INPUT_LENGTH > 0

    def test_float_epsilon(self):
        from eggcalc import FLOAT_EPSILON

        assert FLOAT_EPSILON == 1e-10


# ---------------------------------------------------------------------------
# Unit registry claims
# ---------------------------------------------------------------------------


class TestUnitRegistryClaims:
    """Verify unit registry statistics match docs/release_6_evidence.md claims."""

    def test_unit_categories_covers_known_units(self):
        """UNIT_CATEGORIES must cover all base units and common aliases."""
        from eggcalc.units import UNIT_CATEGORIES

        # Core canonicals and common aliases must be present
        must_have = [
            "m",
            "km",
            "ft",
            "in",
            "mi",
            "kg",
            "g",
            "lb",
            "oz",
            "s",
            "ms",
            "min",
            "h",
            "d",
            "L",
            "mL",
            "gal",
            "J",
            "kJ",
            "cal",
            "W",
            "kW",
            "N",
            "Pa",
            "kPa",
            "atm",
            "psi",
            "V",
            "kV",
            "A",
            "mA",
            "Hz",
            "kHz",
            "B",
            "KB",
            "MB",
            "GB",
            "bps",
            "Mbps",
            "deg",
            "rad",
            "m/s",
            "km/h",
            "m2",
            "ft2",
            "K",
            "C",
            "F",
        ]
        for alias in must_have:
            assert alias in UNIT_CATEGORIES, f"Alias {alias!r} missing from UNIT_CATEGORIES"

    def test_unit_base_has_16_families(self):
        from eggcalc.units import UNIT_BASE

        assert len(UNIT_BASE) >= 16, f"Expected >= 16 families, got {len(UNIT_BASE)}"

    def test_temperature_conversions_all_4_units(self):
        from eggcalc.units import TEMPERATURE_CONVERSIONS

        units_in_conversions = set()
        for a, b in TEMPERATURE_CONVERSIONS:
            units_in_conversions.add(a)
            units_in_conversions.add(b)
        assert units_in_conversions == {"K", "C", "F", "Ra"}

    def test_registry_alias_count(self):
        from eggcalc.units import build_unit_registry

        reg = build_unit_registry()
        assert len(reg) >= 400, f"Expected >= 400 aliases, got {len(reg)}"

    def test_registry_canonical_count(self):
        from eggcalc.units import build_unit_registry

        reg = build_unit_registry()
        assert (
            len(reg.all_canonicals) >= 18
        ), f"Expected >= 18 canonicals, got {len(reg.all_canonicals)}"


# ---------------------------------------------------------------------------
# MCP tool count
# ---------------------------------------------------------------------------


class TestMCPToolClaims:
    """Verify MCP server tool counts match docs."""

    def test_tool_handler_count(self):
        from eggcalc.mcp.server import TOOL_HANDLERS

        assert len(TOOL_HANDLERS) >= 77, f"Expected >= 77 tools, got {len(TOOL_HANDLERS)}"

    def test_tool_schema_count_matches_handlers(self):
        from eggcalc.mcp.schemas import TOOL_SCHEMAS
        from eggcalc.mcp.server import TOOL_HANDLERS

        assert len(TOOL_SCHEMAS) == len(TOOL_HANDLERS)

    def test_profile_count(self):
        from eggcalc.mcp.schemas import TOOL_PROFILES

        assert len(TOOL_PROFILES) >= 11, f"Expected >= 11 profiles, got {len(TOOL_PROFILES)}"

    def test_protocol_versions(self):
        from eggcalc.mcp.server import SUPPORTED_PROTOCOL_VERSIONS

        assert "2024-11-05" in SUPPORTED_PROTOCOL_VERSIONS
        assert "2025-11-25" in SUPPORTED_PROTOCOL_VERSIONS


# ---------------------------------------------------------------------------
# Module import boundaries
# ---------------------------------------------------------------------------


class TestImportBoundaryClaims:
    """Verify import boundary claims from overview.md."""

    def test_units_no_eggcalc_deps(self):
        """units.py should not import from other eggcalc submodules."""
        import ast
        import pathlib

        src = pathlib.Path("eggcalc/units.py").read_text()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                mod = getattr(node, "module", None)
                if isinstance(node, ast.ImportFrom) and mod:
                    assert not mod.startswith("eggcalc."), f"units.py imports from {mod}"

    def test_evaluator_depends_on_units_only(self):
        """evaluator.py should import from units.py but not cli/normalize/exact."""
        import ast
        import pathlib

        src = pathlib.Path("eggcalc/evaluator.py").read_text()
        tree = ast.parse(src)
        forbidden = {"eggcalc.cli", "eggcalc.normalize", "eggcalc.exact"}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                mod = getattr(node, "module", None)
                if mod:
                    for f in forbidden:
                        assert not mod.startswith(f), f"evaluator.py imports from {mod}"


# ---------------------------------------------------------------------------
# Authority parity (criterion 32, 33, 44)
# ---------------------------------------------------------------------------


class TestVersionParity:
    """Package version must be consistent across pyproject.toml and __init__."""

    def test_pyproject_matches_init(self):
        import pathlib
        import re

        init_src = pathlib.Path("eggcalc/__init__.py").read_text()
        m = re.search(r'__version__\s*=\s*"([^"]+)"', init_src)
        assert m, "Could not find __version__ in __init__.py"
        init_version = m.group(1)

        pyproject = pathlib.Path("pyproject.toml").read_text()
        m2 = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)
        assert m2, "Could not find version in pyproject.toml"
        pyproject_version = m2.group(1)

        assert (
            init_version == pyproject_version
        ), f"Version mismatch: __init__={init_version!r}, pyproject={pyproject_version!r}"


class TestProtocolVersionParity:
    """Protocol versions must have one source in _protocol.py and be imported elsewhere."""

    def test_protocol_source_is_single_file(self):
        import pathlib
        import re

        proto_src = pathlib.Path("eggcalc/_protocol.py").read_text()
        m = re.search(r"SUPPORTED_PROTOCOL_VERSIONS.*?=.*?\(([^)]+)\)", proto_src)
        assert m, "Could not find SUPPORTED_PROTOCOL_VERSIONS in _protocol.py"
        proto_versions = tuple(
            v.strip().strip('"').strip("'")
            for v in m.group(1).split(",")
            if v.strip().strip('"').strip("'")
        )
        assert len(proto_versions) >= 2, f"Expected >=2 protocol versions, got {proto_versions}"

    def test_server_imports_from_protocol(self):
        import pathlib

        server_src = pathlib.Path("eggcalc/mcp/server.py").read_text()
        assert "from eggcalc._protocol import" in server_src

    def test_capabilities_imports_from_protocol(self):
        import pathlib

        caps_src = pathlib.Path("eggcalc/capabilities.py").read_text()
        assert "from ._protocol import" in caps_src

    def test_all_sources_agree(self):
        from eggcalc._protocol import SUPPORTED_PROTOCOL_VERSIONS as proto
        from eggcalc.capabilities import detect_capabilities

        caps = detect_capabilities()
        assert caps.supported_protocol_versions == proto


class TestPackageSingleFileParity:
    """Package and single-file must share the same unit/tool/command inventories."""

    def test_unit_registry_counts_match(self):
        """Unit alias and canonical counts must match between package and single-file."""
        import pathlib
        import subprocess
        import sys

        # Package counts
        from eggcalc.units import build_unit_registry

        reg = build_unit_registry()
        pkg_alias_count = len(reg.all_aliases)
        pkg_canonical_count = len(reg.all_canonicals)

        # Build single-file and query its counts via subprocess
        subprocess.run(
            [sys.executable, "build_single.py"],
            check=True,
            capture_output=True,
        )
        single_path = pathlib.Path("eggcalc.py")
        assert single_path.exists(), "eggcalc.py not found after build"

        code = textwrap.dedent("""\
            import importlib.util, sys
            spec = importlib.util.spec_from_file_location("eggcalc_single", "eggcalc.py")
            mod = importlib.util.module_from_spec(spec)
            sys.modules["eggcalc_single"] = mod
            spec.loader.exec_module(mod)
            from eggcalc.units import build_unit_registry
            reg = build_unit_registry()
            print(len(reg.all_aliases))
            print(len(reg.all_canonicals))
        """)
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Single-file query failed: {result.stderr}"
        lines = result.stdout.strip().split("\n")
        single_alias_count = int(lines[0])
        single_canonical_count = int(lines[1])

        assert (
            single_alias_count == pkg_alias_count
        ), f"Alias count mismatch: package={pkg_alias_count}, single-file={single_alias_count}"
        assert (
            single_canonical_count == pkg_canonical_count
        ), f"Canonical count mismatch: package={pkg_canonical_count}, single-file={single_canonical_count}"

    def test_tool_schema_counts_match(self):
        """MCP tool schema counts must match between package and single-file."""
        import pathlib
        import subprocess
        import sys

        # Package counts
        from eggcalc.mcp.tools import TOOL_SCHEMAS

        pkg_schema_count = len(TOOL_SCHEMAS)

        # Build single-file and query its counts via subprocess
        subprocess.run(
            [sys.executable, "build_single.py"],
            check=True,
            capture_output=True,
        )
        single_path = pathlib.Path("eggcalc.py")
        assert single_path.exists(), "eggcalc.py not found after build"

        code = textwrap.dedent("""\
            import importlib.util, sys
            spec = importlib.util.spec_from_file_location("eggcalc_single", "eggcalc.py")
            mod = importlib.util.module_from_spec(spec)
            sys.modules["eggcalc_single"] = mod
            spec.loader.exec_module(mod)
            from eggcalc.mcp.tools import TOOL_SCHEMAS
            print(len(TOOL_SCHEMAS))
        """)
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Single-file query failed: {result.stderr}"
        single_schema_count = int(result.stdout.strip())

        assert (
            single_schema_count == pkg_schema_count
        ), f"Schema count mismatch: package={pkg_schema_count}, single-file={single_schema_count}"
