# stdlib Production Hardening Roadmap

## Scope

This roadmap covers the remaining production-hardening work for `eggcalc` as a pure-stdlib CLI calculator, Python library, single-file executable, and deterministic MCP server for agent workflows.

The roadmap intentionally excludes new tool expansion. Do not add the previously discussed missing agent tools as part of this track. In particular, do not add Python import inspectors, license scanners, YAML tools, CSV tools, `.gitignore` matchers, or new composite patch-planning tools under this roadmap.

The runtime package must remain standard-library-only. Optional development dependencies may remain in the `dev` extra, but no new runtime dependency should be introduced under `eggcalc/`, the single-file build, or MCP server execution.

## Current repo posture

The repo is already fairly mature. It has a calculator/library surface, a single-file distribution path, generated MCP tool inventory, MCP profiles, CI across multiple Python versions, linting, formatting checks, generated-doc checks, packaging validation, and smoke tests. Remaining work should not chase broad feature expansion. It should reduce surprising behavior, tighten resource safety, and make agent-facing operation easier to configure correctly.

## Goals

The primary goal is safe-by-default behavior across all consumer surfaces:

- `import eggcalc` should be safe in arbitrary working directories.
- CLI custom config loading should be explicit, documented, and tested.
- MCP mode should remain deterministic and hardened against cwd config execution.
- MCP tools should have clear input, output, timeout, and concurrency bounds.
- Agent profile selection should be documented as an operational choice, not hidden in source comments.
- Evaluation-path terminology should be consistent across README, API docs, `AGENTS.md`, and MCP docs.
- Version comparison semantics should either be complete for a declared scheme or explicitly rejected with clear errors.
- Release checks should validate editable install, wheel install, single-file build, CLI, Python API, and MCP stdio surfaces.

## Non-goals

- Do not add runtime dependencies.
- Do not add new MCP tool families under this track.
- Do not relax single-file build compatibility.
- Do not add network access to deterministic tools.
- Do not make MCP tools mutate the filesystem.
- Do not remove existing tools without a separate deprecation plan.
- Do not make CI depend on long wall-clock timeout tests.

## Phase 1 — Safe configuration loading

### Problem

`eggcalc.__init__` currently loads `eggcalc_config.py` automatically unless `EGGCALC_NO_CONFIG` is set. This is convenient for local CLI use but unsafe and surprising for library import and agent execution inside arbitrary repositories. MCP mode already sets `EGGCALC_NO_CONFIG=1` before importing other package modules, but the library default still creates unnecessary risk.

### Target outcome

Library import must not execute cwd-local Python config by default. CLI config loading may be preserved for compatibility, but it should be explicitly owned by CLI startup logic rather than package import. MCP mode must continue to disable config loading unconditionally.

### High-level work

Move automatic config loading out of `eggcalc/__init__.py`. Add an explicit CLI-scoped config initialization helper. Preserve `EGGCALC_NO_CONFIG=1`. Consider explicit library opt-in via environment variable or API, but do not make library import execute config by default. Add tests covering package import, CLI behavior, MCP behavior, and single-file behavior.

## Phase 2 — MCP timeout and resource-control audit

### Problem

The MCP server uses a bounded thread pool, bounded request/output sizes, cancellation records, and spawned-process limits for expensive operations. However, timed-out running thread-pool tasks cannot be forcibly stopped. That is acceptable only if each tool is already bounded by input limits, early exits, subprocess isolation, or cheap algorithms.

### Target outcome

Every existing MCP tool has a documented resource-bound story. Pathological inputs should return `input_too_large`, `output_too_large`, `timeout`, or a bounded partial result. No path should cause unbounded worker growth, subprocess growth, cancellation-record growth, orphan-process growth, or unbounded serialized output.

### High-level work

Create an audit table for all current MCP tools. Identify non-linear or potentially expensive paths in regex, diff, patch, JSON, schema, Unicode/confusable, list, and manifest logic. Tighten limits or add early exits where needed. Route truly expensive sections through existing killable subprocess patterns only when necessary and still stdlib-only. Add bounded adversarial tests that avoid CI flakiness.

## Phase 3 — MCP profile defaults and agent configuration

### Problem

The MCP server defaults to the `full` profile for backward compatibility, while source comments indicate coding agents should prefer `codegg_core` or `codegg_core_min`. The recommended operational profile should be obvious from documentation and examples.

### Target outcome

`full` is documented as compatibility/exploration mode. `codegg_core_min` is documented as the safest low-context default for coding agents. `codegg_core` is documented as the normal recommended coding-agent profile. Specialized profiles remain opt-in for patch, config, shell, Unicode/security, and repo-audit workflows.

### High-level work

Review `TOOL_PROFILES` for consistency. Add profile purpose, recommended consumer, and rough context-cost guidance to MCP docs. Add copy-paste configuration examples for common agent profiles. Add tests ensuring every profile-listed tool exists in both schemas and handlers and that hidden/deprecated exposure semantics are preserved.

## Phase 4 — Documentation drift and terminology cleanup

### Problem

README, `AGENTS.md`, API docs, architecture docs, MCP docs, and generated inventory overlap. Some wording is stale or imprecise. The most important drift is around evaluation paths: the distinction is not really “spaces versus no spaces,” but “pre-normalized AST-compatible expression” versus “full natural-language/unit normalization pipeline.”

### Target outcome

Docs use one coherent mental model:

- `evaluate()` is the fast path for already-normalized Python-AST-compatible expressions.
- `evaluate_raw()`, `evaluate_cached()`, `evaluate_async()`, and CLI paths run the full natural-language/unit normalization pipeline.
- `run()` is an internal or compatibility path used by the normalization pipeline.
- MCP `math_eval` uses deterministic defaults, with random and side-effectful functions disabled.

### High-level work

Update `AGENTS.md`, README, `docs/api.md`, `docs/mcp.md`, and relevant architecture docs. Regenerate generated docs. Remove or regenerate stale module line counts. Ensure docs do not imply library import executes cwd config after Phase 1.

## Phase 5 — Version and constraint semantics tightening

### Problem

The version tools support semver and loose numeric schemes, while PEP 440 support is described as deferred. For a Python package, partial or ambiguous PEP 440 behavior is risky. A clear unsupported error is better than silently incorrect sorting.

### Target outcome

Version behavior is deterministic, stdlib-only, and explicit. Either unsupported PEP 440 constructs fail clearly, or a bounded stdlib-only PEP 440 subset is deliberately implemented and documented.

### Recommended approach

First make unsupported or deferred PEP 440 behavior explicit in docs, schemas, and tests. Verify pre/dev/post/local/epoch examples are rejected clearly rather than mis-sorted. Only later consider implementing a stdlib-only PEP 440 subset if there is a concrete need.

## Phase 6 — Release verification and packaging polish

### Problem

CI is already strong, but release readiness should validate the exact surfaces that users and agents consume: editable install, wheel install, single-file artifact, CLI, Python API, MCP stdio, docs generation, and config-loading safety.

### Target outcome

A release candidate has a deterministic checklist that can be run locally and in CI. The built wheel and single-file artifact are tested through realistic smoke tests, including MCP initialize/list/call flows.

### High-level work

Add or update release-check documentation. Add a stdlib-only MCP smoke test script using `subprocess` and `json`. Test both installed package MCP mode and `eggcalc.py --mcp`. Verify package metadata version, `eggcalc.__version__`, generated docs, and changelog/release notes cannot drift silently.

## Phase 7 — Final documentation and UX polish

### Problem

The project now serves multiple audiences: calculator users, Python library users, single-file users, and coding-agent/MCP users. The README should quickly route each audience without duplicating generated docs.

### Target outcome

README remains compact but clearly presents CLI, library, MCP, recommended agent profile, config-safety behavior, and links to detailed docs.

### High-level work

Restructure README minimally. Add a “choose your mode” section. Add recommended MCP profile guidance. Keep generated tool inventory out of the README except as a link. Ensure examples match current behavior after Phases 1–6.

## Recommended execution order

Execute Phase 1 first because config-loading behavior is the main safety issue and affects docs, CLI, library, MCP, and single-file behavior.

Execute Phase 2 next because timeout and resource bounds are the other production-readiness concern.

Execute Phases 3 and 4 together if convenient because MCP profile docs and terminology cleanup overlap.

Execute Phase 5 narrowly at first by making version limitations explicit rather than implementing a full comparator.

Execute Phase 6 after behavior and docs stabilize.

Execute Phase 7 as the final user-facing polish pass.

## Final definition of done

The roadmap is complete when:

- Importing `eggcalc` is side-effect-free with respect to cwd config execution.
- CLI config loading is explicit, documented, and tested.
- MCP mode remains config-hardened and deterministic.
- Existing MCP tools have resource-bound coverage and adversarial tests where appropriate.
- Timeout handling cannot cause unbounded resource accumulation.
- Recommended MCP profiles for agents are documented and tested.
- Evaluation-path terminology is consistent across user and agent docs.
- Version comparison behavior is explicit and does not silently misrepresent unsupported PEP 440 semantics.
- Editable install, wheel install, single-file build, CLI, Python API, and MCP stdio paths are all release-verified.
- Runtime remains pure stdlib.
