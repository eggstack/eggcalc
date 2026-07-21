# mcp/ — Model Context Protocol Server

MCP server providing AI agent tool access to eggcalc's text analysis functions via a stdio-based JSON-RPC interface.

## Table of Contents

- [Module Structure](#module-structure)
- [Overview](#overview)
- [Architecture](#architecture)
- [schemas.py — Tool Schemas](#schemaspy--tool-schemas)
  - [Error Envelope](#error-envelope)
  - [TOOL_SCHEMAS](#tool_schemas)
  - [TOOL_METADATA](#tool_metadata)
- [tools.py — Tool Implementations](#toolspy--tool-implementations)
  - [Response Helpers](#response-helpers)
  - [Error Sanitization](#error-sanitization)
  - [Input Limits](#input-limits)
- [server.py — MCP Protocol Handler](#serverpy--mcp-protocol-handler)
  - [Server Constants](#server-constants)
  - [Request Handling](#request-handling)
  - [Tool Handler Map](#tool-handler-map)
  - [Close Match Suggestions](#close-match-suggestions)
  - [Argument Validation](#argument-validation)
  - [Error Codes](#error-codes)
  - [Response Format](#response-format)
- [Profile System](#profile-system)
  - [Data Structures](#data-structures)
  - [Profile Selection](#profile-selection)
  - [Enforcement](#enforcement)
  - [Schema Detail](#schema-detail)
- [Usage](#usage)
- [State Isolation (Release 5)](#state-isolation-release-5)
  - [McpServerConfig](#mcpserverconfig)
  - [McpServer](#mcpserver)
  - [ToolRegistry](#toolregistry)
  - [ToolExecutor](#toolexecutor)
  - [ConfigSnapshot / ConfigManager](#configsnapshot--configmanager)
  - [Evaluator Policy Isolation](#evaluator-policy-isolation)
  - [Backward Compatibility](#backward-compatibility)
- [Architecture Notes](#architecture-notes)

## Module Structure

```
mcp/
├── __init__.py   # Package init, re-exports main, handle_request, TOOL_SCHEMAS, tools
├── schemas.py    # Tool input/output schemas, profiles, metadata
├── tools.py      # Tool implementations (wraps exact/ functions)
└── server.py     # MCP protocol handler, request routing, thread pool
```

## Overview

The MCP server exposes text analysis, Unicode, math, and unit tools to AI agents. It provides:
- JSON-RPC 2.0 protocol handling over stdio
- Tool discovery via `tools/list`
- Tool execution via `tools/call`
- Profile management via `profiles/list`
- Standardized error envelopes
- Input validation and schema validation
- Case-insensitive tool matching with Levenshtein distance suggestions
- Bounded thread pool for concurrent tool execution
- Orphaned child process cleanup
- Rate limiting
- Config loading disabled by default (security)

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

## State Isolation (Release 5)

Release 5 replaces implicit module-level state with explicit objects that own their dependencies. Each `McpServer` instance is self-contained and can run independently of other instances or module-level globals.

### McpServerConfig

Frozen dataclass containing all server policy:

- `profile`, `schema_detail`, `limits`, `timeouts`, `protocol versions`
- Constructed once via `McpServerConfig()` or `McpServerConfig.from_environment()`
- Immutable after construction; values validated and clamped in `__post_init__`

```python
config = McpServerConfig()                    # defaults from environment
config = McpServerConfig(profile="default")   # explicit overrides
```

### McpServer

Explicit server object owning all components:

- `McpServerConfig` — immutable policy
- `ToolRegistry` — tool definitions
- `ToolExecutor` — execution engine with bounded thread pool
- `ConfigManager` — atomic configuration snapshots
- `Evaluator` — dedicated instance with MCP-safe policy
- Session creation via `create_session()`

```python
server = McpServer(config=McpServerConfig())
session = server.create_session()
```

### ToolRegistry

Owns tool handlers, schemas, metadata, and profiles. Wraps the module-level `TOOL_HANDLERS`, `TOOL_SCHEMAS`, etc. Provides lookup by name, profile filtering, and close-match suggestions without relying on module globals.

### ToolExecutor

Owns the bounded thread pool, argument validation, timeout enforcement, cancellation checking, and orphan cleanup. Does not depend on session globals. Each `McpServer` instance gets its own executor with independently configurable worker count and timeout.

### ConfigSnapshot / ConfigManager

`ConfigSnapshot` is a frozen dataclass for atomic configuration replacement with fields: `generation`, `constants`, `functions`, `units`, and `policy`. `ConfigManager` holds the current snapshot behind a lock, supporting atomic swaps and generation tracking. This allows runtime config changes without corrupting in-flight requests.

### Evaluator Policy Isolation

`McpServer` creates its own `Evaluator` via `create_evaluator()`. This avoids mutating the module-level `_mcp_mode` or `_default_evaluator`. Two `McpServer` instances can have different evaluator policies (e.g., one with `allow_random=False`, another with `allow_random=True`).

### Cache Isolation

The global evaluation cache (`_cache` in evaluator.py) is generation-keyed: `_clear_global_cache()` increments `_config_generation` on each call. MCP tool handlers use `evaluate_with_timeout()` which spawns subprocesses with independent caches, so the global cache is not consulted during tool execution. For library API callers, `EggCalcApp` provides instance-local caches. The `get_config_generation()` function exposes the current generation counter for diagnostics.

### Diagnostics

`McpServer.diagnostic()` returns a deterministic, JSON-serializable dict with:

| Field | Description |
|-------|-------------|
| `config_generation` | Per-server config snapshot generation |
| `global_config_generation` | Global evaluator config generation counter |
| `profile` | Active MCP profile name |
| `registry_tool_count` | Number of tools in registry |
| `max_tool_workers` | Configured worker pool size |
| `active_workers` | Currently executing tool calls |
| `max_tool_queue_size` | Maximum queued requests before rejection |
| `pending_count` | Requests waiting to start execution |
| `max_tool_timeout` | Configured timeout in seconds |
| `orphan_count` | Tracked orphaned subprocesses |
| `session_count` | Active sessions on this server |
| `config_units_count` | Unit entries in current config snapshot |
| `closed` | Whether server has been shut down |

### Backward Compatibility

Module-level `handle_request()` continues to work but emits `DeprecationWarning` when called without an explicit session. It routes through a compatibility path that does not affect explicitly constructed servers.

## schemas.py — Tool Schemas

Defines input/output schemas for each MCP tool. Also contains `TOOL_METADATA`, `TOOL_PROFILES`, and `PROFILE_NAMES`.

### Error Envelope

```python
class ErrorEnvelope(TypedDict):
    ok: bool                    # Always False for errors
    error_type: str             # Error category
    error: str                  # Error message (ASCII-safe)
    hints: list[str]           # Suggested fixes
    tool: str | None            # Tool name that produced error
    warnings: list[str]        # Warning messages (empty list, not None)
```

### TOOL_SCHEMAS

Registry of all available tools (77 total). Tools are organized by tier for selective exposure. The tiers reflect actual schema definitions:

#### Tier 0 — Ultra-common (minimal schema)

| Tool Name | Category | Description |
|-----------|----------|-------------|
| `math_eval` | math | Evaluate arithmetic, unit conversions, constants |
| `text_equal` | text | Compare strings with multiple equality modes |
| `text_count` | text | Count characters or frequency table |
| `text_measure` | text | Measure text properties (bytes, codepoints, words, lines) |
| `text_fingerprint` | text | Compute deterministic SHA-256 fingerprint |
| `validate_json` | validation | Validate JSON syntax |
| `path_normalize` | path | Normalize path using posixpath/ntpath semantics |

#### Tier 1 — Default coding-agent sanity tools

| Tool Name | Category | Description |
|-----------|----------|-------------|
| `text_diff_explain` | text | Explain string differences |
| `text_inspect` | text | Inspect for hidden characters, confusables |
| `text_replace_check` | text | Check replacement before applying |
| `text_window` | text | Get window around position with context lines |
| `text_security_inspect` | text | Composite security inspection |
| `escape_text` | text | Escape text for various output formats |
| `unescape_text` | text | Unescape text from various formats |
| `line_range_extract` | text | Extract exact line ranges with fingerprints |
| `json_compare` | json | Compare two JSON documents semantically |
| `json_canonicalize` | json | Canonicalize JSON with deterministic formatting |
| `json_query` | json | Query JSON using RFC 6901 JSON Pointer (deprecated) |
| `validate_toml` | validation | Validate TOML configuration files |
| `validate_brackets` | validation | Check balanced brackets |
| `validate_regex` | regex | Test regex against samples |
| `regex_finditer` | regex | Find all regex matches with positions |
| `regex_safety_check` | regex | Check regex for catastrophic backtracking risks |
| `glob_match` | path | Match glob pattern against path |
| `identifier_inspect` | identifier | Inspect identifiers for validity and collisions |
| `list_dedupe` | list | Remove duplicates from list preserving order |
| `list_sort` | list | Sort list of strings with normalization |
| `command_preflight` | shell | Composite command safety check |
| `config_preflight` | config | Composite config safety check |
| `edit_preflight` | patch | Composite edit safety check |

#### Tier 2 — Heavier analysis tools

| Tool Name | Category | Description |
|-----------|----------|-------------|
| `unit_convert` | math | Convert numeric value from one unit to another |
| `unit_info` | math | Get information about a unit |
| `constant_lookup` | math | Look up physical constant values and symbols |
| `text_position` | text | Convert between byte offsets, codepoint indices, line/column |
| `text_transform` | text | Apply text transformations (normalization, casefold, etc.) |
| `text_hash` | text | Compute cryptographic hashes of text |
| `json_extract` | json | Extract value using RFC 6901 JSON Pointer |
| `structured_data_compare` | json | Composite structured data comparison |
| `line_range_compare` | text | Compare line ranges from two texts |
| `markdown_structure` | markdown | Parse markdown structure (headings, links, code fences) |
| `markdown_link_check_lexical` | text | Check markdown links lexically |
| `code_fence_extract` | markdown | Extract fenced code blocks with exact ranges |
| `patch_apply_check` | patch | Validate and simulate a unified diff against text |
| `patch_summary` | patch | Summarize a unified diff without applying |
| `patch_conflict_markers_inspect` | patch | Inspect patch conflict markers |
| `diff_touched_paths` | patch | List paths touched by a unified diff |
| `diff_hunk_ranges` | patch | Extract hunk ranges from a unified diff |
| `diff_file_headers` | patch | Extract file headers from a unified diff |
| `unified_diff_validate` | patch | Validate unified diff format |
| `path_analyze` | path | Analyze path components, extensions, hidden status |
| `path_compare` | path | Compare paths under explicit normalization rules |
| `path_scope_check` | path | Determine if target path is lexically inside root |
| `shell_split` | shell | Parse shell command into argv with feature detection |
| `shell_quote_join` | shell | Safely quote argv into shell string |
| `argv_compare` | shell | Compare two command strings by parsed argv |
| `unicode_policy_check` | unicode | Apply named Unicode safety policy |
| `canonicalize_text` | unicode | Apply canonicalization profile |
| `prompt_input_inspect` | text | Composite prompt input inspection |
| `dotenv_validate` | config | Validate .env-style key/value text |
| `ini_validate` | config | Validate INI-style config |
| `toml_shape` | toml | Analyze TOML document structure |
| `version_compare` | version | Compare two version strings |
| `list_compare` | list | Compare two lists (ordered/set/multiset) |
| `llm_json_output_check` | text | Check LLM JSON output validity |
| `pyproject_inspect` | manifest | Inspect pyproject.toml structure |
| `package_json_inspect` | manifest | Inspect package.json structure |
| `requirements_inspect` | manifest | Inspect requirements*.txt files |
| `go_mod_inspect` | manifest | Inspect go.mod structure |
| `lockfile_summary` | manifest | Summarize lockfile contents |
| `repo_file_inventory` | repo | Inventory repository file structure |

#### Tier 3 — Domain-specific tools

| Tool Name | Category | Description |
|-----------|----------|-------------|
| `validate_schema_light` | validation | Validate JSON against simple schema |
| `text_truncate` | text | Truncate to grapheme boundary |
| `json_shape` | json | Analyze JSON structure without returning values |
| `identifier_analyze` | identifier | Classify and validate identifier naming conventions |
| `identifier_table_inspect` | identifier | Analyze identifiers for collisions and suspicious near-collisions |
| `version_constraint_check` | version | Check if version satisfies constraint |
| `cargo_toml_inspect` | cargo | Inspect Cargo.toml structure |

### TOOL_METADATA

Per-tool metadata used for profile building and exposure control. Each entry includes:

- `category` — Tool category (math, text, path, validation, regex, identifier, json, list, shell, config, unicode, markdown, patch, toml, version, manifest, cargo, repo)
- `tier` — Tier level (0–3)
- `profiles` — List of named profiles that include this tool
- `llm_exposure` — Exposure level: `"default"`, `"contextual"`, `"harness_only"`, or `"expert_only"`. Tools with `"hidden"` are excluded from the `full` profile.
- `harness_use` — How the tool is used by the harness (e.g., `"edit_preflight"`, `"command_preflight"`, `"config_preflight"`, `"prompt_input_preflight"`, `"path_preflight"`, `"repo_audit"`, `"reasoning_only"`, `"none"`)
- `cost` — Approximate cost: `"cheap"`, `"moderate"`, or `"heavy"`
- `stability` — Stability level: `"stable"` or `"deprecated"`
- `composite` — Whether the tool is a composite (calls multiple sub-tools)

---

## tools.py — Tool Implementations

Wraps exact/ functions with error handling, sanitization, and response envelopes. 77 tool functions implemented.

### Response Helpers

```python
def _error_response(
    error_type: str,
    error: str,
    hints: list[str] | None = None,
    tool: str | None = None,
) -> dict[str, Any]:
    """Create standardized error envelope."""
    return ErrorEnvelope(
        ok=False,
        tool=tool,
        error_type=error_type,
        error=_sanitize_error(error),
        hints=[_sanitize_error(h) for h in (hints or [])],
        warnings=[],
    )

def _success_response(
    result: Any,
    tool: str | None = None,
    warnings: list[str] | None = None,
    limits_applied: list[str] | None = None,
    findings: list[dict] | None = None,
    machine_code: str | None = None,
    recommended_next_tool: str | list[str] | None = None,
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
        "recommended_next_tool": recommended_next_tool,
    }
```

### Error Sanitization

```python
def _sanitize_error(message: str) -> str:
    """Remove non-ASCII characters from error messages."""
    return message.encode("ascii", "replace").decode("ascii")
```

### Input Limits

```python
MAX_TEXT_LENGTH = 100_000              # Maximum input text length
MAX_EXPRESSION_LENGTH = 10_000         # Maximum math expression
MAX_LIST_ITEMS = 10_000               # Maximum list items for comparison
MAX_PAIRWISE_ITEMS = 1_000            # Maximum items for O(N^2) pairwise comparisons
MAX_REGEX_SAMPLES = 100               # Maximum regex test samples
MAX_REGEX_SAMPLE_LENGTH = 10_000      # Maximum regex sample length
MAX_PATTERN_LENGTH_REGEX = 1_000      # Maximum regex pattern length
MAX_MATCHES_REGEX = 100               # Maximum regex matches returned
MAX_TEXT_LENGTH_REGEX = 100_000       # Maximum text for regex operations
REGEX_TIMEOUT_SECONDS = 5             # Regex execution timeout
MAX_CONCURRENT_SPAWNED = 4            # Max concurrent child processes
MAX_ORPHANED_REGEX_PROCESSES = 256    # Max orphaned regex child processes
```

---

## server.py — MCP Protocol Handler

stdio-based JSON-RPC 2.0 server implementation with bounded thread pool, rate limiting, and orphaned process cleanup.

### Session Lifecycle

The MCP server uses `McpSession` and `McpSessionState` to manage protocol lifecycle:

```
UNINITIALIZED --initialize request--> INITIALIZING
INITIALIZING  --notifications/initialized--> READY
READY         --EOF/shutdown/close--> CLOSED
```

| State | Allowed Methods |
|-------|----------------|
| `UNINITIALIZED` | `initialize` only (plus `ping`, `notifications/initialized`, `notifications/cancelled` which are silently accepted) |
| `INITIALIZING` | All methods except `initialize` are rejected until `notifications/initialized` arrives |
| `READY` | All methods. Tool requests (`tools/list`, `tools/call`) are dispatched normally |
| `CLOSED` | All methods rejected |

Tool requests before initialization return `-32600` ("Server not initialized"). Duplicate `initialize` requests return `-32600` ("Server already initialized").

### Protocol Version Negotiation

Supported versions are defined in `SUPPORTED_PROTOCOL_VERSIONS = ("2024-11-05", "2025-11-25")` with `LATEST_SUPPORTED_PROTOCOL_VERSION = "2025-11-25"`. The `initialize` handler inspects the client's `protocolVersion`:

- If the client requests a supported version, the server responds with that version.
- If the client omits `protocolVersion` or requests an unsupported version, the server responds with the latest supported version.

This avoids breaking clients that depend on a specific version string while keeping the server future-proof.

The draft `2026-07-28` stateless MCP protocol revision is intentionally out of scope until final publication and a separate migration plan. The current stdio lifecycle implementation remains stateful.

### Notification Dispatch

Notifications (JSON-RPC messages with no `id`) are handled silently — they never produce a response. The `McpSession.handle_message()` method dispatches `notifications/initialized` and `notifications/cancelled` to their handlers and returns `None`. Unknown notifications are also silently ignored per the protocol.

### Server Constants

All configurable via environment variables with clamping to safe ranges:

| Constant | Env Var | Default | Range | Description |
|----------|---------|---------|-------|-------------|
| `MAX_REQUEST_BYTES` | `EGGCALC_MCP_MAX_REQUEST_BYTES` | 1,000,000 | 1,000–100,000,000 | Max request body size |
| `MAX_OUTPUT_BYTES` | `EGGCALC_MCP_MAX_OUTPUT_BYTES` | 1,000,000 | 1,000–100,000,000 | Max tool output size |
| `MAX_REQUESTS_PER_SECOND` | `EGGCALC_MCP_MAX_REQUESTS_PER_SECOND` | 10 | 0.1–1000 | Rate limit (sliding window) |
| `MAX_TOOL_TIMEOUT_SECONDS` | `EGGCALC_MCP_MAX_TOOL_TIMEOUT_SECONDS` | 30 | 1–300 | Tool execution timeout |
| `MAX_CANCELLED_REQUESTS` | `EGGCALC_MCP_MAX_CANCELLED_REQUESTS` | 10,000 | 100–1,000,000 | Max cancellation records |
| `MAX_TOOL_WORKERS` | `EGGCALC_MCP_MAX_TOOL_WORKERS` | 16 | 1–128 | Thread pool worker count |
| `MAX_REQUEST_ID_LENGTH` | — | 1,024 | — | Max request ID length |

### Request Handling

```python
def handle_request(request: Any, session: McpSession | None = None) -> dict | None:
    """Route MCP request to appropriate handler.
    
    When session is None, a module-level default session (starting in
    READY state) is used for backward compatibility. This path is
    deprecated and emits a DeprecationWarning.
    """
```

| Method | Handler | Description |
|--------|---------|-------------|
| `initialize` | `_handle_initialize()` | Initialize connection, return capabilities |
| `notifications/initialized` | None (returns None) | Client acknowledgment |
| `tools/list` | `_handle_list_tools()` | List available tools (with filtering) |
| `tools/call` | `_handle_call_tool()` | Execute a tool |
| `profiles/list` | `_handle_list_profiles()` | List all profiles and their tools |
| `notifications/cancelled` | None (records cancellation) | Client-side request cancellation |
| `ping` | Inline response | Health check, returns empty result |

### Tool Handler Map

`TOOL_HANDLERS` in server.py maps tool names to handler functions (77 entries). All tools are registered alphabetically:

```python
TOOL_HANDLERS: dict[str, Any] = {
    "argv_compare": shell_argv_compare,
    "canonicalize_text": canonicalize_text_mcp,
    "cargo_toml_inspect": cargo_toml_inspect_mcp,
    "code_fence_extract": code_fence_extract_mcp,
    "command_preflight": command_preflight,
    "config_preflight": config_preflight,
    "constant_lookup": constant_lookup,
    "diff_file_headers": diff_file_headers_mcp,
    "diff_hunk_ranges": diff_hunk_ranges_mcp,
    "diff_touched_paths": diff_touched_paths_mcp,
    "dotenv_validate": dotenv_validate_mcp,
    "edit_preflight": edit_preflight,
    "escape_text": escape_text,
    "glob_match": glob_match_mcp,
    "go_mod_inspect": go_mod_inspect_mcp,
    "identifier_analyze": identifier_analyze,
    "identifier_inspect": identifier_inspect_mcp,
    "identifier_table_inspect": identifier_table_inspect_mcp,
    "ini_validate": ini_validate_mcp,
    "json_canonicalize": json_canonicalize,
    "json_compare": json_compare,
    "json_extract": json_extract,
    "json_query": json_query,
    "json_shape": json_shape,
    "line_range_compare": line_range_compare,
    "line_range_extract": line_range_extract,
    "list_compare": list_compare,
    "list_dedupe": list_dedupe_mcp,
    "list_sort": list_sort_mcp,
    "llm_json_output_check": llm_json_output_check_mcp,
    "lockfile_summary": lockfile_summary_mcp,
    "markdown_link_check_lexical": markdown_link_check_lexical_mcp,
    "markdown_structure": markdown_structure_mcp,
    "math_eval": math_eval,
    "package_json_inspect": package_json_inspect_mcp,
    "patch_apply_check": patch_apply_check_mcp,
    "patch_conflict_markers_inspect": patch_conflict_markers_inspect_mcp,
    "patch_summary": patch_summary_mcp,
    "path_analyze": path_analyze_mcp,
    "path_compare": path_compare_mcp,
    "path_normalize": path_normalize,
    "path_scope_check": path_scope_check_mcp,
    "prompt_input_inspect": prompt_input_inspect_mcp,
    "pyproject_inspect": pyproject_inspect_mcp,
    "regex_finditer": regex_finditer,
    "regex_safety_check": regex_safety_check,
    "repo_file_inventory": repo_file_inventory_mcp,
    "requirements_inspect": requirements_inspect_mcp,
    "shell_quote_join": shell_quote_join,
    "shell_split": shell_split,
    "structured_data_compare": structured_data_compare,
    "text_count": text_count,
    "text_diff_explain": text_diff_explain,
    "text_equal": text_equal,
    "text_fingerprint": text_fingerprint_mcp,
    "text_hash": text_hash,
    "text_inspect": text_inspect,
    "text_measure": text_measure,
    "text_position": text_position,
    "text_replace_check": text_replace_check,
    "text_security_inspect": text_security_inspect,
    "text_transform": text_transform,
    "text_truncate": text_truncate,
    "text_window": text_window,
    "toml_shape": toml_shape_mcp,
    "unescape_text": unescape_text,
    "unicode_policy_check": unicode_policy_check_mcp,
    "unified_diff_validate": unified_diff_validate_mcp,
    "unit_convert": unit_convert,
    "unit_info": unit_info,
    "validate_brackets": validate_brackets,
    "validate_json": validate_json,
    "validate_regex": validate_regex,
    "validate_schema_light": validate_schema_light,
    "validate_toml": validate_toml,
    "version_compare": version_compare_mcp,
    "version_constraint_check": version_constraint_check_mcp,
}
```

### Close Match Suggestions

When an unknown tool is requested, the server suggests close matches using Levenshtein edit distance:

```python
def _find_close_match(name: str, handlers: dict[str, Any]) -> str | None:
    """Find a case-insensitive close match for tool name."""
```

The algorithm:
1. Check for exact case-insensitive match first
2. Check word-boundary substring matches (e.g., `text_eq` matches `text_equal`)
3. Fall back to Levenshtein edit distance with threshold of `min(len(s1), len(s2)) // 2`

### Argument Validation

Two layers of validation before tool execution:

1. **Signature validation** (`_validate_arguments`): Validates arguments against the handler's Python function signature — checks for unexpected kwargs and missing required args.
2. **Schema validation** (`_validate_arguments_schema`): Validates arguments against `TOOL_SCHEMAS[name]["inputSchema"]` — checks types, enums, const values, string length constraints, numeric ranges, patterns, array constraints, and recursive nested object/array validation.

### Error Codes

| Code | Name | Description |
|------|------|-------------|
| -32700 | ParseError | Invalid JSON |
| -32600 | InvalidRequest | Invalid JSON-RPC request (batch requests rejected, rate limit, server already initialized, not initialized) |
| -32601 | MethodNotFound | Unknown method or tool |
| -32602 | InvalidParams | Invalid method parameters, profile violation, schema validation error |
| -32603 | InternalError | Internal error (unhandled exceptions) |
| -32000 | ToolError | Tool execution error (handler exception) |

Centralized error helpers (`_jsonrpc_error`, `_parse_error`, `_invalid_request`, `_method_not_found`, `_invalid_params`, `_internal_error`) prevent code drift across return paths.

### Response Format

```python
# Success (transported via content wrapper)
{
    "jsonrpc": "2.0",
    "id": request_id,
    "result": {
        "content": [
            {"type": "text", "text": json.dumps(result)}
        ]
    }
}

# Success with error envelope (tool returned ok=False)
{
    "jsonrpc": "2.0",
    "id": request_id,
    "result": {
        "content": [
            {"type": "text", "text": json.dumps({
                "ok": False,
                "error_type": "...",
                "error": "...",
                "hints": [],
                "tool": "tool_name",
                "warnings": []
            })}
        ],
        "isError": true
    }
}

# Timeout (result.content is an error envelope)
{
    "jsonrpc": "2.0",
    "id": request_id,
    "result": {
        "content": [
            {"type": "text", "text": json.dumps({
                "ok": False,
                "error": "Tool 'name' execution timed out after 30s",
                "error_type": "timeout",
                "hints": ["Try a simpler input or shorter text"],
                "tool": "name",
                "warnings": []
            })}
        ],
        "isError": true
    }
}

# Cancelled (pre-dispatch)
{
    "jsonrpc": "2.0",
    "id": request_id,
    "result": {
        "content": [
            {"type": "text", "text": json.dumps({
                "ok": False,
                "error": "Tool 'name' request was cancelled",
                "error_type": "cancelled",
                "hints": [],
                "tool": "name",
                "warnings": []
            })}
        ],
        "isError": true
    }
}

# Error
{
    "jsonrpc": "2.0",
    "id": request_id,
    "error": {
        "code": -32000,
        "message": "Tool execution error: ...",
    }
}
```

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
- **`normal`**: Truncated descriptions (240 chars), compact output schema (`normal_schema()`). Input properties truncated to 120 chars. Includes tier, tags, category, llm_exposure, cost.
- **`compact`**: Types and required fields only (`compact_schema()`). Descriptions truncated to 120 chars (tool) / 80 chars (properties). Includes category, llm_exposure, cost.

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
│  │ TOOL_SCHEMAS│────>│ Wraps exact │<────│ Request routing    │    │
│  │ TOOL_METADATA│    │ functions   │     │ Error handling     │    │
│  │ TOOL_PROFILES│    │             │     │ Thread pool        │    │
│  └─────────────┘     └──────┬──────┘     │ Rate limiting      │    │
│                             │             │ Orphan cleanup     │    │
├─────────────────────────────┴─────────────┴─────────────────────────┤
│                            exact/                                     │
│                    (Text analysis primitives)                        │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Features

1. **Unified Tool Registry** — `TOOL_SCHEMAS` in schemas.py is single source of truth
2. **Case-insensitive matching** — Tool names matched case-insensitively with Levenshtein suggestions
3. **Standardized Responses** — All tools use error envelopes and JSON-RPC content wrapper
4. **Error Sanitization** — Non-ASCII stripped from error messages
5. **Dual Validation** — Handler signature validation + JSON Schema validation before execution
6. **Bounded Thread Pool** — `ThreadPoolExecutor` (default 16 workers) with natural back-pressure
7. **Rate Limiting** — Sliding window rate limiter (default 10 req/s)
8. **Orphan Cleanup** — Tracks and terminates orphaned child processes from timed-out tools
9. **MCP-Safe Defaults** — `allow_random=False`, `allow_side_effects=False` set on first request
10. **Config Security** — `EGGCALC_NO_CONFIG=1` blocks cwd-local config loading at import time

### Cancellation Semantics

Cancellation is best-effort. The server checks cancellation records before dispatching tools, but once a tool is running in the thread pool, Python does not preemptively kill the running thread.

- **Pre-dispatch:** A cancelled request ID is immediately rejected with `error_type: "cancelled"`.
- **Post-dispatch:** `Future.cancel()` only succeeds if the worker has not started yet (Python's `ThreadPoolExecutor` semantics). In practice, most tools will have already started, so cancellation will not stop them.
- **Timeout:** Tool calls are bounded by `EGGCALC_MCP_MAX_TOOL_TIMEOUT_SECONDS` (default 30s). Timeout returns `error_type: "timeout"` to the client; the worker continues until it finishes.
- **Bounded pool:** The `ThreadPoolExecutor` (default 16 workers) provides natural back-pressure.
- **Future enhancement:** Cooperative cancellation via a cancellation token checked mid-execution could allow tools to exit early.

### MCP vs Direct Usage

| Feature | MCP Server | Direct Import |
|---------|-----------|----------------|
| Interface | stdio/JSON-RPC | Python API |
| Use case | AI agents | Embedded usage |
| Functions | 77 tools | All |
| Error format | Envelope | Exceptions |
| Config loading | Blocked | Opt-in via `EGGCALC_LOAD_CONFIG` |

## Entry Point

### `main() -> int`

Main entry point:
1. Sets `EGGCALC_NO_CONFIG=1`
2. Creates one `McpSession(initial_state=UNINITIALIZED)` per connection
3. Reads JSON-RPC requests from stdin (line by line)
4. Validates JSON-RPC version, ID, method
5. Enforces rate limiting (sliding window)
6. Rejects oversized requests and batch requests
7. Handles each request via `handle_request(request, session=session)`
8. Writes responses to stdout
9. Returns exit code on EOF or `BrokenPipeError`

For build compatibility, this is also available as `mcp_main()`:

```python
from eggcalc.mcp.server import main, mcp_main  # Both refer to same function
```
