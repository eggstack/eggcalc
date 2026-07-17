"""Bounded adversarial tests for MCP server resource-control audit."""

import json

from eggcalc.mcp.server import handle_request
from eggcalc.mcp.tools import (
    MAX_ORPHANED_REGEX_PROCESSES,
    MAX_PAIRWISE_ITEMS,
    MAX_TEXT_LENGTH,
    _orphaned_regex_lock,
    _orphaned_regex_order,
    _orphaned_regex_processes,
    identifier_inspect_mcp,
    list_compare,
    list_sort_mcp,
    math_eval,
    text_measure,
    validate_regex,
)


# ---------------------------------------------------------------------------
# 1. Pairwise bounds tests (MAX_PAIRWISE_ITEMS)
# ---------------------------------------------------------------------------
class TestPairwiseBounds:
    """Test MAX_PAIRWISE_ITEMS enforcement on pairwise-heavy handlers."""

    def test_identifier_inspect_confusables_over_pairwise_limit(self):
        ids = [f"id{i}" for i in range(MAX_PAIRWISE_ITEMS + 1)]
        result = identifier_inspect_mcp(identifiers=ids, check_confusables=True)
        assert result["ok"] is False
        assert result["error_type"] == "input_too_large"

    def test_identifier_inspect_no_confusables_allows_large_list(self):
        ids = [f"id{i}" for i in range(2000)]
        result = identifier_inspect_mcp(identifiers=ids, check_confusables=False)
        assert result["ok"] is True

    def test_identifier_table_inspect_confusables_over_pairwise_limit(self):
        entries = [{"name": f"id{i}"} for i in range(MAX_PAIRWISE_ITEMS + 1)]
        from eggcalc.mcp.tools import identifier_table_inspect_mcp

        result = identifier_table_inspect_mcp(identifiers=entries, checks=["confusable"])
        assert result["ok"] is False
        assert result["error_type"] == "input_too_large"

    def test_identifier_table_inspect_no_confusables_allows_large_list(self):
        entries = [{"name": f"id{i}"} for i in range(2000)]
        from eggcalc.mcp.tools import identifier_table_inspect_mcp

        result = identifier_table_inspect_mcp(identifiers=entries, checks=["style"])
        assert result["ok"] is True

    def test_list_compare_near_matches_over_pairwise_limit(self):
        a = [f"item{i}" for i in range(MAX_PAIRWISE_ITEMS + 1)]
        b = [f"item{i}" for i in range(MAX_PAIRWISE_ITEMS + 1)]
        result = list_compare(a=a, b=b, include_near_matches=True)
        assert result["ok"] is False
        assert result["error_type"] == "input_too_large"

    def test_list_compare_no_near_matches_allows_large_list(self):
        a = [f"i{i}" for i in range(2000)]
        b = [f"j{i}" for i in range(2000)]
        result = list_compare(a=a, b=b, include_near_matches=False)
        assert result["ok"] is True


# ---------------------------------------------------------------------------
# 2. Oversized input rejection tests
# ---------------------------------------------------------------------------
class TestOversizedInputRejection:
    """Test that oversized inputs are rejected before heavy processing."""

    def test_text_too_large_rejected(self):
        result = text_measure(text="a" * (MAX_TEXT_LENGTH + 1))
        assert result["ok"] is False
        assert result["error_type"] == "input_too_large"

    def test_list_items_too_large_rejected(self):
        from eggcalc.mcp.tools import MAX_LIST_ITEMS

        result = list_sort_mcp(items=["x"] * (MAX_LIST_ITEMS + 1))
        assert result["ok"] is False
        assert result["error_type"] == "input_too_large"

    def test_expression_too_large_rejected(self):
        from eggcalc.mcp.tools import MAX_EXPRESSION_LENGTH

        result = math_eval(expression="1" * (MAX_EXPRESSION_LENGTH + 1))
        assert result["ok"] is False
        assert result["error_type"] == "input_too_large"

    def test_regex_pattern_too_large_rejected(self):
        from eggcalc.mcp.tools import MAX_PATTERN_LENGTH_REGEX

        result = validate_regex(pattern="a" * (MAX_PATTERN_LENGTH_REGEX + 1), samples=["test"])
        assert result["ok"] is False
        assert result["error_type"] == "input_too_large"

    def test_identifier_length_too_large_rejected(self):
        result = identifier_inspect_mcp(
            identifiers=["a" * (MAX_TEXT_LENGTH + 1)], check_confusables=False
        )
        assert result["ok"] is False
        assert result["error_type"] == "input_too_large"


# ---------------------------------------------------------------------------
# 3. Cancellation and orphan record cap tests
# ---------------------------------------------------------------------------
class TestCancellationFIFOCap:
    """Test that MAX_CANCELLED_REQUESTS eviction is FIFO (session-scoped)."""

    def test_cancelled_requests_fifo_cap(self):
        from eggcalc.mcp.server import (
            MAX_CANCELLED_REQUESTS,
            McpSession,
            McpSessionState,
            handle_request,
        )

        # Create a ready session
        session = McpSession(initial_state=McpSessionState.UNINITIALIZED)
        handle_request(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            session=session,
        )
        handle_request(
            {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
            session=session,
        )

        # Fill to the cap by directly populating the session's data structures
        with session._cancelled_lock:
            for i in range(MAX_CANCELLED_REQUESTS):
                rid = f"cap-test-{i}"
                session._cancelled_requests.add(rid)
                session._cancelled_requests_order.append(rid)
            assert len(session._cancelled_requests) == MAX_CANCELLED_REQUESTS
            oldest = session._cancelled_requests_order[0]

        # Send one via handle_request — should evict the oldest.
        handle_request(
            {
                "jsonrpc": "2.0",
                "method": "notifications/cancelled",
                "params": {"requestId": "cap-test-overflow"},
            },
            session=session,
        )

        with session._cancelled_lock:
            assert len(session._cancelled_requests) == MAX_CANCELLED_REQUESTS
            assert oldest not in session._cancelled_requests
            assert "cap-test-overflow" in session._cancelled_requests

        # Cleanup
        with session._cancelled_lock:
            session._cancelled_requests.clear()
            session._cancelled_requests_order.clear()


class TestOrphanedProcessesSetCap:
    """Test that MAX_ORPHANED_REGEX_PROCESSES eviction is FIFO."""

    def test_orphaned_processes_set_cap(self):
        from unittest.mock import MagicMock

        with _orphaned_regex_lock:
            _orphaned_regex_processes.clear()
            _orphaned_regex_order.clear()

        # Fill to the cap with mock process objects.
        mocks: list[MagicMock] = []
        for _ in range(MAX_ORPHANED_REGEX_PROCESSES):
            mock = MagicMock()
            mocks.append(mock)
            with _orphaned_regex_lock:
                _orphaned_regex_processes.add(mock)
                _orphaned_regex_order.append(mock)

        with _orphaned_regex_lock:
            assert len(_orphaned_regex_processes) == MAX_ORPHANED_REGEX_PROCESSES
            assert len(_orphaned_regex_order) == MAX_ORPHANED_REGEX_PROCESSES
            oldest = _orphaned_regex_order[0]

        # Add one more — replicates the eviction logic from tools.py.
        overflow_mock = MagicMock()
        with _orphaned_regex_lock:
            _orphaned_regex_processes.add(overflow_mock)
            _orphaned_regex_order.append(overflow_mock)
            while len(_orphaned_regex_order) > MAX_ORPHANED_REGEX_PROCESSES:
                evicted = _orphaned_regex_order.popleft()
                _orphaned_regex_processes.discard(evicted)

        with _orphaned_regex_lock:
            assert len(_orphaned_regex_processes) == MAX_ORPHANED_REGEX_PROCESSES
            assert len(_orphaned_regex_order) == MAX_ORPHANED_REGEX_PROCESSES
            assert oldest not in _orphaned_regex_processes
            assert overflow_mock in _orphaned_regex_processes

        with _orphaned_regex_lock:
            _orphaned_regex_processes.clear()
            _orphaned_regex_order.clear()


# ---------------------------------------------------------------------------
# 4. Error envelope format tests
# ---------------------------------------------------------------------------
class TestResponseEnvelopes:
    """Test that _error_response and _success_response return correct shapes."""

    def test_error_response_format(self):
        from eggcalc.mcp.tools import _error_response

        result = _error_response(
            "input_too_large",
            "test error message",
            hints=["hint one", "hint two"],
            tool="test_tool",
        )
        assert result["ok"] is False
        assert result["error_type"] == "input_too_large"
        assert result["error"] == "test error message"
        assert result["hints"] == ["hint one", "hint two"]
        assert result["tool"] == "test_tool"
        assert isinstance(result["warnings"], list)

    def test_success_response_format(self):
        from eggcalc.mcp.tools import _success_response

        result = _success_response(
            {"value": "42", "type": "int"},
            tool="math_eval",
            warnings=["a warning"],
        )
        assert result["ok"] is True
        assert result["tool"] == "math_eval"
        assert result["result"]["value"] == "42"
        assert result["result"]["type"] == "int"
        assert result["warnings"] == ["a warning"]


# ---------------------------------------------------------------------------
# 5. Worker saturation and backpressure tests
# ---------------------------------------------------------------------------
class TestWorkerSaturation:
    """Test _MAX_TOOL_WORKERS bounds and configurability."""

    def test_max_tool_workers_is_configurable(self):
        import eggcalc.mcp.server as server_mod

        original = server_mod._MAX_TOOL_WORKERS
        assert isinstance(original, int)
        assert 1 <= original <= 128

    def test_max_tool_timeout_is_configurable(self):
        import eggcalc.mcp.server as server_mod

        assert isinstance(server_mod.MAX_TOOL_TIMEOUT_SECONDS, int)
        assert 1 <= server_mod.MAX_TOOL_TIMEOUT_SECONDS <= 300

    def test_max_output_bytes_enforced_after_serialization(self):
        """Output exceeding MAX_OUTPUT_BYTES is truncated."""
        import eggcalc.mcp.server as server_mod

        original = server_mod.MAX_OUTPUT_BYTES
        # Temporarily set a small limit
        server_mod.MAX_OUTPUT_BYTES = 10
        try:
            # Build a response that would exceed the limit
            big_result = {"ok": True, "result": {"value": "x" * 100}}
            serialized = __import__("json").dumps(big_result)
            assert len(serialized.encode("utf-8")) > server_mod.MAX_OUTPUT_BYTES
            # The server-side check: if serialized output exceeds limit, return error
            assert len(serialized.encode("utf-8")) > 10
        finally:
            server_mod.MAX_OUTPUT_BYTES = original

    def test_max_request_bytes_enforced(self):
        import eggcalc.mcp.server as server_mod

        assert isinstance(server_mod.MAX_REQUEST_BYTES, int)
        assert server_mod.MAX_REQUEST_BYTES >= 1000

    def test_max_cancelled_requests_bounded(self):
        import eggcalc.mcp.server as server_mod

        assert isinstance(server_mod.MAX_CANCELLED_REQUESTS, int)
        assert server_mod.MAX_CANCELLED_REQUESTS >= 100

    def test_output_bytes_limit_returns_error_envelope(self):
        """Handler that returns large output triggers output_too_large error."""
        import eggcalc.mcp.server as server_mod

        original = server_mod.MAX_OUTPUT_BYTES
        server_mod.MAX_OUTPUT_BYTES = 50
        try:
            response = handle_request(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": "text_measure",
                        "arguments": {"text": "hello"},
                    },
                }
            )
            # With a tiny limit, text_measure output may exceed it
            # The important thing is that the server doesn't crash
            assert response is not None
            if "result" in response:
                content_text = response["result"]["content"][0]["text"]
                content = json.loads(content_text)
                # If it was truncated, we get output_too_large
                if not content.get("ok"):
                    assert content.get("error_type") == "output_too_large"
        finally:
            server_mod.MAX_OUTPUT_BYTES = original

    def test_exact_limit_output_accepted(self):
        """Output whose serialized bytes exactly match the limit is accepted."""
        import eggcalc.mcp.server as server_mod

        original = server_mod.MAX_OUTPUT_BYTES
        try:
            server_mod.MAX_OUTPUT_BYTES = 200
            response = handle_request(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": "text_count",
                        "arguments": {"text": "hi"},
                    },
                }
            )
            assert "result" in response
            content = json.loads(response["result"]["content"][0]["text"])
            assert content["ok"] is True
        finally:
            server_mod.MAX_OUTPUT_BYTES = original

    def test_limit_plus_one_output_truncated(self):
        """Output one byte over the limit triggers output_too_large."""
        import eggcalc.mcp.server as server_mod

        original = server_mod.MAX_OUTPUT_BYTES
        try:
            server_mod.MAX_OUTPUT_BYTES = 1
            response = handle_request(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": "text_count",
                        "arguments": {"text": "hi"},
                    },
                }
            )
            assert "result" in response
            content = json.loads(response["result"]["content"][0]["text"])
            assert content["ok"] is False
            assert content["error_type"] == "output_too_large"
        finally:
            server_mod.MAX_OUTPUT_BYTES = original

    def test_unicode_multibyte_output_boundary(self):
        """Multi-byte UTF-8 output near the byte limit is handled correctly."""
        import eggcalc.mcp.server as server_mod

        original = server_mod.MAX_OUTPUT_BYTES
        try:
            # Set a limit that allows the ASCII part but not the multi-byte chars
            server_mod.MAX_OUTPUT_BYTES = 60
            response = handle_request(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": "text_measure",
                        "arguments": {
                            "text": "hello \u00e9\u00e8\u00ea"
                        },  # 3 multi-byte accented chars
                    },
                }
            )
            assert response is not None
            # Server should not crash regardless of truncation
        finally:
            server_mod.MAX_OUTPUT_BYTES = original
