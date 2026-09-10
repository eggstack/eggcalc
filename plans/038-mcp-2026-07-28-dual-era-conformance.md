# MCP 2026-07-28 Dual-Era Conformance

Status: planned  
Repository: `eggstack/eggcalc`  
Baseline reviewed: `dcd0c5eb427c28712e6fffb75b58b78c8a935494`  
Date: 2026-09-10  
Parent roadmap: `plans/037-mcp-protocol-and-agent-surface-roadmap.md`

## 1. Goal

Add support for the finalized MCP `2026-07-28` protocol revision over eggcalc's existing stdio transport while preserving the legacy handshake behavior required by `2025-11-25` and `2024-11-05` clients.

The important architectural change is that MCP now has two protocol eras:

- legacy/handshake era: `initialize` -> `notifications/initialized` -> READY session;
- modern/stateless era: no initialize handshake and no protocol-level session; each request carries its own protocol version and client capability envelope and may be preceded by `server/discover`.

Eggcalc should represent that distinction explicitly rather than attempting to force modern requests through the existing `McpSession` state machine.

This plan is deliberately stdio-only. HTTP routing headers, OAuth, transport authorization, and remote deployment are out of scope.

## 2. Specification basis

Use the finalized release and current Tier-1 SDK behavior as implementation references:

- https://blog.modelcontextprotocol.io/posts/2026-07-28/
- https://ts.sdk.modelcontextprotocol.io/v2/protocol-versions
- https://ts.sdk.modelcontextprotocol.io/v2/migration/support-2026-07-28

Relevant requirements for eggcalc:

1. `2026-07-28` is finalized.
2. The modern era does not use `initialize`, `notifications/initialized`, or `Mcp-Session-Id`.
3. `server/discover` is the modern discovery/bootstrap RPC and a server supporting the modern era must implement it.
4. Modern requests carry reserved `_meta` values including `io.modelcontextprotocol/protocolVersion` and `io.modelcontextprotocol/clientCapabilities`; `clientInfo` is optional/SHOULD rather than mandatory.
5. Modern responses should carry server identity in `_meta["io.modelcontextprotocol/serverInfo"]`.
6. Modern list/discovery results use the current cache-hint shape. For this plan, conservative `ttlMs = 0` and `cacheScope = "private"` are acceptable; later work may choose a useful nonzero policy once the catalog representation is stable.
7. A modern request advertising an unsupported protocol revision must fail with the current protocol's unsupported-version error semantics rather than being silently interpreted as a legacy call.
8. Methods removed from the modern era must not be accidentally accepted merely because legacy handlers still exist.

Before implementation, verify the exact final wire schemas/error codes against the current specification/schema package. SDK migration pages are useful cross-checks but must not override the final protocol schema.

## 3. Current repository state

### 3.1 Protocol authority

`eggcalc/_protocol.py` is already the single authority for supported versions, currently:

```python
SUPPORTED_PROTOCOL_VERSIONS = ("2024-11-05", "2025-11-25")
LATEST_SUPPORTED_PROTOCOL_VERSION = SUPPORTED_PROTOCOL_VERSIONS[-1]
```

Keep that authority model. Do not reintroduce protocol-version tuples in `server.py` or `capabilities.py`.

### 3.2 Legacy lifecycle

`McpSession` currently owns the negotiated legacy version, client info/capabilities, cancellation records, and state transitions. `_check_ready_for_dispatch()` rejects ordinary methods unless state is READY. This is correct for the supported legacy revisions and must remain covered.

`McpServer.handle_request()` currently routes through a session, and `main()` creates one UNINITIALIZED session for the stdio connection. That cannot remain the universal dispatch path once modern requests are accepted.

### 3.3 Existing state isolation

The server already captures an immutable `RuntimeContext` before dispatch and owns an isolated evaluator, `ToolRegistry`, `ToolExecutor`, and configuration snapshot. Modern stateless MCP does not require deleting those server-owned structures. "Stateless" means the protocol request does not depend on a hidden protocol session; server process state/configuration can remain explicit and immutable as it is today.

## 4. Design constraints

- Standard library only.
- Preserve legacy behavior and public `McpSession` APIs.
- Preserve module-level compatibility `handle_request()` behavior unless a narrowly documented change is unavoidable.
- No new transport.
- Do not model modern calls by constructing fake READY legacy sessions.
- Do not store modern client capabilities/identity in mutable process-global state.
- Do not make per-client modern behavior depend on the previous request from the same stdio process.
- Keep request-local metadata bounded and defensively validated.
- Keep server configuration/profile/evaluator ownership exactly as explicit as it is now.
- Do not add MRTR, Tasks, subscriptions, sampling, roots, prompts, resources, or logging merely because the new protocol revision defines or deprecates them.
- Do not advertise `2026-07-28` until the implementation path satisfies the wire obligations exercised by eggcalc's supported methods.

## 5. Workstream A — explicit protocol-era model

### 5.1 Extend `_protocol.py`

Add the modern revision to the authoritative version set and define the minimum additional helpers needed to classify behavior without duplicating string comparisons throughout `server.py`.

A small model is preferred, for example:

```python
LEGACY_PROTOCOL_VERSIONS = ("2024-11-05", "2025-11-25")
MODERN_PROTOCOL_VERSIONS = ("2026-07-28",)
SUPPORTED_PROTOCOL_VERSIONS = LEGACY_PROTOCOL_VERSIONS + MODERN_PROTOCOL_VERSIONS
LATEST_SUPPORTED_PROTOCOL_VERSION = SUPPORTED_PROTOCOL_VERSIONS[-1]
```

An enum is acceptable if it simplifies tests/dispatch, but do not add a general protocol negotiation framework.

The key invariant is behavioral: version -> era must have one authority.

### 5.2 Add a request-local modern metadata representation

Use a small frozen dataclass or equivalent immutable structure in `mcp/server.py`, e.g. `ModernRequestContext`, containing only request-scoped information needed by eggcalc:

- protocol version;
- client capabilities;
- optional validated client info;
- optionally the raw bounded `_meta` mapping if needed for forward-compatible ignored keys.

Do not copy arbitrary unbounded nested metadata without applying the existing request-size boundary.

### 5.3 One classifier

Add one helper that decides whether an incoming request is:

- modern (`2026-07-28` metadata envelope present and valid enough to classify);
- legacy (normal initialize/session-era traffic);
- malformed/unsupported modern traffic.

Do not infer modern mode from method names alone. `server/discover` is a modern signal only when accompanied by the protocol metadata required by the final schema.

An explicitly unsupported modern protocol version must not fall through into the legacy state machine.

## 6. Workstream B — `server/discover`

Implement the modern discovery method on the server-owned dispatch path.

The result should be generated from existing authorities, not new copies:

- supported protocol versions from `_protocol.py` / server config;
- server capabilities from the same capability construction used by initialize where applicable;
- server identity from `__version__` and the static eggcalc implementation identity;
- concise server instructions from the shared instruction authority introduced/finalized under Plan 039;
- required conservative cache fields for the modern wire shape.

Do not expose Python/runtime internals as protocol capabilities merely because `detect_capabilities()` returns them for eggcalc diagnostics. Distinguish MCP protocol capabilities from eggcalc runtime diagnostic information if the current initialize response has conflated them.

If the final `DiscoverResult` schema places server identity in response `_meta` rather than the main result body, follow that exact shape.

`server/discover` must be callable without an initialized legacy session.

## 7. Workstream C — modern stateless dispatch

### 7.1 Server-owned dispatch path

Add a direct server method/helper for modern requests. A preferred boundary is conceptually:

```text
validate JSON-RPC envelope
  -> classify protocol era
      -> legacy: existing McpSession lifecycle/dispatch
      -> modern: validate request-local metadata -> server-owned method dispatch
```

Do not route modern calls through `McpSession.handle_message()` merely to reuse the switch statement. Extract/share the smallest method-dispatch mechanism if necessary.

### 7.2 Runtime context capture

Capture `McpServer.runtime_context` once before modern tool admission, just as the current server does for session-backed calls. Configuration updates must remain atomic and a modern request must see one evaluator/config generation from validation through execution.

### 7.3 Modern `tools/list`

Reuse the existing registry/profile/schema-detail implementation, but return the wire fields required by the modern revision. In this plan:

- preserve current filtering behavior for eggcalc-aware callers;
- make tool ordering explicitly deterministic (prefer canonical name order rather than relying only on dict insertion order);
- include required conservative cache hints (`ttlMs: 0`, `cacheScope: "private"`) until Plan 039 centralizes cache policy;
- ensure every emitted tool definition is valid for the modern schema.

### 7.4 Modern `tools/call`

Reuse the same `ToolExecutor` and profile authority. Do not duplicate handler execution.

The modern path must not consult legacy session cancellation sets or negotiated client state. Pass only request-local context and server-owned immutable state.

At minimum, ensure tool results on the modern path can satisfy declared `outputSchema`/`structuredContent` obligations. If the full result-boundary refactor in Plan 039 has not yet landed, implement the narrow compatibility bridge necessary so Plan 038 never advertises a protocol revision that produces known-invalid tool responses. Plan 039 remains responsible for centralizing and exhaustively validating this behavior across both eras.

### 7.5 Modern method validity

Define a small allowlist/table or explicit conditional for methods eggcalc actually supports in the modern era. At minimum this includes the final-spec forms of:

- `server/discover`;
- `tools/list`;
- `tools/call`.

Do not automatically inherit legacy-only methods/notifications. In particular, `initialize` and `notifications/initialized` are legacy lifecycle messages and must not become valid modern requests.

Keep `ping` only if the final modern specification still permits it; current SDK guidance says liveness `ping` is not defined for the modern era, so verify and gate it by era rather than assuming the legacy implementation applies.

## 8. Workstream D — legacy preservation

The legacy path should remain byte/behavior compatible unless the final protocol specification requires a correction that is also valid for the older revisions.

Preserve tests for:

- initialize parameter validation;
- supported/unsupported requested legacy versions;
- initialization acknowledgement;
- pre-READY rejection;
- duplicate initialize rejection;
- cancellation record behavior;
- session ownership/isolation;
- module-level compatibility `handle_request()`;
- server close/session close semantics.

Do not convert the entire server to stateless mode and then emulate the old lifecycle. The existing session implementation is valuable compatibility code and should remain isolated to the era that needs it.

## 9. Workstream E — stdio main loop era coexistence

The stdio entry point must be able to serve either era without an environment flag or a second executable.

Preferred behavior:

- parse each JSON-RPC request using the existing size/rate/error boundary;
- modern request -> modern direct dispatch;
- legacy request -> the connection's existing `McpSession` path;
- a modern request must not mutate the legacy session state;
- a legacy initialize must not change how a later explicitly modern request is interpreted;
- malformed cross-era traffic receives a deterministic protocol error.

Because the modern protocol is request-self-describing, do not introduce an implicit "once modern, always modern" mutable connection flag unless the final stdio specification explicitly requires that behavior.

## 10. Workstream F — protocol-response metadata

For every modern response emitted by eggcalc's supported methods:

- attach server identity in the final-spec `_meta` location;
- do not attach modern-only metadata to legacy responses unless permitted and useful;
- ensure error responses follow the final revision's requirements for identity/metadata where applicable;
- avoid using self-reported client/server identity for authorization or behavior changes.

Factor a small response-finalization helper if needed so this is not duplicated across discover/list/call/error code paths.

## 11. Workstream G — documentation and authority repair

Update at least:

```text
eggcalc/_protocol.py
eggcalc/mcp/server.py
eggcalc/mcp/__init__.py              # only if public exports change
docs/mcp.md
architecture/mcp.md
architecture/authority_inventory.md
architecture/capabilities.md         # if protocol/runtime capability distinction changes
AGENTS.md / AGENTS.override.md        # only where current operational guidance is stale
```

Remove the statement that `2026-07-28` is a draft.

Document the two-era model once in detail and link to it from secondary architecture docs rather than repeating the lifecycle matrix in many files.

## 12. Tests

Add focused modern protocol tests rather than expanding every legacy test parametrically.

Required modern cases include:

- `server/discover` succeeds without initialize;
- discover returns `2026-07-28` and any retained legacy revisions in deterministic order;
- discover contains required capabilities/instructions/cache fields/response metadata according to the final schema;
- modern `tools/list` succeeds without a `McpSession`;
- modern `tools/call(math_eval)` succeeds without a `McpSession`;
- modern request missing protocol-version metadata is rejected when it otherwise claims the modern era;
- modern request missing required client-capability metadata is rejected;
- optional missing clientInfo remains accepted if final spec says SHOULD rather than MUST;
- malformed clientInfo is rejected or ignored exactly as the final schema requires;
- unsupported future modern version receives the spec-defined unsupported-version error and supported-version evidence;
- `initialize` is rejected/not-found when sent as an explicitly modern request;
- legacy initialize still works unchanged;
- modern and legacy requests can coexist in one stdio process without state bleed;
- server configuration generation capture is stable during modern queued execution;
- profile restrictions apply identically to modern and legacy tool calls;
- output-size and timeout error behavior remains valid in both eras;
- generated single-file MCP supports both era transcripts.

Where practical, encode request/response fixtures as literal JSON transcript cases. They are easier to compare with official SDK behavior than deeply mocked unit tests.

## 13. Interoperability verification

In addition to unit tests, verify at least one modern and one legacy transcript against a current official MCP client/inspector outside production dependencies.

Do not add the official SDK to eggcalc runtime dependencies. Acceptable approaches include:

- a CI/dev-only ephemeral command using a published MCP inspector/SDK;
- checked-in captured transcript fixtures generated by an external interoperability run;
- a documented manual verification command.

The authoritative automated suite must still be runnable with eggcalc's existing development environment.

## 14. Acceptance criteria

Plan 038 is complete when:

1. `eggcalc/_protocol.py` is the sole version/era authority and includes finalized `2026-07-28`.
2. Legacy and modern protocol eras have explicit, testable dispatch semantics.
3. `server/discover` is implemented according to the final modern wire schema.
4. A valid `2026-07-28` `tools/list` request does not require initialize/session state.
5. A valid `2026-07-28` `tools/call` request does not require initialize/session state.
6. Modern requests derive all client context from request-local metadata and do not persist it globally.
7. Every supported modern response carries required modern metadata/cache fields.
8. The modern tool-call path emits at least the structured-result compatibility necessary for declared output schemas; Plan 039 may subsequently centralize/strengthen validation.
9. `2025-11-25` and `2024-11-05` legacy lifecycle tests remain green.
10. One stdio server process can handle both eras without cross-era state leakage.
11. No HTTP transport or external MCP SDK is added to production.
12. Generated single-file parity includes modern and legacy MCP transcripts.
13. Documentation no longer calls the finalized revision a draft.
14. No runtime dependency is added.
15. Focused MCP tests, `make check`, and package/single-file validation pass.

## 15. Verification commands

At minimum, run the repository's canonical equivalents of:

```bash
python -m pytest tests/test_mcp_server.py tests/test_build_single.py -v
python build_single.py --validate
python scripts/generate_mcp_docs.py --check
make check
make package-check
```

Add a narrowly named modern-protocol test module if `test_mcp_server.py` would otherwise become more difficult to navigate.

## 16. Non-goals

Do not use this plan to:

- remove legacy MCP support;
- remove `McpSession`;
- add Streamable HTTP;
- add OAuth/authorization;
- add MCP Apps, Tasks, resources, prompts, subscriptions, roots, sampling, elicitation, or logging;
- change the tool catalog/profile strategy beyond what modern wire conformance requires;
- introduce dynamic tool discovery;
- restructure evaluator/configuration internals;
- change tool semantics;
- add provider SDKs;
- make server identity a security principal.

This pass should end with one stdio server that cleanly speaks both MCP eras, using shared tool execution and configuration authorities but distinct lifecycle semantics.