# Mutable State Inventory

Systematic inventory of all mutable process-global state in eggcalc.
Created for Release 5 (State Isolation and Concurrency Hardening).

## Classification

| Category | Description |
|----------|-------------|
| **policy** | Configuration, profiles, normalization rules, constants/functions registries |
| **cache** | Evaluation caches, LRU entries, memoization |
| **user_state** | Per-user random state, memory stores |
| **infrastructure** | Locks, semaphores, thread pools, orphan tracking |
| **protocol** | MCP protocol state, session defaults, compatibility flags |

## Status Legend

- **Isolated** — owned by an explicit instance (e.g., `McpServer`), not shared
- **Global-safe** — process-global but protected by locks and justified
- **Shared** — process-global, mutated at runtime, may cause cross-instance interference
- **Deferred** — identified but not yet addressed

---

## eggcalc/evaluator.py

| Line | Variable | Type | Classification | Status | Notes |
|------|----------|------|----------------|--------|-------|
| 69 | `_config_loaded` | `bool` | policy | **Shared** | Written without lock; race under concurrent `load_user_config()` calls |
| 70 | `_mcp_mode` | `bool` | policy | **Shared** | Mutated by `server.py`, no lock; read everywhere |
| 72 | `_EVAL_SPAWN_SEMAPHORE` | `BoundedSemaphore` | infrastructure | **Global-safe** | Bounded concurrency control; inherently thread-safe |
| 219-221 | `_orphaned_eval_processes`, `_orphaned_eval_order`, `_orphaned_eval_lock` | set, list, Lock | infrastructure | **Global-safe** | Protected by `_orphaned_eval_lock` |
| 445-447 | `_cache`, `_cache_lock`, `_cache_bytes` | OrderedDict, Lock, int | cache | **Shared** | Process-global LRU; all instances share one cache; cleared on config change |
| 1189 | `_random_generator` | `random.Random` | user_state | **Shared** | Global RNG with no lock; `seed()` affects all evaluators |
| 1400 | `_current_evaluator` | `ContextVar` | infrastructure | **Global-safe** | Context-isolated by design |
| 1557 | `_memory` (per-instance) | `Memory` | user_state | **Isolated** | Per-Evaluator; internal lock |
| 1738 | `Evaluator.CONSTANTS` | class var dict | policy | **Shared** | Class-level dict mutated by `register_constant()` and `load_user_config()` |
| 1804 | `Evaluator.FUNCTIONS` | class var dict | policy | **Shared** | Class-level dict mutated by `register_function()` and `load_user_config()` |
| 2825 | `_default_evaluator` | `Evaluator` | infrastructure | **Shared** | Module singleton; policy flags mutated by `configure_default_evaluator()` |

## eggcalc/normalize.py

| Line | Variable | Type | Classification | Status | Notes |
|------|----------|------|----------------|--------|-------|
| 129 | `OPERATOR_CONVERSIONS` | dict | policy | **Shared** | Mutated by `load_user_config_extended()` without lock |
| 287 | `NUMBER_WORDS` | dict | policy | **Shared** | Mutated by `load_user_config_extended()` without lock |
| 473 | `NORMALIZE`, `PATTERNS` | dict | policy | **Global-safe** | Rebuilt atomically under `_REBUILD_LOCK` |
| 497 | `check_if_number` | lru_cache | cache | **Global-safe** | Cleared during rebuild; inherently safe |

## eggcalc/units.py

| Line | Variable | Type | Classification | Status | Notes |
|------|----------|------|----------------|--------|-------|
| 341 | `UNIT_BASE` | dict | policy | **Global-safe** | Mutated under `_UNITS_LOCK` |
| 929 | `UNIT_CONVERSIONS` | dict | policy | **Global-safe** | Rebuilt under `_UNITS_LOCK` |
| 953 | `UNIT_ALIASES` | dict | policy | **Global-safe** | Mutated under `_UNITS_LOCK` |
| 1505 | `TEMPERATURE_CONVERSIONS` | dict | policy | **Global-safe** | Mutated under `_UNITS_LOCK` |
| 1680 | `UNIT_CATEGORIES` | dict | policy | **Global-safe** | Mutated under `_UNITS_LOCK` |

## eggcalc/mcp/server.py

| Line | Variable | Type | Classification | Status | Notes |
|------|----------|------|----------------|--------|-------|
| 51 | `_mcp_defaults_configured` | `bool` | protocol | **Global-safe** | Written once under `_mcp_defaults_lock` |
| 290 | `_active_profile` | `str` | policy | **Shared** | Process-global; replaced by `McpServerConfig.profile` |
| 306 | `_schema_detail` | `str` | policy | **Shared** | Process-global; replaced by `McpServerConfig.schema_detail` |
| 365 | `_tool_executor` | `ThreadPoolExecutor` | infrastructure | **Shared** | Process-global; replaced by `ToolExecutor` per-server |
| 387 | `_orphaned_processes` | set | infrastructure | **Shared** | Process-global; replaced by `ToolExecutor._orphaned` per-server |
| 1924 | `_default_session` | `McpSession` | protocol | **Shared** | Deprecated compat path; replaced by explicit `McpSession` per-server |
| — | `os.environ.setdefault` | env mutation | policy | **Removed** | Import-time mutation removed; config suppression now handled by `McpServerConfig.from_environment()` and `main()` setup |
| — | `ConfigSnapshot` dicts | dict fields | policy | **Isolated** | `__post_init__()` defensively copies all dict fields to prevent external mutation |

## eggcalc/mcp/tools.py

| Line | Variable | Type | Classification | Status | Notes |
|------|----------|------|----------------|--------|-------|
| 225 | `_SPAWN_SEMAPHORE` | `BoundedSemaphore` | infrastructure | **Global-safe** | Bounded concurrency; inherently thread-safe |
| 314-316 | `_orphaned_regex_processes`, `_orphaned_regex_order`, `_orphaned_regex_lock` | set, deque, Lock | infrastructure | **Global-safe** | Protected by `_orphaned_regex_lock` |

---

## Identified Thread-Safety Gaps

1. **`_mcp_mode`** — written by `server.py:1945`, read by `evaluator.py` functions. No lock.
2. **`_config_loaded`** — written in `load_user_config()` and `_ensure_config_loaded()`. No lock around reads.
3. **`_random_generator`** — shared RNG, no lock. `seed()` affects all evaluators.
4. **`OPERATOR_CONVERSIONS`** and **`NUMBER_WORDS`** in normalize.py — mutated by `load_user_config_extended()` without lock.
5. **`_cache` / `_cache_bytes`** — shared across all evaluator instances; one instance's config change clears everyone's cache.

## Post-Release-5 Status

After Release 5, the following shared state is **justified and safe**:

- **`_cache` / `_cache_bytes`**: Shared but bounded; cleared on config change. Acceptable for single-server deployments. Multi-server isolation requires either generation-keyed caching or per-server `EggCalcApp` instances.
- **`_mcp_mode`**: Set once at startup, never toggled back. Safe under current usage.
- **`_config_loaded`**: Set once, never toggled back. Safe under current usage.
- **`_random_generator`**: Acceptable for calculator use case; not security-sensitive.
- **`OPERATOR_CONVERSIONS` / `NUMBER_WORDS`**: Set once at startup via `load_user_config_extended()`. Safe under single-threaded startup.

The following are **fully isolated by Release 5**:

- `McpServerConfig` (frozen dataclass)
- `ToolRegistry` (per-server copy of tool definitions)
- `ToolExecutor` (per-server thread pool and orphan tracking)
- `ConfigSnapshot` / `ConfigManager` (per-server atomic config; dicts deeply copied in `__post_init__`)
- `McpSession` (per-connection lifecycle, cancellation, protocol state)
- `Evaluator` instances (per-server via `create_evaluator()`)
