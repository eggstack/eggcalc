# Release 6 — Internal Architecture and Maintainability

Status: ready for implementation handoff after Releases 4–5 closure  
Repository: `eggstack/eggcalc`  
Depends on:

- `plans/001-correctness-protocol-hardening-roadmap.md`
- `plans/006-release-4-runtime-compatibility-and-capability-negotiation.md`
- `plans/007-release-5-state-isolation-and-concurrency-hardening.md`
- `plans/008-releases-4-5-corrective-closure-pass.md`
- `plans/009-releases-4-5-final-closure-pass.md`

Primary objective: reduce internal coupling and long-term semantic complexity without changing Eggcalc's documented calculator grammar, supported release surfaces, deterministic MCP behavior, standard-library-only runtime, or generated single-file distribution.

Release 6 is an architecture release. It must improve boundaries, authority, structural unit semantics, static verification, and measurable startup behavior while preserving the externally observable behavior locked by Releases 1–5.

## 1. Entry condition

Do not begin implementation until the final mandatory criteria in `plans/009-releases-4-5-final-closure-pass.md` are satisfied at the current repository tip.

At minimum, the implementation agent must confirm before the first Release 6 refactor:

- current-tip CI is green on Python 3.11 for Linux, macOS, and Windows;
- Release 4 and Release 5 evidence files reference the exact green commit;
- explicit MCP servers no longer rely on compatibility-global behavior;
- the remaining configuration, registry, executor, session, and evidence discrepancies identified by plan 009 are closed;
- the package and generated single-file artifact pass the full release-surface smoke suite.

If those conditions are not true, stop Release 6 work and finish plan 009 first. Do not mix unresolved Release 5 authority fixes into the Release 6 architecture series.

## 2. Current architectural pressure

The current repository has several deliberate compatibility layers that are now expensive to maintain:

1. `eggcalc.__init__` imports evaluator, normalization, unit, CLI, and capability surfaces eagerly.
2. `eggcalc.normalize` contains natural-language normalization, argument parsing, CLI dispatch, help text, and exact-tool command imports.
3. Importing `eggcalc.normalize` imports selected functions through `eggcalc.exact`, whose package initializer re-exports most exact-tool modules.
4. The console script points directly to `eggcalc.normalize:main`, reinforcing the normalization/CLI coupling.
5. Unit compatibility and compound arithmetic remain string- and category-oriented even though arithmetic behavior is now extensively regression-tested.
6. Unit aliases, conversion factors, categories, canonical names, display strings, simplification rules, and parser lookup structures are maintained through multiple derived mappings.
7. Protocol versions, resource limits, tool metadata, function metadata, version strings, and result-envelope conventions have multiple representations or adapter copies.
8. `build_single.py` maintains an explicit module order and substantial import-rewriting logic that must remain synchronized with package refactors.
9. Ruff and mypy are enabled broadly, but several stronger checks remain disabled repository-wide because legacy modules have not been tightened incrementally.
10. Import latency, loaded-module count, cold CLI startup, single-file startup, MCP schema serialization, and memory costs are not recorded as release evidence.

Release 6 must address these pressures in bounded stages. It must not become a broad rewrite.

## 3. Required end state

At completion, all of the following must be true:

1. `import eggcalc` does not eagerly import `eggcalc.exact`, `eggcalc.mcp`, argparse-based CLI dispatch, or unrelated repository-inspection modules.
2. Core calculator APIs remain available from `eggcalc` with their documented names.
3. CLI parsing and dispatch are separate from pure natural-language normalization.
4. Exact-tool CLI commands load their implementation modules only when selected.
5. Unit compatibility is determined by structural dimensions rather than category-name or display-string coincidence.
6. Unit display remains backward compatible for all documented expressions unless a separately documented correction is required.
7. One authoritative unit registry defines canonical units, aliases, scale, offset/affine behavior, dimensions, and display metadata.
8. Major process-wide constants, protocol identifiers, tool definitions, and result contracts have one authoritative source each.
9. The generated single-file artifact is built from the same architecture declarations rather than a manually divergent dependency model.
10. New or migrated architecture modules pass stronger Ruff and mypy checks without repository-wide blanket suppressions.
11. Import, startup, memory, and schema-serialization baselines are recorded and compared before release closure.
12. Package, CLI, Python API, MCP stdio, wheel, editable install, and single-file behavior remain equivalent for affected features.

## 4. Scope boundaries

### 4.1 In scope

- core import-graph decoupling;
- separation of normalization, CLI parsing, command dispatch, and presentation;
- lazy loading of exact and MCP command surfaces where appropriate;
- structural unit-dimension model and incremental migration;
- authoritative unit and metadata registries;
- consolidation of duplicated version, protocol, limit, metadata, and result-envelope definitions where bounded;
- static-analysis tightening by module group;
- deterministic import/startup/memory/schema benchmarks;
- single-file builder adaptation;
- architecture tests, migration documentation, and release evidence.

### 4.2 Non-goals

Do not include:

- new calculator syntax;
- new exact or MCP tools;
- a new MCP transport;
- removal of the single-file artifact;
- runtime dependencies outside the Python standard library;
- a full parser rewrite;
- arbitrary public API renaming;
- replacing the AST evaluator;
- introducing a general-purpose symbolic algebra system;
- changing established conversion constants merely for stylistic reasons;
- currency conversion, live exchange rates, calendar-aware duration arithmetic, or locale-aware quantity parsing;
- broad performance micro-optimization unrelated to measured architecture costs;
- removal of all compatibility APIs in one release;
- a wholesale repository layout rewrite.

## 5. Compatibility invariants

The following are release invariants and must be captured in tests before structural work begins:

- `from eggcalc import evaluate, evaluate_raw, UnitValue, EvaluationError` remains valid.
- `python -m eggcalc`, `calc`, source checkout, editable install, wheel install, and generated `eggcalc.py` remain supported.
- documented natural-language expressions preserve results and errors.
- direct evaluator expressions preserve Release 1 grammar semantics.
- existing unit aliases continue to resolve.
- existing unit display strings remain stable where documented or asserted by golden tests.
- temperature conversion remains affine and does not become ordinary multiplicative arithmetic.
- MCP tool names, profiles, schemas, output envelopes, and protocol lifecycle remain unchanged unless the change is explicitly documented as an internal-only serialization normalization with byte-equivalent JSON semantics.
- deterministic exact tools remain deterministic.
- standard-library-only runtime remains enforced in packaging metadata and clean-environment tests.
- generated single-file behavior matches package behavior for all changed paths.

## 6. Workstream A — Establish architecture baselines and dependency rules

### A1. Capture the current import graph

Add a deterministic development script, for example `scripts/audit_import_graph.py`, that runs selected imports in fresh subprocesses and records:

- modules loaded after `import eggcalc`;
- modules loaded after `from eggcalc import evaluate`;
- modules loaded after `import eggcalc.normalize`;
- modules loaded after `python -m eggcalc --help`;
- modules loaded after a calculator expression;
- modules loaded after an exact CLI command;
- modules loaded after MCP startup/initialize;
- import wall time using repeated fresh subprocesses;
- peak traced Python allocation using `tracemalloc` where stable;
- imported `eggcalc.exact.*` and `eggcalc.mcp.*` module counts.

Output must be deterministic JSON with environment metadata and repeated-sample statistics. Wall-clock values are evidence, not initially hard CI gates.

### A2. Define import-layer rules

Document and enforce the intended dependency direction:

```text
eggcalc public API facade
    -> evaluator / unit API / normalization API / capabilities

CLI entry point
    -> public calculator API
    -> command registry
        -> lazy exact-tool modules
        -> lazy MCP entry point

MCP
    -> evaluator / units / exact tools / MCP schemas

exact tools
    -> exact shared contracts and standard-library helpers
    -/-> calculator CLI
```

Add an AST-based import-boundary test or small standard-library checker. At minimum, fail CI when:

- evaluator or units import CLI modules;
- core package initialization imports `eggcalc.exact` or `eggcalc.mcp`;
- exact modules import CLI dispatch;
- normalization imports argparse or exact implementation modules after the split;
- MCP server imports CLI dispatch.

### A3. Baseline behavior fixtures

Before moving code, capture:

- representative CLI transcripts;
- public import smoke tests;
- normalized-expression golden cases;
- exact command transcripts;
- MCP initialize/list/call transcripts;
- unit arithmetic and display golden cases;
- package/single-file parity cases.

These fixtures are the behavioral guardrail for the release.

### Acceptance for Workstream A

- baseline import JSON is committed as release evidence or generated deterministically by a documented command;
- import-layer rules are documented;
- CI contains import-boundary tests;
- behavior fixtures pass before refactoring begins;
- no runtime dependency is added.

## 7. Workstream B — Decouple the core public API from CLI and exact tools

### B1. Make package initialization a narrow facade

Refactor `eggcalc.__init__` so it exports documented core APIs without importing:

- argparse;
- exact-tool package initializers;
- MCP modules;
- CLI command registries;
- repository/manifest/patch inspection modules.

Permitted approaches:

- direct imports from small core modules;
- PEP 562 `__getattr__` for compatibility-only lazy exports;
- explicit compatibility shims that import only on attribute access.

Do not use broad dynamic import magic for ordinary core names. Core APIs should remain statically discoverable and type-checkable.

### B2. Preserve compatibility imports

Create explicit tests for every name in the documented `eggcalc.__all__` contract. Classify each export as:

- eager core export;
- lazy compatibility export;
- CLI-only export retained temporarily;
- deprecated export with documented removal timing.

If `main`, `run`, or help functions remain importable from the package root, they must be lazy and must not load exact or MCP modules until invoked.

### B3. Avoid the eager `eggcalc.exact` re-export graph

Core and CLI code must import exact functions from their defining modules or through a lazy command loader, not through `from .exact import ...`.

The broad `eggcalc.exact` re-export package may remain as a compatibility surface, but:

- importing `eggcalc` must not import it;
- calculator evaluation must not import it;
- basic CLI help must not import it;
- exact commands may import only the modules they use;
- its compatibility and startup cost must be documented.

### B4. Add hard structural gates

In subprocess tests, assert:

- `import eggcalc` loads zero `eggcalc.exact.*` implementation modules;
- `import eggcalc` loads zero `eggcalc.mcp.*` modules;
- `from eggcalc import evaluate` does not load CLI dispatch;
- a calculator-only CLI invocation does not load unrelated exact modules;
- selecting one exact command does not necessarily load the entire exact package graph;
- MCP startup loads MCP dependencies deliberately and predictably.

### Acceptance for Workstream B

- package initialization is a narrow facade;
- existing documented root imports remain valid or have explicit deprecation coverage;
- core import tests prove exact/MCP decoupling;
- no circular-import workaround relies on mutable global patching;
- public type information remains available;
- package and single-file public imports match.

## 8. Workstream C — Separate normalization from CLI dispatch

### C1. Define module responsibilities

Introduce or converge on explicit boundaries. Exact filenames may differ, but the responsibilities must be distinct:

- `normalization`: pure text-to-expression transforms and normalization metadata;
- `cli`: argument parsing, output mode selection, error-to-exit-code mapping, and top-level dispatch;
- `commands` or `cli_commands`: declarative command metadata and lazy handler resolution;
- `presentation`: result formatting where useful;
- `__main__`: minimal call to the CLI entry point.

`normalize.py` may remain as a compatibility module, but it should become a thin re-export/wrapper rather than the owner of argparse, exact command imports, and normalization internals.

### C2. Create a declarative command registry

Define immutable command specifications containing only lightweight metadata:

- command name and aliases;
- help text;
- argument shape or parser-builder callback;
- handler import path or lazy loader;
- output mode support;
- capability/platform requirements;
- command category.

Do not store imported exact-tool handler functions in the initial registry if doing so recreates eager imports.

The same registry should drive:

- argparse subcommand creation;
- help/inventory generation;
- command lookup;
- tests for duplicate aliases;
- documentation generation where practical.

### C3. Preserve CLI behavior

Maintain:

- result-only output conventions;
- current JSON output envelopes;
- exit codes;
- stderr/stdout separation;
- REPL behavior;
- `--help`, `--usage`, `--capabilities`, and `--mcp` behavior;
- Windows encoding/path behavior established by Release 4;
- package/single-file transcript parity.

### C4. Prevent CLI coupling from returning

Add tests that fail if the pure normalization module imports:

- `argparse`;
- `eggcalc.exact`;
- MCP modules;
- installer or packaging code.

### Acceptance for Workstream C

- natural-language normalization can be imported and used without CLI or exact-tool imports;
- the console script points to the dedicated CLI entry point;
- `python -m eggcalc` uses the same CLI entry point;
- command help and dispatch derive from one registry;
- command aliases are unique and validated;
- existing CLI transcripts remain stable;
- single-file CLI dispatch matches package behavior.

## 9. Workstream D — Introduce structural unit dimensions

This is the highest semantic-risk part of Release 6. Implement it incrementally behind parity tests and shadow validation.

### D1. Define immutable structural types

Introduce immutable internal types, for example:

```python
@dataclass(frozen=True, slots=True)
class Dimension:
    length: int = 0
    mass: int = 0
    time: int = 0
    current: int = 0
    temperature: int = 0
    amount: int = 0
    luminous_intensity: int = 0
    information: int = 0

@dataclass(frozen=True, slots=True)
class UnitDefinition:
    canonical: str
    dimension: Dimension
    scale: float
    offset: float = 0.0
    affine: bool = False
    aliases: tuple[str, ...] = ()
    display: str | None = None
```

The concrete representation may instead use a normalized tuple or immutable sparse map. It must provide deterministic equality, multiplication, division, integer power, and dimensionless detection.

Do not use mutable dictionaries as public dimension identities.

### D2. Define the base-dimension policy

Document the exact base dimensions used by Eggcalc. At minimum, account for:

- length;
- mass;
- time;
- electric current;
- thermodynamic temperature;
- amount of substance where present;
- luminous intensity where present;
- information/data.

Angles may remain dimensionless with semantic metadata if that matches current behavior. Document the decision.

Map derived categories structurally, including at least:

- area: `L^2`;
- volume: `L^3`;
- speed/data rate: base dimension divided by time;
- acceleration: `L T^-2`;
- force: `M L T^-2`;
- pressure: `M L^-1 T^-2`;
- energy: `M L^2 T^-2`;
- power: `M L^2 T^-3`;
- frequency: `T^-1`;
- charge/voltage/resistance where supported;
- information rate: `Information T^-1`.

### D3. Treat affine units explicitly

Temperature units require explicit affine conversion rules. Structural dimension equality alone is insufficient.

Requirements:

- absolute temperature conversions use scale plus offset;
- incompatible affine/multiplicative compound operations are rejected;
- temperature units cannot silently participate in arbitrary multiplication/division as ordinary scaled units;
- current documented temperature behavior remains covered by golden tests;
- errors are deterministic and explain the affine restriction.

### D4. Build one authoritative unit registry

Replace manually synchronized derived mappings with one registry source that can generate:

- alias-to-definition lookup;
- canonical-unit lookup;
- dimension lookup;
- conversion scale/offset behavior;
- normalization lookup;
- parser unit-name inventory;
- documentation inventory;
- single-file unit data;
- category compatibility adapters where public compatibility requires them.

Registry construction must fail deterministically on:

- duplicate aliases;
- aliases assigned to conflicting definitions;
- invalid canonical names;
- non-finite scales/offsets;
- zero scales;
- affine definitions used in unsupported compound declarations;
- inconsistent display/canonical metadata.

### D5. Introduce a parsed unit-expression model

Compound units must be represented structurally rather than inferred from string coincidence.

A parsed internal unit expression should retain:

- structural dimension;
- conversion scale relative to the chosen canonical basis;
- normalized factors/exponents for deterministic display;
- affine status where applicable;
- original or preferred display metadata where needed.

Support the existing documented compound forms, including multiplication, division, integer powers, short area/volume forms, and reciprocal units.

Set explicit bounds for:

- expression length;
- factor count;
- nesting/parentheses if supported;
- exponent magnitude;
- simplification work.

### D6. Migrate in shadow mode

Use a staged sequence:

1. Build the structural registry from current unit data.
2. Generate and compare legacy aliases/categories/conversion factors.
3. Parse all existing unit fixtures through both systems.
4. Shadow-check compatibility decisions during tests.
5. Switch `are_units_compatible()` to structural dimensions.
6. Switch conversion-factor resolution to registry definitions.
7. Switch multiplication/division/power simplification to structural unit expressions.
8. Remove or quarantine legacy category/string inference only after parity is proven.

Do not switch every path in one commit.

### D7. Preserve display compatibility

Separate semantic identity from display rendering.

Requirements:

- structural dimensions determine compatibility;
- normalized factor metadata determines display;
- existing simple-unit display strings remain stable;
- common compound-unit output remains stable where already documented;
- canonicalization changes require explicit fixture updates and changelog notes;
- dimensionless cancellation returns no unit;
- zero powers return dimensionless results;
- unit equality/hash behavior remains documented.

### D8. Differential and property tests

Add tests for:

- every registered alias resolving to exactly one definition;
- round-trip conversion across every unit family;
- same-dimension compatibility independent of category labels;
- incompatible dimensions rejecting operations;
- multiplication/division dimension identities;
- integer power identities;
- compound simplification;
- area/volume equivalence;
- data rate versus data storage distinctions;
- temperature affine conversions and rejected compounds;
- scalar/unit and reciprocal-unit behavior;
- malformed/bounded unit expressions;
- package/single-file parity.

Development-only differential tests may use Pint when installed, but Pint must not become a runtime or mandatory release dependency. Differential cases must be committed as ordinary expected fixtures so CI remains self-contained.

### Acceptance for Workstream D

- unit compatibility uses structural dimensions;
- one authoritative registry generates aliases and conversion behavior;
- every existing unit alias is accounted for;
- affine temperature semantics are explicit;
- compound arithmetic no longer relies on category-name/string coincidence;
- all Release 1 unit regressions remain green;
- differential/property fixtures cover all advertised unit families;
- package and single-file unit behavior match;
- no standard-library-only constraint is violated.

## 10. Workstream E — Consolidate authoritative metadata and contracts

### E1. Inventory duplicated authority

Create `architecture/authority_inventory.md` or extend the existing mutable-state inventory with a table covering:

- package version;
- supported Python versions;
- MCP protocol versions;
- evaluator limits;
- normalization limits;
- MCP request/output/worker limits;
- unit definitions and aliases;
- calculator constants and functions;
- exact/MCP tool names, schemas, metadata, profiles, and handlers;
- CLI command metadata;
- result/error envelope shapes;
- build-single module inventory.

For each item identify:

- authoritative source;
- generated adapters;
- compatibility exports;
- runtime owner;
- tests that prevent drift.

### E2. Consolidate version and protocol identifiers

Use one source for package version and one source for supported MCP protocol versions.

Requirements:

- package metadata, `eggcalc.__version__`, capabilities, CLI output, MCP server info, and single-file build agree;
- capabilities and MCP negotiation do not maintain independent protocol tuples;
- tests compare all public surfaces.

### E3. Consolidate resource limits

Do not create one indiscriminate global limits module. Group limits by owner:

- normalization limits;
- evaluator limits;
- unit parser limits;
- MCP server defaults;
- exact-tool-specific limits.

Each limit must have one authoritative definition and may have documented compatibility re-exports.

### E4. Consolidate tool and command metadata

Where possible, make one declarative record drive:

- handler lookup;
- schema lookup;
- profile membership;
- CLI/exact command metadata;
- docs/inventory generation;
- capability requirements.

Do not create import cycles by storing heavyweight handler objects in metadata needed during light startup. Use import paths or two-stage binding where necessary.

### E5. Standardize result envelopes

Audit repeated `ok`, `error`, `error_type`, `warnings`, `hints`, `tool`, and finding-envelope structures.

Introduce shared TypedDicts or small immutable/internal constructors only where semantics are genuinely common. Do not force unrelated result types into one weak dictionary.

Requirements:

- success and error envelope fields are documented;
- serialization remains backward compatible;
- exact tools retain precise result types;
- MCP wrapping remains distinct from tool-domain results;
- no new untyped `dict[str, Any]` spread is introduced merely to consolidate names.

### E6. Make build inventory declarative

Replace or validate manually maintained `build_single.py` module lists using a single architecture manifest or deterministic discovery with an explicit order.

The builder must detect:

- missing modules;
- duplicate modules;
- invalid dependency order;
- package modules omitted from the artifact where required;
- artifact-only symbols absent from package mode;
- imports that cannot be represented in single-file mode.

### Acceptance for Workstream E

- authority inventory identifies one source for every major registry/constant family;
- package version and MCP protocol definitions cannot drift;
- limit definitions have explicit owners;
- tool/command metadata drift is caught by tests;
- result-envelope consolidation preserves schemas and types;
- single-file module inventory is derived or mechanically validated from one source.

## 11. Workstream F — Tighten static analysis incrementally

### F1. Define module groups

Apply stronger checks in bounded groups, for example:

1. new architecture/dimension/registry modules;
2. capabilities and public API facade;
3. normalization modules;
4. CLI and command registry;
5. units and evaluator;
6. MCP modules;
7. exact shared contracts;
8. remaining exact implementations;
9. build/install scripts.

### F2. Mypy tightening

For new and migrated modules, enable appropriate checks such as:

- `check_untyped_defs`;
- `no_implicit_optional`;
- `warn_redundant_casts`;
- `warn_unreachable`;
- `disallow_any_generics`;
- `strict_equality` where compatible;
- stricter optional handling;
- typed registries and immutable mappings.

Do not enable a global strict preset and then silence hundreds of findings with broad ignores.

Use per-module configuration and remove exceptions as modules are migrated.

### F3. Ruff tightening

Evaluate additional rules incrementally, including selected portions of:

- `ANN` for new public/internal architecture APIs;
- `SIM`;
- `RET`;
- `RUF`;
- `PERF` where it identifies clear issues;
- `PIE`;
- `ARG` for dead parameters where safe.

Every ignored rule must have a bounded reason. Avoid repository-wide suppression for one legacy file.

### F4. Type stable public facades

Add or improve annotations for:

- public evaluator APIs;
- unit registry and dimension types;
- command specifications;
- capability snapshots;
- MCP registry/configuration types;
- generated adapter interfaces.

Run a small static consumer fixture that imports documented public APIs under mypy.

### Acceptance for Workstream F

- all new Release 6 modules pass the stricter module profile;
- no new blanket ignores are added;
- existing ignores removed by the migration are not reintroduced;
- public API consumer fixture type-checks;
- ordinary repository mypy and Ruff checks remain green;
- single-file generation does not strip or corrupt required typing/runtime declarations.

## 12. Workstream G — Measure and control architecture costs

### G1. Add deterministic benchmark tooling

Add a standard-library-only benchmark script, for example `scripts/measure_architecture_costs.py`, that runs fresh subprocesses and records:

- `import eggcalc` median/p95 time;
- `from eggcalc import evaluate` median/p95 time;
- first calculator evaluation;
- `python -m eggcalc --help` startup;
- simple calculator CLI startup;
- exact command startup;
- generated single-file startup;
- MCP initialize latency;
- `tools/list` serialization for compact, normal, and full schemas;
- loaded module count by namespace;
- optional peak `tracemalloc` allocation.

Record Python, OS, architecture, commit SHA, sample count, and command arguments.

### G2. Use stable structural gates

General CI must use non-flaky structural gates:

- zero exact implementation modules after core import;
- zero MCP modules after core import;
- no unrelated exact modules after calculator-only CLI execution;
- deterministic tool inventory counts;
- bounded schema output size;
- no unbounded growth across repeated imports/serializations in one process.

Wall-clock budgets should be enforced only with generous thresholds or on a controlled runner.

### G3. Release evidence comparison

Capture before/after results on the same machine or controlled CI runner.

The release should demonstrate:

- materially reduced loaded-module count for core import;
- no meaningful regression in direct evaluation latency;
- no meaningful regression in calculator CLI startup;
- bounded full-schema serialization;
- single-file startup not materially worse than the pre-release baseline;
- memory evidence sufficient to identify unexpected eager imports.

A regression greater than 15% in a stable repeated metric requires investigation and written justification. This threshold is an evidence review trigger, not an automatic failure on noisy shared runners.

### Acceptance for Workstream G

- benchmark tool is deterministic and documented;
- before/after evidence is recorded at the final commit;
- structural import gates pass in CI;
- no unexplained material regression remains;
- performance work does not reduce correctness or validation coverage.

## 13. Workstream H — Adapt the generated single-file architecture

### H1. Preserve one implementation model

The single-file artifact must consume the same:

- unit registry declarations;
- dimension types;
- command metadata;
- protocol identifiers;
- version source;
- result contracts;
- public API behavior.

Do not maintain a simplified second implementation for the artifact.

### H2. Reduce brittle import rewriting

Refactor `build_single.py` only as needed to support the new module boundaries.

Preferred improvements:

- explicit build manifest with validated dependency order;
- syntax-aware or narrowly patterned import handling;
- fewer special-case alias injections;
- builder diagnostics naming the unsupported import/module;
- generated artifact metadata identifying source commit and module manifest where appropriate.

Do not replace the builder with an external bundler dependency.

### H3. Add artifact structure tests

Test:

- every declared module appears exactly once;
- generated code compiles;
- generated public names match package mode;
- CLI command inventory matches;
- unit registry counts and aliases match;
- MCP tool/profile inventories match;
- capability output matches except for documented mode fields;
- no package-relative imports remain in the artifact;
- repeated generation is byte-for-byte deterministic for the same source tree.

### Acceptance for Workstream H

- build manifest is authoritative and validated;
- generated artifact is deterministic;
- package/single-file import and behavior parity passes;
- new structural dimension logic is not duplicated manually;
- builder complexity is reduced or at minimum bounded by tests and clear diagnostics.

## 14. Workstream I — Documentation, migration, and evidence

Update as required:

- `README.md`;
- `docs/api.md`;
- `docs/quickstart.md`;
- `docs/installation.md`;
- `docs/mcp.md`;
- unit documentation;
- architecture overview and import-boundary documentation;
- mutable-state/authority inventory;
- `AGENTS.md`;
- `CONTRIBUTING.md`;
- `CHANGELOG.md`;
- generated MCP/tool inventories;
- a new `docs/release_6_evidence.md`.

Document:

- new module responsibilities;
- supported compatibility imports;
- deprecated import paths and removal timing;
- structural dimension policy;
- affine temperature behavior;
- unit canonicalization/display policy;
- authoritative registry locations;
- static-analysis profiles;
- benchmark methodology and results;
- single-file builder architecture.

The evidence record must include:

- exact commit SHA;
- CI workflow/run identifiers;
- OS/Python matrix results;
- full test counts and skip categories;
- import-boundary results;
- package/single-file parity results;
- unit registry and differential-test counts;
- static-analysis commands and results;
- benchmark environment and before/after measurements;
- generated artifact determinism result;
- list of retained compatibility shims and deferred issues.

## 15. Required test matrix

### 15.1 Import boundaries

- core import excludes exact implementations;
- core import excludes MCP;
- evaluator import excludes CLI;
- normalization import excludes argparse/exact/MCP;
- CLI help loads only lightweight command metadata;
- calculator command avoids unrelated exact imports;
- selected exact command loads its required module;
- MCP startup loads expected MCP modules;
- reverse import order remains valid;
- repeated import/reload does not mutate behavior.

### 15.2 Public API compatibility

- every documented root export;
- legacy normalization import paths;
- CLI `main`/`run` compatibility if retained;
- exceptions and type identity;
- package metadata/version agreement;
- source/editable/wheel/single-file imports.

### 15.3 CLI separation

- argument parsing independent from normalization tests;
- command registry duplicate detection;
- lazy handler import;
- exit-code matrix;
- stdout/stderr matrix;
- JSON/text mode parity;
- REPL behavior;
- help/inventory generation;
- Windows encoding and path cases;
- package/single-file transcripts.

### 15.4 Structural dimensions

- registry validation;
- every alias;
- canonical lookup;
- base/derived dimension equality;
- incompatible dimensions;
- conversion round trips;
- compound multiply/divide/power;
- dimensionless cancellation;
- area/volume normalization;
- reciprocal units;
- affine temperatures;
- malformed/bounded expressions;
- hashing/equality;
- display golden cases;
- differential fixtures;
- package/single-file parity.

### 15.5 Authority consolidation

- version agreement;
- protocol-version agreement;
- limits source agreement;
- tool handler/schema/metadata/profile agreement;
- CLI command registry agreement;
- generated docs/inventory agreement;
- build manifest agreement;
- result-envelope schema snapshots.

### 15.6 Static analysis

- repository Ruff;
- repository mypy;
- strict module-group checks;
- typed public consumer fixture;
- no unexpected `Any` expansion in new registries;
- no stale suppressions.

### 15.7 Performance and resources

- fresh-process import measurements;
- module-count structural gates;
- repeated schema serialization;
- bounded unit parser complexity;
- no repeated-build nondeterminism;
- no import-time worker/thread/process creation;
- no material unexplained startup regression.

### 15.8 Release surfaces

- source checkout;
- editable install;
- wheel in clean environment;
- `python -m eggcalc`;
- `calc` console script;
- Python API;
- REPL;
- generated `eggcalc.py`;
- MCP stdio;
- Linux/macOS/Windows Python 3.11 minimum-runtime lanes.

## 16. Explicit acceptance criteria

Release 6 is complete only when every mandatory item below is satisfied.

### Import architecture

- [ ] `import eggcalc` loads no exact implementation modules.
- [ ] `import eggcalc` loads no MCP modules.
- [ ] Core evaluation imports no CLI dispatch.
- [ ] Pure normalization imports no argparse, exact implementation, or MCP modules.
- [ ] Import-boundary rules are enforced in CI.
- [ ] Existing documented package-root imports remain valid or have tested deprecation shims.

### CLI architecture

- [ ] CLI parsing/dispatch is separate from normalization.
- [ ] Console script and `python -m eggcalc` share one entry point.
- [ ] Command metadata has one authoritative registry.
- [ ] Exact handlers are loaded lazily by command selection.
- [ ] CLI output, errors, exit codes, and transcripts remain compatible.

### Structural units

- [ ] Unit compatibility is based on structural dimensions.
- [ ] One unit registry defines aliases, canonical names, dimensions, scale, affine behavior, and display metadata.
- [ ] Duplicate/conflicting unit definitions fail construction.
- [ ] Compound arithmetic uses parsed structural unit expressions.
- [ ] Affine temperature semantics are explicit and tested.
- [ ] Existing documented unit aliases and displays are preserved or migration-noted.
- [ ] Unit parser and simplifier have explicit resource bounds.
- [ ] Differential/property tests cover every advertised family.

### Authoritative metadata

- [ ] Package version has one source across metadata, API, CLI, MCP, capabilities, and single-file mode.
- [ ] MCP protocol versions have one source.
- [ ] Major limits have explicit single owners.
- [ ] Tool handler/schema/metadata/profile consistency is mechanically verified.
- [ ] Build module inventory has one authoritative declaration.
- [ ] Shared result contracts are typed and do not weaken domain result types.

### Static verification

- [ ] New Release 6 modules pass the stronger mypy profile.
- [ ] New Release 6 modules pass selected stronger Ruff rules.
- [ ] No broad new ignore is introduced.
- [ ] Public API consumer fixture type-checks.
- [ ] Ordinary repository Ruff, Black, and mypy checks remain green.

### Performance and packaging

- [ ] Before/after architecture-cost evidence is recorded.
- [ ] Core loaded-module count is materially reduced.
- [ ] No unexplained material evaluation/startup/schema regression remains.
- [ ] Generated artifact is deterministic.
- [ ] Package and single-file registries, CLI inventories, unit behavior, and MCP inventories match.
- [ ] Clean wheel and editable-install release surfaces pass.

### Documentation and release evidence

- [ ] Architecture boundaries are documented.
- [ ] Structural dimension and affine-unit policy are documented.
- [ ] Compatibility/deprecation paths are documented.
- [ ] Authority inventory is current.
- [ ] `docs/release_6_evidence.md` references the exact green commit and workflow.
- [ ] CI passes on all supported platforms and versions.
- [ ] No mandatory minimum-runtime feature is skipped.

## 17. Recommended implementation sequence

Keep the release bisectable and avoid mixing semantic unit migration with import refactors.

1. Record import, behavior, unit, and performance baselines.
2. Add import-boundary checker and architecture tests.
3. Narrow `eggcalc.__init__` and add lazy compatibility exports.
4. Split normalization from CLI dispatch while preserving transcripts.
5. Introduce declarative lazy command registry.
6. Update console script, `__main__`, documentation generation, and single-file entry points.
7. Add immutable dimension and unit-definition types without changing runtime decisions.
8. Build authoritative unit registry and prove parity with current aliases/factors.
9. Add parsed structural unit-expression model and shadow comparisons.
10. Switch compatibility and conversion decisions to structural dimensions.
11. Switch compound arithmetic/display simplification incrementally.
12. Consolidate version, protocol, limits, metadata, and result contracts.
13. Make single-file module manifest authoritative and adapt builder.
14. Tighten Ruff/mypy module groups.
15. Run full differential, property, platform, stress, packaging, and parity suites.
16. Capture final performance evidence and update documentation/evidence.

Do not land steps 7–11 as one commit.

## 18. Suggested commit sequence

A reviewable sequence is:

1. `test(arch): capture release 6 import and behavior baselines`
2. `refactor(api): decouple core package imports from cli exact and mcp`
3. `refactor(cli): separate normalization and lazy command dispatch`
4. `test(cli): lock command transcripts and import boundaries`
5. `feat(units): add immutable dimension and unit registry model`
6. `test(units): add registry parity and structural shadow checks`
7. `refactor(units): use dimensions for compatibility and conversion`
8. `refactor(units): migrate compound arithmetic and display semantics`
9. `refactor(meta): consolidate version protocols limits and contracts`
10. `refactor(build): validate declarative single-file module manifest`
11. `chore(types): tighten ruff and mypy by module group`
12. `perf: record release 6 architecture cost evidence`
13. `docs: close release 6 architecture and migration evidence`

Use smaller commits if a unit migration stage changes more than one semantic subsystem.

## 19. Verification commands

At minimum, run:

```bash
python -m ruff check .
python -m black --check .
mypy eggcalc --ignore-missing-imports
python scripts/audit_import_graph.py
python scripts/measure_architecture_costs.py --output docs/release_6_metrics.json
python build_single.py
python build_single.py --check-deterministic
python scripts/generate_mcp_docs.py --check
python scripts/smoke_release_surfaces.py
python -m pytest tests/ -v
python -m pytest tests/test_import_boundaries.py -v
python -m pytest tests/test_units.py tests/test_unit_dimensions.py -v
python -m pytest tests/test_release_surfaces.py -v
python -m build
```

Adapt filenames to the actual implementation. Do not omit the underlying checks if names differ.

Run focused structural-unit and import-boundary suites repeatedly. Use deterministic fixtures and events rather than timing sleeps.

Run the full GitHub Actions matrix, including Python 3.11 on Linux, macOS, and Windows, and record exact workflow/job results.

## 20. Risk controls

### Risk: public import breakage

Control:

- root-export inventory test;
- lazy compatibility shims;
- wheel/source/single-file consumer fixtures;
- explicit deprecation policy.

### Risk: unit semantic regression

Control:

- shadow model before switching authority;
- all-alias registry parity;
- Release 1 semantic regressions;
- differential fixtures;
- staged compatibility/conversion/compound migration;
- display golden tests.

### Risk: import-cycle replacement with dynamic complexity

Control:

- documented dependency direction;
- AST import-boundary checker;
- minimal package facade;
- lazy loading limited to compatibility and command handlers;
- no hidden mutable import registry.

### Risk: single-file divergence

Control:

- one module/build manifest;
- deterministic generation;
- registry/inventory parity tests;
- no artifact-specific unit or command implementation.

### Risk: flaky performance gates

Control:

- hard structural module-count gates;
- repeated subprocess samples;
- controlled-runner evidence for wall-clock comparisons;
- generous thresholds and manual investigation triggers.

### Risk: scope expansion

Control:

- no new tools or syntax;
- no runtime dependencies;
- no parser/evaluator replacement;
- each workstream has independent acceptance criteria;
- defer unrelated cleanup to later plans.

## 21. Exit condition

Release 6 exits only when Eggcalc can credibly claim all of the following:

- core calculator imports are independent of unrelated exact and MCP implementations;
- normalization is a pure calculator subsystem rather than the CLI owner;
- CLI command dispatch is declarative and lazily loads heavyweight tools;
- unit compatibility and compound arithmetic use structural dimensions;
- unit aliases and conversion behavior derive from one validated registry;
- major metadata and build inventories have one authoritative source;
- stricter static checks protect the new architecture;
- import/startup/memory/schema costs are measured and free of unexplained regressions;
- every release surface, including the generated single-file artifact, remains behaviorally equivalent;
- CI and `docs/release_6_evidence.md` prove the final state at the same commit.

Do not mark Release 6 complete based only on new module names or passing unit tests. The architecture, import graph, unit authority, generated artifact, release surfaces, and evidence must all agree.