"""Regression tests for actionable defects from bugs.md (August 2026)."""

import ast
import math
import unicodedata
from unittest.mock import patch

import pytest

from eggcalc import EvaluationError, evaluate, evaluate_raw
from eggcalc.cli import _cli_text_command, _CommandStatus, _run_repl, run_cli
from eggcalc.evaluator import (
    _int_digit_count,
    _polar,
    _prime_factors,
    _root_unit_expression,
    _safe_pow,
)
from eggcalc.exact.primitives import detect_newline_style
from eggcalc.exact.repo_audit import _classify_path
from eggcalc.exact.shell import shell_split
from eggcalc.exact.synthesis import _detect_special_sequences, text_window
from eggcalc.exact.validate import _check_pattern_complexity, regex_safety_check, validate_json
from eggcalc.mcp.server import McpServer, McpSession, McpSessionState, handle_request
from eggcalc.normalize import NORMALIZE, PATTERNS, normalize_expression, normalize_text
from eggcalc.units import UNIT_CONVERSIONS, UnitValue, convert_temperature


def test_multi_word_number_misses_do_not_scan_a_monolithic_regex():
    from eggcalc.normalize import _replace_multi_word_numbers

    expression = "a b c d " * 1000
    assert _replace_multi_word_numbers(expression) == expression


def test_unit_value_equality_uses_physical_quantity():
    assert UnitValue(5, "m") == UnitValue(5, "meter")
    assert UnitValue(100, "cm") == UnitValue(1, "m")
    assert hash(UnitValue(100, "cm")) == hash(UnitValue(1, "m"))
    assert UnitValue(1, "m") != UnitValue(1, "s")


def test_cross_unit_floor_division_and_modulo_preserve_integral_types():
    quotient = UnitValue(700, "cm") // UnitValue(2, "m")
    remainder = UnitValue(700, "cm") % UnitValue(2, "m")
    assert quotient.value == 3
    assert isinstance(quotient.value, int)
    assert remainder.value == 1
    assert isinstance(remainder.value, int)
    assert isinstance((UnitValue(7, "m") // UnitValue(2, "meter")).value, int)
    assert isinstance((UnitValue(7, "m") % UnitValue(2, "meter")).value, int)


def test_root_mapping_does_not_depend_on_canonical_suffix_slicing():
    assert str(evaluate_raw("sqrt(9*in2)")) == "3 inch"
    assert str(evaluate_raw("cbrt(8*ft3)")) == "2 ft"


def test_cache_byte_accounting_handles_none_and_large_values():
    import eggcalc.evaluator as evaluator

    evaluator._clear_global_cache()
    with evaluator._cache_lock:
        evaluator._store_cache_entry("__none_cache_test__", None)
        assert evaluator._cache_bytes > 0
    evaluator._remove_cache_entry("__none_cache_test__")
    assert evaluator._cache_bytes == 0
    large_int = 10**5000
    assert evaluator._entry_size("key", large_int) >= large_int.__sizeof__()


def test_flat_parentheses_count_toward_nesting_limit():
    from eggcalc.evaluator import EvaluationError

    with pytest.raises(EvaluationError, match="too deeply nested"):
        evaluate("(" * 101 + "1" + ")" * 101)


def test_safe_pow_accepts_integral_float_exponents():
    result = _safe_pow(5, 500.0)
    assert isinstance(result, int)
    assert result == 5**500


def test_safe_pow_preserves_float_type_when_result_fits():
    result = _safe_pow(5.0, 301)
    assert isinstance(result, float)
    assert result == float(5**301)


def test_root_unit_expression_reports_missing_scale_definition(monkeypatch):
    from eggcalc.units import DIM_LENGTH, Dimension, UnitDefinition, UnitExpression

    definition = UnitDefinition(
        canonical="m",
        dimension=DIM_LENGTH,
        scale=1.0,
        aliases=("m",),
        category="length",
        base_canonical="m",
    )

    class Registry:
        def __init__(self):
            self.calls = 0

        def by_canonical(self, canonical):
            self.calls += 1
            if self.calls == 1:
                return definition
            return None

    expression = UnitExpression((("m", 2),), Dimension(length=2), 1.0)
    registry = Registry()
    monkeypatch.setattr("eggcalc.units._get_unit_registry", lambda: registry)
    with pytest.raises(EvaluationError, match="Unknown canonical unit"):
        _root_unit_expression(expression, 2, "sqrt")


def test_visible_repr_only_reports_actual_changes():
    from eggcalc.exact.transform import text_transform

    result = text_transform("hello", ["visible_repr"])
    assert result["changed"] is False
    assert result["operations_applied"] == []
    assert result["summary"] == "No recognized operations applied"


@pytest.mark.parametrize(
    "char,escaped",
    [("\x00", r"\x00"), ("\x07", r"\x07"), ("\x1f", r"\x1f"), ("\x7f", r"\x7f")],
)
def test_python_string_escapes_control_characters(char, escaped):
    from eggcalc.exact.transform import _escape_python_string

    result = _escape_python_string(char)
    assert result == "'" + escaped + "'"
    assert ast.literal_eval(result) == char


@pytest.mark.parametrize(
    "text,expected",
    [("foo`bar", "`` foo`bar ``"), ("foo``bar", "``` foo``bar ```")],
)
def test_markdown_inline_code_uses_longer_fence(text, expected):
    from eggcalc.exact.transform import _escape_markdown_inline_code

    assert _escape_markdown_inline_code(text) == expected


def test_identifier_inspect_reuses_confusable_results(monkeypatch):
    import importlib

    identifier_module = importlib.import_module("eggcalc.exact.identifier_inspect")

    calls = []
    monkeypatch.setattr(
        identifier_module,
        "detect_confusables",
        lambda text: calls.append(text) or [],
    )
    identifier_module.identifier_inspect(["alpha", "beta", "alpha"], check_confusables=True)
    assert calls == ["alpha", "beta"]


def test_polar_supports_complex_and_coordinate_forms():
    radius, angle = _polar(1 + 1j)
    assert math.isclose(radius, math.sqrt(2))
    assert math.isclose(angle, math.pi / 4)
    assert _polar(2, 0) == (2.0, 0.0)


def test_unit_value_mcp_session_requires_initialization():
    assert McpSession().state is McpSessionState.UNINITIALIZED


def test_regional_indicator_pairs_do_not_overlap():
    flags = "\U0001f1fa\U0001f1f8\U0001f1ec\U0001f1e7"
    assert _detect_special_sequences(flags)["regional_indicator_pairs"] == 2


@pytest.mark.parametrize("path", [".eslintrc", ".prettierrc"])
def test_config_dotfiles_are_not_classified_as_hidden(path):
    assert _classify_path(path) == "config"


class TestDetectNewlineStyle:
    """Bug 1: mixed newline detection is incorrect."""

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("line1\r\nline2\nline3", "mixed"),
            ("line1\rline2\nline3", "mixed"),
            ("line1\r\nline2\rc", "mixed"),
            ("line1\r\nline2\r\nline3", "CRLF"),
            ("line1\nline2\nline3", "LF"),
            ("line1\rline2\rline3", "CR"),
            ("", "LF"),
        ],
    )
    def test_newline_styles(self, text, expected):
        assert detect_newline_style(text) == expected


class TestTextWindowGraphemeIndex:
    """Bug 2: text_window reports wrong grapheme index inside combining clusters."""

    def test_combining_mark_in_first_grapheme(self):
        text = unicodedata.normalize("NFD", "é") + "b"
        result = text_window(text, {"kind": "codepoint_index", "value": 1})
        assert result["position"]["grapheme_index"] == 0

    def test_letter_in_second_grapheme(self):
        text = "a👍b"
        result = text_window(text, {"kind": "codepoint_index", "value": 2})
        assert result["position"]["grapheme_index"] == 2

    def test_emoji_codepoint(self):
        text = "a👍b"
        result = text_window(text, {"kind": "codepoint_index", "value": 1})
        assert result["position"]["grapheme_index"] == 1


class TestShellFeatureDetection:
    """Bug 3: shell feature detection flags quoted metacharacters as active operators."""

    def test_quoted_pipe_not_detected(self):
        result = shell_split('echo "hello | world"')
        assert result["features"]["has_pipe"] is False

    def test_quoted_control_operator_not_detected(self):
        result = shell_split('echo "a && b"')
        assert result["features"]["has_control_operator"] is False

    def test_quoted_redirection_not_detected(self):
        result = shell_split('echo "a > b"')
        assert result["features"]["has_redirection"] is False

    def test_real_pipe_detected(self):
        result = shell_split("ls | grep foo")
        assert result["features"]["has_pipe"] is True

    def test_real_semicolon_detected(self):
        result = shell_split("echo a; echo b")
        assert result["features"]["has_control_operator"] is True


class TestRegexSafetyCharClass:
    """Bug 4: regex safety check flags .* inside character classes."""

    def test_dot_star_inside_char_class_low_risk(self):
        result = regex_safety_check(r"[.*]+")
        assert result["risk"] == "low"
        assert result["findings"] == []

    def test_real_dot_star_flagged(self):
        result = regex_safety_check("(.*)")
        kinds = [f["kind"] for f in result["findings"]]
        assert "ambiguous_dot_star" in kinds


class TestBitlshiftGuard:
    """Bug 5: left-shift guard rejects valid results below digit limit."""

    def test_30001_bit_shift_within_limit(self):
        # ~4214 decimal digits, within MAX_RESULT_DIGITS (= CPython's
        # int->str conversion boundary so callers can always print results).
        result = evaluate("1 << 14000")
        assert isinstance(result, int)
        assert result.bit_length() == 14001


class TestUnitPowerZeroUnwraps:
    """Bug 6: dimensionless unit power zero remains wrapped in UnitValue."""

    def test_m_pow_zero_returns_scalar(self):
        result = evaluate("m ** 0")
        assert isinstance(result, (int, float))
        assert result == 1

    def test_kg_pow_zero_returns_scalar(self):
        result = evaluate("kg ** 0")
        assert isinstance(result, (int, float))
        assert result == 1


def test_alternation_overlap_is_rejected_for_quantified_groups():
    safe, message = _check_pattern_complexity("(a|a)+b")
    assert safe is False
    assert "alternation" in message.lower()


@pytest.mark.parametrize("expression", ["10**400 * m", "(1e308*m) * 2"])
def test_unit_overflow_is_wrapped_as_evaluation_error(expression):
    with pytest.raises(EvaluationError):
        evaluate_raw(expression)


@pytest.mark.parametrize(
    "operation",
    [
        lambda: UnitValue(100, "C") * 2,
        lambda: 2 * UnitValue(100, "C"),
        lambda: UnitValue(100, "C") / 2,
        lambda: UnitValue(100, "C") // 2,
        lambda: UnitValue(100, "C") % 2,
        lambda: 2 / UnitValue(0, "C"),
    ],
)
def test_affine_scalar_operations_are_rejected(operation):
    with pytest.raises(ValueError, match="Affine"):
        operation()


@pytest.mark.parametrize(
    "expression,expected",
    [("2 xor 3 xor 4", 5), ("5!5!", 14400), ("3 squared 4", 36), ("3 cubed 5", 135)],
)
def test_normalization_preserves_chained_operator_meaning(expression, expected):
    assert evaluate_raw(expression) == expected


def test_multiword_reserved_operator_is_rejected():
    with pytest.raises(ValueError, match="not in"):
        normalize_text("5 not in 10", NORMALIZE, PATTERNS)


def test_matrix_multiplication_is_rejected_during_validation():
    with pytest.raises(EvaluationError, match="Invalid syntax"):
        evaluate("5 @ 3")


@pytest.mark.parametrize("expression", ["2 * 100*C", "2 * (100*C)"])
def test_affine_quantity_scaling_is_rejected(expression):
    with pytest.raises(EvaluationError, match="Affine"):
        evaluate_raw(expression)


def test_single_letter_unknown_conversion_target_has_clear_error():
    with pytest.raises(ValueError, match="gas constant.*Rankine"):
        normalize_text("100 K in R", NORMALIZE, PATTERNS)


def test_spaced_decimal_digits_are_merged_in_one_pass():
    normalized, code = normalize_expression("3.1 2", NORMALIZE, PATTERNS)
    assert code == 0
    assert normalized == "3.12"


def test_temperature_below_absolute_zero_is_rejected():
    with pytest.raises(ValueError, match="absolute zero"):
        UnitValue(-1, "K").convert_to("C")
    with pytest.raises(ValueError, match="absolute zero"):
        convert_temperature(-1, "K", "C")


def test_temperature_near_absolute_zero_is_snapped_before_guard():
    assert convert_temperature(-5e-13, "K", "C") == pytest.approx(-273.15)
    with pytest.raises(ValueError, match="absolute zero"):
        convert_temperature(-5e-10, "K", "C")


def test_large_integer_digit_count_is_exact():
    assert _int_digit_count(10**4300 - 1) == 4300
    assert _int_digit_count(-(10**4300 - 1)) == 4300


def test_prime_factors_skip_even_candidates_without_changing_result():
    assert _prime_factors(2**8 * 3**2 * 11) == "2^8 × 3^2 × 11"


def test_unit_conversion_mapping_returns_identity_factor():
    assert UNIT_CONVERSIONS[("m", "m")] == 1.0
    assert UNIT_CONVERSIONS[("meter", "m")] == 1.0
    assert ("m", "m") in UNIT_CONVERSIONS


def test_negative_app_cache_size_is_rejected():
    from eggcalc import EggCalcApp

    with pytest.raises(ValueError, match="cache_size"):
        EggCalcApp(cache_size=-1)


def test_pow_unit_guard_and_normalized_unit_power():
    with pytest.raises(EvaluationError, match="unit"):
        evaluate("2**(5*m)")
    result = evaluate_raw("2**5m")
    assert isinstance(result, UnitValue)
    assert result.value == 32
    assert result.unit == "m"


def test_mcp_math_eval_uses_server_timeout(monkeypatch):
    from eggcalc.mcp import tools as mcp_tools
    from eggcalc.mcp.server import McpServerConfig, ToolExecutor, ToolRegistry

    calls = []

    def fake_evaluate(expression, timeout):
        calls.append((expression, timeout))
        return 4

    monkeypatch.setattr(mcp_tools, "evaluate_with_timeout", fake_evaluate)
    executor = ToolExecutor(McpServerConfig(max_tool_timeout_seconds=7), ToolRegistry())
    try:
        response = executor.call_tool("math_eval", {"expression": "2+2"}, request_id="timeout")
    finally:
        executor.close()
    assert response["result"]["content"]
    assert calls == [("2+2", 7)]


def test_compact_units_are_case_insensitive_for_multi_character_symbols():
    assert evaluate_raw("100Ft").unit == "ft"


def test_validate_json_uses_json_type_names():
    assert [validate_json(value)["type"] for value in ["null", "true", "42", "3.14"]] == [
        "null",
        "boolean",
        "integer",
        "number",
    ]


def test_mcp_server_rejects_non_object_requests():
    server = McpServer()
    try:
        response = server.handle_request(42)
    finally:
        server.close()
    assert response["error"]["code"] == -32600


def test_mcp_ping_notification_has_no_response():
    server = McpServer()
    try:
        session = server.create_session(McpSessionState.READY)
        response = server.handle_request({"jsonrpc": "2.0", "method": "ping"}, session=session)
    finally:
        server.close()
    assert response is None


def test_cli_reports_lazy_handler_import_errors(capsys, monkeypatch):
    def broken_handler(_name):
        raise ImportError("broken exact module")

    monkeypatch.setattr("eggcalc.cli._get_handler", broken_handler)
    assert _cli_text_command("inspect hello") is _CommandStatus.ERROR
    assert "Unable to load text command" in capsys.readouterr().err


def test_cli_quiet_suppresses_expression_in_json(capsys):
    result, exit_code = run_cli("5+3", "json", quiet=True)
    assert result == 8
    assert exit_code == 0
    output = capsys.readouterr().out
    assert '"expression"' not in output


def test_repl_reports_unrecognized_input(capsys):
    with patch("builtins.input", side_effect=["hello world", EOFError]):
        assert _run_repl() == 0
    assert "Error:" in capsys.readouterr().err


def test_repl_logs_unexpected_handler_errors(caplog):
    with patch("builtins.input", side_effect=["1 + 1", EOFError]):
        with patch("eggcalc.cli.run_cli", side_effect=RuntimeError("boom")):
            with caplog.at_level("DEBUG"):
                assert _run_repl() == 0
    assert any("REPL command failed" in record.message for record in caplog.records)


def test_compatibility_ping_notification_has_no_response():
    assert handle_request({"jsonrpc": "2.0", "method": "ping"}) is None


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("min 5 10", 5),
        ("min 5.0 10.0", 5.0),
        ("min 5, 10", 5),
        ("mean of 1, 2, 3", 2.0),
        ("max of 5, 10", 10),
        ("sum of 1, 2, 3", 6),
    ],
)
def test_multi_argument_functions_accept_spaced_and_comma_arguments(expression, expected):
    assert evaluate_raw(expression) == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("log -1", complex(0, math.pi)),
        ("sqrt -1", 1j),
        ("sin -30", math.sin(-30)),
        ("log +1", 0.0),
    ],
)
def test_functions_accept_leading_signed_arguments(expression, expected):
    assert evaluate_raw(expression) == pytest.approx(expected)


def test_safe_pow_rejects_non_integral_exponents_beyond_absolute_tolerance():
    with pytest.raises(EvaluationError, match="non-integer"):
        _safe_pow(-4, 2.000000001)
    with pytest.raises(EvaluationError, match="non-integer"):
        _safe_pow(-4, 1000.000001)
