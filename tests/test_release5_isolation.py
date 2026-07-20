"""Tests for Release 5 state isolation and concurrency hardening.

Covers:
- McpServerConfig: defaults, env loading, immutability, validation
- ToolRegistry: handler ownership, profiles, close-matching
- ToolExecutor: tool dispatch, timeout, unknown tool, shutdown
- ConfigSnapshot / ConfigManager: atomic replacement, generation tracking (via _server_mod to handle reload)
- McpServer: creation, sessions, isolation, close semantics
- EvaluatorPolicyIsolation: per-server evaluator independence (Workstream D)
- MultiSessionIsolation: session lifecycle independence (Workstream H)
- Concurrency: parallel execution, worker bounds, thread safety (Workstream I)
- Shutdown: resource reclamation, idempotent close (Workstream I)
"""

from __future__ import annotations

import os
import threading
import time
from unittest.mock import patch

import pytest

os.environ.setdefault("EGGCALC_NO_CONFIG", "1")

from eggcalc.evaluator import (
    EvaluationError,
    Evaluator,
    create_evaluator,
    get_default_evaluator,
)
from eggcalc.mcp import server as _server_mod
from eggcalc.mcp.server import (
    TOOL_HANDLERS,
    McpServer,
    McpServerConfig,
    McpSession,
    McpSessionState,
    ToolExecutor,
    ToolRegistry,
    handle_request,
)

# Access ConfigSnapshot/ConfigManager through the module object to handle
# importlib.reload() in other test modules (test_mcp_env_limits.py).

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ready_session(server: McpServer | None = None) -> McpSession:
    """Create a session and complete the handshake to READY state."""
    session = McpSession(initial_state=McpSessionState.UNINITIALIZED)
    handle_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "0.1.0"},
            },
        },
        session=session,
    )
    handle_request(
        {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
        session=session,
    )
    return session


def _session_request(session: McpSession, method: str, params: dict | None = None, request_id=1):
    """Send a JSON-RPC request through a session."""
    return handle_request(
        {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}},
        session=session,
    )


# ---------------------------------------------------------------------------
# TestMcpServerConfig
# ---------------------------------------------------------------------------


class TestMcpServerConfig:
    """McpServerConfig: immutable config dataclass with validation."""

    def test_config_defaults(self):
        cfg = McpServerConfig()
        assert cfg.profile == "full"
        assert cfg.schema_detail == "full"
        assert cfg.max_request_bytes == 1_000_000
        assert cfg.max_output_bytes == 1_000_000
        assert cfg.max_requests_per_second == 10.0
        assert cfg.max_request_id_length == 1024
        assert cfg.max_tool_timeout_seconds == 30
        assert cfg.max_cancelled_requests == 10_000
        assert cfg.max_tool_workers == 16
        assert cfg.allow_random is False
        assert cfg.allow_side_effects is False
        assert cfg.supported_protocol_versions == ("2024-11-05", "2025-11-25")

    def test_config_from_environment(self):
        env = {
            "EGGCALC_MCP_PROFILE": "default",
            "EGGCALC_MCP_SCHEMA_DETAIL": "compact",
            "EGGCALC_MCP_MAX_REQUEST_BYTES": "2000000",
            "EGGCALC_MCP_MAX_OUTPUT_BYTES": "500000",
            "EGGCALC_MCP_MAX_REQUESTS_PER_SECOND": "20",
            "EGGCALC_MCP_MAX_TOOL_TIMEOUT_SECONDS": "15",
            "EGGCALC_MCP_MAX_CANCELLED_REQUESTS": "5000",
            "EGGCALC_MCP_MAX_TOOL_WORKERS": "8",
        }
        with patch.dict(os.environ, env, clear=False):
            cfg = McpServerConfig.from_environment()
        assert cfg.profile == "default"
        assert cfg.schema_detail == "compact"
        assert cfg.max_request_bytes == 2_000_000
        assert cfg.max_output_bytes == 500_000
        assert cfg.max_requests_per_second == 20.0
        assert cfg.max_tool_timeout_seconds == 15
        assert cfg.max_cancelled_requests == 5_000
        assert cfg.max_tool_workers == 8

    def test_config_immutable(self):
        cfg = McpServerConfig()
        with pytest.raises(AttributeError):
            cfg.profile = "modified"  # type: ignore[misc]

    def test_config_validation_clamps_values(self):
        cfg = McpServerConfig(
            max_request_bytes=100,  # below min 1000
            max_output_bytes=999_999_999,  # above max 100M
            max_requests_per_second=0.01,  # below min 0.1
            max_request_id_length=10,  # below min 64
            max_tool_timeout_seconds=0,  # below min 1
            max_cancelled_requests=10,  # below min 100
            max_tool_workers=0,  # below min 1
        )
        assert cfg.max_request_bytes == 1000
        assert cfg.max_output_bytes == 100_000_000
        assert cfg.max_requests_per_second == 0.1
        assert cfg.max_request_id_length == 64
        assert cfg.max_tool_timeout_seconds == 1
        assert cfg.max_cancelled_requests == 100
        assert cfg.max_tool_workers == 1

    def test_config_rejects_unknown_profile(self):
        with pytest.raises(ValueError, match="Unknown profile"):
            McpServerConfig(profile="nonexistent_profile_xyz")

    def test_config_rejects_invalid_schema_detail(self):
        with pytest.raises(ValueError, match="Invalid schema detail"):
            McpServerConfig(schema_detail="invalid")

    def test_config_from_environment_with_explicit_values(self):
        env = {
            "EGGCALC_MCP_PROFILE": "default",
            "EGGCALC_MCP_SCHEMA_DETAIL": "compact",
        }
        with patch.dict(os.environ, env, clear=False):
            cfg = McpServerConfig(profile="full", schema_detail="full")
        assert cfg.profile == "full"
        assert cfg.schema_detail == "full"

    def test_config_latest_protocol_version(self):
        cfg = McpServerConfig()
        assert cfg.latest_protocol_version == "2025-11-25"


# ---------------------------------------------------------------------------
# TestToolRegistry
# ---------------------------------------------------------------------------


class TestToolRegistry:
    """ToolRegistry: ownership of tool definitions, profiles, matching."""

    def test_registry_uses_global_handlers_by_default(self):
        reg = ToolRegistry()
        assert reg.handlers is not TOOL_HANDLERS
        assert reg.handlers.keys() == TOOL_HANDLERS.keys()

    def test_registry_custom_handlers(self):
        custom = {"my_tool": lambda **kw: None}
        reg = ToolRegistry(handlers=custom, schemas={}, metadata={}, profiles={})
        assert reg.handlers == custom
        assert reg.tool_names == ["my_tool"]

    def test_registry_has_tool(self):
        reg = ToolRegistry()
        assert reg.has_tool("math_eval") is True
        assert reg.has_tool("nonexistent_tool") is False

    def test_registry_get_handler(self):
        reg = ToolRegistry()
        handler = reg.get_handler("math_eval")
        assert handler is not None
        assert callable(handler)
        assert reg.get_handler("nonexistent_tool") is None

    def test_registry_tool_names(self):
        reg = ToolRegistry()
        names = reg.tool_names
        assert isinstance(names, list)
        assert names == sorted(names)
        assert len(names) == len(TOOL_HANDLERS)

    def test_registry_find_close_match(self):
        reg = ToolRegistry()
        match = reg.find_close_match("math_evil")
        assert match is not None
        assert reg.has_tool(match)

    def test_registry_find_close_match_no_match(self):
        reg = ToolRegistry(
            handlers={"foo": lambda **kw: None}, schemas={}, metadata={}, profiles={}
        )
        assert reg.find_close_match("zzzzzzzzzzz") is None

    def test_registry_get_profile_tools(self):
        reg = ToolRegistry()
        default_tools = reg.get_profile_tools("default")
        assert isinstance(default_tools, list)
        assert len(default_tools) > 0
        for name in default_tools:
            assert reg.has_tool(name)

    def test_registry_get_profile_tools_full(self):
        reg = ToolRegistry()
        full_tools = reg.get_profile_tools("full")
        assert len(full_tools) > 0
        for name in full_tools:
            meta = reg.get_metadata(name)
            assert meta.get("llm_exposure") != "hidden"

    def test_registry_get_profile_tools_unknown_raises(self):
        reg = ToolRegistry()
        with pytest.raises(ValueError, match="Unknown profile"):
            reg.get_profile_tools("no_such_profile")

    def test_registry_get_schema(self):
        reg = ToolRegistry()
        schema = reg.get_schema("math_eval")
        assert schema is not None
        assert "inputSchema" in schema

    def test_registry_get_metadata(self):
        reg = ToolRegistry()
        meta = reg.get_metadata("math_eval")
        assert isinstance(meta, dict)

    def test_registry_get_metadata_unknown(self):
        reg = ToolRegistry()
        meta = reg.get_metadata("nonexistent_tool")
        assert meta == {}


# ---------------------------------------------------------------------------
# TestToolExecutor
# ---------------------------------------------------------------------------


class TestToolExecutor:
    """ToolExecutor: dispatch, timeout, unknown tool, shutdown."""

    def _make_executor(self, **config_kwargs) -> ToolExecutor:
        cfg = McpServerConfig(**config_kwargs)
        reg = ToolRegistry()
        return ToolExecutor(cfg, reg)

    def test_executor_call_tool(self):
        executor = self._make_executor()
        result = executor.call_tool("math_eval", {"expression": "2 + 2"}, request_id="r1")
        assert result["id"] == "r1"
        assert "result" in result
        assert result["result"]["content"][0]["text"] is not None

    def test_executor_call_tool_timeout(self):
        executor = self._make_executor(max_tool_timeout_seconds=1)

        def _slow(**kw):
            time.sleep(10)

        registry = ToolRegistry(
            handlers={"slow_tool": _slow},
            schemas={},
            metadata={},
            profiles={},
        )
        executor_slow = ToolExecutor(McpServerConfig(max_tool_timeout_seconds=1), registry)
        result = executor_slow.call_tool("slow_tool", {}, request_id="t1")
        assert result["id"] == "t1"
        assert "result" in result
        inner = result["result"]["content"][0]["text"]
        assert "timeout" in inner.lower() or result["result"].get("isError") is True

    def test_executor_call_tool_unknown(self):
        executor = self._make_executor()
        result = executor.call_tool("nonexistent_tool_xyz", {}, request_id="u1")
        assert result["id"] == "u1"
        assert "error" in result
        assert result["error"]["code"] == -32601

    def test_executor_close(self):
        executor = self._make_executor()
        _ = executor._get_executor()
        executor.close()
        assert executor._executor is None

    def test_executor_close_without_use(self):
        executor = self._make_executor()
        executor.close()
        assert executor._executor is None

    def test_executor_custom_config(self):
        executor = self._make_executor(max_tool_timeout_seconds=5, max_tool_workers=4)
        assert executor._config.max_tool_timeout_seconds == 5
        assert executor._config.max_tool_workers == 4


# ---------------------------------------------------------------------------
# TestConfigSnapshot
# ---------------------------------------------------------------------------


class TestConfigSnapshot:
    """ConfigSnapshot: immutable snapshot for atomic replacement."""

    def test_snapshot_defaults(self):
        CS = _server_mod.ConfigSnapshot
        snap = CS()
        assert snap.generation == 0
        assert snap.constants == {}
        assert snap.functions == {}
        assert snap.policy == "default"

    def test_snapshot_immutable(self):
        CS = _server_mod.ConfigSnapshot
        snap = CS()
        with pytest.raises(AttributeError):
            snap.generation = 1  # type: ignore[misc]
        with pytest.raises(AttributeError):
            snap.policy = "modified"  # type: ignore[misc]

    def test_snapshot_custom_values(self):
        CS = _server_mod.ConfigSnapshot
        snap = CS(generation=42, policy="custom")
        assert snap.generation == 42
        assert snap.policy == "custom"


# ---------------------------------------------------------------------------
# TestConfigManager
# ---------------------------------------------------------------------------


class TestConfigManager:
    """ConfigManager: thread-safe atomic config replacement."""

    def test_manager_current_returns_snapshot(self):
        CS = _server_mod.ConfigSnapshot
        CM = _server_mod.ConfigManager
        mgr = CM()
        snap = mgr.current()
        assert isinstance(snap, CS)
        assert snap.generation == 0

    def test_manager_replace(self):
        CS = _server_mod.ConfigSnapshot
        CM = _server_mod.ConfigManager
        mgr = CM()
        new_snap = CS(generation=1, policy="new")
        mgr.replace(new_snap)
        assert mgr.current().policy == "new"
        assert mgr.current().generation == 1

    def test_manager_replace_increments_generation(self):
        CS = _server_mod.ConfigSnapshot
        CM = _server_mod.ConfigManager
        mgr = CM()
        for i in range(1, 6):
            mgr.replace(CS(generation=i))
        assert mgr.current().generation == 5

    def test_manager_invalidate(self):
        CS = _server_mod.ConfigSnapshot
        CM = _server_mod.ConfigManager
        mgr = CM()
        mgr.replace(CS(generation=10))
        mgr.invalidate()
        assert mgr.current().generation == 11
        assert mgr.current().constants == {}
        assert mgr.current().functions == {}

    def test_manager_invalidate_from_default(self):
        CM = _server_mod.ConfigManager
        mgr = CM()
        mgr.invalidate()
        assert mgr.current().generation == 1


# ---------------------------------------------------------------------------
# TestMcpServer
# ---------------------------------------------------------------------------


class TestMcpServer:
    """McpServer: creation, sessions, isolation, close semantics."""

    def test_server_creates_with_defaults(self):
        server = McpServer()
        assert server.config.profile == "full"
        assert server.registry is not None
        assert server.config_manager is not None
        server.close()

    def test_server_creates_with_custom_config(self):
        cfg = McpServerConfig(profile="default", max_tool_workers=4)
        server = McpServer(config=cfg)
        assert server.config.profile == "default"
        assert server.config.max_tool_workers == 4
        server.close()

    def test_server_creates_session(self):
        server = McpServer()
        session = server.create_session()
        assert isinstance(session, McpSession)
        assert session.state == McpSessionState.UNINITIALIZED
        server.close()

    def test_server_multiple_instances_isolated(self):
        cfg_a = McpServerConfig(profile="default")
        cfg_b = McpServerConfig(max_tool_workers=4)
        server_a = McpServer(config=cfg_a)
        server_b = McpServer(config=cfg_b)
        assert server_a.config.profile == "default"
        assert server_b.config.max_tool_workers == 4
        assert server_a is not server_b
        server_a.close()
        server_b.close()

    def test_server_close(self):
        server = McpServer()
        server.close()
        assert server._closed is True

    def test_server_close_idempotent(self):
        server = McpServer()
        server.close()
        server.close()
        server.close()
        assert server._closed is True

    def test_server_handle_request_after_close(self):
        server = McpServer()
        server.close()
        result = server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {}})
        assert result is not None
        assert "error" in result

    def test_server_diagnostic(self):
        server = McpServer()
        diag = server.diagnostic()
        assert isinstance(diag, dict)
        assert diag["profile"] == "full"
        assert diag["closed"] is False
        assert isinstance(diag["config_generation"], int)
        assert isinstance(diag["registry_tool_count"], int)
        assert diag["registry_tool_count"] == len(TOOL_HANDLERS)
        server.close()

    def test_server_has_evaluator(self):
        server = McpServer()
        assert isinstance(server.evaluator, Evaluator)
        server.close()

    def test_server_has_config_manager(self):
        CS = _server_mod.ConfigSnapshot
        CM = _server_mod.ConfigManager
        server = McpServer()
        assert isinstance(server.config_manager, CM)
        snap = server.config_manager.current()
        assert isinstance(snap, CS)
        server.close()


# ---------------------------------------------------------------------------
# TestEvaluatorPolicyIsolation (Workstream D)
# ---------------------------------------------------------------------------


class TestEvaluatorPolicyIsolation:
    """Workstream D: per-server evaluator isolation."""

    def test_ordinary_evaluator_allows_random(self):
        ev = create_evaluator(allow_random=True)
        assert ev._allow_random is True

    def test_mcp_evaluator_rejects_random(self):
        ev = create_evaluator(allow_random=False)
        with pytest.raises(EvaluationError):
            ev.evaluate("random()")

    def test_two_evaluators_independent(self):
        ev_a = create_evaluator(allow_random=False)
        ev_b = create_evaluator(allow_random=True)
        assert ev_a._allow_random is False
        assert ev_b._allow_random is True

    def test_server_evaluator_does_not_affect_default(self):
        default_ev = get_default_evaluator()
        old_random = default_ev._allow_random
        old_side = default_ev._allow_side_effects
        try:
            server = McpServer(config=McpServerConfig(allow_random=True))
            assert server.evaluator._allow_random is True
            assert default_ev._allow_random == old_random
            assert default_ev._allow_side_effects == old_side
        finally:
            server.close()

    def test_default_evaluator_survives_server_creation(self):
        default_ev = get_default_evaluator()
        before_id = id(default_ev)
        server = McpServer()
        after_ev = get_default_evaluator()
        assert id(after_ev) == before_id
        server.close()

    def test_server_evaluator_is_separate_instance(self):
        default_ev = get_default_evaluator()
        server = McpServer()
        assert server.evaluator is not default_ev
        server.close()

    def test_server_evaluator_policy_from_config(self):
        cfg = McpServerConfig(allow_random=False, allow_side_effects=False)
        server = McpServer(config=cfg)
        assert server.evaluator._allow_random is False
        assert server.evaluator._allow_side_effects is False
        server.close()

    def test_server_evaluator_rejects_setvar(self):
        cfg = McpServerConfig(allow_side_effects=False)
        server = McpServer(config=cfg)
        with pytest.raises(EvaluationError):
            server.evaluator.evaluate('setvar("x", 1)')
        server.close()

    def test_default_evaluator_may_allow_random(self):
        default_ev = get_default_evaluator()
        if default_ev._allow_random:
            result = default_ev.evaluate("random()")
            assert isinstance(result, float)
            assert 0.0 <= result <= 1.0


# ---------------------------------------------------------------------------
# TestMultiSessionIsolation (Workstream H)
# ---------------------------------------------------------------------------


class TestMultiSessionIsolation:
    """Workstream H: sessions are fully independent."""

    def test_two_sessions_independent_cancellation(self):
        s1 = McpSession(initial_state=McpSessionState.READY)
        s2 = McpSession(initial_state=McpSessionState.READY)
        s1._cancelled_requests.add(42)
        assert 42 in s1._cancelled_requests
        assert 42 not in s2._cancelled_requests

    def test_two_sessions_independent_lifecycle(self):
        s1 = McpSession(initial_state=McpSessionState.UNINITIALIZED)
        s2 = McpSession(initial_state=McpSessionState.UNINITIALIZED)
        _session_request(
            s1,
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "a", "version": "1"},
            },
        )
        _session_request(s1, "notifications/initialized", {})
        assert s1.state == McpSessionState.READY
        assert s2.state == McpSessionState.UNINITIALIZED

    def test_sessions_with_same_request_ids(self):
        s1 = McpSession(initial_state=McpSessionState.READY)
        s2 = McpSession(initial_state=McpSessionState.READY)
        r1 = _session_request(s1, "ping", request_id=100)
        r2 = _session_request(s2, "ping", request_id=100)
        assert r1["id"] == 100
        assert r2["id"] == 100

    def test_session_close_does_not_affect_other(self):
        s1 = McpSession(initial_state=McpSessionState.READY)
        s2 = McpSession(initial_state=McpSessionState.READY)
        s1.state = McpSessionState.CLOSED
        assert s2.state == McpSessionState.READY

    def test_two_sessions_separate_cancelled_sets(self):
        s1 = McpSession(initial_state=McpSessionState.READY)
        s2 = McpSession(initial_state=McpSessionState.READY)
        s1._cancelled_requests.add("req_a")
        s2._cancelled_requests.add("req_b")
        assert "req_a" in s1._cancelled_requests
        assert "req_a" not in s2._cancelled_requests
        assert "req_b" in s2._cancelled_requests
        assert "req_b" not in s1._cancelled_requests


# ---------------------------------------------------------------------------
# TestConcurrency (Workstream I)
# ---------------------------------------------------------------------------


class TestConcurrency:
    """Workstream I: parallel execution and thread safety."""

    def test_concurrent_tool_execution(self):
        executor = ToolExecutor(
            McpServerConfig(max_tool_workers=8),
            ToolRegistry(),
        )
        results = [None] * 20
        errors = []

        def _call(i):
            try:
                results[i] = executor.call_tool(
                    "math_eval", {"expression": f"{i} + {i}"}, request_id=i
                )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=_call, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert len(errors) == 0
        for i, result in enumerate(results):
            assert result is not None
            assert result["id"] == i
            assert "result" in result
        executor.close()

    def test_concurrent_session_tool_calls(self):
        server = McpServer()
        sessions = [_ready_session(server) for _ in range(4)]
        results = {}
        errors = []

        def _call_tool(sess_idx, tool_name, expr):
            try:
                r = _session_request(
                    sessions[sess_idx],
                    "tools/call",
                    {"name": tool_name, "arguments": {"expression": expr}},
                    request_id=sess_idx * 1000 + hash(expr) % 1000,
                )
                results[(sess_idx, expr)] = r
            except Exception as e:
                errors.append(e)

        threads = []
        for si in range(4):
            for expr in ["1+1", "2+2", "3+3"]:
                threads.append(threading.Thread(target=_call_tool, args=(si, "math_eval", expr)))
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert len(errors) == 0
        assert len(results) == 12
        for key, res in results.items():
            assert "result" in res or "error" in res
        server.close()

    def test_worker_pool_bounds(self):
        max_workers = 4
        cfg = McpServerConfig(max_tool_workers=max_workers)
        started = threading.Event()
        hold = threading.Event()
        active_count = [0]
        peak_count = [0]
        count_lock = threading.Lock()

        def _blocking(**kw):
            with count_lock:
                active_count[0] += 1
                peak_count[0] = max(peak_count[0], active_count[0])
            started.set()
            hold.wait(timeout=10)
            with count_lock:
                active_count[0] -= 1

        reg = ToolRegistry(
            handlers={"blocker": _blocking},
            schemas={},
            metadata={},
            profiles={},
        )
        bounded = ToolExecutor(cfg, reg)

        futures = []
        pool = bounded._get_executor()
        for i in range(max_workers + 2):
            fut = pool.submit(_blocking)
            futures.append(fut)

        started.wait(timeout=5)
        hold.set()
        for f in futures:
            f.result(timeout=10)

        assert peak_count[0] <= max_workers
        bounded.close()

    def test_concurrent_server_creation(self):
        servers = []
        errors = []

        def _create():
            try:
                servers.append(McpServer())
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=_create) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert len(errors) == 0
        assert len(servers) == 8
        for s in servers:
            assert isinstance(s, McpServer)
            s.close()

    def test_concurrent_config_replacement(self):
        CS = _server_mod.ConfigSnapshot
        CM = _server_mod.ConfigManager
        mgr = CM()
        barrier = threading.Barrier(10)
        errors = []

        def _replace(gen):
            try:
                barrier.wait(timeout=5)
                mgr.replace(CS(generation=gen))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=_replace, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert len(errors) == 0
        final = mgr.current()
        assert isinstance(final.generation, int)


# ---------------------------------------------------------------------------
# TestShutdown (Workstream I)
# ---------------------------------------------------------------------------


class TestShutdown:
    """Workstream I: resource reclamation and safe shutdown."""

    def test_shutdown_reclaims_workers(self):
        server = McpServer()
        session = _ready_session(server)
        _session_request(
            session,
            "tools/call",
            {
                "name": "math_eval",
                "arguments": {"expression": "1+1"},
            },
        )
        server.close()
        assert server._closed is True
        assert server._executor._executor is None

    def test_shutdown_idempotent(self):
        server = McpServer()
        server.close()
        server.close()
        server.close()
        assert server._closed is True

    def test_post_close_requests_rejected(self):
        server = McpServer()
        server.close()
        result = server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {}})
        assert result is not None
        assert "error" in result
        assert result["error"]["code"] == -32600

    def test_executor_shutdown_and_reopen(self):
        executor = ToolExecutor(McpServerConfig(), ToolRegistry())
        exec1 = executor._get_executor()
        executor.close()
        assert executor._executor is None
        exec2 = executor._get_executor()
        assert exec2 is not None
        assert exec2 is not exec1
        executor.close()

    def test_close_cleans_up_all_servers(self):
        servers = [McpServer() for _ in range(5)]
        for s in servers:
            s.close()
        for s in servers:
            assert s._closed is True
            assert s._executor._executor is None


# ---------------------------------------------------------------------------
# TestProtocolLifecycle (bonus: session lifecycle with server)
# ---------------------------------------------------------------------------


class TestProtocolLifecycle:
    """End-to-end session lifecycle through McpServer."""

    def test_full_handshake_and_tool_call(self):
        server = McpServer()
        session = server.create_session()
        result = _session_request(
            session,
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"},
            },
        )
        assert "result" in result
        _session_request(session, "notifications/initialized")
        assert session.state == McpSessionState.READY
        result = _session_request(
            session,
            "tools/call",
            {
                "name": "math_eval",
                "arguments": {"expression": "10 * 5"},
            },
        )
        assert "result" in result
        assert "result" in result
        server.close()

    def test_tools_list_through_server(self):
        server = McpServer()
        session = _ready_session(server)
        result = _session_request(session, "tools/list")
        assert "result" in result
        assert "tools" in result["result"]
        assert len(result["result"]["tools"]) > 0
        server.close()

    def test_profiles_list_through_server(self):
        server = McpServer()
        session = _ready_session(server)
        result = _session_request(session, "profiles/list")
        assert "result" in result
        assert "profiles" in result["result"]
        server.close()
