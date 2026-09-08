# Authority Inventory (Release 6 — E1)

One authoritative source for every major registry, constant, and contract
in eggcalc.  Drift between the authoritative source and adapter/export
copies is caught by the test suites listed in the "Tests" column.

## Version

| Item | Authoritative source | Adapters / exports | Tests |
|------|---------------------|-------------------|-------|
| Package version | `eggcalc/_version.py` (single source of truth) | `pyproject.toml` reads via `setuptools.dynamic`; `__init__.py` re-exports; `build_single.py` embeds | `test_import_boundaries` (version string present) |
| `eggcalc.__version__` | `eggcalc/_version.py` | Re-exported by `eggcalc/__init__.py` (line 26) | `test_import_boundaries` |

## MCP Protocol Versions

| Item | Authoritative source | Adapters / imports | Tests |
|------|---------------------|-------------------|-------|
| `SUPPORTED_PROTOCOL_VERSIONS` | `eggcalc/_protocol.py` (single source of truth) | `eggcalc/mcp/server.py` and `eggcalc/capabilities.py` import from `_protocol`; no intentional duplicate remains | `test_authority_consolidation::TestProtocolAuthority`, `test_mcp_server` (protocol negotiation) |
| `LATEST_SUPPORTED_PROTOCOL_VERSION` | `eggcalc/_protocol.py` | Re-exported via `mcp/server.py` and `mcp/__init__.py` | `test_authority_consolidation::TestProtocolAuthority`, `test_mcp_server` |
| `McpServerConfig.supported_protocol_versions` | Defaults to `_protocol.SUPPORTED_PROTOCOL_VERSIONS` via `server.py` | — | `test_mcp_server` |

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
| `MAX_INPUT_LENGTH` | `eggcalc/normalize.py:44` | 10 000 | `test_normalize` |
| `MAX_NORMALIZED_LENGTH` | `eggcalc/normalize.py:45` | 20 000 | `test_normalize` |
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

## Tool Definitions (MCP)

| Item | Authoritative source | Tests |
|------|---------------------|-------|
| `TOOL_SCHEMAS` | `eggcalc/mcp/schemas.py:45` | `test_mcp_schema_lint` |
| `TOOL_METADATA` | `eggcalc/mcp/schemas.py:4202` | `test_mcp_schema_lint` |
| `TOOL_PROFILES` | `eggcalc/mcp/schemas.py:5152` (built from `TOOL_METADATA`) | `test_mcp_server` |
| `PROFILE_NAMES` | `eggcalc/mcp/schemas.py:5155` | `test_mcp_server` |

## CLI Command Metadata

| Item | Authoritative source | Tests |
|------|---------------------|-------|
| `COMMANDS` (text command registry) | `eggcalc/cli.py:61` | `test_import_boundaries::TestCommandRegistry` |
| `_COMMAND_NAME_TO_SPEC` (lookup) | `eggcalc/cli.py:120` | `test_import_boundaries::TestCommandRegistry` |
| `_HANDLER_MAP` (handler dispatch) | `eggcalc/cli.py:129` | `test_import_boundaries::TestCommandRegistry` |

## Build Inventory

| Item | Authoritative source | Tests |
|------|---------------------|-------|
| `MODULES_CALC` | `build_single.py` | `test_import_boundaries` |
| `MODULES_EXACT` | `build_single.py` | `test_import_boundaries` |
| `MODULES_MCP` | `build_single.py` | `test_import_boundaries` |

## Result / Error Envelopes

| Item | Authoritative source | Tests |
|------|---------------------|-------|
| `ErrorEnvelope` (MCP tool errors) | `eggcalc/mcp/schemas.py` | `test_mcp_server` |
| `EvaluationError` | `eggcalc/evaluator.py:1416` | `test_evaluator` |
| `TimeoutError` (eval spawn) | `eggcalc/evaluator.py:2705` | `test_evaluator` |
