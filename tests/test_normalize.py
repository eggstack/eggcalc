"""Tests for natural-language pipeline fixes in eggcalc.normalize.

Covers the regression suite for production hardening of:
- Group A: Leading zeros (0.015, 0.001, 0.005, 1.015, 10.015, 1.5 percent)
- Group B: N-func patterns (5 factorial, 5 sin, 2 sqrt 9, sqrt 144)
- Group C: ^ ambiguity (5^3 == XOR, 5**3 == power, "to the power of")
- Group D: not/in/to/as SyntaxErrors (raise clear errors; bare-number in m)
- Group E: "sqrt of 144 + 5" (17, not TypeError)
- Group F: Compound speed units (5km/h, 30 km/h in mph)
- Group G: Angle mode (sin 30 degrees == 0.5)
- Group H: Twenty-one hundred style multi-word numbers
- Group I: LRU cache + thread-safety
- Group J: Length + validation regex (MAX_NORMALIZED_LENGTH, tighter regex)
- Group K: Dead code removal
- Inch canonical (in -> inch)
"""
import io
import sys

import pytest

from eggcalc import UnitValue
from eggcalc.normalize import (
    _IMPLICIT_MUL_FUNCS,
    _MULTI_ARG_OF_FUNCS,
    _SINGLE_ARG_IMPLICIT_MUL,
    MAX_NORMALIZED_LENGTH,
    NORMALIZE,
    PATTERNS,
    _binary_word_check,
    apply_math_functions,
    check_if_number,
    normalize_expression,
    run,
)


def _run(expr: str):
    """Run an expression through the full NL pipeline, capturing output."""
    captured = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = captured
    captured_err = io.StringIO()
    old_stderr = sys.stderr
    sys.stderr = captured_err
    try:
        result, code = run(expr, NORMALIZE, PATTERNS)
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
    return result, code, captured.getvalue().strip(), captured_err.getvalue().strip()


def _val(result):
    """Extract numeric value from a possibly-UnitValue result."""
    if isinstance(result, UnitValue):
        return result.value
    return result


# ---------------------------------------------------------------------------
# Group A: Leading zeros preserved
# ---------------------------------------------------------------------------
class TestLeadingZeros:
    """Verify that leading zeros in fractional numbers are preserved."""

    @pytest.mark.parametrize("expr,expected", [
        ("0.015", 0.015),
        ("0.001", 0.001),
        ("0.005", 0.005),
        ("1.015", 1.015),
        ("10.015", 10.015),
    ])
    def test_leading_zeros_preserved(self, expr, expected):
        result, code, _out, _err = _run(expr)
        assert code == 0
        assert _val(result) == pytest.approx(expected)

    def test_percent_with_fractional_value(self):
        """1.5 percent of 100 should give 1.5 (i.e., 0.015 of 100 = 1.5)."""
        result, code, _out, _err = _run("1.5 percent")
        assert code == 0
        assert _val(result) == pytest.approx(0.015)

    def test_percent_followed_by_star_is_multiplication(self):
        """100%*200 must remain multiplication, not exponentiation."""
        normalized, code = normalize_expression("100%*200", NORMALIZE, PATTERNS)
        assert code == 0
        assert normalized == "1.0*200"
        result, code, _out, _err = _run("100%*200")
        assert code == 0
        assert _val(result) == pytest.approx(200.0)


# ---------------------------------------------------------------------------
# Group B: N-func implicit multiplication
# ---------------------------------------------------------------------------
class TestNFuncPatterns:
    """<digit> <func> should be interpreted as <func>(<digit>)."""

    @pytest.mark.parametrize("expr,expected", [
        ("5 factorial", 120),       # 5!
        ("5 sin", -0.9589242746631385),  # sin(5)
        ("5 cos", 0.2836621854632263),   # cos(5)
        ("5 log", 1.6094379124341003),   # ln(5)
        ("2 sqrt 9", 6.0),               # 2 * sqrt(9)
        ("2sqrt9", 6.0),                 # compact form of 2 * sqrt(9)
        ("sqrt 144", 12.0),             # sqrt(144) - existing behavior preserved
        ("sqrt144", 12.0),              # compact form of sqrt(144)
        ("sin 0", 0.0),                 # sin(0) - existing behavior preserved
        ("sin0", 0.0),                  # compact form of sin(0)
    ])
    def test_n_func(self, expr, expected):
        result, code, _out, _err = _run(expr)
        assert code == 0, f"Expected success for {expr!r}, got code={code}, err={_err!r}"
        assert _val(result) == pytest.approx(expected), (
            f"Expected {expected} for {expr!r}, got {_val(result)}"
        )

    @pytest.mark.parametrize("expr,expected_normalized,expected", [
        ("log10(100)", "log10(100)", 2.0),
        ("log2(8)", "log2(8)", 3.0),
        ("expm1(1)", "expm1(1)", 1.718281828459045),
    ])
    def test_function_names_ending_in_digits_before_paren(self, expr, expected_normalized, expected):
        normalized, code = normalize_expression(expr, NORMALIZE, PATTERNS)
        assert code == 0
        assert normalized == expected_normalized
        result, code, _out, _err = _run(expr)
        assert code == 0
        assert _val(result) == pytest.approx(expected)

    @pytest.mark.parametrize("expr,expected_normalized,expected", [
        ("sin30", "sin(30)", -0.9880316240928618),
        ("sqrt9", "sqrt(9)", 3.0),
        ("2sqrt9", "2*sqrt(9)", 6.0),
    ])
    def test_compact_function_number_spacing(self, expr, expected_normalized, expected):
        normalized, code = normalize_expression(expr, NORMALIZE, PATTERNS)
        assert code == 0
        assert normalized == expected_normalized
        result, code, _out, _err = _run(expr)
        assert code == 0
        assert _val(result) == pytest.approx(expected)


# ---------------------------------------------------------------------------
# Group C: ^ is XOR, not power
# ---------------------------------------------------------------------------
class TestXorVsPower:
    """`^` is bitwise XOR; power must use `**` or NL phrase."""

    def test_caret_is_xor(self):
        result, code, _out, _err = _run("5^3")
        assert code == 0
        assert _val(result) == 6  # 5 XOR 3 = 6

    def test_double_star_is_power(self):
        result, code, _out, _err = _run("5 ** 3")
        assert code == 0
        assert _val(result) == 125

    def test_to_the_power_of_is_power(self):
        result, code, _out, _err = _run("5 to the power of 3")
        assert code == 0
        assert _val(result) == 125


# ---------------------------------------------------------------------------
# Group D: not/in/to/as SyntaxErrors
# ---------------------------------------------------------------------------
class TestBinaryWordErrors:
    """<value> not/in/to/as <value> should raise a clear error."""

    @pytest.mark.parametrize("expr", [
        "5 not 6",
        "1 in 2",
        "1 to 2",
        "5 as 6",
    ])
    def test_binary_word_raises(self, expr):
        # The pipeline surfaces a ValueError to the user via a non-zero exit
        # code; we don't expect a clean numeric result.
        result, code, _out, _err = _run(expr)
        assert code != 0, f"Expected failure for {expr!r}, got result={result!r}"

    def test_implicit_multiplication_on_paren(self):
        """(2+3)4 should yield 20, (2+3)(4+5) should yield 45."""
        result, code, _out, _err = _run("(2+3)4")
        assert code == 0
        assert _val(result) == 20
        result, code, _out, _err = _run("(2+3)(4+5)")
        assert code == 0
        assert _val(result) == 45

    def test_bare_number_with_in_unit_conversion(self):
        """`1 in m` should convert 1 meter to the base unit correctly."""
        result, code, _out, _err = _run("1 in m")
        assert code == 0
        assert _val(result) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Group E: sqrt of X + Y
# ---------------------------------------------------------------------------
class TestSqrtOfXPlusY:
    """sqrt of 144 + 5 should be 17 (not a TypeError)."""

    def test_sqrt_of_x_plus_y(self):
        result, code, _out, _err = _run("sqrt of 144 + 5")
        assert code == 0
        assert _val(result) == pytest.approx(17.0)

    def test_mean_of_x_plus_y(self):
        """mean of 1+2+3 should still be 2 (multi-arg of-function)."""
        result, code, _out, _err = _run("mean of 1+2+3")
        assert code == 0
        assert _val(result) == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# Group F: Compound speed units
# ---------------------------------------------------------------------------
class TestCompoundSpeedUnits:
    """km/h and friends should be recognized as compound units."""

    def test_km_h_basic(self):
        result, code, _out, _err = _run("5km/h")
        assert code == 0
        assert isinstance(result, UnitValue)
        assert result.value == 5
        assert result.unit == "km/h"

    def test_km_h_in_mph(self):
        """30 km/h in mph should be ~18.64 mph."""
        result, code, _out, _err = _run("30 km/h in mph")
        assert code == 0
        assert isinstance(result, UnitValue)
        assert result.value == pytest.approx(18.641135767120023)
        assert result.unit == "mph"

    def test_m_per_s(self):
        """5m/s should be a recognized compound speed (no Planck collision)."""
        result, code, _out, _err = _run("5m/s")
        assert code == 0
        assert isinstance(result, UnitValue)
        assert result.value == 5
        assert result.unit == "m/s"


# ---------------------------------------------------------------------------
# Group G: Angle mode (degrees)
# ---------------------------------------------------------------------------
class TestAngleMode:
    """sin/cos of <n> degrees should be interpreted in degrees."""

    def test_sin_30_degrees(self):
        result, code, _out, _err = _run("sin 30 degrees")
        assert code == 0
        assert _val(result) == pytest.approx(0.5, abs=1e-9)

    def test_cos_60_degrees(self):
        result, code, _out, _err = _run("cos 60 degrees")
        assert code == 0
        assert _val(result) == pytest.approx(0.5, abs=1e-9)

    def test_sin_90_deg(self):
        result, code, _out, _err = _run("sin 90 deg")
        assert code == 0
        assert _val(result) == pytest.approx(1.0, abs=1e-9)

    def test_sin_30_in_parens(self):
        result, code, _out, _err = _run("sin(30 degrees)")
        assert code == 0
        assert _val(result) == pytest.approx(0.5, abs=1e-9)


# ---------------------------------------------------------------------------
# Group H: Multi-word number pre-replacement
# ---------------------------------------------------------------------------
class TestMultiWordNumbers:
    """Tens + ones + scale should combine to a single value."""

    @pytest.mark.parametrize("expr,expected", [
        ("twenty one hundred", 2100),
        ("thirty two hundred", 3200),
        ("fifty six thousand", 56000),
        ("twelve hundred", 1200),
        ("twenty one thousand", 21000),
    ])
    def test_tens_ones_scale(self, expr, expected):
        result, code, _out, _err = _run(expr)
        assert code == 0
        assert _val(result) == expected


# ---------------------------------------------------------------------------
# Group I: LRU cache + thread-safety
# ---------------------------------------------------------------------------
class TestRebuildConfig:
    """_rebuild_config should clear the check_if_number cache."""

    def test_rebuild_clears_check_if_number_cache(self):
        from eggcalc.normalize import _rebuild_config

        # Populate the cache
        check_if_number("42")
        info_before = check_if_number.cache_info()
        assert info_before.currsize > 0

        # Rebuild should clear it
        _rebuild_config()
        info_after = check_if_number.cache_info()
        assert info_after.currsize == 0


# ---------------------------------------------------------------------------
# Group J: Length cap + validation regex
# ---------------------------------------------------------------------------
class TestLengthAndValidation:
    """MAX_NORMALIZED_LENGTH constant exists; validation rejects pure operator strings."""

    def test_max_normalized_length_exists(self):
        assert isinstance(MAX_NORMALIZED_LENGTH, int)
        assert MAX_NORMALIZED_LENGTH >= 2 * 10000  # at least 2x input cap

    def test_validation_rejects_bare_operators(self):
        """*/.3 (no leading digit) should be rejected by validation."""
        from eggcalc.normalize import validate_for_eval
        with pytest.raises(ValueError):
            validate_for_eval(["*/.3"], PATTERNS)


# ---------------------------------------------------------------------------
# Group K: Dead code removal (no inline_negative, decimal_negative,
# _handle_negative_token; the catch-all tokens[i].replace("-", "") is gone)
# ---------------------------------------------------------------------------
class TestDeadCodeRemoved:
    """The dead code paths in split_at_operators should be gone."""

    def test_no_inline_negative_handler(self):
        import eggcalc.normalize as m
        assert not hasattr(m, "_handle_negative_token"), (
            "_handle_negative_token should have been removed (dead code)"
        )

    def test_no_decimal_negative_handler(self):
        import eggcalc.normalize as m
        assert not hasattr(m, "_should_handle_decimal_negative")

    def test_no_inline_negative_check(self):
        import eggcalc.normalize as m
        assert not hasattr(m, "_should_handle_inline_negative")

    def test_normalize_handles_simple_subtraction(self):
        """Removing the dead code should not break '90-1'."""
        result, code, _out, _err = _run("90-1")
        assert code == 0
        assert _val(result) == pytest.approx(89)


# ---------------------------------------------------------------------------
# Inch canonical
# ---------------------------------------------------------------------------
class TestInchCanonical:
    """in should be emitted as inch (the canonical alias)."""

    def test_5_in_is_inch(self):
        result, code, _out, _err = _run("5 in")
        assert code == 0
        assert isinstance(result, UnitValue)
        assert result.value == 5
        assert result.unit == "inch"

    def test_5_in_to_cm(self):
        result, code, _out, _err = _run("5 in to cm")
        assert code == 0
        assert isinstance(result, UnitValue)
        assert result.value == pytest.approx(12.7, abs=1e-6)
        assert result.unit == "cm"


# ---------------------------------------------------------------------------
# _binary_word_check helper
# ---------------------------------------------------------------------------
class TestBinaryWordCheck:
    """The helper that raises clear errors for binary-word misuse."""

    def test_raises_for_value_in_value(self):
        with pytest.raises(ValueError, match="not a binary operator"):
            _binary_word_check("5 not 6")

    def test_raises_for_in_to_in(self):
        with pytest.raises(ValueError, match="not a binary operator"):
            _binary_word_check("1 in 2")

    def test_no_raise_for_unrelated(self):
        # Should not raise for expressions without the binary-word pattern.
        _binary_word_check("5 + 3")
        _binary_word_check("sqrt 144")


# ---------------------------------------------------------------------------
# Implicit-mul function sets
# ---------------------------------------------------------------------------
class TestImplicitMulSets:
    """Document and verify the function-name sets used by the pipeline."""

    def test_implicit_mul_set_contents(self):
        assert "sqrt" in _IMPLICIT_MUL_FUNCS
        assert "factorial" in _IMPLICIT_MUL_FUNCS
        assert "min" in _IMPLICIT_MUL_FUNCS  # min is multi-arg
        assert "max" in _IMPLICIT_MUL_FUNCS

    def test_single_arg_set_excludes_multi_arg(self):
        # The single-arg set used by apply_math_functions' swap is a subset
        assert "sqrt" in _SINGLE_ARG_IMPLICIT_MUL
        assert "min" not in _SINGLE_ARG_IMPLICIT_MUL
        assert "max" not in _SINGLE_ARG_IMPLICIT_MUL

    def test_multi_arg_set_contents(self):
        assert "min" in _MULTI_ARG_OF_FUNCS
        assert "max" in _MULTI_ARG_OF_FUNCS
        assert "gcd" in _MULTI_ARG_OF_FUNCS
        assert "lcm" in _MULTI_ARG_OF_FUNCS


# ---------------------------------------------------------------------------
# apply_math_functions: swap behavior
# ---------------------------------------------------------------------------
class TestApplyMathFunctionsSwap:
    """5 factorial -> factorial(5); 5 sqrt(4) keeps sqrt(4)."""

    def test_five_factorial_swaps_to_factorial_5(self):
        out = apply_math_functions(
            ["5", "*", "factorial"], NORMALIZE, PATTERNS
        )
        assert out == ["factorial", "(", "5", ")"]

    def test_five_sin_swaps_to_sin_5(self):
        out = apply_math_functions(
            ["5", "*", "sin"], NORMALIZE, PATTERNS
        )
        assert out == ["sin", "(", "5", ")"]

    def test_two_sqrt_nine_does_not_swap(self):
        """When there's a trailing value, the leading number is a multiplier."""
        out = apply_math_functions(
            ["2", "*", "sqrt", "*", "9"], NORMALIZE, PATTERNS
        )
        # Existing behavior preserved: 2 * sqrt(9)
        assert out == ["2", "*", "sqrt", "(", "9", ")"]


class TestShouldSplitNumberSequence:
    """Verify _should_split_number_sequence returns True for valid inputs."""

    def test_returns_true_for_numeric_parts(self):
        """Function should return True when all parts are numeric."""
        from eggcalc.normalize import _should_split_number_sequence
        assert _should_split_number_sequence("1 2 3") is True

    def test_returns_false_for_non_numeric(self):
        """Function should return False when parts are not numeric."""
        from eggcalc.normalize import _should_split_number_sequence
        assert _should_split_number_sequence("1 abc 3") is False


class TestOperatorSpacing:
    """Whitespace around symbolic operators must not affect parsing."""

    @pytest.mark.parametrize("expr", ["20*20", "20 * 20", "20 *20", "20* 20"])
    def test_multiplication_spacing(self, expr):
        normalized, code = normalize_expression(expr, NORMALIZE, PATTERNS)
        assert code == 0
        assert normalized == "20*20"
        result, code, _out, _err = _run(expr)
        assert code == 0
        assert _val(result) == pytest.approx(400)

    @pytest.mark.parametrize("expr", ["20/20", "20 / 20", "20 /20", "20/ 20"])
    def test_division_spacing(self, expr):
        normalized, code = normalize_expression(expr, NORMALIZE, PATTERNS)
        assert code == 0
        assert normalized == "20/20"
        result, code, _out, _err = _run(expr)
        assert code == 0
        assert _val(result) == pytest.approx(1)

    @pytest.mark.parametrize("expr", ["2**3", "2 ** 3", "2 **3", "2** 3"])
    def test_power_spacing(self, expr):
        normalized, code = normalize_expression(expr, NORMALIZE, PATTERNS)
        assert code == 0
        assert normalized == "2**3"
        result, code, _out, _err = _run(expr)
        assert code == 0
        assert _val(result) == pytest.approx(8)

    @pytest.mark.parametrize("expr", ["8<<2", "8 << 2", "8 <<2", "8<< 2", "8 < < 2"])
    def test_left_shift_spacing(self, expr):
        normalized, code = normalize_expression(expr, NORMALIZE, PATTERNS)
        assert code == 0
        assert normalized == "8<<2"
        result, code, _out, _err = _run(expr)
        assert code == 0
        assert _val(result) == 32

    @pytest.mark.parametrize("expr", ["8>>2", "8 >> 2", "8 >>2", "8>> 2", "8 > > 2"])
    def test_right_shift_spacing(self, expr):
        normalized, code = normalize_expression(expr, NORMALIZE, PATTERNS)
        assert code == 0
        assert normalized == "8>>2"
        result, code, _out, _err = _run(expr)
        assert code == 0
        assert _val(result) == 2

    @pytest.mark.parametrize("expr", ["sqrt(144)", "sqrt (144)", "sqrt( 144)", "sqrt ( 144 )"])
    def test_function_parenthesis_spacing(self, expr):
        normalized, code = normalize_expression(expr, NORMALIZE, PATTERNS)
        assert code == 0
        assert normalized == "sqrt(144)"
        result, code, _out, _err = _run(expr)
        assert code == 0
        assert _val(result) == pytest.approx(12)

    @pytest.mark.parametrize("expr", ["3(4+5)", "3 (4+5)", "3 ( 4 + 5 )"])
    def test_implicit_parenthesis_spacing(self, expr):
        normalized, code = normalize_expression(expr, NORMALIZE, PATTERNS)
        assert code == 0
        assert normalized == "3*(4+5)"
        result, code, _out, _err = _run(expr)
        assert code == 0
        assert _val(result) == pytest.approx(27)

    @pytest.mark.parametrize("expr", ["3+(4*5)", "3 +(4*5)", "3+ (4*5)", "3 + ( 4 * 5 )"])
    def test_operator_before_parenthesis_spacing(self, expr):
        normalized, code = normalize_expression(expr, NORMALIZE, PATTERNS)
        assert code == 0
        assert normalized == "3+(4*5)"
        result, code, _out, _err = _run(expr)
        assert code == 0
        assert _val(result) == pytest.approx(23)

    @pytest.mark.parametrize("expr", ["5!", "5 !"])
    def test_factorial_spacing(self, expr):
        normalized, code = normalize_expression(expr, NORMALIZE, PATTERNS)
        assert code == 0
        assert normalized == "factorial(5)"
        result, code, _out, _err = _run(expr)
        assert code == 0
        assert _val(result) == pytest.approx(120)

    @pytest.mark.parametrize("expr", ["5 m2 + 100 cm**2", "5 m2+ 100 cm ** 2"])
    def test_unit_exponent_spacing(self, expr):
        result, code, _out, _err = _run(expr)
        assert code == 0
        assert isinstance(result, UnitValue)
        assert result.value == pytest.approx(5.01)
        assert result.unit in ("m2", "m**2")

    @pytest.mark.parametrize("expr", ["5m^2", "5 m ^ 2", "5 meters ^ 2"])
    def test_unit_caret_exponent_spacing(self, expr):
        normalized, code = normalize_expression(expr, NORMALIZE, PATTERNS)
        assert code == 0
        assert normalized == "5*m2"
        result, code, _out, _err = _run(expr)
        assert code == 0
        assert isinstance(result, UnitValue)
        assert result.value == pytest.approx(5)
        assert result.unit in ("m2", "m**2")

    @pytest.mark.parametrize("expr", ["5 m squared", "5 meters squared"])
    def test_postfix_unit_squared_word_spacing(self, expr):
        normalized, code = normalize_expression(expr, NORMALIZE, PATTERNS)
        assert code == 0
        assert normalized == "5*m2"
        result, code, _out, _err = _run(expr)
        assert code == 0
        assert isinstance(result, UnitValue)
        assert result.value == pytest.approx(5)
        assert result.unit in ("m2", "m**2")

    def test_postfix_unit_power_word_conversion(self):
        normalized, code = normalize_expression("2 m squared in cm squared", NORMALIZE, PATTERNS)
        assert code == 0
        assert normalized == "convert(2*m2,cm2)"
        result, code, _out, _err = _run("2 m squared in cm squared")
        assert code == 0
        assert isinstance(result, UnitValue)
        assert result.value == pytest.approx(20000)
        assert result.unit in ("cm2", "cm**2")

    @pytest.mark.parametrize("expr", ["2 sec", "2 secs", "2 seconds"])
    def test_second_abbreviation_spacing(self, expr):
        normalized, code = normalize_expression(expr, NORMALIZE, PATTERNS)
        assert code == 0
        assert normalized == "2*s"
        result, code, _out, _err = _run(expr)
        assert code == 0
        assert isinstance(result, UnitValue)
        assert result.value == pytest.approx(2)
        assert result.unit == "s"


class TestUnitSpacingProbes:
    """Whitespace around unit suffixes and conversions must not affect parsing."""

    @pytest.mark.parametrize("expr", ["5m", "5 m", "5   m", "5\tm"])
    def test_simple_unit_suffix_spacing(self, expr):
        normalized, code = normalize_expression(expr, NORMALIZE, PATTERNS)
        assert code == 0
        assert normalized == "5*m"
        result, code, _out, _err = _run(expr)
        assert code == 0
        assert isinstance(result, UnitValue)
        assert result.value == pytest.approx(5)
        assert result.unit == "m"

    @pytest.mark.parametrize("expr,expected_normalized,expected_unit", [
        ("2min", "2*min", "min"),
        ("2 min", "2*min", "min"),
        ("2   min", "2*min", "min"),
        ("2radians", "2*rad", "rad"),
        ("2 radians", "2*rad", "rad"),
    ])
    def test_unit_suffix_function_name_collision_spacing(self, expr, expected_normalized, expected_unit):
        normalized, code = normalize_expression(expr, NORMALIZE, PATTERNS)
        assert code == 0
        assert normalized == expected_normalized
        result, code, _out, _err = _run(expr)
        assert code == 0
        assert isinstance(result, UnitValue)
        assert result.value == pytest.approx(2)
        assert result.unit == expected_unit

    @pytest.mark.parametrize("expr", ["5m+2m", "5 m + 2 m", "5 m+2m", "5m +2 m"])
    def test_unit_addition_spacing(self, expr):
        normalized, code = normalize_expression(expr, NORMALIZE, PATTERNS)
        assert code == 0
        assert normalized == "5*m+2*m"
        result, code, _out, _err = _run(expr)
        assert code == 0
        assert isinstance(result, UnitValue)
        assert result.value == pytest.approx(7)
        assert result.unit == "m"

    @pytest.mark.parametrize("expr", ["5m/2s", "5 m / 2 s", "5 m/ 2 s", "5m /2s"])
    def test_unit_division_spacing(self, expr):
        normalized, code = normalize_expression(expr, NORMALIZE, PATTERNS)
        assert code == 0
        assert normalized == "5*m/(2*s)"
        result, code, _out, _err = _run(expr)
        assert code == 0
        assert isinstance(result, UnitValue)
        assert result.value == pytest.approx(2.5)
        assert result.unit == "m/s"

    @pytest.mark.parametrize("expr", ["1kg in g", "1 kg in g", "1 kg  in   g"])
    def test_simple_unit_conversion_spacing(self, expr):
        normalized, code = normalize_expression(expr, NORMALIZE, PATTERNS)
        assert code == 0
        assert normalized == "convert(1*kg,g)"
        result, code, _out, _err = _run(expr)
        assert code == 0
        assert isinstance(result, UnitValue)
        assert result.value == pytest.approx(1000)
        assert result.unit == "g"

    @pytest.mark.parametrize("expr", ["5in in cm", "5 in in cm", "5 in to cm", "5  in   in   cm"])
    def test_inch_conversion_spacing(self, expr):
        normalized, code = normalize_expression(expr, NORMALIZE, PATTERNS)
        assert code == 0
        assert normalized == "convert(5*inch,cm)"
        result, code, _out, _err = _run(expr)
        assert code == 0
        assert isinstance(result, UnitValue)
        assert result.value == pytest.approx(12.7)
        assert result.unit == "cm"

    @pytest.mark.parametrize("expr", ["30km/h in mph", "30 km/h in mph", "30 km / h in mph", "30km / h in mph"])
    def test_compound_speed_conversion_spacing(self, expr):
        normalized, code = normalize_expression(expr, NORMALIZE, PATTERNS)
        assert code == 0
        assert normalized == "convert(30*km/h,mph)"
        result, code, _out, _err = _run(expr)
        assert code == 0
        assert isinstance(result, UnitValue)
        assert result.value == pytest.approx(18.641135767120023)
        assert result.unit == "mph"

    @pytest.mark.parametrize("expr", ["30 km / h to m / s", "30km/h to m/s", "30 km/h to m / s"])
    def test_compound_speed_target_spacing(self, expr):
        normalized, code = normalize_expression(expr, NORMALIZE, PATTERNS)
        assert code == 0
        assert normalized == "convert(30*km/h,m/s)"
        result, code, _out, _err = _run(expr)
        assert code == 0
        assert isinstance(result, UnitValue)
        assert result.value == pytest.approx(8.333333333333334)
        assert result.unit == "m/s"

    @pytest.mark.parametrize(
        ("expr", "expected_unit", "expected_value"),
        [
            ("30 kilometers per hour in miles per hour", "mph", 18.641135767120023),
            ("30 miles per hour in kilometers per hour", "km/h", 48.28032),
            ("30 miles/hour in km/hour", "km/h", 48.28032),
            ("30 mph in kilometers per hour", "km/h", 48.28032),
            ("30 meters per second in feet per second", "ft/s", 98.42519685039369),
            ("30 feet per second in meters per second", "m/s", 9.144),
            ("-1 kelvin in celsius", "C", -274.15),
        ],
    )
    def test_unit_conversion_word_forms(self, expr, expected_unit, expected_value):
        normalized, code = normalize_expression(expr, NORMALIZE, PATTERNS)
        assert code == 0
        assert "IN" not in normalized
        assert normalized.startswith("convert(")
        result, code, _out, _err = _run(expr)
        assert code == 0
        assert isinstance(result, UnitValue)
        assert result.value == pytest.approx(expected_value)
        assert result.unit == expected_unit

    @pytest.mark.parametrize("expr", ["2 ft/s in m/s", "2 ft / s in m / s", "2ft/s in m / s"])
    def test_foot_per_second_conversion_spacing(self, expr):
        normalized, code = normalize_expression(expr, NORMALIZE, PATTERNS)
        assert code == 0
        assert normalized == "convert(2*ft/s,m/s)"
        result, code, _out, _err = _run(expr)
        assert code == 0
        assert isinstance(result, UnitValue)
        assert result.value == pytest.approx(0.6096)
        assert result.unit == "m/s"

    @pytest.mark.parametrize("expr", ["5 N m", "5 N   m", "5\tN\tm"])
    def test_spaced_unit_product_not_collapsed_to_prefixed_unit(self, expr):
        normalized, code = normalize_expression(expr, NORMALIZE, PATTERNS)
        assert code == 0
        assert normalized == "5*N*m"
        result, code, _out, _err = _run(expr)
        assert code == 0
        assert isinstance(result, UnitValue)
        assert result.value == pytest.approx(5)
        assert result.unit == "N*m"

    @pytest.mark.parametrize("expr", ["5 m s", "5 m   s", "5\tm\ts"])
    def test_spaced_meter_second_not_collapsed_to_millisecond(self, expr):
        normalized, code = normalize_expression(expr, NORMALIZE, PATTERNS)
        assert code == 0
        assert normalized == "5*m*s"
        result, code, _out, _err = _run(expr)
        assert code == 0
        assert isinstance(result, UnitValue)
        assert result.value == pytest.approx(5)
        assert result.unit == "m*s"

    @pytest.mark.parametrize("expr", ["5 kg m / s ** 2", "5 kg   m / s**2"])
    def test_spaced_compound_unit_product_with_denominator(self, expr):
        normalized, code = normalize_expression(expr, NORMALIZE, PATTERNS)
        assert code == 0
        assert normalized == "5*kg*m/s**2"
        result, code, _out, _err = _run(expr)
        assert code == 0
        assert isinstance(result, UnitValue)
        assert result.value == pytest.approx(5)
        assert result.unit == "kg*m/s**2"

    @pytest.mark.parametrize("expr", ["5 m/s^2", "5 m / s ^ 2"])
    def test_compound_unit_denominator_caret_spacing(self, expr):
        normalized, code = normalize_expression(expr, NORMALIZE, PATTERNS)
        assert code == 0
        assert normalized in ("5*m/s**2", "(5*m)/(s)**2")
        result, code, _out, _err = _run(expr)
        assert code == 0
        assert isinstance(result, UnitValue)
        assert result.value == pytest.approx(5)
        assert result.unit == "m/s**2"

    @pytest.mark.parametrize("expr", ["100 c in f", "100 c to fahrenheit"])
    def test_lowercase_temperature_conversion_spacing(self, expr):
        normalized, code = normalize_expression(expr, NORMALIZE, PATTERNS)
        assert code == 0
        assert normalized == "convert(100*C,F)"
        result, code, _out, _err = _run(expr)
        assert code == 0
        assert isinstance(result, UnitValue)
        assert result.value == pytest.approx(212)
        assert result.unit == "F"

    def test_spaced_pascal_second_not_collapsed_identifier(self):
        normalized, code = normalize_expression("5 Pa s", NORMALIZE, PATTERNS)
        assert code == 0
        assert normalized == "5*Pa*s"
        result, code, _out, _err = _run("5 Pa s")
        assert code == 0
        assert isinstance(result, UnitValue)
        assert result.value == pytest.approx(5)
        assert result.unit == "Pa*s"


class TestNumberWordSubstringBoundary:
    """Regression tests for the substring-vs-word-boundary bug in
    ``convert_from_human_handler``. Words like "one" must not be replaced
    when they appear as a substring of another word ("None", "Phone",
    "stone", "done"), but bare number words must still convert normally.
    """

    def test_none_does_not_become_one(self):
        from eggcalc.normalize import NORMALIZE, PATTERNS, normalize_expression
        normalized, code = normalize_expression("None", NORMALIZE, PATTERNS)
        # "None" is not a recognized number word; it should not become "1".
        assert normalized != "1"
        assert code != 0

    def test_phone_does_not_become_one(self):
        from eggcalc.normalize import NORMALIZE, PATTERNS, normalize_expression
        normalized, code = normalize_expression("Phone", NORMALIZE, PATTERNS)
        assert normalized != "1"
        assert code != 0

    def test_stone_does_not_become_one(self):
        from eggcalc.normalize import NORMALIZE, PATTERNS, normalize_expression
        normalized, _code = normalize_expression("stone", NORMALIZE, PATTERNS)
        # The substring "one" inside "stone" must not be replaced.
        assert normalized != "1"
        assert "1" not in normalized

    def test_bare_one_still_converts(self):
        from eggcalc.normalize import NORMALIZE, PATTERNS, normalize_expression
        normalized, code = normalize_expression("one", NORMALIZE, PATTERNS)
        assert normalized == "1"
        assert code == 0

    def test_compound_number_word_still_converts(self):
        from eggcalc.normalize import NORMALIZE, PATTERNS, normalize_expression
        normalized, code = normalize_expression("twenty one", NORMALIZE, PATTERNS)
        # "twenty one" is now recognized as a compound number -> 21
        assert normalized == "21"
        assert code == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
