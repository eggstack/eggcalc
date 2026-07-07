# mcp/ — Model Context Protocol Server

MCP server providing AI agent tool access to eggcalc's text analysis functions via a stdio-based JSON-RPC interface.

## Module Structure

```
mcp/
├── __init__.py   # Empty package marker
├── schemas.py    # Tool input/output schemas
├── tools.py      # Tool implementations
└── server.py     # MCP protocol handler
```

## Overview

The MCP server exposes exact text analysis tools to AI agents. It provides:
- JSON-RPC 2.0 protocol handling over stdio
- Tool discovery via `tools/list`
- Tool execution via `tools/call`
- Standardized error envelopes
- Input validation and sanitization
- Case-insensitive tool matching with suggestions

## Architecture

```
AI Agent <--JSON-RPC--> MCP Server <---> eggcalc exact tools
                              |
                              +-- primitives
                              +-- unicode_tools
                              +-- diff
                              +-- validate
                              +-- measure
                              +-- synthesis
```

## schemas.py — Tool Schemas

Defines input/output schemas for each MCP tool.

### Error Envelope

```python
class ErrorEnvelope(TypedDict):
    ok: bool                    # Always False for errors
    error_type: str             # Error category
    error: str                  # Error message (ASCII-safe)
    hints: list[str]           # Suggested fixes
    tool: str | None            # Tool name that produced error
    warnings: list[str]        # Warning messages
```

### TOOL_SCHEMAS

Registry of all available tools (77 total). Tools are organized by tier for selective exposure:

#### Tier 0 — Ultra-common (minimal schema)

| Tool Name | Description |
|-----------|-------------|
| `math_eval` | Evaluate arithmetic, unit conversions, constants |
| `text_equal` | Compare strings with multiple equality modes |
| `text_count` | Count characters or frequency table |
| `text_fingerprint` | Compute deterministic SHA-256 fingerprint |
| `validate_json` | Validate JSON syntax |
| `path_normalize` | Normalize path using posixpath/ntpath semantics |

#### Tier 1 — Default coding-agent sanity tools

| Tool Name | Description |
|-----------|-------------|
| `text_diff_explain` | Explain string differences |
| `text_inspect` | Inspect for hidden characters, confusables |
| `text_replace_check` | Check replacement before applying |
| `line_range_extract` | Extract exact line ranges with fingerprints |
| `line_range_compare` | Compare line ranges from two texts |
| `json_compare` | Compare two JSON documents semantically |
| `json_extract` | Extract value using RFC 6901 JSON Pointer |
| `json_shape` | Analyze JSON structure without returning values |
| `validate_toml` | Validate TOML configuration files |
| `regex_finditer` | Find all regex matches with positions |
| `regex_test` | Test regex against samples |
| `identifier_inspect` | Inspect identifiers for validity and collisions |
| `text_transform` | Apply text transformations (normalization, casefold, etc.) |
| `escape_text` | Escape text for various output formats |
| `unescape_text` | Unescape text from various formats |

#### Tier 2 — Heavier analysis tools

| Tool Name | Description |
|-----------|-------------|
| `text_measure` | Measure text properties (bytes, codepoints, words, lines) |
| `text_truncate` | Truncate to grapheme boundary |
| `text_position` | Convert between byte offsets, codepoint indices, line/column |
| `text_window` | Get window around position with context lines |
| `text_hash` | Compute cryptographic hashes of text |
| `patch_apply_check` | Validate and simulate a unified diff against text |
| `patch_summary` | Summarize a unified diff without applying |
| `markdown_structure` | Parse markdown structure (headings, links, code fences) |
| `code_fence_extract` | Extract fenced code blocks with exact ranges |
| `identifier_table_inspect` | Analyze identifiers for collisions and suspicious near-collisions |
| `shell_split` | Parse shell command into argv with feature detection |
| `shell_quote_join` | Safely quote argv into shell string |
| `argv_compare` | Compare two command strings by parsed argv |
| `unicode_policy_check` | Apply named Unicode safety policy |
| `canonicalize_text` | Apply canonicalization profile |
| `dotenv_validate` | Validate .env-style key/value text |
| `ini_validate` | Validate INI-style config |
| `path_scope_check` | Determine if target path is lexically inside root |
| `path_compare` | Compare paths under explicit normalization rules |

#### Tier 3 — Domain-specific tools

| Tool Name | Description |
|-----------|-------------|
| `unit_convert` | Convert numeric value from one unit to another |
| `unit_info` | Get information about a unit (canonical form, category) |
| `constant_lookup` | Look up physical constant values and symbols |
| `validate_brackets` | Check balanced brackets |
| `validate_regex` | Test regex against samples (legacy alias) |
| `regex_safety_check` | Check regex for catastrophic backtracking risks |
| `validate_schema_light` | Validate JSON against simple schema |
| `json_canonicalize` | Canonicalize JSON with deterministic formatting |
| `json_query` | Query JSON using RFC 6901 JSON Pointer |
| `path_analyze` | Analyze path components, extensions, hidden status |
| `identifier_analyze` | Classify and validate identifier naming conventions |
| `version_compare` | Compare two version strings (semver, loose) |
| `version_constraint_check` | Check if version satisfies constraint (semver/cargo) |
| `toml_shape` | Analyze TOML document structure |
| `cargo_toml_inspect` | Inspect Cargo.toml structure |
| `glob_match` | Match glob pattern against path |
| `list_compare` | Compare two lists (ordered/set/multiset) |
| `list_dedupe` | Remove duplicates from list preserving order |
| `list_sort` | Sort list of strings with normalization |

### math_eval Schema

```python
"math_eval": {
    "description": "Deterministically evaluate arithmetic...",
    "inputSchema": {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "Math expression (e.g., '5 + 3', '30m + 100ft')"
            }
        },
        "required": ["expression"]
    }
}
```

### text_measure Schema

```python
"text_measure": {
    "description": "Measure exact text properties...",
    "inputSchema": {
        "type": "object",
        "properties": {
            "text": {"type": "string"}
        },
        "required": ["text"]
    }
}
```

### text_equal Schema

```python
"text_equal": {
    "description": "Compare two strings under raw, NFC, casefolded...",
    "inputSchema": {
        "type": "object",
        "properties": {
            "a": {"type": "string"},
            "b": {"type": "string"},
            "normalization": {
                "type": "string",
                "enum": ["raw", "NFC", "NFD", "NFKC", "NFKD"],
                "default": "raw"
            },
            "casefold": {"type": "boolean", "default": False},
            "trim": {"type": "boolean", "default": False}
        },
        "required": ["a", "b"]
    }
}
```

---

## tools.py — Tool Implementations

Wraps exact/ functions with error handling, sanitization, and response envelopes.

### Response Helpers

```python
def _error_response(
    error_type: str,
    error: str,
    hints: list[str] | None = None,
    tool: str | None = None
) -> dict:
    """Create standardized error envelope."""
    return ErrorEnvelope(
        ok=False,
        error_type=error_type,
        error=_sanitize_error(error),
        hints=[_sanitize_error(h) for h in (hints or [])],
        tool=tool,
        warnings=None
    )

def _success_response(
    result: Any,
    tool: str | None = None,
    warnings: list[str] | None = None,
    limits_applied: list[str] | None = None,
    findings: list[dict] | None = None,
    machine_code: str | None = None,
    recommended_next_tool: str | list[str] | None = None
) -> dict:
    """Create standardized success envelope."""
    return {
        "ok": True,
        "result": result,
        "tool": tool,
        "warnings": warnings,
        "limits_applied": limits_applied,
        "findings": findings,
        "machine_code": machine_code,
        "recommended_next_tool": recommended_next_tool
    }
```

### Error Sanitization

```python
def _sanitize_error(message: str) -> str:
    """Remove non-ASCII characters from error messages."""
    return message.encode("ascii", "replace").decode("ascii")
```

### Tool Implementations

| Function | Wraps | Notes |
|----------|-------|-------|
| `math_eval(expression)` | `evaluate_raw()` | Math evaluation |
| `unit_convert(value, from_unit, to_unit)` | `get_conversion_factor()` | Unit conversion |
| `unit_info(unit)` | `UNIT_ALIASES, UNIT_CATEGORIES` | Unit information |
| `constant_lookup(name)` | `constants dict` | Physical constant lookup |
| `text_measure(text, detail)` | `measure_text()` | Text metrics |
| `text_equal(a, b, normalization, ...)` | `text_equal()` | String comparison |
| `text_diff_explain(a, b, max_diffs, ...)` | `explain_diff()` | Diff explanation |
| `text_inspect(text, include_codepoints, ...)` | `inspect_text()` | Hidden char inspection |
| `text_count(text, target, normalization, count_mode)` | `count_chars()` | Char counting |
| `text_truncate(text, max_graphemes)` | `truncate_to_grapheme()` | Truncation |
| `text_transform(text, operations, detail)` | `text_transform()` | Text transformations |
| `text_position(text, byte_offset, ...)` | `text_position()` | Position conversion |
| `validate_brackets(text, pairs)` | `check_brackets()` | Bracket validation |
| `validate_json(text)` | `validate_json()` | JSON validation |
| `validate_regex(pattern, samples, ...)` | `regex_test()` | Regex testing |
| `validate_toml(text, detail)` | `validate_toml_text()` | TOML validation |
| `list_compare(a, b, mode, ...)` | `list_compare()` | List comparison |
| `list_dedupe(items, normalization, casefold)` | `list_dedupe()` | List deduping |
| `list_sort(items, normalization, casefold)` | `list_sort()` | List sorting |
| `json_compare(a, b, ...)` | `json_compare()` | JSON comparison |
| `json_extract(text, pointer, ...)` | `json_extract()` | JSON extraction |
| `json_shape(text, max_depth, ...)` | `json_shape()` | JSON shape analysis |
| `json_canonicalize(text, ...)` | `json_canonicalize()` | JSON canonicalization |
| `json_query(text, pointer)` | `json_query()` | JSON query |
| `regex_finditer(pattern, text, ...)` | `regex_finditer()` | Regex find all |
| `regex_safety_check(pattern)` | `regex_safety_check()` | Regex safety check |
| `validate_schema_light(text, schema)` | `validate_schema_light()` | Schema validation |
| `path_normalize(path, platform, ...)` | `path_normalize()` | Path normalization |
| `path_analyze(path, style, ...)` | `path_analyze()` | Path analysis |
| `text_window(text, position, ...)` | `text_window()` | Text window |
| `text_hash(text, algorithms, ...)` | `text_hash()` | Text hashing |
| `text_fingerprint(text, ...)` | `text_fingerprint()` | Text fingerprinting |
| `escape_text(text, mode)` | `escape_text()` | Text escaping |
| `unescape_text(text, mode)` | `unescape_text()` | Text unescaping |
| `identifier_analyze(text, languages)` | `identifier_analyze()` | Identifier analysis |
| `identifier_inspect(identifiers, ...)` | `identifier_inspect()` | Identifier inspection |
| `version_compare(a, b, scheme)` | `version_compare()` | Version comparison |
| `toml_shape(text, max_tables)` | `toml_shape()` | TOML shape analysis |
| `glob_match(pattern, path, ...)` | `glob_match()` | Glob matching |

### Input Limits

```python
MAX_TEXT_LENGTH = 100_000      # Maximum input text length
MAX_EXPRESSION_LENGTH = 10_000 # Maximum math expression
MAX_LIST_ITEMS = 10_000       # Maximum list items for comparison
MAX_REGEX_SAMPLES = 100       # Maximum regex test samples
```

---

## server.py — MCP Protocol Handler

stdio-based JSON-RPC 2.0 server implementation.

### Request Handling

```python
def handle_request(request: Any) -> dict | None:
    """Route MCP request to appropriate handler."""
    if request.get("method") == "tools/list":
        return _handle_list_tools(request)
    elif request.get("method") == "tools/call":
        return _handle_call_tool(request)
    else:
        return _invalid_request(request.get("id"), "Method not found")
```

| Method | Handler | Description |
|--------|---------|-------------|
| `initialize` | `_handle_initialize()` (called inline) | Initialize connection |
| `tools/list` | `_handle_list_tools()` | List available tools |
| `tools/call` | `_handle_call_tool()` | Execute a tool |
| `notifications/initialized` | None | Acknowledgment |

Note: `_handle_initialize` is a separate function in `server.py` called directly from `handle_request`'s routing logic.

### Tool Handler Map

```python
TOOL_HANDLERS: dict[str, Any] = {
    # Tier 0
    "math_eval": math_eval,
    "text_equal": text_equal,
    "text_count": text_count,
    "text_fingerprint": text_fingerprint_mcp,
    "validate_json": validate_json,
    "path_normalize": path_normalize,
    # Tier 1
    "text_diff_explain": text_diff_explain,
    "text_inspect": text_inspect,
    "text_replace_check": text_replace_check,
    "line_range_extract": line_range_extract,
    "line_range_compare": line_range_compare,
    "json_compare": json_compare,
    "json_extract": json_extract,
    "json_shape": json_shape,
    "validate_toml": validate_toml,
    "regex_finditer": regex_finditer,
    "validate_regex": validate_regex,
    "identifier_inspect": identifier_inspect_mcp,
    "text_transform": text_transform,
    "escape_text": escape_text,
    "unescape_text": unescape_text,
    "prompt_input_inspect": prompt_input_inspect_mcp,
    "text_security_inspect": text_security_inspect,
    "edit_preflight": edit_preflight,
    "command_preflight": command_preflight,
    "config_preflight": config_preflight,
    "structured_data_compare": structured_data_compare,
    # Tier 2
    "text_measure": text_measure,
    "text_truncate": text_truncate,
    "text_position": text_position,
    "text_window": text_window,
    "text_hash": text_hash,
    "patch_apply_check": patch_apply_check_mcp,
    "patch_summary": patch_summary_mcp,
    "markdown_structure": markdown_structure_mcp,
    "code_fence_extract": code_fence_extract_mcp,
    "identifier_table_inspect": identifier_table_inspect_mcp,
    "shell_split": shell_split,
    "shell_quote_join": shell_quote_join,
    "argv_compare": shell_argv_compare,
    "unicode_policy_check": unicode_policy_check_mcp,
    "canonicalize_text": canonicalize_text_mcp,
    "dotenv_validate": dotenv_validate_mcp,
    "ini_validate": ini_validate_mcp,
    "path_scope_check": path_scope_check_mcp,
    "path_compare": path_compare_mcp,
    # Tier 3
    "unit_convert": unit_convert,
    "unit_info": unit_info,
    "constant_lookup": constant_lookup,
    "validate_brackets": validate_brackets,
    "regex_safety_check": regex_safety_check,
    "validate_schema_light": validate_schema_light,
    "json_canonicalize": json_canonicalize,
    "json_query": json_query,
    "path_analyze": path_analyze_mcp,
    "identifier_analyze": identifier_analyze,
    "version_compare": version_compare_mcp,
    "version_constraint_check": version_constraint_check_mcp,
    "toml_shape": toml_shape_mcp,
    "cargo_toml_inspect": cargo_toml_inspect_mcp,
    "glob_match": glob_match_mcp,
    "list_compare": list_compare,
    "list_dedupe": list_dedupe_mcp,
    "list_sort": list_sort_mcp,
}
```

### Close Match Suggestions

When an unknown tool is requested, the server suggests close matches:

```python
def _find_close_match(name: str, handlers: dict[str, Any]) -> str | None:
    """Find a case-insensitive close match for tool name."""
    # Returns suggested tool name or None
```

### Error Codes

| Code | Name | Description |
|------|------|-------------|
| -32700 | ParseError | Invalid JSON |
| -32600 | InvalidRequest | Invalid JSON-RPC request |
| -32601 | MethodNotFound | Unknown method |
| -32602 | InvalidParams | Invalid method parameters |
| -32603 | InternalError | Internal error |
| -32000 | ToolError | Tool execution error |

### Response Format

```python
# Success
{
    "jsonrpc": "2.0",
    "id": request_id,
    "result": {
        "ok": True,
        "result": <actual_result>,
        "tool": "tool_name",           # Tool that produced result
        "warnings": [],                # Warning messages
        "limits_applied": [],          # Input limits that were applied
        "findings": [],                # Structured findings/issues
        "machine_code": None,          # Stable error/result code
        "recommended_next_tool": None  # Suggested next tool(s)
    }
}

# Success (transported via content wrapper)
{
    "jsonrpc": "2.0",
    "id": request_id,
    "result": {
        "content": [
            {"type": "text", "text": json.dumps(<actual_result>)}
        ]
    }
}

# Error
{
    "jsonrpc": "2.0",
    "id": request_id,
    "error": {
        "code": -32000,
        "message": "Error description",
        "data": {
            "ok": False,
            "error_type": "...",
            "error": "...",
            "hints": [],
            "tool": "tool_name",
            "warnings": []
        }
    }
}
```

The actual server implementation wraps success results in `{"content": [{"type": "text", "text": json.dumps(result)}]}` while the internal success response has richer metadata fields.

---

## Profile System

Profiles are named subsets of tools that control which tools are available via `tools/call` and returned by `tools/list`. The system is defined in `schemas.py` (profile metadata and tool assignments) and enforced in `server.py` (profile filtering and call-time rejection).

### Data Structures

**`TOOL_METADATA`** (schemas.py:3808–4670): Each tool has a `profiles` list indicating which named profiles include it, plus `llm_exposure` which controls visibility in the `full` profile.

**`TOOL_PROFILES`** (schemas.py:4691): Built dynamically by `_build_profiles()` iterating `TOOL_METADATA` and grouping tools by their `profiles` lists.

**`PROFILE_NAMES`** (schemas.py:4694–4706): Canonical list of all 11 profile names:
`full`, `default`, `codegg_core_min`, `codegg_core`, `codegg_preflight`, `codegg_patch`, `codegg_config`, `codegg_unicode_security`, `codegg_shell`, `codegg_repo_audit`, `human_math`.

### Profile Selection

The active profile is set at server startup via `EGGCALC_MCP_PROFILE` environment variable (default: `"full"`). Invalid profile names cause `SystemExit(1)` at import time.

```python
_active_profile: str = os.environ.get("EGGCALC_MCP_PROFILE", "full")
```

### `get_profile_tools()` (server.py:313–329)

Special-cases the `full` profile: instead of using `TOOL_PROFILES["full"]`, it dynamically returns all tools where `llm_exposure != "hidden"`. This allows hiding tools from the `full` profile without removing them from individual named profiles.

### Enforcement

- **`tools/list`** (server.py:1006–1106): Filters `TOOL_SCHEMAS` by `get_profile_tools(profile_filter)`. Additional filters (`tier`, `tags`, `names`) are applied after profile selection.
- **`tools/call`** (server.py:807–831): Rejects tools not in the active profile with JSON-RPC error `-32602` before the handler executes.
- **`profiles/list`**: Returns all profile names, their tool lists, and tool counts.

### Schema Detail

`EGGCALC_MCP_SCHEMA_DETAIL` (default `"full"`) controls schema verbosity globally. Overridden per-request via `schema_detail` parameter in `tools/list`:

- **`full`**: Raw schemas with all fields
- **`normal`**: Truncated descriptions, compact output schema (`normal_schema()`)
- **`compact`**: Types and required fields only (`compact_schema()`)

---

## Usage

### CLI Mode (Calculator)

```bash
python eggcalc.py "five plus three"
# Output: 8
```

### MCP Mode (Server)

```bash
python eggcalc.py --mcp
```

Then send JSON-RPC requests via stdio:

```json
// List tools
{"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}

// Call tool
{"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
    "name": "text_measure",
    "arguments": {"text": "Hello, World!"}
}}
```

---

## Architecture Notes

```
┌─────────────────────────────────────────────────────────────────────┐
│                            MCP Server                                │
│                       (stdio-based JSON-RPC)                         │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────────────┐    │
│  │  schemas.py │     │  tools.py   │     │     server.py      │    │
│  │             │     │             │     │                     │    │
│  │ TOOL_SCHEMAS│────▶│ Wraps exact │◀────│ Request routing    │    │
│  │             │     │ functions   │     │ Error handling     │    │
│  └─────────────┘     └──────┬──────┘     └─────────────────────┘    │
│                             │                                        │
├─────────────────────────────┴────────────────────────────────────────┤
│                            exact/                                     │
│                    (Text analysis primitives)                        │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Features

1. **Unified Tool Registry** — `TOOL_SCHEMAS` in schemas.py is single source of truth
2. **Case-insensitive matching** — Tool names matched case-insensitively with suggestions
3. **Standardized Responses** — All tools use error envelopes and JSON-RPC result wrapping
4. **Error Sanitization** — Non-ASCII stripped from error messages
5. **Input Validation** — Length limits enforced before processing

### Cancellation Semantics

Cancellation is best-effort. The server checks cancellation records before dispatching tools, but once a tool is running in the thread pool, Python does not preemptively kill the running thread.

- **Pre-dispatch:** A cancelled request ID is immediately rejected with `error_type: "cancelled"`.
- **Post-dispatch:** `Future.cancel()` only succeeds if the worker has not started yet (Python's `ThreadPoolExecutor` semantics). In practice, most tools will have already started, so cancellation will not stop them.
- **Timeout:** Tool calls are bounded by `EGGCALC_MCP_MAX_TOOL_TIMEOUT_SECONDS` (default 30s). Timeout returns `error_type: "timeout"` to the client; the worker continues until it finishes.
- **Bounded pool:** The `ThreadPoolExecutor` (default 16 workers) provides natural back-pressure.
- **Future enhancement:** Cooperative cancellation via a cancellation token checked mid-execution could allow tools to exit early. See `docs/mcp.md` for full details.

### MCP vs Direct Usage

| Feature | MCP Server | Direct Import |
|---------|-----------|----------------|
| Interface | stdio/JSON-RPC | Python API |
| Use case | AI agents | Embedded usage |
| Functions | Subset | All |
| Error format | Envelope | Exceptions |

## Entry Point

### `main() -> int`

Main entry point:
1. Reads JSON-RPC requests from stdin (line by line)
2. Handles each request
3. Writes responses to stdout
4. Returns exit code

For build compatibility, this is also available as `mcp_main()`:

```python
from eggcalc.mcp.server import main, mcp_main  # Both refer to same function
```