# Release 6 Corrective Closure Pass

Status: implementation handoff  
Repository: `eggstack/eggcalc`  
Baseline reviewed: `b9df49173ecfc60312780aef998c003af0b000b6`  
Depends on:

- `plans/009-releases-4-5-final-closure-pass.md`
- `plans/010-release-6-internal-architecture-and-maintainability.md`

Primary objective: complete the unfinished Release 4-6 authority, import, unit-model, static-verification, packaging, performance, and evidence work without expanding Eggcalc's feature scope or changing documented calculator behavior.

This is a corrective closure pass. It must preserve the useful Release 6 work already landed while replacing incomplete overlays, contradictory tests, and evidence claims with one coherent production architecture.

## 1. Current state

The current repository has meaningful Release 6 progress:

- CLI parsing and dispatch moved from `eggcalc.normalize` to `eggcalc.cli`;
- package-root CLI exports are lazy;
- core imports no longer load MCP or exact implementation modules;
- subprocess import-boundary tests exist;
- `Dimension`, `UnitDefinition`, and `UnitRegistry` scaffolding exists;
- command metadata, authority inventory, import auditing, architecture-cost measurement, and build-manifest validation were introduced.

The release remains open because:

1. unresolved Release 4-5 authority defects remain in registry immutability, configuration activation, executor cancellation accounting, session ownership, and evidence;
2. importing `eggcalc.cli` still imports the broad `eggcalc.exact` re-export graph;
3. the command registry names already-imported functions rather than lazy module/symbol targets;
4. the structural unit model falls back to legacy category matching and string signatures;
5. `Dimension.angle` is excluded from equality, hashing, and arithmetic propagation;
6. registry construction silently overwrites duplicate aliases instead of rejecting conflicts;
7. `UnitRegistry` is derived from multiple legacy authorities rather than serving as the authoritative unit definition source;
8. package version, protocol versions, build inventory, and other metadata still have duplicate authorities;
9. stricter module-level Ruff and mypy profiles have not landed;
10. single-file determinism and registry parity are not fully verified;
11. performance tooling exists, but final before/after evidence does not;
12. `docs/release_6_evidence.md` is not tied to one exact green cross-platform commit.

Release 6 must not be marked complete until every mandatory acceptance criterion in this plan passes at one exact commit.

## 2. Scope boundaries

### 2.1 In scope

- closure of the remaining plan 009 authority defects;
- true lazy loading for exact CLI commands;
- correction and completion of structural dimension semantics;
- migration to one authoritative unit registry;
- removal of category/string fallback from compatibility decisions;
- consolidation of version, protocol, limit, command, tool, and build authorities;
- stronger static verification for migrated modules;
- deterministic single-file generation and package/artifact parity;
- controlled architecture-cost measurements;
- exact current-tip CI and release evidence.

### 2.2 Non-goals

Do not add:

- new calculator grammar;
- new unit families or conversion constants except corrections required to make existing definitions internally consistent;
- new exact or MCP tools;
- a new MCP transport;
- runtime dependencies outside the standard library;
- a symbolic algebra engine;
- arbitrary precision quantity libraries;
- currency, calendar-duration, locale, or network-backed conversion features;
- a new external bundler;
- broad public API renaming;
- a repository-wide rewrite unrelated to the identified closure gaps.

## 3. Required sequencing

Implement in this order:

1. close remaining Release 4-5 production authority defects;
2. correct the existing dimension and unit-registry scaffold;
3. establish one declarative authoritative unit source;
4. migrate compatibility, conversion, and compound arithmetic to that source;
5. remove the legacy fallback paths only after parity tests pass;
6. implement true lazy exact-command loading;
7. consolidate remaining metadata/build authorities;
8. tighten static analysis;
9. complete single-file determinism and release-surface parity;
10. record before/after measurements and final evidence.

Do not combine structural unit migration with unrelated calculator syntax changes.

## 4. Workstream A — Close remaining Release 4-5 authority defects

Release 6 cannot close on top of known Release 5 authority defects.

### A1. Recursively immutable `ToolRegistry`

Use one recursive freeze/copy implementation for schemas and metadata.

Requirements:

- nested dictionaries become immutable mappings;
- nested lists become tuples;
- nested sets become frozensets;
- constructor inputs are detached from registry state;
- `.schemas`, `.metadata`, and `.profiles` do not expose mutable nested state;
- `get_schema()` and `get_metadata()` return either immutable views or independent deep copies;
- handler/schema/metadata inventories are validated at construction;
- every profile entry references a registered tool;
- unknown profile names and unknown profile tools fail deterministically;
- custom registries may define custom profiles without being rejected by global `TOOL_PROFILES` validation.

### A2. Complete instance configuration lifecycle

Provide one integrated operation for:

```python
server.apply_configuration(raw_candidate)
```

or an equivalent explicit sequence with no unusable generation gap.

The operation must:

1. parse into a candidate separate from active state;
2. perform semantic validation;
3. assign the next generation under manager ownership;
4. construct a complete immutable evaluator/tool context;
5. atomically replace the active context;
6. preserve the complete previous context on any failure.

The active context must define the behavior of:

- evaluator constants;
- evaluator functions;
- evaluator policy;
- server-local units when supported;
- configuration-aware caches;
- tool execution context.

If per-server custom units remain unsupported, reject them explicitly during validation and document that boundary. Do not accept and then ignore snapshot units.

### A3. Fix cancellation-before-start accounting

Use one reservation state object or equivalent exact-once transition tracking.

Required transitions:

- accepted -> queued;
- queued -> active;
- queued -> cancelled-before-start;
- active -> completed;
- active -> completed-after-caller-timeout;
- submission failure -> released.

If `Future.cancel()` succeeds before worker start:

- decrement queued exactly once;
- release total reservation exactly once;
- do not decrement active;
- leave no positive or negative counter residue.

### A4. Enforce session ownership completely

`McpServer.handle_request()` must reject:

- foreign sessions;
- closed sessions;
- arbitrary unowned sessions;
- sessions whose owner server is closed.

An optional adoption API must be explicit, one-time, tested, and documented.

The deprecated module-level `handle_request(request, session=...)` must route through the session's owner server. It must not call `session.handle_message()` without server context.

### A5. Release 4-5 evidence closure

Before proceeding to final Release 6 evidence:

- rerun the full supported CI matrix at the current implementation commit;
- record Python 3.11 Linux, macOS, and Windows results;
- replace approximate or stale test counts;
- ensure Releases 4 and 5 evidence reference an exact commit and workflow run;
- remove claims not proven by tests or actual implementation paths.

### Acceptance for Workstream A

- nested registry mutation through every public accessor fails or affects only an independent copy;
- registry construction rejects handler/schema/profile inconsistencies;
- custom registry profiles work independently from global profiles;
- one public configuration operation performs parse, validation, generation assignment, and atomic activation;
- failed configuration leaves generation and active behavior unchanged;
- two servers can activate conflicting constants/functions without cross-talk;
- queued cancellation releases queued and total counters exactly once;
- counters remain non-negative under repeated timeout/cancellation stress;
- unowned, foreign, closed, and owner-closed sessions are rejected;
- deprecated explicit-session dispatch uses owner-server policy;
- Release 4 and 5 evidence references one exact green commit.

## 5. Workstream B — Implement true lazy exact-command loading

### B1. Replace eager exact imports

`eggcalc.cli` must not import `eggcalc.exact` or exact implementation modules at module import time.

Change `CommandSpec` so each exact command identifies a defining module and symbol, for example:

```python
CommandSpec(
    name="inspect",
    module="eggcalc.exact.synthesis",
    symbol="inspect_text",
    ...,
)
```

Use `importlib.import_module()` only after dispatch selects the command.

A small cache of resolved handlers is acceptable if:

- it is private;
- duplicate or missing targets fail deterministically;
- cache behavior does not change command results;
- tests can reset or isolate it.

### B2. Avoid the broad exact re-export graph

Do not resolve handlers through `eggcalc.exact.__init__`.

Each command must target the module that defines its implementation. Examples include:

- `eggcalc.exact.synthesis`;
- `eggcalc.exact.config`;
- `eggcalc.exact.markdown`;
- `eggcalc.exact.patch`;
- `eggcalc.exact.shell`.

### B3. Preserve single-file mode

The generated artifact cannot use package imports for inlined modules.

Implement one explicit adapter:

- package mode resolves `module + symbol` lazily;
- single-file mode resolves the same symbolic command definition against generated globals or a generated handler map.

The authoritative command registry must remain one data declaration. Do not maintain a separate command list for the artifact.

### B4. Correct contradictory tests

Replace the current test that asserts CLI import eagerly loads exact tools.

Required subprocess assertions:

- `import eggcalc.cli` loads no exact implementation modules;
- `python -m eggcalc --help` loads no exact implementation modules;
- calculator-only invocation loads no exact implementation modules;
- selecting one exact command loads its defining module;
- selecting one exact command does not load unrelated exact modules;
- package and single-file command inventories match;
- missing module/symbol produces a bounded internal configuration failure, not an unhandled traceback.

### Acceptance for Workstream B

- importing `eggcalc.cli` loads zero `eggcalc.exact.*` implementation modules;
- CLI help and calculator evaluation load zero exact implementation modules;
- each exact command imports only its required module set;
- command names, aliases, help, argument rules, output, and exit codes remain compatible;
- package and single-file dispatch use the same authoritative command metadata;
- command registry validation rejects duplicate names, aliases, missing modules, and missing symbols.

## 6. Workstream C — Correct structural dimension semantics

### C1. Define dimension identity precisely

`Dimension` equality and hashing must include every semantic field.

For the current shape, that includes:

- the eight exponent fields;
- `angle` metadata.

Decide and document whether angle is:

1. a semantic tag on an otherwise dimensionless quantity; or
2. a ninth structural axis.

Whichever model is chosen must be consistent across equality, hashing, multiplication, division, exponentiation, compatibility, and rendering.

Minimum requirements:

- `Dimension(angle=True) != Dimension()`;
- angle equality has a stable hash contract;
- multiplication/division do not silently drop angle state;
- exponentiation follows an explicit documented rule;
- angle units are not accidentally compatible with arbitrary dimensionless values for addition/subtraction.

### C2. Bound and formalize compound parsing

Replace unconstrained regex/string parsing with a small bounded unit-expression parser or strictly bounded tokenizer/parser.

Define:

- accepted tokens;
- maximum input length;
- maximum atom count;
- maximum nesting or grouping depth if grouping is supported;
- maximum absolute exponent;
- accepted operators;
- associativity;
- canonical representation;
- malformed-input behavior.

Do not treat floor division or modulo symbols as ordinary unit-expression division unless they are intentionally retained for backward compatibility and normalized before structural parsing.

### C3. Use structural unit expressions

Introduce an immutable structural representation, for example:

```python
@dataclass(frozen=True)
class UnitExpression:
    dimension: Dimension
    scale: float
    factors: tuple[tuple[str, int], ...]
    display: str | None
```

The exact class name may differ, but compound arithmetic must no longer depend on comparing hand-maintained category strings.

### C4. Remove compatibility fallback

After migration tests pass, `are_units_compatible()` must not fall back to category-name equality.

Required behavior:

- both dimensionless -> compatible;
- one dimensionless and one dimensional -> incompatible;
- both structurally resolved with equal dimensions -> compatible subject to affine/semantic rules;
- unknown or malformed unit -> incompatible or explicit error according to the existing public contract;
- no category-string coincidence can make unknown units compatible.

### Acceptance for Workstream C

- angle participates in equality, hashing, and arithmetic according to one documented model;
- compound parsing has explicit resource bounds;
- equivalent compound expressions normalize to equal structural representations;
- dimensionally different expressions never compare compatible due to category strings;
- malformed or excessive expressions fail deterministically;
- all existing documented display strings remain stable unless migration-noted;
- package and single-file structural results match.

## 7. Workstream D — Make `UnitRegistry` authoritative

### D1. Introduce one declarative unit source

Create one immutable declaration set containing, at minimum:

- canonical symbol/name;
- aliases;
- structural dimension;
- multiplicative scale to dimension base;
- affine offset and affine marker;
- display/canonicalization metadata;
- optional public category label retained only as presentation metadata.

Example conceptual shape:

```python
UNIT_DEFINITIONS: tuple[UnitDefinitionSpec, ...] = (...)
```

The authoritative declaration must generate compatibility adapters such as:

- `UNIT_ALIASES`;
- `UNIT_CATEGORIES`;
- conversion lookup tables;
- normalization lookup sets;
- documentation inventories.

Legacy mappings must no longer independently define behavior.

### D2. Validate construction

Registry construction must reject:

- duplicate canonical names;
- duplicate aliases;
- aliases that map to conflicting definitions;
- non-finite or zero multiplicative scales;
- invalid affine definitions;
- affine units used in unsupported compound operations;
- unknown display canonicals;
- unsupported dimension values;
- empty aliases or canonical names;
- case-normalization collisions where case-insensitive lookup applies.

Do not test duplicate rejection by iterating a final set. Construct deliberate conflicting inputs and assert failure.

### D3. Migrate simple conversion

`normalize_unit()`, `is_unit()`, `get_conversion_factor()`, and `convert_to()` must resolve through the registry.

For affine units:

- use explicit offset-aware conversion;
- never return a misleading multiplicative factor;
- prevent unsupported multiplication/division/power semantics.

### D4. Migrate `UnitValue` arithmetic

Preserve `UnitValue.unit` public display compatibility if required, but perform arithmetic through resolved structural expressions.

Migrate:

- addition/subtraction;
- multiplication/division;
- floor division;
- modulo;
- integer powers;
- reciprocal units;
- dimensionless cancellation;
- equality/hash policy where unit normalization affects identity.

Display strings may remain strings; semantic compatibility must not.

### D5. Differential and property verification

Development-only tests may compare against Pint without adding it as a runtime dependency.

Cover every advertised family and derived dimension:

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

### Acceptance for Workstream D

- one declarative registry is the source of aliases, dimensions, scales, affine behavior, and display metadata;
- all compatibility mappings are generated adapters, not independent authorities;
- conflicting aliases and canonicals fail construction;
- every public alias resolves to exactly one definition;
- conversion round trips pass within documented tolerances;
- affine temperature conversions remain correct;
- compound arithmetic uses structural expressions;
- category fallback is removed;
- all advertised unit families have differential or invariant coverage;
- package and generated artifact registries have identical counts, aliases, definitions, and behavior.

## 8. Workstream E — Consolidate remaining authorities

### E1. Package version

Use one source for package, API, CLI, capabilities, MCP server info, and single-file version.

Preferred approach:

- define `__version__` in a small dependency-free module such as `eggcalc/_version.py`;
- configure setuptools dynamic version metadata using that attribute;
- import the value everywhere else;
- make the builder read or inline the same source.

Add a test that compares installed metadata with `eggcalc.__version__` in a built wheel.

### E2. MCP protocol versions

Move protocol identifiers to a small module that can be imported by both capabilities and MCP server code without a circular import.

There must be one tuple and one derived latest version.

### E3. Limits and command/tool metadata

For each major limit or registry:

- identify one owner;
- make adapters import or derive from that owner;
- add mechanical drift tests.

At minimum cover:

- evaluator limits;
- normalization limits;
- MCP limits;
- command metadata;
- MCP handlers/schemas/metadata/profiles;
- result/error envelopes.

### E4. Build inventory

Replace separately maintained `MODULES_CALC`, `MODULES_EXACT`, and `MODULES_MCP` knowledge with one authoritative build manifest containing module identity, group, and dependency order.

The builder may derive grouped lists from the manifest for compatibility.

Manifest validation must detect:

- duplicate modules;
- missing files;
- dependency cycles;
- invalid ordering;
- undeclared required inlined imports;
- package-relative imports left after generation.

### Acceptance for Workstream E

- installed package metadata, API, CLI, MCP, capabilities, and single-file version agree from one source;
- protocol versions have one source;
- major limits have one explicit owner each;
- tool handler/schema/metadata/profile consistency is mechanically verified;
- command metadata is singular and drives package/single-file behavior;
- build inventory is one validated declaration;
- authority inventory describes actual ownership rather than documenting unresolved duplicates.

## 9. Workstream F — Tighten static verification

### F1. Stronger module profile

Create a strict mypy target for migrated Release 6 modules, including at least:

- `eggcalc/cli.py`;
- unit registry/dimension modules;
- version/protocol/build metadata modules;
- new shared contracts.

Enable as many of the following as practical for that group:

- `disallow_any_generics`;
- `disallow_incomplete_defs`;
- `check_untyped_defs`;
- `no_implicit_optional`;
- `strict_equality`;
- `warn_redundant_casts`;
- `warn_unreachable`;
- `warn_unused_ignores`.

Do not impose repository-wide strict mode in one pass.

### F2. Stronger Ruff profile

For migrated modules, enable selected checks currently omitted globally, such as:

- exception chaining where useful;
- simplification and return checks;
- annotation checks for public helpers;
- import-boundary or banned-import checks through a custom script if Ruff cannot express them.

Do not add broad new ignores.

### F3. External consumer fixture

Add a small typed consumer that imports the documented public API and exercises:

- evaluation;
- normalization;
- units;
- CLI compatibility exports where public;
- capabilities.

Type-check it against source and installed wheel modes.

### Acceptance for Workstream F

- all new/migrated architecture modules pass the stronger mypy profile;
- all new/migrated architecture modules pass selected stronger Ruff rules;
- no broad new global ignore is added;
- stale ignores in migrated modules are removed;
- the typed public consumer passes against source and wheel installs;
- ordinary repository Ruff, Black, and mypy checks remain green.

## 10. Workstream G — Complete single-file determinism and parity

### G1. Deterministic generation

Run generation twice from the same clean source tree and compare bytes.

Exclude or normalize nondeterministic metadata. If commit metadata is embedded, it must be stable for the same source commit.

### G2. Structural parity

Verify package and generated artifact equality for:

- version;
- public API names;
- command inventory;
- unit registry counts and aliases;
- dimensions and conversion behavior;
- MCP tool/schema/profile inventories;
- protocol versions;
- capability output except explicitly documented mode fields.

### G3. Builder robustness

The builder must fail with clear diagnostics for:

- missing manifest modules;
- dependency cycles;
- unsupported imports;
- unresolved lazy command targets;
- residual relative imports;
- duplicate injected names.

### Acceptance for Workstream G

- repeated generation is byte-for-byte deterministic;
- generated code compiles and starts;
- no package-relative imports remain;
- package and artifact command, unit, MCP, protocol, and version inventories match;
- structural unit behavior is not duplicated as a second implementation;
- builder failure modes are tested and bounded.

## 11. Workstream H — Performance and resource evidence

### H1. Record a controlled baseline

Use the existing scripts or one consolidated script to record fresh-process measurements for:

- `import eggcalc`;
- `from eggcalc import evaluate`;
- CLI help;
- calculator-only CLI expression;
- one exact command;
- MCP initialize and compact/full `tools/list` serialization;
- generated single-file startup;
- loaded module counts;
- peak traced allocation;
- unit registry construction;
- structural compound parsing at normal and maximum supported bounds.

### H2. Compare before and after

Use the Release 6 plan commit or another documented pre-corrective commit as baseline and the final implementation commit as the comparison.

Record:

- environment;
- Python version;
- operating system;
- sample count;
- median, mean, and variation;
- module counts;
- memory measurements;
- caveats for noisy shared runners.

### H3. Regression policy

A stable repeated regression greater than 15% requires investigation and written justification.

Hard structural gates remain mandatory regardless of timing noise:

- core import loads no exact or MCP implementations;
- CLI help loads no exact implementations;
- calculator-only invocation loads no exact implementations;
- no import-time threads, processes, or worker pools are created.

### Acceptance for Workstream H

- before/after measurements are recorded at the exact final commit;
- core loaded-module count is materially reduced from the pre-Release 6 architecture;
- lazy CLI behavior is visible in module-count evidence;
- no unexplained material startup, evaluation, schema, or single-file regression remains;
- unit parser and registry construction remain bounded;
- performance changes do not weaken correctness checks.

## 12. Workstream I — CI, documentation, and final evidence

### I1. Required verification commands

At the final candidate commit run:

```bash
python -m ruff check .
python -m black --check .
mypy eggcalc --ignore-missing-imports
python build_single.py --validate
python build_single.py
python scripts/generate_mcp_docs.py --check
python scripts/smoke_release_surfaces.py
python -m pytest tests/ -v
python -m build
```

Also run the strict module-group checks and typed consumer fixture.

### I2. Required CI matrix

The final candidate must include successful Python 3.11 jobs on:

- `ubuntu-latest`;
- `macos-latest`;
- `windows-latest`.

Linux may continue testing newer supported Python versions.

Minimum-runtime lanes must exercise:

- full tests;
- import-boundary tests;
- unit structural tests;
- CLI transcripts;
- generated artifact build/smoke;
- MCP stdio transcripts;
- wheel or editable install as assigned;
- capability output;
- multiprocessing/timeout behavior;
- Windows path, encoding, and newline behavior.

### I3. Documentation updates

Update as required:

- `README.md`;
- `docs/api.md`;
- `docs/quickstart.md`;
- `docs/installation.md`;
- `docs/mcp.md`;
- unit documentation;
- `architecture/overview.md`;
- `architecture/authority_inventory.md`;
- import-boundary documentation;
- single-file builder documentation;
- `AGENTS.md`;
- `CONTRIBUTING.md`;
- `CHANGELOG.md`;
- `docs/release_4_evidence.md`;
- `docs/release_5_evidence.md`;
- `docs/release_6_evidence.md`.

### I4. Evidence requirements

`docs/release_6_evidence.md` must record:

- exact final commit SHA;
- workflow run ID and stable identifier;
- every relevant job name and conclusion;
- exact Python/OS matrix;
- exact collected/passed/skipped/failed counts;
- skip reasons;
- Release 4-5 prerequisite closure status;
- import-boundary results;
- lazy command-loading results;
- registry conflict-validation results;
- unit alias/family/differential test counts;
- static-analysis commands and results;
- source/editable/wheel/single-file results;
- deterministic generation hash or byte-comparison result;
- before/after architecture measurements;
- retained compatibility shims and removal timing;
- explicitly deferred non-blocking work.

Do not use:

- approximate counts such as `3282+`;
- phrases such as `subsequent commits`;
- expected or assumed CI results;
- local-only evidence to claim cross-platform closure;
- claims of laziness while exact modules load eagerly;
- claims of authoritative units while legacy mappings independently define behavior.

### Acceptance for Workstream I

- all required commands pass at the exact final commit;
- Python 3.11 Linux, macOS, and Windows jobs pass;
- evidence references that exact commit and workflow run;
- test counts are exact and internally consistent;
- Releases 4, 5, and 6 evidence agree on the tested commit where they share closure claims;
- documentation matches actual module and authority boundaries;
- no mandatory criterion is marked complete based only on intention or local observation.

## 13. Required focused test matrix

### 13.1 Release 4-5 closure

- recursive registry immutability through constructor inputs and accessors;
- registry consistency and custom profile validation;
- parse/validate/build/activate configuration lifecycle;
- failed configuration rollback;
- conflicting server-local constants/functions;
- cancellation before start;
- timeout while active;
- repeated close;
- unowned/foreign/closed session rejection;
- deprecated explicit-session owner routing.

### 13.2 Lazy CLI

- package import;
- CLI import;
- CLI help;
- calculator expression;
- each exact command target;
- unrelated exact modules remain unloaded;
- command target failure;
- reverse import order;
- package/single-file parity.

### 13.3 Dimensions and units

- angle identity/hash/arithmetic;
- all base dimensions;
- equivalent derived dimensions;
- incompatible dimensions;
- malformed and resource-bound compound expressions;
- duplicate canonical and alias rejection;
- case-normalization collisions;
- every alias lookup;
- conversion round trips;
- affine temperature conversions;
- compound multiplication/division/power;
- reciprocal units;
- dimensionless cancellation;
- floor division and modulo semantics;
- display golden cases;
- differential reference cases;
- package/single-file parity.

### 13.4 Authority and packaging

- installed version agreement;
- protocol version agreement;
- limits agreement;
- command registry agreement;
- MCP inventory agreement;
- build manifest validation;
- deterministic generation;
- source/editable/wheel/single-file imports;
- typed external consumer.

### 13.5 Performance and resources

- fresh-process import measurements;
- exact module counts by surface;
- no import-time thread/process creation;
- bounded unit parser;
- bounded registry construction;
- compact/full schema serialization;
- repeated generation stability.

## 14. Explicit final acceptance criteria

Release 6 is complete only when every mandatory item below is satisfied.

### Release 4-5 prerequisite closure

- [ ] `ToolRegistry` is recursively immutable through every public path.
- [ ] Registry construction validates handler/schema/metadata/profile consistency.
- [ ] Custom registries can own custom profiles independently.
- [ ] One integrated configuration API parses, validates, assigns generation, and atomically activates.
- [ ] Failed activation leaves complete prior state unchanged.
- [ ] Cancellation-before-start releases queued and total reservations exactly once.
- [ ] Executor counters never become negative under repeated stress.
- [ ] Unowned, foreign, closed, and owner-closed sessions are rejected.
- [ ] Deprecated explicit-session dispatch uses owner-server policy.
- [ ] Release 4 and 5 evidence is exact and green at the prerequisite closure commit.

### Import and CLI architecture

- [ ] `import eggcalc` loads no exact implementation modules.
- [ ] `import eggcalc` loads no MCP modules.
- [ ] `import eggcalc.cli` loads no exact implementation modules.
- [ ] CLI help loads no exact implementation modules.
- [ ] Calculator-only CLI execution loads no exact implementation modules.
- [ ] Exact command handlers load only after command selection.
- [ ] Exact command handlers resolve from defining modules, not broad re-exports.
- [ ] Package and single-file command inventories and behavior match.
- [ ] Existing documented CLI imports, output, errors, and exit codes remain compatible.

### Structural dimensions and units

- [ ] Angle semantics participate correctly in equality, hashing, and arithmetic.
- [ ] Compound parsing is formally defined and resource-bounded.
- [ ] One immutable structural representation drives compound arithmetic.
- [ ] Compatibility never falls back to category-string equality.
- [ ] One declarative registry defines aliases, canonicals, dimensions, scales, affine behavior, and display metadata.
- [ ] Duplicate/conflicting aliases and canonicals fail construction.
- [ ] Every public alias resolves to exactly one definition.
- [ ] Simple and compound conversions use registry semantics.
- [ ] Affine temperature behavior remains correct and explicit.
- [ ] Existing documented displays remain stable or are migration-noted.
- [ ] Differential/invariant tests cover every advertised family.
- [ ] Package and single-file unit registries and behavior match.

### Authority and static verification

- [ ] Package version has one source across installed metadata, API, CLI, MCP, capabilities, and single-file mode.
- [ ] MCP protocol versions have one source.
- [ ] Major limits have one explicit owner each.
- [ ] Command metadata has one source.
- [ ] MCP handler/schema/metadata/profile consistency is mechanically checked.
- [ ] Build module inventory has one source and dependency validation.
- [ ] Migrated modules pass the stronger mypy profile.
- [ ] Migrated modules pass selected stronger Ruff checks.
- [ ] No broad new ignore is introduced.
- [ ] Typed public consumer passes against source and wheel modes.

### Packaging, performance, and evidence

- [ ] Single-file generation is byte-for-byte deterministic for the same source commit.
- [ ] Generated code contains no residual package-relative imports.
- [ ] Package and single-file versions, commands, units, MCP inventories, and capabilities match.
- [ ] Source, editable, wheel, console script, module CLI, Python API, REPL, MCP stdio, and single-file surfaces pass.
- [ ] Before/after import, startup, memory, module-count, schema, and registry measurements are recorded.
- [ ] No unexplained material regression remains.
- [ ] Python 3.11 Linux, macOS, and Windows CI passes at the exact final commit.
- [ ] Release 6 evidence records exact counts, workflow identifiers, measurements, and retained shims.
- [ ] Releases 4-6 documentation accurately describes actual implementation authority.

## 15. Recommended implementation commits

Keep commits reviewable and behaviorally scoped:

1. `fix(mcp): close recursive registry and profile authority gaps`
2. `fix(mcp): add atomic configuration activation and rollback`
3. `fix(mcp): correct queued cancellation and session ownership`
4. `refactor(cli): resolve exact commands lazily by module and symbol`
5. `fix(units): correct angle identity and bound compound parsing`
6. `refactor(units): introduce authoritative declarative unit registry`
7. `refactor(units): migrate conversion and compatibility to registry`
8. `refactor(units): migrate compound UnitValue arithmetic`
9. `refactor(meta): consolidate version protocol limits and build manifest`
10. `chore(types): add strict Release 6 static verification`
11. `test(single): prove deterministic generation and parity`
12. `docs(evidence): close releases 4-6 at exact green commit`

Implementation commits should include their focused tests. Do not postpone all tests to the final evidence commit.

## 16. Stop and rollback rules

Stop and correct the current workstream before continuing if:

- a documented calculator result changes unexpectedly;
- package and single-file behavior diverge;
- structural compatibility disagrees with established conversion semantics;
- registry migration silently drops aliases;
- affine units enter unsupported compound arithmetic;
- CLI lazy loading changes help/output/exit behavior;
- a configuration activation can expose mixed generations;
- executor counters become negative or leak after cancellation;
- minimum-runtime CI introduces mandatory-feature skips;
- benchmark changes reveal a stable unexplained regression greater than 15%.

Prefer reverting one bounded workstream over adding compatibility branches that preserve two conflicting semantic authorities.

## 17. Completion definition

This corrective pass is complete when Eggcalc can demonstrate, at one exact green commit, that:

- Releases 4 and 5 production authority is actually closed;
- the calculator core, CLI, exact commands, and MCP have intentional import boundaries;
- exact CLI handlers load only on demand;
- structural dimensions, not category strings, determine unit compatibility;
- one registry owns unit semantics and generates compatibility adapters;
- package, wheel, editable install, and single-file artifacts share the same authorities;
- stricter static checks protect the migrated architecture;
- performance and resource effects are measured rather than assumed;
- Linux, macOS, and Windows minimum-runtime CI passes;
- release evidence contains exact, reproducible results rather than provisional claims.
