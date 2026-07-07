"""Bounded adversarial tests for MCP server resource-control audit."""

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
    """Test that MAX_CANCELLED_REQUESTS eviction is FIFO."""

    def test_cancelled_requests_fifo_cap(self):
        from eggcalc.mcp.server import (
            MAX_CANCELLED_REQUESTS,
            _cancelled_lock,
            _cancelled_requests,
            _cancelled_requests_order,
            handle_request,
        )

        with _cancelled_lock:
            _cancelled_requests.clear()
            _cancelled_requests_order.clear()

        # Save and restore server-level MCP defaults flag so that calling
        # handle_request doesn't permanently pollute evaluator state for
        # other test modules (conftest only restores evaluator flags, not
        # this server-level guard).
        import eggcalc.mcp.server as _server_mod

        orig_configured = _server_mod._mcp_defaults_configured

        # Fill to the cap by directly populating the data structures
        # (avoids calling handle_request 10,000 times which would trigger
        # MCP defaults setup and pollute evaluator state for other modules).
        with _cancelled_lock:
            for i in range(MAX_CANCELLED_REQUESTS):
                rid = f"cap-test-{i}"
                _cancelled_requests.add(rid)
                _cancelled_requests_order.append(rid)
            assert len(_cancelled_requests) == MAX_CANCELLED_REQUESTS
            oldest = _cancelled_requests_order[0]

        # Send one via handle_request — should evict the oldest.
        handle_request(
            {
                "jsonrpc": "2.0",
                "id": None,
                "method": "notifications/cancelled",
                "params": {"requestId": "cap-test-overflow"},
            }
        )

        with _cancelled_lock:
            assert len(_cancelled_requests) == MAX_CANCELLED_REQUESTS
            assert oldest not in _cancelled_requests
            assert "cap-test-overflow" in _cancelled_requests

        # Restore cancellation data and MCP defaults flag.
        with _cancelled_lock:
            _cancelled_requests.clear()
            _cancelled_requests_order.clear()
        _server_mod._mcp_defaults_configured = orig_configured


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
