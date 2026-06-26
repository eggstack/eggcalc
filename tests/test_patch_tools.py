"""Tests for patch_apply_check and patch_summary MCP tools."""

import json

from eggcalc.mcp.server import TOOL_HANDLERS, handle_request

# --- Test fixtures ---

SINGLE_HUNK_PATCH = """\
--- a/example.py
+++ b/example.py
@@ -1,5 +1,5 @@
 def hello():
-    print("hello")
+    print("hello world")
     return True
 
 def goodbye():
"""

MULTI_HUNK_PATCH = """\
--- a/example.py
+++ b/example.py
@@ -1,5 +1,5 @@
 def hello():
-    print("hello")
+    print("hello world")
     return True
 
 def goodbye():
@@ -8,3 +8,3 @@
 def add(a, b):
-    return a + b
+    return a + b  # addition
     pass
"""

WRONG_CONTEXT_PATCH = """\
--- a/example.py
+++ b/example.py
@@ -1,5 +1,5 @@
 def hello():
-    print("wrong context")
+    print("hello world")
     return True
 
 def goodbye():
"""

ORIGINAL_TEXT = """\
def hello():
    print("hello")
    return True

def goodbye():
    pass
"""

ORIGINAL_TEXT_WITH_ADD = """\
def hello():
    print("hello")
    return True

def goodbye():
    pass

def add(a, b):
    return a + b
    pass
"""

RENAME_PATCH = """\
--- a/old_name.py
+++ b/new_name.py
@@ -1,3 +1,3 @@
 def hello():
-    print("old")
+    print("new")
     return True
"""

BINARY_PATCH = """\
--- a/binary.dat
+++ b/binary.dat
GIT binary patch
literal 0
Hc$@<000001
"""


class TestPatchApplyCheckMCP:
    """Test patch_apply_check via MCP protocol."""

    def test_basic_apply(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "patch_apply_check",
                    "arguments": {
                        "original_text": ORIGINAL_TEXT,
                        "patch_text": SINGLE_HUNK_PATCH,
                    },
                },
            }
        )
        content = json.loads(response["result"]["content"][0]["text"])
        assert content["ok"] is True
        assert content["result"]["patch_parse_ok"] is True
        assert content["result"]["applies"] is True
        assert content["result"]["hunks_total"] == 1
        assert content["result"]["hunks_applied"] == 1
        assert content["result"]["hunks_failed"] == 0
        assert len(content["result"]["failed_hunks"]) == 0

    def test_wrong_context(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "patch_apply_check",
                    "arguments": {
                        "original_text": ORIGINAL_TEXT,
                        "patch_text": WRONG_CONTEXT_PATCH,
                    },
                },
            }
        )
        content = json.loads(response["result"]["content"][0]["text"])
        assert content["ok"] is True
        assert content["result"]["patch_parse_ok"] is True
        assert content["result"]["applies"] is False
        assert content["result"]["hunks_failed"] == 1
        assert len(content["result"]["failed_hunks"]) == 1
        assert "mismatch" in content["result"]["failed_hunks"][0]["reason"]

    def test_multiple_hunks(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "patch_apply_check",
                    "arguments": {
                        "original_text": ORIGINAL_TEXT_WITH_ADD,
                        "patch_text": MULTI_HUNK_PATCH,
                    },
                },
            }
        )
        content = json.loads(response["result"]["content"][0]["text"])
        assert content["ok"] is True
        assert content["result"]["hunks_total"] == 2
        assert content["result"]["applies"] is True

    def test_return_result_text(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "patch_apply_check",
                    "arguments": {
                        "original_text": ORIGINAL_TEXT,
                        "patch_text": SINGLE_HUNK_PATCH,
                        "return_result_text": True,
                    },
                },
            }
        )
        content = json.loads(response["result"]["content"][0]["text"])
        assert content["ok"] is True
        assert content["result"]["result_text"] is not None
        assert "hello world" in content["result"]["result_text"]

    def test_return_result_fingerprint(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "patch_apply_check",
                    "arguments": {
                        "original_text": ORIGINAL_TEXT,
                        "patch_text": SINGLE_HUNK_PATCH,
                        "return_result_fingerprint": True,
                    },
                },
            }
        )
        content = json.loads(response["result"]["content"][0]["text"])
        assert content["ok"] is True
        assert len(content["result"]["result_fingerprint"]) == 64

    def test_affected_line_ranges(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "patch_apply_check",
                    "arguments": {
                        "original_text": ORIGINAL_TEXT,
                        "patch_text": SINGLE_HUNK_PATCH,
                    },
                },
            }
        )
        content = json.loads(response["result"]["content"][0]["text"])
        assert content["ok"] is True
        ranges = content["result"]["affected_line_ranges"]
        assert len(ranges) == 1
        assert "start" in ranges[0]
        assert "end" in ranges[0]

    def test_newline_style_detection(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "patch_apply_check",
                    "arguments": {
                        "original_text": "hello\r\nworld\r\n",
                        "patch_text": SINGLE_HUNK_PATCH,
                    },
                },
            }
        )
        content = json.loads(response["result"]["content"][0]["text"])
        assert content["ok"] is True
        assert content["result"]["newline_style_before"] == "CRLF"

    def test_empty_patch(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "patch_apply_check",
                    "arguments": {
                        "original_text": ORIGINAL_TEXT,
                        "patch_text": "",
                    },
                },
            }
        )
        content = json.loads(response["result"]["content"][0]["text"])
        assert content["ok"] is True
        assert content["result"]["patch_parse_ok"] is False

    def test_malformed_patch(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "patch_apply_check",
                    "arguments": {
                        "original_text": ORIGINAL_TEXT,
                        "patch_text": "not a real patch",
                    },
                },
            }
        )
        content = json.loads(response["result"]["content"][0]["text"])
        assert content["ok"] is True
        assert content["result"]["patch_parse_ok"] is False

    def test_strict_false(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "patch_apply_check",
                    "arguments": {
                        "original_text": ORIGINAL_TEXT,
                        "patch_text": SINGLE_HUNK_PATCH,
                        "strict": False,
                    },
                },
            }
        )
        content = json.loads(response["result"]["content"][0]["text"])
        assert content["ok"] is True

    def test_input_too_large_original(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "patch_apply_check",
                    "arguments": {
                        "original_text": "a" * 300000,
                        "patch_text": SINGLE_HUNK_PATCH,
                    },
                },
            }
        )
        assert "result" in response
        assert response["result"]["isError"] is True

    def test_input_too_large_patch(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "patch_apply_check",
                    "arguments": {
                        "original_text": ORIGINAL_TEXT,
                        "patch_text": "x" * 300000,
                    },
                },
            }
        )
        assert "result" in response
        assert response["result"]["isError"] is True


class TestPatchSummaryMCP:
    """Test patch_summary via MCP protocol."""

    def test_basic_summary(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "patch_summary",
                    "arguments": {
                        "patch_text": SINGLE_HUNK_PATCH,
                    },
                },
            }
        )
        content = json.loads(response["result"]["content"][0]["text"])
        assert content["ok"] is True
        assert content["result"]["files_changed"] == 1
        assert content["result"]["hunks_total"] == 1
        assert content["result"]["additions"] == 1
        assert content["result"]["deletions"] == 1
        assert content["result"]["binary_patch_detected"] is False

    def test_multi_hunk_summary(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "patch_summary",
                    "arguments": {
                        "patch_text": MULTI_HUNK_PATCH,
                    },
                },
            }
        )
        content = json.loads(response["result"]["content"][0]["text"])
        assert content["ok"] is True
        assert content["result"]["files_changed"] == 1
        assert content["result"]["hunks_total"] == 2
        assert content["result"]["additions"] == 2
        assert content["result"]["deletions"] == 2

    def test_rename_detection(self):
        # A standard unified diff with different `a/X` / `b/Y` headers
        # is a modification, NOT a rename. Renames require explicit
        # `rename from X` / `rename to Y` directives (extended diff
        # format, e.g. `git diff -M`). The current parser does not
        # surface that metadata, so renames_detected stays empty for
        # this input. See plans/production_review_2026_07_b.md (B3).
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "patch_summary",
                    "arguments": {
                        "patch_text": RENAME_PATCH,
                    },
                },
            }
        )
        content = json.loads(response["result"]["content"][0]["text"])
        assert content["ok"] is True
        assert content["result"]["renames_detected"] == []

    def test_binary_patch_detection(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "patch_summary",
                    "arguments": {
                        "patch_text": BINARY_PATCH,
                    },
                },
            }
        )
        content = json.loads(response["result"]["content"][0]["text"])
        assert content["ok"] is True
        assert content["result"]["binary_patch_detected"] is True

    def test_line_ranges_by_file(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "patch_summary",
                    "arguments": {
                        "patch_text": SINGLE_HUNK_PATCH,
                    },
                },
            }
        )
        content = json.loads(response["result"]["content"][0]["text"])
        assert content["ok"] is True
        assert "b/example.py" in content["result"]["line_ranges_by_file"]
        ranges = content["result"]["line_ranges_by_file"]["b/example.py"]
        assert len(ranges) == 1
        assert "start" in ranges[0]
        assert "end" in ranges[0]

    def test_empty_patch_summary(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "patch_summary",
                    "arguments": {
                        "patch_text": "",
                    },
                },
            }
        )
        content = json.loads(response["result"]["content"][0]["text"])
        assert content["ok"] is True
        assert content["result"]["files_changed"] == 0
        assert content["result"]["hunks_total"] == 0

    def test_malformed_patch_summary(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "patch_summary",
                    "arguments": {
                        "patch_text": "not a real patch",
                    },
                },
            }
        )
        content = json.loads(response["result"]["content"][0]["text"])
        assert content["ok"] is True
        assert content["result"]["files_changed"] == 0

    def test_input_too_large_summary(self):
        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "patch_summary",
                    "arguments": {
                        "patch_text": "x" * 300000,
                    },
                },
            }
        )
        assert "result" in response
        assert response["result"]["isError"] is True


class TestPatchToolRegistry:
    """Verify patch tools are in the registry."""

    def test_patch_apply_check_in_handlers(self):
        assert "patch_apply_check" in TOOL_HANDLERS

    def test_patch_summary_in_handlers(self):
        assert "patch_summary" in TOOL_HANDLERS

    def test_patch_apply_check_callable(self):
        assert callable(TOOL_HANDLERS["patch_apply_check"])

    def test_patch_summary_callable(self):
        assert callable(TOOL_HANDLERS["patch_summary"])
