# Eggcalc Correctness and Protocol-Hardening Roadmap

Status: proposed execution roadmap  
Repository: `eggstack/eggcalc`  
Primary scope: calculator semantics, unit correctness, MCP conformance, deterministic inspection tools, runtime compatibility, concurrency isolation, and maintainability

## 1. Purpose

Eggcalc has grown from a natural-language calculator into a dual-purpose system:

1. A standard-library-only calculator and unit-conversion engine exposed through a CLI, Python API, and single-file build.
2. A deterministic text, Unicode, validation, manifest, patch, repository-analysis, and MCP tool suite intended for agent consumption.

The repository already has strong foundations: AST-based evaluation, explicit resource limits, broad regression coverage, multi-version CI, generated-document checks, release-surface smoke tests, and MCP profiles. The next phase should prioritize semantic correctness and protocol closure rather than additional tool count.

This roadmap converts the current review findings into an ordered implementation program. The first three releases are correctness releases and should be treated as release-gating. Later releases address compatibility, state isolation, and structural simplification.

## 2. Guiding constraints

All work must preserve these project constraints unless a release explicitly changes one:

- Runtime remains standard-library-only.
- Package, CLI, Python API, MCP server, and single-file artifact remain supported release surfaces.
- User-facing natural-language evaluation remains separate from direct AST-compatible evaluation.
- MCP tools remain deterministic unless explicitly documented otherwise.
- Resource limits remain enforced at parser, evaluator, tool, request, output, and worker boundaries.
- Documentation and generated inventories must remain synchronized with implementation.
- Behavioral changes require regression tests across package and single-file surfaces.

## 3. Target architecture

The intended end state is:

- Calculator syntax is normalized into unambiguous Python-compatible syntax before AST parsing.
- Unit arithmetic uses one shared semantic implementation and eventually structural dimensions rather than string-first inference.
- MCP execution is owned by explicit server/session objects with protocol lifecycle state.
- Manifest and repository tools use common result and finding contracts.
- Advertised capabilities reflect the active runtime and platform.
- MCP operation does not mutate global calculator behavior.
- Core calculator imports do not eagerly load the full exact-tool suite.
- CI verifies semantic, protocol, packaging, platform, and generated-artifact parity.

## 4. Release sequence

### Release 1 — Calculator semantic correctness

Objective: remove known arithmetic ambiguity and make dimensional behavior internally consistent.

Primary deliverables:

- Rewrite calculator caret syntax to `**` before AST parsing.
- Restore `evaluate()` as direct Python-AST-compatible evaluation and keep calculator caret behavior in `evaluate_raw()`/CLI normalization.
- Preserve natural-language XOR through `bitxor(...)` rewriting.
- Define and enforce dimensional semantics for floor division and modulo.
- Add precedence, associativity, unary, unit, and metamorphic regression matrices.
- Update public API and syntax documentation.

Release gate:

- Mixed-precedence caret expressions evaluate correctly.
- Right-associative exponentiation is correct.
- Same-unit and cross-unit modulo both preserve a dimensioned remainder.
- Package and generated single-file behavior match.

Detailed plan: `plans/002-release-1-calculator-semantic-correctness.md`.

### Release 2 — MCP protocol conformance

Objective: replace the permissive request router with a protocol-aware session implementation.

Primary deliverables:

- Protocol-version negotiation based on initialize parameters.
- Explicit lifecycle states: uninitialized, initializing, ready, closed.
- Correct request ID and notification handling.
- Correct JSON-RPC error taxonomy.
- Explicit schema-subset validation and CI rejection of unsupported schema keywords.
- Raw JSON-line conformance fixtures and independent client validation.

Release gate:

- Initialization, notification, request, cancellation, and tool-call flows conform to the selected MCP protocol version.
- Notifications never receive responses.
- Invalid params and invalid envelopes return distinct error codes.
- Tests no longer encode known nonconformant behavior.

Detailed plan: `plans/003-release-2-mcp-protocol-conformance.md`.

### Release 3 — Inspection-tool correctness

Objective: make manifest and repository-inspection output semantically reliable.

Primary deliverables:

- Correct `pyproject_inspect()` backend, build requirement, tool-section, and parse-location extraction.
- Replace false-positive requirements-file suspicious-character logic with conservative lexical recognition.
- Standardize structured findings across Cargo and generic manifest tools.
- Add representative golden fixtures for Python, Rust, JavaScript, Go, and lockfile ecosystems.
- Assert every major returned field rather than only parse success.

Release gate:

- Standard pyproject metadata is reported accurately.
- Valid requirement extras and version specifiers are not flagged as suspicious.
- Manifest tools expose a common finding contract.
- Golden fixtures cover all advertised ecosystems.

Detailed plan: `plans/004-release-3-inspection-tool-correctness.md`.

### Release 4 — Runtime compatibility and capability negotiation

Objective: align the supported-runtime contract with the actual tool surface.

Recommended policy:

- Raise the minimum supported Python version to 3.11 because TOML inspection is part of the advertised tool surface and `tomllib` is standard-library-only from 3.11 onward.

Alternative policy, only if Python 3.10 remains operationally necessary:

- Dynamically hide unavailable TOML-dependent tools and profiles on 3.10.

Primary deliverables:

- Finalize Python minimum-version policy.
- Remove skipped mandatory-feature tests.
- Add runtime capability inspection.
- Add Windows and macOS CI for path, shell, multiprocessing, newline, installer, wheel, and single-file behavior.

Release gate:

- Every advertised tool is operational on every supported runtime.
- Minimum-version CI has no skips for mandatory functionality.

### Release 5 — State isolation and concurrency hardening

Objective: remove process-global policy mutation and make embedding safe.

Primary deliverables:

- Dedicated MCP evaluator with random and side effects disabled instance-locally.
- Explicit `McpServerConfig`, `McpSession`, tool registry, and executor ownership.
- Atomic, lock-protected configuration loading.
- Narrow handling of missing `eggcalc_config`; propagate internal import failures.
- Centralized cache invalidation or generation-based cache keys.
- Concurrency, saturation, cancellation, timeout-storm, and multi-session tests.

Release gate:

- MCP use does not change ordinary library behavior in the same process.
- Independent app and MCP instances do not share mutable user state.
- Configuration application is atomic and load-once.

### Release 6 — Internal architecture and maintainability

Objective: reduce coupling and long-term semantic complexity after correctness is locked.

Primary deliverables:

- Decouple core calculator imports from the eager `eggcalc.exact` re-export graph.
- Separate CLI dispatch from natural-language normalization.
- Introduce structural unit dimensions incrementally while preserving display strings.
- Consolidate duplicated constants, limits, metadata, and result envelopes.
- Tighten Ruff and mypy checks module-by-module.
- Measure import latency, cold startup, memory, and schema serialization costs.

Release gate:

- Importing the calculator no longer eagerly loads unrelated exact-tool modules.
- Unit compatibility relies on dimensions rather than category/string coincidence.
- Major registries have one authoritative source.

## 5. Cross-release verification tracks

### 5.1 Differential testing

Use development-only reference implementations without adding runtime dependencies:

- Python arithmetic for direct evaluator expressions.
- Pint for unit-conversion and dimensional reference checks.
- `packaging` for supported version-semantic subsets.
- A standards-compliant JSON Schema implementation for validator differential fixtures.
- Official MCP clients or SDKs for lifecycle and transport verification.

### 5.2 Property and fuzz testing

Prioritize:

- Normalization termination and bounded output growth.
- Operator precedence and associativity.
- Unit round trips and dimensional identities.
- Compound-unit simplification.
- Unicode normalization and confusable analysis.
- JSON, TOML, regex, shell, patch, and diff parsers.
- MCP envelope parsing and schema recursion limits.

### 5.3 Performance budgets

Track but do not immediately fail on unstable baselines:

- `evaluate()` latency.
- `evaluate_raw()` latency.
- Cold package import.
- Single-file startup.
- `tools/list` serialization at compact, normal, and full detail.
- Typical and maximum-bound tool inputs.
- Multiprocessing timeout-worker startup.

Once baselines stabilize, enforce bounded regression thresholds.

### 5.4 Release-surface parity

Every release must verify:

- Source checkout.
- Editable install.
- Wheel installation in a clean virtual environment.
- `python -m eggcalc`.
- `calc` console script.
- Generated `eggcalc.py` single-file artifact.
- Python library API.
- MCP stdio mode.

## 6. Repository-wide acceptance policy

A release is not complete until:

- Implementation and regression tests land together.
- Generated MCP inventory and documentation checks pass.
- Package and single-file results match for changed behavior.
- CI passes on all supported Python versions and platforms.
- No mandatory feature is skipped in the minimum supported runtime.
- Error behavior is tested, not only success behavior.
- Resource-bound tests cover newly introduced parsing or iteration paths.
- Public API and protocol changes are documented in changelog and migration notes.

## 7. Dependency ordering and parallelism

Required sequence:

1. Release 1 before further calculator syntax expansion.
2. Release 2 before claiming current MCP compatibility.
3. Release 3 before expanding manifest or repository-audit tool inventory.
4. Release 4 before additional runtime-support claims.
5. Release 5 before broad embedding or multi-session use.
6. Release 6 only after earlier behavior is locked by regression suites.

Safe parallelism:

- Release 3 fixture preparation can proceed while Release 2 is being implemented.
- Platform CI preparation from Release 4 can begin during Release 3.
- Structural-dimension design can be prototyped during Release 5, but migration should wait until semantic tests from Release 1 are stable.

## 8. Immediate execution tranche

The first implementation tranche should be bounded to four high-value corrections:

1. Caret preprocessing plus precedence and associativity tests.
2. Same-unit modulo remainder-unit correction and shared implementation cleanup.
3. `pyproject_inspect()` backend, tool-section, and error-location fixes.
4. Requirements lexical recognition for extras and ordinary specifiers.

This tranche provides immediate correctness gains while the full MCP session refactor is prepared.

## 9. Completion definition for the roadmap

The roadmap is complete when eggcalc can credibly claim:

- Correct documented calculator grammar.
- Dimensionally consistent unit arithmetic.
- Conformant MCP lifecycle and JSON-RPC behavior.
- Accurate deterministic repository and manifest inspection.
- Honest runtime capability advertisement.
- Safe embedded use without process-global policy leakage.
- Maintainable internal boundaries that preserve the standard-library-only and single-file goals.
