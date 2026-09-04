# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `eggcalc.exact.network` module with `ip_inspect()` (canonical address, family, packed-bytes hex, decimal numeric, explicit version-stable special-use tags, IPv4-mapped metadata) and `cidr_inspect()` (canonical CIDR, prefix/host bits, range bounds, exact address count, optional same-family containment); both lazily re-exported from `eggcalc.exact`
- `eggcalc.exact.encoding` module with `codec_convert()` (strict utf8/hex/base64/base64url conversion with canonical outputs) and `radix_convert()` (signed ASCII integer conversion across bases 2–36, magnitude capped at `2**128 - 1`); both lazily re-exported from `eggcalc.exact`
- `eggcalc.exact.temporal` module with `datetime_convert()` (nanosecond-exact fixed-offset RFC3339 <-> Unix seconds/milliseconds/nanoseconds with floor semantics) and `cron_inspect()` (five-field cron with corrected star-syntax DOM/DOW semantics, strictly-after bounded search over one 400-year Gregorian cycle); both lazily re-exported from `eggcalc.exact`
- MCP integration for the six utility tools (`ip_inspect`, `cidr_inspect`, `codec_convert`, `radix_convert`, `datetime_convert`, `cron_inspect`): JSON Schemas with `maxLength` 100000 bounds, tier-2 `full`-only contextual metadata in new `network`/`encoding`/`temporal` categories (`cron_inspect` is `moderate` cost, the rest `cheap`), thin deferred-import handlers delegating to the exact functions (`codec_convert` accepts the JSON keys `from`/`to` via `**kwargs` since `from` is a Python keyword), registry/wheel/single-file parity, and generated inventory/docs updates (83 tools, 21 categories)

### Changed
- Removed import-time `os.environ.setdefault("EGGCALC_NO_CONFIG", "1")` from `server.py`; config suppression now handled by `McpServerConfig.from_environment()` and explicit `main()` setup
- `main()` now creates `McpServer(config=config)` per connection instead of bare `McpSession`, with `server.handle_request()` and guaranteed `server.close()` in try/finally
- `McpSession.handle_message()` passes `server=server` to all handlers when available; `_handle_list_tools()`, `_handle_list_profiles()`, `_handle_initialize()`, and `_handle_cancelled()` use `server.config.*` and `server.registry.*`
- `ConfigSnapshot.__post_init__()` defensively copies all dict fields to prevent external mutation (deeply immutable)
- `ConfigManager.replace()` now validates that generation is strictly increasing; stale/decreasing generations raise `ValueError`
- `ToolRegistry` internal dicts wrapped in `MappingProxyType` — properties return immutable views
- `ToolExecutor` gains closed-state sealing: `_get_executor()` and `call_tool()` raise/return errors after `close()`
- `ToolExecutor.call_tool()` timeout accounting uses `Future.add_done_callback()` so `_total_inflight` is released only when the future truly completes, not on caller timeout
- `McpServer.close()` transitions all owned sessions to `CLOSED` state and clears the session set (idempotent)
- `McpSession.close()` method added for explicit session closure

### Added
- `_server_evaluator` ContextVar in `evaluator.py` — binds server-owned evaluator to `evaluate_raw()` and `evaluate_with_timeout()` so MCP math execution uses the server's evaluator instead of the global default
- `_evaluate_with_timeout_worker()` creates a local `Evaluator` instance with the given policy flags instead of mutating `configure_default_evaluator()` — child processes no longer mutate parent evaluator state
- `evaluate_raw()` and `evaluate_with_timeout()` accept optional `_evaluator` parameter for direct evaluator injection
- `ToolExecutor` stores server evaluator and sets `_server_evaluator` ContextVar via `_run_handler_in_thread()` before calling handlers
- Request ID length validation in `McpServer.handle_request()` using `server.config.max_request_id_length`
- `_handle_initialize()` uses `server.config.supported_protocol_versions` when server is available
- `McpSession.close()` method for explicit session lifecycle management
- `McpSession.close()` now removes session from server's live tracking via `_owner_remove_callback`
- `ConfigError` exception for configuration parsing/validation failures
- `parse_config_snapshot()` for validated config construction with type/semantics checks
- `McpServer.activate_snapshot()` for atomic config activation with evaluator push and rollback
- `ToolRegistry.get_schema()` returns deep copy to prevent nested mutation
- 27 new tests covering registry nested mutation, config deep immutability, random isolation determinism, executor cancellation, concurrent session close/dispatch, config activation path, and config parsing

### Fixed

Calculator and normalization:
- Reject ambiguous juxtaposed digit input (`5 5`, `1 000`) instead of silently summing; function arguments and multi-word numbers are unaffected
- Bare-number conversions no longer claim ordinal words (`two to the tenth` no longer yields `2 h`); conversion targets must match unit names exactly
- `convert()` keeps target units intact on function-name collisions (`1 hour in minutes` no longer hits empty `min()`)
- Powered units render uniformly as `base**exp` across parse paths (`5m^2`, `5m**2`, and `5 m squared` all match `5 m ** 2`)
- Nth-root phrases supported (`the 3rd root of 27` → `3`)
- `UnitValue.__floordiv__` preserves the dividend unit when the divisor is a dimensionless `UnitValue`

MCP server and tools:
- `ToolExecutor` shutdown wait is bounded (reaper thread + timeout)
- `_cleanup_orphaned_processes()` is wired into `McpServer.close()` and `atexit`; still-alive orphans stay tracked
- `structured_data_compare` reads the shape type from `result["shape"]["type"]` so `TYPE_MISMATCH` can fire
- `regex_safety_check` derives severity from the top-level risk and uses `len(pattern)` for `pattern_length`

CLI:
- REPL no longer swallows `SystemExit` (SIGTERM during evaluation)
- `normalize.run()` honors `show_expression` in JSON output

Testing:
- pytest `faulthandler_timeout` hang guard added

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
- `--capabilities` CLI flag to display runtime capabilities as JSON
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
- `McpServerConfig` frozen dataclass for immutable MCP server configuration with validation and clamping
- `McpServer` class for explicit server ownership of config, registry, executor, evaluator, and sessions
- `ToolRegistry` class for explicit ownership of tool definitions (handlers, schemas, metadata, profiles)
- `ToolExecutor` class for owned tool validation, timeout, worker dispatch, and cleanup
- `ConfigSnapshot` frozen dataclass for atomic configuration replacement (includes `units` field)
- `ConfigManager` class for thread-safe configuration snapshot management with generation tracking
- `create_evaluator()` factory function for isolated evaluator instances with specified policy
- `get_config_generation()` function for observing configuration generation counter
- `McpServer.diagnostic()` for deterministic, JSON-serializable server diagnostics (includes `active_workers`, `session_count`, `orphan_count`, `config_units_count`, `global_config_generation`, `max_tool_queue_size`, `pending_count`)
- `ToolExecutor.active_workers`, `ToolExecutor.orphan_count`, and `ToolExecutor.pending_count` properties for runtime observability
- `McpServerConfig.max_tool_queue_size` for bounded worker queue with saturation rejection (default 32, clamped 1–1000)
- Mutable state inventory document (`architecture/mutable_state_inventory.md`) cataloging all process-global state
- 98 tests in `test_release5_isolation.py` covering state isolation, concurrency, lifecycle hardening, diagnostics, stress scenarios, saturation rejection, and oversized output storms
- 4 tests in `test_config_loading.py` for import-error precision (syntax errors, runtime exceptions, internal import errors propagate; missing module is silent)
- Release 5 evidence file (`docs/release_5_evidence.md`) with full-suite, stress-suite, platform, and acceptance criteria verification
- Multi-instance isolation tests: two servers with different configs, evaluators, and registries
- Multi-session isolation tests: cancellation independence, lifecycle independence, shared request IDs
- Concurrency tests: parallel tool execution, worker pool bounds, concurrent server creation
- Shutdown tests: resource reclamation, idempotent close, post-close rejection
- Evaluator policy isolation: server evaluator does not affect default evaluator

### Changed
- `load_user_config()` now uses `importlib.util.find_spec()` to precisely detect missing `eggcalc_config`; syntax errors, runtime exceptions, and internal import errors inside the config file now propagate instead of being silently suppressed
- `McpSession.handle_message()` now accepts optional `server` parameter for server-owned dispatch
- `eggcalc/mcp/__init__.py` exports `McpServerConfig`, `McpServer`, `ToolRegistry`, `ToolExecutor`, `ConfigSnapshot`, `ConfigManager`
- Minimum supported Python version raised from 3.10 to 3.11 (Release 4 — Runtime Compatibility)
- CI matrix expanded: removed Python 3.10, added macOS and Windows lanes (Linux, macOS, Windows with Python 3.11–3.14)
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
