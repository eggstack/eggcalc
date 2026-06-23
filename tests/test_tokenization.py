"""Tests for tokenization and expression parsing.

These tests ensure that the expression tokenizer correctly handles:
- Multi-digit numbers with operators (the 90-1 bug was here)
- Operator precedence and associativity
- Negative numbers
- Decimal numbers
- Various edge cases
"""

import pytest

from eggcalc import UnitValue, evaluate
from eggcalc.normalize import NORMALIZE, PATTERNS, split_at_operators


def get_value(result):
    """Extract numeric value from result, handling UnitValue."""
    if isinstance(result, UnitValue):
        return result.value
    return result


class TestMultiDigitSubtraction:
    """Test subtraction with multi-digit numbers.

    Regression tests for bug where '90-1' returned '901'.
    """

    @pytest.mark.parametrize(
        "expr,expected",
        [
            ("90-1", 89),
            ("100-10", 90),
            ("1000-1", 999),
            ("50-5", 45),
            ("123-45", 78),
            ("999-99", 900),
            ("10000-1", 9999),
            ("10-0", 10),
            ("0-10", -10),
            ("0-0", 0),
        ],
    )
    def test_multi_digit_subtraction(self, expr, expected):
        result = evaluate(expr)
        assert abs(get_value(result) - expected) < 1e-10

    @pytest.mark.parametrize(
        "expr,expected",
        [
            ("12+34-56", -10),
            ("100-10-20-30", 40),
            ("50-5-5-5", 35),
            ("1000-100-10-1", 889),
        ],
    )
    def test_chained_subtraction(self, expr, expected):
        result = evaluate(expr)
        assert abs(get_value(result) - expected) < 1e-10


class TestMultiDigitOperations:
    """Test operations with multi-digit numbers."""

    @pytest.mark.parametrize(
        "expr,expected",
        [
            ("12+34", 46),
            ("100+200", 300),
            ("123+456", 579),
            ("99+1", 100),
        ],
    )
    def test_multi_digit_addition(self, expr, expected):
        result = evaluate(expr)
        assert abs(get_value(result) - expected) < 1e-10

    @pytest.mark.parametrize(
        "expr,expected",
        [
            ("10*10", 100),
            ("12*12", 144),
            ("100*100", 10000),
            ("99*99", 9801),
        ],
    )
    def test_multi_digit_multiplication(self, expr, expected):
        result = evaluate(expr)
        assert abs(get_value(result) - expected) < 1e-10

    @pytest.mark.parametrize(
        "expr,expected",
        [
            ("100/10", 10),
            ("144/12", 12),
            ("1000/8", 125),
        ],
    )
    def test_multi_digit_division(self, expr, expected):
        result = evaluate(expr)
        assert abs(get_value(result) - expected) < 1e-10


class TestOperatorPrecedence:
    """Test operator precedence in expressions."""

    def test_multiplication_before_addition(self):
        result = evaluate("2+3*4")
        assert abs(get_value(result) - 14) < 1e-10

    def test_multiplication_before_subtraction(self):
        result = evaluate("10-2*3")
        assert abs(get_value(result) - 4) < 1e-10

    def test_division_before_addition(self):
        result = evaluate("2+10/2")
        assert abs(get_value(result) - 7) < 1e-10

    def test_power_before_multiplication(self):
        result = evaluate("2*3**2")
        assert abs(get_value(result) - 18) < 1e-10

    def test_parentheses_override(self):
        result = evaluate("(2+3)*4")
        assert abs(get_value(result) - 20) < 1e-10
        result = evaluate("2+(3*4)")
        assert abs(get_value(result) - 14) < 1e-10


class TestNegativeNumbers:
    """Test handling of negative numbers."""

    @pytest.mark.parametrize(
        "expr,expected",
        [
            ("-5", -5),
            ("--5", 5),
            ("---5", -5),
            ("5*-3", -15),
            ("10+-2", 8),
            ("-10*-2", 20),
        ],
    )
    def test_negative_literals(self, expr, expected):
        result = evaluate(expr)
        assert abs(get_value(result) - expected) < 1e-10


class TestDecimalNumbers:
    """Test handling of decimal numbers."""

    @pytest.mark.parametrize(
        "expr,expected",
        [
            ("3.14", 3.14),
            ("0.5", 0.5),
            (".5", 0.5),
            ("3.14*2", 6.28),
            ("1.5+2.5", 4.0),
            ("10.5-5.5", 5.0),
        ],
    )
    def test_decimals(self, expr, expected):
        result = evaluate(expr)
        assert abs(get_value(result) - expected) < 1e-10


class TestSplitAtOperators:
    """Direct tests for split_at_operators function."""

    def test_simple_addition(self):
        tokens = split_at_operators("5+3", NORMALIZE, PATTERNS)
        assert tokens == ["5", "+", "3"]

    def test_simple_subtraction(self):
        tokens = split_at_operators("5-3", NORMALIZE, PATTERNS)
        assert tokens == ["5", "-", "3"]

    def test_multi_digit_subtraction(self):
        """This is the bug that '90-1' was returning '901'."""
        tokens = split_at_operators("90-1", NORMALIZE, PATTERNS)
        assert "90" in tokens
        assert "-" in tokens
        assert "1" in tokens

    def test_multiplication(self):
        tokens = split_at_operators("5*3", NORMALIZE, PATTERNS)
        assert tokens == ["5", "*", "3"]

    def test_division(self):
        tokens = split_at_operators("6/2", NORMALIZE, PATTERNS)
        assert tokens == ["6", "/", "2"]

    def test_power(self):
        tokens = split_at_operators("2**3", NORMALIZE, PATTERNS)
        assert tokens == ["2", "*", "*", "3"]

    def test_complex_expression(self):
        tokens = split_at_operators("12+34-56*78/90", NORMALIZE, PATTERNS)
        assert "12" in tokens
        assert "+" in tokens
        assert "34" in tokens
        assert "-" in tokens
        assert "56" in tokens
        assert "*" in tokens
        assert "78" in tokens
        assert "/" in tokens
        assert "90" in tokens

    def test_negative_number(self):
        tokens = split_at_operators("-5", NORMALIZE, PATTERNS)
        assert "-5" in tokens


class TestEdgeCases:
    """Test various edge cases in tokenization."""

    def test_zero_operations(self):
        result = evaluate("0+0")
        assert abs(get_value(result) - 0) < 1e-10
        result = evaluate("0-0")
        assert abs(get_value(result) - 0) < 1e-10
        result = evaluate("0*0")
        assert abs(get_value(result) - 0) < 1e-10

    def test_one_operations(self):
        result = evaluate("1+1")
        assert abs(get_value(result) - 2) < 1e-10
        result = evaluate("1-1")
        assert abs(get_value(result) - 0) < 1e-10
        result = evaluate("1*1")
        assert abs(get_value(result) - 1) < 1e-10

    def test_large_numbers(self):
        result = evaluate("999999+1")
        assert abs(get_value(result) - 1000000) < 1e-10
        result = evaluate("1000000-1")
        assert abs(get_value(result) - 999999) < 1e-10

    def test_order_of_operations_chain(self):
        result = evaluate("2+3*4-5")
        assert abs(get_value(result) - 9) < 1e-10
        result = evaluate("10-2*3+1")
        assert abs(get_value(result) - 5) < 1e-10
