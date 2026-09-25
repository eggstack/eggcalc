# Releases 4–6 Definitive Implementation Closure

Status: implementation handoff  
Repository: `eggstack/eggcalc`  
Baseline reviewed: `cc610025f280314adc0987cf4392ae518f45f81c`  
Supersedes incomplete execution of:

- `plans/011-release-6-corrective-closure-pass.md`
- `plans/012-releases-4-6-final-authority-and-evidence-closure.md`

This plan is the execution specification for the remaining mandatory work. It does not reopen work that is already correct, and it does not permit additional evidence-only commits to stand in for unresolved implementation.

## 1. Objective

Close Releases 4, 5, and 6 by replacing the remaining duplicate or mutable authorities with explicit immutable ownership, correcting the executor/session lifecycle defects, completing the structural unit migration, and producing exact reproducible verification.

The final result must demonstrate that:

- every MCP request is governed by one owning server, registry, profile, evaluator context, and executor;
- registry/configuration data cannot be mutated through public references;
- configuration replacement is one atomic context swap rather than incremental dictionary mutation;
- executor reservations have explicit exact-once state transitions;
- one declarative unit source owns aliases, dimensions, scales, affine behavior, displays, and categories;
- conversion and compound arithmetic use registry/structural semantics rather than independent maps and strings;
- package version, protocol versions, and single-file build inventory have singular authorities;
- strict type/lint checks and a real external typed consumer run in CI;
- release evidence identifies an exact tested implementation commit and exact workflow results without repeated SHA repinning.

## 2. Preserve completed work

Do not regress or rewrite these already-useful results unless required by a later workstream:

- lazy package-root CLI exports;
- `eggcalc.cli` loading zero exact implementations before command selection;
- command resolution by defining module and symbol;
- `Dimension.angle` equality/hash behavior;
- structural compatibility for recognized units;
- MCP protocol versions in `eggcalc/_protocol.py`;
- deterministic single-file byte-comparison tests;
- residual relative-import detection;
- Windows-safe CLI output;
- Python 3.11 Linux/macOS/Windows lanes;
- broad unit-family invariant tests;
- command/MCP parity tests.

## 3. Non-goals

Do not add:

- new calculator grammar;
- new unit families or aliases except a correction needed to preserve existing behavior;
- user-defined unit registration in this closure pass;
- new MCP tools, transports, or protocol extensions;
- runtime dependencies;
- symbolic algebra;
- currency/network-backed conversion;
- repository-wide strict typing;
- a new packaging backend or external single-file bundler;
- unrelated public API renames;
- performance changes that weaken validation.

For configuration `units`, this plan makes a deliberate scope choice: **non-empty custom unit configuration must be rejected before activation**. Full server-local unit overlays are deferred because implementing them safely would expand the closure scope and create another unit authority.

## 4. Execution order and hard gates

Implement in this order:

1. MCP registry immutability and registry-owned profiles.
2. Atomic runtime configuration context.
3. Executor reservation state machine.
4. Session owner routing.
5. Declarative unit authority.
6. Structural unit-expression parsing and arithmetic migration.
7. Version and build-manifest authority.
8. Strict verification and external typed consumer.
9. Artifact parity and controlled performance measurements.
10. Cross-platform CI and synchronized evidence.

Hard dependency rules:

- Do not start unit arithmetic migration until the declarative registry is complete and baseline alias parity passes.
- Do not update Release 4–6 evidence until all implementation workstreams pass locally.
- Do not claim an implementation complete because a new test describes intended behavior; verify the production path exercised by that test.
- Do not suppress counter underflow with `max(0, value - 1)`; underflow must fail a test or assertion.
- Do not retain legacy and new unit sources as coequal behavior authorities.

## 5. Workstream A — Recursively immutable MCP registry

### A1. Establish one ownership conversion

Replace the current combination of `_deep_copy()` plus shallow `MappingProxyType` wrappers with two explicit helpers:

```python
JsonOwned = object


def freeze_owned(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType({k: freeze_owned(v) for k, v in value.items()})
    if isinstance(value, list | tuple):
        return tuple(freeze_owned(v) for v in value)
    if isinstance(value, set | frozenset):
        return frozenset(freeze_owned(v) for v in value)
    return value


def thaw_owned(value: object) -> object:
    if isinstance(value, Mapping):
        return {k: thaw_owned(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [thaw_owned(v) for v in value]
    if isinstance(value, frozenset):
        return {thaw_owned(v) for v in value}
    return value
```

The exact typing may differ. Required semantics:

- constructor inputs are detached and recursively frozen once;
- nested dictionaries are immutable mappings;
- nested lists become tuples;
- nested sets become frozensets;
- tuples are recursively frozen;
- no separate shallow-copy implementation can drift from the freeze logic.

Use the frozen representation for:

- schemas;
- metadata;
- profiles;
- any registry-owned result/error envelope declarations.

### A2. Define accessor policy

Use this consistent policy:

- `.schemas`, `.metadata`, and `.profiles` expose recursively immutable registry-owned values;
- `get_schema()` and `get_metadata()` return independent mutable deep copies for backward compatibility;
- `get_profile_tools()` returns a new list;
- `tool_names` returns an immutable tuple, not a mutable list.

Example required behavior:

```python
registry.schemas["math_eval"]["inputSchema"]["properties"]["expression"]["type"] = "integer"
# TypeError

copy = registry.get_schema("math_eval")
copy["inputSchema"]["properties"]["expression"]["type"] = "integer"
assert registry.get_schema("math_eval")["inputSchema"]["properties"]["expression"]["type"] == "string"
```

### A3. Validate before publishing fields

Validate raw detached inputs before assigning the final registry fields. Reject all errors in a deterministic order.

Required validation:

- handler without schema;
- schema without handler;
- metadata for unknown tool;
- profile referencing unknown tool;
- duplicate tool name after any supported normalization;
- empty profile name;
- duplicate tool within one profile;
- unsupported `llm_exposure` value;
- malformed schema/metadata/profile container type.

Where practical, report all offending names in one error rather than failing at the first unordered set member.

### A4. Make profile names registry-owned

Change `McpServerConfig` profile validation so it validates only syntax:

- non-empty string;
- bounded length;
- no control characters.

Validate profile membership after the server has both its config and registry.

Recommended flow:

```python
config = McpServerConfig(profile="custom_safe")
registry = ToolRegistry(..., profiles={"custom_safe": ["math_eval"]})
server = McpServer(config=config, registry=registry)  # succeeds
```

This must fail clearly:

```python
config = McpServerConfig(profile="custom_safe")
registry = ToolRegistry(..., profiles={"other": ["math_eval"]})
McpServer(config=config, registry=registry)
# ValueError: profile 'custom_safe' is not defined by this registry
```

`profiles/list`, `tools/list`, and `tools/call` must all resolve through `server.registry` and the same selected profile.

### Focused tests

Add tests that mutate every nesting shape:

- nested schema mapping;
- schema list such as `required` or `enum`;
- nested metadata mapping/list;
- profile tuple;
- original constructor dictionaries after construction;
- mutable copies returned by accessors.

Add custom profile tests:

- custom profile accepted even if absent from global defaults;
- default global profile absent from custom registry is rejected;
- profile listing contains only registry-owned profiles plus documented synthetic `full`;
- list and call authorization agree exactly.

### Acceptance criteria — Workstream A

- [ ] No public registry path can mutate nested internal state.
- [ ] Constructor inputs cannot mutate the registry after construction.
- [ ] Mutable accessor copies cannot mutate the registry.
- [ ] Registry validation runs before publication and reports deterministic errors.
- [ ] Custom registries own their profile namespace independently of `TOOL_PROFILES`.
- [ ] `profiles/list`, `tools/list`, and `tools/call` use one profile authority.
- [ ] Existing default registry behavior and tool inventory remain unchanged.

## 6. Workstream B — Atomic runtime configuration context

### B1. Introduce explicit lifecycle objects

Use separate types for:

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

`ConfigCandidate` has no generation and is never active. `ConfigSnapshot` is manager-generated and recursively immutable. `RuntimeContext` is the object captured by a request before dispatch.

### B2. Reject unsupported custom units

`parse_config_candidate(units=...)` must behave as follows:

```python
server.apply_configuration(units={})       # allowed
server.apply_configuration(units=None)     # allowed
server.apply_configuration(units={"foo": 1})
# ConfigError: custom units are not supported by server configuration
```

Do not accept and store ignored unit values.

Remove `units` from the active snapshot if retaining it would imply support. A deprecated serialized field may remain only if it is always empty and explicitly documented.

### B3. Define policy semantics once

Create an enum or frozen policy type and one mapping to evaluator behavior.

Example:

```python
class EvaluationPolicy(Enum):
    DEFAULT = "default"
    STRICT = "strict"
    PERMISSIVE = "permissive"
```

Document and test the exact flags controlled by each policy, including random and side-effect behavior. No policy string may be stored without affecting runtime behavior.

### B4. Build replacement context off to the side

`McpServer.apply_configuration()` must:

1. parse raw input to `ConfigCandidate` outside the publication lock;
2. validate names, scalar values, callables, policy, and unsupported units;
3. read the current generation;
4. build a complete replacement evaluator from immutable built-ins plus the candidate overlay;
5. create the next immutable snapshot and runtime context;
6. acquire one activation lock;
7. verify the expected prior generation still matches;
8. atomically replace `self._runtime_context` and manager snapshot;
9. release the lock.

Do not incrementally mutate the active evaluator dictionaries.

Recommended request behavior:

```python
context = server.runtime_context  # one pointer capture
return server.executor.call_tool(..., evaluator=context.evaluator)
```

An in-flight request continues using the captured old context. A request that starts after publication uses the new context.

### B5. Replacement, not merge

Given:

```python
server.apply_configuration(constants={"alpha": 1})
server.apply_configuration(constants={"beta": 2})
```

The second active overlay must contain `beta` but not `alpha`. Built-ins remain according to a documented base-plus-overlay policy.

Two servers may use conflicting overlays without modifying evaluator class dictionaries or module globals.

### B6. Failure atomicity

Inject failures at each pre-publication stage:

- invalid name;
- unsupported value;
- non-callable function;
- unsupported units;
- evaluator construction failure;
- policy construction failure;
- stale generation race.

After every failure, assert all of these are unchanged:

- runtime-context object identity;
- snapshot identity and generation;
- evaluator visible constants/functions;
- policy behavior;
- dependent caches;
- diagnostics.

### Acceptance criteria — Workstream B

- [ ] One public operation performs parse, validation, generation, context construction, and publication.
- [ ] The active evaluator is never mutated field-by-field during replacement.
- [ ] New requests capture exactly one immutable runtime context.
- [ ] In-flight requests continue on their captured generation.
- [ ] Replacement removes overlay entries absent from the new candidate.
- [ ] Failed activation changes no runtime state or generation.
- [ ] `policy` has explicit tested runtime behavior.
- [ ] Non-empty custom `units` are rejected before activation.
- [ ] Two servers with conflicting configurations remain isolated.

## 7. Workstream C — Exact-once executor reservation accounting

### C1. Replace independent counters with a reservation state machine

Use one lock for reservation state and derived counters.

Recommended model:

```python
class ReservationState(Enum):
    QUEUED = auto()
    ACTIVE = auto()
    RELEASED = auto()

@dataclass
class Reservation:
    state: ReservationState = ReservationState.QUEUED
```

Required transitions:

- accept: create `QUEUED`, increment total and queued;
- worker starts: `QUEUED -> ACTIVE`, decrement queued, increment active;
- cancelled before start: `QUEUED -> RELEASED`, decrement queued and total;
- worker finishes: `ACTIVE -> RELEASED`, decrement active and total;
- submit fails: `QUEUED -> RELEASED`, decrement queued and total;
- shutdown cancels queued work: `QUEUED -> RELEASED` for every successfully cancelled future.

A transition from `RELEASED` must be a no-op or explicit internal error, but must never decrement counters again.

### C2. Handle the worker/cancel race explicitly

The worker wrapper must attempt the `QUEUED -> ACTIVE` transition before invoking the handler. If cancellation already released the reservation, the handler must not run.

The timeout path must inspect `future.cancel()`:

```python
cancelled_before_start = future.cancel()
if cancelled_before_start:
    reservation.release_queued()
# Otherwise worker is active or completed; callback/worker completion releases it.
```

The done callback may be the common release point, but it must distinguish a cancelled queued future from an active/completed future. One path must own each transition.

### C3. Remove underflow masking

Remove `max(0, counter - 1)` from reservation accounting. Add internal assertions:

```python
assert total == queued + active
assert total >= 0 and queued >= 0 and active >= 0
```

Expose an invariant-check helper for tests and diagnostics.

### C4. Adversarial tests

Use barriers/events rather than sleep-only timing.

Required cases:

1. one active worker blocks, second request remains queued, second times out and cancels before start;
2. timeout races with worker start in repeated loops;
3. submit raises after reservation acquisition;
4. handler raises;
5. handler times out but remains active until actual completion;
6. close with queued and active work;
7. repeated close;
8. cancellation storm with hundreds of iterations;
9. queue saturation followed by complete recovery.

After each case:

```python
assert executor.total_inflight == 0
assert executor.queued_count == 0
assert executor.active_workers == 0
executor.assert_accounting_invariants()
```

For active timeout, assert occupancy remains non-zero until the handler actually exits.

### Acceptance criteria — Workstream C

- [ ] Every accepted request has one reservation with explicit state.
- [ ] Queued cancellation releases queued and total exactly once.
- [ ] Active completion releases active and total exactly once.
- [ ] Submit failure releases all acquired capacity.
- [ ] Active timeout remains truthfully counted until completion.
- [ ] Shutdown releases successfully cancelled queued reservations.
- [ ] No counter uses clamping to hide underflow.
- [ ] `total == queued + active` holds at every observable stable point.
- [ ] Stress tests finish with all counters zero and no handler executing after queued cancellation.

## 8. Workstream D — Owner-server session routing

### D1. Store a resolvable owner

Replace owner ID-only tracking with a weak owner reference or bounded dispatch callback.

Example:

```python
self._owner_ref: weakref.ReferenceType[McpServer] | None

@property
def owner(self) -> McpServer:
    owner = self._owner_ref() if self._owner_ref else None
    if owner is None or owner.closed:
        raise RuntimeError("Session owner is unavailable")
    return owner
```

Avoid a strong reference cycle unless explicitly broken on close.

### D2. Route every explicit session through its owner

Module-level compatibility dispatch must use:

```python
return session.owner.handle_request(request, session=session)
```

It must not call `session.handle_message(request)` without a server.

Within `McpSession.handle_message`, remove or fail closed on serverless production dispatch for `tools/list`, `tools/call`, `profiles/list`, initialization metadata, and cancellation. A private compatibility helper may exist only for tests that explicitly exercise legacy behavior.

### D3. Reject invalid ownership states

Deterministically reject:

- never-owned session;
- session owned by a different server;
- closed session;
- closed owner server;
- garbage-collected owner;
- rebinding to another server;
- explicit session supplied to the wrong server.

### D4. Policy enforcement example

Create two registries where `secret_tool` exists only on server A or is excluded from server B's profile. Passing server B's session to module-level `handle_request()` must enforce server B's policy and reject the call. This test must fail under the old direct `session.handle_message(request)` path.

### Acceptance criteria — Workstream D

- [ ] Every owned session resolves one live owning server.
- [ ] Explicit compatibility dispatch routes through that owner.
- [ ] Server-specific registry, profile, evaluator, limits, and executor apply on every call path.
- [ ] Unowned, foreign, closed, owner-closed, and owner-gone sessions fail closed.
- [ ] Sessions cannot be rebound to a different server.
- [ ] Compatibility behavior emits its documented deprecation warning without bypassing policy.

## 9. Workstream E — One declarative unit authority

### E1. Capture the baseline before migration

Add a development script that serializes the current public unit surface to normalized JSON:

- every accepted alias;
- normalized canonical display;
- public category;
- structural dimension;
- multiplicative conversion to the family base where applicable;
- affine known-value conversions;
- representative display strings.

Commit this as a test fixture, not a second runtime authority. The fixture is used only to prove no alias or behavior disappears during migration.

### E2. Introduce declarative specifications

Use one immutable declaration tuple. Suggested shape:

```python
@dataclass(frozen=True)
class UnitSpec:
    canonical: str
    aliases: tuple[str, ...]
    dimension: Dimension
    scale_to_base: float
    offset_to_base: float = 0.0
    affine: bool = False
    display: str | None = None
    category: str = ""

UNIT_DEFINITIONS: tuple[UnitSpec, ...] = (
    UnitSpec(
        canonical="m",
        aliases=("m", "meter", "meters", "metre", "metres"),
        dimension=DIM_LENGTH,
        scale_to_base=1.0,
        display="m",
        category="length",
    ),
    UnitSpec(
        canonical="deg",
        aliases=("deg", "degree", "degrees"),
        dimension=Dimension(angle=True),
        scale_to_base=math.pi / 180.0,
        display="deg",
        category="angle",
    ),
    UnitSpec(
        canonical="C",
        aliases=("C", "celsius", "centigrade", "degc", "°C"),
        dimension=DIM_TEMPERATURE,
        scale_to_base=1.0,
        offset_to_base=273.15,
        affine=True,
        display="C",
        category="temperature",
    ),
)
```

Define affine semantics exactly:

```python
base_value = value * scale_to_base + offset_to_base
target_value = (base_value - target.offset_to_base) / target.scale_to_base
```

For Fahrenheit, use exact constants consistent with existing public results and test known values.

### E3. Build and validate the registry from specifications

Construction must reject:

- empty canonical or alias;
- duplicate canonical;
- duplicate exact alias;
- case-normalization collision where lookup is case-insensitive;
- alias equal to another canonical with conflicting definition;
- non-finite or zero scale;
- non-finite offset;
- affine unit outside pure temperature dimension;
- affine unit with unsupported compound metadata;
- display canonical not owned by the declaration;
- unsupported dimension exponent/type;
- category absent from the documented category set.

Build immutable mappings:

- alias to definition;
- canonical to definition;
- normalized lookup key to definition;
- category presentation adapter.

### E4. Derive legacy public maps

Generate compatibility adapters from `UNIT_DEFINITIONS`:

- `UNIT_ALIASES`;
- `UNIT_CATEGORIES`;
- `UNIT_BASE` only if still required by public compatibility;
- documentation inventories.

Delete independent runtime declarations of these maps. No adapter may contain manually maintained semantic values.

Do not preserve `UNIT_CONVERSIONS` as a pairwise behavior authority. Multiplicative factors are computed from registry scales. Affine conversion is computed through the base transform.

### E5. Baseline parity gate

Before removing legacy sources, require a differential test that compares the generated registry/adapters against the committed baseline fixture:

- identical alias set;
- identical canonical display for every alias;
- identical public category;
- identical conversion results within documented tolerance;
- all known temperature values preserved;
- no new collision silently chooses one definition.

### Acceptance criteria — Workstream E

- [ ] `UNIT_DEFINITIONS` is the only built-in unit semantic declaration.
- [ ] Aliases, categories, dimensions, scales, offsets, affine flags, and displays derive from it.
- [ ] Legacy maps are generated compatibility adapters only.
- [ ] Pairwise conversion tables no longer determine multiplicative behavior.
- [ ] Every baseline alias resolves to exactly one definition.
- [ ] Duplicate/collision/invalid declarations fail construction deterministically.
- [ ] Baseline alias and conversion parity passes with no unexplained deletion or change.
- [ ] Runtime remains standard-library-only.

## 10. Workstream F — Structural `UnitExpression` and bounded parsing

### F1. Add one immutable expression type

Suggested representation:

```python
@dataclass(frozen=True)
class UnitExpression:
    factors: tuple[tuple[str, int], ...]  # sorted canonical unit atoms
    dimension: Dimension
    scale_to_base: float
```

Invariants:

- factors contain canonical identifiers only;
- zero exponents are removed;
- duplicate factors are merged;
- factors are sorted deterministically;
- total scale is finite and non-zero;
- affine units are allowed only as one standalone factor with exponent `1`;
- canonical rendering is derived from factors, never reparsed to determine semantics.

### F2. Define the grammar

Accepted grammar:

```text
expression := product ("/" product)?
product    := factor ("*" factor)*
factor     := atom ("**" signed_integer)?
atom       := known unit alias
```

Compatibility forms such as `m^2` or `m2` may be normalized at the API boundary if currently documented. The structural parser itself uses one canonical exponent syntax.

Do not treat `//` or `%` as unit-expression separators.

Required behavior:

```python
parse_unit_expression("m/s**2")   # accepted
parse_unit_expression("m//s")     # rejected
parse_unit_expression("m%s")      # rejected
parse_unit_expression("unknown/s")# rejected
```

`UnitValue.__floordiv__` and `UnitValue.__mod__` may still implement numeric operators, but any resulting unit semantics must use structural division and render `/`, not inject `//` or `%` into a unit string.

### F3. Enforce complete resource bounds

Define and enforce:

```python
MAX_UNIT_STRING_LENGTH = 256
MAX_COMPOUND_DEPTH = 16
MAX_COMPOUND_ATOMS = 32
MAX_ABS_UNIT_EXPONENT = 16
MAX_CANONICAL_UNIT_LENGTH = 256
```

Also enforce:

- full input consumption;
- finite scale accumulation after every multiplication/power;
- bounded error text;
- no unbounded integer parsing before exponent-length checks;
- no recursion error at limits.

Examples:

```python
parse_unit_expression("m**16")   # accepted
parse_unit_expression("m**17")   # rejected
parse_unit_expression("m**999999999999999999999")  # rejected before expensive arithmetic
```

### F4. Migrate public helpers

These functions must resolve through the registry and parser:

- `normalize_unit()`;
- `is_unit()`;
- `get_unit_category()`;
- `are_units_compatible()`;
- `get_conversion_factor()`;
- `UnitValue.convert_to()`.

Unknown or malformed compound expressions must not fall back to category strings or opaque string equality.

### F5. Migrate `UnitValue`

`UnitValue` may retain `.unit: str | None` for public display compatibility, but must capture or lazily resolve one `UnitExpression` used for semantics.

Migrate:

- addition/subtraction and conversion;
- multiplication/division;
- floor division;
- modulo;
- integer powers;
- reciprocal operations;
- dimensionless cancellation;
- equality/hash policy if normalized units affect identity.

Required examples:

```python
UnitValue(1, "m") + UnitValue(100, "cm") == UnitValue(2, "m")
(UnitValue(2, "m") * UnitValue(3, "m")).unit == "m**2"
(UnitValue(10, "m") / UnitValue(2, "s")).unit == "m/s"
(UnitValue(5, "m") / UnitValue(2, "m")).unit is None
```

Affine restrictions:

```python
UnitValue(20, "C") * UnitValue(2, "m")
# ValueError: affine units cannot participate in compound multiplication

UnitValue(68, "F").convert_to("C")
# 20 C within documented tolerance
```

Before changing floor-division/modulo display behavior, capture current golden results and either preserve them or add an explicit migration note. Do not preserve invalid `//`/`%` unit strings merely to satisfy old internals.

### F6. Differential and invariant tests

For every advertised family:

- every alias normalizes;
- every multiplicative unit round-trips through family base;
- conversion A→B→A stays within tolerance;
- structural dimensions agree across family members;
- incompatible families reject addition;
- representative compound forms have expected dimension and scale;
- package and single-file results match.

### Acceptance criteria — Workstream F

- [ ] One immutable `UnitExpression` drives compound semantics.
- [ ] The parser fully consumes input and recognizes only known units.
- [ ] Length, depth, atom, exponent, canonical-output, and finite-scale bounds are enforced.
- [ ] `//` and `%` are not accepted as unit-expression syntax.
- [ ] Public unit helpers resolve through the registry/parser.
- [ ] Compatibility never depends on category/display-string coincidence.
- [ ] Affine conversion is correct and affine compound arithmetic is rejected.
- [ ] All `UnitValue` operators use structural semantics.
- [ ] Dimensionless cancellation is structural.
- [ ] Package and single-file unit behavior match across all families and focused compound cases.

## 11. Workstream G — Version and build authority

### G1. Single package version

Add `eggcalc/_version.py`:

```python
__version__ = "1.1.6"
```

Use it from:

- `eggcalc.__version__`;
- CLI version output;
- capabilities;
- MCP server info;
- generated single-file code.

Configure setuptools dynamic metadata:

```toml
[project]
dynamic = ["version"]

[tool.setuptools.dynamic]
version = {attr = "eggcalc._version.__version__"}
```

Remove the literal version from `pyproject.toml` and `eggcalc/__init__.py`.

Build a wheel and assert:

```python
import importlib.metadata
import eggcalc
assert importlib.metadata.version("eggcalc") == eggcalc.__version__
```

### G2. Preserve protocol authority

Keep `_protocol.py` as the only protocol-version declaration. Add an AST/text drift test that fails if another source file defines `SUPPORTED_PROTOCOL_VERSIONS` as a literal tuple.

### G3. One build manifest

Replace independent `MODULES_CALC`, `MODULES_EXACT`, and `MODULES_MCP` lists with one declaration:

```python
@dataclass(frozen=True)
class ModuleSpec:
    path: str
    group: Literal["core", "exact", "mcp"]
    depends_on: tuple[str, ...] = ()
    include_single_file: bool = True

MODULE_MANIFEST: tuple[ModuleSpec, ...] = (...)
```

Derive grouped lists only as compatibility views.

Validate:

- duplicate path;
- missing file;
- unknown dependency;
- dependency cycle;
- dependency appearing after consumer in final order;
- undeclared required inlined import;
- residual package-relative import;
- duplicate injected global where detectable;
- lazy CLI target module absent from manifest.

Use deterministic topological ordering. For equal-ready nodes, preserve declaration order.

### G4. Limit ownership

Update `architecture/authority_inventory.md` with one source for each major limit. Add mechanical drift tests for aliases/import adapters. Do not require every subsystem to share one numeric value; require one owner per value.

### Acceptance criteria — Workstream G

- [ ] Installed metadata, API, CLI, capabilities, MCP, and single-file versions derive from `_version.py`.
- [ ] Protocol versions remain singular in `_protocol.py`.
- [ ] The single-file module inventory has one declarative source.
- [ ] Manifest validation detects duplicates, missing modules, cycles, order errors, undeclared dependencies, and missing lazy targets.
- [ ] Major limits have one documented owner each.
- [ ] Authority documentation describes actual code ownership rather than known duplicates.

## 12. Workstream H — Strict verification and external typed consumer

### H1. Expand strict mypy coverage

Add a dedicated config or overrides for:

- `eggcalc.cli`;
- `eggcalc.units` and any extracted registry/parser modules;
- `eggcalc._version`;
- `eggcalc._protocol`;
- MCP registry/configuration/runtime-context/executor/session code;
- build-manifest helper module;
- typed external consumer.

Enable where applicable:

- `disallow_any_generics`;
- `disallow_incomplete_defs`;
- `check_untyped_defs`;
- `no_implicit_optional`;
- `strict_equality`;
- `warn_redundant_casts`;
- `warn_unreachable`;
- `warn_unused_ignores`;
- `disallow_untyped_defs`.

Targeted ignores require an adjacent explanation and exact error code. Do not make the group green with `ignore_errors`, broad module exclusion, or `# type: ignore` without a code.

### H2. Stronger lint target

Create an explicit command for migrated modules enabling selected additional Ruff rules, including:

- `B904` exception chaining;
- simplification/return consistency;
- public annotation checks where practical;
- unused suppression cleanup.

Use a deterministic import-boundary script for constraints Ruff cannot express.

Do not alter global ignores merely to hide migrated-module defects.

### H3. Real external consumer

Move the consumer out of the ordinary pytest module role, for example:

```text
tests/typing/consumer.py
tests/typing/consumer_runtime.py
```

The consumer must import only documented public APIs. It must be type-checked, not merely executed by pytest.

Source mode command:

```bash
python -m mypy --config-file pyproject.toml tests/typing/consumer.py
```

Wheel mode:

1. build wheel;
2. create a clean virtual environment;
3. install wheel and mypy;
4. copy only the consumer file outside the repository import path;
5. type-check using the venv interpreter/site-packages;
6. run the consumer runtime smoke.

Verify that wheel mode does not accidentally import the source checkout by printing and checking `eggcalc.__file__`.

### H4. CI placement

Run ordinary mypy and strict migrated-module checks on Ubuntu Python 3.11 or 3.12. Run source and wheel consumer checks in the package job. Minimum-runtime tests remain cross-platform.

### Acceptance criteria — Workstream H

- [ ] All migrated modules pass the stronger mypy profile with zero errors.
- [ ] All migrated modules pass the stronger Ruff/import-boundary checks.
- [ ] No broad ignore or excluded module masks a closure defect.
- [ ] The external consumer is independently type-checked in source mode.
- [ ] The same consumer is type-checked and executed against the installed wheel outside the source tree.
- [ ] Wheel identity proves the installed artifact was imported.
- [ ] Ordinary repository Ruff, Black, and mypy remain green.

## 13. Workstream I — Artifact parity and performance proof

### I1. Machine-readable inventories

Add one standard-library script that emits normalized JSON for package and single-file modes:

- version;
- public API names;
- CLI command names, aliases, modules, symbols;
- unit canonicals, aliases, dimensions, scales, offsets, affine flags, displays, categories;
- MCP tool names, schemas, metadata, profiles;
- protocol versions;
- capability output excluding documented mode-specific fields.

Compare inventories byte-for-byte after canonical JSON sorting. Any allowed difference must be an explicit named field whitelist.

### I2. Release-surface matrix

Exercise cleanly:

- source import/API;
- editable install;
- wheel install;
- console script;
- `python -m eggcalc`;
- REPL transcript;
- MCP package stdio;
- generated single-file CLI;
- generated single-file MCP;
- typed consumer against wheel.

The smoke script must be Windows-aware when locating venv executables:

- POSIX: `bin/python`, `bin/pip`;
- Windows: `Scripts/python.exe`, `Scripts/pip.exe`.

### I3. Controlled before/after measurements

Use separate clean worktrees at:

- baseline: `b9df49173ecfc60312780aef998c003af0b000b6`;
- final implementation candidate: exact candidate SHA.

Measure fresh processes for:

- `import eggcalc`;
- `from eggcalc import evaluate`;
- CLI help;
- calculator-only expression;
- one exact command;
- MCP initialize;
- compact/full `tools/list` serialization;
- unit registry construction;
- normal and maximum-bound compound parsing;
- generated single-file startup;
- loaded module count;
- peak traced allocation.

Record OS, architecture, Python version, sample count, median, mean, standard deviation, module counts, and memory.

The existing measurements at `1816aca` are not sufficient as a before/after comparison. Re-run both baseline and final using the same script and environment.

A stable repeated regression greater than 15% requires investigation and written explanation. Import-boundary gates are hard requirements regardless of timing noise.

### Acceptance criteria — Workstream I

- [ ] Package and single-file authority inventories match except explicit mode fields.
- [ ] All release surfaces pass in clean environments.
- [ ] Repeated generation remains byte-for-byte deterministic.
- [ ] No package-relative imports remain in generated code.
- [ ] Controlled baseline and final measurements use the same script/environment.
- [ ] Lazy loading is demonstrated by module counts.
- [ ] No unexplained stable regression above 15% remains.
- [ ] Performance evidence includes registry/parser and MCP schema costs, not only package import.

## 14. Workstream J — CI and evidence without SHA-repin loops

### J1. Establish one implementation candidate

All code, tests, CI workflow, documentation corrections, parity tools, and measurement outputs must land before selecting the implementation candidate SHA.

Do not add another code or test commit after selecting it. If a code/test change is needed, select a new candidate and rerun the full workflow.

### J2. Required CI jobs

The candidate must have successful jobs for:

- package/wheel/source-surface verification;
- Ubuntu Python 3.11, 3.12, 3.13, 3.14 full tests;
- macOS Python 3.11 and 3.12 full tests;
- Windows Python 3.11 and 3.12 full tests;
- ordinary lint/format/type checks;
- strict migrated-module checks;
- source and installed-wheel typed consumer;
- single-file build/determinism/parity;
- focused MCP lifecycle tests;
- focused unit authority/parser/arithmetic tests.

At least one minimum-runtime lane must run the full closure-specific command set rather than skipping it as platform-conditional.

### J3. Use a two-identity evidence model

Avoid the impossible self-referential requirement that a committed file contain the SHA of the commit containing that file.

Evidence must record:

- `closure_code_sha`: the exact implementation candidate tested by the full workflow;
- `closure_workflow_run_id`: the full green workflow for that SHA;
- `evidence_document_parent_sha`: the candidate SHA on which evidence was based;
- evidence document commit URL may be obtained from repository history and need not be embedded inside itself.

After the evidence-only commit, run CI once more to prove documentation-only changes did not break checks. Do **not** repeatedly edit the file to repin it to each new evidence-only SHA.

All Release 4–6 final closure sections must use the same `closure_code_sha` and workflow run ID for shared claims.

### J4. Exact evidence fields

Record:

- full 40-character closure code SHA;
- workflow run ID and stable URL;
- every relevant job name and conclusion;
- exact OS/Python matrix;
- exact collected, passed, skipped, xfailed, and failed totals per lane;
- grouped skip reasons;
- exact Ruff, Black, ordinary mypy, strict mypy, build, parity, and typed-consumer results;
- MCP recursive-immutability test count;
- atomic configuration test count;
- executor accounting test count;
- session ownership test count;
- unit declaration/alias/parser/arithmetic test counts;
- source/editable/wheel/single-file results;
- deterministic generation hash/comparison result;
- package/single-file inventory result;
- baseline/final performance tables;
- retained compatibility shims and removal timing;
- explicitly deferred non-blocking work.

Do not use approximate values such as `~3911`, `all pass`, or `subsequent commits` where exact data is available.

### J5. Synchronize Release 4 and 5 evidence

Preserve historical sections, but append a clearly labeled final closure section to:

- `docs/release_4_evidence.md`;
- `docs/release_5_evidence.md`;
- `docs/release_6_evidence.md`.

Release 4 must no longer present the old Windows failures as current closure status. Release 5 must not use stale counts as final closure proof.

Add an evidence-validation test that checks:

- all three final sections contain the same closure code SHA;
- all three contain the same workflow run ID where applicable;
- exact totals add up;
- no approximate-count marker appears in final sections;
- no contradictory `0 errors` plus acknowledged error wording;
- required fields are non-empty;
- historical failures are clearly labeled historical.

### Acceptance criteria — Workstream J

- [ ] One exact implementation candidate has all required green jobs.
- [ ] Python 3.11 Linux, macOS, and Windows full test lanes pass.
- [ ] Strict type/lint, typed consumer, parity, and focused closure jobs pass.
- [ ] Release 4–6 final sections share one exact closure code SHA and workflow run.
- [ ] Evidence uses exact counts and internally consistent totals.
- [ ] Evidence-only commits are not repeatedly repinned.
- [ ] A post-evidence CI run passes without code changes.
- [ ] Historical Windows failures are not represented as current status.

## 15. Required focused test groups

### 15.1 MCP authority

- recursive schema/metadata/profile immutability;
- accessor copy isolation;
- registry construction errors;
- custom registry profile ownership;
- list/call/profile agreement;
- default compatibility.

### 15.2 Configuration

- candidate validation;
- unsupported custom units rejection;
- policy runtime effect;
- complete replacement/removal semantics;
- atomic context publication;
- stale generation race;
- failure rollback;
- in-flight old-generation continuity;
- cross-server isolation.

### 15.3 Executor and session lifecycle

- queued cancel-before-start;
- cancel/start race;
- active timeout occupancy;
- submit failure;
- handler exception;
- close with queued/active work;
- stress invariant;
- unowned/foreign/closed/owner-gone session rejection;
- explicit compatibility owner routing.

### 15.4 Unit authority and expressions

- baseline alias parity;
- duplicate canonical/alias/case collision;
- invalid scale/offset/affine declaration;
- registry-derived adapters;
- all-family normalization/round trips;
- known affine values;
- full parser consumption;
- length/depth/atom/exponent/output/finite-scale limits;
- `//` and `%` rejection;
- every `UnitValue` arithmetic operator;
- affine compound rejection;
- package/single-file parity.

### 15.5 Metadata, build, typing, and evidence

- installed version agreement;
- protocol literal drift;
- manifest duplicate/missing/cycle/order/dependency failures;
- deterministic generation;
- source and wheel typed consumer;
- strict mypy/Ruff targets;
- inventory parity;
- performance result schema;
- evidence exact totals and shared SHA.

## 16. Required verification commands

Run from a clean checkout at the implementation candidate:

```bash
python -m ruff check .
python -m black --check .
python -m mypy eggcalc --ignore-missing-imports
python -m mypy --config-file pyproject.toml <migrated-modules> tests/typing/consumer.py
python build_single.py --validate
python build_single.py
python scripts/generate_mcp_docs.py --check
python scripts/smoke_release_surfaces.py
python <package-single-file-inventory-script>
python -m pytest tests/ -v
python -m build
```

Also run:

- wheel-installed typed-consumer check;
- deterministic double-build comparison;
- controlled baseline/final performance collection;
- evidence validation tests.

## 17. Recommended implementation commits

Keep focused tests with each implementation commit.

1. `fix(mcp): recursively freeze registry state and make profiles registry-owned`
2. `refactor(mcp): introduce immutable runtime configuration contexts`
3. `fix(mcp): implement exact-once executor reservation state machine`
4. `fix(mcp): route every explicit session through its owner server`
5. `refactor(units): introduce declarative built-in unit specifications`
6. `refactor(units): derive aliases categories and conversion adapters`
7. `refactor(units): add bounded immutable unit expressions`
8. `refactor(units): migrate conversion and UnitValue arithmetic`
9. `refactor(meta): consolidate version and single-file module manifest`
10. `chore(types): add strict migrated-module and wheel-consumer checks`
11. `test(parity): prove package single-file and release-surface parity`
12. `perf: record controlled release 6 baseline and final measurements`
13. `docs(evidence): synchronize releases 4-6 to exact closure candidate`

Do not mix MCP lifecycle changes and unit migration in one commit.

## 18. Stop and rollback conditions

Stop the current workstream and correct or revert before continuing if:

- a documented calculator, CLI, exact-tool, unit, or MCP result changes unexpectedly;
- nested registry state remains mutable through any public path;
- profile authorization differs between list and call;
- configuration readers can observe a partially applied generation;
- activation mutates module/class global evaluator state;
- executor accounting requires clamping to avoid negative values;
- a queued-cancelled handler later executes;
- explicit session dispatch reaches a serverless tool path;
- alias inventory shrinks without an approved migration note;
- a legacy unit map continues independently determining behavior;
- affine units enter compound arithmetic;
- parser limits are declared but not enforced;
- package and single-file inventories diverge;
- strict checks are made green with broad ignores;
- wheel consumer imports the source checkout;
- performance shows a stable unexplained regression over 15%;
- evidence is edited before the implementation candidate workflow is green;
- another evidence-only SHA repinning loop begins.

Prefer reverting one bounded workstream over retaining two semantic authorities.

## 19. Final acceptance checklist

Releases 4, 5, and 6 may be marked complete only when every item is checked.

### MCP ownership and lifecycle

- [ ] Registry data is recursively immutable through all public views.
- [ ] Registry accessors return independent mutable copies where documented.
- [ ] Registry consistency validation is deterministic and complete.
- [ ] Custom registries own custom profiles independently of global defaults.
- [ ] One immutable runtime context is atomically published per configuration generation.
- [ ] Replacement removes stale overlay values.
- [ ] Policy has tested runtime meaning.
- [ ] Non-empty custom unit configuration is rejected.
- [ ] Failed configuration changes preserve all prior state.
- [ ] Executor reservations transition exactly once through queued/active/released.
- [ ] Cancellation before start releases queued and total capacity.
- [ ] Active timeout remains counted until actual completion.
- [ ] Counter invariants hold without clamping.
- [ ] Every explicit session dispatch routes through one live owner server.
- [ ] Invalid ownership states fail closed.

### Units

- [ ] One declarative source owns every built-in unit semantic property.
- [ ] Legacy maps are generated adapters only.
- [ ] Baseline alias and conversion parity passes.
- [ ] Invalid declarations and collisions fail construction.
- [ ] Public helpers use registry/parser semantics.
- [ ] One immutable structural expression drives compound arithmetic.
- [ ] All parser resource bounds are enforced.
- [ ] `//` and `%` are not unit-expression syntax.
- [ ] All `UnitValue` arithmetic operators use structural semantics.
- [ ] Affine conversion is correct and affine compounds are rejected.
- [ ] All advertised families have round-trip/invariant coverage.
- [ ] Package and single-file unit inventories and behavior match.

### Metadata, build, static verification

- [ ] Package version has one source across all surfaces.
- [ ] Protocol versions have one source.
- [ ] Build modules have one dependency-validated manifest.
- [ ] Major limits have explicit singular owners.
- [ ] Migrated modules pass strict mypy and Ruff/import checks.
- [ ] No broad ignore masks closure work.
- [ ] External consumer type-checks against source and installed wheel.
- [ ] Wheel identity proves no source-tree leakage.

### Packaging, performance, CI, evidence

- [ ] Single-file generation is deterministic.
- [ ] Generated code has no residual package-relative imports.
- [ ] Package/single-file inventories match.
- [ ] Source, editable, wheel, console, module CLI, REPL, MCP, and single-file surfaces pass.
- [ ] Controlled before/after measurements cover all required surfaces.
- [ ] No unexplained stable regression above 15% remains.
- [ ] Python 3.11 Linux, macOS, and Windows lanes pass at one exact implementation candidate.
- [ ] Strict checks, typed consumer, parity, and focused closure tests pass in CI.
- [ ] Releases 4–6 evidence uses exact counts and one shared closure code SHA/run.
- [ ] Post-evidence CI passes without SHA-repin churn.
- [ ] Documentation accurately describes actual authorities and retained shims.

## 20. Completion definition

This plan is complete only when the repository proves, at one exact implementation candidate and one exact green workflow, that the remaining mutable/duplicate authorities are gone, lifecycle accounting is exact, units are structurally authoritative, package and single-file surfaces share the same declarations, and Releases 4–6 evidence is precise and reproducible.

Until every final acceptance item passes, Releases 4, 5, and 6 remain open.