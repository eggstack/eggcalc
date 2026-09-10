"""Plan 039: structured results, annotations, and cache hints.

Covers the Plan 039 deltas over the Plan 038 baseline:
- result-boundary mapping (structuredContent = text envelope result);
- legacy structured output for object-rooted schemas;
- output-schema validation (including nullable/optional/nested shapes);
- standard tool annotations in every schema-detail mode;
- shared server instructions across eras;
- canonical list ordering on both eras;
- conservative modern cache hints from one authority;
- single bounded output policy after dual representation.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from eggcalc.mcp.schemas import (
    DEFAULT_TOOL_ANNOTATIONS,
    TOOL_SCHEMAS,
    get_tool_annotations,
)
from eggcalc.mcp.server import (
    SERVER_INSTRUCTIONS,
    McpServer,
    McpServerConfig,
    McpSessionState,
    ToolRegistry,
    _split_tool_wire_result,
    _validate_output_payload,
)

MODERN_VERSION = "2026-07-28"
_PROTO = "io.modelcontextprotocol/protocolVersion"
_CAPS = "io.modelcontextprotocol/clientCapabilities"
_INFO = "io.modelcontextprotocol/clientInfo"
_SERVER_INFO = "io.modelcontextprotocol/serverInfo"


def _modern_meta(version=MODERN_VERSION, capabilities=None, client_info=None) -> dict:
    meta: dict = {}
    if version is not None:
        meta[_PROTO] = version
    meta[_CAPS] = {} if capabilities is None else capabilities
    meta[_INFO] = (
        {"name": "test-client", "version": "0.1.0"} if client_info is None else client_info
    )
    return meta


def _modern_request(method, request_id=1, params=None, **meta_kwargs) -> dict:
    body = dict(params or {})
    body["_meta"] = _modern_meta(**meta_kwargs)
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": body}


def _handshake(server, session, request_id=1, version="2025-11-25"):
    server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "initialize",
            "params": {
                "protocolVersion": version,
                "capabilities": {},
                "clientInfo": {"name": "c", "version": "1"},
            },
        },
        session=session,
    )
    server.handle_request(
        {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
        session=session,
    )


class TestResultBoundary:
    def test_split_success_maps_result(self):
        handler_result = {"ok": True, "tool": "t", "result": {"a": 1}, "warnings": []}
        wire = _split_tool_wire_result(handler_result)
        assert wire.is_error is False
        assert wire.text_envelope is handler_result
        assert wire.structured_content == {"a": 1}

    def test_split_error_has_no_structured_payload(self):
        handler_result = {"ok": False, "error": "x", "error_type": "t", "tool": "t"}
        wire = _split_tool_wire_result(handler_result)
        assert wire.is_error is True
        assert wire.structured_content is None
        assert wire.text_envelope is handler_result

    def test_split_non_dict_is_error(self):
        wire = _split_tool_wire_result([1, 2, 3])
        assert wire.is_error is True
        assert wire.structured_content is None
        assert wire.text_envelope["ok"] is False

    def test_math_eval_structured_equals_text_result_modern(self):
        server = McpServer()
        try:
            response = server.handle_request(
                _modern_request(
                    "tools/call",
                    params={"name": "math_eval", "arguments": {"expression": "5+3"}},
                )
            )
            result = response["result"]
            envelope = json.loads(result["content"][0]["text"])
            assert envelope["ok"] is True
            assert (
                result["structuredContent"] == envelope["result"] == {"value": "8", "type": "int"}
            )
        finally:
            server.close()

    def test_math_eval_structured_equals_text_result_legacy(self):
        server = McpServer()
        try:
            session = server.create_session(McpSessionState.UNINITIALIZED)
            _handshake(server, session)
            response = server.handle_request(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": "math_eval", "arguments": {"expression": "5+3"}},
                },
                session=session,
            )
            result = response["result"]
            # Legacy has no resultType but does carry object-rooted structuredContent.
            assert "resultType" not in result
            envelope = json.loads(result["content"][0]["text"])
            assert envelope["ok"] is True
            assert result["structuredContent"] == envelope["result"]
        finally:
            server.close()

    def test_unit_tools_structured_bridge(self):
        server = McpServer()
        try:
            for tool, args in [
                ("unit_convert", {"value": 1, "from_unit": "km", "to_unit": "m"}),
                ("unit_info", {"unit": "km"}),
            ]:
                response = server.handle_request(
                    _modern_request("tools/call", params={"name": tool, "arguments": args})
                )
                result = response["result"]
                envelope = json.loads(result["content"][0]["text"])
                assert envelope["ok"] is True, envelope
                assert result["structuredContent"] == envelope["result"]
        finally:
            server.close()

    def test_text_tools_structured_bridge(self):
        server = McpServer()
        try:
            for tool, args in [
                ("text_measure", {"text": "hello"}),
                ("text_equal", {"a": "hi", "b": "hi"}),
            ]:
                response = server.handle_request(
                    _modern_request("tools/call", params={"name": tool, "arguments": args})
                )
                result = response["result"]
                envelope = json.loads(result["content"][0]["text"])
                assert envelope["ok"] is True, envelope
                assert result["structuredContent"] == envelope["result"]
        finally:
            server.close()

    def test_composite_envelope_preserves_outer_metadata(self):
        server = McpServer()
        try:
            response = server.handle_request(
                _modern_request(
                    "tools/call",
                    params={"name": "command_preflight", "arguments": {"command": "echo hi"}},
                )
            )
            result = response["result"]
            envelope = json.loads(result["content"][0]["text"])
            assert envelope["ok"] is True
            # Compatibility metadata stays on the text envelope ...
            assert "findings" in envelope or "machine_code" in envelope or "warnings" in envelope
            # ... while the semantic payload is the structured result.
            assert result["structuredContent"] == envelope["result"]
        finally:
            server.close()

    def test_domain_error_has_no_structured_payload_both_eras(self):
        server = McpServer()
        try:
            modern = server.handle_request(
                _modern_request(
                    "tools/call",
                    params={"name": "math_eval", "arguments": {"expression": "5/0"}},
                )
            )
            assert modern["result"]["isError"] is True
            assert "structuredContent" not in modern["result"]

            session = server.create_session(McpSessionState.UNINITIALIZED)
            _handshake(server, session)
            legacy = server.handle_request(
                {
                    "jsonrpc": "2.0",
                    "id": 9,
                    "method": "tools/call",
                    "params": {"name": "math_eval", "arguments": {"expression": "5/0"}},
                },
                session=session,
            )
            assert legacy["result"]["isError"] is True
            assert "structuredContent" not in legacy["result"]
        finally:
            server.close()

    def test_output_too_large_has_no_structured_payload(self):
        server = McpServer(config=McpServerConfig(max_output_bytes=40))
        try:
            response = server.handle_request(
                _modern_request(
                    "tools/call",
                    params={"name": "math_eval", "arguments": {"expression": "5+3"}},
                )
            )
            result = response["result"]
            assert result["isError"] is True
            assert "structuredContent" not in result
            assert json.loads(result["content"][0]["text"])["error_type"] == "output_too_large"
        finally:
            server.close()


class TestOutputValidation:
    def test_optional_fields_may_be_omitted(self):
        # math_eval without units omits unit/display; still valid.
        assert _validate_output_payload("math_eval", {"value": "8", "type": "int"}) is None

    def test_nested_object_and_array_shapes(self):
        server = McpServer()
        try:
            for tool, args in [
                ("json_compare", {"a": '{"x": 1}', "b": '{"x": 1}'}),
                ("text_diff_explain", {"a": "hi", "b": "ho"}),
            ]:
                response = server.handle_request(
                    _modern_request("tools/call", params={"name": tool, "arguments": args})
                )
                assert "result" in response, response
                envelope = json.loads(response["result"]["content"][0]["text"])
                assert envelope["ok"] is True, envelope
                assert response["result"]["structuredContent"] == envelope["result"]
        finally:
            server.close()

    def test_frequency_table_shape_passes(self):
        assert _validate_output_payload("text_count", {"h": 1, "e": 1}) is None
        server = McpServer()
        try:
            response = server.handle_request(
                _modern_request(
                    "tools/call", params={"name": "text_count", "arguments": {"text": "hello"}}
                )
            )
            envelope = json.loads(response["result"]["content"][0]["text"])
            assert envelope["ok"] is True
            assert response["result"]["structuredContent"] == envelope["result"]
        finally:
            server.close()

    def test_nullable_optionals_validate(self):
        assert (
            _validate_output_payload(
                "argv_compare",
                {
                    "argv_equal": True,
                    "left_argv": ["ls"],
                    "right_argv": ["ls"],
                    "first_difference": None,
                    "findings": [],
                },
            )
            is None
        )
        assert (
            _validate_output_payload(
                "line_range_compare",
                {
                    "equal": True,
                    "left_fingerprint": "a",
                    "right_fingerprint": "a",
                    "diff_summary": "equal",
                    "first_difference": None,
                },
            )
            is None
        )
        assert (
            _validate_output_payload(
                "canonicalize_text",
                {
                    "text": "hi",
                    "changed": False,
                    "operations_applied": [],
                    "fingerprint_before": "a",
                    "fingerprint_after": "a",
                    "mapping": None,
                    "findings": [],
                },
            )
            is None
        )

    def test_synthetic_mismatch_is_internal_error(self):
        def _bad(**kwargs):
            return {"ok": True, "tool": "bad_probe", "result": {"count": "not-an-int"}}

        registry = ToolRegistry(
            handlers={"bad_probe": _bad},
            schemas={
                "bad_probe": {
                    "description": "synthetic mismatch probe",
                    "inputSchema": {"type": "object", "properties": {}},
                    "outputSchema": {
                        "type": "object",
                        "properties": {"count": {"type": "integer"}},
                    },
                }
            },
            metadata={"bad_probe": {}},
            profiles={"probe": ["bad_probe"]},
        )
        server = McpServer(
            config=McpServerConfig(profile="probe"),
            registry=registry,
        )
        try:
            response = server.handle_request(
                _modern_request("tools/call", params={"name": "bad_probe", "arguments": {}})
            )
            assert "error" in response
            assert response["error"]["code"] == -32000
            assert "traceback" not in response["error"]["message"].lower()
        finally:
            server.close()


class TestToolAnnotations:
    def test_all_visible_tools_emit_annotations(self):
        server = McpServer()
        try:
            response = server.handle_request(_modern_request("tools/list"))
            for tool in response["result"]["tools"]:
                annotations = tool.get("annotations")
                assert isinstance(annotations, dict), tool["name"]
                for key in ("readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint"):
                    assert annotations.get(key) in (True, False), (tool["name"], key)
        finally:
            server.close()

    def test_uniform_closed_world_posture(self):
        assert get_tool_annotations("math_eval") == dict(DEFAULT_TOOL_ANNOTATIONS)
        assert DEFAULT_TOOL_ANNOTATIONS == {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }

    def test_annotation_invariants(self):
        for name in TOOL_SCHEMAS:
            annotations = get_tool_annotations(name)
            if annotations.get("readOnlyHint") is True:
                # Read-only tools must not advertise destructive behavior.
                assert annotations.get("destructiveHint") is False, name

    def test_annotations_survive_schema_detail_modes(self):
        server = McpServer()
        try:
            for detail in ("compact", "normal", "full"):
                response = server.handle_request(
                    _modern_request("tools/list", params={"schema_detail": detail})
                )
                tools = response["result"]["tools"]
                assert tools, detail
                for tool in tools:
                    assert "annotations" in tool, (detail, tool["name"])
                    assert tool["annotations"]["readOnlyHint"] is True
        finally:
            server.close()

    def test_legacy_list_carries_annotations(self):
        server = McpServer()
        try:
            session = server.create_session(McpSessionState.UNINITIALIZED)
            _handshake(server, session)
            response = server.handle_request(
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
                session=session,
            )
            for tool in response["result"]["tools"]:
                assert tool.get("annotations", {}).get("openWorldHint") is False
        finally:
            server.close()


class TestServerInstructions:
    def test_instructions_identical_across_eras(self):
        server = McpServer()
        try:
            modern = server.handle_request(_modern_request("server/discover"))
            session = server.create_session(McpSessionState.UNINITIALIZED)
            init = server.handle_request(
                {
                    "jsonrpc": "2.0",
                    "id": 7,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-11-25",
                        "capabilities": {},
                        "clientInfo": {"name": "c", "version": "1"},
                    },
                },
                session=session,
            )
            assert modern["result"]["instructions"] == init["result"]["instructions"]
            assert init["result"]["instructions"] == SERVER_INSTRUCTIONS
        finally:
            server.close()


class TestListOrderingAndCache:
    def test_legacy_ordering_is_sorted(self):
        server = McpServer()
        try:
            session = server.create_session(McpSessionState.UNINITIALIZED)
            _handshake(server, session)
            response = server.handle_request(
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
                session=session,
            )
            names = [t["name"] for t in response["result"]["tools"]]
            assert names == sorted(names)
        finally:
            server.close()

    def test_ordering_independent_of_source_insertion_legacy(self):
        from eggcalc.mcp.schemas import TOOL_METADATA, TOOL_PROFILES, TOOL_SCHEMAS
        from eggcalc.mcp.server import TOOL_HANDLERS

        def _reversed(mapping):
            return dict(reversed(list(mapping.items())))

        registry = ToolRegistry(
            handlers=_reversed(TOOL_HANDLERS),
            schemas=_reversed(TOOL_SCHEMAS),
            metadata=_reversed(TOOL_METADATA),
            profiles={k: list(v) for k, v in TOOL_PROFILES.items()},
        )
        server = McpServer(registry=registry)
        try:
            session = server.create_session(McpSessionState.UNINITIALIZED)
            _handshake(server, session)
            response = server.handle_request(
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
                session=session,
            )
            names = [t["name"] for t in response["result"]["tools"]]
            assert names == sorted(names)
        finally:
            server.close()

    def test_modern_cache_hints_from_one_authority(self):
        from eggcalc._protocol import MODERN_CACHE_SCOPE, MODERN_CACHE_TTL_MS

        assert (MODERN_CACHE_TTL_MS, MODERN_CACHE_SCOPE) == (0, "private")
        server = McpServer()
        try:
            discover = server.handle_request(_modern_request("server/discover"))
            assert discover["result"]["ttlMs"] == MODERN_CACHE_TTL_MS
            assert discover["result"]["cacheScope"] == MODERN_CACHE_SCOPE
            listing = server.handle_request(_modern_request("tools/list"))
            assert listing["result"]["ttlMs"] == MODERN_CACHE_TTL_MS
            assert listing["result"]["cacheScope"] == MODERN_CACHE_SCOPE
        finally:
            server.close()

    def test_legacy_results_carry_no_cache_hints(self):
        server = McpServer()
        try:
            session = server.create_session(McpSessionState.UNINITIALIZED)
            _handshake(server, session)
            listing = server.handle_request(
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
                session=session,
            )
            assert "ttlMs" not in listing["result"]
            assert "cacheScope" not in listing["result"]
        finally:
            server.close()


class TestSizeAccounting:
    def test_limit_applies_to_envelope_not_double_counted(self):
        # The envelope for math_eval("5+3") is ~70 bytes. A limit just
        # above the envelope must still pass even though the wire form
        # duplicates the payload as structuredContent.
        server = McpServer(config=McpServerConfig(max_output_bytes=200))
        try:
            response = server.handle_request(
                _modern_request(
                    "tools/call",
                    params={"name": "math_eval", "arguments": {"expression": "5+3"}},
                )
            )
            assert "result" in response, response
            assert "structuredContent" in response["result"]
        finally:
            server.close()


class TestSingleFileParity:
    LEGACY_TRANSCRIPT = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "c", "version": "1"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "math_eval", "arguments": {"expression": "5+3"}},
        },
    ]

    @staticmethod
    def _run(cmd, requests, timeout=30):
        proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        try:
            stdout, stderr = proc.communicate(
                input=("\n".join(requests) + "\n").encode(), timeout=timeout
            )
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
        assert proc.returncode == 0, stderr.decode(errors="replace")
        return [json.loads(line) for line in stdout.decode().splitlines() if line.strip()]

    def test_single_file_legacy_structured_and_annotations(self, tmp_path):
        import os

        build_script = os.path.join(os.path.dirname(__file__), "..", "build_single.py")
        single_file = str(tmp_path / "eggcalc_structured_probe.py")
        built = subprocess.run(
            [sys.executable, build_script, "-o", single_file],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if built.returncode != 0:
            pytest.skip(f"build_single.py failed: {built.stderr}")
        requests = [json.dumps(r) for r in self.LEGACY_TRANSCRIPT]
        pkg = self._run([sys.executable, "-m", "eggcalc", "--mcp"], requests)
        single = self._run([sys.executable, single_file, "--mcp"], requests)
        by_pkg = {r.get("id"): r for r in pkg if "id" in r}
        by_single = {r.get("id"): r for r in single if "id" in r}
        # Instructions identical across package/single-file.
        assert by_pkg[1]["result"]["instructions"] == by_single[1]["result"]["instructions"]
        # Legacy list carries annotations in both.
        pkg_tools = {t["name"]: t for t in by_pkg[2]["result"]["tools"]}
        single_tools = {t["name"]: t for t in by_single[2]["result"]["tools"]}
        assert pkg_tools["math_eval"]["annotations"] == single_tools["math_eval"]["annotations"]
        # Legacy structured payload matches in both.
        assert by_pkg[3]["result"]["structuredContent"] == {"value": "8", "type": "int"}
        assert by_single[3]["result"]["structuredContent"] == {"value": "8", "type": "int"}
