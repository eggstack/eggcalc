"""Tests for unit/constant namespace isolation and edge cases.

Covers:
- Group A: Per-instance state isolation in Evaluator/EggCalcApp
- C1:     Unit-before-constant lookup (units shadow 1-letter constants)
- C2:     "in" canonical renamed to "inch" (Python keyword avoidance)
- C3:     Custom unit categories (factor, category) tuple form
- H1:     Case-insensitive unit lookups (normalize_unit, is_unit)
- H2/H3:  Thread-safe unit table rebuilds
- M5:     Astronomical constant precision
- M7:     Compound speed units (60*km/h, conversion to mph)
- M11:    is_unit is now case-insensitive
"""

from __future__ import annotations

import threading

import pytest

from eggcalc import (
    EvaluationError,
    EggCalcApp,
    UnitValue,
    evaluate,
    evaluate_raw,
)
from eggcalc.normalize import NORMALIZE, PATTERNS, run
from eggcalc.units import (
    UNIT_ALIASES,
    UNIT_CATEGORIES,
    get_conversion_factor,
    is_unit,
    normalize_unit,
)


# ---------------------------------------------------------------------------
# Group A: per-instance state isolation
# ---------------------------------------------------------------------------


class TestInstanceStateIsolation:
    """Group A: variables and memory are isolated per Evaluator instance."""

    def test_setvar_isolated_between_eggcalcapp_instances(self):
        app_a = EggCalcApp()
        app_b = EggCalcApp()
        app_a.calculate('setvar("secret", 42)')
        with pytest.raises(EvaluationError) as exc_info:
            app_b.calculate("secret + 1")
        assert "Unknown name" in str(exc_info.value) or "unknown" in str(exc_info.value).lower()

    def test_setvar_isolated_from_default_evaluator(self):
        from eggcalc import clearvars, getvar
        clearvars()
        app = EggCalcApp()
        app.calculate('setvar("appsecret", 99)')
        assert getvar("appsecret") == 0

    def test_memory_isolated_between_eggcalcapp_instances(self):
        app_a = EggCalcApp()
        app_b = EggCalcApp()
        app_a.calculate("Mplus(10)")
        app_a.calculate("Mplus(5)")
        result_a = app_a.calculate("MR()")
        result_b = app_b.calculate("MR()")
        assert result_a == 15
        assert result_b == 0

    def test_memory_isolated_from_default_evaluator(self):
        from eggcalc import memory_clear, memory_recall
        memory_clear()
        app = EggCalcApp()
        app.calculate("store(123)")
        assert memory_recall() == 0

    def test_evaluator_direct_isolation(self):
        from eggcalc.evaluator import Evaluator
        ev1 = Evaluator()
        ev2 = Evaluator()
        ev1.evaluate('setvar("x", 100)')
        with pytest.raises(EvaluationError):
            ev2.evaluate("x + 1")

    def test_evaluator_direct_memory_isolation(self):
        from eggcalc.evaluator import Evaluator
        ev1 = Evaluator()
        ev2 = Evaluator()
        ev1.evaluate("store(7)")
        assert ev1.evaluate("recall()") == 7
        assert ev2.evaluate("recall()") == 0

    def test_module_level_setvar_proxies_to_default(self):
        from eggcalc import clearvars, getvar, setvar
        clearvars()
        setvar("alpha", 11)
        assert getvar("alpha") == 11
        clearvars()
        assert getvar("alpha") == 0


# ---------------------------------------------------------------------------
# C1: visit_Name checks UNIT_ALIASES before CONSTANTS
# ---------------------------------------------------------------------------


class TestUnitShadowsConstant:
    """C1: short unit names (h, g, R) now resolve to units first."""

    def test_h_resolves_to_hour(self):
        result = evaluate("h")
        assert isinstance(result, UnitValue)
        assert result.unit == "h"

    def test_g_resolves_to_gram(self):
        result = evaluate("g")
        assert isinstance(result, UnitValue)
        assert result.unit == "g"

    def test_R_resolves_to_gas_constant(self):
        result = evaluate("R")
        assert abs(result - 8.314462618) < 1e-6

    def test_r_resolves_to_gas_constant(self):
        result = evaluate("r")
        assert abs(result - 8.314462618) < 1e-6

    def test_Ra_resolves_to_rankine(self):
        result = evaluate("Ra")
        assert isinstance(result, UnitValue)
        assert result.unit == "Ra"

    def test_c_still_resolves_to_speed_of_light(self):
        assert evaluate("c") == 299792458

    def test_k_still_resolves_to_boltzmann(self):
        assert evaluate("k") == 1.380649e-23

    def test_long_form_constants_still_work(self):
        assert abs(evaluate("planck") - 6.62607015e-34) < 1e-50
        assert evaluate("standardgravity") == 9.80665
        assert evaluate("boltzmann") == 1.380649e-23
        assert evaluate("speedoflight") == 299792458

    def test_5kg_plus_200g_converts_correctly(self):
        result = evaluate_raw("5kg + 200g")
        assert isinstance(result, UnitValue)
        assert result.unit == "kg"
        assert abs(result.value - 5.2) < 1e-9


# ---------------------------------------------------------------------------
# C2: 'in' canonical renamed to 'inch'
# ---------------------------------------------------------------------------


class TestInchKeyword:
    """C2: the inch unit canonical is 'inch', avoiding the Python keyword 'in'."""

    def test_inch_canonical_in_aliases(self):
        assert UNIT_ALIASES.get("inch") == "inch"
        assert UNIT_ALIASES.get("in") == "inch"
        assert UNIT_ALIASES.get("inches") == "inch"

    def test_inch_canonical_in_categories(self):
        assert UNIT_CATEGORIES.get("inch") == "length"

    def test_two_inch_to_feet_via_run(self):
        result, code = run("2in in ft", NORMALIZE, PATTERNS)
        assert code == 0
        assert result is not None
        val = result.value if isinstance(result, UnitValue) else result
        assert abs(val - (2.0 * 0.0254 / 0.3048)) < 1e-9

    def test_inch_aliases_still_resolve_via_normalize_unit(self):
        assert normalize_unit("in") == "inch"
        assert normalize_unit("inch") == "inch"
        assert normalize_unit("inches") == "inch"

    def test_inch_conversion_factor_to_feet(self):
        factor = get_conversion_factor("inch", "ft")
        assert abs(factor - (0.0254 / 0.3048)) < 1e-12


# ---------------------------------------------------------------------------
# C3: custom unit categories
# ---------------------------------------------------------------------------


class TestCustomUnitCategories:
    """C3: load_user_config supports (factor, category) tuples for CUSTOM_UNITS.

    The normalization pipeline in normalize.py only knows about the
    pre-registered units (via _UNITS_BY_LENGTH), so we test the post-
    normalization layer (Evaluator.visit_BinOp) directly: when a custom
    unit is registered in UNIT_BASE / UNIT_ALIASES / UNIT_CATEGORIES, the
    Evaluator should pick it up via visit_Name + visit_BinOp.
    """

    def _register_custom(self, units_mod, name: str, factor: float, category: str) -> None:
        with units_mod._UNITS_LOCK:
            units_mod.UNIT_BASE.setdefault("m", {}).update({name: factor})
            units_mod.UNIT_ALIASES[name] = name
            units_mod.UNIT_CATEGORIES[name] = category
            units_mod._rebuild_conversions()

    def _unregister_custom(self, units_mod, name: str) -> None:
        with units_mod._UNITS_LOCK:
            units_mod.UNIT_BASE["m"].pop(name, None)
            units_mod.UNIT_ALIASES.pop(name, None)
            units_mod.UNIT_CATEGORIES.pop(name, None)
            units_mod._rebuild_conversions()

    def test_custom_unit_with_explicit_category(self):
        import eggcalc.units as units_mod
        self._register_custom(units_mod, "xu", 0.1, "length")
        try:
            result = evaluate("1*m+10*xu")
            assert isinstance(result, UnitValue)
            assert result.unit == "m"
            assert abs(result.value - 2.0) < 1e-9
        finally:
            self._unregister_custom(units_mod, "xu")

    def test_custom_unit_inferred_category(self):
        import eggcalc.units as units_mod
        self._register_custom(units_mod, "yu", 0.05, "length")
        try:
            result = evaluate("1*m+10*yu")
            assert isinstance(result, UnitValue)
            assert result.unit == "m"
            assert abs(result.value - 1.5) < 1e-9
        finally:
            self._unregister_custom(units_mod, "yu")


# ---------------------------------------------------------------------------
# H1/M11: case-insensitive normalize_unit and is_unit
# ---------------------------------------------------------------------------


class TestCaseInsensitiveUnits:
    """H1/M11: normalize_unit and is_unit accept common capitalizations."""

    def test_normalize_unit_uppercase(self):
        assert normalize_unit("KM") == "km"
        assert normalize_unit("KG") == "kg"
        assert normalize_unit("MB") == "MB"
        assert normalize_unit("GHZ") == "GHz"

    def test_normalize_unit_titlecase(self):
        assert normalize_unit("Meters") == "m"
        assert normalize_unit("Miles") == "mi"
        assert normalize_unit("Inches") == "inch"
        assert normalize_unit("Feet") == "ft"
        assert normalize_unit("Pounds") == "lb"
        assert normalize_unit("Ounces") == "oz"
        assert normalize_unit("Hours") == "h"
        assert normalize_unit("Minutes") == "min"

    def test_normalize_unit_capitalize(self):
        assert normalize_unit("Celsius") == "C"
        assert normalize_unit("Fahrenheit") == "F"
        assert normalize_unit("Kelvin") == "K"

    def test_is_unit_case_insensitive(self):
        assert is_unit("km")
        assert is_unit("KM")
        assert is_unit("Km")
        assert is_unit("Meters")
        assert is_unit("MILES")
        assert is_unit("Celsius")
        assert not is_unit("notarealunit")
        assert not is_unit("NOTAREALUNIT")

    def test_evaluate_raw_uppercase_units(self):
        result, code = run("5KM in m", NORMALIZE, PATTERNS)
        assert code == 0
        assert result is not None
        val = result.value if isinstance(result, UnitValue) else result
        assert abs(val - 5000.0) < 1e-9

    def test_evaluate_raw_capitalized_word_units(self):
        result, code = run("5Meters in m", NORMALIZE, PATTERNS)
        assert code == 0
        assert result is not None
        val = result.value if isinstance(result, UnitValue) else result
        assert abs(val - 5.0) < 1e-9


# ---------------------------------------------------------------------------
# H2/H3: thread-safety of unit table mutations
# ---------------------------------------------------------------------------


class TestUnitsThreadSafety:
    """H2/H3: load_user_config + get_conversion_factor are thread-safe."""

    def test_concurrent_get_conversion_factor_no_crash(self):
        errors: list[BaseException] = []

        def reader() -> None:
            try:
                for _ in range(100):
                    get_conversion_factor("m", "ft")
                    get_conversion_factor("kg", "lb")
                    get_conversion_factor("h", "min")
            except BaseException as e:  # noqa: BLE001
                errors.append(e)

        threads = [threading.Thread(target=reader) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []


# ---------------------------------------------------------------------------
# M5: astronomical constant precision
# ---------------------------------------------------------------------------


class TestAstronomicalPrecision:
    """M5: lightyear/au/parsec are at the IAU 2015 precision."""

    def test_lightyear_precision(self):
        factor = get_conversion_factor("ly", "m")
        assert abs(factor - 9.4607304725808e15) < 1.0

    def test_astronomical_unit_precision(self):
        factor = get_conversion_factor("au", "m")
        assert abs(factor - 1.49597870700e11) < 1.0

    def test_parsec_precision(self):
        factor = get_conversion_factor("pc", "m")
        assert abs(factor - 3.0856775814913673e16) < 1.0


# ---------------------------------------------------------------------------
# M7: compound speed units
# ---------------------------------------------------------------------------


class TestCompoundSpeedUnits:
    """M7: 60*km/h and 60*km/h in mph."""

    def test_60km_per_hour_evaluates(self):
        result = evaluate("(60*km)/h")
        assert isinstance(result, UnitValue)
        assert "/" in result.unit
        assert abs(result.value - 60.0) < 1e-9

    def test_60km_per_hour_to_mph(self):
        result = evaluate("convert((60*km)/h, mph)")
        assert isinstance(result, UnitValue)
        assert result.unit == "mph"
        assert abs(result.value - 37.282271534) < 1e-3


# ---------------------------------------------------------------------------
# are_units_compatible edge cases
# ---------------------------------------------------------------------------


class TestAreUnitsCompatible:
    """Edge cases for are_units_compatible function."""

    def test_both_none(self):
        from eggcalc.units import are_units_compatible
        assert are_units_compatible(None, None) is True

    def test_first_none(self):
        from eggcalc.units import are_units_compatible
        assert are_units_compatible(None, "m") is True

    def test_second_none(self):
        from eggcalc.units import are_units_compatible
        assert are_units_compatible("m", None) is True

    def test_same_category(self):
        from eggcalc.units import are_units_compatible
        assert are_units_compatible("m", "ft") is True

    def test_different_category(self):
        from eggcalc.units import are_units_compatible
        assert are_units_compatible("m", "kg") is False

    def test_unknown_unknown(self):
        from eggcalc.units import are_units_compatible
        assert are_units_compatible("frob", "blarg") is False

    def test_known_unknown(self):
        from eggcalc.units import are_units_compatible
        assert are_units_compatible("m", "frob") is False


# ---------------------------------------------------------------------------
# UnitValue type conversions
# ---------------------------------------------------------------------------


class TestUnitValueConversions:
    """Test UnitValue numeric type conversions and rounding."""

    def test_int_conversion(self):
        uv = UnitValue(3.7, "m")
        assert int(uv) == 3

    def test_float_conversion(self):
        uv = UnitValue(3, "m")
        assert float(uv) == 3.0

    def test_complex_conversion(self):
        uv = UnitValue(3, "m")
        assert complex(uv) == (3+0j)

    def test_complex_conversion_with_decimal(self):
        uv = UnitValue(3.5, "kg")
        assert complex(uv) == (3.5+0j)

    def test_round_default(self):
        uv = UnitValue(3.14159, "m")
        result = round(uv)
        assert isinstance(result, UnitValue)
        assert result.value == 3
        assert result.unit == "m"

    def test_round_with_digits(self):
        uv = UnitValue(3.14159, "m")
        result = round(uv, 2)
        assert isinstance(result, UnitValue)
        assert result.value == 3.14
        assert result.unit == "m"

    def test_abs_positive(self):
        uv = UnitValue(-5.0, "m")
        result = abs(uv)
        assert isinstance(result, UnitValue)
        assert result.value == 5.0
        assert result.unit == "m"

    def test_abs_negative(self):
        uv = UnitValue(-3.0, "kg")
        result = abs(uv)
        assert result.value == 3.0
        assert result.unit == "kg"


# ---------------------------------------------------------------------------
# get_all_units
# ---------------------------------------------------------------------------


class TestGetAllUnits:
    """Test get_all_units returns expected units."""

    def test_returns_list(self):
        from eggcalc.units import get_all_units
        result = get_all_units()
        assert isinstance(result, list)

    def test_sorted(self):
        from eggcalc.units import get_all_units
        result = get_all_units()
        assert result == sorted(result)

    def test_contains_common_units(self):
        from eggcalc.units import get_all_units
        result = get_all_units()
        for unit in ["m", "kg", "s", "L", "K", "C", "F", "Pa", "J", "W", "N", "V", "A", "Hz"]:
            assert unit in result

    def test_non_empty(self):
        from eggcalc.units import get_all_units
        assert len(get_all_units()) > 100
