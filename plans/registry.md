# eggcalc Active Planning Registry

This file is the compact control surface for active interim planning. Detailed requirements and completed history remain in source roadmaps, implementation plans, `plans/closure/`, and Git history.

Canonical direction remains in:

- `plans/000-long-term-specification.md`
- `plans/001-terminology-and-domain-model.md`
- `plans/002-long-term-roadmap.md`
- `plans/003-planning-process.md`

Legacy flat plans (001–043 plus dated/phase files) are archived under `plans/archive/legacy/` and are not authoritative.

## Status vocabulary

- **proposed** — roadmap or plan exists but is not approved for execution.
- **ready** — dependencies and interfaces are satisfied; plan may be handed off.
- **active** — implementation or closure work is in progress.
- **blocked** — a named dependency or evidence requirement prevents progress.
- **closing** — implementation landed and closure evidence is being gathered.
- **closed** — closure record accepted.
- **conditionally closed** — substantial work landed, but a named correctness or operational evidence condition remains.
- **superseded** — replaced by another document.
- **archived** — no longer active and retained for traceability.

## Active subsystem roadmaps

| Subsystem | Status | Roadmap | Current milestone | Dependencies or blockers |
|---|---|---|---|---|
| calculator-core | active | `plans/subsystems/calculator-core-roadmap.md` | No open milestone; legacy evaluator/normalize/units work closed (see archive) | None; next milestone to be registered here before handoff |
| exact-utilities | active | `plans/subsystems/exact-utilities-roadmap.md` | No open milestone; legacy parity work closed (see archive) | None; next milestone to be registered here before handoff |
| mcp-server | active | `plans/subsystems/mcp-server-roadmap.md` | No open milestone; legacy dual-era/catalog work closed (see archive) | None; next milestone to be registered here before handoff |
| cli-distribution | active | `plans/subsystems/cli-distribution-roadmap.md` | No open milestone; legacy CLI/build work closed (see archive) | None; next milestone to be registered here before handoff |

## Dependency-ready implementation plans

| Subsystem | Milestone | Status | Implementation plan | Dependencies / handoff note |
|---|---|---|---|---|
| — | — | — | No dependency-ready plans yet. Register new milestones here before handoff. | — |

## Current execution order and dependency gates

**Phase 0 (this transition) gate:** legacy flat plans are moved to `plans/archive/legacy/`; canonical `000..003`, `adrs/`, `subsystems/`, `implementation/`, `closure/`, `archive/`, and this registry are the control surface. A milestone is dependency-ready only when every hard dependency is closed and every interface dependency has a stable written contract.

**Phase 1–5 gates:** per `plans/002-long-term-roadmap.md`. Phases 1 and 2 may overlap after Phase 0. Phase 4 (catalog/discovery) MUST follow Phase 3 (dual-era conformance). Phase 5 closes last.

## Blocked work

| Subsystem | Milestone | Blocker |
|---|---|---|
| — | — | No blocked milestones registered. |

## Closure work and current control points

| Subsystem | Status | Controlling evidence |
|---|---|---|
| planning transition | closing | This transition: canonical docs, subsystem roadmaps, archive move, registry, AGENTS pointer updates; verify with `make check`-scoped evidence per `plans/003-planning-process.md#12` |

Detailed historical milestone history is intentionally not duplicated here. Legacy evidence remains in `plans/archive/legacy/` and Git history.
