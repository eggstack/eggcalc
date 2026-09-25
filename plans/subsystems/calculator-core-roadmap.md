# Calculator-Core Roadmap

Status: active

Long-term references:

- `plans/000-long-term-specification.md#9`
- `plans/001-terminology-and-domain-model.md#3`
- `plans/002-long-term-roadmap.md#1`

Related ADRs:

- `plans/adrs/ADR-0001-adopt-codegg-planning-conventions.md`

## 1. Purpose and ownership boundary

Owns natural-language normalization, safe AST evaluation, unit registry/conversion, subprocess mechanics, protocol-version constants, and capability detection: `units.py`, `evaluator.py`, `normalize.py`, `_process.py`, `_protocol.py`, `capabilities.py` (plus `__init__.py` public surface for these paths).

Consumes: nothing inside the repo (units is a leaf; evaluator consumes units).

Must not own: `exact/` implementations, MCP schemas/tools/server, CLI dispatch, build assembly.

## 2. Work classification

### Invariants

- Two-evaluation-path contract and caret semantics (`evaluate` XOR vs `evaluate_raw`/CLI exponentiation).
- Safe AST evaluation (never `eval()`); token whitelist and DoS caps.
- Structural angle-algebra rejection; affine temperature math; power-binding and `%`/`//` semantics.
- Canonical `round()` overloads; `UnitPolicy` enforcement while canonical callables are active.
- `r`/`R` is the gas constant, not Rankine.

### Capabilities

- NL math (`"five plus three"`), unit-aware evaluation (`"30m + 100ft in meters"`), `--explain` traces.
- `evaluate*` family and `EggCalcApp` per-instance semantics.

### Infrastructure

- `NORMALIZE`/`PATTERNS` rebuild locks, evaluator caches (global LRU 1,024 / 64 MB), timeout child-process semaphore (4 spawns, 256 orphans), memory/variable caps (1,000 each).

### Polish

- Error-message quality, trace readability, footprint budgets for normalization tables.

## 3. Non-goals

- New unit categories or function catalog expansion without a roadmap milestone.
- CAS/computer-algebra features.
- MCP/CLI/distribution changes except through their subsystem interfaces.

## 4. Current state

Legacy hardening complete and archived under `plans/archive/legacy/`: `001-correctness-protocol-hardening-roadmap.md` with `002/003/004` capability passes and `005-releases-1-3-correctness-closure-pass.md`; releases 4–6 runtime/compatibility/isolation work (`006..019`); footprint/simplification line (`020..028`, notably `023`, `024`, `026`, `027`, `028`); surface consolidation (`033..036`). Repository evidence: 55 constants, 104 functions, 11-member `UnitPolicy`, 150 `UnitSpec` entries across 17 categories, enforced caps in `evaluator.py`.

## 5. Target architecture

Unchanged module boundaries with locked semantics above; every future semantic change arrives as a bounded milestone with regression guards and closure evidence.

## 6. Dependency graph

```text
M001 calculator semantic lock (closed, legacy)
    |
    +--> M002 timeout/state parity (closed, legacy)
    |
    `--> M003 future semantic change (proposed; hard depends on M001+M002 staying green)
```

M003 has a hard dependency on the Phase 0 planning foundation (this transition).

## 7. Milestones

### Milestone 1 — Calculator semantic lock

Class: invariant + capability

Objective: NL/unit/angle/temperature/power semantics hold with regression coverage.

Dependencies: none (historical).

Deliverable boundary: evaluator/normalize/units behavior plus tests and docs.

User or operator value: correct calculation from CLI, library, and single file.

Exit conditions: legacy closure passes green (archived). Deferred work: none.

### Milestone 2 — Timeout and state parity

Class: infrastructure

Objective: timeout, cache, and multi-instance isolation behave deterministically.

Dependencies: Milestone 1 (hard).

Deliverable boundary: `evaluate_with_timeout`, semaphore/orphan bounds, `EggCalcApp` isolation.

User or operator value: safe embedding and concurrent use.

Exit conditions: legacy closure passes green (archived). Deferred work: none.

### Milestone 3 — Future semantic change (template)

Class: tbd (invariant | capability | infrastructure | polish)

Objective: (to be defined by the next implementation plan).

Dependencies: Milestones 1–2 staying green (hard); planning foundation (hard).

Deliverable boundary: tbd. User or operator value: tbd.

Exit conditions: tbd with requirement-to-evidence matrix. Deferred work: tbd.

## 8. Cross-cutting requirements

### Storage and migration

In-memory caches only; no schema migrations. Cache-cap changes need footprint evidence.

### Protocol and compatibility

Calculator semantics feed MCP/CLI; breaking semantic changes require a deprecation note and cross-subsystem review.

### Security and authorization

AST whitelist, input/nesting caps, exponent/factorial/shift/result caps; no `eval()`.

### Concurrency, cancellation, and recovery

Timeout children, semaphore bounds, orphan reaping, per-instance isolation.

### Observability and audit

`trace_normalization()` parity with the pipeline; capability snapshots stay diagnostic-only.

### Performance and resource use

Direct `evaluate()` stays the fast path; `evaluate_raw()` cost documented, not regressed silently.

### Documentation and operations

`architecture/evaluator.md`, `architecture/normalize.md`, `architecture/units.md`, authority/mutable-state inventories stay in sync.

## 9. Verification strategy

Subsystem suites: evaluator/normalize/units boundary matrices, angle/temperature/power/`%`/`//`/`round()` semantics, DoS-cap tests, timeout/concurrency/isolation suites, plus `build_single.py --validate` for manifest impact.

## 10. Risks and decision points

Future semantic changes (new functions, units, or dimension rules) may need an ADR when they cross MCP/exact/CLI contracts. None open.

## 11. Completion definition

This roadmap closes when calculator semantics, timeout/state parity, and observability hold with current closure evidence and no open corrective passes. It stays active while the product evolves.

## 12. Milestone status

| Milestone | Status | Implementation plan | Closure record | Blockers |
|---|---|---|---|---|
| 1 semantic lock | closed (legacy) | `plans/archive/legacy/002-release-1-calculator-semantic-correctness.md` etc. | `plans/archive/legacy/005-releases-1-3-correctness-closure-pass.md` etc. | — |
| 2 timeout/state parity | closed (legacy) | `plans/archive/legacy/007-release-5-state-isolation-and-concurrency-hardening.md`, `plans/archive/legacy/024-unit-aware-function-contracts-and-timeout-state-parity.md` | archived closures | — |
| 3 future change | not started | — | — | needs a registered `implementation/calculator-core/NNN-*.md` plan |
