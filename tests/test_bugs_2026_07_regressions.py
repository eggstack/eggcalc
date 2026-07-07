"""
Regression tests for the 2026-07 bugs.md findings.

Each test class locks in the post-fix behavior described in bugs.md:
  - B1: compound unit exponentiation
  - B2: mult/div of compatible units
  - B3: convert() robustness against non-string target units
  - B4: absolute temperature addition across scales
  - B5: floor/mod on compatible units (precision-safe, correct unit)
  - B6: "convert X to Y" NL phrase normalization
  - B7: caret `^` is exponentiation (xor words → bitxor())
  - B8: setvar/getvar string-arg preservation across name collisions
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("EGGCALC_NO_CONFIG", "1")


# ---------------------------------------------------------------------------
# B1: (1*m/s)**2 must distribute over the whole compound unit.
# ---------------------------------------------------------------------------
class TestCompoundUnitExponentiation:
    """evaluator.py / units.py: exponentiation must apply across a compound unit."""

    def test_velocity_squared_evaluator(self):
        from eggcalc.evaluator import evaluate_raw

        r = evaluate_raw("(1*m/s)**2")
        assert isinstance(r, type(evaluate_raw("(1*m/s)**2")))  # sanity
        assert abs(r.value - 1) < 1e-12
        assert r.unit == "m**2/s**2"

    def test_velocity_squared_value(self):
        from eggcalc.evaluator import evaluate_raw

        r = evaluate_raw("(2*m/s)**2")
        assert abs(r.value - 4) < 1e-12
        assert r.unit == "m**2/s**2"

    def test_velocity_squared_convert(self):
        from eggcalc.evaluator import evaluate_raw

        r = evaluate_raw("convert((1*m/s)**2, m**2/s**2)")
        assert abs(r.value - 1) < 1e-12
        assert r.unit == "m**2/s**2"

    def test_unitvalue_pow_compound(self):
        from eggcalc.units import UnitValue

        r = UnitValue(3, "m/s") ** 2
        assert abs(r.value - 9) < 1e-12
        assert r.unit == "m**2/s**2"


# ---------------------------------------------------------------------------
# B2: mult/div of compatible units must convert via scale factors.
# ---------------------------------------------------------------------------
class TestCompatibleUnitArithmetic:
    """evaluator.py: dividing or multiplying same-dimension units cancels dimension."""

    def test_meters_divided_by_cm(self):
        from eggcalc.evaluator import evaluate_raw

        r = evaluate_raw("(1*m)/(1*cm)")
        # Dimensionless ratio: 1 m / 1 cm = 100.
        assert not isinstance(r, (int, float)) or r == 100
        # Evaluating through the AST path returns a dimensionless number;
        # the unit may be None or a dimensionless wrapping.
        assert getattr(r, "value", r) == 100

    def test_meters_times_cm(self):
        from eggcalc.evaluator import evaluate_raw

        r = evaluate_raw("(1*m)*(1*cm)")
        # 1 m * 1 cm = 0.01 m**2.
        assert abs(getattr(r, "value", r) - 0.01) < 1e-12
        # The result unit should be a square-meter form, not a symbolic cm*m.
        unit = getattr(r, "unit", "m**2") or "m**2"
        assert unit in ("m**2", "m2")

    def test_cm_times_m_converts(self):
        from eggcalc.evaluator import evaluate_raw

        r = evaluate_raw("convert(1*m*1*cm, m2)")
        # 1 m * 1 cm = 1e-2 m**2 = 0.01 m**2
        assert abs(getattr(r, "value", r) - 0.01) < 1e-12


# ---------------------------------------------------------------------------
# B3: convert() must raise EvaluationError (not AttributeError) for bad inputs.
# ---------------------------------------------------------------------------
class TestConvertRejectsBadTarget:
    """evaluator.py: convert() must validate its target unit argument."""

    def test_convert_int_target(self):
        from eggcalc.evaluator import EvaluationError, evaluate_raw

        with pytest.raises(EvaluationError):
            evaluate_raw("convert(1*m, 1)")

    def test_convert_float_target(self):
        from eggcalc.evaluator import EvaluationError, evaluate_raw

        with pytest.raises(EvaluationError):
            evaluate_raw("convert(1*m, m/m)")


# ---------------------------------------------------------------------------
# B4: absolute temperature addition across scales is misleading.
# ---------------------------------------------------------------------------
class TestAbsoluteTemperatureAddition:
    """evaluator.py: adding absolute temperatures across scales must error."""

    def test_celsius_plus_fahrenheit_rejected(self):
        from eggcalc.evaluator import EvaluationError, evaluate_raw

        with pytest.raises(EvaluationError):
            evaluate_raw("10*C + 10*F")

    def test_zero_celsius_plus_32f_rejected(self):
        from eggcalc.evaluator import EvaluationError, evaluate_raw

        with pytest.raises(EvaluationError):
            evaluate_raw("0*C + 32*F")

    def test_subtraction_still_allowed(self):
        from eggcalc.evaluator import evaluate_raw

        # Subtraction across scales yields a temperature delta and is fine.
        r = evaluate_raw("10*C - 10*F")
        assert abs(getattr(r, "value", r) - 22.222222222222221) < 1e-9


# ---------------------------------------------------------------------------
# B5: floor/mod on compatible units must align + avoid precision loss.
# ---------------------------------------------------------------------------
class TestCompatibleUnitFloorMod:
    """evaluator.py / units.py: compatible-unit floor/mod must align units
    (not synthesize a compound unit like m/cm) and avoid float-precision
    loss such as 1 // 0.01 -> 99."""

    def test_floordiv_meters_cm(self):
        from eggcalc.evaluator import evaluate_raw

        r = evaluate_raw("(1*m)//(1*cm)")
        assert getattr(r, "value", r) == 100

    def test_mod_meters_cm(self):
        from eggcalc.evaluator import evaluate_raw

        r = evaluate_raw("(1*m)%(30*cm)")
        # 1 m % 30 cm -> 10 cm (length remainder, not compound m/cm).
        assert abs(getattr(r, "value", r) - 10) < 1e-9
        unit = getattr(r, "unit", "cm") or "cm"
        assert unit == "cm"

    def test_unitvalue_floordiv_aligned(self):
        from eggcalc.units import UnitValue

        r = UnitValue(1, "m") // UnitValue(1, "cm")
        assert r.value == 100

    def test_unitvalue_mod_aligned(self):
        from eggcalc.units import UnitValue

        r = UnitValue(1, "m") % UnitValue(30, "cm")
        assert abs(r.value - 10) < 1e-9
        assert r.unit == "cm"

    def test_floordiv_same_unit_still_dimensionless(self):
        from eggcalc.evaluator import evaluate_raw

        r = evaluate_raw("(6*m)//(3*m)")
        assert getattr(r, "value", r) == 2

    def test_floordiv_km_mi(self):
        from eggcalc.evaluator import evaluate_raw

        r = evaluate_raw("(2*km)//(1*mi)")
        # 2 km // 1 mi = 2000 m // 1609.344 m = 1
        assert getattr(r, "value", r) == 1


# ---------------------------------------------------------------------------
# B6: "convert X to Y" NL phrase must produce a real conversion.
# ---------------------------------------------------------------------------
class TestConvertToNLPhrase:
    """normalize.py: 'convert <num> <unit> to <unit>' must normalize to
    ``convert(<num>*<unit>,<unit>)`` rather than collapse to ''."""

    def test_normalize_convert_phrase(self):
        from eggcalc.normalize import NORMALIZE, PATTERNS, normalize_expression

        out, code = normalize_expression("convert 100 meters to feet", NORMALIZE, PATTERNS)
        assert code == 0
        assert "convert(100" in out and "ft" in out

    def test_run_convert_phrase(self):
        from eggcalc.normalize import NORMALIZE, PATTERNS, run

        result, code = run("convert 100 meters to feet", NORMALIZE, PATTERNS)
        assert code == 0
        assert abs(result.value - 328.0839895013123) < 1e-6
        assert "ft" in result.unit


# ---------------------------------------------------------------------------
# B7: caret `^` is exponentiation; xor words stay bitwise XOR.
# ---------------------------------------------------------------------------
class TestCaretIsPower:
    """evaluator.py / normalize.py: ``^`` is exponentiation (matching
    docs/quickstart.md and docs/api.md). The word forms ``xor`` /
    ``XOR`` / ``bitxor`` / ``bit xor`` must remain bitwise XOR via
    ``bitxor(...)`` function calls."""

    def test_caret_symbol_is_power(self):
        from eggcalc.evaluator import evaluate_raw

        assert evaluate_raw("2^10") == 1024
        assert evaluate_raw("5^3") == 125

    def test_pi_r_squared_circle_area(self):
        import math

        from eggcalc.evaluator import evaluate_raw

        # pi * r^2 where r = 5 (parenthesize to override ^'s higher
        # precedence over *): pi * (5^2) -> pi * 25.
        r = evaluate_raw("pi * (5 ^ 2)")
        assert abs(r - math.pi * 25) < 1e-9

    def test_pi_r_squared_natural_language(self):
        import math

        from eggcalc.normalize import NORMALIZE, PATTERNS, run

        result, code = run("pi * (5 ^ 2)", NORMALIZE, PATTERNS)
        assert code == 0
        assert abs(result - math.pi * 25) < 1e-9

    def test_xor_word_is_bitwise(self):
        from eggcalc.evaluator import evaluate_raw

        assert evaluate_raw("5 xor 3") == 6
        assert evaluate_raw("5 XOR 3") == 6
        assert evaluate_raw("5 bitxor 3") == 6
        assert evaluate_raw("5 bit xor 3") == 6

    def test_xor_word_with_operands(self):
        from eggcalc.evaluator import evaluate_raw

        # 5 xor 3 + 2 == bitxor(5, 3) + 2 == 8 (parens around right operand)
        assert evaluate_raw("5 xor 3 + 2") == 8
        # 5 + 3 xor 2 == 5 + bitxor(3, 2) == 6
        assert evaluate_raw("5 + 3 xor 2") == 6


# ---------------------------------------------------------------------------
# B8: setvar/getvar string-arg preservation across name collisions.
# ---------------------------------------------------------------------------
class TestSetvarGetvarNameCollisions:
    """evaluator.py: string literals passed to setvar/getvar/delvar must
    remain strings even when they collide with constant or unit names."""

    def test_setvar_with_r_name(self):
        from eggcalc import evaluate_raw

        assert evaluate_raw('setvar("r", 5)') == 5
        assert evaluate_raw('getvar("r")') == 5

    def test_setvar_with_pi_name(self):
        from eggcalc import evaluate_raw

        assert evaluate_raw('setvar("pi", 5)') == 5
        assert evaluate_raw('getvar("pi")') == 5

    def test_setvar_with_m_name(self):
        from eggcalc import evaluate_raw

        # Storing under a unit name works without raising.
        assert evaluate_raw('setvar("m", 5)') == 5
        assert evaluate_raw('getvar("m")') == 5

    def test_delvar_preserves_string_arg(self):
        from eggcalc import evaluate_raw

        evaluate_raw('setvar("m", 5)')
        # delvar returns None and removes the binding.
        assert evaluate_raw('delvar("m")') is None
        # After deletion, getvar returns the default 0.
        assert evaluate_raw('getvar("m")') == 0

    def test_normal_setvar_unaffected(self):
        from eggcalc import evaluate_raw

        assert evaluate_raw('setvar("x", 10)') == 10
        assert evaluate_raw('getvar("x")') == 10
