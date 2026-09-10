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

**In `ToolExecutor.call_tool()` (both eras)**, handler results are split once via `_split_tool_wire_result()` into compatibility text (the full `{ok, tool, result, ...}` envelope) plus `structuredContent` (equals the envelope's `result` member) when the declared `outputSchema` is object-rooted. Success payloads are validated via `_validate_output_payload()` (sanitized `-32000` on mismatch). Error envelopes stay `isError` with no structured payload. `max_output_bytes` bounds the envelope JSON; both forms serialize after it passes.

- **Legacy era** (`McpSession._handle_call_tool_server()`): `{"content": [...]}` plus `structuredContent`, no `resultType`.
- **Modern (`2026-07-28`) path** (`call_tool(..., modern=True)` + `_attach_modern_server_info()`): additionally `resultType: "complete"` and server identity in `result._meta`.

Do not hand-build these fields — go through the executor + finalizer.

### Annotations, Instructions, Cache Hints

- Annotations live in `TOOL_ANNOTATIONS` / `get_tool_annotations()` in `schemas.py` (uniform read-only/closed-world; hints only, never policy). `tools/list` emits `annotations` in every schema-detail mode.
- `SERVER_INSTRUCTIONS` in `server.py` is the one prose authority, shared by legacy `initialize` and modern `server/discover`.
- Modern `tools/list` / `server/discover` carry conservative `ttlMs: 0`, `cacheScope: "private"` from `eggcalc/_protocol.py` (final policy); `tools/list` order is canonical sorted-name on both eras.

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