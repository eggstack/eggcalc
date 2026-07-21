# Releases 4–5 Corrective Closure Pass

Status: ready for implementation handoff  
Repository: `eggstack/eggcalc`  
Depends on:

- `plans/001-correctness-protocol-hardening-roadmap.md`
- `plans/006-release-4-runtime-compatibility-and-capability-negotiation.md`
- `plans/007-release-5-state-isolation-and-concurrency-hardening.md`

Primary objective: make the Release 4 runtime contract independently verifiable and complete the Release 5 migration so explicit server, registry, evaluator, configuration, executor, and session objects are the authoritative production runtime rather than parallel scaffolding around legacy module-global behavior.

## 1. Purpose

Releases 4 and 5 introduced the correct architectural components:

- Python 3.11+ packaging metadata;
- Linux, macOS, and Windows CI configuration;
- immutable runtime capability reporting;
- `McpServerConfig`;
- `McpServer`;
- `ToolRegistry`;
- `ToolExecutor`;
- `ConfigSnapshot` and `ConfigManager`;
- per-server evaluator construction;
- per-session lifecycle and cancellation state;
- saturation, timeout, shutdown, and multi-instance tests.

The remaining problem is authority, not missing class names. Production stdio and several request paths still depend on module-level policy, registries, handlers, limits, evaluator mutation, configuration mutation, or compatibility functions. Some evidence claims therefore describe the intended architecture rather than the complete runtime path.

This pass must close those gaps without beginning Release 6 import-graph, unit-dimension, or broad maintainability work.

## 2. Required end state

At completion, all supported MCP production paths must follow one ownership chain:

```text
main()
└── McpServer(McpServerConfig.from_environment(), RuntimeCapabilities)
    ├── ToolRegistry
    ├── ToolExecutor
    ├── ConfigManager / immutable ConfigSnapshot
    ├── dedicated Evaluator
    └── McpSession
        └── server.handle_request(session, request)
```

The following statements must be true in implementation, not only tests or documentation:

1. Importing MCP code does not mutate process environment or ordinary evaluator policy.
2. Starting stdio MCP does not mutate the package-level default evaluator.
3. `McpServerConfig` controls every server policy field it exposes.
4. `ToolRegistry` is authoritative for listing, validation, profile filtering, and execution.
5. The server-owned evaluator is the evaluator used by MCP math execution.
6. Configuration snapshots are deeply immutable and are applied atomically to the owning instance.
7. Executor saturation and diagnostics represent real queued and running work.
8. A closed server cannot recreate workers through any retained session or executor reference.
9. Release 4 evidence contains actual successful CI results for the supported minimum runtime on Linux, macOS, and Windows.
10. Package and generated single-file MCP behavior remain equivalent.

## 3. Non-goals

Do not include:

- Release 6 eager-import decoupling;
- structural unit dimensions;
- new calculator or inspection tools;
- new MCP transports;
- new MCP protocol revisions;
- removal of all compatibility APIs unless required for correctness;
- broad evaluator API redesign;
- persistent configuration storage;
- distributed execution;
- performance optimization unrelated to correctness or bounded-resource behavior.

## 4. Workstream A — Make `McpServer` the production owner

### A1. Migrate stdio entry point

Replace the current production path that constructs a bare `McpSession` and calls module-level `handle_request()`.

Required shape:

```python
config = McpServerConfig.from_environment()
server = McpServer(config=config, capabilities=detect_capabilities())
session = server.create_session(McpSessionState.UNINITIALIZED)
try:
    ...
    response = server.handle_request(request, session=session)
finally:
    server.close()
```

Requirements:

- `main()` creates exactly one explicit server per stdio connection/process;
- all parsed requests go through that server;
- server shutdown runs on EOF, broken pipe, parse-loop exit, and unexpected failure;
- no production test invokes the sessionless compatibility route;
- the generated single-file MCP entry point uses the same ownership path;
- rate-limit state is assigned an explicit scope and owner.

### A2. Remove import-time process mutation

Remove import-time mutation such as:

```python
os.environ.setdefault("EGGCALC_NO_CONFIG", "1")
```

Configuration suppression for MCP must be represented in `McpServerConfig` or explicit server construction, not a process environment side effect.

Acceptance:

- importing `eggcalc.mcp.server` leaves `os.environ` unchanged;
- importing MCP leaves the package default evaluator flags unchanged;
- tests assert environment and evaluator state before and after import;
- reverse import order is tested.

### A3. Compatibility path containment

The deprecated module-level `handle_request()` may remain for this release only if:

- it owns one explicit compatibility `McpServer` object;
- it never mutates the package default evaluator;
- its state cannot affect explicitly constructed servers;
- its deprecation warning is consistent;
- production stdio and documentation examples do not use it;
- removal timing is documented for the next major release.

## 5. Workstream B — Make server configuration authoritative

Audit every `McpServerConfig` field and connect it to runtime behavior.

At minimum:

- `profile` controls list and call visibility;
- `schema_detail` controls default schema serialization;
- `max_request_bytes` controls stdio envelope size;
- `max_output_bytes` controls tool output serialization;
- `max_requests_per_second` controls documented rate-limit scope;
- `max_request_id_length` controls envelope validation;
- `max_tool_timeout_seconds` controls executor timeouts;
- `max_cancelled_requests` controls each owned session;
- `max_tool_workers` controls the executor pool;
- `max_tool_queue_size` controls accepted queued work;
- `supported_protocol_versions` controls negotiation;
- `allow_random` and `allow_side_effects` control the MCP evaluator;
- config-loading policy controls user configuration behavior without environment mutation;
- runtime capabilities are stored on the server and reported from that snapshot.

Remove or restrict module-level constants that duplicate server-owned policy. Compatibility constants may remain exported but must not be authoritative for explicit servers.

### Acceptance for Workstream B

Construct two servers in one process with conflicting values and prove:

- different protocol-version tuples negotiate differently;
- different profiles list and execute different tools;
- different schema detail defaults produce different list payloads;
- different request/output/timeout/queue limits are enforced independently;
- different evaluator policies produce different MCP math behavior;
- neither server changes the other or the package defaults.

## 6. Workstream C — Make `ToolRegistry` authoritative

### C1. Listing

Refactor tool and profile listing so explicit servers use only their registry.

Requirements:

- `tools/list` iterates `server.registry.schemas` and metadata;
- default profile comes from `server.config.profile`;
- profile filters are validated against `server.registry.profiles`;
- schema detail comes from request override or `server.config.schema_detail`;
- hidden/exposure policy comes from registry metadata;
- custom or minimal registries list only their own tools;
- `profiles/list` derives all data from the same registry and server config.

### C2. Calling

Requirements:

- calls are rejected when a tool is outside the server profile;
- handler lookup comes only from the server registry;
- signature validation uses the selected handler;
- schema validation uses the selected registry schema, not global `TOOL_SCHEMAS`;
- close-match suggestions search only the selected registry;
- unavailable capability requirements are enforced consistently at registry construction or call time;
- listing and calling cannot disagree about tool availability.

### C3. Registry immutability

`ToolRegistry` currently copies top-level mappings but exposes mutable dictionaries.

Choose one bounded correction:

- immutable mappings/tuples; or
- private deep copies with read-only accessors; or
- explicit builder/freeze lifecycle.

Acceptance:

- external mutation of constructor inputs cannot change an existing registry;
- accessors cannot mutate internal registry state accidentally;
- duplicate or inconsistent handler/schema/profile entries fail deterministically;
- profile entries referencing unknown tools fail construction.

## 7. Workstream D — Connect the dedicated evaluator to execution

The server-owned evaluator must be used by MCP math execution.

Implement one explicit mechanism:

1. bind `math_eval` handler to the server evaluator when building the registry;
2. inject evaluator/context into executor calls for handlers declaring that dependency; or
3. create a server-owned tool context passed to all handlers.

Do not rely on:

- `_mcp_mode`;
- `configure_default_evaluator()`;
- mutation of `_default_evaluator`;
- process environment flags for semantics.

Required tests in one process:

- ordinary package evaluation permits its documented default behavior;
- restricted MCP server rejects randomness and side effects;
- permissive explicit server allows configured behavior if supported;
- two servers with opposite policies remain independent;
- construction and destruction order does not matter;
- legacy compatibility calls do not alter package defaults;
- package and single-file results match.

If tools other than `math_eval` depend on evaluator or unit configuration, identify and bind them explicitly in the same context model.

## 8. Workstream E — Complete configuration ownership

### E1. Deeply immutable snapshots

A frozen dataclass containing mutable dictionaries is not an immutable snapshot.

Use immutable or copy-on-write values, for example:

- `MappingProxyType` over owned deep copies;
- immutable mapping wrappers;
- frozen value objects and tuples;
- validated normalized representations.

A caller must not be able to mutate active configuration through retained constructor arguments or returned properties.

### E2. Parse, validate, then swap

Add an explicit instance-scoped configuration path:

```python
candidate = parse_config(source)
validated = validate_config(candidate)
snapshot = ConfigSnapshot.from_validated(validated, generation=next_generation)
manager.replace(snapshot)
server.apply_snapshot(snapshot)
```

Requirements:

- parsing and validation happen before active-state mutation;
- generation increases monotonically inside the manager;
- callers cannot supply arbitrary stale or decreasing generations;
- failed parsing, import, or validation preserves the prior snapshot;
- application updates the owning evaluator/tool context atomically;
- one server/application configuration does not mutate global unit, constant, function, or normalization tables;
- load-once and reload semantics are explicit.

### E3. Legacy user configuration

The module-level `load_user_config()` may remain for CLI/backward compatibility, but Release 5 claims must clearly separate it from isolated application/server configuration.

Requirements:

- MCP never invokes the global loader;
- `McpServer` and `EggCalcApp` use instance-owned snapshots;
- missing `eggcalc_config` is the only suppressed absence case;
- syntax, runtime, internal import, and validation failures propagate;
- documentation distinguishes legacy global CLI configuration from isolated embedding configuration.

## 9. Workstream F — Cache and mutable evaluator state

The corrective pass does not need to remove every package-level compatibility cache, but explicit instances must not depend on semantically unsafe shared caches.

Requirements:

- server-owned evaluator results use an instance-local cache or keys containing the complete immutable policy/config generation;
- two servers with conflicting constants/functions/units cannot share stale results;
- changing one instance's configuration does not clear or alter another instance's cache;
- `EggCalcApp` constants and functions are instance-owned, including class-level dictionary hazards;
- evaluator construction deep-copies mutable registries rather than sharing class dictionaries;
- random state used by explicit evaluators is instance-owned or explicitly synchronized;
- global compatibility cache behavior is accurately documented and not presented as multi-instance isolation.

Tests must cover conflicting constants, functions, units, random seeds, cache hits, cache clearing, and configuration replacement across at least two simultaneous instances.

## 10. Workstream G — Correct executor accounting and lifecycle

### G1. Real running versus queued accounting

Current submission-time counters must be replaced with state that reflects actual execution.

Required model:

- capacity reservation occurs atomically before submission;
- queued count increments on accepted submission;
- queued count decrements when a worker actually starts;
- active count increments inside the worker wrapper;
- active count decrements when the handler exits;
- total reservation is released only when the future is truly complete or cancelled before start;
- timeout response does not falsely release capacity for work still running;
- completion callbacks may be used to release reservations safely.

Acceptance:

- diagnostics distinguish queued and active work correctly under barriers;
- saturation rejects exactly at the configured bound;
- timed-out but still-running handlers continue consuming capacity;
- capacity recovers after actual completion;
- counters never become negative;
- repeated timeout storms cannot create unbounded queued/running work.

### G2. Cancellation semantics

Document whether cancellation means:

- reject before execution;
- cancel queued future;
- cooperative running cancellation;
- response suppression only.

Tests must align with the implemented guarantee and must not imply that `Future.cancel()` stops an already-running thread.

### G3. Closed-state sealing

Add explicit closed state to `ToolExecutor` and close sessions during `McpServer.close()`.

Requirements:

- executor submission after close fails deterministically;
- `_get_executor()` cannot recreate a pool after close;
- retained sessions cannot dispatch through a closed server;
- sessions receive `CLOSED` state on server shutdown;
- server close is idempotent;
- close with queued and running work follows documented bounded behavior;
- no non-daemon worker threads remain after successful shutdown tests.

### G4. Orphan ownership

Either connect process-producing handlers to `ToolExecutor` orphan tracking or remove the nominal per-executor orphan set and define the actual owner accurately.

Acceptance:

- diagnostic `orphan_count` reports the processes the server can actually clean;
- evaluator and regex worker processes are registered with the owning server/executor where practical;
- cleanup tests create and observe the actual tracked path;
- broad `except Exception: pass` blocks in cleanup are narrowed or logged where safe.

## 11. Workstream H — Session-owned policy

Move remaining session policy to the owning server/session:

- cancellation-record bound from `server.config.max_cancelled_requests`;
- negotiated versions from `server.config.supported_protocol_versions`;
- rate-limit accounting according to documented scope;
- request-ID validation limit from server config;
- close state and in-flight bookkeeping;
- session diagnostics where useful.

Requirements:

- `McpSession` does not silently fall back to module-level server policy when attached to an explicit server;
- sessions cannot be shared across unrelated servers without deterministic rejection or explicit rebinding rules;
- closing one session removes it from server tracking;
- server `session_count` reports live sessions, not every session ever created;
- duplicate request IDs across sessions remain isolated.

## 12. Workstream I — Release 4 closure evidence

Release 4 is not formally closed until CI evidence is real rather than marked `expected`.

### I1. Minimum-version platform matrix

Run Python 3.11 on:

- Ubuntu;
- macOS;
- Windows.

Linux may continue Python 3.12–3.14 coverage. Additional platform lanes may use 3.12, but they do not replace minimum-version validation.

### I2. Evidence requirements

Update `docs/release_4_evidence.md` with:

- commit SHA tested;
- workflow run ID and URL or stable run identifier;
- each OS/Python job result;
- full pass/skip/failure counts per relevant lane;
- explanation for every skip category;
- wheel-build and clean-install result;
- console-script result;
- package and single-file MCP transcript result;
- repeated macOS timeout-test result;
- Windows path/newline/subprocess result;
- exact runtime capability output.

Do not use `expected` as a result.

### I3. Capability diagnostic completion

Extend the deterministic capability diagnostic to include:

- Eggcalc package version;
- Python version and implementation;
- platform;
- supported MCP protocol versions;
- package versus single-file mode;
- configured or available tool/profile summary;
- relevant multiprocessing start methods;
- unavailable capabilities, if any.

Keep the runtime-fact object separate from server-specific configured capabilities where appropriate. Avoid falsely describing a per-call probe as a process-cached snapshot.

## 13. Workstream J — Documentation and evidence correction

Update documentation only after runtime paths are authoritative.

Required documents:

- `README.md`;
- `docs/mcp.md`;
- `architecture/mcp.md`;
- `architecture/mutable_state_inventory.md`;
- Python API/configuration documentation;
- `AGENTS.md`;
- `CHANGELOG.md`;
- `docs/release_4_evidence.md`;
- `docs/release_5_evidence.md`.

Correct any existing claims that are not yet true, including:

- production stdio ownership;
- complete evaluator isolation;
- profile independence;
- atomic configuration application;
- cache generation isolation;
- worker/orphan cleanup guarantees;
- completed CI matrix.

The final mutable-state inventory must classify each residual global as:

- immutable lookup data;
- compatibility-only state;
- process-wide infrastructure with bounded semantics;
- deferred Release 6 concern;
- removed.

Singleton-use assumptions are not acceptable justification for a Release 5 multi-instance guarantee.

## 14. Required tests

Add or revise tests for all of the following.

### Production-path tests

- stdio `main()` constructs and uses `McpServer`;
- monkeypatching the module-level compatibility handler does not affect production stdio;
- import does not mutate environment or package evaluator policy;
- EOF and broken-pipe paths close the server.

### Authority tests

- custom server protocol versions control negotiation;
- custom request ID, cancellation, timeout, output, queue, and rate limits are enforced;
- custom registry controls list, profile list, validation, and execution;
- custom schemas are used instead of global schemas;
- profile-hidden tools cannot be called;
- tools listed are exactly tools callable under the same config.

### Evaluator/configuration tests

- server evaluator is actually used by `math_eval`;
- opposite policies on two servers remain independent;
- default evaluator remains unchanged;
- snapshot constructor-input mutation cannot affect active state;
- returned snapshot mappings cannot be mutated;
- failed replacement preserves prior state and generation;
- generation increases monotonically;
- conflicting constants/functions/units and cache results remain isolated.

### Executor tests

- queued and active counters using barriers/events;
- exact saturation boundary;
- running timed-out tasks retain capacity;
- recovery after true completion;
- close prevents pool recreation;
- retained session cannot dispatch after server close;
- sessions become closed;
- actual orphan registration and cleanup;
- repeated stress execution to expose negative/leaked counters.

### Platform and release tests

- Python 3.11 on Linux/macOS/Windows;
- package, editable, wheel, console script, module, API, single-file, and MCP stdio surfaces;
- package/single-file registry and transcript parity;
- deterministic capability output;
- repeated timeout and subprocess tests on macOS and Windows.

Avoid sleep-based synchronization when events, barriers, or instrumented handlers can prove state deterministically.

## 15. Explicit acceptance criteria

This corrective pass is complete only when all criteria below are met.

### Production ownership

- [ ] Production stdio constructs and uses one explicit `McpServer`.
- [ ] Production request dispatch never uses the sessionless compatibility path.
- [ ] Importing MCP does not mutate environment or default evaluator policy.
- [ ] Server shutdown is guaranteed on all loop exits.

### Server policy authority

- [ ] Every `McpServerConfig` field is enforced or removed from the public config.
- [ ] Explicit servers do not use module-level policy constants for negotiation, limits, profiles, schema detail, or cancellation bounds.
- [ ] Two conflicting server configurations operate independently in one process.

### Registry authority

- [ ] Listing, profile listing, validation, close matches, and execution use the server registry.
- [ ] Listed tools and callable tools are identical under one server configuration.
- [ ] Custom/minimal registries do not consult global schemas or profiles.
- [ ] Registry data cannot be mutated externally after construction.

### Evaluator and configuration isolation

- [ ] MCP math execution uses the server-owned evaluator.
- [ ] MCP does not set `_mcp_mode` or reconfigure `_default_evaluator`.
- [ ] Configuration snapshots are deeply immutable.
- [ ] Parsing and validation precede atomic activation.
- [ ] Failed activation preserves the prior complete snapshot.
- [ ] Instance configuration does not mutate global constants, functions, units, or normalization policy.
- [ ] Cache results cannot cross configuration or evaluator-policy boundaries.

### Executor and session correctness

- [ ] Queued and active diagnostics represent actual state.
- [ ] Timed-out running work continues to consume capacity until completion.
- [ ] Saturation is bounded at the configured worker-plus-queue limit.
- [ ] Close prevents executor recreation and further session dispatch.
- [ ] Server close closes owned sessions and releases live-session tracking.
- [ ] Orphan diagnostics and cleanup correspond to actually registered processes.
- [ ] Stress tests leave no negative counters, leaked workers, or unbounded queues.

### Release 4 evidence

- [ ] Python 3.11 passes on Linux, macOS, and Windows.
- [ ] Evidence records real workflow identifiers and job results.
- [ ] No mandatory feature is skipped on the minimum supported runtime.
- [ ] Capability diagnostics include package, protocol, mode, and availability data.
- [ ] Wheel and all release surfaces pass in clean environments.

### Release 5 evidence

- [ ] Evidence claims match the actual production path.
- [ ] Multi-server tests prove different profiles, limits, registries, evaluators, and configuration.
- [ ] Package and single-file MCP transcripts and inventories match.
- [ ] Residual global state has precise, non-singleton-dependent justification.
- [ ] Release 5 can be marked closed without relying on compatibility globals for production behavior.

## 16. Recommended implementation sequence

1. Add failing authority tests for current production stdio and server configuration.
2. Remove MCP import-time environment mutation.
3. Migrate `main()` to explicit `McpServer` ownership and guaranteed close.
4. Route session initialization and envelope validation through server config.
5. Refactor list/profile/call validation to use `ToolRegistry` exclusively.
6. Bind the dedicated evaluator/tool context to actual MCP handlers.
7. Make configuration snapshots deeply immutable and operationally applied.
8. Isolate evaluator registries, random state, and semantic caches for explicit instances.
9. Correct executor reservation, queued/running accounting, timeout capacity, and closed state.
10. Close sessions and connect actual orphan tracking.
11. Rebuild and test the generated single-file artifact.
12. Run Python 3.11 CI on Linux, macOS, and Windows.
13. Correct architecture documents, changelog, state inventory, and evidence records.
14. Run the complete verification matrix and record exact evidence.

## 17. Suggested commit sequence

Keep implementation reviewable:

1. `test: expose releases 4-5 ownership and authority gaps`
2. `refactor(mcp): route stdio through explicit server ownership`
3. `refactor(mcp): make server config and registry authoritative`
4. `refactor(mcp): bind evaluator and immutable configuration context`
5. `fix(mcp): correct executor accounting shutdown and orphan ownership`
6. `test: add multi-server production-path and stress closure coverage`
7. `ci: verify python 3.11 on linux macos and windows`
8. `docs: close releases 4-5 evidence and ownership documentation`

Do not combine all changes into one unreviewable commit.

## 18. Verification commands

At minimum:

```bash
python -m ruff check .
python -m black --check .
mypy eggcalc --ignore-missing-imports
python build_single.py
python scripts/generate_mcp_docs.py --check
python scripts/smoke_release_surfaces.py
python -m pytest tests/ -v
python -m pytest tests/test_release5_isolation.py -v --count=5
python -m build
```

Where `pytest-repeat` is not installed, use a bounded shell loop or an existing repository stress runner without adding a runtime dependency.

Also execute and record the full GitHub Actions matrix with Python 3.11 on all supported operating systems.

## 19. Exit condition

Do not begin Release 6 until this pass is complete.

The pass exits only when:

- Release 4 has real cross-platform minimum-version evidence;
- Release 5 explicit ownership governs production runtime behavior;
- compatibility globals are isolated from explicit servers;
- the evidence documents accurately describe the implementation;
- no known authority, shutdown, configuration, or executor-accounting discrepancy remains.