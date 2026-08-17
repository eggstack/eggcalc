"""Regression tests for actionable defects from bugs.md (August 2026)."""

import math

import pytest

from eggcalc.evaluator import _polar, _safe_pow
from eggcalc.exact.repo_audit import _classify_path
from eggcalc.exact.synthesis import _detect_special_sequences
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
