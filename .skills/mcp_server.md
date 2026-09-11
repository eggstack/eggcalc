# MCP Server Implementation Patterns

## Purpose
Guide agents on MCP server implementation and tool definitions.

## MCP Server Structure

### Tool Registration (Plan 040 authority model)
Catalog authority is `TOOL_METADATA` in `schemas.py` (canonical name +
`handler` locator + category/tier/tags/profiles/exposure/cost/stability/
composite + `selection_summary`/`keywords`); protocol shape is `TOOL_SCHEMAS`
(description/inputSchema/outputSchema/deprecated only). `TOOL_HANDLERS` in
`server.py` is derived via `_build_tool_handlers()` — never hand-edit the
mapping. `TOOL_PROFILES` is derived via `_build_profiles()`. The JSON fixture
is a compatibility snapshot, not a registry; `docs/tool_inventory.md` is
generated. Read selection metadata via `get_tool_selection_summary()` /
`get_tool_keywords()`.

### Discovery and Profiles (Plan 041)

- 12 profiles; `agent_core` (10 front doors) is an opt-in candidate surface,
  not a validated general-agent recommendation (the 2026-09-10 held-out
  closure report found selection regression). `full` stays the default. Never
  silently remap profile names.
- `ToolRegistry.search_tools(query, *, profile="full", limit=5)` ranks via
  exact name (300) / alias (250) / name-token / keyword / category / summary /
  description fallback with canonical-name tie-break. Returns `ToolMatch`
  (no schemas, no authorization). Query truncates to 4096 chars; limit 1–20.
- Compact `tools/list` descriptions are the authored `selection_summary`
  (≤240 chars). Thaw compact/normal entries with `thaw_owned()` before
  emission — frozen registry values crash JSON serialization.
- Corpus + scorer: `evals/mcp_tool_selection/` (121 cases, dev/held_out
  splits), `scripts/measure_mcp_tool_surface.py`,
  `scripts/score_mcp_tool_selection.py`, and
  `scripts/analyze_mcp_tool_selection_failures.py`. The Plan 043 candidate
  lists are evaluation-only; they do not create profiles. Tune on
  `development` only and retain normalized per-case rollout JSONL before
  making model-selection claims. The current cross-model evidence is
   recorded in `evals/mcp_tool_selection/reports/closure_2026_09_10.md`; do not describe `agent_core` as
  recommended until a later held-out run passes non-inferiority and
  specialist-recovery gates. The corrective stopping decision is recorded in
  `evals/mcp_tool_selection/reports/corrective_held_out_2026_09_10.md`.

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
1. Add protocol shape to `TOOL_SCHEMAS` in `schemas.py` (description/inputSchema/outputSchema only — no tier/tags)
2. Add handler function in `tools.py` (deferred exact imports inside the function body)
3. Add catalog entry to `TOOL_METADATA` in `schemas.py` (`handler` + category/tier/tags/profiles/exposure/cost/stability/composite + `selection_summary` ≤240 chars + `keywords` ≤8 items of ≤48 chars; add to `agent_core` only if it earns permanent context)
4. Run `python scripts/generate_mcp_docs.py` and update the compatibility fixture intentionally (`tests/fixtures/mcp_tool_registry_expected.json`)
5. Add test in `test_mcp_server.py` (and `test_tool_inventory.py` covers authority parity automatically); reference the tool from `evals/mcp_tool_selection/cases.json` if it fills a selection gap

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
