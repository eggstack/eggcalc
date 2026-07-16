"""Shared pytest fixtures for eggcalc tests."""

import pytest

from eggcalc import UnitValue, evaluate
from eggcalc.normalize import NORMALIZE, PATTERNS


@pytest.fixture(autouse=True, scope="module")
def _restore_evaluator_defaults():
    """Save and restore the default evaluator state after each test module.

    handle_request() in mcp/server.py permanently sets _mcp_mode=True and
    configure_default_evaluator(allow_random=False, allow_side_effects=False)
    on first call. This fixture saves the original state before each module
    runs and restores it after, so that non-MCP modules (e.g. test_clicalc)
    are not affected by MCP state changes.
    """
    import eggcalc.mcp.server as _server_mod
    from eggcalc import evaluator as _evaluator
    from eggcalc import get_default_evaluator

    ev = get_default_evaluator()
    orig_mcp_mode = _evaluator._mcp_mode
    orig_allow_random = ev._allow_random
    orig_allow_side_effects = ev._allow_side_effects
    orig_mcp_defaults_configured = _server_mod._mcp_defaults_configured
    orig_default_session = _server_mod._default_session
    yield
    _evaluator._mcp_mode = orig_mcp_mode
    ev._allow_random = orig_allow_random
    ev._allow_side_effects = orig_allow_side_effects
    _server_mod._mcp_defaults_configured = orig_mcp_defaults_configured
    _server_mod._default_session = orig_default_session


@pytest.fixture
def eval_result():
    """Optional helper: wraps evaluate result, extracting value from UnitValue if needed.
    Not currently used by any tests — available for convenience if needed.
    """

    def _eval_result(expr):
        result = evaluate(expr)
        if isinstance(result, UnitValue):
            return result.value
        return result

    return _eval_result


@pytest.fixture
def evaluate_raw():
    """Direct access to evaluate_raw function."""
    from eggcalc import evaluate_raw

    return evaluate_raw


@pytest.fixture
def normalize_config():
    """Access to normalize config and patterns."""
    return (NORMALIZE, PATTERNS)


@pytest.fixture
def extract_value():
    """Extract the numeric value from a result, intentionally hiding the UnitValue wrapper.

    Use this when you only care about the numeric value and want convenience
    over verifying the UnitValue wrapper type.
    """

    def _extract_value(result):
        if isinstance(result, UnitValue):
            return result.value
        return result

    return _extract_value


@pytest.fixture
def approx():
    """Optional helper: pytest.approx wrapper for floating point comparisons.
    Most tests use pytest.approx directly — available for convenience if needed.
    """
    return lambda x, y, rel_tol=1e-10: abs(x - y) < rel_tol
