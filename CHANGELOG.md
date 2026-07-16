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

### Changed
- Tool requests before initialization now return `-32600` ("Server not initialized") instead of being silently accepted
- Duplicate `initialize` requests return `-32600` ("Server already initialized")
- Documentation updated for protocol version support, session lifecycle, error taxonomy, and migration notes

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
