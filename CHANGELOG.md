# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
