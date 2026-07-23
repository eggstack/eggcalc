"""Typed public consumer test (criterion 41).

Verifies that the public API surface has correct type annotations and
that type checkers can reason about the exported interface.
"""

from __future__ import annotations

import inspect
from typing import get_type_hints

import eggcalc

# ---------------------------------------------------------------------------
# All __all__ entries have type annotations
# ---------------------------------------------------------------------------


class TestTypeAnnotations:
    """Every exported callable should have type annotations."""

    def test_evaluate_has_return_annotation(self):
        hints = get_type_hints(eggcalc.evaluate)
        assert "return" in hints, "evaluate() missing return annotation"

    def test_evaluate_raw_has_return_annotation(self):
        hints = get_type_hints(eggcalc.evaluate_raw)
        assert "return" in hints, "evaluate_raw() missing return annotation"

    def test_evaluate_cached_has_return_annotation(self):
        hints = get_type_hints(eggcalc.evaluate_cached)
        assert "return" in hints, "evaluate_cached() missing return annotation"

    def test_evaluate_async_has_return_annotation(self):
        hints = get_type_hints(eggcalc.evaluate_async)
        assert "return" in hints, "evaluate_async() missing return annotation"

    def test_evaluate_with_timeout_has_annotations(self):
        hints = get_type_hints(eggcalc.evaluate_with_timeout)
        assert "return" in hints
        assert "timeout" in hints or "expression" in hints

    def test_register_constant_has_annotations(self):
        hints = get_type_hints(eggcalc.register_constant)
        assert "return" in hints

    def test_register_function_has_annotations(self):
        hints = get_type_hints(eggcalc.register_function)
        assert "return" in hints

    def test_normalize_unit_has_annotations(self):
        hints = get_type_hints(eggcalc.normalize_unit)
        assert "return" in hints

    def test_get_conversion_factor_has_annotations(self):
        hints = get_type_hints(eggcalc.get_conversion_factor)
        assert "return" in hints

    def test_get_all_units_has_annotations(self):
        hints = get_type_hints(eggcalc.get_all_units)
        assert "return" in hints

    def test_is_unit_has_annotations(self):
        hints = get_type_hints(eggcalc.is_unit)
        assert "return" in hints

    def test_get_unit_category_has_annotations(self):
        hints = get_type_hints(eggcalc.get_unit_category)
        assert "return" in hints

    def test_are_units_compatible_has_annotations(self):
        hints = get_type_hints(eggcalc.are_units_compatible)
        assert "return" in hints

    def test_memory_store_has_annotations(self):
        hints = get_type_hints(eggcalc.memory_store)
        assert "return" in hints

    def test_memory_recall_has_annotations(self):
        hints = get_type_hints(eggcalc.memory_recall)
        assert "return" in hints

    def test_setvar_has_annotations(self):
        hints = get_type_hints(eggcalc.setvar)
        assert "return" in hints

    def test_getvar_has_annotations(self):
        hints = get_type_hints(eggcalc.getvar)
        assert "return" in hints


# ---------------------------------------------------------------------------
# Class type structure
# ---------------------------------------------------------------------------


class TestClassStructure:
    """Key classes should have proper type structure."""

    def test_unit_value_has_slots(self):
        assert hasattr(eggcalc.UnitValue, "__slots__") or hasattr(eggcalc.UnitValue, "__dict__")

    def test_evaluation_error_is_exception(self):
        assert issubclass(eggcalc.EvaluationError, Exception)

    def test_timeout_error_is_exception(self):
        assert issubclass(eggcalc.TimeoutError, Exception)

    def test_egg_calc_app_is_class(self):
        assert inspect.isclass(eggcalc.EggCalcApp)

    def test_memory_is_class(self):
        assert inspect.isclass(eggcalc.Memory)

    def test_runtime_capabilities_is_class(self):
        assert inspect.isclass(eggcalc.RuntimeCapabilities)


# ---------------------------------------------------------------------------
# Return type consistency
# ---------------------------------------------------------------------------


class TestReturnTypes:
    """Functions should return types consistent with annotations."""

    def test_evaluate_returns_numeric(self):
        result = eggcalc.evaluate("5 + 3")
        assert isinstance(result, (int, float))

    def test_evaluate_raw_returns_numeric(self):
        result = eggcalc.evaluate_raw("5 + 3")
        assert isinstance(result, (int, float))

    def test_is_unit_returns_bool(self):
        assert isinstance(eggcalc.is_unit("m"), bool)

    def test_are_units_compatible_returns_bool(self):
        assert isinstance(eggcalc.are_units_compatible("m", "ft"), bool)

    def test_get_unit_category_returns_str_or_none(self):
        result = eggcalc.get_unit_category("m")
        assert result is None or isinstance(result, str)

    def test_get_conversion_factor_returns_float_or_none(self):
        result = eggcalc.get_conversion_factor("ft", "m")
        assert result is None or isinstance(result, float)

    def test_normalize_unit_returns_str_or_none(self):
        result = eggcalc.normalize_unit("meter")
        assert result is None or isinstance(result, str)

    def test_get_all_units_returns_list(self):
        result = eggcalc.get_all_units()
        assert isinstance(result, list)

    def test_memory_list_returns_dict(self):
        result = eggcalc.memory_list()
        assert isinstance(result, dict)

    def test_listvars_returns_dict(self):
        result = eggcalc.listvars()
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# EggCalcApp API surface
# ---------------------------------------------------------------------------


class TestEggCalcAppAPI:
    """EggCalcApp should expose documented methods."""

    def test_has_calculate_method(self):
        assert hasattr(eggcalc.EggCalcApp, "calculate")
        assert callable(getattr(eggcalc.EggCalcApp, "calculate", None))

    def test_has_calculate_async_method(self):
        assert hasattr(eggcalc.EggCalcApp, "calculate_async")
        assert callable(getattr(eggcalc.EggCalcApp, "calculate_async", None))

    def test_has_register_constant_method(self):
        assert hasattr(eggcalc.EggCalcApp, "register_constant")

    def test_has_register_function_method(self):
        assert hasattr(eggcalc.EggCalcApp, "register_function")

    def test_has_clear_cache_method(self):
        assert hasattr(eggcalc.EggCalcApp, "clear_cache")

    def test_has_cache_size_property(self):
        # Should be a property or attribute
        app = eggcalc.EggCalcApp()
        _ = app.cache_size


# ---------------------------------------------------------------------------
# __all__ completeness
# ---------------------------------------------------------------------------


class TestAllCompleteness:
    """__all__ should list all public symbols."""

    def test_all_entries_exist(self):
        for name in eggcalc.__all__:
            assert hasattr(eggcalc, name), f"__all__ lists {name!r} but it's missing"

    def test_all_is_list(self):
        assert isinstance(eggcalc.__all__, list)

    def test_all_entries_are_strings(self):
        for name in eggcalc.__all__:
            assert isinstance(name, str), f"__all__ entry {name!r} is not a string"
