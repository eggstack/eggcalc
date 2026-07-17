"""
MCP server implementation for eggcalc.

Provides a stdio-based MCP server that exposes exact text, Unicode,
and measurement tools to agents.
"""

from __future__ import annotations

import enum
import inspect
import json
import logging
import multiprocessing
import os
import sys
import threading
import time
import warnings
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from typing import Any

# Disable any user-supplied config loading at import time, before any
# other eggcalc modules have a chance to read the env var. The MCP
# server is a tool surface for agents, not a user REPL, and loading
# arbitrary code from the working directory would be a security risk.
os.environ.setdefault("EGGCALC_NO_CONFIG", "1")

from .. import __version__
from .. import evaluator as _evaluator
from .schemas import (
    PROFILE_NAMES,
    SCHEMA_DETAIL_FULL,
    TOOL_METADATA,
    TOOL_PROFILES,
    TOOL_SCHEMAS,
    compact_schema,
    normal_schema,
)

# Flag set the first time handle_request() runs to ensure MCP-safe defaults
# are configured (allow_random=False, allow_side_effects=False). We do this
# at first use, not at module import, so importing the MCP module for any
# reason (e.g. tests of unrelated CLI code that transitively imports the
# schema) does not globally disable random/setvar.
_mcp_defaults_configured: bool = False
_mcp_defaults_lock = threading.Lock()
from .tools import (
    _sanitize_error,
    canonicalize_text_mcp,
    cargo_toml_inspect_mcp,
    code_fence_extract_mcp,
    command_preflight,
    config_preflight,
    constant_lookup,
    diff_file_headers_mcp,
    diff_hunk_ranges_mcp,
    diff_touched_paths_mcp,
    dotenv_validate_mcp,
    edit_preflight,
    escape_text,
    glob_match_mcp,
    go_mod_inspect_mcp,
    identifier_analyze,
    identifier_inspect_mcp,
    identifier_table_inspect_mcp,
    ini_validate_mcp,
    json_canonicalize,
    json_compare,
    json_extract,
    json_query,
    json_shape,
    line_range_compare,
    line_range_extract,
    list_compare,
    list_dedupe_mcp,
    list_sort_mcp,
    llm_json_output_check_mcp,
    lockfile_summary_mcp,
    markdown_link_check_lexical_mcp,
    markdown_structure_mcp,
    math_eval,
    package_json_inspect_mcp,
    patch_apply_check_mcp,
    patch_conflict_markers_inspect_mcp,
    patch_summary_mcp,
    path_analyze_mcp,
    path_compare_mcp,
    path_normalize,
    path_scope_check_mcp,
    prompt_input_inspect_mcp,
    pyproject_inspect_mcp,
    regex_finditer,
    regex_safety_check,
    repo_file_inventory_mcp,
    requirements_inspect_mcp,
    shell_argv_compare,
    shell_quote_join,
    shell_split,
    structured_data_compare,
    text_count,
    text_diff_explain,
    text_equal,
    text_fingerprint_mcp,
    text_hash,
    text_inspect,
    text_measure,
    text_position,
    text_replace_check,
    text_security_inspect,
    text_transform,
    text_truncate,
    text_window,
    toml_shape_mcp,
    unescape_text,
    unicode_policy_check_mcp,
    unified_diff_validate_mcp,
    unit_convert,
    unit_info,
    validate_brackets,
    validate_json,
    validate_regex,
    validate_schema_light,
    validate_toml,
    version_compare_mcp,
    version_constraint_check_mcp,
)

TOOL_HANDLERS: dict[str, Any] = {
    "cargo_toml_inspect": cargo_toml_inspect_mcp,
    "code_fence_extract": code_fence_extract_mcp,
    "dotenv_validate": dotenv_validate_mcp,
    "ini_validate": ini_validate_mcp,
    "escape_text": escape_text,
    "line_range_compare": line_range_compare,
    "line_range_extract": line_range_extract,
    "llm_json_output_check": llm_json_output_check_mcp,
    "markdown_link_check_lexical": markdown_link_check_lexical_mcp,
    "unescape_text": unescape_text,
    "json_canonicalize": json_canonicalize,
    "json_compare": json_compare,
    "json_extract": json_extract,
    "json_query": json_query,
    "json_shape": json_shape,
    "list_compare": list_compare,
    "list_dedupe": list_dedupe_mcp,
    "list_sort": list_sort_mcp,
    "math_eval": math_eval,
    "patch_apply_check": patch_apply_check_mcp,
    "patch_conflict_markers_inspect": patch_conflict_markers_inspect_mcp,
    "patch_summary": patch_summary_mcp,
    "diff_touched_paths": diff_touched_paths_mcp,
    "diff_hunk_ranges": diff_hunk_ranges_mcp,
    "diff_file_headers": diff_file_headers_mcp,
    "unified_diff_validate": unified_diff_validate_mcp,
    "path_analyze": path_analyze_mcp,
    "path_compare": path_compare_mcp,
    "path_normalize": path_normalize,
    "path_scope_check": path_scope_check_mcp,
    "regex_finditer": regex_finditer,
    "regex_safety_check": regex_safety_check,
    "repo_file_inventory": repo_file_inventory_mcp,
    "shell_split": shell_split,
    "shell_quote_join": shell_quote_join,
    "argv_compare": shell_argv_compare,
    "text_count": text_count,
    "text_diff_explain": text_diff_explain,
    "text_equal": text_equal,
    "text_hash": text_hash,
    "text_inspect": text_inspect,
    "text_measure": text_measure,
    "text_position": text_position,
    "text_replace_check": text_replace_check,
    "text_truncate": text_truncate,
    "text_transform": text_transform,
    "text_window": text_window,
    "toml_shape": toml_shape_mcp,
    "unit_convert": unit_convert,
    "unit_info": unit_info,
    "constant_lookup": constant_lookup,
    "validate_brackets": validate_brackets,
    "validate_json": validate_json,
    "validate_regex": validate_regex,
    "validate_schema_light": validate_schema_light,
    "validate_toml": validate_toml,
    "version_compare": version_compare_mcp,
    "version_constraint_check": version_constraint_check_mcp,
    "identifier_analyze": identifier_analyze,
    "glob_match": glob_match_mcp,
    "text_fingerprint": text_fingerprint_mcp,
    "identifier_inspect": identifier_inspect_mcp,
    "identifier_table_inspect": identifier_table_inspect_mcp,
    "markdown_structure": markdown_structure_mcp,
    "unicode_policy_check": unicode_policy_check_mcp,
    "canonicalize_text": canonicalize_text_mcp,
    "prompt_input_inspect": prompt_input_inspect_mcp,
    "text_security_inspect": text_security_inspect,
    "edit_preflight": edit_preflight,
    "command_preflight": command_preflight,
    "config_preflight": config_preflight,
    "structured_data_compare": structured_data_compare,
    "pyproject_inspect": pyproject_inspect_mcp,
    "package_json_inspect": package_json_inspect_mcp,
    "requirements_inspect": requirements_inspect_mcp,
    "go_mod_inspect": go_mod_inspect_mcp,
    "lockfile_summary": lockfile_summary_mcp,
}


def _parse_env_int(name: str, default: int, min_val: int, max_val: int) -> int:
    """Parse a positive integer from environment variable with clamping.

    Returns default if the variable is not set, empty, or contains a
    non-numeric value.  The result is always clamped to [min_val, max_val].
    """
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except (ValueError, TypeError):
        return default
    return max(min_val, min(value, max_val))


def _parse_env_float(name: str, default: float, min_val: float, max_val: float) -> float:
    """Parse a float from environment variable with clamping.

    Returns default if the variable is not set, empty, or contains a
    non-numeric value.  The result is always clamped to [min_val, max_val].
    """
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        value = float(raw)
    except (ValueError, TypeError):
        return default
    return max(min_val, min(value, max_val))


MAX_REQUEST_BYTES = _parse_env_int("EGGCALC_MCP_MAX_REQUEST_BYTES", 1_000_000, 1_000, 100_000_000)
MAX_OUTPUT_BYTES = _parse_env_int("EGGCALC_MCP_MAX_OUTPUT_BYTES", 1_000_000, 1_000, 100_000_000)
MAX_REQUESTS_PER_SECOND = _parse_env_float("EGGCALC_MCP_MAX_REQUESTS_PER_SECOND", 10, 0.1, 1000)
MAX_REQUEST_ID_LENGTH = 1024
MAX_TOOL_TIMEOUT_SECONDS = _parse_env_int("EGGCALC_MCP_MAX_TOOL_TIMEOUT_SECONDS", 30, 1, 300)
MAX_CANCELLED_REQUESTS = _parse_env_int(
    "EGGCALC_MCP_MAX_CANCELLED_REQUESTS", 10_000, 100, 1_000_000
)

SUPPORTED_PROTOCOL_VERSIONS = ("2024-11-05", "2025-11-25")
LATEST_SUPPORTED_PROTOCOL_VERSION = SUPPORTED_PROTOCOL_VERSIONS[-1]

SUPPORTED_SCHEMA_KEYWORDS = frozenset(
    {
        "type",
        "enum",
        "const",
        "default",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "multipleOf",
        "minLength",
        "maxLength",
        "pattern",
        "minItems",
        "maxItems",
        "uniqueItems",
        "items",
        "properties",
        "required",
        "additionalProperties",
        "description",
    }
)

# Per-session cancellation records are owned by McpSession instances.
# Module-level lock is no longer needed; each session has its own lock.

# Active MCP profile.  Set by set_active_profile() or read from
# EGGCALC_MCP_PROFILE env var at startup.  "full" is the default for
# backward compatibility; codegg should use codegg_core or codegg_core_min.
_active_profile: str = os.environ.get("EGGCALC_MCP_PROFILE", "full")
_profile_lock = threading.Lock()

# Validate startup profile eagerly
if _active_profile not in TOOL_PROFILES and _active_profile != "full":
    import sys as _sys

    _available = ", ".join(sorted(TOOL_PROFILES))
    print(
        f"Error: Invalid EGGCALC_MCP_PROFILE: {_active_profile!r}. "
        f"Available profiles: {_available}",
        file=_sys.stderr,
    )
    raise SystemExit(1)

# Schema detail level: full, normal, compact
_schema_detail: str = os.environ.get("EGGCALC_MCP_SCHEMA_DETAIL", SCHEMA_DETAIL_FULL)
_schema_detail_lock = threading.Lock()


def set_active_profile(name: str) -> None:
    """Set the active MCP profile.  Raises ValueError for unknown profiles."""
    if name not in TOOL_PROFILES and name != "full":
        raise ValueError(
            f"Unknown profile: {name!r}. " f"Available profiles: {', '.join(sorted(TOOL_PROFILES))}"
        )
    global _active_profile
    with _profile_lock:
        _active_profile = name


def get_active_profile() -> str:
    """Return the currently active MCP profile name."""
    with _profile_lock:
        return _active_profile


def set_schema_detail(level: str) -> None:
    """Set the schema detail level (compact, normal, full)."""
    if level not in ("compact", "normal", "full"):
        raise ValueError(f"Invalid schema detail: {level!r}. Use compact, normal, or full.")
    global _schema_detail
    with _schema_detail_lock:
        _schema_detail = level


def get_schema_detail() -> str:
    """Return the current schema detail level."""
    with _schema_detail_lock:
        return _schema_detail


def get_profile_tools(profile: str | None = None) -> list[str]:
    """Return the sorted list of tool names for a profile.

    If profile is None, uses the active profile.  Returns all stable
    tools (including deprecated) for 'full', or the profile's tool list
    otherwise.  Only truly hidden tools are excluded from 'full'.
    """
    if profile is None:
        profile = get_active_profile()
    if profile == "full":
        return sorted(
            name for name, meta in TOOL_METADATA.items() if meta.get("llm_exposure") != "hidden"
        )
    if profile not in TOOL_PROFILES:
        available = ", ".join(sorted(TOOL_PROFILES))
        raise ValueError(f"Unknown MCP profile: {profile!r}. Available profiles: {available}")
    return list(TOOL_PROFILES[profile])


# Bounded thread pool for tool invocations. Prevents unbounded thread
# accumulation when tools time out. Tasks submitted to a full pool queue
# until a worker becomes available, providing natural back-pressure.
_MAX_TOOL_WORKERS = _parse_env_int("EGGCALC_MCP_MAX_TOOL_WORKERS", 16, 1, 128)
_tool_executor: ThreadPoolExecutor | None = None
_tool_executor_lock = threading.Lock()


def _get_tool_executor() -> ThreadPoolExecutor:
    """Lazily initialize the bounded thread pool for tool invocations."""
    global _tool_executor
    if _tool_executor is None:
        with _tool_executor_lock:
            if _tool_executor is None:
                _tool_executor = ThreadPoolExecutor(
                    max_workers=_MAX_TOOL_WORKERS,
                    thread_name_prefix="mcp-tool",
                )
    return _tool_executor


# Track orphaned child processes for defensive cleanup. When a tool times out,
# its handler may have spawned a child process (via evaluate_with_timeout or
# validate_regex). The handler's finally block normally terminates these, but
# if the thread is reclaimed before cleanup completes, the process becomes
# orphaned. This set allows periodic cleanup and prevents FD/resource leaks.
_orphaned_processes: set[multiprocessing.Process] = set()
_orphaned_lock = threading.Lock()


def _cleanup_orphaned_processes() -> None:
    """Terminate any orphaned child processes that survived their handler's cleanup."""
    with _orphaned_lock:
        # Also check evaluator and regex tool orphan sets
        try:
            from ..evaluator import (
                _orphaned_eval_lock,
                _orphaned_eval_order,
                _orphaned_eval_processes,
            )

            with _orphaned_eval_lock:
                _orphaned_processes.update(_orphaned_eval_processes)
                _orphaned_eval_processes.clear()
                _orphaned_eval_order.clear()
        except Exception:
            pass
        try:
            from .tools import (
                _orphaned_regex_lock,
                _orphaned_regex_order,
                _orphaned_regex_processes,
            )

            with _orphaned_regex_lock:
                _orphaned_processes.update(_orphaned_regex_processes)
                _orphaned_regex_processes.clear()
                _orphaned_regex_order.clear()
        except Exception:
            pass
        stale = [p for p in _orphaned_processes if p.is_alive()]
        for proc in stale:
            try:
                proc.terminate()
                proc.join(timeout=1)
            except Exception:
                pass
            if proc.is_alive():
                try:
                    proc.kill()
                    proc.join(timeout=1)
                except Exception:
                    pass
            try:
                proc.close()
            except Exception:
                pass
            _orphaned_processes.discard(proc)
            logging.debug("Cleaned up orphaned MCP child process pid=%s", proc.pid)


def _invalid_request(request_id: Any, message: str) -> dict:
    """Build JSON-RPC invalid request/params error."""
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": -32600,
            "message": message,
        },
    }


_invalid_request_error = _invalid_request


def _jsonrpc_error(request_id: Any, code: int, message: str) -> dict:
    """Build a JSON-RPC error response."""
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _parse_error(request_id: Any = None, message: str = "Parse error") -> dict:
    """Build JSON-RPC parse error (-32700)."""
    return _jsonrpc_error(request_id, -32700, message)


def _method_not_found(request_id: Any, method: str) -> dict:
    """Build JSON-RPC method not found error (-32601)."""
    display = method[:100] + "..." if len(method) > 100 else method
    return _jsonrpc_error(request_id, -32601, f"Method not found: {display}")


def _invalid_params(request_id: Any, message: str) -> dict:
    """Build JSON-RPC invalid params error (-32602)."""
    return _jsonrpc_error(request_id, -32602, message)


def _internal_error(request_id: Any, message: str) -> dict:
    """Build JSON-RPC internal error (-32603)."""
    return _jsonrpc_error(request_id, -32603, f"Internal error: {message}")


class McpSessionState(enum.Enum):
    """MCP protocol session lifecycle states."""

    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    READY = "ready"
    CLOSED = "closed"


class McpSession:
    """MCP protocol session with lifecycle state management.

    Owns negotiated protocol version, client info, and lifecycle state.
    The ``handle_message`` method dispatches JSON-RPC requests and
    notifications with lifecycle enforcement.
    """

    def __init__(self, *, initial_state: McpSessionState = McpSessionState.READY):
        self.state = initial_state
        self.negotiated_version: str | None = None
        self.requested_version: str | None = None
        self.client_name: str | None = None
        self.client_version: str | None = None
        self.client_info: dict | None = None
        self.client_capabilities: dict | None = None
        self.request_id: str | None = None
        # Session-scoped cancellation records. Each session owns its own
        # set + deque + lock so sessions are isolated from each other.
        self._cancelled_requests: set[Any] = set()
        self._cancelled_requests_order: deque[Any] = deque()
        self._cancelled_lock = threading.Lock()

    def handle_message(self, request: dict) -> dict | None:
        """Route MCP request to appropriate handler with lifecycle enforcement."""
        method = request.get("method", "")
        request_id = request.get("id")

        # Lifecycle state check
        error = self._check_ready_for_dispatch(method, request_id)
        if error is not None:
            return error

        # Dispatch
        if method == "initialize":
            return self._handle_initialize(request)
        elif method == "notifications/initialized":
            self._handle_notifications_initialized()
            return None
        elif method == "notifications/cancelled":
            self._handle_cancelled(request)
            return None
        elif method == "ping":
            return {"jsonrpc": "2.0", "id": request_id, "result": {}}
        elif method == "tools/list":
            return _handle_list_tools(request)
        elif method == "tools/call":
            return _handle_call_tool(
                request,
                cancelled_set=self._cancelled_requests,
                cancelled_order=self._cancelled_requests_order,
                cancelled_lock=self._cancelled_lock,
            )
        elif method == "profiles/list":
            return _handle_list_profiles(request)
        elif method.startswith("notifications/"):
            # Unknown notifications are silently ignored per MCP spec
            return None
        else:
            display = method[:100] + "..." if len(method) > 100 else method
            return _method_not_found(request_id, display)

    def _check_ready_for_dispatch(self, method: str, request_id: Any) -> dict | None:
        """Check if session state allows this method to be dispatched."""
        if method == "initialize":
            if self.state == McpSessionState.UNINITIALIZED:
                return None
            return _invalid_request_error(request_id, "Server already initialized")

        if method == "notifications/initialized":
            return None  # Always accepted (silently ignored in wrong state)

        if method == "ping":
            return None  # Allowed in any state

        if method == "notifications/cancelled":
            return None  # Always accepted

        # All other methods require READY state
        if self.state != McpSessionState.READY:
            return _invalid_request_error(request_id, "Server not initialized")

        return None

    def _handle_initialize(self, request: dict) -> dict:
        """Handle an initialize MCP request with parameter validation."""
        params = request.get("params")
        if not isinstance(params, dict):
            return _invalid_params(request.get("id"), "initialize params must be an object")

        protocol_version = params.get("protocolVersion")
        if not isinstance(protocol_version, str) or not protocol_version.strip():
            return _invalid_params(request.get("id"), "protocolVersion must be a non-empty string")

        capabilities = params.get("capabilities")
        if not isinstance(capabilities, dict):
            return _invalid_params(request.get("id"), "capabilities must be an object")

        client_info = params.get("clientInfo")
        if not isinstance(client_info, dict):
            return _invalid_params(request.get("id"), "clientInfo must be an object")

        client_name = client_info.get("name")
        if not isinstance(client_name, str) or not client_name.strip():
            return _invalid_params(request.get("id"), "clientInfo.name must be a non-empty string")

        client_version = client_info.get("version", "")

        # Version negotiation
        if protocol_version in SUPPORTED_PROTOCOL_VERSIONS:
            negotiated = protocol_version
        else:
            negotiated = LATEST_SUPPORTED_PROTOCOL_VERSION

        self.negotiated_version = negotiated
        self.requested_version = protocol_version
        self.client_name = client_name
        self.client_version = client_version if isinstance(client_version, str) else ""
        self.client_info = client_info
        self.client_capabilities = capabilities
        self.state = McpSessionState.INITIALIZING

        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "result": {
                "protocolVersion": negotiated,
                "capabilities": {
                    "tools": {"listChanged": False},
                },
                "serverInfo": {
                    "name": "eggcalc",
                    "version": __version__,
                },
            },
        }

    def _handle_notifications_initialized(self) -> None:
        """Transition from INITIALIZING to READY state."""
        if self.state == McpSessionState.INITIALIZING:
            self.state = McpSessionState.READY

    def _handle_cancelled(self, request: dict) -> None:
        """Handle notifications/cancelled using session-scoped cancellation state."""
        params = request.get("params", {})
        if not isinstance(params, dict):
            return None
        cancelled_id = params.get("requestId")
        if (
            cancelled_id is not None
            and isinstance(cancelled_id, (str, int))
            and not isinstance(cancelled_id, bool)
        ):
            with self._cancelled_lock:
                if cancelled_id not in self._cancelled_requests:
                    self._cancelled_requests.add(cancelled_id)
                    self._cancelled_requests_order.append(cancelled_id)
                while len(self._cancelled_requests) > MAX_CANCELLED_REQUESTS:
                    oldest = self._cancelled_requests_order.popleft()
                    self._cancelled_requests.discard(oldest)


def _levenshtein_distance(s1: str, s2: str) -> int:
    """Compute Levenshtein edit distance between two strings."""
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    prev_row: list[int] = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row

    return prev_row[-1]


_MAX_TOOL_NAME_LENGTH = 200


def _find_close_match(name: str, handlers: dict[str, Any]) -> str | None:
    """Find a case-insensitive close match for tool name using edit distance.

    Returns the best matching tool name, or None if no good match found.
    A match is considered good if the edit distance is at most half the length
    of the shorter string, or if it's a prefix/substring match.
    """
    if len(name) > _MAX_TOOL_NAME_LENGTH:
        return None
    name_lower = name.lower()

    # First check for exact case-insensitive match
    for tool_name in handlers:
        if tool_name.lower() == name_lower:
            return tool_name

    # Find best match by edit distance
    best_match: str | None = None
    best_distance = float('inf')

    def _at_word_boundary(sub: str, s: str) -> bool:
        idx = s.find(sub)
        if idx == -1:
            return False
        if idx == 0:
            return True
        return s[idx - 1] in ('_', '-')

    for tool_name in handlers:
        tool_lower = tool_name.lower()

        if _at_word_boundary(name_lower, tool_lower) or _at_word_boundary(tool_lower, name_lower):
            if best_match is None or len(tool_name) < len(best_match):
                best_match = tool_name
                best_distance = 0
            continue

        # Compute edit distance
        distance = _levenshtein_distance(name_lower, tool_lower)
        threshold = min(len(name_lower), len(tool_lower)) // 2

        if distance < best_distance and distance <= threshold:
            best_distance = distance
            best_match = tool_name

    return best_match


def _validate_arguments(handler: Any, arguments: dict[str, Any]) -> str | None:
    """Validate that arguments match the handler's signature.

    Returns None if valid, or an error message string if invalid.
    """
    try:
        sig = inspect.signature(handler)
    except (ValueError, TypeError):
        # Can't introspect; allow call (handler will raise on bad args)
        return None

    params = sig.parameters
    has_var_keyword = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())

    # Check for unexpected keyword arguments (skip if handler accepts **kwargs)
    if not has_var_keyword:
        unexpected = set(arguments.keys()) - set(params.keys())
        if unexpected:
            return f"Unexpected argument(s): {', '.join(sorted(unexpected))}"

    # Check for missing required arguments (no default)
    for name, param in params.items():
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue
        if param.default is inspect.Parameter.empty and name not in arguments:
            return f"Missing required argument: {name}"

    return None


def _run_handler_in_thread(handler: Any, arguments: dict[str, Any]) -> Any:
    """Run a tool handler on a pool thread, returning the result or raising."""
    return handler(**arguments)


def _json_value_equal(a: Any, b: Any) -> bool:
    """Recursively compare two JSON-like values for structural equality.

    Used by uniqueItems to detect duplicates among unhashable items (dicts,
    lists) as well as scalars. Floats compare exactly — JSON Schema does not
    require a canonical NaN or ±0 representation, so we use Python's `==`.
    """
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        if a.keys() != b.keys():
            return False
        return all(_json_value_equal(a[k], b[k]) for k in a)
    if isinstance(a, list):
        if len(a) != len(b):
            return False
        return all(_json_value_equal(x, y) for x, y in zip(a, b))
    return bool(a == b)


def _validate_value_against_schema(
    value: Any, prop: dict, path: str, max_depth: int = 10
) -> str | None:
    """Validate a single value against a JSON schema property definition.

    Returns None if valid, or an error message string if invalid.
    Supports recursive validation for nested objects and arrays.

    Supported keywords (subset of JSON Schema):
      type, enum, const, default (ignored — Python kwargs handle defaults),
      minimum, maximum, exclusiveMinimum, exclusiveMaximum, multipleOf,
      minLength, maxLength, pattern, format (ignored — see TODO),
      minItems, maxItems, uniqueItems, items, properties, required,
      additionalProperties.

    Unsupported (silently ignored): oneOf, anyOf, allOf, not, $ref,
    patternProperties, dependencies.
    """
    if max_depth <= 0:
        return f"Schema nesting too deep at '{path}'"

    # Reject boolean schemas (true/false) — we don't honor them.
    if not isinstance(prop, dict):
        return f"Schema for '{path}' must be an object"

    expected_type = prop.get("type")
    if expected_type is None:
        return None

    # JSON Schema allows type as a string or a list of strings (e.g.
    # ["string", "null"] for a nullable field). We support both forms.
    if isinstance(expected_type, list):
        type_options = expected_type
    elif isinstance(expected_type, str):
        type_options = [expected_type]
    else:
        return f"Argument '{path}' has unsupported 'type' (must be a string or list of strings, got {type(expected_type).__name__})"

    type_map = {
        "string": str,
        "number": (int, float),
        "integer": int,
        "boolean": bool,
        "array": list,
        "object": dict,
        "null": type(None),
    }

    if not all(t in type_map for t in type_options):
        return f"Argument '{path}' has unknown 'type' value(s): {expected_type!r}"

    # Build the union of allowed Python types from the schema's type list.
    allowed_types: list = []
    for t in type_options:
        mapped = type_map[t]
        if isinstance(mapped, tuple):
            allowed_types.extend(mapped)
        else:
            allowed_types.append(mapped)
    allowed_types_tuple: tuple = tuple(allowed_types)

    if not isinstance(value, allowed_types_tuple):
        # Preserve the original "must be X" wording for single-type
        # schemas (used by tests and external consumers). For list
        # schemas (nullable fields), use the explicit "one of [...]"
        # form so the user sees all valid types.
        if len(type_options) == 1:
            return f"Argument '{path}' must be {type_options[0]}, got {type(value).__name__}"
        return f"Argument '{path}' must be one of [{', '.join(type_options)}], got {type(value).__name__}"

    # Bool is subclass of int in Python; reject bool when any numeric type is allowed
    if any(t in ("integer", "number") for t in type_options) and isinstance(value, bool):
        if len(type_options) == 1:
            return f"Argument '{path}' must be {type_options[0]}, got bool"
        return f"Argument '{path}' must be one of [{', '.join(type_options)}], got bool"

    const_value = prop.get("const")
    if const_value is not None and value != const_value:
        return f"Argument '{path}' must equal {const_value!r}, got {value!r}"

    enum_values = prop.get("enum")
    if enum_values is not None and value not in enum_values:
        return f"Argument '{path}' must be one of: {', '.join(str(v) for v in enum_values)}"

    # String length constraints + pattern
    if "string" in type_options and isinstance(value, str):
        min_length = prop.get("minLength")
        if min_length is not None and len(value) < min_length:
            return f"Argument '{path}' length {len(value)} is less than minLength {min_length}"
        max_length = prop.get("maxLength")
        if max_length is not None and len(value) > max_length:
            return f"Argument '{path}' length {len(value)} exceeds maxLength {max_length}"
        pattern = prop.get("pattern")
        if pattern is not None:
            try:
                import re as _re

                if _re.search(pattern, value) is None:
                    return f"Argument '{path}' does not match pattern {pattern!r}"
            except _re.error as e:
                return f"Argument '{path}' has invalid pattern: {e}"

    # Numeric range constraints
    if (
        any(t in ("number", "integer") for t in type_options)
        and isinstance(value, (int, float))
        and not isinstance(value, bool)
    ):
        import math as _math

        if _math.isnan(value):
            return f"Argument '{path}' must be a finite number, got NaN"
        if _math.isinf(value):
            return (
                f"Argument '{path}' must be a finite number, got {'+inf' if value > 0 else '-inf'}"
            )
        minimum = prop.get("minimum")
        if minimum is not None and value < minimum:
            return f"Argument '{path}' value {value} is less than minimum {minimum}"
        maximum = prop.get("maximum")
        if maximum is not None and value > maximum:
            return f"Argument '{path}' value {value} exceeds maximum {maximum}"
        excl_min = prop.get("exclusiveMinimum")
        if excl_min is not None and value <= excl_min:
            return f"Argument '{path}' value {value} must be > exclusiveMinimum {excl_min}"
        excl_max = prop.get("exclusiveMaximum")
        if excl_max is not None and value >= excl_max:
            return f"Argument '{path}' value {value} must be < exclusiveMaximum {excl_max}"
        multiple = prop.get("multipleOf")
        if multiple is not None and multiple > 0 and not isinstance(value, bool):
            remainder = value % multiple
            if not _math.isclose(remainder, 0, rel_tol=1e-9, abs_tol=1e-12):
                return f"Argument '{path}' value {value} is not a multiple of {multiple}"

    # Recursive validation for nested objects (only when sub-schema defines properties)
    if "object" in type_options and isinstance(value, dict):
        sub_props = prop.get("properties", {})
        sub_required = prop.get("required", [])
        sub_additional = prop.get("additionalProperties", False)

        # Only validate recursively if the schema actually defines sub-properties
        # or required fields. Opaque object types (no sub-schema) are accepted as-is.
        if sub_props or sub_required:
            for field in sub_required:
                if field not in value:
                    return f"Missing required field '{field}' in '{path}'"

            if not sub_additional:
                unknown = set(value.keys()) - set(sub_props.keys())
                if unknown:
                    return f"Unexpected field(s) in '{path}': {', '.join(sorted(unknown))}"

            for sub_key, sub_val in value.items():
                if sub_key in sub_props:
                    err = _validate_value_against_schema(
                        sub_val, sub_props[sub_key], f"{path}.{sub_key}", max_depth=max_depth - 1
                    )
                    if err:
                        return err

    # Recursive validation for arrays
    if "array" in type_options and isinstance(value, list):
        min_items = prop.get("minItems")
        if min_items is not None and len(value) < min_items:
            return f"Argument '{path}' has {len(value)} items, less than minItems {min_items}"
        max_items = prop.get("maxItems")
        if max_items is not None and len(value) > max_items:
            return f"Argument '{path}' has {len(value)} items, exceeds maxItems {max_items}"

        if prop.get("uniqueItems") is True:
            seen: list[Any] = []
            for item in value:
                duplicate = False
                for prev in seen:
                    if _json_value_equal(prev, item):
                        duplicate = True
                        break
                if duplicate:
                    return f"Argument '{path}' has duplicate items but uniqueItems is True"
                seen.append(item)

        items_schema = prop.get("items")
        if items_schema:
            for i, item in enumerate(value):
                err = _validate_value_against_schema(
                    item, items_schema, f"{path}[{i}]", max_depth=max_depth - 1
                )
                if err:
                    return err

    return None


def _validate_arguments_schema(name: str, arguments: dict[str, Any]) -> str | None:
    """Validate arguments against the tool's inputSchema from TOOL_SCHEMAS.

    Returns None if valid, or an error message string if invalid.
    """
    schema = TOOL_SCHEMAS.get(name, {}).get("inputSchema")
    if not schema:
        return None

    props = schema.get("properties", {})
    required = schema.get("required", [])
    additional_allowed = schema.get("additionalProperties", False)

    for field in required:
        if field not in arguments:
            return f"Missing required argument: {field}"

    if not additional_allowed:
        unknown = set(arguments.keys()) - set(props.keys())
        if unknown:
            return f"Unexpected argument(s): {', '.join(sorted(unknown))}"

    for key, value in arguments.items():
        if key not in props:
            continue
        err = _validate_value_against_schema(value, props[key], key)
        if err:
            return err

    return None


def _handle_call_tool(
    request: dict,
    cancelled_set: set[Any] | None = None,
    cancelled_order: deque[Any] | None = None,
    cancelled_lock: threading.Lock | None = None,
) -> dict:
    """Handle a tools/call MCP request."""
    # Lazily clean up any orphaned processes from previous timed-out requests
    _cleanup_orphaned_processes()

    params = request.get("params", {})
    if not isinstance(params, dict):
        return _invalid_request(request.get("id"), "Invalid params: expected object")

    name = params.get("name", "")
    arguments = params.get("arguments", {})
    if not isinstance(name, str) or not name:
        return _invalid_request(request.get("id"), "Invalid params: missing tool name")
    if not isinstance(arguments, dict):
        return _invalid_request(request.get("id"), "Invalid arguments: expected object")

    if name not in TOOL_HANDLERS:
        close = _find_close_match(name, TOOL_HANDLERS)
        msg = f"Unknown tool: {name}"
        if close:
            msg += f". Did you mean: {close}?"
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "error": {
                "code": -32601,
                "message": msg,
            },
        }

    # Enforce active profile: reject tools not in the current profile
    profile = get_active_profile()
    try:
        profile_tools = get_profile_tools(profile)
    except ValueError as e:
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "error": {
                "code": -32602,
                "message": str(e),
            },
        }
    if name not in profile_tools:
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "error": {
                "code": -32602,
                "message": (
                    f"Tool '{name}' is not available in profile '{profile}'. "
                    f"Use tools/list to see available tools, or switch profile."
                ),
            },
        }

    # Validate arguments against handler signature before calling
    handler = TOOL_HANDLERS[name]
    validation_error = _validate_arguments(handler, arguments)
    if validation_error is not None:
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "error": {
                "code": -32602,
                "message": f"Invalid arguments for tool '{name}': {validation_error}",
            },
        }

    schema_error = _validate_arguments_schema(name, arguments)
    if schema_error is not None:
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "error": {
                "code": -32602,
                "message": f"Invalid arguments for tool '{name}': {schema_error}",
            },
        }

    req_id = request.get("id")
    _c_lock = cancelled_lock
    _c_set = cancelled_set
    _c_order = cancelled_order
    if _c_lock is not None and _c_set is not None:
        with _c_lock:
            if req_id is not None and req_id in _c_set:
                # Remove from both the set and the FIFO order queue
                _c_set.discard(req_id)
                if _c_order is not None:
                    try:
                        _c_order.remove(req_id)
                    except ValueError:
                        pass
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(
                                    {
                                        "ok": False,
                                        "error": f"Tool '{name}' request was cancelled",
                                        "error_type": "cancelled",
                                        "hints": [],
                                        "tool": name,
                                        "warnings": [],
                                    }
                                ),
                            }
                        ],
                        "isError": True,
                    },
                }

    timed_out = False
    result = None
    future: Future | None = None
    try:
        # Submit to a bounded thread pool instead of spawning unbounded
        # daemon threads. This prevents thread accumulation when tools
        # consistently time out under sustained load. The pool provides
        # natural back-pressure: tasks queue when all workers are busy.
        executor = _get_tool_executor()
        future = executor.submit(_run_handler_in_thread, handler, arguments)
        result = future.result(timeout=MAX_TOOL_TIMEOUT_SECONDS)
    except FuturesTimeoutError:
        timed_out = True
        # Cancel the future so the worker thread can return promptly.
        # cancel() is best-effort: it returns False if the task is
        # already running, in which case the worker will complete on
        # its own. In either case, we MUST not block waiting on the
        # future; just log and return a timeout error to the client.
        if future is not None:
            cancelled = future.cancel()
            if not cancelled:
                logging.warning(
                    "MCP tool '%s' timed out after %ds; "
                    "worker already running and cannot be cancelled",
                    name,
                    MAX_TOOL_TIMEOUT_SECONDS,
                )
            else:
                logging.info(
                    "MCP tool '%s' cancelled before execution began",
                    name,
                )
    except Exception as e:
        message = _sanitize_error(str(e))[:2000]
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "error": {
                "code": -32000,
                "message": f"Tool execution error: {message}",
            },
        }

    if timed_out:
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {
                                "ok": False,
                                "error": f"Tool '{name}' execution timed out after {MAX_TOOL_TIMEOUT_SECONDS}s",
                                "error_type": "timeout",
                                "hints": ["Try a simpler input or shorter text"],
                                "tool": name,
                                "warnings": [],
                            }
                        ),
                    }
                ],
                "isError": True,
            },
        }

    # If result is an error envelope, return as MCP tool result with isError
    if isinstance(result, dict) and result.get("ok") is False:
        serialized = json.dumps(result)
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "result": {
                "content": [{"type": "text", "text": serialized}],
                "isError": True,
            },
        }

    serialized = json.dumps(result)
    if len(serialized.encode("utf-8")) > MAX_OUTPUT_BYTES:
        truncated = {
            "ok": False,
            "tool": name,
            "error_type": "output_too_large",
            "error": f"Output exceeds {MAX_OUTPUT_BYTES} bytes and was truncated",
            "hints": ["Try reducing input size or using a summary/detail option"],
            "warnings": ["Output was truncated due to size limit"],
        }
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(truncated),
                    }
                ],
                "isError": True,
            },
        }

    return {
        "jsonrpc": "2.0",
        "id": request.get("id"),
        "result": {
            "content": [
                {
                    "type": "text",
                    "text": serialized,
                }
            ]
        },
    }


def _handle_list_tools(request: dict) -> dict:
    """Handle a tools/list MCP request with optional filtering."""
    params = request.get("params", {})
    request_id = request.get("id")
    if not isinstance(params, dict):
        return _invalid_request(request_id, "Invalid params: expected object")

    tier_filter = params.get("tier")
    tags_filter = params.get("tags")
    names_filter = params.get("names")
    profile_filter = params.get("profile")
    schema_detail_param = params.get("schema_detail")

    if tier_filter is not None and not isinstance(tier_filter, int):
        return _invalid_request(request_id, "Invalid 'tier' parameter: expected integer")
    if tags_filter is not None and not isinstance(tags_filter, list):
        return _invalid_request(request_id, "Invalid 'tags' parameter: expected array")
    if tags_filter is not None and not all(isinstance(t, str) for t in tags_filter):
        return _invalid_request(request_id, "Invalid 'tags' parameter: all items must be strings")
    if names_filter is not None and not isinstance(names_filter, list):
        return _invalid_request(request_id, "Invalid 'names' parameter: expected array")
    if names_filter is not None and not all(isinstance(n, str) for n in names_filter):
        return _invalid_request(request_id, "Invalid 'names' parameter: all items must be strings")
    if profile_filter is not None and not isinstance(profile_filter, str):
        return _invalid_request(request_id, "Invalid 'profile' parameter: expected string")
    if schema_detail_param is not None and schema_detail_param not in ("compact", "normal", "full"):
        return _invalid_request(
            request_id, "Invalid 'schema_detail' parameter: expected compact, normal, or full"
        )

    # Schema detail: per-request override or global default
    detail = schema_detail_param or get_schema_detail()
    use_compact = detail == "compact"
    schema_detail = detail

    # Determine profile-visible tools
    try:
        profile_tools = set(get_profile_tools(profile_filter))
    except ValueError as e:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32602,
                "message": str(e),
            },
        }

    tools = []
    for name, schema in TOOL_SCHEMAS.items():
        if name not in profile_tools:
            continue

        if names_filter is not None:
            if name not in names_filter:
                continue

        if tier_filter is not None:
            if schema.get("tier") != tier_filter:
                continue

        if tags_filter is not None:
            tool_tags = set(schema.get("tags", []))
            if not all(tag in tool_tags for tag in tags_filter):
                continue

        meta = TOOL_METADATA.get(name, {})
        if use_compact:
            entry = compact_schema(schema)
            entry["name"] = name
            entry["category"] = meta.get("category")
            entry["llm_exposure"] = meta.get("llm_exposure")
            entry["cost"] = meta.get("cost")
        elif schema_detail == "normal":
            entry = normal_schema(schema)
            entry["name"] = name
            entry["tier"] = schema.get("tier")
            entry["tags"] = schema.get("tags", [])
            entry["category"] = meta.get("category")
            entry["llm_exposure"] = meta.get("llm_exposure")
            entry["cost"] = meta.get("cost")
        else:
            entry = {
                "name": name,
                "description": schema["description"],
                "inputSchema": schema["inputSchema"],
                "outputSchema": schema.get("outputSchema"),
                "tier": schema.get("tier"),
                "tags": schema.get("tags", []),
                "deprecated": schema.get("deprecated", False),
                "category": meta.get("category"),
                "llm_exposure": meta.get("llm_exposure"),
                "cost": meta.get("cost"),
            }
        tools.append(entry)

    return {
        "jsonrpc": "2.0",
        "id": request.get("id"),
        "result": {"tools": tools},
    }


def _handle_initialize(request: dict) -> dict:
    """Handle an initialize MCP request."""
    params = request.get("params")
    if not isinstance(params, dict):
        return _invalid_params(request.get("id"), "initialize params must be an object")

    protocol_version = params.get("protocolVersion")
    if not isinstance(protocol_version, str) or not protocol_version.strip():
        return _invalid_params(request.get("id"), "protocolVersion must be a non-empty string")

    capabilities = params.get("capabilities")
    if not isinstance(capabilities, dict):
        return _invalid_params(request.get("id"), "capabilities must be an object")

    client_info = params.get("clientInfo")
    if not isinstance(client_info, dict):
        return _invalid_params(request.get("id"), "clientInfo must be an object")

    client_name = client_info.get("name")
    if not isinstance(client_name, str) or not client_name.strip():
        return _invalid_params(request.get("id"), "clientInfo.name must be a non-empty string")

    client_version = client_info.get("version", "")

    # Version negotiation
    if protocol_version in SUPPORTED_PROTOCOL_VERSIONS:
        negotiated = protocol_version
    else:
        negotiated = LATEST_SUPPORTED_PROTOCOL_VERSION

    return {
        "jsonrpc": "2.0",
        "id": request.get("id"),
        "result": {
            "protocolVersion": negotiated,
            "capabilities": {
                "tools": {"listChanged": False},
            },
            "serverInfo": {
                "name": "eggcalc",
                "version": __version__,
            },
        },
    }


def _handle_list_profiles(request: dict) -> dict:
    """Handle a profiles/list MCP request."""
    params = request.get("params", {})
    if not isinstance(params, dict):
        return _invalid_request(request.get("id"), "Invalid params: expected object")

    active = get_active_profile()

    profiles_info = {}
    for name in PROFILE_NAMES:
        tool_list = TOOL_PROFILES.get(name, [])
        profiles_info[name] = {
            "tools": tool_list,
            "tool_count": len(tool_list),
        }

    return {
        "jsonrpc": "2.0",
        "id": request.get("id"),
        "result": {
            "active_profile": active,
            "profiles": profiles_info,
            "available_profiles": PROFILE_NAMES,
        },
    }


_default_session: McpSession | None = None


def handle_request(request: Any, session: McpSession | None = None) -> dict | None:
    """Route MCP request to appropriate handler.

    If *session* is ``None`` a module-level default session (starting in
    READY state) is used for backward compatibility — existing callers
    that do not perform the handshake will continue to work unchanged.
    Callers that pass an explicit ``McpSession`` get full lifecycle
    enforcement.
    """
    # Ensure MCP-safe defaults are in effect. Idempotent: a one-time
    # check is enough to set _mcp_mode and configure the default
    # evaluator. We do this on first call (not at import time) so that
    # importing this module for any reason does not globally disable
    # random/setvar in the default evaluator — only code that actually
    # uses the MCP server gets the MCP-safe defaults.
    global _mcp_defaults_configured, _default_session
    with _mcp_defaults_lock:
        if not _mcp_defaults_configured:
            _evaluator._mcp_mode = True
            _evaluator.configure_default_evaluator(
                allow_random=False,
                allow_side_effects=False,
            )
            _mcp_defaults_configured = True

    if not isinstance(request, dict):
        return _invalid_request(None, "Invalid Request: expected JSON object")

    # Validate JSON-RPC version
    jsonrpc_version = request.get("jsonrpc")
    if jsonrpc_version != "2.0":
        return _invalid_request(
            request.get("id"),
            f"Invalid Request: jsonrpc must be '2.0', got '{jsonrpc_version}'",
        )

    # Validate 'id' type before checking 'method' (per JSON-RPC 2.0 spec)
    request_id = request.get("id")
    # Explicit null id on a request is rejected: requests must have a
    # non-null string or integer id.  Notifications omit "id" entirely.
    if "id" in request and request_id is None and "method" in request:
        return _invalid_request(
            None,
            "Invalid Request: 'id' must be a string or integer, not null",
        )
    if request_id is not None:
        # bool is a subclass of int in Python, so exclude it explicitly
        if not isinstance(request_id, (str, int)) or isinstance(request_id, bool):
            return _invalid_request(
                None,
                "Invalid Request: 'id' must be a string, integer, or null",
            )
        id_str = str(request_id)
        if len(id_str) > MAX_REQUEST_ID_LENGTH:
            return _invalid_request(
                None,
                f"Invalid Request: 'id' exceeds maximum length of {MAX_REQUEST_ID_LENGTH}",
            )

    if "method" not in request:
        return _invalid_request(request_id, "Invalid Request: missing 'method'")

    method = request["method"]
    if not isinstance(method, str):
        return _invalid_request(
            request.get("id"),
            "Invalid Request: 'method' must be a string",
        )

    # Get or create session for backward compatibility
    if session is None:
        warnings.warn(
            "Calling handle_request() without an explicit session is deprecated. "
            "Pass a McpSession instance for full lifecycle enforcement. "
            "This compatibility path will be removed in a future version.",
            DeprecationWarning,
            stacklevel=2,
        )
        if _default_session is None:
            _default_session = McpSession()
        session = _default_session

    return session.handle_message(request)


def main() -> int:
    """Main entry point for MCP server.

    Reads JSON-RPC requests from stdin and writes responses to stdout.
    Creates one McpSession per connection for lifecycle management.
    """
    os.environ["EGGCALC_NO_CONFIG"] = "1"
    # MCP-safe defaults are configured by handle_request() on first call,
    # so the very first request also sets them. We do not need to
    # configure them here.
    request_times: deque[float] = deque()
    window = 1.0  # sliding window in seconds
    session = McpSession(initial_state=McpSessionState.UNINITIALIZED)

    for line in sys.stdin:
        try:
            line = line.strip()
            if not line:
                continue

            response: dict[str, Any] | None = None
            if len(line.encode('utf-8')) > MAX_REQUEST_BYTES:
                response = _parse_error(
                    None,
                    f"Request exceeds maximum size of {MAX_REQUEST_BYTES} bytes",
                )
                print(json.dumps(response), flush=True)
                continue

            if line.startswith('['):
                response = _invalid_request_error(None, "Batch requests are not supported")
                print(json.dumps(response), flush=True)
                continue

            try:
                request = json.loads(line)
            except json.JSONDecodeError:
                response = _parse_error(None, "Parse error: invalid JSON")
                print(json.dumps(response), flush=True)
                continue

            now = time.monotonic()
            while request_times and request_times[0] < now - window:
                request_times.popleft()

            if len(request_times) >= MAX_REQUESTS_PER_SECOND:
                response = _invalid_request_error(
                    request.get("id") if isinstance(request, dict) else None,
                    f"Rate limit exceeded: max {MAX_REQUESTS_PER_SECOND} requests per second",
                )
                print(json.dumps(response), flush=True)
                continue

            request_times.append(now)

            try:
                response = handle_request(request, session=session)
            except Exception as e:
                message = _sanitize_error(str(e))[:2000]
                response = _internal_error(
                    request.get("id") if isinstance(request, dict) else None,
                    message,
                )

            if response is not None:
                try:
                    print(json.dumps(response), flush=True)
                except TypeError:
                    fallback = _internal_error(None, "response not JSON-serializable")
                    print(json.dumps(fallback), flush=True)
        except BrokenPipeError:
            return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# Build-time alias for MCP entry point
mcp_main = main
