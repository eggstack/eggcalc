# eggcalc Architecture Overview

A natural language math expression calculator that parses expressions in English (like "five plus three") and converts them to numeric results, with support for unit conversions. The system also includes a comprehensive suite of Unicode text analysis tools exposed via an MCP (Model Context Protocol) server.

**All tests pass.**

---

## Table of Contents

- [System Overview](#system-overview)
- [Core Calculator Modules](#core-calculator-modules)
  - [normalize.py](normalize.md) — Natural Language Processing Pipeline
  - [evaluator.py](evaluator.md) — Safe AST-Based Expression Evaluation
  - [units.py](units.md) — Unit Definitions and Conversions
  - [CLI Entry Point](cli.md) — Command-Line Interface
- [Build System](#build-system)
- [Data Flow](#data-flow)
- [Key Data Structures](#key-data-structures)
- [Module Dependencies](#module-dependencies)
- [Deep Dive Index](#deep-dive-index)

---

## System Overview

eggcalc is a dual-purpose tool:

1. **Natural Language Calculator** — Accepts math expressions in plain English ("five plus three") and evaluates them with full unit conversion support
2. **Unicode Text Analysis Suite** — A collection of deterministic text processing tools for AI safety, security auditing, and text manipulation

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLI / API                                │
│                   (eggcalc/__main__.py)                         │
└────────────────────────────────────┬────────────────────────────┘
                                     │
                    ┌────────────────┴────────────────┐
                    │                                 │
          ┌─────────▼─────────┐              ┌────────▼────────┐
          │   Normalize.py   │              │   MCP Server    │
          │  (NL → Python)   │              │  (Tool Access)  │
          └─────────┬─────────┘              └────────┬────────┘
                    │                                 │
          ┌─────────▼─────────┐              ┌────────▼────────┐
          │   Evaluator.py   │              │  exact/ Tools   │
          │    (AST Eval)    │              │   (Text Ops)    │
          └─────────┬─────────┘              └─────────────────┘
                    │
          ┌─────────▼─────────┐
          │     Units.py      │
          │ (Conversions)     │
          └───────────────────┘
```

---

## Core Calculator Modules

### [normalize.py](normalize.md) — Natural Language Processing Pipeline

**Location:** `eggcalc/normalize.py`

Converts natural language expressions into Python syntax through a multi-stage pipeline:

| Stage | Description | Example |
|-------|-------------|---------|
| Word Replacement | Number words → digits | `"five"` → `5` |
| Operator Conversion | Operator words → symbols | `"plus"` → `+` |
| Function Normalization | Function aliases → canonical | `"square root"` → `sqrt` |
| Constant Recognition | Physical constants | `"avogadro"` → `6.022e23` |
| Phrase Stripping | Remove filler | `"what's"` → `""` |
| Unit Parsing | Number + unit detection | `"30m"` → `30*m` |

Unit parsing is spacing-tolerant, including compound units with spaces around `/` and unit conversions like `30 km / h in mph` or `5 in in cm`.

**Key exports:** `run()`, `normalize()`, `normalize_expression()`, `NORMALIZE`, `PATTERNS`

**Detailed documentation:** [normalize.md](normalize.md)

---

### [evaluator.py](evaluator.md) — Safe AST-Based Expression Evaluation

**Location:** `eggcalc/evaluator.py`

Safely evaluates mathematical expressions using Python's AST module — **not `eval()`**. Provides full protection against code injection.

| Category | Functions/Features |
|----------|-------------------|
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

**Key exports:** `evaluate()`, `evaluate_raw()`, `evaluate_cached()`, `evaluate_async()`, `evaluate_with_timeout()`, `EggCalcApp`, `Evaluator`

**Detailed documentation:** [evaluator.md](evaluator.md)

---

### [units.py](units.md) — Unit Definitions and Conversions

**Location:** `eggcalc/units.py`

Comprehensive unit conversion system with 20+ unit categories and proper temperature offset handling.

| Category | Base Unit | Example Units |
|----------|-----------|--------------|
| Length | m | km, cm, mm, in, ft, yd, mi, ly, au, pc |
| Time | s | ms, us, ns, min, h, d, wk, yr |
| Mass | kg | g, mg, lb, oz, ton, stone |
| Data | B (bytes) | KB, MB, GB, TB (binary 1024) |
| Data Rate | bps | Kbps, Mbps, Gbps (decimal 1000) |
| Volume | L | mL, gal, qt, pt, cup, floz, tbsp, tsp |
| Pressure | Pa | kPa, MPa, GPa, bar, atm, psi |
| Energy | J | kJ, MJ, cal, kcal, Wh, kWh, BTU, eV |
| Power | W | kW, MW, GW, mW, hp |
| Force | N | kN, mN, dyne, lbf |
| Speed | m/s | km/h, mph, kn, mach |
| Temperature | K | C, F, R (offset-based) |
| Frequency | Hz | kHz, MHz, GHz, THz |
| Area | m2 | km2, cm2, mm2, acre, ft2, in2 |

**Key exports:** `UnitValue`, `get_conversion_factor()`, `is_unit()`, `get_unit_category()`, `are_units_compatible()`, `convert_temperature()`

**Detailed documentation:** [units.md](units.md)

---

### [CLI Entry Point](cli.md) — Command-Line Interface

**Location:** `eggcalc/__main__.py`

Entry point for `python -m eggcalc`. Delegates to `normalize.main()` which handles:
- Single expression mode: `calc "5 + 3"`
- Interactive REPL: `calc -i`
- Text tools: `calc inspect <text>`, `calc count <text>`, etc.
- MCP server mode: `calc --mcp`

**Detailed documentation:** [cli.md](cli.md)

---

## Build System

### [build_single.py](../build_single.py)

Combines all modules into a single `eggcalc.py` file (~394KB) for portability.

**Module Groups:**
- `MODULES_CALC`: units, evaluator, normalize (core calculator)
- `MODULES_EXACT`: 22 exact/ submodules (text analysis tools)
- `MODULES_MCP`: schemas, tools, server (MCP protocol)

**Output:** Self-contained executable with CLI and MCP modes.

### [install.py](../install.py)

Builds and installs `eggcalc.py` to `~/.local/bin/calc`.

```bash
python install.py --install     # Install
python install.py --update      # Update
python install.py --uninstall   # Remove
```

---

## Data Flow

### Natural Language Evaluation (`run()`)

```
Input: "five plus three"
    ↓
normalize(): Remove filler, replace words with symbols
    ↓
normalize_expression(): Build "5+3" Python syntax
    ↓
evaluator.evaluate(): AST parse → safe evaluation
    ↓
Output: 8
```

### Unit Conversion (`run()`)

```
Input: "30m + 100ft in meters"
    ↓
normalize(): Parse units, recognize "in" conversion
    ↓
evaluator: UnitValue(30, "m") + UnitValue(100, "ft")
    ↓
UnitValue.convert_to(): Apply conversion factor
    ↓
Output: UnitValue(60.48, "m")
```

Spacing around unit symbols is normalized here as well, so `30 km / h in mph` and `2 ft / s in m / s` follow the same pipeline.

### Direct AST Evaluation (`evaluate()`)

```
Input: "5 + 3" (valid Python syntax)
    ↓
evaluator.evaluate(): AST parse → safe evaluation
    ↓
Output: 8
```

---

## Key Data Structures

| Structure | Module | Purpose |
|-----------|--------|---------|
| `NUMBER_WORDS` | normalize.py | Maps number values to word variants ("one" → "1") |
| `OPERATOR_CONVERSIONS` | normalize.py | Maps operator words to symbols ("plus" → "+") |
| `FUNCTION_MAPPINGS` | normalize.py | Maps function name aliases ("square root" → "sqrt") |
| `CONSTANT_WORDS` | normalize.py | Maps physical constant names ("avogadro" → "na") |
| `UNIT_BASE` | units.py | Base units with conversion factors to canonical unit |
| `UNIT_CONVERSIONS` | units.py | Pre-computed pairwise conversion factors |
| `UNIT_ALIASES` | units.py | Maps all unit variants to canonical forms |
| `UNIT_CATEGORIES` | units.py | Maps units to categories (length, mass, time, etc.) |
| `UnitValue` | units.py | Numeric value with optional units and arithmetic |
| `Memory` | evaluator.py | Calculator memory registers (M, M+, MR, MC) |
| `Evaluator` | evaluator.py | AST visitor for safe expression evaluation |
| `TOOL_SCHEMAS` | mcp/schemas.py | MCP tool definitions with JSON schemas |

---

## Module Dependencies

```
eggcalc/__main__.py
    └── normalize.main()

eggcalc/normalize.py
    ├── evaluator.evaluate()
    ├── units.UnitValue, UNIT_ALIASES, is_unit
    └── exact/ (inspect_text, count_chars, regex_test, etc.)

eggcalc/evaluator.py
    └── units (UnitValue, UNIT_ALIASES, convert_temperature)

eggcalc/units.py
    (no dependencies on other eggcalc modules)

eggcalc/exact/
    ├── primitives.py (foundation - no dependencies)
    ├── unicode_tools.py → primitives
    ├── measure.py → primitives
    ├── diff.py → primitives
    ├── validate.py → primitives
    ├── synthesis.py → all exact modules
    ├── confusables.py (data only - auto-generated)
    ├── config.py
    ├── shell.py
    ├── path_tools.py
    ├── markdown.py
    ├── patch.py
    ├── transform.py
    ├── position.py
    ├── identifier.py
    ├── identifier_inspect.py
    ├── glob.py
    ├── unicode_policy.py
    ├── cargo.py
    ├── version.py
    └── inspect_prompt.py

eggcalc/mcp/
    ├── schemas.py (no dependencies)
    ├── tools.py → exact/, evaluator
    └── server.py → tools, schemas
```

---

## Deep Dive Index

Each module has a dedicated architecture document for focused review:

### Core Calculator Modules

| Module | Document | Purpose |
|--------|----------|---------|
| normalize.py | [normalize.md](normalize.md) | NL → Python expression pipeline |
| evaluator.py | [evaluator.md](evaluator.md) | Safe AST-based evaluation |
| units.py | [units.md](units.md) | Unit definitions & conversions |
| CLI | [cli.md](cli.md) | Command-line interface |

### exact/ — Unicode Text Primitives

The `exact/` package provides low-level deterministic text analysis tools.

| Module | Document | Purpose |
|--------|----------|---------|
| primitives.py | [primitives.md](primitives.md) | UTF-8, codepoints, normalization, invisibles |
| unicode_tools.py | [unicode_tools.md](unicode_tools.md) | Script detection, confusables |
| measure.py | [measure.md](measure.md) | Text metrics (words, lines, categories) |
| diff.py | [diff.md](diff.md) | String diffing algorithms |
| validate.py | [validate.md](validate.md) | JSON/bracket/regex validation |
| synthesis.py | [synthesis.md](synthesis.md) | Higher-level text analysis |
| confusables.py | [confusables.md](confusables.md) | Homoglyph identification (auto-generated data) |
| cargo.py | — | Cargo.toml inspection |
| version.py | — | Semver/cargo constraint checking |
| inspect_prompt.py | — | Prompt injection detection |
| exact (overview) | [exact.md](exact.md) | Package-level overview |

### mcp/ — Model Context Protocol Server

| Module | Document | Purpose |
|--------|----------|---------|
| schemas.py | [mcp.md](mcp.md#schemaspy) | Tool JSON schemas |
| tools.py | [mcp.md](mcp.md#toolspy) | Tool implementations |
| server.py | [mcp.md](mcp.md#serverpy) | stdio-based JSON-RPC server |

### Supporting Documentation

| Document | Purpose |
|----------|---------|
| [api.md](api.md) | Public API reference |
| [review_plan.md](review_plan.md) | Architecture review orchestration |

---

## API Quick Reference

### CLI Usage

```bash
# Natural language math
python -m eggcalc "five plus three"           # → 8
python -m eggcalc "thirty meters plus 100 feet" # → 60.48 m

# Unit conversion
python -m eggcalc "100F to C"                  # → 37.777... C
python -m eggcalc "1km in miles"               # → 0.621... mi

# Interactive REPL
python -m eggcalc -i

# Text inspection
python -m eggcalc inspect "paypal"             # Check for confusables
python -m eggcalc count "hello world"
```

### Library Usage

```python
from eggcalc import evaluate, run, UnitValue, NORMALIZE, PATTERNS

# Direct math (valid Python syntax)
evaluate("5 + 3")  # → 8

# Natural language (requires run())
run("five plus three", NORMALIZE, PATTERNS)  # → 8

# Unit conversion
run("30m + 100ft", NORMALIZE, PATTERNS)  # → UnitValue(60.48, "m")
```

### MCP Server

```bash
python eggcalc.py --mcp
```
