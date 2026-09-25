# CLI-Distribution Roadmap

Status: active

Long-term references:

- `plans/000-long-term-specification.md#8`
- `plans/000-long-term-specification.md#11`
- `plans/000-long-term-specification.md#12`
- `plans/001-terminology-and-domain-model.md#6`
- `plans/002-long-term-roadmap.md#5`

Related ADRs:

- `plans/adrs/ADR-0001-adopt-codegg-planning-conventions.md`

## 1. Purpose and ownership boundary

Owns CLI dispatch, entry points, capability reporting, single-file assembly, installation, packaging, and release verification: `cli.py`, `__main__.py` (thin entry), `capabilities.py`, `build_single.py`, `install.py`, `pyproject.toml` packaging, completions, `calc.sh`.

Consumes: calculator-core, exact-utilities (lazy per-command via `importlib`), mcp-server (only for `--mcp`).

Must not own: evaluation semantics, `exact/` implementations, MCP protocol decisions.

## 2. Work classification

### Invariants

- CLI output is result-only (REPL included).
- Mode classification before cwd-local config loading; `--help`/`--version`/`--capabilities`/`--mcp`/text commands never execute `eggcalc_config.py`.
- `import eggcalc.cli` loads zero `exact.*` modules.
- Runtime code lives only in core, `exact/`, or `mcp/`; imports in top-level multi-line parenthesized blocks; never `(`/`)` in comments inside such blocks; never reference `normalize_main` in source/tests.
- Python `>=3.11`; stdlib-only production runtime.
- `docs/tool_inventory.md` generated, never hand-edit; releases manual via Twine, never CI-published.

### Capabilities

- Expression/REPL modes, 9 text commands, `--explain`/`--commands`/`--capabilities`, `--mcp` stdio server launch, completions, installer.

### Infrastructure

- `MODULE_MANIFEST` (38 specs), `validate_build_manifest()`, topological assembly, import rewrites, entry-point renames, `install.py` atomic copy + PATH management.

### Polish

- Help text, error messages, startup footprint, artifact-size budgets.

## 3. Non-goals

- New transports, auth systems, or plugin frameworks.
- Broad module splitting solely to reduce line counts.
- Default-profile or semantic changes except through owning subsystems.

## 4. Current state

Legacy work complete and archived: trust-boundary correction (`023-cli-dispatch-and-trust-boundary-correction.md`), footprint reduction (`026-measured-artifact-and-startup-footprint-reduction.md`), CI/release simplification (`020`, `021`), config loading phases (`phase_1_*`, `next_pass_*`), release-polish family (`2026-07-06-*`, `release-polish-*`). Repository evidence: lazy dispatch, mode-gated config, manifest validation, `make check` then `make package-check` CI.

## 5. Target architecture

Same entry-point shape with locked trust boundaries; future CLI/distribution changes arrive as bounded milestones with transcript and packaging evidence.

## 6. Dependency graph

```text
M001 trust-boundary correction (closed, legacy 023)
    |
    +--> M002 footprint reduction (closed, legacy 026)
    |
    +--> M003 CI/release simplification (closed, legacy 020/021)
    |
    `--> M004 future CLI/dist change (proposed)
```

M004 has a soft dependency on the other three subsystems staying green (integration), operational on release evidence.

## 7. Milestones

### Milestone 1 — Trust-boundary correction

Class: invariant. Objective: mode-gated config loading and lazy dispatch. Dependencies: none (historical). Status: closed (legacy `023`).

### Milestone 2 — Footprint reduction

Class: infrastructure + polish. Objective: measured artifact/startup budgets with parity. Dependencies: M001 (hard). Status: closed (legacy `026`).

### Milestone 3 — CI/release simplification

Class: infrastructure. Objective: `make check` -> `make package-check`, manual Twine releases, compatibility matrix. Dependencies: M001 (hard). Status: closed (legacy `020`/`021`).

### Milestone 4 — Future CLI/distribution change (template)

Class: tbd. Objective: tbd. Dependencies: M001–M003 green (hard). Exit conditions: tbd.

## 8. Cross-cutting requirements

### Storage and migration

No migrations; installer backs up/rolls back atomically.

### Protocol and compatibility

CLI flags and text-command names are compatibility contracts; renames need deprecation notes.

### Security and authorization

Cwd-config trust boundary; installer PATH handling; no secret logging.

### Concurrency, cancellation, and recovery

REPL/`--mcp` lifecycle, signal handling, atomic installs.

### Observability and audit

`--explain` (no evaluation), `--commands`, `--capabilities` JSON, packaging smoke logs.

### Performance and resource use

Startup-import budgets, artifact-size tracking (~1.5 MB single file), worker/timeout bounds unchanged unless measured.

### Documentation and operations

`architecture/cli.md`, `architecture/build.md`, `architecture/capabilities.md`, `docs/releasing.md`, completions stay in sync.

## 9. Verification strategy

CLI transcript tests per mode, lazy-import tests, manifest validation, wheel/sdist/single-file smoke, `generate_mcp_docs.py --check`, `make check` + `make package-check`.

## 10. Risks and decision points

Installer/PATH and packaging-policy changes may need an ADR when they alter compatibility contracts. None open.

## 11. Completion definition

Roadmap closes when trust boundaries, footprint budgets, and release verification hold with current closure evidence and no open corrective passes. Stays active while distribution evolves.

## 12. Milestone status

| Milestone | Status | Implementation plan | Closure record | Blockers |
|---|---|---|---|---|
| 1 trust boundary | closed (legacy) | `plans/archive/legacy/023-cli-dispatch-and-trust-boundary-correction.md` | archived | — |
| 2 footprint | closed (legacy) | `plans/archive/legacy/026-measured-artifact-and-startup-footprint-reduction.md` | archived | — |
| 3 CI/release | closed (legacy) | `plans/archive/legacy/020-ci-verification-and-manual-pypi-release-simplification.md` | `plans/archive/legacy/021-ci-verification-simplification-closure.md` | — |
| 4 future change | not started | — | — | needs `implementation/cli-distribution/NNN-*.md` |
