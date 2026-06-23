"""Tests for mathematical identities and laws.

These tests verify that mathematical laws hold for the evaluator:
- Addition: commutative, associative, identity, inverse
- Multiplication: commutative, associative, identity, inverse, distributive
- Power laws
- Trigonometric identities
"""

from eggcalc import UnitValue, evaluate


def get_value(result):
    """Extract numeric value from result, handling UnitValue."""
    if isinstance(result, UnitValue):
        return result.value
    return result


def val(expr):
    """Evaluate and extract value, handling UnitValue."""
    result = evaluate(expr)
    if isinstance(result, UnitValue):
        return result.value
    return result


class TestAdditionLaws:
    """Test mathematical laws for addition."""

    def test_commutative_a_plus_b_equals_b_plus_a(self):
        a, b = 5.0, 3.0
        result1 = evaluate(f"{a}+{b}")
        result2 = evaluate(f"{b}+{a}")
        assert abs(get_value(result1) - get_value(result2)) < 1e-10

    def test_associative_a_plus_b_plus_c(self):
        a, b, c = 2.0, 3.0, 4.0
        result1 = evaluate(f"({a}+{b})+{c}")
        result2 = evaluate(f"{a}+({b}+{c})")
        assert abs(get_value(result1) - get_value(result2)) < 1e-10

    def test_identity_a_plus_zero_equals_a(self):
        for a in [0, 1, 5, -3, 0.5]:
            result = evaluate(f"{a}+0")
            assert abs(get_value(result) - a) < 1e-10

    def test_inverse_a_plus_minus_a_equals_zero(self):
        for a in [1, 5, -3, 0.5, 100]:
            result = evaluate(f"{a}+{-a}")
            assert abs(get_value(result) - 0) < 1e-10


class TestMultiplicationLaws:
    """Test mathematical laws for multiplication."""

    def test_commutative_a_times_b_equals_b_times_a(self):
        a, b = 5.0, 3.0
        result1 = evaluate(f"{a}*{b}")
        result2 = evaluate(f"{b}*{a}")
        assert abs(get_value(result1) - get_value(result2)) < 1e-10

    def test_associative_a_times_b_times_c(self):
        a, b, c = 2.0, 3.0, 4.0
        result1 = evaluate(f"({a}*{b})*{c}")
        result2 = evaluate(f"{a}*({b}*{c})")
        assert abs(get_value(result1) - get_value(result2)) < 1e-10

    def test_identity_a_times_one_equals_a(self):
        for a in [0, 1, 5, -3, 0.5]:
            result = evaluate(f"{a}*1")
            assert abs(get_value(result) - a) < 1e-10

    def test_zero_times_anything_is_zero(self):
        for a in [1, 5, -3, 0.5]:
            result = evaluate(f"{a}*0")
            assert abs(get_value(result) - 0) < 1e-10

    def test_inverse_a_times_one_over_a_equals_one(self):
        for a in [2, 3, 5, 10, 0.5]:
            result = evaluate(f"{a}*(1/{a})")
            assert abs(get_value(result) - 1) < 1e-10

    def test_distributive_a_times_b_plus_c(self):
        a, b, c = 2.0, 3.0, 4.0
        result1 = evaluate(f"{a}*({b}+{c})")
        result2 = evaluate(f"{a}*{b}+{a}*{c}")
        assert abs(get_value(result1) - get_value(result2)) < 1e-10


class TestPowerLaws:
    """Test mathematical laws for exponentiation."""

    def test_a_to_power_zero_is_one(self):
        for a in [2, 3, 5, 0.5]:
            assert abs(val(f"{a}**0") - 1) < 1e-10

    def test_a_to_power_one_is_a(self):
        for a in [0, 1, 5, 0.5]:
            assert abs(val(f"{a}**1") - a) < 1e-10

    def test_a_to_power_two_is_a_times_a(self):
        for a in [0, 1, 5, 0.5]:
            r1, r2 = val(f"{a}**2"), val(f"{a}*{a}")
            assert abs(r1 - r2) < 1e-10

    def test_power_multiplication_a_power_b_times_a_power_c(self):
        a, b, c = 2.0, 3.0, 2.0
        result1 = evaluate(f"{a}**{b}*{a}**{c}")
        result2 = evaluate(f"{a}**({b}+{c})")
        assert abs(get_value(result1) - get_value(result2)) < 1e-10

    def test_power_of_power_a_power_b_power_c(self):
        a, b, c = 2.0, 3.0, 2.0
        result1 = evaluate(f"({a}**{b})**{c}")
        result2 = evaluate(f"{a}**({b}*{c})")
        assert abs(get_value(result1) - get_value(result2)) < 1e-10


class TestTrigonometricIdentities:
    """Test trigonometric identities."""

    def test_sin_squared_plus_cos_squared(self):
        x = 0.5
        result = evaluate(f"sin({x})**2+cos({x})**2")
        assert abs(get_value(result) - 1) < 1e-10

    def test_tan_equals_sin_over_cos(self):
        x = 0.5
        result1 = evaluate(f"tan({x})")
        result2 = evaluate(f"sin({x})/cos({x})")
        assert abs(get_value(result1) - get_value(result2)) < 1e-10


class TestOrderOfOperations:
    """Test that order of operations is respected."""

    def test_multiplication_before_addition(self):
        result = evaluate("2+3*4")
        assert abs(get_value(result) - 14) < 1e-10

    def test_power_before_multiplication(self):
        result = evaluate("2*3**2")
        assert abs(get_value(result) - 18) < 1e-10

    def test_parentheses_override(self):
        result = evaluate("(2+3)*4")
        assert abs(get_value(result) - 20) < 1e-10
        result = evaluate("2+(3*4)")
        assert abs(get_value(result) - 14) < 1e-10

    def test_left_to_right_for_same_precedence(self):
        result = evaluate("10-5-3")
        assert abs(get_value(result) - 2) < 1e-10
        result = evaluate("10/5/2")
        assert abs(get_value(result) - 1) < 1e-10


class TestDivisionLaws:
    """Test mathematical laws for division."""

    def test_a_over_one_is_a(self):
        for a in [0, 1, 5, -3, 0.5]:
            result = evaluate(f"{a}/1")
            assert abs(get_value(result) - a) < 1e-10

    def test_zero_over_a_is_zero(self):
        for a in [1, 5, -3, 0.5]:
            result = evaluate(f"0/{a}")
            assert abs(get_value(result) - 0) < 1e-10

    def test_a_over_a_is_one(self):
        for a in [1, 5, -3, 0.5]:
            result = evaluate(f"{a}/{a}")
            assert abs(get_value(result) - 1) < 1e-10


class TestSpecialCases:
    """Test special mathematical cases."""

    def test_double_negative(self):
        result = evaluate("--5")
        assert abs(get_value(result) - 5) < 1e-10

    def test_zero_exponentiation_zero(self):
        result = evaluate("0**0")
        assert abs(get_value(result) - 1) < 1e-10

    def test_one_to_any_power(self):
        result = evaluate("1**999")
        assert abs(get_value(result) - 1) < 1e-10

    def test_any_to_power_one_half(self):
        import math

        result = evaluate("4**0.5")
        expected = math.sqrt(4)
        assert abs(get_value(result) - expected) < 1e-10
