# MCP Server

eggcalc includes an MCP (Model Context Protocol) server that exposes text analysis and math evaluation tools to AI agents. This page explains MCP protocol usage, server configuration, profiles, schema-detail controls, and selected examples. The complete generated tool inventory lives in [tool_inventory.md](tool_inventory.md).

## What is MCP?

The Model Context Protocol is a JSON-RPC 2.0 based protocol for exposing tools to AI agents. The calc MCP server provides:

- **Deterministic tools** for AI agent workflows (see [tool_inventory.md](tool_inventory.md) for count)
- **Deterministic results** - same input always produces same output
- **No external dependencies** - pure Python standard library
- **stdio-based communication** - operates over stdin/stdout

## Running the Server

Start the MCP server with the `--mcp` flag:

```bash
calc --mcp
```

The server reads JSON-RPC requests from stdin and writes responses to stdout. It runs until EOF is received.

## Configuration

The MCP server exposes several rate-limiting and resource-guard constants that can be overridden via environment variables. All values are validated and clamped to safe ranges; invalid or out-of-range values silently fall back to the default.

| Environment Variable | Default | Min | Max | Description |
|----------------------|---------|-----|-----|-------------|
| `EGGCALC_MCP_MAX_REQUEST_BYTES` | 1,000,000 | 1,000 | 100,000,000 | Maximum size of a single JSON-RPC request in bytes |
| `EGGCALC_MCP_MAX_OUTPUT_BYTES` | 1,000,000 | 1,000 | 100,000,000 | Maximum size of a single tool response in bytes |
| `EGGCALC_MCP_MAX_REQUESTS_PER_SECOND` | 10 | 0.1 | 1,000 | Rate limit for incoming requests (float) |
| `EGGCALC_MCP_MAX_TOOL_TIMEOUT_SECONDS` | 30 | 1 | 300 | Maximum time in seconds a tool call may run |
| `EGGCALC_MCP_MAX_CANCELLED_REQUESTS` | 10,000 | 100 | 1,000,000 | Size of the cancellation-record ring buffer |
| `EGGCALC_MCP_MAX_TOOL_WORKERS` | 16 | 1 | 128 | Maximum threads in the tool-execution thread pool |

**Example:**

```bash
# Allow larger requests and more concurrent workers
EGGCALC_MCP_MAX_REQUEST_BYTES=5000000 \
EGGCALC_MCP_MAX_TOOL_WORKERS=32 \
calc --mcp
```

## Protocol Basics

The server uses JSON-RPC 2.0 over stdio:

```bash
# List available tools
{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}

# Call a tool
{"jsonrpc": "2.0", "id": 2, "method": "tools/call",
 "params": {"name": "math_eval", "arguments": {"expression": "5 + 3"}}}
```

### Supported Protocol Versions

The server supports MCP protocol version `2024-11-05`. Version negotiation happens during the `initialize` handshake:

- If the client requests a supported version, the server responds with that version.
- If the client omits `protocolVersion` or requests an unsupported version, the server responds with the latest supported version (`2024-11-05`).

Supported versions are defined in `SUPPORTED_PROTOCOL_VERSIONS` in `eggcalc/mcp/server.py`.

### Session Lifecycle

Clients **must** complete the full initialization handshake before calling tools:

1. Send an `initialize` request with `protocolVersion`, `capabilities`, and `clientInfo`.
2. Receive the `initialize` response with `protocolVersion`, `capabilities`, and `serverInfo`.
3. Send `notifications/initialized` to acknowledge the handshake.
4. After step 3, the session is in **READY** state and tools can be called.

```
UNINITIALIZED --initialize request--> INITIALIZING
INITIALIZING  --notifications/initialized--> READY
READY         --EOF/shutdown/close--> CLOSED
```

Tool requests (`tools/list`, `tools/call`) before the session reaches READY state return JSON-RPC error `-32600` ("Server not initialized"). Duplicate `initialize` requests return `-32600` ("Server already initialized").

### Notification Handling

The server handles these notifications silently (no response is returned):

- `notifications/initialized` — Transitions the session from INITIALIZING to READY.
- `notifications/cancelled` — Records a cancellation request for pre-dispatch rejection.

Unknown notifications are silently ignored per the JSON-RPC 2.0 spec. The server never returns a response to a notification.

### Error Codes

| Code | Name | When Returned |
|------|------|---------------|
| `-32700` | Parse error | Invalid JSON in request |
| `-32600` | Invalid request | Non-object request, missing `jsonrpc`/`method`, invalid ID type, batch requests, server already initialized, server not initialized |
| `-32601` | Method not found | Unknown top-level method (e.g., `foo/bar`) |
| `-32602` | Invalid params | Invalid method parameters, profile violation, schema validation error |
| `-32603` | Internal error | Unhandled server exception |
| `-32000` | Tool error | Tool execution failure (handler exception, timeout) |

### Migration Notes

**Callers using `handle_request()` without a session:** The `handle_request(request, session=None)` function still works without an explicit `McpSession`. When `session` is `None`, a module-level default session (starting in READY state) is used for backward compatibility. This preserves behavior for callers that did not perform the handshake.

**Callers that need full lifecycle enforcement:** Pass an explicit `McpSession(initial_state=McpSessionState.UNINITIALIZED)` to `handle_request()`. This enables initialize-first enforcement and lifecycle state tracking.

**`main()` entry point:** Now creates one `McpSession(initial_state=UNINITIALIZED)` per connection, enabling full lifecycle management for stdio-based server usage.

## Selected Tool Examples

### math_eval

Evaluate mathematical expressions with full natural language and unit support.

**Arguments:**
- `expression` (string): The math expression to evaluate

**Tier:** 0
**Tags:** `math`, `evaluation`, `units`

**Example:**
```json
{"name": "math_eval", "arguments": {"expression": "five plus three"}}
// Returns: {"ok": true, "result": {"result": "8", "type": "int"}}
```

**Supported expressions:**
- Arithmetic: `5 + 3`, `2 ** 10`, `100 % 7`
- Natural language: `five plus three`, `twenty times five`
- Units: `30m + 100ft`, `5km in miles`
- Constants: `pi`, `avogadro`, `speed of light`
- Functions: `sqrt(144)`, `sin(pi/2)`, `factorial(5)`

---

### text_measure

Return comprehensive text metrics.

**Arguments:**
- `text` (string): The text to measure

**Tier:** 0
**Tags:** `text`, `metrics`, `unicode`

**Returns:**
- `bytes_utf8`: Raw UTF-8 byte count
- `codepoints`: Number of Unicode codepoints
- `chars_no_whitespace`: Characters excluding whitespace
- `ascii`: Count of ASCII characters
- `non_ascii`: Count of non-ASCII characters
- `words`: Word count
- `lines`: Line count (including empty)
- `nonempty_lines`: Lines with content
- `blank_lines`: Empty lines
- `newline_style`: LF, CRLF, CR, mixed, or none
- `ends_with_newline`: Boolean
- `letters`, `digits`, `punctuation`, `symbols`, `spaces`, `control_chars`
- `is_nfc`, `is_nfd`, `is_nfkc`, `is_nfkd`: Normalization state

**Example:**
```json
{"name": "text_measure", "arguments": {"text": "Hello, 世界!\n"}}
// Returns: {"ok": true, "result": {"bytes_utf8": 17, "codepoints": 13, "words": 2, ...}}
```

---

### text_equal

Compare two strings under various normalization modes with detailed evidence.

**Arguments:**
- `a` (string): First string
- `b` (string): Second string
- `normalization` (string, optional): "raw", "NFC", "NFD", "NFKC", "NFKD"
- `casefold` (boolean, optional): Case-insensitive comparison
- `trim` (boolean, optional): Trim whitespace

**Tier:** 0
**Tags:** `text`, `comparison`, `unicode`, `normalization`

**Returns:**
- `equal`: Boolean result
- `mode`: Comparison mode used
- `raw_equal`: Byte-for-byte equality
- `nfc_equal`, `nfd_equal`, `nfkc_equal`, `nfkd_equal`: Per-normalization equality
- `casefold_equal`: After casefolding
- `byte_equal`: After trimming
- `lengths`: Codepoint lengths of both strings
- `first_difference`: Details of first differing character (if any)
- `classification`: "identical", "normalized_equivalent", "casefold_equivalent", "trimmed_equivalent", "confusable_characters", "completely_different"

**Example:**
```json
{"name": "text_equal", "arguments": {"a": "café", "b": "cafe\u0301", "normalization": "NFC"}}
// Returns: {"ok": true, "result": {"equal": true, "mode": "NFC", ...}}
```

---

### text_diff_explain

Explain differences between two strings with detailed codepoint information.

**Arguments:**
- `a` (string): First string
- `b` (string): Second string
- `max_diffs` (integer, optional): Maximum diff spans to return (default 20)
- `include_codepoints` (boolean, optional): Include codepoint details (default true)
- `include_context` (boolean, optional): Include context notes (default true)

**Tier:** 1
**Tags:** `text`, `diff`, `unicode`, `comparison`

**Returns:**
- `equal`: Boolean
- `classification`: Why they differ (confusable_characters, insertion, deletion, etc.)
- `summary`: Human-readable summary
- `spans`: Array of DiffSpan with:
  - `kind`: "equal", "insert", "delete", "replace"
  - `a_text`, `b_text`: The text spans
  - `a_codepoints`, `b_codepoints`: Codepoint details
  - `note`: Explanation (e.g., "CYRILLIC SMALL LETTER A looks like LATIN SMALL LETTER A")
- `security_findings`: Array of security warnings
- `agent_instruction`: Instructions for AI agent handling

**Example:**
```json
{"name": "text_diff_explain", "arguments": {"a": "pаypal", "b": "paypal"}}
// Returns diff with security finding about Cyrillic confusable
```

---

### text_inspect

Complete text inspection for hidden characters, confusables, and Unicode risks.

**Arguments:**
- `text` (string): The text to inspect
- `include_codepoints` (boolean, optional): Include codepoint details (default true)
- `include_confusables` (boolean, optional): Check for confusables (default true)

**Tier:** 1
**Tags:** `text`, `unicode`, `security`, `inspection`

**Returns:**
- `safe_repr`: Display-safe representation (invisibles shown as markers)
- `metrics`: Full text metrics (same as text_measure)
- `normalization`: Normalization state
- `invisibles`: Array of InvisibleCharInfo with index, char, codepoint, name, category, display
- `scripts`: Script analysis for each character
- `confusables`: Array of ConfusableInfo with confusable character details
- `warnings`: Human-readable warnings

**Example:**
```json
{"name": "text_inspect", "arguments": {"text": "user\u200Bname"}}
// Returns inspection showing zero-width space at index 4
```

**Security warnings include:**
- "Text contains invisible character ZERO WIDTH SPACE at index N"
- "Character at index N is confusable (SCRIPT vs SCRIPT)"
- "Text contains bidirectional control characters"

---

### text_count

Count character occurrences or return frequency table.

**Arguments:**
- `text` (string): The text to analyze
- `target` (string, optional): Specific character to count (if omitted, returns frequency table)
- `normalization` (string, optional): Normalization to apply before counting

**Tier:** 0
**Tags:** `text`, `count`, `frequency`

**Returns:**
- `target`: Character being counted (or null for frequency table)
- `normalization`: Normalization mode used
- `count`: Number of occurrences (when target specified)
- `positions`: Array of codepoint indices where target appears
- `text_length_codepoints`: Total codepoint count
- Frequency table when no target specified: `{"h": 1, "e": 1, "l": 2, ...}`

**Example:**
```json
{"name": "text_count", "arguments": {"text": "hello world", "target": "l"}}
// Returns: {"ok": true, "result": {"count": 3, "positions": [2, 3, 9], ...}}
```

---

### text_truncate

Truncate a string to a specified number of grapheme clusters (user-perceived characters).

**Arguments:**
- `text` (string): Input string to truncate
- `max_graphemes` (integer): Maximum number of grapheme clusters to return

**Tier:** 3
**Tags:** `text`, `truncation`, `unicode`

**Returns:**
- `text`: Result string (truncated if truncation occurred)
- `original_graphemes`: Original grapheme count
- `truncated_graphemes`: Grapheme count in result
- `truncated`: Boolean indicating if text was truncated

**Example:**
```json
{"name": "text_truncate", "arguments": {"text": "Hello, world!", "max_graphemes": 5}}
// Returns: {"ok": true, "result": {"text": "Hello", "original_graphemes": 13, "truncated_graphemes": 5, "truncated": true}}
```

---

### text_window

Get a window around a position in text with context lines. Shows the line at the given position with surrounding context, position metrics, and character details.

**Arguments:**
- `text` (string): Input string to analyze
- `position` (object): Position specification with kind and value
  - `kind` (string): "byte_offset", "codepoint_index", "grapheme_index", or "line_column"
  - `value` (integer): Value for byte_offset, codepoint_index, or grapheme_index
  - `line` (integer): Line number for line_column kind
  - `column` (integer): Column number for line_column kind
- `context_lines` (integer, optional): Number of context lines before and after (default: 2)
- `include_visible_repr` (boolean, optional): Include visible representation of the line (default: true)

**Tier:** 1
**Tags:** `text`, `position`, `context`, `unicode`, `window`

**Returns:**
- `position`: Object with byte_offset, codepoint_index, grapheme_index, line, column
- `line_text`: Text of the line at the position
- `line_visible_repr`: Visible representation (with invisible chars marked)
- `before`: Array of {line, text} before the position
- `after`: Array of {line, text} after the position
- `newline_style`: LF, CRLF, CR, mixed, or none
- `at_codepoint`: Object with char, codepoint, name, category
- `warnings`: Any warnings (e.g., position in middle of multibyte)

**Example:**
```json
{"name": "text_window", "arguments": {"text": "line1\nline2\nline3", "position": {"kind": "line_column", "line": 2, "column": 3}, "context_lines": 1}}
// Returns: {"ok": true, "result": {"position": {"byte_offset": 8, "codepoint_index": 8, "grapheme_index": 7, "line": 2, "column": 3}, "line_text": "line2", ...}}
```

---

### validate_brackets

Check bracket balance and return details on unmatched brackets.

**Arguments:**
- `text` (string): Text containing brackets to validate
- `pairs` (object, optional): Bracket pair mapping (default: `() [] {} <>`)

**Tier:** 1
**Tags:** `validation`, `brackets`, `structure`

**Returns:**
- `balanced`: Boolean
- `unmatched_openers`: Array of BracketError (char, index, line, column)
- `unmatched_closers`: Array of BracketError

**Example:**
```json
{"name": "validate_brackets", "arguments": {"text": "(a + b) * [c - d]"}}
// Returns: {"ok": true, "result": {"balanced": true, "unmatched_openers": [], "unmatched_closers": []}}

{"name": "validate_brackets", "arguments": {"text": "(a + b]"}}
// Returns: {"ok": true, "result": {"balanced": false, "unmatched_openers": [...], "unmatched_closers": [...]}}
```

---

### validate_json

Validate JSON and report detailed parse errors.

**Arguments:**
- `text` (string): JSON string to validate

**Tier:** 0
**Tags:** `validation`, `json`, `structured-data`

**Returns:**
- `valid`: Boolean
- `error`: Error message (if invalid)
- `line`, `column`, `position`: Error location (if invalid)
- `type`: Error type (e.g., "syntax", "structure")
- `top_level_keys`: Array of top-level object/array keys (if valid)

**Example:**
```json
{"name": "validate_json", "arguments": {"text": "{\"name\": \"test\"}"}}
// Returns: {"ok": true, "result": {"valid": true, "top_level_keys": ["name"]}}

{"name": "validate_json", "arguments": {"text": "{\"name\":}"}}
// Returns: {"ok": true, "result": {"valid": false, "error": "Expecting property name...", "line": 1, "column": 9}}
```

---

### validate_regex

Test regex patterns against sample strings.

**Arguments:**
- `pattern` (string): Regex pattern
- `samples` (array of strings): Strings to test against
- `flags` (array of strings, optional): Flag names (IGNORECASE, MULTILINE, etc.)

**Tier:** 1
**Tags:** `validation`, `regex`, `pattern`

**Returns:**
- `valid_pattern`: Boolean
- `results`: Array of RegexMatch for each sample:
  - `sample`: The input string
  - `matches`: Boolean (any match)
  - `fullmatch`: Boolean (entire string matches)
  - `span`: Tuple of (start, end) positions
  - `groups`: Array of capture groups
  - `groupdict`: Dict of named capture groups

**Example:**
```json
{"name": "validate_regex", "arguments": {"pattern": "(\\d+)-(\\d+)", "samples": ["123-4567", "hello"]}}
// Returns: {"ok": true, "result": {
  "valid_pattern": true,
  "results": [
    {"sample": "123-4567", "matches": true, "groups": ["123", "4567"], ...},
    {"sample": "hello", "matches": false, ...}
  ]
}}
```

---

### list_compare

Compare two lists with various comparison options.

**Arguments:**
- `a` (array): First list
- `b` (array): Second list
- `ignore_order` (boolean, optional): Compare as sets (default true)
- `casefold` (boolean, optional): Case-insensitive string comparison (default false)
- `normalization` (string, optional): Unicode normalization for strings (default "NFC")

**Tier:** 2
**Tags:** `comparison`, `lists`, `sets`

**Returns:**
- `equal`: Boolean indicating if lists are equal under given mode
- `missing_in_b`: Items in `a` not found in `b`
- `missing_in_a`: Items in `b` not found in `a`
- `duplicates_in_a`: Items appearing more than once in `a`
- `duplicates_in_b`: Items appearing more than once in `b`
- `near_matches`: Items that differ slightly (Levenshtein distance < 3)

**Example:**
```json
{"name": "list_compare", "arguments": {"a": ["apple", "banana"], "b": ["APPLE", "cherry"], "ignore_order": true}}
// Returns: {"ok": true, "result": {
  "equal": false,
  "missing_in_b": ["banana"],
  "missing_in_a": ["cherry"],
  "duplicates_in_a": [],
  "duplicates_in_b": [],
  ...
}}
```

---

### validate_toml

Validate TOML configuration files (Cargo.toml, pyproject.toml, etc.) and report parse errors with line/column positions.

**Arguments:**
- `text` (string): TOML document string to validate
- `detail` (string, optional): "summary" | "normal" | "full" (default "normal")

**Tier:** 1
**Tags:** `validation`, `structured-data`, `toml`, `config`, `rust`, `python`

**Returns:**
- `valid`: Boolean
- `error`: Error message (if invalid)
- `line`, `column`: Error location (if invalid)
- `position`: Character position (if available)
- `type`: Error type (e.g., "syntax")
- `top_level_keys`: Array of top-level keys (if valid)
- `tables`: Array of table names (if valid)
- `summary`: Human-readable summary

**Example:**
```json
{"name": "validate_toml", "arguments": {"text": "[package]\nname = \"demo\"\nversion = \"0.1.0\""}}
// Returns: {"ok": true, "result": {"valid": true, "top_level_keys": ["package"], "tables": ["package"], "summary": "Valid TOML with 1 top-level key and 1 table"}}

{"name": "validate_toml", "arguments": {"text": "[package]\nname = \"demo\"\nversion"}}
// Returns: {"ok": true, "result": {"valid": false, "error": "Expected '=' after a key in a key/value pair", "line": 3, "column": 8}}
```

**Limits:** Input limited to 100,000 characters. Parse failures return `valid: false` in result, not server errors.

---

### json_extract

Extract a value from JSON using RFC 6901 JSON Pointer (e.g., `/foo/bar/0`). Navigate nested objects and arrays.

**Arguments:**
- `text` (string): JSON document string
- `pointer` (string, optional): RFC 6901 JSON Pointer path (default empty = whole document)
- `detail` (string, optional): "summary" | "normal" | "full" (default "normal")
- `max_output_chars` (integer, optional): Maximum output characters (default 4000)

**Tier:** 2
**Tags:** `json`, `structured-data`, `extraction`, `config`, `pointer`

**Returns:**
- `valid_json`: Boolean
- `found`: Boolean
- `pointer`: The pointer that was used
- `value_type`: Type of extracted value (string, number, object, array, boolean, null)
- `value`: The extracted value (truncated if necessary)
- `preview`: String preview of the value
- `child_keys`: Array of keys (for objects)
- `array_length`: Length (for arrays)
- `truncated`: Boolean
- `summary`: Human-readable summary

**Example:**
```json
{"name": "json_extract", "arguments": {"text": "{\"dependencies\": {\"tokio\": {\"version\": \"1.36\"}}}", "pointer": "/dependencies/tokio"}}
// Returns: {"ok": true, "result": {"valid_json": true, "found": true, "value_type": "object", "child_keys": ["version"], ...}}
```

**Pointer Syntax:**
- `/foo/bar` - Navigate to `foo` then `bar`
- `/arr/0` - Navigate to index 0 of array
- `/~1/f~0` - Escape `~1` → `/`, `~0` → `~` (RFC 6901)

**Limits:** Output truncated at `max_output_chars`. Parse failures return `valid_json: false`, not server errors.

---

### json_canonicalize

Canonicalize JSON with deterministic formatting, key ordering, duplicate key detection, and stable hashes.

**Arguments:**
- `text` (string): Input JSON string to canonicalize
- `sort_keys` (boolean, optional): Sort object keys alphabetically (default true)
- `indent` (integer, optional): Indentation spaces (None for minified)
- `ensure_ascii` (boolean, optional): Use ASCII escaping for non-ASCII characters (default false)
- `detect_duplicate_keys` (boolean, optional): Report duplicate keys in the input (default true)
- `trailing_newline` (boolean, optional): Add a trailing newline to the canonical form (default false)

**Tier:** 1
**Tags:** `json`, `canonical`, `hash`, `deterministic`, `format`

**Returns:**
- `valid`: Boolean
- `canonical`: Canonical JSON string
- `minified`: Minified JSON string (compact, no whitespace)
- `sha256`: SHA-256 hash of the canonical form
- `duplicate_keys`: Array of keys that appear more than once (top-level only)
- `top_level_type`: "object", "array", or primitive type name
- `top_level_keys`: Array of top-level object keys (if object)
- `error`: Error message if invalid
- `line`, `column`: Error location if invalid

**Example:**
```json
{"name": "json_canonicalize", "arguments": {"text": "{\"b\": 2, \"a\": 1}", "sort_keys": true}}
// Returns: {"ok": true, "result": {"valid": true, "canonical": "{\"a\": 1, \"b\": 2}\n", "minified": "{\"a\":1,\"b\":2}", "sha256": "...", "duplicate_keys": [], "top_level_type": "object", "top_level_keys": ["b", "a"]}}
```

---

### json_query

Extract a value from JSON using RFC 6901 JSON Pointer. Navigate nested objects and arrays.

**Arguments:**
- `text` (string): JSON document string
- `pointer` (string, optional): RFC 6901 JSON Pointer path (e.g., "/foo/bar/0"). Empty string means the whole document.

**Tier:** 1
**Tags:** `json`, `pointer`, `extraction`, `query`, `rfc6901`

**Returns:**
- `found`: Boolean
- `pointer`: The pointer that was used
- `value`: The value at the pointer (if found)
- `type`: Type of the value: "object", "array", "string", "number", "boolean", "null"
- `missing_at`: The path where lookup failed (if not found)
- `reason`: "key_not_found", "index_out_of_range", "invalid_pointer_syntax", "invalid_json"
- `error`: Error message if invalid JSON

**Example:**
```json
{"name": "json_query", "arguments": {"text": "{\"foo\": \"bar\"}", "pointer": "/foo"}}
// Returns: {"ok": true, "result": {"found": true, "pointer": "/foo", "value": "bar", "type": "string", ...}}
```

---

### json_compare

Compare two JSON documents semantically, ignoring formatting and key order.

**Arguments:**
- `a` (string): First JSON document
- `b` (string): Second JSON document
- `ignore_object_order` (boolean, optional): Sort object keys for comparison (default true)
- `ignore_array_order` (boolean, optional): Sort arrays if all items are serializable (default false)
- `numeric_string_equivalence` (boolean, optional): Treat numeric strings as numbers (default false)
- `casefold_keys` (boolean, optional): Casefold object keys before comparison (default false)
- `treat_missing_null_as_equal` (boolean, optional): Treat missing and null as equal (default false)
- `max_diffs` (integer, optional): Maximum number of differences to report (default 50)
- `detail` (string, optional): "summary" | "normal" | "full" (default "normal")

**Tier:** 1
**Tags:** `json`, `structured-data`, `comparison`, `config`

**Returns:**
- `valid_json_a`: Boolean
- `valid_json_b`: Boolean
- `equal`: Boolean
- `same_type`: Boolean (both valid JSON)
- `diff_count`: Number of differences found
- `diffs`: Array of diff objects:
  - `path`: JSON Pointer path to difference
  - `kind`: "type_changed", "value_changed", "key_missing_in_a", "key_missing_in_b", "array_length_changed", "array_item_changed"
  - `a_type`, `b_type`: Types of values at path
  - `a_preview`, `b_preview`: String previews of values
- `truncated`: Boolean
- `summary`: Human-readable summary

**Example:**
```json
{"name": "json_compare", "arguments": {"a": "{\"x\": 1, \"y\": 2}", "b": "{\"y\": 2, \"x\": 1}"}}
// Returns: {"ok": true, "result": {"valid_json_a": true, "valid_json_b": true, "equal": true, "diff_count": 0, ...}}
```

**Limits:** Diff output limited to `max_diffs` entries. Parse failures return `valid_json_a: false` or `valid_json_b: false`, not server errors.

---

### text_position

Convert between byte offsets, codepoint indices, line/column positions, and UTF-16 offsets. Useful for LSP/editor integrations.

**Arguments:**
- `text` (string): Input string
- `byte_offset` (integer, optional): UTF-8 byte offset (0-based)
- `codepoint_index` (integer, optional): Python string index (Unicode scalar index)
- `line` (integer, optional): 1-based line number (with line_base)
- `column` (integer, optional): 1-based column number (with column_base)
- `utf16_offset` (integer, optional): UTF-16 code unit offset for LSP-style positions
- `line_base` (integer, optional): Base for line numbers (1 for 1-based, 0 for 0-based, default 1)
- `column_base` (integer, optional): Base for column numbers (1 for 1-based, 0 for 0-based, default 1)
- `detail` (string, optional): "summary" | "normal" | "full" (default "normal")

**Tier:** 2
**Tags:** `text`, `position`, `offset`, `unicode`, `lsp`

**Returns:**
- `valid`: Boolean
- `byte_offset`: UTF-8 byte offset
- `codepoint_index`: Unicode scalar index
- `utf16_offset`: UTF-16 code unit offset
- `line`: Line number (1-based)
- `column`: Column number (1-based)
- `line_base`, `column_base`: Bases used
- `char`: Character at position
- `codepoint`: Unicode codepoint (e.g., "U+0078")
- `name`: Unicode name of character
- `line_text_preview`: Content of the line
- `summary`: Human-readable summary
- `error`: Error message (if invalid)
- `warnings`: Array of warnings (e.g., for CRLF handling)

**Example:**
```json
{"name": "text_position", "arguments": {"text": "let x = 1;\nconst y = 2;", "byte_offset": 12}}
// Returns: {"ok": true, "result": {"valid": true, "byte_offset": 12, "codepoint_index": 10, "line": 2, "column": 4, ...}}
```

**Limits:** Exactly one locator mode must be provided. Input limited to 100,000 characters.

---

### text_transform

Apply deterministic text transformations: Unicode normalization, casefold, trim, newline normalization, zero-width removal, bidi control stripping, and visible representation.

**Arguments:**
- `text` (string): Input string to transform
- `operations` (array of strings): Operations to apply
- `detail` (string, optional): "summary" | "normal" | "full" (default "normal")

**Tier:** 2
**Tags:** `text`, `unicode`, `transform`, `normalization`, `sanitation`

**Available Operations:**
- `normalize_nfc` / `normalize_nfd` / `normalize_nfkc` / `normalize_nfkd`: Unicode normalization
- `casefold`: Case-insensitive comparison preparation
- `trim`: Remove leading/trailing whitespace
- `trim_trailing_whitespace`: Remove trailing whitespace only
- `normalize_newlines_lf`: Convert all newlines to LF
- `ensure_final_newline`: Ensure text ends with newline
- `strip_final_newline`: Remove final newline
- `remove_zero_width`: Remove zero-width characters (U+200B, U+FEFF, etc.)
- `remove_bidi_controls`: Remove bidirectional control characters
- `visible_repr`: Show invisibles as escape sequences

**Returns:**
- `changed`: Boolean indicating if text was modified
- `text`: Transformed text
- `operations_applied`: Array of operations that were applied
- `removed`: Array of removed character info (if any invisibles removed)
- `warnings`: Array of warnings
- `summary`: Human-readable summary

**Example:**
```json
{"name": "text_transform", "arguments": {"text": "hello  ", "operations": ["trim_trailing_whitespace"]}}
// Returns: {"ok": true, "result": {"changed": true, "text": "hello", "operations_applied": ["trim_trailing_whitespace"], ...}}
```

**Limits:** Input limited to 100,000 characters.

---

### escape_text

Escape text for various output formats. Safely quote text for shell, JSON, regex, and other contexts.

**Arguments:**
- `text` (string): Input string to escape
- `mode` (string): Escape mode
- `detail` (string, optional): "summary" | "normal" | "full" (default "normal")

**Tier:** 1
**Tags:** `text`, `escape`, `encoding`, `shell`, `json`, `regex`

**Available Modes:**
- `json_string`: JSON string literal (escapes quotes, backslashes, newlines)
- `python_string`: Python string literal
- `rust_string`: Rust string literal
- `posix_shell_single`: POSIX shell single-quoted string
- `regex_literal`: Regular expression literal
- `markdown_inline_code`: Markdown inline code
- `markdown_code_block`: Markdown code block
- `html_text`: HTML text content
- `url_component`: URL component (percent-encoding)

**Returns:**
- `mode`: The escape mode used
- `escaped`: The escaped text
- `changed`: Boolean indicating if text was modified
- `summary`: Human-readable summary

**Example:**
```json
{"name": "escape_text", "arguments": {"text": "hello\nworld", "mode": "json_string"}}
// Returns: {"ok": true, "result": {"mode": "json_string", "escaped": "\"hello\\nworld\"", "changed": true, "summary": "Escaped text as JSON string literal"}}
```

**Limits:** Input limited to 100,000 characters.

---

### unescape_text

Unescape text from various formats.

**Arguments:**
- `text` (string): Input string to unescape
- `mode` (string): Unescape mode
- `detail` (string, optional): "summary" | "normal" | "full" (default "normal")

**Tier:** 1
**Tags:** `text`, `escape`, `encoding`, `shell`, `json`, `regex`

**Available Modes:**
- `json_string`: JSON string literal
- `python_string`: Python string literal (via ast.literal_eval)
- `unicode_escape`: Unicode escape sequences (\uXXXX, \UXXXXXXXX)
- `url_component`: URL component (decode percent-encoding)

**Returns:**
- `mode`: The unescape mode used
- `unescaped`: The unescaped text
- `changed`: Boolean indicating if text was modified
- `error`: Error message (if unescape failed)
- `summary`: Human-readable summary

**Example:**
```json
{"name": "unescape_text", "arguments": {"text": "\"hello\\nworld\"", "mode": "json_string"}}
// Returns: {"ok": true, "result": {"mode": "json_string", "unescaped": "hello\nworld", "changed": true, ...}}
```

**Limits:** Input limited to 100,000 characters.

---

### text_hash

Compute cryptographic hashes of text for identity checking. Verify large generated text without loading it again.

**Arguments:**
- `text` (string): Input string to hash
- `algorithms` (array of strings, optional): Hash algorithms (sha256, sha1, md5, crc32) (default ["sha256"])
- `encoding` (string, optional): Text encoding for byte conversion (default "utf-8")
- `detail` (string, optional): "summary" | "normal" | "full" (default "normal")

**Tier:** 2
**Tags:** `text`, `hash`, `identity`, `security`

**Returns:**
- `encoding`: The encoding used
- `bytes`: Number of UTF-8 bytes
- `codepoints`: Number of Unicode codepoints
- `hashes`: Object mapping algorithm names to hex digests
- `warnings`: Array of warnings (e.g., for md5)
- `summary`: Human-readable summary

**Example:**
```json
{"name": "text_hash", "arguments": {"text": "hello world", "algorithms": ["sha256", "md5"]}}
// Returns: {"ok": true, "result": {"encoding": "utf-8", "bytes": 11, "codepoints": 11, "hashes": {"sha256": "...", "md5": "..."}, ...}}
```

**Limits:** Input limited to 100,000 characters.

---

### path_analyze

Analyze path components, extensions, hidden status, and traversal without filesystem access. Lexical analysis only.

**Arguments:**
- `path` (string): Path string to analyze
- `style` (string, optional): "auto" | "posix" | "windows" (default "auto")
- `detail` (string, optional): "summary" | "normal" | "full" (default "normal")

**Tier:** 2
**Tags:** `text`, `path`, `filesystem`, `lexical`

**Returns:**
- `input`: Original input path
- `style`: Detected or specified style (posix/windows)
- `absolute`: Boolean indicating if path is absolute
- `has_traversal`: Boolean indicating if path contains `..` segments
- `components`: Array of path components
- `parent`: Parent directory
- `name`: Filename
- `stem`: Filename without extension
- `suffix`: File extension (single)
- `suffixes`: All extensions (for `.tar.gz`)
- `hidden`: Boolean indicating if file/dir starts with `.`
- `normalized_lexical`: Lexically normalized path
- `warnings`: Array of warnings (e.g., traversal, unicode issues)
- `summary`: Human-readable summary

**Example:**
```json
{"name": "path_analyze", "arguments": {"path": "../src/lib.rs"}}
// Returns: {"ok": true, "result": {"input": "../src/lib.rs", "style": "posix", "absolute": false, "has_traversal": true, "name": "lib.rs", "stem": "lib", "suffix": ".rs", ...}}
```

**Limits:** Input limited to 100,000 characters. No filesystem access.

---

### identifier_analyze

Classify and validate identifier naming conventions across languages. Help avoid naming drift.

**Arguments:**
- `text` (string): Identifier to analyze
- `languages` (array of strings, optional): Languages to check (python, rust, javascript, env) (default all)
- `detail` (string, optional): "summary" | "normal" | "full" (default "normal")

**Tier:** 3
**Tags:** `text`, `identifier`, `naming`, `validation`, `language`

**Returns:**
- `text`: Original identifier
- `classification`: Primary classification (snake_case, camelCase, PascalCase, kebab-case, SCREAMING_SNAKE_CASE, mixed, invalid)
- `python_valid`: Boolean for Python identifier
- `python_keyword`: Boolean if Python keyword
- `rust_valid`: Boolean for Rust identifier
- `rust_keyword`: Boolean if Rust keyword
- `javascript_valid`: Boolean for JavaScript identifier
- `env_valid`: Boolean for environment variable name
- `transforms`: Suggested transformations:
  - `snake_case`, `kebab_case`, `pascal_case`, `screaming_snake_case`
- `warnings`: Array of warnings
- `summary`: Human-readable summary

**Example:**
```json
{"name": "identifier_analyze", "arguments": {"text": "my_function_name"}}
// Returns: {"ok": true, "result": {"text": "my_function_name", "classification": "snake_case", "python_valid": true, "python_keyword": false, "env_valid": true, ...}}
```

**Limits:** Input limited to 100,000 characters.

---

### validate_schema_light

Validate JSON against a simple schema format with type, required, enum, pattern, and nested constraints. Does NOT implement full JSON Schema.

**Arguments:**
- `text` (string): JSON document string to validate
- `schema` (object): Schema to validate against
- `detail` (string, optional): "summary" | "normal" | "full" (default "normal")

**Tier:** 3
**Tags:** `validation`, `json`, `schema`, `structured-data`

**Supported Schema Features:**
- `type`: "object", "array", "string", "number", "integer", "boolean", "null"
- `required`: Array of required property names
- `properties`: Object with property definitions
- `additional_properties`: Boolean to disallow extra properties
- `enum`: Array of allowed string values
- `min_length`, `max_length`: String length constraints
- `min_items`, `max_items`: Array length constraints
- `items`: Schema for array items
- `pattern`: Regex pattern for strings

**Returns:**
- `valid`: Boolean
- `errors`: Array of validation errors:
  - `path`: JSON Pointer path to violation
  - `message`: Human-readable error message
  - `type`: Error type
- `summary`: Human-readable summary

**Example:**
```json
{"name": "validate_schema_light", "arguments": {"text": "{\"name\": \"test\", \"version\": \"1.0.0\"}", "schema": {"type": "object", "required": ["name", "version"], "properties": {"name": {"type": "string"}, "version": {"type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$"}}}}
// Returns: {"ok": true, "result": {"valid": true, "errors": [], "summary": "Valid against schema"}}
```

**Limits:** Input limited to 100,000 characters.

---

### unit_convert

Convert a numeric value from one unit to another using pre-defined conversion factors.

**Arguments:**
- `value` (number): Numeric value to convert
- `from_unit` (string): Source unit (e.g., 'km', 'ft', 'kg')
- `to_unit` (string): Target unit (e.g., 'm', 'in', 'lb')

**Tier:** 2
**Tags:** `math`, `units`, `conversion`

**Returns:**
- `value`: Converted value
- `from_unit`: Source unit
- `to_unit`: Target unit
- `factor`: Conversion factor used

**Example:**
```json
{"name": "unit_convert", "arguments": {"value": 1, "from_unit": "km", "to_unit": "m"}}
// Returns: {"ok": true, "result": {"value": 1000.0, "from_unit": "km", "to_unit": "m", "factor": 1000.0}}
```

---

### unit_info

Get information about a unit including its canonical form and category.

**Arguments:**
- `unit` (string): Unit name or alias (e.g., 'km', 'kilogram', '℃')

**Tier:** 2
**Tags:** `math`, `units`, `information`

**Returns:**
- `unit`: Original input
- `canonical`: Canonical unit name
- `category`: Unit category (e.g., 'length', 'mass', 'temperature')
- `is_valid`: Whether the unit is recognized

**Example:**
```json
{"name": "unit_info", "arguments": {"unit": "kilograms"}}
// Returns: {"ok": true, "result": {"unit": "kilograms", "canonical": "kg", "category": "mass", "is_valid": true}}
```

---

### constant_lookup

Look up physical constant values and symbols (Avogadro, Planck, speed of light, etc.).

**Arguments:**
- `name` (string): Constant name (e.g., 'avogadro', 'planck', 'c', 'G')

**Tier:** 2
**Tags:** `math`, `constants`, `physics`, `lookup`

**Returns:**
- `name`: Original input
- `value`: Constant value
- `symbol`: Display symbol (e.g., 'N_A', 'h', 'c')
- `display_name`: Human-readable name

**Example:**
```json
{"name": "constant_lookup", "arguments": {"name": "avogadro"}}
// Returns: {"ok": true, "result": {"name": "avogadro", "value": 6.02214076e+23, "symbol": "N_A", "display_name": "Avogadro constant"}}
```

**Supported constants:** avogadro, planck, boltzmann, c (speed of light), echarge (elementary charge), faraday, amu, epsilon0 (vacuum permittivity), mu0 (vacuum permeability), g (standard gravity), G (gravitational constant), rydberg, stefan (Stefan-Boltzmann), hbar (reduced Planck), me (electron mass), mp (proton mass), mn (neutron mass), re (classical electron radius), alpha (fine-structure), wien (Wien displacement), r (gas constant)

---

### json_shape

Analyze the structure of a JSON document without returning values. Shows type, keys, and nested structure with configurable depth limits.

**Arguments:**
- `text` (string): JSON document string to analyze
- `max_depth` (integer, optional): Maximum depth for nested structure (default 4)
- `max_keys` (integer, optional): Maximum keys to show per object (default 100)
- `max_array_items` (integer, optional): Maximum array item previews (default 5)

**Tier:** 3
**Tags:** `json`, `structured-data`, `shape`, `schema`

**Returns:**
- `valid`: Boolean
- `top_level_type`: "object", "array", or primitive type name
- `structure`: Nested structure representation

**Example:**
```json
{"name": "json_shape", "arguments": {"text": "{\"a\": 1, \"b\": [1, 2, 3]}", "max_depth": 2}}
// Returns: {"ok": true, "result": {"valid": true, "top_level_type": "object", "structure": {"a": "integer", "b": "array"}}}
```

---

### regex_finditer

Find all regex matches in text with positions, line/column info, and capture groups.

**Arguments:**
- `pattern` (string): Regular expression pattern
- `text` (string): Input string to search
- `flags` (array of strings, optional): Flag names (IGNORECASE, MULTILINE, DOTALL, etc.)
- `max_matches` (integer, optional): Maximum matches to return (default 100)
- `include_line_column` (boolean, optional): Include line and column info (default true)
- `include_groups` (boolean, optional): Include capture groups (default true)

**Tier:** 1
**Tags:** `text`, `regex`, `search`, `find`, `pattern`

**Returns:**
- `match_count`: Number of matches found
- `matches`: Array of match objects with span, groups, line/column info

**Example:**
```json
{"name": "regex_finditer", "arguments": {"pattern": "(\\d+)", "text": "abc 123 def 456"}}
// Returns: {"ok": true, "result": {"match_count": 2, "matches": [{"span": [4, 7], "groups": ["123"], ...}, ...]}}
```

**Limits:** Text limited to 100,000 characters. Pattern limited to 1,000 characters. Maximum 100 matches.

---

### regex_safety_check

Heuristic check for potential catastrophic backtracking risks in regex patterns. Flags nested quantifiers, repeated alternations, ambiguous dot-star, and backreferences.

**Arguments:**
- `pattern` (string): Regular expression pattern to check

**Tier:** 1
**Tags:** `text`, `regex`, `safety`, `security`, `backtracking`

**Returns:**
- `safe`: Boolean indicating if pattern appears safe
- `findings`: Array of risk findings with severity and explanation
- `pattern_length`: Length of the pattern

**Example:**
```json
{"name": "regex_safety_check", "arguments": {"pattern": "(a+)+b"}}
// Returns: {"ok": true, "result": {"safe": false, "findings": [{"kind": "nested_quantifier", "severity": "high", ...}], ...}}
```

---

## Error Responses

When a tool call fails, the response includes an error envelope:

```json
{"ok": false, "error_type": "invalid_arguments", "error": "Invalid normalization form", "hints": ["Use NFC or NFD"]}
```

**Error types:**
- `invalid_arguments`: Input validation failed (wrong type, out of range, etc.)
- `input_too_large`: Input exceeds size limits
- `unsupported_option`: Unknown or unsupported option value
- `parse_error`: Could not parse input (invalid JSON, regex, etc.)
- `evaluation_error`: Math expression evaluation failed
- `timeout`: Operation timed out
- `cancelled`: Request was cancelled before dispatch
- `internal_error`: Unexpected error in the tool

---

## Response Envelope

All tool responses follow a standard envelope. Callers (e.g., `codegg`) can consume results predictably by checking the envelope fields.

### Success Envelope

```json
{
  "ok": true,
  "tool": "tool_name",
  "result": { ... },
  "warnings": [],
  "limits_applied": [],
  "findings": [],
  "machine_code": null,
  "recommended_next_tool": null
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `ok` | boolean | yes | Always `true` for success |
| `tool` | string | yes | Tool name that produced this result |
| `result` | object | yes | Tool-specific result payload |
| `warnings` | array of strings | yes | Human-readable warnings |
| `limits_applied` | array of strings | yes | Limits that were applied (e.g., truncation) |
| `findings` | array of Finding | no | Structured issues or observations |
| `machine_code` | string | no | Stable code summarizing the outcome |
| `recommended_next_tool` | string or array | no | Suggested follow-up tool(s) |

### Error Envelope

```json
{
  "ok": false,
  "tool": "tool_name",
  "error_type": "invalid_arguments",
  "error": "Human-readable error message",
  "hints": ["Suggestion for fixing the error"],
  "warnings": []
}
```

### Finding Shape

Findings provide structured, machine-readable diagnostics. They are emitted by tools that perform inspection, validation, or safety analysis.

```json
{
  "code": "ZERO_WIDTH_CHAR",
  "severity": "warn",
  "message": "Zero-width character found at index 4",
  "span": {
    "byte_start": 4,
    "byte_end": 7,
    "char_start": 4,
    "char_end": 5,
    "line": 1,
    "column": 5
  },
  "details": {}
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `code` | string | yes | Machine-readable code (e.g., `INVISIBLE_CHAR`, `CONFUSABLE_CHAR`, `JSON_PARSE_ERROR`) |
| `severity` | string | yes | One of `info`, `warn`, `error` |
| `message` | string | yes | Human-readable description |
| `span` | object | no | Location within the input (byte and character offsets, line/column) |
| `details` | object | no | Additional structured context |

**Common finding codes:**

| Code | Severity | Description |
|------|----------|-------------|
| `INVISIBLE_CHAR` | warn | Invisible Unicode character detected |
| `CONFUSABLE_CHAR` | warn | Confusable (homoglyph) character detected |
| `BIDI_CONTROL` | warn | Bidirectional control character detected |
| `JSON_PARSE_ERROR` | error | Invalid JSON syntax |
| `REGEX_UNSAFE` | warn | Regex pattern may cause catastrophic backtracking |
| `PATH_TRAVERSAL` | warn | Path contains `..` traversal |
| `PATH_HIDDEN` | info | Path starts with a dot |
| `IDENT_COLLISIONS` | warn | Identifier collision detected |
| `IDENT_INVALID` | error | Invalid identifier for target language |

**Severity semantics:**
- `info`: Observational, no action required
- `warn`: Potential issue, review recommended
- `error`: Definite problem, action required

---

## Input Limits

The MCP server enforces these limits to prevent DoS:
- `MAX_TEXT_LENGTH`: 100,000 characters per text argument
- `MAX_LIST_ITEMS`: 10,000 items per list argument
- `MAX_REGEX_SAMPLES`: 100 samples per regex test
- `MAX_EXPRESSION_LENGTH`: 10,000 characters for math expressions

---

## Cancellation Semantics

The MCP server supports request cancellation via the `notifications/cancelled` method. Cancellation is best-effort — once a tool starts executing in the thread pool, it cannot be reliably stopped.

### Pre-dispatch cancellation

When a `notifications/cancelled` message arrives, the server records the `requestId` in a bounded set (`_cancelled_requests`, capped at 10,000 entries with FIFO eviction). If a `tools/call` arrives with that ID *before* dispatch, it is immediately rejected:

```json
{
  "ok": false,
  "error_type": "cancelled",
  "error": "Tool 'math_eval' request was cancelled",
  "hints": []
}
```

After rejection, the cancelled ID is removed from the tracking set so it does not affect future requests.

### Post-dispatch cancellation (timeout path)

If a tool is already running when a timeout fires, the server calls `Future.cancel()` on the worker. This is best-effort: it only succeeds if the worker has not started executing yet (Python's `ThreadPoolExecutor` semantics). In practice, most tools will have already started, so cancellation will not stop them. The worker completes on its own, and its result is discarded.

### Bounded thread pool

Tool invocations run in a bounded `ThreadPoolExecutor` (default 16 workers, configurable via `EGGCALC_MCP_MAX_TOOL_WORKERS`). This provides natural back-pressure: when all workers are busy, new tasks queue rather than spawning unbounded threads. This prevents thread accumulation under sustained load or repeated timeouts.

### Long-running tools

Tools that perform heavy computation (regex scanning on large text, diff analysis, schema traversal, identifier collision detection) may run for the full `MAX_TOOL_TIMEOUT_SECONDS` (30 seconds) even after cancellation. The client receives a timeout error, but the worker continues until it finishes or the process exits.

### Error envelope determinism

Both timeout and cancellation error envelopes are sanitized and follow the standard error format. The `error_type` field distinguishes `"timeout"` (tool ran too long) from `"cancelled"` (rejected before dispatch). Error messages are truncated to 2,000 characters and stripped of non-ASCII characters.

### Cooperative cancellation (future enhancement)

Currently, tools do not check for cancellation mid-execution. A future enhancement could add a cancellation token or callback that long-running tools check periodically (e.g., inside regex iteration loops or recursive JSON traversal). This would allow tools to exit early when cancelled, rather than running to completion.

---

## Tool Tiers

Tools are categorized into tiers based on scope and context cost. See [tool_inventory.md](tool_inventory.md) for the authoritative tier assignments.

**Tier 0:** Ultra-common, small-schema tools. Always exposed.
- `math_eval`, `text_equal`, `text_count`, `text_fingerprint`, `validate_json`, `path_normalize`

**Tier 1:** Default coding-agent sanity tools. Exposed by default for coding agents.
- `text_diff_explain`, `text_inspect`, `text_replace_check`, `line_range_extract`, `json_query`, `json_compare`, `validate_toml`, `glob_match`, `validate_regex`, `regex_finditer`, `regex_safety_check`, `identifier_inspect`, `escape_text`, `unescape_text`, `text_window`, `json_canonicalize`, `validate_brackets`, `list_dedupe`, `list_sort`

**Tier 2:** Heavier analysis tools. Exposed when text/unicode/config analysis is needed.
- `text_position`, `text_hash`, `text_transform`, `text_measure`, `unit_convert`, `unit_info`, `constant_lookup`, `path_analyze`, `path_compare`, `path_scope_check`, `list_compare`, `json_extract`, `version_compare`, `toml_shape`, `markdown_structure`, `code_fence_extract`, `dotenv_validate`, `ini_validate`, `patch_apply_check`, `patch_summary`, `shell_split`, `shell_quote_join`, `argv_compare`, `unicode_policy_check`, `canonicalize_text`, `line_range_compare`, `diff_touched_paths`, `pyproject_inspect`, `repo_file_inventory`

**Tier 3:** Domain-specific tools. Opt-in for specialized workflows.
- `text_truncate`, `json_shape`, `identifier_analyze`, `validate_schema_light`, `version_constraint_check`, `cargo_toml_inspect`

---

## Profile Selection

The active profile controls which tools are available in `tools/call` and which tools are returned by `tools/list`. Select a profile at server startup with the `EGGCALC_MCP_PROFILE` environment variable:

```bash
# Start the server with a restricted profile
EGGCALC_MCP_PROFILE=codegg_core_min calc --mcp

# Start the server with math-only tools
EGGCALC_MCP_PROFILE=human_math calc --mcp
```

The default profile is `full`, which exposes all 77 tools. Unknown profile names cause an immediate `SystemExit(1)` at startup.

Tools outside the active profile are **rejected** at `tools/call` time with JSON-RPC error `-32602`:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {"name": "math_eval", "arguments": {"expression": "1+1"}}
}
```
→ Returns error `-32602`: `Tool 'math_eval' is not available in profile 'codegg_core_min'.`

You can override the active profile per-request by passing a `profile` parameter in `tools/list`:

```json
{"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {"profile": "human_math"}}
```

The `profiles/list` method returns all available profiles and their tool counts, so agents can discover and switch profiles at runtime.

### Schema Detail

The `EGGCALC_MCP_SCHEMA_DETAIL` environment variable controls the default schema verbosity for `tools/list` responses. This can also be overridden per-request with the `schema_detail` parameter:

| Level | Behavior |
|-------|----------|
| `"full"` (default) | Complete schema with descriptions, examples, defaults, and verbose help |
| `"normal"` | Truncated descriptions (240 chars), compact output schema, preserves input schema structure |
| `"compact"` | Tool names, types, required fields, enums only. Drops descriptions and defaults for minimal context |

---

## Tool Profiles

Profiles are named subsets of tools. Each profile includes only the tools relevant to its use case, minimizing context overhead. Use `EGGCALC_MCP_PROFILE` to select the active profile, or pass `profile` in `tools/list` to override per-request.

### `codegg_core_min`

Minimal preflight and edit-safety tools (6 tools). Ideal for agents with tight context budgets.

**Tools:** `command_preflight`, `config_preflight`, `edit_preflight`, `text_replace_check`, `text_security_inspect`, `validate_json`

**Use when:** You need edit preflight checks, config validation, or text safety inspection without loading the full tool set.

### `codegg_core`

Core coding-agent tools (22 tools). Recommended for general-purpose coding agents.

**Tools:** `cargo_toml_inspect`, `command_preflight`, `config_preflight`, `edit_preflight`, `go_mod_inspect`, `identifier_inspect`, `llm_json_output_check`, `lockfile_summary`, `markdown_link_check_lexical`, `package_json_inspect`, `path_normalize`, `pyproject_inspect`, `requirements_inspect`, `structured_data_compare`, `text_diff_explain`, `text_equal`, `text_fingerprint`, `text_inspect`, `text_replace_check`, `text_security_inspect`, `validate_json`, `validate_toml`

**Use when:** You want the standard set of tools for code editing, text inspection, diff analysis, path manipulation, JSON comparison, and TOML validation.

### `codegg_preflight`

Pre-execution safety tools (10 tools). For agents that need to validate actions before executing them.

**Tools:** `command_preflight`, `config_preflight`, `edit_preflight`, `llm_json_output_check`, `patch_apply_check`, `path_scope_check`, `prompt_input_inspect`, `shell_split`, `text_security_inspect`, `unicode_policy_check`

**Use when:** You need comprehensive preflight validation including edit safety, shell command inspection, path scope checks, and prompt security analysis.

### `codegg_unicode_security`

Unicode analysis and security tools (8 tools). For agents working with internationalized text, confusable detection, or Unicode security.

**Tools:** `canonicalize_text`, `identifier_inspect`, `prompt_input_inspect`, `text_inspect`, `text_position`, `text_security_inspect`, `text_transform`, `unicode_policy_check`

**Use when:** You need deep Unicode analysis, canonicalization profiles, or security policy checks beyond basic text inspection.

### `codegg_config`

Configuration and structured data tools (17 tools). For agents working with configuration files, patches, or structured data.

**Tools:** `config_preflight`, `dotenv_validate`, `ini_validate`, `json_canonicalize`, `json_compare`, `json_extract`, `lockfile_summary`, `go_mod_inspect`, `package_json_inspect`, `pyproject_inspect`, `requirements_inspect`, `structured_data_compare`, `toml_shape`, `validate_json`, `validate_schema_light`, `validate_toml`, `version_compare`

**Use when:** You need to validate, compare, or analyze configuration files, unified diffs, shell commands, or Markdown structure.

### `codegg_repo_audit`

Repository audit and manifest tools (18 tools). For agents auditing repository structure.

**Tools:** `cargo_toml_inspect`, `code_fence_extract`, `diff_file_headers`, `diff_hunk_ranges`, `diff_touched_paths`, `go_mod_inspect`, `identifier_table_inspect`, `json_shape`, `lockfile_summary`, `markdown_link_check_lexical`, `markdown_structure`, `package_json_inspect`, `patch_conflict_markers_inspect`, `pyproject_inspect`, `repo_file_inventory`, `requirements_inspect`, `text_fingerprint`, `unified_diff_validate`

**Use when:** You need to audit repository structure, inspect manifests, or check documentation quality.

### `codegg_patch`

Patch structural tools (12 tools). For agents working with unified diffs and patches.

**Tools:** `diff_file_headers`, `diff_hunk_ranges`, `diff_touched_paths`, `edit_preflight`, `line_range_compare`, `line_range_extract`, `patch_apply_check`, `patch_conflict_markers_inspect`, `patch_summary`, `text_diff_explain`, `text_replace_check`, `unified_diff_validate`

**Use when:** You are working with unified diffs and need to validate or summarize patches.

### `codegg_shell`

Shell command analysis tools (5 tools). For agents inspecting or comparing shell commands.

**Tools:** `argv_compare`, `command_preflight`, `regex_safety_check`, `shell_quote_join`, `shell_split`

**Use when:** You need to split, compare, or validate shell commands and argv lists.

### `human_math`

Math and unit conversion tools (4 tools). For agents focused on calculations and unit conversions.

**Tools:** `constant_lookup`, `math_eval`, `unit_convert`, `unit_info`

**Use when:** You need math evaluation, unit conversion, physical constants, or unit metadata.

### `default`

General-purpose coding-agent tools (25 tools). The `default` profile is a curated subset for typical coding workflows.

See [tool_inventory.md](tool_inventory.md) for the complete profile membership tables.

### `full`

All 77 tools. This is the default profile — it includes every tool where `llm_exposure` is not `"hidden"`.

### Filtering tools/list

The `tools/list` method supports these filters to narrow the returned tool set:

| Parameter | Type | Description |
|-----------|------|-------------|
| `profile` | string | Return only tools in the named profile (e.g., `"codegg_core_min"`). Overrides the active profile. Unknown profile names return a JSON-RPC error. |
| `tier` | integer | Return only tools at the given tier (0, 1, 2, or 3). |
| `tags` | array of strings | Return tools that have **all** listed tags. |
| `names` | array of strings | Return only the listed tool names (subset selection). |
| `schema_detail` | string | `"compact"`, `"normal"`, or `"full"` — controls schema verbosity per-request. Overrides the global default. |

Filters are applied **after** profile selection: the profile narrows the tool set, then `tier`/`tags`/`names` filter further within that profile.

Unknown `profile` values return a JSON-RPC error code `-32602` (invalid params) rather than silently returning an empty tool list.

### profiles/list

A `profiles/list` request returns all available profile names, their tool lists, and tool counts:

```json
{"jsonrpc": "2.0", "id": 1, "method": "profiles/list"}
```

**Response:**
```json
{
  "result": {
    "active": "full",
    "profiles": {
      "full": {"tools": ["math_eval", "text_equal", ...], "tool_count": 77},
      "default": {"tools": ["escape_text", "glob_match", ...], "tool_count": 25},
      "codegg_core_min": {"tools": ["command_preflight", ...], "tool_count": 6},
      "codegg_core": {"tools": ["cargo_toml_inspect", ...], "tool_count": 22},
      "codegg_preflight": {"tools": ["command_preflight", ...], "tool_count": 10},
      "codegg_patch": {"tools": ["diff_file_headers", ...], "tool_count": 12},
      "codegg_config": {"tools": ["config_preflight", ...], "tool_count": 17},
      "codegg_unicode_security": {"tools": ["canonicalize_text", ...], "tool_count": 8},
      "codegg_shell": {"tools": ["argv_compare", ...], "tool_count": 5},
      "codegg_repo_audit": {"tools": ["cargo_toml_inspect", ...], "tool_count": 18},
      "human_math": {"tools": ["constant_lookup", ...], "tool_count": 4}
    }
  }
}
```

---

## AI Agent Integration Example

Here's how an AI agent would use the MCP server:

```python
import subprocess
import json

class CalcMCPClient:
    def __init__(self):
        self.process = subprocess.Popen(
            ["calc", "--mcp"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        self._next_id = 1

    def _send_request(self, method, params=None):
        request = {
            "jsonrpc": "2.0",
            "id": self._next_id,
            "method": method,
            "params": params or {}
        }
        self._next_id += 1

        self.process.stdin.write(json.dumps(request).encode())
        self.process.stdin.write(b"\n")
        self.process.stdin.flush()

        response = json.loads(self.process.stdout.readline())
        return response.get("result")

    def list_tools(self):
        return self._send_request("tools/list")

    def call_tool(self, name, arguments):
        return self._send_request("tools/call", {"name": name, "arguments": arguments})

    def math_eval(self, expression):
        return self.call_tool("math_eval", {"expression": expression})

    def text_inspect(self, text):
        return self.call_tool("text_inspect", {"text": text})

# Usage
client = CalcMCPClient()
result = client.math_eval("5 + 3")  # {"ok": true, "result": {"result": "8", "type": "int"}}
inspection = client.text_inspect("p\u0430ypal")  # Confusable detection
```

---

### glob_match

Match a glob pattern against a path with explicit semantics.

**Arguments:**
- `pattern` (string): Glob pattern (e.g., "src/**/*.rs")
- `path` (string): Path to match
- `platform` (string, optional): "posix" or "windows"
- `case_sensitive` (boolean, optional): Default true

**Tier:** 1
**Tags:** `text`, `glob`, `pattern`, `path`, `wildcard`

**Glob Semantics:**
- `*` matches any characters within one path segment (not crossing `/`)
- `**` matches zero or more full path segments
- `?` matches exactly one character within a segment

**Example:**
```json
{"name": "glob_match", "arguments": {"pattern": "src/**/*.rs", "path": "src/main.rs"}}
// Returns: {"ok": true, "result": {"matches": true, "normalized_pattern": "src/**/*.rs", ...}}
```

---

### text_fingerprint

Compute a deterministic SHA-256 fingerprint of text with canonicalization options.

**Arguments:**
- `text` (string): Input string to fingerprint
- `unicode` (string, optional): "raw", "NFC", "NFD", "NFKC", "NFKD"
- `newline` (string, optional): "raw" or "LF"
- `trim_final_newline` (boolean, optional): Remove trailing newline
- `casefold` (boolean, optional): Apply casefolding before hashing

**Tier:** 0
**Tags:** `text`, `hash`, `fingerprint`, `sha256`, `identity`, `canonicalization`

**Example:**
```json
{"name": "text_fingerprint", "arguments": {"text": "hello\n", "trim_final_newline": true, "unicode": "NFC"}}
// Returns: {"ok": true, "result": {"sha256": "...", "bytes_utf8": 5, "codepoints": 5, ...}}
```

---

### identifier_inspect

Inspect identifiers for validity and collisions. Detects confusables, mixed scripts, normalization issues, and casefold collisions.

**Arguments:**
- `identifiers` (array): List of identifier strings to inspect
- `language` (string, optional): "generic", "python", "rust", "javascript", "typescript", "json_key"
- `normalization` (string, optional): "NFC", "NFD", etc.
- `casefold` (boolean, optional): Check for casefold collisions
- `check_confusables` (boolean, optional): Default true

**Tier:** 1
**Tags:** `text`, `identifier`, `collision`, `confusable`, `security`, `validation`

**Example:**
```json
{"name": "identifier_inspect", "arguments": {"identifiers": ["paypal", "pаypal"], "language": "python"}}
// Returns: {"ok": true, "result": {"identifiers": [{"raw": "paypal", "scripts": ["Latin"], ...}, ...], "collisions": [...]}}
```

---

### identifier_table_inspect

Inspect a table of identifiers for casefold collisions, normalization collisions, confusable/near-collisions, style variants, reserved keyword hits, and mixed naming style groups. Accepts structured entries with name, kind, file, and line metadata.

**Arguments:**
- `identifiers` (array): List of identifier entries (objects with required `name`, optional `kind`, `file`, `line`)
- `language` (string, optional): "python" (default), "rust", "javascript", "typescript", "generic", "json_key"
- `checks` (array, optional): Subset of `["casefold", "normalization", "confusable", "style", "reserved", "mixed_style"]`

**Tier:** 3
**Tags:** `text`, `identifier`, `collision`, `naming`, `style`, `reserved`, `validation`

**Checks:**
| Check | What it detects |
|-------|----------------|
| `casefold` | Identifiers that collide when casefolded (e.g., `myVar` vs `myvar`) |
| `normalization` | Identifiers that collide under NFC normalization (e.g., `cafe\u0301` vs `caf\u00e9`) |
| `confusable` | Confusable characters or Levenshtein-distance-1 near-collisions |
| `style` | Same stripped form but different naming styles (snake_case vs camelCase vs kebab-case) |
| `reserved` | Identifiers that are reserved keywords in the target language |
| `mixed_style` | Groups where identifiers share the same stripped form but use different styles |

**Example:**
```json
{"name": "identifier_table_inspect", "arguments": {
  "identifiers": [
    {"name": "myVar", "file": "src/main.py", "line": 10},
    {"name": "myvar", "file": "src/utils.py", "line": 25},
    {"name": "my_var"},
    {"name": "if"}
  ],
  "language": "python"
}}
// Returns: {"ok": true, "result": {"count": 4, "collisions": [...], "reserved_keyword_hits": [...], "mixed_style_groups": [...]}}
```

---

### path_normalize

Normalize and analyze a path with explicit platform semantics.

**Arguments:**
- `path` (string): Path to normalize
- `platform` (string, optional): "posix" or "windows" (default "posix")
- `collapse_dot_segments` (boolean, optional): Remove . and .. segments (default true)
- `preserve_trailing_separator` (boolean, optional): Keep trailing slash (default false)

**Tier:** 0
**Tags:** `text`, `path`, `normalization`, `platform`

**Returns:**
- `normalized`: Normalized path string
- `is_absolute`: Boolean
- `components`: Array of path segments
- `warnings`: Array of warnings

**Example:**
```json
{"name": "path_normalize", "arguments": {"path": "src/../src/main.rs", "collapse_dot_segments": true}}
// Returns: {"ok": true, "result": {"normalized": "src/main.rs", "is_absolute": false, ...}}
```

---

### path_compare

Compare two paths under explicit normalization rules with separator normalization, dot-segment collapsing, and optional case-insensitive comparison.

**Arguments:**
- `left` (string): First path string
- `right` (string): Second path string
- `platform` (string, optional): "posix" or "windows" (default "posix")
- `case_sensitive` (boolean, optional): Case-sensitive comparison (default true)
- `normalize_separators` (boolean, optional): Normalize path separators (default true)
- `collapse_dot_segments` (boolean, optional): Collapse . and .. segments (default true)

**Tier:** 2
**Tags:** `text`, `path`, `filesystem`, `comparison`

**Returns:**
- `equal`: Boolean indicating if paths are equal under normalization
- `left_normalized`: Normalized left path
- `right_normalized`: Normalized right path
- `differences`: Array of differences found
- `findings`: Array of normalization notes

**Example:**
```json
{"name": "path_compare", "arguments": {"left": "src/../src/main.rs", "right": "src/main.rs"}}
// Returns: {"ok": true, "result": {"equal": true, "left_normalized": "src/main.rs", "right_normalized": "src/main.rs", ...}}
```

---

### path_scope_check

Determine whether a target path remains lexically inside a declared root. Lexical only, does not resolve symlinks. Symlink-safe enforcement requires filesystem-aware checks outside this tool.

**Arguments:**
- `root` (string): Root directory path
- `target` (string): Target path to check
- `platform` (string, optional): "posix" or "windows" (default "posix")
- `case_sensitive` (boolean, optional): Case-sensitive comparison (default true)

**Tier:** 2
**Tags:** `text`, `path`, `filesystem`, `security`, `scope`

**Returns:**
- `inside_root`: Boolean indicating if target is lexically inside root
- `root_normalized`: Normalized root path
- `target_normalized`: Normalized target path
- `relative_path`: Relative path from root to target (if inside)
- `escapes_via_dotdot`: Boolean indicating if target contains parent traversal
- `absolute_target`: Absolute form of target
- `findings`: Array of analysis notes

**Example:**
```json
{"name": "path_scope_check", "arguments": {"root": "/home/user", "target": "/home/user/docs/file.txt"}}
// Returns: {"ok": true, "result": {"inside_root": true, "relative_path": "docs/file.txt", ...}}
```

**Security note:** This tool performs lexical analysis only. It does NOT resolve symlinks. To enforce that a path stays within a root on a real filesystem, combine this tool with filesystem-aware checks.

---

### version_compare

Compare two version strings with explicit scheme.

**Arguments:**
- `a` (string): First version
- `b` (string): Second version
- `scheme` (string, optional): "semver" or "loose" (default "semver")

**Tier:** 2
**Tags:** `text`, `version`, `semver`, `comparison`

**Supported schemes:**
- `semver`: strict major.minor.patch comparison. Pre-release identifiers are parsed but ignored in comparison (simplified behavior — use `version_constraint_check` for full pre-release ordering).
- `loose`: extract all numeric parts and compare sequentially. Non-numeric suffixes are ignored.

**Note:** PEP 440 is not supported. Passing `scheme: "pep440"` returns an error.

**Returns:**
- `comparison`: -1, 0, or 1
- `valid`: Boolean
- `scheme`: The scheme used

**Example:**
```json
{"name": "version_compare", "arguments": {"a": "1.2.3", "b": "1.2.10", "scheme": "semver"}}
// Returns: {"ok": true, "result": {"comparison": -1, "valid": true, "scheme": "semver"}}
```

---

### version_constraint_check

Check whether a version satisfies a constraint under a declared versioning scheme.

**Arguments:**
- `version` (string): Version to check (e.g., "1.2.3", "0.5.0-beta.1")
- `constraint` (string): Version constraint (e.g., ">=1.0,<2.0", "^1.2.3", "~0.5", "1.*")
- `scheme` (string, optional): "semver" or "cargo" (default "semver")

**Tier:** 3
**Tags:** `version`, `semver`, `cargo`, `constraint`, `satisfiability`

**Supported schemes:**
- `semver`: strict major.minor.patch with full pre-release ordering. Supports operators: `==`, `!=`, `>=`, `<=`, `>`, `<`, `=`, `!=`, and comma-separated ranges.
- `cargo`: semver with Rust/Cargo-style range operators: `^` (caret), `~` (tilde), `*` (wildcard).

**Supported constraint forms:**
- Semver exact: `1.2.3`
- Semver comparison: `>=1.2.3`, `<2.0`, `!=1.0`
- Semver comma-separated ranges: `>=1.2,<2.0`
- Cargo caret: `^1.2.3` (>=1.2.3, <2.0.0)
- Cargo tilde: `~1.2.3` (>=1.2.3, <1.3.0)
- Cargo wildcard: `1.*` (>=1.0.0, <2.0.0), `1.2.*` (>=1.2.0, <1.3.0)

**Returns:**
- `satisfies`: Boolean
- `parsed_version`: Parsed version components
- `parsed_constraint`: Parsed constraint components
- `scheme`: The scheme used
- `explanation`: Human-readable explanation
- `findings`: Analysis notes and warnings

**Example:**
```json
{"name": "version_constraint_check", "arguments": {"version": "1.5.0", "constraint": ">=1.2,<2.0", "scheme": "semver"}}
// Returns: {"ok": true, "result": {"satisfies": true, "parsed_version": {"major": 1, "minor": 5, "patch": 0, ...}, ...}}
```

---

### cargo_toml_inspect

Inspect `Cargo.toml` text without network or filesystem access.

**Arguments:**
- `text` (string): The Cargo.toml content
- `check_workspace` (boolean, optional): Whether to analyze `[workspace]` section (default true)
- `check_dependencies` (boolean, optional): Whether to analyze dependency sections (default true)

**Tier:** 3
**Tags:** `rust`, `cargo`, `toml`, `dependencies`, `workspace`, `inspection`

**Returns:**
- `parse_ok`: Boolean - whether TOML parsed successfully
- `package`: Object with name, version, edition, license, repository, readme
- `workspace`: Object with present, members, exclude
- `dependencies`: Object by section: dependencies, dev-dependencies, build-dependencies, target-specific
- `path_dependencies`: Array of extracted path values
- `suspicious_dependency_names`: Array of names with suspicious patterns
- `duplicate_or_confusable_dependency_names`: Array of names that normalize identically
- `findings`: Array of structural findings

**Example:**
```json
{"name": "cargo_toml_inspect", "arguments": {"text": "[package]\nname = \"my-crate\"\nversion = \"0.1.0\"\nedition = \"2021\"\n\n[dependencies]\nserde = \"1.0\"\nmy-lib = { path = \"../my-lib\" }\n"}}
// Returns: {"ok": true, "result": {"parse_ok": true, "package": {"name": "my-crate", "version": "0.1.0", "edition": "2021"}, "path_dependencies": ["../my-lib"], ...}}
```

---

### toml_shape

Analyze the structure of a TOML document.

**Arguments:**
- `text` (string): TOML document
- `max_depth` (integer, optional): Maximum nesting depth (default 4)
- `max_tables` (integer, optional): Maximum tables to report (default 50)

**Tier:** 2
**Tags:** `text`, `toml`, `structured-data`, `shape`

**Returns:**
- `valid`: Boolean
- `top_level_keys`: Array of top-level key names
- `tables`: Array of table info (name, depth, key_count)
- `truncated`: Boolean

**Example:**
```json
{"name": "toml_shape", "arguments": {"text": "[package]\nname = \"foo\"\n[dependencies]\n"}}
// Returns: {"ok": true, "result": {"valid": true, "top_level_keys": ["package", "dependencies"], ...}}
```

---

### list_dedupe

Remove duplicates from a list with optional normalization and casefolding.

**Arguments:**
- `items` (array): List of strings to deduplicate
- `normalization` (string, optional): "NFC", "NFD", "NFKC", "NFKD", or "raw" (default "NFC")
- `casefold` (boolean, optional): Case-insensitive deduplication (default false)
- `stable` (boolean, optional): Accepted for compatibility; deduplication keeps first occurrence order

**Tier:** 1
**Tags:** `text`, `list`, `deduplication`, `normalization`

**Returns:**
- `items`: Deduplicated list
- `original_count`: Original count
- `deduped_count`: After deduplication
- `duplicates_removed`: Number of removed duplicate entries

**Example:**
```json
{"name": "list_dedupe", "arguments": {"items": ["a", "A", "b", "a"], "casefold": true}}
// Returns: {"ok": true, "result": {"items": ["a", "b"], "original_count": 4, "deduped_count": 2, "duplicates_removed": 2}}
```

---

### list_sort

Sort a list of strings with optional normalization and casefolding.

**Arguments:**
- `items` (array): List of strings to sort
- `normalization` (string, optional): "NFC", "NFD", "NFKC", "NFKD", or "raw" (default "NFC")
- `casefold` (boolean, optional): Case-insensitive sorting (default false)
- `reverse` (boolean, optional): Descending order (default false)
- `stable` (boolean, optional): Accepted for compatibility; Python sorting is always stable

**Tier:** 1
**Tags:** `text`, `list`, `sorting`, `normalization`

**Returns:**
- `items`: Sorted list
- `original_count`: Original count
- `sorted_count`: Number of sorted items

**Example:**
```json
{"name": "list_sort", "arguments": {"items": ["b", "A", "c"], "casefold": true}}
// Returns: {"ok": true, "result": {"items": ["A", "b", "c"], "original_count": 3, "sorted_count": 3}}
```

---

### text_replace_check

Check whether a text replacement would apply cleanly before an agent attempts to edit text.

**Arguments:**
- `text` (string): Source text to search in
- `old` (string): Text to find
- `new` (string): Replacement text
- `mode` (string, optional): Matching mode - `exact`, `nfc`, `nfkc`, `casefold`, `whitespace_collapse` (default: `exact`)
- `expected_count` (integer, optional): Expected number of matches
- `allow_multiple` (boolean, optional): If false and more than one match, add a finding (default: false)
- `newline_policy` (string, optional): How to handle newlines - `preserve`, `normalize_lf`, `normalize_crlf` (default: `preserve`)
- `return_preview` (boolean, optional): Include before/after text previews (default: false)
- `max_preview_chars` (integer, optional): Maximum characters in preview output (default: 2000)

**Tier:** 2
**Tags:** `text`, `replace`, `edit`, `safety`, `check`

**Example:**
```json
{"name": "text_replace_check", "arguments": {"text": "hello world", "old": "world", "new": "earth"}}
// Returns: {"ok": true, "result": {"match_count": 1, "unique_match": true, "would_change": true, ...}}
```

---

### line_range_extract

Extract exact line ranges from text and return stable offsets, byte positions, line counts, and optional fingerprint.

**Arguments:**
- `text` (string): Input text
- `start_line` (integer): First line to extract
- `end_line` (integer): Last line to extract (inclusive)
- `line_base` (integer, optional): Base for line numbers (default: 1)
- `include_line_numbers` (boolean, optional): Include line number in each line dict (default: false)
- `include_fingerprint` (boolean, optional): Compute SHA-256 fingerprint (default: true)

**Tier:** 2
**Tags:** `text`, `line`, `range`, `extract`, `offset`

**Example:**
```json
{"name": "line_range_extract", "arguments": {"text": "line1\nline2\nline3", "start_line": 1, "end_line": 2}}
// Returns: {"ok": true, "result": {"text": "line1\nline2", "line_count_total": 3, ...}}
```

---

### line_range_compare

Compare a line range from two text inputs with exact, trailing-whitespace-ignoring, or newline-normalizing comparison.

**Arguments:**
- `left_text` (string): First text input
- `right_text` (string): Second text input
- `start_line` (integer): First line to compare
- `end_line` (integer): Last line to compare (inclusive)
- `line_base` (integer, optional): Base for line numbers (default: 1)
- `comparison_mode` (string, optional): `exact`, `ignore_trailing_whitespace`, `normalize_newlines` (default: `exact`)

**Tier:** 2
**Tags:** `text`, `line`, `range`, `compare`, `diff`

**Example:**
```json
{"name": "line_range_compare", "arguments": {"left_text": "aaa\nbbb", "right_text": "aaa\nBBB", "start_line": 2, "end_line": 2}}
// Returns: {"ok": true, "result": {"equal": false, "first_difference": {"line_number": 2, ...}, ...}}
```

---

### shell_split

Parse a shell-like command string into argv tokens and report risky lexical features.

**Arguments:**
- `command` (string): The shell command string to parse
- `shell` (string, optional): Shell dialect, only `posix` supported (default: `posix`)
- `detect_risky_features` (boolean, optional): Whether to detect risky lexical features (default: `true`)

**Tier:** 2
**Tags:** `shell`, `argv`, `parsing`, `security`, `sanity`

**Returns:**
- `parse_ok` (boolean): Whether the command parsed successfully
- `argv` (array): Parsed argument tokens
- `argc` (integer): Number of arguments
- `features` (object): Detected risky features (has_pipe, has_redirection, has_command_substitution, has_variable_expansion, has_glob_pattern, has_control_operator, has_unbalanced_quotes)
- `findings` (array): Analysis notes and warnings

**Note:** This is lexical POSIX-like parsing only, not full shell evaluation.

**Example:**
```json
{"name": "shell_split", "arguments": {"command": "cargo test -- --nocapture"}}
// Returns: {"ok": true, "result": {"parse_ok": true, "argv": ["cargo", "test", "--", "--nocapture"], "argc": 4, ...}}
```

---

### shell_quote_join

Safely quote a list of argv tokens into a POSIX-like shell string. Verifies round-trip safety.

**Arguments:**
- `argv` (array of strings): List of argument strings to join
- `shell` (string, optional): Shell dialect, only `posix` supported (default: `posix`)

**Tier:** 2
**Tags:** `shell`, `argv`, `quoting`, `safety`

**Returns:**
- `command` (string): Safely quoted command string
- `roundtrip_ok` (boolean): Whether shell_split(quote_join(argv)) produces equivalent argv
- `findings` (array): Analysis notes

**Example:**
```json
{"name": "shell_quote_join", "arguments": {"argv": ["echo", "hello world"]}}
// Returns: {"ok": true, "result": {"command": "echo 'hello world'", "roundtrip_ok": true, ...}}
```

---

### argv_compare

Compare two command strings or argv lists by parsed argv tokens rather than raw text.

**Arguments:**
- `left_command` (string, optional): Left command string to parse and compare
- `right_command` (string, optional): Right command string to parse and compare
- `left_argv` (array of strings, optional): Left pre-parsed argv list
- `right_argv` (array of strings, optional): Right pre-parsed argv list
- `shell` (string, optional): Shell dialect, only `posix` supported (default: `posix`)

**Tier:** 2
**Tags:** `shell`, `argv`, `comparison`, `sanity`

**Returns:**
- `argv_equal` (boolean): Whether parsed argv lists are identical
- `left_argv` (array): Resolved left argv
- `right_argv` (array): Resolved right argv
- `first_difference` (integer or null): Index of first differing token
- `findings` (array): Analysis notes

**Example:**
```json
{"name": "argv_compare", "arguments": {"left_command": "cargo test -- --nocapture", "right_argv": ["cargo", "test", "--", "--nocapture"]}}
// Returns: {"ok": true, "result": {"argv_equal": true, ...}}
```

---

### markdown_structure

Parse Markdown structure with a deterministic line scanner. Reports headings, code fences, links, HTML comments, frontmatter, and table detection. Not a full CommonMark parser.

**Arguments:**
- `text` (string): Markdown text to analyze
- `include_sections` (boolean, optional): Include heading detection (default true)
- `include_links` (boolean, optional): Include link detection (default true)
- `include_code_fences` (boolean, optional): Include code fence detection (default true)
- `include_html_comments` (boolean, optional): Include HTML comment detection (default true)

**Tier:** 2
**Tags:** `markdown`, `structure`, `headings`, `code-fences`, `links`, `frontmatter`

**Returns:**
- `headings` (array): Headings with level, text, line number, and slug
- `code_fences` (array): Code fences with language, start/end lines, closed state
- `links` (array): Links with visible text, target, line number, mismatch flags
- `html_comments` (array): HTML comments with text, line number, and column positions
- `frontmatter` (object): Detection result with present, format (yaml/toml), line range
- `tables_detected` (boolean): Whether Markdown tables were detected
- `findings` (array): Warnings (e.g., unclosed fences)

**Example:**
```json
{"name": "markdown_structure", "arguments": {"text": "# Hello\n\n```python\nprint('hi')\n```\n\n[link](http://example.com)"}}
// Returns: {"ok": true, "result": {"headings": [{"level": 1, "text": "Hello", "line": 1, "slug": "hello"}], "code_fences": [{"language": "python", "start_line": 3, "end_line": 5, "closed": true}], "links": [{"visible_text": "link", "target": "http://example.com", "line": 7, "mismatch_flags": []}], ...}}
```

---

### code_fence_extract

Extract fenced code blocks from Markdown with exact line ranges, optional language filter, content, and SHA-256 fingerprints. Reports unclosed fences.

**Arguments:**
- `text` (string): Markdown text to scan
- `language` (string, optional): Language filter (case-insensitive)
- `include_content` (boolean, optional): Include block content in output (default true)

**Tier:** 2
**Tags:** `markdown`, `code-fences`, `extraction`, `fingerprint`

**Returns:**
- `blocks` (array): Code blocks with index, language, start/end lines, closed state, content, fingerprint
- `unclosed_fences` (array): Unclosed code fences found
- `findings` (array): Warnings

**Example:**
```json
{"name": "code_fence_extract", "arguments": {"text": "```python\nprint('hi')\n```", "language": "python"}}
// Returns: {"ok": true, "result": {"blocks": [{"index": 0, "language": "python", "start_line": 1, "end_line": 3, "closed": true, "content": "print('hi')", "fingerprint": "..."}], "unclosed_fences": [], "findings": []}}
```

**Limits:** Input limited to 100,000 characters.

---

### dotenv_validate

Validate .env-style key=value configuration text. Detects invalid keys, duplicate keys, missing quotes, and variable expansion syntax. Line-by-line parser, no shell evaluation.

**Arguments:**
- `text` (string): .env file content to validate
- `allow_export` (boolean, optional): Allow `export KEY=VALUE` syntax (default true)
- `key_pattern` (string, optional): Regex pattern keys must match (default `^[A-Za-z_][A-Za-z0-9_]*$`)
- `duplicate_policy` (string, optional): "warn", "error", or "allow" (default "warn")

**Tier:** 2
**Tags:** `validation`, `config`, `env`, `dotenv`

**Returns:**
- `parse_ok` (boolean): True if no parse errors found
- `entries` (array): Parsed entries with key, value, value_present, quote_style, line
- `duplicates` (array): Duplicate key entries with first_line, second_line
- `invalid_lines` (array): Lines that failed to parse with line number and reason
- `requires_quoting` (array): Keys whose unquoted values contain spaces
- `contains_expansion_syntax` (array): Keys with `${VAR}` or `$VAR` syntax
- `findings` (array): Human-readable findings

**Example:**
```json
{"name": "dotenv_validate", "arguments": {"text": "DB_HOST=localhost\nDB_PORT=5432\nexport API_KEY=secret"}}
// Returns: {"ok": true, "result": {"parse_ok": true, "entries": [{"key": "DB_HOST", "value": "localhost", ...}, ...], ...}}
```

---

### ini_validate

Validate simple INI-style configuration files. Supports [section] headers, key=value and key:value lines, ; and # comments. Detects duplicate sections, duplicate keys, and malformed lines.

**Arguments:**
- `text` (string): INI file content to validate
- `duplicate_policy` (string, optional): "warn", "error", or "allow" (default "warn")

**Tier:** 2
**Tags:** `validation`, `config`, `ini`

**Returns:**
- `parse_ok` (boolean): True if no parse errors found
- `sections` (array): Ordered list of section names
- `keys_by_section` (object): Keys grouped by section
- `duplicates` (array): Duplicate keys/sections with line numbers
- `invalid_lines` (array): Lines that failed to parse with line number and reason
- `findings` (array): Human-readable findings

**Example:**
```json
{"name": "ini_validate", "arguments": {"text": "[server]\nhost = localhost\nport = 8080\n\n[database]\nurl = postgres://localhost/mydb"}}
// Returns: {"ok": true, "result": {"parse_ok": true, "sections": ["server", "database"], "keys_by_section": {"server": ["host", "port"], "database": ["url"]}, ...}}
```

---

### patch_apply_check

Validate and simulate a unified diff against provided in-memory files/text without touching the filesystem. Reports parse status, application success, failed hunks with context, and optional result fingerprint.

**Arguments:**
- `original_text` (string): The original source text to apply the patch to
- `patch_text` (string): The unified diff patch text
- `strict` (boolean, optional): If True, context lines must match exactly (default true)
- `return_result_fingerprint` (boolean, optional): If True, compute SHA-256 of result (default true)
- `return_result_text` (boolean, optional): If True, include the resulting text, bounded to 50000 chars (default false)

**Tier:** 2
**Tags:** `patch`, `diff`, `unified`, `validation`, `apply`

**Returns:**
- `patch_parse_ok` (boolean): True if patch parsed successfully
- `applies` (boolean): True if all hunks applied cleanly
- `hunks_total` (integer): Total number of hunks in patch
- `hunks_applied` (integer): Number of hunks that applied successfully
- `hunks_failed` (integer): Number of hunks that failed to apply
- `failed_hunks` (array): Details of each failed hunk with expected/actual context and reason
- `affected_line_ranges` (array): Line ranges affected by successful hunks
- `newline_style_before` (string): Newline style in original text
- `newline_style_after` (string): Newline style in result text
- `result_fingerprint` (string): SHA-256 of the result text
- `result_text` (string|null): Resulting text if requested
- `findings` (array): Analysis notes and warnings

**Example:**
```json
{"name": "patch_apply_check", "arguments": {"original_text": "def hello():\n    print('hello')", "patch_text": "--- a/f.py\n+++ b/f.py\n@@ -1,2 +1,2 @@\n def hello():\n-    print('hello')\n+    print('world')\n"}}
// Returns: {"ok": true, "result": {"patch_parse_ok": true, "applies": true, "hunks_total": 1, "hunks_applied": 1, "hunks_failed": 0, ...}}
```

---

### patch_summary

Summarize a unified diff without applying it. Reports file counts, hunk counts, additions, deletions, renames, and line ranges by file.

**Arguments:**
- `patch_text` (string): The unified diff text to summarize

**Tier:** 2
**Tags:** `patch`, `diff`, `unified`, `summary`, `statistics`

**Returns:**
- `files_changed` (integer): Number of files changed
- `hunks_total` (integer): Total number of hunks across all files
- `additions` (integer): Total number of added lines
- `deletions` (integer): Total number of deleted lines
- `renames_detected` (array): Detected file renames with from/to
- `binary_patch_detected` (boolean): True if binary patch content detected
- `line_ranges_by_file` (object): Line ranges affected per file
- `findings` (array): Analysis notes and warnings

**Example:**
```json
{"name": "patch_summary", "arguments": {"patch_text": "--- a/f.py\n+++ b/f.py\n@@ -1,2 +1,2 @@\n def hello():\n-    print('hello')\n+    print('world')\n"}}
// Returns: {"ok": true, "result": {"files_changed": 1, "hunks_total": 1, "additions": 1, "deletions": 1, ...}}
```

---

### unicode_policy_check

Apply a named deterministic Unicode safety policy to input text. Policies are deterministic heuristics, not semantic security guarantees.

**Arguments:**
- `text` (string): Input text to check
- `policy` (string): One of `identifier_strict`, `filename_safe`, `source_code`, `human_text`, `json_key`, `domain_like`
- `normalization` (string, optional): Normalization form (defaults to policy-specific)

**Tier:** 2
**Tags:** `text`, `unicode`, `policy`, `security`, `validation`

**Policies:**

| Policy | Checks | Severity |
|--------|--------|----------|
| `identifier_strict` | Mixed scripts, bidi controls, zero-width chars, confusables, normalization instability, invisible chars | Error |
| `filename_safe` | Control chars, path separators, bidi controls, zero-width chars, reserved Windows names | Error |
| `source_code` | Bidi controls, zero-width chars, confusables | Error/Warning |
| `human_text` | Mixed scripts, bidi controls, zero-width chars, confusables | Warning only |
| `json_key` | Bidi controls, zero-width chars, control chars, confusables | Error/Warning |
| `domain_like` | Mixed scripts, confusables, bidi controls, zero-width chars | Error |

**Example:**
```json
{"name": "unicode_policy_check", "arguments": {"text": "hello\u0410", "policy": "identifier_strict"}}
// Returns: {"ok": true, "result": {"pass": false, "policy": "identifier_strict", "findings": [{"rule": "mixed_scripts", "severity": "error", "message": "Mixed scripts detected: Cyrillic, Latin"}], ...}}
```

---

### canonicalize_text

Apply a named text canonicalization profile. Profiles provide a single call to select common normalization sequences.

**Arguments:**
- `text` (string): Input text to canonicalize
- `profile` (string): One of `source_file_identity`, `identifier_compare`, `human_label_compare`, `json_key_compare`, `path_segment_compare`
- `return_mapping` (boolean, optional): If True, include character mapping of changes

**Tier:** 2
**Tags:** `text`, `unicode`, `canonicalization`, `normalization`, `identity`

**Profiles:**

| Profile | Operations |
|---------|------------|
| `source_file_identity` | NFC + LF newlines + strip trailing whitespace + ensure final newline |
| `identifier_compare` | NFC + casefold |
| `human_label_compare` | NFC + casefold + trim + collapse whitespace |
| `json_key_compare` | NFC + casefold |
| `path_segment_compare` | NFC + lowercase + LF newlines |

**Example:**
```json
{"name": "canonicalize_text", "arguments": {"text": "HELLO", "profile": "identifier_compare"}}
// Returns: {"ok": true, "result": {"text": "hello", "changed": true, "operations_applied": ["casefold"], "fingerprint_before": "...", "fingerprint_after": "..."}}
```

---

### prompt_input_inspect

Surface hidden or misleading content in user-pasted input, docs, or prompt-like text. Deterministic scanner for red flags that may influence agents or humans unexpectedly.

**Arguments:**
- `text` (string): Input text to inspect
- `checks` (array, optional): List of checks to perform. Defaults to all checks. Options: `unicode_hidden`, `bidi`, `html_comments`, `markdown_links`, `ansi_escapes`, `terminal_controls`, `base64_like_blobs`, `instruction_phrases`, `long_minified_lines`
- `phrase_patterns` (array, optional): Custom literal strings or safe regexes to flag as suspicious instruction phrases

**Tier:** 2
**Tags:** `text`, `security`, `inspection`, `prompt`, `hidden`

**Returns:**
- `ok`: Whether inspection succeeded
- `summary`: Human-readable summary of findings
- `risk_score`: Simple deterministic score (0-100, higher is riskier)
- `findings`: Array of FindingInfo with code, severity, message, span (byte/char/line positions), and details
- `recommended_next_tool`: Suggested follow-up tool based on findings

**Checks performed:**
| Check | What it detects |
|-------|----------------|
| `unicode_hidden` | Zero-width chars, BOM, invisible format chars |
| `bidi` | Bidirectional control characters |
| `html_comments` | HTML/XML comments that may hide content |
| `markdown_links` | Links where visible text differs from href |
| `ansi_escapes` | ANSI escape sequences (colors, cursor movement) |
| `terminal_controls` | Terminal control sequences |
| `base64_like_blobs` | Base64-encoded content >100 chars |
| `instruction_phrases` | Phrases like "disregard", "ignore previous" |
| `long_minified_lines` | Lines >500 chars that may hide content |

**Example:**
```json
{"name": "prompt_input_inspect", "arguments": {"text": "Hello <!-- hidden --> world", "checks": ["html_comments"]}}
// Returns: {"ok": true, "summary": "1 finding", "risk_score": 25, "findings": [{"code": "HTML_COMMENT", "severity": "warn", "message": "HTML comment found", "span": {"byte_start": 6, "byte_end": 23, "line": 1}}]}
```

**Note:** This is deterministic inspection, not semantic classification. It reports observable features only, not intent.

---

### text_security_inspect

Composite security text hygiene check. Combines prompt injection detection, hidden character inspection, and confusable analysis into a single call with a unified verdict and machine-readable codes.

**Arguments:**
- `text` (string): Text to inspect for security concerns

**Tier:** 1
**Tags:** `text`, `security`, `inspection`, `composite`

**Returns:**
- `verdict`: "safe", "warn", or "risk"
- `findings`: Array of Finding objects
- `machine_code`: Stable code summarizing the outcome
- `recommended_next_tool`: Suggested follow-up tool
- `summary`: Human-readable summary

**Example:**
```json
{"name": "text_security_inspect", "arguments": {"text": "Hello <!-- hidden --> world"}}
// Returns: {"ok": true, "result": {"verdict": "warn", "findings": [...], "summary": "1 finding"}}
```

**Note:** Composite tool — calls `prompt_input_inspect`, `text_inspect`, and `text_equal` internally.

---

### edit_preflight

Composite pre-edit validation. Check whether a text edit (string replacement, unified diff, or line-range replacement) would apply cleanly before modifying a file.

**Arguments:**
- `text` (string): Source text to edit
- `old` (string, optional): Text to find (for string replacement)
- `new` (string, optional): Replacement text (for string replacement)
- `patch_text` (string, optional): Unified diff patch (for patch mode)
- `start_line` (integer, optional): First line (for line_range mode)
- `end_line` (integer, optional): Last line inclusive (for line_range mode)
- `replacement` (string, optional): Replacement text (for line_range mode)
- `mode` (string): "replace", "patch", or "line_range"

**Tier:** 1
**Tags:** `text`, `edit`, `safety`, `composite`

**Returns:**
- `would_change`: Boolean
- `match_count`: Number of matches found
- `apply_ok`: Boolean (for patch mode)
- `findings`: Array of analysis notes
- `machine_code`: Stable code summarizing the outcome

**Example:**
```json
{"name": "edit_preflight", "arguments": {"text": "hello world", "old": "world", "new": "earth", "mode": "replace"}}
// Returns: {"ok": true, "result": {"would_change": true, "match_count": 1, "findings": []}}
```

**Note:** Composite tool — dispatches to `text_replace_check` or `patch_apply_check` based on mode.

---

### command_preflight

Composite command analysis before execution. Parse a shell command, detect risky lexical features, and report security findings.

**Arguments:**
- `command` (string): Shell command string to analyze

**Tier:** 1
**Tags:** `shell`, `security`, `preflight`, `composite`

**Returns:**
- `parse_ok`: Boolean
- `argv`: Parsed argument tokens
- `features`: Detected risky features
- `findings`: Array of analysis notes
- `machine_code`: Stable code summarizing the outcome

**Example:**
```json
{"name": "command_preflight", "arguments": {"command": "cargo test -- --nocapture"}}
// Returns: {"ok": true, "result": {"parse_ok": true, "argv": ["cargo", "test", "--", "--nocapture"], "features": {}, "findings": []}}
```

**Note:** Composite tool — calls `shell_split` and applies additional safety heuristics.

---

### config_preflight

Composite config validation with format auto-detect. Detects config format (TOML, JSON, .env, INI) and validates accordingly.

**Arguments:**
- `text` (string): Config text to validate
- `format` (string, optional): Force format — "toml", "json", "dotenv", "ini" (auto-detected if omitted)

**Tier:** 1
**Tags:** `config`, `validation`, `preflight`, `composite`

**Returns:**
- `detected_format`: Detected config format
- `valid`: Boolean
- `errors`: Array of validation errors
- `findings`: Array of analysis notes
- `machine_code`: Stable code summarizing the outcome

**Example:**
```json
{"name": "config_preflight", "arguments": {"text": "[package]\nname = \"demo\"\nversion = \"0.1.0\""}}
// Returns: {"ok": true, "result": {"detected_format": "toml", "valid": true, "errors": [], "findings": []}}
```

**Note:** Composite tool — dispatches to `validate_toml`, `validate_json`, `dotenv_validate`, or `ini_validate` based on format.

---

### structured_data_compare

Composite JSON comparison with shape analysis. Compare two JSON documents semantically and include structural shape information in the result.

**Arguments:**
- `a` (string): First JSON document
- `b` (string): Second JSON document
- `ignore_object_order` (boolean, optional): Sort object keys (default true)
- `include_shape` (boolean, optional): Include shape analysis (default true)

**Tier:** 2
**Tags:** `json`, `structured-data`, `comparison`, `composite`

**Returns:**
- `equal`: Boolean
- `diff_count`: Number of differences
- `diffs`: Array of diff objects
- `shape_a`: Shape of first document (if include_shape)
- `shape_b`: Shape of second document (if include_shape)
- `summary`: Human-readable summary
- `machine_code`: Stable code summarizing the outcome

**Example:**
```json
{"name": "structured_data_compare", "arguments": {"a": "{\"x\": 1}", "b": "{\"x\": 2}"}}
// Returns: {"ok": true, "result": {"equal": false, "diff_count": 1, "diffs": [...], "shape_a": {"x": "integer"}, "shape_b": {"x": "integer"}}}
```

**Note:** Composite tool — calls `json_compare` and `json_shape` internally.

---

## Resource Limits

Every MCP tool has explicit input and output bounds. The server enforces:

- **Request byte limit**: `MAX_REQUEST_BYTES` (default 1 MB) — rejects oversized JSON-RPC requests
- **Output byte limit**: `MAX_OUTPUT_BYTES` (default 1 MB) — truncates oversized tool responses
- **Per-tool timeout**: `MAX_TOOL_TIMEOUT_SECONDS` (default 30s) — cancels long-running tools
- **Worker count**: `MAX_TOOL_WORKERS` (default 16) — bounded thread pool
- **Rate limit**: `MAX_REQUESTS_PER_SECOND` (default 10) — token-bucket rate limiter
- **Spawned-process limit**: `MAX_CONCURRENT_SPAWNED` (4) — regex/math tools use subprocess isolation
- **Pairwise limit**: `MAX_PAIRWISE_ITEMS` (1,000) — caps O(N²) work in `identifier_inspect`, `identifier_table_inspect`, and `list_compare` (near-match mode)

Tool-level constants:

- `MAX_TEXT_LENGTH` = 100,000 (string inputs)
- `MAX_EXPRESSION_LENGTH` = 10,000 (math expressions)
- `MAX_LIST_ITEMS` = 10,000 (list inputs)
- Regex: `MAX_PATTERN_LENGTH_REGEX` = 1,000, `MAX_REGEX_SAMPLES` = 100, `MAX_MATCHES_REGEX` = 100, `REGEX_TIMEOUT_SECONDS` = 5

Already-running Python threads cannot be force-killed, so tool inputs are pre-bounded at the handler level. Pathological inputs return structured MCP errors (`input_too_large`, `timeout`, `internal_error`) rather than unbounded results.

For the complete per-tool audit, see [mcp_resource_limits.md](mcp_resource_limits.md).

## Security Considerations

The MCP server is designed for AI agent use with these security properties:

1. **No arbitrary code execution** - math_eval uses AST parsing, not eval()
2. **Input limits enforced** - Prevents DoS via large inputs
3. **Deterministic results** - Same input produces same output
4. **No external network calls** - Pure computation, no side effects
5. **Text inspection tools** - Help detect Unicode-based spoofing attacks
6. **Config trust boundary** - `eggcalc_config.py` is Python code loaded from the current working directory. Only run eggcalc in directories you trust. Set `EGGCALC_NO_CONFIG=1` to disable config loading entirely.

**For untrusted input handling:**
- Use `text_inspect` to check for hidden characters and confusables before storing user text
- Use `validate_json` to safely parse user-provided JSON
- Use `validate_brackets` to check expression syntax before evaluation
- Use `escape_text` to safely embed text in JSON, shell commands, or regex patterns

---

## See Also

- [Exact Module](exact.md) - Underlying text processing functions
- [Resource Limits](mcp_resource_limits.md) - Per-tool resource bounds audit
- [Security](security.md) - Security best practices
- [CLI](cli.md) - Command-line text tools (`calc inspect`, `calc count`, `calc regex`)
- [Agent Recipes](agent-recipes.md) - Suggested workflows for common tasks
