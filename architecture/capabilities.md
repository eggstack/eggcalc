# capabilities.md — Runtime Capability Detection

Platform detection and capability snapshotting for eggcalc. Used by MCP tool registration, CLI diagnostics, and release-surface checks.

## Table of Contents

- [Purpose](#purpose)
- [RuntimeCapabilities](#runtimecapabilities)
- [detect_capabilities()](#detect_capabilities)
- [Usage](#usage)

## Purpose

`capabilities.py` provides a frozen, immutable snapshot of the current runtime environment. This allows different parts of the codebase (MCP server, CLI, build validation) to query platform facts without side effects or repeated detection.

## RuntimeCapabilities

A frozen dataclass with 13 fields:

| Field | Type | Description |
|-------|------|-------------|
| `python_version` | `tuple[int, int, int]` | `(major, minor, micro)` |
| `platform` | `str` | `sys.platform` (e.g. `"linux"`, `"darwin"`) |
| `implementation` | `str` | `sys.implementation.name` (e.g. `"cpython"`) |
| `has_tomllib` | `bool` | `True` if Python ≥3.11 (stdlib `tomllib` available) |
| `has_math_cbrt` | `bool` | `True` if Python ≥3.11 (`math.cbrt` available) |
| `supports_fork` | `bool` | `True` if `os.fork` exists (POSIX) |
| `supports_spawn` | `bool` | Always `True` (all platforms support `multiprocessing`) |
| `supports_posix_paths` | `bool` | `True` if not Windows |
| `supports_windows_paths` | `bool` | `True` if Windows/MSYS/Cygwin |
| `eggcalc_version` | `str` | Version from `_version.py` or `importlib.metadata` |
| `supported_protocol_versions` | `tuple[str, ...]` | MCP protocol versions from `_protocol.py` |
| `multiprocessing_start_method` | `str` | `"fork"`, `"spawn"`, or `"forkserver"` |
| `mode` | `str` | `"package"` or `"single-file"` (detected from `__main__.__file__`) |

Methods:
- `to_dict()` → `dict[str, object]` — JSON-serializable dictionary
- `to_json(indent=None)` → `str` — JSON string

## detect_capabilities()

Factory function that probes the runtime and returns a `RuntimeCapabilities` instance. No side effects, no config loading, no network calls.

```python
from eggcalc import detect_capabilities
caps = detect_capabilities()
print(caps.eggcalc_version)  # "1.1.8"
print(caps.mode)             # "package" or "single-file"
```

## Usage

- **MCP server**: `McpServerConfig` reads capabilities to set protocol versions and mode
- **CLI diagnostics**: `capability_summary()` prints a human-readable snapshot
- **Build validation**: `scripts/smoke_release_surfaces.py` checks capabilities in installed wheel and single-file distributions

See also: [overview.md](overview.md) for module placement, [mcp.md](mcp.md) for MCP integration.
