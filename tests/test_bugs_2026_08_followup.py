"""Regression tests for the 2026-08-24 bugs.md audit follow-up fixes.

Covers: quantity exponentiation semantics (§2.1), UnitValue.__format__
contract (§2.2), convert_to temperature rounding (§2.3), stranded leading
operators after phrase stripping (§2.4), grapheme ZWJ base guard (§2.5),
unified JSON-RPC id validation (§2.6), lazy handler AttributeError leak
(§2.7), REPL crash-proofing (§2.8), dead ToolExecutor orphan API (§3.1),
ConfigSnapshot deep immutability (§3.2), duplicate regex removal (§3.3),
and the build rename occurrence guard (§3.4).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from types import MappingProxyType

import pytest

from eggcalc.evaluator import EvaluationError, evaluate_raw
from eggcalc.normalize import NORMALIZE, PATTERNS, normalize_expression


# ---------------------------------------------------------------------------
# §2.1: quantity exponentiation binds power to the unit for every exponent
# ---------------------------------------------------------------------------
class TestQuantityExponentiationConsistency:
    @pytest.mark.parametrize(
        "expr,expected",
        [
            ("5m**2", "5 m**2"),
            ("5m**3", "5 m**3"),
            ("5m**4", "5 m**4"),
            ("5m**6", "5 m**6"),
            ("5m**10", "5 m**10"),
            ("5m**-2", "5 1/m**2"),
            ("5 m** -2", "5 1/m**2"),
            ("5m**+2", "5 m**2"),
            ("5m**2.0", "5 m**2"),
        ],
    )
    def test_power_binds_unit_regardless_of_spacing(self, expr, expected):
        assert str(evaluate_raw(expr)) == expected

    def test_caret_form_matches_double_star(self):
        assert str(evaluate_raw("5m^4")) == str(evaluate_raw("5m**4"))

    def test_explicit_parens_still_power_the_quantity(self):
        r = evaluate_raw("(5m)**2")
        assert r.value == 25
        assert r.unit == "m**2"

    def test_plain_numbers_unaffected(self):
        assert evaluate_raw("2**10") == 1024

    def test_affine_temperature_power_rejected(self):
        with pytest.raises(EvaluationError):
            evaluate_raw("5c**2")

    def test_compound_unit_denominator_power(self):
        r = evaluate_raw("5km/h**2")
        assert r.value == 5
        assert r.unit == "km/h**2"


# ---------------------------------------------------------------------------
# §2.2: __format__ empty spec agrees with __str__/__repr__
# ---------------------------------------------------------------------------
class TestUnitValueFormatContract:
    def test_empty_spec_matches_str(self):
        r = evaluate_raw("100F - 100C")
        assert f"{r}" == str(r)

    def test_conversion_format_matches_str(self):
        r = evaluate_raw("100C in F")
        assert f"{r}" == str(r) == "212 F"

    def test_nonempty_spec_keeps_numeric_formatting(self):
        from eggcalc.units import UnitValue

        uv = UnitValue(3.14159, "m")
        assert f"{uv:.2f}" == "3.14 m"
        assert f"{UnitValue(7)}" == "7"


# ---------------------------------------------------------------------------
# §2.3: convert_to snaps near-integer temperature results
# ---------------------------------------------------------------------------
class TestConvertToTemperatureRounding:
    def test_convert_to_fahrenheit_exact(self):
        from eggcalc.units import UnitValue

        converted = UnitValue(100, "C").convert_to("F")
        assert converted.value == 212.0

    def test_convert_to_celsius_exact(self):
        from eggcalc.units import UnitValue

        converted = UnitValue(32, "F").convert_to("C")
        assert converted.value == 0.0

    def test_agrees_with_convert_temperature_helper(self):
        from eggcalc.units import UnitValue, convert_temperature

        via_value = UnitValue(37, "C").convert_to("F").value
        via_helper = convert_temperature(37, "celsius", "fahrenheit")
        assert via_value == via_helper


# ---------------------------------------------------------------------------
# §2.4: article stripping cannot strand a leading operator
# ---------------------------------------------------------------------------
class TestArticleStripping:
    def test_article_of_phrase_evaluates(self):
        assert evaluate_raw("what is a of five") == 5

    def test_bare_article_of_phrase_evaluates(self):
        assert evaluate_raw("a of five") == 5

    def test_leading_expression_after_strip(self):
        assert evaluate_raw("what is a of 5 plus 3") == 8

    def test_unary_signs_survive(self):
        assert evaluate_raw("what is -5") == -5
        assert evaluate_raw("what is +5") == 5


# ---------------------------------------------------------------------------
# §2.5: grapheme segmentation requires a pictographic ZWJ base
# ---------------------------------------------------------------------------
class TestGraphemeZwjBaseGuard:
    def test_zwj_without_pictographic_base_counts_separately(self):
        from eggcalc.exact.primitives import count_graphemes

        assert count_graphemes("a\u200d\U0001f525") == 3

    def test_real_emoji_sequences_still_one_cluster(self):
        from eggcalc.exact.primitives import count_graphemes

        family = "\U0001f468\u200d\U0001f469\u200d\U0001f467\u200d\U0001f466"
        couple = "\U0001f468\u200d\U0001f469"
        flag = "\U0001f3f3\ufe0f\u200d\U0001f308"
        assert count_graphemes(family) == 1
        assert count_graphemes(couple) == 1
        assert count_graphemes(flag) == 1

    def test_unicode_13_plus_pictographic_blocks_recognized(self):
        from eggcalc.exact.primitives import _is_extended_pictographic, count_graphemes

        # U+1FAF6 HAND WITH INDEX FINGER AND THUMB CROSSED (Unicode 14)
        assert _is_extended_pictographic("\U0001faf6")
        # U+1FABF GOOSE (Unicode 15)
        assert _is_extended_pictographic("\U0001fabf")
        # ZWJ sequence over a Unicode 14 base stays one cluster
        assert count_graphemes("\U0001faf6\u200d\U0001f525") == 1


# ---------------------------------------------------------------------------
# §2.6: one JSON-RPC id validator shared by both dispatch paths
# ---------------------------------------------------------------------------
class TestJsonRpcIdValidation:
    @pytest.fixture()
    def ready_session(self):
        from eggcalc.mcp.server import McpServer

        server = McpServer()
        session = server.create_session()
        server.handle_request(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            session=session,
        )
        server.handle_request(
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            session=session,
        )
        yield server, session
        server.close()

    def test_session_path_rejects_bool_id(self, ready_session):
        server, session = ready_session
        response = server.handle_request({"jsonrpc": "2.0", "id": True, "method": "ping"}, session)
        assert response is not None and response["error"]["code"] == -32600
        assert response["id"] is None

    def test_session_path_accepts_float_id(self, ready_session):
        server, session = ready_session
        response = server.handle_request({"jsonrpc": "2.0", "id": 3.5, "method": "ping"}, session)
        assert response == {"jsonrpc": "2.0", "id": 3.5, "result": {}}

    def test_session_path_rejects_object_id(self, ready_session):
        server, session = ready_session
        response = server.handle_request(
            {"jsonrpc": "2.0", "id": {"x": 1}, "method": "ping"}, session
        )
        assert response is not None and response["error"]["code"] == -32600

    def test_compat_path_rejects_bool_and_list_ids(self):
        from eggcalc.mcp.server import handle_request

        # Id validation happens before session routing, so these return
        # early without reaching the deprecated compat path.
        response = handle_request({"jsonrpc": "2.0", "id": True, "method": "tools/list"})
        assert response is not None and response["error"]["code"] == -32600
        response = handle_request({"jsonrpc": "2.0", "id": [1], "method": "tools/list"})
        assert response is not None and response["error"]["code"] == -32600

    def test_compat_path_accepts_float_id(self):
        from eggcalc.mcp.server import handle_request

        with pytest.warns(DeprecationWarning):
            response = handle_request({"jsonrpc": "2.0", "id": 2.5, "method": "tools/list"})
        assert response is not None and "result" in response


# ---------------------------------------------------------------------------
# §2.7: lazy text-command loader converts AttributeError to ImportError
# ---------------------------------------------------------------------------
class TestLazyHandlerErrorMapping:
    def test_missing_symbol_raises_import_error(self, monkeypatch):
        import eggcalc.cli as cli

        cli._reset_handler_cache()
        monkeypatch.setattr(
            cli,
            "COMMANDS",
            (
                {
                    "handler": "no_such_handler_xyz",
                    "module": "json",
                    "symbol": "definitely_absent",
                },
            ),
        )
        try:
            with pytest.raises(ImportError):
                cli._get_handler("no_such_handler_xyz")
        finally:
            cli._reset_handler_cache()

    def test_dispatch_reports_friendly_error_for_bad_symbol(self, monkeypatch, capsys):
        import eggcalc.cli as cli

        cli._reset_handler_cache()
        spec = {
            "name": "broken",
            "aliases": (),
            "description": "broken command",
            "usage": "calc broken <arg>",
            "min_args": 2,
            "category": "text",
            "json_output": False,
            "handler": "no_such_handler_xyz",
            "module": "json",
            "symbol": "definitely_absent",
        }
        monkeypatch.setattr(cli, "COMMANDS", (spec,))
        monkeypatch.setattr(cli, "_COMMAND_NAME_TO_SPEC", {"broken": spec})
        status = cli._cli_text_command("broken extra", json_output=False, argv=None)
        assert status == cli._CommandStatus.ERROR
        assert "Unable to load text command" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# §2.8: REPL survives stray BaseExceptions from evaluation
# ---------------------------------------------------------------------------
class TestReplCrashProofing:
    def _run_repl_script(self, injected: str) -> subprocess.CompletedProcess:
        script = (
            "import eggcalc.cli as cli\n"
            "real_run_cli = cli.run_cli\n"
            "calls = {'n': 0}\n"
            "def fake(expression, output_format='plain', quiet=False):\n"
            "    calls['n'] += 1\n"
            f"    {injected}\n"
            "    return real_run_cli(expression, output_format, quiet)\n"
            "cli.run_cli = fake\n"
            "cli._run_repl()\n"
            "print('SURVIVED', calls['n'])\n"
        )
        return subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=60,
            input="1+1\n2+2\nquit\n",
        )

    @pytest.mark.parametrize("exc", ["raise SystemExit(3)", "raise RuntimeError('boom')"])
    def test_repl_continues_after_injected_exception(self, exc):
        result = self._run_repl_script(exc)
        assert result.returncode == 0, result.stderr
        assert "SURVIVED 2" in result.stdout


# ---------------------------------------------------------------------------
# §3.1: ToolExecutor no longer carries write-only orphan tracking
# ---------------------------------------------------------------------------
class TestDeadOrphanApiRemoved:
    def test_executor_has_no_orphaned_state(self):
        from eggcalc.mcp.server import McpServerConfig, ToolExecutor, ToolRegistry

        executor = ToolExecutor(McpServerConfig(), ToolRegistry())
        assert not hasattr(executor, "_orphaned")
        assert not hasattr(executor, "_cleanup_orphans")
        assert not hasattr(executor, "orphan_count")
        executor.close()

    def test_diagnostic_reports_real_orphan_tracking(self):
        from eggcalc.mcp import server as mcp_server
        from eggcalc.mcp.server import McpServer

        server = McpServer()
        diag = server.diagnostic()
        assert diag["orphan_count"] == len(mcp_server._orphaned_processes)
        server.close()


# ---------------------------------------------------------------------------
# §3.2: ConfigSnapshot is deeply immutable but serializable
# ---------------------------------------------------------------------------
class TestConfigSnapshotDeepImmutability:
    def test_nested_dict_frozen(self):
        from eggcalc.mcp.server import ConfigSnapshot

        snap = ConfigSnapshot(constants={"group": {"inner": 1}})
        with pytest.raises(TypeError):
            snap.constants["group"]["inner"] = 2  # type: ignore[index]

    def test_nested_list_frozen(self):
        from eggcalc.mcp.server import ConfigSnapshot

        snap = ConfigSnapshot(constants={"a": [1, 2]})
        frozen = snap.constants["a"]
        with pytest.raises((AttributeError, TypeError)):
            frozen.append(3)  # type: ignore[union-attr]

    def test_constructor_input_detached(self):
        from eggcalc.mcp.server import ConfigSnapshot

        source: dict = {"a": {"b": [1]}}
        snap = ConfigSnapshot(constants=source)
        source["a"]["b"].append(2)
        source["a"]["c"] = 3
        assert snap.constants["a"]["b"] == (1,)
        assert "c" not in snap.constants["a"]

    def test_field_mappings_are_proxy_type(self):
        from eggcalc.mcp.server import ConfigSnapshot

        snap = ConfigSnapshot(constants={"x": {"y": 1}})
        assert isinstance(snap.constants, MappingProxyType)
        assert isinstance(snap.constants["x"], MappingProxyType)

    def test_to_dict_is_json_serializable(self):
        from eggcalc.mcp.server import ConfigSnapshot

        d = ConfigSnapshot(constants={"a": [1, {"b": 2}]}).to_dict()
        assert json.loads(json.dumps(d)) == {
            "generation": 0,
            "constants": {"a": [1, {"b": 2}]},
            "functions": {},
            "units": {},
            "policy": "default",
        }


# ---------------------------------------------------------------------------
# §3.3: operator tokenization uses a single compiled pattern
# ---------------------------------------------------------------------------
class TestSingleOperatorRegex:
    def test_split_function_defines_pattern_once(self):
        import inspect

        import eggcalc.normalize as normalize

        source = inspect.getsource(normalize)
        assert len(re.findall(r'operator_split_re = re\.compile\(', source)) == 1
        assert "boundary_operator_re" not in source

    def test_boundary_tokenization_still_works(self):
        joined, code = normalize_expression("sqrt +(4*5)", NORMALIZE, PATTERNS)
        assert code == 0


# ---------------------------------------------------------------------------
# §3.4: build rename step fails loudly on ambiguous definitions
# ---------------------------------------------------------------------------
class TestBuildRenameGuard:
    def test_current_tools_module_has_single_definitions(self):
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        tools_path = os.path.join(repo_root, "eggcalc", "mcp", "tools.py")
        with open(tools_path, encoding="utf-8") as fh:
            code = fh.read()

        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)
        try:
            import build_single

            conflict_functions = build_single.MCP_CONFLICT_FUNCTIONS
        finally:
            if repo_root in sys.path:
                sys.path.remove(repo_root)

        for fn_name in conflict_functions:
            assert code.count(f"def {fn_name}(") == 1, fn_name
