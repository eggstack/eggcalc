# build.md — Build System and Distribution

How eggcalc is assembled, packaged, and distributed.

## Table of Contents

- [Build Pipeline](#build-pipeline)
- [build_single.py](#build_singlepy)
- [Module Manifest](#module-manifest)
- [Assembly Process](#assembly-process)
- [install.py](#installpy)
- [Development Commands](#development-commands)

## Build Pipeline

eggcalc has two distribution paths:

| Path | Output | Use Case |
|------|--------|----------|
| **PyPI package** | `eggcalc-1.1.8-py3-none-any.whl` | Standard `pip install eggcalc` |
| **Single-file** | `eggcalc.py` (~394KB) | Portable, zero-install distribution |

Both are validated by `make check` and `make package-check`.

## build_single.py

Assembles all modules into a single self-contained `eggcalc.py` file. This is the primary distribution mechanism for portability.

### Module Manifest

`MODULE_MANIFEST` is a tuple of `ModuleSpec` dataclasses — the single source of truth for module ordering, dependencies, and validation:

```python
@dataclass(frozen=True)
class ModuleSpec:
    name: str          # dotted module name (e.g. "exact.primitives")
    path: str          # filesystem path relative to eggcalc/
    group: Literal["core", "exact", "mcp"]
    depends_on: tuple[str, ...] = ()
    include_single_file: bool = True
```

Three derived views are generated from the manifest:
- `MODULES_CALC` — core calculator modules (units, evaluator, normalize, cli, capabilities, _protocol)
- `MODULES_EXACT` — 25 exact/ submodules
- `MODULES_MCP` — 3 MCP server modules (schemas, tools, server)

### Assembly Process

1. **Validate manifest** — checks for duplicates, missing files, unknown deps, cycles, reachability
2. **Topological sort** — modules assembled in dependency order
3. **Transform** — strips docstrings, relative imports, `__main__` blocks, `__future__` imports
4. **Rewrite imports** — relative imports become global assignments
5. **Concatenate** — all modules written to single file with section markers
6. **Output** — `eggcalc.py` in project root (or custom path via `-o`)

```bash
python3 build_single.py --validate   # Validate only
python3 build_single.py              # Build eggcalc.py
python3 build_single.py -o /path     # Custom output path
```

### Constraints

- All runtime code must live in one of the six core modules or `exact/`/`mcp/` packages
- No imports outside the allowed set (standard library only)
- `__main__.py` is a thin entry point (not in the manifest)
- `confusables.py` is auto-generated data (~176KB) — included as-is

## install.py

Builds and installs `eggcalc.py` to `~/.local/bin/calc`.

```bash
python install.py --install     # Build + install
python install.py --update      # Rebuild + update
python install.py --uninstall   # Remove
```

## Development Commands

```bash
make build          # python -m build (wheel + sdist)
make package-check  # twine check + smoke tests
make release-check  # check + package-check
make publish        # twine upload
```

See [docs/releasing.md](../docs/releasing.md) for the manual PyPI release procedure.

See also: [overview.md](overview.md) for module placement, [api.md](api.md) for public API surface.
