# eggcalc Architecture Overview

A natural language math calculator (CLI, library, MCP server) and Unicode text analysis suite. Standard library only, no external deps. Assembled by `build_single.py` into a single portable Python file.

---

## Table of Contents

- [What eggcalc Is](#what-eggcalc-is)
- [Architecture Diagram](#architecture-diagram)
- [Subsystem Map](#subsystem-map)
- [Core Calculator Pipeline](#core-calculator-pipeline)
  - [Two Evaluation Paths](#two-evaluation-paths)
  - [Caret Semantics](#caret-semantics)
  - [Normalization Pipeline](#normalization-pipeline)
  - [Safe AST Evaluation](#safe-ast-evaluation)
  - [Unit System](#unit-system)
- [exact/ Text Analysis Package](#exact-text-analysis-package)
  - [Module Dependency Graph](#module-dependency-graph)
  - [Capability Categories](#capability-categories)
- [MCP Server](#mcp-server)
  - [Tool Categories](#tool-categories-77-tools)
  - [Profile System](#profile-system-11-profiles)
  - [Session Lifecycle](#session-lifecycle)
- [Data Flow](#data-flow)
- [Entry Points](#entry-points)
- [Module Dependencies](#module-dependencies)
- [Key Data Structures](#key-data-structures)
- [Build System](#build-system)
- [Constraints](#constraints)
- [Ownership Model](#ownership-model)
- [Deep Dive Index](#deep-dive-index)

---

## What eggcalc Is

eggcalc is a dual-purpose tool:

1. **Natural Language Calculator** — Accepts math expressions in plain English (`"five plus three"`) or with units (`"30m + 100ft"`) and evaluates them with full unit conversion support.
2. **Unicode Text Analysis Suite** — Deterministic text processing tools for AI safety, security auditing, and text manipulation, exposed via CLI subcommands and an MCP server.

### Key Properties

- **Standard library only** — zero external dependencies in production code
- **Two distribution paths** — PyPI wheel and single-file `eggcalc.py` (~1.4MB)
- **Thread-safe** — `McpServer` owns isolated evaluator, config, registry, executor per connection
- **Bounded concurrency** — child process spawns controlled by `BoundedSemaphore`
- **Lazy loading** — `exact/` modules imported on first use, not at startup

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Entry Points                                │
│  CLI (__main__.py → cli.main())  |  MCP Server (server.main())     │
│  Library API (evaluate, evaluate_raw, EggCalcApp)                   │
└────────────────────────────┬────────────────────────────────────────┘
                             │
            ┌────────────────┴────────────────┐
            │                                 │
  ┌─────────▼─────────┐            ┌──────────▼──────────┐
  │     cli.py        │            │   mcp/server.py     │
  │  (CLI dispatch)   │            │  (JSON-RPC server)  │
  └─────────┬─────────┘            └──────────┬──────────┘
            │                                 │
  ┌─────────▼─────────┐            ┌──────────▼──────────┐
  │   normalize.py    │            │   mcp/tools.py      │
  │  (NL → Python)    │            │  (Tool router)      │
  └─────────┬─────────┘            └──────────┬──────────┘
            │                                 │
  ┌─────────▼─────────┐            ┌──────────▼──────────┐
  │   evaluator.py    │            │   exact/ pkg        │
  │    (AST eval)     │            │  (Text analysis)    │
  └─────────┬─────────┘            └─────────────────────┘
            │
  ┌─────────▼─────────┐
  │     units.py      │
  │  (Conversions)    │
  └───────────────────┘
```

---

## Subsystem Map

The codebase is organized into three subsystems plus supporting infrastructure.

### Core Calculator (6 modules)

| Module | Role | Key Exports |
|--------|------|-------------|
| [`units.py`](units.md) | Unit definitions, conversions, `UnitValue` class | `UnitValue`, `get_conversion_factor()`, `is_unit()`, `normalize_unit()` |
| [`evaluator.py`](evaluator.md) | AST parsing, safe math evaluation, `EggCalcApp` | `evaluate()`, `evaluate_raw()`, `evaluate_cached()`, `evaluate_async()`, `evaluate_with_timeout()` |
| [`normalize.py`](normalize.md) | NL tokenization, number words, expression normalization | `run()`, `normalize_text()`, `normalize_expression()` |
| [`cli.py`](cli.md) | CLI dispatch: argparse, REPL, text commands, help | `main()`, `print_help()` |
| [`capabilities.py`](capabilities.md) | Runtime capability detection | `detect_capabilities()`, `RuntimeCapabilities` |
| [`_protocol.py`] | MCP protocol version constants | `SUPPORTED_PROTOCOL_VERSIONS` |

### exact/ — Unicode Text Analysis Package (25 modules)

All deterministic, side-effect-free text analysis primitives. No external deps.

| Module | Role | Key Exports |
|--------|------|-------------|
| [`primitives.py`](primitives.md) | UTF-8 bytes, codepoints, Unicode normalization, invisible chars | `utf8_bytes()`, `codepoints()`, `normalize_unicode()`, `find_invisibles()` |
| [`unicode_tools.py`](unicode_tools.md) | Script detection, confusable identification, mixed scripts | `unicode_script()`, `detect_confusables()`, `detect_mixed_scripts()` |
| [`confusables.py`](confusables.md) | Auto-generated homoglyph data (compressed payload, 6565 entries, lazy decode) | `CONFUSABLES` lazy mapping |
| [`measure.py`](measure.md) | Text metrics: line, word, character category counts | `line_metrics()`, `word_metrics()`, `char_category_metrics()` |
| [`diff.py`](diff.md) | String diffing: first diff, Levenshtein, LCS, diff spans | `first_diff()`, `levenshtein_distance()`, `diff_spans()` |
| `diff_analysis.py` | Structural analysis of unified diffs and patches | `diff_touched_paths()`, `diff_hunk_ranges()`, `unified_diff_validate()` |
| [`validate.py`](validate.md) | Bracket/JSON/TOML/regex validation, version comparison | `check_brackets()`, `validate_json()`, `regex_test()`, `json_compare()` |
| [`synthesis.py`](synthesis.md) | Higher-level text analysis combining primitives | `measure_text()`, `inspect_text()`, `explain_diff()`, `list_compare()` |
| `transform.py` | Text escaping, hashing, fingerprinting | `escape_text()`, `text_hash()`, `text_fingerprint()` |
| `identifier.py` | Identifier naming convention analysis | `identifier_analyze()` |
| `identifier_inspect.py` | Identifier collision detection | `identifier_inspect()`, `identifier_table_inspect()` |
| `position.py` | Text position (line/column) conversion | `text_position()` |
| `glob.py` | Glob pattern matching | `glob_match()` |
| `config.py` | .env and INI file validation | `dotenv_validate()`, `ini_validate()` |
| `patch.py` | Unified diff parsing and simulation | `patch_apply_check()`, `patch_summary()` |
| `path_tools.py` | Path comparison and scoping | `path_compare()`, `path_scope_check()` |
| `inspect_prompt.py` | Hidden char/ANSI/instruction detection | `prompt_input_inspect()` |
| `markdown.py` | Markdown structure analysis and link checking | `markdown_structure()`, `code_fence_extract()` |
| `shell.py` | Shell command parsing and argv comparison | `shell_split()`, `shell_quote_join()`, `argv_compare()` |
| `unicode_policy.py` | Named Unicode safety policies | `unicode_policy_check()`, `canonicalize_text()` |
| `cargo.py` | Cargo.toml inspection | `cargo_toml_inspect()` |
| `version.py` | Semver/cargo constraint checking | `check_version_constraint()`, `parse_version()` |
| `llm_hygiene.py` | LLM JSON output hygiene detection | `llm_json_output_check()` |
| `repo_audit.py` | Repository file inventory analysis | `repo_file_inventory()` |
| `manifests.py` | Manifest/package inspection (pyproject, package.json, etc.) | `pyproject_inspect()`, `requirements_inspect()` |

### mcp/ — Model Context Protocol Server (3 modules)

| Module | Role | Key Exports |
|--------|------|-------------|
| `schemas.py` | 77 tool definitions, 11 profiles, JSON schemas | `TOOL_SCHEMAS`, `TOOL_PROFILES`, `TOOL_METADATA` |
| `tools.py` | Tool implementations bridging MCP names to exact/ functions | All 77 tool handler functions |
| `server.py` | JSON-RPC server, session lifecycle, thread pool | `McpServer`, `McpSession`, `ToolRegistry`, `ToolExecutor` |

### Supporting Modules

| Module | Role | Key Exports |
|--------|------|-------------|
| `__init__.py` | Public API surface, re-exports all key symbols | All core API functions |
| `__main__.py` | Module entry point | Delegates to `cli.main()` |
| `_version.py` | Single source of truth for version | `__version__` |
| `_protocol.py` | MCP protocol version constants | `SUPPORTED_PROTOCOL_VERSIONS` |
| `capabilities.py` | Runtime capability detection | `detect_capabilities()`, `RuntimeCapabilities` |

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

### Caret (`^`) Semantics

The two paths interpret `^` differently:

| Path | `^` means | `xor` / `bitxor` |
|------|-----------|-------------------|
| `evaluate()` | Bitwise XOR (Python AST) | N/A (use `^` directly) |
| `evaluate_raw()` / CLI | Rewritten to `**` (exponentiation) | Use `xor`/`bitxor` for bitwise XOR |

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

See [normalize.md](normalize.md) for the full 30-step pipeline.

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

## exact/ Text Analysis Package

The `exact/` package provides deterministic, independently testable text analysis primitives. All functions are pure (no side effects, no network, no LLM calls).

### Module Dependency Graph

```
primitives.py          ← foundation (no exact/ deps)
    ├── unicode_tools.py → confusables.py
    ├── measure.py
    ├── diff.py
    ├── validate.py
    ├── glob.py
    ├── position.py
    ├── transform.py
    ├── identifier.py
    ├── config.py
    ├── shell.py
    ├── markdown.py
    ├── patch.py → diff.py
    ├── diff_analysis.py → diff.py, patch.py
    ├── inspect_prompt.py → primitives.py
    ├── unicode_policy.py → primitives.py, unicode_tools.py
    ├── cargo.py → manifests.py
    ├── version.py
    ├── llm_hygiene.py
    ├── manifests.py
    ├── identifier_inspect.py → identifier.py
    ├── path_tools.py
    ├── repo_audit.py
    └── synthesis.py → primitives, diff, measure, unicode_tools (high-level orchestrator)
```

### Capability Categories

| Category | Modules | Purpose |
|----------|---------|---------|
| **Unicode Primitives** | primitives, unicode_tools, confusables, unicode_policy | Codepoint analysis, script detection, confusable identification, safety policies |
| **Text Metrics** | measure, synthesis (partial) | Line/word/char counts, character category breakdowns |
| **String Comparison** | diff, diff_analysis | First diff location, Levenshtein distance, LCS, unified diff parsing |
| **Format Validation** | validate, config | JSON/TOML/bracket/regex validation, .env/INI checking |
| **Text Transform** | transform, position | Escaping, hashing, fingerprinting, line/column conversion |
| **Code Analysis** | identifier, identifier_inspect, markdown, patch | Naming conventions, collision detection, markdown structure, patch simulation |
| **Shell & Path** | shell, path_tools, glob | Command parsing, argv comparison, path normalization, glob matching |
| **Package Inspection** | manifests, cargo, version | pyproject/package.json/requirements inspection, Cargo.toml parsing, semver checking |
| **Security & Safety** | inspect_prompt, llm_hygiene, repo_audit | Prompt injection detection, LLM output hygiene, repository inventory |
| **Higher-Level** | synthesis | Combines primitives into composite analyses (measure_text, inspect_text, etc.) |

---

## MCP Server

The MCP server exposes eggcalc's text analysis tools to AI agents via a stdio-based JSON-RPC interface.

### Tool Categories (77 tools)

| Category | Count | Examples |
|----------|-------|---------|
| Math | 3 | `math_eval`, `unit_convert`, `unit_info` |
| Text | 7 | `text_measure`, `text_equal`, `text_window`, `count_chars` |
| Diff | 3 | `explain_diff`, `list_compare`, `text_replace_check` |
| Unicode | 7 | `unicode_script`, `detect_confusables`, `unicode_policy_check` |
| Validation | 9 | `check_brackets`, `validate_json`, `regex_test`, `json_compare` |
| Identifier | 4 | `identifier_analyze`, `identifier_inspect` |
| Shell | 3 | `shell_split`, `shell_quote_join`, `argv_compare` |
| Markdown | 3 | `markdown_structure`, `code_fence_extract` |
| Config | 2 | `dotenv_check`, `ini_check` |
| Path | 4 | `path_analyze`, `path_compare`, `path_scope_check` |
| Patch | 2 | `patch_check`, `patch_summary` |
| Transform | 4 | `escape_text`, `text_hash`, `text_fingerprint` |
| Position | 1 | `text_position` |
| Glob | 1 | `glob_match` |
| Version | 2 | `version_compare`, `check_version_constraint` |
| Cargo | 1 | `cargo_inspect` |
| Manifest | 4 | `manifest_inspect`, `requirements_inspect` |
| Repo | 1 | `repo_inventory` |

### Profile System (11 profiles)

| Profile | Purpose |
|---------|---------|
| `full` | All 77 tools (default) |
| `default` | Core subset for general use |
| `human_math` | Math-focused with human-readable output |
| `codegg_core` / `codegg_core_min` | Code analysis subset |
| `codegg_preflight` / `codegg_patch` | Pre-commit and patch workflows |
| `codegg_config` | Config file validation |
| `codegg_unicode_security` | Unicode safety auditing |
| `codegg_shell` | Shell command analysis |
| `codegg_repo_audit` | Repository inventory |

### Session Lifecycle

```
UNINITIALIZED → INITIALIZING → READY → CLOSED
```

Clients must complete `initialize` + `notifications/initialized` handshake before calling tools. Tool requests before initialization are rejected with `-32600`.

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
    ├── confusables.py (auto-generated compressed data — ~40KB)
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
| `RuntimeCapabilities` | capabilities.py | Frozen snapshot of platform capabilities |

---

## Build System

For detailed build system documentation, see [build.md](build.md).

### build_single.py

Assembles all modules into a single `eggcalc.py` file (~1.4MB) for portability.

| Module Group | Modules |
|-------------|---------|
| `MODULES_CALC` | units, evaluator, normalize, cli, capabilities, _protocol |
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
make check         # All checks (lint + format-check + typecheck + docs-check + test)
make build         # Build distribution
make package-check # Validate wheel, sdist, and release surfaces
make release-check # All checks + package validation
make publish       # Upload to PyPI (requires twine)
```

See [docs/releasing.md](../docs/releasing.md) for the manual PyPI release procedure.

---

## Constraints

- **Standard library only** — no pip packages in `eggcalc/`. Imports limited to: `argparse`, `os`, `sys`, `re`, `math`, `ast`, `functools`, `typing`, `stat`, `shutil`, `subprocess`, `traceback`, `cmath`, `contextvars`, `logging`, `multiprocessing`, `threading`, `random`, `queue`, `collections.abc`, `zlib`, `base64`
- **`build_single.py` compatibility** — all runtime code must live in one of the six core modules or the `exact/` and `mcp/` packages
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

See [mutable_state_inventory.md](mutable_state_inventory.md) for a complete inventory of all mutable process-global state.
See [authority_inventory.md](authority_inventory.md) for the single authoritative source of every registry, constant, and contract.

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
| Runtime capabilities | [capabilities.md](capabilities.md) | Platform detection, RuntimeCapabilities, mode detection |

### exact/ — Unicode Text Analysis Package

| Component | Document | What It Covers |
|-----------|----------|----------------|
| exact/ (overview) | [exact.md](exact.md) | Package-level architecture, all 25 submodule APIs |
| primitives.py | [primitives.md](primitives.md) | UTF-8 bytes, codepoints, Unicode normalization, invisible chars |
| unicode_tools.py | [unicode_tools.md](unicode_tools.md) | Script detection, confusable identification, mixed scripts |
| confusables.py | [confusables.md](confusables.md) | Auto-generated homoglyph data (compressed, lazy decode) |
| measure.py | [measure.md](measure.md) | Text metrics: line, word, character category counts |
| diff.py | [diff.md](diff.md) | String diffing: first diff, common prefix/suffix, Levenshtein distance |
| validate.py | [validate.md](validate.md) | Bracket checking, JSON/TOML validation, regex safety |
| synthesis.py | [synthesis.md](synthesis.md) | Higher-level text analysis, inspection, comparison |

### mcp/ — Model Context Protocol Server

| Component | Document | What It Covers |
|-----------|----------|----------------|
| mcp/ (overview) | [mcp.md](mcp.md) | Server architecture, tool schemas, profiles, JSON-RPC protocol |
| schemas.py | [mcp.md](mcp.md#schemaspy--tool-schemas) | 77 tool definitions, 11 profiles, schema detail levels |
| tools.py | [mcp.md](mcp.md#toolspy--tool-implementations) | Tool implementations, error handling, input validation |
| server.py | [mcp.md](mcp.md#serverpy--mcp-protocol-handler) | stdio JSON-RPC, ThreadPoolExecutor, profile selection |

### Build & Distribution

| Component | Document | What It Covers |
|-----------|----------|----------------|
| build system | [build.md](build.md) | build_single.py, MODULE_MANIFEST, assembly, install.py |

### Cross-Cutting Concerns

| Document | What It Covers |
|----------|----------------|
| [authority_inventory.md](authority_inventory.md) | Single authoritative source for every major registry/constant/contract |
| [mutable_state_inventory.md](mutable_state_inventory.md) | Inventory of all mutable process-global state |
