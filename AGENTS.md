# AGENTS.md

## What This Is

`eggcalc` — a natural language math calculator (CLI, library, MCP server). Standard library only, no external deps. Assembled by `build_single.py` into a single portable Python file. Also see `AGENTS.override.md` for session-specific overrides (takes precedence over this file) and `.skills/*.md` for per-domain agent guides (testing, implementation, MCP server, build & release, architecture review, documentation maintenance).

## Critical: Two Evaluation Paths

This is the #1 source of mistakes. The codebase has two distinct entry points:

| Function | Handles | Input format |
|----------|---------|-------------|
| `evaluate(expr)` | Direct AST evaluation | Already-normalized Python-AST-compatible math expression (`"5+3"`, `"5 + 3"`, `"2**10"`) |
| `evaluate_raw(expr)` | NL + units + math | User-facing expressions (`"five plus three"`, `"30m + 100ft"`) |
| `run(expr, NORMALIZE, PATTERNS)` | CLI-compatible normalization path | Lower-level helper for NL/unit normalization and evaluation |

`run()` normalizes NL/units first, then calls `evaluate()` internally. It is a CLI helper: it **prints** the result (or error) to stdout/stderr and returns `(result, exit_code)` — result is `None` on failure. `evaluate()` parses directly via Python AST — it **rejects** natural language and unit suffixes.

```python
run("five plus three", NORMALIZE, PATTERNS)  # → (8, 0); also prints "8" to stdout
run("30m + 100ft", NORMALIZE, PATTERNS)      # → (60.48 m, 0); prints too
evaluate("5+3")                              # → 8
evaluate("5 + 3")                            # → 8 (spaces are tolerated)
evaluate("five plus three")                  # → raises EvaluationError (invalid syntax)
```

The public API wraps these differently:
- `evaluate_raw()` / `evaluate_cached()` / `evaluate_async()` → full pipeline (NL/units → normalize → evaluate)
- `evaluate()` → direct AST evaluation (accepts valid Python math syntax with or without spaces, but rejects natural language and unit suffixes)

Note: `main()` and `print_help()` are lazy re-exports via PEP 562 from `cli.py` — they are not imported at `import eggcalc` time. `import eggcalc.cli` now loads zero `eggcalc.exact.*` implementation modules.

### Caret (`^`) semantics

The two paths interpret `^` differently:

| Path | `^` means | `xor` / `bitxor` |
|------|-----------|-------------------|
| `evaluate()` | Bitwise XOR (Python AST) | N/A (use `^` directly) |
| `evaluate_raw()` / CLI | Rewritten to `**` (exponentiation) via `_rewrite_calculator_caret()` | Use `xor`/`bitxor` for bitwise XOR |

```python
evaluate("5 ^ 3")                    # → 6 (bitwise XOR)
evaluate_raw("5 ^ 3")                # → 125 (exponentiation, rewritten to 5**3)
evaluate_raw("5 xor 3")              # → 6 (bitwise XOR)
```

### Floor division and modulo with units

Same-unit modulo returns a dimensioned remainder in the divisor unit; incompatible dimensions are rejected:

```python
evaluate_raw("5m % 2m")   # → 1 m (remainder in divisor unit)
evaluate_raw("7m // 2m")  # → 3 (dimensionless quotient)
evaluate_raw("5m % 2s")   # → EvaluationError (incompatible dimensions)
```

**When writing tests:** use `evaluate()` for direct AST evaluator behavior (e.g. `"5+3"`, `"2**10"`). Use `evaluate_raw()`, CLI subprocesses, or `run()` for natural-language and unit parsing behavior.

### Unit-aware function contracts

Every built-in function has a `UnitPolicy` (defined in `evaluator.py`, enforced in `visit_Call`). Key policies: `DIMENSIONLESS` (log, exp, gcd, factorial), `ANGLE_INPUT` (sin, cos, tan — accepts angle UnitValue with degree conversion), `ANGLE_OUTPUT` (asin, acos, atan), `PRESERVE_SINGLE` (abs, round, floor, ceil), `COMPATIBLE_REDUCER` (mean, min, max, sum), `ROOT` (sqrt), `HYPOT/ATAN2`. User-registered functions default to DIMENSIONLESS. See `architecture/evaluator.md` for full policy list.

#### Callable identity authority

Each evaluator snapshots canonical built-in callables in `_builtin_function_baseline`. `visit_Call` compares the active callable by identity — a canonical callable gets its built-in unit policy; any added or replaced callable defaults to dimensionless-only. Canonical `round()` accepts one or two positional args, or `ndigits=` keyword; omitted precision returns `int`, explicit precision returns `float`.

#### Angle algebra bounds

`Dimension.angle: bool` is a structural flag — cannot represent angle exponents other than 0 or 1. Guards reject: angle raised to exponent ≠ 0 or 1, multiplying two angle dimensions, dividing a non-angle by an angle. See `architecture/units.md` for supported patterns.

### Angle conversion

Trig functions convert angle `UnitValue` to radians before calling `math`:
```python
evaluate_raw("sin(90*deg)")  # → 1.0 (converted to π/2 radians)
evaluate_raw("sin(1*m)")     # → EvaluationError (non-angle dimension)
```

## Commands

```bash
# Testing (use venv python — system python won't have pytest)
.venv/bin/python -m pytest tests/ -v

# Single test file
.venv/bin/python -m pytest tests/test_clicalc.py -v

# Lint
ruff check eggcalc tests

# Format
black eggcalc tests

# Type check
mypy eggcalc --ignore-missing-imports
mypy --strict --follow-imports=silent --ignore-missing-imports tests/typing/consumer.py  # external consumer API surface

# All checks at once (includes generated-doc drift check)
make check

# Build single-file distribution (validates manifest first)
python3 build_single.py --validate && python3 build_single.py

# Install to ~/.local/bin/calc
python install.py --install

# Install pre-commit hooks (black, ruff, trailing-whitespace, etc.)
make hooks

# Install with dev dependencies (for new contributors)
make dev
```

CI runs `make check` (lint, format-check, typecheck, docs-check, build validation, full pytest suite) followed by `make package-check` (twine check, installed-wheel smoke, single-file smoke). See [docs/releasing.md](docs/releasing.md) for the manual PyPI release procedure.

## Constraints

- **Standard library only** — no pip packages in `eggcalc/`. Core modules (`units.py`, `evaluator.py`, `_protocol.py`, `normalize.py`, `capabilities.py`, `cli.py`) use: `argparse`, `ast`, `cmath`, `collections`, `contextvars`, `dataclasses`, `enum`, `functools`, `json`, `logging`, `math`, `multiprocessing`, `os`, `queue`, `random`, `re`, `sys`, `threading`, `traceback`, `types`, `typing`. `exact/` and `mcp/` packages may use additional stdlib modules (e.g. `tomllib`, `importlib`, `unicodedata`, `hashlib`, `shlex`, `signal`, `asyncio`, `zlib`, `base64`).
- **`build_single.py` compatibility** — all runtime code must live in one of the six core modules (`units.py`, `evaluator.py`, `_protocol.py`, `normalize.py`, `capabilities.py`, `cli.py`) or the `exact/` and `mcp/` packages. The build script concatenates them into one file. `__main__.py` is a thin entry point (not in the manifest). Adding imports outside the allowed set will break the build.
- **TypedDict over NamedTuple** — the codebase uses `TypedDict` for structured return types. TypedDict classes do NOT support `__slots__`.
- **CLI output is result-only** — no echo of input, no arrows, no extra characters. Applies to both single-expression and REPL modes.
- **Python requirement** — `>=3.11` per `pyproject.toml`. Required CI uses 3.11; optional compatibility workflow tests 3.14 and Windows.
- **`McpServerConfig` clamps `max_output_bytes` to min 1** — was previously 1000.

## Verification and Release Policy

- `make check` is canonical correctness verification (lint, format-check, typecheck, docs-check, build validation, full test suite).
- `make package-check` validates distributable surfaces (twine check, installed-wheel smoke, single-file smoke).
- `make release-check` combines correctness and package validation.
- Publication is manual through Twine/PyPI (`make publish`).
- GitHub Actions never publishes, creates releases, or modifies repository contents.
- Historical release evidence files under `docs/release_*_evidence.md` are archived records, not active policy. They do not participate in routine verification.

## Module Map

| Module | Role |
|--------|------|
| `eggcalc/_version.py` | Single source of truth for `__version__` (imported by `__init__.py`, read by `pyproject.toml` and `build_single.py`) |
| `eggcalc/normalize.py` | NL tokenization, expression normalization (no CLI dispatch) |
| `eggcalc/evaluator.py` | AST parsing, math evaluation, `evaluate()`, `EggCalcApp` |
| `eggcalc/units.py` | Unit definitions, conversions, `UnitValue` class, `UnitSpec`, `UnitExpression` |
| `eggcalc/cli.py` | CLI dispatch: argparse, REPL, text commands, help, main entry point. Text commands use lazy `importlib` loading of exact modules. |
| `eggcalc/__main__.py` | Module entry, delegates to `cli.main()` |
| `eggcalc/exact/` | Text analysis and deterministic utilities: Unicode, confusables, diffs, validation, shell parsing, IP/CIDR inspection (`network.py`), codec/radix conversion (`encoding.py`) |
| `eggcalc/mcp/` | MCP server: schemas, tools, server, McpServer, McpServerConfig, ToolRegistry, ToolExecutor, EvaluationPolicy, ConfigCandidate, RuntimeContext |
| `build_single.py` | Assembles everything into `eggcalc.py`. Uses `MODULE_MANIFEST` (tuple of `ModuleSpec` dataclasses) as the single source of truth for module ordering, dependencies, and validation. `MODULES_CALC`, `MODULES_EXACT`, `MODULES_MCP` are derived views. `validate_build_manifest()` checks for duplicates, missing files, unknown deps, cycles, and reachability. |

## Unit Conventions

- Prefixed units (`kN`, `mV`, `mA`) map to themselves in `UNIT_ALIASES`. Word forms (`kilonewton`) alias to the prefixed symbol.
- Temperature conversions use offset math (not multiplicative factors). Fahrenheit and Rankine use `scale_to_base=5/9` with correct unit-to-base offsets (F: 255.3722222222222, Ra: 0.0). Kelvin is the base unit (scale=1, offset=0). Celsius uses scale=1, offset=273.15.
- Gas constant is `r`/`R` (8.314...). Rankine is `Ra`/`rankine`/`°R`. The `r`/`R` identifiers are **not** Rankine.
- `5m ** 2` → `5 m**2` (power binds the unit; `(5m)**2` → `25.0 m**2`). `5m / 2s` → `2.5 m/s` (denominator is wrapped in parens by the preprocessor).
- British spellings (`metre`/`metres`, `litre`/`litres`) are included in aliases.
- `UnitSpec` is a frozen dataclass for declarative unit specifications (canonical name, aliases, dimension, scale/offset factors, category). `UNIT_DEFINITIONS` is a tuple of 150+ `UnitSpec` entries.
- `UnitExpression` is a frozen dataclass for structural compound units (factors as `(unit, exponent)` tuples, dimension, scale). `parse_unit_expression()` parses `"m/s"` → `UnitExpression` with bounded parsing. Duplicate factors are merged and the normalized exponent is validated against `MAX_ABS_UNIT_EXPONENT` (16) after merging.

## exact/ Module Notes

- `confusables.py` is **auto-generated** (~40KB) with a zlib-compressed base85 payload and lazy `_LazyConfusables` mapping (6565 entries). Data is decoded on first access, not at import time. Don't add code to it. Edit `scripts/generate_confusables.py` instead.
- `validate.py` enforces `MAX_INPUT_LENGTH = 100_000` on `check_brackets()` and `validate_json()`.
- `visible_repr()` check order is correct: variation selector (U+FE00-FE0F) **before** combining mark check.
- `utf8_bytes()` returns `bytes`, not an int count.
- `manifests.py` functions (`pyproject_inspect`, `requirements_inspect`, etc.) are NOT re-exported from `__init__.py`. Import directly.
- `cargo.py` `cargo_toml_inspect()` IS re-exported from `__init__.py`.
- Both modules use the shared `_Finding` TypedDict from `manifests.py` for structured findings.
- Inspection is lexical/structural, not dependency resolution. Package-manager signals are heuristic.

## TypedDict Field Conventions

When adding or modifying TypedDict classes in the `exact/` package, use these field names:

- `ConfusableInfo`: `confusable_with`, `confusable_name` (not `confusable_for`/`confusable_codepoint`)
- `ScriptInfo`: `index`, `char`, `script`, `codepoint` (not `count`, `start`, `end`)
- `detect_mixed_scripts` returns `MixedScriptsResult` with keys `mixed_scripts`, `scripts`, `positions`
- `CommonPrefixSuffix`: `common_prefix_len`, `common_suffix_len` (not `prefix`, `suffix`)
- `InspectionFinding` (used in `_Finding`): `code`, `severity`, `message`, `line`, `column`
  - Severity vocabulary: `error`, `warning`, `info`
  - Finding codes use stable identifiers: `TOML_PARSE_ERROR`, `INPUT_TOO_LONG`, `CARGO_MISSING_PACKAGE_NAME`, etc.
- `IpInspectResult`: `address`, `family`, `bytes_hex`, `numeric`, `special_use`, `ipv4_mapped` (family is `"ipv4"`/`"ipv6"`; `ipv4_mapped` is `Ipv4MappedInfo` or `None`)
- `Ipv4MappedInfo`: `address`, `numeric` (decimal magnitude as text)
- `CidrInspectResult`: `family`, `cidr`, `prefix_length`, `host_bits`, `network_address`, `netmask`, `first_address`, `last_address`, `broadcast_address` (`None` for IPv6), `address_count` (decimal text), `contains`/`contains_address` (`None` when no candidate)
- `CodecConvertResult`: `value`, `from`, `to`, `byte_length` (functional-syntax TypedDict — `from` is a keyword; params are `from_format`/`to_format`; byte length is decoded payload size)
- `RadixConvertResult`: `value`, `from_base`, `to_base`, `uppercase`, `negative`, `magnitude_decimal` (magnitude capped at `2**128 - 1`)

## MCP Server

- 77 tools across 18 categories. Tool names unified via `TOOL_SCHEMAS` in `schemas.py` and `server.py`.
- 11 tool profiles: `full`, `default`, `codegg_core_min`, `codegg_core`, `codegg_preflight`, `codegg_patch`, `codegg_config`, `codegg_unicode_security`, `codegg_shell`, `codegg_repo_audit`, `human_math`.
- Profile selection: `EGGCALC_MCP_PROFILE` env var at startup (default `full`). Per-request `profile` param overrides in `tools/list`.
- `mcp_main` is an alias for `main` in `server.py`.
- **Session lifecycle:** Clients must complete `initialize` + `notifications/initialized` handshake before calling tools. Tool requests before initialization are rejected with `-32600`.
- **Protocol version:** `SUPPORTED_PROTOCOL_VERSIONS = ("2024-11-05", "2025-11-25")`.
- **Deferred exact imports:** `tools.py` uses local imports for `eggcalc.exact` modules. Implementation modules are imported on first tool invocation, not at `import eggcalc.mcp` time. Schemas remain eagerly available for `tools/list`.
- `McpServerConfig` is a frozen dataclass. `ConfigSnapshot` fields are deeply immutable (`MappingProxyType`). See `architecture/mcp.md` for full session lifecycle, evaluator binding, timeout accounting, and config management details.

## Architecture Docs

The `architecture/` directory has module-level developer docs (40 files — every module in the codebase has a dedicated deep dive). Start with `architecture/overview.md` for the data flow, verified module map, and the full Deep Dive Index; the table below covers the highest-traffic docs.

| Doc | Covers |
|-----|--------|
| `overview.md` | System architecture, data flow, module map, Deep Dive Index for all 40 docs |
| `normalize.md` | NL tokenization pipeline |
| `evaluator.md` | AST parsing, math functions, constants, unit policies |
| `units.md` | Unit definitions, conversions, UnitValue, UnitSpec, UnitExpression |
| `cli.md` | CLI entry, options, text subcommands |
| `api.md` | Public Python API surface |
| `mcp.md` | MCP server, tool schemas, profiles, session lifecycle |
| `build.md` | build_single.py, MODULE_MANIFEST, single-file assembly |
| `exact.md` | exact/ package (Unicode, text analysis) |
| `authority_inventory.md` | Single authoritative source for every major registry/constant/contract |

Historical records: `plans/*.md` are archived roadmap/evidence documents from past releases — read-only reference, not active work.

## Config Loading Safety

`import eggcalc` does **not** execute cwd-local Python. Config loading (`eggcalc_config.py`) is handled by:

| Path | Entry Point | When |
|------|-------------|------|
| CLI (calculator eval / REPL) | `maybe_load_cli_config()` in cli.py | After mode classification, only for expression evaluation or REPL |
| CLI (informational / MCP / text commands) | *not called* | `--help`, `--version`, `--capabilities`, `--mcp`, and text commands never load config |
| API (opt-in) | `_ensure_config_loaded()` in evaluator.py | Only when `EGGCALC_LOAD_CONFIG=1` is set |
| MCP server | Handled by `McpServerConfig.from_environment()` and `main()` | `EGGCALC_NO_CONFIG=1` set in `main()` setup |

Library APIs (`evaluate_raw()`, `evaluate_cached()`, `evaluate_async()`, `evaluate_with_timeout()`) do **not** load cwd-local config by default. Set `EGGCALC_LOAD_CONFIG=1` to enable lazy config loading, or call `load_user_config()` explicitly.

**Do not** add import-time config loading back to `__init__.py`. Library import must remain side-effect-free.

**Do not** move `maybe_load_cli_config()` before mode classification in `main()`. Informational commands, MCP, and text commands must not execute cwd-local Python as a side effect.

## Common Pitfalls

1. **Wrong test API** — `evaluate("five plus three")` fails. Use `run()` or CLI for NL.
2. **Wrong python** — `.venv/bin/python` needed for pytest (system python lacks deps).
3. **Importing from wrong path** — `from eggcalc import ...` works; `from eggcalc.normalize import run` also works. But `evaluate()` from normalize won't handle NL. `import eggcalc.cli` no longer loads `eggcalc.exact.*` implementation modules — exact command handlers are loaded lazily via `importlib.import_module()` only when dispatched.
4. **build_single.py breakage** — adding imports outside the allowed set or code that can't be concatenated will break the build.
5. **confusables.py editing** — it's generated data with a compressed payload; edit `scripts/generate_confusables.py` instead.
6. **`normalize_main` alias** — created by `build_single.py` during assembly, does not exist in source `normalize.py`. Don't reference it in tests.
7. **Caret (`^`) contract mismatch** — `evaluate("5^3")` returns `6` (XOR), but `evaluate_raw("5^3")` returns `125` (exponentiation). Use `evaluate()` for XOR, `evaluate_raw()` or CLI for exponentiation. Use `xor`/`bitxor` word forms when you need XOR through the full pipeline.
8. **Floor/mod with incompatible units** — `evaluate_raw("5m % 2s")` raises `EvaluationError`. Floor division and modulo require dimensionally compatible operands.
9. **MCP handshake before tools** — `main()` creates an UNINITIALIZED session. Clients must send `initialize` then `notifications/initialized` before `tools/list` or `tools/call`. Tool requests before init return `-32600`.
10. **Sessionless API deprecation** — `handle_request()` without a session emits `DeprecationWarning` and routes through an isolated compatibility `McpServer` (does NOT mutate `_mcp_mode` or `_default_evaluator`). Use `McpServer` + `McpSession` for new code.
11. **Two evaluator paths** — `McpServer` creates its own `Evaluator` via `create_evaluator()`. It does NOT mutate the module-level `_mcp_mode` or `_default_evaluator`.
12. **`import eggcalc` does NOT load argparse, exact, or MCP modules** — CLI re-exports (`main()`, `print_help()`) are lazy via PEP 562. `eggcalc.exact` and `eggcalc.mcp` are separate packages. Eagerly loaded: `_version`, `_protocol`, `normalize`, `evaluator`, `units`, `capabilities`. Confusables data is lazy and decoded only on first access.
13. **`Dimension(angle=True)` is not dimensionless** — Angle is a structural axis, not a compatibility alias for dimensionless. `rad + 1` is rejected.
14. **`ToolRegistry.tool_names` returns `tuple[str, ...]`** — not `list[str]`. Use `list(registry.tool_names)` if you need a mutable list.
15. **exact/ results are plain dicts** — synthesis/validate/measure/etc. return `TypedDict`s, which are ordinary `dict`s at runtime. Attribute access (`result.equal`) raises `AttributeError`; use key access (`result["equal"]`). Exception: `codepoints()` items are `CodepointInfo` named tuples (`cp.idx`, not `cp.index`).
