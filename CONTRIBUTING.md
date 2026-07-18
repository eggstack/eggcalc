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

4. Install pre-commit hooks:
   ```bash
   pip install pre-commit
   pre-commit install
   ```

## Running Tests

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=eggcalc --cov-report=term-missing

# Run specific test file
pytest tests/test_clicalc.py -v
```

## Code Style

This project uses the following tools:

- **black** - Code formatting
- **ruff** - Linting
- **mypy** - Type checking

Run them before committing:

```bash
# Format code
black eggcalc tests

# Lint code
ruff check eggcalc tests --fix

# Type check
mypy eggcalc --ignore-missing-imports
```

## Pull Request Process

1. Create a feature branch from `main`
2. Make your changes
3. Ensure tests pass: `pytest tests/`
4. Run linting: `ruff check eggcalc tests`
5. Run formatting: `black eggcalc tests`
6. Submit a pull request

### PR Checklist

- [ ] Tests pass locally
- [ ] Code is formatted with black
- [ ] No linting errors from ruff
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
