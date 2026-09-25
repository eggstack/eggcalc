# Phase 1 Plan — Safe Configuration Loading

## Objective

Make `eggcalc` safe by default when imported as a Python library or loaded by an agent inside an arbitrary repository, while preserving explicitly documented CLI custom-config behavior and keeping MCP mode hardened.

The main deliverable is to remove cwd-local Python execution from package import. `eggcalc_config.py` may remain a CLI customization mechanism, but it must be loaded by explicit CLI startup logic rather than by `eggcalc.__init__` import side effects.

## Background

The package currently supports `eggcalc_config.py` for custom constants, functions, units, and aliases. That feature is useful for local CLI use, but package import can happen inside untrusted or semi-trusted directories during agent workflows. Import-time execution of cwd-local Python is therefore too surprising for a library and too risky for agent contexts.

The MCP server already sets `EGGCALC_NO_CONFIG=1` early. Preserve and test that hardening.

## Constraints

Runtime remains stdlib-only.

Do not remove CLI customization unless a deliberate breaking-change decision is made separately.

Do not introduce new config file formats or parser dependencies.

Do not change deterministic MCP behavior.

Do not break the single-file build.

## Desired behavior matrix

| Surface | Default behavior | Opt-out / opt-in behavior |
|---|---|---|
| `import eggcalc` | Does not load cwd `eggcalc_config.py` | Optional explicit API/env opt-in may load config |
| Python API call after import | Uses built-in constants/functions/units unless caller explicitly loads config | Explicit `load_user_config()` remains available |
| CLI `calc ...` | May load cwd config for backward compatibility if not disabled | `EGGCALC_NO_CONFIG=1` disables config |
| CLI interactive mode | Same as CLI single-expression mode | `EGGCALC_NO_CONFIG=1` disables config |
| MCP package mode | Never loads cwd config | No cwd config opt-in in MCP mode |
| MCP single-file mode | Never loads cwd config | No cwd config opt-in in MCP mode |
| Single-file CLI mode | Mirrors package CLI behavior | `EGGCALC_NO_CONFIG=1` disables config |

## Implementation steps

### 1. Locate all config-loading entry points

Inspect these files before editing:

- `eggcalc/__init__.py`
- `eggcalc/evaluator.py`
- `eggcalc/normalize.py`
- `eggcalc/mcp/server.py`
- `build_single.py`
- tests covering config behavior

Confirm whether config loading occurs only through `eggcalc.__init__` and direct calls to `load_user_config()`, or whether other startup paths load it indirectly.

### 2. Remove import-time config loading

Remove the automatic load from `eggcalc/__init__.py`:

```python
import os as _os

if not _os.environ.get("EGGCALC_NO_CONFIG", ""):
    load_user_config()
```

Do not remove `load_user_config` from the public API. Users should still be able to call it explicitly.

### 3. Add a CLI-owned config helper

Add a small helper in CLI startup code, preferably `eggcalc/normalize.py`, with behavior similar to:

```python
def maybe_load_cli_config() -> None:
    if os.environ.get("EGGCALC_NO_CONFIG", ""):
        return
    try:
        from .evaluator import load_user_config
    except Exception:
        return
    load_user_config()
```

Keep error behavior consistent with the existing `load_user_config()` behavior. Do not swallow errors differently unless current behavior is already too noisy. If behavior changes, document and test it.

Call the helper exactly once during CLI startup, before evaluating user expressions. Ensure it covers:

- single-expression CLI mode
- `-e`/`--expression`
- interactive mode
- any text subcommands that depend on config only if they currently did

Avoid calling it from library helpers such as `evaluate_raw()` unless explicit backward compatibility demands it. The target is no config execution from normal API usage unless the caller opted in.

### 4. Preserve MCP hardening

Keep `eggcalc/mcp/server.py` setting `EGGCALC_NO_CONFIG=1` before package imports.

Check whether moving config loading out of `__init__` makes any MCP test redundant. Keep at least one direct regression test proving MCP does not load cwd config.

### 5. Update single-file assembly

Run `python build_single.py` locally after changes.

Inspect generated `eggcalc.py` enough to confirm:

- CLI config helper is included.
- MCP entry still sets `EGGCALC_NO_CONFIG=1`.
- No source-only package import assumption was introduced.

Add or adjust tests so single-file CLI and single-file MCP smoke tests cover config behavior if the current CI structure permits it.

### 6. Add regression tests

Add tests using a temporary directory containing an `eggcalc_config.py` with a detectable side effect.

Recommended side effects:

- create a sentinel file
- set a custom constant and check whether it is visible
- print output only if current test harness can capture it reliably

Required tests:

1. `import eggcalc` from a cwd containing `eggcalc_config.py` does not execute the file.
2. Explicit `eggcalc.load_user_config()` still loads the file.
3. CLI execution loads config by default if backward compatibility is preserved.
4. CLI execution with `EGGCALC_NO_CONFIG=1` does not load config.
5. MCP mode does not load config.
6. Single-file CLI behavior matches package CLI behavior.
7. Single-file MCP behavior does not load config.

Prefer subprocess tests for import/CLI/MCP behavior so module cache state does not hide side effects.

### 7. Update documentation

Update all relevant docs:

- README security section
- `docs/api.md`
- `docs/mcp.md`
- `AGENTS.md`
- architecture docs if they discuss config loading

Required documentation points:

- Library import is side-effect-free with respect to cwd config.
- CLI may load `eggcalc_config.py` for customization unless disabled.
- Explicit API call `load_user_config()` remains available.
- MCP never loads cwd config.
- `EGGCALC_NO_CONFIG=1` disables config loading for CLI and remains enforced by MCP.

## Edge cases to check

Config loading should not happen merely because `from eggcalc import evaluate_raw` is executed.

Config loading should not happen merely because docs generation imports package modules.

Config loading should not happen when MCP schemas/tools are imported by tests.

Repeated CLI evaluations in interactive mode should not reload config on every expression unless this was already intentional.

If config loading is guarded by evaluator-level `_config_loaded`, ensure the guard still works after moving call sites.

## Validation commands

Run:

```bash
ruff check eggcalc tests
black --check eggcalc tests
python build_single.py
python scripts/generate_mcp_docs.py --check
pytest tests/ -v
mypy eggcalc --ignore-missing-imports
```

Also manually smoke test:

```bash
python -m eggcalc "2+2"
EGGCALC_NO_CONFIG=1 python -m eggcalc "2+2"
python eggcalc.py "2+2"
EGGCALC_NO_CONFIG=1 python eggcalc.py "2+2"
```

For MCP smoke tests, send at least `initialize`, `tools/list`, and `tools/call` with `math_eval` to both package and single-file server modes.

## Acceptance criteria

- `import eggcalc` does not execute cwd `eggcalc_config.py`.
- Explicit `load_user_config()` remains functional.
- CLI config behavior is either preserved or deliberately changed and documented.
- `EGGCALC_NO_CONFIG=1` reliably disables CLI config loading.
- MCP mode never loads cwd config.
- Single-file behavior matches package behavior.
- Docs accurately describe the new config-loading model.
- CI remains green.

## Handoff notes

This phase should be implemented before documentation cleanup because it changes the truth that docs must describe. Avoid broad refactors while changing config behavior; keep the diff small and heavily tested.
