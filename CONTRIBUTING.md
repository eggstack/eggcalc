# Contributing to eggcalc

Thank you for your interest in contributing to eggcalc! This document provides guidelines and instructions for contributing.

## Development Setup

### Prerequisites

- Python 3.11 or higher
- pip

### Installation

1. Fork and clone the repository:
   ```bash
   git clone https://github.com/YOUR_USERNAME/eggcalc.git
   cd eggcalc
   ```

2. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install in development mode:
   ```bash
   pip install -e ".[dev]"
   ```

4. (Optional) Install pre-commit hooks:
   ```bash
   make hooks
   ```

## Verification

The canonical correctness command is:

```bash
make check
```

This runs Ruff lint, Black format check, mypy type check, generated documentation drift check, and the full pytest suite.

For changes affecting packaging, entry points, generated single-file output, MCP startup, version metadata, or public exports, also run:

```bash
make package-check
```

### Individual targets

```bash
make test           # Run tests
make test-cov       # Run tests with coverage
make lint           # Ruff lint
make format         # Format with black
make format-check   # Check formatting (no changes)
make typecheck      # Mypy type check
make docs-check     # Check generated documentation drift
make build          # Build wheel and sdist
make package-check  # Validate wheel, sdist, and release surfaces
make release-check  # Full correctness + package validation
```

## Code Style

This project uses the following tools:

- **black** - Code formatting
- **ruff** - Linting
- **mypy** - Type checking

Run `make check` to run all of them at once.

## Pull Request Process

1. Create a feature branch from `main`
2. Make your changes
3. Run `make check` to verify correctness
4. For packaging-related changes, also run `make package-check`
5. Submit a pull request

### PR Checklist

- [ ] `make check` passes
- [ ] `make package-check` passes (for packaging changes)
- [ ] New features have tests
- [ ] Documentation updated if needed

## Project Structure

```
eggcalc/
├── eggcalc/           # Main package
│   ├── __init__.py    # Package exports
│   ├── __main__.py    # CLI entry point
│   ├── evaluator.py   # AST-based evaluator
│   ├── normalize.py   # Expression normalization
│   └── units.py       # Unit definitions
├── tests/             # Test suite
├── benchmarks/        # Performance benchmarks
├── docs/              # User documentation
├── architecture/      # Developer documentation
└── pyproject.toml     # Project config
```

## Reporting Issues

- Use the GitHub issue tracker
- Include Python version and OS
- Provide minimal reproduction steps
- Check for existing issues first

## Code of Conduct

Be respectful and inclusive. Treat others as you would like to be treated.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
