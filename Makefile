.PHONY: help install dev test lint format check clean build publish docs generate-docs docs-check

help:
	@echo "eggcalc - Development Commands"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@echo "  install     Install package"
	@echo "  dev         Install with dev dependencies"
	@echo "  test        Run tests"
	@echo "  test-cov    Run tests with coverage"
	@echo "  lint        Run linter (ruff)"
	@echo "  format      Format code (black)"
	@echo "  typecheck   Run type checker (mypy)"
	@echo "  check       Run all checks (lint, format --check, typecheck, docs-check, test)"
	@echo "  clean       Remove build artifacts"
	@echo "  build       Build distribution packages"
	@echo "  publish     Publish to PyPI (requires twine)"
	@echo "  docs        Build documentation"
	@echo "  pre-commit  Install pre-commit hooks"

install:
	pip install -e .

dev:
	pip install -e ".[dev]"
	pip install pre-commit
	pre-commit install

test:
	pytest tests/ -v

test-cov:
	pytest tests/ --cov=eggcalc --cov-report=term-missing --cov-report=html

lint:
	ruff check eggcalc tests

format:
	black eggcalc tests

format-check:
	black --check eggcalc tests

typecheck:
	mypy eggcalc --ignore-missing-imports

check: lint format-check typecheck docs-check test
	@echo "All checks passed!"

generate-docs:
	python3 scripts/generate_mcp_docs.py

docs-check:
	python3 scripts/generate_mcp_docs.py --check

clean:
	rm -rf build/ dist/ *.egg-info .pytest_cache .mypy_cache .ruff_cache
	rm -rf htmlcov/ .coverage coverage.xml
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

build: clean
	python -m build

publish: build
	twine upload dist/*

docs:
	@echo "Building docs with mkdocs..."
	mkdocs build

pre-commit:
	pip install pre-commit
	pre-commit install
	pre-commit run --all-files

release: check build
	@echo "Ready to release! Run: git tag vX.Y.Z && git push --tags"
