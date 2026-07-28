.PHONY: help install dev test test-cov lint format format-check typecheck docs-check check clean build package-check release-check publish hooks

help:
	@echo "eggcalc - Development Commands"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@echo "  install        Install package"
	@echo "  dev            Install with dev dependencies (no hooks)"
	@echo "  test           Run tests"
	@echo "  test-cov       Run tests with coverage"
	@echo "  lint           Run linter (ruff)"
	@echo "  format         Format code (black)"
	@echo "  format-check   Check formatting (black --check)"
	@echo "  typecheck      Run type checker (mypy)"
	@echo "  docs-check     Check generated documentation drift"
	@echo "  check          Full correctness (lint + format-check + typecheck + docs-check + test)"
	@echo "  clean          Remove build artifacts"
	@echo "  build          Build distribution packages"
	@echo "  package-check  Validate wheel, sdist, and release surfaces"
	@echo "  release-check  Full correctness + package validation"
	@echo "  publish        Upload to PyPI via twine"
	@echo "  hooks          Install pre-commit hooks (optional)"

install:
	pip install -e .

dev:
	pip install -e ".[dev]"

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

generate-docs:
	python3 scripts/generate_mcp_docs.py

docs-check:
	python3 scripts/generate_mcp_docs.py --check

check: lint format-check typecheck docs-check
	python build_single.py --validate
	python -m pytest tests/ -v
	@echo "All checks passed!"

clean:
	rm -rf build/ dist/ *.egg-info .pytest_cache .mypy_cache .ruff_cache
	rm -rf htmlcov/ .coverage coverage.xml
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

build: clean
	python -m build

package-check: build
	twine check dist/*
	python scripts/smoke_release_surfaces.py

release-check: check package-check
	@echo "Release check passed!"

publish: release-check
	twine upload dist/*

hooks:
	pip install pre-commit
	pre-commit install
