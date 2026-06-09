# Changelog

All notable changes to eggcalc are documented here.

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
