# eggcalc Canonical Terminology and Domain Model

Status: normative companion to `plans/000-long-term-specification.md`

This document defines the language eggcalc implementation plans, protocol types, storage schemas, architecture documents, tests, CLI labels, and operator documentation MUST use. When current code or legacy plans use a term differently, the compatibility mapping in this document describes the migration target.

## 1. Naming rules

1. A durable concept MUST have a typed identifier or canonical name rather than an ad-hoc string.
2. A path is a locator and MUST NOT be treated as durable identity for tools, profiles, or units.
3. A normalization stage, an AST evaluation, a unit conversion, a tool call, and a distribution artifact are distinct objects.
4. Terms MUST NOT be used as interchangeable shorthand when they cross normalization/evaluation, protocol-era, profile, or packaging boundaries.
5. Compatibility fields and shims MAY remain during migration but MUST be labeled as compatibility projections.

## 2. Top-level relationships

```text
Distribution
|-- PyPI wheel (pip install eggcalc)
`-- Single-file eggcalc.py (build_single.py assembly)

Process
|-- calculator-core (normalize -> evaluator -> units)
|-- exact-utilities (28 deterministic modules)
|-- mcp-server (schemas -> tools -> server/sessions)
`-- cli-distribution (cli dispatch -> REPL/text commands/--mcp)

Expression
  -> NormalizationTrace (explain-only, never evaluates)
  -> Evaluator (AST walk, UnitPolicy, memory/variables)
  -> UnitValue + Dimension
```

The principal runtime relationship is:

```text
Input text
  -> normalize_text / normalize_expression (NORMALIZE, PATTERNS tables)
  -> validate_for_eval (whitelist, caps)
  -> Evaluator (ast.NodeVisitor)
  -> result (number | UnitValue | complex)

Tool call
  -> McpServer (config, registry, executor, evaluator, sessions)
  -> McpSession (legacy) | ModernRequestContext (modern)
  -> ToolRegistry + ToolExecutor -> exact/ function
```

## 3. Calculator terms

### Evaluate (direct)

`evaluate(expr)`: direct AST evaluation of already-normalized Python-syntax math (`"5+3"`, `"2**10"`). Rejects natural language and unit suffixes. `^` means bitwise XOR.

### Evaluate raw (full pipeline)

`evaluate_raw(expr)` / `evaluate_cached()` / `evaluate_async()` / `evaluate_with_timeout()` / `EggCalcApp().calculate()`: full pipeline (NL + units + math). `^` is rewritten to `**`; use `xor`/`bitxor` word forms for XOR.

### Run (CLI helper)

`run(expr, NORMALIZE, PATTERNS)`: normalizes, then calls `evaluate()` internally. Prints to stdout/stderr; returns `(result, exit_code)`, `None` on failure. Used by CLI and tests for NL/unit paths.

### Normalization trace

`trace_normalization(expr)` / `calc --explain "<expr>"`: deterministic, side-effect-free, stage-by-stage explanation. Observability only, never a behavior change.

### Normalization tables

`NORMALIZE` / `PATTERNS`: mutable config dicts rebuilt under a lock on config change (`numbers`, `functions`, `word_to_number`, `word_to_operator`, `word_to_constant`, `word_to_all`, `symbols`, `convert`).

### Evaluator

`Evaluator`: `ast.NodeVisitor` implementation; class-level `CONSTANTS` (55) and `FUNCTIONS` (104); per-instance variables (<=1,000); `Memory` (<=1,000 named registers). `EggCalcApp` wraps an instance-local evaluator plus LRU cache.

### UnitPolicy

`UnitPolicy` (11 members: `DIMENSIONLESS`, `ANGLE_INPUT`, `ANGLE_OUTPUT`, `PRESERVE_SINGLE`, `COMPATIBLE_REDUCER`, `VARIANCE_SQUARED`, `SIGN_OUTPUT`, `ROOT`, `CUBE_ROOT`, `HYPOT`, `ATAN2`): dimensional contract enforced in `visit_Call`. Replacing a canonical built-in drops it to dimensionless custom-callable rules.

### UnitValue

`UnitValue`: numeric value plus optional unit; arithmetic auto-converts via the registry. `Dimension`: 8 SI base exponents plus structural `angle` flag. `UnitSpec`: frozen declarative definition; `UnitRegistry`: immutable alias/canonical/dimension/conversion maps.

### Capability snapshot

`RuntimeCapabilities`: frozen 13-field platform snapshot from `detect_capabilities()`; diagnostic only, never a protocol capability.

## 4. exact/ terms

### Deterministic utility

An `exact/` public function: pure, bounded, independently testable; no network, filesystem, or LLM calls. Returns a TypedDict (never NamedTuple, except `codepoints()` items which are `CodepointInfo` named tuples).

### Finding

A structured issue (`code`, `severity in {error, warning, info}`, `message`, `line`, `column`); issues are reported, not raised. `manifests.py` defines the shared `_Finding` TypedDict.

### Orchestrator

`synthesis.py`: high-level composition of primitives into composite analyses (`measure_text`, `text_equal`, `explain_diff`, `inspect_text`, ...).

### Leaf module

`network.py`, `encoding.py`, `temporal.py`: stdlib-only, no `exact/` deps. `confusables.py`: generated homoglyph data (never hand-edit; edit `scripts/generate_confusables.py`).

## 5. MCP terms

### Protocol era

`legacy` (`2024-11-05`, `2025-11-25`): handshake era; `initialize` -> `notifications/initialized` -> READY session. `modern` (`2026-07-28`): stateless era; per-request `_meta`, bootstrap `server/discover`, allowlist `discover`/`tools/list`/`tools/call` only. Mapping authority: `_protocol.py::protocol_era()`.

### McpServer

`McpServer`: owns `McpServerConfig`, `ToolRegistry`, `ToolExecutor`, `ConfigManager`, dedicated `Evaluator`, session set. Multiple servers in one process are fully isolated.

### McpSession

`McpSession`: per-connection lifecycle (`UNINITIALIZED` -> `INITIALIZING` -> `READY` -> `CLOSED`), negotiated protocol version, client info, cancellation records. Legacy era only.

### ModernRequestContext

Request-local immutable metadata for modern calls (protocol version, client capabilities, optional validated client info). Never persisted globally; never consulted across requests.

### Tool catalog authority

`TOOL_METADATA` in `schemas.py`: handler/tier/tags/profiles (authority). `TOOL_SCHEMAS`: protocol shape (reviewable separately). `TOOL_HANDLERS`/`TOOL_PROFILES`: derived, never hand-edit. `ToolRegistry`: immutable runtime facade.

### Profile

A named callable subset (12 profiles; `full` = 83 tools default; `agent_core` = 10-tool opt-in experimental surface; `human_math`, `codegg_*` for workflows). Selected via `EGGCALC_MCP_PROFILE` at startup or per-request in `tools/list`.

### Structured result

`structuredContent` (= envelope `result`) for object-rooted schemas via `_split_tool_wire_result()`; `outputSchema` describes the inner `result`, never the envelope. Text envelope retained for compatibility.

### Compatibility shim

Module-level `handle_request()`: deprecated isolated-compat path; new code uses `McpServer` + `McpSession`. `json_query`: deprecated compat adapter over `json_extract()`.

## 6. Distribution terms

### Build manifest

`MODULE_MANIFEST` in `build_single.py`: 38 `ModuleSpec` entries (7 core + 28 exact + 3 mcp) with name, path, group, `depends_on`, inclusion flag. Assembly topologically sorts, strips docstrings/`__all__`, rewrites relative imports, renames colliding entry points (`normalize_main()`, `mcp_main()`).

### Single-file parity

Behavioral equivalence between `pip install eggcalc` and `python3 eggcalc.py` for calculator, exact/, and MCP paths, verified by `build_single.py --validate` and transcript tests.

### CLI text command

One of the 9 `COMMANDS` in `cli.py` (`inspect`/`count`/`regex`/...), lazily loading `exact/` via `importlib`. Distinct from the 83 MCP tools. Listed by `calc --commands`.

## 7. Compatibility mapping from current code and legacy plans

### Current `evaluate` vs `run` confusion

Treat bare `evaluate()` NL/unit failures as correct API-boundary behavior, not bugs. Migrate call sites and plans to `evaluate_raw()`/`run()`/CLI for user-facing expressions.

### Current `normalize.main` / `mcp.main` names

Source uses `cli.main()` and `mcp.server.mcp_main()` (alias `main`); `normalize_main` exists only in the built file. New plans MUST NOT reference `normalize_main` in source/tests.

### Current `TOOL_SCHEMAS` tier duplication

Treat collocated tier/tags in schemas as a review convenience; `TOOL_METADATA` is the authority. Fixture `tests/fixtures/mcp_tool_registry_expected.json` is a compatibility snapshot/golden contract, not an implementation authority.

### Legacy flat `plans/001..043` numbering

Those files are historical interim planning, now under `plans/archive/legacy/`. They MUST NOT be cited as canonical direction. New work cites `plans/000..003`, accepted ADRs, and active subsystem roadmaps.

### Current `ServerState`-style globals

Module-level default evaluator plus global cache exist for convenience. Isolated paths (`McpServer`-owned evaluator, `EggCalcApp`) are authoritative for concurrency-sensitive work.

## 8. Prohibited ambiguous usage

The following phrases SHOULD be removed from new design documents unless qualified:

- "evaluate the expression" when the path (`evaluate` vs `evaluate_raw`/`run`/CLI) matters;
- "the tool registry" when the intended object is `TOOL_METADATA` vs `TOOL_SCHEMAS` vs `ToolRegistry` vs the fixture snapshot;
- "the latest protocol" without naming the era and version;
- "the default profile" without naming `full` vs the request override;
- "the session" when turn, client connection, stdio process, or evaluator instance is intended;
- "structured output" when the envelope-vs-`structuredContent` distinction matters;
- "the build" when manifest validation vs assembly vs install is intended;
- "reload config" when the operation specifically refreshes normalization tables vs MCP `ConfigSnapshot`;
- "closed" for a milestone without a closure record and requirement-to-evidence matrix.

## 9. Review checklist

Any implementation plan or architectural change SHOULD answer:

1. Which evaluation path is involved (`evaluate` vs `evaluate_raw`/`run`/CLI/MCP)?
2. Which object owns the mutable state (server, session, app, module-global)?
3. Is the operation normalize-, evaluator-, unit-, exact-, protocol-, or packaging-scoped?
4. Is a string being mistaken for a canonical name or version?
5. Which evaluator/config generation is active?
6. Which protocol era applies and where is client context stored?
7. Which profile/tool subset is visible, and does every visible tool resolve to one handler/schema/catalog entry?
8. What happens on timeout, cancellation, restart, duplicate delivery, queue overflow, or oversized I/O?
9. What is visible in text envelope vs `structuredContent` vs logs?
10. Which compatibility shim remains, and how is it retired?
11. Does the change preserve stdlib-only, lazy-import, side-effect-free-import, and single-file-manifest constraints?
12. Which generated docs or fixtures must be regenerated (`docs/tool_inventory.md`, registry fixture)?
