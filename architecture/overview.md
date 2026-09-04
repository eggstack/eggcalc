# eggcalc Architecture Overview

A natural language math calculator (CLI, Python library, MCP server) and a deterministic Unicode text analysis suite. Standard library only, no external dependencies. Assembled by `build_single.py` into a single portable `eggcalc.py` file.

This document is the birds-eye view: how the subsystems fit together, what each module does, and an index into one deep-dive document per component in this directory.

---

## Table of Contents

- [What eggcalc Is](#what-eggcalc-is)
- [Architecture Diagram](#architecture-diagram)
- [How Everything Works Together](#how-everything-works-together)
- [Subsystem Map](#subsystem-map)
  - [Core Calculator (6 modules)](#core-calculator-6-modules)
  - [Package Plumbing](#package-plumbing)
  - [exact/ — Deterministic Utility Package (27 modules)](#exact--deterministic-utility-package-27-modules)
  - [mcp/ — Model Context Protocol Server (3 modules)](#mcp--model-context-protocol-server-3-modules)
- [Core Calculator Pipeline](#core-calculator-pipeline)
  - [Two Evaluation Paths](#two-evaluation-paths)
  - [Caret (`^`) Semantics](#caret--semantics)
  - [Normalization Pipeline](#normalization-pipeline-normalizepy)
  - [Safe AST Evaluation](#safe-ast-evaluation-evaluatorpy)
  - [Unit System](#unit-system-unitspy)
- [exact/ Design Notes](#exact-design-notes)
- [MCP Server](#mcp-server)
- [Entry Points](#entry-points)
- [Module Dependency Graph](#module-dependency-graph)
- [Key Data Structures](#key-data-structures)
- [Build & Distribution](#build--distribution)
- [Constraints](#constraints)
- [Ownership Model](#ownership-model)
- [Deep Dive Index](#deep-dive-index)

---

## What eggcalc Is

eggcalc is a dual-purpose tool:

1. **Natural Language Calculator** — evaluates math written in plain English (`"five plus three"`) or with units (`"30m + 100ft"`), with full unit conversion support.
2. **Unicode Text Analysis Suite** — deterministic text primitives for AI safety, security auditing, and text manipulation, exposed via CLI subcommands and an MCP server for AI agents.

### Key Properties

| Property | Detail |
|----------|--------|
| **Standard library only** | Zero runtime dependencies in production code |
| **Two distribution paths** | PyPI wheel (`pip install eggcalc`) and single-file `eggcalc.py` (~1.5 MB) |
| **Safe evaluation** | Python `ast` parsing — never `eval()` — with explicit DoS limits |
| **Deterministic tools** | Every exact/ function is pure: same input → same output, no I/O, no LLM calls |
| **Thread-safe & isolated** | Each `McpServer` / `EggCalcApp` owns its own evaluator, config, and state |
| **Lazy loading** | `import eggcalc` loads only the six core modules; CLI loads `exact/` handlers via `importlib` on first dispatch |

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Entry Points                               │
│   CLI (__main__.py → cli.main())   |   Library API                  │
│   (evaluate, evaluate_raw, EggCalcApp)   |   --mcp → mcp/server.py  │
└────────────────────────────┬────────────────────────────────────────┘
                             │
             ┌───────────────┴────────────────┐
             │                                │
   ┌─────────▼─────────┐          ┌──────────▼──────────┐
   │      cli.py       │          │   mcp/server.py     │
   │  (CLI dispatch,   │          │  (JSON-RPC stdio,   │
   │   REPL, modes)    │          │ sessions, profiles) │
   └─────────┬─────────┘          └──────────┬──────────┘
             │                                │
   ┌─────────▼─────────┐          ┌──────────▼──────────┐
   │   normalize.py    │          │    mcp/tools.py     │
   │  (NL + units →    │          │ (77 tool handlers,  │
   │  Python syntax)   │          │ lazy exact/ bridge) │
   └─────────┬─────────┘          └──────────┬──────────┘
             │                                │
   ┌─────────▼─────────┐          ┌──────────▼──────────┐
   │   evaluator.py    │          │     exact/ pkg      │
   │  (AST eval, no    │          │ (deterministic text │
   │      eval())      │          │  analysis, 25 mods) │
   └─────────┬─────────┘          └─────────────────────┘
             │
   ┌─────────▼─────────┐          ┌─────────────────────┐
   │     units.py      │          │  mcp/schemas.py     │
   │  (UnitValue,      │          │ (77 tool schemas,   │
   │   registry)       │          │  11 profiles)       │
   └───────────────────┘          └─────────────────────┘

Supporting: capabilities.py (runtime snapshot) · _protocol.py (protocol versions)
            _version.py (single version source)
```

---

## How Everything Works Together

Four canonical flows cover nearly all behavior:

### 1. Natural language evaluation (`"five plus three"`)

```
input → normalize_text()        "five"→"5", "plus"→"+"
      → tokenize + number words "five plus three" becomes "5+3"
      → unit preprocessing      "30m" becomes "30*m"
      → validate_for_eval()     reject unknown/unsafe tokens
      → evaluator.evaluate()    ast.parse → NodeVisitor walk
      → result                  8
```

### 2. Unit-aware evaluation (`"30m + 100ft in meters"`)

```
input → normalization inserts * before units, detects "in <unit>" conversion
      → evaluator builds UnitValue(30,"m") + UnitValue(100,"ft")
      → UnitValue arithmetic auto-converts via units.py registry
      → UnitValue(60.48, "m")
```

### 3. Direct AST evaluation (`evaluate("5+3")`)

Skips normalization entirely — `evaluator.evaluate()` parses valid Python math syntax directly. Fastest path (roughly an order of magnitude faster than `evaluate_raw()` on typical expressions; exact ratio is machine-dependent). Rejects natural language and unit suffixes.

### 4. MCP tool call (`tools/call`)

```
JSON-RPC request → McpSession (must be READY: initialize handshake done)
                → ToolExecutor validates args vs JSON Schema + signature,
                  enforces timeout, dispatches on bounded ThreadPoolExecutor
                → mcp/tools.py handler lazily imports the exact/ function
                → deterministic result → JSON-RPC response (size-capped)
```

---

## Subsystem Map

The codebase is three subsystems plus package plumbing.

### Core Calculator (6 modules)

These six modules form the calculator and are the only code loaded by `import eggcalc` (plus `_version.py`). They are also the only core members of the single-file build manifest.

| Module | Lines | Role | Key Exports | Deep Dive |
|--------|------:|------|-------------|-----------|
| `units.py` | 3,787 | Unit definitions, structural dimensions, conversions, `UnitValue` | `UnitValue`, `Dimension`, `UnitSpec`, `UnitExpression`, `UnitRegistry`, `normalize_unit()`, `get_conversion_factor()` | [units.md](units.md) |
| `evaluator.py` | 3,472 | Safe AST parsing/evaluation, constants, functions, memory/variables | `evaluate()`, `evaluate_raw()`, `evaluate_cached()`, `evaluate_async()`, `evaluate_with_timeout()`, `Evaluator`, `EggCalcApp`, `EvaluationError`, `Memory`, `register_constant()`, `register_function()` | [evaluator.md](evaluator.md) |
| `normalize.py` | 3,330 | NL tokenization, number words, unit preprocessing, expression validation | `run()`, `normalize_text()`, `normalize_expression()`, `NORMALIZE`, `PATTERNS` | [normalize.md](normalize.md) |
| `cli.py` | 951 | CLI dispatch: argparse, REPL, text subcommands, config loading | `main()`, `print_help()`, `run_cli()`, `COMMANDS` | [cli.md](cli.md) |
| `capabilities.py` | 141 | Runtime capability detection (frozen snapshot) | `detect_capabilities()`, `RuntimeCapabilities`, `capability_summary()` | [capabilities.md](capabilities.md) |
| `_protocol.py` | 11 | MCP protocol version constants | `SUPPORTED_PROTOCOL_VERSIONS`, `LATEST_SUPPORTED_PROTOCOL_VERSION` | (covered here + [mcp.md](mcp.md)) |

### Package Plumbing

| Module | Lines | Role | Deep Dive |
|--------|------:|------|-----------|
| `__init__.py` | 156 | Public API surface; eager re-exports from the six core modules; PEP 562 lazy `main`/`print_help` | [api.md](api.md) |
| `__main__.py` | 19 | `python -m eggcalc` entry; delegates to `cli.main()` | [api.md](api.md) |
| `_version.py` | 3 | Single source of truth for `__version__`; read by `pyproject.toml` and `build_single.py` | [build.md](build.md) |
| `eggcalc_config.py` (repo root template) | 73 | User config extension points: `CUSTOM_CONSTANTS`, `CUSTOM_FUNCTIONS`, `CUSTOM_UNITS`, `CUSTOM_ALIASES`, `CUSTOM_TEMP_CONVERSIONS`, `CUSTOM_NUMBER_WORDS`, `CUSTOM_OPERATOR_WORDS`. Loaded only by CLI calculator modes or when `EGGCALC_LOAD_CONFIG=1`; never at import time | [api.md](api.md) |

### exact/ — Deterministic Utility Package (27 modules)

All functions are deterministic, side-effect-free, and independently testable. No network, no filesystem, no LLM calls.

| Module | Lines | Role | Deep Dive |
|--------|------:|------|-----------|
| `primitives.py` | 740 | Foundation: UTF-8 bytes, codepoints, normalization, invisibles, graphemes, line/column helpers | [primitives.md](primitives.md) |
| `unicode_tools.py` | 310 | Script detection, confusable identification, mixed scripts | [unicode_tools.md](unicode_tools.md) |
| `confusables.py` | 60 | Auto-generated homoglyph data (6,565 entries, zlib+base85 payload, lazy decode) — do not edit by hand | [confusables.md](confusables.md) |
| `measure.py` | 265 | Line, word, character-category metrics | [measure.md](measure.md) |
| `diff.py` | 258 | First diff, common prefix/suffix, Levenshtein, LCS, diff spans | [diff.md](diff.md) |
| `diff_analysis.py` | 736 | Structural analysis of unified diffs: touched paths, hunk ranges, headers, conflict markers | [diff_analysis.md](diff_analysis.md) |
| `validate.py` | 3,053 | Bracket/JSON/TOML/regex validation, JSON shape/extract/compare, list sort/dedupe, version compare | [validate.md](validate.md) |
| `synthesis.py` | 1,982 | **High-level orchestrator**: composes primitives into composite analyses | [synthesis.md](synthesis.md) |
| `transform.py` | 712 | Escaping/unescaping (JSON, Python, Rust, shell, regex, markdown, HTML, URL), hashing, fingerprinting | [transform.md](transform.md) |
| `identifier.py` | 308 | Naming convention classification and cross-language validity | [identifier.md](identifier.md) |
| `identifier_inspect.py` | 756 | Identifier collision detection (confusables, casefold, mixed scripts, keywords) | [identifier_inspect.md](identifier_inspect.md) |
| `position.py` | 503 | Byte offset ↔ codepoint ↔ line/column ↔ UTF-16 conversion | [position.md](position.md) |
| `glob.py` | 311 | Glob matching with `*`, `**`, `?`; POSIX/Windows | [glob.md](glob.md) |
| `config.py` | 347 | `.env` and INI file validation | [config.md](config.md) |
| `patch.py` | 641 | Unified diff parsing and in-memory apply simulation | [patch.md](patch.md) |
| `path_tools.py` | 615 | Lexical path analysis, normalization, comparison, scope checks | [path_tools.md](path_tools.md) |
| `inspect_prompt.py` | 560 | Prompt-injection red flags: hidden chars, bidi, ANSI, base64 blobs, instruction phrases | [inspect_prompt.md](inspect_prompt.md) |
| `markdown.py` | 645 | Markdown structure scanning, code fence extraction, lexical link check | [markdown.md](markdown.md) |
| `shell.py` | 362 | POSIX shell tokenization, quote-join, argv compare, risky-feature flags | [shell.md](shell.md) |
| `unicode_policy.py` | 930 | Named Unicode safety policies and canonicalization profiles | [unicode_policy.md](unicode_policy.md) |
| `cargo.py` | 508 | Cargo.toml inspection (package, workspace, deps, suspicious names) | [cargo.md](cargo.md) |
| `version.py` | 545 | Semver/cargo version parsing and constraint checking | [version.md](version.md) |
| `llm_hygiene.py` | 326 | LLM JSON output diagnosis (fences, prose, trailing commas, BOM, …) | [llm_hygiene.md](llm_hygiene.md) |
| `manifests.py` | 868 | Manifest inspection: pyproject.toml, package.json, requirements.txt, go.mod, lockfiles; shared `_Finding` TypedDict | [manifests.md](manifests.md) |
| `repo_audit.py` | 422 | Repository file inventory, language signals, vendor/generated detection | [repo_audit.md](repo_audit.md) |
| `network.py` | 240 | IP/CIDR inspection with explicit version-stable special-use taxonomy | [network.md](network.md) |
| `encoding.py` | 282 | Strict codec (utf8/hex/base64/base64url) and radix (2–36, u128-capped) conversion | [encoding.md](encoding.md) |
| `__init__.py` | 495 | Fully lazy public API: zero implementation imports at import time; 206-name `__all__` resolved via a matching 206-entry `_LAZY_IMPORTS` map | [exact.md](exact.md#exact__init__py--public-api) |

*(Package-level doc: [exact.md](exact.md).)*

### mcp/ — Model Context Protocol Server (3 modules)

| Module | Lines | Role | Key Exports | Deep Dive |
|--------|------:|------|-------------|-----------|
| `schemas.py` | 5,075 | 77 tool definitions with JSON Schemas, metadata, tiers, profiles | `TOOL_SCHEMAS`, `TOOL_METADATA`, `TOOL_PROFILES` | [mcp.md](mcp.md#schemaspy--tool-schemas) |
| `tools.py` | 6,302 | Tool handler implementations; lazily imports exact/ functions inside each handler; bounded input pre-checks | all 77 handlers | [mcp.md](mcp.md#toolspy--tool-implementations) |
| `server.py` | 3,011 | stdio JSON-RPC server, sessions, config management, executor | `McpServer`, `McpSession`, `McpServerConfig`, `ConfigSnapshot`, `ConfigManager`, `ToolRegistry`, `ToolExecutor`, `EvaluationPolicy`, `RuntimeContext` | [mcp.md](mcp.md#serverpy--mcp-protocol-handler) |

---

## Core Calculator Pipeline

### Two Evaluation Paths

This is the most important architectural distinction in the codebase:

| Function | Handles | Input format |
|----------|---------|--------------|
| `evaluate(expr)` | Direct AST evaluation | Already-normalized Python-syntax math (`"5+3"`, `"2**10"`); spaces tolerated |
| `evaluate_raw(expr)` | NL + units + math | User-facing expressions (`"five plus three"`, `"30m + 100ft"`) |
| `run(expr, NORMALIZE, PATTERNS)` | CLI-compatible path | Normalizes NL/units, **prints** result to stdout (or error to stderr), returns `(result, exit_code)` — `None` on failure |

```python
run("five plus three", NORMALIZE, PATTERNS)  # → (8, 0); prints "8"
evaluate("5+3")                              # → 8
evaluate("five plus three")                  # → raises SyntaxError
```

### Caret (`^`) Semantics

The two paths interpret `^` differently:

| Path | `^` means | bitwise XOR |
|------|-----------|-------------|
| `evaluate()` | Bitwise XOR (Python AST semantics) | use `^` directly |
| `evaluate_raw()` / CLI | Rewritten to `**` (exponentiation) | use `xor` / `bitxor` word forms |

### Normalization Pipeline (normalize.py)

Multi-stage pipeline converting natural language to Python syntax:

| Stage | Description | Example |
|-------|-------------|---------|
| Filler removal | Strip conversational noise | `"what's"` → removed |
| Number words | Words → digits (40 base entries + ~12,700 derived multi-word forms) | `"twenty one"` → `"21"` |
| Operator conversion | Words → symbols (15 operator keys) | `"plus"` → `+`, `"of"` → `*` |
| Function mapping | NL names → canonical calls (128 mappings + 20 multi-word names) | `"square root"` → `sqrt` |
| Constant recognition | Physical constant names | `"avogadro"` → `na` |
| Unit preprocessing | Insert implicit multiplication, canonicalize | `"30m"` → `30*m` |
| XOR handling | `xor`/`bitxor` → `bitxor(...)` calls | `"5 xor 3"` → `bitxor(5, 3)` |
| Validation | Token whitelist before eval; length/nesting caps | rejects anything unsafe |

Hard limits: `MAX_INPUT_LENGTH = 10_000`, `MAX_NORMALIZED_LENGTH = 20_000`, `MAX_NESTING_DEPTH = 100`.

See [normalize.md](normalize.md) for the full pipeline, thread-safety notes, and config rebuild mechanics.

### Safe AST Evaluation (evaluator.py)

Parses with Python's `ast` module — **never `eval()`** — and walks the tree with an `ast.NodeVisitor`.

| Category | Examples |
|----------|----------|
| Arithmetic | `+`, `-`, `*`, `/`, `//`, `%`, `**` |
| Trig / hyperbolic | `sin`, `cos`, `tan`, `asin`, … `sinh`, `cosh`, `tanh` (complex-aware) |
| Log / power | `log`, `log2`, `log10`, `exp`, `sqrt`, `cbrt` |
| Statistics | `mean`, `median`, `mode`, `std`, `variance`, `sum`, `min`, `max` |
| Combinatorics | `factorial`, `gcd`, `lcm`, `perm`, `comb` |
| Bitwise | `&`, `|`, `^`, `~`, `<<`, `>>`, `bitand`, `bitor`, `bitxor` |
| Complex | `real`, `imag`, `conj`, `phase`, `polar`, `rect` |
| Primes | `isprime`, `primefactors`, `nextprime`, `prevprime` |
| Random (gated) | `random`, `randint`, `randn`, `gauss`, `seed` — disabled in MCP mode |
| Memory / variables | `M`, `M+`, `MR`, `MC`; `setvar`, `getvar`, `listvars` |
| Constants (55) | `pi`, `e`, `tau`, `i`, `c`, `h`, `na`, `k`, `G`, `R`, … |

DoS limits: `MAX_INPUT_LENGTH = 10_000`, `MAX_NESTING_DEPTH = 100`, `MAX_AST_NODES = 10_000`, `MAX_EXPONENT = 10_000`, `MAX_FACTORIAL = 1_000`, `MAX_SHIFT_COUNT = 50_000`, `MAX_RESULT_VALUE = 1e308`. Timeout evaluation runs in child processes bounded by a semaphore (4 concurrent spawns).

Every built-in function has a `UnitPolicy` (10 members: `DIMENSIONLESS`, `ANGLE_INPUT`, `ANGLE_OUTPUT`, `PRESERVE_SINGLE`, `COMPATIBLE_REDUCER`, `VARIANCE_SQUARED`, `SIGN_OUTPUT`, `ROOT`, `HYPOT`, `ATAN2`) enforced dimensionally in `visit_Call`. Replacing a canonical built-in drops it to dimensionless custom-callable rules.

See [evaluator.md](evaluator.md) for the full function catalog, memory/variable systems, and callable identity contract.

### Unit System (units.py)

Declarative registry: **150 `UnitSpec` entries**, ~508 alias strings, 17 categories (length, mass, time, temperature, data, data_rate, volume, pressure, energy, power, force, voltage, current, angle, speed, area, frequency).

- `Dimension` models 8 SI base axes plus a structural `angle` flag; guards reject impossible angle algebra (e.g. `rad + 1`).
- Temperature uses affine conversion (`scale_to_base` / `offset_to_base`; Kelvin is base). Fahrenheit/Rankine use `scale=5/9`.
- Compound expressions parse via `parse_unit_expression("m/s")` → validated `UnitExpression` (merged factors, exponent bound `MAX_ABS_UNIT_EXPONENT = 16`).
- Power binds units: `5m ** 2` → `5 m**2`, `(5m)**2` → `25.0 m**2`. Division renders denominators parenthesized: `5m / 2s` → `2.5 m/s`.
- Pairwise conversion factors (`UNIT_CONVERSIONS`) and `TEMPERATURE_CONVERSIONS` are computed lazily on first access, not at import.

See [units.md](units.md) for the registry internals and temperature math.

---

## exact/ Design Notes

### Module Dependency Graph

```
primitives.py          ← foundation (no exact/ deps)
    ├── confusables.py (generated data, leaf)
    ├── unicode_tools.py → confusables
    ├── measure.py
    ├── diff.py
    ├── validate.py
    ├── glob.py, position.py, transform.py, identifier.py
    ├── config.py, shell.py, markdown.py, patch.py, version.py
    │                    , manifests.py, llm_hygiene.py, repo_audit.py
    ├── network.py, encoding.py (standalone leaves, stdlib only)
    ├── diff_analysis.py → diff, patch
    ├── inspect_prompt.py → primitives
    ├── unicode_policy.py → primitives, unicode_tools
    ├── identifier_inspect.py → identifier, diff, unicode_tools
    ├── path_tools.py → unicode_tools
    ├── cargo.py → manifests (_Finding), unicode_tools (lazy)
    └── synthesis.py → primitives, diff, measure, unicode_tools  ← orchestrator
```

### Shared Conventions

- **TypedDict results** — every public function returns a TypedDict (never NamedTuple); fields use a stable vocabulary (`valid`, `findings`, `warnings`, `summary`, `changed`).
- **Findings pattern** — issues are reported, not raised. `manifests.py` defines the shared `_Finding` TypedDict (`code`, `severity ∈ {error, warning, info}`, `message`, `line`, `column`); `cargo.py` reuses it.
- **Bounded inputs** — each module enforces its own caps (validate/config/shell/synthesis: 100,000 chars; manifests/llm_hygiene: 500,000; patch: 200,000; lists: 10,000 items; findings capped at 200 with truncation notice).
- **Purity** — lexical analysis only; `path_tools.py` explicitly never touches the filesystem; nothing calls the network or an LLM.

`synthesis.py` is the high-level orchestrator: `measure_text`, `text_equal`, `explain_diff`, `inspect_text`, `count_chars`, `list_compare`, `text_window`, `text_replace_check`, `line_range_extract`, `line_range_compare` compose lower-level primitives into agent-facing analyses.

---

## MCP Server

stdio JSON-RPC server exposing deterministic tools to AI agents. Protocol versions supported: `2024-11-05` and `2025-11-25` (latest).

### Tool Categories (77 tools, 18 categories)

| Category | Count | Category | Count |
|----------|------:|----------|------:|
| text | 20 | identifier | 3 |
| patch | 8 | list | 3 |
| json | 6 | config | 3 |
| manifest | 5 | regex | 3 |
| path | 5 | markdown | 2 |
| math | 4 | unicode | 2 |
| shell | 4 | version | 2 |
| validation | 4 | cargo / repo / toml | 1 each |

Tools carry tier metadata (tier 0: 7, tier 1: 23, tier 2: 40, tier 3: 7) used for profile curation.

### Profile System (11 profiles)

Selected via `EGGCALC_MCP_PROFILE` at startup or per-request in `tools/list`:

| Profile | Tools | Purpose |
|---------|------:|---------|
| `full` | 77 | Everything (default) |
| `default` | 26 | General-purpose subset |
| `codegg_core` | 22 | Code analysis workflow |
| `codegg_repo_audit` | 18 | Repository inventory |
| `codegg_config` | 17 | Config file validation |
| `codegg_patch` | 12 | Patch application workflows |
| `codegg_preflight` | 10 | Pre-commit checks |
| `codegg_unicode_security` | 8 | Unicode safety auditing |
| `codegg_core_min` | 6 | Minimal code subset |
| `codegg_shell` | 5 | Shell command analysis |
| `human_math` | 4 | Math-focused, human-readable |

### Session Lifecycle & Isolation

```
UNINITIALIZED → INITIALIZING → READY → CLOSED
```

Clients must complete `initialize` + `notifications/initialized` before `tools/list` or `tools/call`; earlier tool requests get `-32600`. `ping` works in any state.

- `McpServer` owns its `McpServerConfig`, `ToolRegistry`, `ToolExecutor`, `ConfigManager`, dedicated `Evaluator`, and session set — multiple servers in one process are fully isolated.
- `McpServerConfig` is a frozen dataclass with clamped defaults: 1 MB request/output byte caps (`max_output_bytes` clamps to min 1), 16 tool workers, queue size 32, 30 s max tool timeout, 10 req/s rate limit. Built via `from_environment()`.
- Config changes flow through validated `ConfigCandidate` → immutable `ConfigSnapshot` (generation-numbered, `MappingProxyType` throughout) applied atomically by `ConfigManager`.
- The sessionless `handle_request()` compat shim emits `DeprecationWarning` and routes through an isolated compatibility server; new code should use `McpServer` + `McpSession`.

See [mcp.md](mcp.md) for the protocol details, resource limits table, and embedding examples.

---

## Entry Points

| Entry Point | Invocation | Path |
|-------------|-----------|------|
| CLI (package script) | `calc "expr"` | `pyproject.toml` console script → `cli.main()` |
| CLI (module) | `python -m eggcalc "expr"` | `__main__.py` → `cli.main()` |
| CLI (single-file) | `python3 eggcalc.py "expr"` | assembled single file |
| API (fast) | `evaluate("5+3")` | direct AST evaluation |
| API (full pipeline) | `evaluate_raw("five plus three")` | NL + units → normalize → evaluate |
| API (cached) | `evaluate_cached(expr)` | global LRU cache (1,024 entries / 64 MB cap) |
| API (async) | `await evaluate_async(expr)` | thread-pool wrapper |
| API (timeout) | `evaluate_with_timeout(expr, timeout=5.0)` | child process, semaphore-bounded |
| API (webapp) | `EggCalcApp().calculate(expr)` | per-instance evaluator + cache |
| Capabilities | `calc --capabilities` | `detect_capabilities().to_json()` |
| MCP server | `calc --mcp` | `mcp.server.mcp_main()` (alias: `main`) |
| Text commands | `calc inspect/count/regex/replace-check/lines/patch-check/shell-split/md-structure/dotenv-check` | lazy `importlib` load of exact/ handler |

CLI mode classification happens **before** any cwd-local config loading: informational modes (`--help`, `--version`, `--capabilities`), `--mcp`, and text commands never execute `eggcalc_config.py`.

---

## Module Dependency Graph

```
__main__.py ──► cli.main()

__init__.py ──► _version, capabilities, evaluator, normalize, units
                 (+ lazy PEP 562: main, print_help from cli)

cli.py ──► evaluator, normalize, units            (eager)
           exact/<handler>                        (lazy importlib per command)
           eggcalc.mcp.server                     (only for --mcp)

normalize.py ──► evaluator (evaluate, EvaluationError — eager),
                 units (UNIT_ALIASES, UnitValue, is_unit)
                 (evaluator → normalize is LAZY, inside evaluate_raw/cache paths)

evaluator.py ──► units (UnitValue, UNIT_ALIASES, conversions)

units.py ──► (no eggcalc deps — leaf)

exact/primitives.py ◄── every other exact module (directly or transitively)
exact/__init__.py ──► fully lazy PEP 562 (zero implementation imports)

mcp/schemas.py ──► (declarative only)
mcp/tools.py ──► evaluator (eager), exact/* (lazy, inside each handler)
mcp/server.py ──► schemas, tools, evaluator, capabilities
```

**Lazy CLI re-exports.** Both `normalize.py` and `__init__.py` expose `main`/`print_help` via PEP 562 `__getattr__`. This preserves backward compatibility while keeping the graph acyclic — `cli.py` imports `normalize`, so `normalize` cannot eagerly import `cli`.

---

## Key Data Structures

| Structure | Module | Purpose |
|-----------|--------|---------|
| `Dimension` | units.py | Immutable structural dimension: 8 SI base exponents + `angle` flag; operator algebra for compound derivation |
| `UnitSpec` | units.py | Frozen declarative unit definition (canonical, aliases, dimension, scale/offset, category) |
| `UnitDefinition` | units.py | Immutable runtime unit built from `UnitSpec` by the registry builder |
| `UnitRegistry` | units.py | Immutable registry: `by_alias()`, `by_canonical()`, `dimension_of()`, `conversion_factor()` |
| `UnitExpression` | units.py | Frozen compound-unit expression ((canonical, exponent) factors) with self-validation |
| `UnitValue` | units.py | Numeric value + optional unit; full arithmetic with auto-conversion |
| `DIM_*` constants | units.py | Pre-built dimensions (`DIM_LENGTH`, `DIM_MASS`, `DIM_TIME`, `DIM_TEMPERATURE`, …, `DIM_DIMENSIONLESS`) |
| `UNIT_DEFINITIONS` | units.py | Tuple of 150 `UnitSpec` — authoritative unit registry source |
| `UNIT_ALIASES` / `UNIT_CATEGORIES` | units.py | Alias → canonical (~508) and alias → category maps |
| `UNIT_CONVERSIONS` / `TEMPERATURE_CONVERSIONS` | units.py | Lazily-populated pairwise factor / affine-rule dicts |
| `NUMBER_WORDS` / `OPERATOR_CONVERSIONS` / `FUNCTION_MAPPINGS` / `CONSTANT_WORDS` | normalize.py | NL lookup tables (40 number entries, 15 operator keys, 128 function aliases, 20 constant word groups; `_MULTI_WORD_FUNCTIONS` adds 20 multi-word names) |
| `NORMALIZE` / `PATTERNS` | normalize.py | Mutable config dicts rebuilt under a lock on config change |
| `Memory` | evaluator.py | Thread-safe memory registers (≤1,000 named registers) |
| `Evaluator` | evaluator.py | `ast.NodeVisitor` implementation; class-level `CONSTANTS` (55) and `FUNCTIONS` (104); per-instance variables (≤1,000) |
| `UnitPolicy` / `FunctionSpec` | evaluator.py | Dimensional contract enum (10 members) + frozen wrapper |
| `TimeoutError` (custom) | evaluator.py | Raised by `evaluate_with_timeout()` |
| `EggCalcApp` | evaluator.py | Thread-safe app wrapper: instance-local evaluator + LRU cache |
| `CommandSpec` / `COMMANDS` | cli.py | TypedDict metadata for the 9 text subcommands |
| `TOOL_SCHEMAS` / `TOOL_METADATA` / `TOOL_PROFILES` | mcp/schemas.py | 77 tool schemas/metadata/tiers, 11 profiles |
| `McpServerConfig` / `ConfigSnapshot` / `ConfigManager` | mcp/server.py | Frozen config, deeply-immutable snapshots, atomic generation-numbered replacement |
| `ToolRegistry` / `ToolExecutor` | mcp/server.py | Validated tool tables; bounded worker pool + reservation state machine |
| `McpSession` / `McpSessionState` | mcp/server.py | Per-connection lifecycle (`UNINITIALIZED`→`READY`→`CLOSED`), cancellation records |
| `RuntimeCapabilities` | capabilities.py | Frozen 13-field platform snapshot (versions, features, start method, mode) |
| `_Finding` | exact/manifests.py | Shared structured finding: `code`, `severity`, `message`, `line`, `column` |
| `CONFUSABLES` | exact/confusables.py | Lazy `Mapping` (6,565 entries), decoded on first access |

---

## Build & Distribution

Full details: [build.md](build.md).

- **`build_single.py`** (1,323 lines) assembles everything into one portable `eggcalc.py` (~42k lines / ~1.5 MB). `MODULE_MANIFEST` is the single source of truth: **34 `ModuleSpec` entries** (6 core + 25 exact + 3 mcp) with name, path, group, declared `depends_on`, and single-file inclusion flag. `validate_build_manifest()` checks duplicates, missing files, unknown deps, cycles, reachability, and residual package-relative imports. Assembly topologically sorts modules, strips docstrings/`__all__`, rewrites relative imports to globals, renames colliding entry points (`normalize_main()`, `mcp_main()`), and prefixes conflicting MCP function names.
- **`install.py`** builds and installs the single file as `calc` (`~/.local/bin/calc` on Linux/macOS, `%LOCALAPPDATA%\Programs\calc` on Windows) with atomic copy and PATH management.
- **Development commands:** `make test`, `make lint`, `make format`, `make typecheck`, `make docs-check` (generated-MCP-doc drift), `make check` (all correctness incl. build validation + pytest), `make package-check` (wheel/sdist/single-file smoke), `make release-check`, `make publish` (manual Twine upload). CI runs `make check` then `make package-check`; GitHub Actions never publishes.

---

## Constraints

- **Standard library only.** Core modules may import only: `argparse`, `ast`, `cmath`, `collections`, `contextvars`, `dataclasses`, `enum`, `functools`, `json`, `logging`, `math`, `multiprocessing`, `os`, `queue`, `random`, `re`, `sys`, `threading`, `traceback`, `types`, `typing`. The `exact/` and `mcp/` packages may additionally use e.g. `tomllib`, `importlib`, `unicodedata`, `hashlib`, `shlex`, `signal`, `asyncio`, `zlib`, `base64`.
- **`build_single.py` compatibility** — runtime code lives only in the six core modules, `exact/`, or `mcp/`; anything else breaks the single-file build.
- **TypedDict over NamedTuple** for structured returns (TypedDicts cannot take `__slots__`).
- **CLI output is result-only** — no echo of input, no arrows, no decoration (REPL included).
- **Import must stay side-effect-free** — no cwd-local config loading at `import eggcalc`; see the config-loading rules in [AGENTS.md](../AGENTS.md).
- **Python ≥ 3.11** per `pyproject.toml`.

---

## Ownership Model

Explicit ownership of mutable state prevents cross-instance interference:

| Owner | Owns |
|-------|------|
| `McpServer` | `McpServerConfig`, `ToolRegistry`, `ToolExecutor`, `ConfigManager`, dedicated `Evaluator`, session creation |
| `McpSession` | lifecycle state, negotiated protocol version, client info, cancellation records |
| `EggCalcApp` | instance-local `Evaluator`, instance-local cache |
| Module-level API functions (`evaluate*`) | global `_default_evaluator` + global cache |

Multiple `McpServer` instances coexist safely with different configs, registries, and evaluator policies; two sessions on one server share nothing.

Inventories: [authority_inventory.md](authority_inventory.md) (single authoritative source per registry/constant/contract) · [mutable_state_inventory.md](mutable_state_inventory.md) (every mutable process-global).

---

## Deep Dive Index

Every component has a dedicated document in this directory. Use this index to jump straight to focused review material.

### Core Calculator & Public Surface

| Component | Document | Covers |
|-----------|----------|--------|
| Public API surface (`__init__.py`, exports, limits) | [api.md](api.md) | Exported symbols, signatures, usage patterns, performance |
| normalize.py | [normalize.md](normalize.md) | Pipeline stages, lookup tables, thread safety, security notes |
| evaluator.py | [evaluator.md](evaluator.md) | AST handlers, functions/constants, unit policies, memory/variables, `EggCalcApp` |
| units.py | [units.md](units.md) | Dimensions, registry, `UnitSpec`/`UnitExpression`, temperature offset math |
| cli.py | [cli.md](cli.md) | Modes, options, text subcommands, REPL, output formats |
| capabilities.py | [capabilities.md](capabilities.md) | Detection logic, `RuntimeCapabilities` fields, mode detection |
| User configuration | [api.md](api.md#configuration-functions) | `load_user_config()`, `CUSTOM_*` extension points, env-var gates |

### exact/ — Text Analysis Package

| Component | Document | Covers |
|-----------|----------|--------|
| Package overview (all 27 modules) | [exact.md](exact.md) | Structure, dependency graph, full API listing |
| primitives.py | [primitives.md](primitives.md) | Bytes/codepoints/normalization/invisibles/graphemes |
| unicode_tools.py | [unicode_tools.md](unicode_tools.md) | Scripts, confusables, mixed-script detection |
| confusables.py | [confusables.md](confusables.md) | Generated data, payload format, regeneration procedure |
| measure.py | [measure.md](measure.md) | Line/word/category metrics |
| diff.py | [diff.md](diff.md) | first_diff, Levenshtein, LCS, spans |
| diff_analysis.py | [diff_analysis.md](diff_analysis.md) | Touched paths, hunk ranges, headers, conflict markers |
| validate.py | [validate.md](validate.md) | Brackets, JSON/TOML, regex safety, limits |
| synthesis.py | [synthesis.md](synthesis.md) | Composite analyses (orchestrator) |
| transform.py | [transform.md](transform.md) | Escape modes, hashing, fingerprints |
| identifier.py | [identifier.md](identifier.md) | Naming conventions, cross-language validity |
| identifier_inspect.py | [identifier_inspect.md](identifier_inspect.md) | Collision/confusable detection across identifier sets |
| position.py | [position.md](position.md) | Byte/codepoint/line-column/UTF-16 conversion |
| glob.py | [glob.md](glob.md) | Glob semantics, platform separators |
| config.py | [config.md](config.md) | .env / INI validation |
| patch.py | [patch.md](patch.md) | Diff parsing, apply simulation, summaries |
| path_tools.py | [path_tools.md](path_tools.md) | Lexical path analysis, scope checks |
| inspect_prompt.py | [inspect_prompt.md](inspect_prompt.md) | Prompt-injection detection categories |
| markdown.py | [markdown.md](markdown.md) | Structure scan, fences, link check |
| shell.py | [shell.md](shell.md) | argv splitting, quote-join, risky features |
| unicode_policy.py | [unicode_policy.md](unicode_policy.md) | Named policies, canonicalization profiles |
| cargo.py | [cargo.md](cargo.md) | Cargo.toml inspection |
| version.py | [version.md](version.md) | Semver parsing, constraint operators |
| llm_hygiene.py | [llm_hygiene.md](llm_hygiene.md) | LLM JSON output diagnosis |
| manifests.py | [manifests.md](manifests.md) | pyproject/package.json/requirements/go.mod/lockfiles, `_Finding` |
| repo_audit.py | [repo_audit.md](repo_audit.md) | File inventory, language signals |
| network.py | [network.md](network.md) | IP/CIDR inspection, explicit special-use taxonomy |
| encoding.py | [encoding.md](encoding.md) | Codec and radix conversion, strict validation |

### mcp/ — Model Context Protocol Server

| Component | Document | Covers |
|-----------|----------|--------|
| mcp/ overall | [mcp.md](mcp.md) | Architecture, isolation, usage, notes |
| schemas.py | [mcp.md](mcp.md#schemaspy--tool-schemas) | 77 schemas, detail levels, tiers |
| tools.py | [mcp.md](mcp.md#toolspy--tool-implementations) | Handler patterns, validation, error mapping |
| server.py | [mcp.md](mcp.md#serverpy--mcp-protocol-handler) | Sessions, config manager, executor, profiles |

### Build, Distribution, Cross-Cutting

| Document | Covers |
|----------|--------|
| [build.md](build.md) | `build_single.py`, `MODULE_MANIFEST`, assembly transforms, `install.py` |
| [authority_inventory.md](authority_inventory.md) | Single authoritative source per registry/constant/contract |
| [mutable_state_inventory.md](mutable_state_inventory.md) | Inventory of mutable process-global state |
| [review_plan.md](review_plan.md) | Archived 2026-05-29 module-review plan (historical record) |
