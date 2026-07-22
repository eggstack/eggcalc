# Release 6 Evidence

Release 6 — Internal Architecture and Maintainability

## Commit

- **SHA**: `0015b10` (initial CLI separation) + subsequent commits
- **Branch**: `main`
- **Date**: 2026-07-22

## CI Results

All checks pass on Python 3.14.2 (macOS).

```
ruff check .           → 0 errors
black --check .        → 0 changes needed
mypy eggcalc           → 0 errors
docs-check             → OK
pytest tests/ -v       → 3282+ passed, 33 skipped
```

## Import Architecture

### Before (Release 5)

```
import eggcalc → loads normalize, evaluator, units, capabilities
                 normalize loads argparse, traceback, exact/* (via CLI dispatch)
```

### After (Release 6)

```
import eggcalc → loads normalize, evaluator, units, capabilities
                 normalize: pure NL normalization pipeline (no argparse, no exact)
                 cli.py: separate CLI dispatch module (lazy-loaded)
```

### Import Boundary Test Results

16 subprocess-based tests verify:
- `import eggcalc` loads zero `eggcalc.exact.*` implementation modules
- `import eggcalc` loads zero `eggcalc.mcp.*` modules
- `from eggcalc import evaluate` does not load CLI dispatch
- `eggcalc.normalize` imports no argparse, exact, or MCP modules
- Backward-compatible `from eggcalc.normalize import main` still works

## CLI Architecture

### Command Registry (C2)

9 text commands declared in `COMMANDS` tuple of `CommandSpec` TypedDicts:
`inspect`, `count`, `regex`, `replace-check`, `lines`, `patch-check`, `shell-split`, `md-structure`, `dotenv-check`

Each entry has: name, aliases, description, usage, min_args, category, handler.
Dispatch is registry-driven via `_COMMAND_NAME_TO_SPEC` lookup.

### Entry Points

| Surface | Entry point |
|---------|-------------|
| `calc` console script | `eggcalc.cli:main` (pyproject.toml) |
| `python -m eggcalc` | `eggcalc/__main__.py` → `cli.main()` |
| Single-file `eggcalc.py` | `normalize_main()` (renamed from `cli.main()`) |
| `from eggcalc import main` | Lazy re-export via PEP 562 `__getattr__` |
| `from eggcalc.normalize import main` | Lazy re-export (backward compat) |

## Structural Unit Dimensions (D1-D8)

### Dimension Type

Immutable 8-exponent SI dimension (length, mass, time, current, temperature, amount, luminous_intensity, information) + angle flag.

```python
Dimension(length=1)           # L
Dimension(length=1, time=-1)  # L T^-1 (speed)
Dimension(mass=1, length=1, time=-2)  # M L T^-2 (force)
```

### UnitDefinition

Ties canonical name, dimension, scale factor, offset, and aliases into one immutable object.

### UnitRegistry

431 aliases → 20 canonicals → 16 dimensions. Built from `UNIT_BASE`, `UNIT_ALIASES`, `TEMPERATURE_CONVERSIONS`.

### Conversion Factor Parity

10 cross-family conversion tests confirm registry matches legacy `get_conversion_factor`:
km↔m, ft↔in, lb↔kg, mi↔km, gal↔L, psi↔Pa, kWh↔J, mph↔m/s, acre↔m2, GB↔B.

### Structural Compatibility

`are_units_compatible()` now uses Dimension comparison first, falling back to category-based matching for compound units not in the registry.

### Temperature

Temperature units (K, C, F, Ra) are marked `affine=True` in the registry. Affine units return `None` from `conversion_factor()` — conversion must use `convert_temperature()`.

## Authority Consolidation (E1-E5)

### Consolidated Items

| Item | Before | After |
|------|--------|-------|
| `MAX_NESTING_DEPTH` | Duplicated in evaluator.py + normalize.py | Single source: evaluator.py, re-imported by normalize.py |
| `McpServerConfig` defaults | Hardcoded literals | References module-level constants (`MAX_REQUEST_BYTES`, etc.) |
| `McpServerConfig.from_environment()` | Hardcoded defaults | References module-level constants |
| Build manifest validation | None | `--validate` flag checks duplicates, ordering, file existence |

### Authority Inventory

Documented in `architecture/authority_inventory.md` — 12 categories with authoritative sources, adapters, and test coverage.

## Benchmark Tooling (G1)

`scripts/measure_architecture_costs.py` — standard-library-only benchmark that measures:
- `import eggcalc` median/mean/stdev (5 samples)
- `from eggcalc import evaluate` timing
- `python -m eggcalc --help` startup
- `python -m eggcalc -e 5+3` expression timing
- Peak traced memory allocation

## Test Matrix

| Test file | Count | Covers |
|-----------|-------|--------|
| `test_import_boundaries.py` | 20 | Import graph, backward compat, command registry |
| `test_unit_dimensions.py` | 68 | Dimension type, UnitDefinition, registry, compatibility, display |
| `test_repl_and_cli.py` | 41 | CLI dispatch, REPL, output format |
| `test_unit_namespace.py` | 6 | Unit namespace exports |
| Existing tests | 3282+ | Full regression suite |

## Backward Compatibility

All documented public API surfaces preserved:
- `from eggcalc import evaluate, evaluate_raw, UnitValue, EvaluationError` ✓
- `from eggcalc.normalize import main, print_help` ✓ (lazy re-export)
- `python -m eggcalc` ✓
- `calc` console script ✓ (now points to `eggcalc.cli:main`)
- Generated `eggcalc.py` ✓ (regenerated, works correctly)
- NL expressions (`"five plus three"`) ✓
- Unit expressions (`"30m + 100ft"`) ✓
- All 3282+ existing tests pass ✓

## Documentation Updates

- `architecture/overview.md` — Updated module map, key data structures, entry points
- `architecture/authority_inventory.md` — New: authoritative source inventory
- `AGENTS.md` — Updated module map, lazy re-exports, command registry
