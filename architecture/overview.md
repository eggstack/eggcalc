# eggcalc Architecture Overview

A natural language math calculator (CLI, library, MCP server) and Unicode text analysis suite. Standard library only, no external deps. Assembled by `build_single.py` into a single portable Python file.

---

## Table of Contents

- [What eggcalc Is](#what-eggcalc-is)
- [Module Map](#module-map)
- [Core Calculator Pipeline](#core-calculator-pipeline)
- [Data Flow](#data-flow)
- [Entry Points](#entry-points)
- [Module Dependencies](#module-dependencies)
- [Key Data Structures](#key-data-structures)
- [Build System](#build-system)
- [Deep Dive Index](#deep-dive-index)

---

## What eggcalc Is

eggcalc is a dual-purpose tool:

1. **Natural Language Calculator** — Accepts math expressions in plain English (`"five plus three"`) or with units (`"30m + 100ft"`) and evaluates them with full unit conversion support.
2. **Unicode Text Analysis Suite** — Deterministic text processing tools for AI safety, security auditing, and text manipulation, exposed via CLI subcommands and an MCP server.

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     Entry Points                                │
│   CLI (__main__.py → cli.main())  |  MCP Server (server)       │
└────────────────────────────────────┬────────────────────────────┘
                                     │
                    ┌────────────────┴────────────────┐
                    │                                 │
          ┌─────────▼─────────┐              ┌────────▼────────┐
          │     cli.py        │              │   mcp/tools.py  │
          │  (CLI dispatch)   │              │  (Tool Router)  │
          └─────────┬─────────┘              └────────┬────────┘
                    │                                 │
          ┌─────────▼─────────┐              ┌────────▼────────┐
          │   normalize.py   │              │   exact/ pkg    │
          │  (NL → Python)   │              │  (Text Ops)     │
          └─────────┬─────────┘              └─────────────────┘
                    │
          ┌─────────▼─────────┐
          │   evaluator.py   │
          │    (AST Eval)    │
          └─────────┬─────────┘
                    │
          ┌─────────▼─────────┐
          │     units.py      │
          │  (Conversions)    │
          └───────────────────┘
```

---

## Module Map

| Module | Role | Key Exports |
|--------|------|-------------|
| [`cli.py`](cli.md) | CLI dispatch: argparse, REPL, text commands, help, main entry point | `main()`, `print_help()` |
| [`normalize.py`](normalize.md) | Pure normalization: NL tokenization, number words, expression normalization | `run()`, `normalize_text()`, `normalize_expression()` |
| [`evaluator.py`](evaluator.md) | AST parsing, math evaluation, `EggCalcApp` | `evaluate()`, `evaluate_raw()`, `evaluate_cached()`, `evaluate_async()`, `evaluate_with_timeout()` |
| [`units.py`](units.md) | Unit definitions, conversions, `UnitValue` class | `UnitValue`, `get_conversion_factor()`, `is_unit()`, `convert_temperature()` |
| `__main__.py` | Module entry point | Delegates to `cli.main()` |
| `__init__.py` | Public API surface | Re-exports all key symbols; lazy re-exports `main`/`print_help` from `cli` via PEP 562 |
| [`exact/`](exact.md) | Text analysis: Unicode, confusables, diffs, validation, shell parsing | `inspect_text()`, `count_chars()`, `shell_split()`, `markdown_structure()` |
| [`mcp/`](mcp.md) | MCP server: schemas, tools, server | `mcp_main()`, `handle_request()`, `TOOL_SCHEMAS` |
| `build_single.py` | Assembles all modules into one file | Produces `eggcalc.py` (~394KB) |
| `install.py` | Installs to `~/.local/bin/calc` | `python install.py --install` |

---

## Core Calculator Pipeline

### Two Evaluation Paths

This is the most important architectural distinction in the codebase:

| Function | Handles | Input format |
|----------|---------|-------------|
| `evaluate(expr)` | Direct AST evaluation | Already-normalized Python-AST-compatible math expression (`"5+3"`, `"2**10"`) |
| `evaluate_raw(expr)` | NL + units + math | User-facing expressions (`"five plus three"`, `"30m + 100ft"`) |
| `run(expr, NORMALIZE, PATTERNS)` | CLI-compatible normalization path | Lower-level helper for NL/unit normalization and evaluation |

```python
run("five plus three", NORMALIZE, PATTERNS)  # → 8
run("30m + 100ft", NORMALIZE, PATTERNS)      # → 60.48 m
evaluate("5+3")                              # → 8
evaluate("five plus three")                  # → raises SyntaxError
```

### Normalization Pipeline (normalize.py)

Multi-stage pipeline that converts natural language to Python syntax:

| Stage | Description | Example |
|-------|-------------|---------|
| Unicode replacement | Normalize special characters | `→` → `to` |
| Number word replacement | Words → digits | `"five"` → `5` |
| Operator conversion | Words → symbols | `"plus"` → `+` |
| Function normalization | Aliases → canonical | `"square root"` → `sqrt` |
| Constant recognition | Physical constants | `"avogadro"` → `6.022e23` |
| Phrase stripping | Remove filler words | `"what's"` → `""` |
| Unit parsing | Number + unit detection | `"30m"` → `30*m` |
| Parenthesization | Implicit precedence | `"2 + 3 * 4"` → correct grouping |

### Safe AST Evaluation (evaluator.py)

Uses Python's `ast` module — **never `eval()`**. Provides full protection against code injection.

| Category | Functions |
|----------|-----------|
| Arithmetic | `+`, `-`, `*`, `/`, `**`, `//`, `%` |
| Trigonometric | `sin`, `cos`, `tan`, `asin`, `acos`, `atan` (complex-aware) |
| Hyperbolic | `sinh`, `cosh`, `tanh`, `asinh`, `acosh`, `atanh` |
| Logarithmic | `log`, `log10`, `log2`, `exp`, `log1p` |
| Statistical | `mean`, `median`, `mode`, `std`, `variance`, `sum`, `min`, `max` |
| Combinatorics | `factorial`, `gcd`, `lcm`, `perm`, `comb` |
| Bitwise | `bitand`, `bitor`, `bitxor`, `bitnot`, `<<`, `>>` |
| Complex Numbers | `real`, `imag`, `conj`, `phase`, `polar`, `rect` |
| Prime Functions | `isprime`, `primefactors`, `nextprime`, `prevprime` |
| Random | `random`, `randint`, `randn`, `gauss`, `seed` |
| Memory | `M`, `M+`, `M-`, `MR`, `MC` |
| Variables | `setvar`, `getvar`, `delvar`, `listvars` |
| Physical Constants | `pi`, `e`, `c`, `h`, `avogadro`, `k`, `G`, etc. |

### Unit System (units.py)

Comprehensive unit conversion with 20+ categories and proper temperature offset handling:

| Category | Base | Example Units |
|----------|------|--------------|
| Length | m | km, cm, mm, in, ft, yd, mi, ly, au, pc |
| Time | s | ms, μs, ns, min, h, d, wk, yr |
| Mass | kg | g, mg, lb, oz, ton, stone |
| Data | B | KB, MB, GB, TB (binary 1024) |
| Data Rate | bps | Kbps, Mbps, Gbps (decimal 1000) |
| Volume | L | mL, gal, qt, pt, cup, floz, tbsp, tsp |
| Pressure | Pa | kPa, MPa, GPa, bar, atm, psi |
| Energy | J | kJ, MJ, cal, kcal, Wh, kWh, BTU, eV |
| Power | W | kW, MW, GW, mW, hp |
| Force | N | kN, mN, dyne, lbf |
| Speed | m/s | km/h, mph, kn, mach |
| Temperature | K | C, F, Ra (offset-based) |
| Frequency | Hz | kHz, MHz, GHz, THz |
| Area | m² | km², cm², mm², acre, ft², in² |

---

## Data Flow

### Natural Language Evaluation

```
Input: "five plus three"
    ↓
normalize_text():    "five" → "5", "plus" → "+"
    ↓
normalize_expression(): build "5+3", add parens
    ↓
evaluator.evaluate(): AST parse → safe evaluation
    ↓
Output: 8
```

### Unit Conversion

```
Input: "30m + 100ft in meters"
    ↓
normalize(): parse units, detect "in" conversion
    ↓
evaluator: UnitValue(30, "m") + UnitValue(100, "ft")
    ↓
UnitValue arithmetic: auto-convert to shared unit
    ↓
Output: UnitValue(60.48, "m")
```

### Direct AST Evaluation

```
Input: "5 + 3"  (valid Python syntax)
    ↓
evaluator.evaluate(): AST parse → safe evaluation
    ↓
Output: 8
```

### MCP Tool Execution

```
Input: JSON-RPC tools/call with tool name + args
    ↓
server.py: route to tools.py handler
    ↓
tools.py: validate args, call exact/ function
    ↓
exact/: deterministic text analysis
    ↓
Output: JSON result
```

---

## Entry Points

| Entry Point | How | Description |
|-------------|-----|-------------|
| CLI (package) | `python -m eggcalc "expr"` | `cli.main()` → NL pipeline → evaluate |
| CLI (pip) | `calc "expr"` | Same (via pyproject.toml scripts) |
| CLI (single-file) | `python3 eggcalc.py "expr"` | Assembled single file |
| API (direct) | `evaluate("5+3")` | Direct AST evaluation |
| API (raw) | `evaluate_raw("five plus three")` | Full NL pipeline |
| API (cached) | `evaluate_cached("5+3")` | With LRU cache |
| API (async) | `await evaluate_async("5+3")` | Async wrapper |
| API (timeout) | `evaluate_with_timeout("5+3", timeout=5.0)` | Child process with timeout |
| API (webapp) | `EggCalcApp().calculate("5+3")` | Thread-safe with isolation |
| MCP server | `python eggcalc.py --mcp` | stdio JSON-RPC server |

---

## Module Dependencies

```
__main__.py
    └── cli.main()

__init__.py
    ├── evaluator, normalize, units, capabilities
    └── lazy: cli.main, cli.print_help (PEP 562 __getattr__)

cli.py  (CLI dispatch — argparse, REPL, text commands)
    ├── evaluator
    ├── normalize
    ├── exact/
    └── units

normalize.py  (pure normalization — no CLI, no exact/)
    ├── evaluator.evaluate()
    └── units.UnitValue, UNIT_ALIASES, is_unit, UNIT_CATEGORIES

evaluator.py
    └── units (UnitValue, UNIT_ALIASES, convert_temperature, etc.)

units.py
    └── (no eggcalc dependencies — leaf module)

exact/
    ├── primitives.py (foundation — no dependencies on other exact modules)
    ├── unicode_tools.py → primitives
    ├── measure.py → primitives
    ├── diff.py → primitives
    ├── validate.py → primitives
    ├── synthesis.py → all exact modules (high-level orchestrator)
    ├── confusables.py (auto-generated data only — ~176KB)
    ├── config.py, shell.py, path_tools.py, markdown.py, patch.py
    ├── transform.py, position.py, identifier.py, identifier_inspect.py
    ├── glob.py, unicode_policy.py, cargo.py, version.py
    └── inspect_prompt.py, manifests.py, llm_hygiene.py, repo_audit.py

mcp/
    ├── schemas.py (no dependencies — tool definitions)
    ├── tools.py → exact/, evaluator
    └── server.py → tools, schemas
```

**Lazy CLI re-exports.** Both `normalize.py` and `__init__.py` re-export `main` and `print_help` from `cli` using PEP 562 `__getattr__`. This preserves backward compatibility (`from eggcalc import main`) while keeping the dependency graph acyclic — `cli.py` imports `normalize`, so `normalize` cannot eagerly import `cli`.

---

## Key Data Structures

| Structure | Module | Purpose |
|-----------|--------|---------|
| `Dimension` | units.py | Immutable structural dimension (8 SI base exponents + angle flag) |
| `UnitDefinition` | units.py | Immutable unit definition (canonical, dimension, scale, offset, aliases) |
| `UnitRegistry` | units.py | Authoritative registry of all units with alias/canonical/dimension lookups |
| `_CATEGORY_DIMENSIONS` | units.py | Maps UNIT_BASE category keys to Dimension instances |
| `NUMBER_WORDS` | normalize.py | Maps number values to word variants (`"one"` → `"1"`) |
| `OPERATOR_CONVERSIONS` | normalize.py | Maps operator words to symbols (`"plus"` → `"+"`) |
| `FUNCTION_MAPPINGS` | normalize.py | Maps function name aliases (`"square root"` → `"sqrt"`) |
| `CONSTANT_WORDS` | normalize.py | Maps physical constant names (`"avogadro"` → `"na"`) |
| `NORMALIZE` / `PATTERNS` | normalize.py | Mutable config dicts rebuilt on config change |
| `UNIT_BASE` | units.py | Base units with conversion factors to canonical unit |
| `UNIT_ALIASES` | units.py | Maps all unit variants to canonical forms (~500 entries) |
| `UNIT_CATEGORIES` | units.py | Maps units to categories (length, mass, time, etc.) |
| `UNIT_CONVERSIONS` | units.py | Pre-computed pairwise conversion factors |
| `TEMPERATURE_CONVERSIONS` | units.py | Offset-based temperature conversion rules |
| `UnitValue` | units.py | Numeric value with optional units and full arithmetic |
| `Memory` | evaluator.py | Thread-safe calculator memory registers (M, M+, MR, MC) |
| `Evaluator` | evaluator.py | `ast.NodeVisitor` for safe expression evaluation |
| `EggCalcApp` | evaluator.py | Thread-safe wrapper with LRU cache and async support |
| `CommandSpec` | cli.py | TypedDict for declarative CLI text command metadata |
| `COMMANDS` | cli.py | Tuple of 9 CommandSpec entries (inspect, count, regex, etc.) |
| `TOOL_SCHEMAS` | mcp/schemas.py | MCP tool definitions with JSON schemas (77 tools) |
| `TOOL_PROFILES` | mcp/schemas.py | 11 tool profiles (full, default, codegg_*, human_math) |

---

## Build System

### build_single.py

Assembles all modules into a single `eggcalc.py` file (~394KB) for portability.

| Module Group | Modules |
|-------------|---------|
| `MODULES_CALC` | units, evaluator, normalize, cli |
| `MODULES_EXACT` | 25 exact/ submodules |
| `MODULES_MCP` | schemas, tools, server |

Strips docstrings, relative imports, `__main__` blocks, and `__future__` imports. Replaces relative imports with global assignments.

### install.py

Builds and installs `eggcalc.py` to `~/.local/bin/calc`.

```bash
python install.py --install     # Install
python install.py --update      # Update
python install.py --uninstall   # Remove
```

### Development Commands

```bash
make test          # Run tests
make lint          # ruff check
make format        # black
make typecheck     # mypy
make check         # All checks (lint + format + typecheck + docs-check + test)
make build         # Build distribution
make release-check # All checks + build + smoke tests
```

### Release Evidence Integrity

Releases 4–6 follow a strict identity-integrity contract. The evidence set
(`docs/evidence/releases-4-6-*.json`, `docs/performance/baseline-5a1bb34c.json`,
`docs/performance/candidate-<short-sha>.json`, `docs/performance/comparison.{json,md}`,
and the three `docs/release_*_evidence.md` Markdown final sections) is generated
from a single in-memory manifest by `scripts/finalize_release_evidence.py` after
the new code candidate receives a green workflow. The validator
`scripts/check_evidence_consistency.py` enforces the contract in two modes:

- `--candidate-state` — code-only commits before final closure. Rejects any
  committed final manifest, CI snapshot, inventory, candidate performance
  file, or comparison artifact.
- `--final --candidate-sha <SHA>` — after a successful workflow. Refuses to
  mark `final_decision=APPROVED` unless every invariant holds: manifest
  candidate equals workflow head equals CI snapshot candidate equals
  evidence parent; CI snapshot has `workflow_conclusion=success` with all
  eight lanes succeeding; artifact provenance includes structured fields;
  candidate performance file uses at least 15 samples and 5 warmups on a
  matching environment; baseline SHA is exactly
  `5a1bb34c9efa269ca6159217827f1742faa95d20`; the evidence commit
  modifies only the documented allowlist.

Production CI must invoke these modes explicitly. The generic
`validate_documents()` auto-detection entry point is retained for external
callers but cannot return success for contradictory final evidence. See
`plans/019-releases-4-6-final-evidence-integrity-corrective-closure.md`
for the full contract.

---

## Deep Dive Index

Each component has a dedicated architecture document. Use this index to navigate to focused reviews.

### Core Calculator

| Component | Document | What It Covers |
|-----------|----------|----------------|
| normalize.py | [normalize.md](normalize.md) | Pure normalization: NL tokenization, number words, unit parsing (no CLI) |
| evaluator.py | [evaluator.md](evaluator.md) | AST parsing, math functions, constants, EggCalcApp, memory, variables |
| units.py | [units.md](units.md) | Unit definitions, conversions, UnitValue class, temperature offset math |
| CLI | [cli.md](cli.md) | Entry points, argument parsing, REPL, text subcommands |
| Public API | [api.md](api.md) | Exported symbols, function signatures, usage patterns |

### exact/ — Unicode Text Analysis Package

| Component | Document | What It Covers |
|-----------|----------|----------------|
| exact/ (overview) | [exact.md](exact.md) | Package-level architecture, module relationships |
| primitives.py | [primitives.md](primitives.md) | UTF-8 bytes, codepoints, Unicode normalization, invisible chars |
| unicode_tools.py | [unicode_tools.md](unicode_tools.md) | Script detection, confusable identification, mixed scripts |
| confusables.py | [confusables.md](confusables.md) | Auto-generated homoglyph data (~176KB) |
| measure.py | [measure.md](measure.md) | Text metrics: line, word, character category counts |
| diff.py | [diff.md](diff.md) | String diffing: first diff, common prefix/suffix, Levenshtein distance |
| validate.py | [validate.md](validate.md) | Bracket checking, JSON/TOML validation, regex safety |
| synthesis.py | [synthesis.md](synthesis.md) | Higher-level text analysis, inspection, comparison |

### mcp/ — Model Context Protocol Server

| Component | Document | What It Covers |
|-----------|----------|----------------|
| mcp/ (overview) | [mcp.md](mcp.md) | Server architecture, tool schemas, profiles, JSON-RPC protocol |
| schemas.py | [mcp.md](mcp.md#schemaspy) | 77 tool definitions, 11 profiles, schema detail levels |
| tools.py | [mcp.md](mcp.md#toolspy) | Tool implementations, error handling, input validation |
| server.py | [mcp.md](mcp.md#serverpy) | stdio JSON-RPC, ThreadPoolExecutor, profile selection |

### Supporting Documentation

| Document | What It Covers |
|----------|----------------|
| [review_plan.md](review_plan.md) | Architecture review plan (completed 2026-05-29) |

---

## Constraints

- **Standard library only** — no pip packages in `eggcalc/`. Imports limited to: `argparse`, `os`, `sys`, `re`, `math`, `ast`, `functools`, `typing`, `stat`, `shutil`, `subprocess`, `traceback`, `cmath`, `contextvars`, `logging`, `multiprocessing`, `threading`, `random`, `queue`, `collections.abc`
- **`build_single.py` compatibility** — all runtime code must live in one of the four core modules or the `exact/` and `mcp/` packages
- **TypedDict over NamedTuple** — for structured return types
- **CLI output is result-only** — no echo of input, no arrows, no extra characters
- **Python ≥3.11** — per `pyproject.toml`

---

## Ownership Model (Release 5)

The codebase establishes explicit ownership of mutable state:

- `McpServer` owns: `McpServerConfig`, `ToolRegistry`, `ToolExecutor`, `ConfigManager`, dedicated `Evaluator`, session creation
- `McpSession` owns: lifecycle state, negotiated protocol version, client info, cancellation records
- `EggCalcApp` owns: instance-local `Evaluator`, instance-local cache
- Module-level functions (`evaluate`, `evaluate_raw`, `evaluate_cached`) use the global `_default_evaluator` and `_cache`

Multiple `McpServer` instances can coexist safely with different configs, registries, and evaluator policies. Two `McpSession` instances on one server do not share cancellation or lifecycle state.
