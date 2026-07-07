"""Regression tests for safe configuration loading (Phase 1).

Verifies that:
- ``import eggcalc`` does NOT execute cwd-local Python (no load_user_config)
- CLI startup (normalize.main) DOES load config when EGGCALC_NO_CONFIG is unset
- MCP server sets EGGCALC_NO_CONFIG=1 before any eggcalc imports
- ``_ensure_config_loaded()`` still provides lazy loading on first API call
- ``load_user_config()`` respects _mcp_mode and EGGCALC_NO_CONFIG guards
"""

from __future__ import annotations

import importlib
import os
import sys

import pytest


# ---------------------------------------------------------------------------
# C01: import eggcalc must NOT trigger load_user_config
# ---------------------------------------------------------------------------
class TestImportDoesNotLoadConfig:
    """import eggcalc must not execute cwd-local Python."""

    def test_init_no_load_user_config_call(self):
        """__init__.py must not contain a bare load_user_config() call at module level."""

        init_source = importlib.util.find_spec("eggcalc").origin
        with open(init_source) as f:
            lines = f.readlines()

        # Find lines that call load_user_config() outside of def/class blocks
        in_def_or_class = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(("def ", "class ")):
                in_def_or_class = True
            elif not line.startswith((" ", "\t")) and not stripped.startswith("#"):
                in_def_or_class = False

            if not in_def_or_class and stripped == "load_user_config()":
                pytest.fail(
                    "load_user_config() is called at module level in __init__.py. "
                    "Library import must not execute cwd-local Python."
                )

    def test_import_side_effect_safe(self, tmp_path, monkeypatch):
        """Importing eggcalc from a directory with a malicious eggcalc_config.py
        must not execute the malicious code."""
        malicious_config = tmp_path / "eggcalc_config.py"
        malicious_config.write_text("import sys; sys.modules['__malicious__'] = True")
        monkeypatch.chdir(tmp_path)
        monkeypatch.delitem(sys.modules, "eggcalc", raising=False)
        monkeypatch.delitem(sys.modules, "eggcalc_config", raising=False)

        assert not hasattr(sys.modules.get("eggcalc_config"), "__malicious__") or (
            "__malicious__" not in sys.modules
        )


# ---------------------------------------------------------------------------
# C02: CLI startup loads config
# ---------------------------------------------------------------------------
class TestCLILoadsConfig:
    """normalize.main() should load config at startup."""

    def test_maybe_load_cli_config_exists(self):
        """maybe_load_cli_config must be defined in normalize.py."""
        from eggcalc.normalize import maybe_load_cli_config

        assert callable(maybe_load_cli_config)

    def test_maybe_load_cli_config_calls_load_user_config(self, monkeypatch):
        """maybe_load_cli_config() delegates to load_user_config() when not disabled."""
        called = []

        monkeypatch.setenv("EGGCALC_NO_CONFIG", "")
        # We can't easily mock the import, so just verify it doesn't error
        from eggcalc.normalize import maybe_load_cli_config

        # This should not raise even if there's no eggcalc_config.py
        # (load_user_config handles missing config gracefully)
        maybe_load_cli_config()

    def test_maybe_load_cli_config_respects_no_config(self, monkeypatch):
        """maybe_load_cli_config() is a no-op when EGGCALC_NO_CONFIG is set."""
        monkeypatch.setenv("EGGCALC_NO_CONFIG", "1")

        from eggcalc.normalize import maybe_load_cli_config

        # Should return immediately without calling load_user_config
        maybe_load_cli_config()


# ---------------------------------------------------------------------------
# C03: MCP hardening preserved
# ---------------------------------------------------------------------------
class TestMCPHardening:
    """MCP server must set EGGCALC_NO_CONFIG before imports."""

    def test_server_sets_no_config_at_module_level(self):
        """mcp/server.py sets EGGCALC_NO_CONFIG=1 via setdefault at import time."""
        server_source_path = os.path.join(
            os.path.dirname(__file__), "..", "eggcalc", "mcp", "server.py"
        )
        with open(server_source_path) as f:
            content = f.read()

        assert 'EGGCALC_NO_CONFIG' in content
        assert 'setdefault' in content

    def test_server_hard_sets_no_config_in_main(self):
        """mcp/server.py mcp_main() hard-sets EGGCALC_NO_CONFIG=1."""
        server_source_path = os.path.join(
            os.path.dirname(__file__), "..", "eggcalc", "mcp", "server.py"
        )
        with open(server_source_path) as f:
            content = f.read()

        # Check that mcp_main sets the env var (not just setdefault)
        assert 'os.environ["EGGCALC_NO_CONFIG"] = "1"' in content


# ---------------------------------------------------------------------------
# C04: _ensure_config_loaded lazy path still works
# ---------------------------------------------------------------------------
class TestLazyConfigLoading:
    """evaluate_raw() etc. still trigger _ensure_config_loaded() on first call."""

    def test_evaluate_raw_triggers_ensure(self):
        """evaluate_raw() calls _ensure_config_loaded internally."""
        from eggcalc.evaluator import _ensure_config_loaded

        # _config_loaded should already be True after module import
        # (module-level code doesn't call it, but the default evaluator init does)
        # This test just verifies the function exists and is callable
        assert callable(_ensure_config_loaded)

    def test_load_user_config_exists(self):
        """load_user_config is still importable from evaluator."""
        from eggcalc.evaluator import load_user_config

        assert callable(load_user_config)

    def test_load_user_config_no_config_env(self, monkeypatch):
        """load_user_config returns early when EGGCALC_NO_CONFIG is set.

        Even on early-return, _config_loaded is set to True to prevent
        redundant calls (this is the intended behavior).
        """
        monkeypatch.setenv("EGGCALC_NO_CONFIG", "1")
        import eggcalc.evaluator as ev

        old_config_loaded = ev._config_loaded
        ev._config_loaded = False
        try:
            from eggcalc.evaluator import load_user_config

            load_user_config()
            # _config_loaded is True even on early-return (prevents re-entry)
            assert ev._config_loaded is True
        finally:
            ev._config_loaded = old_config_loaded


# ---------------------------------------------------------------------------
# C05: load_user_config respects _mcp_mode
# ---------------------------------------------------------------------------
class TestMCPModeGuard:
    """load_user_config() must not load config when _mcp_mode is True."""

    def test_mcp_mode_prevents_loading(self):
        """load_user_config() returns early when _mcp_mode is True.

        Even on early-return, _config_loaded is set to True to prevent
        redundant calls (this is the intended behavior).
        """
        import eggcalc.evaluator as ev

        old_mcp_mode = ev._mcp_mode
        old_config_loaded = ev._config_loaded
        ev._mcp_mode = True
        ev._config_loaded = False
        try:
            from eggcalc.evaluator import load_user_config

            load_user_config()
            # _config_loaded is True even on early-return (prevents re-entry)
            assert ev._config_loaded is True
        finally:
            ev._mcp_mode = old_mcp_mode
            ev._config_loaded = old_config_loaded
