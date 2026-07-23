"""Typed external consumer fixture.

Imports the documented public API and exercises evaluation, normalization,
units, CLI compatibility exports, and capabilities under strict typing.
Passes against both source installs and wheel builds.
"""

from __future__ import annotations

from typing import Any

import eggcalc
from eggcalc import (
    DEFAULT_CACHE_SIZE,
    MAX_EXPONENT,
    MAX_FACTORIAL,
    MAX_INPUT_LENGTH,
    MAX_NESTING_DEPTH,
    MAX_RESULT_VALUE,
    NORMALIZE,
    PATTERNS,
    EggCalcApp,
    EvaluationError,
    RuntimeCapabilities,
    UnitValue,
    are_units_compatible,
    clearvars,
    delvar,
    detect_capabilities,
    evaluate,
    evaluate_async,
    evaluate_cached,
    evaluate_raw,
    evaluate_with_timeout,
    get_all_units,
    get_conversion_factor,
    get_default_evaluator,
    get_unit_category,
    getvar,
    is_unit,
    listvars,
    load_user_config,
    main,
    memory_add,
    memory_clear,
    memory_list,
    memory_recall,
    memory_store,
    memory_subtract,
    normalize_expression,
    normalize_text,
    normalize_unit,
    print_help,
    register_constant,
    register_function,
    run,
    setvar,
)

# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


class TestEvaluateTyped:
    def test_evaluate_int(self) -> None:
        result: int | float = evaluate("2 + 3")
        assert result == 5

    def test_evaluate_float(self) -> None:
        result = evaluate("2.5 * 4")
        assert result == 10.0

    def test_evaluate_raw_nl(self) -> None:
        result = evaluate_raw("five plus three")
        assert result == 8

    def test_evaluate_cached(self) -> None:
        result = evaluate_cached("10 + 20")
        assert result == 30

    def test_evaluate_with_timeout(self) -> None:
        result = evaluate_with_timeout("7 * 6", timeout=5.0)
        assert result == 42

    def test_evaluate_error(self) -> None:
        try:
            evaluate("1 / 0")
            raise AssertionError("Should have raised")
        except (EvaluationError, ZeroDivisionError):
            pass

    def test_evaluate_async(self) -> None:
        import asyncio

        async def _run() -> Any:
            return await evaluate_async("2 ** 10")

        result = asyncio.run(_run())
        assert result == 1024


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------


class TestNormalizeTyped:
    def test_normalize_expression(self) -> None:
        expr, code = normalize_expression("five plus three")
        assert isinstance(expr, str)
        assert "+" in expr
        assert isinstance(code, int)

    def test_normalize_text(self) -> None:
        result = normalize_text("five plus three", NORMALIZE, PATTERNS)
        assert isinstance(result, str)
        assert "+" in result

    def test_run(self) -> None:
        result, code = run("five plus three", NORMALIZE, PATTERNS)
        assert result == 8
        assert isinstance(code, int)

    def test_max_input_length(self) -> None:
        assert isinstance(MAX_INPUT_LENGTH, int)
        assert MAX_INPUT_LENGTH > 0

    def test_max_nesting_depth(self) -> None:
        assert isinstance(MAX_NESTING_DEPTH, int)
        assert MAX_NESTING_DEPTH > 0


# ---------------------------------------------------------------------------
# Units
# ---------------------------------------------------------------------------


class TestUnitsTyped:
    def test_unit_value(self) -> None:
        u: UnitValue = UnitValue(1, "m")
        assert u.value == 1

    def test_convert_to(self) -> None:
        u = UnitValue(1, "m")
        ft = u.convert_to("ft")
        assert ft.value > 3

    def test_normalize_unit(self) -> None:
        result: str = normalize_unit("metre")
        assert result == "m"

    def test_is_unit(self) -> None:
        assert is_unit("m") is True
        assert is_unit("xyzzy") is False

    def test_get_conversion_factor(self) -> None:
        factor = get_conversion_factor("km", "m")
        assert factor is not None
        assert factor == 1000

    def test_get_unit_category(self) -> None:
        cat: str = get_unit_category("m")
        assert cat == "length"

    def test_are_units_compatible(self) -> None:
        assert are_units_compatible("m", "ft") is True
        assert are_units_compatible("m", "kg") is False

    def test_get_all_units(self) -> None:
        units = get_all_units()
        assert isinstance(units, (list, set, frozenset))
        assert len(units) > 0

    def test_float_epsilon(self) -> None:
        assert isinstance(eggcalc.FLOAT_EPSILON, float)
        assert eggcalc.FLOAT_EPSILON >= 0


# ---------------------------------------------------------------------------
# CLI compatibility exports
# ---------------------------------------------------------------------------


class TestCLIExportsTyped:
    def test_main_callable(self) -> None:
        assert callable(main)

    def test_print_help_callable(self) -> None:
        assert callable(print_help)

    def test_run_callable(self) -> None:
        assert callable(run)


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------


class TestCapabilitiesTyped:
    def test_detect_capabilities(self) -> None:
        caps: RuntimeCapabilities = detect_capabilities()
        assert isinstance(caps.python_version, tuple)
        assert len(caps.python_version) == 3
        assert isinstance(caps.platform, str)
        assert isinstance(caps.eggcalc_version, str)
        assert isinstance(caps.supported_protocol_versions, tuple)
        assert len(caps.supported_protocol_versions) > 0
        assert isinstance(caps.mode, str)

    def test_capabilities_to_dict(self) -> None:
        caps = detect_capabilities()
        d: dict[str, object] = caps.to_dict()
        assert "python_version" in d
        assert "platform" in d
        assert "supported_protocol_versions" in d

    def test_capabilities_to_json(self) -> None:
        import json

        caps = detect_capabilities()
        j: str = caps.to_json()
        parsed = json.loads(j)
        assert "python_version" in parsed

    def test_version_matches(self) -> None:
        assert eggcalc.__version__  # non-empty
        caps = detect_capabilities()
        # When installed, version should match; from source may be "unknown"
        if caps.eggcalc_version != "unknown":
            assert caps.eggcalc_version == eggcalc.__version__


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class TestConfigTyped:
    def test_load_user_config_callable(self) -> None:
        assert callable(load_user_config)

    def test_get_default_evaluator(self) -> None:
        ev = get_default_evaluator()
        assert ev is not None

    def test_register_constant(self) -> None:
        # register_constant stores in evaluator CONSTANTS dict, not via setvar
        register_constant("typed_consumer_test_const", 42)
        # Just verify it doesn't raise; the constant is in the evaluator

    def test_register_function(self) -> None:
        # register_function stores in evaluator FUNCTIONS dict, not via setvar
        register_function("typed_consumer_test_fn", lambda x: x + 1)
        # Just verify it doesn't raise

    def test_setvar_getvar_delvar(self) -> None:
        setvar("typed_test_var", 99)
        assert getvar("typed_test_var") == 99
        delvar("typed_test_var")


# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------


class TestMemoryTyped:
    def test_memory_store_recall(self) -> None:
        memory_store(123.0, "M")
        assert memory_recall("M") == 123.0
        memory_clear()

    def test_memory_add_subtract(self) -> None:
        memory_store(10.0, "M")
        memory_add(5.0, "M")
        assert memory_recall("M") == 15.0
        memory_subtract(3.0, "M")
        assert memory_recall("M") == 12.0
        memory_clear()

    def test_memory_list(self) -> None:
        memory_store(1.0, "M")
        result = memory_list()
        assert isinstance(result, (dict, list))
        memory_clear()


# ---------------------------------------------------------------------------
# Variables
# ---------------------------------------------------------------------------


class TestVariablesTyped:
    def test_listvars(self) -> None:
        result: dict[str, Any] = listvars()
        assert isinstance(result, dict)

    def test_clearvars(self) -> None:
        setvar("typed_cv", 1)
        clearvars()
        # After clear, typed_cv should be gone
        try:
            getvar("typed_cv")
        except (AttributeError, KeyError):
            pass


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestConstantsTyped:
    def test_max_exponent(self) -> None:
        assert isinstance(MAX_EXPONENT, int)

    def test_max_factorial(self) -> None:
        assert isinstance(MAX_FACTORIAL, int)

    def test_max_result_value(self) -> None:
        assert isinstance(MAX_RESULT_VALUE, (int, float))

    def test_default_cache_size(self) -> None:
        assert isinstance(DEFAULT_CACHE_SIZE, int)

    def test_egg_calc_app(self) -> None:
        app = EggCalcApp(cache_size=64)
        result = app.calculate("2 + 2")
        assert result == 4


# ---------------------------------------------------------------------------
# Protocol versions
# ---------------------------------------------------------------------------


class TestProtocolVersionsTyped:
    def test_capabilities_has_protocol_versions(self) -> None:
        caps = detect_capabilities()
        for v in caps.supported_protocol_versions:
            assert isinstance(v, str)
            assert "-" in v  # e.g. "2024-11-05"


# ---------------------------------------------------------------------------
# Module-level exports
# ---------------------------------------------------------------------------


class TestModuleExportsTyped:
    def test_all_list_is_list_of_strings(self) -> None:
        assert isinstance(eggcalc.__all__, list)
        for name in eggcalc.__all__:
            assert isinstance(name, str)

    def test_version_is_string(self) -> None:
        assert isinstance(eggcalc.__version__, str)

    def test_author_is_string(self) -> None:
        assert isinstance(eggcalc.__author__, str)
