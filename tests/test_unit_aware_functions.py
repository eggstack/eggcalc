"""Tests for unit-aware function contracts and timeout state parity.

Covers:
- Workstream A: Every built-in function has an explicit dimensional policy
- Workstream B: Centralized unit-policy dispatcher (visit_Call)
- Workstream C: Angle-model correction (trig with deg/rad, compound angles)
- Workstream D: Timeout evaluator state parity
- Workstream E: Custom unit category validation
"""

import math

import pytest

from eggcalc import EvaluationError, UnitValue, evaluate, evaluate_raw, evaluate_with_timeout
from eggcalc.evaluator import (
    Evaluator,
    _get_function_specs,
)

# ---------------------------------------------------------------------------
# Workstream A: Registry completeness
# ---------------------------------------------------------------------------


class TestRegistryCompleteness:
    """Every built-in function in Evaluator.FUNCTIONS must have a unit policy."""

    def test_all_builtin_functions_have_unit_policy(self):
        """Assert _FUNCTION_SPECS covers every entry in Evaluator.FUNCTIONS."""
        specs = _get_function_specs()
        funcs = Evaluator.FUNCTIONS
        missing = sorted(set(funcs) - set(specs))
        # Functions handled by visit_Call directly (before policy dispatch):
        exempt = {
            "temp",
            "convert",
            "store",
            "recall",
            "M",
            "Mplus",
            "Mminus",
            "MC",
            "MR",
            "setvar",
            "getvar",
            "delvar",
            "listvars",
            "clearvars",
        }
        truly_missing = [f for f in missing if f not in exempt]
        assert truly_missing == [], f"Functions without unit policy: {truly_missing}"


# ---------------------------------------------------------------------------
# Workstream B: Unit-policy dispatcher — negative tests (reject dimensional)
# ---------------------------------------------------------------------------


class TestDimensionlessRequired:
    """Functions that require dimensionless arguments must reject UnitValue."""

    @pytest.mark.parametrize(
        "expr",
        [
            "log(5*kg)",
            "log10(5*kg)",
            "log2(5*kg)",
            "exp(5*kg)",
            "sinh(5*kg)",
            "cosh(5*kg)",
            "tanh(5*kg)",
            "asinh(5*kg)",
            "acosh(5*kg)",
            "atanh(5*kg)",
        ],
    )
    def test_log_exp_hyp_reject_dimensional(self, expr):
        """Log/exp/hyperbolic functions must reject dimensional arguments."""
        with pytest.raises(EvaluationError, match="dimensionless"):
            evaluate_raw(expr)

    @pytest.mark.parametrize(
        "expr",
        [
            "factorial(5*m)",
            "fact(5*m)",
            "gcd(12*m, 8*m)",
            "lcm(4*m, 6*m)",
            "perm(5*m, 2)",
            "comb(5*m, 2)",
            "isprime(7*m)",
            "primefactors(12*m)",
        ],
    )
    def test_integer_functions_reject_dimensional(self, expr):
        """Integer-domain functions must reject dimensional arguments."""
        with pytest.raises(EvaluationError, match="dimensionless"):
            evaluate_raw(expr)

    @pytest.mark.parametrize(
        "expr",
        [
            "percentof(50, 100*m)",
            "aspercent(50*m, 100*s)",
        ],
    )
    def test_percentage_rejects_dimensional(self, expr):
        """Percentage functions must reject dimensional arguments."""
        with pytest.raises(EvaluationError, match="dimensionless"):
            evaluate_raw(expr)


# ---------------------------------------------------------------------------
# Workstream B: Angle-input functions (trig)
# ---------------------------------------------------------------------------


class TestAngleInput:
    """Trig functions accept dimensionless (radians) or angle UnitValues."""

    def test_sin_radians(self):
        assert abs(evaluate("sin(0)") - 0.0) < 1e-10
        assert abs(evaluate("sin(pi/2)") - 1.0) < 1e-10

    def test_sin_degrees(self):
        result = evaluate_raw("sin(90*deg)")
        assert abs(result - 1.0) < 1e-10

    def test_cos_degrees(self):
        result = evaluate_raw("cos(180*deg)")
        assert abs(result - (-1.0)) < 1e-10

    def test_tan_degrees(self):
        result = evaluate_raw("tan(45*deg)")
        assert abs(result - 1.0) < 1e-6

    def test_sin_radians_unit(self):
        result = evaluate_raw("sin(1*rad)")
        assert abs(result - math.sin(1.0)) < 1e-10

    def test_sin_rejects_length(self):
        with pytest.raises(EvaluationError, match="dimensionless or angle"):
            evaluate_raw("sin(1*m)")

    def test_cos_rejects_mass(self):
        with pytest.raises(EvaluationError, match="dimensionless or angle"):
            evaluate_raw("cos(5*kg)")

    def test_tan_rejects_time(self):
        with pytest.raises(EvaluationError, match="dimensionless or angle"):
            evaluate_raw("tan(3*s)")


# ---------------------------------------------------------------------------
# Workstream B: Angle-output functions (inverse trig)
# ---------------------------------------------------------------------------


class TestAngleOutput:
    """Inverse trig functions accept dimensionless, return dimensionless."""

    def test_asin_dimensionless(self):
        assert abs(evaluate("asin(0)") - 0.0) < 1e-10
        assert abs(evaluate("asin(1)") - math.pi / 2) < 1e-10

    def test_acos_dimensionless(self):
        assert abs(evaluate("acos(1)") - 0.0) < 1e-10

    def test_atan_dimensionless(self):
        assert abs(evaluate("atan(0)") - 0.0) < 1e-10

    def test_asin_rejects_unit(self):
        with pytest.raises(EvaluationError, match="dimensionless"):
            evaluate_raw("asin(1*m)")


# ---------------------------------------------------------------------------
# Workstream B: atan2 with compatible units
# ---------------------------------------------------------------------------


class TestAtan2:
    """atan2 requires both args dimensionless or both compatible."""

    def test_atan2_dimensionless(self):
        assert abs(evaluate("atan2(1, 1)") - math.atan2(1, 1)) < 1e-10

    def test_atan2_compatible_units(self):
        result = evaluate_raw("atan2(1*m, 100*cm)")
        assert abs(result - math.atan2(1, 1)) < 1e-10

    def test_atan2_incompatible_units(self):
        with pytest.raises(EvaluationError, match="compatible"):
            evaluate_raw("atan2(1*m, 1*s)")

    def test_atan2_mixed_scalar_unit(self):
        with pytest.raises(EvaluationError, match="compatible"):
            evaluate_raw("atan2(1*m, 1)")


# ---------------------------------------------------------------------------
# Workstream B: Compatible-unit reducers (mean, min, max, etc.)
# ---------------------------------------------------------------------------


class TestCompatibleReducers:
    """Reducers require all args dimensionless or all compatible."""

    def test_mean_dimensionless(self):
        assert evaluate("mean(1, 2, 3)") == 2.0

    def test_mean_compatible_units(self):
        result = evaluate_raw("mean(1*m, 100*cm)")
        assert isinstance(result, UnitValue)
        assert abs(result.value - 1.0) < 1e-10
        assert result.unit == "m"

    def test_mean_incompatible_units(self):
        with pytest.raises(EvaluationError, match="compatible"):
            evaluate_raw("mean(1*m, 1*s)")

    def test_mean_mixed_scalar_unit(self):
        with pytest.raises(EvaluationError, match="compatible"):
            evaluate_raw("mean(1*m, 1)")

    def test_min_compatible_units(self):
        result = evaluate_raw("min(1*m, 3*ft)")
        assert isinstance(result, UnitValue)

    def test_max_compatible_units(self):
        result = evaluate_raw("max(1*m, 300*cm)")
        assert isinstance(result, UnitValue)
        assert abs(result.value - 3.0) < 1e-10

    def test_median_compatible_units(self):
        result = evaluate_raw("median(1*m, 2*m, 3*m)")
        assert isinstance(result, UnitValue)
        assert result.value == 2.0

    def test_sum_compatible_units(self):
        result = evaluate_raw("sum(1*m, 2*m)")
        assert isinstance(result, UnitValue)
        assert result.value == 3.0

    @pytest.mark.parametrize("func", ["std", "std_sample", "variance", "variance_sample"])
    def test_stats_compatible_units(self, func):
        result = evaluate_raw(f"{func}(1*m, 2*m, 3*m)")
        assert isinstance(result, UnitValue)


# ---------------------------------------------------------------------------
# Workstream B: sqrt with dimensional support
# ---------------------------------------------------------------------------


class TestSqrtDimensional:
    """sqrt preserves even-exponent units, rejects odd exponents."""

    def test_sqrt_dimensionless(self):
        assert evaluate("sqrt(4)") == 2.0

    def test_sqrt_complex(self):
        assert evaluate("sqrt(-1)") == 1j

    def test_sqrt_even_exponent(self):
        """sqrt(4*m**2) -> 2 m"""
        result = evaluate_raw("sqrt(4*m**2)")
        assert isinstance(result, UnitValue)
        assert abs(result.value - 2.0) < 1e-10
        assert result.unit == "m"

    def test_sqrt_odd_exponent_rejected(self):
        """sqrt(4*m) -> error (m has exponent 1, not even)"""
        with pytest.raises(EvaluationError, match="cannot represent"):
            evaluate_raw("sqrt(4*m)")

    def test_sqrt_compound_even(self):
        """sqrt(9*m**2/s**2) -> 3 m/s"""
        result = evaluate_raw("sqrt(9*m**2/s**2)")
        assert isinstance(result, UnitValue)
        assert abs(result.value - 3.0) < 1e-10


# ---------------------------------------------------------------------------
# Workstream B: hypot with compatible units
# ---------------------------------------------------------------------------


class TestHypot:
    """hypot requires all args dimensionless or all compatible."""

    def test_hypot_dimensionless(self):
        assert abs(evaluate("hypot(3, 4)") - 5.0) < 1e-10

    def test_hypot_compatible_units(self):
        result = evaluate_raw("hypot(3*m, 400*cm)")
        assert isinstance(result, UnitValue)
        assert abs(result.value - 5.0) < 1e-10
        assert result.unit == "m"

    def test_hypot_incompatible_units(self):
        with pytest.raises(EvaluationError, match="compatible"):
            evaluate_raw("hypot(3*m, 4*s)")

    def test_hypot_mixed_scalar_unit(self):
        with pytest.raises(EvaluationError, match="compatible"):
            evaluate_raw("hypot(3*m, 4)")


# ---------------------------------------------------------------------------
# Workstream B: Unit-preserving single-value transforms
# ---------------------------------------------------------------------------


class TestPreserveSingle:
    """abs, round, floor, ceil, trunc, sign preserve UnitValue."""

    def test_abs_preserves_unit(self):
        result = evaluate_raw("abs(-5*m)")
        assert isinstance(result, UnitValue)
        assert result.value == 5
        assert result.unit == "m"

    def test_round_preserves_unit(self):
        result = evaluate_raw("round(3.7*m)")
        assert isinstance(result, UnitValue)
        assert result.value == 4.0
        assert result.unit == "m"

    def test_round_with_ndigits_preserves_unit(self):
        result = evaluate_raw("round(3.14*m, 1)")
        assert isinstance(result, UnitValue)
        assert abs(result.value - 3.1) < 1e-10
        assert result.unit == "m"

    def test_floor_preserves_unit(self):
        result = evaluate_raw("floor(3.7*m)")
        assert isinstance(result, UnitValue)
        assert result.value == 3
        assert result.unit == "m"

    def test_ceil_preserves_unit(self):
        result = evaluate_raw("ceil(3.2*m)")
        assert isinstance(result, UnitValue)
        assert result.value == 4
        assert result.unit == "m"

    def test_trunc_preserves_unit(self):
        result = evaluate_raw("trunc(-3.7*m)")
        assert isinstance(result, UnitValue)
        assert result.value == -3
        assert result.unit == "m"

    def test_sign_returns_dimensionless(self):
        result = evaluate_raw("sign(-5*m)")
        assert not isinstance(result, UnitValue)
        assert result == -1

    def test_abs_dimensionless(self):
        assert evaluate("abs(-5)") == 5

    def test_round_dimensionless(self):
        assert evaluate("round(3.7)") == 4


# ---------------------------------------------------------------------------
# Workstream B: User-registered functions default to dimensionless
# ---------------------------------------------------------------------------


class TestUserFunctionDefault:
    """User-registered functions must reject UnitValue arguments."""

    def test_user_function_rejects_dimensional(self):
        ev = Evaluator()
        ev.FUNCTIONS["double"] = lambda x: x * 2
        with pytest.raises(EvaluationError, match="dimensionless"):
            ev.evaluate("double(5*m)")

    def test_user_function_accepts_dimensionless(self):
        ev = Evaluator()
        ev.FUNCTIONS["double"] = lambda x: x * 2
        assert ev.evaluate("double(5)") == 10


# ---------------------------------------------------------------------------
# Workstream C: Angle model
# ---------------------------------------------------------------------------


class TestAngleModel:
    """Angle model: degrees convert, non-angles rejected."""

    def test_sin_90_degrees(self):
        """sin(90*deg) must be 1, not sin(90 radians)."""
        result = evaluate_raw("sin(90*deg)")
        assert abs(result - 1.0) < 1e-10

    def test_cos_0_degrees(self):
        result = evaluate_raw("cos(0*deg)")
        assert abs(result - 1.0) < 1e-10

    def test_sin_pi_radians(self):
        """sin(pi rad) ≈ 0."""
        result = evaluate_raw("sin(pi*rad)")
        assert abs(result) < 1e-10

    def test_non_angle_dimension_rejected_by_trig(self):
        with pytest.raises(EvaluationError, match="dimensionless or angle"):
            evaluate_raw("sin(1*m)")

    def test_compound_angle_deg_per_s(self):
        """deg/s produces angular velocity with angle=True dimension."""
        result = evaluate_raw("30*deg/s")
        assert isinstance(result, UnitValue)
        assert result.value == 30
        assert result.unit == "deg/s"

    def test_compound_angle_rad_per_s(self):
        result = evaluate_raw("5*rad/s")
        assert isinstance(result, UnitValue)
        assert result.value == 5

    def test_compound_angle_cancel(self):
        """deg/s * s cancels time, leaving direct angle."""
        result = evaluate_raw("30*deg/s * 2*s")
        assert isinstance(result, UnitValue)
        assert abs(result.value - 60) < 1e-10
        assert result.unit == "deg"

    def test_compound_angle_rejected_by_trig(self):
        """Angular velocity (deg/s) must not be accepted as angle input."""
        with pytest.raises(EvaluationError, match="dimensionless or angle"):
            evaluate_raw("sin(1*deg/s)")

    def test_compound_angle_division(self):
        """180*deg / (pi*s) produces angular velocity."""
        result = evaluate_raw("180*deg / (pi*s)")
        assert isinstance(result, UnitValue)
        assert abs(result.value - 57.2958) < 0.01
        assert result.unit == "deg/s"


# ---------------------------------------------------------------------------
# Workstream D: Timeout evaluator state parity
# ---------------------------------------------------------------------------


class TestTimeoutStateParity:
    """Timeout evaluation must reconstruct supported evaluator state."""

    def test_timeout_constant_parity(self):
        """Registered scalar constants must be available in timeout eval."""
        ev = Evaluator()
        ev.CONSTANTS["testconst"] = 42
        result = evaluate_with_timeout("testconst", timeout=5.0, _evaluator=ev)
        assert result == 42

    def test_timeout_variable_parity(self):
        """Variables must be available in timeout eval."""
        ev = Evaluator()
        ev._user_variables["testvar"] = 99
        result = evaluate_with_timeout("testvar", timeout=5.0, _evaluator=ev)
        assert result == 99

    def test_timeout_memory_parity(self):
        """Memory registers must be available in timeout eval."""
        ev = Evaluator()
        ev._memory.store(77, "M")
        result = evaluate_with_timeout("recall()", timeout=5.0, _evaluator=ev)
        assert result == 77

    def test_timeout_builtin_function_parity(self):
        """Built-in functions must be available in timeout eval."""
        ev = Evaluator()
        result = evaluate_with_timeout("sqrt(16)", timeout=5.0, _evaluator=ev)
        assert result == 4.0

    def test_timeout_rejects_custom_function(self):
        """Custom registered functions must cause immediate failure."""
        ev = Evaluator()
        ev.FUNCTIONS["custom_fn"] = lambda: 42
        with pytest.raises(EvaluationError, match="custom registered"):
            evaluate_with_timeout("1+1", timeout=5.0, _evaluator=ev)

    def test_timeout_termination(self):
        """Timeout must terminate and not leak child processes."""
        from eggcalc import TimeoutError

        ev = Evaluator()
        with pytest.raises(TimeoutError):
            evaluate_with_timeout("2**2**2**2**2**2**2**2", timeout=0.01, _evaluator=ev)

    def test_timeout_allow_random_true(self):
        """allow_random=True permits random functions in timeout worker."""
        ev = Evaluator(allow_random=True)
        result = evaluate_with_timeout("random()", timeout=5.0, _evaluator=ev)
        assert isinstance(result, float)
        assert 0.0 <= result < 1.0

    def test_timeout_allow_random_false(self):
        """allow_random=False rejects random functions in timeout worker."""
        ev = Evaluator(allow_random=False)
        with pytest.raises(EvaluationError, match="non-deterministic"):
            evaluate_with_timeout("random()", timeout=5.0, _evaluator=ev)

    def test_timeout_allow_side_effects_false(self):
        """allow_side_effects=False rejects state-mutating functions."""
        ev = Evaluator(allow_side_effects=False)
        with pytest.raises(EvaluationError, match="mutates evaluator state"):
            evaluate_with_timeout("store(42)", timeout=5.0, _evaluator=ev)

    def test_timeout_allow_side_effects_override(self):
        """Explicit allow_side_effects=True overrides parent evaluator."""
        ev = Evaluator(allow_side_effects=False)
        result = evaluate_with_timeout(
            "store(42)", timeout=5.0, _evaluator=ev, allow_side_effects=True
        )
        assert result == 42.0


# ---------------------------------------------------------------------------
# Workstream E: Custom unit category validation
# ---------------------------------------------------------------------------


class TestCustomUnitCategoryValidation:
    """Custom unit registration must reject category/dimension mismatches."""

    def test_valid_inherited_category(self):
        from eggcalc.units import register_custom_units, unregister_custom_units

        try:
            register_custom_units({"m": {"xu": 0.001}})
            from eggcalc.units import get_unit_category

            assert get_unit_category("xu") == "length"
        finally:
            unregister_custom_units(["xu"])

    def test_valid_explicit_matching_category(self):
        from eggcalc.units import register_custom_units, unregister_custom_units

        try:
            register_custom_units({"m": {"xu2": (0.001, "length")}})
            from eggcalc.units import get_unit_category

            assert get_unit_category("xu2") == "length"
        finally:
            unregister_custom_units(["xu2"])

    def test_invalid_explicit_mismatched_category(self):
        from eggcalc.units import register_custom_units

        with pytest.raises(ValueError, match="does not match"):
            register_custom_units({"m": {"badunit": (0.001, "time")}})

    def test_unknown_category(self):
        from eggcalc.units import register_custom_units

        with pytest.raises(ValueError, match="does not match"):
            register_custom_units({"m": {"badunit2": (0.001, "nonexistent")}})


# ---------------------------------------------------------------------------
# Explicit negative tests from plan section 13
# ---------------------------------------------------------------------------


class TestExplicitNegatives:
    """These must raise errors, not return plausible unitless numbers."""

    def test_sqrt_4m_rejected(self):
        with pytest.raises(EvaluationError):
            evaluate_raw("sqrt(4*m)")

    def test_log_5kg_rejected(self):
        with pytest.raises(EvaluationError):
            evaluate_raw("log(5*kg)")

    def test_mean_incompatible_rejected(self):
        with pytest.raises(EvaluationError):
            evaluate_raw("mean(1*m, 1*s)")

    def test_hypot_incompatible_rejected(self):
        with pytest.raises(EvaluationError):
            evaluate_raw("hypot(3*m, 4*s)")

    def test_sin_1m_rejected(self):
        with pytest.raises(EvaluationError):
            evaluate_raw("sin(1*m)")

    def test_atan2_incompatible_rejected(self):
        with pytest.raises(EvaluationError):
            evaluate_raw("atan2(1*m, 1*s)")

    def test_sin_90_deg_uses_conversion(self):
        result = evaluate_raw("sin(90*deg)")
        assert abs(result - 1.0) < 1e-10

    def test_timeout_does_not_lose_constant(self):
        ev = Evaluator()
        ev.CONSTANTS["timeout_test_const"] = 123
        result = evaluate_with_timeout("timeout_test_const", timeout=5.0, _evaluator=ev)
        assert result == 123

    def test_timeout_rejects_custom_callable(self):
        ev = Evaluator()
        ev.FUNCTIONS["tempfn"] = lambda: 1
        with pytest.raises(EvaluationError, match="custom registered"):
            evaluate_with_timeout("1+1", timeout=5.0, _evaluator=ev)

    def test_length_unit_cannot_be_time_category(self):
        from eggcalc.units import register_custom_units

        with pytest.raises(ValueError, match="does not match"):
            register_custom_units({"m": {"fake_time": (1.0, "time")}})


# ---------------------------------------------------------------------------
# Workstream A: Variance squared units
# ---------------------------------------------------------------------------


class TestVarianceSquaredUnits:
    """Variance functions must return squared units for dimensional input."""

    @pytest.mark.parametrize("func", ["variance", "var"])
    def test_population_variance_squared_unit(self, func):
        result = evaluate_raw(f"{func}(1*m, 2*m, 3*m)")
        assert isinstance(result, UnitValue)
        assert abs(result.value - 2 / 3) < 1e-10
        assert result.unit == "m**2"

    @pytest.mark.parametrize("func", ["variance_sample", "vars", "var_sample"])
    def test_sample_variance_squared_unit(self, func):
        result = evaluate_raw(f"{func}(1*m, 2*m, 3*m)")
        assert isinstance(result, UnitValue)
        assert abs(result.value - 1.0) < 1e-10
        assert result.unit == "m**2"

    def test_variance_mixed_scale_squared(self):
        result = evaluate_raw("variance(1*m, 200*cm, 3*m)")
        assert isinstance(result, UnitValue)
        assert abs(result.value - 2 / 3) < 1e-10
        assert result.unit == "m**2"

    def test_variance_ft_squared(self):
        result = evaluate_raw("variance_sample(1*ft, 2*ft)")
        assert isinstance(result, UnitValue)
        assert result.unit == "ft**2"

    def test_std_remains_first_power(self):
        result = evaluate_raw("std(1*m, 2*m, 3*m)")
        assert isinstance(result, UnitValue)
        assert result.unit == "m"

    def test_mean_remains_first_power(self):
        result = evaluate_raw("mean(1*m, 2*m, 3*m)")
        assert isinstance(result, UnitValue)
        assert result.unit == "m"

    def test_variance_dimensionless(self):
        result = evaluate("variance(1, 2, 3)")
        assert abs(result - 2 / 3) < 1e-10

    def test_variance_incompatible_units(self):
        with pytest.raises(EvaluationError, match="compatible"):
            evaluate_raw("variance(1*m, 1*s)")

    def test_variance_mixed_dimensional_dimensionless(self):
        with pytest.raises(EvaluationError, match="compatible"):
            evaluate_raw("variance(1*m, 1)")

    def test_variance_affine_temperature_rejected(self):
        with pytest.raises(EvaluationError, match="squared affine"):
            evaluate_raw("variance(10*C, 20*C, 30*C)")

    def test_variance_single_arg(self):
        with pytest.raises(EvaluationError):
            evaluate_raw("variance(1*m)")


# ---------------------------------------------------------------------------
# Workstream B: Dimensionless sign
# ---------------------------------------------------------------------------


class TestSignDimensionless:
    """sign() must always return a dimensionless scalar."""

    def test_sign_with_unit(self):
        result = evaluate_raw("sign(-5*m)")
        assert not isinstance(result, UnitValue)
        assert result == -1

    def test_sign_zero_with_unit(self):
        result = evaluate_raw("sign(0*m)")
        assert not isinstance(result, UnitValue)
        assert result == 0

    def test_sign_positive_with_unit(self):
        result = evaluate_raw("sign(5*m)")
        assert not isinstance(result, UnitValue)
        assert result == 1

    def test_sign_dimensionless(self):
        assert evaluate("sign(-5)") == -1
        assert evaluate("sign(0)") == 0
        assert evaluate("sign(5)") == 1


# ---------------------------------------------------------------------------
# Workstream B: Exact round() return type
# ---------------------------------------------------------------------------


class TestRoundReturnType:
    """round() must preserve Python's exact return type semantics."""

    def test_round_omitted_ndigits_returns_int(self):
        result = evaluate("round(3.7)")
        assert type(result) is int
        assert result == 4

    def test_round_explicit_zero_ndigits_returns_float(self):
        result = evaluate("round(3.7, 0)")
        assert type(result) is float
        assert result == 4.0

    def test_round_keyword_zero_ndigits_returns_float(self):
        result = evaluate("round(3.7, ndigits=0)")
        assert type(result) is float
        assert result == 4.0

    def test_round_with_ndigits(self):
        result = evaluate("round(3.14159, 2)")
        assert result == 3.14

    def test_round_unit_omitted_ndigits(self):
        result = evaluate_raw("round(3.7*m)")
        assert isinstance(result, UnitValue)
        assert type(result.value) is int
        assert result.value == 4
        assert result.unit == "m"

    def test_round_unit_explicit_zero_ndigits(self):
        result = evaluate_raw("round(3.7*m, 0)")
        assert isinstance(result, UnitValue)
        assert type(result.value) is float
        assert result.value == 4.0
        assert result.unit == "m"

    def test_round_unit_keyword_ndigits(self):
        result = evaluate_raw("round(3.7*m, ndigits=0)")
        assert isinstance(result, UnitValue)
        assert type(result.value) is float
        assert result.value == 4.0

    def test_duplicate_ndigits_rejected(self):
        with pytest.raises(EvaluationError):
            evaluate("round(3.7, 0, ndigits=0)")


# ---------------------------------------------------------------------------
# Workstream C: Callable identity authority
# ---------------------------------------------------------------------------


class TestCallableIdentity:
    """Built-in unit policies apply only to canonical built-in callables."""

    def test_override_sin_no_angle_policy(self):
        ev = Evaluator()
        ev.FUNCTIONS["sin"] = lambda x: x
        # Custom sin: no angle conversion, just passes through dimensionless
        assert ev.evaluate("sin(2)") == 2

    def test_override_sin_rejects_dimensional(self):
        ev = Evaluator()
        ev.FUNCTIONS["sin"] = lambda x: x
        with pytest.raises(EvaluationError, match="dimensionless"):
            ev.evaluate("sin(2*m)")

    def test_override_round_no_preserve_policy(self):
        ev = Evaluator()
        ev.FUNCTIONS["round"] = lambda x: x
        # Custom round: dimensionless-only, identity function
        assert ev.evaluate("round(3.7)") == 3.7

    def test_override_round_rejects_dimensional(self):
        ev = Evaluator()
        ev.FUNCTIONS["round"] = lambda x: x
        with pytest.raises(EvaluationError, match="dimensionless"):
            ev.evaluate("round(3.7*m)")

    def test_override_variance_no_squared_policy(self):
        ev = Evaluator()
        ev.FUNCTIONS["variance"] = lambda *args: sum(args) / len(args)
        # Custom variance: dimensionless-only
        assert ev.evaluate("variance(1, 2, 3)") == 2.0

    def test_override_variance_rejects_dimensional(self):
        ev = Evaluator()
        ev.FUNCTIONS["variance"] = lambda *args: sum(args) / len(args)
        with pytest.raises(EvaluationError, match="dimensionless"):
            ev.evaluate("variance(1*m, 2*m, 3*m)")

    def test_add_custom_function_dimensionless(self):
        ev = Evaluator()
        ev.FUNCTIONS["double"] = lambda x: x * 2
        result = ev.evaluate("double(5)")
        assert result == 10

    def test_add_custom_function_rejects_unit(self):
        ev = Evaluator()
        ev.FUNCTIONS["double"] = lambda x: x * 2
        with pytest.raises(EvaluationError, match="dimensionless"):
            ev.evaluate("double(5*m)")

    def test_restore_canonical_sin(self):
        ev = Evaluator()
        canonical_sin = ev._builtin_function_baseline["sin"]
        ev.FUNCTIONS["sin"] = lambda x: x
        with pytest.raises(EvaluationError, match="dimensionless"):
            ev.evaluate("sin(2*m)")  # custom, rejects dimensional
        ev.FUNCTIONS["sin"] = canonical_sin
        assert abs(ev.evaluate("sin(pi/2)") - 1.0) < 1e-10  # canonical, angle policy

    def test_canonical_random_recognized(self):
        ev = Evaluator(random_seed=1)
        baseline = ev._builtin_function_baseline
        assert ev.FUNCTIONS["random"] is baseline["random"]
        assert ev.FUNCTIONS["randint"] is baseline["randint"]


# ---------------------------------------------------------------------------
# Workstream D: Timeout callable identity rejection
# ---------------------------------------------------------------------------


class TestTimeoutCallableIdentity:
    """Timeout rejects added and overridden callables before spawning."""

    def test_timeout_rejects_added_function(self):
        ev = Evaluator()
        ev.FUNCTIONS["double"] = lambda x: x * 2
        with pytest.raises(EvaluationError, match="double"):
            evaluate_with_timeout("1+1", timeout=5.0, _evaluator=ev)

    def test_timeout_rejects_overridden_builtin(self):
        ev = Evaluator()
        ev.FUNCTIONS["sin"] = lambda x: x
        with pytest.raises(EvaluationError, match="sin"):
            evaluate_with_timeout("1+1", timeout=5.0, _evaluator=ev)

    def test_timeout_accepts_canonical_random(self):
        ev = Evaluator(random_seed=1)
        result = evaluate_with_timeout("random()", timeout=5.0, _evaluator=ev)
        assert isinstance(result, float)


# ---------------------------------------------------------------------------
# Workstream E: Angle algebra bounds
# ---------------------------------------------------------------------------


class TestAngleAlgebraBounds:
    """Unsupported angle powers and inverse-angle operations must fail clearly."""

    def test_deg_to_zero(self):
        result = evaluate_raw("deg**0")
        assert isinstance(result, UnitValue)
        assert result.unit is None

    def test_deg_to_one(self):
        result = evaluate_raw("deg**1")
        assert isinstance(result, UnitValue)
        assert result.unit == "deg"

    def test_deg_to_two(self):
        with pytest.raises(EvaluationError):
            evaluate_raw("deg**2")

    def test_deg_to_neg_one(self):
        with pytest.raises(EvaluationError):
            evaluate_raw("deg**-1")

    def test_deg_times_rad(self):
        with pytest.raises(EvaluationError):
            evaluate_raw("1/deg")

    def test_deg_times_rad_explicit(self):
        with pytest.raises(EvaluationError):
            evaluate_raw("deg*rad")

    def test_deg_div_rad_dimensionless(self):
        result = evaluate_raw("deg/rad")
        # Same-dimension division produces dimensionless; evaluator unwraps
        assert isinstance(result, float)
        assert abs(result - 0.017453) < 0.001

    def test_deg_per_s_times_s(self):
        result = evaluate_raw("(30*deg/s) * (2*s)")
        assert isinstance(result, UnitValue)
        assert result.unit == "deg"

    def test_deg_per_s_times_rad_per_s(self):
        with pytest.raises(EvaluationError):
            evaluate_raw("(deg/s)*(rad/s)")

    def test_sin_deg_per_s(self):
        with pytest.raises(EvaluationError, match="dimensionless or angle"):
            evaluate_raw("sin(deg/s)")
