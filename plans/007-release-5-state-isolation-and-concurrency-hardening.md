# Release 5 — State Isolation and Concurrency Hardening

Status: ready for implementation handoff  
Repository: `eggstack/eggcalc`  
Depends on:

- `plans/001-correctness-protocol-hardening-roadmap.md`
- `plans/003-release-2-mcp-protocol-conformance.md`
- `plans/005-releases-1-3-correctness-closure-pass.md`
- `plans/006-release-4-runtime-compatibility-and-capability-negotiation.md`

Primary objective: eliminate process-global policy mutation and shared mutable user state so ordinary library use, CLI execution, MCP sessions, and embedded applications can coexist safely in one process.

## 1. Problem statement

Eggcalc has evolved from a primarily process-oriented CLI into a reusable Python library and a stateful MCP server. Several existing design choices remain process-global or module-global:

- evaluator policy can be changed for MCP operation;
- user configuration can mutate shared registries;
- caches may outlive the configuration or instance that produced them;
- tool registration and execution policy are not fully owned by explicit server objects;
- sessionless compatibility paths make lifecycle bypass possible;
- reload and test isolation have required manual restoration of module objects;
- concurrency behavior is difficult to reason about because ownership boundaries are implicit.

These properties are acceptable for a one-shot CLI but unsafe for embedding, long-running MCP use, multiple sessions, test parallelism, and applications that need independent calculator instances.

Release 5 must establish explicit ownership of mutable state and policy. The result must support multiple independent instances in the same process without cross-talk.

## 2. Target architecture

The intended ownership model is:

```text
McpServer
├── immutable McpServerConfig
├── RuntimeCapabilities
├── ToolRegistry
├── ToolExecutor
├── ConfigSnapshot / ConfigManager
├── dedicated evaluator policy
└── creates McpSession instances
    ├── lifecycle state
    ├── negotiated protocol/client metadata
    ├── cancellation state
    ├── rate-limit state
    └── session-local request bookkeeping

EggCalcApp / evaluator instance
├── immutable or copy-on-write policy
├── constants/functions/units snapshot
├── cache namespace or generation
└── no dependency on MCP globals
```

The precise class names may differ, but ownership must be explicit and testable.

## 3. Scope

This release includes:

- explicit MCP server configuration;
- server-owned tool registry and executor;
- dedicated MCP evaluator policy;
- session-local lifecycle, cancellation, and request state;
- atomic configuration loading and snapshot application;
- safe import-error handling for optional user configuration;
- cache invalidation or generation-based cache separation;
- multi-instance and multi-session concurrency tests;
- saturation, timeout-storm, cancellation, and shutdown behavior;
- deprecation progression for sessionless request handling.

This release does not include:

- removing eager `eggcalc.exact` imports, which belongs to Release 6;
- structural unit-dimension migration;
- adding new tools;
- changing the selected MCP protocol revisions;
- replacing stdio transport;
- network transports;
- durable persistence of session state;
- distributed execution.

## 4. Invariants

The implementation must preserve these invariants:

1. Starting or importing MCP code does not alter ordinary calculator behavior.
2. Two `EggCalcApp` instances can hold different user constants/functions/configuration.
3. Two MCP server instances can use different profiles, limits, registries, and evaluator policies.
4. Two MCP sessions on one server do not share cancellation or lifecycle state.
5. Configuration changes become visible atomically, never field-by-field.
6. Cached results are never reused under a different configuration or evaluator policy.
7. A failed configuration load leaves the prior valid snapshot active.
8. Internal import failures from a configuration module are not mistaken for “configuration missing.”
9. Shutdown reclaims workers, subprocesses, and session state.
10. The generated single-file artifact preserves the same isolation guarantees where the relevant surface exists.

## 5. Workstream A — Inventory and classify mutable global state

Before refactoring, create a repository-level inventory of mutable state in:

- evaluator modules;
- normalization modules;
- units/constants/functions registries;
- configuration loading;
- caches;
- MCP server and tools modules;
- rate limiting;
- cancellation tracking;
- worker pools and orphan-process tracking;
- generated single-file aliases and assembly behavior.

For each stateful object, record:

- current owner;
- mutation sites;
- readers;
- lifecycle;
- thread/process safety;
- whether it is policy, user state, cache, telemetry, or protocol state;
- target owner after Release 5.

This inventory may be committed as an implementation note or embedded in architecture documentation.

### Acceptance for Workstream A

- every mutable module-level object in MCP, evaluator, configuration, and cache paths is classified;
- no mutable state is left without an explicit ownership decision;
- process-wide constants and immutable lookup tables are distinguished from mutable state and need not be moved.

## 6. Workstream B — Introduce `McpServerConfig`

Create an immutable configuration object containing server policy that is currently scattered across environment reads and module-level constants.

Candidate fields:

- enabled tool profile;
- schema detail level;
- request/input/output limits;
- rate-limit policy;
- worker counts;
- timeout limits;
- orphan-process limits;
- supported protocol versions;
- random/side-effect policy;
- config-loading policy;
- runtime capabilities.

### Requirements

- construct once at server creation;
- validate and clamp values in one place;
- do not re-read environment variables per request;
- expose a deterministic diagnostic representation;
- remain immutable after construction;
- support direct construction in tests without environment mutation;
- preserve current defaults unless a documented correction is required.

Environment variables may remain an input adapter:

```python
config = McpServerConfig.from_environment()
server = McpServer(config=config)
```

They must not remain the authoritative runtime state.

## 7. Workstream C — Explicit `McpServer` ownership

Introduce or complete an explicit server object that owns:

- `McpServerConfig`;
- runtime capabilities;
- tool registry;
- tool executor;
- evaluator instance/policy;
- configuration snapshot manager;
- shared bounded worker resources;
- session creation;
- shutdown.

Suggested API:

```python
server = McpServer(config, registry=registry)
session = server.create_session()
response = server.handle_message(session, request)
server.close()
```

The exact API may differ, but the following must be impossible or deprecated:

- request dispatch without an explicit server owner;
- hidden use of a module-global default session for new code;
- mutation of calculator globals during server initialization;
- per-request construction of expensive registries or worker pools.

### Sessionless compatibility

The deprecated `handle_request(request, session=None)` path must progress toward removal.

At minimum in Release 5:

- internally route legacy calls through one explicit compatibility server object;
- emit `DeprecationWarning` consistently;
- document removal timing or next-major behavior;
- ensure tests for production paths never use the compatibility route;
- ensure compatibility state cannot affect explicitly constructed servers.

Removal is allowed if semantic-versioning policy and migration documentation support it.

## 8. Workstream D — Dedicated MCP evaluator policy

MCP must use a dedicated evaluator or application instance configured with MCP-safe policy:

- randomness disabled or explicitly rejected;
- side-effecting/user-extension behavior disabled where required;
- resource limits fixed by server config;
- no mutation of ordinary package-level evaluator behavior;
- no reliance on a process-global “MCP mode” flag for semantics.

### Required tests

In one process:

1. create an ordinary application instance that permits its normal documented behavior;
2. create an MCP server with restricted behavior;
3. execute both in alternating order;
4. prove neither changes the other;
5. destroy the MCP server;
6. prove ordinary behavior remains unchanged.

Also test the reverse construction order.

## 9. Workstream E — Tool registry and executor ownership

### E1. Tool registry

Create an explicit registry object or immutable mapping that owns:

- tool names;
- handlers;
- input schemas;
- output schemas;
- profiles/tags;
- runtime capability requirements;
- exposure policy.

Requirements:

- registry construction is deterministic;
- profiles are derived from registered tools;
- duplicate tool names fail at construction;
- unavailable capability requirements are resolved at construction;
- registry objects can differ between server instances;
- tests can construct minimal registries;
- global registry data, if retained for compatibility, is immutable.

### E2. Tool executor

The executor must own:

- validation;
- timeout policy;
- worker dispatch;
- cancellation checks;
- result serialization limits;
- error translation;
- cleanup.

The executor must not depend on session globals. Session state must be passed explicitly.

## 10. Workstream F — Atomic configuration snapshots

Replace incremental mutation of global registries with atomic configuration snapshots.

Suggested design:

```python
@dataclass(frozen=True)
class ConfigSnapshot:
    generation: int
    constants: Mapping[str, Any]
    functions: Mapping[str, Callable[..., Any]]
    units: Mapping[str, Any]
    policy: EvaluationPolicy
```

A manager may hold the current snapshot behind a lock:

```python
snapshot = manager.current()
manager.replace(validated_snapshot)
```

### Requirements

- parse and validate into a new snapshot without mutating the active one;
- acquire a lock only for the final swap;
- readers see either the old or new complete snapshot;
- failed loads leave the current snapshot unchanged;
- configuration generation increases monotonically;
- user configuration can be scoped to an application/server instance;
- load-once behavior is explicit and testable;
- reload behavior, if supported, is explicit rather than incidental.

### Import-error handling

Only suppress the precise case where `eggcalc_config` is absent.

Do not suppress:

- syntax errors in the config file;
- imports missing inside the config file;
- runtime exceptions raised by config initialization;
- validation failures.

Tests must distinguish all of these cases.

## 11. Workstream G — Cache isolation and invalidation

Audit every cache affected by:

- constants;
- functions;
- units;
- evaluator policy;
- normalization policy;
- runtime capability;
- tool registry/profile;
- configuration generation.

Choose one consistent model:

### Option 1: Instance-local caches

Each application/server owns its own bounded caches.

Advantages:

- strongest isolation;
- simple correctness model;
- straightforward cleanup.

### Option 2: Generation-keyed shared caches

Cache keys include an immutable configuration/policy generation identifier.

Advantages:

- controlled sharing;
- lower duplication.

Whichever model is selected:

- cache keys must include every semantic input;
- configuration replacement cannot return stale results;
- bounded eviction remains enforced;
- clearing one instance must not clear unrelated instance state unless explicitly documented;
- test fixtures must not rely on global cache resets for isolation.

## 12. Workstream H — Session-local protocol state

Verify and complete session ownership of:

- lifecycle state;
- negotiated protocol version;
- client information and capabilities;
- cancellation identifiers;
- rate-limit accounting if policy is per-session;
- in-flight request bookkeeping;
- close state;
- session-local diagnostics.

### Multi-session requirements

- cancelling request ID `X` in session A does not cancel `X` in session B;
- initializing session A does not initialize session B;
- closing session A does not affect session B;
- rate limiting follows the documented server/global/session scope;
- duplicate request IDs across independent sessions are allowed unless explicitly prohibited;
- session objects cannot be reused after close.

## 13. Workstream I — Concurrency and lifecycle hardening

Add deterministic concurrency tests for:

### I1. Multi-instance behavior

- two application instances with conflicting constants;
- two server instances with different profiles;
- server and ordinary library use in parallel;
- configuration reload in one instance while another evaluates;
- cache clearing in one instance while another is active.

### I2. Multi-session behavior

- simultaneous initialization;
- simultaneous tool calls;
- same request IDs in different sessions;
- cancellation isolation;
- session close during in-flight work;
- malformed traffic in one session while another remains healthy.

### I3. Saturation behavior

- worker pool at capacity;
- queue limit reached;
- repeated timeouts;
- cancellation storm;
- oversized-output storm;
- regex or subprocess orphan limits;
- clean rejection without unbounded thread/process creation.

### I4. Shutdown behavior

- close with no active work;
- close with queued work;
- close with timed-out work;
- repeated close is idempotent;
- no workers remain after shutdown;
- no orphan subprocesses remain after bounded cleanup;
- post-close requests fail deterministically.

Use barriers, events, and bounded queues rather than sleep-based timing wherever possible.

## 14. Workstream J — Error and observability contract

Define stable diagnostics for:

- configuration load failure;
- unavailable or closed server/session;
- executor saturation;
- cancellation;
- timeout;
- shutdown;
- stale configuration generation where relevant;
- internal import error.

Diagnostics must not leak secrets from user configuration.

Add server/application diagnostic output containing:

- configuration generation;
- active profile;
- registry tool count;
- worker limits and active counts;
- session count where safe;
- cache sizes where safe;
- runtime capability summary.

The diagnostic representation must be deterministic and JSON serializable.

## 15. Workstream K — Generated single-file compatibility

The single-file build may not expose every embedding API, but it must preserve equivalent behavior for supported surfaces.

Verify:

- no assembly-time alias reintroduces module-global mutable policy;
- MCP package and single-file modes use explicit session/server ownership;
- generated code contains the required registry/config/evaluator definitions in valid order;
- package and single-file transcript results match;
- state-isolation regression tests run against the single-file artifact where practical;
- unsupported embedding APIs are clearly documented rather than silently divergent.

## 16. Documentation and migration

Update:

- README;
- Python API docs;
- MCP docs;
- evaluator/configuration architecture docs;
- AGENTS.md;
- changelog;
- migration notes;
- generated inventories where affected.

Document:

- instance ownership model;
- server/session construction;
- sessionless API deprecation/removal;
- configuration snapshot semantics;
- reload semantics;
- cache isolation model;
- thread-safety guarantees;
- shutdown responsibilities;
- unsupported patterns.

## 17. Test plan

At minimum, add tests for:

- immutable `McpServerConfig`;
- environment adapter versus explicit config;
- two server instances with different configs;
- two registries with different tools;
- ordinary evaluator versus MCP evaluator isolation;
- atomic configuration replacement;
- failed configuration preserving prior snapshot;
- absent config versus internal config import failure;
- generation-aware or instance-local cache behavior;
- two sessions with same request IDs;
- cancellation isolation;
- lifecycle isolation;
- saturation bounds;
- timeout storms;
- clean and idempotent shutdown;
- package/single-file MCP parity;
- no global behavior mutation after server creation or close.

Recommended commands:

```bash
python -m ruff check .
python -m black --check .
python build_single.py
python scripts/smoke_release_surfaces.py
python -m pytest tests/ -v
mypy eggcalc --ignore-missing-imports
```

Add repeated and stress-focused test invocations for the concurrency suites. Keep stress bounds small enough for CI but large enough to expose sharing and cleanup bugs.

## 18. Explicit acceptance criteria

Release 5 is complete only when all criteria below are met.

### Ownership

- [ ] MCP request dispatch is owned by an explicit server object.
- [ ] Server policy is represented by immutable `McpServerConfig` or an equivalent object.
- [ ] Tool registry and executor ownership are explicit.
- [ ] Production paths do not use the sessionless compatibility route.
- [ ] Mutable process-global state in evaluator, MCP, configuration, and cache paths has been removed or justified as safe.

### Behavioral isolation

- [ ] Starting, using, and closing MCP does not change ordinary library behavior.
- [ ] Two application instances can use conflicting user configuration without cross-talk.
- [ ] Two server instances can use different profiles, limits, and registries.
- [ ] Two sessions do not share lifecycle or cancellation state.
- [ ] Configuration changes in one instance do not affect another.

### Configuration correctness

- [ ] Configuration is parsed and validated before activation.
- [ ] Activation is atomic.
- [ ] Failed activation leaves the prior snapshot intact.
- [ ] Missing `eggcalc_config` is distinguished from failures inside it.
- [ ] Configuration generation or equivalent invalidation semantics are explicit.

### Cache correctness

- [ ] Cached results cannot cross configuration or policy boundaries.
- [ ] Cache ownership or generation-keying is documented and tested.
- [ ] Cache bounds remain enforced.
- [ ] Clearing or replacing one instance’s state does not corrupt another instance.

### Concurrency and lifecycle

- [ ] Multi-instance and multi-session concurrency suites pass reliably.
- [ ] Saturation produces bounded rejection rather than unbounded resource growth.
- [ ] Cancellation and timeout storms remain bounded.
- [ ] Shutdown is deterministic and idempotent.
- [ ] No worker threads/processes or tracked orphan subprocesses remain after shutdown tests.

### Compatibility and documentation

- [ ] Package and generated single-file MCP transcripts match.
- [ ] Sessionless API deprecation/removal is documented with migration guidance.
- [ ] Architecture documentation accurately describes ownership and thread-safety guarantees.
- [ ] Changelog records public API and behavior changes.

### Evidence

- [ ] A Release 5 evidence file records full-suite, stress-suite, platform, and release-surface results.
- [ ] Test evidence includes multiple independent server and session instances.
- [ ] Any residual shared state is explicitly listed with justification and tests.

## 19. Recommended implementation sequence

1. Inventory mutable global state and define target ownership.
2. Add immutable `McpServerConfig` and environment adapter.
3. Introduce explicit `McpServer` ownership around existing dispatch.
4. Move tool registry and executor under the server.
5. Introduce the dedicated MCP evaluator policy.
6. Replace configuration mutation with atomic snapshots.
7. Isolate or generation-key caches.
8. Complete session-local protocol and cancellation state.
9. Add multi-instance, multi-session, saturation, and shutdown tests.
10. Align generated single-file behavior.
11. Update documentation and migration notes.
12. Produce Release 5 verification evidence.

## 20. Handoff notes

Implement this release incrementally. Preserve behavior behind explicit objects before deleting compatibility globals. Avoid a single large rewrite of the MCP server.

A practical sequence is to wrap current behavior in explicit ownership, add isolation tests, then move state one category at a time. Each state move should land with tests proving that two independent instances no longer interfere.

Do not begin Release 6 import-graph or structural-unit work until Release 5 isolation tests are stable. Those refactors will be substantially safer once mutable ownership boundaries are explicit.
