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

import itertools
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
        gen_counter = itertools.count(1)

        def _replace():
            try:
                barrier.wait(timeout=5)
                gen = next(gen_counter)
                mgr.replace(CS(generation=gen))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=_replace) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert len(errors) == 0
        final = mgr.current()
        assert isinstance(final.generation, int)
        assert final.generation == 10


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
        assert executor._closed is True
        with pytest.raises(RuntimeError, match="closed"):
            executor._get_executor()
        result = executor.call_tool("math_eval", {"expression": "1+1"})
        assert result["error"]["code"] == -32600

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


# ---------------------------------------------------------------------------
# TestConfigSnapshotUnits (Workstream F: units field)
# ---------------------------------------------------------------------------


class TestConfigSnapshotUnits:
    """ConfigSnapshot should carry units alongside constants/functions."""

    def test_config_snapshot_has_units_field(self):
        CS = _server_mod.ConfigSnapshot
        snap = CS(generation=1, units={"length": {"m": (1.0, "length")}})
        assert snap.units == {"length": {"m": (1.0, "length")}}

    def test_config_snapshot_units_default_empty(self):
        CS = _server_mod.ConfigSnapshot
        snap = CS()
        assert snap.units == {}

    def test_config_snapshot_units_immutable(self):
        CS = _server_mod.ConfigSnapshot
        snap = CS(units={"length": {"m": (1.0, "length")}})
        with pytest.raises(AttributeError):
            snap.units = {}  # type: ignore[misc]

    def test_config_manager_replace_with_units(self):
        CS = _server_mod.ConfigSnapshot
        CM = _server_mod.ConfigManager
        mgr = CM()
        snap = CS(generation=1, units={"length": {"m": (1.0, "length")}})
        mgr.replace(snap)
        assert mgr.current().units == {"length": {"m": (1.0, "length")}}


# ---------------------------------------------------------------------------
# TestEnhancedDiagnostics (Workstream J)
# ---------------------------------------------------------------------------


class TestEnhancedDiagnostics:
    """Diagnostics should include active workers, session count, orphans."""

    def test_diagnostic_has_active_workers(self):
        server = McpServer()
        diag = server.diagnostic()
        assert "active_workers" in diag
        assert diag["active_workers"] == 0
        server.close()

    def test_diagnostic_has_session_count(self):
        server = McpServer()
        diag = server.diagnostic()
        assert "session_count" in diag
        assert diag["session_count"] == 0
        session = server.create_session()
        diag = server.diagnostic()
        assert diag["session_count"] == 1
        server.close()

    def test_diagnostic_has_orphan_count(self):
        server = McpServer()
        diag = server.diagnostic()
        assert "orphan_count" in diag
        assert diag["orphan_count"] == 0
        server.close()

    def test_diagnostic_has_config_units_count(self):
        server = McpServer()
        diag = server.diagnostic()
        assert "config_units_count" in diag
        assert diag["config_units_count"] == 0
        server.close()

    def test_diagnostic_has_global_config_generation(self):
        server = McpServer()
        diag = server.diagnostic()
        assert "global_config_generation" in diag
        assert isinstance(diag["global_config_generation"], int)
        server.close()

    def test_diagnostic_deterministic(self):
        server = McpServer()
        d1 = server.diagnostic()
        d2 = server.diagnostic()
        assert d1 == d2
        server.close()

    def test_executor_active_workers_property(self):
        cfg = McpServerConfig(max_tool_workers=4)
        reg = ToolRegistry()
        executor = ToolExecutor(cfg, reg)
        assert executor.active_workers == 0
        executor.close()

    def test_executor_orphan_count_property(self):
        cfg = McpServerConfig()
        reg = ToolRegistry()
        executor = ToolExecutor(cfg, reg)
        assert executor.orphan_count == 0
        executor.close()


# ---------------------------------------------------------------------------
# TestConfigGeneration (Workstream G)
# ---------------------------------------------------------------------------


class TestConfigGeneration:
    """Config generation counter tracks cache invalidation."""

    def test_get_config_generation_returns_int(self):
        from eggcalc.evaluator import get_config_generation

        gen = get_config_generation()
        assert isinstance(gen, int)

    def test_clear_global_cache_increments_generation(self):
        from eggcalc.evaluator import _clear_global_cache, get_config_generation

        gen_before = get_config_generation()
        _clear_global_cache()
        gen_after = get_config_generation()
        assert gen_after == gen_before + 1


# ---------------------------------------------------------------------------
# TestConcurrencyStress (Workstream I: storms and saturation)
# ---------------------------------------------------------------------------


class TestConcurrencyStress:
    """Stress tests for concurrency bounds and storms."""

    def test_cancellation_storm(self):
        """Rapid cancellations do not leak or crash."""
        server = McpServer()
        session = _ready_session(server)
        for i in range(50):
            _session_request(
                session,
                "notifications/cancelled",
                {"requestId": f"cancel-{i}"},
            )
        result = _session_request(
            session,
            "tools/call",
            {"name": "math_eval", "arguments": {"expression": "1+1"}},
            request_id="after-storm",
        )
        assert "result" in result
        server.close()

    def test_repeated_timeout_does_not_exhaust_workers(self):
        """Repeated timeouts should not leave permanently blocked workers."""
        cfg = McpServerConfig(max_tool_timeout_seconds=1, max_tool_workers=2)
        reg = ToolRegistry(
            handlers={"always_slow": lambda **kw: time.sleep(100)},
            schemas={},
            metadata={},
            profiles={},
        )
        executor = ToolExecutor(cfg, reg)
        for i in range(5):
            result = executor.call_tool("always_slow", {}, request_id=f"t{i}")
            assert result["id"] == f"t{i}"
        # After timeouts, a fast tool should still work
        fast_reg = ToolRegistry(
            handlers={"fast": lambda **kw: {"ok": True}},
            schemas={},
            metadata={},
            profiles={},
        )
        fast_exec = ToolExecutor(McpServerConfig(max_tool_timeout_seconds=5), fast_reg)
        result = fast_exec.call_tool("fast", {}, request_id="f1")
        assert result["id"] == "f1"
        assert "result" in result
        executor.close()
        fast_exec.close()

    def test_multiple_sessions_concurrent_init(self):
        """Simultaneous initialization of many sessions."""
        server = McpServer()
        sessions = [server.create_session() for _ in range(10)]
        errors = []

        def _init(session, idx):
            try:
                handle_request(
                    {
                        "jsonrpc": "2.0",
                        "id": idx,
                        "method": "initialize",
                        "params": {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {},
                            "clientInfo": {"name": f"test-{idx}", "version": "0.1"},
                        },
                    },
                    session=session,
                )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=_init, args=(s, i)) for i, s in enumerate(sessions)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0
        for s in sessions:
            assert s.state in (McpSessionState.INITIALIZING, McpSessionState.READY)
        server.close()

    def test_close_with_no_active_work(self):
        """Close when no work has been submitted."""
        server = McpServer()
        server.close()
        assert server._closed is True
        assert server._executor._executor is None

    def test_malformed_traffic_isolated_between_sessions(self):
        """Malformed request in one session does not affect another."""
        server = McpServer()
        s1 = _ready_session(server)
        s2 = _ready_session(server)
        # Send malformed request to s1
        result = handle_request(
            {"jsonrpc": "2.0", "id": "bad", "method": 12345},
            session=s1,
        )
        assert result is not None
        assert "error" in result
        # s2 should still work
        result = _session_request(
            s2,
            "tools/call",
            {"name": "math_eval", "arguments": {"expression": "2+2"}},
            request_id="s2-ok",
        )
        assert "result" in result
        server.close()

    def test_two_servers_independent_config(self):
        """Two servers with different configs do not interfere."""
        CS = _server_mod.ConfigSnapshot
        s1 = McpServer()
        s2 = McpServer()
        snap1 = CS(generation=1, constants={"x": 10}, policy="a")
        snap2 = CS(generation=1, constants={"x": 20}, policy="b")
        s1.config_manager.replace(snap1)
        s2.config_manager.replace(snap2)
        assert s1.config_manager.current().policy == "a"
        assert s2.config_manager.current().policy == "b"
        assert s1.config_manager.current().constants == {"x": 10}
        assert s2.config_manager.current().constants == {"x": 20}
        s1.close()
        s2.close()


# ---------------------------------------------------------------------------
# TestSaturationRejection (Workstream I3)
# ---------------------------------------------------------------------------


class TestSaturationRejection:
    """Bounded queue saturation and backpressure."""

    def test_queue_full_rejects_new_requests(self):
        """When queue is full, new requests get rejected immediately."""
        hold = threading.Event()
        call_count = [0]
        count_lock = threading.Lock()

        def _blocker(**kw):
            with count_lock:
                call_count[0] += 1
            hold.wait(timeout=10)

        cfg = McpServerConfig(max_tool_workers=1, max_tool_queue_size=2)
        reg = ToolRegistry(
            handlers={"blocker": _blocker},
            schemas={},
            metadata={},
            profiles={},
        )
        executor = ToolExecutor(cfg, reg)
        max_inflight = cfg.max_tool_workers + cfg.max_tool_queue_size
        threads = [
            threading.Thread(target=lambda i=i: executor.call_tool("blocker", {}, request_id=i))
            for i in range(max_inflight)
        ]
        for t in threads:
            t.start()
        time.sleep(0.5)
        with count_lock:
            assert call_count[0] >= 1
        result = executor.call_tool("blocker", {}, request_id="rejected")
        assert "error" in result
        assert "busy" in result["error"]["message"].lower()
        hold.set()
        for t in threads:
            t.join(timeout=15)
        executor.close()

    def test_queue_rejects_then_recovers(self):
        """After rejection, requests succeed once queue drains."""
        cfg = McpServerConfig(max_tool_workers=1, max_tool_queue_size=1)
        hold = threading.Event()

        def _slow(**kw):
            hold.wait(timeout=10)

        reg = ToolRegistry(
            handlers={"slow": _slow, "fast": lambda **kw: {"ok": True}},
            schemas={},
            metadata={},
            profiles={},
        )
        executor = ToolExecutor(cfg, reg)
        max_inflight = cfg.max_tool_workers + cfg.max_tool_queue_size
        # Fill: 1 active + 1 queued = 2 in flight (= max)
        threads = [
            threading.Thread(target=lambda i=i: executor.call_tool("slow", {}, request_id=f"s{i}"))
            for i in range(max_inflight)
        ]
        for t in threads:
            t.start()
        time.sleep(0.5)
        result = executor.call_tool("fast", {}, request_id="c")
        assert "error" in result
        assert "busy" in result["error"]["message"].lower()
        hold.set()
        for t in threads:
            t.join(timeout=15)
        result = executor.call_tool("fast", {}, request_id="d")
        assert "result" in result
        executor.close()

    def test_queue_size_config_clamped(self):
        """max_tool_queue_size is clamped during construction."""
        cfg1 = McpServerConfig(max_tool_queue_size=0)
        assert cfg1.max_tool_queue_size == 1
        cfg2 = McpServerConfig(max_tool_queue_size=9999)
        assert cfg2.max_tool_queue_size == 1000
        cfg3 = McpServerConfig(max_tool_queue_size=50)
        assert cfg3.max_tool_queue_size == 50

    def test_diagnostic_includes_queue_info(self):
        """Diagnostic output includes queue size and pending count."""
        cfg = McpServerConfig(max_tool_workers=2, max_tool_queue_size=8)
        server = McpServer(config=cfg)
        diag = server.diagnostic()
        assert "max_tool_queue_size" in diag
        assert "pending_count" in diag
        assert diag["max_tool_queue_size"] == 8
        assert diag["pending_count"] == 0
        server.close()


# ---------------------------------------------------------------------------
# TestOversizedOutputStorm (Workstream I3)
# ---------------------------------------------------------------------------


class TestOversizedOutputStorm:
    """Repeated oversized outputs are truncated without corruption."""

    def test_oversized_output_truncated(self):
        """Output exceeding max_output_bytes returns truncation error."""
        big = "x" * 2_000_000
        reg = ToolRegistry(
            handlers={"big_out": lambda **kw: {"data": big}},
            schemas={},
            metadata={},
            profiles={},
        )
        executor = ToolExecutor(McpServerConfig(max_output_bytes=1000), reg)
        result = executor.call_tool("big_out", {}, request_id="big1")
        assert result["id"] == "big1"
        assert "result" in result
        assert result["result"]["isError"] is True
        assert "truncated" in result["result"]["content"][0]["text"].lower()
        executor.close()

    def test_oversized_output_storm_no_corruption(self):
        """Repeated oversized outputs do not corrupt subsequent normal results."""
        big = "y" * 2_000_000
        reg = ToolRegistry(
            handlers={
                "big_out": lambda **kw: {"data": big},
                "normal": lambda **kw: {"ok": True, "val": 42},
            },
            schemas={},
            metadata={},
            profiles={},
        )
        executor = ToolExecutor(McpServerConfig(max_output_bytes=1000), reg)
        for i in range(5):
            result = executor.call_tool("big_out", {}, request_id=f"big-{i}")
            assert result["result"]["isError"] is True
        # Normal tool still works correctly after oversized outputs
        result = executor.call_tool("normal", {}, request_id="norm1")
        assert "result" in result
        assert result["result"].get("isError") is not True
        import json

        payload = json.loads(result["result"]["content"][0]["text"])
        assert payload["val"] == 42
        executor.close()


# ---------------------------------------------------------------------------
# Corrective closure pass tests (Workstreams B, C3, D, E2, G, H)
# ---------------------------------------------------------------------------


class TestWorkstreamB_ConfigAuthority:
    """Workstream B: every McpServerConfig field is enforced or removed."""

    def test_custom_protocol_versions_negotiated_independently(self):
        """Two servers with different protocol versions negotiate differently."""
        s1 = McpServer(
            config=McpServerConfig(
                supported_protocol_versions=("2024-11-05",),
            )
        )
        s2 = McpServer(
            config=McpServerConfig(
                supported_protocol_versions=("2024-11-05", "2025-11-25"),
            )
        )
        try:
            init_req = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1"},
                },
            }
            r1 = s1.handle_request(init_req)
            r2 = s2.handle_request(init_req)
            # s1 only supports 2024-11-05, so it falls back to that
            assert r1["result"]["protocolVersion"] == "2024-11-05"
            # s2 supports 2025-11-25, so it negotiates it
            assert r2["result"]["protocolVersion"] == "2025-11-25"
        finally:
            s1.close()
            s2.close()

    def test_max_request_id_length_enforced(self):
        """Request ID exceeding max_request_id_length is rejected."""
        s = McpServer(config=McpServerConfig(max_request_id_length=64))
        try:
            long_id = "x" * 65
            result = s.handle_request({"jsonrpc": "2.0", "id": long_id, "method": "ping"})
            assert result is not None
            assert "error" in result
        finally:
            s.close()

    def test_max_request_id_length_accepts_valid(self):
        """Request ID within max_request_id_length is accepted."""
        s = McpServer(config=McpServerConfig(max_request_id_length=64))
        try:
            result = s.handle_request({"jsonrpc": "2.0", "id": "short", "method": "ping"})
            assert result is not None
            assert "result" in result
        finally:
            s.close()

    def test_two_servers_independent_config(self):
        """Two servers with conflicting configs operate independently."""
        s1 = McpServer(config=McpServerConfig(profile="full"))
        s2 = McpServer(config=McpServerConfig(profile="default"))
        try:
            sess1 = s1.create_session()
            sess2 = s2.create_session()
            init_req = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1"},
                },
            }
            s1.handle_request(init_req, session=sess1)
            s2.handle_request(init_req, session=sess2)
            s1.handle_request(
                {"jsonrpc": "2.0", "id": 2, "method": "notifications/initialized"}, session=sess1
            )
            s2.handle_request(
                {"jsonrpc": "2.0", "id": 2, "method": "notifications/initialized"}, session=sess2
            )

            r1 = s1.handle_request(
                {"jsonrpc": "2.0", "id": 3, "method": "tools/list"}, session=sess1
            )
            r2 = s2.handle_request(
                {"jsonrpc": "2.0", "id": 3, "method": "tools/list"}, session=sess2
            )
            assert len(r1["result"]["tools"]) >= len(r2["result"]["tools"])
        finally:
            s1.close()
            s2.close()


class TestWorkstreamC3_RegistryImmutability:
    """Workstream C3: ToolRegistry data cannot be mutated externally."""

    def test_handlers_is_mapping_proxy(self):
        from types import MappingProxyType

        reg = ToolRegistry()
        assert isinstance(reg.handlers, MappingProxyType)

    def test_schemas_is_mapping_proxy(self):
        from types import MappingProxyType

        reg = ToolRegistry()
        assert isinstance(reg.schemas, MappingProxyType)

    def test_metadata_is_mapping_proxy(self):
        from types import MappingProxyType

        reg = ToolRegistry()
        assert isinstance(reg.metadata, MappingProxyType)

    def test_profiles_is_mapping_proxy(self):
        from types import MappingProxyType

        reg = ToolRegistry()
        assert isinstance(reg.profiles, MappingProxyType)

    def test_external_mutation_rejected(self):
        """Attempting to mutate the returned mappings raises TypeError."""
        reg = ToolRegistry()
        with pytest.raises(TypeError):
            reg.handlers["new_tool"] = lambda **kw: None  # type: ignore[misc]
        with pytest.raises(TypeError):
            reg.schemas["new_tool"] = {}  # type: ignore[misc]
        with pytest.raises(TypeError):
            reg.metadata["new_tool"] = {}  # type: ignore[misc]
        with pytest.raises(TypeError):
            reg.profiles["new_profile"] = []  # type: ignore[misc]


class TestWorkstreamD_EvaluatorBinding:
    """Workstream D: MCP math execution uses server-owned evaluator."""

    def test_server_evaluator_rejects_random(self):
        """Server with allow_random=False rejects random functions via math_eval."""
        server = McpServer(config=McpServerConfig(allow_random=False))
        try:
            session = server.create_session()
            init_req = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1"},
                },
            }
            server.handle_request(init_req, session=session)
            server.handle_request(
                {"jsonrpc": "2.0", "id": 2, "method": "notifications/initialized"}, session=session
            )
            result = server.handle_request(
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {"name": "math_eval", "arguments": {"expression": "randint(1,10)"}},
                },
                session=session,
            )
            assert result is not None
            assert result["result"]["isError"] is True
        finally:
            server.close()

    def test_two_servers_independent_evaluator_policy(self):
        """Two servers with opposite evaluator policies remain independent."""
        s_restrict = McpServer(config=McpServerConfig(allow_random=False))
        s_permit = McpServer(config=McpServerConfig(allow_random=True))
        try:
            sess_r = s_restrict.create_session()
            sess_p = s_permit.create_session()
            init_req = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1"},
                },
            }
            for s, sess in ((s_restrict, sess_r), (s_permit, sess_p)):
                s.handle_request(init_req, session=sess)
                s.handle_request(
                    {"jsonrpc": "2.0", "id": 2, "method": "notifications/initialized"}, session=sess
                )

            r1 = s_restrict.handle_request(
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {"name": "math_eval", "arguments": {"expression": "randint(1,10)"}},
                },
                session=sess_r,
            )
            r2 = s_permit.handle_request(
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {"name": "math_eval", "arguments": {"expression": "randint(1,10)"}},
                },
                session=sess_p,
            )
            assert r1["result"]["isError"] is True
            assert r2["result"].get("isError") is not True
        finally:
            s_restrict.close()
            s_permit.close()

    def test_default_evaluator_unchanged_after_server_creation(self):
        """Creating servers does not alter the default evaluator policy."""
        from eggcalc.evaluator import _default_evaluator

        orig_random = _default_evaluator._allow_random
        orig_se = _default_evaluator._allow_side_effects
        try:
            _ = McpServer(config=McpServerConfig(allow_random=False, allow_side_effects=False))
            assert _default_evaluator._allow_random == orig_random
            assert _default_evaluator._allow_side_effects == orig_se
        finally:
            _default_evaluator._allow_random = orig_random
            _default_evaluator._allow_side_effects = orig_se

    def test_server_evaluator_is_separate_instance(self):
        """Server evaluator is a different object from the global default."""
        from eggcalc.evaluator import _default_evaluator

        server = McpServer()
        try:
            assert server.evaluator is not _default_evaluator
        finally:
            server.close()


class TestWorkstreamE2_ConfigManagerValidation:
    """Workstream E2: ConfigManager.replace() validates generation."""

    def test_replace_rejects_stale_generation(self):
        CS = _server_mod.ConfigSnapshot
        CM = _server_mod.ConfigManager
        mgr = CM()
        mgr.replace(CS(generation=5))
        with pytest.raises(ValueError, match="must be greater"):
            mgr.replace(CS(generation=5))

    def test_replace_rejects_decreasing_generation(self):
        CS = _server_mod.ConfigSnapshot
        CM = _server_mod.ConfigManager
        mgr = CM()
        mgr.replace(CS(generation=10))
        with pytest.raises(ValueError, match="must be greater"):
            mgr.replace(CS(generation=3))

    def test_generation_increases_monotonically(self):
        CS = _server_mod.ConfigSnapshot
        CM = _server_mod.ConfigManager
        mgr = CM()
        for i in range(1, 6):
            gen = mgr.replace(CS(generation=i))
            assert gen == i
        assert mgr.current().generation == 5

    def test_failed_replace_preserves_prior(self):
        CS = _server_mod.ConfigSnapshot
        CM = _server_mod.ConfigManager
        mgr = CM()
        mgr.replace(CS(generation=3, constants={"pi": 3.14}))
        with pytest.raises(ValueError):
            mgr.replace(CS(generation=2))
        assert mgr.current().constants == {"pi": 3.14}
        assert mgr.current().generation == 3


class TestWorkstreamG_ExecutorAccounting:
    """Workstream G: executor accounting, closed-state, lifecycle."""

    def test_closed_executor_rejects_get_executor(self):
        executor = ToolExecutor(McpServerConfig(), ToolRegistry())
        executor.close()
        with pytest.raises(RuntimeError, match="closed"):
            executor._get_executor()

    def test_closed_executor_rejects_call_tool(self):
        executor = ToolExecutor(McpServerConfig(), ToolRegistry())
        executor.close()
        result = executor.call_tool("math_eval", {"expression": "1+1"})
        assert result["error"]["code"] == -32600

    def test_timeout_worker_retains_capacity(self):
        """After timeout, capacity is released only when the future completes."""
        import threading as _threading

        barrier = _threading.Barrier(2)
        slow_handler = lambda **kw: (barrier.wait(timeout=30), 42)[1]
        reg = ToolRegistry(
            handlers={"slow": slow_handler},
            schemas={"slow": {"inputSchema": {"type": "object", "properties": {}}}},
            metadata={"slow": {"llm_exposure": "full"}},
            profiles={"full": ["slow"]},
        )
        executor = ToolExecutor(
            McpServerConfig(max_tool_timeout_seconds=1, max_tool_workers=1, max_tool_queue_size=0),
            reg,
        )
        try:
            # First call will time out
            result = executor.call_tool("slow", {}, request_id="t1")
            assert "error" not in result or result["result"].get("error_type") == "timeout"
            # Wait for the worker to actually finish
            barrier.wait(timeout=10)
            # Now capacity should be recovered
            result2 = executor.call_tool("slow", {}, request_id="t2")
            assert "error" not in result2 or result2.get("error") is None
        finally:
            executor.close()

    def test_server_close_transitions_sessions(self):
        """Server close transitions all owned sessions to CLOSED state."""
        server = McpServer()
        s1 = server.create_session()
        s2 = server.create_session()
        assert s1.state != McpSessionState.CLOSED
        assert s2.state != McpSessionState.CLOSED
        server.close()
        assert s1.state == McpSessionState.CLOSED
        assert s2.state == McpSessionState.CLOSED

    def test_server_close_is_idempotent(self):
        server = McpServer()
        server.close()
        server.close()  # Should not raise
        assert server._closed is True

    def test_request_after_server_close_rejected(self):
        server = McpServer()
        server.close()
        result = server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "ping"})
        assert result is not None
        assert "error" in result
        assert result["error"]["code"] == -32600
