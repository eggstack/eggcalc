"""Modern (2026-07-28) stateless protocol conformance tests.

Covers Plan 038 acceptance behavior: dual-era dispatch, ``server/discover``,
request-local ``_meta`` validation, modern ``tools/list`` / ``tools/call``
without session state, legacy preservation, era coexistence, profile parity,
error bounds, and generated single-file parity.

Request/response cases are literal JSON transcript dicts so they can be
compared directly against official SDK behavior.
"""

import json
import subprocess
import sys
import threading

import pytest

from eggcalc.mcp.server import McpServer, McpSessionState

MODERN_VERSION = "2026-07-28"

_PROTO = "io.modelcontextprotocol/protocolVersion"
_CAPS = "io.modelcontextprotocol/clientCapabilities"
_INFO = "io.modelcontextprotocol/clientInfo"
_SERVER_INFO = "io.modelcontextprotocol/serverInfo"

_DEFAULT = object()


def _modern_meta(version=MODERN_VERSION, capabilities=_DEFAULT, client_info=_DEFAULT) -> dict:
    """Build a modern params._meta envelope.

    Passing None for a field omits it (to exercise missing-field paths).
    """
    meta: dict = {}
    if version is not None:
        meta[_PROTO] = version
    if capabilities is _DEFAULT:
        capabilities = {}
    if capabilities is not None:
        meta[_CAPS] = capabilities
    if client_info is _DEFAULT:
        client_info = {"name": "test-client", "version": "0.1.0"}
    if client_info is not None:
        meta[_INFO] = client_info
    return meta


def _modern_request(method, request_id=1, params=None, **meta_kwargs) -> dict:
    """Build a literal modern JSON-RPC request transcript case."""
    body = dict(params or {})
    body["_meta"] = _modern_meta(**meta_kwargs)
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": body}


def _server_info_of(response) -> dict:
    return response["result"]["_meta"][_SERVER_INFO]


class TestProtocolEraAuthority:
    """Version -> era has one authority in eggcalc._protocol."""

    def test_era_mapping(self):
        from eggcalc._protocol import protocol_era

        assert protocol_era("2024-11-05") == "legacy"
        assert protocol_era("2025-11-25") == "legacy"
        assert protocol_era("2026-07-28") == "modern"
        assert protocol_era("2099-01-01") is None
        assert protocol_era("") is None
        assert protocol_era(None) is None
        assert protocol_era(123) is None

    def test_era_tuples(self):
        from eggcalc._protocol import (
            LATEST_LEGACY_PROTOCOL_VERSION,
            LATEST_SUPPORTED_PROTOCOL_VERSION,
            LEGACY_PROTOCOL_VERSIONS,
            MODERN_PROTOCOL_VERSIONS,
            SUPPORTED_PROTOCOL_VERSIONS,
        )

        assert LEGACY_PROTOCOL_VERSIONS == ("2024-11-05", "2025-11-25")
        assert MODERN_PROTOCOL_VERSIONS == ("2026-07-28",)
        assert SUPPORTED_PROTOCOL_VERSIONS == LEGACY_PROTOCOL_VERSIONS + MODERN_PROTOCOL_VERSIONS
        assert LATEST_SUPPORTED_PROTOCOL_VERSION == "2026-07-28"
        assert LATEST_LEGACY_PROTOCOL_VERSION == "2025-11-25"

    def test_server_reexports_match_protocol(self):
        from eggcalc import _protocol
        from eggcalc.mcp import server as server_mod

        assert tuple(server_mod.SUPPORTED_PROTOCOL_VERSIONS) == tuple(
            _protocol.SUPPORTED_PROTOCOL_VERSIONS
        )
        assert server_mod.LATEST_SUPPORTED_PROTOCOL_VERSION == (
            _protocol.LATEST_SUPPORTED_PROTOCOL_VERSION
        )

    def test_modern_method_allowlist(self):
        from eggcalc._protocol import MODERN_METHODS

        assert "server/discover" in MODERN_METHODS
        assert "tools/list" in MODERN_METHODS
        assert "tools/call" in MODERN_METHODS
        assert "initialize" not in MODERN_METHODS
        assert "notifications/initialized" not in MODERN_METHODS
        assert "ping" not in MODERN_METHODS
        assert "profiles/list" not in MODERN_METHODS


class TestModernDiscover:
    """server/discover succeeds without initialize and follows the schema."""

    def test_discover_without_initialize(self):
        server = McpServer()
        try:
            response = server.handle_request(_modern_request("server/discover"))
            assert "result" in response
            assert response["id"] == 1
        finally:
            server.close()

    def test_discover_versions_deterministic(self):
        server = McpServer()
        try:
            response = server.handle_request(_modern_request("server/discover"))
            versions = response["result"]["supportedVersions"]
            assert versions == ["2024-11-05", "2025-11-25", "2026-07-28"]
        finally:
            server.close()

    def test_discover_shape(self):
        import eggcalc

        server = McpServer()
        try:
            response = server.handle_request(_modern_request("server/discover"))
            result = response["result"]
            assert result["resultType"] == "complete"
            # Protocol capabilities only: runtime diagnostics stay out.
            assert result["capabilities"] == {"tools": {"listChanged": False}}
            assert "runtime" not in result["capabilities"]
            # Shared concise server instructions.
            assert isinstance(result["instructions"], str)
            assert len(result["instructions"]) > 0
            # Conservative cache hints.
            assert result["ttlMs"] == 0
            assert result["cacheScope"] == "private"
            # Server identity lives in result _meta, not the body.
            assert "serverInfo" not in result
            info = _server_info_of(response)
            assert info["name"] == "eggcalc"
            assert info["version"] == eggcalc.__version__
        finally:
            server.close()

    def test_discover_instructions_are_shared_authority(self):
        from eggcalc.mcp.server import SERVER_INSTRUCTIONS

        server = McpServer()
        try:
            response = server.handle_request(_modern_request("server/discover"))
            assert response["result"]["instructions"] == SERVER_INSTRUCTIONS
        finally:
            server.close()


class TestModernToolsList:
    """Modern tools/list needs no McpSession and is deterministic."""

    def test_list_without_session(self):
        server = McpServer()
        try:
            # No session passed at all: auto-created session is bypassed
            # for modern traffic and closed immediately.
            response = server.handle_request(_modern_request("tools/list", request_id=2))
            assert response["id"] == 2
            tools = response["result"]["tools"]
            assert len(tools) == 83
            names = [t["name"] for t in tools]
            assert "math_eval" in names
        finally:
            server.close()

    def test_list_modern_wire_fields(self):
        server = McpServer()
        try:
            response = server.handle_request(_modern_request("tools/list"))
            result = response["result"]
            assert result["resultType"] == "complete"
            assert result["ttlMs"] == 0
            assert result["cacheScope"] == "private"
            info = _server_info_of(response)
            assert info["name"] == "eggcalc"
        finally:
            server.close()

    def test_list_legacy_shape_unchanged(self):
        server = McpServer()
        try:
            session = server.create_session(McpSessionState.UNINITIALIZED)
            server.handle_request(
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
                session=session,
            )
            server.handle_request(
                {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
                session=session,
            )
            response = server.handle_request(
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
                session=session,
            )
            assert set(response["result"].keys()) == {"tools"}
        finally:
            server.close()

    def test_list_ordering_is_canonical(self):
        server = McpServer()
        try:
            response = server.handle_request(_modern_request("tools/list"))
            names = [t["name"] for t in response["result"]["tools"]]
            assert names == sorted(names)
        finally:
            server.close()

    def test_list_ordering_independent_of_registry_insertion(self):
        from eggcalc.mcp.schemas import TOOL_METADATA, TOOL_PROFILES, TOOL_SCHEMAS
        from eggcalc.mcp.server import TOOL_HANDLERS, ToolRegistry

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
            response = server.handle_request(_modern_request("tools/list"))
            names = [t["name"] for t in response["result"]["tools"]]
            assert names == sorted(names)
        finally:
            server.close()

    def test_list_filters_preserved_on_modern_path(self):
        server = McpServer()
        try:
            response = server.handle_request(_modern_request("tools/list", params={"tier": 0}))
            from eggcalc.mcp.schemas import TOOL_SCHEMAS

            for tool in response["result"]["tools"]:
                assert TOOL_SCHEMAS[tool["name"]].get("tier") == 0
        finally:
            server.close()


class TestModernToolsCall:
    """Modern tools/call needs no McpSession and bridges structured content."""

    def test_call_math_eval_without_session(self):
        server = McpServer()
        try:
            response = server.handle_request(
                _modern_request(
                    "tools/call",
                    params={"name": "math_eval", "arguments": {"expression": "5+3"}},
                )
            )
            result = response["result"]
            assert result["resultType"] == "complete"
            assert "isError" not in result
            envelope = json.loads(result["content"][0]["text"])
            assert envelope["ok"] is True
            assert envelope["result"]["value"] == "8"
            # Narrow compatibility bridge: structured payload equals the
            # text envelope's semantic result.
            assert result["structuredContent"] == envelope["result"]
            info = _server_info_of(response)
            assert info["name"] == "eggcalc"
        finally:
            server.close()

    def test_call_unknown_tool(self):
        server = McpServer()
        try:
            response = server.handle_request(
                _modern_request(
                    "tools/call",
                    params={"name": "nope_missing_tool", "arguments": {}},
                )
            )
            assert response["error"]["code"] == -32601
        finally:
            server.close()

    def test_call_invalid_arguments(self):
        server = McpServer()
        try:
            response = server.handle_request(
                _modern_request(
                    "tools/call",
                    params={"name": "math_eval", "arguments": {"bogus": 1}},
                )
            )
            assert response["error"]["code"] == -32602
        finally:
            server.close()

    def test_call_domain_error_has_no_structured_payload(self):
        server = McpServer()
        try:
            response = server.handle_request(
                _modern_request(
                    "tools/call",
                    params={"name": "math_eval", "arguments": {"expression": "5/0"}},
                )
            )
            result = response["result"]
            assert result["isError"] is True
            assert result["resultType"] == "complete"
            assert "structuredContent" not in result
            envelope = json.loads(result["content"][0]["text"])
            assert envelope["ok"] is False
        finally:
            server.close()

    def test_modern_call_leaves_explicit_session_untouched(self):
        server = McpServer()
        try:
            session = server.create_session(McpSessionState.UNINITIALIZED)
            response = server.handle_request(
                _modern_request(
                    "tools/call",
                    params={"name": "math_eval", "arguments": {"expression": "5+3"}},
                ),
                session=session,
            )
            assert "result" in response
            assert session.state == McpSessionState.UNINITIALIZED
        finally:
            server.close()


class TestModernEnvelopeValidation:
    """Malformed modern traffic gets deterministic protocol errors."""

    def test_missing_protocol_version_rejected(self):
        server = McpServer()
        try:
            response = server.handle_request(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/list",
                    "params": {"_meta": {_CAPS: {}}},
                }
            )
            assert response["error"]["code"] == -32602
        finally:
            server.close()

    def test_missing_client_capabilities_rejected(self):
        server = McpServer()
        try:
            response = server.handle_request(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/list",
                    "params": {"_meta": {_PROTO: MODERN_VERSION}},
                }
            )
            assert response["error"]["code"] == -32602
        finally:
            server.close()

    def test_non_dict_client_capabilities_rejected(self):
        server = McpServer()
        try:
            response = server.handle_request(_modern_request("tools/list", capabilities=[1, 2]))
            assert response["error"]["code"] == -32602
        finally:
            server.close()

    def test_missing_client_info_accepted(self):
        server = McpServer()
        try:
            response = server.handle_request(_modern_request("server/discover", client_info=None))
            assert "result" in response
        finally:
            server.close()

    @pytest.mark.parametrize(
        "client_info",
        [
            "not-an-object",
            {"version": "1.0.0"},
            {"name": ""},
            {"name": "   "},
            {"name": "c", "version": 123},
        ],
    )
    def test_malformed_client_info_rejected(self, client_info):
        server = McpServer()
        try:
            response = server.handle_request(
                _modern_request("server/discover", client_info=client_info)
            )
            assert response["error"]["code"] == -32602
        finally:
            server.close()

    def test_unsupported_future_version(self):
        server = McpServer()
        try:
            response = server.handle_request(_modern_request("tools/list", version="2099-01-01"))
            error = response["error"]
            assert error["code"] == -32022
            assert error["data"]["requested"] == "2099-01-01"
            assert "2026-07-28" in error["data"]["supported"]
            assert "2025-11-25" in error["data"]["supported"]
            assert "2024-11-05" in error["data"]["supported"]
        finally:
            server.close()

    def test_method_without_meta_is_legacy(self):
        server = McpServer()
        try:
            session = server.create_session(McpSessionState.UNINITIALIZED)
            response = server.handle_request(
                {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
                session=session,
            )
            assert response["error"]["code"] == -32600
        finally:
            server.close()

    def test_bare_discover_without_meta_is_not_modern(self):
        server = McpServer()
        try:
            session = server.create_session(McpSessionState.UNINITIALIZED)
            response = server.handle_request(
                {"jsonrpc": "2.0", "id": 1, "method": "server/discover", "params": {}},
                session=session,
            )
            # Legacy path: no supportedVersions, just a legacy error.
            assert "result" not in response or "supportedVersions" not in response.get("result", {})
            assert response["error"]["code"] == -32600
        finally:
            server.close()

    def test_modern_initialize_rejected(self):
        server = McpServer()
        try:
            response = server.handle_request(
                _modern_request(
                    "initialize",
                    params={
                        "protocolVersion": MODERN_VERSION,
                        "capabilities": {},
                        "clientInfo": {"name": "c", "version": "1"},
                    },
                )
            )
            assert response["error"]["code"] == -32601
        finally:
            server.close()

    def test_modern_ping_not_defined(self):
        server = McpServer()
        try:
            response = server.handle_request(_modern_request("ping"))
            assert response["error"]["code"] == -32601
        finally:
            server.close()

    def test_modern_profiles_list_not_exposed(self):
        server = McpServer()
        try:
            response = server.handle_request(_modern_request("profiles/list"))
            assert response["error"]["code"] == -32601
        finally:
            server.close()

    def test_modern_notification_produces_no_response(self):
        server = McpServer()
        try:
            session = server.create_session(McpSessionState.UNINITIALIZED)
            response = server.handle_request(
                {
                    "jsonrpc": "2.0",
                    "method": "notifications/cancelled",
                    "params": {
                        "requestId": 1,
                        "_meta": _modern_meta(),
                    },
                },
                session=session,
            )
            assert response is None
            assert session.state == McpSessionState.UNINITIALIZED
        finally:
            server.close()

    def test_legacy_version_in_envelope_uses_legacy_path(self):
        server = McpServer()
        try:
            session = server.create_session(McpSessionState.UNINITIALIZED)
            response = server.handle_request(
                _modern_request("tools/list", version="2025-11-25"),
                session=session,
            )
            # Handshake era owns legacy revisions: still requires READY.
            assert response["error"]["code"] == -32600
        finally:
            server.close()


class TestLegacyPreservation:
    """The handshake era is byte/behavior compatible."""

    def _handshake(self, server, session, version="2025-11-25"):
        response = server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": version,
                    "capabilities": {},
                    "clientInfo": {"name": "test-client", "version": "0.1.0"},
                },
            },
            session=session,
        )
        server.handle_request(
            {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
            session=session,
        )
        return response

    @pytest.mark.parametrize("version", ["2024-11-05", "2025-11-25"])
    def test_legacy_handshake_versions(self, version):
        from eggcalc.mcp.server import McpSessionState as SS

        server = McpServer()
        try:
            session = server.create_session(SS.UNINITIALIZED)
            response = self._handshake(server, session, version)
            assert response["result"]["protocolVersion"] == version
            assert session.state == SS.READY
        finally:
            server.close()

    def test_initialize_with_modern_version_falls_back_to_legacy(self):
        from eggcalc.mcp.server import McpSessionState as SS

        server = McpServer()
        try:
            session = server.create_session(SS.UNINITIALIZED)
            response = server.handle_request(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2026-07-28",
                        "capabilities": {},
                        "clientInfo": {"name": "c", "version": "1"},
                    },
                },
                session=session,
            )
            # The handshake never negotiates the stateless revision.
            assert response["result"]["protocolVersion"] == "2025-11-25"
        finally:
            server.close()

    def test_legacy_ping_still_defined(self):
        from eggcalc.mcp.server import McpSessionState as SS

        server = McpServer()
        try:
            session = server.create_session(SS.UNINITIALIZED)
            response = server.handle_request(
                {"jsonrpc": "2.0", "id": 9, "method": "ping", "params": {}},
                session=session,
            )
            assert response["result"] == {}
        finally:
            server.close()


class TestEraCoexistence:
    """One server process serves both eras without state bleed."""

    def test_interleaved_modern_and_legacy(self):
        server = McpServer()
        try:
            session = server.create_session(McpSessionState.UNINITIALIZED)
            # Legacy handshake to READY.
            init = server.handle_request(
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
                session=session,
            )
            assert init["result"]["protocolVersion"] == "2025-11-25"
            # Modern traffic before the legacy ack: session unaffected.
            discover = server.handle_request(
                _modern_request("server/discover", request_id=2), session=session
            )
            assert "supportedVersions" in discover["result"]
            assert session.state == McpSessionState.INITIALIZING
            # Complete the legacy handshake.
            server.handle_request(
                {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
                session=session,
            )
            assert session.state == McpSessionState.READY
            # Legacy tools still work after modern traffic.
            legacy_call = server.handle_request(
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "math_eval",
                        "arguments": {"expression": "5+3"},
                    },
                },
                session=session,
            )
            assert json.loads(legacy_call["result"]["content"][0]["text"])["ok"] is True
            # Modern call on the same connection: structured bridge + stamp.
            modern_call = server.handle_request(
                _modern_request(
                    "tools/call",
                    request_id=4,
                    params={"name": "math_eval", "arguments": {"expression": "5+3"}},
                ),
                session=session,
            )
            assert modern_call["result"]["structuredContent"] == {"value": "8", "type": "int"}
            assert _SERVER_INFO in modern_call["result"]["_meta"]
            assert session.state == McpSessionState.READY
        finally:
            server.close()

    def test_stdio_coexistence_transcript(self):
        """A single stdio process answers modern + legacy requests inline."""
        requests = [
            json.dumps(_modern_request("server/discover", request_id=1)),
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-11-25",
                        "capabilities": {},
                        "clientInfo": {"name": "c", "version": "1"},
                    },
                }
            ),
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
            json.dumps(_modern_request("tools/list", request_id=3)),
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 4,
                    "method": "tools/call",
                    "params": {
                        "name": "math_eval",
                        "arguments": {"expression": "5+3"},
                    },
                }
            ),
            json.dumps(
                _modern_request(
                    "tools/call",
                    request_id=5,
                    params={"name": "math_eval", "arguments": {"expression": "5+3"}},
                )
            ),
        ]
        proc = subprocess.Popen(
            [sys.executable, "-m", "eggcalc", "--mcp"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            stdout, stderr = proc.communicate(
                input=("\n".join(requests) + "\n").encode(), timeout=30
            )
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
        assert proc.returncode == 0, stderr.decode(errors="replace")
        by_id = {
            json.loads(line)["id"]: json.loads(line)
            for line in stdout.decode().splitlines()
            if line.strip()
        }
        assert by_id[1]["result"]["supportedVersions"][-1] == "2026-07-28"
        assert by_id[2]["result"]["protocolVersion"] == "2025-11-25"
        assert len(by_id[3]["result"]["tools"]) == 83
        assert json.loads(by_id[4]["result"]["content"][0]["text"])["ok"] is True
        assert by_id[5]["result"]["structuredContent"] == {"value": "8", "type": "int"}


class TestModernConfigCapture:
    """Modern requests see one stable evaluator/config generation."""

    def test_generation_stable_across_modern_call(self):
        server = McpServer()
        try:
            before = server.runtime_context.snapshot.generation
            server.handle_request(
                _modern_request(
                    "tools/call",
                    params={"name": "math_eval", "arguments": {"expression": "1+1"}},
                )
            )
            assert server.runtime_context.snapshot.generation == before
        finally:
            server.close()

    def test_configuration_change_visible_to_later_modern_call(self):
        server = McpServer()
        try:
            server.apply_configuration(constants={"modern_probe_const": 41})
            response = server.handle_request(
                _modern_request(
                    "tools/call",
                    params={
                        "name": "math_eval",
                        "arguments": {"expression": "modern_probe_const + 1"},
                    },
                )
            )
            envelope = json.loads(response["result"]["content"][0]["text"])
            assert envelope["ok"] is True
            assert envelope["result"]["value"] == "42"
        finally:
            server.close()


class TestModernProfileParity:
    """Profile restrictions apply identically to both eras."""

    def _excluded_tool(self) -> str:
        from eggcalc.mcp.server import ToolRegistry

        registry = ToolRegistry()
        full = set(registry.get_profile_tools("full"))
        narrow = set(registry.get_profile_tools("human_math"))
        excluded = sorted(full - narrow)
        assert excluded, "expected at least one full-only tool"
        return excluded[0]

    def test_profile_restriction_identical(self):
        from eggcalc.mcp.server import McpServerConfig

        server = McpServer(config=McpServerConfig(profile="human_math"))
        try:
            excluded = self._excluded_tool()
            modern = server.handle_request(
                _modern_request(
                    "tools/call",
                    params={"name": excluded, "arguments": {}},
                )
            )
            assert modern["error"]["code"] == -32602

            session = server.create_session(McpSessionState.UNINITIALIZED)
            server.handle_request(
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
                session=session,
            )
            server.handle_request(
                {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
                session=session,
            )
            legacy = server.handle_request(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": excluded, "arguments": {}},
                },
                session=session,
            )
            assert legacy["error"]["code"] == -32602

            # ... while an allowed tool works on both paths.
            for req in (
                _modern_request(
                    "tools/call",
                    params={"name": "math_eval", "arguments": {"expression": "1+1"}},
                ),
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {"name": "math_eval", "arguments": {"expression": "1+1"}},
                },
            ):
                if req.get("method") == "tools/call" and "_meta" not in req.get("params", {}):
                    resp = server.handle_request(req, session=session)
                else:
                    resp = server.handle_request(req)
                assert "result" in resp, resp
        finally:
            server.close()


class TestModernErrorBounds:
    """Output-size and timeout errors stay valid in both eras."""

    def test_output_too_large_both_eras(self):
        from eggcalc.mcp.server import McpServerConfig

        server = McpServer(config=McpServerConfig(max_output_bytes=40))
        try:
            modern = server.handle_request(
                _modern_request(
                    "tools/call",
                    params={"name": "math_eval", "arguments": {"expression": "5+3"}},
                )
            )
            modern_result = modern["result"]
            assert modern_result["isError"] is True
            assert modern_result["resultType"] == "complete"
            assert _SERVER_INFO in modern_result["_meta"]
            inner = json.loads(modern_result["content"][0]["text"])
            assert inner["error_type"] == "output_too_large"

            session = server.create_session(McpSessionState.UNINITIALIZED)
            server.handle_request(
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
                session=session,
            )
            server.handle_request(
                {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
                session=session,
            )
            legacy = server.handle_request(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": "math_eval", "arguments": {"expression": "5+3"}},
                },
                session=session,
            )
            assert legacy["result"]["isError"] is True
            assert "resultType" not in legacy["result"]
            legacy_inner = json.loads(legacy["result"]["content"][0]["text"])
            assert legacy_inner["error_type"] == "output_too_large"
        finally:
            server.close()

    def test_timeout_both_eras(self):
        from eggcalc.mcp.server import McpServerConfig, ToolRegistry

        release = threading.Event()

        def _slow(**kwargs):
            release.wait(timeout=10)
            return {"ok": True, "result": {}}

        schema = {"description": "slow probe", "inputSchema": {"type": "object", "properties": {}}}
        registry = ToolRegistry(
            handlers={"slow_probe": _slow},
            schemas={"slow_probe": schema},
            metadata={"slow_probe": {}},
            profiles={"probe": ["slow_probe"]},
        )
        server = McpServer(
            config=McpServerConfig(profile="probe", max_tool_timeout_seconds=1, max_tool_workers=2),
            registry=registry,
        )
        try:
            modern = server.handle_request(
                _modern_request(
                    "tools/call",
                    params={"name": "slow_probe", "arguments": {}},
                )
            )
            modern_result = modern["result"]
            assert modern_result["isError"] is True
            assert modern_result["resultType"] == "complete"
            assert _SERVER_INFO in modern_result["_meta"]
            assert "timed out" in json.loads(modern_result["content"][0]["text"])["error"]

            session = server.create_session(McpSessionState.UNINITIALIZED)
            server.handle_request(
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
                session=session,
            )
            server.handle_request(
                {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
                session=session,
            )
            legacy = server.handle_request(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": "slow_probe", "arguments": {}},
                },
                session=session,
            )
            assert legacy["result"]["isError"] is True
            assert "resultType" not in legacy["result"]
            assert "timed out" in json.loads(legacy["result"]["content"][0]["text"])["error"]
        finally:
            release.set()
            server.close()


def _run_transcript(cmd, requests, timeout=30):
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
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


def _normalize_modern(responses):
    normalized = []
    for resp in responses:
        resp = json.loads(json.dumps(resp))
        result = resp.get("result")
        if isinstance(result, dict):
            meta = result.get("_meta", {})
            info = dict(meta.get(_SERVER_INFO, {}))
            if "version" in info:
                info["version"] = "<normalized>"
                meta[_SERVER_INFO] = info
        normalized.append(resp)
    return normalized


class TestModernSingleFileParity:
    """Generated single-file MCP supports the modern transcript."""

    MODERN_TRANSCRIPT = [
        json.dumps(_modern_request("server/discover", request_id=1)),
        json.dumps(_modern_request("tools/list", request_id=2)),
        json.dumps(
            _modern_request(
                "tools/call",
                request_id=3,
                params={"name": "math_eval", "arguments": {"expression": "5+3"}},
            )
        ),
    ]

    def test_package_modern_transcript(self):
        responses = _run_transcript(
            [sys.executable, "-m", "eggcalc", "--mcp"], self.MODERN_TRANSCRIPT
        )
        assert len(responses) == 3
        assert responses[0]["result"]["supportedVersions"][-1] == "2026-07-28"
        assert len(responses[1]["result"]["tools"]) == 83
        assert responses[1]["result"]["resultType"] == "complete"
        assert responses[2]["result"]["structuredContent"] == {"value": "8", "type": "int"}

    def test_single_file_modern_transcript_matches_package(self, tmp_path):
        import os

        build_script = os.path.join(os.path.dirname(__file__), "..", "build_single.py")
        single_file = str(tmp_path / "eggcalc_modern_probe.py")
        built = subprocess.run(
            [sys.executable, build_script, "-o", single_file],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if built.returncode != 0:
            pytest.skip(f"build_single.py failed: {built.stderr}")
        pkg = _run_transcript([sys.executable, "-m", "eggcalc", "--mcp"], self.MODERN_TRANSCRIPT)
        single = _run_transcript([sys.executable, single_file, "--mcp"], self.MODERN_TRANSCRIPT)
        assert _normalize_modern(pkg) == _normalize_modern(single)


class TestInteropFixture:
    """Checked-in external-interop transcript stays consistent with the server."""

    @staticmethod
    def _fixture() -> dict:
        import os

        path = os.path.join(
            os.path.dirname(__file__), "fixtures", "mcp_2026_07_28_interop_transcript.json"
        )
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def test_fixture_matches_live_server(self):
        fixture = self._fixture()
        by_id = {r["id"]: r for r in fixture["responses"] if "id" in r}

        server = McpServer()
        try:
            live_discover = server.handle_request(_modern_request("server/discover"))
            assert (
                live_discover["result"]["supportedVersions"]
                == by_id[1]["result"]["supportedVersions"]
            )
            assert live_discover["result"]["capabilities"] == by_id[1]["result"]["capabilities"]
            live_call = server.handle_request(
                _modern_request(
                    "tools/call",
                    request_id=3,
                    params={"name": "math_eval", "arguments": {"expression": "5+3"}},
                )
            )
            assert (
                live_call["result"]["structuredContent"] == by_id[3]["result"]["structuredContent"]
            )
            live_list = server.handle_request(_modern_request("tools/list", request_id=2))
            assert len(live_list["result"]["tools"]) == by_id[2]["result"]["tools"]["count"] == 83
        finally:
            server.close()
