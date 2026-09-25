# AGENTS.md

`eggcalc` — natural-language math calculator (CLI, library, MCP server). Stdlib only, no runtime deps. `build_single.py` assembles everything into one portable `eggcalc.py`.

Start with `architecture/overview.md` (data flow, module map, Deep Dive Index for all 41 docs). Per-domain guides live in `.skills/*.md` (testing, implementation, mcp_server, build_release, architecture_review, documentation_maintenance). `.agents/skills` is a symlink to `.skills/` — edit the `.skills/` originals only. `AGENTS.override.md` takes precedence over this file when present.

## Two evaluation paths (the #1 mistake)

| Function | Handles | Notes |
|----------|---------|-------|
| `evaluate(expr)` | Already-normalized Python math only (`"5+3"`, `"2**10"`) | Rejects NL and unit suffixes; spaces tolerated |
| `evaluate_raw(expr)` / `evaluate_cached()` / `evaluate_async()` | Full pipeline: NL + units + math (`"five plus three"`, `"30m + 100ft"`) | Use for anything user-facing |
| `run(expr, NORMALIZE, PATTERNS)` | CLI helper: normalizes, then calls `evaluate()` internally | **Prints** to stdout/stderr; returns `(result, exit_code)`, `None` on failure |

```python
evaluate("5+3")                 # 8
evaluate("five plus three")     # EvaluationError — wrong API, use evaluate_raw/run/CLI
run("five plus three", NORMALIZE, PATTERNS)  # (8, 0), also prints "8"
```

**Caret differs by path:** `evaluate("5 ^ 3")` → `6` (bitwise XOR, Python AST). `evaluate_raw("5 ^ 3")` → `125` (rewritten to `**`). Use `xor`/`bitxor` word forms for XOR through the full pipeline. **Tests:** `evaluate()` for AST behavior, `evaluate_raw()`/`run()`/CLI subprocess for NL and units.

**Traces never evaluate:** `trace_normalization(expr)` (also `calc --explain "<expr>"`, `--json` supported) explains the same pipeline; `calc --commands` lists the 9 CLI text commands (distinct from the 83 MCP tools).

## Commands

```bash
.venv/bin/python -m pytest tests/ -v                          # system python lacks pytest — always use venv
.venv/bin/python -m pytest tests/test_clicalc.py -v            # single file
.venv/bin/python -m pytest tests/test_clicalc.py::test_name -v # single test
ruff check eggcalc tests
black eggcalc tests                                            # check with black --check
mypy eggcalc --ignore-missing-imports
mypy --strict --follow-imports=silent --ignore-missing-imports tests/typing/consumer.py
make check          # canonical gate, in order: lint → format-check → typecheck (+ strict consumer) → docs-check → build_single --validate → pytest
make package-check  # twine check + wheel/single-file smoke (CI runs check then package-check)
python3 build_single.py --validate && python3 build_single.py
```

## Layout and boundaries

- Core (only code loaded by `import eggcalc`): `_process.py` (subprocess mechanics only), `units.py`, `evaluator.py`, `_protocol.py`, `normalize.py`, `capabilities.py`, `cli.py`. `__main__.py` is a thin entry point, not in the build manifest. `_version.py` is the single version source.
- `exact/` — deterministic text/unicode utilities (leaf modules: `network.py`, `encoding.py`, `temporal.py` are stdlib-only, no exact/ deps). `mcp/` — server, schemas, tools. Runtime code must live in core, `exact/`, or `mcp/` or the single-file build breaks.
- `import eggcalc` is side-effect-free: `main`/`print_help` are lazy PEP 562 re-exports; `import eggcalc.cli` loads zero `exact.*` modules (handlers load via `importlib` on dispatch); `tools.py` imports `exact` lazily inside handlers. `exact/__init__.py` is fully lazy with `__all__ = list(_LAZY_IMPORTS)`.
- `architecture/authority_inventory.md` is the registry/constant authority index; `architecture/mutable_state_inventory.md` tracks process-globals. Planning follows the codegg-style hierarchy: `plans/README.md` + canonical `plans/000-long-term-specification.md` / `001-terminology-and-domain-model.md` / `002-long-term-roadmap.md` / `003-planning-process.md`, `plans/adrs/`, `plans/subsystems/` (`calculator-core`, `exact-utilities`, `mcp-server`, `cli-distribution`), `plans/implementation/<subsystem>/`, `plans/closure/<subsystem>/`, `plans/registry.md`; `plans/archive/legacy/` and `docs/release_*_evidence.md` are archived records, not policy.

## Constraints that break the build or CI

- **Stdlib only in `eggcalc/`**; keep `eggcalc` imports inside top-level multi-line parenthesized blocks (single-line `from eggcalc...` survives into the single file and fails `test_generated_file_no_eggcalc_import`); never put `(`/`)` in comments inside such blocks. `normalize_main` exists only in the built file (renamed by `build_single.py`) — never reference it in source/tests.
- **CLI output is result-only** — no echo, arrows, or decoration (REPL included).
- **Python `>=3.11`.** `make docs-check` (`scripts/generate_mcp_docs.py --check`) fails on stale generated docs; `docs/tool_inventory.md` is generated, never hand-edit. Releases are manual via Twine; GitHub Actions never publishes.
- **Config loading must stay lazy:** `import eggcalc` never executes cwd-local `eggcalc_config.py`. CLI loads it via `maybe_load_cli_config()` only for expression/REPL modes (never for `--help`/`--version`/`--capabilities`/`--mcp`/text commands — keep the call after mode classification). Library loads only with `EGGCALC_LOAD_CONFIG=1` or explicit `load_user_config()`.

## Unit and function gotchas

- `r`/`R` is the gas constant, **not** Rankine (`Ra`/`rankine`/`°R`). `5m ** 2` → `5 m**2`; `(5m)**2` → `25.0 m**2`. Same-dimension `%` returns a remainder in the divisor unit; `//` returns a dimensionless quotient; mismatched dimensions raise (`5m % 2s` fails).
- `Dimension(angle=True)` is structural, not dimensionless: `rad + 1`, angle², and angle×angle are rejected. Trig takes angle `UnitValue` (degrees converted to radians); `sin(1*m)` fails.
- Built-in `UnitPolicy` (in `evaluator.py`, enforced in `visit_Call`) applies only while the canonical callable is active — a replaced/added function defaults to dimensionless-only. Canonical `round()` takes `round(n)` / `round(n, ndigits)` / `ndigits=`; omitted precision returns `int`.

## exact/ gotchas

- `confusables.py` is generated (~6.5k entries, compressed payload, lazy decode) — edit `scripts/generate_confusables.py`, never the data file.
- Results are plain-dict TypedDicts: use `result["equal"]`, never `result.equal`. Exception: `codepoints()` items are `CodepointInfo` named tuples (`cp.idx`). `CodecConvertResult` uses functional syntax (`from` key; params are `from_format`/`to_format`).
- Single authorities: `json_extract()` in `validate.py` owns RFC 6901 traversal (`json_query` is a deprecated compat adapter, tier 2 / `full`-only); `exact/version.py` owns SemVer (`parse_version`/`compare_versions`). Field vocab and finding codes (`code`/`severity`/`message`/`line`/`column`) follow `architecture/authority_inventory.md` — verify against code, never invent names.

## MCP gotchas (details in `architecture/mcp.md`)

- Catalog authority is `TOOL_METADATA` in `schemas.py`; protocol shape is `TOOL_SCHEMAS` (no tier/tags — use `get_tool_tier()` etc.). `TOOL_HANDLERS`/`TOOL_PROFILES` are derived — never hand-edit. Default profile is `full` (`EGGCALC_MCP_PROFILE` at startup, per-request override in `tools/list`); `agent_core` is opt-in/experimental, not the recommended surface.
- One stdio server, two eras classified per-request before session logic: legacy (`2024-11-05`, `2025-11-25`) needs `initialize` + `notifications/initialized` before tools (early tools → `-32600`); modern (`2026-07-28`) is stateless via `params._meta`, bootstrap is `server/discover`, allowlist is `discover`/`tools/list`/`tools/call` only. Version→era mapping lives in `_protocol.py` (`protocol_era()`). New code uses `McpServer` + `McpSession`; bare `handle_request()` is a deprecated compat shim.
- `tools/call` on both eras returns the text envelope plus `structuredContent` (= envelope `result`) for object-rooted schemas via `_split_tool_wire_result()`; `outputSchema` describes the inner `result`, never the envelope. Use `McpServer`'s own `Evaluator` (`create_evaluator()`), never the module-global evaluator.
