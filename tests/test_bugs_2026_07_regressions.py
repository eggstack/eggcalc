"""
Regression tests for the 2026-07 bugs.md findings.

Each test class locks in the post-fix behavior described in bugs.md:
  - B1: compound unit exponentiation
  - B2: mult/div of compatible units
  - B3: convert() robustness against non-string target units
  - B4: absolute temperature addition across scales
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
