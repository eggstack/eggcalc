# Changelog

All notable changes to eggcalc are documented here.

## [1.1.2] - 2026-06-10

### Added
- MCP server expanded to 64 tools (from 59)
- Additional text analysis tools: edit_preflight, command_preflight, config_preflight, structured_data_compare, text_security_inspect, prompt_input_inspect
- Production review tests
- Unit namespace tests
- REPL and CLI integration tests
- Build script tests
- Math edge case tests
- Normalization tests

### Changed
- evaluator.py expanded to 2734 lines (from 1515)
- normalize.py expanded to 3066 lines (from 1807)
- units.py expanded to 2086 lines (from 1284)
- Test suite grew to 2070 tests

## [1.1.1] - 2026-05-29

### Added
- Architecture review completed across all 15 modules
- All 35 identified issues fixed
- Unicode policy checks and canonicalization profiles
- Prompt injection detection tools
- Cargo.toml inspection
- Version constraint checking
- Identifier table inspection
- Additional exact/ modules: shell.py, config.py, markdown.py, path_tools.py, position.py, transform.py, glob.py, identifier.py, identifier_inspect.py, inspect_prompt.py, cargo.py, version.py, unicode_policy.py, patch.py

### Fixed
- Float regex pipe bug in normalize.py
- Temperature conversion crash with ValueError
- Duplicate _VALID_TRANSFORM_OPERATIONS in mcp/tools.py
- Int regex patterns in normalize.py
- UnitValue __eq__ returning NotImplemented for different units

## [1.1.0] - 2026-02-20

### Added

- Comprehensive CI/CD pipeline with GitHub Actions
- Shell completions for bash, zsh, and fish
- Man page for Unix systems
- MkDocs documentation
- SECURITY.md security policy
- CONTRIBUTING.md contribution guidelines
- Issue and PR templates
- Pre-commit hooks configuration
- Makefile for common development tasks
- Black, ruff, and mypy configuration

### Security

- AST-based evaluation (no eval)
- Input length limits
- Nesting depth limits
- Exponent limits
- Timeout protection
- Blocked dangerous operations

## [1.0.0] - 2026-01-15

### Added

- Natural language math expression parsing
- Unit conversions (length, time, data, mass, volume, etc.)
- Scientific functions (trig, log, exponential, etc.)
- Physical constants (Avogadro, Planck, Boltzmann, etc.)
- Complex number support
- Bitwise operations
- Combinatorics functions (factorial, perm, comb)
- Prime number functions
- Statistical functions
- Random number generation
- Memory registers
- User variables
- Percentage calculations
- Interactive REPL mode
- JSON output
- Python API with caching
- Async support for web applications
- Thread-safe EggCalcApp class
- Custom configuration via eggcalc_config.py

### Security

- AST-based safe evaluation
- Blocked import, eval, exec
- Blocked attribute access
- Blocked comprehensions
- Blocked lambda expressions
- Input length limits
- Nesting depth limits

## [0.1.0] - 2025-12-01

### Added

- Initial release
- Basic arithmetic operations
- Number word conversion
- Simple unit conversions
- CLI interface
