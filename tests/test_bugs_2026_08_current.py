"""Regression tests for the remaining findings in the 2026-08 bug audit."""

from __future__ import annotations

import ast

import pytest


def test_global_variable_mutations_invalidate_cache():
    from eggcalc import clearvars, delvar, evaluate_cached, setvar
    from eggcalc.evaluator import EvaluationError

    clearvars()
    setvar("audit_cache_value", 5)
    assert evaluate_cached("audit_cache_value + 1") == 6
    setvar("audit_cache_value", 10)
    assert evaluate_cached("audit_cache_value + 1") == 11
    delvar("audit_cache_value")
    with pytest.raises(EvaluationError):
        evaluate_cached("audit_cache_value + 1")
    clearvars()


def test_app_evaluator_variable_mutations_invalidate_instance_cache():
    from eggcalc import EggCalcApp

    app = EggCalcApp()
    app._evaluator.evaluate('setvar("audit_app_value", 5)')
    assert app.calculate("audit_app_value + 1") == 6
    app._evaluator.evaluate('setvar("audit_app_value", 10)')
    assert app.calculate("audit_app_value + 1") == 11


def test_configure_default_evaluator_clears_cache():
    import eggcalc.evaluator as evaluator
    from eggcalc import evaluate_cached, get_default_evaluator

    configure_default_evaluator = evaluator.configure_default_evaluator

    evaluate_cached("17 + 1")
    with evaluator._cache_lock:
        assert "17 + 1" in evaluator._cache
    default = get_default_evaluator()
    configure_default_evaluator(allow_random=not default._allow_random)
    with evaluator._cache_lock:
        assert "17 + 1" not in evaluator._cache
    configure_default_evaluator(allow_random=not default._allow_random)


def test_as_percent_accepts_small_finite_divisors():
    from eggcalc import evaluate_raw

    assert evaluate_raw("as_percent(1, 1e-150)") == pytest.approx(1e152)


@pytest.mark.parametrize(
    "value",
    [float("nan"), complex(float("nan"), 0)],
)
def test_nan_result_has_specific_error(value):
    from eggcalc.evaluator import EvaluationError, _check_result_size

    with pytest.raises(EvaluationError, match="Result is not a number"):
        _check_result_size(value)


def test_unit_nan_result_has_specific_error():
    from eggcalc.evaluator import EvaluationError, _check_result_size
    from eggcalc.units import UnitValue

    value = object.__new__(UnitValue)
    value.value = float("nan")
    with pytest.raises(EvaluationError, match="Result is not a number"):
        _check_result_size(value)


def test_evaluator_ast_validation_walks_once(monkeypatch):
    from eggcalc import evaluator

    original_walk = ast.walk
    calls = 0

    def counting_walk(tree):
        nonlocal calls
        calls += 1
        return original_walk(tree)

    monkeypatch.setattr(ast, "walk", counting_walk)
    assert evaluator.Evaluator().evaluate("1 + 1") == 2
    assert calls == 1


def test_cached_bypass_uses_ast_calls_not_substrings():
    from eggcalc.evaluator import _expression_bypasses_cache

    assert not _expression_bypasses_cache('"random("')
    assert _expression_bypasses_cache("random()")


def test_check_if_number_cache_result_is_immutable():
    from eggcalc.normalize import check_if_number

    result = check_if_number("42")
    with pytest.raises(TypeError):
        result["bool"] = False  # type: ignore[index]
    assert check_if_number("42")["bool"] is True


def test_unexpected_number_conversion_error_does_not_leave_dict_token(monkeypatch):
    import eggcalc.normalize as normalize

    def fail(*args, **kwargs):
        raise TypeError("unexpected conversion failure")

    monkeypatch.setattr(normalize, "convert_numbers", fail)
    tokens = ["not a number"]
    with pytest.raises(TypeError, match="unexpected conversion failure"):
        normalize.convert_from_human_handler(tokens, {}, normalize.PATTERNS, "not a number")
    assert tokens == ["not a number"]


def test_number_parts_return_separate_operator_tokens():
    from eggcalc.normalize import PATTERNS, combine_number_parts

    assert combine_number_parts([3, 100, 20, 2], PATTERNS, []) == [
        "3",
        "*",
        "100",
        "+",
        "22",
    ]


def test_dimensionless_unitvalue_divisors_follow_numeric_path():
    from eggcalc.units import UnitValue

    assert str(UnitValue(5, "m") // UnitValue(2, None)) == "2 m"
    assert str(UnitValue(5, "m") % UnitValue(2, None)) == "1 m"


def test_unitvalue_checks_large_integer_magnitude():
    from eggcalc.units import UnitValue

    with pytest.raises(OverflowError):
        UnitValue(10**1_000_000, "m") + UnitValue(0, "m")


def test_unit_registry_length_is_canonical_count():
    from eggcalc.units import build_unit_registry

    registry = build_unit_registry()
    assert len(registry) == len(registry.definitions)
    assert len(registry.all_aliases) > len(registry)


# ---------------------------------------------------------------------------
# 2026-09-01 bugs.md: abs(complex) leaks OverflowError at three call sites,
# and visit_BinOp is missing the MAX_RESULT_VALUE magnitude check for complex.
# ---------------------------------------------------------------------------
class TestComplexAbsOverflow:
    """abs(complex) raises OverflowError for |x| > ~1.97e308 with finite components.

    All three call sites (_check_result_size for UnitValue+complex, for bare
    complex, and _safe_pow's post-pow magnitude check) must catch it.
    """

    def test_balance_overflow_at_check_result_size_bare_complex(self):
        from eggcalc.evaluator import EvaluationError, evaluate

        with pytest.raises(EvaluationError, match="Result too large"):
            evaluate("(7e307+7e307j) + (7e307+7e307j)")

    def test_complex_with_huge_components_at_check_result_size(self):
        from eggcalc.evaluator import EvaluationError, evaluate

        with pytest.raises(EvaluationError, match="Result too large"):
            evaluate("(1.4e308+1.4e308j) + 0j")

    def test_check_result_size_unitvalue_complex_overflow(self):
        from eggcalc.evaluator import EvaluationError, _check_result_size
        from eggcalc.units import UnitValue

        value = object.__new__(UnitValue)
        value.value = complex(1.4e308, 1.4e308)
        with pytest.raises(EvaluationError, match="Result too large"):
            _check_result_size(value)

    def test_safe_pow_complex_result_overflow_at_abs(self):
        from eggcalc.evaluator import EvaluationError, _safe_pow

        with pytest.raises(EvaluationError, match="Result too large"):
            _safe_pow(complex(1.4e308, 1.4e308), 1.0)

    def test_check_result_size_bare_complex_overflow(self):
        from eggcalc.evaluator import EvaluationError, _check_result_size

        with pytest.raises(EvaluationError, match="Result too large"):
            _check_result_size(complex(1.4e308, 1.4e308))

    def test_finite_complex_just_under_threshold_is_accepted(self):
        from eggcalc.evaluator import evaluate

        assert evaluate("(1e308+0j)") == complex(1e308, 0.0)

    def test_normal_complex_arithmetic_still_works(self):
        from eggcalc.evaluator import evaluate

        assert evaluate("(3+4j) * (3-4j)") == complex(25, 0)
        assert evaluate("abs(3+4j)") == 5.0
