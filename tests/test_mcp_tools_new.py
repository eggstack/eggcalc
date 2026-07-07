"""Integration tests for text_replace_check, line_range_extract, line_range_compare MCP tools."""

import json

from eggcalc.mcp.server import TOOL_HANDLERS, handle_request


class TestTextReplaceCheckMCP:
    """Test text_replace_check via MCP protocol."""

    def test_basic_replace_check(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "text_replace_check",
                    "arguments": {"text": "hello world", "old": "world", "new": "earth"},
                },
            }
        )
        content = json.loads(response["result"]["content"][0]["text"])
        assert content["ok"] is True
        assert content["result"]["match_count"] == 1
        assert content["result"]["would_change"] is True

    def test_no_match(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "text_replace_check",
                    "arguments": {"text": "hello", "old": "xyz", "new": "abc"},
                },
            }
        )
        content = json.loads(response["result"]["content"][0]["text"])
        assert content["ok"] is True
        assert content["result"]["match_count"] == 0
        assert content["result"]["would_change"] is False

    def test_casefold_mode(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "text_replace_check",
                    "arguments": {
                        "text": "Hello World",
                        "old": "world",
                        "new": "earth",
                        "mode": "casefold",
                    },
                },
            }
        )
        content = json.loads(response["result"]["content"][0]["text"])
        assert content["ok"] is True
        assert content["result"]["match_count"] == 1

    def test_ambiguous_replacement(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "text_replace_check",
                    "arguments": {
                        "text": "aaa bbb aaa",
                        "old": "aaa",
                        "new": "xxx",
                        "allow_multiple": False,
                    },
                },
            }
        )
        content = json.loads(response["result"]["content"][0]["text"])
        assert content["ok"] is True
        assert content["result"]["match_count"] == 2
        assert any(f["kind"] == "ambiguous_replacement" for f in content["result"]["findings"])

    def test_preview(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "text_replace_check",
                    "arguments": {
                        "text": "hello world",
                        "old": "world",
                        "new": "earth",
                        "return_preview": True,
                    },
                },
            }
        )
        content = json.loads(response["result"]["content"][0]["text"])
        assert content["ok"] is True
        assert content["result"]["preview_before"] == "hello world"
        assert content["result"]["preview_after"] == "hello earth"

    def test_invalid_mode(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "text_replace_check",
                    "arguments": {"text": "hello", "old": "lo", "new": "x", "mode": "invalid"},
                },
            }
        )
        assert "error" in response

    def test_input_too_large(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "text_replace_check",
                    "arguments": {"text": "a" * 100001, "old": "a", "new": "b"},
                },
            }
        )
        assert "result" in response
        assert response["result"]["isError"] is True


class TestLineRangeExtractMCP:
    """Test line_range_extract via MCP protocol."""

    def test_basic_extract(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "line_range_extract",
                    "arguments": {"text": "line1\nline2\nline3", "start_line": 1, "end_line": 2},
                },
            }
        )
        content = json.loads(response["result"]["content"][0]["text"])
        assert content["ok"] is True
        assert content["result"]["text"] == "line1\nline2"
        assert content["result"]["line_count_total"] == 3
        assert content["result"]["valid_range"] is True

    def test_out_of_range(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "line_range_extract",
                    "arguments": {"text": "line1\nline2", "start_line": 5, "end_line": 5},
                },
            }
        )
        content = json.loads(response["result"]["content"][0]["text"])
        assert content["ok"] is True
        assert content["result"]["valid_range"] is False

    def test_include_line_numbers(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "line_range_extract",
                    "arguments": {
                        "text": "aaa\nbbb\nccc",
                        "start_line": 1,
                        "end_line": 3,
                        "include_line_numbers": True,
                    },
                },
            }
        )
        content = json.loads(response["result"]["content"][0]["text"])
        assert content["ok"] is True
        assert content["result"]["lines"][0]["line"] == 1
        assert content["result"]["lines"][2]["line"] == 3

    def test_invalid_range(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "line_range_extract",
                    "arguments": {"text": "hello", "start_line": 3, "end_line": 1},
                },
            }
        )
        assert "result" in response
        assert response["result"]["isError"] is True

    def test_input_too_large(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "line_range_extract",
                    "arguments": {"text": "a" * 100001, "start_line": 1, "end_line": 1},
                },
            }
        )
        assert "result" in response
        assert response["result"]["isError"] is True


class TestLineRangeCompareMCP:
    """Test line_range_compare via MCP protocol."""

    def test_equal_compare(self):
        text = "aaa\nbbb\nccc"
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "line_range_compare",
                    "arguments": {
                        "left_text": text,
                        "right_text": text,
                        "start_line": 1,
                        "end_line": 2,
                    },
                },
            }
        )
        content = json.loads(response["result"]["content"][0]["text"])
        assert content["ok"] is True
        assert content["result"]["equal"] is True

    def test_different_compare(self):
        left = "aaa\nbbb\nccc"
        right = "aaa\nBBB\nccc"
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "line_range_compare",
                    "arguments": {
                        "left_text": left,
                        "right_text": right,
                        "start_line": 2,
                        "end_line": 2,
                    },
                },
            }
        )
        content = json.loads(response["result"]["content"][0]["text"])
        assert content["ok"] is True
        assert content["result"]["equal"] is False
        assert content["result"]["first_difference"] is not None

    def test_trailing_whitespace_mode(self):
        left = "hello  \nworld"
        right = "hello\nworld"
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "line_range_compare",
                    "arguments": {
                        "left_text": left,
                        "right_text": right,
                        "start_line": 1,
                        "end_line": 1,
                        "comparison_mode": "ignore_trailing_whitespace",
                    },
                },
            }
        )
        content = json.loads(response["result"]["content"][0]["text"])
        assert content["ok"] is True
        assert content["result"]["equal"] is True

    def test_invalid_mode(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "line_range_compare",
                    "arguments": {
                        "left_text": "a",
                        "right_text": "a",
                        "start_line": 1,
                        "end_line": 1,
                        "comparison_mode": "invalid",
                    },
                },
            }
        )
        assert "error" in response

    def test_input_too_large(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "line_range_compare",
                    "arguments": {
                        "left_text": "a" * 100001,
                        "right_text": "a" * 100001,
                        "start_line": 1,
                        "end_line": 1,
                    },
                },
            }
        )
        assert "result" in response
        assert response["result"]["isError"] is True


class TestToolRegistry:
    """Verify new tools are in the registry."""

    def test_text_replace_check_in_handlers(self):
        assert "text_replace_check" in TOOL_HANDLERS

    def test_line_range_extract_in_handlers(self):
        assert "line_range_extract" in TOOL_HANDLERS

    def test_line_range_compare_in_handlers(self):
        assert "line_range_compare" in TOOL_HANDLERS

    def test_toml_shape_in_handlers(self):
        assert "toml_shape" in TOOL_HANDLERS

    def test_version_compare_in_handlers(self):
        assert "version_compare" in TOOL_HANDLERS

    def test_all_handlers_callable(self):
        for name in [
            "text_replace_check",
            "line_range_extract",
            "line_range_compare",
            "toml_shape",
            "version_compare",
        ]:
            assert callable(TOOL_HANDLERS[name])


class TestConstantLookupMCP:
    """Test constant_lookup via MCP protocol."""

    def test_valid_constant(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "constant_lookup",
                    "arguments": {"name": "avogadro"},
                },
            }
        )
        content = json.loads(response["result"]["content"][0]["text"])
        assert content["ok"] is True
        assert content["result"]["value"] == 6.02214076e23
        assert content["result"]["symbol"] == "N_A"

    def test_case_insensitive(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "constant_lookup",
                    "arguments": {"name": "AVOGADRO"},
                },
            }
        )
        content = json.loads(response["result"]["content"][0]["text"])
        assert content["ok"] is True

    def test_non_string_name_returns_error(self):
        """Schema validation catches non-string name before handler."""
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "constant_lookup",
                    "arguments": {"name": 123},
                },
            }
        )
        assert "error" in response
        assert "must be string" in response["error"]["message"]

    def test_none_name_returns_error(self):
        """Schema validation catches None name before handler."""
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "constant_lookup",
                    "arguments": {"name": None},
                },
            }
        )
        assert "error" in response
        assert "must be string" in response["error"]["message"]

    def test_unknown_constant(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "constant_lookup",
                    "arguments": {"name": "nonexistent"},
                },
            }
        )
        assert "result" in response
        assert response["result"]["isError"] is True

    def test_missing_name_argument(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "constant_lookup",
                    "arguments": {},
                },
            }
        )
        assert "error" in response
        assert "Missing required argument" in response["error"]["message"]

    def test_direct_call_non_string(self):
        """Direct handler call with non-string should return error envelope."""
        from eggcalc.mcp.tools import constant_lookup

        result = constant_lookup(123)
        assert result["ok"] is False
        assert "must be a string" in result["error"]

    def test_direct_call_none(self):
        """Direct handler call with None should return error envelope."""
        from eggcalc.mcp.tools import constant_lookup

        result = constant_lookup(None)
        assert result["ok"] is False
        assert "must be a string" in result["error"]

    def test_all_aliases(self):
        """Test all aliases for a constant return the same value."""
        aliases = ["na", "avogadro", "avogadros"]
        values = set()
        for alias in aliases:
            response = handle_request(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": "constant_lookup",
                        "arguments": {"name": alias},
                    },
                }
            )
            content = json.loads(response["result"]["content"][0]["text"])
            values.add(content["result"]["value"])
        assert len(values) == 1


class TestTomlShapeMCP:
    """Test toml_shape via MCP protocol."""

    def test_basic_toml_shape(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "toml_shape",
                    "arguments": {"text": "[a]\nb = 1\n\n[c]\nd = 2"},
                },
            }
        )
        content = json.loads(response["result"]["content"][0]["text"])
        assert content["ok"] is True
        assert content["result"]["valid"] is True
        assert len(content["result"]["top_level_keys"]) == 2
        assert len(content["result"]["tables"]) >= 2
        assert content["result"]["truncated"] is False

    def test_empty_toml(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "toml_shape",
                    "arguments": {"text": ""},
                },
            }
        )
        content = json.loads(response["result"]["content"][0]["text"])
        assert content["ok"] is True
        assert content["result"]["valid"] is True
        assert content["result"]["top_level_keys"] == []
        assert content["result"]["tables"] == []

    def test_invalid_toml(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "toml_shape",
                    "arguments": {"text": "[invalid = [[["},
                },
            }
        )
        content = json.loads(response["result"]["content"][0]["text"])
        assert content["ok"] is True
        assert content["result"]["valid"] is False

    def test_summary_detail(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "toml_shape",
                    "arguments": {"text": "[a]\nb = 1", "detail": "summary"},
                },
            }
        )
        content = json.loads(response["result"]["content"][0]["text"])
        assert content["ok"] is True
        assert "valid" in content["result"]
        assert "summary" in content["result"]
        assert "truncated" in content["result"]
        assert "top_level_keys" not in content["result"]
        assert "tables" not in content["result"]


class TestVersionCompareMCP:
    """Test version_compare via MCP protocol."""

    def test_basic_equal(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "version_compare",
                    "arguments": {"a": "1.0.0", "b": "1.0.0"},
                },
            }
        )
        content = json.loads(response["result"]["content"][0]["text"])
        assert content["ok"] is True
        assert content["result"]["comparison"] == 0
        assert content["result"]["valid"] is True
        assert content["result"]["scheme"] == "semver"

    def test_basic_less(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "version_compare",
                    "arguments": {"a": "1.0.0", "b": "2.0.0"},
                },
            }
        )
        content = json.loads(response["result"]["content"][0]["text"])
        assert content["ok"] is True
        assert content["result"]["comparison"] == -1
        assert content["result"]["valid"] is True

    def test_basic_greater(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "version_compare",
                    "arguments": {"a": "2.0.0", "b": "1.0.0"},
                },
            }
        )
        content = json.loads(response["result"]["content"][0]["text"])
        assert content["ok"] is True
        assert content["result"]["comparison"] == 1
        assert content["result"]["valid"] is True

    def test_invalid_scheme(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "version_compare",
                    "arguments": {"a": "1.0.0", "b": "1.0.0", "scheme": "invalid"},
                },
            }
        )
        assert "error" in response

    def test_pep440_scheme(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "version_compare",
                    "arguments": {"a": "1.0.0", "b": "2.0.0", "scheme": "pep440"},
                },
            }
        )
        assert "error" in response
