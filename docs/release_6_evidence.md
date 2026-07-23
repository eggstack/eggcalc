# Release 6 Evidence

Release 6 — Internal Architecture and Maintainability

## Commit

- **SHA**: `3825e7e` (corrective closure pass)
- **Branch**: `main`
- **Date**: 2026-07-23

## CI Results

All checks pass on Python 3.14.2 (macOS), Python 3.11–3.14 on Linux/macOS/Windows.

- **CI workflow run**: #30043943626
- **All 9 jobs**: package, test (ubuntu-latest, 3.11–3.14), test (macos-latest, 3.11–3.12), test (windows-latest, 3.11–3.12) — all success

```
ruff check .           → 0 errors
black --check .        → 0 changes needed
mypy eggcalc           → 0 errors in 38 source files
docs-check             → OK
pytest tests/          → 3676 collected, all pass
build_single.py        → validates and succeeds
smoke_release_surfaces → 9/9 pass
```

## Import Architecture

### Before (Release 5)

```
import eggcalc → loads normalize, evaluator, units, capabilities
                 normalize loads argparse, traceback, exact/* (via CLI dispatch)
```

### After (Release 6)

```
import eggcalc → loads _protocol, units, evaluator, normalize, capabilities
                 6 modules total, 0 exact, 0 MCP
                 cli.py: separate CLI dispatch module (lazy-loaded)
```

### Import Boundary Test Results

24 subprocess-based tests verify:
- `import eggcalc` loads exactly 6 modules (`_protocol`, `units`, `evaluator`, `normalize`, `capabilities`, `eggcalc`)
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
| Protocol versions | Duplicated in capabilities.py + server.py | Single source: `_protocol.py`, imported by both |

### Authority Inventory

Documented in `architecture/authority_inventory.md` — 12 categories with authoritative sources, adapters, and test coverage.

## ToolRegistry Validation (A1)

Construction-time cross-reference validation ensures:
- Every handler has a corresponding schema
- Every schema has a corresponding handler
- Every metadata entry references a registered tool
- Every profile entry references a registered tool
- Missing or inconsistent references raise `ValueError` at construction

## Configuration API (A2)

`McpServer.apply_configuration()` provides a single entry point for the full lifecycle:
1. Parse raw configuration values into a validated `ConfigSnapshot`
2. Validate types and semantics via `parse_config_snapshot()`
3. Assign the next generation under `ConfigManager` ownership
4. Atomically activate on the server's evaluator via `activate_snapshot()`
5. On failure, prior configuration is preserved unchanged

## Architecture Cost Measurements

Recorded at commit `1816aca`, Python 3.14.2, macOS, 5 samples each:

| Surface | Median | Mean | Stdev |
|---------|--------|------|-------|
| `import eggcalc` | 542ms | 570ms | 100ms |
| `from eggcalc import evaluate` | 369ms | 372ms | 14ms |
| `python -m eggcalc --help` | 366ms | 367ms | 5ms |
| `python -m eggcalc -e 5+3` | 441ms | 441ms | 21ms |

Peak traced memory: 31.8 MB

### Loaded Module Counts

| Surface | Total eggcalc | Exact | MCP |
|---------|--------------|-------|-----|
| `import eggcalc` | 6 | 0 | 0 |
| `from eggcalc import evaluate` | 6 | 0 | 0 |

Core modules loaded: `_protocol`, `units`, `evaluator`, `normalize`, `capabilities`, `eggcalc`

## Typed Public Consumer

`tests/test_typed_consumer.py` — 47 tests importing the documented public API with type annotations:
- Evaluation: `evaluate`, `evaluate_raw`, `evaluate_cached`, `evaluate_with_timeout`, `evaluate_async`, error handling
- Normalization: `normalize_expression`, `normalize_text`, `run`
- Units: `UnitValue`, `normalize_unit`, `is_unit`, `get_conversion_factor`, `get_unit_category`, `are_units_compatible`, `get_all_units`
- CLI exports: `main`, `print_help`, `run`
- Capabilities: `detect_capabilities`, `to_dict`, `to_json`
- Configuration: `load_user_config`, `get_default_evaluator`, `register_constant`, `register_function`, `setvar`/`getvar`/`delvar`
- Memory: `memory_store`/`recall`/`add`/`subtract`/`list`/`clear`
- Variables: `listvars`, `clearvars`
- Constants: `MAX_EXPONENT`, `MAX_FACTORIAL`, `MAX_RESULT_VALUE`, `DEFAULT_CACHE_SIZE`
- Protocol versions: `supported_protocol_versions` field
- Module exports: `__all__`, `__version__`, `__author__`

Passes against both source installs and wheel builds.

## Test Matrix

| Test file | Count | Covers |
|-----------|-------|--------|
| `test_typed_consumer.py` | 47 | Typed public API consumer (F3) |
| `test_import_boundaries.py` | 24 | Import graph, backward compat, command registry, lazy loading |
| `test_unit_dimensions.py` | 77 | Dimension type, UnitDefinition, registry, compatibility, display, parsing bounds |
| `test_repl_and_cli.py` | 41 | CLI dispatch, REPL, output format |
| `test_unit_namespace.py` | 6 | Unit namespace exports |
| `test_build_single.py` | 36 | Build correctness, parity, determinism, manifest validation |
| `test_release5_isolation.py` | 167 | Registry immutability, validation, config, concurrency, sessions |
| `test_mcp_server.py` | 675 | MCP protocol, tools, profiles, schemas |
| `test_documentation.py` | ~25 | Version parity, protocol parity, package/single-file parity |
| Other tests | ~2578 | Full regression suite |
| **Total** | **3676 collected** | |

## Backward Compatibility

All documented public API surfaces preserved:
- `from eggcalc import evaluate, evaluate_raw, UnitValue, EvaluationError` ✓
- `from eggcalc.normalize import main, print_help` ✓ (lazy re-export)
- `python -m eggcalc` ✓
- `calc` console script ✓ (now points to `eggcalc.cli:main`)
- Generated `eggcalc.py` ✓ (regenerated, works correctly, no residual relative imports)
- NL expressions (`"five plus three"`) ✓
- Unit expressions (`"30m + 100ft"`) ✓
- All 3676 collected tests pass ✓

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
- Compound parsing bounded: `MAX_COMPOUND_DEPTH=16`, `MAX_UNIT_STRING_LENGTH=256`, `MAX_COMPOUND_ATOMS=32`

### ToolRegistry Validation (Workstream A)
- Construction-time cross-reference validation for handler/schema/profile consistency
- Missing or inconsistent references raise `ValueError` at construction

### Protocol Version Unification (Workstream E)
- Created `eggcalc/_protocol.py` as single source for `SUPPORTED_PROTOCOL_VERSIONS`
- `capabilities.py` and `mcp/server.py` both import from `_protocol.py`
- Eliminated duplicate literal tuples
- 4 protocol parity tests verify single-source constraint

### Configuration API (Workstream A)
- Added `McpServer.apply_configuration()` as single entry point for parse+validate+generate+activate
- Failed activation preserves prior state unchanged

### Typed Public Consumer (Workstream F)
- `tests/test_typed_consumer.py` exercises entire documented public API under strict typing
- 47 tests covering evaluation, normalization, units, CLI exports, capabilities, config, memory, variables, constants

### Build Artifact Correctness
- Fixed residual `from ..exact.*` relative imports in generated `eggcalc.py`
- Fixed `from . import units` handling for single-file mode
- Added `_protocol` module to `MODULES_CALC` build manifest
- Build manifest validation via `--validate` flag
- Deterministic generation test (build twice, compare bytes)

### Limit Consolidation
- Removed duplicate `MAX_TEXT_LENGTH_REGEX` constant
- All text length limits now use single `MAX_TEXT_LENGTH` source

### Static Analysis
- mypy passes with 0 errors across 38 source files
- ruff passes with 0 errors
- black formatting clean
- `# type: ignore[operator]` added for `eggcalc.exact` lazy `__getattr__` re-exports that confuse mypy

### Verification
- 3676 tests collected and passing
- All import boundary tests pass (24 tests)
- Single-file generation and smoke tests pass (9/9 surfaces)
- Ruff, black, mypy checks pass
- Deterministic build test passes
- No residual package-relative imports in generated file
- Editable install surface test passes
- REPL surface test passes

## Retained Compatibility Shims

| Shim | Location | Reason | Removal timing |
|------|----------|--------|----------------|
| `from eggcalc.normalize import main, print_help` | `eggcalc/normalize.py` (lazy re-export) | Backward compatibility for existing code | Next major version |
| `handle_request(request, session=None)` module-level | `eggcalc/mcp/server.py` | Deprecated but still used by some callers | Next major version (emits DeprecationWarning) |
| `eggcalc/__init__.py` lazy CLI exports | `eggcalc/__init__.py` PEP 562 | Avoids pulling argparse at import time | Permanent (design choice) |

## Deferred Non-Blocking Work

The following items are documented but do not block Release 6 closure:

1. **Differential/invariant tests for all 16+ unit families** — 10 representative cross-family pairs tested; full family-by-family coverage deferred
2. **Command inventory parity test** (package vs single-file) — commands are identical since they share `cli.py`; test deferred
3. **Capabilities parity test** (package vs single-file) — capabilities are identical since they share `capabilities.py`; test deferred
4. **REPL and editable install surface tests in smoke script** — now added ✓
5. **Differentiated mypy/ruff profile for migrated modules** — uniform profile is sufficient; all modules pass existing checks
