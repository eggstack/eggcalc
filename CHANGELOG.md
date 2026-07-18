# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2026-07-16

### Fixed
- Calculator caret (`^`) rewritten to exponentiation before AST parsing in `evaluate_raw()` and CLI
- `evaluate()` now correctly treats `^` as bitwise XOR (Python AST semantics)
- Same-unit modulo returns dimensioned remainder in divisor unit (e.g., `5m % 2m` → `1 m`)
- Cross-unit modulo converts dividend to divisor unit (e.g., `1m % 30cm` → `10 cm`)
- Incompatible-dimension floor/mod now rejected (no misleading compound unit strings)

### Added
- `_rewrite_calculator_caret()` tokenizer-aware helper for safe `^` → `**` rewriting
- `_floor_divide_quantities()` and `_modulo_quantities()` shared helpers in units.py
- 59 new tests in `test_calculator_operator_semantics.py` covering precedence, associativity, word-form XOR, unit floor/mod, CLI subprocess, and adversarial input

### Changed
- Caret rewrite placed after `_normalize_spaced_unit_caret_exponents` to preserve unit caret shorthand (`5 m ^ 2`)
- Documentation updated: README, AGENTS.md, architecture docs, API docs, functions.md, CLI docs, quickstart

## [2.0.0] - Unreleased

### Added
- `McpSession` class for explicit MCP protocol lifecycle management (UNINITIALIZED → INITIALIZING → READY → CLOSED)
- `McpSessionState` enum for lifecycle state tracking
- Protocol version negotiation in `initialize` — client-requested version matched against `SUPPORTED_PROTOCOL_VERSIONS`
- Centralized JSON-RPC error helpers (`_jsonrpc_error`, `_parse_error`, `_invalid_request`, `_method_not_found`, `_invalid_params`, `_internal_error`)
- `SUPPORTED_SCHEMA_KEYWORDS` frozenset defining which JSON Schema keywords the validator supports
- Schema lint tests (`test_mcp_schema_lint.py`) that walk all `TOOL_SCHEMAS` and reject unsupported keywords
- Session-aware test helpers (`ready_session()`, `session_request()`) for clean handshake setup
- `handle_request()` now accepts an optional `session` parameter for lifecycle enforcement
- `main()` creates one `McpSession` per connection for lifecycle management
- MCP protocol version `2025-11-25` support (latest stable) with backward compatibility for `2024-11-05`
- `SUPPORTED_PROTOCOL_VERSIONS` now includes both `2024-11-05` and `2025-11-25`
- `McpSession` now stores `requested_version`, `client_name`, `client_version` per session
- `RuntimeCapabilities` frozen dataclass for immutable runtime capability detection (platform, Python version, tomllib, fork/spawn support)
- `detect_capabilities()` function for probing observable runtime facts
- `capability_summary()` for human-readable runtime diagnostics
- MCP server `initialize` response now includes `runtime` key with capability information
- Initialization requires `protocolVersion`, `capabilities`, and `clientInfo` fields (returns `-32602` for missing/invalid)
- `TestInitializeValidation` — 11 tests for initialization parameter validation
- `TestLifecycleMisuse` — 8 tests for lifecycle state machine enforcement
- `TestErrorNotificationConformance` — 6 tests for error codes and notification behavior
- `TestInspectionContract` — 7 tests for finding structure invariants
- `TestCargoScriptDetection` — 9 tests for Unicode/confusable detection with distinct finding codes
- Cargo dependency finding codes: `CARGO_NON_ASCII_DEPENDENCY_NAME`, `CARGO_MIXED_SCRIPT_DEPENDENCY_NAME`, `CARGO_CONFUSABLE_DEPENDENCY_COLLISION`, `CARGO_SUSPICIOUS_DEPENDENCY_NAME`

- `_Finding` TypedDict (`code`, `severity`, `message`, `line`, `column`) for structured inspection findings with closed severity vocabulary (`error`, `warning`, `info`)
- `build_requirements`, `build_backend_path`, `dynamic`, `entry_points`, `gui_scripts`, `urls` fields to `pyproject_inspect()` result
- `requirement_includes`, `index_options`, `hash_options` fields to `requirements_inspect()` result
- Conservative lexical classifier for requirements-line classification (replaces broad suspicious-character regex)
- Multiline continuation support for compiled requirements with backslash continuation
- Stable finding codes for Cargo inspections (`CARGO_PARSE_ERROR`, `CARGO_MISSING_PACKAGE_NAME`, etc.)
- Unicode confusable detection for Cargo dependency names
- 37 fixture files across Python, Cargo, JavaScript, Go, requirements, and lockfile ecosystems
- 257 comprehensive inspection tests with field-level assertions, negative/boundary tests, and invariant tests

### Changed
- Minimum supported Python version raised from 3.10 to 3.11 (Release 4 — Runtime Compatibility)
- Removed `_needs_tomllib` skip decorators from 5 test files (no longer needed on Python 3.11+)
- Removed `math.cbrt` version skip from `test_clicalc.py`
- Updated `build_single.py` to include `capabilities` module in single-file build
- `pyproject_inspect()` now reads `build-backend` from `build-system.build-backend` instead of deriving it from requires[0]
- `pyproject_inspect()` tool sections read nested `data["tool"]` dict instead of flat `tool.`-prefixed keys
- `pyproject_inspect()` parse-error location uses `col_offset` with fallback for Python 3.11 compatibility
- `requirements_inspect()` suspicious-character matching replaced with conservative checks targeting shell metacharacters, unbalanced brackets, and control characters
- Cargo findings migrated from `list[str]` to `list[_Finding]` with stable codes
- Cargo inspection no longer flags valid virtual workspaces as missing package metadata
- MCP output schemas updated with new inspection result fields
- Documentation updated: architecture/exact.md, AGENTS.md field conventions, tool_inventory.md
- `_has_confusable_unicode()` now uses actual Unicode confusables table instead of codepoint range heuristic
- `_detect_suspicious_name()` returns `list[_Finding]` with distinct finding codes instead of `bool`
- Initialization validation tightened: `protocolVersion`, `capabilities`, `clientInfo` are now required
- `handle_request(session=None)` now emits `DeprecationWarning` — callers should pass an explicit `McpSession`

### Deprecated
- Sessionless `handle_request()` compatibility path (pass an explicit `McpSession` instead)

## [1.1.6] - 2026-07-14

### Fixed
- Trailing comma detection made unconditional in llm_json_output_check
- Skip 3.10-only test failures and fix mypy type errors
- Skip additional 3.10-only tests that were missed

## [1.1.4] - 2026-06-30

### Fixed
- Semver parsing now preserves hyphenated pre-release identifiers such as `alpha-beta` instead of splitting them at the hyphen.
- Semver parsing now rejects leading-zero numeric identifiers and empty pre-release/build identifiers.

### Changed
- Version constraint range result construction was consolidated for easier maintenance.
- Release documentation updated to match package version `1.1.4`.

## [1.1.3] - 2026-06-10

### Fixed
- Spacing-sensitive unit parsing: `5m ** 2`, `30 km / h in mph`, `5 N m` now parse correctly
- Spaced lowercase temperature conversions (`100c in f`)
- Unit caret exponents (`5m**2`)
- RAII spawn semaphore for evaluate_async (replaced manual acquire/release)

### Changed
- Documentation updated to match current codebase
- Package description and keywords updated for PyPI

## [1.1.2] - 2026-06-10

### Added
- MCP server expanded to 64 tools (from 59)
- Additional text analysis tools: edit_preflight, command_preflight, config_preflight, structured_data_compare, text_security_inspect, prompt_input_inspect
- Production review tests, unit namespace tests, REPL and CLI integration tests
- Build script tests, math edge case tests, normalization tests

### Changed
- evaluator.py expanded to 2734 lines (from 1515)
- normalize.py expanded to 3066 lines (from 1807)
- units.py expanded to 2086 lines (from 1284)
- Test suite grew to 2070 tests

## [1.1.1] - 2026-05-29

### Added
- Architecture review completed across all 15 modules
- Unicode policy checks and canonicalization profiles
- Prompt injection detection tools
- Cargo.toml inspection, version constraint checking
- Identifier table inspection
- 14 new exact/ modules for text analysis

### Fixed
- Float regex pipe bug in normalize.py
- Temperature conversion crash with ValueError
- Duplicate _VALID_TRANSFORM_OPERATIONS in mcp/tools.py
- Int regex patterns in normalize.py
- UnitValue __eq__ returning NotImplemented for different units

## [1.1.0] - 2026-02-20

### Added
- New configuration constants for fine-tuned control:
  - `MAX_NESTING_DEPTH` - Maximum parentheses nesting depth
  - `MAX_FACTORIAL` - Maximum factorial input to prevent DoS
  - `MAX_RESULT_VALUE` - Maximum result value
  - `DEFAULT_CACHE_SIZE` - Default LRU cache size
- `FLOAT_EPSILON` constant in units.py for float comparisons
- Export of new constants in `__all__`
- Python 3.13 support in pyproject.toml

### Changed
- `factorial()` now has input bounds checking (max 1,000)
- `cbrt()` now correctly handles negative numbers
- Cache clearing now only happens on non-EvaluationError exceptions
- Nesting depth is now validated in normalize()
- Named constants used throughout instead of magic numbers

### Fixed
- Thread-safe access to user variables with lock in `visit_Name()`
- Float equality uses named `FLOAT_EPSILON` constant

### Security
- Added bounds checking for factorial to prevent DoS via large factorial inputs
- Fixed cbrt negative number handling
- Added nesting depth limits

## [1.0.0] - 2026-01-15

### Added
- Initial release
- Natural language expression parsing
- Unit conversions (length, time, data, mass, volume, pressure, energy, power)
- Scientific functions (trig, hyperbolic, log, exp)
- Physical constants
- Complex number support
- Bitwise operations
- Statistical functions
- Prime number utilities
- Memory registers and variables
- Webapp support with caching and async
- AST-based safe evaluation
- CLI with interactive REPL mode
