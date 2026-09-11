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
  - [Progressive Disclosure (Plan 041)](#progressive-disclosure-plan-041)
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

Owns tool handlers, schemas, metadata, and profiles. Wraps the module-level `TOOL_HANDLERS`, `TOOL_SCHEMAS`, etc. Provides lookup by name, profile filtering, close-match suggestions, and deterministic lexical discovery (`search_tools()`, Plan 041) without relying on module globals. Internal state is deeply immutable after construction via `freeze_owned()` — nested dicts, lists, and profile lists are `MappingProxyType`/`tuple`/`frozenset` so callers cannot mutate the registry through constructor inputs or accessor return values. `tool_names` returns `tuple[str, ...]` (not `list`).

Validates at construction time:
- Duplicate handler names
- Schemas/metadata without corresponding handlers
- Unsupported `llm_exposure` values
- Malformed `selection_summary`/`keywords` (when present; the canonical
  catalog is strictly validated at import by
  `schemas._validate_catalog_metadata()`)
- Empty profile names
- Profiles referencing unknown tools

### ToolExecutor

Owns the bounded thread pool, argument validation, timeout enforcement, cancellation checking, and orphan cleanup. Does not depend on session globals. Each `McpServer` instance gets its own executor with independently configurable worker count and timeout.

### ConfigSnapshot / ConfigManager

`ConfigSnapshot` is a frozen dataclass for atomic configuration replacement with fields: `generation`, `constants`, `functions`, `units`, and `policy`. The `policy` field is `EvaluationPolicy | str` (backward compatible — strings are auto-converted to the enum). `__post_init__()` defensively copies all dict fields to prevent external mutation. `ConfigManager` holds the current snapshot behind a lock, supporting atomic swaps and generation tracking. This allows runtime config changes without corrupting in-flight requests.

### EvaluationPolicy

```python
class EvaluationPolicy(enum.Enum):
    DEFAULT = "default"
    STRICT = "strict"
    PERMISSIVE = "permissive"
```

Valid evaluation policy values for server configuration. `parse_config_snapshot()` validates policy values and rejects invalid strings.

### ConfigCandidate / RuntimeContext

`ConfigCandidate` is a frozen dataclass holding validated constants, functions, and policy ready to be turned into a `ConfigSnapshot`. `RuntimeContext` is a frozen dataclass pairing a `ConfigSnapshot` with the `Evaluator` instance built from it, enabling atomic replacement without partial updates.

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

## schemas.py — Tool Schemas (Plan 040 authority model)

Two authorities, different concerns (see `authority_inventory.md`):

- `TOOL_METADATA` — catalog/selection authority: canonical name, `handler`
  locator (attribute in `mcp/tools.py`), category/tier/tags/profiles/aliases/
  exposure/harness/cost/stability/composite, plus Plan 041 selection fields:
  `selection_summary` (authored "choose this over neighbors" signal,
  `<= SELECTION_SUMMARY_MAX_LENGTH` chars) and `keywords` (authored discovery
  synonyms, `<= SELECTION_KEYWORDS_MAX_COUNT` items of
  `<= SELECTION_KEYWORD_MAX_LENGTH` chars). Validated at import by
  `_validate_catalog_metadata()`; read via `get_tool_tier()`/`get_tool_tags()`/
  `get_tool_handler_name()`/`get_tool_selection_summary()`/`get_tool_keywords()`.
- `TOOL_SCHEMAS` — protocol-schema authority only:
  description/inputSchema/outputSchema/deprecated. No authored tier/tags copies.

Also contains `TOOL_PROFILES` (derived via `_build_profiles()`), `PROFILE_NAMES`,
`TOOL_ANNOTATIONS`/`get_tool_annotations()`, and `compact_schema()`/
`normal_schema()` transforms.

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

Protocol-shape registry of all available tools (83 total). Each entry owns
description/inputSchema/outputSchema (plus `deprecated` where applicable).
Tier/tags live in `TOOL_METADATA` — see tier tables below, which reflect the
catalog authority, not schema copies:

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
| `json_extract` | json | Extract value using RFC 6901 JSON Pointer (canonical; preferred) |
| `json_query` | json | Query JSON using RFC 6901 JSON Pointer (deprecated compatibility adapter; use `json_extract`) |
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
| `ip_inspect` | network | Inspect IP address (canonical text, family, special-use tags) |
| `cidr_inspect` | network | Inspect CIDR range (bounds, exact count, containment) |
| `codec_convert` | encoding | Convert between utf8/hex/base64/base64url codecs |
| `radix_convert` | encoding | Convert integers between bases 2–36 (u128-capped) |
| `datetime_convert` | temporal | Convert RFC3339 <-> Unix time with nanosecond precision |
| `cron_inspect` | temporal | Inspect five-field cron, list strictly-later runs |

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

Catalog authority used for profile building, exposure control, handler
binding, and selection metadata. Each entry includes:

- `handler` — Attribute name in `mcp/tools.py` (narrow locator, not an import path). Resolved by `server._build_tool_handlers()` into `TOOL_HANDLERS`.
- `category` — Tool category (math, text, path, validation, regex, identifier, json, list, shell, config, unicode, markdown, patch, toml, version, manifest, cargo, repo, network, encoding, temporal)
- `tier` — Tier level (0–3; sole authored authority, read via `get_tool_tier()`)
- `tags` — Selection/discovery keywords (sole authored authority, read via `get_tool_tags()`)
- `profiles` — List of named profiles that include this tool
- `aliases` — Alternative names (future use)
- `llm_exposure` — Exposure level: `"default"`, `"contextual"`, `"harness_only"`, `"expert_only"`, or `"hidden"`. Tools with `"hidden"` are excluded from the `full` profile.
- `harness_use` — How the tool is used by the harness (e.g., `"edit_preflight"`, `"command_preflight"`, `"config_preflight"`, `"prompt_input_preflight"`, `"path_preflight"`, `"repo_audit"`, `"reasoning_only"`, `"none"`)
- `cost` — Approximate cost: `"cheap"`, `"moderate"`, or `"heavy"`
- `stability` — Stability level: `"stable"`, `"experimental"`, or `"deprecated"`
- `composite` — Whether the tool is a composite (calls multiple sub-tools)

Annotations stay in `TOOL_ANNOTATIONS`/`get_tool_annotations()` (uniform
posture) and are not duplicated here. Tier/tag helpers: `_get_tool_tier()`
in `tools.py` reads `TOOL_METADATA`.

---

## tools.py — Tool Implementations

Wraps exact/ functions with error handling, sanitization, and response envelopes. 83 tool functions implemented.

Handlers import their exact/ function lazily inside the function body (never at module top level), pre-check inputs with `_require_str`/`_validate_str_list` against `MAX_TEXT_LENGTH`, then map exact `ValueError` to `invalid_arguments` envelopes and unexpected exceptions to `internal_error`. One naming exception: `codec_convert_mcp` accepts the JSON keys `from`/`to` via `**kwargs` (`from` is a Python keyword) and forwards them to the exact params `from_format`/`to_format`.

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

Spawn-permit, queue/child cleanup, and context-selection mechanics are shared with the evaluator via `eggcalc/_process.py` (single mechanism authority); `_SpawnPermit` is an alias of the shared `SpawnPermit`, and `_cleanup_child_process` delegates cleanup to it while keeping MCP orphan registration/caps. Spawn limits, acquire timeouts, and error envelopes remain MCP-owned policy.

---

## server.py — MCP Protocol Handler

stdio-based JSON-RPC 2.0 server implementation with bounded thread pool, rate limiting, and orphaned process cleanup.

### Dual-Era Model (authoritative)

This section is the single detailed description of the two-era model; other docs link here instead of repeating the lifecycle matrix.

MCP has two protocol eras, and one stdio server process speaks both:

| | Legacy era | Modern era |
|---|---|---|
| Revisions | `2024-11-05`, `2025-11-25` | `2026-07-28` (finalized) |
| Bootstrap | `initialize` → `notifications/initialized` → READY `McpSession` | Per-request `params._meta` envelope; optional `server/discover` |
| Client context | Negotiated once per session | `ModernRequestContext` per request (never persisted) |
| Served methods | All registered methods | `server/discover`, `tools/list`, `tools/call` only |
| Liveness | `ping` | Not defined (`ping` is `-32601` here) |
| Identity | `serverInfo` in the `initialize` result | `result._meta["io.modelcontextprotocol/serverInfo"]` on every result |
| Errors | `-32600`/`-32601`/`-32602`/`-32603`/`-32000` | Plus `-32022` unsupported-version (with `data.supported`/`data.requested`) |

Authority and dispatch rules:

- `eggcalc/_protocol.py` is the sole version/era authority (`LEGACY_PROTOCOL_VERSIONS`, `MODERN_PROTOCOL_VERSIONS`, `SUPPORTED_PROTOCOL_VERSIONS`, `protocol_era()` plus the reserved `_meta` key constants, conservative cache-hint constants, and the `MODERN_METHODS` allowlist). No other module defines version tuples.
- `_classify_request_era()` is the one classifier. A request is a modern candidate only when `params._meta` carries a reserved `io.modelcontextprotocol/` key — the method name alone (including `server/discover`) never selects the era. Unsupported revisions yield `-32022` and never fall into the legacy state machine; a modern envelope naming a supported legacy revision is served by the legacy path.
- `McpServer.handle_request()` classifies before any session logic. Modern requests go to `_handle_modern_request()` (server-owned dispatch over the captured `RuntimeContext`, no `McpSession` involved, no fake READY sessions constructed); everything else follows the legacy `McpSession` lifecycle. Modern notifications produce no response and mutate nothing.
- `server/discover` is generated from existing authorities: supported versions from the server config, protocol-only capabilities (`{"tools": {"listChanged": False}}` — runtime diagnostics from `detect_capabilities()` are intentionally excluded), identity via the `_meta` stamp (never a body field), `SERVER_INSTRUCTIONS`, and conservative `ttlMs: 0` / `cacheScope: "private"` (final policy, not a floor).
- Modern `tools/list` reuses the registry/profile/schema-detail machinery, emits canonical sorted-name order, and adds `resultType`/`ttlMs`/`cacheScope`/`_meta`. `tools/call` on both eras reuses the same `ToolExecutor` and profile authority (modern: no session cancellation sets) and adds the `structuredContent = text_envelope["result"]` compatibility bridge; only the modern path additionally carries `resultType` (see `ToolExecutor.call_tool()` and `ToolWireResult`; output validation via `_validate_output_payload()` rejects defective payloads with sanitized `-32000`).
- `_attach_modern_server_info()` is the single response-finalization helper; JSON-RPC errors carry no `_meta`.
- `SERVER_INSTRUCTIONS` is the one concise instruction authority, currently wired to `server/discover` (Plan 039 reuses it for legacy `initialize` where protocol-appropriate).

### Session Lifecycle (legacy era)

The MCP server uses `McpSession` and `McpSessionState` to manage the legacy handshake-era lifecycle (unchanged by modern support):

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

Supported versions are defined in `eggcalc/_protocol.py` (imported by `server.py`): `SUPPORTED_PROTOCOL_VERSIONS = ("2024-11-05", "2025-11-25", "2026-07-28")` with `LATEST_SUPPORTED_PROTOCOL_VERSION = "2026-07-28"`, split into `LEGACY_PROTOCOL_VERSIONS` and `MODERN_PROTOCOL_VERSIONS` with `protocol_era()` as the single version→era mapping. The legacy `initialize` handler negotiates legacy revisions only (unknown or modern revisions fall back to `LATEST_LEGACY_PROTOCOL_VERSION = "2025-11-25"`); modern revisions are negotiated per-request via the `_meta` envelope, with mismatches answered by `-32022`. See [Dual-Era Model](#dual-era-model-authoritative) above.

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
| `initialize` | `McpSession._handle_initialize()` | Initialize connection, return capabilities (legacy era only; negotiates legacy revisions) |
| `notifications/initialized` | None (returns None) | Client acknowledgment (legacy era only) |
| `server/discover` | `_handle_discover()` | Modern bootstrap: versions, capabilities, instructions, cache hints (modern era only) |
| `tools/list` | `_handle_list_tools()` | List available tools (with filtering); modern calls add `resultType`/cache hints/`_meta` |
| `tools/call` | `McpSession._handle_call_tool_server()` (legacy) / `_handle_call_tool_modern()` (modern) | Execute a tool; modern results add `resultType`/`structuredContent`/`_meta` |
| `profiles/list` | `_handle_list_profiles()` | List all profiles and their tools (legacy era only; `-32601` on the modern path) |
| `notifications/cancelled` | None (records cancellation) | Client-side request cancellation (legacy session state; modern notifications are dropped silently) |
| `ping` | Inline response | Health check, returns empty result (legacy era only; `-32601` on the modern path) |

`McpServer.handle_request()` classifies the era before session dispatch (see [Dual-Era Model](#dual-era-model-authoritative)): modern-enveloped requests never reach `McpSession`, and legacy requests never receive modern-only response fields.

### Tool Handler Map (derived, Plan 040)

`TOOL_HANDLERS` in server.py is derived from the catalog, not hand-maintained
(83 entries). Each `TOOL_METADATA[name]["handler"]` names an attribute in
`mcp/tools.py`; `server._build_tool_handlers()` resolves it eagerly with
`getattr` (plus a `_mcp_` fallback for single-file conflict renames) and
fails fast on missing/non-callable bindings:

```python
TOOL_HANDLERS: dict[str, Any] = _build_tool_handlers(TOOL_METADATA)
# e.g. "math_eval" -> math_eval, "argv_compare" -> shell_argv_compare,
#      "canonicalize_text" -> canonicalize_text_mcp
```

Do not add per-tool imports or mapping entries here — add `handler` + `tags`
to `TOOL_METADATA` and the protocol shape to `TOOL_SCHEMAS`. See
`authority_inventory.md` and `.skills/mcp_server.md` for the checklist.

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
| -32602 | InvalidParams | Invalid method parameters, malformed modern `_meta` envelope, profile violation, schema validation error |
| -32603 | InternalError | Internal error (unhandled exceptions) |
| -32000 | ToolError | Tool execution error (handler exception) |
| -32021 | MissingRequiredClientCapability | Reserved: processing needs an undeclared client capability (eggcalc tools currently require none) |
| -32022 | UnsupportedProtocolVersion | Modern request names an unserved revision (`data.supported` / `data.requested`) |

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

Modern-era results add `resultType: "complete"`, the server-identity `_meta` stamp, and — for `tools/list` / `server/discover` — `ttlMs` / `cacheScope` on top of these shapes. Successful `tools/call` results on **both** eras carry `structuredContent` equal to the text envelope's `result` member when the declared output schema is object-rooted (all 83 current tools); only the modern path adds `resultType`. Error, timeout, and output-too-large shapes stay `isError` with no structured payload on both eras. Legacy `initialize` results additionally carry the shared `SERVER_INSTRUCTIONS` text (identical to modern `server/discover`). See [Dual-Era Model](#dual-era-model-authoritative).

### Structured-Result Boundary (Plan 039)

`ToolWireResult` (frozen dataclass in `server.py`) is the one extraction helper mapping a handler return value to wire form: success `{ok: true, result: X, ...}` → text = full envelope + `structuredContent = X`; error `{ok: false, ...}` (or non-dict) → text = full envelope, no structured payload. Both representations come from the same in-memory object. `TOOL_SCHEMAS[name]["outputSchema"]` describes `structuredContent` (the inner `result`), never the outer compatibility envelope. Success payloads are validated via `_validate_output_payload()` (which reuses `_validate_value_against_schema()` with output-permissive `additionalProperties` defaulting) before emission; mismatches log locally and return sanitized `-32000`. `max_output_bytes` bounds the canonical envelope JSON; both representations serialize only after it passes, so the limit is not halved.

### Tool Annotations and Instructions

`ToolAnnotations` / `TOOL_ANNOTATIONS` / `get_tool_annotations()` in `schemas.py` own the standard MCP annotations (uniform `readOnlyHint: true`, `destructiveHint: false`, `idempotentHint: true`, `openWorldHint: false`; per-tool overrides merge over the default for Plan 040 migration). `tools/list` emits `annotations` in every schema-detail mode. Annotations are hints only — profile/evaluator policy never consults them. `SERVER_INSTRUCTIONS` is the one concise prose authority, emitted identically by legacy `initialize` and modern `server/discover`.

---

## Profile System

Profiles are named subsets of tools that control which tools are available via `tools/call` and returned by `tools/list`. The system is defined in `schemas.py` (profile metadata and tool assignments) and enforced in `server.py` (profile filtering and call-time rejection).

### Data Structures

**`TOOL_METADATA`** (schemas.py): Each tool has a `profiles` list indicating which named profiles include it, plus `llm_exposure` which controls visibility in the `full` profile. `agent_core` (10 front-door tools) is an opt-in experimental exposure; the 2026-09-10 held-out cross-model evaluation did not validate it as the recommended general-agent exposure. The Plan 043 corrective pass evaluated 15- and 22-tool name lists without creating profiles, but lacked retained per-case provider rollouts needed for promotion. `full` remains the default and practical general-agent recommendation.

**`TOOL_PROFILES`** (schemas.py): Built dynamically by `_build_profiles()` iterating `TOOL_METADATA` and grouping tools by their `profiles` lists.

**`PROFILE_NAMES`** (schemas.py): Canonical list of all 12 profile names:
`full`, `default`, `codegg_core_min`, `codegg_core`, `codegg_preflight`, `codegg_patch`, `codegg_config`, `codegg_unicode_security`, `codegg_shell`, `codegg_repo_audit`, `human_math`, `agent_core`.

### Profile Selection

The active profile is set at server startup via `EGGCALC_MCP_PROFILE` environment variable (default: `"full"`). Invalid profile names cause `SystemExit(1)` at import time.

```python
_active_profile: str = os.environ.get("EGGCALC_MCP_PROFILE", "full")
```

### `get_profile_tools()` (server.py:313–329)

Special-cases the `full` profile: instead of using `TOOL_PROFILES["full"]`, it dynamically returns all tools where `llm_exposure != "hidden"`. This allows hiding tools from the `full` profile without removing them from individual named profiles.

### Enforcement

- **`tools/list`**: Iterates `TOOL_SCHEMAS` in sorted-name order for protocol shape, filters by `get_profile_tools(profile_filter)`, then by catalog `tier`/`tags`/`names` from `TOOL_METADATA` (registry-aware when a `McpServer` is available). Wire entries carry standard `name`/`description`/`inputSchema`/`annotations` plus catalog `tier`/`tags`/`category`/`llm_exposure`/`cost` for backward compat (see `TestStandardToolShape`).
- **`tools/call`** (server.py:807–831): Rejects tools not in the active profile with JSON-RPC error `-32602` before the handler executes.
- **`profiles/list`**: Returns all profile names, their tool lists, and tool counts. When a `McpServer` is available, routes through `server.registry.*` instead of module-level globals.

### Schema Detail

`EGGCALC_MCP_SCHEMA_DETAIL` (default `"full"`) controls schema verbosity globally. Overridden per-request via `schema_detail` parameter in `tools/list`. All modes preserve standard `annotations` (small and useful); eggcalc-specific keys (`tier`, `tags`, `category`, `llm_exposure`, `cost`) ride alongside the standard shape and pass the official SDK wire schemas (see `scripts/mcp_interop_probe.mjs`):

- **`full`**: Raw schemas with all fields
- **`normal`**: Truncated descriptions (240 chars), compact output schema (`normal_schema()`). Input properties truncated to 120 chars. Includes tier, tags, category, llm_exposure, cost.
- **`compact`**: Types and required fields only (`compact_schema()`). Descriptions are the authored `selection_summary` (Plan 041 selection signal, not truncation); input properties truncated to 80 chars. Includes category, llm_exposure, cost.

### Progressive Disclosure (Plans 041 and 043)

`ToolRegistry.search_tools(query, *, profile="full", limit=5) -> list[ToolMatch]`
is the harness-side discovery primitive: a deterministic stdlib-only
lexical ranker (NFKC + casefold normalization, alphanumeric tokenization,
integer weights, canonical-name tie-break) over the fixed catalog. Evidence
tiers: exact tool-name match (300), exact alias match (250), name
token/prefix match, keyword phrase/token match, category match,
selection-summary token overlap, description/tags fallback. Queries truncate
to `MAX_SEARCH_QUERY_LENGTH` (4096) chars; `limit` is bounded to 1–20;
zero-score tools are omitted.

`ToolMatch` carries `name`/`score`/`category`/`selection_summary`/
`matched_on` — never full schemas. Search defaults to the `full` callable
catalog and accepts a `profile` restriction; results never widen call
authorization (enforced separately by profile filtering in `tools/list` and
`tools/call`). Wire compact entries are `thaw_owned()` before emission so
frozen registry values never reach JSON serialization.

Intended aware-harness flow: start from `agent_core` definitions → search
with task text → load full definitions for shortlisted names via the
registry or `tools/list(names=[...])` → call under normal validation.
Deterministic cost evidence lives in
`evals/mcp_tool_selection/reports/baseline_2026_09_10.md`
(`agent_core/compact` ≈ 11.7 KB vs `full/full` ≈ 118.4 KB, −90.1%);
provider-neutral rollout scoring via
`scripts/score_mcp_tool_selection.py`. This is a harness/library facility,
not a claim that MCP standardizes profile-aware tool search or tool-definition
expansion. Modern MCP `server/discover` is the protocol bootstrap; the current
empirical result is recorded in
`evals/mcp_tool_selection/reports/closure_2026_09_10.md`: the 90.1% footprint
reduction passes, but selection non-inferiority and specialist recovery do
not. Plan 043 adds deterministic rank/depth decomposition and evaluation-only
15-/22-tool candidate lists; its reports show improved static reachability but
do not claim model-selection or end-to-end improvement because normalized
per-case closure rollouts were not retained. Keep the profile opt-in until a
later held-out run supports promotion.

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
10. **Config Security** — Config suppression handled by `McpServerConfig.from_environment()` and `main()` setup (no import-time env mutation)

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
| Functions | 83 tools | All |
| Error format | Envelope | Exceptions |
| Config loading | Blocked | Opt-in via `EGGCALC_LOAD_CONFIG` |

## Entry Point

### `main() -> int`

Main entry point:
1. Creates `McpServerConfig.from_environment()` for policy
2. Instantiates `McpServer(config=config)` per connection
3. Creates a session via `server.create_session()`
4. Reads JSON-RPC requests from stdin (line by line)
5. Validates JSON-RPC version, ID, method
6. Enforces rate limiting (sliding window)
7. Rejects oversized requests and batch requests
8. Handles each request via `server.handle_request(request, session=session)`
9. Writes responses to stdout
10. Returns exit code on EOF or `BrokenPipeError`
11. Guaranteed `server.close()` in try/finally block

For build compatibility, this is also available as `mcp_main()`:

```python
from eggcalc.mcp.server import main, mcp_main  # Both refer to same function
```
