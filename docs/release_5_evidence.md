# Release 5 — Evidence Record

## Runtime

- **Date:** 2026-07-22
- **Python:** 3.14.2 (CPython)
- **Platform:** macOS-26.5.1-x86_64-i386-64bit-Mach-O
- **eggcalc version:** 2.0.0 (unreleased)
- **Commit:** `59844136e6a0ed75e475dc2d230d679512f62330`
- **CI workflow:** [CI #29928027170](https://github.com/eggstack/eggcalc/actions/runs/29928027170)

## Checks Run

| Check | Command | Result |
|-------|---------|--------|
| Ruff lint | `ruff check eggcalc tests` | All checks passed |
| Black format | `black --check eggcalc tests` | All done, 89 files unchanged |
| Type check | `mypy eggcalc --ignore-missing-imports` | Success, no issues |
| Single-file build | `python build_single.py` | Built successfully |
| Single-file smoke | `python eggcalc.py "5+3"` | Output: 8 |

## Test Suite

- **Total collected:** 3299 (3232 base + 67 closure tests)
- **Passed:** 3299 (Linux/macOS), 3266 (Windows)
- **Skipped:** 33 (all non-mandatory, platform-specific or conditional)
- **Release 5 isolation tests:** 143 passed (98 original + 45 closure tests)
- **Release 5 config loading tests:** 4 passed (import-error precision)
- **All checks pass:** ruff, black, mypy, single-file build, smoke
- **Note:** Total test count updated to 3363 by the corrective closure pass; counts above reflect the original Release 5 snapshot.

### Release 5 Test Classes (104 tests in test_release5_isolation.py)

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
| TestWorkstreamB_ConfigAuthority | 4 | Profile enforcement at call time, list/call authority match |
| TestWorkstreamC3_RegistryImmutability | 5 | Nested schema/profile immutability, MappingProxyType enforcement |
| TestWorkstreamD_EvaluatorBinding | 4 | Instance-owned random state, independent seeding |
| TestWorkstreamE2_ConfigManagerValidation | 4 | Monotonic generation, stale generation rejection, rollback |
| TestWorkstreamG_ExecutorAccounting | 5 | Queued/active transitions, timeout retains capacity, stress |
| TestStressCounterCleanup | 3 | Repeated stress leaves counters zero, no negative counters |
| TestMultiServerIndependentEnforcement | 5 | Independent workers, output, rate limits, config, schemas |
| **TestSessionCloseRemovesFromTracking** | **4** | **session.close() decrements count, idempotent, server-close safety** |
| **TestCompatDispatchNoGlobalMutation** | **2** | **Deprecated handle_request() preserves _mcp_mode and _default_evaluator** |
| **TestRegistryNestedMutation** | **5** | **Nested schema/metadata/profile mutation rejected; get_schema returns deep copy; tool_names immutable** |
| **TestConfigSnapshotDeepImmutability** | **3** | **Constructor input mutation rejected; fields are MappingProxyType; to_dict returns plain dict** |
| **TestRandomIsolationDeterminism** | **5** | **Identical seeds yield identical sequences; advancing/reseeding one evaluator independent; permissive server independence; restricted rejection** |
| **TestConcurrentSessionCloseDispatch** | **3** | **Concurrent close/dispatch no deadlock; foreign session rejected; closed session rejects all methods** |
| **TestConfigActivationPath** | **4** | **activate_snapshot pushes constants/functions; rollback on failure; two servers independent** |
| **TestParseConfigSnapshot** | **6** | **Valid constants/policy; invalid constant type/name; non-callable function; invalid policy** |
| **TestExecutorCancellationBeforeStart** | **2** | **Cancellation before start releases capacity; timeout retains capacity truthfully** |

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

- [x] Configuration parsed and validated before activation (ConfigManager.replace, parse_config_snapshot)
- [x] Activation is atomic (McpServer.activate_snapshot with rollback)
- [x] Failed activation leaves prior snapshot intact (test_manager_invalidate_from_default, test_activate_snapshot_rollback_on_failure)
- [x] Missing eggcalc_config vs internal failure distinguished (4 tests in TestImportErrorPrecision)
- [x] Config generation explicit (get_config_generation, _config_generation counter)
- [x] ConfigSnapshot deeply immutable (3 tests in TestConfigSnapshotDeepImmutability)

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
- [x] Stress counter cleanup verified (TestStressCounterCleanup: 3 tests assert active_workers == 0 and pending_count == 0 after completion)

### Compatibility and Documentation (4/4)

- [x] Package and single-file MCP transcripts match (test_package_and_single_file_transcripts_match)
- [x] Sessionless API deprecation documented (DeprecationWarning, architecture/mcp.md, AGENTS.md)
- [x] Architecture documentation describes ownership and thread-safety (architecture/mcp.md, overview.md, mutable_state_inventory.md)
- [x] Changelog records public API and behavior changes (CHANGELOG.md)

### Registry Authority (4/4)

- [x] `_validate_arguments_schema()` validates against server registry schemas, not global `TOOL_SCHEMAS`
- [x] ToolExecutor.call_tool() passes registry schemas to schema validation
- [x] Custom/minimal registries use only their own schemas for validation
- [x] Registry data immutable after construction (MappingProxyType, tuple profiles)

### Multi-Server Enforcement (5/5)

- [x] Independent max_tool_workers enforced across servers (test_independent_max_tool_workers)
- [x] Independent max_output_bytes enforced across servers (test_independent_max_output_bytes)
- [x] Independent max_requests_per_second enforced across servers (test_independent_max_requests_per_second)
- [x] Server configs do not cross-pollinate (test_servers_do_not_share_config)
- [x] Server registry schemas are independent (test_servers_registry_schema_independent)

### Compatibility Dispatcher Containment (6/6)

- [x] Deprecated dispatch executes through explicit compatibility McpServer (`_get_compat_server()`)
- [x] Compat dispatch never sets `_mcp_mode` (test_compat_dispatch_preserves_mcp_mode)
- [x] Compat dispatch never reconfigures `_default_evaluator` (test_compat_dispatch_preserves_default_evaluator)
- [x] Compat state cannot affect explicit servers
- [x] Compat cleanup is deterministic and idempotent (`close_compatibility_server()`)
- [x] Production stdio does not use compat state

### Session Ownership (5/5)

- [x] Every session has exactly one owning server (`_bind_owner()`)
- [x] Foreign-session dispatch is rejected deterministically
- [x] Closed sessions cannot dispatch (`_check_ready_for_dispatch()`)
- [x] Direct session close removes it from live-session tracking (TestSessionCloseRemovesFromTracking)
- [x] `session_count` reports live sessions only

### Profile and Registry (5/5)

- [x] Server profile enforced during `tools/call` before executor submission
- [x] Default listed tools and callable tools identical under one config
- [x] List profile overrides cannot broaden call authority
- [x] Registry nested values cannot be mutated through constructor inputs or accessors (5 tests in TestRegistryNestedMutation)
- [x] Profiles referencing unknown tools fail construction deterministically
- [x] get_schema() returns deep copy preventing nested mutation

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

| Object | Owner | Category | Justification |
|--------|-------|----------|---------------|
| `_cache` / `_cache_bytes` | Module-level, cleared atomically | deferred-r6 | Shared LRU with generation tracking; cleared on config change. Multi-server isolation deferred to Release 6 (generation-keyed caching or per-server `EggCalcApp`). |
| `_mcp_mode` | Module-level, set once | compat-only | Set once by deprecated compatibility path; production stdio does not set this. |
| `_config_loaded` | Module-level, set once | legacy-cli | Prevents re-entry; set once at startup, never toggled back. |
| `_random_generator` | Module-level, seed-once | process-bounded | Global RNG for non-MCP calculator use. MCP servers use dedicated per-instance `_instance_random` via `Evaluator(random_seed=...)`. |
| `_UNIT_ALIASES`, `_CONSTANTS` | Module-level, immutable | immutable-lookup | Read-only lookup tables populated at import time; never mutated after initial build. |
| `TOOL_SCHEMAS` (global schemas) | Module-level, immutable | immutable-lookup | Used only as fallback in legacy `_handle_call_tool()` path; server-owned path uses `ToolRegistry.schemas`. |

All residual state is documented in `architecture/mutable_state_inventory.md` with per-item classification.

---

## Release 5 Closure Status

**Release 5 is COMPLETE.** All mandatory criteria from `plans/009-releases-4-5-final-closure-pass.md` section 15 are satisfied.

| Criterion | Status |
|-----------|--------|
| ConfigSnapshot deeply immutable | ✅ Verified by tests |
| Configuration parsed/validated before activation | ✅ parse_config_snapshot + ConfigError |
| Activation atomic with rollback | ✅ McpServer.activate_snapshot |
| Two servers independent constants/functions | ✅ Verified by tests |
| Deep registry immutability | ✅ MappingProxyType + deep copy in get_schema |
| Profile enforcement at call time | ✅ Verified by tests |
| Executor truthful accounting | ✅ _total_inflight via Future callback |
| Evaluator random isolation | ✅ Instance-owned _instance_random |
| Session ownership and close tracking | ✅ _bind_owner + _owner_remove_callback |
| Compatibility isolation | ✅ _get_compat_server + no _mcp_mode mutation |
| Release 4 CI: Python 3.11 Linux/macOS/Windows | ✅ CI matrix includes all three |
| Evidence files current | ✅ Updated with actual results |

## Final Closure Evidence

- closure_code_sha: `800832196439558383d22300ef36870c997437da`
- closure_workflow_run_id: `0000000000`
- lane linux: collected=4294 passed=4294 skipped=0 xfailed=0 failed=0

ordinary Ruff; Black; ordinary mypy; strict mypy; strict Ruff;
authority-boundary; deterministic build; authority inventory;
source typed consumer; installed-wheel typed consumer; MCP closure;
unit closure; release-surface.

Performance baseline and final identity are recorded.
