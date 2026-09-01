"""Regression tests for the September 2026 bug report."""

import pytest


@pytest.mark.parametrize(
    ("expression", "expected_value", "expected_unit"),
    [
        ("5 m / 3 s^2", 5 / 3, "m/s**2"),
        ("10 kg / 2 s^3", 5, "kg/s**3"),
        ("5m/3s^2", 5 / 3, "m/s**2"),
        ("10kg/2s^3", 5, "kg/s**3"),
    ],
)
def test_unit_denominator_exponents_stay_inside_group(expression, expected_value, expected_unit):
    from eggcalc import evaluate_raw
    from eggcalc.normalize import NORMALIZE, PATTERNS, normalize_expression
    from eggcalc.units import UnitValue

    normalized, code = normalize_expression(expression, NORMALIZE, PATTERNS)
    assert code == 0
    assert "/(" in normalized
    result = evaluate_raw(expression)
    assert isinstance(result, UnitValue)
    assert result.value == pytest.approx(expected_value)
    assert result.unit == expected_unit


@pytest.mark.parametrize("token", [".", "+.", "-.", "5.."])
def test_bare_decimal_points_are_not_numbers(token):
    from eggcalc.normalize import check_if_number

    result = check_if_number(token)
    assert result["bool"] is False
    assert result["converted"] == token


def test_bare_decimal_point_raises_evaluation_error():
    from eggcalc import EvaluationError, evaluate_raw

    with pytest.raises(EvaluationError):
        evaluate_raw(". + 1")


def test_bitwise_variables_reject_booleans():
    from eggcalc import EvaluationError
    from eggcalc.evaluator import Evaluator

    evaluator = Evaluator()
    evaluator._user_variables["truth"] = True
    with pytest.raises(EvaluationError):
        evaluator.evaluate("truth | 1")
    with pytest.raises(EvaluationError):
        evaluator.evaluate("truth & 1")


def test_combination_result_has_digit_limit(monkeypatch):
    import eggcalc.evaluator as evaluator

    monkeypatch.setattr(evaluator, "MAX_RESULT_DIGITS", 1)
    with pytest.raises(evaluator.EvaluationError, match="too many digits"):
        evaluator._comb(5, 2)


def test_large_integer_digit_count_is_efficient_and_exact():
    from eggcalc.evaluator import _int_digit_count

    assert _int_digit_count(10**10000 - 1) == 10000


def test_parenthesized_compound_unit_floor_mod_operand_is_grouped():
    from eggcalc.normalize import NORMALIZE, PATTERNS, normalize_expression

    normalized, code = normalize_expression("7*m/s//1*(m/s)", NORMALIZE, PATTERNS)
    assert code == 0
    assert normalized == "(7*m/s)//(1*(m/s))"


def test_register_constant_requires_identifier():
    from eggcalc import register_constant

    with pytest.raises(ValueError):
        register_constant("not valid", 1)


def test_app_registration_validates_names_and_callables():
    from eggcalc import EggCalcApp

    app = EggCalcApp()
    with pytest.raises(ValueError):
        app.register_constant("not valid", 1)
    with pytest.raises(ValueError):
        app.register_function("not valid", lambda: 1)
    with pytest.raises(TypeError):
        app.register_function("valid_name", "not callable")


def test_custom_function_names_with_digits_are_normalized():
    import eggcalc.evaluator as evaluator
    from eggcalc import EggCalcApp, evaluate_raw
    from eggcalc.normalize import normalize_expression

    def f_1(value):
        return value * 2

    evaluator.register_function("f_1", f_1)
    try:
        normalized, code = normalize_expression("f_1(5)")
        assert (normalized, code) == ("f_1(5)", 0)
        assert evaluate_raw("f_1(5)") == 10
    finally:
        evaluator._default_evaluator.FUNCTIONS.pop("f_1", None)

    app = EggCalcApp()
    app.register_function("f_1", f_1)
    assert app.calculate("f_1(5)") == 10


def test_truncated_equal_span_recomputes_visible_text():
    from eggcalc.exact.synthesis import _truncate_diff_spans

    spans, truncated, omitted = _truncate_diff_spans(
        [
            {
                "kind": "equal",
                "a_span": [0, 250],
                "b_span": [0, 250],
                "a_text": "a" * 250,
                "b_text": "a" * 250,
                "a_visible": "a" * 250,
                "b_visible": "a" * 250,
                "a_codepoints": [],
                "b_codepoints": [],
                "note": "Matching text",
            }
        ],
        max_diffs=1,
        max_equal_context=10,
    )

    assert not truncated
    assert omitted == 0
    assert spans[0]["a_text"] == "a" * 10 + "..."
    assert spans[0]["a_visible"] == "a" * 10 + "..."


def test_json_extract_preserves_integer_type():
    from eggcalc.exact.validate import json_extract

    assert json_extract('{"value": 42}', "/value")["value_type"] == "integer"


def test_json_compare_reports_value_changes_in_overlapping_arrays():
    from eggcalc.exact.validate import json_compare

    result = json_compare("[1, 2, 3]", "[1, 99, 3, 4]")
    assert [diff["kind"] for diff in result["diffs"]] == [
        "array_length_changed",
        "value_changed",
    ]
    assert result["diffs"][1]["path"] == "/[1]"


def test_app_cache_enforces_byte_cap(monkeypatch):
    import eggcalc.evaluator as evaluator
    from eggcalc import EggCalcApp

    monkeypatch.setattr(evaluator, "MAX_CACHE_BYTES", 1)
    app = EggCalcApp(cache_size=4)
    app.calculate("1")
    app.calculate("2")

    assert app.cache_size == 1
    assert app._cache_bytes > 1
