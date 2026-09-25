# MCP and Configuration Authority Consolidation

Status: implemented  
Repository: `eggstack/eggcalc`  
Baseline reviewed: `8515579e9e64fcb49a3e5b46ac4f0c47e77d8ff1`  
Date: 2026-07-31  
Roadmap: `plans/022-correctness-simplification-and-footprint-roadmap.md`  
Depends on: `plans/024-unit-aware-function-contracts-and-timeout-state-parity.md`

## 1. Purpose

Reduce internal MCP and configuration complexity by making the instance-oriented `McpServer`/`McpSession`/`ToolRegistry`/`ToolExecutor` path authoritative and converting module-level compatibility APIs into thin delegates.

At the same time, consolidate configuration parsing, validation, recursive freezing, snapshot construction, and replacement so invalid or mutable data cannot bypass the canonical path.

This plan preserves the full current MCP product surface. It does not remove tools, profiles, schemas, protocol versions, compatibility APIs, runtime reconfiguration, or stdio operation.

## 2. Governing constraints

The implementation must preserve:

- all current MCP tool names and handlers;
- all 18 tool categories and 11 profiles;
- all current tool schemas and schema-detail modes;
- case-insensitive lookup and suggestions;
- protocol versions `2024-11-05` and `2025-11-25`;
- session lifecycle and initialization requirements;
- request/output limits and queue accounting;
- `McpServer`, `McpSession`, `McpServerConfig`, `ToolRegistry`, `ToolExecutor`, `ConfigSnapshot`, `ConfigManager`, `EvaluationPolicy`, and other public imports;
- `handle_request()` compatibility behavior and deprecation warning;
- `close_compatibility_server()`;
- stdio `calc --mcp` behavior;
- package and single-file parity;
- standard-library-only runtime.

Do not:

- remove or rename a tool;
- change a public tool schema for cleanup alone;
- introduce a plugin framework, dependency-injection container, async framework, or server framework;
- replace stdio MCP with HTTP, sockets, or subprocess RPC;
- add hot-reload file watching;
- add persistent configuration storage;
- introduce a second schema library;
- broaden protocol support;
- add CI lanes, evidence artifacts, or release automation;
- combine this pass with lazy tool imports unless a trivial prerequisite is required for Plan 026.

## 3. Current complexity to correct

### 3.1 Duplicate request execution paths

The codebase has an instance-oriented runtime with server-owned registry, executor, evaluator, config manager, and sessions. It also retains module-level compatibility functions and global executor/config state.

Compatibility is necessary; duplicate implementation is not.

The target is:

```text
public compatibility function
    -> compatibility server/session adapter
        -> canonical McpServer dispatch
            -> canonical ToolRegistry + ToolExecutor
```

There must not be a second independent tool-resolution, validation, execution, timeout, output-limiting, or error-conversion path.

### 3.2 Multiple configuration construction paths

Configuration is represented through snapshots, candidates, managers, runtime contexts, parser helpers, and direct constructors.

At least one replacement path can construct a `ConfigSnapshot` without passing through the same validation as `parse_config_snapshot()`. Invalid function values or nested mutable data may therefore be accepted, ignored, or represented inconsistently.

### 3.3 Competing recursive-freeze helpers

The module contains both `freeze_owned()` and another deep-freeze implementation. `ConfigSnapshot` claims deep immutability, but direct construction or shallow wrappers can leave nested values mutable.

One recursive ownership conversion must be authoritative.

### 3.4 Policy values have conceptual duplication

`EvaluationPolicy.DEFAULT` and `EvaluationPolicy.PERMISSIVE` currently resolve to equivalent effective behavior.

The public enum values must remain importable, but internal branching should not pretend they are distinct when they are not.

### 3.5 Public and private state ownership is hard to audit

Global compatibility state, server-owned state, config manager state, evaluator overlays, and registry mappings can overlap. The pass should make ownership explicit without adding more layers.

## 4. Target architecture

The desired runtime is:

```text
McpServerConfig (immutable primitive config)
        |
McpServer
  owns ToolRegistry
  owns ToolExecutor
  owns evaluator
  owns ConfigManager
  owns live McpSession instances
        |
McpSession
  owns protocol lifecycle for one connection
        |
canonical request dispatch
  validates protocol state
  resolves tool through ToolRegistry
  executes through ToolExecutor
  enforces limits/timeouts/output bounds
  returns JSON-RPC response
```

Compatibility surface:

```text
handle_request(request, session=None)
  if session provided:
      delegate to that session/server canonical dispatch
  else:
      acquire isolated compatibility server/session
      perform canonical dispatch
      preserve deprecation warning

close_compatibility_server()
  closes and clears only compatibility-owned server/session state
```

Configuration surface:

```text
plain input mapping
  -> parse_config_snapshot()
      -> normalized validated owned values
      -> ConfigSnapshot through canonical constructor/factory
          -> ConfigManager.replace()
              -> McpServer.activate_snapshot()
                  -> atomic evaluator/runtime update with rollback
```

No alternate direct-construction replacement path may bypass this sequence.

## 5. Workstream A — inventory authorities before editing

### A1. Identify every request entry point

Document in implementation notes or code comments, not a new permanent inventory file:

- stdio main loop entry;
- `McpServer` request method;
- `McpSession` dispatch method;
- module-level `handle_request()`;
- direct tool execution helpers used by tests or consumers;
- compatibility server creation and closure.

For each, identify whether it currently performs:

- protocol-state validation;
- method routing;
- tool lookup;
- argument schema validation;
- tool execution;
- timeout handling;
- output limiting;
- error mapping.

The goal is to find duplicate authorities, not to generate documentation machinery.

### A2. Identify every config entry point

Inventory:

- `ConfigSnapshot` constructors/factories;
- `parse_config_snapshot()`;
- `ConfigCandidate` construction;
- `ConfigManager.replace()`;
- `ConfigManager.replace_validated()`;
- server activation;
- runtime-context creation;
- compatibility config setters;
- tests that construct snapshots directly.

### A3. Stop rule

Do not begin a broad class rewrite. First choose the existing path that already enforces the most complete semantics and make other paths delegate to it.

The preferred canonical path is the current instance-oriented path unless inspection reveals a concrete correctness gap.

## 6. Workstream B — canonicalize request dispatch

### B1. One dispatch method

Select one method on `McpSession` or `McpServer` as the canonical JSON-RPC request dispatcher.

It must own or delegate exactly once for:

- request shape validation;
- lifecycle validation;
- initialize/initialized transitions;
- method routing;
- tools/list behavior;
- tools/call behavior;
- ping and diagnostics where supported;
- JSON-RPC error construction;
- session close behavior.

Do not preserve a second function with copied branches.

### B2. Compatibility delegation

Refactor `handle_request()` so it contains only:

- deprecation warning behavior;
- session selection;
- compatibility server/session acquisition when no session is supplied;
- delegation to canonical dispatch;
- minimal compatibility result adaptation if required.

It must not independently:

- resolve tools;
- validate tool arguments;
- construct runtime context;
- execute handlers;
- enforce timeout/output limits;
- reconstruct JSON-RPC errors already produced by canonical dispatch.

### B3. Global compatibility executor

If a module-level executor or registry is publicly imported or relied upon by tests, retain the symbol as a compatibility view or delegate.

Preferred approaches, in order:

1. expose the compatibility server's canonical executor through a read-only accessor;
2. retain the old symbol as a lazily initialized alias to the canonical compatibility server object;
3. preserve a small facade that forwards methods.

Do not maintain a separately populated registry/executor.

### B4. Compatibility state lifetime

Compatibility state must be:

- lazily created;
- isolated from explicitly constructed `McpServer` instances;
- safe under the existing thread/process assumptions;
- closed and cleared by `close_compatibility_server()`;
- recreated cleanly after closure;
- not loaded during ordinary `import eggcalc`.

Use existing locking primitives if already present. Do not add a generalized service locator.

### B5. Tests

Add or adapt tests proving:

- explicit-session requests and compatibility requests produce equivalent normalized responses;
- both paths enforce initialization state;
- both paths enforce profile visibility;
- both paths enforce schema validation;
- both paths enforce output/timeout limits;
- closing compatibility state does not close an independent server;
- a subsequent compatibility request recreates clean state;
- the deprecation warning remains emitted only by the compatibility call.

Do not duplicate the complete tool suite for both paths. Use representative protocol and tool calls plus one normalized transcript comparison.

### B6. Acceptance criteria

- one request-dispatch authority remains;
- compatibility APIs delegate;
- no separately populated compatibility registry/executor remains;
- public behavior is preserved;
- protocol/session tests remain green.

## 7. Workstream C — consolidate tool registry ownership

### C1. Registry construction

Ensure `ToolRegistry` is constructed from the existing authoritative tool handlers, schemas, metadata, and profiles exactly once per server or through one immutable shared definition where safe.

The public runtime registry object may be per-server, but source definitions must not be copied into separate global and instance tables.

### C2. Immutability

Registry-owned nested structures must be recursively frozen through the canonical freeze helper.

Public getters that promise caller-owned mutable data should return thawed/deep-copied values.

Internal accessors may return immutable views.

Do not freeze live callables or server objects.

### C3. Validation

Retain current registry validation for:

- duplicate handlers;
- unsupported `llm_exposure` values;
- empty profile names;
- missing schemas or metadata;
- profile references to unknown tools, if currently enforced.

Add one completeness assertion only if a gap exists. Avoid a second registry-lint framework.

### C4. Acceptance criteria

- tool definitions have one source;
- each server uses the canonical registry construction path;
- public mutable returns cannot mutate registry internals;
- no tool/schema/profile membership changes occur.

## 8. Workstream D — one recursive freeze/thaw authority

### D1. Select the canonical helpers

Prefer the existing public/internal pair:

```text
freeze_owned()
thaw_owned()
```

if they already handle:

- mappings -> `MappingProxyType`;
- lists/tuples -> tuples;
- sets -> frozensets;
- nested combinations recursively;
- scalar/callable passthrough as appropriate.

Delete or delegate `_deep_freeze()` and any equivalent private implementation.

### D2. Define ownership semantics

`freeze_owned(value)` must recursively detach mutable caller-owned containers before wrapping them.

It is insufficient to wrap the caller's original dictionary while preserving references to nested lists or dictionaries.

A suitable rule is:

- construct fresh normalized containers recursively;
- then expose immutable forms;
- never retain caller-owned mutable nested containers.

### D3. Snapshot construction

`ConfigSnapshot` must receive only canonical frozen values through:

- a private validated constructor;
- a classmethod/factory;
- or `parse_config_snapshot()`.

If direct public construction must remain for compatibility, `__post_init__` must normalize and freeze deeply, then perform invariant validation that does not depend on external parser context.

Prefer a factory if changing dataclass initialization semantics would be risky.

### D4. Tests

Verify nested immutability:

1. build input with nested dict/list/set values;
2. create snapshot/registry;
3. mutate original inputs;
4. assert internal snapshot/registry values do not change;
5. attempt mutation of exposed immutable structures and assert failure;
6. call `to_dict()` or getter and mutate returned data;
7. assert original remains unchanged.

### D5. Acceptance criteria

- one recursive freeze implementation remains;
- one thaw/deep-copy implementation remains;
- snapshots and registries do not retain caller-owned nested mutables;
- public conversion methods return independent data;
- no third-party immutable collection package is added.

## 9. Workstream E — canonical configuration parsing and replacement

### E1. One parser

`parse_config_snapshot()` must be the authoritative parser for plain configuration mappings.

It must normalize and validate:

- generation handling where supplied;
- constants and allowed scalar value types;
- function callability;
- unit declarations and names;
- policy values;
- any custom-unit restrictions already part of the current product;
- unknown or malformed keys according to current behavior;
- nested ownership/freeze semantics.

Plan 024's custom-unit category validation must be reused, not duplicated.

### E2. `replace_validated()` behavior

Refactor `ConfigManager.replace_validated()` so it:

1. assigns or reserves the next monotonic generation;
2. calls the canonical parser/factory;
3. receives a valid deeply immutable snapshot;
4. delegates to `replace()` for monotonic replacement;
5. returns the activated snapshot or existing documented result.

It must not construct `ConfigSnapshot` directly from unvalidated input.

### E3. Direct snapshot replacement

`ConfigManager.replace(snapshot)` may continue accepting a snapshot object, but must verify:

- correct type;
- valid generation ordering;
- snapshot invariants that can be checked locally;
- no nested mutability if direct construction remains possible.

Do not reparse already validated snapshots into a second representation.

### E4. Runtime context construction

Runtime/evaluator context creation must not silently ignore invalid values.

After this pass, invalid function entries, constants, policy values, or units must fail before activation.

Context construction should assume validated input and contain no second permissive parser.

### E5. Atomic activation and rollback

Preserve current atomic activation behavior:

- prepare new evaluator/runtime state;
- apply snapshot;
- if activation fails, restore the prior state;
- update active generation only on success.

Consolidation must not weaken rollback.

Use focused failure injection in tests; do not add transactional infrastructure.

### E6. Tests

Cover:

- valid replacement with manager-assigned generation;
- stale/decreasing generation rejection;
- invalid constant type rejection;
- non-callable function rejection;
- invalid policy rejection;
- invalid unit declaration rejection;
- nested input mutation does not affect active snapshot;
- activation failure rolls back evaluator and generation;
- compatibility config entry points use the same parser.

### E7. Acceptance criteria

- all plain config input flows through one parser;
- `replace_validated()` cannot bypass validation;
- runtime context creation does not silently discard invalid entries;
- activation remains atomic;
- generation rules remain monotonic;
- public compatibility behavior remains available.

## 10. Workstream F — simplify evaluation-policy semantics

### F1. Preserve public enum values

Do not remove or rename:

```text
EvaluationPolicy.DEFAULT
EvaluationPolicy.STRICT
EvaluationPolicy.PERMISSIVE
```

### F2. Make effective behavior explicit

If `DEFAULT` and `PERMISSIVE` are intentionally equivalent, encode that in one normalization function:

```python
def _effective_policy(policy: EvaluationPolicy) -> EvaluationPolicy:
    if policy is EvaluationPolicy.PERMISSIVE:
        return EvaluationPolicy.DEFAULT
    return policy
```

or equivalent.

Document `PERMISSIVE` as a compatibility alias for default behavior.

Do not maintain duplicate conditional branches that perform the same actions.

If inspection reveals a documented behavioral distinction that is currently broken, implement only that documented distinction with focused tests. Do not invent a new permission model.

### F3. Acceptance criteria

- public enum values remain importable and parseable;
- effective semantics are defined in one place;
- equivalent values share one execution path;
- policy documentation is truthful;
- no new policy values are added.

## 11. Workstream G — remove obsolete private layers

After delegation and tests are in place, remove private code that has become redundant, such as:

- duplicate global tool dispatch;
- duplicate schema validation wrappers;
- duplicate output limiting;
- duplicate runtime-context parsing;
- duplicate freeze helpers;
- duplicate compatibility registry population;
- dead config candidate transformations;
- unused policy branches.

Before deletion, use repository search to verify each private symbol has no remaining call sites.

Do not remove public imports merely because direct repository tests do not use them.

The desired outcome is fewer authorities and fewer lines, not renamed equivalents.

## 12. Files expected to change

Primary:

```text
eggcalc/mcp/server.py
eggcalc/mcp/__init__.py
tests/test_mcp_server.py
tests/test_mcp_config.py or equivalent configuration tests
```

Possible:

```text
eggcalc/mcp/tools.py
eggcalc/mcp/schemas.py
eggcalc/evaluator.py
eggcalc/_protocol.py
docs/architecture/mcp.md
docs/mcp_resource_limits.md
AGENTS.md
AGENTS.override.md
build_single.py
```

`mcp/tools.py` should not be converted to lazy imports in this phase. Plan 026 owns that decision.

Do not touch unrelated exact-tool implementations, workflow files, release documentation, or package dependencies.

## 13. Verification strategy

Use the existing test architecture.

Suggested focused sequence:

```text
python -m pytest tests/test_mcp_server.py -q
python -m pytest tests/test_mcp_stdio_smoke.py -q
python -m pytest tests/test_mcp_schema_lint.py -q
python -m pytest tests/ -q -k 'config or snapshot or registry'
python build_single.py --validate
```

Final required verification:

```text
make check
make package-check
```

Do not add:

- protocol transcript artifacts;
- generated registry inventories;
- an MCP conformance service;
- network tests;
- a new compatibility workflow.

## 14. Explicit negative tests

The implementation is incomplete unless tests prove:

1. compatibility `handle_request()` cannot bypass session initialization rules.
2. compatibility calls and explicit-session calls do not use separately populated tool registries.
3. invalid function values cannot enter an active snapshot through `replace_validated()`.
4. mutating nested caller input cannot mutate `ConfigSnapshot` or `ToolRegistry` internals.
5. activation failure does not advance generation or leave partial evaluator state.
6. closing the compatibility server does not close independent `McpServer` instances.
7. `DEFAULT` and `PERMISSIVE` do not maintain duplicated equivalent branches.
8. ordinary import does not eagerly create compatibility server state.

## 15. Final acceptance criteria

This plan is complete when:

1. one canonical MCP request-dispatch path exists;
2. module-level compatibility APIs are thin delegates;
3. compatibility state is lazy, isolated, closeable, and recreatable;
4. tool definitions and registry construction have one authority;
5. all plain configuration input uses one parser;
6. `replace_validated()` cannot bypass parsing;
7. one recursive freeze/thaw implementation remains;
8. snapshots and registries are deeply immutable from caller mutation;
9. runtime context creation assumes validated input and does not silently ignore invalid values;
10. atomic activation and rollback remain correct;
11. evaluation-policy equivalence is explicit and centralized;
12. obsolete duplicate private paths are removed rather than renamed;
13. every current tool, profile, schema, protocol version, and public MCP type remains available;
14. package and single-file MCP transcripts remain equivalent;
15. runtime remains standard-library-only;
16. required CI and manual release policy remain unchanged;
17. `make check` and `make package-check` pass.

After these conditions are met, stop. Do not extend this plan into a plugin architecture, transport expansion, persistent configuration service, new protocol versions, or lazy-loading optimization beyond prerequisites for Plan 026.
