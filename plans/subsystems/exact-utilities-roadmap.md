# exact-Utilities Roadmap

Status: active

Long-term references:

- `plans/000-long-term-specification.md#9`
- `plans/001-terminology-and-domain-model.md#4`
- `plans/002-long-term-roadmap.md#2`

Related ADRs:

- `plans/adrs/ADR-0001-adopt-codegg-planning-conventions.md`

## 1. Purpose and ownership boundary

Owns the deterministic text/Unicode utility package: 28 `exact/` modules plus the fully-lazy `__init__.py` (`__all__ = list(_LAZY_IMPORTS)`).

Consumes: calculator-core only for MCP handler bridging (handlers import `exact/` lazily); leaf modules (`network.py`, `encoding.py`, `temporal.py`) consume nothing in `exact/`.

Must not own: evaluator semantics, MCP protocol/profile decisions, CLI dispatch, build assembly.

## 2. Work classification

### Invariants

- Purity: no network, filesystem, or LLM calls; `path_tools.py` lexical only.
- Bounded inputs per module; findings reported, not raised.
- TypedDict field vocabulary (`code`/`severity`/`message`/`line`/`column`); `result["equal"]` access.
- Single authorities: `json_extract()` for RFC 6901, `exact/version.py` for SemVer.
- `confusables.py` generated (edit `scripts/generate_confusables.py`, never the data file).
- Leaves stay dependency-free.

### Capabilities

- Deterministic analyses: bytes/codepoints/normalization, scripts/confusables, measure, diff, validate, synthesis composites, transforms, identifiers, positions, globs, configs, patches, paths, prompt-inspection, markdown, shell, policies, cargo/manifests/repo, network/encoding/temporal, LLM hygiene.

### Infrastructure

- `_LAZY_IMPORTS` authority, lazy `__init__`, per-module caps, shared `_Finding` TypedDict.

### Polish

- Message quality, finding-code consistency, performance of hot paths (confusables decode, diff).

## 3. Non-goals

- Semantic search, embeddings, or networked registries for utilities.
- Broad module splitting solely to reduce line counts.
- New MCP tools except through the mcp-server subsystem.

## 4. Current state

Legacy parity complete and archived: `029-eggsact-deterministic-utility-parity-roadmap.md` with `030-network-and-encoding-utility-parity.md`, `031-temporal-and-cron-utility-parity.md`, `032-utility-parity-integration-and-closure.md`. Repository evidence: 28 modules, leaf independence, lazy exports (213 names), bounded caps (100k/500k/200k chars, 10k items, 200 findings).

## 5. Target architecture

Same 28-module shape with locked authorities; new utilities arrive as bounded milestones with per-module tests and vocabulary conformance.

## 6. Dependency graph

```text
M001 parity foundation (closed, legacy)
    |
    +--> M002 network/encoding (closed, legacy)
    |
    +--> M003 temporal/cron (closed, legacy)
    |
    `--> M004 integration/closure (closed, legacy)
              |
              `--> M005 future utility (proposed)
```

## 7. Milestones

### Milestone 1 — Parity foundation

Class: capability + invariant

Objective: deterministic utility coverage with single authorities.

Dependencies: none (historical). Deliverable boundary: `exact/` modules plus tests/docs. User value: agent-facing text analysis primitives. Exit conditions: archived closures green.

### Milestone 2 — Network and encoding parity

Class: capability. Objective: IP/CIDR inspection and codec/radix conversion with strict validation. Dependencies: M001 (hard). Status: closed (legacy `030`).

### Milestone 3 — Temporal and cron parity

Class: capability. Objective: fixed-offset datetime and cron inspection with corrected DOM/DOW semantics. Dependencies: M001 (hard). Status: closed (legacy `031`).

### Milestone 4 — Integration and closure

Class: infrastructure + polish. Objective: cross-module consistency, vocabulary conformance, lazy-export coverage. Dependencies: M002+M003 (hard). Status: closed (legacy `032`).

### Milestone 5 — Future utility (template)

Class: tbd. Objective: tbd. Dependencies: M001–M004 staying green (hard). Exit conditions: tbd.

## 8. Cross-cutting requirements

### Storage and migration

No durable storage; stateless pure functions.

### Protocol and compatibility

Field-vocab changes require MCP schema/handler review (soft dependency on mcp-server).

### Security and authorization

Bounded inputs, path containment within declared roots, no script execution on discovery.

### Concurrency, cancellation, and recovery

Stateless; thread-safe by construction; no shared mutable state.

### Observability and audit

Deterministic outputs; truncation notices where findings are capped.

### Performance and resource use

Lazy decode for confusables; documented caps; no silent footprint growth.

### Documentation and operations

Per-module `architecture/*.md` docs plus `architecture/exact.md` stay in sync.

## 9. Verification strategy

Per-module correctness plus limit/truncation tests, authority tests, lazy-import tests, vocabulary conformance checks.

## 10. Risks and decision points

New utility domains may need an ADR when they create new authorities or cross MCP contracts. None open.

## 11. Completion definition

Roadmap closes when parity, authorities, laziness, and vocabulary hold with current closure evidence and no open corrective passes. Stays active while utilities evolve.

## 12. Milestone status

| Milestone | Status | Implementation plan | Closure record | Blockers |
|---|---|---|---|---|
| 1 foundation | closed (legacy) | `plans/archive/legacy/029-eggsact-deterministic-utility-parity-roadmap.md` | `plans/archive/legacy/032-utility-parity-integration-and-closure.md` | — |
| 2 network/encoding | closed (legacy) | `plans/archive/legacy/030-network-and-encoding-utility-parity.md` | archived | — |
| 3 temporal/cron | closed (legacy) | `plans/archive/legacy/031-temporal-and-cron-utility-parity.md` | archived | — |
| 4 integration | closed (legacy) | `plans/archive/legacy/032-utility-parity-integration-and-closure.md` | archived | — |
| 5 future utility | not started | — | — | needs `implementation/exact-utilities/NNN-*.md` |
