"""Regression tests for actionable defects from bugs.md (August 2026)."""

import math
import unicodedata

import pytest

from eggcalc import evaluate
from eggcalc.evaluator import _polar, _safe_pow
from eggcalc.exact.primitives import detect_newline_style
from eggcalc.exact.repo_audit import _classify_path
from eggcalc.exact.shell import shell_split
from eggcalc.exact.synthesis import _detect_special_sequences, text_window
from eggcalc.exact.validate import regex_safety_check
from eggcalc.mcp.server import McpSession, McpSessionState


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
