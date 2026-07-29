"""Smoke test for MCP stdio tools/list path.

Exercises the same entry point a user would use via ``python -m eggcalc --mcp``.
Sends a single ``tools/list`` JSON-RPC request over newline-delimited JSON,
asserts a valid response, and verifies that key tools appear in the list.
"""

import json
import subprocess
import sys

import pytest


def _make_request(method: str, req_id: int = 1) -> str:
    return json.dumps({"jsonrpc": "2.0", "id": req_id, "method": method})


def _make_initialize_request(req_id: int = 1, protocol_version: str = "2025-11-25") -> str:
    return json.dumps(
        {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": "initialize",
            "params": {
                "protocolVersion": protocol_version,
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "0.1.0"},
            },
        }
    )


def test_mcp_tools_list_subprocess_smoke():
    proc = subprocess.Popen(
        [sys.executable, "-m", "eggcalc", "--mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        # Send initialize, notifications/initialized, then tools/list
        init_req = _make_initialize_request(1) + "\n"
        notif_req = json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n"
        list_req = _make_request("tools/list", 2) + "\n"
        stdout, stderr = proc.communicate(
            input=(init_req + notif_req + list_req).encode(), timeout=10
        )
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        raise AssertionError("MCP server did not respond within 10 seconds")
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()

    assert (
        proc.returncode == 0 or proc.returncode is None
    ), f"MCP server exited with code {proc.returncode}: " + stderr.decode("utf-8", errors="replace")

    lines = [line for line in stdout.decode().splitlines() if line.strip()]
    assert lines, f"No response lines from MCP server. stderr: {stderr.decode(errors='replace')}"

    # Find the tools/list response (second response, first is initialize)
    payload = None
    for line in lines:
        p = json.loads(line)
        if p.get("id") == 2:
            payload = p
            break
    assert payload is not None, f"No tools/list response found in: {lines}"

    assert payload["jsonrpc"] == "2.0", f"Not JSON-RPC: {payload}"
    assert payload["id"] == 2, f"Wrong id: {payload}"

    tools = payload.get("result", {}).get("tools", [])
    assert tools, "No tools returned"
    names = {tool["name"] for tool in tools}
    assert "math_eval" in names, f"math_eval not in tool list: {sorted(names)}"
    assert "text_inspect" in names, f"text_inspect not in tool list: {sorted(names)}"


def test_mcp_eof_exits_cleanly():
    """MCP server should exit cleanly (returncode 0) when stdin reaches EOF."""
    proc = subprocess.Popen(
        [sys.executable, "-m", "eggcalc", "--mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        # Send nothing — immediate EOF
        stdout, stderr = proc.communicate(input=b"", timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        raise AssertionError("MCP server did not exit within 10 seconds on EOF")
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()

    assert proc.returncode == 0, (
        f"MCP server exited with code {proc.returncode} on EOF. "
        f"stderr: {stderr.decode('utf-8', errors='replace')}"
    )


def test_mcp_broken_pipe_exits_cleanly():
    """MCP server should handle BrokenPipeError and exit with code 0."""
    proc = subprocess.Popen(
        [sys.executable, "-m", "eggcalc", "--mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        # Send initialize, then close stdin to simulate broken pipe.
        # Use communicate(input=...) so the write and close are atomic,
        # avoiding a race where flush() raises ValueError on Linux if
        # the server exits before the flush completes.
        init_req = _make_initialize_request(1) + "\n"
        stdout, stderr = proc.communicate(input=init_req.encode(), timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        raise AssertionError("MCP server did not exit within 10 seconds on broken pipe")
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()

    assert proc.returncode == 0, (
        f"MCP server exited with code {proc.returncode} on broken pipe. "
        f"stderr: {stderr.decode('utf-8', errors='replace')}"
    )


def test_mcp_single_file_eof_exits_cleanly():
    """Generated single-file eggcalc.py should also exit cleanly on EOF."""
    import os

    single_file = os.path.join(os.path.dirname(__file__), "..", "eggcalc.py")
    if not os.path.exists(single_file):
        pytest.skip("eggcalc.py single-file not built yet")

    proc = subprocess.Popen(
        [sys.executable, single_file, "--mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        stdout, stderr = proc.communicate(input=b"", timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        raise AssertionError("Single-file MCP server did not exit within 10 seconds on EOF")
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()

    assert proc.returncode == 0, (
        f"Single-file MCP server exited with code {proc.returncode} on EOF. "
        f"stderr: {stderr.decode('utf-8', errors='replace')}"
    )


def _run_mcp_transcript(
    cmd: list[str], timeout: int = 15, protocol_version: str = "2025-11-25"
) -> list[dict]:
    """Run a full MCP transcript against a server command and return parsed responses.

    Transcript: initialize → notifications/initialized → ping → tools/list →
    tools/call math_eval "5+3". Returns list of response dicts (excluding
    notifications which produce no response).
    """
    requests = [
        _make_initialize_request(1, protocol_version),
        json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
        _make_request("ping", 2),
        _make_request("tools/list", 3),
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "math_eval", "arguments": {"expression": "5+3"}},
            }
        ),
    ]
    input_data = "\n".join(requests) + "\n"

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        stdout, stderr = proc.communicate(input=input_data.encode(), timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        raise AssertionError(f"Server did not respond within {timeout}s")
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()

    assert proc.returncode == 0, (
        f"Server exited with code {proc.returncode}. "
        f"stderr: {stderr.decode('utf-8', errors='replace')}"
    )

    lines = [line for line in stdout.decode().splitlines() if line.strip()]
    responses = [json.loads(line) for line in lines]
    return responses


def _normalize_transcript(responses: list[dict]) -> list[dict]:
    """Normalize a transcript for comparison.

    Strips variable fields (server version, exact id values, mode-specific
    capabilities) so transcripts from package and single-file modes can be
    compared structurally.
    """
    normalized = []
    for resp in responses:
        n = dict(resp)
        # Keep error codes and result structure, normalize version strings
        if "result" in n and isinstance(n["result"], dict):
            result = dict(n["result"])
            if "serverInfo" in result:
                info = dict(result["serverInfo"])
                info["version"] = "<normalized>"
                result["serverInfo"] = info
            if "protocolVersion" in result:
                result["protocolVersion"] = "<normalized>"
            # Normalize runtime capabilities that legitimately differ
            caps = result.get("capabilities", {})
            if isinstance(caps, dict) and "runtime" in caps:
                rt = dict(caps["runtime"])
                rt["mode"] = "<normalized>"
                rt["eggcalc_version"] = "<normalized>"
                new_caps = dict(caps)
                new_caps["runtime"] = rt
                result["capabilities"] = new_caps
            n["result"] = result
        normalized.append(n)
    return normalized


def test_package_mcp_transcript():
    """Package mode MCP server handles a full initialize → ping → list → call transcript."""
    responses = _run_mcp_transcript([sys.executable, "-m", "eggcalc", "--mcp"])

    # Should have 4 responses: initialize, ping, tools/list, tools/call
    assert len(responses) == 4, f"Expected 4 responses, got {len(responses)}: {responses}"

    # initialize response
    init_resp = responses[0]
    assert init_resp["id"] == 1
    assert "result" in init_resp
    assert init_resp["result"]["protocolVersion"] == "2025-11-25"
    assert "tools" in init_resp["result"]["capabilities"]
    assert init_resp["result"]["serverInfo"]["name"] == "eggcalc"

    # ping response
    ping_resp = responses[1]
    assert ping_resp["id"] == 2
    assert ping_resp["result"] == {}

    # tools/list response
    list_resp = responses[2]
    assert list_resp["id"] == 3
    tools = list_resp["result"]["tools"]
    tool_names = {t["name"] for t in tools}
    assert "math_eval" in tool_names
    assert "text_inspect" in tool_names

    # tools/call response
    call_resp = responses[3]
    assert call_resp["id"] == 4
    content = json.loads(call_resp["result"]["content"][0]["text"])
    assert content["ok"] is True
    assert content["result"]["value"] == "8"


def test_single_file_mcp_transcript():
    """Generated single-file eggcalc.py handles the same full transcript."""
    import os

    single_file = os.path.join(os.path.dirname(__file__), "..", "eggcalc.py")
    if not os.path.exists(single_file):
        pytest.skip("eggcalc.py single-file not built yet")

    responses = _run_mcp_transcript([sys.executable, single_file, "--mcp"])

    assert len(responses) == 4, f"Expected 4 responses, got {len(responses)}: {responses}"

    init_resp = responses[0]
    assert init_resp["id"] == 1
    assert "result" in init_resp
    assert init_resp["result"]["protocolVersion"] == "2025-11-25"

    ping_resp = responses[1]
    assert ping_resp["id"] == 2
    assert ping_resp["result"] == {}

    list_resp = responses[2]
    assert list_resp["id"] == 3
    tools = list_resp["result"]["tools"]
    tool_names = {t["name"] for t in tools}
    assert "math_eval" in tool_names

    call_resp = responses[3]
    assert call_resp["id"] == 4
    content = json.loads(call_resp["result"]["content"][0]["text"])
    assert content["ok"] is True
    assert content["result"]["value"] == "8"


def test_package_and_single_file_transcripts_match():
    """Package and single-file MCP transcripts are structurally identical."""
    import os
    import tempfile

    build_script = os.path.join(os.path.dirname(__file__), "..", "build_single.py")
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
        single_file = f.name
    try:
        result = subprocess.run(
            [sys.executable, build_script, "-o", single_file],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            pytest.skip(f"build_single.py failed: {result.stderr}")

        pkg_responses = _run_mcp_transcript([sys.executable, "-m", "eggcalc", "--mcp"])
        sf_responses = _run_mcp_transcript([sys.executable, single_file, "--mcp"])

        pkg_norm = _normalize_transcript(pkg_responses)
        sf_norm = _normalize_transcript(sf_responses)

        assert len(pkg_norm) == len(
            sf_norm
        ), f"Different response counts: package={len(pkg_norm)}, single-file={len(sf_norm)}"

        for i, (p, s) in enumerate(zip(pkg_norm, sf_norm)):
            assert p == s, (
                f"Transcript mismatch at response {i}:\n"
                f"  package:      {json.dumps(p, indent=2)}\n"
                f"  single-file:  {json.dumps(s, indent=2)}"
            )
    finally:
        if os.path.exists(single_file):
            os.unlink(single_file)


def test_package_mcp_transcript_2024_11_05():
    """Verify backward compatibility with 2024-11-05."""
    responses = _run_mcp_transcript(
        [sys.executable, "-m", "eggcalc", "--mcp"],
        protocol_version="2024-11-05",
    )

    assert len(responses) == 4, f"Expected 4 responses, got {len(responses)}: {responses}"

    init_resp = responses[0]
    assert init_resp["id"] == 1
    assert "result" in init_resp
    assert init_resp["result"]["protocolVersion"] == "2024-11-05"
    assert "tools" in init_resp["result"]["capabilities"]
    assert init_resp["result"]["serverInfo"]["name"] == "eggcalc"

    ping_resp = responses[1]
    assert ping_resp["id"] == 2
    assert ping_resp["result"] == {}

    list_resp = responses[2]
    assert list_resp["id"] == 3
    tools = list_resp["result"]["tools"]
    tool_names = {t["name"] for t in tools}
    assert "math_eval" in tool_names

    call_resp = responses[3]
    assert call_resp["id"] == 4
    content = json.loads(call_resp["result"]["content"][0]["text"])
    assert content["ok"] is True
    assert content["result"]["value"] == "8"
