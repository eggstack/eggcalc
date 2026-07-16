# Release 2 Plan — MCP Protocol Conformance

Status: ready for implementation handoff  
Depends on: Release 1 semantic baseline  
Roadmap: `plans/001-correctness-protocol-hardening-roadmap.md`

## 1. Release objective

Replace the current largely stateless MCP request router with an explicit protocol session that correctly handles initialization, lifecycle state, request IDs, notifications, version negotiation, error codes, tool execution, cancellation, and schema validation.

The goal is not to add new MCP tools. The release should make the existing tool surface reliable for current MCP clients and safe for embedded or long-running use.

## 2. Protocol support policy

Before implementation begins, define the exact MCP protocol version or versions supported by this release.

Create one authoritative module-level definition, for example:

```python
SUPPORTED_PROTOCOL_VERSIONS = (...)
LATEST_SUPPORTED_PROTOCOL_VERSION = SUPPORTED_PROTOCOL_VERSIONS[-1]
```

Requirements:

- Do not hardcode the version independently in tests, documentation, and response handlers.
- `initialize` must inspect the client-requested protocol version.
- Return the requested version when supported.
- If the requested version is unsupported, follow the selected MCP specification’s compatibility rule and document the behavior.
- Add migration notes if older clients previously depended on the hardcoded `2024-11-05` response.

## 3. Target architecture

Introduce explicit objects instead of adding further global flags.

Suggested structure:

```text
McpServerConfig
McpSessionState
McpSession
McpToolRegistry
McpExecutor
```

For this release, it is acceptable to defer full executor/global-state isolation to Release 5, but lifecycle state and protocol behavior must be owned by `McpSession` now.

Suggested state enum:

```text
UNINITIALIZED
INITIALIZING
READY
CLOSED
```

Suggested session responsibilities:

- Negotiated protocol version.
- Client capability snapshot.
- Server capability snapshot.
- Lifecycle state.
- Request/notification classification.
- Cancellation records scoped to the session.
- Dispatch authorization by state.

The stdio `main()` function should construct one session per process/connection and pass every decoded message through it.

## 4. Workstream A — Lifecycle state machine

### A1. Define legal transitions

Required transitions:

```text
UNINITIALIZED --initialize request--> INITIALIZING
INITIALIZING --notifications/initialized--> READY
READY --EOF/shutdown/close--> CLOSED
```

Define explicit behavior for:

- Tool requests before initialization.
- Tool requests after `initialize` but before `notifications/initialized`.
- Repeated initialize requests.
- `notifications/initialized` before initialize.
- Messages after close.
- Ping behavior in each state.

Prefer deterministic protocol errors over permissive acceptance.

### A2. Enforce initialize-first behavior

Before initialization, reject methods that are not explicitly permitted by the selected protocol version.

The tests must no longer call `tools/list` or `tools/call` on a fresh implicit global server without first establishing a ready session. Provide test helpers that perform a valid handshake.

### A3. Record negotiated data

Store:

- Negotiated protocol version.
- Client info.
- Client capabilities.
- Optional implementation metadata needed for diagnostics.

Do not trust arbitrary nested capability data without request-size and nesting bounds already enforced by the outer input limits.

## 5. Workstream B — Request and notification semantics

### B1. Classify message type

A JSON-RPC message with a method and no `id` is a notification. A request requires a non-null string or integer `id`.

Requirements:

- Reject boolean IDs explicitly.
- Reject null IDs for requests.
- Enforce maximum ID length.
- Never generate a response for notifications, including unknown notifications and malformed notification parameters where the protocol requires silent handling.
- Continue returning parse errors for invalid JSON because no valid notification was decoded.

### B2. Normalize notification handling

Do not special-case only `notifications/initialized` and `notifications/cancelled` at the top-level router while responding to every other notification.

Create a notification dispatch path that always returns `None` to the transport layer.

Unknown notifications should be ignored or logged according to the protocol rather than receiving `Method not found` responses.

### B3. Cancellation semantics

Scope cancellation records to the session.

Required behavior:

- Accept valid cancellation notifications without response.
- Validate request ID type.
- Bound cancellation storage.
- Use deterministic FIFO eviction.
- Remove cancellation records once consumed or no longer relevant.
- Document that Python threads cannot be force-cancelled once running.
- Preserve process-child cleanup for tools that use subprocess isolation.

Add races covering cancellation before queueing, while queued, while running, and after completion.

## 6. Workstream C — JSON-RPC error taxonomy

Audit every return path and assign the correct category:

```text
-32700 Parse error
-32600 Invalid Request
-32601 Method not found
-32602 Invalid params
-32603 Internal error
```

Server-defined tool failures should use a documented server error or MCP tool-result error envelope consistently.

Required corrections include:

- Non-object decoded message -> invalid request.
- Missing/invalid `jsonrpc` -> invalid request.
- Missing/invalid method -> invalid request.
- Non-object `params` -> invalid params for a known method.
- Non-object tool `arguments` -> invalid params.
- Missing required tool arguments -> invalid params.
- Unknown top-level method -> method not found.
- Unknown tool name -> use the MCP-defined/tool-call error convention selected by the implementation and test it consistently.
- Handler exception -> sanitized server/tool execution error.

Centralize error construction helpers to prevent code drift.

## 7. Workstream D — Initialize and capabilities

### D1. Parse initialize params

Validate at minimum:

- `protocolVersion` type and length.
- `capabilities` object shape.
- `clientInfo` object shape and bounded strings.

Return:

- Negotiated protocol version.
- Server capabilities.
- Server implementation name and version.
- Any protocol-required instructions or metadata.

### D2. Advertise only implemented capabilities

Audit capability flags against actual behavior. Do not advertise list-change notifications, subscriptions, resources, prompts, logging, or other capability families that are not implemented.

Tool capability advertisement should match:

- `tools/list` implementation.
- Pagination behavior, if any.
- List-change behavior.
- Tool annotations/schema detail supported by the selected protocol.

### D3. Add handshake fixtures

Add complete raw sessions with exact expected output:

```text
initialize request
initialize response
notifications/initialized
ping request
ping response
tools/list request
tools/list response
```

Use fixture normalization only for fields that are intentionally variable, such as package version under test.

## 8. Workstream E — Schema-validation contract

The current validator implements only a subset of JSON Schema. This release must make that limitation explicit and mechanically enforced.

### E1. Define supported keywords

Create a constant set for supported input-schema keywords, covering only what the implementation validates.

Example families:

- `type`
- `enum`
- `const`
- `minimum`/`maximum`
- `exclusiveMinimum`/`exclusiveMaximum`
- `multipleOf`
- `minLength`/`maxLength`
- `pattern`
- `minItems`/`maxItems`
- `uniqueItems`
- `items`
- `properties`
- `required`
- `additionalProperties`

Decide whether `format` is unsupported or annotation-only. Do not silently imply validation.

### E2. Add recursive schema linting

Create a CI test that walks all `TOOL_SCHEMAS` and fails when an unsupported keyword appears.

This prevents future schemas from using `oneOf`, `anyOf`, `$ref`, or other ignored constructs without implementation support.

### E3. Validate defaults and handler signatures

Add consistency tests ensuring:

- Required schema properties match required handler parameters.
- Optional schema properties match defaults or accepted keyword arguments.
- No handler argument is inaccessible from its schema.
- Schema type expectations match wrapper validation.
- Profile-visible tools have schemas and handlers.

### E4. Bound validation complexity

Retain or improve:

- Maximum recursive depth.
- Maximum array lengths through schema constraints.
- Bounded `uniqueItems` comparisons.
- Bounded pattern length.
- Finite-number checks.

Add adversarial tests near each boundary.

## 9. Workstream F — Tool execution and timeout behavior

### F1. Preserve bounded worker behavior

Keep the bounded thread pool and configured maximum worker count.

Clarify that `ThreadPoolExecutor` bounds workers but its internal queue is not strictly bounded. If queue growth under sustained input is a concern, add an explicit submission semaphore or bounded pending-task counter.

Required metrics/tests:

- Maximum simultaneous workers.
- Maximum pending calls.
- Rejection/backpressure behavior when saturated.
- Timeout response latency.
- Cleanup after repeated timeouts.

### F2. Separate protocol timeout from handler cleanup

A timed-out call should return promptly while cleanup continues safely.

Ensure:

- Running futures are not awaited after timeout.
- Child processes are terminated and reaped.
- Orphan sets remain bounded.
- Completed timed-out tasks cannot write a second response.
- Executor shutdown is performed on normal server exit where practical.

### F3. Output serialization

Maintain output-size enforcement after JSON serialization.

Add tests for:

- Non-serializable handler output.
- Unicode byte-length boundaries.
- Exact-limit and limit-plus-one outputs.
- Error envelopes that themselves remain below the limit.

## 10. Workstream G — Test refactor and conformance suite

### G1. Introduce session-aware helpers

Create helpers such as:

```python
def ready_session() -> McpSession:
    ...

def request(session, method, params, request_id):
    ...
```

Do not let test order depend on a global `_mcp_defaults_configured` flag.

### G2. Correct existing tests

Remove tests that intentionally assert:

- A hardcoded old protocol version regardless of request.
- Null request IDs.
- IDs on notifications.
- `-32600` for invalid method params.
- Tool access before initialization.

Replace them with spec-grounded assertions.

### G3. Add full matrix

Cover:

- Supported and unsupported protocol versions.
- Valid and invalid client info.
- Every lifecycle state transition.
- Requests, responses, and notifications.
- Unknown request method versus unknown notification.
- Missing, null, boolean, oversized, integer, and string IDs.
- Invalid params for each supported method.
- Tool profile restrictions.
- Schema detail filters.
- Rate limits.
- Cancellation.
- Worker saturation and timeout.
- Request/output byte limits.
- Batch rejection.
- EOF and broken-pipe behavior.

### G4. Independent client verification

Run the stdio server against at least two external/current MCP clients or SDK harnesses in development/CI where feasible.

Record:

- Client versions.
- Negotiated protocol version.
- Initialization transcript.
- Tool listing success.
- Representative tool call success.
- Cancellation/timeout behavior where supported.

Do not add these clients as runtime dependencies.

## 11. Workstream H — Documentation and migration

Update:

- `README.md`
- `docs/mcp.md`
- `docs/mcp_resource_limits.md`
- `architecture/mcp.md`
- `AGENTS.md`
- Generated tool inventory
- `CHANGELOG.md`

Document:

- Supported protocol versions.
- Initialization requirements.
- Notification behavior.
- Error taxonomy.
- Schema subset.
- Profile selection.
- Resource limits.
- Cancellation limitations.
- Migration notes for callers that invoked `handle_request()` without a session/handshake.

## 12. Validation commands

Run at minimum:

```bash
python -m pytest tests/test_mcp_server.py -v
python -m pytest tests/test_mcp_resource_bounds.py -v
python -m pytest tests/ -v
ruff check eggcalc tests
black --check eggcalc tests
mypy eggcalc --ignore-missing-imports
python build_single.py
python scripts/generate_mcp_docs.py --check
python scripts/smoke_release_surfaces.py
```

Add an end-to-end stdin/stdout transcript test for both package and generated single-file server modes.

## 13. Acceptance criteria

Release 2 is complete when:

- Initialize negotiates a supported protocol version.
- Tool operations are rejected until the session reaches ready state.
- Requests require non-null string/integer IDs.
- Notifications never produce responses.
- Unknown notifications are handled without JSON-RPC responses.
- Invalid request and invalid params errors are distinguished.
- Schema support is explicit and all published schemas pass the subset linter.
- Cancellation and timeout state are bounded and session-scoped.
- Package and single-file MCP transcripts match.
- At least two independent MCP client/harness checks complete successfully.
- Full CI, generated docs, type checking, and release-surface tests pass.

## 14. Non-goals

Do not include:

- New tool categories.
- Full general-purpose JSON Schema 2020-12 implementation.
- Network MCP transports unless already required by project scope.
- Broad exact-tool semantic changes.
- Full global-state isolation beyond what is needed for session correctness; that remains Release 5.

## 15. Recommended commit sequence

1. Add session class and failing lifecycle tests.
2. Implement initialize negotiation and ready-state enforcement.
3. Refactor request/notification classification and ID validation.
4. Centralize JSON-RPC errors and correct error codes.
5. Add schema-subset constants and recursive schema linting.
6. Harden execution queue, timeout, cancellation, and serialization paths.
7. Add raw transcript and external-client conformance checks.
8. Update documentation, generated inventory, changelog, and release-surface verification.
