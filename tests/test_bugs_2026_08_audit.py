"""
Regression tests for the 2026-08-24 bugs.md audit findings.

Each test class locks in the post-fix behavior described in the audit:
  - B1: ordinal power phrases ("two to the tenth") no longer evaluate
        silently to a wrong unit conversion
  - B2: a target unit named like an evaluator function ("min") inside
        convert(...) is no longer rewritten to an empty call
  - B3: UnitValue.__floordiv__ keeps the dividend's unit when the divisor
        is a dimensionless UnitValue
  - B4: juxtaposed bare digit groups ("5 5", "1 000") are rejected instead
        of being silently summed; function-argument and word-number forms
        keep working
  - B5: identical powered quantities render identically ("m**2") regardless
        of which parse path produced them
  - B6: nth-root phrases ("the 3rd root of 27") evaluate correctly
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("EGGCALC_NO_CONFIG", "1")


# ---------------------------------------------------------------------------
# B1: ordinal words must not be claimed by the bare-number conversion path.
# ---------------------------------------------------------------------------
class TestOrdinalPowerPhrases:
    """normalize.py: 'two to the tenth' must not become a bogus conversion."""

    @pytest.mark.parametrize(
        "expr",
        ["two to the tenth", "two to the third", "five to the fourth"],
    )
    def test_ordinal_power_phrase_does_not_convert(self, expr):
        from eggcalc.evaluator import EvaluationError, evaluate_raw

        with pytest.raises(EvaluationError):
            evaluate_raw(expr)

    def test_digit_power_phrase_still_works(self):
        from eggcalc.evaluator import evaluate_raw

        assert evaluate_raw("2 to the 10") == 1024

    def test_bare_number_exact_target_conversion(self):
        from eggcalc.evaluator import evaluate_raw

        r = evaluate_raw("5 km in mi")
        assert abs(r.value - 3.10685596118667) < 1e-9


# ---------------------------------------------------------------------------
# B2: target units colliding with function names inside convert(...).
# ---------------------------------------------------------------------------
class TestConvertTargetFunctionCollision:
    """normalize.py: 'min' as a convert() target stays a unit, not min()."""

    def test_hours_in_minutes(self):
        from eggcalc.evaluator import evaluate_raw

        r = evaluate_raw("1 hour in minutes")
        assert abs(r.value - 60) < 1e-9
        assert r.unit == "min"

    def test_hours_in_min_abbrev(self):
        from eggcalc.evaluator import evaluate_raw

        r = evaluate_raw("2 hours in min")
        assert abs(r.value - 120) < 1e-9
        assert r.unit == "min"

    def test_source_position_still_works(self):
        from eggcalc.evaluator import evaluate_raw

        r = evaluate_raw("60 min in hours")
        assert abs(r.value - 1) < 1e-12


# ---------------------------------------------------------------------------
# B3: floordiv with a dimensionless UnitValue divisor keeps the unit.
# ---------------------------------------------------------------------------
class TestFloorDivDimensionlessDivisor:
    """units.py: UnitValue(5,'m') // UnitValue(3,None) == UnitValue(1,'m')."""

    def test_floordiv_dimensionless_unitvalue_keeps_unit(self):
        from eggcalc.units import UnitValue

        r = UnitValue(5, "m") // UnitValue(3, None)
        assert r.value == 1
        assert r.unit == "m"

    def test_floordiv_plain_number_keeps_unit(self):
        from eggcalc.units import UnitValue

        r = UnitValue(5, "m") // 3
        assert r.value == 1
        assert r.unit == "m"

    def test_floordiv_same_unit_dimensionless_result(self):
        from eggcalc.units import UnitValue

        r = UnitValue(7, "m") // UnitValue(2, "m")
        assert r.value == 3
        assert r.unit is None

    def test_truediv_and_mod_consistency(self):
        from eggcalc.units import UnitValue

        assert (UnitValue(5, "m") / UnitValue(3, None)).unit == "m"
        assert (UnitValue(5, "m") % UnitValue(2, None)).unit == "m"


# ---------------------------------------------------------------------------
# B4: juxtaposed bare digit tokens are rejected, not summed.
# ---------------------------------------------------------------------------
class TestJuxtaposedDigitsRejected:
    """normalize.py: '5 5' and '1 000' raise instead of returning garbage."""

    @pytest.mark.parametrize("expr", ["5 5", "1 000", "1 000 + 1"])
    def test_juxtaposed_digits_error(self, expr):
        from eggcalc.evaluator import EvaluationError, evaluate_raw

        with pytest.raises((EvaluationError, ValueError)):
            evaluate_raw(expr)

    def test_explicit_operator_still_works(self):
        from eggcalc.evaluator import evaluate_raw

        assert evaluate_raw("5 + 5") == 10

    def test_word_number_sequence_still_adds(self):
        from eggcalc.evaluator import evaluate_raw

        assert evaluate_raw("twenty sixteen") == 36

    def test_function_args_with_spaces_still_work(self):
        from eggcalc.evaluator import evaluate_raw

        assert evaluate_raw("gcd 12 18") == 6
        assert evaluate_raw("hypot 3 4") == 5.0
        assert evaluate_raw("mean of 1 2 3") == 2.0
        assert evaluate_raw("mean 1 2 3") == 2.0


# ---------------------------------------------------------------------------
# B5: powered units render identically across parse paths.
# ---------------------------------------------------------------------------
class TestPowerUnitRenderingConsistency:
    """normalize.py/units.py: every power path renders 'm**2'."""

    @pytest.mark.parametrize(
        "expr",
        ["5 m ** 2", "5m^2", "5m**2", "(5m)^2", "5 m squared", "5 m ^ 2"],
    )
    def test_all_power_paths_render_m_squared(self, expr):
        from eggcalc.evaluator import evaluate_raw

        r = evaluate_raw(expr)
        assert str(r).split()[1] == "m**2"

    def test_cubed_renders_m_cubed(self):
        from eggcalc.evaluator import evaluate_raw

        r = evaluate_raw("3 m cubed")
        assert r.unit == "m**3"

    def test_explicit_compact_alias_unchanged(self):
        from eggcalc.evaluator import evaluate_raw

        r = evaluate_raw("5 m2")
        assert r.value == 5
        assert r.unit == "m2"


# ---------------------------------------------------------------------------
# B6: nth-root phrases evaluate instead of collapsing into identifiers.
# ---------------------------------------------------------------------------
class TestNthRootPhrases:
    """normalize.py: '<ordinal> root of X' evaluates to X**(1/N)."""

    @pytest.mark.parametrize(
        ("expr", "expected"),
        [
            ("the 3rd root of 27", 3.0),
            ("3rd root of 27", 3.0),
            ("4th root of 81", 3.0),
            ("fourth root of 81", 3.0),
            ("second root of 16", 4.0),
            ("tenth root of 1024", 2.0),
        ],
    )
    def test_nth_root_phrase(self, expr, expected):
        from eggcalc.evaluator import evaluate_raw

        result = evaluate_raw(expr)
        assert abs(result - expected) < 1e-9

    def test_existing_root_phrases_unchanged(self):
        from eggcalc.evaluator import evaluate_raw

        assert abs(evaluate_raw("square root of 144") - 12) < 1e-12
        assert abs(evaluate_raw("cube root of 27") - 3) < 1e-9
