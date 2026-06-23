"""Comprehensive tests for missing math functions and edge cases."""

import math

import pytest

from eggcalc.evaluator import EvaluationError, evaluate

# ---------------------------------------------------------------------------
# Hyperbolic function tests
# ---------------------------------------------------------------------------

class TestHyperbolicFunctions:
    def test_sinh(self):
        assert evaluate("sinh(0)") == pytest.approx(0.0)
        assert evaluate("sinh(1)") == pytest.approx(1.1752011936438014)

    def test_cosh(self):
        assert evaluate("cosh(0)") == pytest.approx(1.0)
        assert evaluate("cosh(1)") == pytest.approx(1.5430806348152437)

    def test_tanh(self):
        assert evaluate("tanh(0)") == pytest.approx(0.0)
        assert evaluate("tanh(1)") == pytest.approx(0.7615941559557649)

    def test_asinh(self):
        assert evaluate("asinh(0)") == pytest.approx(0.0)
        assert evaluate("asinh(1)") == pytest.approx(0.881373587019543)

    def test_acosh(self):
        assert evaluate("acosh(1)") == pytest.approx(0.0)
        assert evaluate("acosh(2)") == pytest.approx(1.3169578969248166)

    def test_atanh(self):
        assert evaluate("atanh(0)") == pytest.approx(0.0)
        assert evaluate("atanh(0.5)") == pytest.approx(0.5493061443340549)


# ---------------------------------------------------------------------------
# atan2 test
# ---------------------------------------------------------------------------

class TestAtan2:
    def test_atan2(self):
        assert evaluate("atan2(1, 1)") == pytest.approx(math.pi / 4)
        assert evaluate("atan2(0, 1)") == pytest.approx(0.0)
        assert evaluate("atan2(1, 0)") == pytest.approx(math.pi / 2)


# ---------------------------------------------------------------------------
# Additional math function tests
# ---------------------------------------------------------------------------

class TestAdditionalMathFunctions:
    def test_log1p(self):
        assert evaluate("log1p(0)") == pytest.approx(0.0)
        assert evaluate("log1p(e - 1)") == pytest.approx(1.0)

    def test_expm1(self):
        assert evaluate("expm1(0)") == pytest.approx(0.0)
        assert evaluate("expm1(1)") == pytest.approx(math.e - 1)

    def test_trunc(self):
        assert evaluate("trunc(3.7)") == 3
        assert evaluate("trunc(-3.7)") == -3

    def test_round_builtin(self):
        # Python banker's rounding: round(3.5) == 4, round(2.5) == 2
        assert evaluate("round(3.5)") == 4
        assert evaluate("round(3.14, 1)") == pytest.approx(3.1)

    def test_stdev_sample(self):
        # Sample standard deviation of 1,2,3,4,5 => sqrt(2.5) ≈ 1.5811
        result = evaluate("std_sample(1, 2, 3, 4, 5)")
        assert result == pytest.approx(1.5811388300841898)

    def test_clamp_above_max(self):
        assert evaluate("clamp(15, 1, 10)") == 10


# ---------------------------------------------------------------------------
# Edge case tests
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_mismatched_parens_open(self):
        with pytest.raises(EvaluationError):
            evaluate("sin(5")

    def test_mismatched_parens_close(self):
        with pytest.raises(EvaluationError):
            evaluate("5+3)")

    def test_empty_parens(self):
        with pytest.raises(EvaluationError):
            evaluate("sin()")

    def test_unknown_function(self):
        with pytest.raises(EvaluationError):
            evaluate("foobar(5)")

    def test_expression_only_operators(self):
        with pytest.raises(EvaluationError):
            evaluate("+++")

    def test_scientific_notation_input(self):
        assert evaluate("1e3") == pytest.approx(1000.0)

    def test_scientific_notation_negative_exp(self):
        assert evaluate("2.5e-3") == pytest.approx(0.0025)

    def test_negative_zero(self):
        result = evaluate("-0")
        assert result == 0

    def test_very_small_result(self):
        result = evaluate("1e-308 * 0.5")
        assert result == pytest.approx(5e-309)

    def test_unicode_multiplication_sign(self):
        # The Unicode × character should raise a syntax error, not crash
        with pytest.raises(EvaluationError):
            evaluate("5 × 3")

    def test_zero_value_unit_conversion(self):
        result = evaluate("0")
        assert result == 0

    def test_unknown_unit_string(self):
        with pytest.raises(EvaluationError):
            evaluate("5 foo")


# ---------------------------------------------------------------------------
# Function argument tests
# ---------------------------------------------------------------------------

class TestFunctionArguments:
    def test_function_too_many_args(self):
        with pytest.raises(EvaluationError):
            evaluate("sin(1, 2)")

    def test_function_wrong_type_args(self):
        # sin expects numeric; passing a string-like unsupported arg triggers error
        with pytest.raises(EvaluationError):
            evaluate("abs()")

    def test_gcd_two_args(self):
        assert evaluate("gcd(12, 8)") == 4

    def test_lcm_two_args(self):
        assert evaluate("lcm(4, 6)") == 12

    def test_pow_two_args(self):
        assert evaluate("pow(2, 10)") == 1024

    def test_hypot_two_args(self):
        assert evaluate("hypot(3, 4)") == pytest.approx(5.0)
