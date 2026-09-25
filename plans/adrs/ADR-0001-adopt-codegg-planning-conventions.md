# ADR-0001: Adopt codegg Planning Conventions for eggcalc

Status: accepted

Date: 2026-09-25

Decision owners: project maintainers

Related specification sections:

- `plans/000-long-term-specification.md#5`
- `plans/001-terminology-and-domain-model.md#7`
- `plans/002-long-term-roadmap.md#0`
- `plans/003-planning-process.md`

Affected subsystem roadmaps:

- `plans/subsystems/calculator-core-roadmap.md`
- `plans/subsystems/exact-utilities-roadmap.md`
- `plans/subsystems/mcp-server-roadmap.md`
- `plans/subsystems/cli-distribution-roadmap.md`

## Context

eggcalc planning lived as ~59 flat files directly under `plans/` (`001..043` plus dated `2026-07-06-*`, `phase_*`, `next_pass_*`, `release-polish-*`, `stdlib_*`). Roadmap, implementation, closure, and corrective passes were interleaved with ad-hoc `Status:` headers, no registry, no ADR lane, no work classification, and no dependency vocabulary. `AGENTS.md` treated `plans/*.md` as archived records, not policy.

codegg (`/home/sugarwookie/projects/codegg`, `https://github.com/dbowm91/codegg`) uses a hierarchical system: canonical `000..003` long-term docs, `adrs/`, `subsystems/`, `implementation/<subsystem>/`, `closure/<subsystem>/`, `archive/`, and a compact `registry.md`, with mandatory invariant/capability/infrastructure/polish classification, hard/interface/soft/operational dependencies, bounded handoff milestones, corrective-pass discipline, and a 10-point planning review.

eggcalc needs the same separation (durable direction vs. transient handoffs) without importing codegg's daemon/distributed content.

## Decision drivers

- Preserve history while ending flat-plan sprawl.
- Give agents one authoritative direction (canonical docs + ADRs + subsystem roadmaps) instead of 59 competing files.
- Make closure evidence (requirement-to-evidence matrix, verification commands, residual findings) mandatory.
- Keep eggcalc constraints explicit in the process (evaluation paths, stdlib-only, lazy imports, single-file manifest, generated docs, result-only CLI).
- Keep the transition reviewable and reversible via `git mv`.

## Considered options

### Option A — Keep flat plans, add a registry only

Add `registry.md` pointing at existing flat files. Minimal churn, but preserves ad-hoc statuses, mixed roadmap/closure content, date-encoded filenames, and no ADR lane. Rejected: does not fix authority ambiguity.

### Option B — Adopt codegg hierarchy verbatim, including daemon phases

Copy codegg's `000..003` content and subsystem list (project catalog, coordinator/leaf, presence, work orders). Rejected: wrong domain; eggcalc has no daemon, nodes, or team authorization.

### Option C — Adopt codegg structure with eggcalc domain content (selected)

Keep codegg's document classes, templates, lifecycle, classification, dependency model, sizing, handoff, corrective, review, and anti-pattern machinery; rewrite the domain content for eggcalc (calculator-core, exact-utilities, mcp-server, cli-distribution; evaluation paths; catalog/era authorities; stdlib-only/build constraints).

## Decision

Adopt Option C:

1. Canonical `plans/000-long-term-specification.md`, `plans/001-terminology-and-domain-model.md`, `plans/002-long-term-roadmap.md`, `plans/003-planning-process.md` (eggcalc domain, normative).
2. `plans/adrs/`, `plans/subsystems/`, `plans/implementation/<subsystem>/`, `plans/closure/<subsystem>/`, `plans/archive/`, `plans/registry.md`, `plans/README.md` per codegg roles and naming (stable subsystem names above; no dates unless time-bound).
3. Move all pre-adoption flat plans verbatim to `plans/archive/legacy/` via `git mv`; they are historical evidence, not authority.
4. Four initial subsystem roadmaps (calculator-core, exact-utilities, mcp-server, cli-distribution) recording legacy work as closed history and leaving future milestones proposed/ready.
5. Update `AGENTS.md` / `AGENTS.override.md` planning pointers and `architecture/overview.md` Deep Dive Index to the new control surface.

## Consequences

### Positive

- One authority order: canonical spec/terminology -> ADRs -> subsystem roadmap -> milestone plan -> repo evidence.
- Bounded agent handoffs with acceptance/stop/closure-evidence sections.
- Corrective passes become new plans referencing originals instead of silent rewrites.
- Registry stays compact; history stays traceable under `archive/`.

### Negative

- Legacy `plans/001..043` links in `docs/release_*_evidence.md` must be retargeted to `plans/archive/legacy/`.
- Contributors must learn the heavier template for new milestones.

### Neutral or deferred

- No production code change in this ADR.
- Future ADRs will record durable technical decisions (evaluation paths, catalog authority, dual-era model) as needed; this ADR records only the planning-adoption decision.

## Compatibility and migration

Docs change only. Historical plan filenames preserved under `archive/legacy/`. Inbound links from `docs/release_4_evidence.md`, `docs/release_5_evidence.md`, `docs/release_6_evidence.md` updated to the archived paths. No API, protocol, packaging, or storage migration.

## Security and reliability implications

None directly. Indirect benefit: explicit invariant review and stop conditions reduce the chance of safety-relevant regressions slipping through undocumented plans.

## Verification

- `plans/README.md`, `000..003`, `registry.md`, `adrs/README.md`, `subsystems/*-roadmap.md`, `implementation/README.md`, `closure/README.md`, `archive/README.md` exist.
- `plans/archive/legacy/` contains the moved flat plans with history preserved (`git log --follow` works).
- No active document cites `plans/archive/legacy/*` as authority.
- `python3 scripts/generate_mcp_docs.py --check` and `python3 build_single.py --validate` pass (docs-only change must not break them).

## Supersession

None.
