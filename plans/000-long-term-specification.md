# eggcalc Long-Term Architecture and Product Specification

Status: canonical long-term implementation directive

Companion documents:

- `plans/001-terminology-and-domain-model.md`
- `plans/002-long-term-roadmap.md`
- `plans/003-planning-process.md`

This document defines the intended end state for eggcalc. It establishes product scope, domain boundaries, architectural ownership, protocol expectations, security properties, interoperability requirements, and acceptance criteria. The roadmap decomposes this specification into ordered execution phases. The terminology document is normative whenever older plans, code, or documentation use overlapping terms such as evaluate, normalize, tool, profile, snapshot, or session.

The keywords MUST, MUST NOT, REQUIRED, SHOULD, SHOULD NOT, and MAY are normative.

## 1. Product definition

eggcalc is a natural-language math calculator (CLI, Python library, MCP server) plus a deterministic Unicode text-analysis suite. Standard library only, zero production runtime dependencies. `build_single.py` assembles everything into one portable `eggcalc.py` single file.

The same architecture MUST support three consumption forms without creating separate products:

```text
CLI library
    calc "expr" / python -m eggcalc / python3 eggcalc.py
        |-- normalize (NL + units -> Python syntax)
        `-- evaluator (safe AST, never eval())

Python library
    evaluate / evaluate_raw / evaluate_cached / evaluate_async /
    evaluate_with_timeout / EggCalcApp

MCP server (stdio JSON-RPC)
    calc --mcp -> McpServer + McpSession -> 83 deterministic tools
        |-- schemas (protocol shape)
        `-- tools (lazy exact/ bridge) -> exact/ (28 modules)
```

## 2. Primary product goals

eggcalc MUST provide:

1. A fast, low-friction calculator: plain-English math (`"five plus three"`) and unit-aware evaluation (`"30m + 100ft in meters"`).
2. A safe evaluation core: Python `ast` parsing, never `eval()`, with explicit DoS limits.
3. A deterministic text/Unicode utility suite (`exact/`, 28 modules): pure functions, same input -> same output, no I/O, no network, no LLM calls.
4. A dual-era MCP server over stdio: legacy handshake era (`2024-11-05`, `2025-11-25`) plus finalized modern stateless era (`2026-07-28`), with typed `structuredContent` results and deterministic `tools/list`.
5. A curated tool surface: all 83 tools callable under an appropriate profile; `full` for compatibility, small profiles (`agent_core`, `codegg_*`, `human_math`) for agents and harnesses.
6. Two distribution paths: PyPI wheel (`pip install eggcalc`) and single-file `eggcalc.py`, with generated parity.
7. Lazy, side-effect-free imports: `import eggcalc` loads only the seven core modules; CLI/MCP load `exact/` handlers via `importlib` on dispatch.
8. Observable normalization: `trace_normalization()` / `calc --explain` explains the pipeline without evaluating.

## 3. Non-goals

eggcalc is not initially:

- a general-purpose computer-algebra system;
- a units database beyond the declared 150-`UnitSpec` registry and 17 categories;
- a networked service (stdio is the production MCP transport; no HTTP/OAuth merely because modern MCP supports it);
- an embedding/vector/semantic-search tool-discovery service;
- a plugin framework, dependency-injection framework, or metaclass/decorator registration system;
- a universal `utility(operation=...)` mega-tool hiding unrelated domains behind one schema;
- an MCP Apps/Tasks/prompts/resources/sampling/elicitation/roots/subscriptions platform unless a separate product requirement exists.

eggcalc MAY integrate with those systems where they support calculation or deterministic text analysis. It MUST NOT absorb their complete product scope.

## 4. Architectural principles

### 4.1 One architecture, progressively enabled

CLI, library, single-file, and MCP server MUST share the same `Evaluator`, `UnitRegistry`, normalization tables, and `exact/` implementations. The single-file build is an assembly transform, not a fork.

### 4.2 Explicit ownership

Every mutable record and registry MUST have one canonical owner documented in `architecture/authority_inventory.md`. `architecture/mutable_state_inventory.md` tracks process-globals. New registries MUST NOT duplicate authority.

### 4.3 Two evaluation paths stay distinct

`evaluate()` is direct AST evaluation of already-normalized Python math. `evaluate_raw()` / `evaluate_cached()` / `evaluate_async()` / `EggCalcApp` / CLI / MCP `math_eval` run the full normalize-then-evaluate pipeline. Plans and code MUST NOT conflate them; `^` semantics differ by path (XOR in `evaluate()`, exponentiation in `evaluate_raw()`/CLI).

### 4.4 Determinism before magic

`exact/` functions report findings with bounded inputs; they do not raise for content issues, fetch networks, touch filesystems (`path_tools.py` is lexical only), or call LLMs. MCP handlers validate against JSON Schema plus signature, enforce timeouts, and run on a bounded worker pool.

### 4.5 Progressive disclosure

Large catalogs, tool schemas, skill bodies, logs, and artifacts SHOULD be represented by metadata and handles until explicitly requested. `tools/list` ordering MUST be deterministic; modern list/discovery results carry conservative cache hints.

### 4.6 Correctness before transparent magic

Explicit unit dimensions, affine temperature math, structural angle guards, `UnitPolicy` enforcement in `visit_Call`, and protocol-era classification MUST be preferred over silent coercion or session-state inference.

## 5. Canonical subsystem model

```text
Deployment (one process)
|-- calculator-core (normalize, evaluator, units, _process, _protocol, capabilities)
|-- exact-utilities (28 deterministic modules + lazy __init__)
|-- mcp-server (schemas, tools, server, sessions, profiles, eras)
`-- cli-distribution (cli, __main__, build_single, install, packaging, docs)
```

The coordinator/execution-node distinction from codegg does not apply. The analogue is: `McpServer` owns config/registry/executor/evaluator/sessions; `McpSession` owns per-connection lifecycle; `EggCalcApp` owns per-instance evaluator plus cache; module-level `evaluate*` functions own the global default evaluator plus global cache.

## 6. Canonical identity relationships

```text
Expression
  -> NormalizationTrace (stages, no evaluation)
  -> UnitValue(value, unit) + Dimension (8 SI axes + structural angle flag)
  -> Evaluator (CONSTANTS 55, FUNCTIONS 104, UnitPolicy 11 members)

Tool call
  -> McpServer (config, registry, executor, evaluator, sessions)
  -> McpSession (UNINITIALIZED -> INITIALIZING -> READY -> CLOSED, legacy era)
  -> ModernRequestContext (request-local, modern era, never persisted globally)
  -> ToolRegistry + ToolExecutor -> exact/ function -> TypedDict result
```

A session MUST bind tool calls to one evaluator/config generation from validation through execution. A modern request MUST derive client context from request-local `_meta` only.

## 7. Current foundation and required evolution

The existing codebase already contains the dual-era MCP server, 83-tool catalog with tier/profile metadata, `UnitValue` arithmetic with auto-conversion, `NormalizationTrace` observability, lazy CLI/MCP loading, single-file assembly with manifest validation, and generated-docs drift checks.

The primary evolution is not another rewrite. It is: keep the calculator semantically correct, keep the MCP surface protocol-current and discoverable, keep one catalog authority, and keep the distribution footprint small — with closure evidence for each step.

Compatibility shims (`json_query` adapter, module-level `handle_request()`, `normalize.main`/`print_help` PEP 562 re-exports) MUST be progressively classified and reduced, never silently expanded.

## 8. Deployment profiles and configuration

CLI loads cwd-local `eggcalc_config.py` via `maybe_load_cli_config()` only for expression/REPL modes — never for `--help`/`--version`/`--capabilities`/`--mcp`/text commands. Library loads only with `EGGCALC_LOAD_CONFIG=1` or explicit `load_user_config()`. `import eggcalc` MUST stay side-effect-free.

`McpServerConfig` is a frozen dataclass with clamped defaults (1 MB request/output caps, 16 tool workers, queue 32, 30 s max tool timeout, 10 req/s rate limit), built via `from_environment()`. Config changes flow through validated `ConfigCandidate` -> immutable `ConfigSnapshot` applied atomically by `ConfigManager`.

## 9. Calculator, units, and exact/ model

- `Dimension` models 8 SI base axes plus a structural `angle` flag; `rad + 1`, angle-squared, and angle-times-angle are rejected.
- Temperature uses affine conversion (`scale_to_base` / `offset_to_base`; Kelvin is base).
- Power binds units: `5m ** 2` -> `5 m**2`, `(5m)**2` -> `25.0 m**2`.
- Same-dimension `%` returns a remainder in the divisor unit; `//` returns a dimensionless quotient; mismatched dimensions raise.
- `exact/` results are plain-dict TypedDicts (`result["equal"]`, never `result.equal`; `codepoints()` items are `CodepointInfo` named tuples).
- Each `exact/` module enforces its own bounded-input caps; findings use the shared `_Finding` vocabulary (`code`/`severity`/`message`/`line`/`column`).

## 10. MCP boundary

MCP MUST be implemented over stdio JSON-RPC without external SDK dependencies.

Version-to-era mapping lives in `_protocol.py` (`protocol_era()`); it is the sole authority. Legacy era requires `initialize` + `notifications/initialized` before tools (early tools -> `-32600`). Modern era is stateless via `params._meta`; bootstrap is `server/discover`; allowlist is `discover`/`tools/list`/`tools/call` only.

`tools/call` returns the text envelope plus `structuredContent` (= envelope `result`) for object-rooted schemas via `_split_tool_wire_result()`; `outputSchema` describes the inner `result`, never the envelope. Catalog authority is `TOOL_METADATA` in `schemas.py`; protocol shape is `TOOL_SCHEMAS`. `TOOL_HANDLERS`/`TOOL_PROFILES` are derived — never hand-edit.

## 11. Distribution and storage requirements

All native protocol operations MUST be versioned and capability-negotiated. Large output MUST remain behind bounded handles. `build_single.py` `MODULE_MANIFEST` (38 `ModuleSpec` entries: 7 core + 28 exact + 3 mcp) is the single source of truth; `validate_build_manifest()` checks duplicates, missing files, unknown deps, cycles, reachability, residual imports, and lazy-exact coverage.

SQLite is not used; caches are bounded in-memory (global LRU 1,024 entries / 64 MB cap; per-`EggCalcApp` instance cache). Timeout evaluation runs in child processes bounded by a semaphore (4 concurrent spawns; at most 256 orphaned timeout processes).

## 12. CLI target behavior

CLI output is result-only — no echo, arrows, or decoration (REPL included). Mode classification happens before any cwd-local config loading. `calc --commands` lists the 9 CLI text commands (distinct from the 83 MCP tools). `trace_normalization()` explains without evaluating.

## 13. Reliability and recovery

Timeout/child-process cleanup, bounded worker queues, atomic config swaps, immutable `RuntimeContext` capture before dispatch, and deterministic cancellation MUST preserve isolation: multiple `McpServer` instances and `EggCalcApp` instances coexist safely with different configs, registries, and evaluator policies.

A failed config refresh MUST preserve the prior valid snapshot. A failed normalization MUST NOT evaluate. A failed tool call MUST return a deterministic protocol error, never a partial envelope.

## 14. Security requirements

Safe AST evaluation (never `eval()`), token whitelist before eval, length/nesting caps, exponent/factorial/shift/result-size caps, secret redaction at every protocol/logging boundary, bounded request/output sizes, rate limits, path validation staying within declared roots, and no automatic script execution for discovered assets.

## 15. Observability

`trace_normalization()` stage-by-stage traces, `detect_capabilities().to_json()` runtime snapshots, deterministic evaluation corpus measurements, MCP transcript fixtures, registry invariants, and size/footprint measurements. Domain identifiers (`UnitSpec` canonical names, tool names, profile names) remain canonical.

## 16. System invariants

The implementation MUST preserve the following invariants:

1. Production runtime is standard library only; `dependencies = []` remains true.
2. `import eggcalc` is side-effect-free and loads only the seven core modules.
3. Runtime code lives only in core, `exact/`, or `mcp/` or the single-file build breaks.
4. `evaluate()` rejects natural language and unit suffixes; `evaluate_raw()`/CLI handle NL + units.
5. `^` means XOR in `evaluate()`, exponentiation in `evaluate_raw()`/CLI; `xor`/`bitxor` word forms mean XOR through the full pipeline.
6. `r`/`R` is the gas constant, not Rankine.
7. Structural angle algebra stays rejected (`rad + 1`, angle-squared, angle-times-angle).
8. Canonical `round()` takes `round(n)` / `round(n, ndigits)` / `ndigits=`; omitted precision returns `int`.
9. `exact/` functions stay pure, bounded, and side-effect-free.
10. `TOOL_METADATA` is the catalog authority; `protocol_era()` is the version-to-era authority.
11. All 83 existing tool names remain callable under an appropriate profile unless a documented deprecation policy says otherwise.
12. `full` remains available for backward compatibility.
13. Legacy MCP handshake behavior remains supported while modern support exists.
14. stdio remains the production MCP transport for this line of work.
15. `structuredContent` and compatibility JSON text encode the same logical result.
16. Modern requests never depend on legacy session-only state.
17. CLI output stays result-only.
18. Config loading stays lazy per Section 8.
19. Single-file behavior remains equivalent for supported MCP eras and tool responses.
20. `docs/tool_inventory.md` is generated, never hand-edited.

## 17. Completion criteria

This long-term directive is complete when:

- a user can evaluate NL math and unit expressions from CLI, library, and single-file paths with identical semantics;
- an MCP client of either era can discover and call every tool it is profiled for, with typed results and deterministic ordering;
- an agent presented with the catalog selects appropriate tools with measured context footprint and selection quality;
- the single-file distribution reproduces package behavior for calculator, exact/, and MCP paths;
- the system has explicit quotas, recovery, migration, backup, revocation (where applicable), and protocol-compatibility tests with closure evidence.

## 18. Research anchors

Implementation work should consult current primary specifications rather than copying assumptions indefinitely:

- MCP `2026-07-28` release: `https://blog.modelcontextprotocol.io/posts/2026-07-28/`
- MCP August 2026 roadmap: `https://blog.modelcontextprotocol.io/posts/mcp-roadmap/`
- MCP TypeScript SDK protocol-era guidance: `https://ts.sdk.modelcontextprotocol.io/v2/protocol-versions`
- MCP tool schema/annotation reference: `https://modelcontextprotocol.io/specification/2025-11-25/schema`
- Anthropic, "Introducing advanced tool use": `https://www.anthropic.com/engineering/advanced-tool-use`
- Anthropic, "Writing effective tools for AI agents": `https://www.anthropic.com/engineering/writing-tools-for-agents`

These references inform interoperability. eggcalc's evaluation semantics, unit registry, catalog authority, and control-plane ownership remain defined by this specification.
