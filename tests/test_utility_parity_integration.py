"""Integration tests for the six deterministic utility tools (Plan 032).

Covers the cross-cutting work that turns the direct exact implementations
(Plans 030-031) into supported product surfaces:

- lazy exact exports and import-cost regression (Workstream A);
- MCP schemas, metadata, handlers, and registry agreement (Workstreams B-E);
- representative MCP success/error envelopes over a shared static corpus
  (Workstream G);
- package versus generated-single-file parity (Workstream H).

The shared corpus lives in ``tests/fixtures/utility_parity_cases.json``;
vectors are transcribed from reviewed eggsact behavior (upstream feature
commit ``879570e``, corrective commit ``ae2be1d``, cron semantics
correction ``330e7a6``). No test shells out to eggsact.
"""

from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tempfile

import pytest

from eggcalc.mcp import schemas as _schemas
from eggcalc.mcp import server as _server
from eggcalc.mcp import tools as _tools

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
PARITY_CASES = json.loads((FIXTURES / "utility_parity_cases.json").read_text())["cases"]
BUILD_SCRIPT = os.path.join(os.path.dirname(__file__), "..", "build_single.py")

SIX_TOOLS = (
    "ip_inspect",
    "cidr_inspect",
    "codec_convert",
    "radix_convert",
    "datetime_convert",
    "cron_inspect",
)

HANDLERS = {
    "ip_inspect": _tools.ip_inspect_mcp,
    "cidr_inspect": _tools.cidr_inspect_mcp,
    "codec_convert": _tools.codec_convert_mcp,
    "radix_convert": _tools.radix_convert_mcp,
    "datetime_convert": _tools.datetime_convert_mcp,
    "cron_inspect": _tools.cron_inspect_mcp,
}


def _assert_subset(actual: dict, subset: dict) -> None:
    for key, expected in subset.items():
        assert key in actual, f"Missing key {key!r} in {actual!r}"
        assert (
            actual[key] == expected
        ), f"Mismatch for {key!r}: expected {expected!r}, got {actual[key]!r}"


def _run_import_check(code: str, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


class TestUtilityRegistry:
    """Schema/handler/metadata agreement for the six utility tools."""

    def test_schemas_exist(self):
        for name in SIX_TOOLS:
            assert name in _schemas.TOOL_SCHEMAS, f"Missing schema for {name!r}"

    def test_handlers_exist_and_callable(self):
        for name in SIX_TOOLS:
            assert name in _server.TOOL_HANDLERS, f"Missing handler for {name!r}"
            assert callable(_server.TOOL_HANDLERS[name])

    def test_schema_handler_sets_agree(self):
        for name in SIX_TOOLS:
            assert name in _schemas.TOOL_SCHEMAS
            assert name in _server.TOOL_HANDLERS
            assert name in _schemas.TOOL_METADATA

    def test_tier_two_full_only_contextual(self):
        for name in SIX_TOOLS:
            schema = _schemas.TOOL_SCHEMAS[name]
            meta = _schemas.TOOL_METADATA[name]
            assert schema["tier"] == 2, f"{name}: schema tier {schema['tier']!r} != 2"
            assert meta["tier"] == 2, f"{name}: metadata tier {meta['tier']!r} != 2"
            assert meta["profiles"] == ["full"], f"{name}: profiles {meta['profiles']!r}"
            assert meta["llm_exposure"] == "contextual", f"{name}: exposure"
            assert meta["aliases"] == [], f"{name}: unexpected aliases"
            assert name in _schemas.TOOL_PROFILES["full"]

    def test_categories(self):
        assert _schemas.TOOL_METADATA["ip_inspect"]["category"] == "network"
        assert _schemas.TOOL_METADATA["cidr_inspect"]["category"] == "network"
        assert _schemas.TOOL_METADATA["codec_convert"]["category"] == "encoding"
        assert _schemas.TOOL_METADATA["radix_convert"]["category"] == "encoding"
        assert _schemas.TOOL_METADATA["datetime_convert"]["category"] == "temporal"
        assert _schemas.TOOL_METADATA["cron_inspect"]["category"] == "temporal"

    def test_cost_classification(self):
        for name in (
            "ip_inspect",
            "cidr_inspect",
            "codec_convert",
            "radix_convert",
            "datetime_convert",
        ):
            assert _schemas.TOOL_METADATA[name]["cost"] == "cheap", name
        assert _schemas.TOOL_METADATA["cron_inspect"]["cost"] == "moderate"

    def test_new_tools_absent_from_restricted_profiles(self):
        for profile in (
            "default",
            "human_math",
            "codegg_core_min",
            "codegg_core",
            "codegg_preflight",
            "codegg_patch",
            "codegg_config",
            "codegg_unicode_security",
            "codegg_shell",
            "codegg_repo_audit",
        ):
            members = set(_schemas.TOOL_PROFILES.get(profile, []))
            overlap = members.intersection(SIX_TOOLS)
            assert not overlap, f"Profile {profile!r} unexpectedly contains {sorted(overlap)}"

    def test_required_schema_params_match_handlers(self):
        import inspect

        for name in SIX_TOOLS:
            handler = _server.TOOL_HANDLERS[name]
            sig = inspect.signature(handler)
            has_kwargs = any(
                p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
            )
            required = _schemas.TOOL_SCHEMAS[name].get("inputSchema", {}).get("required", [])
            for prop in required:
                assert prop in sig.parameters or has_kwargs, (
                    f"Tool {name!r} requires {prop!r} "
                    f"but handler params are {sorted(sig.parameters)}"
                )


class TestUtilityImportBoundaries:
    """Import-cost regression: the three modules stay lazy."""

    def test_import_eggcalc_loads_no_utility_modules(self):
        code = (
            "import sys\n"
            "import eggcalc\n"
            "loaded = [m for m in sys.modules "
            "if m in ('eggcalc.exact.network', 'eggcalc.exact.encoding', "
            "'eggcalc.exact.temporal')]\n"
            "assert not loaded, f'Utility modules loaded: {loaded}'\n"
        )
        result = _run_import_check(code)
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"

    def test_import_exact_namespace_loads_no_utility_modules(self):
        code = (
            "import sys\n"
            "import eggcalc.exact\n"
            "loaded = [m for m in sys.modules "
            "if m in ('eggcalc.exact.network', 'eggcalc.exact.encoding', "
            "'eggcalc.exact.temporal')]\n"
            "assert not loaded, f'Utility modules loaded: {loaded}'\n"
        )
        result = _run_import_check(code)
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"

    def test_calling_one_function_loads_only_its_module(self):
        code = (
            "import sys\n"
            "import eggcalc.exact\n"
            "result = eggcalc.exact.ip_inspect('192.0.2.1')\n"
            "assert result['family'] == 'ipv4'\n"
            "assert 'eggcalc.exact.network' in sys.modules\n"
            "assert 'eggcalc.exact.encoding' not in sys.modules, "
            "'encoding loaded by ip_inspect'\n"
            "assert 'eggcalc.exact.temporal' not in sys.modules, "
            "'temporal loaded by ip_inspect'\n"
        )
        result = _run_import_check(code)
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"

    def test_import_cli_loads_no_utility_modules(self):
        code = (
            "import sys\n"
            "import eggcalc.cli\n"
            "loaded = [m for m in sys.modules "
            "if m in ('eggcalc.exact.network', 'eggcalc.exact.encoding', "
            "'eggcalc.exact.temporal')]\n"
            "assert not loaded, f'Utility modules loaded: {loaded}'\n"
        )
        result = _run_import_check(code)
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"


class TestUtilityMcpEnvelopes:
    """Representative MCP success/error envelopes over the shared corpus."""

    @pytest.mark.parametrize("case", PARITY_CASES, ids=lambda c: f"{c['tool']}-{c['arguments']}")
    def test_package_handler_envelope(self, case):
        handler = HANDLERS[case["tool"]]
        response = handler(**case["arguments"])
        if case["expect_ok"]:
            assert response.get("ok") is True, response
            assert response.get("tool") == case["tool"], response
            _assert_subset(response["result"], case["expect_subset"])
        else:
            assert response.get("ok") is False, response
            assert response.get("tool") == case["tool"], response
            assert response.get("error_type") == case["expect_error_type"], response

    def test_cron_runs_strictly_after_reference(self):
        response = _tools.cron_inspect_mcp("0 0 */1 * MON", "2026-09-03T00:00:00Z", 3)
        assert response["ok"] is True, response
        runs = response["result"]["next_runs"]
        assert len(runs) == 3
        assert all(run > "2026-09-03T00:00:00Z" for run in runs)
        assert response["result"]["count"] == 3 == len(runs)

    def test_overlong_input_rejected_without_exact_call(self):
        big = "x" * 100_001
        response = _tools.ip_inspect_mcp(big)
        assert response["ok"] is False
        assert response["error_type"] == "input_too_large"

    def test_non_string_input_rejected(self):
        response = _tools.cidr_inspect_mcp(123)  # type: ignore[arg-type]
        assert response["ok"] is False
        assert response["error_type"] == "invalid_arguments"


@pytest.fixture(scope="module")
def single_file_module():
    """Build the single file once and load it as a module."""
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as handle:
        output_path = handle.name
    try:
        result = subprocess.run(
            [sys.executable, BUILD_SCRIPT, "-o", output_path],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, f"Build failed: {result.stderr}"
        spec = importlib.util.spec_from_file_location("eggcalc_single_utility", output_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        yield module
    finally:
        sys.modules.pop("eggcalc_single_utility", None)
        if os.path.exists(output_path):
            os.unlink(output_path)


class TestUtilitySingleFileParity:
    """Package and generated-single-file results agree with types preserved."""

    @pytest.mark.parametrize(
        "case",
        [c for c in PARITY_CASES if c["expect_ok"]],
        ids=lambda c: f"{c['tool']}-{c['arguments']}",
    )
    def test_single_file_matches_package(self, single_file_module, case):
        package_handler = HANDLERS[case["tool"]]
        single_handler = getattr(single_file_module, f"{case['tool']}_mcp", None)
        if single_handler is None:
            # Handlers sharing exact names are renamed with an _mcp_ prefix.
            single_handler = getattr(single_file_module, f"_mcp_{case['tool']}")
        package_response = package_handler(**case["arguments"])
        single_response = single_handler(**case["arguments"])
        assert package_response["ok"] is True, package_response
        assert single_response["ok"] is True, single_response
        assert type(single_response["result"]) is type(package_response["result"])
        assert json.loads(json.dumps(single_response["result"])) == json.loads(
            json.dumps(package_response["result"])
        )
        assert single_response["result"] == package_response["result"]

    @pytest.mark.parametrize(
        "case",
        [c for c in PARITY_CASES if not c["expect_ok"]],
        ids=lambda c: f"{c['tool']}-{c['arguments']}",
    )
    def test_single_file_error_parity(self, single_file_module, case):
        single_handler = getattr(single_file_module, f"{case['tool']}_mcp", None)
        if single_handler is None:
            single_handler = getattr(single_file_module, f"_mcp_{case['tool']}")
        response = single_handler(**case["arguments"])
        assert response.get("ok") is False, response
        assert response.get("error_type") == case["expect_error_type"], response

    def test_single_file_registers_all_six_tools(self, single_file_module):
        for name in SIX_TOOLS:
            assert name in single_file_module.TOOL_HANDLERS, f"{name} missing in build"
            assert name in single_file_module.TOOL_SCHEMAS, f"{name} schema missing"
