"""Tests for Phase 5 MCP tools: llm_json_output_check, markdown_link_check_lexical, repo_file_inventory."""

import json

from eggcalc.exact.llm_hygiene import llm_json_output_check
from eggcalc.exact.markdown import markdown_link_check_lexical
from eggcalc.exact.repo_audit import repo_file_inventory
from eggcalc.mcp.server import handle_request

# =============================================================================
# llm_json_output_check tests
# =============================================================================


class TestLlmJsonOutputCheck:
    """Test llm_json_output_check core function."""

    def test_plain_valid_json(self):
        result = llm_json_output_check('{"key": "value"}')
        assert result["parse_ok"] is True
        assert result["has_fence"] is False
        assert result["leading_prose"] is False
        assert result["trailing_prose"] is False
        assert result["has_bom"] is False
        assert result["extracted_content"] is None

    def test_fenced_json(self):
        text = '```json\n{"key": "value"}\n```'
        result = llm_json_output_check(text)
        assert result["parse_ok"] is True
        assert result["has_fence"] is True
        assert result["fence_language"] == "json"
        assert result["extracted_content"] == '{"key": "value"}'

    def test_fenced_json_no_language(self):
        text = '```\n{"key": "value"}\n```'
        result = llm_json_output_check(text)
        assert result["parse_ok"] is True
        assert result["has_fence"] is True
        assert result["fence_language"] == ""

    def test_leading_prose(self):
        text = 'Here is the result: {"key": "value"}'
        result = llm_json_output_check(text)
        assert result["parse_ok"] is True
        assert result["leading_prose"] is True

    def test_trailing_prose(self):
        text = '{"key": "value"}\n\nLet me know if you need more.'
        result = llm_json_output_check(text)
        assert result["parse_ok"] is True
        assert result["trailing_prose"] is True

    def test_invalid_json_trailing_comma(self):
        text = '{"key": "value",}'
        result = llm_json_output_check(text)
        assert result["parse_ok"] is False
        assert result["error_line"] is not None
        assert any(h["code"] == "TRAILING_COMMA" for h in result["fix_hints"])

    def test_bom_prefix(self):
        text = '\ufeff{"key": "value"}'
        result = llm_json_output_check(text)
        assert result["has_bom"] is True
        assert result["parse_ok"] is True

    def test_empty_input(self):
        result = llm_json_output_check("")
        assert result["parse_ok"] is False

    def test_multiple_json_objects(self):
        text = '{"a": 1}{"b": 2}'
        result = llm_json_output_check(text)
        assert result["multiple_json_objects"] is True

    def test_input_too_long(self):
        text = "x" * 500_001
        result = llm_json_output_check(text)
        assert result["parse_ok"] is False
        assert "exceeds" in result["error_message"]

    def test_not_a_string(self):
        result = llm_json_output_check(123)
        assert result["parse_ok"] is False

    def test_valid_array(self):
        result = llm_json_output_check('[1, 2, 3]')
        assert result["parse_ok"] is True

    def test_valid_string(self):
        result = llm_json_output_check('"hello"')
        assert result["parse_ok"] is True


class TestLlmJsonOutputCheckMCP:
    """Test llm_json_output_check via MCP protocol."""

    def test_mcp_valid_json(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "llm_json_output_check",
                    "arguments": {"text": '{"key": "value"}'},
                },
            }
        )
        content = json.loads(response["result"]["content"][0]["text"])
        assert content["ok"] is True
        assert content["result"]["parse_ok"] is True

    def test_mcp_fenced_json(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "llm_json_output_check",
                    "arguments": {"text": '```json\n{"key": "value"}\n```'},
                },
            }
        )
        content = json.loads(response["result"]["content"][0]["text"])
        assert content["ok"] is True
        assert content["result"]["has_fence"] is True

    def test_mcp_invalid_json(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "llm_json_output_check",
                    "arguments": {"text": '{"key": "value",}'},
                },
            }
        )
        content = json.loads(response["result"]["content"][0]["text"])
        assert content["ok"] is True
        assert content["result"]["parse_ok"] is False

    def test_mcp_missing_text(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "llm_json_output_check",
                    "arguments": {},
                },
            }
        )
        assert "error" in response


# =============================================================================
# markdown_link_check_lexical tests
# =============================================================================


class TestMarkdownLinkCheckLexical:
    """Test markdown_link_check_lexical core function."""

    def test_valid_links(self):
        text = "[Google](https://google.com) and [repo](./README.md)"
        result = markdown_link_check_lexical(text)
        assert result["total_links"] == 2
        assert result["external_count"] == 1

    def test_image_link(self):
        text = "![logo](image.png)"
        result = markdown_link_check_lexical(text)
        assert result["total_links"] == 1
        assert result["image_count"] == 1

    def test_malformed_link_empty_url(self):
        text = "[text]()"
        result = markdown_link_check_lexical(text)
        assert result["total_links"] == 1
        assert len(result["malformed"]) > 0

    def test_duplicate_anchors(self):
        text = "# Heading\n# Heading\n[link](#heading)"
        result = markdown_link_check_lexical(text)
        assert len(result["duplicate_anchors"]) > 0

    def test_unresolved_relative(self):
        text = "[docs](./docs/missing.md)"
        result = markdown_link_check_lexical(text, known_paths=["./README.md"])
        assert len(result["unresolved_relatives"]) == 1
        assert result["unresolved_relatives"][0]["target"] == "./docs/missing.md"

    def test_resolved_relative(self):
        text = "[docs](./docs/guide.md)"
        result = markdown_link_check_lexical(text, known_paths=["./docs/guide.md"])
        assert len(result["unresolved_relatives"]) == 0

    def test_empty_input(self):
        result = markdown_link_check_lexical("")
        assert result["total_links"] == 0

    def test_no_links(self):
        result = markdown_link_check_lexical("Just some text.")
        assert result["total_links"] == 0

    def test_reference_style_link(self):
        text = "[text][ref]\n\n[ref]: http://example.com"
        result = markdown_link_check_lexical(text)
        assert result["total_links"] >= 1

    def test_input_too_long(self):
        text = "x" * 500_001
        result = markdown_link_check_lexical(text)
        assert result["total_links"] == 0

    def test_not_a_string(self):
        result = markdown_link_check_lexical(123)
        assert result["total_links"] == 0

    def test_code_fence_ignored(self):
        text = "```\n[not a link](http://example.com)\n```"
        result = markdown_link_check_lexical(text)
        assert result["total_links"] == 0

    def test_multiple_external_links(self):
        text = "[a](http://a.com) " "[b](https://b.com) " "[c](./local.md)"
        result = markdown_link_check_lexical(text)
        assert result["external_count"] == 2
        assert result["total_links"] == 3


class TestMarkdownLinkCheckLexicalMCP:
    """Test markdown_link_check_lexical via MCP protocol."""

    def test_mcp_basic(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "markdown_link_check_lexical",
                    "arguments": {"text": "[Google](https://google.com)"},
                },
            }
        )
        content = json.loads(response["result"]["content"][0]["text"])
        assert content["ok"] is True
        assert content["result"]["total_links"] == 1

    def test_mcp_with_known_paths(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "markdown_link_check_lexical",
                    "arguments": {
                        "text": "[docs](./missing.md)",
                        "known_paths": ["./README.md"],
                    },
                },
            }
        )
        content = json.loads(response["result"]["content"][0]["text"])
        assert content["ok"] is True
        assert len(content["result"]["unresolved_relatives"]) == 1

    def test_mcp_invalid_known_paths(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "markdown_link_check_lexical",
                    "arguments": {
                        "text": "[link](http://example.com)",
                        "known_paths": "not a list",
                    },
                },
            }
        )
        assert "error" in response


# =============================================================================
# repo_file_inventory tests
# =============================================================================


class TestRepoFileInventory:
    """Test repo_file_inventory core function."""

    def test_python_project(self):
        paths = ["src/main.py", "tests/test_main.py", "pyproject.toml", "README.md"]
        result = repo_file_inventory(paths)
        assert result["total_files"] == 4
        assert "python" in result["language_signals"]
        assert result["by_category"]["source"] == 1
        assert result["by_category"]["test"] == 1

    def test_mixed_project(self):
        paths = [
            "src/app.py",
            "src/lib.rs",
            "index.js",
            "tsconfig.json",
            "README.md",
            "data.csv",
        ]
        result = repo_file_inventory(paths)
        assert result["total_files"] == 6
        assert "python" in result["language_signals"]
        assert "rust" in result["language_signals"]
        assert "javascript" in result["language_signals"]

    def test_hidden_files(self):
        paths = [".gitignore", ".env", "src/main.py"]
        result = repo_file_inventory(paths)
        assert result["hidden_files"] == 2

    def test_vendor_dirs(self):
        paths = ["node_modules/pkg/index.js", "vendor/lib.c", "src/main.py"]
        result = repo_file_inventory(paths)
        assert len(result["vendor_candidates"]) == 2

    def test_config_files(self):
        paths = ["Cargo.toml", "pyproject.toml", "package.json", "src/main.py"]
        result = repo_file_inventory(paths)
        assert len(result["config_files_found"]) == 3

    def test_duplicate_hashes(self):
        paths = ["a.txt", "b.txt", "c.txt"]
        hashes = {"a.txt": "abc123", "b.txt": "abc123", "c.txt": "def456"}
        result = repo_file_inventory(paths, hashes=hashes)
        assert len(result["duplicate_hashes"]) == 1
        assert set(result["duplicate_hashes"][0]) == {"a.txt", "b.txt"}

    def test_sizes(self):
        paths = ["big.bin", "small.txt"]
        sizes = {"big.bin": 1_000_000, "small.txt": 100}
        result = repo_file_inventory(paths, sizes=sizes)
        assert result["total_size"] == 1_000_100
        assert len(result["largest_files"]) == 2
        assert result["largest_files"][0]["path"] == "big.bin"

    def test_empty_paths(self):
        result = repo_file_inventory([])
        assert result["total_files"] == 0

    def test_truncation_warning(self):
        paths = [f"file_{i}.py" for i in range(50_001)]
        result = repo_file_inventory(paths)
        assert result["truncation_warning"] is True
        assert result["total_files"] == 50_000

    def test_not_a_list(self):
        result = repo_file_inventory("not a list")
        assert result["total_files"] == 0

    def test_suspicious_paths(self):
        paths = ["normal.py", "a" * 2000]
        result = repo_file_inventory(paths)
        assert len(result["suspicious_paths"]) > 0

    def test_generated_candidates(self):
        paths = ["src/__pycache__/main.pyc", "dist/app.js", "src/main.py"]
        result = repo_file_inventory(paths)
        assert len(result["generated_candidates"]) > 0


class TestRepoFileInventoryMCP:
    """Test repo_file_inventory via MCP protocol."""

    def test_mcp_basic(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "repo_file_inventory",
                    "arguments": {"paths": ["src/main.py", "tests/test.py"]},
                },
            }
        )
        content = json.loads(response["result"]["content"][0]["text"])
        assert content["ok"] is True
        assert content["result"]["total_files"] == 2

    def test_mcp_with_sizes(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "repo_file_inventory",
                    "arguments": {
                        "paths": ["a.py"],
                        "sizes": {"a.py": 1024},
                    },
                },
            }
        )
        content = json.loads(response["result"]["content"][0]["text"])
        assert content["ok"] is True
        assert content["result"]["total_size"] == 1024

    def test_mcp_missing_paths(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "repo_file_inventory",
                    "arguments": {},
                },
            }
        )
        assert "error" in response

    def test_mcp_invalid_paths(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "repo_file_inventory",
                    "arguments": {"paths": "not a list"},
                },
            }
        )
        assert "error" in response
