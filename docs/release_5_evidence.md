# Release 5 — Evidence Record

## Runtime

- **Date:** 2026-07-21
- **Python:** 3.14.2 (CPython)
- **Platform:** macOS-26.5.1-x86_64-i386-64bit-Mach-O
- **eggcalc version:** 2.0.0 (unreleased)

## Checks Run

| Check | Command | Result |
|-------|---------|--------|
| Ruff lint | `ruff check eggcalc tests` | All checks passed |
| Black format | `black --check eggcalc tests` | All done, 89 files unchanged |
| Type check | `mypy eggcalc --ignore-missing-imports` | Success, no issues |
| Single-file build | `python build_single.py` | Built successfully |
| Single-file smoke | `python eggcalc.py "5+3"` | Output: 8 |

## Test Suite

- **Total collected:** 3230 (3197 passed, 33 skipped)
- **Release 5 isolation tests:** 98 passed
- **Release 5 config loading tests:** 4 passed (import-error precision)
- **All checks pass:** ruff, black, mypy, single-file build, smoke

### Release 5 Test Classes (98 tests in test_release5_isolation.py)

| Test Class | Tests | Covers |
|------------|-------|--------|
| TestMcpServerConfig | 8 | Defaults, env loading, immutability, validation |
| TestToolRegistry | 13 | Handler ownership, profiles, close-match, schemas |
| TestToolExecutor | 6 | Dispatch, timeout, unknown tool, close, custom config |
| TestConfigSnapshot | 3 | Defaults, immutability, custom values |
| TestConfigManager | 5 | Current, replace, generation, invalidation |
| TestMcpServer | 11 | Creation, sessions, isolation, close, diagnostic |
| TestEvaluatorPolicyIsolation | 10 | Random rejection, independence, default preservation |
| TestMultiSessionIsolation | 5 | Cancellation, lifecycle, shared request IDs |
| TestConcurrency | 5 | Parallel execution, worker bounds, concurrent creation |
| TestShutdown | 5 | Resource reclamation, idempotent close, post-close rejection |
| TestProtocolLifecycle | 3 | Full handshake, tools/list, profiles/list |
| TestConfigSnapshotUnits | 4 | Units field, defaults, immutability |
| TestEnhancedDiagnostics | 8 | Active workers, session count, orphan count, queue info |
| TestConfigGeneration | 2 | get_config_generation, cache clear increments |
| TestConcurrencyStress | 6 | Cancellation storm, repeated timeout, concurrent init, malformed traffic |
| TestSaturationRejection | 4 | Queue full rejection, recovery after drain, config clamping, diagnostic |
| TestOversizedOutputStorm | 2 | Output truncation, no corruption after oversized outputs |

### Additional Release 5 Tests (4 in test_config_loading.py)

| Test | Covers |
|------|--------|
| test_syntax_error_in_config propagates | Syntax errors in config file are not swallowed |
| test_runtime_error_in_config propagates | Runtime exceptions in config are not swallowed |
| test_missing_config_is_silent | Absent eggcalc_config module is silently ignored |
| test_internal_import_error_propagates | ImportError inside config file is not confused with missing module |

## Acceptance Criteria Verification

### Ownership (5/5)

- [x] MCP request dispatch owned by explicit `McpServer` object
- [x] Server policy via immutable `McpServerConfig` frozen dataclass
- [x] Tool registry and executor ownership explicit (`ToolRegistry`, `ToolExecutor`)
- [x] Production paths use `McpServer.handle_request(session=...)`
- [x] Mutable process-global state cataloged in `architecture/mutable_state_inventory.md`

### Behavioral Isolation (5/5)

- [x] Starting/using/closing MCP does not change ordinary library behavior (10 tests in TestEvaluatorPolicyIsolation)
- [x] Two application instances with conflicting config (test_two_servers_independent_config)
- [x] Two server instances with different profiles (test_server_multiple_instances_isolated)
- [x] Two sessions do not share lifecycle/cancellation state (5 tests in TestMultiSessionIsolation)
- [x] Configuration changes in one instance do not affect another (test_two_servers_independent_config)

### Configuration Correctness (5/5)

- [x] Configuration parsed and validated before activation (ConfigManager.replace)
- [x] Activation is atomic (ConfigManager lock)
- [x] Failed activation leaves prior snapshot intact (test_manager_invalidate_from_default)
- [x] Missing eggcalc_config vs internal failure distinguished (4 tests in TestImportErrorPrecision)
- [x] Config generation explicit (get_config_generation, _config_generation counter)

### Cache Correctness (4/4)

- [x] Cached results cannot cross config/policy boundaries (generation-keyed, subprocess-based MCP tools)
- [x] Cache ownership documented and tested (TestConfigGeneration)
- [x] Cache bounds enforced (MAX_CACHE_BYTES = 64MB, LRU eviction)
- [x] Clearing one instance does not corrupt another (EggCalcApp instance-local caches)

### Concurrency and Lifecycle (5/5)

- [x] Multi-instance and multi-session concurrency suites pass (TestConcurrency: 5, TestConcurrencyStress: 6)
- [x] Saturation produces bounded rejection (TestSaturationRejection: 4, max_tool_queue_size)
- [x] Cancellation/timeout storms bounded (test_cancellation_storm: 50 rapid cancels, test_repeated_timeout)
- [x] Shutdown deterministic and idempotent (TestShutdown: 5)
- [x] No worker threads or orphan processes remain after shutdown (test_close_cleans_up_all_servers)

### Compatibility and Documentation (4/4)

- [x] Package and single-file MCP transcripts match (test_package_and_single_file_transcripts_match)
- [x] Sessionless API deprecation documented (DeprecationWarning, architecture/mcp.md, AGENTS.md)
- [x] Architecture documentation describes ownership and thread-safety (architecture/mcp.md, overview.md, mutable_state_inventory.md)
- [x] Changelog records public API and behavior changes (CHANGELOG.md)

### Evidence (3/3)

- [x] This evidence file records full-suite, stress-suite, platform, and release-surface results
- [x] Test evidence includes multiple independent server and session instances
- [x] Residual shared state listed in architecture/mutable_state_inventory.md with justification

## Single-File Artifact

- **Built:** eggcalc.py (core: 4, exact: 25, MCP: 3 modules)
- **Smoke test:** `python eggcalc.py "5+3"` → `8`
- **New classes in single-file:** McpServerConfig, ToolRegistry, ToolExecutor, ConfigSnapshot, ConfigManager, McpSession, McpServer, create_evaluator, get_config_generation
- **Bounded queue:** max_tool_queue_size field in McpServerConfig, _total_inflight counter in ToolExecutor, rejection when capacity exceeded

## Residual Shared State (Justified)

| Object | Owner | Justification |
|--------|-------|---------------|
| `_cache` (evaluator LRU) | Module-level, cleared atomically | Shared lookup cache with generation tracking; cleared on config change |
| `_mcp_mode` (evaluator flag) | Module-level, set once at startup | Process-wide mode; safe under singleton-usage assumption |
| `_config_loaded` (evaluator) | Module-level, set once | Prevents re-entry; safe under single-threaded init |
| `_random_generator` (evaluator) | Module-level, seed-once | Deterministic RNG for non-MCP use; MCP uses dedicated evaluator |
| `_UNIT_ALIASES`, `_CONSTANTS` | Module-level, immutable | Read-only lookup tables; never mutated after import |

All residual state is documented in `architecture/mutable_state_inventory.md` with per-item justification.
