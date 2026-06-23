# AGENTS.md

## What This Is

`eggcalc` — a natural language math calculator (CLI, library, MCP server). Standard library only, no external deps. Assembled by `build_single.py` into a single portable Python file.

## Critical: Two Evaluation Paths

This is the #1 source of mistakes. The codebase has two distinct entry points:

| Function | Handles | Input Format |
|----------|---------|-------------|
| `run(expr, NORMALIZE, PATTERNS)` | NL + units + math | `"five plus three"`, `"30m + 100ft"` |
| `evaluate(expr)` | Pure math only | `"5+3"`, `"2**10"` — no spaces, no NL, no units |

`run()` normalizes NL/units first, then calls `evaluate()` internally. `evaluate()` parses directly via Python AST — it **rejects** natural language and unit suffixes.

```python
run("five plus three", NORMALIZE, PATTERNS)  # → 8
run("30m + 100ft", NORMALIZE, PATTERNS)      # → 60.48 m
evaluate("5+3")                              # → 8
evaluate("five plus three")                  # → raises SyntaxError
```

The public API wraps these differently:
- `evaluate_raw()` / `evaluate_cached()` / `evaluate_async()` → full pipeline (like `run()`)
- `evaluate()` → direct AST only

**When writing tests:** use `evaluate()` for pure math (`5+3`), use CLI or `run()` for NL/units.

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

# All checks at once
make check

# Build single-file distribution
python build_single.py

# Install to ~/.local/bin/calc
python install.py --install
```

## Constraints

- **Standard library only** — no pip packages in `eggcalc/`. Imports limited to: `argparse`, `os`, `sys`, `re`, `math`, `ast`, `functools`, `typing`, `stat`, `shutil`, `subprocess`, `traceback`, `cmath`, `contextvars`, `logging`, `multiprocessing`, `threading`, `random`, `queue`, `collections.abc`
- **`build_single.py` compatibility** — all runtime code must live in one of the four core modules (`normalize.py`, `evaluator.py`, `units.py`, `__main__.py`) or the `exact/` and `mcp/` packages. The build script concatenates them into one file.
- **TypedDict over NamedTuple** — the codebase uses `TypedDict` for structured return types. TypedDict classes do NOT support `__slots__`.
- **CLI output is result-only** — no echo of input, no arrows, no extra characters. Applies to both single-expression and REPL modes.

## Module Map

| Module | Lines | Role |
|--------|-------|------|
| `eggcalc/normalize.py` | ~3360 | NL tokenization, number words, expression normalization, CLI main |
| `eggcalc/evaluator.py` | ~2765 | AST parsing, math evaluation, `evaluate()`, `EggCalcApp` |
| `eggcalc/units.py` | ~2088 | Unit definitions, conversions, `UnitValue` class |
| `eggcalc/__main__.py` | 19 | Module entry, delegates to `normalize.main()` |
| `eggcalc/exact/` | — | Text analysis: Unicode, confusables, diffs, validation, shell parsing |
| `eggcalc/mcp/` | — | MCP server for AI agent tool access |
| `build_single.py` | ~842 | Assembles everything into `eggcalc.py` |

## Unit Conventions

- Prefixed units (`kN`, `mV`, `mA`) map to themselves in `UNIT_ALIASES`. Word forms (`kilonewton`) alias to the prefixed symbol.
- Temperature conversions use offset math (not multiplicative factors).
- Gas constant is `r`/`R` (8.314...). Rankine is `Ra`/`rankine`/`°R`. The `r`/`R` identifiers are **not** Rankine.
- `5m ** 2` → `25.0 m**2` (power binds the unit). `5m / 2s` → `25.0 m/s` (denominator is wrapped in parens by the preprocessor).
- British spellings (`metre`/`metres`, `litre`/`litres`) are included in aliases.

## exact/ Module Notes

- `confusables.py` is **auto-generated data only** (~176KB). Don't add code to it.
- `validate.py` enforces `MAX_INPUT_LENGTH = 100_000` on `check_brackets()` and `validate_json()`.
- `visible_repr()` check order is correct: variation selector (U+FE00-FE0F) **before** combining mark check.
- `utf8_bytes()` returns `bytes`, not an int count.

## MCP Server

- Tool names unified via `TOOL_SCHEMAS` in `schemas.py` and `server.py`.
- `MAX_TEXT_LENGTH` enforced on `math_eval`.
- Case-insensitive tool matching with suggestions for unknown tools.
- `mcp_main` is defined in `server.py:234`.

## Architecture Docs

The `architecture/` directory has module-level developer docs. Start with `architecture/overview.md` for data flow and module dependencies.

## Common Pitfalls

1. **Wrong test API** — `evaluate("five plus three")` fails. Use `run()` or CLI for NL.
2. **Wrong python** — `.venv/bin/python` needed for pytest (system python lacks deps).
3. **Importing from wrong path** — `from eggcalc import ...` works; `from eggcalc.normalize import run` also works. But `evaluate()` from normalize won't handle NL.
4. **build_single.py breakage** — adding imports outside the allowed set or code that can't be concatenated will break the build.
5. **confusables.py editing** — it's generated data; edit `scripts/generate_confusables.py` instead.
