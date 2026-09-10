# Authority Inventory (Release 6 — E1)

One authoritative source for every major registry, constant, and contract
in eggcalc.  Drift between the authoritative source and adapter/export
copies is caught by the test suites listed in the "Tests" column.

## Version

| Item | Authoritative source | Adapters / exports | Tests |
|------|---------------------|-------------------|-------|
| Package version | `eggcalc/_version.py` (single source of truth) | `pyproject.toml` reads via `setuptools.dynamic`; `__init__.py` re-exports; `build_single.py` embeds | `test_import_boundaries` (version string present) |
| `eggcalc.__version__` | `eggcalc/_version.py` | Re-exported by `eggcalc/__init__.py` (line 26) | `test_import_boundaries` |

## MCP Protocol Versions and Eras

| Item | Authoritative source | Adapters / imports | Tests |
|------|---------------------|-------------------|-------|
| `SUPPORTED_PROTOCOL_VERSIONS` | `eggcalc/_protocol.py` (single source of truth; `LEGACY + MODERN`) | `eggcalc/mcp/server.py` and `eggcalc/capabilities.py` import from `_protocol`; no intentional duplicate remains | `test_authority_consolidation::TestProtocolAuthority`, `test_mcp_server` (protocol negotiation), `test_mcp_modern::TestProtocolEraAuthority` |
| `LEGACY_PROTOCOL_VERSIONS` / `MODERN_PROTOCOL_VERSIONS` | `eggcalc/_protocol.py` | Re-exported via `mcp/server.py` and `mcp/__init__.py` | `test_mcp_modern::TestProtocolEraAuthority` |
| `LATEST_SUPPORTED_PROTOCOL_VERSION` | `eggcalc/_protocol.py` (`"2026-07-28"`) | Re-exported via `mcp/server.py` and `mcp/__init__.py` | `test_authority_consolidation::TestProtocolAuthority`, `test_mcp_server` |
| `LATEST_LEGACY_PROTOCOL_VERSION` | `eggcalc/_protocol.py` (`"2025-11-25"`) | Legacy `initialize` fallback target in `mcp/server.py` | `test_mcp_modern::TestLegacyPreservation` |
| `protocol_era()` / `is_legacy_version()` / `is_modern_version()` | `eggcalc/_protocol.py` (sole version→era mapping) | `mcp/server.py` classifier and dispatch; no inline string comparisons elsewhere | `test_mcp_modern::TestProtocolEraAuthority` |
| Reserved `_meta` key constants | `eggcalc/_protocol.py` (`PROTOCOL_VERSION_META_KEY`, `CLIENT_CAPABILITIES_META_KEY`, `CLIENT_INFO_META_KEY`, `LOG_LEVEL_META_KEY`, `SERVER_INFO_META_KEY`) | `mcp/server.py` envelope validation and `_attach_modern_server_info()` | `test_mcp_modern` (envelope validation, `_meta` stamps) |
| `MODERN_METHODS` allowlist | `eggcalc/_protocol.py` | `_handle_modern_request()` gates `server/discover`, `tools/list`, `tools/call` | `test_mcp_modern::TestModernEnvelopeValidation` |
| `ModernRequestContext` | `eggcalc/mcp/server.py` (frozen dataclass; request-scoped, never persisted) | Re-exported via `mcp/__init__.py` | `test_mcp_modern` |
| `SERVER_INSTRUCTIONS` | `eggcalc/mcp/server.py` (single concise prose authority) | Legacy `initialize` and modern `server/discover` results (identical text) | `test_mcp_structured_results::TestServerInstructions`, `test_mcp_modern::TestModernDiscover` |
| Modern cache-hint policy (`MODERN_CACHE_TTL_MS = 0`, `MODERN_CACHE_SCOPE = "private"`) | `eggcalc/_protocol.py` (final conservative policy) | Modern `server/discover` / `tools/list` results | `test_mcp_structured_results::TestListOrderingAndCache`, `test_mcp_modern` |
| `TOOL_ANNOTATIONS` / `get_tool_annotations()` / `DEFAULT_TOOL_ANNOTATIONS` | `eggcalc/mcp/schemas.py` (catalog authority; uniform read-only/closed-world posture) | `tools/list` emission in every schema-detail mode | `test_mcp_structured_results::TestToolAnnotations` |
| `outputSchema` → `structuredContent` contract | `eggcalc/mcp/schemas.py` (`outputSchema` describes the inner `result`) | `ToolExecutor.call_tool()` emits `structuredContent = text_envelope["result"]` on both eras (object-rooted only) | `test_mcp_structured_results::TestResultBoundary`, `test_mcp_modern` |
| `ToolWireResult` / `_split_tool_wire_result()` / `_validate_output_payload()` | `eggcalc/mcp/server.py` (one result-boundary mapper + validator) | Success/error wire mapping; sanitized `-32000` on output mismatch | `test_mcp_structured_results::TestResultBoundary`, `test_mcp_structured_results::TestOutputValidation` |
| `max_output_bytes` scope | `McpServerConfig.max_output_bytes` bounds the canonical handler-envelope JSON | Both text and structured forms serialize after the envelope passes | `test_mcp_structured_results::TestSizeAccounting`, `test_mcp_modern::TestModernErrorBounds` |
| `McpServerConfig.supported_protocol_versions` | Defaults to `_protocol.SUPPORTED_PROTOCOL_VERSIONS` via `server.py` | `server/discover` versions and `-32022` evidence | `test_mcp_server` |
| Legacy `initialize` negotiation | `McpSession._handle_initialize()` negotiates legacy revisions only | — | `test_mcp_modern::TestLegacyPreservation`, `test_mcp_server` |

## RFC 6901 JSON Pointer Extraction

| Item | Authoritative source | Adapters / compatibility | Tests |
|------|---------------------|-------------------------|-------|
| RFC 6901 traversal/parser | `eggcalc/exact/validate.py::json_extract` (canonical) | `json_query` is a thin compatibility adapter delegating to `json_extract` via `_json_extract_to_query_result`; no independent traversal remains | `test_authority_consolidation::TestJsonPointerParity`, `test_mcp_server::TestJsonQuery` |
| `JsonExtractResult` | `eggcalc/exact/validate.py` | — | `test_authority_consolidation`, `test_bugs_2026_09` |
| `JsonQueryResult` (legacy shape) | Preserved for compatibility (`type` with integers as `"number"`) | Built only by `_json_extract_to_query_result` from the canonical result | `test_authority_consolidation::TestJsonPointerParity` |
| MCP exposure | `json_extract` (tier 2, stable) is the preferred tool; `json_query` (tier 2, deprecated, `full` profile only) remains callable with `recommended_next_tool="json_extract"` | Schemas mark `deprecated: True`; docs Tier lists place the deprecated tool outside Tier 1 | `test_authority_consolidation::TestMcpExposure` |

## SemVer Parsing and Precedence

| Item | Authoritative source | Adapters / compatibility | Tests |
|------|---------------------|-------------------------|-------|
| SemVer parsing (`parse_version`) | `eggcalc/exact/version.py` | — | `test_version_constraint`, `test_authority_consolidation::TestSemVerAuthority` |
| SemVer precedence (`compare_versions`, `version_less_than`, `version_equal`) | `eggcalc/exact/version.py` (build metadata ignored; pre-release sorts lower) | `exact/validate.py::version_compare(scheme="semver")` delegates via `_semver_compare`; no independent SemVer parser remains in `validate.py` | `test_authority_consolidation::TestSemVerAuthority`, `test_version_constraint` |
| Loose numeric comparison | `eggcalc/exact/validate.py::_loose_version_compare` (intentionally separate; not SemVer) | `version_compare(scheme="loose")` only | `test_version_constraint`, `test_authority_consolidation` |
| Cargo constraints | `eggcalc/exact/version.py::check_version_constraint` | — | `test_version_constraint` |

## Subprocess Lifecycle Primitives

| Item | Authoritative source | Adapters / policy owners | Tests |
|------|---------------------|-------------------------|-------|
| `SpawnPermit` (idempotent RAII guard) | `eggcalc/_process.py` | `evaluator._EvalSpawnPermit` and `mcp/tools._SpawnPermit` are aliases; limits/timeouts stay with each subsystem | `test_shared_lifecycle::TestSpawnPermit` |
| Spawn acquire (timeout without consuming a slot) | `eggcalc/_process.py::try_acquire_spawn_permit` | `evaluator` raises `EvaluationError` on `None`; MCP tools return error envelopes on `None` | `test_shared_lifecycle::TestSpawnPermit` |
| Queue close/join + terminate → join → kill → join → close | `eggcalc/_process.py::cleanup_child_process` (returns survivor bool) | `evaluator.evaluate_with_timeout` and `mcp/tools._cleanup_child_process` own orphan registration/caps | `test_shared_lifecycle::TestCleanupChildProcess` |
| Process context selection | `eggcalc/_process.py::get_process_context(prefer)` | Evaluator prefers `spawn`; MCP prefers `fork` only for single-file non-`__main__` | `test_shared_lifecycle::TestProcessContext` |
| Semaphore shutdown close | `eggcalc/_process.py::close_semaphore` | `mcp/tools._close_spawn_semaphore` wraps it (atexit) | `test_shared_lifecycle`, `test_mcp_server::TestDeferredD7SemaphoreCleanup` |

Policy constants (`_MAX_CONCURRENT_EVAL_SPAWNS`, `MAX_CONCURRENT_SPAWNED`, acquire/regex/eval timeouts, orphan caps, error envelopes) remain independently tunable in their owning subsystems by design.

## Exact Public Exports

| Item | Authoritative source | Adapters / exports | Tests |
|------|---------------------|-------------------|-------|
| Lazy public names | `eggcalc/exact/__init__.py::_LAZY_IMPORTS` (single source of truth) | `__all__ = list(_LAZY_IMPORTS)` — no parallel manual list | `test_shared_lifecycle::TestExactExportAuthority` |
| Lazy exact → build manifest coverage | `build_single.py::validate_build_manifest` (check 13 via `_lazy_exact_modules`) | Every `_LAZY_IMPORTS` submodule must be present in `MODULE_MANIFEST` | `test_shared_lifecycle::TestLazyManifestCoverage` |

## Evaluator Limits

| Constant | Authoritative source | Value | Tests |
|----------|---------------------|-------|-------|
| `MAX_EXPONENT` | `eggcalc/evaluator.py:103` | 10 000 | `test_evaluator` |
| `MAX_FACTORIAL` | `eggcalc/evaluator.py:104` | 1 000 | `test_evaluator` |
| `MAX_NESTING_DEPTH` | `eggcalc/evaluator.py:105` | 100 | `test_evaluator`, `test_unit_dimensions` |
| `MAX_RESULT_VALUE` | `eggcalc/evaluator.py:106` | 1e308 | `test_evaluator` |
| `MAX_RESULT_DIGITS` | `eggcalc/evaluator.py:107` | 4 300 | `test_evaluator` |
| `MAX_SHIFT_COUNT` | `eggcalc/evaluator.py:108` | 50 000 | `test_evaluator` |
| `MAX_INPUT_LENGTH` | `eggcalc/evaluator.py:109` | 10 000 | `test_evaluator` |
| `MAX_USER_VARIABLES` | `eggcalc/evaluator.py:110` | 1 000 | `test_evaluator` |
| `DEFAULT_CACHE_SIZE` | `eggcalc/evaluator.py:111` | 1 024 | `test_evaluator` |
| `MAX_CACHE_BYTES` | `eggcalc/evaluator.py:112` | 64 MB | `test_evaluator` |
| `MAX_ORPHANED_PROCESSES` | `eggcalc/evaluator.py:223` | 256 | `test_evaluator` |

Re-exports from `eggcalc/__init__.py:28-31`: `DEFAULT_CACHE_SIZE`, `MAX_EXPONENT`, `MAX_FACTORIAL`, `MAX_RESULT_VALUE`.

## Normalization Limits

| Constant | Authoritative source | Value | Tests |
|----------|---------------------|-------|-------|
| `MAX_INPUT_LENGTH` | `eggcalc/normalize.py:48` | 10 000 | `test_normalize` |
| `MAX_NORMALIZED_LENGTH` | `eggcalc/normalize.py:49` | 20 000 | `test_normalize` |
| `MAX_NESTING_DEPTH` | Re-exported from `eggcalc.evaluator:105` | 100 | `test_normalize` |

Note: `MAX_INPUT_LENGTH` in `exact/validate.py` (100 000), `exact/cargo.py` (200 000), `exact/llm_hygiene.py` (500 000), and `exact/manifests.py` (500 000) are intentionally different limits for their respective subsystems.

## MCP Server Limits

| Constant | Authoritative source | Env var | Tests |
|----------|---------------------|---------|-------|
| `MAX_REQUEST_BYTES` | `eggcalc/mcp/server.py:243` | `EGGCALC_MCP_MAX_REQUEST_BYTES` | `test_mcp_server` |
| `MAX_OUTPUT_BYTES` | `eggcalc/mcp/server.py:244` | `EGGCALC_MCP_MAX_OUTPUT_BYTES` | `test_mcp_server` |
| `MAX_REQUESTS_PER_SECOND` | `eggcalc/mcp/server.py:245` | `EGGCALC_MCP_MAX_REQUESTS_PER_SECOND` | `test_mcp_server` |
| `MAX_REQUEST_ID_LENGTH` | `eggcalc/mcp/server.py:246` | — | `test_mcp_server` |
| `MAX_TOOL_TIMEOUT_SECONDS` | `eggcalc/mcp/server.py:247` | `EGGCALC_MCP_MAX_TOOL_TIMEOUT_SECONDS` | `test_mcp_server` |
| `MAX_CANCELLED_REQUESTS` | `eggcalc/mcp/server.py:248` | `EGGCALC_MCP_MAX_CANCELLED_REQUESTS` | `test_mcp_server` |
| `_MAX_TOOL_WORKERS` | `eggcalc/mcp/server.py:361` | `EGGCALC_MCP_MAX_TOOL_WORKERS` | `test_mcp_server` |
| `SUPPORTED_SCHEMA_KEYWORDS` | `eggcalc/mcp/server.py:255` | — | `test_mcp_schema_lint` |

`McpServerConfig` dataclass defaults reference these module-level constants (single source of truth).

## Calculator Constants and Functions

| Item | Authoritative source | Tests |
|------|---------------------|-------|
| Physical/math constants | `eggcalc/evaluator.py:1763` (`Evaluator.CONSTANTS`) | `test_evaluator` |
| Built-in functions | `eggcalc/evaluator.py:1829` (`Evaluator.FUNCTIONS`) | `test_evaluator` |
| `FUNCTION_MAPPINGS` (NL aliases) | `eggcalc/normalize.py:145` | `test_normalize` |

## Unit Definitions and Aliases

| Item | Authoritative source | Tests |
|------|---------------------|-------|
| `UNIT_BASE` (base-unit factor tables) | `eggcalc/units.py:341` | `test_unit_namespace`, `test_unit_dimensions` |
| `UNIT_ALIASES` (user-facing → canonical) | `eggcalc/units.py:953` | `test_unit_namespace`, `test_unit_dimensions` |
| `UNIT_CATEGORIES` (unit → category) | `eggcalc/units.py:1680` + `1717` | `test_unit_dimensions` |
| `_CATEGORY_DIMENSIONS` (category → Dimension) | `eggcalc/units.py:220` | `test_unit_dimensions` |
| `TEMPERATURE_CONVERSIONS` | `eggcalc/units.py:1505` | `test_unit_dimensions` |
| `UnitRegistry` (structural registry) | `eggcalc/units.py:310` (built by `build_unit_registry()`) | `test_unit_dimensions` |

## Tool Definitions (MCP) — Plan 040 consolidated authorities
| Item | Authoritative source | Adapters / derived views | Tests |
|------|---------------------|--------------------------|-------|
| Catalog: names + handler locators + selection metadata (category/tier/tags/profiles/aliases/exposure/harness/cost/stability/composite) | `eggcalc/mcp/schemas.py::TOOL_METADATA` (validated by `_validate_catalog_metadata()`) | `TOOL_HANDLERS` derived via `server._build_tool_handlers()`; `get_tool_tier()`/`get_tool_tags()`/`get_tool_handler_name()` accessors | `test_tool_inventory` (catalog/protocol key parity, handler identity, tier/tag single authority) |
| Protocol shape: description/inputSchema/outputSchema/deprecated | `eggcalc/mcp/schemas.py::TOOL_SCHEMAS` (no tier/tags copies) | `compact_schema()`/`normal_schema()` transforms; `tools/list` full/normal/compact rendering | `test_mcp_schema_lint`, `test_tool_inventory::TestTierConsistency`, `test_tool_inventory::TestStandardToolShape` |
| Runtime handlers | Derived `eggcalc/mcp/server.py::TOOL_HANDLERS` compatibility view (eager `getattr(tools)` + `_mcp_` single-file fallback, fail-fast) | `ToolRegistry.handlers` (frozen); `ToolExecutor` dispatch | `test_tool_inventory`, `test_mcp_server`, `test_build_single` (package/single-file parity) |
| Profile lists | Derived `eggcalc/mcp/schemas.py::TOOL_PROFILES` via `_build_profiles()` from catalog | `ToolRegistry.profiles` (frozen); `get_profile_tools()` | `test_tool_inventory`, `test_mcp_server` |
| `PROFILE_NAMES` | `eggcalc/mcp/schemas.py` (recommended order) | — | `test_mcp_server` |
| Annotations | `eggcalc/mcp/schemas.py::TOOL_ANNOTATIONS`/`get_tool_annotations()` (uniform posture; not duplicated in metadata) | `tools/list` emission in every schema-detail mode | `test_mcp_structured_results::TestToolAnnotations` |
| Public-name golden fixture | `tests/fixtures/mcp_tool_registry_expected.json` — compatibility snapshot only (`schema_version`, `tool_count`, sorted `tools`) | Never constructs runtime behavior; CI diff makes additions/removals explicit | `test_tool_inventory::TestSourceOfTruthConsistency`, `TestToolRegistryFixture` |
| Generated inventory | `docs/tool_inventory.md` — documentation artifact only, generated from runtime catalog via `scripts/generate_mcp_docs.py` | `generate_mcp_docs.py --check` in CI | `test_tool_inventory::TestDocGenerator` |
| `tools/list` emission order | Canonical sorted-name order in `_handle_list_tools()` (stable across source reorderings, both eras) | — | `test_mcp_structured_results::TestListOrderingAndCache`, `test_mcp_modern::TestModernToolsList` |
| Standard Tool keys | `name`/`description`/`inputSchema`/`annotations` at standard locations (both eras; selection metadata from catalog) | `tier`/`tags`/`category`/`llm_exposure`/`cost` still emitted top-level for backward compat, sourced from metadata | `test_tool_inventory::TestStandardToolShape` |

## CLI Command Metadata

| Item | Authoritative source | Tests |
|------|---------------------|-------|
| `COMMANDS` (text command registry) | `eggcalc/cli.py:61` | `test_import_boundaries::TestCommandRegistry` |
| `_COMMAND_NAME_TO_SPEC` (lookup) | `eggcalc/cli.py:120` | `test_import_boundaries::TestCommandRegistry` |
| `_get_handler` / `_handler_cache` (lazy handler dispatch) | `eggcalc/cli.py` | `test_import_boundaries::TestCommandRegistry` |

## Build Inventory

| Item | Authoritative source | Tests |
|------|---------------------|-------|
| `MODULE_MANIFEST` (module ordering, deps, validation) | `build_single.py` (single source of truth) | `test_import_boundaries`, `test_build_manifest_graph` |
| `MODULES_CALC` / `MODULES_EXACT` / `MODULES_MCP` | Derived views generated from `MODULE_MANIFEST` (never manually maintained) | `test_import_boundaries` |

## Normalization Trace Contract

| Item | Authoritative source | Tests |
|------|---------------------|-------|
| `NormalizationTrace` / `NormalizationStep` (trace shape) | `eggcalc/normalize.py` | `test_normalization_trace` |
| Trace stage vocabulary (`sanitize` … `validation`) | `eggcalc/normalize.py::trace_normalization` docstring | `test_normalization_trace::TestTraceStages` |
| Trace/normal-path parity | Same implementation via private `_trace` collector | `test_normalization_trace::TestTraceParity`, `test_build_single` (`--explain` parity) |
| `--explain` / `--commands` CLI surface | `eggcalc/cli.py` (`_explain_expression`, `_print_commands`) | `test_cli_compatibility` |

## Result / Error Envelopes

| Item | Authoritative source | Tests |
|------|---------------------|-------|
| `ErrorEnvelope` (MCP tool errors) | `eggcalc/mcp/schemas.py` | `test_mcp_server` |
| `EvaluationError` | `eggcalc/evaluator.py:1416` | `test_evaluator` |
| `TimeoutError` (eval spawn) | `eggcalc/evaluator.py:2705` | `test_evaluator` |
