"""Smoke test for MCP stdio tools/list path.

Exercises the same entry point a user would use via ``python -m eggcalc --mcp``.
Sends a single ``tools/list`` JSON-RPC request over newline-delimited JSON,
asserts a valid response, and verifies that key tools appear in the list.
"""

import json
import subprocess
import sys


def _make_request(method: str, req_id: int = 1) -> str:
    return json.dumps({"jsonrpc": "2.0", "id": req_id, "method": method})


def test_mcp_tools_list_subprocess_smoke():
    proc = subprocess.Popen(
        [sys.executable, "-m", "eggcalc", "--mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        # Send initialize, notifications/initialized, then tools/list
        init_req = _make_request("initialize", 1) + "\n"
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
