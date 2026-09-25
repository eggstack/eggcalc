# build.md — Build System and Distribution

How eggcalc is assembled, packaged, and distributed.

## Table of Contents

- [Build Pipeline](#build-pipeline)
- [build_single.py](#build_singlepy)
- [Module Manifest](#module-manifest)
- [Topological Sort](#topological-sort)
- [Module Extraction (`get_module_code`)](#module-extraction-get_module_code)
- [Cross-Module Rewrites](#cross-module-rewrites)
- [Entry-Point Renames](#entry-point-renames)
- [MCP Prefix Conflicts](#mcp-prefix-conflicts)
- [Assembly and Entry Point](#assembly-and-entry-point)
- [Validation (`validate_build_manifest`)](#validation-validate_build_manifest)
- [install.py](#installpy)
- [pyproject.toml](#pyprojecttoml)
- [Development Commands (Makefile)](#development-commands-makefile)
- [CI](#ci)
- [Releases](#releases)
- [Constraints](#constraints)

## Build Pipeline

eggcalc has two distribution paths:

| Path | Output | Use Case |
|------|--------|----------|
| **PyPI package** | `eggcalc-<version>-py3-none-any.whl` + sdist | Standard `pip install eggcalc` |
| **Single-file** | `eggcalc.py` (self-contained, stdlib-only) | Portable, zero-install distribution |

Version source is `eggcalc/_version.py` (currently `1.1.11`); `pyproject.toml`
reads it via `setuptools.dynamic`, and `build_single.py` embeds it as a
module-level `__version__` assignment.

Both paths are validated by `make check` and `make package-check`.

## build_single.py

Assembles all modules into a single self-contained `eggcalc.py` file
(1516 lines of builder). Stdlib-only, so any `python3` works:

```bash
python3 build_single.py --validate   # Validate only (always runs before build)
python3 build_single.py              # Build eggcalc.py in project root
python3 build_single.py -o /path     # Custom output path
```

## Module Manifest

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

38 entries total: 7 core + 28 exact + 3 MCP.

Core (7):

| name | path | depends_on |
|------|------|------------|
| `_process` | `_process.py` | — |
| `units` | `units.py` | — |
| `evaluator` | `evaluator.py` | `_process`, `units` |
| `_protocol` | `_protocol.py` | — |
| `normalize` | `normalize.py` | `units`, `evaluator` |
| `capabilities` | `capabilities.py` | `_protocol` |
| `cli` | `cli.py` | `units`, `evaluator`, `normalize`, `capabilities` |

Exact (28): `exact.primitives` (no deps; leaf for most), `exact.diff`
(`primitives`), `exact.diff_analysis` (`diff`, `patch`), `exact.validate`
(`primitives`), `exact.measure` (`primitives`), `exact.unicode_tools`
(`primitives`, `confusables`), `exact.synthesis` (`primitives`, `diff`,
`measure`, `unicode_tools`), `exact.confusables` (`primitives`),
`exact.config`/`shell`/`markdown`/`patch`/`transform`/`position`/
`identifier`/`glob`/`inspect_prompt`/`version`/`manifests`/`llm_hygiene`/
`repo_audit` (each `primitives`), `exact.path_tools` (`primitives`,
`unicode_tools`), `exact.identifier_inspect` (`identifier`, `diff`,
`unicode_tools`), `exact.unicode_policy` (`primitives`, `unicode_tools`),
`exact.cargo` (`primitives`, `unicode_tools`), and three dependency-free
leaves with no `exact/` deps: `exact.network`, `exact.encoding`,
`exact.temporal`.

MCP (3):

| name | path | depends_on |
|------|------|------------|
| `mcp.schemas` | `mcp/schemas.py` | `exact.primitives` |
| `mcp.tools` | `mcp/tools.py` | `mcp.schemas`, `_process`, `evaluator`, `units`, plus 28 exact modules (cargo, config, confusables, diff, diff_analysis, encoding, glob, identifier, identifier_inspect, inspect_prompt, llm_hygiene, manifests, markdown, measure, network, patch, path_tools, position, primitives, repo_audit, shell, synthesis, temporal, transform, unicode_policy, unicode_tools, validate, version) |
| `mcp.server` | `mcp/server.py` | `mcp.schemas`, `mcp.tools`, `evaluator`, `capabilities` |

Three derived views are generated from the manifest (never hand-maintained):

- `MODULES_CALC` — core paths (`_process`, `units`, `evaluator`, `_protocol`, `normalize`, `capabilities`, `cli`)
- `MODULES_EXACT` — 28 exact/ submodules
- `MODULES_MCP` — 3 MCP modules (`mcp/schemas`, `mcp/tools`, `mcp/server`)
- `ALL_MODULES = MODULES_CALC + MODULES_EXACT + MODULES_MCP`

`__main__.py` is a thin entry point and is **not** in the manifest.

## Topological Sort

`_topological_sort(manifest)` returns modules in dependency order via DFS,
preserving declaration order for ties. Raises `ValueError` on unknown
dependency or dependency cycle. `build_single_file()` iterates this order
and emits `# === Core modules ===` / `# === Exact modules ===` /
`# === Mcp modules ===` group headers plus per-file `# === <path> ===`
section markers.

## Module Extraction (`get_module_code`)

`get_module_code(module_name)` returns `(code, imports, exact_globals)`:

1. **Docstring stripping** — drops the leading `"""..."""` module docstring
   (first-block scan); the built file gets its own `HEADER` instead.
2. **Top-level multi-line import stripping** — any top-level
   `from X import (` without `)` on the same line is skipped until the
   closing paren. Exception: `from ..exact ...` / `from .exact ...` blocks
   are converted to global aliases (`alias = name`) recorded in
   `exact_globals` and emitted under `# === Exact module global aliases ===`.
3. **Relative-import stripping** — top-level `from .<mod> import ...`
   matching an inlined module is dropped (the name is now a global).
   Local (indented) relative imports are kept for post-processing.
4. **`__future__` stripping** — removed per-module; `HEADER` carries the
   single `from __future__ import annotations`.
5. **`__all__` stripping** — all per-module `__all__` assignments are
   dropped; the canonical `__all__` extracted from `eggcalc/__init__.py`
   by `get_init_all()` (AST lookup) is appended once under
   `# === Public API surface (from __init__.py) ===`.
6. **`__main__` stripping** — `if __name__ == "__main__":` blocks are
   dropped; the built file supplies its own `_main()` + guard.
7. **Single-line import collection** — top-level (column-0), complete,
   non-relative, non-`eggcalc`, non-`__future__` `import X` /
   `from X import Y` lines (no parens/backslash) are collected, deduplicated
   (order-preserving), and emitted once under `# === Collected imports ===`.
8. **Post-processing (`_replace_local_imports`)** — indented
   `from <exact-module> import name` lines become global assignments
   (`name = name`, `new = orig` for `as`); indented imports of inlined
   non-exact modules (`evaluator`, `units`, …) are removed (names are
   already globals), including a surrounding `try:`/`except` wrapper when
   present. `from . import X` / `from .. import X` for inlined modules
   become `sys.modules` lookups.

## Cross-Module Rewrites

Naive `str.replace` calls in `get_module_code` normalize references that
only exist as package paths in source (guarded by check 11, see below):

- `units.UNIT_BASE` / `UNIT_ALIASES` / `UNIT_CATEGORIES` /
  `TEMPERATURE_CONVERSIONS` / `_UNITS_LOCK` / `_rebuild_conversions()` /
  `_simplify_unit_string` / `_expand_short_compound` → bare names.
- `from eggcalc import __version__` → comment (built file defines it).
- `from .primitives import` / `diff` / `validate` / `measure` /
  `unicode_tools` / `synthesis` / `confusables` / `config` / `shell` /
  `path_tools` / `markdown` / `patch` / `transform` / `position` /
  `identifier` / `identifier_inspect` / `glob` / `unicode_policy` /
  `inspect_prompt` / `cargo` / `version` → `from <bare> import` (plus
  parenthesized-block variants → `# ... imports handled inline`).
- `from .schemas/tools/server import` → `from schemas/tools/server import`.
- `from ..exact import` → `from exact import`; `from ..exact.<m> import (`
  → inline comments (with a regex for the multi-line `patch` block).
- `from .. import EvaluationError, evaluate_raw` →
  `from evaluator import EvaluationError, evaluate_raw`;
  `from .. import evaluator as _evaluator` → comment, plus
  `_evaluator._mcp_mode` → `_mcp_mode`,
  `_evaluator.configure_default_evaluator(` →
  `configure_default_evaluator(`, `_evaluator.Evaluator(` → `Evaluator(`,
  `_evaluator.get_config_generation()` → `get_config_generation()`,
  `_evaluator.Evaluator:` → `Evaluator:`,
  `_evaluator._server_evaluator` → `_server_evaluator`.
- `from ..capabilities import detect_capabilities` → comment (inlined).
- Synthesis aliased primitives (`_measure_basic(`, `_char_category_metrics(`,
  `_line_metrics(`, `_word_metrics(`, `_find_invisibles(`,
  `_count_graphemes(`, `_casefold_text(`, `_normalize_unicode(`,
  `_normalized_equal(`, `_raw_equal(`, `_visible_repr(`,
  `_detect_confusables(`, `_detect_mixed_scripts(`,
  `_common_prefix_suffix(`, `_diff_spans(`, `_first_diff(`,
  `_levenshtein_distance(`) → unprefixed names.
- `_SUPPORTED_PROTOCOL_VERSIONS` → `SUPPORTED_PROTOCOL_VERSIONS` in
  `capabilities.py` usage.
- Patch aliases: built file appends `_patch_apply_check =
  patch_apply_check` and `_patch_summary = patch_summary` because the lazy
  `as _patch_*` imports in `tools.py` are stripped.
- `_RISKY_REPLACE_SOURCES` (12 patterns: the `units.*` rewrites above plus
  `from ..exact import`, `from .. import EvaluationError`,
  `from .. import evaluator as _evaluator`) documents the BUG-02 hazard:
  naive replaces would corrupt string literals/comments containing those
  substrings.

## Entry-Point Renames

Two `main()` functions would collide in one file, so each is renamed by
docstring-gated replace:

- `normalize` (CLI): when `'"""Main entry point for CLI."""'` is present,
  `def main() -> int:` → `def normalize_main() -> int:`, plus removal of
  `import eggcalc`, `eggcalc.__version__` → `__version__`, and the
  `from eggcalc.mcp.server import mcp_main/set_active_profile/
  set_schema_detail` lines. `normalize_main` exists **only** in the built
  file — never reference it in source or tests.
- `mcp.server`: when `'"""Main entry point for MCP server.'` is present,
  `def main() -> int:` → `def mcp_main() -> int:` and
  `mcp_main = main` → comment. Source keeps `main` + `mcp_main` alias;
  the built file has only `mcp_main`.

The built-file `_main()` dispatches: `--capabilities` →
`detect_capabilities()`; `--commands` / `--mcp` / expressions / help /
version / REPL flags are forwarded to `normalize_main()` via rewritten
`sys.argv` (mirroring `cli.main` rejections for `--commands`/`--version`
combined with an expression).

## MCP Prefix Conflicts

`MCP_CONFLICT_FUNCTIONS` (24 names) lists MCP tool wrappers that collide
with exact/ public helpers in the flat namespace:

```python
MCP_CONFLICT_FUNCTIONS = (
    "text_equal", "text_replace_check", "line_range_extract",
    "line_range_compare", "text_window", "list_compare", "shell_split",
    "shell_quote_join", "path_normalize", "escape_text", "unescape_text",
    "text_hash", "text_transform", "text_position", "identifier_analyze",
    "validate_json", "json_compare", "json_extract", "json_shape",
    "regex_finditer", "regex_safety_check", "validate_schema_light",
    "json_canonicalize", "json_query",
)
```

During assembly, each `def <name>(` in an `mcp` module becomes
`def _mcp_<name>(` (first match only) and each `"<name>": <name>,` handler
entry becomes `"<name>": _mcp_<name>,`. The build fails loudly if any name
is defined more than once in one module or not exactly once across all
MCP modules (`missing_renames` check). Check 10 allowlists both the
`_mcp_*` and bare names so the intentional collision is not flagged.

## Assembly and Entry Point

`build_single_file()`:

1. Reads the version, topologically sorts the manifest.
2. Extracts/transforms each module, applies MCP renames, collects imports
   and exact globals.
3. Fails on ambiguous or missing MCP renames.
4. Dedupes imports, writes `HEADER` + `__version__` + imports + module
   code + exact aliases + patch aliases + canonical `__all__` + `_main()`.
5. Runs `_replace_local_imports`, then `ast.parse` validates the result
   before writing; output is `chmod +x` on non-Windows.
6. Prints core/exact/MCP module counts and unique-import count.

## Validation (`validate_build_manifest`)

Returns a list of error strings (empty when valid); `main()` always
validates before building, and `--validate` stops after validation.
13 checks:

1. Duplicate names or paths.
2. Missing source files on disk.
3. Unknown dependencies (not in the manifest name set).
4. Dependency cycles (via `_topological_sort`).
5. Invalid group (must be `core`/`exact`/`mcp`).
6. Undeclared relative-import targets: every top-level relative import
   found by `_relative_import_targets()` (AST visitor, top-level only,
   skips function/class bodies and `__main__` blocks) must be declared as
   a dependency (or be a package prefix); literal CLI targets from
   `_literal_cli_targets()` (`module = "..."` strings in `cli.py`) must be
   in the manifest.
7. (Numbering in source skips 7; reachability is check 8.)
8. Reachability: every `include_single_file` module must be reachable from
   `cli` or `mcp.server` via `depends_on`; all `exact` modules count as
   reachable (lazy `importlib` in `cli.py`/`mcp/tools.py`).
9. No residual `^from \.\.?` package-relative imports in generated code.
10. No duplicate top-level `def`/`class`/assignment globals across modules
    (private `_`-prefixed identical definitions allowed; MCP conflict
    names + `main` allowlisted; conflicting assignments with different
    values flagged).
11. BUG-02 guard: no `_RISKY_REPLACE_SOURCES` pattern inside any string
    literal (AST) or comment (tokenize) — a future doc example containing
    e.g. `"from ..exact import ..."` fails validation instead of shipping
    a silently corrupted build.
12. Generated concatenation still parses as valid Python.
13. Every submodule named by `_LAZY_IMPORTS` in `exact/__init__.py`
    (parsed via AST by `_lazy_exact_modules()`, 26 modules) is present in
    the manifest. `exact.confusables` and `exact.manifests` are in the
    manifest but not named by `_LAZY_IMPORTS` (data/aggregate modules) —
    the check is one-directional.

## install.py

Builds and installs `eggcalc.py` to a platform path (408 lines):

```bash
python install.py --install     # Build + install
python install.py --update      # Rebuild + update
python install.py --uninstall   # Remove
python install.py --path /custom/dir --no-path --spawn-shell
```

- `get_install_path()`: `~/.local/bin` on POSIX;
  `%LOCALAPPDATA%/Programs/calc` on Windows.
- `build_single_file()`: runs `build_single.py` via subprocess, returns
  `eggcalc.py`.
- `create_executable()`: atomic copy via `tempfile.mkstemp` +
  `os.replace`, `chmod 755`.
- `is_installed()`: true if `calc` exists in the install dir **or** a
  pip console-script entry point is on `PATH`
  (`_is_pip_entry_point()` sniffs the first `calc` on `PATH` for
  `"from eggcalc"` / `"import eggcalc"` in its first 512 bytes).
- `add_to_path()` / `remove_from_path()`: append/remove
  `export PATH="<dir>:$PATH"` with a `# Added by eggcalc install` marker
  in `~/.zshrc` (if present) else `~/.bashrc`; Windows prints `setx`
  instructions. Paths containing shell-unsafe chars
  (`"$`\\!#;&|` + newline) are rejected by `_validate_shell_path()`.
- `update_calc()`: if a pip entry point is detected, upgrades via
  `pip install --upgrade eggcalc` instead of replacing the file.
- `uninstall_calc()`: removes only `calc` + `.calc_tmp_*` leftovers (never
  the whole directory blindly), prunes the shell-config block, collapses
  blank lines.

## pyproject.toml

- `build-system`: `setuptools>=61.0` + `wheel`, `setuptools.build_meta`.
- `project`: name `eggcalc`, dynamic version, MIT, `requires-python =
  ">=3.11"`, classifiers for 3.11–3.14, zero runtime `dependencies`.
- `project.optional-dependencies.dev`: pytest, pytest-cov, black, ruff,
  mypy, mkdocs/material/mkdocstrings, pre-commit, build, twine.
- `project.scripts`: `calc = "eggcalc.cli:main"`.
- `tool.setuptools`: packages under `.` matching `eggcalc*`; `py.typed`
  included; version from `eggcalc._version.__version__`.
- `tool.pytest.ini_options`: `tests/` root, `test_*.py` / `Test*` /
  `test_*` discovery, `faulthandler_timeout = 300`.
- `tool.black`: line-length 100, py311–py314, no string normalization.
- `tool.ruff.lint`: `E,W,F,I,UP,B,C4` with ignores for E501, E731, E741,
  E402, B006, B007, B904, B905, C414, C416, F841, W293.
- `tool.mypy`: `python_version = 3.11`, `warn_return_any`,
  `warn_unused_ignores`, `disallow_untyped_defs`; per-module overrides for
  `cli`, `units`, `normalize`, `evaluator`, `capabilities`, `_protocol`
  add `check_untyped_defs`, `no_implicit_optional`, `strict_equality`.

## Development Commands (Makefile)

```bash
make test           # pytest suite: $(PYTHON) -m pytest tests/ -v
make test-cov       # pytest with coverage (term + html)
make lint           # ruff check eggcalc tests
make format         # black eggcalc tests
make format-check   # black --check eggcalc tests
make typecheck      # mypy eggcalc + strict consumer (tests/typing/consumer.py)
make generate-docs  # scripts/generate_mcp_docs.py (regenerate)
make docs-check     # scripts/generate_mcp_docs.py --check (drift gate)
make check          # canonical gate: lint → format-check → typecheck → docs-check → build_single --validate → pytest
make clean          # remove build/, dist/, egg-info, caches, pycache
make build          # clean + python -m build (wheel + sdist)
make package-check  # build + twine check dist/* + scripts/smoke_release_surfaces.py
make release-check  # check + package-check
make publish        # twine upload dist/* (manual; never CI)
make hooks          # pre-commit install (optional)
make install/dev/help
```

`VENV_BIN ?= .venv/bin`; `PYTHON` prefers the venv python when present.
Always use `.venv/bin/python -m pytest` — system python lacks pytest.

## CI

`.github/workflows/ci.yml` (primary gate, Ubuntu + Python 3.11):

1. `actions/checkout`, `setup-python 3.11` (pip cache on pyproject.toml).
2. `pip install -e ".[dev]"`.
3. `make check`.
4. `make package-check`.

`.github/workflows/compatibility.yml` (platform matrix; small by design —
do not add 3.12/3.13 jobs without a concrete regression):

| OS | Python |
|----|--------|
| `windows-latest` | 3.11 |
| `macos-latest` | 3.11 |
| `ubuntu-latest` | 3.14 |

Each job: install dev extras, `pytest tests/ -q`,
`build_single.py --validate` + `build_single.py` +
`python eggcalc.py "5+3"`, plus a shell-agnostic step covering units,
regex ops, multiprocessing timeouts, and a subprocess CLI invocation.
Triggers on pushes/PRs touching `eggcalc/**`, `tests/**`,
`build_single.py`, `pyproject.toml`, `Makefile`, workflows, or the smoke
script, plus a weekly Monday 06:00 UTC cron.

## Releases

Manual via Twine; GitHub Actions never publishes (see
[docs/releasing.md](../docs/releasing.md)):

1. Set the version in `eggcalc/_version.py`, update `CHANGELOG.md`,
   commit, ensure a clean tree.
2. `make release-check` (= `make check` + `make package-check`, which
   runs `twine check` and `scripts/smoke_release_surfaces.py`: package
   API, CLI, wheel-install provenance, single-file CLI/MCP from a temp
   dir, MCP stdio, config-loading sentinel checks, REPL surface).
3. Inspect `dist/`, tag `vX.Y.Z`, `make publish`
   (`twine upload dist/*`).

`docs/tool_inventory.md` is generated — never hand-edit; `make
docs-check` fails on stale output.

## Constraints

- All runtime code must live in one of the seven core modules or
  `exact/`/`mcp/` packages, or the single-file build breaks.
- Stdlib only in `eggcalc/`; keep `eggcalc` imports inside top-level
  multi-line parenthesized blocks (single-line `from eggcalc...` survives
  into the single file and fails
  `test_generated_file_no_eggcalc_import`); never put `(`/`)` in comments
  inside such blocks.
- `normalize_main` exists only in the built file (renamed by
  `build_single.py`) — never reference it in source/tests.
- Config loading stays lazy: `import eggcalc` never executes cwd-local
  `eggcalc_config.py`.
- `confusables.py` is auto-generated with a compressed payload — included
  as-is (no transform).

See also: [overview.md](overview.md) for module placement, [api.md](api.md) for public API surface.
