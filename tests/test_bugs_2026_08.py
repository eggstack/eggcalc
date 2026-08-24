"""Regression tests for actionable defects from bugs.md (August 2026)."""

import math
import unicodedata
from unittest.mock import patch

import pytest

from eggcalc import EvaluationError, evaluate, evaluate_raw
from eggcalc.cli import _cli_text_command, _CommandStatus, _run_repl, run_cli
from eggcalc.evaluator import _polar, _safe_pow
from eggcalc.exact.primitives import detect_newline_style
from eggcalc.exact.repo_audit import _classify_path
from eggcalc.exact.shell import shell_split
from eggcalc.exact.synthesis import _detect_special_sequences, text_window
from eggcalc.exact.validate import _check_pattern_complexity, regex_safety_check, validate_json
from eggcalc.mcp.server import McpServer, McpSession, McpSessionState, handle_request
from eggcalc.normalize import NORMALIZE, PATTERNS, normalize_text
from eggcalc.units import UnitValue, convert_temperature


def test_safe_pow_accepts_integral_float_exponents():
    result = _safe_pow(5, 500.0)
    assert isinstance(result, int)
    assert result == 5**500


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
        result = evaluate("1 << 30001")
        assert isinstance(result, int)
        assert result.bit_length() == 30002


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


def test_temperature_below_absolute_zero_is_rejected():
    with pytest.raises(ValueError, match="absolute zero"):
        UnitValue(-1, "K").convert_to("C")
    with pytest.raises(ValueError, match="absolute zero"):
        convert_temperature(-1, "K", "C")


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


def test_compatibility_ping_notification_has_no_response():
    assert handle_request({"jsonrpc": "2.0", "method": "ping"}) is None
