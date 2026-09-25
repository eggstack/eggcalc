# MCP-Server Roadmap

Status: active

Long-term references:

- `plans/000-long-term-specification.md#10`
- `plans/001-terminology-and-domain-model.md#5`
- `plans/002-long-term-roadmap.md#3`
- `plans/002-long-term-roadmap.md#4`

Related ADRs:

- `plans/adrs/ADR-0001-adopt-codegg-planning-conventions.md`

## 1. Purpose and ownership boundary

Owns the stdio JSON-RPC server, protocol-era model, tool schemas/catalog, handlers, sessions, profiles, and MCP conformance: `mcp/schemas.py`, `mcp/tools.py`, `mcp/server.py`, `_protocol.py` (era mapping), plus MCP docs and fixtures.

Consumes: calculator-core (evaluator) and exact-utilities (via lazy per-handler imports).

Must not own: evaluator semantics, `exact/` implementations, CLI dispatch, build assembly.

## 2. Work classification

### Invariants

- `protocol_era()` is the sole version-to-era authority.
- `TOOL_METADATA` is the catalog authority; `TOOL_HANDLERS`/`TOOL_PROFILES` derived, never hand-edited.
- Modern requests never depend on legacy session state; legacy keeps handshake semantics.
- `structuredContent` and text encode the same result; `outputSchema` covers the inner `result`.
- All 83 tools callable under an appropriate profile; `agent_core` strict subset of `full`.
- Deterministic `tools/list` ordering; bounded request/output, workers, timeouts, rate limits.
- Server-owned `Evaluator` per `McpServer`; never the module-global evaluator.

### Capabilities

- Dual-era discovery and calls (`server/discover`, `tools/list`, `tools/call`); 12 profiles; lexical catalog search; evaluation corpus for tool selection.

### Infrastructure

- `ToolRegistry`/`ToolExecutor` pools, `ConfigManager` atomic snapshots, `ModernRequestContext`, response-finalization helpers.

### Polish

- Annotation accuracy, cache-hint policy, server-instruction concision, discovery ergonomics.

## 3. Non-goals

- HTTP transport, OAuth, MCP Apps/Tasks/prompts/resources/sampling/elicitation/roots/subscriptions without a separate requirement.
- Embedding/semantic search, mega-tools, plugin frameworks, external MCP SDKs.
- Deleting specialist tools to hit a count; renaming for aesthetics.

## 4. Current state

Legacy work complete and archived: `037-mcp-protocol-and-agent-surface-roadmap.md` with `038-dual-era-conformance`, `039-structured-results-annotations-cache-hints`, `040-catalog-authority-consolidation`, `041-discovery-selection-evaluation`, plus `042-closure-pass` and `043-corrective-experimental-pass`. Repository evidence: dual-era dispatch, `server/discover`, `structuredContent` boundary, derived handlers, 12 profiles, transcript fixtures, generated-inventory drift check.

## 5. Target architecture

Same three-module shape with locked authorities; future exposure changes driven by evaluation evidence, not tier labels alone.

## 6. Dependency graph

```text
M001 dual-era conformance (closed, legacy 038)
    |
    +--> M002 structured results (closed, legacy 039)
    |
    +--> M003 catalog authority (closed, legacy 040)
    |
    `--> M004 discovery/evaluation (closed, legacy 041/042/043)
              |
              `--> M005 future exposure change (proposed; hard on M001-M004 green + held-out evidence)
```

## 7. Milestones

### Milestone 1 — Dual-era conformance

Class: invariant + capability. Objective: modern stateless + legacy handshake over stdio. Dependencies: calculator-core isolation (hard). Status: closed (legacy `038`).

### Milestone 2 — Structured results and metadata

Class: invariant + polish. Objective: typed results, annotations, ordering, cache hints, instructions. Dependencies: M001 (hard). Status: closed (legacy `039`).

### Milestone 3 — Catalog authority consolidation

Class: infrastructure. Objective: one practical authority with derived views; fixture as snapshot. Dependencies: M002 (hard). Status: closed (legacy `040`).

### Milestone 4 — Discovery surface and evaluation

Class: capability + infrastructure. Objective: lexical search, `agent_core` profile, selection corpus with footprint evidence. Dependencies: M003 (hard). Status: closed (legacy `041`/`042`, experimental corrective `043`).

### Milestone 5 — Future exposure change (template)

Class: tbd. Objective: tbd, only on held-out evidence. Dependencies: M001–M004 green (hard) + evaluation evidence (interface). Exit conditions: tbd.

## 8. Cross-cutting requirements

### Storage and migration

No DB; immutable snapshots and bounded queues. Profile/catalog changes need compatibility review.

### Protocol and compatibility

Era allowlists explicit; legacy responses never gain modern-only fields unless allowed; unsupported versions fail deterministically.

### Security and authorization

Schema+signature validation, timeouts, bounded pools, size caps, rate limits, redaction; `ping` gated by era.

### Concurrency, cancellation, and recovery

Worker reservation state machine; session cancellation sets (legacy only); request-local context (modern); atomic config generation capture.

### Observability and audit

Transcript fixtures, registry invariants, size measurements, evaluation reports pinning catalog/profile/schema-detail revisions.

### Performance and resource use

Schema-detail modes (compact/normal/full); context-footprint measurement before/after exposure changes.

### Documentation and operations

`architecture/mcp.md`, `docs/mcp.md`, `docs/tool_inventory.md` (generated), authority inventory stay in sync.

## 9. Verification strategy

Transcript tests per era, classifier/allowlist/bleed tests, result/schema agreement, profile-subset and ordering invariants, single-file MCP parity, inspector/SDK interop captures (dev-only, never a runtime dep).

## 10. Risks and decision points

Progressive-discovery standardization is not yet stable; eggcalc MUST NOT invent a private replacement. Future exposure changes need an ADR when they alter profile contracts. None open.

## 11. Completion definition

Roadmap closes when dual-era conformance, typed results, catalog authority, and evidence-backed discovery hold with current closure evidence and no open corrective passes. Stays active while MCP evolves.

## 12. Milestone status

| Milestone | Status | Implementation plan | Closure record | Blockers |
|---|---|---|---|---|
| 1 dual-era | closed (legacy) | `plans/archive/legacy/038-mcp-2026-07-28-dual-era-conformance.md` | archived (`042` family) | — |
| 2 structured | closed (legacy) | `plans/archive/legacy/039-mcp-structured-results-annotations-and-cache-hints.md` | archived | — |
| 3 catalog | closed (legacy) | `plans/archive/legacy/040-mcp-tool-catalog-authority-consolidation.md` | archived | — |
| 4 discovery | closed (legacy) | `plans/archive/legacy/041-agent-tool-discovery-and-selection-evaluation.md` | `plans/archive/legacy/042-mcp-agent-surface-closure-pass.md` | — |
| 5 future exposure | not started | — | — | needs `implementation/mcp-server/NNN-*.md` + held-out evidence |
