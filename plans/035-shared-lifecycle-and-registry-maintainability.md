# Shared Lifecycle and Registry Maintainability

Status: planned  
Repository: `eggstack/eggcalc`  
Baseline reviewed: `55993e58b438f4548c58569248cdada52c099030`  
Date: 2026-09-08  
Parent roadmap: `plans/033-surface-consolidation-and-maintainability-roadmap.md`  
Depends on: Plan 034 semantic authorities stable or equivalent current behavior verified

## 1. Goal

Reduce maintenance risk in two internal areas where the codebase currently keeps parallel implementation machinery:

- subprocess spawn permits, process cleanup, and timeout-support lifecycle logic in evaluator and MCP tool paths;
- exact package lazy import/public export registry synchronization.

The goal is not to introduce a generalized framework. The goal is to remove duplicated tricky mechanics while preserving existing policy boundaries and public behavior.

## 2. Constraints

- Standard library only.
- No public API redesign.
- No generalized process supervisor or worker framework.
- Evaluator and MCP may keep different limits, timeouts, error messages, and policies.
- Do not merge evaluator and MCP execution paths.
- Do not alter MCP session/tool-executor architecture.
- Do not split large calculator modules merely for size reduction.
- Do not turn registry data into generated Python source if a normal Python mapping is sufficient.
- Preserve Windows/macOS/Linux behavior and generated single-file compatibility.
- Any new internal module must remain small and narrowly scoped.

## 3. Workstream A — shared subprocess lifecycle primitives

### 3.1 Inventory the duplicated mechanics

Compare the current lifecycle code in:

- `eggcalc/evaluator.py` around `_EVAL_SPAWN_SEMAPHORE`, `_EvalSpawnPermit`, process creation, timeout, termination/kill, queue cleanup, and orphan tracking;
- `eggcalc/mcp/tools.py` around `_SPAWN_SEMAPHORE`, `_SpawnPermit`, process context selection, `_cleanup_child_process`, queue handling, and orphan tracking;
- `eggcalc/mcp/server.py` cleanup hooks that observe MCP tool orphan processes.

Classify each item as either:

- shared mechanism;
- evaluator-specific policy;
- MCP-specific policy;
- single-file-specific behavior;
- platform-specific behavior.

Only shared mechanism should move.

### 3.2 Preferred extraction boundary

If the inventory confirms useful commonality, add one small private module, for example:

```text
eggcalc/_process.py
```

The exact name may differ if repository conventions suggest a better one.

The module may contain narrowly reusable primitives such as:

- an idempotent semaphore permit/guard;
- process-context selection helper where the exact policy is truly shared;
- queue close/join helper;
- terminate → bounded join → kill → bounded join → close helper;
- optional callback/result describing whether a process survived cleanup.

It should not contain:

- evaluator-specific constants;
- MCP-specific constants;
- tool names;
- JSON error envelopes;
- evaluator exceptions;
- registry/session state;
- global orphan collections unless a single shared collection is demonstrably correct for both subsystems.

Prefer returning cleanup status to the caller so each subsystem can preserve its own orphan accounting.

### 3.3 Preserve independent policy

Keep these concepts owned by their existing subsystem unless there is a concrete reason otherwise:

- maximum evaluator spawn count;
- maximum MCP spawned-tool count;
- semaphore acquire timeout values;
- regex timeout values;
- evaluator timeout values;
- orphan caps;
- MCP resource envelope behavior;
- evaluator `TimeoutError` behavior.

Mechanism sharing must not accidentally couple operational tuning.

### 3.4 RAII/idempotence requirements

The shared permit must remain safe under:

- normal `with` exit;
- exceptions;
- explicit release followed by context exit;
- destructor/finalizer fallback if retained;
- acquire timeout without consuming a permit.

If relying on `__del__` proves difficult or noisy across interpreter shutdown, prefer explicit/context-managed release and retain destructor behavior only where required by existing tests/contracts.

### 3.5 Process cleanup requirements

Process cleanup must preserve current defensive behavior:

1. close/join queue resources as appropriate;
2. terminate a live child;
3. bounded join;
4. kill if still alive and supported;
5. bounded join;
6. close handle only when safe;
7. report survivors to the caller for subsystem-specific orphan tracking.

Do not assume `resource` exists on Windows. Do not make `fork` a requirement. Do not change single-file process start semantics without dedicated parity tests.

## 4. Workstream B — exact lazy export authority

### 4.1 Current problem

`eggcalc/exact/__init__.py` maintains a large `_LAZY_IMPORTS` registry and a parallel `__all__` list. These two structures describe largely the same public surface and therefore create avoidable drift risk.

### 4.2 Preferred authority

Use `_LAZY_IMPORTS` as the practical source of truth for lazy public names unless inspection shows an existing `__all__` ordering or extra-name contract that must be preserved.

Preferred simple model:

```python
_LAZY_IMPORTS = {...}
__all__ = list(_LAZY_IMPORTS)
```

or equivalent immutable tuple/list according to current conventions.

If some names must remain in `__all__` without lazy resolution, represent those explicitly as a small separate tuple and derive the final list from both authorities.

Do not maintain two full manually synchronized 200+ name inventories.

### 4.3 Preserve import characteristics

Regression-test that:

- `import eggcalc.exact` does not eagerly import implementation modules;
- every name in `__all__` resolves;
- every intended lazy public name appears in `__all__`;
- unknown names still raise `AttributeError` correctly;
- package import remains side-effect-free;
- generated single-file behavior matches package behavior where the exact lazy surface is represented.

### 4.4 Build manifest invariants

Review whether `build_single.py` manually mirrors module/export knowledge that can drift when exact modules are added.

Do not redesign the single-file builder. Add only cheap invariants such as:

- every module named by `_LAZY_IMPORTS` is present in the exact build manifest when required for the full single-file distribution;
- no exact build module is silently omitted from dependency closure;
- existing `validate_build_manifest()` remains the central validation entry point if possible.

If equivalent tests already exist, extend them instead of adding another validator.

## 5. Workstream C — targeted calculator/unit coupling cleanup

This is optional and should only be performed if implementation inspection confirms the change is small.

The evaluator currently performs some structural unit-root operations using unit internals/private registry access. If the same unit algebra is plausibly useful outside the evaluator and moving it can be done with a narrow public/private helper in `units.py`, extract that helper.

Acceptable example:

```python
root_unit_expression(expr, degree) -> UnitExpression | None/error
```

The evaluator would own function-level policy/error wording while `units.py` owns structural unit algebra.

Do not create a new unit algebra module, generic dimensional dispatch framework, or broad evaluator/unit refactor in this plan.

Skip this workstream entirely if it does not clearly reduce coupling with a small diff.

## 6. Testing strategy

### Process lifecycle tests

Use focused deterministic tests that do not rely on long sleeps.

Cover:

- permit acquisition/release count;
- acquire timeout;
- release on exception;
- idempotent release;
- clean child exit;
- terminated child;
- killed child where platform supports it;
- queue cleanup;
- survivor reporting/orphan registration path using mocks/fakes where direct reproduction would be flaky;
- Windows-compatible spawn path;
- package versus single-file worker execution for representative timeout-backed functions.

Avoid tests that intentionally leak children or semaphores.

### Export tests

Cover:

- `set(__all__) == intended exported lazy names`;
- no duplicate names;
- all exported names resolve;
- importing exact alone does not populate representative implementation modules in `sys.modules`;
- added network/encoding/temporal exports from Plans 030–032 remain present.

## 7. Files likely to change

Expected files may include:

```text
eggcalc/_process.py              # only if extraction is justified
eggcalc/evaluator.py
eggcalc/mcp/tools.py
eggcalc/mcp/server.py            # only if cleanup interface changes
eggcalc/exact/__init__.py
eggcalc/units.py                 # optional narrow helper only
build_single.py
tests/test_import_boundaries.py
tests/test_build_manifest_graph.py
tests/test_build_single.py
tests/test_evaluator.py
tests/test_mcp_server.py
architecture/authority_inventory.md
architecture/build.md
```

Do not touch unrelated exact modules.

## 8. Implementation sequence

1. Add characterization tests for current spawn/cleanup behavior.
2. Extract the smallest shared process primitives.
3. Migrate evaluator to shared mechanisms without changing policy.
4. Migrate MCP tools to shared mechanisms without changing policy.
5. Run timeout/process-focused tests on package path.
6. Run generated single-file timeout/process smoke tests.
7. Consolidate exact export authority and add lazy-import invariants.
8. Extend build manifest checks only where needed.
9. Consider the narrow unit-root ownership cleanup; skip if nontrivial.
10. Update architecture authority/build documentation.
11. Run canonical verification.

## 9. Acceptance criteria

Plan 035 is complete when:

- evaluator and MCP no longer maintain independent copies of the same permit/cleanup mechanism;
- policy constants remain independently tunable;
- no process cleanup behavior is weakened;
- no new platform requirement is introduced;
- exact public export authority is no longer duplicated across two full manual registries, or an unavoidable compatibility exception is explicitly documented and invariant-tested;
- lazy import behavior remains intact;
- build manifest validation catches omissions relevant to the lazy exact surface;
- package and single-file timeout-backed behavior remain operational;
- no runtime dependency is added;
- `make check` and focused process/build tests pass.

## 10. Verification

Run at minimum:

```bash
python -m pytest tests/test_evaluator.py tests/test_mcp_server.py tests/test_import_boundaries.py tests/test_build_manifest_graph.py tests/test_build_single.py -v
python build_single.py --validate
make check
```

Where CI runners are available, ensure the lifecycle-focused tests are not Linux-only unless the implementation itself is explicitly platform-gated.

## 11. Non-goals

Do not use this plan to:

- replace multiprocessing with asyncio;
- replace thread pools/processes with a persistent worker daemon;
- centralize all resource limits into one global config;
- refactor MCP server/session classes;
- eliminate all module globals regardless of purpose;
- convert registries to metaclasses/decorators/plugins;
- split `evaluator.py`, `normalize.py`, `units.py`, `mcp/tools.py`, or `mcp/schemas.py` purely by line count;
- rewrite `build_single.py` as an AST bundler/import hook system;
- change public evaluator or MCP semantics.

The plan should produce a smaller maintenance burden, not a more abstract architecture.
