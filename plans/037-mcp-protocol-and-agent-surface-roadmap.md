# MCP Protocol and Agent Surface Roadmap

Status: implementation complete; agent-surface recommendation remains gated by held-out evidence
Repository: `eggstack/eggcalc`  
Baseline reviewed: `dcd0c5eb427c28712e6fffb75b58b78c8a935494`  
Date: 2026-09-10  
Depends on: completed surface/authority work through Plans 033-036

## 1. Purpose

The current repository is functionally broad, standard-library-only, and well defended by behavioral/invariant tests. The remaining MCP problem is not primarily missing functionality or duplicated implementation. It is the interaction between a large 83-tool public catalog, protocol drift since the finalized MCP `2026-07-28` revision, duplicated tool-definition bookkeeping, and the absence of an empirical agent tool-selection evaluation loop.

This roadmap brings eggcalc's MCP surface current and makes the full tool set easier for agents to discover without deleting useful primitives or replacing them with a few oversized multi-action tools.

The desired end state is:

- support both the legacy handshake MCP era and finalized `2026-07-28` stateless MCP requests over the existing stdio transport;
- return protocol-correct structured tool results while retaining text compatibility content;
- publish accurate tool annotations, deterministic/cacheable list responses where the negotiated protocol supports them, and concise server instructions;
- reduce tool-definition change amplification and eliminate ambiguity over which registry/fixture is authoritative;
- keep every existing tool directly callable under an appropriate profile;
- provide a small candidate agent-facing profile, promoted to recommended only
  when held-out evidence supports it, while preserving `full` for
  compatibility and expert/harness use;
- make specialist tools searchable/discoverable using deterministic stdlib-only catalog metadata, without pretending that a proprietary search RPC is standardized MCP progressive discovery;
- evaluate tool-selection quality and context footprint before and after exposure changes;
- retain zero production runtime dependencies and generated single-file parity.

## 2. Research basis

This roadmap is based on the finalized MCP `2026-07-28` release and the August 2026 MCP roadmap, not the earlier release-candidate assumptions currently described in `docs/mcp.md`.

Primary protocol references:

- MCP `2026-07-28` release: https://blog.modelcontextprotocol.io/posts/2026-07-28/
- MCP August 2026 roadmap: https://blog.modelcontextprotocol.io/posts/mcp-roadmap/
- MCP TypeScript SDK protocol-era guidance: https://ts.sdk.modelcontextprotocol.io/v2/protocol-versions
- MCP TypeScript SDK `2026-07-28` migration guidance: https://ts.sdk.modelcontextprotocol.io/v2/migration/support-2026-07-28
- MCP tool schema/annotation reference: https://modelcontextprotocol.io/specification/2025-11-25/schema

Agent-tool design references:

- Anthropic, "Introducing advanced tool use": https://www.anthropic.com/engineering/advanced-tool-use
- Anthropic, "Writing effective tools for AI agents": https://www.anthropic.com/engineering/writing-tools-for-agents

Relevant conclusions from those sources:

1. `2026-07-28` is finalized and creates a new stateless protocol era. The `initialize` / `notifications/initialized` lifecycle is not used in that era. Each modern request carries protocol/client capability metadata, and `server/discover` is the bootstrap/discovery RPC.
2. Modern list/read results are designed to be deterministic and cacheable and carry cache hints.
3. Structured tool output is part of the MCP contract when an `outputSchema` is declared; `2026-07-28` broadens tool schemas/results to full JSON Schema 2020-12 / arbitrary conforming JSON values.
4. Current MCP tool annotations provide `readOnlyHint`, `destructiveHint`, `idempotentHint`, and `openWorldHint`. Their defaults are intentionally pessimistic when omitted.
5. The MCP maintainers explicitly identify hundred-tool catalogs as a model-context and tool-selection problem and are beginning a standardized progressive-discovery effort. That effort is not yet a stable protocol primitive eggcalc should depend on.
6. Anthropic's deferred tool loading experiments report materially lower tool-schema context use and better large-catalog tool-selection accuracy. Their broader tool-design guidance recommends realistic agent evaluations, clear functional boundaries, concise high-signal responses, and measuring tool calls/errors/tokens rather than optimizing descriptions by intuition alone.

## 3. Current repository findings driving this roadmap

### 3.1 Protocol drift

`eggcalc/_protocol.py` currently supports:

```text
2024-11-05
2025-11-25
```

`docs/mcp.md` still calls `2025-11-25` the latest stable revision and calls `2026-07-28` a draft. That statement is now stale.

The current server architecture is explicitly session/handshake-oriented. `McpSession` gates normal requests on the `READY` state and `main()` creates one uninitialized session for stdio. This must remain available for legacy clients, but it cannot be the only protocol path after modern support lands.

### 3.2 Structured-result gap

Tool definitions declare `outputSchema` broadly, but the executor currently serializes handler dictionaries to JSON text inside `result.content`. The modernized server should emit the corresponding MCP `structuredContent` representation and retain the text block for compatibility.

### 3.3 Large default discovery surface

The repository has 83 registered tools. `tools/list` already supports useful eggcalc-specific filters (`tier`, `tags`, `names`, `profile`, `schema_detail`), and schemas support compact/normal/full representations. However, a generic MCP client calling ordinary `tools/list` receives the configured profile. `McpServerConfig` currently defaults to `profile="full"` and `schema_detail="full"` for compatibility, so the broad catalog remains the default path.

This means the existing filtering machinery is useful to aware harnesses but does not by itself solve generic agent context pollution.

### 3.4 Tool-definition authority/change amplification

Current tool knowledge is distributed across:

- `eggcalc/mcp/schemas.py::TOOL_SCHEMAS`;
- `eggcalc/mcp/schemas.py::TOOL_METADATA`;
- `eggcalc/mcp/server.py::TOOL_HANDLERS`;
- `tests/fixtures/mcp_tool_registry_expected.json`;
- generated `docs/tool_inventory.md`.

The runtime and tests detect drift, which protects correctness, but changes still require several coordinated edits. The generated inventory currently calls the fixture the "source of truth" while architecture documentation describes the runtime registries as authoritative. The fixture should be treated as an explicit compatibility snapshot/golden contract, not an independent implementation authority.

### 3.5 Missing agent-selection evidence

The repository has strong function/tool correctness coverage. It does not currently have a provider-neutral corpus that measures whether an agent presented with the catalog selects appropriate tools, how many irrelevant calls it makes, or how much schema context each exposure strategy consumes.

This is the key missing evidence for deciding whether new composite/front-door tools are worth adding.

## 4. Non-negotiable constraints

All work under this roadmap must preserve:

- Python standard library only for production runtime; `dependencies = []` remains true;
- existing calculator, Python API, CLI, MCP server, exact utilities, and generated single-file distribution;
- all 83 existing tool names remain callable unless an already-deprecated compatibility tool follows a separately documented deprecation policy;
- `full` remains available for backward compatibility;
- legacy MCP handshake behavior remains supported while modern support is added;
- stdio remains the production MCP transport for this line of work; do not add HTTP merely because modern MCP supports HTTP-native routing;
- no external MCP SDK dependency;
- no embeddings/vector database/search service for tool discovery;
- no generic plugin framework, dependency-injection framework, or metaclass/decorator registration system;
- no giant `action`/`operation` mega-tool that hides unrelated domains behind one schema;
- no broad module splitting solely to reduce line counts;
- no provider SDK or required API key in the normal test suite;
- no default-profile breaking change until compatibility impact is explicitly evaluated.

## 5. Workstream structure

### Plan 038 — Modern MCP `2026-07-28` dual-era conformance

File: `plans/038-mcp-2026-07-28-dual-era-conformance.md`

Scope:

- add `2026-07-28` to the authoritative protocol-version model;
- distinguish legacy handshake requests from modern stateless requests explicitly;
- implement `server/discover`;
- validate required modern per-request `_meta` fields without requiring legacy session state;
- preserve legacy `initialize` / initialized-session semantics for older protocol revisions;
- keep stdio as the transport;
- add modern/legacy transcript tests and generated-single-file parity;
- repair stale MCP protocol documentation.

Primary objective: protocol correctness without throwing away legacy compatibility.

### Plan 039 — Structured tool results and protocol metadata

File: `plans/039-mcp-structured-results-annotations-and-cache-hints.md`

Scope:

- return `structuredContent` for tools that declare `outputSchema` while retaining JSON text content for compatibility;
- validate result/schema agreement at the protocol boundary;
- emit existing MCP tool annotations accurately;
- make tool-list ordering explicitly deterministic;
- emit modern cache hints conservatively;
- add concise static server instructions shared by legacy initialize and modern discovery where protocol-appropriate;
- avoid introducing tasks, prompts/resources, HTTP, or other unrelated MCP features.

Primary objective: make the existing tools clean, typed MCP citizens before optimizing discovery.

### Plan 040 — Tool catalog authority and maintenance consolidation

File: `plans/040-mcp-tool-catalog-authority-consolidation.md`

Scope:

- establish one practical authority for tool names, selection metadata, and handler binding while keeping protocol schemas separately reviewable;
- derive compatibility views rather than maintaining redundant full inventories;
- remove duplicated tier ownership between schema and metadata where possible;
- reclassify the fixture as a generated/explicit compatibility snapshot rather than an implementation authority;
- keep `ToolRegistry` as the immutable runtime facade;
- add catalog invariants and generated-doc checks;
- avoid a large framework or source-code generation system.

Primary objective: reduce change amplification without a risky wholesale schema rewrite.

### Plan 041 — Agent discovery surface and evaluation-driven consolidation

File: `plans/041-agent-tool-discovery-and-selection-evaluation.md`

Scope:

- create a realistic provider-neutral tool-selection evaluation corpus and stdlib scoring/reporting path;
- measure current `full/full`, current compact/profile modes, and proposed small-agent exposure strategies;
- add selection-specific catalog metadata (`selection_summary`, keywords/synonyms) only where evaluations justify it;
- add deterministic stdlib lexical catalog search for harness use;
- introduce a small recommended `agent_core` profile, but keep `full` available and avoid silently changing compatibility defaults in the first pass;
- use existing composite tools as primary entry points where evaluations support them;
- add new front-door composites such as manifest/network inspection only if held-out evaluation evidence shows a real selection/call-efficiency improvement;
- prepare catalog metadata for future standardized MCP progressive discovery without inventing a private replacement for that standard.

Primary objective: reduce model-visible context and selection ambiguity while retaining the entire callable toolbox.

## 6. Implementation order

Implement Plans 038, 039, 040, and 041 in that order.

Plan 038 lands first because protocol-era semantics affect every subsequent MCP response and test fixture.

Plan 039 lands second because discovery work should optimize a protocol-correct tool representation, not perpetuate text-only result behavior or pessimistic missing annotations.

Plan 040 lands third because it establishes the maintainable catalog authority needed for selection metadata and future progressive-discovery adaptation.

Plan 041 lands last because exposure/profile changes should be driven by measured agent behavior against the finalized catalog representation.

Each plan must be independently reviewable and leave `main` green.

## 7. Acceptance criteria

The roadmap is complete when:

1. `_protocol.py` recognizes finalized `2026-07-28` and the server supports both modern stateless and legacy handshake-era clients over stdio.
2. `server/discover` returns the required modern discovery information and normal modern tool calls do not require a legacy `McpSession` READY state.
3. Legacy `2025-11-25` and `2024-11-05` behavior remains covered by transcript tests.
4. Tools with `outputSchema` return conforming `structuredContent` plus compatibility text content.
5. Tool annotations truthfully reflect eggcalc's read-only, deterministic, closed-world MCP behavior.
6. Modern list/discovery results have deterministic ordering and protocol-correct cache fields.
7. Tool-name/handler/selection-metadata ownership is materially simpler and the fixture is no longer described as a competing implementation source of truth.
8. All 83 existing tool names remain directly callable through an appropriate profile.
9. A recommended small agent-facing profile exists and its membership is backed by evaluation evidence rather than tier labels alone.
10. A deterministic catalog-search function can rank specialist tools from natural-language intent without external dependencies; it remains a harness/library mechanism unless a standardized MCP discovery primitive or separately justified compatibility adapter is available.
11. A checked-in evaluation corpus/reporting path measures at least first-tool selection, eventual tool-path correctness, irrelevant/redundant calls, invalid-argument calls, and initial schema/context footprint.
12. New composite/front-door tools are added only when measured benefits justify their extra public surface.
13. Generated single-file behavior remains equivalent for supported MCP eras and tool responses.
14. No runtime dependency is added.
15. Canonical verification (`make check`, package/single-file checks, focused MCP protocol tests) passes after the final implementation.

## 8. Verification philosophy

Prefer protocol transcript tests, registry invariants, deterministic size measurements, and replayable evaluation fixtures over additional framework code.

Important invariants include:

- every incoming MCP request is classified into exactly one supported protocol era;
- modern requests never accidentally depend on session-only state;
- legacy requests do not receive modern-only response fields unless allowed by their revision;
- `structuredContent` and compatibility JSON text encode the same logical result;
- declared `outputSchema` accepts the emitted structured result;
- tool-list ordering is stable for an immutable registry/profile/filter tuple;
- compatibility fixture names equal the intended public catalog snapshot but do not construct runtime behavior;
- every visible profile tool resolves to exactly one handler/schema/catalog entry;
- `agent_core` is a strict subset of `full`;
- specialist tools excluded from `agent_core` remain callable when explicitly exposed through another profile;
- catalog search is deterministic for identical metadata/query input;
- evaluation reports identify the exact catalog/profile/schema-detail revision they measured.

## 9. Explicit non-goals

This roadmap does not authorize:

- deleting specialist tools to hit a target tool count;
- collapsing unrelated tools into a universal `utility(operation=...)` interface;
- renaming all existing tools for aesthetic consistency;
- adding an embedding model or semantic-search dependency;
- adding a networked registry service;
- implementing HTTP transport, OAuth, MCP Apps, Tasks, prompts/resources, sampling, elicitation, roots, or subscriptions unless a separate product requirement exists;
- adopting an external MCP SDK;
- implementing the MCP roadmap's not-yet-final progressive-discovery design speculatively;
- adding provider-specific LLM SDK dependencies to production or required CI;
- changing the default profile from `full` until compatibility consequences are explicitly assessed;
- broad evaluator/normalizer/unit refactoring unrelated to MCP tool representation;
- reopening completed Plans 033-036 except for documentation/status corrections required by this work.

The line of work should end once eggcalc speaks the current MCP protocol correctly, exposes typed/high-signal tool definitions, has one maintainable catalog authority, and can demonstrate with evaluations that agents see a smaller useful surface without losing access to the full toolbox.
