# Build & Release Skill

## Purpose
Guide agents through building, testing, and releasing eggcalc.

## Build Pipeline

### Single-File Build
```bash
.venv/bin/python build_single.py
```
Assembles `eggcalc/` into a single portable `eggcalc.py`. The build script:
- Concatenates core modules (units.py, evaluator.py, normalize.py, cli.py, capabilities.py, `_protocol.py`)
- Concatenates exact/ and mcp/ sub-packages
- Renames `main()` → `normalize_main()` and `mcp_main()` to avoid conflicts
- Handles aliased imports (e.g., `count_graphemes as _count_graphemes`)

### Verification After Build
```bash
# Run full test suite
.venv/bin/python -m pytest tests/ -v

# Verify single-file works
.venv/bin/python eggcalc.py "five plus three"
```

## CI Pipeline Order
```
ruff → black --check → build_single.py → python eggcalc.py "5+3" (smoke) → pytest → mypy
```
- `make check` runs all of the above (lint + format-check + typecheck + docs-check + full test suite)
- `docs-check` runs `python scripts/generate_mcp_docs.py --check` to verify generated docs aren't stale
- All checks must pass before merge

## Commands Reference

```bash
# Lint
ruff check eggcalc tests

# Format check
black --check eggcalc tests

# Format (auto-fix)
black eggcalc tests

# Type check (includes strict consumer check via make typecheck)
mypy eggcalc --ignore-missing-imports
mypy --strict tests/typing/consumer.py

# All checks at once
make check

# Build single-file
python build_single.py

# Install to ~/.local/bin/calc
python install.py --install
```

## Version Bumping

When releasing a new version:
1. Update version in `pyproject.toml` (via `eggcalc/_version.py`)
2. Update `__version__` in `eggcalc/_version.py`
3. Update `docs/installation.md` version examples
4. Add entry to `docs/changelog.md`
5. Run full test suite to verify

## Constraints

- **Standard library only** — no pip packages in `eggcalc/`
- **Python >=3.11** — CI tests 3.11–3.14
- **build_single.py compatibility** — all runtime code must be in core modules, exact/, or mcp/
- **Import limits** — core modules use: `argparse`, `ast`, `cmath`, `collections`, `contextvars`, `dataclasses`, `enum`, `functools`, `json`, `logging`, `math`, `multiprocessing`, `os`, `queue`, `random`, `re`, `sys`, `threading`, `traceback`, `types`, `typing`. `exact/` and `mcp/` packages may use additional stdlib modules (e.g. `tomllib`, `importlib`, `unicodedata`, `hashlib`, `shlex`, `signal`, `asyncio`, `zlib`, `base64`).

## Common Build Issues

1. **Import outside allowed set** — will break `build_single.py`. Check allowed imports above.
2. **Aliased imports** — synthesis.py uses `count_graphemes as _count_graphemes`. Build script must de-alias these.
3. **Name conflicts** — `main()` and `mcp_main()` are renamed by build script. Don't reference `normalize_main` in source tests.
4. **Circular imports** — Core modules import each other in specific order: normalize → evaluator → units
