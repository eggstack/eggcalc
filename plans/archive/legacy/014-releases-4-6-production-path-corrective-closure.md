# Releases 4–6 Production-Path Corrective Closure

Status: implementation handoff  
Repository: `eggstack/eggcalc`  
Baseline reviewed: `3770304bf9cd313284a8a8e3801ebc358f1dfd6e`  
Depends on:

- `plans/013-releases-4-6-definitive-implementation-closure.md`

This plan corrects the incomplete implementation of plan 013. The baseline added useful scaffolding, but several new types are not connected to the active production paths. Completion requires replacing the old authorities and lifecycle paths, not adding more parallel abstractions or tests that only prove symbols exist.

## 1. Corrective objective

Make the plan-013 scaffolding authoritative in production by completing these migrations:

1. make custom MCP profile names registry-owned;
2. make `RuntimeContext` the only active configuration/evaluator state;
3. replace the old executor counters with a real exact-once reservation state machine;
4. route every explicit session through a resolvable live owner server;
5. make `UNIT_DEFINITIONS` the sole built-in unit authority;
6. make `UnitExpression` drive conversion and every `UnitValue` operation;
7. replace the three manual single-file module lists with one dependency-validated manifest;
8. add strict static, artifact-parity, performance, cross-platform CI, and synchronized evidence closure.

The implementation is not complete when a class, enum, fixture, or test has merely been added. It is complete only when the previous production path has been removed, delegated to the new authority, or reduced to a generated compatibility adapter.

## 2. Baseline findings that this plan must correct

At `3770304b`:

- registry schemas and metadata are recursively frozen, but profile selection is still validated against global `TOOL_PROFILES`;
- `RuntimeContext` exists, but requests and the executor continue using `McpServer._evaluator`;
- `apply_configuration()` builds a second evaluator and then mutates the original evaluator with `.update()`;
- `ConfigCandidate` is not the parser result or activation input;
- `EvaluationPolicy` is stored but does not determine runtime evaluator behavior;
- `ReservationState`/`Reservation` are claimed by the commit message, but the active executor still has three independent locks and `max(0, ...)` counter clamping;
- timeout cancellation does not inspect `Future.cancel()` and can leak `_queued_count`;
- sessions still store `_owner_id`, and module-level explicit-session dispatch still calls `session.handle_message(request)` directly;
- `UNIT_DEFINITIONS` exists, but `build_unit_registry()` still derives from `UNIT_BASE` and `TEMPERATURE_CONVERSIONS`;
- `UnitExpression` exists, but `UnitValue` still performs string construction/simplification;
- the Fahrenheit and Rankine `scale_to_base` values are oriented as base-to-unit values rather than unit-to-base values;
- the committed baseline fixture is not actually loaded by the parity test;
- `build_single.py` still uses `MODULES_CALC`, `MODULES_EXACT`, and `MODULES_MCP` as independent authorities;
- strict typing, wheel-consumer verification, parity inventory, controlled performance, and final evidence work are still absent.

## 3. Preserve completed work

Do not regress these changes from the baseline:

- recursive freezing of registry schemas and metadata;
- mutable accessor-copy isolation;
- immutable `tool_names`;
- rejection of non-empty configured units;
- `eggcalc/_version.py` and dynamic package metadata;
- `_protocol.py` protocol authority;
- existing `UnitSpec` data inventory, after correcting semantics;
- existing `UnitExpression` public name, if its final invariant model remains compatible;
- current Python 3.11–3.14 CI matrix;
- deterministic single-file generation checks already present;
- lazy CLI and exact-module loading;
- existing command/MCP and unit-family test breadth.

## 4. Non-goals

Do not add:

- new calculator syntax;
- new unit categories or aliases except corrections necessary to preserve the prior public surface;
- custom runtime unit registration;
- new MCP tools or transports;
- a new concurrency framework;
- a new packaging backend;
- repository-wide strict typing;
- third-party runtime dependencies;
- unrelated API redesign.

## 5. Required implementation order

Implement in this order:

1. MCP profile authority and registry validation cleanup.
2. Runtime-context configuration replacement.
3. Executor reservation state machine.
4. Session owner routing.
5. Unit declaration authority and baseline parity.
6. Structural unit-expression and `UnitValue` migration.
7. Build-manifest authority.
8. Static checks and typed consumer.
9. Package/single-file parity and performance proof.
10. CI and exact evidence.

Hard gates:

- Do not start `UnitValue` migration until `UNIT_DEFINITIONS` generates the runtime registry and the pre-migration baseline fixture passes.
- Do not retain old and new executor accounting paths simultaneously.
- Do not retain `_evaluator` and `_runtime_context.evaluator` as independently mutable active evaluators.
- Do not update release evidence before all implementation and verification work is complete.
- Do not use another evidence SHA-repin loop.

---

# Workstream A — Registry-owned MCP profiles

## A1. Remove global membership validation from `McpServerConfig`

`McpServerConfig.__post_init__()` may validate only profile syntax:

- value is a string;
- value is non-empty;
- maximum length, for example 128 characters;
- no control characters;
- `full` remains syntactically valid as the documented synthetic profile.

It must not check membership in global `TOOL_PROFILES`.

Example that must succeed:

```python
registry = ToolRegistry(
    handlers={"math_eval": handler},
    schemas={"math_eval": schema},
    metadata={"math_eval": {}},
    profiles={"custom_safe": ["math_eval"]},
)
config = McpServerConfig(profile="custom_safe")
server = McpServer(config=config, registry=registry)
```

This exact construction currently fails at `McpServerConfig` and must be a regression test.

## A2. Validate membership at server construction

After config and registry are available, `McpServer.__init__()` must validate:

```python
if config.profile != "full" and config.profile not in registry.profiles:
    raise ValueError(...)
```

The error must list profiles from that registry, not global defaults.

Example that must fail:

```python
registry = ToolRegistry(..., profiles={"custom_safe": ["math_eval"]})
McpServer(config=McpServerConfig(profile="default"), registry=registry)
# ValueError mentioning custom_safe, not global TOOL_PROFILES
```

## A3. Consolidate instance profile behavior

For server-owned request paths, these must resolve exclusively through `server.registry`:

- `profiles/list`;
- `tools/list`;
- `tools/call` authorization;
- diagnostics;
- close-match errors involving profiles.

Module-level `set_active_profile()` and `get_profile_tools()` may remain only as deprecated compatibility adapters for the singleton compatibility server. They must not be imported or called by `McpServer`, `McpSession`, or `ToolExecutor` instance paths.

## A4. Complete registry validation

Before publishing frozen fields, reject deterministically:

- duplicate tool within one profile;
- empty or control-character profile names;
- malformed profile containers;
- malformed schema/metadata containers;
- case-normalized tool-name collision if tool lookup is case-insensitive anywhere;
- unsupported `llm_exposure` values;
- handler/schema asymmetry;
- metadata for unknown tool;
- profile references to unknown tools.

Because Python dictionaries cannot contain duplicate exact keys after construction, do not claim that iterating a dict detects duplicate handler names. Test meaningful collisions through a normalized name check or a sequence-based construction helper if one is introduced.

### Workstream A acceptance criteria

- [ ] `McpServerConfig(profile="custom_safe")` is valid without consulting global profiles.
- [ ] Server construction validates the selected profile against the supplied registry.
- [ ] `profiles/list`, `tools/list`, and `tools/call` use the same registry-owned authority.
- [ ] No instance request path reads global `TOOL_PROFILES`.
- [ ] The synthetic `full` profile behavior is documented and tested.
- [ ] Registry validation is deterministic and tests only meaningful collision cases.
- [ ] Default registry behavior remains backward compatible.

---

# Workstream B — Make `RuntimeContext` the sole active configuration state

## B1. Define final lifecycle types

Use:

```python
@dataclass(frozen=True)
class ConfigCandidate:
    constants: Mapping[str, Scalar]
    functions: Mapping[str, Callable[..., object]]
    policy: EvaluationPolicy

@dataclass(frozen=True)
class ConfigSnapshot:
    generation: int
    constants: Mapping[str, Scalar]
    functions: Mapping[str, Callable[..., object]]
    policy: EvaluationPolicy

@dataclass(frozen=True)
class RuntimeContext:
    snapshot: ConfigSnapshot
    evaluator: Evaluator
```

Required changes:

- `parse_config_candidate()` returns `ConfigCandidate`;
- remove `units` from the active snapshot, or retain it only as a deprecated always-empty serialized compatibility field;
- recursively freeze candidate/snapshot mappings with the same ownership helper used by the registry;
- `ConfigManager` owns snapshots only; it does not construct evaluators;
- `McpServer` owns exactly one active `RuntimeContext` reference.

## B2. Create the initial context once

At server construction:

```python
initial_snapshot = ConfigSnapshot(
    generation=0,
    constants={},
    functions={},
    policy=policy_from_server_config(config),
)
initial_context = build_runtime_context(config, initial_snapshot)
self._runtime_context = initial_context
self._executor = ToolExecutor(config, registry)
```

Do not retain a separately authoritative mutable `self._evaluator`. A compatibility `evaluator` property may return `self._runtime_context.evaluator`.

The executor must not permanently capture an evaluator during construction. It must receive the request-captured evaluator/context during each call.

## B3. Give `EvaluationPolicy` exact runtime semantics

Define one mapping, for example:

```python
POLICY_OPTIONS = {
    EvaluationPolicy.DEFAULT: {
        "allow_random": config.allow_random,
        "allow_side_effects": config.allow_side_effects,
    },
    EvaluationPolicy.STRICT: {
        "allow_random": False,
        "allow_side_effects": False,
    },
    EvaluationPolicy.PERMISSIVE: {
        "allow_random": True,
        "allow_side_effects": True,
    },
}
```

Document any precedence between server config flags and policy. A safer rule is:

- `STRICT` always disables both;
- `PERMISSIVE` enables only features allowed by the immutable server config ceiling;
- `DEFAULT` follows server config.

Do not store a policy value that has no runtime effect.

Tests must distinguish all policies by evaluating random and side-effect expressions through MCP.

## B4. Build a full replacement context before publication

`McpServer.apply_configuration()` must:

1. parse and validate raw values to `ConfigCandidate` outside the activation lock;
2. read the current context and expected generation;
3. construct a new evaluator from immutable built-ins plus exactly the candidate overlay;
4. create the next snapshot and runtime context;
5. acquire one activation lock;
6. verify that the active generation still equals the expected generation;
7. atomically assign `self._runtime_context = new_context` and publish the same snapshot to `ConfigManager`;
8. release the lock.

No `.update()` may be applied to the old active evaluator.

## B5. Make requests capture one context

At the start of server-owned dispatch:

```python
context = self._runtime_context
```

Pass that context or its evaluator through the full call chain:

```python
session.handle_message(request, server=self, context=context)
executor.call_tool(..., evaluator=context.evaluator)
```

A request that has captured generation N must remain on N even if generation N+1 publishes while it is queued or executing. Define whether capture occurs before queue admission or at worker start; use before queue admission so the request has one stable semantic context from validation through execution.

## B6. Replacement and removal semantics

This sequence:

```python
server.apply_configuration(constants={"alpha": 1})
server.apply_configuration(constants={"beta": 2})
```

must leave `beta` visible and `alpha` absent. Built-ins remain available from immutable evaluator base tables.

Do not merge new overlays into previous overlays unless the API explicitly exposes a separate patch operation. `apply_configuration()` is replacement.

## B7. Failure and concurrency tests

Use injected builders or monkeypatch points to fail:

- candidate validation;
- evaluator construction;
- policy application;
- snapshot construction;
- stale generation publication.

After failure, assert:

```python
assert server.runtime_context is old_context
assert server.config_manager.current() is old_context.snapshot
assert server.diagnostic()["config_generation"] == old_generation
```

Concurrency test:

- request A captures generation 1 and blocks before handler completion;
- configuration generation 2 publishes;
- request B starts and observes generation 2;
- request A completes using generation 1 values.

### Workstream B acceptance criteria

- [ ] `ConfigCandidate` is the parser result and is actually used.
- [ ] `RuntimeContext` is initialized at server construction and is never `None` during normal operation.
- [ ] There is no separately authoritative mutable server evaluator.
- [ ] Executor calls use the evaluator captured from one request context.
- [ ] Configuration publication is one pointer replacement, not incremental mutation.
- [ ] Replacement removes stale overlay entries.
- [ ] Policy values have distinct tested runtime effects.
- [ ] Failed activation preserves context identity, snapshot identity, generation, and behavior.
- [ ] Concurrent requests observe either the old or new complete context, never a mixture.
- [ ] Non-empty custom units are rejected before context construction.

---

# Workstream C — Implement the real executor reservation state machine

## C1. Remove the old counter design

Delete:

- `_inflight_lock`;
- `_queued_lock`;
- `_active_lock`;
- direct independent counter mutations;
- every `max(0, counter - 1)` clamp.

Use one accounting lock and a reservation per accepted request.

Suggested implementation:

```python
class ReservationState(Enum):
    QUEUED = auto()
    ACTIVE = auto()
    RELEASED = auto()

@dataclass
class Reservation:
    state: ReservationState

class ToolExecutor:
    def _reserve(self) -> Reservation: ...
    def _start(self, reservation: Reservation) -> bool: ...
    def _release_queued(self, reservation: Reservation) -> bool: ...
    def _release_active(self, reservation: Reservation) -> bool: ...
```

All transitions occur under one accounting lock.

## C2. Required transition table

| Event | Prior | Next | Counter change |
|---|---|---|---|
| accepted | none | QUEUED | total +1, queued +1 |
| worker starts | QUEUED | ACTIVE | queued -1, active +1 |
| queued cancel succeeds | QUEUED | RELEASED | queued -1, total -1 |
| submit fails | QUEUED | RELEASED | queued -1, total -1 |
| active handler finishes/raises | ACTIVE | RELEASED | active -1, total -1 |
| shutdown cancels queued | QUEUED | RELEASED | queued -1, total -1 |

A second release attempt must not decrement anything. It may return `False` or raise an internal invariant exception in tests.

## C3. Correct the cancel/start race

The worker wrapper must call `_start(reservation)` before invoking the handler:

```python
if not self._start(reservation):
    return CANCELLED_BEFORE_START
```

The timeout path must inspect cancellation:

```python
if future.cancel():
    self._release_queued(reservation)
```

If `future.cancel()` returns `False`, the worker has started or completed. The active/finish path owns release.

Do not let both the done callback and worker `finally` release the same active reservation. Pick one exact owner. Recommended:

- queued cancellation and submit failure release directly;
- worker `finally` releases active reservations;
- done callback handles only the narrow case of a future cancelled before the worker wrapper begins, if needed by the chosen executor mechanics.

## C4. Publish truthful diagnostics

Under the accounting lock, expose:

- `total_inflight`;
- `queued_count`;
- `active_workers`;
- `assert_accounting_invariants()`.

Required invariant:

```python
assert total_inflight == queued_count + active_workers
assert min(total_inflight, queued_count, active_workers) >= 0
```

## C5. Deterministic adversarial tests

Use `threading.Event` and `Barrier`, not sleep-only assumptions.

Required tests:

1. one worker blocks; second request is queued; second times out and cancels before start; queued returns to zero and handler never executes;
2. repeated cancel/start race for at least 500 iterations;
3. submit raises after reservation;
4. handler raises;
5. active handler times out but remains counted until release event;
6. queue fills, rejects, drains, and recovers;
7. close cancels queued futures and waits for active work according to documented close behavior;
8. repeated close is idempotent;
9. all stable checkpoints satisfy the invariant;
10. no counter underflow is masked.

Baseline-failing example:

```python
assert executor.queued_count == 1
result = queued_request_that_times_out()
assert result_is_timeout(result)
assert executor.queued_count == 0
assert queued_handler_call_count == 0
```

### Workstream C acceptance criteria

- [ ] `ReservationState` and `Reservation` exist in the actual execution path.
- [ ] Old independent accounting locks and clamping are removed.
- [ ] Every accepted request receives exactly one reservation.
- [ ] Queued cancellation releases queued and total exactly once.
- [ ] Active completion releases active and total exactly once.
- [ ] Submit failure releases the reservation.
- [ ] Active timeout remains counted until actual handler completion.
- [ ] Cancelled queued work never executes later.
- [ ] Shutdown accounting finishes at zero.
- [ ] `total == queued + active` holds at every stable observation.

---

# Workstream D — Route explicit sessions through a live owner

## D1. Replace `_owner_id` with a resolvable owner

Use a weak reference:

```python
self._owner_ref: weakref.ReferenceType[McpServer] | None = None
```

Provide:

```python
@property
def owner(self) -> McpServer:
    owner = self._owner_ref() if self._owner_ref else None
    if owner is None:
        raise RuntimeError("Session owner is unavailable")
    if owner.closed:
        raise RuntimeError("Session owner is closed")
    return owner
```

`_bind_owner()` must reject rebinding even if Python later reuses an object ID.

## D2. Route module-level explicit sessions through the owner

Replace:

```python
return session.handle_message(request)
```

with:

```python
return session.owner.handle_request(request, session=session)
```

The compatibility function must emit its documented deprecation warning for both sessionless and explicit-session use if the entire module-level API is deprecated.

## D3. Fail closed on serverless production dispatch

`McpSession.handle_message()` must not invoke serverless implementations for:

- `initialize` metadata/version selection;
- `notifications/cancelled` limits;
- `profiles/list`;
- `tools/list`;
- `tools/call`.

For those methods, require a supplied owner server/context or resolve the owner internally. `ping` and protocol-state checks may remain session-local.

A private helper used exclusively by legacy tests must not be reachable from normal module-level dispatch.

## D4. Ownership tests

Required cases:

- unowned session passed to module-level `handle_request()`;
- session owned by another server passed to a server;
- owner server closed;
- session closed;
- owner garbage collected;
- attempted rebind;
- explicit module-level dispatch enforces the owner registry/profile;
- owner evaluator/config generation is used;
- owner max output and timeout limits are used.

High-value example:

```python
server_a = server_with_profile_allowing("secret_tool")
server_b = server_with_profile_denying("secret_tool")
session_b = server_b.create_session(McpSessionState.READY)

result = handle_request(call("secret_tool"), session=session_b)
assert result_is_profile_denied(result)
```

This must fail on the baseline direct-session path and pass after owner routing.

### Workstream D acceptance criteria

- [ ] `_owner_id` is removed from ownership decisions.
- [ ] A session resolves one live owner object.
- [ ] Rebinding is impossible.
- [ ] Module-level explicit-session calls route through the owner server.
- [ ] Serverless tool/profile/cancellation dispatch is removed or fails closed.
- [ ] Closed, unowned, foreign, owner-gone, and owner-closed sessions fail deterministically.
- [ ] Owner registry, profile, context, executor, limits, and diagnostics govern every explicit call.

---

# Workstream E — Make `UNIT_DEFINITIONS` the only built-in unit authority

## E1. Correct the affine declaration semantics first

Use one declared transform:

```python
base_value = value * scale_to_base + offset_to_base
value = (base_value - offset_to_base) / scale_to_base
```

With kelvin as base:

- Celsius: `scale_to_base=1`, `offset_to_base=273.15`;
- Fahrenheit: `scale_to_base=5/9`, `offset_to_base=255.3722222222222`;
- Rankine: `scale_to_base=5/9`, `offset_to_base=0`;
- Kelvin: `scale_to_base=1`, `offset_to_base=0`.

Do not retain `1.8` as a value-to-kelvin multiplier.

Required values:

```python
32 F  -> 273.15 K
212 F -> 373.15 K
491.67 Ra -> 273.15 K
0 C -> 273.15 K
```

## E2. Strengthen `UnitSpec` validation

Reject:

- empty canonical or alias;
- duplicate canonical;
- duplicate exact alias;
- lookup-normalization/case collision;
- non-finite or zero scale;
- non-finite offset;
- affine declaration outside pure temperature dimension;
- affine compound canonical/alias;
- invalid display value;
- unsupported category;
- unsupported dimension exponent/type;
- canonical not present in its own alias set, unless a documented generated rule adds it.

Validation errors must identify both colliding definitions.

## E3. Build `UnitRegistry` exclusively from `UNIT_DEFINITIONS`

Replace `build_unit_registry()` with:

```python
def build_unit_registry(definitions: tuple[UnitSpec, ...] = UNIT_DEFINITIONS) -> UnitRegistry:
    validate_unit_definitions(definitions)
    ...
```

Do not read:

- `UNIT_BASE`;
- `UNIT_ALIASES`;
- `UNIT_CATEGORIES`;
- `_CATEGORY_DIMENSIONS`;
- `TEMPERATURE_CONVERSIONS`.

The registry owns:

- exact alias lookup;
- normalized alias lookup;
- canonical lookup;
- dimension;
- scale;
- offset;
- affine flag;
- display;
- category.

## E4. Generate compatibility adapters

After registry construction, generate public compatibility constants from it:

- `UNIT_ALIASES`;
- `UNIT_CATEGORIES`;
- `UNIT_BASE` if external compatibility requires it;
- `TEMPERATURE_CONVERSIONS` only if public compatibility requires it.

Generated adapters must be immutable where possible and contain no manually maintained semantic values.

If pairwise `UNIT_CONVERSIONS` is public, generate it from scale ratios. It must not drive runtime conversion.

Add an AST/source test that fails if a second large literal unit-semantic map is introduced.

## E5. Make the committed baseline fixture real

The fixture must represent the public unit behavior at the pre-migration baseline, not regenerated current declarations.

Add a script, run against the chosen historical baseline, that records:

- accepted alias set;
- normalized canonical per alias;
- public category;
- dimension tuple;
- representative conversion factors;
- known affine conversions;
- representative displays.

Commit the resulting JSON. Tests must load that file and compare current behavior.

Replace the current permissive check:

```python
if alias in defs_by_alias:
    assert ...
```

with strict equality:

```python
assert set(current_aliases) == set(baseline_aliases)
```

Any intentional difference requires a named migration allowlist with reason.

## E6. Remove duplicate runtime authority

After parity passes:

- delete manual semantic declarations now generated from `UNIT_DEFINITIONS`;
- update documentation to identify `UNIT_DEFINITIONS` as sole authority;
- update `UnitRegistry` docstrings that currently claim `UNIT_BASE`/temperature tables are canonical.

### Workstream E acceptance criteria

- [ ] Affine scales and offsets implement value-to-base semantics correctly.
- [ ] `UnitRegistry` is built only from `UNIT_DEFINITIONS`.
- [ ] Legacy maps are generated adapters, not inputs.
- [ ] Validation covers finite values, normalization collisions, affine restrictions, display, category, and dimension validity.
- [ ] The committed historical fixture is loaded and compared.
- [ ] Current aliases, categories, dimensions, conversions, temperatures, and displays match the baseline except explicit approved migrations.
- [ ] No second built-in unit semantic source remains.

---

# Workstream F — Make `UnitExpression` drive runtime unit behavior

## F1. Finalize expression invariants

`UnitExpression` must contain enough information to avoid reparsing or consulting string categories:

```python
@dataclass(frozen=True)
class UnitExpression:
    factors: tuple[tuple[str, int], ...]
    dimension: Dimension
    scale_to_base: float
    affine_unit: str | None = None
```

Invariants enforced in a factory or `__post_init__()`:

- factors use canonical registry identifiers;
- factors are merged, zero-free, sorted;
- scale is finite and non-zero;
- absolute exponents are bounded;
- affine expression is exactly one affine factor with exponent 1;
- canonical rendering length is bounded;
- directly constructing invalid instances fails.

## F2. Replace parser delegation where necessary

The public parser may reuse low-level tokenization, but it must guarantee:

- full input consumption;
- known units only;
- one `/` division level or a clearly documented grammar;
- `*`, `/`, and exponent syntax only;
- no `//` or `%` separators;
- bounded input length;
- bounded nesting/depth;
- bounded atom count;
- bounded exponent digit length before `int()`;
- bounded absolute exponent;
- finite scale after each operation;
- bounded canonical output;
- bounded error strings.

Required constants:

```python
MAX_UNIT_STRING_LENGTH = 256
MAX_COMPOUND_DEPTH = 16
MAX_COMPOUND_ATOMS = 32
MAX_ABS_UNIT_EXPONENT = 16
MAX_CANONICAL_UNIT_LENGTH = 256
MAX_EXPONENT_DIGITS = 3
```

Use exact values already public where applicable; add only missing owners.

## F3. Migrate public helpers

These functions must use the registry/expression model exclusively:

- `normalize_unit()`;
- `is_unit()`;
- `get_unit_category()`;
- `are_units_compatible()`;
- `get_conversion_factor()`;
- `UnitValue.convert_to()`.

Unknown compounds must fail rather than fall back to category equality or opaque string matching.

## F4. Migrate `UnitValue`

Store a structural expression internally:

```python
class UnitValue:
    def __init__(self, value, unit=None):
        self._unit_expr = parse_unit_expression(unit) if unit else DIMENSIONLESS_EXPRESSION
```

Preserve `.unit` display compatibility by rendering from `_unit_expr` or retaining a display token that never determines semantics.

Migrate all operations:

- addition/subtraction;
- conversion;
- multiplication;
- true division;
- floor division;
- modulo;
- integer powers;
- reverse operations;
- equality/hash if unit normalization affects identity;
- dimensionless cancellation.

Do not construct semantic strings and send them to `_simplify_unit_string()`.

Required examples:

```python
UnitValue(1, "m") + UnitValue(100, "cm") == UnitValue(2, "m")
(UnitValue(2, "m") * UnitValue(3, "m")).unit == "m**2"
(UnitValue(10, "m") / UnitValue(2, "s")).unit == "m/s"
(UnitValue(5, "m") / UnitValue(2, "m")).unit is None
UnitValue(68, "F").convert_to("C").value == approx(20)
```

Affine operations that must fail:

```python
UnitValue(20, "C") * UnitValue(2, "m")
UnitValue(20, "C") ** 2
parse_unit_expression("C/m")
```

## F5. Decide floor division and modulo semantics explicitly

Numeric floor division/modulo may be supported, but their resulting units must follow structural dimensional rules and render valid unit syntax.

Do not produce unit strings containing `//` or `%`.

Example acceptable policy:

- `10 m // 3 s` has numeric result `3` and structural unit `m/s`;
- `10 m % 3 m` returns `1 m`;
- modulo across incompatible dimensions rejects.

Capture current documented behavior before changing it and add a migration note if output changes.

## F6. Differential tests

For every family and alias:

- alias normalizes;
- dimension matches baseline;
- scale matches baseline;
- A→B→A round trip;
- incompatible addition rejects;
- compound dimension and scale are correct;
- package and single-file results agree.

Property-style loops are acceptable without adding Hypothesis.

### Workstream F acceptance criteria

- [ ] `UnitExpression` invariants are enforced on all construction paths.
- [ ] Parser enforces all length/depth/atom/exponent/output/finite-scale limits.
- [ ] Public helpers use registry/expression semantics only.
- [ ] `UnitValue` no longer uses string construction as semantic authority.
- [ ] All arithmetic operations use structural dimensions and scales.
- [ ] Affine compounds are rejected.
- [ ] Floor division/modulo never create invalid unit syntax.
- [ ] Dimensionless cancellation is structural.
- [ ] Baseline family and alias behavior remains compatible.
- [ ] Package and single-file behavior match.

---

# Workstream G — Replace manual build lists with one manifest

## G1. Introduce one manifest

Replace independent lists with:

```python
@dataclass(frozen=True)
class ModuleSpec:
    name: str
    path: str
    group: Literal["core", "exact", "mcp"]
    depends_on: tuple[str, ...] = ()
    include_single_file: bool = True

MODULE_MANIFEST: tuple[ModuleSpec, ...] = (...)
```

Derived compatibility views may exist:

```python
MODULES_CALC = [m.path for m in MODULE_MANIFEST if m.group == "core"]
```

but the builder and validator must iterate the manifest or a topological order derived from it. Derived lists must not be manually maintained.

Include `_version` in the manifest if its contents are inlined or otherwise explicitly generated.

## G2. Validate the graph

`validate_build_manifest()` must detect:

- duplicate names or paths;
- missing source files;
- unknown dependencies;
- dependency cycles;
- invalid group;
- required dependency ordered after consumer;
- inlined relative import whose target is absent from the manifest;
- lazy CLI target module absent from the manifest;
- manifest entry never consumed;
- residual package-relative imports after generation;
- duplicate generated global collisions where statically detectable.

Use deterministic topological sorting, preserving declaration order for ties.

## G3. Fail the build on invalid manifest

Normal `python build_single.py` must call validation and exit non-zero before writing output when invalid. `--validate` must use the same validation path.

## G4. Add mutation tests

Test synthetic manifests containing:

- a cycle;
- unknown dependency;
- duplicate path;
- missing file;
- missing lazy target;
- stable topological tie order.

### Workstream G acceptance criteria

- [ ] `MODULE_MANIFEST` is the sole module inventory.
- [ ] Builder order derives from dependencies.
- [ ] Manual group lists are removed or generated only.
- [ ] Validation detects duplicates, missing files, unknown dependencies, cycles, absent lazy targets, and residual imports.
- [ ] Invalid manifests fail ordinary builds before output is written.
- [ ] Repeated valid builds remain byte-for-byte deterministic.

---

# Workstream H — Strict static verification and external consumer

## H1. Expand strict mypy scope

Add migrated-module strict checks for:

- MCP registry/config/runtime context/executor/session modules;
- units registry/parser/value modules;
- `_version` and `_protocol`;
- build manifest helper;
- typed consumer.

Enable:

- `disallow_any_generics`;
- `disallow_incomplete_defs`;
- `disallow_untyped_defs`;
- `check_untyped_defs`;
- `no_implicit_optional`;
- `strict_equality`;
- `warn_redundant_casts`;
- `warn_unreachable`;
- `warn_unused_ignores`.

A targeted ignore must include an error code and adjacent reason. No `ignore_errors` or broad exclusion.

## H2. Add strict lint/import-boundary command

Keep ordinary Ruff unchanged for compatibility, but add a second command targeting migrated modules with at least:

- `B904` enabled;
- unused suppression cleanup;
- simplification/return consistency rules;
- annotation rules practical for public/internal boundaries.

Add a deterministic script for:

- forbidden instance-path reads of global `TOOL_PROFILES`;
- forbidden unit runtime reads of legacy adapters;
- duplicate protocol/version literal declarations;
- direct executor counter clamping;
- direct explicit-session `session.handle_message(request)` compatibility dispatch.

## H3. Real source and wheel consumer

Create `tests/typing/consumer.py` that imports documented public APIs only.

Source mode:

```bash
python -m mypy tests/typing/consumer.py
python tests/typing/consumer.py
```

Wheel mode:

1. build wheel;
2. create a clean venv;
3. install wheel and mypy;
4. copy consumer outside repository root;
5. assert `eggcalc.__file__` points into the venv;
6. run mypy and runtime smoke there.

Use platform-aware venv executable paths.

### Workstream H acceptance criteria

- [ ] Migrated modules pass the strict mypy profile.
- [ ] Migrated modules pass the strict Ruff/import-boundary checks.
- [ ] No broad ignore masks a closure defect.
- [ ] Consumer is type-checked and executed against source.
- [ ] Consumer is type-checked and executed against the installed wheel outside the source tree.
- [ ] Wheel identity proves no source checkout leakage.
- [ ] Ordinary Ruff, Black, and mypy remain green.

---

# Workstream I — Artifact parity and controlled performance

## I1. Package/single-file inventory

Add a standard-library inventory script that emits canonical JSON for both modes:

- version;
- public API names;
- CLI commands/aliases/module/symbol targets;
- unit definitions and aliases;
- dimensions/scales/offsets/categories/displays;
- MCP tools/schemas/metadata/profiles;
- protocol versions;
- capability fields.

Compare sorted JSON exactly, allowing only named mode-specific fields.

## I2. Release-surface matrix

Verify in clean environments:

- source API;
- editable install;
- wheel install;
- console script;
- `python -m eggcalc`;
- REPL transcript;
- package MCP stdio;
- single-file CLI;
- single-file MCP;
- typed wheel consumer.

## I3. Controlled before/after measurements

Use identical scripts and environment for:

- baseline `b9df49173ecfc60312780aef998c003af0b000b6`;
- final implementation candidate.

Measure fresh processes for:

- `import eggcalc`;
- evaluator import;
- CLI help;
- normal expression;
- exact command;
- MCP initialize;
- compact/full `tools/list`;
- unit registry construction;
- normal and maximum-bound unit parsing;
- single-file startup;
- loaded module count;
- peak traced allocation.

Record sample count, median, mean, standard deviation, OS, architecture, and Python version.

Investigate stable regressions over 15%. Import-boundary failures are hard blockers regardless of timings.

### Workstream I acceptance criteria

- [ ] Package and single-file inventories match except explicit mode fields.
- [ ] All release surfaces pass in clean environments.
- [ ] Single-file generation is deterministic.
- [ ] No residual package-relative imports remain.
- [ ] Baseline and final measurements use the same script/environment.
- [ ] Lazy loading remains demonstrated by module counts.
- [ ] No unexplained stable regression over 15% remains.

---

# Workstream J — CI and synchronized closure evidence

## J1. Required CI additions

Add jobs or explicit steps for:

- strict migrated-module mypy;
- strict migrated-module Ruff/import boundaries;
- source typed consumer;
- wheel typed consumer;
- build-manifest validation;
- package/single-file inventory parity;
- focused MCP lifecycle suite;
- focused unit authority/expression suite;
- deterministic double build;
- release-surface smoke matrix.

Keep full tests on:

- Ubuntu Python 3.11, 3.12, 3.13, 3.14;
- macOS Python 3.11, 3.12;
- Windows Python 3.11, 3.12.

At least the Python 3.11 lane on each OS must run the full closure-focused tests without platform skip.

## J2. Select one implementation candidate

All code, tests, workflow, parity scripts, performance results, and documentation corrections land before selecting the candidate SHA.

If any code/test/workflow change follows, select a new candidate and rerun the full matrix.

## J3. Evidence identity model

Use:

- `closure_code_sha` — exact tested implementation commit;
- `closure_workflow_run_id` — green full workflow for that SHA;
- evidence commit — documentation-only child commit;
- post-evidence workflow — confirms documentation-only commit remains green.

Do not edit evidence again merely to embed its own new SHA.

## J4. Synchronize Releases 4–6

Append a final closure section to:

- `docs/release_4_evidence.md`;
- `docs/release_5_evidence.md`;
- `docs/release_6_evidence.md`.

All three sections must share:

- the same full 40-character closure code SHA;
- the same workflow run ID for shared checks;
- exact lane totals;
- exact focused-suite counts;
- strict check results;
- package/wheel/single-file results;
- parity results;
- baseline/final performance tables;
- retained compatibility shims;
- explicit non-blocking deferrals.

Historical Windows failures may remain only in clearly labeled historical sections.

## J5. Evidence validator

Add a test that rejects:

- approximate count markers such as `~`;
- mismatched closure SHAs or run IDs;
- totals that do not add up;
- contradictory success/error wording;
- missing required jobs;
- final sections that cite historical failed lanes as current status;
- repeated evidence-repin language.

### Workstream J acceptance criteria

- [ ] One exact implementation candidate has all required green jobs.
- [ ] Python 3.11 Linux, macOS, and Windows full lanes pass.
- [ ] Strict, consumer, manifest, parity, deterministic-build, MCP, and unit jobs pass.
- [ ] Release 4–6 final sections share one closure code SHA and run ID.
- [ ] Exact counts and conclusions are internally consistent.
- [ ] Post-evidence CI passes without SHA-repin churn.

---

# 6. Required baseline-failing tests

Before implementing each workstream, add or identify tests that fail specifically on `3770304b`.

Minimum set:

```text
custom registry profile accepted by McpServerConfig + McpServer
config replacement removes old overlay values
policy changes actual MCP evaluator behavior
request A retains old runtime context while request B uses new context
queued cancellation decrements queued_count and prevents handler execution
executor invariant total == queued + active
module-level explicit session enforces owner profile
owner-gone and owner-closed sessions fail closed
runtime UnitRegistry derives from UNIT_DEFINITIONS only
Fahrenheit/Rankine value-to-kelvin transforms
committed baseline fixture is loaded and exact alias sets match
UnitValue multiplication/division no longer calls string simplifier
invalid affine compound rejected
canonical-output and finite-scale parser bounds
build manifest cycle and missing lazy-target failures
wheel consumer mypy outside source tree
package/single-file inventory exact comparison
```

A test that only checks `hasattr`, class existence, tuple length, or fixture JSON validity does not satisfy this requirement.

# 7. Recommended implementation commits

Keep each commit behaviorally complete and include its focused tests.

1. `fix(mcp): make profiles registry-owned in instance paths`
2. `refactor(mcp): make runtime context the sole active evaluator state`
3. `fix(mcp): implement exact-once executor reservation transitions`
4. `fix(mcp): route explicit sessions through live owner servers`
5. `fix(units): correct affine specifications and declaration validation`
6. `refactor(units): build runtime registry and adapters from unit definitions`
7. `refactor(units): make structural expressions drive helpers and UnitValue`
8. `refactor(build): replace module lists with dependency manifest`
9. `chore(verification): add strict checks and installed-wheel consumer`
10. `test(parity): add package single-file inventory and release surfaces`
11. `perf: record controlled baseline and final measurements`
12. `ci: enforce releases 4-6 closure gates across platforms`
13. `docs(evidence): synchronize releases 4-6 to closure candidate`

Do not combine the executor rewrite and unit migration in one commit.

# 8. Stop and rollback conditions

Stop the current workstream and correct or revert if:

- the new type exists but the old production path still owns behavior;
- instance MCP paths read global profile state;
- two active evaluator objects can diverge;
- configuration activation mutates the prior evaluator;
- a queued cancellation can leave non-zero queue accounting;
- counter clamping remains;
- an explicit session can dispatch without a live owner;
- runtime unit conversion reads legacy semantic maps;
- `UNIT_DEFINITIONS` and generated adapters disagree;
- an affine scale is oriented incorrectly;
- the historical baseline fixture is regenerated from current declarations during tests;
- `UnitValue` arithmetic remains string-authoritative;
- parser bounds are declared but not enforced;
- manual module lists remain independently editable;
- strict checks are green only through broad ignores;
- wheel tests import the source checkout;
- package and single-file inventories diverge;
- evidence is updated before the implementation candidate is fully green;
- another SHA-repin loop begins.

# 9. Final closure checklist

Releases 4–6 remain open until every item below is checked.

## MCP

- [ ] Profiles are registry-owned for all instance paths.
- [ ] Registry/config/profile validation is deterministic.
- [ ] `RuntimeContext` is the sole active configuration/evaluator state.
- [ ] Requests capture one immutable context.
- [ ] Configuration replacement removes stale overlays.
- [ ] Policy values change runtime behavior.
- [ ] Failed activation leaves the prior context unchanged.
- [ ] Executor uses a real reservation state machine.
- [ ] No independent counter locks or clamping remain.
- [ ] Queued cancellation releases capacity and prevents execution.
- [ ] Explicit sessions route through live owner servers.
- [ ] Serverless tool/profile dispatch is removed or fails closed.

## Units

- [ ] Affine value-to-base definitions are correct.
- [ ] `UNIT_DEFINITIONS` is the sole built-in semantic source.
- [ ] Runtime registry is generated only from definitions.
- [ ] Legacy maps are generated compatibility adapters.
- [ ] Historical baseline fixture is loaded and compared exactly.
- [ ] All aliases/categories/dimensions/conversions remain compatible.
- [ ] `UnitExpression` invariants and all parser bounds are enforced.
- [ ] Public helpers use structural registry semantics.
- [ ] `UnitValue` arithmetic is structural, not string-authoritative.
- [ ] Affine compounds reject.
- [ ] Package and single-file unit behavior match.

## Build and verification

- [ ] `_version.py` remains the single package version authority.
- [ ] `_protocol.py` remains the single protocol authority.
- [ ] One dependency manifest owns single-file modules.
- [ ] Manifest validation covers cycles, missing modules/dependencies, lazy targets, and residual imports.
- [ ] Migrated modules pass strict mypy and lint/import-boundary checks.
- [ ] Typed consumer passes against source and installed wheel.
- [ ] Wheel identity proves no source leakage.
- [ ] Package/single-file inventory parity passes.
- [ ] Release surfaces pass in clean environments.
- [ ] Controlled performance comparison is complete.

## CI and evidence

- [ ] Required full and focused jobs pass at one implementation candidate.
- [ ] Python 3.11 Linux, macOS, and Windows pass.
- [ ] Release 4–6 evidence shares one exact code SHA and workflow run.
- [ ] Evidence contains exact, internally consistent counts.
- [ ] Historical failures are clearly historical.
- [ ] Post-evidence CI passes without repinning.

# 10. Completion definition

This corrective plan is complete only when the scaffolding introduced at `3770304b` has become the active and sole production authority, the superseded paths are removed or generated adapters, the required behavioral tests fail on the baseline and pass on the candidate, and exact cross-platform evidence proves closure at one implementation commit.
