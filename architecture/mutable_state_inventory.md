# Mutable State Inventory

Systematic inventory of all mutable process-global state in eggcalc.
Created for Release 5 (State Isolation and Concurrency Hardening).

## Classification (Release 5 Taxonomy)

Every residual global is classified as one of:

| Category | Description |
|----------|-------------|
| **immutable-lookup** | Read-only lookup tables populated at import time; never mutated after initial build |
| **process-bounded** | Process-wide infrastructure protected by locks or semaphores; inherently thread-safe |
| **compat-only** | State used only by the deprecated compatibility dispatcher; production paths do not touch it |
| **legacy-cli** | One-shot CLI configuration state; not used by explicit `McpServer` instances |
| **deferred-r6** | Identified but deferred to Release 6 (e.g., import-graph restructuring) |
| **removed** | Eliminated during Release 5 |

## Status Legend

- **Isolated** — owned by an explicit instance (e.g., `McpServer`), not shared
- **Bounded** — process-global but protected by locks and bounded in size

---

## eggcalc/_process.py

Stateless by design: no module-level mutable state. `SpawnPermit` instances are caller-owned; semaphores, orphan sets, and locks remain with `evaluator.py` / `mcp/tools.py` (see below).

## eggcalc/evaluator.py

| Variable | Type | Category | Status | Notes |
|----------|------|----------|--------|-------|
| `_config_loaded` | `bool` | legacy-cli | Bounded | Set once at startup to prevent re-entry; never toggled back |
| `_config_generation` | `int` | process-bounded | Bounded | Incremented under `_cache_lock` on config change; invalidates caches |
| `_FUNCTION_SPECS` | `dict \| None` | process-bounded | Bounded | Lazily built function-spec table (process-global cache) |
| `_orphaned_eval_order` / `_orphaned_eval_lock` | `deque`, `Lock` | process-bounded | Bounded | Companions of `_orphaned_eval_processes` below |
| `_mcp_mode` | `bool` | compat-only | Bounded | Set once by deprecated compatibility path; production stdio does not set this |
| `_server_evaluator` | `ContextVar` | process-bounded | Bounded | Context-isolated; binds server evaluator to `evaluate_raw()`/`evaluate_with_timeout()` |
| `_EVAL_SPAWN_SEMAPHORE` | `BoundedSemaphore` | process-bounded | Bounded | Bounded concurrency control; inherently thread-safe |
| `_orphaned_eval_processes` | set | process-bounded | Bounded | Protected by `_orphaned_eval_lock` |
| `_cache` / `_cache_lock` / `_cache_bytes` | OrderedDict, Lock, int | deferred-r6 | Bounded | Process-global LRU; shared across instances. Multi-server isolation requires generation-keyed caching or per-server `EggCalcApp` instances |
| `_random_generator` | `random.Random` | process-bounded | Bounded | Global RNG for non-MCP use; MCP servers use dedicated per-instance `_instance_random` |
| `_current_evaluator` | `ContextVar` | process-bounded | Bounded | Context-isolated by design (used by `evaluate()` for function calls) |
| `_memory` (per-instance) | `Memory` | — | Isolated | Per-Evaluator; internal lock |
| `Evaluator.CONSTANTS` | class var dict | legacy-cli | Bounded | Class-level dict mutated by `register_constant()` and `load_user_config()`. Per-server instances copy this at construction |
| `Evaluator.FUNCTIONS` | class var dict | legacy-cli | Bounded | Class-level dict mutated by `register_function()` and `load_user_config()`. Per-server instances copy this at construction |
| `_default_evaluator` | `Evaluator` | compat-only | Bounded | Module singleton; used only by deprecated sessionless path. Production uses `McpServer.evaluator` |

## eggcalc/normalize.py

| Variable | Type | Category | Status | Notes |
|----------|------|----------|--------|-------|
| `OPERATOR_CONVERSIONS` | dict | legacy-cli | Bounded | Mutated by `load_user_config_extended()` at startup only |
| `NUMBER_WORDS` | dict | legacy-cli | Bounded | Mutated by `load_user_config_extended()` at startup only |
| `NORMALIZE` / `PATTERNS` | dict | process-bounded | Bounded | Rebuilt atomically under `_REBUILD_LOCK` |
| `_COMPACT_ARG_CACHE` | dict | process-bounded | Bounded | Cache for compact-arg parsing (process-global) |
| `check_if_number` | lru_cache | process-bounded | Bounded | Cleared during rebuild; inherently safe |

## eggcalc/units.py

| Variable | Type | Category | Status | Notes |
|----------|------|----------|--------|-------|
| `UNIT_BASE` | MappingProxyType | immutable-lookup | Bounded | Generated adapter from `UNIT_DEFINITIONS`, installed once at import by `_install_generated_adapters()`; read-only thereafter |
| `UNIT_CONVERSIONS` | lazy Mapping | immutable-lookup | Bounded | `_LazyUnitConversions`: computes pairwise factors on demand from the registry; no lock (stateless computation) |
| `UNIT_ALIASES` | MappingProxyType | immutable-lookup | Bounded | Generated adapter installed once at import; read-only thereafter |
| `TEMPERATURE_CONVERSIONS` | MappingProxyType | immutable-lookup | Bounded | Generated adapter installed once at import; read-only thereafter |
| `UNIT_CATEGORIES` | MappingProxyType | immutable-lookup | Bounded | Generated adapter installed once at import; read-only thereafter |
| `_unit_registry` | `UnitRegistry \| None` | process-bounded | Bounded | Lazily built on first access via `_get_unit_registry()` |
| `_CUSTOM_UNIT_DEFINITIONS` | dict | process-bounded | Bounded | User-registered unit definitions; triggers adapter reinstall |

## eggcalc/mcp/server.py

| Variable | Type | Category | Status | Notes |
|----------|------|----------|--------|-------|
| `_active_profile` | `str` | compat-only | Bounded | Process-global; replaced by `McpServerConfig.profile` in explicit servers; guarded by `_profile_lock` |
| `_schema_detail` | `str` | compat-only | Bounded | Process-global; replaced by `McpServerConfig.schema_detail` in explicit servers; guarded by `_schema_detail_lock` |
| `_tool_executor` / `_tool_executor_lock` | `ThreadPoolExecutor \| None`, `Lock` | process-bounded | Bounded | Compat-path shared executor via `_get_tool_executor()`; per-server `ToolExecutor` is the production path |
| `_orphaned_processes` / `_orphaned_lock` | set, `Lock` | process-bounded | Bounded | Compat-path orphan set harvested by `_cleanup_orphaned_processes()` (atexit); per-server executors track their own orphans |
| `_compat_server_lock` | `Lock` | process-bounded | Bounded | Guards the deprecated sessionless compat server |
| `_default_session` | `McpSession` | removed | — | Replaced by explicit `McpSession` per-server |
| `os.environ.setdefault` | env mutation | removed | — | Import-time mutation removed; handled by `McpServerConfig.from_environment()` |
| `ConfigSnapshot` dicts | dict fields | — | Isolated | `__post_init__()` defensively copies all dict fields |
| `ToolRegistry` dicts | dict fields | — | Isolated | `MappingProxyType` wrapping prevents external mutation |
| `ToolExecutor._closed` | `bool` | — | Isolated | Per-executor; prevents pool recreation |
| `ToolExecutor._total_inflight` | `int` | — | Isolated | Per-executor; released on true completion |

## eggcalc/mcp/tools.py

| Variable | Type | Category | Status | Notes |
|----------|------|----------|--------|-------|
| `_SPAWN_SEMAPHORE` | `BoundedSemaphore` | process-bounded | Bounded | Bounded concurrency; inherently thread-safe |
| `_orphaned_regex_processes` | set | process-bounded | Bounded | Protected by `_orphaned_regex_lock` |

---

## Fully Isolated by Release 5

These objects are owned by explicit instances and not shared across servers:

- `McpServerConfig` — frozen dataclass
- `ToolRegistry` — per-server; `MappingProxyType` prevents external mutation
- `ToolExecutor` — per-server thread pool, orphan tracking, closed-state sealing
- `ConfigSnapshot` / `ConfigManager` — per-server atomic config with generation validation
- `McpSession` — per-connection lifecycle, cancellation, protocol state
- `Evaluator` instances — per-server via `create_evaluator()`; instance-owned `_instance_random`
- `ToolExecutor._total_inflight` — released via `Future.add_done_callback()` on true completion
