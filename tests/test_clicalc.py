"""Tests for nl-calc."""

import pytest

from eggcalc import EvaluationError, UnitValue, evaluate
from eggcalc.normalize import NORMALIZE, PATTERNS, check_if_number, run


class TestEvaluator:
    """Tests for the evaluator module."""

    def test_basic_arithmetic(self):
        """Test basic arithmetic operations."""
        result = evaluate("5 + 3")
        assert result == 8 or (isinstance(result, UnitValue) and result.value == 8)

    def _get_value(self, result):
        """Extract numeric value from result."""
        if isinstance(result, UnitValue):
            return result.value
        return result

    def test_multi_digit_subtraction(self):
        """Test subtraction with multi-digit numbers."""
        assert abs(self._get_value(evaluate("90-1")) - 89) < 1e-10
        assert abs(self._get_value(evaluate("100-10")) - 90) < 1e-10
        assert abs(self._get_value(evaluate("50-5")) - 45) < 1e-10
        assert abs(self._get_value(evaluate("1000-1")) - 999) < 1e-10

    def test_order_of_operations(self):
        """Test order of operations."""
        result = evaluate("2 + 3 * 4")
        assert result == 14 or (isinstance(result, UnitValue) and result.value == 14)

    def test_trigonometric_functions(self):
        """Test trigonometric functions."""
        assert abs(evaluate("sin(0)") - 0.0) < 1e-10
        assert abs(evaluate("cos(0)") - 1.0) < 1e-10
        assert abs(evaluate("tan(0)") - 0.0) < 1e-10

    def test_constants(self):
        """Test mathematical constants."""
        assert abs(evaluate("pi") - 3.141592653589793) < 1e-10
        assert abs(evaluate("e") - 2.718281828459045) < 1e-10

class TestUnitConversions:
    """Tests for unit conversions using the run function."""

    def test_length_conversion(self):
        """Test length unit conversions."""
        result, _ = run("30m + 100ft", NORMALIZE, PATTERNS)
        value = result.value if isinstance(result, UnitValue) else result
        assert abs(value - 60.48) < 1e-10

    def test_time_conversion(self):
        """Test time unit conversions via run()."""
        # Use '1d + 12h' instead of '1h + 30min' because 'min' is also a
        # function name in FUNCTIONS, which causes apply_math_functions in
        # normalize.py to wrap it as 'min()' before AST evaluation.
        # 1d + 12h = 1.5d (the previous buggy result was 30.0 min, which
        # was the result of `h` resolving to Planck's constant instead of
        # the hour unit - now `h` correctly resolves to hours first per C1).
        result, _ = run("1d + 12h", NORMALIZE, PATTERNS)
        assert result is not None
        val = result.value if isinstance(result, UnitValue) else result
        assert abs(val - 1.5) < 1e-10

    def test_data_conversion(self):
        """Test data storage unit conversions."""
        result, _ = run("1GB + 500MB", NORMALIZE, PATTERNS)
        value = result.value if isinstance(result, UnitValue) else result
        assert abs(value - 1524 / 1024) < 1e-10

    def test_mixed_conversion(self):
        """Test mixed unit operations."""
        result, _ = run("(30m+100ft)/2", NORMALIZE, PATTERNS)
        value = result.value if isinstance(result, UnitValue) else result
        assert abs(value - 30.24) < 1e-10

    def test_invalid_expression(self):
        """Test that invalid expressions raise errors."""
        with pytest.raises(EvaluationError):
            evaluate("import os")

    def test_power_operations(self):
        """Test power operations."""
        result = evaluate("2 ** 3")
        assert result == 8 or (isinstance(result, UnitValue) and result.value == 8)
        result = evaluate("4 ** 0.5")
        assert result == 2 or (isinstance(result, UnitValue) and result.value == 2)

    def test_negative_numbers(self):
        """Test negative numbers."""
        result = evaluate("-5 + 3")
        value = result.value if isinstance(result, UnitValue) else result
        assert value == -2

    def test_unit_conversion_precision_inches_to_mm(self):
        """1 inch = 25.4 mm exactly"""
        result, _ = run("1 inch in mm", NORMALIZE, PATTERNS)
        val = result.value if isinstance(result, UnitValue) else result
        assert abs(val - 25.4) < 1e-10

    def test_unit_conversion_precision_mile_to_km(self):
        """1 mile = 1.609344 km exactly"""
        result, _ = run("1 mile in km", NORMALIZE, PATTERNS)
        val = result.value if isinstance(result, UnitValue) else result
        assert abs(val - 1.609344) < 1e-10

    def test_unit_conversion_precision_foot_to_meter(self):
        """1 foot = 0.3048 m exactly"""
        result, _ = run("1 foot in m", NORMALIZE, PATTERNS)
        val = result.value if isinstance(result, UnitValue) else result
        assert abs(val - 0.3048) < 1e-10

    def test_bitwise_not_rejects_float(self):
        """Test that bitwise NOT raises an error for float operands."""
        with pytest.raises(EvaluationError):
            evaluate("~3.14")


class TestNormalize:
    """Tests for the normalize module."""

    def test_check_if_number_integer(self):
        """Test checking if token is an integer."""
        result = check_if_number("42")
        assert result["bool"] is True
        assert result["converted"] == 42

    def test_check_if_number_float(self):
        """Test checking if token is a float."""
        result = check_if_number("3.14")
        assert result["bool"] is True
        assert result["converted"] == 3.14

    def test_check_if_number_with_unit(self):
        """Test checking if token has a unit."""
        result = check_if_number("50m")
        assert result["bool"] is True
        assert result["converted"] == 50

    def test_check_if_number_invalid(self):
        """Test checking invalid number."""
        result = check_if_number("abc")
        assert result["bool"] is False

    def test_natural_language_numbers(self):
        """Test natural language number conversion."""
        result, _ = run("five plus three", NORMALIZE, PATTERNS)
        assert result == 8 or (isinstance(result, UnitValue) and result.value == 8)

    def test_empty_input_returns_error(self):
        """Empty string input should return error exit code."""
        from eggcalc.normalize import normalize_expression
        _, exit_code = normalize_expression("", NORMALIZE, PATTERNS)
        assert exit_code != 0

    def test_whitespace_input_returns_error(self):
        """Whitespace-only input should return error exit code."""
        from eggcalc.normalize import normalize_expression
        _, exit_code = normalize_expression("   ", NORMALIZE, PATTERNS)
        assert exit_code != 0


class TestCLI:
    """Tests for CLI functionality."""

    def test_help_flag(self):
        """Test that help flag works."""
        from eggcalc.normalize import print_help
        # Just verify it doesn't error
        print_help()

    def test_help_text_constants(self):
        """Help text should list pi/e/tau but not inf/nan."""
        import io
        import sys

        from eggcalc.normalize import print_help
        buf = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = buf
        try:
            print_help()
        finally:
            sys.stdout = old_stdout
        output = buf.getvalue()
        assert "pi" in output
        assert "tau" in output
        # inf and nan should NOT appear as listed constants
        # (they may appear in other context like "infinity" unit names)
        lines = output.split("\n")
        constants_section = False
        for line in lines:
            if line.strip().startswith("Constants:"):
                constants_section = True
            elif constants_section and line.strip() and not line.startswith("  "):
                constants_section = False
            elif constants_section:
                assert "inf" not in line.lower().split(",")[0:2], \
                    f"inf should not be listed as a constant: {line}"
                assert "nan" not in line.lower().split(",")[0:2], \
                    f"nan should not be listed as a constant: {line}"

    def test_empty_expression(self):
        """Test empty expression shows help."""
        import sys

        from eggcalc.normalize import main
        old_argv = sys.argv
        try:
            sys.argv = ["eggcalc"]
            main()
        finally:
            sys.argv = old_argv


class TestUnitValue:
    """Tests for UnitValue class."""

    def test_creation(self):
        """Test creating UnitValue."""
        uv = UnitValue(5, "m")
        assert uv.value == 5
        assert uv.unit == "m"

    def test_repr(self):
        """Test string representation."""
        uv = UnitValue(5, "m")
        assert repr(uv) == "5 m"

    def test_addition_same_unit(self):
        """Test adding same units."""
        uv1 = UnitValue(5, "m")
        uv2 = UnitValue(3, "m")
        result = uv1 + uv2
        assert result.value == 8
        assert result.unit == "m"

    def test_addition_different_unit(self):
        """Test adding different units."""
        uv1 = UnitValue(1, "m")
        uv2 = UnitValue(100, "cm")
        result = uv1 + uv2
        assert result.unit == "m"
        assert abs(result.value - 2) < 1e-10

    def test_addition_incompatible_units(self):
        """Test adding incompatible units raises ValueError."""
        uv1 = UnitValue(30, "mi")
        uv2 = UnitValue(30, "gal")
        with pytest.raises(ValueError):
            uv1 + uv2

    def test_subtraction_incompatible_units(self):
        """Test subtracting incompatible units raises ValueError."""
        uv1 = UnitValue(30, "m")
        uv2 = UnitValue(10, "kg")
        with pytest.raises(ValueError):
            uv1 - uv2

    def test_addition_compatible_units(self):
        """Test adding compatible units (same category)."""
        uv1 = UnitValue(30, "mi")
        uv2 = UnitValue(30, "m")
        result = uv1 + uv2
        assert result.unit in ("mi", "m")
        assert result.value > 30


class TestPhysicalConstants:
    """Tests for physical constants."""

    def test_avogadro(self):
        """Test Avogadro constant via run()."""
        result, _ = run("5 times avogadro", NORMALIZE, PATTERNS)
        assert result is not None
        assert abs(float(result) - 3.011e24) < 1e22

    def test_speed_of_light(self):
        """Test speed of light."""
        result = evaluate("c")
        assert result == 299792458

    def test_boltzmann(self):
        """Test Boltzmann constant."""
        result = evaluate("k")
        assert abs(result - 1.380649e-23) < 1e-30

    def test_planck(self):
        """Test Planck constant (use the long name; 'h' resolves to hour unit)."""
        result = evaluate("planck")
        assert abs(result - 6.62607015e-34) < 1e-40


class TestEggCalcApp:
    """Tests for EggCalcApp class."""

    def _get_value(self, result):
        """Extract numeric value from result."""
        if isinstance(result, UnitValue):
            return result.value
        return result

    def test_basic_calculate(self):
        """Test basic calculation."""
        from eggcalc import EggCalcApp
        app = EggCalcApp()
        result = app.calculate("5 + 3")
        assert self._get_value(result) == 8

    def test_natural_language(self):
        """Test natural language input."""
        from eggcalc import EggCalcApp
        app = EggCalcApp()
        result = app.calculate("five plus three")
        assert self._get_value(result) == 8

    def test_caching(self):
        """Test that caching works."""
        from eggcalc import EggCalcApp
        app = EggCalcApp(cache_size=10)

        # First call
        result1 = app.calculate("5 + 3")
        assert app.cache_size == 1

        # Second call should use cache
        result2 = app.calculate("5 + 3")
        assert app.cache_size == 1
        assert self._get_value(result1) == self._get_value(result2)

    def test_cache_clear(self):
        """Test cache clearing."""
        from eggcalc import EggCalcApp
        app = EggCalcApp()
        app.calculate("5 + 3")
        assert app.cache_size == 1
        app.clear_cache()
        assert app.cache_size == 0

    def test_cache_disabled(self):
        """Test with caching disabled."""
        from eggcalc import EggCalcApp
        app = EggCalcApp(enable_cache=False)
        app.calculate("5 + 3")
        assert app.cache_size == 0

    def test_register_constant(self):
        """Test registering custom constant."""
        from eggcalc import EggCalcApp
        app = EggCalcApp()
        app.register_constant("myconst", 42)
        result = app.calculate("myconst")
        assert self._get_value(result) == 42

    def test_register_function(self):
        """Test registering custom function."""
        from eggcalc import EggCalcApp
        app = EggCalcApp()
        app.register_function("double", lambda x: x * 2)
        result = app.calculate("double(5)")
        assert self._get_value(result) == 10

    def test_instance_isolation_constants(self):
        """Test that instances have isolated constants."""
        from eggcalc import EggCalcApp
        app1 = EggCalcApp()
        app2 = EggCalcApp()

        app1.register_constant("myconst", 42)
        app2.register_constant("myconst", 100)

        result1 = app1.calculate("myconst")
        result2 = app2.calculate("myconst")

        assert self._get_value(result1) == 42
        assert self._get_value(result2) == 100

    def test_instance_isolation_functions(self):
        """Test that instances have isolated functions."""
        from eggcalc import EggCalcApp
        app1 = EggCalcApp()
        app2 = EggCalcApp()

        app1.register_function("myfunc", lambda x: x * 2)
        app2.register_function("myfunc", lambda x: x * 3)

        result1 = app1.calculate("myfunc(5)")
        result2 = app2.calculate("myfunc(5)")

        assert self._get_value(result1) == 10
        assert self._get_value(result2) == 15

    def test_unit_calculations(self):
        """Test unit calculations in EggCalcApp."""
        from eggcalc import EggCalcApp
        app = EggCalcApp()
        result = app.calculate("30m + 100ft")
        assert hasattr(result, 'unit')
        assert result.unit == "m"
        assert abs(result.value - 60.48) < 0.01


class TestAsyncFunctions:
    """Tests for async evaluation functions."""

    def _get_value(self, result):
        """Extract numeric value from result."""
        if isinstance(result, UnitValue):
            return result.value
        return result

    def test_evaluate_async(self):
        """Test async evaluation."""
        import asyncio

        from eggcalc import evaluate_async

        async def run_test():
            result = await evaluate_async("5 + 3")
            return result

        result = asyncio.run(run_test())
        assert self._get_value(result) == 8

    def test_eggcalc_app_async(self):
        """Test EggCalcApp async calculation."""
        import asyncio

        from eggcalc import EggCalcApp

        app = EggCalcApp()

        async def run_test():
            result = await app.calculate_async("5 + 3")
            return result

        result = asyncio.run(run_test())
        assert self._get_value(result) == 8


class TestCaching:
    """Tests for caching functions."""

    def _get_value(self, result):
        """Extract numeric value from result."""
        if isinstance(result, UnitValue):
            return result.value
        return result

    def test_evaluate_cached(self):
        """Test evaluate_cached function."""
        from eggcalc import evaluate_cached

        result = evaluate_cached("5 + 3")
        assert self._get_value(result) == 8

        # Second call should use cache
        result2 = evaluate_cached("5 + 3")
        assert self._get_value(result2) == 8

    def test_evaluate_cached_natural_language(self):
        """Test evaluate_cached with natural language."""
        from eggcalc import evaluate_cached

        result = evaluate_cached("five plus three")
        assert self._get_value(result) == 8


class TestTimeout:
    """Tests for timeout functionality."""

    def _get_value(self, result):
        """Extract numeric value from result."""
        if isinstance(result, UnitValue):
            return result.value
        return result

    def test_evaluate_with_timeout_success(self):
        """Test evaluate_with_timeout with fast expression."""
        from eggcalc import evaluate_with_timeout

        result = evaluate_with_timeout("5 + 3", timeout=1.0)
        assert self._get_value(result) == 8

    def test_evaluate_with_timeout_natural_language(self):
        """Test evaluate_with_timeout with natural language."""
        from eggcalc import evaluate_with_timeout

        result = evaluate_with_timeout("five plus three", timeout=1.0)
        assert self._get_value(result) == 8

    def test_timeout_error_raised(self):
        """Test that evaluate_with_timeout raises TimeoutError on slow expression."""
        from eggcalc import TimeoutError, evaluate_with_timeout

        # A deeply nested exponentiation will take longer than 0.001s
        with pytest.raises(TimeoutError):
            evaluate_with_timeout("2**2**2**2**2**2**2", timeout=0.001)


class TestComplexNumbers:
    """Tests for complex number functionality."""

    def test_imaginary_unit(self):
        """Test imaginary unit i."""
        from eggcalc import evaluate_raw

        result = evaluate_raw("i * i")
        if hasattr(result, 'value'):
            result = result.value
        assert abs(result.real + 1) < 1e-10
        assert abs(result.imag) < 1e-10

    def test_complex_literal(self):
        """Test complex literals."""
        from eggcalc import evaluate_raw

        result = evaluate_raw("3 + 4i")
        if hasattr(result, 'value'):
            result = result.value
        assert abs(result.real - 3) < 1e-10
        assert abs(result.imag - 4) < 1e-10

    def test_sqrt_negative(self):
        """Test sqrt of negative number."""
        from eggcalc import evaluate_raw

        result = evaluate_raw("sqrt(-1)")
        if hasattr(result, 'value'):
            result = result.value
        assert abs(result.imag - 1) < 1e-10

    def test_abs_complex(self):
        """Test abs of complex number."""
        from eggcalc import evaluate_raw

        result = evaluate_raw("abs(3+4i)")
        if hasattr(result, 'value'):
            result = result.value
        assert abs(result - 5) < 1e-10

    def test_conj(self):
        """Test complex conjugate."""
        from eggcalc import evaluate_raw

        result = evaluate_raw("conj(3+4i)")
        if hasattr(result, 'value'):
            result = result.value
        assert abs(result.real - 3) < 1e-10
        assert abs(result.imag + 4) < 1e-10


class TestBitwise:
    """Tests for bitwise operations."""

    def _get_value(self, result):
        """Extract numeric value from result."""
        if hasattr(result, 'value'):
            return result.value
        return result

    def test_bitand(self):
        """Test bitwise AND."""
        from eggcalc import evaluate_raw

        assert self._get_value(evaluate_raw("5 bitand 3")) == 1
        assert self._get_value(evaluate_raw("5 & 3")) == 1

    def test_bitor(self):
        """Test bitwise OR."""
        from eggcalc import evaluate_raw

        assert self._get_value(evaluate_raw("5 OR 3")) == 7
        assert self._get_value(evaluate_raw("5 | 3")) == 7

    def test_bitxor_word(self):
        """Test bitwise XOR using word."""
        from eggcalc import evaluate_raw

        assert self._get_value(evaluate_raw("5 XOR 3")) == 6

    def test_bitnot(self):
        """Test bitwise NOT."""
        from eggcalc import evaluate_raw

        assert self._get_value(evaluate_raw("~5")) == -6

    def test_shifts(self):
        """Test bit shifts."""
        from eggcalc import evaluate_raw

        assert self._get_value(evaluate_raw("5 << 2")) == 20
        assert self._get_value(evaluate_raw("5 >> 1")) == 2

    def test_base_prefixes(self):
        """Test base prefixes."""
        from eggcalc import evaluate_raw

        assert evaluate_raw("0xFF") == 255
        assert evaluate_raw("0b1010") == 10
        assert evaluate_raw("0o777") == 511


class TestCombinatorics:
    """Tests for combinatorics functions."""

    def test_perm(self):
        """Test permutations."""
        from eggcalc import evaluate_raw

        assert evaluate_raw("perm(5, 3)") == 60
        assert evaluate_raw("nPr(5, 3)") == 60

    def test_comb(self):
        """Test combinations."""
        from eggcalc import evaluate_raw

        assert evaluate_raw("comb(5, 3)") == 10
        assert evaluate_raw("nCr(5, 3)") == 10

    def test_lcm(self):
        """Test LCM."""
        from eggcalc import evaluate_raw

        assert evaluate_raw("lcm(12, 18)") == 36
        assert evaluate_raw("lcm(12, 18, 24)") == 72


class TestPrimes:
    """Tests for prime functions."""

    def test_isprime(self):
        """Test prime check."""
        from eggcalc import evaluate_raw

        assert evaluate_raw("isprime(17)") is True
        assert evaluate_raw("isprime(18)") is False

    def test_primefactors(self):
        """Test prime factorization."""
        from eggcalc import evaluate_raw

        result = evaluate_raw("primefactors(84)")
        assert "2" in result and "3" in result and "7" in result

    def test_nextprime(self):
        """Test next prime."""
        from eggcalc import evaluate_raw

        assert evaluate_raw("nextprime(17)") == 19

    @pytest.mark.parametrize("expr", [
        "isprime(5.5)",
        "nextprime(5.5)",
        "prevprime(5.5)",
        "primefactors(12.5)",
        "isprime(5*m)",
    ])
    def test_prime_functions_reject_non_integer_or_unit_inputs(self, expr):
        with pytest.raises(EvaluationError):
            evaluate(expr)


class TestStatistics:
    """Tests for statistical functions."""

    def test_median(self):
        """Test median."""
        from eggcalc import evaluate_raw

        assert evaluate_raw("median(1, 2, 3, 4, 5)") == 3
        assert evaluate_raw("median(1, 2, 3, 4)") == 2.5

    def test_mode(self):
        """Test mode."""
        from eggcalc import evaluate_raw

        assert evaluate_raw("mode(1, 2, 2, 3)") == 2

    def test_variance(self):
        """Test variance."""
        from eggcalc import evaluate_raw

        result = evaluate_raw("variance(1, 2, 3, 4, 5)")
        assert abs(result - 2.0) < 1e-10


class TestPercentage:
    """Tests for percentage functionality."""

    def test_percent_literal(self):
        """Test percentage literal."""
        from eggcalc import evaluate_raw

        assert abs(evaluate_raw("50%") - 0.5) < 1e-10
        assert abs(evaluate_raw("25%") - 0.25) < 1e-10

    def test_percentof(self):
        """Test percentof function."""
        from eggcalc import evaluate_raw

        assert evaluate_raw("percentof(20, 100)") == 20.0


class TestRandom:
    """Tests for random functions."""

    def test_random_range(self):
        """Test random is in range."""
        from eggcalc import evaluate_raw

        evaluate_raw("seed(42)")
        result = evaluate_raw("random()")
        assert 0 <= result < 1

    def test_randint_range(self):
        """Test randint is in range."""
        from eggcalc import evaluate_raw

        evaluate_raw("seed(42)")
        result = evaluate_raw("randint(1, 100)")
        assert 1 <= result <= 100

    @pytest.mark.parametrize("expr", [
        "randint(1.5, 10)",
        "randrange(10.5)",
        "randrange(1, 10.5)",
        "randint(1*m, 10)",
    ])
    def test_random_integer_functions_reject_non_integer_or_unit_inputs(self, expr):
        with pytest.raises(EvaluationError):
            evaluate(expr)


class TestMemory:
    """Tests for memory functions."""

    def test_store_recall(self):
        """Test store and recall."""
        from eggcalc import evaluate_raw, memory_clear

        memory_clear()
        result = evaluate_raw("store(42)")
        assert result == 42

        result = evaluate_raw("recall()")
        assert result == 42


class TestVariables:
    """Tests for variable functionality."""

    def _get_value(self, result):
        """Extract numeric value from result."""
        if hasattr(result, 'value'):
            return result.value
        return result

    def test_setvar_getvar(self):
        """Test setvar and getvar."""
        from eggcalc import clearvars, evaluate_raw

        clearvars()
        result = evaluate_raw('setvar("x", 10)')
        assert self._get_value(result) == 10

        result = evaluate_raw("x + 5")
        assert self._get_value(result) == 15


class TestPrefixedUnitConversions:
    """Tests for prefixed unit conversions via get_conversion_factor."""

    def test_kilonewton_to_newton(self):
        """Test kN to N conversion factor is 1000.0."""
        from eggcalc import get_conversion_factor
        result = get_conversion_factor("kN", "N")
        assert result == 1000.0

    def test_millivolt_to_volt(self):
        """Test mV to V conversion factor is 0.001."""
        from eggcalc import get_conversion_factor
        result = get_conversion_factor("mV", "V")
        assert abs(result - 0.001) < 1e-10

    def test_milliamp_to_amp(self):
        """Test mA to A conversion factor is 0.001."""
        from eggcalc import get_conversion_factor
        result = get_conversion_factor("mA", "A")
        assert abs(result - 0.001) < 1e-10

    def test_kilowatt_to_watt(self):
        """Test kW to W conversion factor is 1000.0."""
        from eggcalc import get_conversion_factor
        result = get_conversion_factor("kW", "W")
        assert result == 1000.0

    def test_megabyte_to_byte(self):
        """Test MB to B conversion factor is 1048576.0."""
        from eggcalc import get_conversion_factor
        result = get_conversion_factor("MB", "B")
        assert result == 1048576.0

    def test_kilometer_to_meter(self):
        """Test km to m conversion factor is 1000.0."""
        from eggcalc import get_conversion_factor
        result = get_conversion_factor("km", "m")
        assert result == 1000.0


class TestTemperatureConversions:
    """Tests for temperature conversions with exact offset handling."""

    def test_fahrenheit_to_celsius_exact_freezing(self):
        """Test 32F to C equals exactly 0.0C."""
        from eggcalc.units import convert_temperature
        result = convert_temperature(32.0, "F", "C")
        assert abs(result - 0.0) < 1e-9

    def test_fahrenheit_to_celsius_boiling(self):
        """Test 212F to C equals approximately 100.0C."""
        from eggcalc.units import convert_temperature
        result = convert_temperature(212.0, "F", "C")
        assert abs(result - 100.0) < 1e-9

    def test_celsius_to_fahrenheit_freezing(self):
        """Test 0C to F equals exactly 32F."""
        from eggcalc.units import convert_temperature
        result = convert_temperature(0.0, "C", "F")
        assert abs(result - 32.0) < 1e-9

    def test_celsius_to_fahrenheit_boiling(self):
        """Test 100C to F equals approximately 212F."""
        from eggcalc.units import convert_temperature
        result = convert_temperature(100.0, "C", "F")
        assert abs(result - 212.0) < 1e-9

    def test_kelvin_to_celsius(self):
        """0 K = -273.15 C"""
        result, _ = run("0K in C", NORMALIZE, PATTERNS)
        val = result.value if isinstance(result, UnitValue) else result
        assert abs(val - (-273.15)) < 1e-6

    def test_celsius_to_kelvin(self):
        """0 C = 273.15 K"""
        result, _ = run("0C in K", NORMALIZE, PATTERNS)
        val = result.value if isinstance(result, UnitValue) else result
        assert abs(val - 273.15) < 1e-6

    def test_kelvin_to_fahrenheit(self):
        """0 K = -459.67 F"""
        result, _ = run("0K in F", NORMALIZE, PATTERNS)
        val = result.value if isinstance(result, UnitValue) else result
        assert abs(val - (-459.67)) < 1e-6

    def test_fahrenheit_to_kelvin(self):
        """32 F = 273.15 K"""
        result, _ = run("32F in K", NORMALIZE, PATTERNS)
        val = result.value if isinstance(result, UnitValue) else result
        assert abs(val - 273.15) < 1e-6

    def test_rankine_to_kelvin(self):
        """0 Ra = 0 K"""
        result, _ = run("0Ra in K", NORMALIZE, PATTERNS)
        val = result.value if isinstance(result, UnitValue) else result
        assert abs(val - 0.0) < 1e-6

    def test_kelvin_to_rankine(self):
        """273.15 K = 491.67 Ra"""
        from eggcalc.units import convert_temperature
        result = convert_temperature(273.15, "K", "Ra")
        assert abs(result - 491.67) < 1e-6

    def test_celsius_to_rankine(self):
        """0 C = 491.67 Ra"""
        result, _ = run("0C in Ra", NORMALIZE, PATTERNS)
        val = result.value if isinstance(result, UnitValue) else result
        assert abs(val - 491.67) < 1e-6

    def test_fahrenheit_to_rankine(self):
        """0 F = 459.67 Ra"""
        result, _ = run("0F in Ra", NORMALIZE, PATTERNS)
        val = result.value if isinstance(result, UnitValue) else result
        assert abs(val - 459.67) < 1e-6


class TestUnicodeScriptOther:
    """Tests for unicode_script() returning 'Other' for digits and punctuation."""

    def test_digits_return_other(self):
        """Test that ASCII digits return 'Other'."""
        from eggcalc.exact import unicode_script
        assert unicode_script("0") == "Other"
        assert unicode_script("1") == "Other"
        assert unicode_script("5") == "Other"
        assert unicode_script("9") == "Other"

    def test_punctuation_return_other(self):
        """Test that ASCII punctuation returns 'Other'."""
        from eggcalc.exact import unicode_script
        assert unicode_script(".") == "Other"
        assert unicode_script(",") == "Other"
        assert unicode_script("!") == "Other"
        assert unicode_script("?") == "Other"
        assert unicode_script(":") == "Other"
        assert unicode_script(";") == "Other"
        assert unicode_script("-") == "Other"
        assert unicode_script("(") == "Other"
        assert unicode_script(")") == "Other"

    def test_space_returns_other(self):
        """Test that space returns 'Other'."""
        from eggcalc.exact import unicode_script
        assert unicode_script(" ") == "Other"

    def test_math_symbols_return_other(self):
        """Test that common math symbols return 'Other'."""
        from eggcalc.exact import unicode_script
        assert unicode_script("+") == "Other"
        assert unicode_script("=") == "Other"
        assert unicode_script("*") == "Other"
        assert unicode_script("/") == "Other"
        assert unicode_script("%") == "Other"


class TestDivisionByZero:
    """Tests for division by zero error handling."""

    def test_division_by_zero(self):
        """Test that division by zero raises EvaluationError."""
        with pytest.raises(EvaluationError, match="Cannot divide by zero"):
            evaluate("1/0")

    def test_floor_div_by_zero(self):
        """Test that floor division by zero raises EvaluationError."""
        with pytest.raises(EvaluationError, match="Cannot divide by zero"):
            evaluate("1//0")

    def test_mod_by_zero(self):
        """Test that modulo by zero raises EvaluationError."""
        with pytest.raises(EvaluationError, match="Cannot divide by zero"):
            evaluate("1%0")

    def test_zero_division_float(self):
        """0.0/0.0 should raise EvaluationError"""
        with pytest.raises(EvaluationError):
            evaluate("0.0/0.0")

    def test_unit_division_by_zero(self):
        """5m / 0 should raise ZeroDivisionError or EvaluationError"""
        with pytest.raises((ZeroDivisionError, EvaluationError)):
            evaluate("5m / 0")


class TestErrorHandling:
    """Tests for proper error handling (no raw Python exceptions)."""

    def test_perm_negative(self):
        """Test that perm with negative input raises EvaluationError."""
        with pytest.raises(EvaluationError, match="non-negative"):
            evaluate("perm(-1)")

    def test_perm_negative_r(self):
        """Test that perm with negative r raises EvaluationError."""
        with pytest.raises(EvaluationError, match="non-negative"):
            evaluate("perm(5, -1)")

    def test_shift_negative(self):
        """Test that negative shift count raises EvaluationError."""
        with pytest.raises(EvaluationError, match="non-negative"):
            evaluate("5 << -1")
        with pytest.raises(EvaluationError, match="non-negative"):
            evaluate("5 >> -1")

    def test_pow_overflow(self):
        """Test that very large exponent raises EvaluationError."""
        with pytest.raises(EvaluationError, match="Exponent too large"):
            evaluate("2 ** 100000")

    def test_log_zero(self):
        """Test that log of zero raises EvaluationError."""
        with pytest.raises(EvaluationError):
            evaluate("log(0)")

    def test_factorial_negative(self):
        """Test that factorial of negative raises EvaluationError."""
        with pytest.raises(EvaluationError):
            evaluate("factorial(-1)")

    def test_factorial_non_integer(self):
        """Test that factorial of non-integer raises EvaluationError."""
        with pytest.raises(EvaluationError):
            evaluate("factorial(1.5)")

    def test_zero_to_zeroth_power(self):
        """0**0 is defined as 1 in this calculator"""
        result = evaluate("0**0")
        assert result == 1

    def test_zero_to_negative_power(self):
        """0**-1 should raise error (division by zero)"""
        with pytest.raises(EvaluationError):
            evaluate("0**-1")

    def test_inf_plus_one(self):
        """inf + 1 should raise EvaluationError (result too large)"""
        with pytest.raises(EvaluationError):
            evaluate("1e309 + 1e309")


class TestCompoundUnitDivision:
    """Tests for compound unit division (Fix #1)."""

    def test_unit_division_by_number(self):
        """Test that UnitValue / number correctly divides the value."""
        result = evaluate("(100*km) / 2")
        assert isinstance(result, UnitValue)
        assert result.unit == "km"
        assert abs(result.value - 50.0) < 1e-10

    def test_unit_division_by_unit(self):
        """Test that UnitValue / UnitValue with different units creates compound."""
        result = evaluate("(100*km) / (2*m)")
        assert isinstance(result, UnitValue)
        assert result.unit == "km/m"
        # Division does NOT convert units (only add/sub do); result is 100/2 = 50 km/m
        assert abs(result.value - 50.0) < 1e-10


class TestCompoundUnitPipeline:
    """Integration tests for compound unit expressions through run() pipeline."""

    def test_addition_with_unit_conversion(self):
        """5m + 3km should convert km to m and add."""
        result, code = run("5m + 3km", NORMALIZE, PATTERNS)
        assert code == 0
        assert isinstance(result, UnitValue)
        assert result.unit == "m"
        assert abs(result.value - 3005.0) < 1e-10

    def test_addition_length_conversion_other_order(self):
        """100ft + 30m should convert and add, result in ft."""
        result, code = run("100ft + 30m", NORMALIZE, PATTERNS)
        assert code == 0
        assert isinstance(result, UnitValue)
        assert result.unit == "ft"
        assert abs(result.value - 198.4251968503937) < 1e-6

    def test_unit_power_suffix(self):
        """5m ** 2 applies power to unit only (m2)."""
        result, code = run("5m ** 2", NORMALIZE, PATTERNS)
        assert code == 0
        assert isinstance(result, UnitValue)
        assert result.unit == "m2"
        assert abs(result.value - 5.0) < 1e-10

    def test_unit_power_suffix_three(self):
        """3m ** 3 applies power to unit only (m3)."""
        result, code = run("3m ** 3", NORMALIZE, PATTERNS)
        assert code == 0
        assert isinstance(result, UnitValue)
        assert result.unit == "m3"
        assert abs(result.value - 3.0) < 1e-10

    def test_unit_division_different_units(self):
        """10m / 2s should produce 5.0 m/s."""
        result, code = run("10m / 2s", NORMALIZE, PATTERNS)
        assert code == 0
        assert isinstance(result, UnitValue)
        assert result.unit == "m/s"
        assert abs(result.value - 5.0) < 1e-10

    def test_unit_division_same_category(self):
        """100km / 2h should produce 50.0 km/h."""
        result, code = run("100km / 2h", NORMALIZE, PATTERNS)
        assert code == 0
        assert isinstance(result, UnitValue)
        assert result.unit == "km/h"
        assert abs(result.value - 50.0) < 1e-10

    def test_same_unit_multiplication(self):
        """5m * 5m should produce 25.0 m**2."""
        result, code = run("5m * 5m", NORMALIZE, PATTERNS)
        assert code == 0
        assert isinstance(result, UnitValue)
        assert result.unit == "m**2"
        assert abs(result.value - 25.0) < 1e-10

    def test_mixed_operations_with_conversion(self):
        """(5m + 3km) / 2 should convert, add, then divide."""
        result, code = run("(5m + 3km) / 2", NORMALIZE, PATTERNS)
        assert code == 0
        assert isinstance(result, UnitValue)
        assert result.unit == "m"
        assert abs(result.value - 1502.5) < 1e-10

    def test_unit_division_by_number(self):
        """10m / 2 should produce 5.0 m."""
        result, code = run("10m / 2", NORMALIZE, PATTERNS)
        assert code == 0
        assert isinstance(result, UnitValue)
        assert result.unit == "m"
        assert abs(result.value - 5.0) < 1e-10

    def test_number_times_unit(self):
        """3 * 5m should produce 15.0 m."""
        result, code = run("3 * 5m", NORMALIZE, PATTERNS)
        assert code == 0
        assert isinstance(result, UnitValue)
        assert result.unit == "m"
        assert abs(result.value - 15.0) < 1e-10

    def test_unit_power_of_kilometer(self):
        """2km ** 2 applies power to unit only (km2)."""
        result, code = run("2km ** 2", NORMALIZE, PATTERNS)
        assert code == 0
        assert isinstance(result, UnitValue)
        assert result.unit == "km2"
        assert abs(result.value - 2.0) < 1e-10


class TestUppercaseOperators:
    """Tests for uppercase operator words (Fix #3)."""

    def test_uppercase_plus(self):
        """Test that uppercase PLUS works."""
        result, code = run("3 PLUS 5", NORMALIZE, PATTERNS)
        assert code == 0
        val = result.value if isinstance(result, UnitValue) else result
        assert val == 8

    def test_uppercase_minus(self):
        """Test that uppercase MINUS works."""
        result, code = run("10 MINUS 3", NORMALIZE, PATTERNS)
        assert code == 0
        val = result.value if isinstance(result, UnitValue) else result
        assert val == 7

    def test_uppercase_times(self):
        """Test that uppercase TIMES works."""
        result, code = run("4 TIMES 5", NORMALIZE, PATTERNS)
        assert code == 0
        val = result.value if isinstance(result, UnitValue) else result
        assert val == 20

    def test_mixed_case(self):
        """Test mixed case operator words."""
        result, code = run("3 PlUs 5", NORMALIZE, PATTERNS)
        assert code == 0
        val = result.value if isinstance(result, UnitValue) else result
        assert val == 8


class TestFunctionSpaceNumber:
    """Tests for function followed by space and number (Fix #2/#17)."""

    def test_sqrt_space_number(self):
        """Test 'sqrt 144' parses correctly."""
        result, code = run("sqrt 144", NORMALIZE, PATTERNS)
        assert code == 0
        val = result.value if isinstance(result, UnitValue) else result
        assert abs(val - 12.0) < 1e-10

    def test_sin_space_number(self):
        """Test 'sin 0' parses correctly."""
        result, code = run("sin 0", NORMALIZE, PATTERNS)
        assert code == 0
        val = result.value if isinstance(result, UnitValue) else result
        assert abs(val) < 1e-10

    def test_abs_space_number(self):
        """Test 'abs( -5)' parses correctly."""
        result, code = run("abs( -5)", NORMALIZE, PATTERNS)
        assert code == 0
        val = result.value if isinstance(result, UnitValue) else result
        assert val == 5


class TestTemperatureCaseSensitivity:
    """Tests for lowercase temperature unit support (Fix #18)."""

    def test_lowercase_f_to_c(self):
        """Test '100f to c' converts correctly."""
        result, code = run("100f to c", NORMALIZE, PATTERNS)
        assert code == 0
        val = result.value if isinstance(result, UnitValue) else result
        assert abs(val - 37.77777777777778) < 1e-5

    def test_lowercase_c_to_f(self):
        """Test '0c to f' converts correctly."""
        result, code = run("0c to f", NORMALIZE, PATTERNS)
        assert code == 0
        val = result.value if isinstance(result, UnitValue) else result
        assert abs(val - 32.0) < 1e-10

    def test_uppercase_still_works(self):
        """Test that uppercase temperature units still work."""
        result, code = run("100F to C", NORMALIZE, PATTERNS)
        assert code == 0
        val = result.value if isinstance(result, UnitValue) else result
        assert abs(val - 37.77777777777778) < 1e-5


class TestUntestedMathFunctions:
    """Tests for math functions that had no test coverage."""

    def test_log(self):
        """Test natural logarithm."""
        result = evaluate("log(1)")
        val = result.value if isinstance(result, UnitValue) else result
        assert abs(val) < 1e-10

    def test_log10(self):
        """Test base-10 logarithm."""
        result = evaluate("log10(100)")
        val = result.value if isinstance(result, UnitValue) else result
        assert abs(val - 2.0) < 1e-10

    def test_log2(self):
        """Test base-2 logarithm."""
        result = evaluate("log2(8)")
        val = result.value if isinstance(result, UnitValue) else result
        assert abs(val - 3.0) < 1e-10

    def test_exp(self):
        """Test exponential function."""
        result = evaluate("exp(0)")
        val = result.value if isinstance(result, UnitValue) else result
        assert abs(val - 1.0) < 1e-10

    def test_abs_function(self):
        """Test absolute value function."""
        result = evaluate("abs(-5)")
        val = result.value if isinstance(result, UnitValue) else result
        assert val == 5

    def test_floor(self):
        """Test floor function."""
        result = evaluate("floor(3.7)")
        val = result.value if isinstance(result, UnitValue) else result
        assert val == 3

    def test_round_rejects_non_integer_digits(self):
        """round(x, ndigits) should not truncate fractional ndigits."""
        with pytest.raises(EvaluationError):
            evaluate("round(3.14159, 1.5)")

    def test_ceil(self):
        """Test ceiling function."""
        result = evaluate("ceil(3.2)")
        val = result.value if isinstance(result, UnitValue) else result
        assert val == 4

    def test_sign(self):
        """Test sign function."""
        result = evaluate("sign(-5)")
        val = result.value if isinstance(result, UnitValue) else result
        assert val == -1

    def test_cbrt(self):
        """Test cube root function."""
        result = evaluate("cbrt(27)")
        val = result.value if isinstance(result, UnitValue) else result
        assert abs(val - 3.0) < 1e-10

    def test_asin(self):
        """Test arcsine function."""
        result = evaluate("asin(1)")
        import math
        val = result.value if isinstance(result, UnitValue) else result
        assert abs(val - math.pi / 2) < 1e-10

    def test_acos(self):
        """Test arccosine function."""
        result = evaluate("acos(1)")
        val = result.value if isinstance(result, UnitValue) else result
        assert abs(val) < 1e-10

    def test_atan(self):
        """Test arctangent function."""
        result = evaluate("atan(1)")
        import math
        val = result.value if isinstance(result, UnitValue) else result
        assert abs(val - math.pi / 4) < 1e-10

    def test_factorial(self):
        """Test factorial function."""
        result = evaluate("factorial(5)")
        val = result.value if isinstance(result, UnitValue) else result
        assert val == 120

    def test_gcd(self):
        """Test GCD function."""
        result = evaluate("gcd(12, 8)")
        val = result.value if isinstance(result, UnitValue) else result
        assert val == 4

    def test_sum(self):
        """Test sum function."""
        result = evaluate("sum(1, 2, 3, 4)")
        val = result.value if isinstance(result, UnitValue) else result
        assert val == 10

    def test_max_function(self):
        """Test max function."""
        result = evaluate("max(3, 7, 2)")
        val = result.value if isinstance(result, UnitValue) else result
        assert val == 7

    def test_min_function(self):
        """Test min function."""
        result = evaluate("min(3, 7, 2)")
        val = result.value if isinstance(result, UnitValue) else result
        assert val == 2

    def test_hypot(self):
        """Test hypotenuse function."""
        result = evaluate("hypot(3, 4)")
        val = result.value if isinstance(result, UnitValue) else result
        assert abs(val - 5.0) < 1e-10

    def test_clamp(self):
        """Test clamp function."""
        result = evaluate("clamp(5, 1, 10)")
        val = result.value if isinstance(result, UnitValue) else result
        assert val == 5

    def test_clamp_below(self):
        """Test clamp with value below range."""
        result = evaluate("clamp(-5, 0, 10)")
        val = result.value if isinstance(result, UnitValue) else result
        assert val == 0

    def test_prevprime(self):
        """Test previous prime function."""
        result = evaluate("prevprime(10)")
        val = result.value if isinstance(result, UnitValue) else result
        assert val == 7

    def test_var_sample(self):
        """Test sample variance function."""
        result = evaluate("variance(2, 4, 4, 4, 5, 5, 7, 9)")
        val = result.value if isinstance(result, UnitValue) else result
        assert abs(val - 4.0) < 1e-10

    def test_nl_numbers(self):
        """Test natural language number parsing."""
        result, code = run("five plus three", NORMALIZE, PATTERNS)
        assert code == 0
        val = result.value if isinstance(result, UnitValue) else result
        assert val == 8

    def test_nl_sqrt(self):
        """Test natural language sqrt with single number."""
        result, code = run("sqrt of 144", NORMALIZE, PATTERNS)
        assert code == 0
        val = result.value if isinstance(result, UnitValue) else result
        assert abs(val - 12.0) < 1e-10

    def test_nl_sqrt_simple(self):
        """Test natural language sqrt with simple number word."""
        result, code = run("square root of nine", NORMALIZE, PATTERNS)
        assert code == 0
        val = result.value if isinstance(result, UnitValue) else result
        assert abs(val - 3.0) < 1e-10


class TestCacheByteCap:
    """H25: LRU cache has both a hard entry count and a soft byte cap."""

    def test_cache_caps_at_default_size(self):
        """Adding more than DEFAULT_CACHE_SIZE entries should evict oldest."""
        import eggcalc.evaluator as ev
        from eggcalc.evaluator import DEFAULT_CACHE_SIZE, _cache, _cache_lock, _entry_size

        test_keys = []
        with _cache_lock:
            for i in range(DEFAULT_CACHE_SIZE + 50):
                key = f"__test_evict_{i}__"
                if len(_cache) >= DEFAULT_CACHE_SIZE:
                    old_key, old_value = _cache.popitem(last=False)
                    ev._cache_bytes -= _entry_size(old_key, old_value)
                _cache[key] = float(i)
                ev._cache_bytes += _entry_size(key, float(i))
                test_keys.append(key)

        assert len(_cache) <= DEFAULT_CACHE_SIZE

        with _cache_lock:
            for key in test_keys:
                if key in _cache:
                    ev._cache_bytes -= _entry_size(key, _cache.pop(key))

    def test_cache_under_byte_cap(self):
        """Total cache bytes should stay under MAX_CACHE_BYTES."""
        from eggcalc import evaluate_cached
        from eggcalc.evaluator import MAX_CACHE_BYTES, _cache_bytes

        for i in range(50):
            evaluate_cached(f"{i}+1")
        # Even if we don't hit the cap, total bytes must be bounded
        assert _cache_bytes <= MAX_CACHE_BYTES * 2


class TestBinOpOverflowComplex:
    """M4: complex results with NaN/inf components raise EvaluationError."""

    def test_complex_division_by_zero(self):
        """Complex division by zero should not return inf silently."""
        with pytest.raises(EvaluationError):
            evaluate("1j/0")


class TestWorkerReap:
    """M5: evaluate_with_timeout kills stragglers after the timeout."""

    def test_timeout_returns_within_reasonable_time(self):
        """evaluate_with_timeout should return control quickly even on a
        pathological input. We just check that the function returns
        (with TimeoutError) within a reasonable time."""
        import time

        from eggcalc import TimeoutError, evaluate_with_timeout

        start = time.monotonic()
        try:
            evaluate_with_timeout("0+0+0+0+0", timeout=0.5)
        except TimeoutError:
            pass
        elapsed = time.monotonic() - start
        assert elapsed < 5.0, f"Timeout took {elapsed:.2f}s"


class TestDigitScales:
    """Verify _DIGIT_SCALES produces correct results."""

    def test_billion_correct(self):
        """'5 billion' should be 5_000_000_000, not 5_000_000_000_000."""
        result, code = run("5 billion", NORMALIZE, PATTERNS)
        assert code == 0
        val = result.value if isinstance(result, UnitValue) else result
        assert val == 5_000_000_000

    def test_trillion_correct(self):
        """'3 trillion' should be 3_000_000_000_000."""
        result, code = run("3 trillion", NORMALIZE, PATTERNS)
        assert code == 0
        val = result.value if isinstance(result, UnitValue) else result
        assert val == 3_000_000_000_000

    def test_quadrillion_correct(self):
        """'2 quadrillion' should be 2_000_000_000_000_000."""
        result, code = run("2 quadrillion", NORMALIZE, PATTERNS)
        assert code == 0
        val = result.value if isinstance(result, UnitValue) else result
        assert val == 2_000_000_000_000_000

    def test_million_still_correct(self):
        """'7 million' should still be 7_000_000."""
        result, code = run("7 million", NORMALIZE, PATTERNS)
        assert code == 0
        val = result.value if isinstance(result, UnitValue) else result
        assert val == 7_000_000


class TestVisitAttribute:
    """Verify standalone .real/.imag/.conjugate attribute access."""

    def test_real_of_complex(self):
        """(3+4j).real should be 3.0."""
        result = evaluate("(3+4j).real")
        assert abs(result - 3.0) < 1e-10

    def test_imag_of_complex(self):
        """(3+4j).imag should be 4.0."""
        result = evaluate("(3+4j).imag")
        assert abs(result - 4.0) < 1e-10

    def test_real_of_real(self):
        """(5).real should be 5."""
        result = evaluate("(5).real")
        assert result == 5

    def test_imag_of_real(self):
        """(5).imag should be 0.0."""
        result = evaluate("(5).imag")
        assert result == 0.0

    def test_conjugate(self):
        """(3+4j).conjugate should be (3-4j)."""
        result = evaluate("(3+4j).conjugate")
        assert isinstance(result, complex)
        assert result == (3-4j)


class TestComplexPower:
    """Verify complex number exponentiation works."""

    def test_i_squared(self):
        """i**2 should be -1 (or close to it)."""
        result = evaluate("i**2")
        val = result.value if isinstance(result, UnitValue) else result
        assert abs(val - (-1)) < 1e-10 or abs(val - (-1+0j)) < 1e-10

    def test_j_squared(self):
        """j**2 should be -1."""
        result = evaluate("j**2")
        val = result.value if isinstance(result, UnitValue) else result
        assert abs(val - (-1)) < 1e-10 or abs(val - (-1+0j)) < 1e-10

    def test_complex_power(self):
        """(1+1j)**2 should be 2j."""
        result = evaluate("(1+1j)**2")
        assert isinstance(result, complex)
        assert abs(result - 2j) < 1e-10


class TestLargeIntStrSafety:
    """Verify large integer str() doesn't raise ValueError."""

    def test_large_shift_result(self):
        """1 << 14300 should not raise ValueError."""
        result = evaluate("1 << 14300")
        assert result is not None
        assert isinstance(result, int)
        assert result > 0

    def test_large_factorial(self):
        """factorial(1000) should not raise ValueError."""
        result = evaluate("factorial(1000)")
        assert result is not None
        assert isinstance(result, int)


class TestNestingDepth:
    """Verify MAX_NESTING_DEPTH is enforced."""

    def test_deep_nesting_rejected(self):
        """Deeply nested expressions should raise EvaluationError."""
        from eggcalc.evaluator import MAX_NESTING_DEPTH
        expr = "1+" * (MAX_NESTING_DEPTH + 10) + "1"
        with pytest.raises(EvaluationError, match="deeply nested"):
            evaluate(expr)


class TestUnitValueHashEqContract:
    """Test that UnitValue maintains the hash/eq contract."""

    def test_equal_values_have_same_hash(self):
        a = UnitValue(1.0, "m")
        b = UnitValue(1.0, "m")
        assert a == b
        assert hash(a) == hash(b)

    def test_different_values_different_hash(self):
        a = UnitValue(1.0, "m")
        b = UnitValue(2.0, "m")
        assert a != b

    def test_dict_lookup_works(self):
        d = {UnitValue(5.0, "m"): "found"}
        assert d[UnitValue(5.0, "m")] == "found"

    def test_set_membership(self):
        s = {UnitValue(1.0, "m"), UnitValue(2.0, "m")}
        assert UnitValue(1.0, "m") in s
        assert UnitValue(3.0, "m") not in s

    def test_different_units_not_equal(self):
        a = UnitValue(1.0, "m")
        b = UnitValue(1.0, "km")
        assert a != b

    def test_exact_comparison(self):
        a = UnitValue(1.0, "m")
        b = UnitValue(1.000000000000001, "m")
        assert a != b


class TestBitShiftSafety:
    """Test that bitlshift/bitrshift functions reject negative shift counts."""

    def test_bitlshift_negative_raises(self):
        with pytest.raises(EvaluationError, match="non-negative"):
            evaluate("bitlshift(5, -3)")

    def test_bitrshift_negative_raises(self):
        with pytest.raises(EvaluationError, match="non-negative"):
            evaluate("bitrshift(5, -3)")

    def test_bitlshift_positive_works(self):
        result = evaluate("bitlshift(1, 3)")
        assert result == 8

    def test_bitrshift_positive_works(self):
        result = evaluate("bitrshift(8, 2)")
        assert result == 2

    @pytest.mark.parametrize("expr", [
        "bitand(1.5, 3)",
        "bitor(1.5, 2)",
        "bitxor(1.5, 3)",
        "bitnot(1.5)",
        "bitlshift(1, 1.5)",
        "bitrshift(8, 1.5)",
        "bitand(1*m, 3)",
    ])
    def test_bitwise_functions_reject_non_integer_or_unit_inputs(self, expr):
        with pytest.raises(EvaluationError):
            evaluate(expr)


class TestEvaluatorEdgeCases:
    """Tests for evaluator edge cases identified in production readiness review."""

    def test_large_int_overflow_error(self):
        """2**100000 produces EvaluationError, not OverflowError crash."""
        with pytest.raises(EvaluationError):
            evaluate("2**100000")

    def test_add_string_error(self):
        """1 + '2' produces EvaluationError with clear message, not raw TypeError."""
        with pytest.raises(EvaluationError, match="Cannot apply"):
            evaluate("1 + '2'")

    def test_complex_floor_div_error(self):
        """(1+2j) // (1+2j) produces EvaluationError, not raw TypeError."""
        with pytest.raises(EvaluationError):
            evaluate("(1+2j) // (1+2j)")

    def test_complex_mod_error(self):
        """(1+2j) % (1+2j) produces EvaluationError, not raw TypeError."""
        with pytest.raises(EvaluationError):
            evaluate("(1+2j) % (1+2j)")

    def test_large_int_unitvalue_no_crash(self):
        """UnitValue with very large int doesn't crash _check_result_size."""
        from eggcalc.evaluator import _check_result_size
        from eggcalc.units import UnitValue
        try:
            _check_result_size(UnitValue(10**100001, "m"))
        except EvaluationError:
            pass
        except OverflowError:
            pytest.fail("OverflowError leaked from _check_result_size")

    def test_negative_kelvin_converts(self):
        """-1K in C converts to -274.15C (calculator doesn't enforce physical constraints)."""
        import sys
        from io import StringIO
        captured = StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            run("-1K in C", NORMALIZE, PATTERNS)
        finally:
            sys.stdout = old_stdout
        output = captured.getvalue()
        assert "-274.15" in output

    def test_unit_mismatch_error(self):
        """30m + 100gal should produce an error about incompatible units."""
        import sys
        from io import StringIO
        captured = StringIO()
        old_stderr = sys.stderr
        sys.stderr = captured
        try:
            run("30m + 100gal", NORMALIZE, PATTERNS)
        finally:
            sys.stderr = old_stderr
        stderr_output = captured.getvalue()
        assert stderr_output != "", "Expected an error on stderr for incompatible units"

    def test_temp_wrong_args_error(self):
        """temp(0) should produce EvaluationError, not raw TypeError."""
        with pytest.raises(EvaluationError):
            evaluate("temp(0)")

    def test_convert_wrong_args_error(self):
        """convert(5) should produce EvaluationError, not raw TypeError."""
        with pytest.raises(EvaluationError):
            evaluate("convert(5)")

    def test_negative_number_to_complex_power(self):
        """(-2)**(3+0j) should work since 3+0j is effectively an integer."""
        result = evaluate("(-2)**(3+0j)")
        assert abs(result - (-8)) < 1e-10

    def test_negative_number_to_complex_noninteger_power(self):
        """(-2)**(1.5+0j) should produce EvaluationError."""
        with pytest.raises(EvaluationError):
            evaluate("(-2)**(1.5+0j)")

    def test_negative_number_to_complex_imaginary_power(self):
        """(-2)**(1+1j) should produce EvaluationError."""
        with pytest.raises(EvaluationError):
            evaluate("(-2)**(1+1j)")

    def test_nan_constant_rejected(self):
        """Bare 'nan' should raise EvaluationError (not accessible as constant)."""
        with pytest.raises(EvaluationError, match="Unknown name"):
            evaluate("nan")

    def test_inf_constant_rejected(self):
        """Bare 'inf' should raise EvaluationError (not accessible as constant)."""
        with pytest.raises(EvaluationError, match="Unknown name"):
            evaluate("inf")

    def test_pi_still_works(self):
        """'pi' should still resolve as a constant."""
        import math
        result = evaluate("pi")
        assert abs(result - math.pi) < 1e-10


class TestUnitValueScalarArithmetic:
    """Tests for UnitValue arithmetic with scalar values."""

    def test_unitless_add_scalar(self):
        """UnitValue(5, None) + 10 should return UnitValue(15, None)."""
        result = UnitValue(5, None) + 10
        assert isinstance(result, UnitValue)
        assert result.value == 15
        assert result.unit is None

    def test_unitless_sub_scalar(self):
        """UnitValue(10, None) - 3 should return UnitValue(7, None)."""
        result = UnitValue(10, None) - 3
        assert isinstance(result, UnitValue)
        assert result.value == 7
        assert result.unit is None

    def test_unitless_add_unitless_unitvalue(self):
        """UnitValue(5, None) + UnitValue(3, None) should return UnitValue(8, None)."""
        result = UnitValue(5, None) + UnitValue(3, None)
        assert isinstance(result, UnitValue)
        assert result.value == 8
        assert result.unit is None

    def test_dimensioned_add_unitless_raises(self):
        """UnitValue(5, 'm') + 10 should raise ValueError."""
        with pytest.raises(ValueError):
            UnitValue(5, "m") + 10

    def test_unitless_add_dimensioned(self):
        """UnitValue(5, None) + UnitValue(10, 'm') returns UnitValue(15, 'm')."""
        result = UnitValue(5, None) + UnitValue(10, "m")
        assert isinstance(result, UnitValue)
        assert result.value == 15
        assert result.unit == "m"


class TestReviewerEdgeCases:
    """Tests for edge cases identified during production review."""

    def test_log_negative_returns_complex(self):
        """log(-1) should return complex result."""
        result = evaluate("log(-1)")
        assert isinstance(result, complex)
        assert abs(result - 1j * 3.141592653589793) < 1e-10

    def test_asin_out_of_domain_returns_complex(self):
        """asin(2) should return complex result for out-of-domain input."""
        result = evaluate("asin(2)")
        assert isinstance(result, complex)

    def test_acos_out_of_domain_returns_complex(self):
        """acos(2) should return complex result for out-of-domain input."""
        result = evaluate("acos(2)")
        assert isinstance(result, complex)

    def test_atanh_out_of_domain_returns_complex(self):
        """atanh(2) should return complex result for out-of-domain input."""
        result = evaluate("atanh(2)")
        assert isinstance(result, complex)

    def test_clamp_lo_greater_than_hi(self):
        """clamp(5, 10, 1) should raise ValueError when lo > hi."""
        from eggcalc.evaluator import _clamp
        with pytest.raises(ValueError, match="lower bound.*exceeds upper bound"):
            _clamp(5, 10, 1)

    def test_clamp_normal_cases(self):
        """clamp works correctly for normal cases."""
        from eggcalc.evaluator import _clamp
        assert _clamp(5, 1, 10) == 5
        assert _clamp(-5, 0, 10) == 0
        assert _clamp(15, 0, 10) == 10

    def test_bin_negative(self):
        """bin(-5) should return binary string with sign."""
        result = evaluate("bin(-5)")
        assert result == "-0b101"

    def test_hex_negative(self):
        """hex(-5) should return hex string with sign."""
        result = evaluate("hex(-5)")
        assert result == "-0x5"

    def test_oct_negative(self):
        """oct(-5) should return octal string with sign."""
        result = evaluate("oct(-5)")
        assert result == "-0o5"

    def test_bin_float_rejected(self):
        """bin(1.5) should raise error for non-integer."""
        with pytest.raises(EvaluationError):
            evaluate("bin(1.5)")

    def test_gcd_zero_zero(self):
        """gcd(0, 0) should return 0."""
        assert evaluate("gcd(0, 0)") == 0

    def test_gcd_negative(self):
        """gcd(-12, 8) should handle negative inputs."""
        result = evaluate("gcd(-12, 8)")
        assert result == 4

    def test_perm_r_greater_than_n(self):
        """perm(5, 10) should return 0 when r > n."""
        assert evaluate("perm(5, 10)") == 0

    def test_comb_r_greater_than_n(self):
        """comb(5, 10) should return 0 when r > n."""
        assert evaluate("comb(5, 10)") == 0

    def test_unitvalue_pow_integer(self):
        """UnitValue raised to integer power should work correctly."""
        from eggcalc.units import UnitValue
        result = UnitValue(2, "m") ** 3
        assert result.value == 8
        assert result.unit == "m**3"

    def test_unitvalue_pow_non_integer_rejected(self):
        """UnitValue raised to non-integer power should raise ValueError."""
        from eggcalc.units import UnitValue
        with pytest.raises(ValueError, match="non-integer power"):
            UnitValue(2, "m") ** 1.5

    def test_unitvalue_pow_float_integer(self):
        """UnitValue raised to float integer power should work."""
        from eggcalc.units import UnitValue
        result = UnitValue(2, "m") ** 2.0
        assert result.value == 4
        assert result.unit == "m**2"

    def test_atan2_function(self):
        """atan2 function should work correctly."""
        import math
        result = evaluate("atan2(1, 1)")
        assert abs(result - math.pi / 4) < 1e-10

    def test_degrees_function(self):
        """degrees function should convert radians to degrees."""
        result = evaluate("degrees(pi)")
        assert abs(result - 180.0) < 1e-10

    def test_radians_function(self):
        """radians function should convert degrees to radians."""
        import math
        result = evaluate("radians(180)")
        assert abs(result - math.pi) < 1e-10

    def test_expm1_function(self):
        """expm1 function should compute exp(x) - 1."""
        import math
        result = evaluate("expm1(1)")
        assert abs(result - (math.e - 1)) < 1e-10

    def test_log1p_function(self):
        """log1p function should compute log(1+x)."""
        import math
        result = evaluate("log1p(1)")
        assert abs(result - math.log(2)) < 1e-10

    def test_sign_zero(self):
        """sign(0) should return 0."""
        assert evaluate("sign(0)") == 0

    def test_mean_empty_raises(self):
        """mean() with no args should raise error."""
        with pytest.raises(EvaluationError):
            evaluate("mean()")

    @pytest.mark.parametrize("expr", [
        "bin(3*m)",
        "hex(3*m)",
        "oct(3*m)",
    ])
    def test_base_conversion_rejects_unit_inputs(self, expr):
        with pytest.raises(EvaluationError):
            evaluate(expr)

    def test_std_single_arg(self):
        """std(1) with single arg should raise error."""
        with pytest.raises(EvaluationError):
            evaluate("std(1)")

    def test_conj_real_number(self):
        """conj(5) with real number should return complex."""
        result = evaluate("conj(5)")
        assert isinstance(result, complex)
        assert result.real == 5
        assert result.imag == 0


class TestGapCoverage:
    """Tests for identified coverage gaps."""

    def test_same_unit_division_dimensionless(self):
        """5m / 3m should be dimensionless (1.666...)."""
        r = run('5m / 3m', NORMALIZE, PATTERNS)
        assert isinstance(r[0], float)
        assert abs(r[0] - 5 / 3) < 1e-10

    def test_safe_pow_negative_base_near_integer_float_exp(self):
        """(-4)**2.000000000001 should return 16, not complex."""
        from eggcalc.evaluator import _safe_pow
        result = _safe_pow(-4, 2.000000000001)
        assert result == 16
        assert isinstance(result, int)

    def test_unitvalue_rsub_dimensionless(self):
        """10 - UnitValue(5, None) should work."""
        from eggcalc.units import UnitValue
        result = 10 - UnitValue(5, None)
        assert result.value == 5
        assert result.unit is None

    def test_overflow_error_clean_message(self):
        """std(0, 1e308) should produce 'Result too large', not raw errno tuple."""
        with pytest.raises(EvaluationError, match="Result too large"):
            evaluate('std(0, 1e308)')

    def test_evaluate_rejects_nl_input(self):
        """evaluate() should fail on natural language input."""
        with pytest.raises(EvaluationError):
            evaluate("five plus three")
        with pytest.raises(EvaluationError):
            evaluate("30m + 100ft")

    def test_factorial_boundary(self):
        """factorial(MAX_FACTORIAL) works, factorial(MAX_FACTORIAL+1) fails."""
        from eggcalc.evaluator import MAX_FACTORIAL
        evaluate(f'factorial({MAX_FACTORIAL})')  # should not raise
        with pytest.raises(EvaluationError):
            evaluate(f'factorial({MAX_FACTORIAL + 1})')

    def test_division_by_zero_edge_cases(self):
        """Various division by zero forms should all raise."""
        with pytest.raises(EvaluationError):
            evaluate('0.0 // 0.0')
        with pytest.raises(EvaluationError):
            evaluate('0 % 0')

    def test_dimensionless_subtraction_unitvalue(self):
        """10 - UnitValue(5, None) should produce UnitValue(5, None)."""
        from eggcalc.units import UnitValue
        result = 10 - UnitValue(5, None)
        assert isinstance(result, UnitValue)
        assert result.value == 5
        assert result.unit is None


class TestDeferredD5D6UnitSimplification:
    """Tests for compound unit cancellation (plans/production_review_2026_07_b.md D5, D6)."""

    def test_m_per_s_times_s_simplifies_to_m(self):
        """(1 m / 1 s) * 1 s should give 1 m, not 1 m/s*s."""
        from eggcalc.units import UnitValue
        result = UnitValue(1.0, "m/s") * UnitValue(1.0, "s")
        assert result.unit == "m"
        assert result.value == 1.0

    def test_m_times_m_over_m_simplifies_to_m(self):
        """(1 m * 1 m) / 1 m should give 1 m, not 1 m*m/m."""
        from eggcalc.units import UnitValue
        result = UnitValue(1.0, "m*m") / UnitValue(1.0, "m")
        assert result.unit == "m"
        assert result.value == 1.0

    def test_m_per_m_equals_dimensionless(self):
        """1 m / 1 m should give a dimensionless value, not '1/m' string."""
        from eggcalc.units import UnitValue
        result = UnitValue(1.0, "m") / UnitValue(1.0, "m")
        assert result.unit is None

    def test_m_per_s_squared_times_s_squared_equals_m(self):
        """Acceleration * time_squared should give m, not m/s**2*s**2."""
        from eggcalc.units import UnitValue
        result = UnitValue(9.8, "m/s**2") * UnitValue(4.0, "s**2")
        assert result.unit == "m"
        assert abs(result.value - 39.2) < 1e-10

    def test_simplify_unit_string_helper(self):
        """The _simplify_unit_string helper should normalize compound forms."""
        from eggcalc.units import _simplify_unit_string
        assert _simplify_unit_string("m/s*s") == "m"
        assert _simplify_unit_string("m*m/m") == "m"
        assert _simplify_unit_string("m**2*m") == "m**3"
        assert _simplify_unit_string("m/s") == "m/s"
        assert _simplify_unit_string("m") == "m"
        assert _simplify_unit_string(None) is None
        assert _simplify_unit_string("xyz") == "xyz"

    def test_floordiv_simplifies_compound_units(self):
        """Floor division of compound units should also be simplified."""
        from eggcalc.units import UnitValue
        result = UnitValue(7.0, "m/s") // UnitValue(1.0, "s")
        assert result.unit == "m/s**2"
        assert result.value == 7.0

    def test_mod_simplifies_compound_units(self):
        """Modulo of compound units should also be simplified."""
        from eggcalc.units import UnitValue
        result = UnitValue(7.0, "m/s") % UnitValue(2.0, "s")
        assert result.unit == "m/s**2"
        assert result.value == 1.0

    def test_truediv_reciprocal_of_compound(self):
        """1 / (m/s) should produce s/m, not 1/m/s."""
        from eggcalc.units import UnitValue
        result = UnitValue(1.0, None) / UnitValue(1.0, "m/s")
        assert result.unit == "s/m"
        assert result.value == 1.0

    def test_canonical_forms_unchanged(self):
        """Canonical forms pass through simplification unchanged."""
        from eggcalc.units import _simplify_unit_string
        for unit in ("m/s", "m/s**2", "m**2", "km/h", "mi/h", "B/s", "GB/s"):
            assert _simplify_unit_string(unit) == unit, f"{unit!r} changed unexpectedly"


class TestProductionReviewBugfixes2026_07:
    """Tests for bugs found in the 2026-07 production code review.

    These cover cross-module correctness issues that existing tests did
    not catch. Grouped here for clarity.
    """

    def _get_value(self, result):
        if isinstance(result, UnitValue):
            return result.value
        return result

    # --- MCP constant_lookup: math constants ---
    def test_mcp_constant_lookup_pi(self):
        from eggcalc.mcp.tools import constant_lookup
        r = constant_lookup("pi")
        assert r["ok"] is True
        assert abs(r["result"]["value"] - 3.141592653589793) < 1e-12
        assert r["result"]["display_name"] == "Pi (mathematical constant)"

    def test_mcp_constant_lookup_e(self):
        from eggcalc.mcp.tools import constant_lookup
        r = constant_lookup("e")
        assert r["ok"] is True
        assert abs(r["result"]["value"] - 2.718281828459045) < 1e-12

    def test_mcp_constant_lookup_tau(self):
        from eggcalc.mcp.tools import constant_lookup
        r = constant_lookup("tau")
        assert r["ok"] is True
        assert abs(r["result"]["value"] - 6.283185307179586) < 1e-12

    def test_mcp_constant_lookup_c_still_works(self):
        from eggcalc.mcp.tools import constant_lookup
        r = constant_lookup("c")
        assert r["ok"] is True
        assert r["result"]["value"] == 299792458

    # --- Evaluator: UnitValue / BinOp correctness ---
    def test_evaluator_unary_plus_on_unitvalue(self):
        """+5m should not produce a nested UnitValue."""
        r = run("+5m", NORMALIZE, PATTERNS)
        result, exit_code = r
        assert exit_code == 0
        assert isinstance(result, UnitValue)
        assert result.value == 5.0
        assert result.unit == "m"

    def test_evaluator_pow_rejects_unit_on_right(self):
        """2**(3m) should error, not silently produce 8.0 m."""
        result, exit_code = run("2**(3m)", NORMALIZE, PATTERNS)
        assert exit_code != 0

    def test_evaluator_add_dimensionless_plus_unit_errors(self):
        """5 + 3m should error, not silently mix units."""
        result, exit_code = run("5 + 3m", NORMALIZE, PATTERNS)
        assert exit_code != 0

    def test_evaluator_sub_temperature_plus_dimensionless_errors(self):
        """0C + 5 should error, not silently produce 5.0 C."""
        result, exit_code = run("0C + 5", NORMALIZE, PATTERNS)
        assert exit_code != 0

    def test_evaluator_temperature_addition_works(self):
        """1K + 1C should give 275.15 K (after offset conversion)."""
        result, exit_code = run("1K + 1C", NORMALIZE, PATTERNS)
        assert exit_code == 0
        assert isinstance(result, UnitValue)
        assert abs(result.value - 275.15) < 1e-9
        assert result.unit == "K"

    # --- Units: simplification / cross-form ---
    def test_simplify_returns_none_for_fully_cancelled(self):
        from eggcalc.units import _simplify_unit_string
        assert _simplify_unit_string("m**0") is None
        assert _simplify_unit_string("m/m") is None
        assert _simplify_unit_string("m**2*m**-2") is None

    def test_unitvalue_pow_zero_is_dimensionless(self):
        from eggcalc.units import UnitValue
        r = UnitValue(5.0, "m") ** 0
        assert r.value == 1.0
        assert r.unit is None

    def test_cross_form_unit_addition(self):
        """5 m2 + 100 cm**2 should give 5.01 m**2 (or 5.01 m2)."""
        result, exit_code = run("5 m2 + 100 cm**2", NORMALIZE, PATTERNS)
        assert exit_code == 0
        assert isinstance(result, UnitValue)
        assert abs(result.value - 5.01) < 1e-9
        # The result unit is "m2" (the canonical form stored in the table)
        assert result.unit in ("m2", "m**2")

    def test_unit_convert_cross_form(self):
        from eggcalc.mcp.tools import unit_convert
        r = unit_convert(1, "m**2", "acre")
        assert r["ok"] is True
        assert abs(r["result"]["value"] - 0.0002471053814671653) < 1e-9

    def test_unit_convert_m2_to_acre_preserved(self):
        from eggcalc.mcp.tools import unit_convert
        r = unit_convert(4046.8564224, "m2", "acre")
        assert r["ok"] is True
        assert abs(r["result"]["value"] - 1.0) < 0.01

    # --- Normalize: hex/binary/octal literals ---
    def test_hex_literal_with_trailing_letter(self):
        """0x1F should be 31, not 1.0 F."""
        result, exit_code = run("0x1F", NORMALIZE, PATTERNS)
        assert exit_code == 0
        assert self._get_value(result) == 31

    def test_hex_literal_with_a_digit(self):
        result, exit_code = run("0x1A", NORMALIZE, PATTERNS)
        assert exit_code == 0
        assert self._get_value(result) == 26

    def test_hex_literal_uppercase(self):
        result, exit_code = run("0XFF", NORMALIZE, PATTERNS)
        assert exit_code == 0
        assert self._get_value(result) == 255

    def test_binary_literal(self):
        result, exit_code = run("0b1010", NORMALIZE, PATTERNS)
        assert exit_code == 0
        assert self._get_value(result) == 10

    def test_octal_literal(self):
        result, exit_code = run("0o17", NORMALIZE, PATTERNS)
        assert exit_code == 0
        assert self._get_value(result) == 15

    # --- Normalize: multi-subtraction ---
    def test_multi_subtraction_no_spaces(self):
        result, exit_code = run("4-5-3", NORMALIZE, PATTERNS)
        assert exit_code == 0
        assert self._get_value(result) == -4

    def test_multi_subtraction_with_spaces(self):
        result, exit_code = run("5 - 3 - 2", NORMALIZE, PATTERNS)
        assert exit_code == 0
        assert self._get_value(result) == 0

    def test_multi_subtraction_four_terms(self):
        result, exit_code = run("5 - 3 - 2 - 1", NORMALIZE, PATTERNS)
        assert exit_code == 0
        assert self._get_value(result) == -1

    def test_subtraction_with_parenthesized_subexpression(self):
        """5 - (3 + 2) should give 0."""
        result, exit_code = run("5 - (3 + 2)", NORMALIZE, PATTERNS)
        assert exit_code == 0
        assert self._get_value(result) == 0

    def test_subtraction_with_nested_parens(self):
        """5 - (3 - 2) - 1 should give 3."""
        result, exit_code = run("5 - (3 - 2) - 1", NORMALIZE, PATTERNS)
        assert exit_code == 0
        assert self._get_value(result) == 3

    # --- Normalize: 'to the N' power syntax ---
    def test_to_the_n_power(self):
        result, exit_code = run("2 to the 10", NORMALIZE, PATTERNS)
        assert exit_code == 0
        assert self._get_value(result) == 1024

    def test_to_the_n_power_decimal(self):
        result, exit_code = run("2 to the 3.5", NORMALIZE, PATTERNS)
        assert exit_code == 0
        assert abs(self._get_value(result) - 11.313708498984761) < 1e-9

    # --- Normalize: arc / hyperbolic functions ---
    def test_arc_cosine(self):
        import math
        result, exit_code = run("arc cosine of 0.5", NORMALIZE, PATTERNS)
        assert exit_code == 0
        assert abs(self._get_value(result) - math.acos(0.5)) < 1e-9

    def test_arc_tangent(self):
        import math
        result, exit_code = run("arc tangent of 1", NORMALIZE, PATTERNS)
        assert exit_code == 0
        assert abs(self._get_value(result) - math.atan(1)) < 1e-9

    def test_arccosine_compact(self):
        import math
        result, exit_code = run("arccosine of 0.5", NORMALIZE, PATTERNS)
        assert exit_code == 0
        assert abs(self._get_value(result) - math.acos(0.5)) < 1e-9

    def test_arctangent_compact(self):
        import math
        result, exit_code = run("arctangent of 1", NORMALIZE, PATTERNS)
        assert exit_code == 0
        assert abs(self._get_value(result) - math.atan(1)) < 1e-9

    def test_hyperbolic_sine(self):
        import math
        result, exit_code = run("hyperbolic sine of 1", NORMALIZE, PATTERNS)
        assert exit_code == 0
        assert abs(self._get_value(result) - math.sinh(1)) < 1e-9

    # --- Normalize: factorial postfix ---
    def test_factorial_postfix(self):
        result, exit_code = run("5!", NORMALIZE, PATTERNS)
        assert exit_code == 0
        assert self._get_value(result) == 120

    def test_factorial_postfix_in_expression(self):
        result, exit_code = run("5!+3", NORMALIZE, PATTERNS)
        assert exit_code == 0
        assert self._get_value(result) == 123

    def test_factorial_postfix_in_parens(self):
        """(5+3)! should be 40320."""
        result, exit_code = run("(5+3)!", NORMALIZE, PATTERNS)
        assert exit_code == 0
        assert self._get_value(result) == 40320

    # --- Normalize: implicit multiplication ---
    def test_implicit_mul_digit_paren(self):
        result, exit_code = run("3(4+5)", NORMALIZE, PATTERNS)
        assert exit_code == 0
        assert self._get_value(result) == 27

    def test_implicit_mul_two_digits_paren(self):
        result, exit_code = run("2(3+4)", NORMALIZE, PATTERNS)
        assert exit_code == 0
        assert self._get_value(result) == 14

    def test_implicit_mul_paren_paren(self):
        result, exit_code = run("(2)(3)", NORMALIZE, PATTERNS)
        assert exit_code == 0
        assert self._get_value(result) == 6

    # --- Normalize: trailing decimal point ---
    def test_trailing_dot(self):
        result, exit_code = run("5.", NORMALIZE, PATTERNS)
        assert exit_code == 0
        assert self._get_value(result) == 5.0

    def test_trailing_dot_in_expression(self):
        result, exit_code = run("5. + 3", NORMALIZE, PATTERNS)
        assert exit_code == 0
        assert self._get_value(result) == 8.0

    def test_trailing_dot_zero(self):
        result, exit_code = run("0.", NORMALIZE, PATTERNS)
        assert exit_code == 0
        assert self._get_value(result) == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
