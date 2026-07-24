# Releases 4–6 Final Unit-Authority and Evidence Closure

Status: implementation handoff  
Repository: `eggstack/eggcalc`  
Baseline reviewed: `5a1bb34c9efa269ca6159217827f1742faa95d20`  
Depends on:

- `plans/013-releases-4-6-definitive-implementation-closure.md`
- `plans/014-releases-4-6-production-path-corrective-closure.md`

This plan closes only the defects still present after the production-path corrective pass. It preserves the MCP ownership, reservation-state, package-version, and initial module-manifest work that now exists. It does not authorize another broad rewrite or another evidence-only closure claim.

## 1. Final objective

Releases 4, 5, and 6 may close only after the repository proves all of the following at one exact implementation commit:

1. instance-owned profile listing and authorization use the same registry namespace;
2. `RuntimeContext` is the only mutable server configuration/evaluator authority;
3. executor reservation bookkeeping remains bounded for long-running servers;
4. session ownership is permanent and every production dispatch requires a live owner;
5. `UNIT_DEFINITIONS` is the sole built-in unit semantic declaration;
6. all public conversion and arithmetic paths use `UnitRegistry` and `UnitExpression` rather than legacy tables and unit strings;
7. the committed pre-migration unit fixture is actually compared against the migrated behavior;
8. the single-file builder executes and validates one dependency graph rather than merely declaring one;
9. strict source and installed-wheel consumers run without hiding imports;
10. package and single-file authority inventories match;
11. controlled before/after architecture measurements exist;
12. Release 4–6 evidence is synchronized to the exact green implementation commit and workflow.

The work is not complete when a new data structure exists beside an old authority. The old authority must be removed, generated from the new authority, or limited to a compatibility adapter that cannot independently determine behavior.

## 2. Preserve completed work

Do not regress these baseline improvements:

- recursively frozen `ToolRegistry` schemas, metadata, and profiles;
- registry-owned custom profile selection at `McpServer` construction;
- request capture of a `RuntimeContext` before dispatch;
- `ReservationState` and one accounting lock in `ToolExecutor`;
- weak-reference session ownership and owner-routed explicit compatibility dispatch;
- corrected Fahrenheit and Rankine declaration orientation;
- dynamic package version authority in `eggcalc/_version.py`;
- protocol authority in `eggcalc/_protocol.py`;
- `MODULE_MANIFEST` as the declared single-file inventory;
- current Linux/macOS/Windows Python 3.11+ CI matrix;
- deterministic single-file generation tests already present;
- lazy CLI/exact-module loading;
- existing unit-family, command-parity, MCP, isolation, and resource-bound test breadth.

## 3. Non-goals

Do not add:

- new unit families or user-defined unit registration;
- a new calculator grammar;
- symbolic dimensional algebra beyond the existing integer-exponent unit model;
- new MCP tools, transports, or authentication;
- a third-party units library;
- a new concurrency framework;
- repository-wide strict typing unrelated to migrated closure modules;
- a new packaging backend;
- performance optimizations that weaken validation;
- unrelated public API renames.

## 4. Current residual defects

At `5a1bb34c`:

- `_handle_list_profiles()` still publishes global `PROFILE_NAMES` even for a custom server registry;
- `ConfigManager` can mutate a snapshot independently of `McpServer._runtime_context`;
- `apply_configuration()` and `activate_snapshot()` publish the runtime context before the manager update, so a later manager failure can leave split state;
- policy derivation is coupled to the MCP profile name and `DEFAULT`/`PERMISSIVE` behavior is not cleanly specified;
- released executor reservations remain in `_reservations` until shutdown;
- `_bind_owner()` can permit rebinding after a previous owner is garbage-collected;
- direct serverless `initialize` dispatch remains possible through `McpSession.handle_message()`;
- `UnitRegistry` still builds from `UNIT_BASE`, `_CATEGORY_DIMENSIONS`, and `TEMPERATURE_CONVERSIONS`;
- `UnitValue` still stores semantic unit strings and uses `_simplify_unit_string()`/`_pow_unit_string()`;
- `parse_unit_expression()` still resolves through `UNIT_ALIASES`, the legacy registry, and `UNIT_BASE` fallback;
- `UnitSpec` validation is incomplete;
- the committed unit baseline fixture is not loaded by tests, and missing aliases are skipped;
- the single-file builder still iterates derived group lists instead of the topologically sorted manifest;
- manifest validation advertises checks it does not perform;
- the strict consumer uses `--follow-imports=silent` and is not type-checked against the installed wheel;
- no package/single-file authority inventory or controlled baseline/final performance proof exists;
- Release 4–6 evidence still references old commits, old workflow runs, approximate counts, and historical Windows failures.

## 5. Required implementation order

Implement in this order:

1. residual MCP authority and lifecycle cleanup;
2. capture and commit the true pre-migration unit fixture;
3. make `UNIT_DEFINITIONS` generate the runtime registry and compatibility adapters;
4. replace the legacy parser and migrate public unit helpers;
5. migrate `UnitValue` to structural semantics;
6. make the build graph executable and fully validated;
7. add strict source/wheel consumer and authority-boundary checks;
8. add package/single-file inventory and performance proof;
9. complete CI and exact synchronized evidence.

Hard gates:

- Do not modify unit runtime behavior until the baseline fixture is generated from legacy public behavior at `5a1bb34c`.
- Do not migrate `UnitValue` while `UnitRegistry` still reads legacy tables.
- Do not retain two conversion paths after migration.
- Do not update final evidence before all code, tests, workflows, inventories, and performance files are committed.
- Do not repin evidence repeatedly to evidence-only commits.

---

# Workstream A — Close residual MCP authority defects

## A1. Make profile listing registry-owned

For `server is not None`, `_handle_list_profiles()` must derive every published field from that server:

```python
profile_names = tuple(sorted(server.registry.profiles))
if "full" not in profile_names:
    available_profiles = ("full", *profile_names)
else:
    available_profiles = profile_names

profiles_info = {
    name: {
        "tools": server.registry.get_profile_tools(name),
        "tool_count": len(server.registry.get_profile_tools(name)),
    }
    for name in available_profiles
}
```

Do not iterate global `PROFILE_NAMES` or read `TOOL_PROFILES` in any instance-owned list/call/diagnostic path.

Required regression example:

```python
registry = ToolRegistry(
    handlers={"math_eval": handler},
    schemas={"math_eval": schema},
    metadata={"math_eval": {}},
    profiles={"custom_safe": ["math_eval"]},
)
server = McpServer(McpServerConfig(profile="custom_safe"), registry)
session = server.create_session(McpSessionState.READY)

listed = server.handle_request(rpc("profiles/list"), session)
assert listed["result"]["available_profiles"] == ["full", "custom_safe"]
assert "default" not in listed["result"]["profiles"]
assert server.handle_request(call("math_eval"), session) is successful
```

### A1 acceptance criteria

- [ ] Instance `profiles/list` publishes only `full` plus profiles owned by that registry.
- [ ] `profiles/list`, `tools/list`, and `tools/call` agree for every custom profile.
- [ ] Global `PROFILE_NAMES`/`TOOL_PROFILES` remain compatibility-server adapters only.
- [ ] A source-boundary test rejects global profile reads inside `McpServer`, `McpSession`, and `ToolExecutor` instance paths.

## A2. Eliminate split runtime-context/config-manager state

`McpServer._runtime_context` must be the only active state. `ConfigManager` may remain public for compatibility only as a facade over the server-owned context.

Recommended design:

```python
class ConfigManager:
    def __init__(self, owner: McpServer | None = None):
        self._owner_ref = weakref.ref(owner) if owner is not None else None
        self._snapshot = ConfigSnapshot()

    def current(self) -> ConfigSnapshot:
        owner = self._owner_ref() if self._owner_ref else None
        return owner.runtime_context.snapshot if owner is not None else self._snapshot

    def replace(self, snapshot: ConfigSnapshot) -> int:
        owner = self._owner_ref() if self._owner_ref else None
        if owner is not None:
            owner.activate_snapshot(snapshot)
            return snapshot.generation
        return self._replace_standalone(snapshot)
```

An alternative is a separate read-only `ServerConfigView`; however, there must be no public method capable of changing `ConfigManager.current()` without also atomically changing `McpServer.runtime_context`.

`diagnostic()` must read generation and configured values from one captured runtime context, not from a separately mutable manager snapshot.

## A3. Make publication failure-proof

All operations that can raise must occur before publication. Under one server lock:

1. verify expected generation;
2. validate manager generation without mutating;
3. assign the new context;
4. update any compatibility facade using a non-raising assignment;
5. release the lock.

The two assignments must be simple in-memory pointer assignments after validation. Do not call a mutating validator after assigning `_runtime_context`.

Required injected-failure test:

```python
old = server.runtime_context
monkeypatch.setattr(server.config_manager, "_validate_next", raising_validator)
with pytest.raises(ExpectedError):
    server.apply_configuration(constants={"x": 1})
assert server.runtime_context is old
assert server.config_manager.current() is old.snapshot
assert server.diagnostic()["config_generation"] == old.snapshot.generation
```

## A4. Decouple evaluation policy from MCP profiles

`policy_from_server_config()` must not inspect `config.profile`.

Use these semantics:

- `STRICT`: random and side effects disabled;
- `DEFAULT`: use `McpServerConfig.allow_random` and `allow_side_effects`;
- `PERMISSIVE`: enable each capability only where the immutable server ceiling allows it.

`DEFAULT` and `PERMISSIVE` may coincide when both server ceilings are enabled. That is acceptable. What is not acceptable is a dead policy value or policy derivation from a tool-profile string.

Required tests:

- strict overrides a server configured with both capabilities allowed;
- permissive on an allowing server enables both;
- permissive cannot exceed a disabled ceiling;
- default follows the configured flags;
- changing tool profile does not change evaluator policy;
- applying a policy replacement changes only new request contexts.

## A5. Bound executor reservation storage

On every successful terminal transition, remove the reservation from `_reservations` under the accounting lock:

```python
reservation.state = ReservationState.RELEASED
self._reservations.discard(reservation)
```

Add invariant:

```python
assert len(self._reservations) == self._total_inflight
assert all(r.state is not ReservationState.RELEASED for r in self._reservations)
```

Required long-run test:

```python
for _ in range(10_000):
    assert call_fast_tool(executor) is successful
executor.assert_accounting_invariants()
assert executor.total_inflight == 0
assert executor.reservation_count == 0
```

Include successful calls, handler failures, queued cancellations, active timeouts, and submission failures.

## A6. Make session ownership permanently single-assignment

Add an ownership sentinel independent of weak-reference liveness:

```python
self._owner_bound_once = False


def _bind_owner(self, server: McpServer) -> None:
    if self._owner_bound_once:
        raise RuntimeError("Session ownership is immutable")
    self._owner_bound_once = True
    self._owner_ref = weakref.ref(server)
```

Do not permit rebinding after owner garbage collection or close.

At the start of `McpSession.handle_message()`, resolve one effective server for all production protocol methods:

```python
if server is None:
    try:
        server = self.owner
    except RuntimeError:
        if method != "ping":
            return invalid_owner_error(...)
```

`initialize`, cancellation, profile listing, tool listing, and tool calls must all require the owner. Only `ping` and local lifecycle rejection may remain owner-independent.

### Workstream A final acceptance criteria

- [ ] Custom profile listing and authorization use one registry namespace.
- [ ] No server-attached `ConfigManager` mutation can diverge from `RuntimeContext`.
- [ ] Failed publication preserves context and manager identity.
- [ ] Evaluation policy does not depend on MCP profile names.
- [ ] Reservation storage returns to zero after terminal transitions.
- [ ] Session ownership cannot be rebound after close or owner collection.
- [ ] Direct serverless initialization and production dispatch fail closed.
- [ ] Existing compatibility-server behavior remains isolated and deprecated.

---

# Workstream B — Capture a real pre-migration unit baseline

The existing fixture test is insufficient because it serializes the new declarations into a temporary file. Capture the actual legacy public behavior before changing runtime authority.

## B1. Add a deterministic exporter

Create `scripts/export_unit_baseline.py`. It must use public/current runtime behavior, not `UNIT_DEFINITIONS`, to emit canonical JSON containing:

- every key accepted by `UNIT_ALIASES`;
- normalized canonical result;
- public category;
- structural dimension tuple from current compatibility logic;
- multiplicative factor to the family base where defined;
- affine flag and representative known-value transforms;
- display result;
- representative arithmetic renderings for compound cases.

Run the exporter from a clean worktree at `5a1bb34c9efa269ca6159217827f1742faa95d20`:

```bash
git worktree add ../eggcalc-unit-baseline 5a1bb34c9efa269ca6159217827f1742faa95d20
python ../eggcalc-unit-baseline/scripts/export_unit_baseline.py \
  --output tests/fixtures/units/legacy-5a1bb34c.json
```

If the exporter itself must be introduced after that commit, copy the script into the baseline worktree without copying migrated runtime files. Record the exporter SHA256 in a fixture metadata field.

## B2. Compare the committed fixture

Replace the temporary-file test with a test that loads the committed fixture and compares current public behavior.

This must fail on:

- one missing alias;
- one changed canonical;
- one changed category;
- one changed scale beyond tolerance;
- one changed affine known value;
- one changed documented arithmetic rendering.

Do not write fixtures during ordinary test execution.

## B3. Make alias coverage exact

Replace conditional checks such as:

```python
if alias in defs_by_alias:
    assert ...
```

with exact set and mapping equality:

```python
assert set(defs_by_alias) == set(fixture["aliases"])
assert defs_by_alias == fixture_alias_mapping
```

Any intentional migration must be listed in an explicit `allowed_changes` section with rationale and corresponding changelog entry. The expected default is no behavioral change.

### Workstream B acceptance criteria

- [ ] The fixture originates from legacy runtime behavior at exact commit `5a1bb34c`.
- [ ] Ordinary tests read but never regenerate the fixture.
- [ ] Alias coverage is exact, not conditional.
- [ ] Canonical/category/dimension/scale/affine/display parity is enforced.
- [ ] Intentional differences require explicit fixture metadata and changelog documentation.

---

# Workstream C — Make `UNIT_DEFINITIONS` the sole built-in authority

## C1. Complete the declaration model

Extend `UnitSpec` so every compatibility adapter can be generated without consulting legacy tables:

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
    base_canonical: str = ""
```

`base_canonical` identifies the public family base used to generate `UNIT_BASE` compatibility shape. Examples:

```python
UnitSpec("m", ("m", "meter", "meters"), DIM_LENGTH, 1.0,
         display="m", category="length", base_canonical="m")
UnitSpec("km", ("km", "kilometer", "kilometers"), DIM_LENGTH, 1000.0,
         display="km", category="length", base_canonical="m")
UnitSpec("F", ("F", "fahrenheit", "°F"), DIM_TEMPERATURE, 5/9,
         offset_to_base=255.3722222222222, affine=True,
         display="F", category="temperature", base_canonical="K")
```

Do not infer family bases from dictionary order or the first scale of `1.0`.

## C2. Enforce complete declaration validation

Reject before registry publication:

- empty canonical, alias, category, or base canonical;
- canonical missing from its alias set unless a documented generated rule adds it;
- duplicate canonical;
- duplicate exact alias;
- normalized/case-fold alias collision;
- alias colliding with another canonical;
- non-finite or zero scale;
- non-finite offset;
- affine declaration outside pure temperature dimension;
- affine alias/canonical containing compound operators;
- affine exponent other than standalone `1`;
- invalid display token;
- unsupported category;
- base canonical absent from declarations;
- base canonical in another category/dimension;
- base unit with non-unit scale or nonzero offset where not affine;
- unsupported dimension exponent/type.

Errors must identify both conflicting definitions and be deterministic.

## C3. Build the runtime registry only from declarations

Change:

```python
def build_unit_registry(
    definitions: tuple[UnitSpec, ...] = UNIT_DEFINITIONS,
) -> UnitRegistry:
    validate_unit_definitions(definitions)
    ...
```

This function must not read:

- `UNIT_BASE`;
- `UNIT_ALIASES`;
- `UNIT_CATEGORIES`;
- `_CATEGORY_DIMENSIONS`;
- `_CATEGORY_NAME_TO_DIMENSION`;
- `TEMPERATURE_CONVERSIONS`;
- pairwise `UNIT_CONVERSIONS`.

Add `category` and `base_canonical` to `UnitDefinition` so the registry owns all required semantics.

Registry mappings must be immutable after construction. Public introspection returns immutable values or copies.

## C4. Generate compatibility adapters from the registry

After building the registry, derive:

- `UNIT_ALIASES`;
- `UNIT_CATEGORIES`;
- `UNIT_BASE`;
- `TEMPERATURE_CONVERSIONS`, only if retained as a public compatibility constant;
- documentation inventories.

These adapters must contain no manually maintained semantic literals.

Recommended adapter generation:

```python
UNIT_ALIASES = MappingProxyType({alias: definition.canonical ...})
UNIT_CATEGORIES = MappingProxyType({alias: definition.category ...})
UNIT_BASE = MappingProxyType({
    base: MappingProxyType({alias: definition.scale ...})
    for each multiplicative family
})
```

Affine pairwise tables, if preserved, must be generated mathematically from each source/target declaration:

```python
base = value * source.scale_to_base + source.offset_to_base
target = (base - target.offset_to_base) / target.scale_to_base
```

## C5. Add negative authority checks

Create `scripts/check_authority_boundaries.py` using AST/token inspection. It must fail if production unit functions outside the declaration/adapter section read legacy adapters to determine behavior.

At minimum reject:

- `build_unit_registry()` reading `UNIT_BASE` or `TEMPERATURE_CONVERSIONS`;
- `parse_unit_expression()` reading `UNIT_ALIASES` or `UNIT_BASE`;
- `get_conversion_factor()` reading pairwise tables;
- `are_units_compatible()` comparing category strings;
- `UnitValue` calling `_simplify_unit_string()` or `_pow_unit_string()` for semantics.

### Workstream C acceptance criteria

- [ ] Every built-in alias, canonical, category, dimension, scale, offset, display, affine flag, and family base is declared once.
- [ ] `build_unit_registry()` consumes only `UNIT_DEFINITIONS`.
- [ ] Legacy public maps are generated immutable adapters.
- [ ] No pairwise table independently controls conversion.
- [ ] Invalid/colliding definitions fail deterministically.
- [ ] The legacy fixture passes exactly after migration.
- [ ] Authority-boundary checks prevent regression to legacy runtime reads.

---

# Workstream D — Replace legacy parsing and migrate public helpers

## D1. Implement one bounded parser

Do not delegate the new structural parser to `_parse_compound_signature()` if that function continues supporting legacy `//`/`%` syntax or unknown atom fallbacks.

Use a tokenizer and iterative or bounded recursive-descent parser for:

```text
expression := product ("/" product)?
product    := factor ("*" factor)*
factor     := atom ("**" signed_integer)?
atom       := registered unit alias
```

Compatibility spellings such as `m^2` and `m2` may resolve as registered aliases. They are not separate grammar productions.

Required limits:

```python
MAX_UNIT_STRING_LENGTH = 256
MAX_COMPOUND_DEPTH = 16
MAX_COMPOUND_ATOMS = 32
MAX_ABS_UNIT_EXPONENT = 16
MAX_EXPONENT_DIGITS = 3
MAX_CANONICAL_UNIT_LENGTH = 256
MAX_UNIT_ERROR_LENGTH = 512
```

Enforce:

- full input consumption;
- exponent digit bound before `int()`;
- finite scale after every multiply/divide/power;
- canonical output bound;
- bounded error text;
- no `//` or `%` separators;
- no unknown atoms;
- no affine compound/exponent use.

## D2. Make `UnitExpression` self-validating

`UnitExpression.__post_init__()` must enforce invariants even when constructed directly:

- canonical factors only;
- merge duplicate factors;
- remove zero exponents;
- deterministic factor order;
- bounded factor count and exponent;
- dimension and scale match registry-derived factors;
- finite nonzero scale;
- canonical rendering within limit;
- affine only as one standalone factor with exponent `1`.

Prefer a private constructor/factory if arbitrary public construction cannot be validated safely.

Required examples:

```python
parse_unit_expression("m/s**2")       # accepted
parse_unit_expression("kg*m/s**2")    # accepted
parse_unit_expression("m//s")         # rejected
parse_unit_expression("m%s")          # rejected
parse_unit_expression("C/m")          # rejected
parse_unit_expression("C**2")         # rejected
parse_unit_expression("m**17")        # rejected
parse_unit_expression("m**999999999") # rejected before unbounded int/power work
```

## D3. Migrate all public unit helpers

These functions must resolve exclusively through the registry and structural parser:

- `normalize_unit()`;
- `is_unit()`;
- `get_unit_category()`;
- `are_units_compatible()`;
- `get_conversion_factor()`;
- `convert_temperature()`;
- `UnitValue.convert_to()`.

Rules:

- multiplicative conversion factor is `source.scale_to_base / target.scale_to_base`;
- affine conversion uses source-to-base then base-to-target;
- dimensions must match exactly;
- unknown units fail explicitly;
- malformed compounds fail explicitly;
- category equality never substitutes for dimension equality.

## D4. Remove semantic legacy helpers

After migration:

- `_parse_compound_signature()` may remain only as a private compatibility renderer/parser used by no public semantic path, or be deleted;
- `_simplify_unit_string()` and `_pow_unit_string()` must not determine `UnitValue` semantics;
- `_CATEGORY_DIMENSIONS` and `_CATEGORY_NAME_TO_DIMENSION` must be generated adapters or removed;
- pairwise `UNIT_CONVERSIONS` must be removed from runtime conversion.

### Workstream D acceptance criteria

- [ ] One parser governs compound unit semantics.
- [ ] All declared resource bounds are enforced.
- [ ] Affine compound expressions are rejected.
- [ ] Public helpers use registry/expression semantics only.
- [ ] Unknown/malformed units never fall back to legacy category/string behavior.
- [ ] Multiplicative and affine conversion formulas are registry-driven.
- [ ] Negative source-boundary tests confirm legacy helpers are not semantic authorities.

---

# Workstream E — Migrate `UnitValue` to structural semantics

## E1. Store structural state

Use:

```python
class UnitValue:
    def __init__(self, value: Numeric, unit: str | None = None) -> None:
        self.value = validated_value
        self._unit_expr = (
            parse_unit_expression(unit)
            if unit is not None
            else DIMENSIONLESS_EXPRESSION
        )
        self._display_unit = unit
```

`.unit` may preserve the current display contract, but `_display_unit` must never determine compatibility, conversion, cancellation, or result dimensions.

Preserve the existing equality/hash contract unless current documentation requires normalization-based equality. If display-sensitive equality is retained, document that arithmetic is structural while object identity remains display-sensitive.

## E2. Implement structural expression operations

Add bounded methods/functions:

- `multiply_expressions(left, right)`;
- `divide_expressions(left, right)`;
- `power_expression(expr, exponent)`;
- `render_expression(expr)`.

They must combine factors and dimensions without reparsing generated strings.

Multiplication/division must preserve the current numeric compatibility behavior. When two operands are same-dimension units and existing behavior converts one side before multiplication/division, preserve that behavior explicitly rather than accidentally changing values.

## E3. Migrate every arithmetic operator

Migrate:

- addition/subtraction;
- multiplication/reverse multiplication;
- true division/reverse division;
- floor division/reverse floor division;
- modulo/reverse modulo;
- integer power;
- unary operations;
- conversion;
- dimensionless cancellation.

Required examples:

```python
UnitValue(1, "m") + UnitValue(100, "cm") == UnitValue(2, "m")
(UnitValue(2, "m") * UnitValue(3, "m")).unit == "m**2"
(UnitValue(10, "m") / UnitValue(2, "s")).unit == "m/s"
(UnitValue(5, "m") / UnitValue(2, "m")).unit is None
UnitValue(68, "F").convert_to("C").value == pytest.approx(20)
```

Affine operations that must fail:

```python
UnitValue(20, "C") * UnitValue(2, "m")
UnitValue(20, "C") / UnitValue(2, "s")
UnitValue(20, "C") ** 2
```

## E4. Preserve floor-division and modulo policy

Do not invent new dimensional behavior in this closure pass. Preserve current supported semantics:

- floor division of compatible unit values returns a dimensionless quotient;
- floor division of incompatible units rejects;
- scalar floor division preserves the left unit where currently documented;
- modulo of compatible units returns the divisor/shared unit;
- modulo of incompatible units rejects;
- no result unit string contains `//` or `%`.

Capture these as explicit golden tests before replacing implementation.

## E5. Differential tests

For every declared alias and family:

- construction succeeds;
- normalization matches fixture;
- dimension matches fixture;
- A→B→A round trip is within family tolerance;
- compatible addition/subtraction works;
- incompatible operations reject;
- representative compound multiplication/division/power has expected factors, dimension, scale, and rendering;
- package and single-file results match.

### Workstream E acceptance criteria

- [ ] Every `UnitValue` stores or resolves one structural expression.
- [ ] No arithmetic operator constructs a semantic unit string and reparses it.
- [ ] Dimensionless cancellation is structural.
- [ ] Affine units cannot participate in compound arithmetic.
- [ ] Existing floor/modulo policy is preserved and explicitly tested.
- [ ] Conversion and compatibility are registry-driven.
- [ ] Full legacy fixture and family differential suites pass.

---

# Workstream F — Make the build manifest executable and honest

## F1. Build directly from the topological manifest

The builder must use:

```python
ordered_specs = _topological_sort(MODULE_MANIFEST)
for spec in ordered_specs:
    if spec.include_single_file:
        inline(spec)
```

Group headings may be emitted for readability, but group-derived lists must not control execution order.

The derived `MODULES_CALC`, `MODULES_EXACT`, and `MODULES_MCP` views may remain only for backward-compatible diagnostics/tests.

## F2. Validate actual imports and dynamic targets

Use `ast` to scan every included module for relative imports that refer to repository modules. Verify that each target is in `MODULE_MANIFEST` and declared as a dependency where execution order requires it.

Derive lazy CLI targets from the literal command registry in `eggcalc/cli.py` or from a generated command inventory. Do not maintain a hardcoded four-item lazy-target set that can drift from `COMMANDS`.

Validate MCP dynamic exact-module imports similarly.

## F3. Implement advertised post-build checks

`validate_build_manifest()` or a shared validation pipeline must actually perform:

- duplicate names and paths;
- missing files;
- unknown dependencies;
- dependency cycles;
- deterministic topological order;
- invalid group;
- undeclared relative import dependency;
- missing CLI/MCP dynamic target;
- unconsumed included manifest entry;
- residual package-relative import in a temporary generated file;
- top-level generated symbol collision, with an explicit allowlist for intentional wrapper renames;
- repeated-build byte determinism.

Normal `python build_single.py` and `--validate` must use the same validation implementation.

## F4. Mutation tests

Build synthetic manifests/modules to prove detection of:

- cycle;
- missing dependency;
- dependency declared after consumer but topologically resolvable;
- undeclared relative import;
- missing command target;
- duplicate generated global;
- residual import after generation;
- stable declaration-order tie breaking.

### Workstream F acceptance criteria

- [ ] Topological manifest order drives actual assembly.
- [ ] No manually maintained group list controls build order.
- [ ] Dynamic CLI/MCP targets are mechanically validated.
- [ ] Every check claimed by validator documentation is implemented and tested.
- [ ] Invalid builds fail before replacing the output artifact.
- [ ] Valid repeated builds are byte-identical.

---

# Workstream G — Strict static and installed-wheel verification

## G1. Add typed-package marker

Add `eggcalc/py.typed` and ensure it is included in wheel/sdist metadata. A wheel consumer is not meaningful if mypy treats the package as untyped.

## G2. Expand strict migrated-module checks

Add a dedicated mypy target for:

- `eggcalc.units` and any extracted unit registry/parser modules;
- `eggcalc.mcp.server`;
- `eggcalc._protocol`;
- `eggcalc._version`;
- `build_single.py` or extracted build-manifest helper;
- `tests/typing/consumer.py`.

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

No `ignore_errors`, broad module exclusion, or unqualified `type: ignore` is allowed.

## G3. Remove hidden-import consumer mode

Do not use `--follow-imports=silent` for the closure consumer. Source mode must type-check the real public package:

```bash
python -m mypy --config-file pyproject.toml tests/typing/consumer.py
python tests/typing/consumer.py
```

Fix the public annotations required for this to pass. Do not narrow the consumer until it stops exercising intended public APIs.

## G4. Type-check the installed wheel outside the repository

In a clean venv:

1. install the built wheel and mypy;
2. copy `tests/typing/consumer.py` into an unrelated temporary directory;
3. change working directory outside the repository;
4. assert `eggcalc.__file__` points into the venv;
5. assert `eggcalc/py.typed` is installed;
6. run mypy on the copied consumer;
7. execute the consumer.

Use a Python helper to locate venv executables portably rather than hardcoding only `bin/` paths.

## G5. Add strict Ruff and authority checks

Run a second Ruff invocation for migrated modules with `B904` enabled and targeted annotation/simplification rules. Keep the broad repository profile unchanged if necessary.

Run `scripts/check_authority_boundaries.py` in CI.

### Workstream G acceptance criteria

- [ ] Wheel contains `py.typed`.
- [ ] Migrated modules pass the strict mypy target.
- [ ] Source consumer passes without `--follow-imports=silent`.
- [ ] Installed-wheel consumer passes outside the repository.
- [ ] Wheel identity proves no source-tree import leakage.
- [ ] Strict Ruff and authority-boundary checks pass.
- [ ] Ordinary Ruff, Black, and mypy remain green.

---

# Workstream H — Package/single-file parity and architecture cost proof

## H1. Add a machine-readable authority inventory

Create `scripts/release_inventory.py` that emits canonical JSON for package mode and generated single-file mode:

- package version;
- protocol versions;
- public API names;
- CLI commands, aliases, modules, and symbols;
- all unit declarations and aliases;
- dimensions, scales, offsets, affine flags, categories, displays, base canonicals;
- MCP tools, schemas, metadata, profiles;
- capability fields excluding documented mode-specific fields.

Run each mode in a fresh subprocess. Sort keys and normalize tuples/lists before comparison.

Allowed differences must be an explicit field allowlist in the script. Do not compare only counts.

## H2. Expand release-surface verification

Verify cleanly:

- source API;
- editable install;
- wheel install;
- console script;
- `python -m eggcalc`;
- REPL transcript;
- package MCP stdio;
- generated single-file CLI;
- generated single-file MCP;
- source typed consumer;
- wheel typed consumer;
- package/single-file authority inventory.

## H3. Controlled before/after measurements

Create `scripts/measure_architecture_costs.py` and use identical environments/scripts for:

- baseline `b9df49173ecfc60312780aef998c003af0b000b6`;
- final implementation candidate.

Measure fresh processes for:

- `import eggcalc`;
- `from eggcalc import evaluate`;
- CLI help;
- normal expression;
- exact command;
- MCP initialize;
- compact and full `tools/list` serialization;
- unit registry construction;
- normal and maximum-bound unit parsing;
- representative `UnitValue` compound arithmetic;
- generated single-file startup;
- loaded module count;
- peak traced allocation.

Record:

- full commit SHA;
- OS, architecture, Python version;
- sample count;
- median, mean, standard deviation;
- module counts;
- peak allocation;
- command line.

Commit normalized JSON and a human-readable table under `docs/performance/`. A stable repeated regression greater than 15% requires investigation and explanation; import-boundary regressions are hard failures regardless of timing.

### Workstream H acceptance criteria

- [ ] Package and single-file inventories match except named mode fields.
- [ ] Every release surface passes in a clean environment.
- [ ] Single-file generation remains deterministic.
- [ ] Baseline and final measurements use the same script and environment.
- [ ] Registry/parser/MCP schema costs are measured.
- [ ] No unexplained stable regression above 15% remains.

---

# Workstream I — CI and exact synchronized evidence

## I1. Required CI checks

Add explicit steps or jobs for:

- ordinary Ruff and Black;
- ordinary mypy;
- strict migrated-module mypy;
- strict migrated-module Ruff;
- authority-boundary script;
- build-manifest validation;
- deterministic double build;
- package/single-file authority inventory;
- source typed consumer;
- installed-wheel typed consumer outside source tree;
- focused residual MCP suite;
- focused unit declaration/parser/arithmetic suite;
- release-surface smoke suite;
- full test matrix.

Keep full tests on:

- Ubuntu Python 3.11, 3.12, 3.13, 3.14;
- macOS Python 3.11, 3.12;
- Windows Python 3.11, 3.12.

At least Python 3.11 on each OS must execute the closure-focused tests without platform skips.

## I2. Select one implementation candidate

Before selecting the candidate, land:

- all production code;
- all tests;
- CI workflow changes;
- fixture and inventory scripts;
- baseline/final performance files;
- architecture/changelog corrections.

Any later code, test, or workflow change creates a new candidate and requires a full rerun.

## I3. Evidence identity model

Use:

- `closure_code_sha`: exact implementation candidate tested by the full workflow;
- `closure_workflow_run_id`: exact green workflow for that SHA;
- evidence commit: documentation-only child commit;
- post-evidence workflow: proves documentation-only changes remain green.

Do not edit evidence again solely to embed the SHA of the evidence commit itself.

## I4. Synchronize Release 4–6 evidence

Append a final closure section to:

- `docs/release_4_evidence.md`;
- `docs/release_5_evidence.md`;
- `docs/release_6_evidence.md`.

All three final sections must share:

- one full 40-character `closure_code_sha`;
- one workflow run ID for shared checks;
- exact job names and conclusions;
- exact collected/passed/skipped/xfailed/failed totals per lane;
- grouped skip reasons;
- exact focused MCP and unit suite counts;
- strict mypy/Ruff/authority results;
- source and installed-wheel consumer results;
- manifest/determinism/inventory results;
- release-surface matrix;
- baseline/final performance tables;
- retained compatibility adapters and removal timing;
- explicit non-blocking deferrals.

Historical Windows failures may remain only in clearly labeled historical sections. They must not be presented as current closure status.

Do not use approximate values such as `~3911`, `all pass`, or abbreviated SHAs in final evidence fields.

## I5. Add evidence validation

Create an automated test that rejects:

- mismatched closure SHAs/run IDs;
- abbreviated SHAs;
- approximate count markers;
- arithmetic totals that do not add up;
- missing mandatory jobs;
- contradictory success/failure wording;
- old Windows failures labeled as current;
- Release 6 text claiming registry construction from legacy maps;
- performance tables missing baseline or final identity.

### Workstream I acceptance criteria

- [ ] One exact implementation candidate has all required green jobs.
- [ ] Python 3.11 passes on Linux, macOS, and Windows.
- [ ] Source and installed-wheel strict consumers pass.
- [ ] Unit authority, parser, arithmetic, manifest, inventory, and evidence validators pass.
- [ ] Release 4–6 final sections share one exact code SHA and workflow run.
- [ ] Evidence contains exact counts and no stale current-status claims.
- [ ] A post-evidence workflow passes without SHA-repin churn.

---

# 6. Required focused test files

Create or expand focused groups with names that make CI selection straightforward.

## 6.1 Residual MCP closure

Suggested file: `tests/test_final_mcp_authority_closure.py`

Cover:

- custom profile list/list/call agreement;
- no global profile namespace in instance paths;
- manager facade cannot diverge from runtime context;
- publication rollback identity;
- policy independent of profile;
- reservation-set boundedness after 10,000 terminal calls;
- reservation cleanup after failure/timeout/cancel;
- owner single-assignment after garbage collection;
- serverless initialize rejection;
- explicit owner limits/registry/context enforcement.

## 6.2 Unit declaration authority

Suggested file: `tests/test_final_unit_authority.py`

Cover:

- committed fixture exact equality;
- complete declaration validation matrix;
- registry construction exclusively from declarations;
- generated adapter parity;
- no runtime legacy reads;
- known Fahrenheit/Rankine/Celsius/Kelvin transforms;
- every family base and alias.

## 6.3 Unit parser and arithmetic

Suggested file: `tests/test_final_unit_expression.py`

Cover:

- grammar and full consumption;
- all resource limits;
- finite-scale overflow;
- affine compound rejection;
- direct-construction invariants;
- every `UnitValue` operator;
- floor/modulo golden behavior;
- package/single-file differential cases.

## 6.4 Build, typing, parity, evidence

Suggested files:

- `tests/test_build_manifest_graph.py`;
- `tests/test_release_inventory.py`;
- `tests/test_evidence_consistency.py`;
- `tests/typing/consumer.py`.

Cover all mutation and clean-environment cases described above.

# 7. Required verification commands

Run from a clean checkout of the implementation candidate:

```bash
python -m ruff check .
python -m black --check .
python -m mypy eggcalc --ignore-missing-imports
python -m mypy --config-file pyproject.toml \
  eggcalc/units.py eggcalc/mcp/server.py build_single.py tests/typing/consumer.py
python scripts/check_authority_boundaries.py
python build_single.py --validate
python build_single.py
python scripts/generate_mcp_docs.py --check
python scripts/release_inventory.py --check
python scripts/smoke_release_surfaces.py
python -m pytest tests/test_final_mcp_authority_closure.py -v
python -m pytest tests/test_final_unit_authority.py tests/test_final_unit_expression.py -v
python -m pytest tests/test_build_manifest_graph.py tests/test_release_inventory.py -v
python -m pytest tests/ -v
python -m build
```

Also run:

- deterministic double-build comparison;
- source consumer execution;
- installed-wheel mypy and runtime consumer outside the repository;
- controlled baseline/final architecture-cost collection;
- evidence consistency tests.

# 8. Recommended implementation commits

Keep each commit independently testable.

1. `fix(mcp): close residual profile context and ownership authority leaks`
2. `fix(mcp): bound executor reservation lifecycle storage`
3. `test(units): capture exact pre-migration public unit fixture`
4. `refactor(units): complete and validate declarative unit specifications`
5. `refactor(units): build registry and adapters solely from declarations`
6. `refactor(units): replace legacy compound parser with bounded expressions`
7. `refactor(units): migrate public conversion helpers to registry semantics`
8. `refactor(units): migrate UnitValue arithmetic to structural expressions`
9. `refactor(build): execute and validate the module dependency graph`
10. `chore(types): add typed package marker and strict source-wheel consumer`
11. `test(parity): add authority inventory and clean release-surface matrix`
12. `perf: record controlled release 6 baseline and final costs`
13. `ci: enforce final closure checks across supported platforms`
14. `docs(evidence): synchronize releases 4-6 to exact closure candidate`

Do not combine the declaration migration and `UnitValue` migration in one unreviewable commit.

# 9. Stop and rollback conditions

Stop the active workstream and correct or revert if:

- custom registry profiles disappear from `profiles/list`;
- manager and runtime-context snapshots can differ;
- a failed configuration operation changes any active identity or behavior;
- reservation storage grows after requests reach terminal states;
- a session can be rebound after owner loss;
- any unit alias disappears without an explicit approved migration;
- `UnitRegistry` still reads legacy semantic maps;
- public conversion uses pairwise tables after registry migration;
- `UnitValue` still constructs/reparses semantic unit strings;
- affine units enter compound arithmetic;
- parser limits are declared but not enforced;
- generated adapters become independently maintained tables;
- builder order differs from the manifest graph;
- validator documentation claims checks not implemented;
- strict consumer is made green through hidden imports or broad ignores;
- wheel consumer imports the source checkout;
- package/single-file inventories diverge;
- stable performance regression exceeds 15% without explanation;
- evidence is updated before the candidate workflow is fully green;
- another evidence-only SHA-repin loop begins.

# 10. Final closure checklist

Releases 4, 5, and 6 remain open until every item is checked.

## MCP residual closure

- [ ] Custom profile listing/list/call use one registry namespace.
- [ ] No instance-owned path reads global profile tables.
- [ ] `RuntimeContext` is the sole active configuration/evaluator state.
- [ ] `ConfigManager` cannot diverge from the server context.
- [ ] Configuration publication cannot partially commit.
- [ ] Policy is independent of MCP profile names and has tested runtime effect.
- [ ] Released reservations are removed from live bookkeeping.
- [ ] Reservation storage remains bounded under long-running stress.
- [ ] Session ownership is permanently single-assignment.
- [ ] Serverless production initialization/dispatch fails closed.

## Unit authority

- [ ] A true legacy fixture from `5a1bb34c` is committed and tested.
- [ ] Fixture alias coverage is exact.
- [ ] `UNIT_DEFINITIONS` owns every built-in semantic property.
- [ ] Full declaration validation is implemented.
- [ ] `UnitRegistry` builds only from declarations.
- [ ] Legacy maps are generated immutable adapters.
- [ ] No pairwise conversion table controls runtime behavior.
- [ ] Authority-boundary checks reject legacy runtime reads.

## Unit expressions and arithmetic

- [ ] One bounded parser governs compound semantics.
- [ ] Input/depth/atom/exponent/output/error/finite-scale limits are enforced.
- [ ] `//` and `%` are not unit-expression syntax.
- [ ] Affine compound arithmetic is rejected.
- [ ] Public helpers use registry/expression semantics only.
- [ ] Every `UnitValue` operator uses structural state.
- [ ] Dimensionless cancellation is structural.
- [ ] Existing floor/modulo behavior is preserved and tested.
- [ ] Full legacy/family/package/single-file differential suites pass.

## Build and verification

- [ ] Topological manifest order drives actual assembly.
- [ ] Manifest validation implements every documented check.
- [ ] Dynamic CLI/MCP import targets are mechanically validated.
- [ ] Single-file generation is deterministic and free of residual imports.
- [ ] Wheel contains `py.typed`.
- [ ] Strict migrated-module mypy/Ruff checks pass.
- [ ] Source consumer passes without hidden imports.
- [ ] Installed-wheel consumer passes outside the repository.
- [ ] Package/single-file authority inventories match.
- [ ] All clean release surfaces pass.
- [ ] Controlled baseline/final measurements are committed.
- [ ] No unexplained stable regression above 15% remains.

## CI and evidence

- [ ] Full supported OS/Python matrix is green at one exact candidate.
- [ ] Python 3.11 Linux/macOS/Windows closure tests pass.
- [ ] Exact job and test totals are captured.
- [ ] Release 4–6 final sections share one full code SHA and workflow run.
- [ ] Historical Windows failures are labeled historical only.
- [ ] No approximate counts or stale architecture claims remain.
- [ ] Evidence consistency validation passes.
- [ ] Post-evidence CI passes without repinning evidence.

## 11. Completion definition

This plan is complete only when the active runtime has one MCP configuration authority, one built-in unit authority, one structural compound-unit model, one executable build graph, and one exact cross-platform closure record. Until then, Releases 4, 5, and 6 remain open.