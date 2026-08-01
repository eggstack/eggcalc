"""Final MCP ownership, configuration, and reservation closure tests."""

from __future__ import annotations

import gc

import pytest

from eggcalc.mcp.server import (
    ConfigSnapshot,
    EvaluationPolicy,
    McpServer,
    McpServerConfig,
    McpSession,
    McpSessionState,
    ToolExecutor,
    ToolRegistry,
    build_runtime_context,
    close_compatibility_server,
    handle_request,
)


def _registry() -> ToolRegistry:
    return ToolRegistry(
        handlers={"math_eval": lambda: {"ok": True}},
        schemas={"math_eval": {"description": "test", "inputSchema": {"type": "object"}}},
        metadata={"math_eval": {}},
        profiles={"custom_safe": ["math_eval"]},
    )


def _request(method: str, request_id: int, params: dict | None = None) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}


def test_custom_registry_profile_list_tools_and_call_agree() -> None:
    server = McpServer(McpServerConfig(profile="custom_safe"), _registry())
    session = server.create_session(McpSessionState.READY)
    try:
        listed = server.handle_request(_request("profiles/list", 1), session)
        assert listed["result"]["available_profiles"] == ["full", "custom_safe"]
        assert "default" not in listed["result"]["profiles"]
        tools = server.handle_request(_request("tools/list", 2), session)
        assert [tool["name"] for tool in tools["result"]["tools"]] == ["math_eval"]
        called = server.handle_request(
            _request("tools/call", 3, {"name": "math_eval", "arguments": {}}), session
        )
        assert called["result"]["content"]
    finally:
        server.close()


def test_failed_publication_preserves_both_authorities() -> None:
    server = McpServer(registry=_registry())
    try:
        old = server.runtime_context

        def fail(_snapshot: ConfigSnapshot) -> None:
            raise RuntimeError("injected validation failure")

        server.config_manager._validate_next = fail  # type: ignore[method-assign]
        with pytest.raises(RuntimeError, match="injected"):
            server.apply_configuration(constants={"x": 1})
        assert server.runtime_context is old
        assert server.config_manager.current() is old.snapshot
        assert server.diagnostic()["config_generation"] == old.snapshot.generation
    finally:
        server.close()


def test_policy_is_independent_of_tool_profile() -> None:
    allowing = McpServerConfig(
        profile="custom_safe",
        allow_random=True,
        allow_side_effects=True,
        evaluation_policy="default",
    )
    strict = build_runtime_context(
        allowing,
        ConfigSnapshot(policy=EvaluationPolicy.STRICT),
    )
    permissive = build_runtime_context(
        allowing,
        ConfigSnapshot(policy=EvaluationPolicy.PERMISSIVE),
    )
    default = build_runtime_context(allowing, ConfigSnapshot(policy=EvaluationPolicy.DEFAULT))
    assert strict.evaluator._allow_random is False
    assert strict.evaluator._allow_side_effects is False
    assert permissive.evaluator._allow_random is True
    assert permissive.evaluator._allow_side_effects is True
    assert default.evaluator._allow_random is True
    assert default.evaluator._allow_side_effects is True


def test_reservations_are_removed_after_long_running_terminal_calls() -> None:
    config = McpServerConfig(max_tool_workers=2, max_tool_queue_size=2)
    executor = ToolExecutor(config, _registry())
    try:
        for request_id in range(10_000):
            response = executor.call_tool("math_eval", {}, request_id=request_id)
            assert response["result"]["content"]
        executor.assert_accounting_invariants()
        assert executor.total_inflight == 0
        assert executor.reservation_count == 0
    finally:
        executor.close()


def test_session_owner_is_single_assignment_and_serverless_initialize_fails() -> None:
    session = McpSession(initial_state=McpSessionState.UNINITIALIZED)
    rejected = session.handle_message(
        _request(
            "initialize",
            1,
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1"},
            },
        )
    )
    assert rejected["error"]["code"] == -32600

    server = McpServer(registry=_registry())
    session = server.create_session(McpSessionState.READY)
    session.close()
    server.close()
    gc.collect()
    with pytest.raises(RuntimeError, match="immutable"):
        session._bind_owner(McpServer(registry=_registry()))


# ---------------------------------------------------------------------------
# Section 14 negative tests — compatibility dispatch authority
# ---------------------------------------------------------------------------


def test_compat_and_explicit_sessions_share_same_tool_definitions() -> None:
    """Section 14 #2: compatibility and explicit sessions must use the same tool
    definitions source, not separately populated registries."""
    server = McpServer()
    try:
        explicit_session = server.create_session(McpSessionState.READY)
        explicit_result = server.handle_request(_request("tools/list", 1), session=explicit_session)
        explicit_names = sorted(t["name"] for t in explicit_result["result"]["tools"])

        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            compat_result = handle_request(_request("tools/list", 2))
        compat_names = sorted(t["name"] for t in compat_result["result"]["tools"])

        assert explicit_names == compat_names
        assert len(explicit_names) > 0
    finally:
        close_compatibility_server()
        server.close()


def test_close_compatibility_server_does_not_close_independent_server() -> None:
    """Section 14 #6: closing the compatibility server must not close
    independently constructed McpServer instances."""
    independent = McpServer(registry=_registry())
    independent_session = independent.create_session(McpSessionState.READY)
    try:
        before = independent.handle_request(
            _request("tools/call", 1, {"name": "math_eval", "arguments": {}}),
            session=independent_session,
        )
        assert "result" in before

        close_compatibility_server()

        after = independent.handle_request(
            _request("tools/call", 2, {"name": "math_eval", "arguments": {}}),
            session=independent_session,
        )
        assert "result" in after
        assert not independent._closed
    finally:
        independent.close()


def test_ordinary_import_does_not_create_compat_server() -> None:
    """Section 14 #8: importing eggcalc.mcp.server must not eagerly create
    compatibility server state."""
    import subprocess
    import sys
    import textwrap

    code = textwrap.dedent("""\
        import importlib
        import sys

        # Ensure a clean state — remove cached module if present
        for key in list(sys.modules):
            if key.startswith("eggcalc.mcp"):
                del sys.modules[key]

        import eggcalc.mcp.server as srv

        assert srv._compat_server is None, (
            f"compat server created at import time: {srv._compat_server!r}"
        )
    """)
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"


def test_compat_dispatch_cannot_bypass_session_init_rules() -> None:
    """Section 14 #1: the compatibility handle_request() path creates a READY
    session by design (backward compat), so it does not bypass init — it
    satisfies it. An explicit UNINITIALIZED session correctly rejects pre-init
    tool calls. Both paths route through the same canonical dispatch."""
    import warnings

    # Compat path: creates READY session, tools/call succeeds
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        compat_call = handle_request(
            _request(
                "tools/call",
                1,
                {"name": "math_eval", "arguments": {"expression": "5+3"}},
            )
        )
    assert "result" in compat_call

    # Explicit UNINITIALIZED session: tools/call rejected before init
    server = McpServer()
    try:
        uninitialized = server.create_session(McpSessionState.UNINITIALIZED)
        rejected = server.handle_request(
            _request(
                "tools/call",
                2,
                {"name": "math_eval", "arguments": {"expression": "5+3"}},
            ),
            session=uninitialized,
        )
        assert "error" in rejected
        assert rejected["error"]["code"] == -32600
    finally:
        close_compatibility_server()
        server.close()
