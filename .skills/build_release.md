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

`make check` runs, in order:
```
ruff → black --check → mypy (package + strict consumer) → docs-check → build_single.py --validate → pytest
```
- `docs-check` runs `python scripts/generate_mcp_docs.py --check` to verify generated docs aren't stale
- `make package-check` builds the wheel/sdist and runs `twine check` plus installed-wheel and single-file smoke tests
- CI runs `make check` then `make package-check`; all checks must pass before merge

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
1. Update `__version__` in `eggcalc/_version.py` (single source of truth; `pyproject.toml` reads it dynamically)
2. Add an entry to `CHANGELOG.md`
3. Update the version example in `docs/installation.md`
4. Run `make release-check` to verify

## Constraints

- **Standard library only** — no pip packages in `eggcalc/`
- **Python >=3.11** — required CI uses 3.11; optional compatibility workflow tests 3.14 and Windows
- **build_single.py compatibility** — all runtime code must be in core modules, exact/, or mcp/
- **Import limits** — core modules use: `argparse`, `ast`, `cmath`, `collections`, `contextvars`, `dataclasses`, `enum`, `functools`, `json`, `logging`, `math`, `multiprocessing`, `os`, `queue`, `random`, `re`, `sys`, `threading`, `traceback`, `types`, `typing`. `exact/` and `mcp/` packages may use additional stdlib modules (e.g. `tomllib`, `importlib`, `unicodedata`, `hashlib`, `shlex`, `signal`, `asyncio`, `zlib`, `base64`).

## Common Build Issues

1. **Import outside allowed set** — will break `build_single.py`. Check allowed imports above.
2. **Aliased imports** — synthesis.py uses `count_graphemes as _count_graphemes`. Build script must de-alias these.
3. **Name conflicts** — `main()` and `mcp_main()` are renamed by build script. Don't reference `normalize_main` in source tests.
4. **Module order** — the manifest declares dependencies; `validate_build_manifest()` rejects cycles, unknown deps, and unreachable modules. Run `python3 build_single.py --validate` before assembling.

See `architecture/build.md` for manifest details and assembly transforms.
