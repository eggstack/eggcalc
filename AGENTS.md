# AGENTS.md

## What This Is

`eggcalc` — a natural language math calculator (CLI, library, MCP server). Standard library only, no external deps. Assembled by `build_single.py` into a single portable Python file. Also see `AGENTS.override.md` for session-specific overrides (takes precedence over this file).

## Critical: Two Evaluation Paths

This is the #1 source of mistakes. The codebase has two distinct entry points:

| Function | Handles | Input format |
|----------|---------|-------------|
| `evaluate(expr)` | Direct AST evaluation | Already-normalized Python-AST-compatible math expression (`"5+3"`, `"5 + 3"`, `"2**10"`) |
| `evaluate_raw(expr)` | NL + units + math | User-facing expressions (`"five plus three"`, `"30m + 100ft"`) |
| `run(expr, NORMALIZE, PATTERNS)` | CLI-compatible normalization path | Lower-level helper for NL/unit normalization and evaluation |

`run()` normalizes NL/units first, then calls `evaluate()` internally. `evaluate()` parses directly via Python AST — it **rejects** natural language and unit suffixes.

```python
run("five plus three", NORMALIZE, PATTERNS)  # → 8
run("30m + 100ft", NORMALIZE, PATTERNS)      # → 60.48 m
evaluate("5+3")                              # → 8
evaluate("5 + 3")                            # → 8 (spaces are tolerated)
evaluate("five plus three")                  # → raises SyntaxError
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

Every built-in function has an explicit `UnitPolicy` (defined in `evaluator.py`). The centralized dispatcher in `visit_Call` enforces these policies:

- **DIMENSIONLESS**: Reject `UnitValue` with unit (`log`, `exp`, `gcd`, `factorial`, etc.)
- **ANGLE_INPUT**: Accept dimensionless (radians) or angle `UnitValue` with degree conversion (`sin`, `cos`, `tan`)
- **ANGLE_OUTPUT**: Accept dimensionless, reject dimensional (`asin`, `acos`, `atan`)
- **PRESERVE_SINGLE**: Single arg, preserve unit on result (`abs`, `round`, `floor`, `ceil`, `trunc`)
- **SIGN_OUTPUT**: Unwrap magnitude, return dimensionless scalar (`sign`)
- **COMPATIBLE_REDUCER**: All args dimensionless or all compatible units (`mean`, `min`, `max`, `median`, `std`, `sum`)
- **VARIANCE_SQUARED**: Like COMPATIBLE_REDUCER but result has squared units (`variance`, `var`, `variance_sample`, `vars`, `var_sample`). Rejects affine temperature variance.
- **ROOT**: Dimensionless or even-exponent unit; halve exponents (`sqrt`)
- **HYPOT/ATAN2**: Both dimensionless or both compatible units

User-registered functions default to DIMENSIONLESS. Custom callables are rejected by `evaluate_with_timeout()`.

#### Callable identity authority

Each evaluator maintains a `_builtin_function_baseline` snapshot of canonical built-in callables after instance-specific binding. `visit_Call` compares the active callable by identity against this baseline. A canonical callable receives its built-in unit policy; any added or replaced callable defaults to dimensionless-only. This prevents a user replacing `sin` with a custom function from inheriting the built-in `ANGLE_INPUT` policy.

Identity is established before all built-in-name-specific argument handling:
only canonical `temp`, `convert`, variable-management functions, and
`round` receive their special argument contracts. Canonical `round()` accepts
one or two positional arguments, or one `ndigits=` keyword with one value
argument; omitted precision preserves Python's integer return type, explicit
precision returns a float, and unit-bearing `ndigits` is rejected. Timeout
state checks reject added, overridden, and deleted callable names in sorted
order before a worker is spawned.

#### Angle algebra bounds

`Dimension.angle: bool` is a structural flag that cannot represent angle exponents other than 0 or 1. Bounded guards reject:
- angle-bearing dimension raised to any exponent other than 0 or 1
- multiplying two angle-bearing dimensions (`deg*rad`, `deg**2`)
- dividing a non-angle dimension by an angle-bearing dimension (`1/deg`)

Supported: `deg**0` (dimensionless), `deg**1` (angle), `deg/rad` (dimensionless), `(deg/s)*s` (angle).

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
| `eggcalc/exact/` | Text analysis: Unicode, confusables, diffs, validation, shell parsing |
| `eggcalc/mcp/` | MCP server: schemas, tools, server, McpServer, McpServerConfig, ToolRegistry, ToolExecutor, EvaluationPolicy, ConfigCandidate, RuntimeContext |
| `build_single.py` | Assembles everything into `eggcalc.py`. Uses `MODULE_MANIFEST` (tuple of `ModuleSpec` dataclasses) as the single source of truth for module ordering, dependencies, and validation. `MODULES_CALC`, `MODULES_EXACT`, `MODULES_MCP` are derived views. `validate_build_manifest()` checks for duplicates, missing files, unknown deps, cycles, and reachability. |

## Unit Conventions

- Prefixed units (`kN`, `mV`, `mA`) map to themselves in `UNIT_ALIASES`. Word forms (`kilonewton`) alias to the prefixed symbol.
- Temperature conversions use offset math (not multiplicative factors). Fahrenheit and Rankine use `scale_to_base=5/9` with correct unit-to-base offsets (F: 255.3722222222222, Ra: 0.0). Kelvin is the base unit (scale=1, offset=0). Celsius uses scale=1, offset=273.15.
- Gas constant is `r`/`R` (8.314...). Rankine is `Ra`/`rankine`/`°R`. The `r`/`R` identifiers are **not** Rankine.
- `5m ** 2` → `25.0 m**2` (power binds the unit). `5m / 2s` → `25.0 m/s` (denominator is wrapped in parens by the preprocessor).
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

## MCP Server

- 77 tools across 18 categories (math, text, json, validation, regex, list, path, identifier, shell, markdown, config, version, toml, cargo, unicode, manifest, patch, repo).
- Tool names unified via `TOOL_SCHEMAS` in `schemas.py` and `server.py`.
- `MAX_TEXT_LENGTH` enforced on `math_eval`.
- `MAX_PAIRWISE_ITEMS` (1,000) caps O(N²) work in `identifier_inspect`, `identifier_table_inspect`, and `list_compare` (near-match mode).
- Case-insensitive tool matching with suggestions for unknown tools.
- `mcp_main` is defined in `server.py:2936`.
- 11 tool profiles: `full`, `default`, `codegg_core_min`, `codegg_core`, `codegg_preflight`, `codegg_patch`, `codegg_config`, `codegg_unicode_security`, `codegg_shell`, `codegg_repo_audit`, `human_math`.
- Profile selection: `EGGCALC_MCP_PROFILE` env var at startup (default `full`). Tools outside active profile rejected at `tools/call` with JSON-RPC `-32602`. Per-request `profile` param overrides in `tools/list`.
- `full` profile uses `llm_exposure != "hidden"` filter (not `TOOL_PROFILES["full"]`). `EGGCALC_MCP_SCHEMA_DETAIL` controls schema verbosity (compact/normal/full).
- `close_compatibility_server()` is exported from `eggcalc.mcp`.
- `McpServer.diagnostic()` now counts only live (non-closed) sessions.
- Resource audit: `docs/mcp_resource_limits.md` covers all 77 tools.
- **Deferred exact imports:** `tools.py` uses local imports for `eggcalc.exact` modules. Implementation modules are imported on first tool invocation, not at `import eggcalc.mcp` time. Schemas remain eagerly available for `tools/list`.
- **Session lifecycle:** `McpServer` creates one `McpSession(initial_state=UNINITIALIZED)` per connection via `server.create_session()`. The `McpSession` class manages protocol state (UNINITIALIZED → INITIALIZING → READY → CLOSED). `McpSessionState` enum tracks the lifecycle. Clients must complete `initialize` + `notifications/initialized` handshake before calling tools. Tool requests before initialization are rejected with `-32600`. Server close transitions all owned sessions to `CLOSED`. `McpSession` has `_owner_id` binding and `_closed` flag; `_check_ready_for_dispatch` uses `.name` comparison for `importlib.reload` safety. `McpSession.close()` calls `_owner_remove_callback(self)` to proactively remove from server's `_sessions` set.
- **Protocol version:** `SUPPORTED_PROTOCOL_VERSIONS = ("2024-11-05", "2025-11-25")`. Version negotiation uses `server.config.supported_protocol_versions` when available.
- **`handle_request(request, session=None)`**: When `session` is `None`, routes through an isolated compatibility `McpServer` for backward compatibility. **Deprecated** — emits `DeprecationWarning`. Callers should pass an explicit `McpSession` instance.
- **`main()`**: Creates one `McpServer` per connection, which owns a `McpSession` for lifecycle management.
- **Centralized error helpers:** `_jsonrpc_error()`, `_parse_error()`, `_method_not_found()`, `_invalid_params()`, `_internal_error()` in server.py.
- **`ConfigSnapshot`**: Deeply immutable — fields are `MappingProxyType`, has `to_dict()` method. `policy` field is `EvaluationPolicy | str` (backward compatible).
- **`ConfigManager.replace()`**: Validates generation is strictly increasing; stale/decreasing generations raise `ValueError`. `replace_validated()` uses manager-assigned monotonic generations and validates input through `parse_config_snapshot()`.
- **`ConfigError` / `parse_config_snapshot()`**: Configuration parsing with type/semantics validation before snapshot construction. Validates constant types (int/float/str/bool), function callability, unit names, and policy values. `parse_config_snapshot()` rejects non-empty custom units. `parse_config_candidate()` delegates to `parse_config_snapshot()` for validation.
- **`McpServer.activate_snapshot()`**: Atomically pushes snapshot constants and functions to the server's evaluator. On failure, rolls back to prior evaluator state.
- **Schema validation:** `SUPPORTED_SCHEMA_KEYWORDS` frozenset defines which JSON Schema keywords the validator supports. `tests/test_mcp_schema_lint.py` walks all `TOOL_SCHEMAS` and fails on unsupported keywords.
- **Session-aware test helpers:** `ready_session()` and `session_request(session, method, params, request_id)` in `tests/test_mcp_server.py`.
- `McpServerConfig` frozen dataclass for immutable server configuration (profile, limits, timeouts, protocol versions)
- `McpServer` class owns config, `ToolRegistry`, `ToolExecutor`, evaluator instance, `ConfigManager`, and session creation
- `ToolRegistry` wraps tool handlers, schemas, metadata, and profiles with lookup methods; internal dicts are `MappingProxyType` via `freeze_owned()` for recursive immutability, nested schemas use `MappingProxyType`, profiles use tuples, `tool_names` returns `tuple[str, ...]`, `get_schema()` returns deep copy via `thaw_owned()`; has `is_tool_visible(name, profile)` method. Validates: duplicate handlers, unsupported `llm_exposure` values, empty profile names.
- `freeze_owned()` and `thaw_owned()` utility functions for recursive immutability conversion of nested containers (`Mapping`→`MappingProxyType`, `list`→`tuple`, `set`→`frozenset` and back). `thaw_owned()` recursively converts both frozen and mutable containers to mutable equivalents.
- `EvaluationPolicy` enum (`DEFAULT`, `STRICT`, `PERMISSIVE`) for server evaluation configuration. `PERMISSIVE` is a compatibility alias for `DEFAULT`; `_effective_policy()` normalizes them.
- `ConfigCandidate` frozen dataclass for validated configuration before snapshot construction. `RuntimeContext` frozen dataclass pairing a `ConfigSnapshot` with its `Evaluator` instance.
- `ToolExecutor` owns thread pool, validation, timeout, cancellation, and cleanup; has closed-state sealing preventing pool recreation after `close()`; has three counters: `_total_inflight`, `_queued_count`, `_active_count` with worker-wrapper lifecycle transitions.
- **Evaluator binding:** `ToolExecutor` stores the server evaluator and sets `_server_evaluator` ContextVar via `_run_handler_in_thread()`. `evaluate_raw()` and `evaluate_with_timeout()` check this ContextVar, so `math_eval` uses the server's evaluator policy (allow_random, allow_side_effects) instead of the global default. `Evaluator` has instance-owned `_instance_random` generator via `random_seed` parameter.
- **Timeout accounting:** `call_tool()` uses `Future.add_done_callback()` to release `_total_inflight` only when the future truly completes (not on caller timeout). Timed-out-but-still-running handlers continue consuming capacity until they finish.
- `ConfigSnapshot` / `ConfigManager` for atomic configuration replacement with generation tracking
- `create_evaluator()` factory for isolated evaluator instances (avoids mutating global `_mcp_mode`)
- `McpServer.handle_request(request, session)` replaces module-level `handle_request()` for new code
- Sessionless `handle_request(session=None)` emits `DeprecationWarning` and routes through an isolated compatibility `McpServer` (does NOT mutate `_mcp_mode` or `_default_evaluator`).

## Architecture Docs

The `architecture/` directory has module-level developer docs. Start with `architecture/overview.md` for data flow and module dependencies.

| Doc | Covers |
|-----|--------|
| `overview.md` | System architecture, data flow, module map |
| `normalize.md` | NL tokenization pipeline |
| `evaluator.md` | AST parsing, math functions, constants |
| `units.md` | Unit definitions, conversions, UnitValue, UnitSpec, UnitExpression |
| `cli.md` | CLI entry, options, text subcommands |
| `api.md` | Public Python API surface |
| `capabilities.md` | Runtime capability detection, RuntimeCapabilities |
| `exact.md` | exact/ package (Unicode, text analysis) |
| `mcp.md` | MCP server, tool schemas, profiles |
| `build.md` | build_single.py, MODULE_MANIFEST, single-file assembly |
| `primitives.md` | UTF-8, codepoints, invisible chars |
| `unicode_tools.md` | Script detection, confusables |
| `measure.md` | Text metrics (lines, words, chars) |
| `diff.md` | String diffing algorithms |
| `validate.md` | Bracket/JSON/regex validation |
| `synthesis.md` | Higher-level text analysis |
| `confusables.md` | Auto-generated homoglyph data |
| `authority_inventory.md` | Single authoritative source for every major registry/constant/contract |
| `mutable_state_inventory.md` | Inventory of all mutable process-global state |

## Config Loading Safety

`import eggcalc` does **not** execute cwd-local Python. Config loading (`eggcalc_config.py`) is handled by:

| Path | Entry Point | When |
|------|-------------|------|
| CLI (calculator eval / REPL) | `maybe_load_cli_config()` in cli.py | After mode classification, only for expression evaluation or REPL |
| CLI (informational / MCP / text commands) | *not called* | `--help`, `--version`, `--capabilities`, `--mcp`, and text commands never load config |
| API (opt-in) | `_ensure_config_loaded()` in evaluator.py | Only when `EGGCALC_LOAD_CONFIG=1` is set |
| MCP server | Handled by `McpServerConfig.from_environment()` and `main()` | `EGGCALC_NO_CONFIG=1` set in `main()` setup |

Library APIs (`evaluate_raw()`, `evaluate_cached()`, `evaluate_async()`, `evaluate_with_timeout()`) do **not** load cwd-local config by default. Set `EGGCALC_LOAD_CONFIG=1` to enable lazy config loading, or call `load_user_config()` explicitly.

The `load_user_config()` function checks two guards: `_mcp_mode` flag and `EGGCALC_NO_CONFIG` env var. Both early-return paths set `_config_loaded = True` to prevent re-entry.

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
12. **`import eggcalc` does NOT load argparse, exact, or MCP modules** — CLI re-exports (`main()`, `print_help()`) are lazy via PEP 562. `eggcalc.exact` and `eggcalc.mcp` are separate packages. Only `normalize`, `evaluator`, and `units` are loaded eagerly. Confusables data is lazy and decoded only on first access.
13. **`Dimension(angle=True)` is not dimensionless** — Angle is a structural axis, not a compatibility alias for dimensionless. `rad + 1` is rejected.
14. **`ToolRegistry.tool_names` returns `tuple[str, ...]`** — not `list[str]`. Use `list(registry.tool_names)` if you need a mutable list.
