# MCP Server Implementation Patterns

## Purpose
Guide agents on MCP server implementation and tool definitions.

## MCP Server Structure

### Tool Registration
Tools are defined in `TOOL_SCHEMAS` (in `schemas.py`) and registered via `TOOL_HANDLERS` (in `server.py`).

### Response Conventions

**Success responses** should return direct result dict:
```python
return {"result": str(value), "type": type(value).__name__}
```

**Error responses** should use `_error_response()`:
```python
return _error_response("ErrorType", error_message, hints)
```

**In `McpSession._handle_call_tool_server()` (legacy era)**, results are wrapped in MCP format:
```python
return {
    "jsonrpc": "2.0",
    "id": request.get("id"),
    "result": {
        "content": [{"type": "text", "text": json.dumps(result)}]
    },
}
```

**On the modern (`2026-07-28`) path** (`ToolExecutor.call_tool(..., modern=True)` + `_attach_modern_server_info()`), successful results additionally carry `resultType: "complete"`, `structuredContent` (equals the text envelope's `result` member), and server identity in `result._meta`. Do not hand-build these fields — go through the executor + finalizer.

### Protocol Eras

One stdio server speaks both eras; `McpServer.handle_request()` classifies per-request via `_classify_request_era()` before any session logic:

- **Legacy** (`2024-11-05`, `2025-11-25`): `initialize` → `notifications/initialized` → READY `McpSession`. `initialize` negotiates legacy revisions only.
- **Modern** (`2026-07-28`, finalized): stateless; each request carries `params._meta` (`io.modelcontextprotocol/protocolVersion` + `clientCapabilities` required, `clientInfo` optional). Allowed methods: `server/discover`, `tools/list`, `tools/call`. Never construct fake READY sessions for modern traffic; never store modern client metadata globally.

Version→era mapping lives in `eggcalc/_protocol.py` (`protocol_era()`); do not add inline version comparisons.

### Tool Naming
Tool names should match exactly between schemas and handlers. Case-insensitive matching with suggestions is available.

### Input Validation
All text inputs should check against `MAX_TEXT_LENGTH`. Expression inputs should check against `MAX_EXPRESSION_LENGTH`.

### Error Sanitization
Error messages should be sanitized to remove non-ASCII characters before returning JSON-RPC responses.

## Common Patterns

### Adding a New Tool
1. Add schema to `TOOL_SCHEMAS` in `schemas.py`
2. Add handler function in `tools.py`
3. Register in `TOOL_HANDLERS` dict in `server.py`
4. Add test in `test_mcp_server.py`

### Tool Function Signature
```python
def tool_name(expression: str) -> dict:
    """Description.

    Args:
        expression: Description.

    Returns:
        Success response with result, or error envelope.
    """
    if len(expression) > MAX_TEXT_LENGTH:
        return _error_response("InputError", f"Exceeds max length of {MAX_TEXT_LENGTH}")
    try:
        result = evaluate_raw(expression)
        return {"result": str(result), "type": type(result).__name__}
    except EvaluationError as e:
        return _error_response("EvaluationError", str(e))
    except Exception as e:
        return _error_response("UnexpectedError", str(e))
```

## Testing MCP Tools
```bash
# Run MCP-specific tests (use venv python)
.venv/bin/python -m pytest tests/test_mcp_server.py tests/test_mcp_modern.py -v

# Test server manually via stdio (legacy era: initialize handshake first —
# tool calls before initialize + notifications/initialized are rejected
# with -32600; modern 2026-07-28 requests carry params._meta instead)
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05"}}' | .venv/bin/python -m eggcalc --mcp
echo '{"jsonrpc":"2.0","id":1,"method":"server/discover","params":{"_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28","io.modelcontextprotocol/clientCapabilities":{}}}}' | .venv/bin/python -m eggcalc --mcp
```