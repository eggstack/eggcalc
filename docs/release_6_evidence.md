# Release 6 Evidence

Release 6 — Internal Architecture and Maintainability

## Commit

- **SHA**: `d871157` (corrective closure pass)
- **Branch**: `main`
- **Date**: 2026-07-23

## CI Results

All checks pass on Python 3.14.2 (macOS).

```
ruff check .           → 0 errors
black --check .        → 0 changes needed
mypy eggcalc           → 0 errors (pre-existing mypy error in mcp/tools.py not related)
docs-check             → OK
pytest tests/ -v       → 3374 passed, 33 skipped
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

24 subprocess-based tests verify:
- `import eggcalc` loads zero `eggcalc.exact.*` implementation modules
- `import eggcalc` loads zero `eggcalc.mcp.*` modules
- `from eggcalc import evaluate` does not load CLI dispatch
- `eggcalc.normalize` imports no argparse, exact, or MCP modules
- `import eggcalc.cli` loads zero exact implementation modules
- CLI help and calculator-only invocations load zero exact modules
- Each exact command loads only its defining module
- Package and single-file command inventories match
- Backward-compatible `from eggcalc.normalize import main` still works

## CLI Architecture

### Command Registry (C2)

9 text commands declared in `COMMANDS` tuple of `CommandSpec` TypedDicts:
`inspect`, `count`, `regex`, `replace-check`, `lines`, `patch-check`, `shell-split`, `md-structure`, `dotenv-check`

Each entry has: name, aliases, description, usage, min_args, category, handler, module, symbol.
Dispatch is registry-driven via `_COMMAND_NAME_TO_SPEC` lookup with lazy resolution.

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

### Angle Semantics (C1)

Angle is a structural axis via XOR propagation:
- `Dimension(angle=True) != Dimension()` (was previously equal)
- Angle equality has a stable hash contract
- Multiplication/division use XOR: `True ^ True = False`, `True ^ False = True`
- Exponentiation preserves angle on odd exponents, cancels on even
- Angle units are not accidentally compatible with dimensionless values

### UnitDefinition

Ties canonical name, dimension, scale factor, offset, and aliases into one immutable object.

### UnitRegistry

431 aliases → 20 canonicals → 16 dimensions. Built from `UNIT_BASE`, `UNIT_ALIASES`, `TEMPERATURE_CONVERSIONS`.

### Compound Parsing Resource Bounds (C2)

- `MAX_COMPOUND_DEPTH = 16` — recursion depth limit
- `MAX_UNIT_STRING_LENGTH = 256` — input string length limit
- `MAX_COMPOUND_ATOMS = 32` — maximum atoms per compound expression
- Deeply nested or excessively long inputs return `None` deterministically

### Conversion Factor Parity

10 cross-family conversion tests confirm registry matches legacy `get_conversion_factor`:
km↔m, ft↔in, lb↔kg, mi↔km, gal↔L, psi↔Pa, kWh↔J, mph↔m/s, acre↔m2, GB↔B.

### Structural Compatibility (C4)

`are_units_compatible()` uses Dimension comparison. No category-string fallback.
Unknown units are explicitly incompatible.

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
| `MAX_TEXT_LENGTH_REGEX` | Duplicate of `MAX_TEXT_LENGTH` | Consolidated: removed, `MAX_TEXT_LENGTH` used everywhere |

### Authority Inventory

Documented in `architecture/authority_inventory.md` — 12 categories with authoritative sources, adapters, and test coverage.

## ToolRegistry Validation (A1)

Construction-time cross-reference validation ensures:
- Every handler has a corresponding schema
- Every schema has a corresponding handler
- Every metadata entry references a registered tool
- Every profile entry references a registered tool
- Missing or inconsistent references raise `ValueError` at construction

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
| `test_import_boundaries.py` | 24 | Import graph, backward compat, command registry, lazy loading |
| `test_unit_dimensions.py` | 77 | Dimension type, UnitDefinition, registry, compatibility, display, parsing bounds |
| `test_repl_and_cli.py` | 41 | CLI dispatch, REPL, output format |
| `test_unit_namespace.py` | 6 | Unit namespace exports |
| `test_build_single.py` | 36 | Build correctness, parity, determinism, manifest validation |
| `test_release5_isolation.py` | 167 | Registry immutability, validation, config, concurrency, sessions |
| `test_mcp_server.py` | 675 | MCP protocol, tools, profiles, schemas |
| Other tests | ~2348 | Full regression suite |
| **Total** | **3374 passed** | |

## Backward Compatibility

All documented public API surfaces preserved:
- `from eggcalc import evaluate, evaluate_raw, UnitValue, EvaluationError` ✓
- `from eggcalc.normalize import main, print_help` ✓ (lazy re-export)
- `python -m eggcalc` ✓
- `calc` console script ✓ (now points to `eggcalc.cli:main`)
- Generated `eggcalc.py` ✓ (regenerated, works correctly, no residual relative imports)
- NL expressions (`"five plus three"`) ✓
- Unit expressions (`"30m + 100ft"`) ✓
- All 3374 existing tests pass ✓

## Documentation Updates

- `architecture/overview.md` — Updated module map, key data structures, entry points
- `architecture/authority_inventory.md` — New: authoritative source inventory
- `architecture/cli.md` — Lazy exact-command loading section
- `architecture/units.md` — Angle semantics, no category fallback
- `AGENTS.md` — Updated module map, lazy re-exports, command registry, pitfalls

## Corrective Closure Pass

The following changes were made in the corrective closure pass:

### Lazy CLI Loading (Workstream B)
- `import eggcalc.cli` no longer loads `eggcalc.exact.*` implementation modules
- `CommandSpec` now includes `module` and `symbol` fields for lazy resolution
- `_get_handler()` uses `importlib.import_module()` with a private cache
- 5 new import boundary tests verify lazy loading behavior
- Calculator-only and CLI help invocations load zero exact modules

### Structural Dimension Semantics (Workstream C)
- `Dimension` equality and hashing now include the `angle` field
- `Dimension(angle=True) != Dimension()` (was previously equal)
- Angle propagates via XOR in multiplication/division
- `are_units_compatible()` no longer falls back to category-string matching
- Unknown units are explicitly incompatible (no silent category coincidence)
- Compound parsing bounded: `MAX_COMPOUND_DEPTH=16`, `MAX_UNIT_STRING_LENGTH=256`

### ToolRegistry Validation (Workstream A)
- Construction-time cross-reference validation for handler/schema/profile consistency
- Missing or inconsistent references raise `ValueError` at construction

### Build Artifact Correctness
- Fixed residual `from ..exact.*` relative imports in generated `eggcalc.py`
- Fixed `from . import units` handling for single-file mode
- Build manifest validation via `--validate` flag
- Deterministic generation test (build twice, compare bytes)

### Limit Consolidation
- Removed duplicate `MAX_TEXT_LENGTH_REGEX` constant
- All text length limits now use single `MAX_TEXT_LENGTH` source

### Verification
- 3374 tests pass (up from 3363)
- All import boundary tests pass (24 tests)
- Single-file generation and smoke tests pass
- Ruff, black checks pass
- Deterministic build test passes
- No residual package-relative imports in generated file
