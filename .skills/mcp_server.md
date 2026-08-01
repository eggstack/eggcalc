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

**In `McpSession._handle_call_tool_server()`**, results are wrapped in MCP format:
```python
return {
    "jsonrpc": "2.0",
    "id": request.get("id"),
    "result": {
        "content": [{"type": "text", "text": json.dumps(result)}]
    },
}
```

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
# Run MCP-specific tests
python3 -m pytest tests/test_mcp_server.py -v

# Test server manually via stdio
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05"}}' | python3 -m eggcalc --mcp
```