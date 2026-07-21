# Releases 4–5 Final Closure Pass

Status: ready for implementation handoff  
Repository: `eggstack/eggcalc`  
Depends on:

- `plans/006-release-4-runtime-compatibility-and-capability-negotiation.md`
- `plans/007-release-5-state-isolation-and-concurrency-hardening.md`
- `plans/008-releases-4-5-corrective-closure-pass.md`

Primary objective: close the remaining Release 4 and Release 5 correctness gaps without expanding scope into Release 6. This pass must make compatibility behavior isolated, server profiles authoritative at call time, registry and configuration state deeply immutable, configuration snapshots operationally applied, executor diagnostics truthful, permissive evaluator state instance-owned, session ownership explicit, and cross-platform Python 3.11 evidence complete.

## 1. Current state

The preceding corrective pass successfully established the primary production ownership chain:

```text
stdio main()
└── McpServer
    ├── McpServerConfig
    ├── ToolRegistry
    ├── ToolExecutor
    ├── Evaluator
    ├── ConfigManager
    └── McpSession
```

Production stdio now constructs one explicit server, routes requests through `server.handle_request()`, applies server-owned request and rate limits, and closes the server in a `finally` block.

The remaining work is smaller and must remain tightly bounded to the following defects:

1. the deprecated module-level compatibility dispatcher still mutates package-global evaluator policy;
2. server profiles are respected by `tools/list` but are not enforced by `tools/call`;
3. `ConfigSnapshot` copies dictionaries but still exposes mutable mappings;
4. `ToolRegistry` protects only top-level mappings while nested schemas, metadata, and profile lists remain mutable;
5. configuration snapshots are stored but are not parsed, semantically validated, or atomically applied to the owning evaluator/tool context;
6. executor active and queued diagnostics do not represent actual worker lifecycle state;
7. permissive evaluator instances share one process-global random generator;
8. sessions are not bound to one owning server and directly closed sessions remain counted as live;
9. Release 4 lacks real Python 3.11 macOS/Windows CI evidence, and Release 4/5 evidence files are stale.

This document is the final closure gate for this line of work. Release 6 must remain blocked until every mandatory criterion in section 15 is satisfied.

## 2. Required end state

At completion, all of the following must be true:

1. Production stdio and deprecated compatibility calls both use explicit server ownership.
2. No MCP entry point mutates `_mcp_mode`, `_default_evaluator`, or package-global evaluator flags.
3. A tool omitted by the active server profile cannot be invoked directly.
4. `tools/list`, `profiles/list`, validation, suggestions, and execution agree on one authoritative registry and profile.
5. Registry constructor inputs and accessor return values cannot mutate an existing registry, including nested values.
6. Configuration snapshots are deeply immutable.
7. Configuration parsing and semantic validation complete before activation.
8. Activating a snapshot atomically updates the owning server/evaluator context without mutating package globals.
9. Failed parsing, validation, or activation preserves the complete prior state and generation.
10. Executor diagnostics distinguish accepted, queued, and running work truthfully.
11. Timed-out running handlers continue to count as running and continue consuming capacity until actual completion.
12. Each permissive evaluator owns independent random state.
13. Every `McpSession` has exactly one server owner, cannot be dispatched through another server, and is removed from live-session tracking when closed.
14. Python 3.11 passes on Linux, macOS, and Windows.
15. Evidence files record actual commit SHAs, workflow/run identifiers, job outcomes, pass/skip counts, and release-surface results.
16. Package and generated single-file MCP behavior remain equivalent.

## 3. Scope boundaries

This pass includes only:

- compatibility dispatcher containment;
- profile enforcement at call time;
- deep registry immutability and registry consistency validation;
- deep configuration snapshot immutability;
- instance-scoped configuration parsing, validation, activation, and rollback;
- truthful executor state accounting;
- evaluator random-state isolation;
- session ownership and live-session tracking;
- Python 3.11 macOS and Windows CI lanes;
- Release 4 and Release 5 evidence refresh;
- package/single-file parity for the affected surfaces.

This pass does not include:

- Release 6 eager-import or import-graph restructuring;
- structural unit-dimension migration;
- broad unit subsystem redesign;
- new MCP transports;
- new protocol revisions;
- new calculator or inspection tools;
- persistent or distributed configuration;
- process-wide removal of all legacy global APIs;
- performance optimization unrelated to bounded-resource correctness;
- changes to public semantics outside the defects listed above.

## 4. Workstream A — Contain the compatibility dispatcher

### A1. Replace global policy mutation

The deprecated module-level `handle_request(request, session=None)` must stop calling or mutating:

- `_evaluator._mcp_mode`;
- `configure_default_evaluator()`;
- `_default_evaluator` policy flags;
- process-global configuration state.

Replace the compatibility path with one explicit compatibility server owner:

```python
_compat_server: McpServer | None = None
_compat_server_lock = threading.Lock()


def _get_compat_server() -> McpServer:
    ...
```

The exact API may differ, but the compatibility server must:

- use a restricted `McpServerConfig` equivalent to historical MCP-safe defaults;
- own its evaluator, registry, executor, configuration manager, and default compatibility session;
- remain isolated from explicitly constructed servers;
- emit `DeprecationWarning` for sessionless calls;
- support explicit cleanup in tests and interpreter shutdown where practical;
- not be used by production stdio or current documentation examples.

### A2. Compatibility lifecycle

Add a bounded cleanup mechanism such as:

```python
close_compatibility_server()
```

or a private test hook with equivalent behavior.

Requirements:

- repeated close is idempotent;
- subsequent compatibility use either creates a new isolated server or fails according to documented behavior;
- no worker pool is leaked across compatibility tests;
- compatibility sessions use the same lifecycle validation as explicit server sessions where compatible with existing API behavior.

### A3. Compatibility tests

Test, in one process and in both construction orders:

1. evaluate ordinary package randomness or side-effect behavior;
2. call the deprecated compatibility MCP API;
3. prove ordinary package behavior is unchanged;
4. create an explicit permissive server and restricted server;
5. prove the compatibility server does not affect either;
6. close the compatibility server;
7. prove explicit servers and package defaults remain unchanged.

### Acceptance for Workstream A

- module-level compatibility dispatch does not set `_mcp_mode`;
- module-level compatibility dispatch does not call `configure_default_evaluator()`;
- compatibility requests execute through an explicit `McpServer`;
- compatibility state cannot alter explicit servers;
- compatibility cleanup is deterministic and idempotent;
- production stdio remains independent of the compatibility server;
- single-file compatibility behavior matches package behavior where exposed.

## 5. Workstream B — Enforce profile authority during tool calls

### B1. Define one call-visibility decision

Add one server-owned visibility check, for example:

```python
server.registry.is_tool_visible(name, profile=server.config.profile)
```

or an equivalent method on `ToolRegistry`/`ToolExecutor`.

The same visibility rules must govern:

- `tools/list`;
- `profiles/list`;
- `tools/call`;
- direct server-owned executor entry points, if public;
- close-match suggestions;
- diagnostics that report available tools.

### B2. Call-time rejection

Before handler lookup or execution, reject a tool outside the configured profile.

Required behavior:

- return a stable JSON-RPC error;
- use the existing profile-violation error shape where practical;
- include the configured profile name without leaking unrelated hidden tool details;
- do not submit work to the executor;
- do not increment queued/running counters;
- do not consume cancellation records;
- do not fall back to module-level profile state.

### B3. Per-request list profile overrides

If `tools/list` continues to allow a per-request `profile` filter, document that this is an inventory filter only and does not change call authority.

A client must not be able to:

1. list a broader profile using a request override; then
2. call tools outside `server.config.profile`.

Alternatively, remove per-request profile broadening and allow only equal-or-narrower filtering. Select one behavior and test it explicitly.

### B4. Registry/profile consistency

At `ToolRegistry` construction, validate:

- every profile tool exists in handlers;
- every profile tool has a schema when schemas are required for exposed tools;
- profile lists contain no duplicates;
- hidden tools are not accidentally exposed by the `full` profile derivation;
- handler/schema name mismatches are rejected or explicitly classified as hidden/internal;
- metadata references only known tools, unless a documented internal-only case exists.

### Acceptance for Workstream B

- every tool returned by default `tools/list` is callable under the same server config;
- every callable tool is present in the corresponding default list unless explicitly internal and documented;
- profile-hidden tools return a stable rejection before execution;
- two servers with conflicting profiles enforce their profiles independently;
- custom registries do not consult global profiles;
- list overrides cannot broaden call authority;
- package and single-file profile enforcement match.

## 6. Workstream C — Deep-freeze `ToolRegistry`

### C1. Freeze nested values

Top-level `MappingProxyType` is insufficient because nested schema dictionaries, metadata dictionaries, and profile lists remain mutable.

Convert registry data into immutable owned structures. Acceptable approaches include:

- recursive immutable mappings plus tuples/frozensets;
- deep copies retained privately with accessor methods returning immutable copies/views;
- frozen schema/profile value objects;
- an explicit mutable builder followed by a frozen registry.

The selected representation must preserve JSON serialization where required by MCP output.

### C2. Constructor-input isolation

After construction, mutating any original input must not alter the registry:

- handler mapping;
- schemas and nested `inputSchema`/`properties` objects;
- metadata and nested lists/dictionaries;
- profiles and profile lists.

### C3. Accessor isolation

Callers must not be able to mutate registry state through:

- `.handlers`;
- `.schemas`;
- `.metadata`;
- `.profiles`;
- `get_schema()`;
- `get_metadata()`;
- `get_profile_tools()`.

Returning a new mutable copy is acceptable when documented, but returning a live mutable internal object is not.

### C4. Deterministic validation errors

Construction failures must identify:

- duplicate tools;
- profile references to unknown tools;
- exposed handlers lacking schemas;
- schemas lacking handlers where not intentionally documentation-only;
- malformed profile values;
- malformed metadata values.

### Acceptance for Workstream C

- registry nested state cannot be changed through retained constructor inputs;
- registry nested state cannot be changed through accessors;
- invalid profile references fail construction;
- minimal custom registries remain supported;
- registry serialization and listing remain deterministic;
- package and single-file registry inventories remain identical.

## 7. Workstream D — Deep-freeze and operationalize configuration snapshots

### D1. Deeply immutable `ConfigSnapshot`

Replace exposed mutable dictionaries with immutable mappings over owned copies.

Candidate shape:

```python
@dataclass(frozen=True)
class ConfigSnapshot:
    generation: int
    constants: Mapping[str, Any]
    functions: Mapping[str, Callable[..., Any]]
    units: Mapping[str, Any]
    policy: EvaluationPolicy
```

Requirements:

- nested values are immutable or defensively copied according to their semantics;
- callers cannot mutate the snapshot through constructor inputs;
- callers cannot mutate the snapshot through returned fields;
- snapshot contents are deterministic and inspectable;
- diagnostics expose only safe summary information, not secret values.

### D2. Configuration candidate model

Introduce an explicit parse/validate phase. The exact names may differ:

```python
candidate = parse_server_config(source)
validated = validate_server_config(candidate, registry=server.registry)
snapshot = manager.build_next(validated)
server.activate_snapshot(snapshot)
```

The candidate must be separate from active state.

Validation must cover at least:

- constant names and supported value types;
- function names, callability, and policy restrictions;
- unit names and normalized unit definitions where instance units are supported;
- policy values;
- duplicate/conflicting names;
- reserved names;
- generation ownership;
- any schema/capability requirements affected by configuration.

### D3. Manager-owned generation

Do not require callers to choose arbitrary generation numbers.

Preferred API:

```python
snapshot = manager.replace_validated(validated)
```

The manager must assign the next monotonic generation under its lock.

If a lower-level `replace(snapshot)` remains public, it must retain strict stale-generation validation and be documented as advanced/internal.

### D4. Atomic activation

Activation must update one owning context atomically.

At minimum, define how a snapshot affects:

- the server evaluator constants;
- evaluator functions;
- evaluator policy if configurable;
- server-local unit definitions or unit context;
- configuration-aware cache generation;
- tool context where tools depend on configured state.

Readers must see either the complete previous snapshot or complete new snapshot, never mixed fields.

Acceptable designs include:

- replacing the server evaluator/tool context object atomically;
- swapping an immutable application context referenced by executor calls;
- replacing immutable registry/evaluator snapshots behind one lock or context variable.

### D5. Rollback behavior

Failures during parsing, validation, context construction, or activation must leave unchanged:

- active snapshot;
- active evaluator/tool context;
- configuration generation;
- cache namespace/generation;
- registry exposure;
- live sessions.

### D6. Legacy global configuration boundary

The existing global CLI/user configuration path may remain for backward compatibility, but:

- explicit `McpServer` instances must not invoke it;
- instance configuration must not mutate global constants, functions, units, aliases, or normalization tables;
- documentation must distinguish global one-shot CLI configuration from isolated server configuration;
- Release 5 evidence must not claim the legacy global loader itself is instance-isolated.

### Acceptance for Workstream D

- `ConfigSnapshot` is deeply immutable;
- manager assigns strictly monotonic generations;
- parse and semantic validation complete before activation;
- activation changes the owning evaluator/tool context atomically;
- failed activation preserves complete prior state and generation;
- two servers can activate conflicting constants/functions without cross-talk;
- two servers can activate conflicting supported unit configuration without cross-talk, or unsupported per-server unit configuration is rejected explicitly and documented;
- instance configuration does not mutate package globals;
- configuration-aware cache results do not cross generations or servers;
- package/single-file supported configuration behavior matches.

## 8. Workstream E — Truthful executor state accounting

### E1. Define executor states

Use explicit counters with precise meanings:

- `accepted_count`: all reservations not yet fully released, if exposed;
- `queued_count`: accepted futures that have not started;
- `active_count`: handlers currently executing;
- optionally `timed_out_running_count`: running handlers whose callers already received timeout responses.

Do not infer queued/running state solely from submission-time arithmetic.

### E2. Worker-wrapper transitions

Move lifecycle transitions into the worker wrapper or an equivalent instrumented future state:

1. reserve capacity before submission;
2. increment queued count after successful submission;
3. when the worker starts, decrement queued and increment active atomically;
4. when the handler exits, decrement active;
5. release total reservation exactly once when the future completes or is cancelled before start.

Protect against:

- submit failure;
- callback registration failure;
- cancellation before start;
- timeout while running;
- handler exception;
- executor shutdown with queued futures;
- duplicate completion callbacks;
- negative counters.

### E3. Timeout semantics

A caller timeout must not imply worker termination.

Required behavior:

- if `Future.cancel()` succeeds before start, queued and reservation state are released exactly once;
- if cancellation fails because execution started, active and total capacity remain consumed until true completion;
- diagnostic counters remain truthful after the timeout response;
- saturation decisions use actual outstanding reservations, not caller wait state.

### E4. Shutdown behavior

Document and test close semantics for:

- no work;
- queued work;
- active work;
- timed-out active work;
- repeated close;
- retained executor references;
- retained sessions.

`close()` must not deadlock indefinitely. If `wait=True` remains, all supported handlers must have bounded execution or subprocess cleanup. If bounded waiting is introduced, document the failure mode and diagnostics.

### E5. Orphan diagnostic correction

The final implementation must either:

1. connect actual evaluator/regex subprocess registration to the owning executor; or
2. remove/rename the per-executor `orphan_count` claim and report the actual process-wide owner accurately.

Do not expose a zero-valued per-server diagnostic that is disconnected from the actual orphan tracking path.

### Acceptance for Workstream E

- queued count changes only when work is truly queued;
- active count changes only while handler code is executing;
- timed-out running work remains active and consumes capacity;
- exact saturation boundary equals workers plus configured queue capacity;
- capacity recovers after true completion/cancellation;
- counters never become negative under repeated stress;
- close cannot recreate a pool;
- close with queued/active/timed-out work follows documented bounded behavior;
- orphan diagnostics correspond to actual tracked subprocesses or are removed/reclassified;
- package and single-file executor behavior match.

## 9. Workstream F — Isolate evaluator random state

### F1. Instance-owned generator

Each `Evaluator` must own a `random.Random` instance when randomness is permitted.

Suggested shape:

```python
class Evaluator:
    def __init__(..., random_seed: int | None = None):
        self._random = random.Random(random_seed)
```

Random functions must resolve through the current evaluator context rather than a module-global generator:

- `random`;
- `randint`;
- `randrange`;
- `uniform`;
- `randn`;
- `gauss`;
- `seed`.

### F2. Function binding

Because `FUNCTIONS` currently contains module-level random helpers, choose one explicit mechanism:

- bind evaluator methods into each instance’s function map;
- resolve the active evaluator through the existing evaluator context variable;
- construct closures bound to the evaluator instance.

The design must work under:

- direct `Evaluator.evaluate()`;
- `evaluate_raw()`;
- timeout subprocess execution;
- MCP executor thread context;
- generated single-file mode.

### F3. Determinism and isolation tests

Test:

- two evaluators seeded identically produce the same sequence independently;
- advancing evaluator A does not advance evaluator B;
- reseeding A does not affect B;
- two permissive MCP servers remain independent;
- restricted servers continue to reject random calls;
- package default evaluator behavior remains backward compatible;
- timeout/subprocess evaluation preserves documented seed behavior or explicitly documents per-call subprocess isolation.

### Acceptance for Workstream F

- no explicit evaluator uses the module-global random generator;
- permissive servers have independent random sequences;
- restricted servers reject random functions before state changes;
- compatibility server randomness does not affect package defaults;
- random-state behavior is documented and covered in package/single-file parity tests.

## 10. Workstream G — Enforce session ownership and live tracking

### G1. Bind session to owner

When `McpServer.create_session()` creates a session, bind it to that server using one of:

- a private owner token;
- a weak reference to the server;
- an opaque server identifier;
- an internal registry membership check plus identity token.

`server.handle_request(request, session=...)` must reject:

- a session owned by another server;
- a session already closed;
- a session whose owner was closed;
- an arbitrary unowned session, unless an explicit adoption API exists.

Any adoption API must be deliberate, one-time, and documented. Silent rebinding is prohibited.

### G2. Session close callback

Closing a session directly must remove it from its owner’s live-session registry.

Requirements:

- session close is idempotent;
- close does not require holding locks in an order that can deadlock with server close;
- server diagnostics count only live owned sessions;
- server close closes and removes all remaining sessions;
- closed sessions cannot dispatch ping, notifications, or tool calls unless a specific protocol rule requires a final close acknowledgement.

### G3. Concurrency behavior

Test concurrent:

- session creation;
- session close;
- server close;
- request dispatch racing with session close;
- foreign-session dispatch attempts;
- duplicate request IDs on different sessions.

### Acceptance for Workstream G

- each session has exactly one owner;
- foreign sessions are rejected deterministically;
- closed sessions cannot dispatch;
- directly closing a session decrements `session_count`;
- server close leaves `session_count == 0`;
- no deadlock occurs under concurrent session/server close;
- package and single-file session behavior match.

## 11. Workstream H — Complete Release 4 CI evidence

### H1. Minimum-runtime matrix

Update CI so Python 3.11 runs on:

- `ubuntu-latest`;
- `macos-latest`;
- `windows-latest`.

Linux may continue testing 3.12–3.14. Additional macOS/Windows 3.12 lanes are optional and must not replace minimum-version coverage.

### H2. Platform-sensitive checks

Ensure the Python 3.11 macOS and Windows lanes cover:

- full unit/integration suite;
- MCP stdio transcript tests;
- generated single-file build and smoke;
- path and newline tests;
- multiprocessing/timeout tests;
- broken-pipe/closed-stream behavior where supported;
- editable install or wheel install surface as assigned by the matrix;
- capability JSON output.

### H3. Evidence capture

Update `docs/release_4_evidence.md` only after a completed green workflow.

Record:

- exact tested commit SHA;
- workflow run ID;
- stable GitHub run URL or documented identifier;
- each relevant job name and result;
- OS and Python version;
- collected/passed/skipped/failed counts per minimum-runtime lane;
- reason for each skip category;
- package build, wheel install, console script, single-file, and MCP transcript results;
- exact capability output for Linux/macOS/Windows where materially different;
- repeated timeout-test result on macOS;
- Windows path/newline/subprocess result.

No result may be marked `expected`.

### Acceptance for Workstream H

- Python 3.11 Linux job passes;
- Python 3.11 macOS job passes;
- Python 3.11 Windows job passes;
- workflow identifiers and job results are recorded;
- no mandatory feature is skipped on Python 3.11;
- all release surfaces pass in clean or controlled environments;
- Release 4 evidence matches the tested commit.

## 12. Workstream I — Refresh Release 5 evidence and documentation

### I1. Re-run all verification

At the final implementation commit, run:

```bash
python -m ruff check .
python -m black --check .
mypy eggcalc --ignore-missing-imports
python build_single.py
python scripts/generate_mcp_docs.py --check
python scripts/smoke_release_surfaces.py
python -m pytest tests/ -v
python -m build
```

Run the focused closure suites repeatedly using an existing stress runner, `pytest-repeat`, or a bounded shell loop:

- compatibility isolation;
- profile enforcement;
- registry deep immutability;
- configuration activation/rollback;
- executor counter transitions;
- timeout saturation;
- random-state isolation;
- session ownership/close races;
- package/single-file parity.

### I2. Correct evidence claims

Update `docs/release_5_evidence.md` with:

- current commit SHA;
- current total test counts;
- focused closure suite counts;
- repeated stress-run counts;
- package and single-file build/transcript results;
- real platform CI results or references to Release 4 evidence;
- exact residual shared-state list;
- explicit distinction between compatibility-only globals and production explicit-server state.

Do not claim:

- deep immutability unless nested mutation tests pass;
- atomic configuration application unless evaluator/tool state is actually swapped;
- profile isolation unless hidden direct calls are rejected;
- truthful active/queued diagnostics unless barrier-based tests prove transitions;
- per-server orphan ownership unless actual registration is connected;
- full random isolation while explicit evaluators share a generator.

### I3. Documentation updates

Update as required:

- `README.md`;
- `docs/mcp.md`;
- `architecture/mcp.md`;
- `architecture/mutable_state_inventory.md`;
- configuration/API documentation;
- `AGENTS.md`;
- `CHANGELOG.md`;
- `docs/release_4_evidence.md`;
- `docs/release_5_evidence.md`.

The final state inventory must classify every residual global as one of:

- immutable lookup data;
- process-wide bounded infrastructure;
- compatibility-only state;
- legacy one-shot CLI state;
- deferred Release 6 concern;
- removed.

“Safe under singleton usage” is not an acceptable justification for any state involved in the explicit multi-server guarantee.

### Acceptance for Workstream I

- evidence counts match the final tested commit;
- all checked criteria correspond to actual implementation paths;
- residual globals have precise ownership and concurrency justification;
- compatibility-only state is not described as production state;
- documentation examples use explicit servers;
- migration/removal timing for the deprecated dispatcher is documented;
- changelog accurately records behavior and API changes.

## 13. Required test matrix

### 13.1 Compatibility isolation

- deprecated dispatcher uses compatibility server;
- no `_mcp_mode` mutation;
- no default evaluator reconfiguration;
- compatibility cleanup is idempotent;
- explicit servers remain unaffected;
- package defaults remain unaffected;
- reverse construction order.

### 13.2 Profile authority

- hidden tool absent from list and rejected on call;
- visible tool listed and callable;
- two servers with conflicting profiles;
- custom registry profile enforcement;
- per-request list override cannot broaden call authority;
- rejection occurs before executor submission/counter changes.

### 13.3 Registry immutability

- mutate original nested schema after construction;
- mutate original metadata after construction;
- mutate original profile list after construction;
- attempt mutation through each accessor;
- unknown profile tool rejected;
- handler/schema inconsistency rejected;
- deterministic inventory order.

### 13.4 Configuration ownership

- mutate original snapshot constructor dictionaries;
- attempt mutation through snapshot fields;
- parse failure preserves prior state;
- semantic validation failure preserves prior state;
- activation failure preserves prior state;
- monotonic manager-owned generation;
- conflicting constants across servers;
- conflicting functions across servers;
- unit configuration isolation or explicit unsupported error;
- cache result isolation by server and generation.

### 13.5 Executor accounting

Use events/barriers, not sleeps, to prove:

- accepted-but-not-started work increments queued only;
- started work transitions queued to active;
- completed work decrements active and total;
- timeout while running retains active and capacity;
- cancellation before start releases queued and capacity once;
- exact worker-plus-queue saturation boundary;
- submit failure cleanup;
- callback/handler exception cleanup;
- repeated stress leaves all counters zero;
- no counter becomes negative.

### 13.6 Random isolation

- identical seeds yield identical independent sequences;
- advancing one evaluator does not advance another;
- reseeding one evaluator does not reseed another;
- permissive server independence;
- restricted server rejection;
- compatibility server independence;
- timeout/subprocess documented behavior.

### 13.7 Session ownership

- foreign session rejected;
- unowned session rejected or deliberately adopted;
- closed session rejected;
- owner server close invalidates sessions;
- direct session close decrements count;
- concurrent close/create/dispatch stress;
- duplicate IDs isolated across sessions.

### 13.8 Release surfaces

- source checkout import;
- editable install;
- wheel build and clean install;
- `python -m eggcalc`;
- `calc` console script;
- direct Python API;
- generated `eggcalc.py`;
- package MCP stdio;
- single-file MCP stdio;
- package/single-file inventory parity;
- package/single-file transcript parity;
- capability JSON parity except documented mode field.

## 14. Recommended implementation sequence

Keep commits reviewable and independently testable.

1. `test: expose final releases 4-5 closure gaps`
   - add failing compatibility, profile-call, deep-mutation, counter, random, and session-owner tests.

2. `refactor(mcp): isolate deprecated compatibility dispatcher`
   - add compatibility server ownership and cleanup;
   - remove global evaluator mutation from compatibility calls.

3. `fix(mcp): enforce server profile during tool calls`
   - centralize visibility decision;
   - add registry/profile consistency validation.

4. `refactor(mcp): deep-freeze tool registry`
   - recursively own/freeze schemas, metadata, and profiles;
   - update accessors and serialization.

5. `refactor(config): activate immutable instance snapshots`
   - deep-freeze snapshots;
   - add parse/validate/build-next/activate path;
   - add rollback and cache-generation behavior.

6. `fix(mcp): make executor diagnostics lifecycle-accurate`
   - queued/active transitions in worker wrapper;
   - exact timeout/cancellation accounting;
   - correct orphan diagnostic ownership.

7. `refactor(evaluator): isolate random state per instance`
   - bind random helpers to evaluator context;
   - preserve restricted policy behavior.

8. `fix(mcp): enforce session ownership and live tracking`
   - owner binding;
   - direct close removal;
   - concurrent close tests.

9. `ci: verify python 3.11 on linux macos and windows`
   - update matrix;
   - run and obtain green workflow evidence.

10. `docs: close releases 4-5 evidence`
    - refresh evidence, state inventory, API docs, changelog, and migration notes.

Do not combine all implementation into one large commit. Do not update evidence files to “complete” before the corresponding workflow and full verification pass are finished.

## 15. Explicit final acceptance criteria

This line of work is complete only when every mandatory checkbox below is satisfied.

### Compatibility containment

- [ ] Deprecated module-level dispatch executes through an explicit compatibility `McpServer`.
- [ ] Compatibility dispatch never sets `_mcp_mode`.
- [ ] Compatibility dispatch never reconfigures `_default_evaluator`.
- [ ] Compatibility state cannot affect explicit servers or package defaults.
- [ ] Compatibility cleanup is deterministic and idempotent.
- [ ] Production stdio does not use compatibility state.

### Profile and registry authority

- [ ] Server profile is enforced during `tools/call` before executor submission.
- [ ] Default listed tools and callable tools are identical under one config.
- [ ] List profile overrides cannot broaden call authority.
- [ ] Two conflicting server profiles operate independently.
- [ ] Custom registries never consult global profiles or schemas.
- [ ] Registry nested values cannot be mutated through constructor inputs.
- [ ] Registry nested values cannot be mutated through accessors.
- [ ] Profiles referencing unknown tools fail construction.
- [ ] Handler/schema/profile inconsistencies fail deterministically or are explicitly classified as internal.

### Configuration correctness

- [ ] `ConfigSnapshot` is deeply immutable.
- [ ] Configuration is parsed and semantically validated before activation.
- [ ] Configuration generation is assigned monotonically by the owning manager.
- [ ] Activation atomically updates the owning evaluator/tool context.
- [ ] Failed parsing, validation, or activation preserves prior snapshot, generation, evaluator context, and cache namespace.
- [ ] Two servers can use conflicting supported constants/functions without cross-talk.
- [ ] Per-server unit configuration is isolated or explicitly rejected as unsupported.
- [ ] Instance configuration does not mutate global constants, functions, units, aliases, or normalization state.
- [ ] Cache results cannot cross server or configuration-generation boundaries.

### Executor correctness

- [ ] Queued diagnostics count accepted work that has not started.
- [ ] Active diagnostics count only currently executing handlers.
- [ ] Worker start atomically transitions queued to active.
- [ ] Handler completion releases active and total reservation exactly once.
- [ ] Timed-out running work remains active and consumes capacity until true completion.
- [ ] Cancellation before start releases queued work and capacity exactly once.
- [ ] Saturation rejects exactly at `max_tool_workers + max_tool_queue_size`.
- [ ] Counters never become negative under repeated stress.
- [ ] Close cannot recreate an executor pool.
- [ ] Orphan diagnostics report actual owned processes or are removed/reclassified accurately.

### Evaluator isolation

- [ ] Every explicit evaluator owns independent random state.
- [ ] Seeding one evaluator does not affect another.
- [ ] Two permissive servers have independent random sequences.
- [ ] Restricted servers reject random calls without changing state.
- [ ] Compatibility random behavior does not affect package defaults.
- [ ] Package and single-file random policy behavior match.

### Session ownership

- [ ] Every session has exactly one owning server.
- [ ] Foreign-session dispatch is rejected deterministically.
- [ ] Closed sessions cannot dispatch.
- [ ] Direct session close removes it from live-session tracking.
- [ ] Server close closes and removes all sessions.
- [ ] `session_count` reports live sessions only.
- [ ] Concurrent create/close/dispatch tests complete without deadlock or cross-talk.

### Release 4 evidence

- [ ] Python 3.11 passes on Linux.
- [ ] Python 3.11 passes on macOS.
- [ ] Python 3.11 passes on Windows.
- [ ] Evidence records tested commit SHA, workflow run identifier, and per-job outcomes.
- [ ] No mandatory feature is skipped on the minimum runtime.
- [ ] Wheel, console script, package, single-file, API, and MCP stdio surfaces pass.
- [ ] Capability evidence reflects the current expanded diagnostic fields.
- [ ] No CI result remains marked `expected`.

### Release 5 evidence

- [ ] Evidence test counts match the final commit.
- [ ] Evidence includes focused closure and repeated stress results.
- [ ] Evidence claims match actual production and compatibility paths.
- [ ] Multi-server tests cover profiles, registry schemas, evaluator policy, random state, configuration, and limits.
- [ ] Package and single-file inventories and transcripts match.
- [ ] Residual globals have non-singleton-dependent ownership justification.
- [ ] Architecture and API docs accurately describe immutability, configuration activation, executor diagnostics, and session ownership.

### Final gate

- [ ] Full lint, format, type-check, build, documentation-generation, smoke, test, and package checks pass.
- [ ] GitHub Actions is green for the complete supported matrix.
- [ ] No known Release 4/5 authority, isolation, shutdown, configuration, executor-accounting, profile, session, or evidence discrepancy remains.
- [ ] Release 4 is marked closed.
- [ ] Release 5 is marked closed.
- [ ] Release 6 may begin only after all preceding criteria are satisfied.

## 16. Verification commands

At minimum:

```bash
python -m ruff check .
python -m black --check .
mypy eggcalc --ignore-missing-imports
python build_single.py
python scripts/generate_mcp_docs.py --check
python scripts/smoke_release_surfaces.py
python -m pytest tests/ -v
python -m build
```

Run focused suites repeatedly. Example bounded loop:

```bash
for i in 1 2 3 4 5; do
  python -m pytest \
    tests/test_release5_isolation.py \
    tests/test_mcp_stdio_smoke.py \
    tests/test_config_loading.py \
    tests/test_runtime_capabilities.py \
    -q || exit 1
done
```

Add new focused files to this command if the implementation separates final closure tests into dedicated modules.

Also run and record the full GitHub Actions matrix, including Python 3.11 on Ubuntu, macOS, and Windows.

## 17. Handoff notes

Treat this as a closure pass, not a redesign opportunity.

The implementation agent should:

- begin with failing tests that demonstrate each remaining defect;
- reuse the explicit ownership model already established;
- remove duplicate authority rather than adding another parallel abstraction;
- keep legacy compatibility code visibly separated from production explicit-server code;
- prefer immutable context replacement over incremental mutation;
- use barriers/events for concurrency tests instead of timing sleeps;
- update evidence only after final implementation and CI success;
- stop if a proposed change expands into Release 6 import-graph or broad unit-system work and record that dependency instead.

The line of work exits only when the code, tests, CI, documentation, state inventory, and evidence files all agree on the same ownership and compatibility model.