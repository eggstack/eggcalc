# Releases 4–6 Final Authority and Evidence Closure

Status: implementation handoff  
Repository: `eggstack/eggcalc`  
Baseline reviewed: `9a6334d90cf0595934a78b75788f94523fe082d6`  
Depends on:

- `plans/009-releases-4-5-final-closure-pass.md`
- `plans/010-release-6-internal-architecture-and-maintainability.md`
- `plans/011-release-6-corrective-closure-pass.md`

Primary objective: close only the remaining mandatory blockers preventing Releases 4, 5, and 6 from being declared complete. Preserve the useful implementation already landed for lazy CLI loading, angle identity, structural compatibility, deterministic single-file generation, alias-conflict detection, and unowned-session rejection.

This plan is intentionally narrower than plan 011. It does not reopen completed work and it does not add product features. Completion requires one exact current-tip commit with green minimum-runtime CI and synchronized evidence.

## 1. Verified current state

The following work is already materially present and should be retained:

- `eggcalc.cli` resolves exact-command handlers lazily by defining module and symbol;
- importing `eggcalc`, `eggcalc.normalize`, or `eggcalc.cli` does not eagerly load exact implementation modules;
- package-root CLI compatibility exports remain lazy;
- `Dimension.angle` participates in equality and hashing;
- angle propagation has an explicit arithmetic rule;
- `are_units_compatible()` no longer directly falls back to category-string equality;
- compound parsing has string-length and recursion-depth limits;
- duplicate conflicting aliases are rejected during the current registry build;
- unowned sessions are rejected by `McpServer.handle_request()`;
- single-file generation has deterministic byte-comparison coverage;
- generated-artifact residual relative-import checks exist;
- broad CLI, documentation, unit-family, and annotation tests were added.

The following blockers remain and define the complete scope of this plan:

1. `ToolRegistry` exposes mutable nested schema and metadata state;
2. custom registry profiles remain constrained by global `TOOL_PROFILES` validation;
3. configuration parsing, generation assignment, evaluator construction, and activation are not one atomic lifecycle;
4. configuration snapshots are not recursively immutable and accepted `units`/`policy` fields are not fully applied;
5. executor cancellation before worker start can leak `_queued_count`;
6. deprecated explicit-session dispatch bypasses the owner server;
7. the unit registry is still derived from independent legacy authorities;
8. conversions and compound `UnitValue` arithmetic remain table/string driven;
9. compound parsing does not enforce atom-count and exponent bounds and still treats `//` and `%` as unit separators;
10. package version, MCP protocol versions, and build inventory still have duplicate authorities;
11. migrated modules do not have a stricter static-analysis profile or a real typed consumer checked against a wheel;
12. performance tooling exists without controlled before/after evidence;
13. Release 4–6 evidence is stale, internally inconsistent, and not tied to one exact green workflow run.

Releases 4, 5, and 6 remain open until every mandatory criterion in section 15 passes.

## 2. Scope boundaries

### 2.1 In scope

- recursive immutability and consistency for MCP registries and configuration snapshots;
- registry-owned custom profile validation and profile enumeration;
- one integrated atomic server configuration operation;
- exact-once executor reservation accounting;
- owner-server routing for every session dispatch path;
- one declarative source for all built-in unit definitions;
- registry-driven normalization, conversion, compatibility, and compound arithmetic;
- complete bounded unit-expression parsing;
- single-source package version, protocol versions, and build manifest;
- stronger static verification for the migrated architecture;
- package, editable, wheel, console, module, MCP, and single-file parity proof;
- controlled architecture-cost measurements;
- exact current-tip cross-platform CI and synchronized Release 4–6 evidence.

### 2.2 Non-goals

Do not add:

- new calculator grammar;
- new unit families, aliases, or conversion constants except corrections required to preserve existing behavior;
- new exact or MCP tools;
- new MCP transports;
- external runtime dependencies;
- symbolic algebra;
- currency or network-backed conversion;
- arbitrary user-defined compound-unit grammars;
- repository-wide strict typing in one pass;
- a new build system or external bundler;
- public API renaming unrelated to closure;
- performance optimizations that weaken validation or alter documented results.

### 2.3 Preservation requirements

The following behavior must remain compatible unless an existing behavior is explicitly proven erroneous and documented:

- public Python imports and `__all__`;
- `calc` console behavior;
- `python -m eggcalc` behavior;
- REPL behavior;
- exact-command names, aliases, arguments, JSON envelopes, errors, and exit codes;
- MCP tool names, schemas, profiles, and protocol negotiation;
- existing unit aliases and canonical displays;
- generated `eggcalc.py` CLI and MCP behavior;
- Python 3.11 minimum support;
- standard-library-only runtime.

## 3. Required execution order

Implement in this order:

1. MCP recursive immutability and profile authority;
2. atomic configuration lifecycle;
3. executor reservation accounting and owner-session routing;
4. declarative unit source and registry validation;
5. registry-driven simple conversion;
6. bounded structural compound expressions and `UnitValue` migration;
7. version, protocol, limit, and build authority consolidation;
8. strict module-group checks and typed consumer;
9. package/single-file parity and performance measurement;
10. final CI and synchronized evidence.

Do not start final evidence work until all implementation and focused-test workstreams are green locally.

## 4. Workstream A — Close MCP registry and profile authority

### A1. Recursively freeze registry-owned data

Use one recursive ownership boundary for schemas, metadata, and profiles.

Required behavior:

- mappings become immutable mappings;
- lists become tuples;
- sets become frozensets;
- tuples are recursively frozen;
- constructor inputs are detached before publication;
- nested mutable values cannot be changed through `.schemas`, `.metadata`, or `.profiles`;
- `get_schema()` and `get_metadata()` return either recursively immutable values or independent deep mutable copies;
- one accessor policy is documented and applied consistently.

The existing `_deep_freeze()` helper may be corrected and used, but do not retain two divergent copy/freeze implementations for registry state.

### A2. Validate registry consistency before publication

Construction must fail before assigning usable registry state when any of the following occurs:

- handler without schema;
- schema without handler;
- metadata for an unknown tool;
- profile entry for an unknown tool;
- duplicate tool name after normalization;
- duplicate profile name after normalization, if profile normalization is supported;
- malformed profile entries;
- metadata exposure policy with an unsupported value.

Validation errors must be deterministic and identify all offending names where practical.

### A3. Make profiles registry-owned

`McpServerConfig` must not reject a profile solely because it is absent from global `TOOL_PROFILES`.

Choose one of these bounded designs:

1. `McpServerConfig` validates only profile syntax/non-emptiness, and `McpServer` validates membership against its supplied registry; or
2. a registry-aware configuration constructor validates the profile after both objects are available.

Required consequences:

- custom registries may define custom profile names;
- server creation fails clearly when its selected profile is absent from that registry;
- `profiles/list` enumerates only the server registry's profiles plus any documented synthetic `full` profile;
- `tools/list` and `tools/call` use the same registry/profile authority;
- global default registries preserve existing profile behavior.

### Focused tests

Add or correct tests for:

- nested schema dict mutation through `.schemas`;
- nested schema list mutation through `.schemas`;
- nested metadata mutation through `.metadata`;
- constructor-input mutation after registry creation;
- independent-copy mutation from `get_schema()` and `get_metadata()`;
- handler/schema/metadata/profile mismatch rejection;
- custom registry with a custom profile;
- custom profile listing;
- custom profile call authorization;
- global profile absent from custom registry;
- default registry compatibility.

### Acceptance for Workstream A

- [ ] No public registry path can mutate nested internal state.
- [ ] Constructor inputs cannot mutate registry state after construction.
- [ ] Registry consistency is validated before publication.
- [ ] Custom registries own their profile namespace.
- [ ] `profiles/list`, `tools/list`, and `tools/call` share one profile authority.
- [ ] Default MCP behavior remains compatible.

## 5. Workstream B — Implement one atomic configuration lifecycle

### B1. Separate raw candidate, validated candidate, and active snapshot

Introduce explicit lifecycle types or equivalent phases:

- raw configuration input;
- validated candidate with no active generation;
- immutable active snapshot with manager-assigned generation;
- immutable runtime context used by new requests.

Do not use a generation-zero active snapshot as a value that callers must manually repair.

### B2. Add one public server operation

Provide one operation such as:

```python
server.apply_configuration(
    constants={...},
    functions={...},
    policy="strict",
)
```

The exact name may differ, but it must perform, in order:

1. parse raw values;
2. validate names, values, callables, policy, and unsupported fields;
3. acquire the configuration activation lock;
4. assign the next generation under manager ownership;
5. build a complete replacement evaluator/runtime context off to the side;
6. atomically swap the active context pointer;
7. publish the new immutable snapshot;
8. release the lock;
9. leave existing in-flight calls using the context they already captured.

No caller should need to call `replace_validated()` and then `activate_snapshot()` in separate steps.

### B3. Define replacement semantics

Activation is replacement, not incremental mutation.

Required behavior:

- definitions present only in snapshot A disappear after activating snapshot B;
- built-in constants/functions remain according to one documented base-plus-overlay policy;
- server-specific overlays do not mutate evaluator class dictionaries or module globals;
- caches dependent on configuration are recreated or invalidated with the new context;
- two servers may activate conflicting values without cross-talk;
- a failed build or validation leaves the prior context, snapshot, and generation unchanged.

### B4. Handle `units` and `policy` honestly

For this closure pass, choose one explicit scope:

- fully support server-local units through the new immutable unit registry overlay; or
- reject non-empty `units` during validation with a precise `ConfigError` and document that server-local unit registration is unsupported.

Do not accept and ignore `units`.

Define exact policy behavior. If `default`, `strict`, and `permissive` map to evaluator flags, centralize that mapping and test it. Do not store a policy string that has no runtime effect.

### B5. Recursively immutable snapshots

`ConfigSnapshot` must recursively freeze nested accepted values or constrain accepted values to immutable scalar/callable forms.

Requirements:

- nested mappings/lists cannot be mutated after activation;
- `to_dict()` returns a detached serializable copy;
- callable identity is preserved where needed;
- unsupported mutable objects fail validation rather than leaking into active state.

### Focused tests

Add or correct tests for:

- first activation from generation zero;
- monotonic manager-assigned generations;
- invalid policy and non-callable function rejection;
- non-empty units support or explicit rejection;
- snapshot A to B removal semantics;
- failed activation rollback;
- recursive snapshot immutability;
- two servers with conflicting constants/functions/policies;
- concurrent readers observing only old or new context;
- in-flight request retaining its captured context;
- cache invalidation or replacement;
- no mutation of evaluator class/global tables.

Use barriers/events to prove readers never observe mixed generations.

### Acceptance for Workstream B

- [ ] One public operation performs parse, validation, generation assignment, context construction, and activation.
- [ ] Activation is one atomic pointer swap.
- [ ] Failed activation preserves the full prior runtime state.
- [ ] Replacement removes prior overlay entries not present in the new snapshot.
- [ ] Policy has tested runtime meaning.
- [ ] Units are either fully supported or rejected explicitly.
- [ ] Snapshots are recursively immutable.
- [ ] Multiple servers remain behaviorally isolated.

## 6. Workstream C — Fix executor accounting and session routing

### C1. Replace distributed counters with exact-once reservation state

Use one reservation object and one accounting lock, or an equivalent state machine that can prove exact-once transitions.

Required states:

- reserved/queued;
- active;
- cancelled before start;
- completed;
- completed after caller timeout;
- submission failed;
- released.

Required properties:

- every accepted request increments total and queued once;
- queued-to-active decrements queued and increments active once;
- cancellation-before-start decrements queued and total once;
- completion decrements active and total once;
- a timed-out active handler retains total/active occupancy until it actually finishes;
- executor shutdown cancellation releases queued reservations;
- submission failure releases all reservations;
- counters never rely on `max(0, value - 1)` to hide double-release defects.

Expose diagnostics from one consistent snapshot under the accounting lock.

### C2. Correct the done-callback race

The completion callback must distinguish:

- future cancelled before worker wrapper entry;
- future completed after worker entry;
- submission failure before callback installation.

A successful `Future.cancel()` before start must release queued state even though the worker wrapper never runs.

### C3. Bind sessions to an owner server object

Replace owner identity-only behavior with a resolvable owner reference or explicit owner-dispatch callback.

Requirements:

- binding is one-time;
- foreign rebind is rejected;
- owner collection/closure is detected;
- owner reference does not create an uncollectable cycle;
- closing a session removes it from owner tracking;
- closing a server invalidates all owned sessions.

A weak reference is acceptable if lifecycle behavior is deterministic.

### C4. Route deprecated explicit-session calls through the owner

Module-level:

```python
handle_request(request, session=session)
```

must:

1. resolve the session owner;
2. reject unowned, owner-gone, owner-closed, or closed sessions;
3. call `owner.handle_request(request, session=session)`;
4. therefore enforce the owner's registry, profile, evaluator, limits, and configuration.

It must not call `session.handle_message(request)` without server context.

### Focused tests

Add or correct tests for:

- cancellation before worker start;
- repeated queued cancellation stress;
- active timeout retaining occupancy;
- completion after caller timeout;
- shutdown with queued futures;
- submit failure;
- non-negative exact counters;
- saturation and recovery;
- unowned session rejection;
- foreign session rejection;
- owner-closed rejection;
- owner-gone rejection if weak references are used;
- explicit deprecated dispatch enforcing custom profile;
- explicit deprecated dispatch using custom evaluator/config;
- session close tracking and repeated close.

### Acceptance for Workstream C

- [ ] Queued cancellation releases queued and total exactly once.
- [ ] Active timeout retains truthful occupancy until actual completion.
- [ ] Shutdown releases queued reservations.
- [ ] Counter values never become negative and do not leak after stress.
- [ ] Every explicit session dispatch resolves and uses its owner server.
- [ ] Unowned, foreign, closed, owner-closed, and owner-gone sessions are rejected.
- [ ] Deprecated compatibility paths cannot bypass owner policy.

## 7. Workstream D — Establish one authoritative unit declaration

### D1. Introduce an immutable declaration schema

Create one source such as:

```python
@dataclass(frozen=True)
class UnitSpec:
    canonical: str
    aliases: tuple[str, ...]
    dimension: Dimension
    scale: float
    offset: float = 0.0
    affine: bool = False
    display: str | None = None
    category: str | None = None

UNIT_DEFINITIONS: tuple[UnitSpec, ...] = (...)
```

The exact names may differ. The declaration must own:

- canonical identifiers;
- aliases;
- structural dimensions;
- scale to a dimension base;
- affine offset behavior;
- display/canonicalization metadata;
- optional public category labels used only for presentation/compatibility APIs.

### D2. Generate legacy compatibility adapters

Generate, rather than independently maintain:

- `UNIT_ALIASES`;
- `UNIT_CATEGORIES`;
- simple conversion lookup adapters, if retained;
- normalization lookup sets;
- temperature lookup adapters, if retained;
- documentation inventories;
- package/single-file registry data.

Legacy names may remain public, but they must be derived views. They must not independently define conversion or compatibility behavior.

### D3. Validate declarations before registry publication

Reject:

- duplicate canonical names;
- duplicate aliases;
- conflicting aliases;
- empty names or aliases;
- case-normalization collisions where lookup is case-insensitive;
- non-finite or zero scales;
- non-finite offsets;
- affine definitions with unsupported dimensions;
- unknown display canonicals;
- unsupported dimension values;
- duplicate public category/canonical combinations that imply conflicting behavior.

Tests must construct deliberate invalid declaration sets. Do not attempt duplicate detection by iterating a final set.

### D4. Preserve the baseline inventory

Before migration, capture a machine-readable baseline from `9a6334d` containing:

- every accepted alias;
- normalized canonical result;
- category label;
- conversion family;
- conversion factors for representative and exhaustive same-family pairs where feasible;
- affine temperature results;
- canonical display outputs.

Use this as a migration oracle. Any intentional correction must be separately documented and tested.

### Acceptance for Workstream D

- [ ] One immutable declaration is the source of all built-in unit semantics.
- [ ] Legacy public mappings are generated adapters.
- [ ] Every existing public alias is preserved or explicitly migration-noted.
- [ ] Every alias resolves to exactly one definition.
- [ ] Duplicate/conflicting declarations fail deterministically.
- [ ] Package and single-file declarations produce identical registry inventories.

## 8. Workstream E — Move conversion and arithmetic to structural registry semantics

### E1. Registry-driven simple APIs

Migrate these APIs to resolve through `UnitRegistry`:

- `normalize_unit()`;
- `is_unit()`;
- `get_all_units()`;
- `get_unit_category()`;
- `get_conversion_factor()`;
- temperature conversion;
- `UnitValue.convert_to()`.

For multiplicative units, factor calculation must come from registry scales. For affine units, conversion must use explicit scale/offset transforms and `get_conversion_factor()` must not return a misleading factor.

### E2. Introduce an immutable structural compound representation

Use a type such as:

```python
@dataclass(frozen=True)
class UnitExpression:
    dimension: Dimension
    scale: float
    factors: tuple[tuple[str, int], ...]
    affine: bool = False
    display: str | None = None
```

Requirements:

- semantic equality is structural;
- factor ordering is canonical;
- zero exponents are removed;
- scale is finite and bounded;
- affine units cannot enter unsupported multiplication, division, or power;
- display rendering remains separate from semantic identity.

### E3. Migrate `UnitValue` operations

All operations must use resolved structural expressions:

- addition and subtraction;
- multiplication and division;
- floor division;
- modulo;
- integer powers;
- reciprocal operations;
- dimensionless cancellation;
- conversion before arithmetic;
- equality/hash behavior where normalization matters.

`UnitValue.unit` may remain a public display string, but operations must not make compatibility decisions by comparing display strings, category strings, or hand-maintained conversion tables.

### E4. Remove old semantic fallback paths

After parity tests pass:

- remove `_CATEGORY_NAME_TO_DIMENSION` as a semantic recovery path for built-ins;
- remove direct `UNIT_CONVERSIONS` authority from conversion decisions;
- remove `_DERIVED_CATEGORIES` from compatibility decisions;
- retain compatibility adapters only for public introspection or documented legacy exports;
- ensure unknown units cannot become compatible because they share a category label.

### E5. Family and differential verification

Cover all advertised families:

- length;
- time;
- mass;
- volume;
- area;
- speed;
- acceleration;
- pressure;
- force;
- energy;
- power;
- current;
- voltage;
- frequency;
- data;
- data rate;
- angles;
- temperatures.

Development-only comparison against Pint is allowed but must not become a runtime dependency. Invariant tests are mandatory even if Pint is not used.

### Acceptance for Workstream E

- [ ] Simple normalization and conversion resolve through the registry.
- [ ] Affine conversions are explicit and correct.
- [ ] Compound arithmetic uses one immutable structural representation.
- [ ] Category and display strings do not determine compatibility.
- [ ] Dimensionless cancellation is structural.
- [ ] Floor division, modulo, reciprocals, and powers preserve documented behavior.
- [ ] Every advertised family has round-trip and invariant coverage.
- [ ] Package and single-file conversion/arithmetic results match.

## 9. Workstream F — Formalize and fully bound compound parsing

### F1. Define the accepted grammar

Document and implement a small fully consuming tokenizer/parser.

Minimum grammar elements:

- known unit atoms;
- `*` multiplication;
- `/` division;
- integer exponents using one canonical syntax;
- optional accepted compatibility syntax normalized before parsing;
- no implicit acceptance of arbitrary identifiers.

Do not treat arithmetic floor division `//` or modulo `%` as native unit-expression separators. If historical unit strings contain them, normalize those strings at the API boundary into the canonical `/` form before structural parsing and stop rendering new unit strings with `//` or `%`.

### F2. Enforce all resource bounds

Define and enforce:

- `MAX_UNIT_STRING_LENGTH`;
- `MAX_COMPOUND_DEPTH`;
- `MAX_COMPOUND_ATOMS`;
- `MAX_ABS_UNIT_EXPONENT`;
- maximum canonical output length;
- finite scale accumulation;
- bounded error-message length.

The parser must be deterministic and must fully consume input.

### F3. Define malformed-input behavior

Choose one consistent public behavior per API:

- return `None` for internal resolution helpers;
- return `False` for `is_unit()`;
- raise bounded `ValueError` for conversion/arithmetic APIs.

Do not silently treat a malformed compound as an opaque compatible string.

### Focused tests

Add tests for:

- exact boundary lengths;
- overlong strings;
- exact atom limit and one-over-limit;
- exact exponent limit and one-over-limit;
- deep left- and right-associated expressions;
- malformed `**`, repeated operators, empty atoms, and unsupported characters;
- `//` and `%` normalization/rejection policy;
- huge integer exponent text;
- full-input consumption;
- canonical output length;
- no recursion error or pathological runtime at bounds.

### Acceptance for Workstream F

- [ ] Grammar and operator semantics are documented.
- [ ] Atom-count and exponent limits are enforced, not merely declared.
- [ ] `//` and `%` are not semantic unit separators.
- [ ] Parsing fully consumes input.
- [ ] Malformed/excessive input fails deterministically and within bounded resources.
- [ ] Parser behavior matches in package and single-file modes.

## 10. Workstream G — Consolidate metadata and build authorities

### G1. Single package version source

Create one dependency-free version authority, preferably `eggcalc/_version.py`.

Required consumers:

- `eggcalc.__version__`;
- CLI `--version`;
- installed package metadata;
- capability output;
- MCP server information;
- generated single-file version;
- documentation generation where version is emitted.

Configure build metadata to read that same attribute or generated value. Add a wheel test comparing `importlib.metadata.version("eggcalc")` to `eggcalc.__version__`.

### G2. Single MCP protocol-version source

Create one dependency-free protocol module imported by both capabilities and MCP server code.

It must define:

- one ordered tuple of supported versions;
- one derived latest version;
- any negotiation helper needed by both consumers.

No duplicate literal tuple may remain.

### G3. Explicit owners for major limits

Inventory and mechanically test owners for:

- evaluator limits;
- normalization limits;
- MCP request/output/rate/worker limits;
- compound-unit parser limits;
- exact-tool text limits.

Different subsystem limits may differ, but each value must have one owner and imports/adapters elsewhere.

### G4. One build manifest

Replace manually independent `MODULES_CALC`, `MODULES_EXACT`, and `MODULES_MCP` lists with one declaration containing at least:

- module path;
- logical group;
- dependency/order metadata;
- whether the module is package-only or included in single-file mode;
- any special transformation policy.

The builder may derive grouped compatibility lists from this manifest.

Manifest validation must reject:

- duplicate modules;
- missing files;
- dependency cycles;
- invalid order;
- undeclared inlined dependencies;
- unsupported package-relative imports;
- duplicate injected global names where detectable.

### G5. Keep command/tool authorities singular

- `COMMANDS` remains the only CLI command declaration;
- package and single-file adapters derive from it;
- MCP schema/handler/metadata/profile inventories remain split only where necessary and are mechanically cross-validated at import/build/test time;
- shared result/error envelope definitions should have one owner per public contract.

### Acceptance for Workstream G

- [ ] Installed metadata, API, CLI, capabilities, MCP, and single-file versions agree from one source.
- [ ] Protocol versions have one source.
- [ ] Major limits have one documented owner each.
- [ ] Build inventory is one validated declaration with dependency checks.
- [ ] Command metadata is singular.
- [ ] MCP inventory consistency is mechanically verified.
- [ ] `architecture/authority_inventory.md` reflects actual ownership rather than documenting duplicates.

## 11. Workstream H — Add stronger static verification and a real typed consumer

### H1. Strict profile for migrated modules

Add a dedicated mypy configuration or overrides for at least:

- CLI command registry and lazy loader;
- dimension, unit declaration, registry, and parser modules;
- version and protocol authority modules;
- build-manifest contracts;
- MCP registry/configuration lifecycle code;
- shared runtime-context and reservation-state types.

Enable, where applicable:

- `disallow_any_generics`;
- `disallow_incomplete_defs`;
- `check_untyped_defs`;
- `no_implicit_optional`;
- `strict_equality`;
- `warn_redundant_casts`;
- `warn_unreachable`;
- `warn_unused_ignores`;
- `disallow_untyped_defs`.

Do not claim success while excluding a known error in a migrated module.

### H2. Stronger lint profile

Use a dedicated Ruff configuration or explicit command for migrated modules. Add selected checks for:

- exception chaining;
- simplification and return consistency;
- annotations on public helpers;
- import boundaries;
- unused suppression cleanup.

If Ruff cannot express import boundaries, add a deterministic standard-library validation script.

Do not introduce a broad new global ignore.

### H3. Typed external consumer

Add a small consumer outside the package implementation that imports documented public APIs and exercises:

- direct evaluation;
- natural-language evaluation;
- units and conversion;
- capabilities;
- public CLI compatibility exports;
- selected MCP construction APIs if documented public.

Run mypy against the consumer in:

1. source-tree mode;
2. installed-wheel mode in a clean virtual environment.

Runtime-introspection tests for annotations are supplementary and do not replace this requirement.

### Acceptance for Workstream H

- [ ] Migrated modules pass the stronger mypy profile with zero errors.
- [ ] Migrated modules pass the stronger lint profile.
- [ ] No broad new ignore masks closure defects.
- [ ] Stale ignores in migrated code are removed.
- [ ] The typed consumer passes against source and built wheel.
- [ ] Ordinary Ruff, Black, and repository mypy remain green.

## 12. Workstream I — Prove artifact parity and measure architecture costs

### I1. Machine-readable parity inventories

Create one script that emits normalized JSON inventories for package and generated single-file modes.

Compare:

- version;
- public API names;
- command names, aliases, and targets;
- unit aliases, canonicals, dimensions, scales, affine flags, and displays;
- MCP tool names, schemas, metadata, and profiles;
- protocol versions;
- capability fields except explicitly mode-specific values;
- selected calculator/unit/MCP transcripts.

Fail on any unexplained difference.

### I2. Release-surface matrix

Verify in clean environments:

- source-tree import;
- editable install;
- wheel install;
- console script;
- `python -m eggcalc`;
- Python API;
- REPL transcript;
- MCP stdio transcript;
- generated single-file CLI;
- generated single-file MCP;
- typed consumer against wheel.

### I3. Controlled before/after measurements

Use separate clean worktrees or checked-out commits for:

- baseline: `b9df49173ecfc60312780aef998c003af0b000b6` or another explicitly justified pre-corrective Release 6 commit;
- final: the exact closure candidate commit.

Measure fresh processes for:

- `import eggcalc`;
- `from eggcalc import evaluate`;
- CLI help;
- calculator-only expression;
- one exact command;
- MCP initialize;
- compact and full `tools/list` serialization;
- unit registry construction;
- normal and maximum-bound compound parsing;
- generated single-file startup;
- loaded module counts;
- peak traced allocation.

Record:

- OS and architecture;
- Python version;
- sample count;
- median, mean, and variation;
- loaded module count;
- peak memory;
- exact commands;
- noisy-runner caveats.

A repeated stable regression over 15% requires investigation and written justification. Structural import gates remain mandatory regardless of timing noise.

### Acceptance for Workstream I

- [ ] Package and single-file inventories match for all mandatory authorities.
- [ ] All release surfaces pass in clean environments.
- [ ] Repeated generation remains byte-for-byte deterministic.
- [ ] No residual package-relative imports remain.
- [ ] Before/after measurements are recorded at the exact final commit.
- [ ] Lazy loading is visible in module-count evidence.
- [ ] No unexplained stable regression over 15% remains.

## 13. Workstream J — Final CI and synchronized Releases 4–6 evidence

### J1. Required commands at the final candidate

Run from a clean checkout:

```bash
python -m ruff check .
python -m black --check .
python -m mypy eggcalc --ignore-missing-imports
python -m mypy --config-file <strict-config> <migrated-modules-and-consumer>
python build_single.py --validate
python build_single.py
python scripts/generate_mcp_docs.py --check
python scripts/smoke_release_surfaces.py
python <parity-script>
python -m pytest tests/ -v
python -m build
```

Also run the wheel-installed typed consumer and performance collection commands.

### J2. Required CI matrix

The exact final candidate must have successful Python 3.11 jobs on:

- `ubuntu-latest`;
- `macos-latest`;
- `windows-latest`.

Minimum-runtime lanes must exercise:

- full tests;
- import-boundary tests;
- Release 4–6 focused closure tests;
- unit registry/parser/family tests;
- CLI transcripts;
- generated artifact build and smoke;
- MCP stdio transcripts;
- wheel or editable installation;
- typed consumer;
- capability and parity inventories;
- multiprocessing, timeout, and queued-cancellation behavior;
- Windows path, encoding, newline, and console behavior.

Linux may continue testing newer Python versions.

### J3. Update evidence only after the final green run

Preserve historical evidence sections where useful, but add a clearly labeled final closure verification section to:

- `docs/release_4_evidence.md`;
- `docs/release_5_evidence.md`;
- `docs/release_6_evidence.md`.

Each final closure section must identify the same exact closure commit where claims overlap.

`docs/release_6_evidence.md` must record:

- full final commit SHA;
- workflow run ID and stable URL/identifier;
- every relevant job name and conclusion;
- exact OS/Python matrix;
- exact collected, passed, skipped, xfailed, and failed counts;
- skip reasons grouped by category;
- exact Ruff, Black, ordinary mypy, strict mypy, build, docs, parity, and typed-consumer results;
- recursive immutability tests;
- configuration atomicity tests;
- executor cancellation tests;
- owner-session routing tests;
- unit declaration and conflict-validation counts;
- family/round-trip/parser-bound counts;
- source/editable/wheel/single-file outcomes;
- deterministic generation result;
- package/single-file parity result;
- before/after measurements;
- retained compatibility shims and planned removal timing;
- explicitly deferred non-blocking work.

Do not use approximate counts, stale SHAs, phrases such as “subsequent commits,” or local-only observations to claim cross-platform closure.

### J4. Evidence consistency checks

Add a documentation/evidence test that verifies:

- evidence SHA equals the expected final closure SHA input or generated metadata;
- reported test totals are internally consistent;
- required workflow/job fields are present;
- Release 4–6 final closure sections agree on the shared commit;
- no release evidence claims zero errors while also acknowledging an error;
- no stale Windows-failure text is presented as current closure status.

### Acceptance for Workstream J

- [ ] All required commands pass at one exact commit.
- [ ] Python 3.11 Linux, macOS, and Windows jobs pass at that commit.
- [ ] Evidence references the exact commit and workflow run.
- [ ] Test counts are exact and internally consistent.
- [ ] Release 4–6 shared closure claims use the same commit.
- [ ] Performance and parity results are recorded, not merely described.
- [ ] Documentation matches actual authority and import boundaries.

## 14. Required focused test files or groups

The exact file organization may differ, but coverage must be clearly attributable.

### 14.1 MCP authority and lifecycle

- recursive `ToolRegistry` immutability;
- custom profile authority;
- atomic configuration activation;
- failed rollback;
- replacement/removal semantics;
- server isolation;
- queued cancellation exact accounting;
- active timeout accounting;
- shutdown cancellation;
- owner-server session routing;
- deprecated explicit-session policy enforcement.

### 14.2 Unit authority and parsing

- declaration validation;
- complete alias inventory parity;
- duplicate canonical/alias/case-collision rejection;
- simple conversion through registry;
- affine temperature conversions;
- structural compound expression equality;
- every arithmetic operator;
- atom/depth/length/exponent bounds;
- malformed input;
- every advertised family;
- package/single-file parity.

### 14.3 Metadata, build, and typing

- installed version agreement;
- protocol-version agreement;
- limits ownership drift checks;
- build-manifest duplicate/missing/cycle/order failures;
- deterministic build;
- residual import detection;
- package/single-file inventory comparison;
- strict mypy target;
- typed consumer source and wheel modes.

### 14.4 Evidence and performance

- baseline/final measurement schema validation;
- module-count gates;
- no import-time worker creation;
- evidence required fields;
- exact total arithmetic;
- shared closure SHA consistency.

## 15. Explicit final acceptance criteria

Releases 4, 5, and 6 may be marked complete only when every mandatory item below is satisfied.

### MCP registry, configuration, executor, and sessions

- [ ] `ToolRegistry` is recursively immutable through every public path.
- [ ] Registry construction validates handlers, schemas, metadata, profiles, and exposure policy.
- [ ] Custom registries own custom profiles independently of global defaults.
- [ ] `profiles/list`, `tools/list`, and `tools/call` use one registry/profile authority.
- [ ] One public configuration operation parses, validates, assigns generation, builds context, and activates atomically.
- [ ] Failed activation leaves the prior snapshot, generation, evaluator, caches, and behavior unchanged.
- [ ] Snapshot replacement removes prior overlay entries absent from the new snapshot.
- [ ] Configuration snapshots are recursively immutable.
- [ ] Policy has tested runtime meaning.
- [ ] Custom units are fully supported or explicitly rejected before activation.
- [ ] Cancellation-before-start releases queued and total reservations exactly once.
- [ ] Active timeout retains truthful occupancy until actual completion.
- [ ] Executor shutdown releases queued reservations.
- [ ] Counters never leak or become negative under stress.
- [ ] Unowned, foreign, closed, owner-closed, and owner-gone sessions are rejected.
- [ ] Deprecated explicit-session dispatch routes through owner-server policy.

### Unit authority and behavior

- [ ] One declarative unit source owns aliases, canonicals, dimensions, scales, offsets, affine flags, displays, and categories.
- [ ] Legacy unit maps are generated adapters, not independent behavior authorities.
- [ ] Every baseline public alias resolves to exactly one declaration.
- [ ] Duplicate canonicals, aliases, conflicts, empty names, and case collisions fail construction.
- [ ] `normalize_unit()`, `is_unit()`, category lookup, conversion, and `convert_to()` resolve through the registry.
- [ ] Affine temperature conversion is explicit and correct.
- [ ] One immutable structural representation drives compound arithmetic.
- [ ] Compatibility never depends on category or display-string coincidence.
- [ ] Addition, subtraction, multiplication, division, floor division, modulo, powers, reciprocals, and cancellation use structural semantics.
- [ ] Compound parsing enforces length, depth, atom-count, exponent, output-length, and finite-scale bounds.
- [ ] `//` and `%` are not semantic unit-expression separators.
- [ ] All advertised unit families have round-trip and invariant coverage.
- [ ] Existing documented displays remain stable or are explicitly migration-noted.
- [ ] Package and single-file unit inventories and behavior match.

### Metadata, build, and static verification

- [ ] Package version has one source across metadata, API, CLI, capabilities, MCP, and single-file mode.
- [ ] MCP protocol versions have one source.
- [ ] Major limits have one explicit owner each.
- [ ] Command metadata has one source.
- [ ] MCP tool/schema/metadata/profile consistency is mechanically checked.
- [ ] Build module inventory has one validated source with dependency-cycle and order checks.
- [ ] Migrated modules pass the stronger mypy profile with zero errors.
- [ ] Migrated modules pass the stronger lint profile.
- [ ] No broad new ignore masks closure issues.
- [ ] Typed public consumer passes against source and installed wheel.

### Packaging, performance, CI, and evidence

- [ ] Single-file generation is byte-for-byte deterministic.
- [ ] Generated code contains no residual package-relative imports.
- [ ] Package and single-file versions, commands, units, MCP inventories, protocols, and capabilities match.
- [ ] Source, editable, wheel, console, module CLI, Python API, REPL, MCP stdio, and single-file surfaces pass.
- [ ] Before/after import, startup, memory, module-count, schema, registry, parser, and artifact measurements are recorded.
- [ ] Lazy loading is demonstrated by module-count evidence.
- [ ] No unexplained stable regression over 15% remains.
- [ ] Python 3.11 Linux, macOS, and Windows CI passes at the exact final commit.
- [ ] Release 4–6 final closure evidence references that exact commit and workflow run.
- [ ] Test totals and skip reasons are exact and internally consistent.
- [ ] Documentation accurately describes current implementation authority.

## 16. Recommended implementation commits

Keep commits behaviorally scoped and include focused tests with each implementation commit.

1. `fix(mcp): recursively freeze registry state and validate custom profiles`
2. `refactor(mcp): add atomic configuration candidate and runtime-context activation`
3. `fix(mcp): implement exact-once executor reservation accounting`
4. `fix(mcp): route explicit sessions through owner server`
5. `refactor(units): introduce authoritative declarative unit definitions`
6. `refactor(units): derive aliases categories and conversion adapters`
7. `refactor(units): migrate simple conversion to registry semantics`
8. `refactor(units): add bounded structural unit expressions`
9. `refactor(units): migrate UnitValue arithmetic and remove semantic fallbacks`
10. `refactor(meta): consolidate version protocol limits and build manifest`
11. `chore(types): add strict architecture checks and typed wheel consumer`
12. `test(parity): prove package single-file and release-surface parity`
13. `perf: record release 6 architecture baseline and final measurements`
14. `docs(evidence): close releases 4-6 at exact green commit`

Do not combine the unit-authority migration with MCP lifecycle changes in one commit.

## 17. Stop and rollback rules

Stop the current workstream and correct or revert it before continuing if:

- a documented calculator, CLI, unit, exact-tool, or MCP result changes unexpectedly;
- package and single-file behavior diverge;
- alias inventory shrinks without an explicit approved migration note;
- affine units enter unsupported compound arithmetic;
- configuration readers can observe mixed generations;
- activation mutates module/class globals;
- executor counters leak or become negative;
- explicit session dispatch bypasses owner policy;
- parser limits are declared but not enforced;
- a legacy unit map continues independently determining behavior after migration;
- strict checks are made green by broad ignores;
- minimum-runtime CI skips a mandatory closure test;
- performance measurements show a stable unexplained regression over 15%;
- evidence is updated before the exact final workflow is green.

Prefer reverting one bounded workstream over retaining two conflicting semantic authorities.

## 18. Completion definition

This final closure pass is complete only when Eggcalc demonstrates at one exact green commit that:

- Release 4 runtime compatibility evidence is current and cross-platform;
- Release 5 state ownership, configuration, executor, and session isolation are structurally correct;
- Release 6 import boundaries and lazy CLI loading remain intact;
- one registry owns all built-in unit semantics;
- structural expressions drive conversion and arithmetic;
- package, wheel, editable, and single-file surfaces share the same authorities;
- stricter static checks protect the migrated architecture;
- performance and resource effects are measured rather than assumed;
- Python 3.11 Linux, macOS, and Windows CI passes;
- Release 4–6 evidence contains exact reproducible results and no provisional claims.

Until then, Releases 4, 5, and 6 remain open.