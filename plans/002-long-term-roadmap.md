# eggcalc Long-Term Implementation Roadmap

Status: execution roadmap for `plans/000-long-term-specification.md`

Terminology: `plans/001-terminology-and-domain-model.md`

This roadmap orders the work needed to reach the long-term eggcalc architecture while preserving a useful calculator, library, MCP server, and single-file distribution at every stage. Each phase MUST leave the repository in a coherent state and MUST include focused implementation plans, migrations where applicable, tests, documentation, and closure evidence before the next dependent phase is treated as available.

The roadmap is dependency-ordered, not calendar-ordered. Parallel work is appropriate only where the dependency notes allow it.

## Cross-phase execution rules

Every phase MUST:

1. preserve the stdlib-only, side-effect-free-import, and lazy-loading invariants;
2. preserve the two-evaluation-path contract and caret semantics;
3. use explicit evaluator/config/session/request scope rather than process-global mutation;
4. add typed protocol and schema representations before frontend-only state;
5. maintain backward-compatible behavior or document an intentional break with a deprecation policy;
6. add bounded snapshots, queues, caches, and events rather than unbounded payloads;
7. include timeout, cancellation, restart, duplicate-delivery, and contention tests where applicable;
8. include source provenance and diagnostics for loaded configuration or catalog metadata;
9. update architecture documentation, authority/mutable-state inventories, and static guards;
10. record explicit exit evidence in the implementation plan or closure record.

## Phase 0 — Canonical planning and identity foundation

### Objective

Introduce the planning language and typed identity relationships required by all later work without changing user behavior.

### Deliverables

- Adopt this planning system (`plans/000..003`, `adrs/`, `subsystems/`, `implementation/`, `closure/`, `archive/`, `registry.md`); move legacy flat plans to `plans/archive/legacy/` with history preserved.
- Formalize canonical names: evaluation paths, `UnitValue`/`Dimension`/`UnitSpec`, `TOOL_METADATA` vs `TOOL_SCHEMAS` vs `ToolRegistry`, protocol eras, profiles, `ModuleSpec` manifest entries.
- Mark `json_query`, module-level `handle_request()`, and PEP 562 re-exports as compatibility projections.
- Add architecture docs matching `plans/001-terminology-and-domain-model.md`.
- Add review guards preventing new `eggcalc`-relative imports that break the single-file build and new hand-edited derived registries.

### Dependencies

None beyond the current calculator/exact/MCP baseline.

### Exit criteria

- New production code distinguishes evaluation paths, catalog authorities, and protocol eras.
- No new runtime code lives outside core, `exact/`, or `mcp/`.
- Protocol DTOs carry era-appropriate versions while retaining legacy compatibility.
- Legacy flat plans are archived and no active plan cites them as authority.

### Required tests

- evaluation-path boundary tests (`evaluate` rejects NL/units; `evaluate_raw`/`run`/CLI accept them);
- `protocol_era()` round trips and single-authority guard;
- catalog-authority invariant (every visible profile tool resolves to one handler/schema/catalog entry);
- single-file manifest validation (`build_single.py --validate`).

## Phase 1 — Calculator-core semantic correctness

### Objective

Lock calculator semantics: normalization pipeline, safe AST evaluation, unit registry, and timeout/state isolation.

### Deliverables

- Normalize pipeline stability (number words, operators, functions, constants, unit preprocessing, XOR handling, validation caps).
- Evaluator function/constant catalog correctness with `UnitPolicy` enforcement.
- Unit registry correctness (150 `UnitSpec`, affine temperature, structural angle guards, compound expressions, power binding).
- Timeout/state parity (`evaluate_with_timeout`, semaphore bounds, orphan caps, per-instance isolation).

### Dependencies

Phase 0 identity. May proceed in parallel with Phase 2 after Phase 0.

### Exit criteria

- NL, unit, angle, temperature, power-binding, `%`/`//`, and `round()` contracts hold with regression tests.
- Replacing a canonical built-in drops it to dimensionless-only (tested).
- Timeout and multi-instance isolation behave deterministically.

### Required tests

- evaluator/normalize/units boundary matrices;
- angle/temperature/power/`%`/`//` semantics;
- DoS caps (length, nesting, exponent, factorial, shift, result size);
- timeout, concurrency, and `EggCalcApp` isolation suites.

## Phase 2 — exact/ utility parity and authority consolidation

### Objective

Complete the deterministic utility suite with single authorities and bounded, report-not-raise semantics.

### Deliverables

- Finish parity workstreams (network, encoding, temporal, and prior synthesis/validate/measure/diff coverage).
- Consolidate authorities: `json_extract()` for RFC 6901, `exact/version.py` for SemVer, `_Finding` vocabulary, `confusables` generation procedure.
- Preserve leaf-module independence (`network.py`, `encoding.py`, `temporal.py` stdlib-only, no `exact/` deps).
- Keep `__init__.py` fully lazy (`__all__ = list(_LAZY_IMPORTS)`).

### Dependencies

Phase 0. Phase 1 may proceed in parallel after Phase 0.

### Exit criteria

- Every public `exact/` function has bounded-input behavior and TypedDict field-vocabulary tests.
- No `exact/` module performs I/O, network, or LLM calls.
- Confusables data is reproducible from `scripts/generate_confusables.py`.

### Required tests

- per-module correctness plus limit/truncation tests;
- authority tests (RFC 6901 traversal, SemVer parsing/comparison);
- lazy-import test (`import eggcalc.cli` loads zero `exact.*`; `tools.py` imports `exact` lazily inside handlers).

## Phase 3 — MCP dual-era conformance and structured results

### Objective

Speak the current MCP protocol correctly in both eras with typed results.

### Deliverables

- Finalized `2026-07-28` support over stdio; `server/discover`; request-local modern metadata; explicit era classifier; legacy lifecycle preservation.
- `structuredContent` plus compatibility text; result/schema agreement validation; truthful annotations; deterministic ordering; conservative cache hints; concise shared server instructions.
- Repair stale protocol documentation (no "draft" language for the finalized revision).

### Dependencies

Phases 0–1 (evaluator/config ownership). Phase 2 SHOULD be stable so tool handlers rest on settled `exact/` behavior.

### Exit criteria

- Valid modern `tools/list`/`tools/call` require no legacy session; legacy handshake still works unchanged.
- Every supported modern response carries required metadata/cache fields.
- Declared `outputSchema` accepts the emitted structured result.
- One stdio process serves both eras without cross-era state leakage.

### Required tests

- modern/legacy transcript fixtures (literal JSON where practical);
- era classifier, unsupported-version error, method-allowlist, session-bleed tests;
- generated single-file MCP parity for both eras.

## Phase 4 — Tool catalog authority and agent discovery surface

### Objective

Make the 83-tool catalog maintainable and discoverable without deleting useful primitives.

### Deliverables

- One practical authority (`TOOL_METADATA`) with derived views; fixture reclassified as compatibility snapshot; catalog invariants and generated-doc checks.
- Deterministic stdlib lexical catalog search for harness use.
- Small recommended `agent_core` profile backed by evaluation evidence; `full` retained for compatibility.
- Provider-neutral tool-selection evaluation corpus with stdlib scoring/reporting (first-tool selection, path correctness, irrelevant/redundant/invalid calls, schema/context footprint).
- New composites only on held-out evidence.

### Dependencies

Phase 3 (protocol-correct representation comes before discovery optimization).

### Exit criteria

- Tool-name/handler/selection-metadata ownership is materially simpler.
- All 83 tools remain callable under an appropriate profile; `agent_core` is a strict subset of `full`.
- Catalog search is deterministic; evaluation reports pin the catalog/profile/schema-detail revision measured.

### Required tests

- registry invariants, profile-subset tests, ordering stability;
- evaluation corpus replay and footprint measurement;
- generated-inventory drift check (`scripts/generate_mcp_docs.py --check`).

## Phase 5 — CLI, distribution, and operational hardening

### Objective

Keep the CLI result-only, the single file portable, and releases manual and safe.

### Deliverables

- CLI dispatch correctness (mode classification before config loading; 9 text commands; `--explain`/`--commands`/`--capabilities`/`--mcp` behavior).
- `build_single.py` manifest validation and assembly transforms; `install.py` atomic install; wheel/sdist/single-file smoke (`make package-check`).
- Manual Twine release procedure; CI runs `make check` then `make package-check` (never publishes).
- Footprint budgets (artifact size, startup imports, worker/queue/timeout bounds) with measurements.

### Dependencies

Phases 0–4 for behavior that distribution must preserve.

### Exit criteria

- `make check` and `make package-check` pass on Ubuntu/Python 3.11; compatibility workflow covers Windows/macOS and Python 3.14.
- CLI output stays result-only including REPL.
- Single-file behavior matches package behavior for calculator, exact/, and MCP paths.

### Required tests

- CLI transcript tests (expression/REPL/text-command/`--explain`/`--commands` modes);
- build-manifest validation, no-`eggcalc`-import test, generated-file parity;
- packaging smoke (twine check + wheel/single-file).

## Recommended immediate execution sequence

```text
Phase 0  canonical planning and identity foundation (this transition)
Phase 1  calculator-core semantic correctness
Phase 2  exact/ utility parity and authority consolidation
Phase 3  MCP dual-era conformance and structured results
Phase 4  catalog authority and agent discovery surface
Phase 5  CLI, distribution, and operational hardening
```

Phases 1 and 2 may overlap after Phase 0. Phase 4 MUST follow Phase 3. Phase 5 runs continuously but closes last.

## Roadmap governance

Implementation plans derived from this roadmap SHOULD cite the exact phase and specification sections they satisfy. A phase is not complete because code exists; it is complete only when its ownership model, migrations, protocol, tests, documentation, failure semantics, and closure evidence are present.

When implementation reveals that a term or ownership boundary is wrong, update the terminology document and long-term specification first (via an ADR when cross-subsystem), then adjust the roadmap. Avoid accumulating incompatible local meanings in phase plans.

New scope SHOULD be evaluated against the non-goals in the specification. Features that do not strengthen calculation correctness, deterministic text analysis, MCP conformance, agent discoverability, or distribution portability SHOULD not displace the roadmap's core work.
