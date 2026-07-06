"""Tests for environment-variable-configurable MCP server limits."""

import importlib
import sys

import pytest

_ENV_PREFIX = "EGGCALC_MCP_MAX"

_ENV_KEYS = [
    "EGGCALC_MCP_MAX_REQUEST_BYTES",
    "EGGCALC_MCP_MAX_OUTPUT_BYTES",
    "EGGCALC_MCP_MAX_REQUESTS_PER_SECOND",
    "EGGCALC_MCP_MAX_TOOL_TIMEOUT_SECONDS",
    "EGGCALC_MCP_MAX_CANCELLED_REQUESTS",
    "EGGCALC_MCP_MAX_TOOL_WORKERS",
]


def _reload_server():
    """Re-import server.py so module-level constants pick up env var changes."""
    mod = sys.modules.get("eggcalc.mcp.server")
    if mod is not None:
        importlib.reload(mod)
    else:
        import eggcalc.mcp.server as mod
    return mod


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Ensure no EGGCALC_MCP_* env vars leak between tests."""
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    yield
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


class TestParseEnvInt:
    """Tests for _parse_env_int helper."""

    def test_default_when_not_set(self, monkeypatch):
        monkeypatch.delenv("EGGCALC_TEST_INT", raising=False)
        from eggcalc.mcp.server import _parse_env_int

        assert _parse_env_int("EGGCALC_TEST_INT", 42, 1, 100) == 42

    def test_default_when_empty(self, monkeypatch):
        monkeypatch.setenv("EGGCALC_TEST_INT", "")
        from eggcalc.mcp.server import _parse_env_int

        assert _parse_env_int("EGGCALC_TEST_INT", 42, 1, 100) == 42

    def test_valid_override(self, monkeypatch):
        monkeypatch.setenv("EGGCALC_TEST_INT", "50")
        from eggcalc.mcp.server import _parse_env_int

        assert _parse_env_int("EGGCALC_TEST_INT", 42, 1, 100) == 50

    def test_invalid_non_numeric(self, monkeypatch):
        monkeypatch.setenv("EGGCALC_TEST_INT", "not_a_number")
        from eggcalc.mcp.server import _parse_env_int

        assert _parse_env_int("EGGCALC_TEST_INT", 42, 1, 100) == 42

    def test_too_low_clamped_to_min(self, monkeypatch):
        monkeypatch.setenv("EGGCALC_TEST_INT", "0")
        from eggcalc.mcp.server import _parse_env_int

        assert _parse_env_int("EGGCALC_TEST_INT", 42, 5, 100) == 5

    def test_too_high_clamped_to_max(self, monkeypatch):
        monkeypatch.setenv("EGGCALC_TEST_INT", "999")
        from eggcalc.mcp.server import _parse_env_int

        assert _parse_env_int("EGGCALC_TEST_INT", 42, 1, 100) == 100

    def test_zero_value(self, monkeypatch):
        monkeypatch.setenv("EGGCALC_TEST_INT", "0")
        from eggcalc.mcp.server import _parse_env_int

        assert _parse_env_int("EGGCALC_TEST_INT", 42, 0, 100) == 0

    def test_float_string_returns_default(self, monkeypatch):
        monkeypatch.setenv("EGGCALC_TEST_INT", "3.14")
        from eggcalc.mcp.server import _parse_env_int

        assert _parse_env_int("EGGCALC_TEST_INT", 42, 1, 100) == 42


class TestParseEnvFloat:
    """Tests for _parse_env_float helper."""

    def test_default_when_not_set(self, monkeypatch):
        monkeypatch.delenv("EGGCALC_TEST_FLOAT", raising=False)
        from eggcalc.mcp.server import _parse_env_float

        assert _parse_env_float("EGGCALC_TEST_FLOAT", 2.5, 0.1, 100.0) == 2.5

    def test_default_when_empty(self, monkeypatch):
        monkeypatch.setenv("EGGCALC_TEST_FLOAT", "")
        from eggcalc.mcp.server import _parse_env_float

        assert _parse_env_float("EGGCALC_TEST_FLOAT", 2.5, 0.1, 100.0) == 2.5

    def test_valid_override(self, monkeypatch):
        monkeypatch.setenv("EGGCALC_TEST_FLOAT", "7.5")
        from eggcalc.mcp.server import _parse_env_float

        assert _parse_env_float("EGGCALC_TEST_FLOAT", 2.5, 0.1, 100.0) == 7.5

    def test_invalid_non_numeric(self, monkeypatch):
        monkeypatch.setenv("EGGCALC_TEST_FLOAT", "not_a_number")
        from eggcalc.mcp.server import _parse_env_float

        assert _parse_env_float("EGGCALC_TEST_FLOAT", 2.5, 0.1, 100.0) == 2.5

    def test_too_low_clamped_to_min(self, monkeypatch):
        monkeypatch.setenv("EGGCALC_TEST_FLOAT", "0.01")
        from eggcalc.mcp.server import _parse_env_float

        assert _parse_env_float("EGGCALC_TEST_FLOAT", 2.5, 0.5, 100.0) == 0.5

    def test_too_high_clamped_to_max(self, monkeypatch):
        monkeypatch.setenv("EGGCALC_TEST_FLOAT", "999.9")
        from eggcalc.mcp.server import _parse_env_float

        assert _parse_env_float("EGGCALC_TEST_FLOAT", 2.5, 0.1, 100.0) == 100.0

    def test_integer_string_accepted(self, monkeypatch):
        monkeypatch.setenv("EGGCALC_TEST_FLOAT", "10")
        from eggcalc.mcp.server import _parse_env_float

        assert _parse_env_float("EGGCALC_TEST_FLOAT", 2.5, 0.1, 100.0) == 10.0


class TestServerConstants:
    """Test that server constants use env-var-backed defaults."""

    def test_default_constants_match_original(self, monkeypatch):
        """With no env vars set, constants should equal original hardcoded values."""
        # Clean all relevant env vars
        for prefix in (
            "EGGCALC_MCP_MAX_REQUEST_BYTES",
            "EGGCALC_MCP_MAX_OUTPUT_BYTES",
            "EGGCALC_MCP_MAX_REQUESTS_PER_SECOND",
            "EGGCALC_MCP_MAX_TOOL_TIMEOUT_SECONDS",
            "EGGCALC_MCP_MAX_CANCELLED_REQUESTS",
            "EGGCALC_MCP_MAX_TOOL_WORKERS",
        ):
            monkeypatch.delenv(prefix, raising=False)

        mod = _reload_server()
        assert mod.MAX_REQUEST_BYTES == 1_000_000
        assert mod.MAX_OUTPUT_BYTES == 1_000_000
        assert mod.MAX_REQUESTS_PER_SECOND == 10
        assert mod.MAX_TOOL_TIMEOUT_SECONDS == 30
        assert mod.MAX_CANCELLED_REQUESTS == 10_000
        assert mod._MAX_TOOL_WORKERS == 16

    def test_override_max_request_bytes(self, monkeypatch):
        monkeypatch.setenv("EGGCALC_MCP_MAX_REQUEST_BYTES", "5000000")
        mod = _reload_server()
        assert mod.MAX_REQUEST_BYTES == 5_000_000

    def test_override_max_output_bytes(self, monkeypatch):
        monkeypatch.setenv("EGGCALC_MCP_MAX_OUTPUT_BYTES", "2000000")
        mod = _reload_server()
        assert mod.MAX_OUTPUT_BYTES == 2_000_000

    def test_override_requests_per_second(self, monkeypatch):
        monkeypatch.setenv("EGGCALC_MCP_MAX_REQUESTS_PER_SECOND", "20.5")
        mod = _reload_server()
        assert mod.MAX_REQUESTS_PER_SECOND == 20.5

    def test_override_tool_timeout(self, monkeypatch):
        monkeypatch.setenv("EGGCALC_MCP_MAX_TOOL_TIMEOUT_SECONDS", "60")
        mod = _reload_server()
        assert mod.MAX_TOOL_TIMEOUT_SECONDS == 60

    def test_override_cancelled_requests(self, monkeypatch):
        monkeypatch.setenv("EGGCALC_MCP_MAX_CANCELLED_REQUESTS", "50000")
        mod = _reload_server()
        assert mod.MAX_CANCELLED_REQUESTS == 50_000

    def test_override_tool_workers(self, monkeypatch):
        monkeypatch.setenv("EGGCALC_MCP_MAX_TOOL_WORKERS", "32")
        mod = _reload_server()
        assert mod._MAX_TOOL_WORKERS == 32

    def test_invalid_env_var_uses_default(self, monkeypatch):
        monkeypatch.setenv("EGGCALC_MCP_MAX_REQUEST_BYTES", "garbage")
        mod = _reload_server()
        assert mod.MAX_REQUEST_BYTES == 1_000_000

    def test_clamped_too_low(self, monkeypatch):
        monkeypatch.setenv("EGGCALC_MCP_MAX_TOOL_TIMEOUT_SECONDS", "0")
        mod = _reload_server()
        assert mod.MAX_TOOL_TIMEOUT_SECONDS == 1  # min_val

    def test_clamped_too_high(self, monkeypatch):
        monkeypatch.setenv("EGGCALC_MCP_MAX_TOOL_WORKERS", "999")
        mod = _reload_server()
        assert mod._MAX_TOOL_WORKERS == 128  # max_val

    def test_negative_value_clamped_to_min(self, monkeypatch):
        monkeypatch.setenv("EGGCALC_MCP_MAX_CANCELLED_REQUESTS", "-5")
        mod = _reload_server()
        assert mod.MAX_CANCELLED_REQUESTS == 100  # min_val
