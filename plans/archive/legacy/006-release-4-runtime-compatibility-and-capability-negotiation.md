# Release 4 — Runtime Compatibility and Capability Negotiation

Status: ready for implementation handoff  
Repository: `eggstack/eggcalc`  
Depends on:

- `plans/001-correctness-protocol-hardening-roadmap.md`
- `plans/002-release-1-calculator-semantic-correctness.md`
- `plans/003-release-2-mcp-protocol-conformance.md`
- `plans/004-release-3-inspection-tool-correctness.md`
- `plans/005-releases-1-3-correctness-closure-pass.md`

Primary objective: make the supported-runtime contract truthful, deterministic, testable, and consistent across every advertised release surface.

## 1. Problem statement

Eggcalc currently advertises a broad standard-library-only tool surface while retaining Python 3.10 compatibility. TOML-backed functionality depends on `tomllib`, which is available in the standard library only on Python 3.11 and later. The current test matrix therefore skips mandatory inspection behavior on Python 3.10.

This creates a contract mismatch:

- the package claims a supported runtime;
- the MCP and Python APIs advertise tools that are not fully operational on that runtime;
- CI passes by skipping required functionality;
- users cannot reliably infer which capabilities exist from the package version or MCP tool inventory.

Release 4 must resolve this mismatch explicitly. It must not preserve Python 3.10 through silent degradation unless the unavailable capability is removed from every affected advertised surface.

## 2. Required policy decision

The preferred and default implementation path is:

> Raise the minimum supported Python version to 3.11.

Rationale:

- TOML inspection is an established, advertised feature rather than an optional extension.
- The project’s runtime-dependency policy is standard-library-only.
- Adding a TOML compatibility dependency would weaken that policy.
- Dynamic feature hiding on Python 3.10 would create a runtime-dependent public API and tool inventory.
- Python 3.11 provides the cleanest and most honest support boundary.

The implementation agent must begin by recording the final decision in the release implementation commit or an architecture decision note.

### Alternative path

Retaining Python 3.10 is allowed only if there is a documented operational requirement that outweighs the preferred policy. If retained, the implementation must satisfy all of the following:

1. TOML-dependent tools are not advertised on Python 3.10.
2. Python exports and MCP schemas accurately expose runtime availability.
3. Calls to unavailable tools return a stable capability-unavailable result or error rather than import failures.
4. The full Python 3.10 CI lane verifies degraded-mode behavior without skipping assertions.
5. Documentation states that the runtime is supported with a reduced capability set.

Merely retaining skips is not acceptable.

## 3. Scope

This release includes:

- Python minimum-version policy;
- packaging metadata and lockfile alignment;
- runtime capability representation;
- MCP tool and profile capability consistency;
- supported-platform CI expansion;
- package, CLI, wheel, single-file, and MCP release-surface verification;
- platform-specific path, shell, newline, subprocess, multiprocessing, and installer behavior;
- timeout-test reliability where required to obtain stable supported-platform CI.

This release does not include:

- process-global state isolation, which belongs to Release 5;
- core import decoupling, which belongs to Release 6;
- structural unit-dimension migration;
- new calculator, manifest, or MCP tools;
- support for draft MCP protocol revisions;
- replacement of the standard-library-only runtime policy.

## 4. Workstream A — Finalize the Python runtime contract

### A1. Audit all runtime declarations

Inspect and reconcile:

- `pyproject.toml` `requires-python`;
- wheel metadata;
- classifiers;
- README installation requirements;
- developer documentation;
- CI matrix versions;
- `uv.lock` Python constraints;
- generated single-file documentation or headers;
- release and changelog claims;
- any runtime guards in `eggcalc/exact/manifests.py`, `eggcalc/exact/cargo.py`, tests, or MCP registration.

### A2. Implement the selected policy

For the preferred Python 3.11+ path:

- set `requires-python` to `>=3.11`;
- remove Python 3.10 from supported classifiers and normal CI;
- remove `tomllib`-missing branches that can no longer occur on supported runtimes, unless they are intentionally preserved for direct file reuse;
- remove `_needs_tomllib` skips from tests that are mandatory on supported runtimes;
- ensure the package fails clearly during installation on Python 3.10;
- update lockfiles and contributor commands.

For the Python 3.10 degraded-capability path:

- define a runtime capability object;
- derive tool registration and profile contents from it;
- ensure TOML-dependent tools are absent from `tools/list` and direct registries on 3.10;
- test stable failure behavior for direct Python calls where exports remain present;
- document the reduced surface in README, API, architecture, and MCP docs.

### A3. Prevent accidental runtime drift

Add tests that compare:

- packaging metadata versus CI versions;
- documented minimum version versus `pyproject.toml`;
- runtime capability declarations versus MCP tool registration;
- supported-version classifiers versus CI matrix entries.

## 5. Workstream B — Runtime capability model

Even on Python 3.11+, Eggcalc has platform-sensitive and environment-sensitive behavior. Introduce a small immutable capability representation rather than scattered checks.

Suggested shape:

```python
@dataclass(frozen=True)
class RuntimeCapabilities:
    python_version: tuple[int, int, int]
    platform: str
    has_tomllib: bool
    supports_fork: bool
    supports_spawn: bool
    supports_resource_module: bool
    supports_posix_paths: bool
    supports_windows_paths: bool
```

The exact fields may differ, but the object must:

- be computed once per process from observable runtime facts;
- be immutable;
- have no dependency on user configuration;
- be injectable into tests;
- avoid changing global behavior when imported;
- be usable by MCP registration, CLI diagnostics, and release-surface checks.

### B1. Capability inspection API

Expose a stable diagnostic function or CLI output that reports:

- package version;
- Python version;
- platform;
- supported MCP protocol versions;
- available tool categories or unavailable capabilities;
- multiprocessing start methods where relevant;
- single-file/package mode.

The output must be deterministic and JSON serializable.

### B2. MCP capability alignment

Ensure:

- `tools/list` does not advertise unavailable tools;
- profiles contain only registered tools;
- schema generation excludes unavailable tools;
- direct `tools/call` of an unavailable tool returns a stable error;
- package and generated single-file MCP inventories match on the same runtime.

If Python 3.11+ is adopted and all current tools are available, tests must still prove that the advertised inventory is derived consistently rather than relying on undocumented assumptions.

## 6. Workstream C — Supported-platform CI

Establish supported CI lanes for:

- Linux;
- macOS;
- Windows.

Use a bounded matrix. At minimum:

- minimum supported Python on all three platforms;
- latest supported Python on Linux;
- one intermediate Python version on Linux if the project continues broad version support.

### C1. Platform-sensitive test categories

Add or strengthen tests for:

- POSIX and Windows path parsing;
- drive letters, UNC paths, path separators, and reserved names;
- CRLF, LF, and mixed-newline input;
- shell lexical tools without invoking a platform shell unexpectedly;
- subprocess startup and clean shutdown;
- multiprocessing start methods (`spawn` and `fork` where available);
- timeout worker behavior;
- broken-pipe and closed-stream behavior;
- editable install;
- wheel installation into a clean virtual environment;
- console-script installation;
- generated single-file execution;
- MCP stdio transcripts.

### C2. No unsupported assumptions

Tests and implementation must not assume:

- `/tmp` exists;
- `/bin/sh` exists;
- `fork` exists;
- file deletion of open files behaves like POSIX;
- newline is always `\n`;
- paths are case-sensitive;
- console scripts use a POSIX shebang;
- signal handling is identical across platforms.

## 7. Workstream D — Timeout and multiprocessing reliability

The closure evidence records two timing-sensitive macOS failures in `tests/test_clicalc.py`. Resolve them as part of supported-platform readiness.

Required approach:

- identify whether the tests are asserting implementation behavior or scheduler timing;
- replace narrow wall-clock assumptions with explicit synchronization where practical;
- use generous bounded deadlines only for process-liveness failure detection;
- avoid sleeps as the primary synchronization mechanism;
- ensure child processes are always reaped;
- ensure timeout tests cannot leave orphaned workers;
- run the affected tests repeatedly on macOS and Linux.

Acceptance requires deterministic pass behavior under repeated execution, not merely increasing the timeout until failures disappear.

## 8. Workstream E — Packaging and release-surface verification

### E1. Clean-environment matrix

Automate verification of:

1. source checkout import;
2. editable install;
3. wheel build;
4. wheel installation in a clean virtual environment;
5. `python -m eggcalc`;
6. `calc` console script;
7. direct Python API;
8. generated `eggcalc.py`;
9. MCP stdio package mode;
10. MCP stdio single-file mode.

### E2. Runtime rejection behavior

For the preferred Python 3.11+ policy, add a packaging-level check that Python 3.10 is rejected by metadata. This may be a metadata assertion or a controlled installation test.

Do not rely on syntax errors or missing modules as the rejection mechanism.

### E3. Lockfile ownership

Clarify the role of `uv.lock`:

- document whether it is normative for development and CI;
- ensure its Python constraint matches `pyproject.toml`;
- add a consistency check or regeneration instruction;
- do not allow stale lock metadata to silently expand or narrow supported runtimes.

## 9. Workstream F — Documentation and migration notes

Update:

- README;
- installation docs;
- API docs;
- MCP docs;
- architecture runtime notes;
- AGENTS.md;
- changelog;
- release notes;
- contributor setup commands.

Documentation must state:

- minimum supported Python version;
- supported operating systems;
- whether all tools are available on every supported runtime;
- runtime capability inspection method;
- any migration action for Python 3.10 users;
- how the lockfile is used;
- supported MCP protocol revisions.

## 10. Test plan

Add focused tests for:

- runtime metadata consistency;
- capability object immutability;
- capability JSON serialization;
- tool registry versus capabilities;
- MCP profile versus registered tools;
- package versus single-file inventory parity;
- path behavior on Windows and POSIX fixtures;
- newline normalization;
- subprocess and broken-pipe handling;
- repeated timeout execution;
- clean wheel installation;
- console-script invocation;
- unsupported-Python metadata behavior.

Run at least:

```bash
python -m ruff check .
python -m black --check .
python build_single.py
python scripts/smoke_release_surfaces.py
python -m pytest tests/ -v
mypy eggcalc --ignore-missing-imports
python -m build
```

Also run the supported OS/Python CI matrix and record links or run identifiers in a Release 4 evidence document.

## 11. Explicit acceptance criteria

Release 4 is complete only when all criteria below are met.

### Runtime contract

- [ ] One minimum-version policy is selected and documented.
- [ ] `pyproject.toml`, classifiers, README, CI, lockfile, and release documentation agree.
- [ ] No supported runtime relies on skipped tests for mandatory functionality.
- [ ] Unsupported Python versions fail through packaging metadata or expose an explicitly documented reduced capability set.

### Capability correctness

- [ ] Runtime capabilities are represented by one immutable, testable source of truth.
- [ ] Every advertised MCP tool is callable on every supported runtime.
- [ ] MCP profiles contain no unavailable or unregistered tools.
- [ ] Package and single-file tool inventories match on the same runtime.
- [ ] Capability diagnostics are deterministic and JSON serializable.

### Platform support

- [ ] Linux, macOS, and Windows CI lanes pass on the minimum supported Python version.
- [ ] Path, newline, subprocess, multiprocessing, and installer behavior are covered on relevant platforms.
- [ ] Tests do not encode POSIX-only assumptions in cross-platform paths.
- [ ] Broken-pipe and timeout tests pass reliably on supported platforms.

### Packaging

- [ ] Source, editable install, wheel install, module execution, console script, single-file, Python API, and MCP stdio surfaces pass.
- [ ] `uv.lock` has a documented role and matching Python constraints.
- [ ] Generated single-file checks remain clean after runtime-policy changes.

### Evidence

- [ ] A release evidence file records commands, OS/Python matrix, pass counts, skips, warnings, and CI identifiers.
- [ ] Any remaining skips are explicitly non-mandatory and justified.
- [ ] Documentation and changelog accurately describe the final runtime contract.

## 12. Recommended implementation sequence

1. Record the runtime policy decision.
2. Update packaging metadata, classifiers, lockfile constraints, and CI matrix.
3. Introduce the runtime capability object and diagnostics.
4. Align tool registration, profiles, and MCP inventory with capabilities.
5. Remove mandatory-feature skips or replace them with degraded-mode assertions.
6. Add Windows/macOS platform fixtures and CI.
7. Stabilize timeout and subprocess tests.
8. Run clean-environment release-surface verification.
9. Update documentation and migration notes.
10. Commit a Release 4 evidence record.

## 13. Handoff notes

The implementation agent should prefer the Python 3.11+ policy unless a concrete repository requirement demonstrates that Python 3.10 must remain supported. Do not preserve Python 3.10 merely because it is currently present in CI.

Avoid mixing Release 5 state-isolation work into this release. Runtime capabilities may be injectable and immutable, but evaluator, configuration, registry, and session ownership changes belong to the next plan.
