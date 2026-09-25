# capabilities.md — Runtime Capability Detection

Platform detection and capability snapshotting for eggcalc. Used by MCP tool registration, CLI diagnostics, and release-surface checks.

## Table of Contents

- [Overview](#overview)
- [Type Definitions](#type-definitions)
- [Constants](#constants)
- [Public Functions](#public-functions)
- [Internal Helpers](#internal-helpers)
- [Dependencies](#dependencies)
- [Limits and Security Notes](#limits-and-security-notes)
- [See Also](#see-also)

## Overview

`capabilities.py` provides a frozen, immutable snapshot of the current runtime environment. This allows different parts of the codebase (MCP server, CLI, build validation) to query platform facts without side effects or repeated detection.

The snapshot is a frozen dataclass (`RuntimeCapabilities`) built by a side-effect-free factory (`detect_capabilities()`), plus a human-readable renderer (`capability_summary()`). The CLI exposes the snapshot as JSON via `calc --capabilities`; the MCP server reads it for protocol versions and mode.

Runtime capabilities are eggcalc diagnostics, not MCP protocol capabilities: the modern `server/discover` result advertises only protocol capabilities (`{"tools": {"listChanged": false}}`), while the legacy `initialize` response keeps the `runtime` diagnostics key for backward compatibility.

## Type Definitions

### `RuntimeCapabilities`

A frozen dataclass with 13 fields. Frozen means assignment raises `dataclasses.FrozenInstanceError`:

```python
from eggcalc import detect_capabilities
caps = detect_capabilities()
caps.mode = "x"  # raises FrozenInstanceError
```

| Field | Type | Description |
|-------|------|-------------|
| `python_version` | `tuple[int, int, int]` | `(major, minor, micro)` from `sys.version_info` |
| `platform` | `str` | `sys.platform` (e.g. `"linux"`, `"darwin"`, `"win32"`) |
| `implementation` | `str` | `sys.implementation.name` (e.g. `"cpython"`) |
| `has_tomllib` | `bool` | `True` if Python ≥3.11 (stdlib `tomllib` available) |
| `has_math_cbrt` | `bool` | `True` if Python ≥3.11 (`math.cbrt` available) |
| `supports_fork` | `bool` | `True` if `os.fork` exists (POSIX) |
| `supports_spawn` | `bool` | Always `True` (all platforms support `multiprocessing`) |
| `supports_posix_paths` | `bool` | `True` if not Windows (`platform != "win32"`) |
| `supports_windows_paths` | `bool` | `True` if Windows/MSYS/Cygwin |
| `eggcalc_version` | `str` | Version from `_version.py` or `importlib.metadata`, else `"unknown"` |
| `supported_protocol_versions` | `tuple[str, ...]` | MCP protocol versions from `_protocol.py` |
| `multiprocessing_start_method` | `str` | `"fork"`, `"spawn"`, `"forkserver"`, or `"unknown"` |
| `mode` | `str` | `"package"` or `"single-file"` (detected from `__main__.__file__`) |

Methods:

- `to_dict() -> dict[str, object]` — JSON-serializable dictionary. Tuples become lists (`python_version` and `supported_protocol_versions`).
- `to_json(*, indent: int | None = None) -> str` — JSON string via `json.dumps(self.to_dict(), indent=indent)`.

```python
caps = detect_capabilities()
d = caps.to_dict()
d["eggcalc_version"]   # "1.1.11"
d["python_version"]    # [3, 12, 3] (list, JSON-serializable)
d["mode"]              # "package" or "single-file"
caps.to_json(indent=2) # pretty-printed JSON string
```

## Constants

`capabilities.py` defines no local constants. Values come from two single sources:

- `eggcalc_version` — from `._version.__version__`, falling back to `importlib.metadata.version("eggcalc")`, else `"unknown"`.
- `supported_protocol_versions` — re-exported as-is from `_protocol.py` (`SUPPORTED_PROTOCOL_VERSIONS`, currently `("2024-11-05", "2025-11-25", "2026-07-28")`).

Thresholds are inline, not named constants: `ver >= (3, 11)` for `has_tomllib`/`has_math_cbrt`, `plat != "win32"` for POSIX paths, `"msys" in plat or "cygwin" in plat` for Windows-path detection.

## Public Functions

### `detect_capabilities() -> RuntimeCapabilities`

Factory function that probes the runtime and returns a `RuntimeCapabilities` instance. No side effects, no config loading, no network calls.

```python
def detect_capabilities() -> RuntimeCapabilities:
```

Behavior:
- Reads `sys.version_info`, `sys.platform`, `sys.implementation.name`.
- Derives feature flags (`has_tomllib`, `has_math_cbrt`, `supports_fork`, `supports_spawn`, path flags) by pure observation.
- Resolves `eggcalc_version` with the `_version.py` → `importlib.metadata` → `"unknown"` fallback chain.
- Reads `multiprocessing.get_start_method()`, returning `"unknown"` on `RuntimeError` (no start method set yet).
- Detects `mode` via `_detect_mode()`.

Example (verified):

```python
from eggcalc import detect_capabilities
caps = detect_capabilities()
print(caps.eggcalc_version)  # "1.1.11"
print(caps.mode)             # "package" or "single-file"
print(caps.platform)         # "linux"
```

### `capability_summary() -> str`

Human-readable multi-line summary of the current snapshot. Calls `detect_capabilities()` internally, so output always reflects the live runtime.

```python
def capability_summary() -> str:
```

Example (verified):

```python
from eggcalc.capabilities import capability_summary
print(capability_summary())
# eggcalc runtime capabilities
#   Version: 1.1.11
#   Python: 3.12.3 (cpython)
#   Platform: linux
#   Mode: package
#   tomllib: yes
#   math.cbrt: yes
#   fork: yes
#   spawn: yes
#   POSIX paths: yes
#   Windows paths: no
#   Protocol versions: 2024-11-05, 2025-11-25, 2026-07-28
#   Multiprocessing start method: fork
```

Exact line labels are `Version`, `Python`, `Platform`, `Mode`, `tomllib`, `math.cbrt`, `fork`, `spawn`, `POSIX paths`, `Windows paths`, `Protocol versions`, `Multiprocessing start method`, under the header `eggcalc runtime capabilities`.

### `RuntimeCapabilities.to_dict() -> dict[str, object]`

Returns a JSON-serializable dictionary. Tuple fields are converted to lists; all other values are already JSON primitives.

```python
caps = detect_capabilities()
d = caps.to_dict()
sorted(d.keys())
# ['eggcalc_version', 'has_math_cbrt', 'has_tomllib', 'implementation',
#  'mode', 'multiprocessing_start_method', 'platform', 'python_version',
#  'supports_fork', 'supports_posix_paths', 'supports_spawn',
#  'supports_windows_paths', 'supported_protocol_versions']
```

### `RuntimeCapabilities.to_json(*, indent: int | None = None) -> str`

Returns `json.dumps(self.to_dict(), indent=indent)`. Used directly by `calc --capabilities` with `indent=2`.

```python
caps = detect_capabilities()
caps.to_json()            # compact JSON string
caps.to_json(indent=2)    # pretty-printed, as printed by the CLI
```

## Internal Helpers

### `_detect_mode() -> str`

Detects whether running as an installed package or as the assembled single file.

```python
def _detect_mode() -> str:
```

Behavior:
- Reads `sys.modules.get("__main__")` and its `__file__`.
- Returns `"package"` when `__file__` is missing (e.g. REPL, embedded interpreter).
- Returns `"single-file"` only when the basename is exactly `"eggcalc.py"`.
- Returns `"package"` otherwise.

This is the sole mode-detection authority; `detect_capabilities()` calls it for the `mode` field.

## Dependencies

```
capabilities.py
    ├── _protocol.py (SUPPORTED_PROTOCOL_VERSIONS)
    ├── _version.py (__version__, with importlib.metadata fallback)
    └── stdlib only: dataclasses, json, multiprocessing, os, sys
```

No dependency on `evaluator.py`, `normalize.py`, `units.py`, `cli.py`, `exact/`, or `mcp/`. Importing `eggcalc.capabilities` never loads argparse, exact-tool implementations, or MCP modules, and never executes cwd-local config.

## Limits and Security Notes

- **Side-effect-free:** `detect_capabilities()` performs no I/O, no config loading, no network calls. It only reads `sys`, `os`, and `multiprocessing` state.
- **Frozen snapshot:** `RuntimeCapabilities` is `@dataclass(frozen=True)`. Callers cannot mutate a snapshot; re-probe with `detect_capabilities()` for fresh facts.
- **No config trust boundary:** version resolution imports only `._version` (package-owned) and `importlib.metadata` (installed metadata). It never imports `eggcalc_config` from the working directory.
- **Mode heuristic limits:** `_detect_mode()` keys on the `__main__` filename. Renaming the single file breaks `"single-file"` detection (falls back to `"package"`). REPL/embedded use without `__main__.__file__` always reports `"package"`.
- **Start-method caveat:** `multiprocessing.get_start_method()` raises `RuntimeError` when no method has been set and `multiprocessing` has not been configured; this is mapped to `"unknown"`, not an error.
- **Stdlib-only:** no third-party imports, safe in the single-file build.

## See Also

- [overview.md](overview.md) for module placement and the core calculator pipeline.
- [mcp.md](mcp.md) for MCP integration (protocol versions, `server/discover` vs legacy `initialize`).
- [cli.md](cli.md) for `calc --capabilities` (JSON output) and mode classification before config loading.
- [api.md](api.md) for the public re-exports (`RuntimeCapabilities`, `detect_capabilities`).
