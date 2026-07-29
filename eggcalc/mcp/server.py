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
import weakref
from collections import deque
from collections.abc import Mapping
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from dataclasses import dataclass as _dataclass
from dataclasses import field as _field
from types import MappingProxyType
from typing import Any, cast

from .. import __version__
from .. import evaluator as _evaluator
from ..capabilities import detect_capabilities
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

from eggcalc._protocol import (
    LATEST_SUPPORTED_PROTOCOL_VERSION,
    SUPPORTED_PROTOCOL_VERSIONS,
)

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
    _invalidate_compat_server()


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


def _invalid_request(request_id: Any, message: str) -> dict[str, Any]:
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


def _jsonrpc_error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    """Build a JSON-RPC error response."""
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _parse_error(request_id: Any = None, message: str = "Parse error") -> dict[str, Any]:
    """Build JSON-RPC parse error (-32700)."""
    return _jsonrpc_error(request_id, -32700, message)


def _method_not_found(request_id: Any, method: str) -> dict[str, Any]:
    """Build JSON-RPC method not found error (-32601)."""
    display = method[:100] + "..." if len(method) > 100 else method
    return _jsonrpc_error(request_id, -32601, f"Method not found: {display}")


def _invalid_params(request_id: Any, message: str) -> dict[str, Any]:
    """Build JSON-RPC invalid params error (-32602)."""
    return _jsonrpc_error(request_id, -32602, message)


def _internal_error(request_id: Any, message: str) -> dict[str, Any]:
    """Build JSON-RPC internal error (-32603)."""
    return _jsonrpc_error(request_id, -32603, f"Internal error: {message}")


@_dataclass(frozen=True)
class McpServerConfig:
    """Immutable MCP server configuration.

    Constructed once at server creation. All values are validated and
    clamped during construction. Environment variables serve as input
    adapters via ``from_environment()`` but are not authoritative at runtime.
    """

    profile: str = "full"
    schema_detail: str = "full"
    max_request_bytes: int = MAX_REQUEST_BYTES
    max_output_bytes: int = MAX_OUTPUT_BYTES
    max_requests_per_second: float = MAX_REQUESTS_PER_SECOND
    max_request_id_length: int = MAX_REQUEST_ID_LENGTH
    max_tool_timeout_seconds: int = MAX_TOOL_TIMEOUT_SECONDS
    max_cancelled_requests: int = MAX_CANCELLED_REQUESTS
    max_tool_workers: int = _MAX_TOOL_WORKERS
    max_tool_queue_size: int = 32
    supported_protocol_versions: tuple[str, ...] = SUPPORTED_PROTOCOL_VERSIONS
    allow_random: bool = False
    allow_side_effects: bool = False
    evaluation_policy: str = "default"

    def __post_init__(self) -> None:
        """Validate and clamp values after construction."""
        object.__setattr__(self, 'profile', self._clamp_profile(self.profile))
        object.__setattr__(self, 'schema_detail', self._clamp_schema_detail(self.schema_detail))
        if self.evaluation_policy not in {policy.value for policy in EvaluationPolicy}:
            raise ValueError(
                f"Invalid evaluation_policy: {self.evaluation_policy!r}; "
                f"expected one of {sorted(policy.value for policy in EvaluationPolicy)}"
            )
        object.__setattr__(
            self, 'max_request_bytes', max(1000, min(self.max_request_bytes, 100_000_000))
        )
        object.__setattr__(
            self, 'max_output_bytes', max(1, min(self.max_output_bytes, 100_000_000))
        )
        object.__setattr__(
            self, 'max_requests_per_second', max(0.1, min(self.max_requests_per_second, 1000.0))
        )
        object.__setattr__(
            self, 'max_request_id_length', max(64, min(self.max_request_id_length, 65536))
        )
        object.__setattr__(
            self, 'max_tool_timeout_seconds', max(1, min(self.max_tool_timeout_seconds, 300))
        )
        object.__setattr__(
            self, 'max_cancelled_requests', max(100, min(self.max_cancelled_requests, 1_000_000))
        )
        object.__setattr__(self, 'max_tool_workers', max(1, min(self.max_tool_workers, 128)))
        object.__setattr__(self, 'max_tool_queue_size', max(1, min(self.max_tool_queue_size, 1000)))

    @staticmethod
    def _clamp_profile(profile: str) -> str:
        """Validate profile syntax only — membership is checked at server construction.

        Accepts any non-empty string up to 128 characters with no control
        characters.  The synthetic ``"full"`` profile is always syntactically
        valid.  Actual profile membership is validated against the
        :class:`ToolRegistry` supplied to :class:`McpServer`.
        """
        if not isinstance(profile, str):
            raise ValueError(f"Profile must be a string, got {type(profile).__name__}")
        if not profile:
            raise ValueError("Profile must not be empty")
        if len(profile) > 128:
            raise ValueError(f"Profile exceeds 128 characters: {len(profile)}")
        if any(ord(c) < 32 or ord(c) == 127 for c in profile):
            raise ValueError("Profile must not contain control characters")
        return profile

    @staticmethod
    def _clamp_schema_detail(detail: str) -> str:
        if detail not in ("compact", "normal", "full"):
            raise ValueError(f"Invalid schema detail: {detail!r}. Use compact, normal, or full.")
        return detail

    @classmethod
    def from_environment(cls) -> McpServerConfig:
        """Create a config from environment variables."""
        return cls(
            profile=os.environ.get("EGGCALC_MCP_PROFILE", "full"),
            schema_detail=os.environ.get("EGGCALC_MCP_SCHEMA_DETAIL", "full"),
            max_request_bytes=_parse_env_int(
                "EGGCALC_MCP_MAX_REQUEST_BYTES", MAX_REQUEST_BYTES, 1_000, 100_000_000
            ),
            max_output_bytes=_parse_env_int(
                "EGGCALC_MCP_MAX_OUTPUT_BYTES", MAX_OUTPUT_BYTES, 1, 100_000_000
            ),
            max_requests_per_second=_parse_env_float(
                "EGGCALC_MCP_MAX_REQUESTS_PER_SECOND", MAX_REQUESTS_PER_SECOND, 0.1, 1000
            ),
            max_tool_timeout_seconds=_parse_env_int(
                "EGGCALC_MCP_MAX_TOOL_TIMEOUT_SECONDS", MAX_TOOL_TIMEOUT_SECONDS, 1, 300
            ),
            max_cancelled_requests=_parse_env_int(
                "EGGCALC_MCP_MAX_CANCELLED_REQUESTS", MAX_CANCELLED_REQUESTS, 100, 1_000_000
            ),
            max_tool_workers=_parse_env_int(
                "EGGCALC_MCP_MAX_TOOL_WORKERS", _MAX_TOOL_WORKERS, 1, 128
            ),
            max_tool_queue_size=_parse_env_int("EGGCALC_MCP_MAX_TOOL_QUEUE_SIZE", 32, 1, 1000),
            evaluation_policy=os.environ.get("EGGCALC_EVALUATION_POLICY", "default"),
        )

    @property
    def latest_protocol_version(self) -> str:
        return self.supported_protocol_versions[-1]


def _deep_freeze(obj: Any) -> Any:
    """Recursively convert mutable containers to immutable equivalents."""
    if isinstance(obj, dict):
        return MappingProxyType({k: _deep_freeze(v) for k, v in obj.items()})
    if isinstance(obj, list):
        return tuple(_deep_freeze(item) for item in obj)
    if isinstance(obj, set):
        return frozenset(_deep_freeze(item) for item in obj)
    return obj


def freeze_owned(value: Any) -> Any:
    """Recursively convert mutable containers to immutable equivalents."""
    if isinstance(value, Mapping):
        return MappingProxyType({k: freeze_owned(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(freeze_owned(v) for v in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(freeze_owned(v) for v in value)
    return value


def thaw_owned(value: Any) -> Any:
    """Recursively convert immutable containers back to mutable equivalents."""
    if isinstance(value, MappingProxyType):
        return {k: thaw_owned(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [thaw_owned(v) for v in value]
    if isinstance(value, frozenset):
        return {thaw_owned(v) for v in value}
    return value


def _deep_copy(obj: Any) -> Any:
    """Recursively copy mutable containers so originals cannot mutate us.

    Converts frozen containers back to mutable equivalents:
    MappingProxyType → dict, tuple → list, frozenset → set.
    """
    if isinstance(obj, MappingProxyType):
        return {k: _deep_copy(v) for k, v in obj.items()}
    if isinstance(obj, dict):
        return {k: _deep_copy(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_deep_copy(item) for item in obj]
    if isinstance(obj, (set, frozenset)):
        return {_deep_copy(item) for item in obj}
    return obj


class ToolRegistry:
    """Explicit ownership of tool definitions.

    Owns tool names, handlers, input schemas, output schemas,
    profiles/tags, and exposure policy. Construction is deterministic;
    duplicate tool names fail at construction. Internal state is
    deeply immutable after construction — nested dicts, lists, and
    profile lists are defensively copied so callers cannot mutate the
    registry through constructor inputs or accessor return values.
    """

    _VALID_LLM_EXPOSURE: frozenset[str] = frozenset(
        {"default", "contextual", "expert_only", "harness_only", "hidden"}
    )

    def __init__(
        self,
        handlers: dict[str, Any] | None = None,
        schemas: dict[str, dict[str, Any]] | None = None,
        metadata: dict[str, dict[str, Any]] | None = None,
        profiles: dict[str, list[str]] | None = None,
    ) -> None:
        raw_handlers = handlers or TOOL_HANDLERS
        raw_schemas = schemas or TOOL_SCHEMAS
        raw_metadata = metadata or TOOL_METADATA
        raw_profiles = profiles or TOOL_PROFILES

        self._handlers: MappingProxyType[str, Any] = freeze_owned(dict(raw_handlers))
        self._schemas: MappingProxyType[str, Any] = freeze_owned(raw_schemas)
        self._metadata: MappingProxyType[str, Any] = freeze_owned(raw_metadata)
        self._profiles: MappingProxyType[str, tuple[str, ...]] = freeze_owned(
            {name: tuple(tools) for name, tools in raw_profiles.items()}
        )

        handler_names = set(self._handlers.keys())

        # Detect case-normalized collisions — tool lookup is case-insensitive
        # in find_close_match(), so two handlers that differ only in case
        # would be ambiguous.
        seen_normalized: set[str] = set()
        for name in self._handlers:
            norm = name.lower()
            if norm in seen_normalized:
                raise ValueError(
                    f"Case-collision: {name!r} conflicts with another tool "
                    f"that normalizes to {norm!r}"
                )
            seen_normalized.add(norm)

        seen_handlers: set[str] = set()
        for name in self._handlers:
            if name in seen_handlers:
                raise ValueError(f"Duplicate tool handler: {name!r}")
            seen_handlers.add(name)

        schema_names = set(self._schemas.keys())
        metadata_names = set(self._metadata.keys())

        missing_schemas = handler_names - schema_names
        if missing_schemas:
            raise ValueError(f"Handlers without schemas: {sorted(missing_schemas)}")

        orphan_schemas = schema_names - handler_names
        if orphan_schemas:
            raise ValueError(f"Schemas without handlers: {sorted(orphan_schemas)}")

        orphan_metadata = metadata_names - handler_names
        if orphan_metadata:
            raise ValueError(f"Metadata for unregistered tools: {sorted(orphan_metadata)}")

        for name in self._metadata:
            exposure = self._metadata[name].get("llm_exposure")
            if exposure is not None and exposure not in self._VALID_LLM_EXPOSURE:
                raise ValueError(
                    f"Unsupported llm_exposure {exposure!r} for tool {name!r}; "
                    f"must be one of {sorted(self._VALID_LLM_EXPOSURE)}"
                )

        for profile_name, profile_tools in self._profiles.items():
            if not profile_name:
                raise ValueError("Profile name must not be empty")
            if any(ord(c) < 32 or ord(c) == 127 for c in profile_name):
                raise ValueError(
                    f"Profile name must not contain control characters: {profile_name!r}"
                )
            if not isinstance(profile_tools, (list, tuple)):
                raise ValueError(
                    f"Profile {profile_name!r} must be a list of tool names, "
                    f"got {type(profile_tools).__name__}"
                )
            seen_in_profile: set[str] = set()
            for tool_name in profile_tools:
                if tool_name in seen_in_profile:
                    raise ValueError(f"Duplicate tool {tool_name!r} in profile {profile_name!r}")
                seen_in_profile.add(tool_name)
                if tool_name not in handler_names:
                    raise ValueError(
                        f"Profile {profile_name!r} references unknown tool: {tool_name!r}"
                    )

    @property
    def handlers(self) -> MappingProxyType[str, Any]:
        return self._handlers

    @property
    def schemas(self) -> MappingProxyType[str, Any]:
        return self._schemas

    @property
    def metadata(self) -> MappingProxyType[str, Any]:
        return self._metadata

    @property
    def profiles(self) -> MappingProxyType[str, tuple[str, ...]]:
        return self._profiles

    @property
    def tool_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._handlers.keys()))

    def has_tool(self, name: str) -> bool:
        return name in self._handlers

    def get_handler(self, name: str) -> Any | None:
        return self._handlers.get(name)

    def get_schema(self, name: str) -> dict[str, Any] | None:
        schema = self._schemas.get(name)
        if schema is None:
            return None
        # Return a deep copy so callers cannot mutate internal state
        # through nested dicts (e.g. inputSchema.properties).
        result: dict[str, Any] = _deep_copy(dict(schema))
        return result

    def get_metadata(self, name: str) -> dict[str, Any]:
        meta = self._metadata.get(name)
        if meta is None:
            return {}
        result: dict[str, Any] = _deep_copy(dict(meta))
        return result

    def get_profile_tools(self, profile: str | None = None) -> list[str]:
        """Return sorted tool names for a profile."""
        if profile is None:
            profile = "full"
        if profile == "full":
            return sorted(
                name
                for name, meta in self._metadata.items()
                if meta.get("llm_exposure") != "hidden"
            )
        if profile not in self._profiles:
            available = ", ".join(sorted(self._profiles))
            raise ValueError(f"Unknown profile: {profile!r}. Available: {available}")
        return list(self._profiles[profile])

    def is_tool_visible(self, name: str, profile: str | None = None) -> bool:
        """Check whether *name* is callable under the given profile."""
        if not self.has_tool(name):
            return False
        try:
            return name in self.get_profile_tools(profile)
        except ValueError:
            return False

    def find_close_match(self, name: str) -> str | None:
        """Find a case-insensitive close match for a tool name."""
        return _find_close_match(name, self._handlers)


class ReservationState(enum.Enum):
    """Lifecycle states for a tool-call reservation."""

    QUEUED = "queued"
    ACTIVE = "active"
    RELEASED = "released"


@_dataclass(eq=False)
class Reservation:
    """A single request's accounting reservation.

    Transitions occur under the executor's accounting lock:

    - accepted: none → QUEUED (total +1, queued +1)
    - worker starts: QUEUED → ACTIVE (queued -1, active +1)
    - queued cancel succeeds: QUEUED → RELEASED (queued -1, total -1)
    - submit fails: QUEUED → RELEASED (queued -1, total -1)
    - active handler finishes/raises: ACTIVE → RELEASED (active -1, total -1)
    - shutdown cancels queued: QUEUED → RELEASED (queued -1, total -1)
    """

    state: ReservationState = ReservationState.QUEUED


class ToolExecutor:
    """Owns tool validation, timeout, worker dispatch, and cleanup.

    Does not depend on session globals. Session state is passed explicitly.

    State accounting uses a single reservation state machine with one
    accounting lock.  Every accepted request receives exactly one
    :class:`Reservation` that transitions through QUEUED → ACTIVE →
    RELEASED exactly once.

    Counters derived from reservations:

    - ``_total_inflight``: all reservations not yet RELEASED;
    - ``_queued_count``: reservations in QUEUED state;
    - ``_active_count``: reservations in ACTIVE state.

    Invariant: ``total_inflight == queued_count + active_count``.
    """

    def __init__(
        self,
        config: McpServerConfig,
        registry: ToolRegistry,
        evaluator: _evaluator.Evaluator | None = None,
    ) -> None:
        self._config = config
        self._registry = registry
        # Evaluator is passed per-call from the captured request context.
        # A fallback is retained only for backward compatibility with
        # callers that construct ToolExecutor directly without a server.
        self._evaluator = evaluator
        self._executor: ThreadPoolExecutor | None = None
        self._lock = threading.Lock()
        self._orphaned: set[multiprocessing.Process] = set()
        self._orphan_lock = threading.Lock()
        # Unified accounting: one lock, one reservation per request.
        self._accounting_lock = threading.Lock()
        self._total_inflight = 0
        self._queued_count = 0
        self._active_count = 0
        self._reservations: set[Reservation] = set()
        self._closed = False

    def _get_executor(self) -> ThreadPoolExecutor:
        if self._closed:
            raise RuntimeError("ToolExecutor is closed")
        if self._executor is None:
            with self._lock:
                if self._closed:
                    raise RuntimeError("ToolExecutor is closed")
                if self._executor is None:
                    self._executor = ThreadPoolExecutor(
                        max_workers=self._config.max_tool_workers,
                        thread_name_prefix="mcp-tool",
                    )
        return self._executor

    # -- Reservation state machine ----------------------------------------

    def _reserve(self) -> Reservation | None:
        """Accept a request: transition none → QUEUED.

        Returns a Reservation on success, or None if the inflight limit
        is reached.  Increments total_inflight and queued_count.
        """
        max_inflight = self._config.max_tool_workers + self._config.max_tool_queue_size
        with self._accounting_lock:
            if self._total_inflight >= max_inflight:
                return None
            self._total_inflight += 1
            self._queued_count += 1
            reservation = Reservation(state=ReservationState.QUEUED)
            self._reservations.add(reservation)
        return reservation

    def _start(self, reservation: Reservation) -> bool:
        """Transition QUEUED → ACTIVE.  Returns False if already released."""
        with self._accounting_lock:
            if reservation.state != ReservationState.QUEUED:
                return False
            reservation.state = ReservationState.ACTIVE
            self._queued_count -= 1
            self._active_count += 1
        return True

    def _release_queued(self, reservation: Reservation) -> bool:
        """Release a QUEUED reservation: QUEUED → RELEASED.

        Decrements queued_count and total_inflight.  Returns False if
        the reservation was already released.
        """
        with self._accounting_lock:
            if reservation.state != ReservationState.QUEUED:
                return False
            reservation.state = ReservationState.RELEASED
            self._queued_count -= 1
            self._total_inflight -= 1
            self._reservations.discard(reservation)
        return True

    def _release_active(self, reservation: Reservation) -> bool:
        """Release an ACTIVE reservation: ACTIVE → RELEASED.

        Decrements active_count and total_inflight.  Returns False if
        the reservation was already released.
        """
        with self._accounting_lock:
            if reservation.state != ReservationState.ACTIVE:
                return False
            reservation.state = ReservationState.RELEASED
            self._active_count -= 1
            self._total_inflight -= 1
            self._reservations.discard(reservation)
        return True

    def assert_accounting_invariants(self) -> None:
        """Assert that accounting invariants hold.  Raises AssertionError on violation."""
        with self._accounting_lock:
            assert self._total_inflight == self._queued_count + self._active_count, (
                f"Invariant violated: total={self._total_inflight} "
                f"!= queued={self._queued_count} + active={self._active_count}"
            )
            assert min(self._total_inflight, self._queued_count, self._active_count) >= 0, (
                f"Invariant violated: negative counter "
                f"total={self._total_inflight} queued={self._queued_count} "
                f"active={self._active_count}"
            )
            assert len(self._reservations) == self._total_inflight
            assert all(
                reservation.state is not ReservationState.RELEASED
                for reservation in self._reservations
            )

    def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        request_id: Any = None,
        cancelled_set: set[Any] | None = None,
        cancelled_order: deque[Any] | None = None,
        cancelled_lock: threading.Lock | None = None,
        evaluator: _evaluator.Evaluator | None = None,
    ) -> dict[str, Any]:
        """Execute a tool call with validation, timeout, and cancellation.

        Uses the evaluator captured from the request context when provided;
        falls back to the executor's own evaluator for backward compatibility.
        """
        if self._closed:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32600, "message": "ToolExecutor is closed"},
            }

        handler = self._registry.get_handler(name)
        if handler is None:
            return self._tool_not_found(request_id, name)

        if cancelled_lock is not None and cancelled_set is not None:
            with cancelled_lock:
                if request_id is not None and request_id in cancelled_set:
                    cancelled_set.discard(request_id)
                    if cancelled_order is not None:
                        try:
                            cancelled_order.remove(request_id)
                        except ValueError:
                            pass
                    return self._cancelled_response(request_id, name)

        validation_error = _validate_arguments(handler, arguments)
        if validation_error is not None:
            return self._invalid_arguments(request_id, name, validation_error)

        schema = self._registry.get_schema(name)
        if schema:
            input_schema = schema.get("inputSchema")
            if input_schema:
                schema_error = _validate_arguments_schema(
                    name, arguments, schemas=self._registry.schemas
                )
                if schema_error is not None:
                    return self._invalid_arguments(request_id, name, schema_error)

        # Use the context-captured evaluator, falling back to the
        # executor's own evaluator for backward compatibility.
        active_evaluator = evaluator if evaluator is not None else self._evaluator

        timed_out = False
        result = None
        future = None
        reservation: Reservation | None = None
        try:
            # Accept the request: none → QUEUED
            reservation = self._reserve()
            if reservation is None:
                max_inflight = self._config.max_tool_workers + self._config.max_tool_queue_size
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32000,
                        "message": (
                            f"Server busy: {self._total_inflight} requests in flight "
                            f"(limit {max_inflight})"
                        ),
                    },
                }
            try:
                executor = self._get_executor()

                def _worker_wrapper() -> Any:
                    """Run handler with lifecycle transitions for accurate counters."""
                    # Transition: queued → active
                    if not self._start(reservation):
                        return None  # Cancelled before start
                    try:
                        return _run_handler_in_thread(handler, arguments, active_evaluator)
                    finally:
                        # Active completion releases active and total exactly once.
                        self._release_active(reservation)

                future = executor.submit(_worker_wrapper)

                result = future.result(timeout=self._config.max_tool_timeout_seconds)
            except BaseException:
                # Submit failed (future is None) → release the queued reservation.
                if future is None:
                    self._release_queued(reservation)
                raise
        except FuturesTimeoutError:
            timed_out = True
            # Best-effort cancel: returns False if the task is already running
            # or has completed.  If cancel succeeds (queued, not yet started),
            # release the queued reservation.  If it fails, the worker wrapper's
            # finally block owns the active release.
            if future is not None:
                if future.cancel() and reservation is not None:
                    self._release_queued(reservation)
        except Exception as e:
            message = _sanitize_error(str(e))[:2000]
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32000, "message": f"Tool execution error: {message}"},
            }

        if timed_out:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                {
                                    "ok": False,
                                    "error": f"Tool '{name}' execution timed out after {self._config.max_tool_timeout_seconds}s",
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

        if isinstance(result, dict) and result.get("ok") is False:
            serialized = json.dumps(result)
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"content": [{"type": "text", "text": serialized}], "isError": True},
            }

        serialized = json.dumps(result)
        if len(serialized.encode("utf-8")) > self._config.max_output_bytes:
            truncated = {
                "ok": False,
                "tool": name,
                "error_type": "output_too_large",
                "error": f"Output exceeds {self._config.max_output_bytes} bytes and was truncated",
                "hints": ["Try reducing input size or using a summary/detail option"],
                "warnings": ["Output was truncated due to size limit"],
            }
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(truncated)}],
                    "isError": True,
                },
            }

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"content": [{"type": "text", "text": serialized}]},
        }

    def _tool_not_found(self, request_id: Any, name: str) -> dict[str, Any]:
        close = self._registry.find_close_match(name)
        msg = f"Unknown tool: {name}"
        if close:
            msg += f". Did you mean: {close}?"
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": msg}}

    def _cancelled_response(self, request_id: Any, name: str) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
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

    def _invalid_arguments(self, request_id: Any, name: str, error: str) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32602, "message": f"Invalid arguments for tool '{name}': {error}"},
        }

    def close(self) -> None:
        """Shut down the thread pool and clean up orphaned processes.

        Cancels queued futures, waits for active work to finish, and
        releases any queued reservations that were cancelled before
        the worker wrapper could run.
        """
        with self._lock:
            self._closed = True
            if self._executor is not None:
                self._executor.shutdown(wait=True, cancel_futures=True)
                self._executor = None
        # Release any QUEUED reservations that were cancelled by
        # cancel_futures=True before the worker wrapper could run.
        with self._accounting_lock:
            for res in list(self._reservations):
                if res.state == ReservationState.QUEUED:
                    res.state = ReservationState.RELEASED
                    self._queued_count -= 1
                    self._total_inflight -= 1
            self._reservations.clear()
        self._cleanup_orphans()

    def _cleanup_orphans(self) -> None:
        with self._orphan_lock:
            for proc in list(self._orphaned):
                if proc.is_alive():
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
            self._orphaned.clear()

    @property
    def active_workers(self) -> int:
        """Number of currently executing tool handlers."""
        with self._accounting_lock:
            return self._active_count

    @property
    def queued_count(self) -> int:
        """Number of accepted futures that have not started executing."""
        with self._accounting_lock:
            return self._queued_count

    @property
    def orphan_count(self) -> int:
        """Number of tracked orphaned processes."""
        with self._orphan_lock:
            return len(self._orphaned)

    @property
    def pending_count(self) -> int:
        """Number of requests waiting to start execution (queued)."""
        with self._accounting_lock:
            return self._queued_count

    @property
    def total_inflight(self) -> int:
        """Number of requests not yet fully released (queued + active)."""
        with self._accounting_lock:
            return self._total_inflight

    @property
    def reservation_count(self) -> int:
        """Number of live reservations retained for accounting."""
        with self._accounting_lock:
            return len(self._reservations)


class EvaluationPolicy(enum.Enum):
    """Valid evaluation policy values for server configuration."""

    DEFAULT = "default"
    STRICT = "strict"
    PERMISSIVE = "permissive"


@_dataclass(frozen=True)
class ConfigSnapshot:
    """Deeply immutable configuration snapshot for atomic replacement.

    Dict fields are defensively deep-copied on construction and stored
    as ``MappingProxyType`` so callers cannot mutate the snapshot through
    constructor inputs or returned field values.
    """

    generation: int = 0
    constants: Mapping[str, Any] = _field(default_factory=dict)
    functions: Mapping[str, Any] = _field(default_factory=dict)
    units: Mapping[str, Any] = _field(default_factory=dict)
    policy: EvaluationPolicy | str = EvaluationPolicy.DEFAULT

    def __post_init__(self) -> None:
        # Deep copy mutable defaults to prevent external mutation, then
        # wrap in MappingProxyType for deep immutability.
        object.__setattr__(self, 'constants', MappingProxyType(dict(self.constants)))
        object.__setattr__(self, 'functions', MappingProxyType(dict(self.functions)))
        object.__setattr__(self, 'units', MappingProxyType(dict(self.units)))
        # Accept str for backward compatibility, converting to EvaluationPolicy.
        # Also handle EvaluationPolicy instances from reloaded modules (different class).
        policy_value: object = self.policy
        if isinstance(policy_value, str):
            try:
                object.__setattr__(self, 'policy', EvaluationPolicy(policy_value))
            except ValueError:
                raise ConfigError(
                    f"Invalid policy {policy_value!r}; "
                    f"must be one of {sorted(e.value for e in EvaluationPolicy)}"
                )
        elif not isinstance(policy_value, EvaluationPolicy) and hasattr(policy_value, "value"):
            # EvaluationPolicy from a reloaded module — convert via its value
            try:
                object.__setattr__(self, 'policy', EvaluationPolicy(cast(Any, policy_value).value))
            except ValueError:
                raise ConfigError(
                    f"Invalid policy {policy_value!r}; "
                    f"must be one of {sorted(e.value for e in EvaluationPolicy)}"
                )

    def to_dict(self) -> dict[str, Any]:
        """Return a plain dict view safe for serialization."""
        policy_val = self.policy.value if isinstance(self.policy, EvaluationPolicy) else self.policy
        return {
            "generation": self.generation,
            "constants": dict(self.constants),
            "functions": {k: getattr(v, "__name__", str(v)) for k, v in self.functions.items()},
            "units": dict(self.units),
            "policy": policy_val,
        }


class ConfigError(Exception):
    """Raised when configuration parsing or validation fails."""


@_dataclass(frozen=True)
class ConfigCandidate:
    """Validated configuration candidate before snapshot construction.

    Holds the parsed and validated constants, functions, and policy
    ready to be turned into a ConfigSnapshot and RuntimeContext.
    """

    constants: Mapping[str, Any] = _field(default_factory=dict)
    functions: Mapping[str, Any] = _field(default_factory=dict)
    policy: EvaluationPolicy = EvaluationPolicy.DEFAULT


@_dataclass(frozen=True)
class RuntimeContext:
    """Complete atomic configuration state for the server.

    Pairs a ConfigSnapshot with the evaluator instance that was built
    from it, enabling atomic replacement without partial updates.
    """

    snapshot: ConfigSnapshot
    evaluator: _evaluator.Evaluator


def parse_config_candidate(
    *,
    constants: dict[str, Any] | None = None,
    functions: dict[str, Any] | None = None,
    units: dict[str, Any] | None = None,
    policy: str | EvaluationPolicy | None = None,
) -> ConfigCandidate:
    """Parse raw configuration values into a validated ConfigCandidate.

    The candidate is the parser result and the input to context construction.
    Raises ConfigError on invalid input.
    """
    parsed_constants: dict[str, Any] = {}
    if constants is not None:
        for name, value in constants.items():
            if not isinstance(name, str):
                raise ConfigError(f"Constant name must be str, got {type(name).__name__}")
            if not isinstance(value, (int, float, str, bool)):
                raise ConfigError(
                    f"Constant '{name}' must be int/float/str/bool, " f"got {type(value).__name__}"
                )
            parsed_constants[name] = value

    parsed_functions: dict[str, Any] = {}
    if functions is not None:
        for name, value in functions.items():
            if not isinstance(name, str):
                raise ConfigError(f"Function name must be str, got {type(name).__name__}")
            if not callable(value):
                raise ConfigError(f"Function '{name}' must be callable")
            parsed_functions[name] = value

    if units:
        raise ConfigError("custom units are not supported by server configuration")

    if isinstance(policy, EvaluationPolicy):
        resolved_policy: EvaluationPolicy = policy
    elif isinstance(policy, str):
        try:
            resolved_policy = EvaluationPolicy(policy)
        except ValueError:
            valid_values = sorted(e.value for e in EvaluationPolicy)
            raise ConfigError(f"Invalid policy {policy!r}; must be one of {valid_values}")
    elif policy is None:
        resolved_policy = EvaluationPolicy.DEFAULT
    else:
        raise ConfigError(f"Invalid policy type: {type(policy).__name__}")

    return ConfigCandidate(
        constants=freeze_owned(parsed_constants),
        functions=freeze_owned(parsed_functions),
        policy=resolved_policy,
    )


def policy_from_server_config(config: McpServerConfig) -> EvaluationPolicy:
    """Resolve the effective EvaluationPolicy from server config.

    Precedence:
    - STRICT always disables both allow_random and allow_side_effects;
    - PERMISSIVE enables only features allowed by the immutable server config ceiling;
    - DEFAULT follows server config flags.
    """
    # Tool profiles select exposure only.  They must never alter evaluator
    # capabilities.  The explicit evaluation policy is an independent server
    # configuration field, with DEFAULT preserving the configured ceilings.
    return EvaluationPolicy(config.evaluation_policy)


def build_runtime_context(config: McpServerConfig, snapshot: ConfigSnapshot) -> RuntimeContext:
    """Build a RuntimeContext from a config and snapshot.

    Constructs a fresh evaluator from the immutable built-in base tables
    plus exactly the snapshot overlay.  The policy determines the
    evaluator's allow_random and allow_side_effects flags.
    """
    policy = (
        snapshot.policy
        if isinstance(snapshot.policy, EvaluationPolicy)
        else EvaluationPolicy(
            snapshot.policy.value if hasattr(snapshot.policy, "value") else snapshot.policy
        )
    )
    # STRICT always disables both; PERMISSIVE enables only what config allows;
    # DEFAULT follows config flags.
    if policy == EvaluationPolicy.STRICT:
        allow_random, allow_side_effects = False, False
    elif policy == EvaluationPolicy.PERMISSIVE:
        allow_random = config.allow_random
        allow_side_effects = config.allow_side_effects
    else:
        allow_random = config.allow_random
        allow_side_effects = config.allow_side_effects

    evaluator = _evaluator.Evaluator(
        allow_random=allow_random,
        allow_side_effects=allow_side_effects,
    )
    # Apply snapshot overlay to the fresh evaluator
    for name, value in snapshot.constants.items():
        evaluator.CONSTANTS[name] = value
    for name, value in snapshot.functions.items():
        if callable(value):
            evaluator.FUNCTIONS[name] = value

    return RuntimeContext(snapshot=snapshot, evaluator=evaluator)


def parse_config_snapshot(
    *,
    constants: dict[str, Any] | None = None,
    functions: dict[str, Any] | None = None,
    units: dict[str, Any] | None = None,
    policy: str | EvaluationPolicy | None = None,
) -> ConfigSnapshot:
    """Parse raw configuration values into a validated ConfigSnapshot.

    Validates types and semantics before constructing the snapshot.
    Raises ConfigError on invalid input.
    """
    parsed_constants: dict[str, Any] = {}
    if constants is not None:
        for name, value in constants.items():
            if not isinstance(name, str):
                raise ConfigError(f"Constant name must be str, got {type(name).__name__}")
            if not isinstance(value, (int, float, str, bool)):
                raise ConfigError(
                    f"Constant '{name}' must be int/float/str/bool, " f"got {type(value).__name__}"
                )
            parsed_constants[name] = value

    parsed_functions: dict[str, Any] = {}
    if functions is not None:
        for name, value in functions.items():
            if not isinstance(name, str):
                raise ConfigError(f"Function name must be str, got {type(name).__name__}")
            if not callable(value):
                raise ConfigError(f"Function '{name}' must be callable")
            parsed_functions[name] = value

    if units:
        raise ConfigError("custom units are not supported by server configuration")

    if isinstance(policy, EvaluationPolicy):
        resolved_policy: EvaluationPolicy = policy
    elif isinstance(policy, str):
        try:
            resolved_policy = EvaluationPolicy(policy)
        except ValueError:
            valid_values = sorted(e.value for e in EvaluationPolicy)
            raise ConfigError(f"Invalid policy {policy!r}; must be one of {valid_values}")
    elif policy is None:
        resolved_policy = EvaluationPolicy.DEFAULT
    else:
        raise ConfigError(f"Invalid policy type: {type(policy).__name__}")

    return ConfigSnapshot(
        constants=parsed_constants,
        functions=parsed_functions,
        units={},
        policy=resolved_policy,
    )


class ConfigManager:
    """Thread-safe manager for atomic configuration snapshots.

    Configuration changes become visible atomically, never field-by-field.
    Failed loads leave the prior valid snapshot active. Generation numbers
    increase monotonically; stale or decreasing generations are rejected.
    """

    def __init__(self, owner: McpServer | None = None) -> None:
        self._owner_ref = weakref.ref(owner) if owner is not None else None
        self._snapshot = ConfigSnapshot()
        self._lock = threading.Lock()

    def current(self) -> ConfigSnapshot:
        owner = self._owner_ref() if self._owner_ref is not None else None
        if owner is not None:
            return owner.runtime_context.snapshot
        return self._snapshot

    def _validate_next(self, snapshot: ConfigSnapshot) -> None:
        """Validate a snapshot without changing either authority."""
        current = self.current()
        if snapshot.generation <= current.generation:
            raise ValueError(
                f"Snapshot generation {snapshot.generation} must be greater "
                f"than current {current.generation}"
            )

    def _set_snapshot(self, snapshot: ConfigSnapshot) -> None:
        """Publish a validated snapshot as a non-raising pointer assignment."""
        self._snapshot = snapshot

    def replace(self, snapshot: ConfigSnapshot) -> int:
        """Atomically replace the current snapshot.

        The new snapshot's generation must be greater than the current one.
        Returns the new generation on success.

        Raises:
            ValueError: If the snapshot generation is not greater than current.
        """
        owner = self._owner_ref() if self._owner_ref is not None else None
        if owner is not None:
            owner.activate_snapshot(snapshot)
            return snapshot.generation
        with self._lock:
            self._validate_next(snapshot)
            self._set_snapshot(snapshot)
            return snapshot.generation

    def replace_validated(
        self,
        *,
        constants: dict[str, Any] | None = None,
        functions: dict[str, Any] | None = None,
        units: dict[str, Any] | None = None,
        policy: str | EvaluationPolicy | None = None,
    ) -> ConfigSnapshot:
        """Build the next snapshot with a manager-assigned generation, validate, and apply.

        Returns the new snapshot on success.  On failure the prior state
        is preserved unchanged.
        """
        owner = self._owner_ref() if self._owner_ref is not None else None
        if owner is not None:
            current = owner.runtime_context.snapshot
            snap = ConfigSnapshot(
                generation=current.generation + 1,
                constants=constants if constants is not None else dict(current.constants),
                functions=functions if functions is not None else dict(current.functions),
                units=units if units is not None else dict(current.units),
                policy=policy if policy is not None else current.policy,
            )
            owner.activate_snapshot(snap)
            return snap
        with self._lock:
            new_gen = self._snapshot.generation + 1
            prev = self._snapshot
            snap = ConfigSnapshot(
                generation=new_gen,
                constants=constants if constants is not None else dict(prev.constants),
                functions=functions if functions is not None else dict(prev.functions),
                units=units if units is not None else dict(prev.units),
                policy=policy if policy is not None else prev.policy,
            )
            self._validate_next(snap)
            self._set_snapshot(snap)
            return snap

    def invalidate(self) -> None:
        current = self.current()
        snapshot = ConfigSnapshot(generation=current.generation + 1)
        owner = self._owner_ref() if self._owner_ref is not None else None
        if owner is not None:
            owner.activate_snapshot(snapshot)
            return
        with self._lock:
            self._validate_next(snapshot)
            self._set_snapshot(snapshot)


class McpSessionState(enum.Enum):
    """MCP protocol session lifecycle states."""

    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    READY = "ready"
    CLOSED = "closed"


class McpSession:
    """MCP protocol session with lifecycle state management.

    Owns negotiated protocol version, client info, and lifecycle state.
    Each session is bound to exactly one owning ``McpServer``.  The
    ``handle_message`` method dispatches JSON-RPC requests and
    notifications with lifecycle enforcement.
    """

    def __init__(self, *, initial_state: McpSessionState = McpSessionState.READY):
        self.state = initial_state
        self.negotiated_version: str | None = None
        self.requested_version: str | None = None
        self.client_name: str | None = None
        self.client_version: str | None = None
        self.client_info: dict[str, Any] | None = None
        self.client_capabilities: dict[str, Any] | None = None
        self.request_id: str | None = None
        # Owner server binding — set once by the owning McpServer.
        # Uses a weak reference so the session does not prevent the
        # server from being garbage collected.
        self._owner_ref: weakref.ref[McpServer] | None = None
        self._owner_bound_once = False
        self._owner_remove_callback: Any = None
        self._closed = False
        # Session-scoped cancellation records. Each session owns its own
        # set + deque + lock so sessions are isolated from each other.
        self._cancelled_requests: set[Any] = set()
        self._cancelled_requests_order: deque[Any] = deque()
        self._cancelled_lock = threading.Lock()

    def handle_message(
        self,
        request: dict[str, Any],
        server: McpServer | None = None,
        context: RuntimeContext | None = None,
    ) -> dict[str, Any] | None:
        """Route MCP request to appropriate handler with lifecycle enforcement.

        When *server* and *context* are provided, all dispatch uses the
        server-owned registry, executor, and evaluator.  Serverless
        fallbacks are removed for tool/profile/cancellation dispatch —
        those methods require a supplied owner server/context.
        """
        method = request.get("method", "")
        request_id = request.get("id")

        # Production protocol dispatch is owner-routed.  Ping and the local
        # lifecycle notification are the only owner-independent methods.
        if server is None and method not in {"ping", "notifications/initialized"}:
            try:
                server = self.owner
            except RuntimeError:
                return _invalid_request_error(
                    request_id,
                    "Production MCP dispatch requires a live owning server",
                )

        # Lifecycle state check
        error = self._check_ready_for_dispatch(method, request_id)
        if error is not None:
            return error

        # Dispatch
        if method == "initialize":
            return self._handle_initialize(request, server=server)
        elif method == "notifications/initialized":
            self._handle_notifications_initialized()
            return None
        elif method == "notifications/cancelled":
            if server is None:
                return _invalid_request_error(
                    request_id,
                    "notifications/cancelled requires a server context",
                )
            self._handle_cancelled(request, server=server)
            return None
        elif method == "ping":
            return {"jsonrpc": "2.0", "id": request_id, "result": {}}
        elif method == "tools/list":
            if server is None:
                return _invalid_request_error(request_id, "tools/list requires a server context")
            return _handle_list_tools(request, server=server)
        elif method == "tools/call":
            if server is None:
                return _invalid_request_error(request_id, "tools/call requires a server context")
            return self._handle_call_tool_server(request, server, context)
        elif method == "profiles/list":
            if server is None:
                return _invalid_request_error(request_id, "profiles/list requires a server context")
            return _handle_list_profiles(request, server=server)
        elif method.startswith("notifications/"):
            # Unknown notifications are silently ignored per MCP spec
            return None
        else:
            display = method[:100] + "..." if len(method) > 100 else method
            return _method_not_found(request_id, display)

    def _handle_call_tool_server(
        self, request: dict[str, Any], server: McpServer, context: RuntimeContext | None = None
    ) -> dict[str, Any]:
        """Handle tools/call using server-owned executor for state isolation.

        Uses the evaluator captured from the request context so that
        concurrent requests observe a consistent configuration generation.
        """
        params = request.get("params", {})
        if not isinstance(params, dict):
            return _invalid_request(request.get("id"), "Invalid params: expected object")

        name = params.get("name", "")
        arguments = params.get("arguments", {})
        if not isinstance(name, str) or not name:
            return _invalid_request(request.get("id"), "Invalid params: missing tool name")
        if not isinstance(arguments, dict):
            return _invalid_request(request.get("id"), "Invalid arguments: expected object")

        # Check handler existence first (returns -32601 for unknown tools)
        if not server.registry.has_tool(name):
            close = server.registry.find_close_match(name)
            msg = f"Unknown tool: {name}"
            if close:
                msg += f". Did you mean: {close}?"
            return _jsonrpc_error(request.get("id"), -32601, msg)

        # Enforce server profile authority before executor submission
        profile = server.config.profile
        try:
            profile_tools = server.registry.get_profile_tools(profile)
        except ValueError as e:
            return _jsonrpc_error(request.get("id"), -32602, str(e))
        if name not in profile_tools:
            return _jsonrpc_error(
                request.get("id"),
                -32602,
                (
                    f"Tool '{name}' is not available in profile '{profile}'. "
                    f"Use tools/list to see available tools, or switch profile."
                ),
            )

        evaluator = context.evaluator if context is not None else server.evaluator
        return server._executor.call_tool(
            name=name,
            arguments=arguments,
            request_id=request.get("id"),
            cancelled_set=self._cancelled_requests,
            cancelled_order=self._cancelled_requests_order,
            cancelled_lock=self._cancelled_lock,
            evaluator=evaluator,
        )

    def close(self) -> None:
        """Close this session, transitioning to CLOSED state.

        Idempotent — calling close() on an already-closed session is safe.
        Removes the session from its owner server's live tracking.
        """
        if self._closed:
            return
        self._closed = True
        self.state = McpSessionState.CLOSED
        # Remove from owner's live session set via the registered callback.
        if self._owner_remove_callback is not None:
            try:
                self._owner_remove_callback(self)
            except Exception:
                pass  # Best-effort cleanup; server may already be closed.
        self._owner_remove_callback = None

    @property
    def owner(self) -> McpServer:
        """Return the live owning server, raising if unavailable or closed."""
        owner = self._owner_ref() if self._owner_ref else None
        if owner is None:
            raise RuntimeError("Session owner is unavailable")
        if owner.closed:
            raise RuntimeError("Session owner is closed")
        return owner

    def _bind_owner(self, server: McpServer) -> None:
        """Bind this session to exactly one owning server. Called once by create_session."""
        if self._owner_bound_once:
            raise RuntimeError("Session ownership is immutable")
        self._owner_bound_once = True
        self._owner_ref = weakref.ref(server)

    def _check_ready_for_dispatch(self, method: str, request_id: Any) -> dict[str, Any] | None:
        """Check if session state allows this method to be dispatched."""
        # Closed sessions cannot dispatch
        if self._closed and method not in ("notifications/initialized", "notifications/cancelled"):
            return _invalid_request_error(request_id, "Session is closed")

        # Compare by name rather than identity to survive importlib.reload()
        state_name = self.state.name

        if method == "initialize":
            if state_name == "UNINITIALIZED":
                return None
            return _invalid_request_error(request_id, "Server already initialized")

        if method == "notifications/initialized":
            return None  # Always accepted (silently ignored in wrong state)

        if method == "ping":
            return None  # Allowed in any state

        if method == "notifications/cancelled":
            return None  # Always accepted

        # All other methods require READY state
        if state_name != "READY":
            return _invalid_request_error(request_id, "Server not initialized")

        return None

    def _handle_initialize(
        self, request: dict[str, Any], server: McpServer | None = None
    ) -> dict[str, Any]:
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

        # Version negotiation: use server config when available
        supported_versions = (
            server.config.supported_protocol_versions
            if server is not None
            else SUPPORTED_PROTOCOL_VERSIONS
        )
        latest_version = (
            supported_versions[-1] if supported_versions else LATEST_SUPPORTED_PROTOCOL_VERSION
        )
        if protocol_version in supported_versions:
            negotiated = protocol_version
        else:
            negotiated = latest_version

        self.negotiated_version = negotiated
        self.requested_version = protocol_version
        self.client_name = client_name
        self.client_version = client_version if isinstance(client_version, str) else ""
        self.client_info = client_info
        self.client_capabilities = capabilities
        self.state = McpSessionState.INITIALIZING

        caps = detect_capabilities()
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "result": {
                "protocolVersion": negotiated,
                "capabilities": {
                    "tools": {"listChanged": False},
                    "runtime": caps.to_dict(),
                },
                "serverInfo": {
                    "name": "eggcalc",
                    "version": __version__,
                },
            },
        }

    def _handle_notifications_initialized(self) -> None:
        """Transition from INITIALIZING to READY state."""
        if self.state.name == "INITIALIZING":
            self.state = McpSessionState.READY

    def _handle_cancelled(self, request: dict[str, Any], server: McpServer | None = None) -> None:
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
            max_cancelled = (
                server.config.max_cancelled_requests if server else MAX_CANCELLED_REQUESTS
            )
            with self._cancelled_lock:
                if cancelled_id not in self._cancelled_requests:
                    self._cancelled_requests.add(cancelled_id)
                    self._cancelled_requests_order.append(cancelled_id)
                while len(self._cancelled_requests) > max_cancelled:
                    oldest = self._cancelled_requests_order.popleft()
                    self._cancelled_requests.discard(oldest)


class McpServer:
    """Explicit MCP server owning all mutable state.

    Owns configuration, tool registry, tool executor, evaluator policy,
    and session creation. Multiple instances can coexist safely.
    """

    def __init__(
        self,
        config: McpServerConfig | None = None,
        registry: ToolRegistry | None = None,
    ) -> None:
        self._config = config or McpServerConfig()
        self._registry = registry or ToolRegistry()

        # Validate that the configured profile is resolvable against the
        # supplied registry.  The synthetic "full" profile is always valid.
        if self._config.profile != "full" and self._config.profile not in self._registry.profiles:
            available = ", ".join(sorted(self._registry.profiles))
            raise ValueError(
                f"Unknown profile: {self._config.profile!r}. " f"Available profiles: {available}"
            )

        # Build the initial RuntimeContext once at construction.
        # There is no separately authoritative mutable evaluator — the
        # context's evaluator is the sole active evaluator.
        initial_snapshot = ConfigSnapshot(
            generation=0,
            constants={},
            functions={},
            units={},
            policy=policy_from_server_config(self._config),
        )
        self._runtime_context = build_runtime_context(self._config, initial_snapshot)
        self._executor = ToolExecutor(self._config, self._registry)
        self._config_manager = ConfigManager(self)
        # Initialize the config manager with the initial snapshot directly
        # (generation 0 is valid as the starting point).
        self._config_manager._set_snapshot(initial_snapshot)
        self._closed = False
        self._lock = threading.Lock()
        self._sessions: set[McpSession] = set()
        self._sessions_lock = threading.Lock()

    @property
    def config(self) -> McpServerConfig:
        return self._config

    @property
    def registry(self) -> ToolRegistry:
        return self._registry

    @property
    def config_manager(self) -> ConfigManager:
        return self._config_manager

    @property
    def runtime_context(self) -> RuntimeContext:
        """The server's active runtime context (never None during normal operation)."""
        return self._runtime_context

    @property
    def evaluator(self) -> _evaluator.Evaluator:
        """Compatibility accessor returning the active evaluator from the runtime context."""
        return self._runtime_context.evaluator

    @property
    def closed(self) -> bool:
        """Whether this server has been shut down."""
        return self._closed

    def create_session(
        self, initial_state: McpSessionState = McpSessionState.UNINITIALIZED
    ) -> McpSession:
        """Create a new session owned by this server."""
        session = McpSession(initial_state=initial_state)
        session._bind_owner(self)
        session._owner_remove_callback = self._remove_session
        with self._sessions_lock:
            self._sessions.add(session)
        return session

    def _remove_session(self, session: McpSession) -> None:
        """Remove a closed session from live tracking."""
        with self._sessions_lock:
            self._sessions.discard(session)

    def handle_request(
        self, request: Any, session: McpSession | None = None
    ) -> dict[str, Any] | None:
        """Handle a JSON-RPC request with server-owned dispatch.

        Captures the active RuntimeContext before queue admission so the
        request has one stable semantic context from validation through
        execution, even if a new configuration publishes while it is queued.
        """
        if self._closed:
            return _invalid_request(None, "Server is closed")

        # Validate request ID length using server config
        if isinstance(request, dict):
            request_id = request.get("id")
            if request_id is not None:
                id_str = str(request_id)
                if len(id_str) > self._config.max_request_id_length:
                    return _invalid_request(
                        None,
                        f"Invalid Request: 'id' exceeds maximum length of {self._config.max_request_id_length}",
                    )

        if session is None:
            session = self.create_session()
        elif session._closed:
            return _invalid_request(None, "Session is closed")
        elif session._owner_ref is None:
            return _invalid_request(None, "Session is not bound to a server")
        else:
            owner = session._owner_ref()
            if owner is None:
                return _invalid_request(None, "Session owner is unavailable")
            if owner is not self:
                return _invalid_request(None, "Session belongs to another server")

        # Capture one immutable context before dispatch.
        context = self._runtime_context
        return session.handle_message(request, server=self, context=context)

    def close(self) -> None:
        """Shut down the server, releasing workers and cleaning up."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
        self._executor.close()
        # Snapshot and clear sessions under the lock, then close each one.
        # session.close() may call back into _remove_session, so we must not
        # hold _sessions_lock during those calls.
        with self._sessions_lock:
            sessions_to_close = list(self._sessions)
            self._sessions.clear()
        for session in sessions_to_close:
            session.close()

    def apply_configuration(
        self,
        *,
        constants: dict[str, Any] | None = None,
        functions: dict[str, Any] | None = None,
        units: dict[str, Any] | None = None,
        policy: str | EvaluationPolicy | None = None,
    ) -> ConfigSnapshot:
        """Parse, validate, and atomically activate a configuration change.

        Single entry point for the full configuration lifecycle:
        parse -> validate -> construct snapshot -> build context ->
        atomically assign.

        This is a *replacement* operation: new overlay entries replace
        previous ones entirely.  Built-ins remain available from immutable
        evaluator base tables.

        Returns the new snapshot on success.  On failure the prior
        configuration is preserved unchanged.
        """
        # 1. Parse and validate raw values to ConfigCandidate outside the lock
        candidate = parse_config_candidate(
            constants=constants,
            functions=functions,
            units=units,
            policy=policy,
        )

        # 2. Read the current context and expected generation
        with self._lock:
            current_context = self._runtime_context
            expected_generation = current_context.snapshot.generation
            new_gen = expected_generation + 1

        # 3. Construct a new evaluator from immutable built-ins plus exactly
        #    the candidate overlay (outside the lock)
        new_snapshot = ConfigSnapshot(
            generation=new_gen,
            constants=candidate.constants,
            functions=candidate.functions,
            units={},
            policy=candidate.policy,
        )
        new_context = build_runtime_context(self._config, new_snapshot)

        # 4. Acquire one activation lock
        with self._lock:
            # 5. Verify that the active generation still equals expected
            if self._runtime_context.snapshot.generation != expected_generation:
                raise ValueError(
                    f"Stale generation: expected {expected_generation}, "
                    f"got {self._runtime_context.snapshot.generation}"
                )

            # Validate every operation that can raise before publication.
            self._config_manager._validate_next(new_snapshot)
            # These plain pointer assignments are the publication boundary.
            self._runtime_context = new_context
            self._config_manager._set_snapshot(new_snapshot)

        return new_snapshot

    def activate_snapshot(self, snapshot: ConfigSnapshot) -> None:
        """Atomically activate a configuration snapshot.

        Builds a fresh evaluator from the snapshot and atomically replaces
        the active runtime context.  On failure the prior context is
        preserved unchanged.
        """
        new_context = build_runtime_context(self._config, snapshot)
        with self._lock:
            # Verify generation is strictly increasing before replacing.
            if snapshot.generation <= self._runtime_context.snapshot.generation:
                raise ValueError(
                    f"Snapshot generation {snapshot.generation} must be greater "
                    f"than current {self._runtime_context.snapshot.generation}"
                )
            self._config_manager._validate_next(snapshot)
            self._runtime_context = new_context
            self._config_manager._set_snapshot(snapshot)

    def diagnostic(self) -> dict[str, Any]:
        """Return deterministic diagnostic information."""
        with self._lock:
            context = self._runtime_context
        config_snap = context.snapshot
        with self._sessions_lock:
            live_sessions = sum(1 for s in self._sessions if not s._closed)
        return {
            "config_generation": config_snap.generation,
            "global_config_generation": _evaluator.get_config_generation(),
            "profile": self._config.profile,
            "registry_tool_count": len(self._registry.tool_names),
            "max_tool_workers": self._config.max_tool_workers,
            "active_workers": self._executor.active_workers,
            "max_tool_queue_size": self._config.max_tool_queue_size,
            "pending_count": self._executor.queued_count,
            "total_inflight": self._executor.total_inflight,
            "max_tool_timeout": self._config.max_tool_timeout_seconds,
            "orphan_count": self._executor.orphan_count,
            "session_count": live_sessions,
            "config_units_count": len(config_snap.units),
            "closed": self._closed,
        }


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


def _find_close_match(
    name: str, handlers: MappingProxyType[str, Any] | dict[str, Any]
) -> str | None:
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


def _run_handler_in_thread(
    handler: Any,
    arguments: dict[str, Any],
    evaluator: _evaluator.Evaluator | None = None,
) -> Any:
    """Run a tool handler on a pool thread, returning the result or raising.

    If an evaluator is provided, sets the ``_current_evaluator`` ContextVar
    so that ``evaluate_raw`` and ``evaluate_with_timeout`` use it instead of
    the module-level default. This binds MCP math execution to the
    server-owned evaluator without modifying handler signatures.
    """
    if evaluator is not None:
        token = _evaluator._server_evaluator.set(evaluator)
        try:
            return handler(**arguments)
        finally:
            _evaluator._server_evaluator.reset(token)
    return handler(**arguments)


def _json_value_equal(a: Any, b: Any) -> bool:
    """Recursively compare two JSON-like values for structural equality.

    Used by uniqueItems to detect duplicates among unhashable items (dicts,
    lists) as well as scalars. JSON Schema treats all numbers as one numeric
    domain, so int 1 and float 1.0 are equal.
    """
    # JSON numeric domain: int and float compare by mathematical value
    if (
        isinstance(a, (int, float))
        and not isinstance(a, bool)
        and isinstance(b, (int, float))
        and not isinstance(b, bool)
    ):
        return a == b
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        if a.keys() != b.keys():
            return False
        return all(_json_value_equal(a[k], b[k]) for k in a)
    if isinstance(a, list):
        if len(a) != len(b):
            return False
        return all(_json_value_equal(x, y) for x, y in zip(a, b, strict=False))
    return bool(a == b)


def _validate_value_against_schema(
    value: Any, prop: Mapping[str, Any], path: str, max_depth: int = 10
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
    if not isinstance(prop, (dict, MappingProxyType)):
        return f"Schema for '{path}' must be an object"

    expected_type = prop.get("type")
    if expected_type is None:
        return None

    # JSON Schema allows type as a string or a list of strings (e.g.
    # ["string", "null"] for a nullable field). We support both forms.
    if isinstance(expected_type, (list, tuple)):
        type_options = list(expected_type)
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
    allowed_types: list[Any] = []
    for t in type_options:
        mapped = type_map[t]
        if isinstance(mapped, tuple):
            allowed_types.extend(mapped)
        else:
            allowed_types.append(mapped)
    allowed_types_tuple: tuple[Any, ...] = tuple(allowed_types)

    if not isinstance(value, allowed_types_tuple):
        # Preserve the original "must be X" wording for single-type
        # schemas (used by tests and external consumers). For list
        # schemas (nullable fields), use the explicit "one of [...]"
        # form so the user sees all valid types.
        if len(type_options) == 1:
            return f"Argument '{path}' must be {type_options[0]}, got {type(value).__name__}"
        return f"Argument '{path}' must be one of [{', '.join(type_options)}], got {type(value).__name__}"

    # Bool is subclass of int in Python; reject bool when any numeric type is allowed
    # but only if boolean is not also explicitly permitted in the type union.
    if (
        any(t in ("integer", "number") for t in type_options)
        and isinstance(value, bool)
        and "boolean" not in type_options
    ):
        if len(type_options) == 1:
            return f"Argument '{path}' must be {type_options[0]}, got bool"
        return f"Argument '{path}' must be one of [{', '.join(type_options)}], got bool"

    if "const" in prop and not _json_value_equal(value, prop["const"]):
        return f"Argument '{path}' must equal {prop['const']!r}, got {value!r}"

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
            quotient = value / multiple
            nearest_int = round(quotient)
            if not _math.isclose(quotient, nearest_int, rel_tol=1e-9, abs_tol=1e-12):
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


def _validate_arguments_schema(
    name: str,
    arguments: dict[str, Any],
    schemas: Mapping[str, dict[str, Any]] | None = None,
) -> str | None:
    """Validate arguments against the tool's inputSchema.

    When *schemas* is provided (the server registry's schemas mapping),
    validation uses that mapping instead of the global ``TOOL_SCHEMAS``.
    Returns None if valid, or an error message string if invalid.
    """
    source = schemas if schemas is not None else TOOL_SCHEMAS
    schema = source.get(name, {}).get("inputSchema")
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
    request: dict[str, Any],
    cancelled_set: set[Any] | None = None,
    cancelled_order: deque[Any] | None = None,
    cancelled_lock: threading.Lock | None = None,
) -> dict[str, Any]:
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
    future: Future[Any] | None = None
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


def _handle_list_tools(request: dict[str, Any], server: McpServer | None = None) -> dict[str, Any]:
    """Handle a tools/list MCP request with optional filtering.

    When *server* is provided, its config and registry are used instead
    of module-level globals, giving callers full state isolation.
    """
    params = request.get("params", {})
    request_id = request.get("id")
    if not isinstance(params, dict):
        return _invalid_request(request_id, "Invalid params: expected object")

    tier_filter = params.get("tier")
    tags_filter = params.get("tags")
    names_filter = params.get("names")
    profile_filter = params.get("profile")
    schema_detail_param = params.get("schema_detail")

    if tier_filter is not None:
        if isinstance(tier_filter, bool) or not isinstance(tier_filter, int):
            return _invalid_request(request_id, "Invalid 'tier' parameter: expected integer")
        if tier_filter not in (0, 1, 2, 3):
            return _invalid_request(request_id, "Invalid 'tier' parameter: expected 0, 1, 2, or 3")
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

    # Schema detail: per-request override or global default (server-aware)
    if server is not None:
        default_detail = server.config.schema_detail
    else:
        default_detail = get_schema_detail()
    detail = schema_detail_param or default_detail
    use_compact = detail == "compact"
    schema_detail = detail

    # Determine profile-visible tools (server-aware)
    try:
        if server is not None:
            default_profile = profile_filter or server.config.profile
            profile_tools = set(server.registry.get_profile_tools(default_profile))
        else:
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

    # Use server registry when available, fall back to globals
    schemas_src = server.registry.schemas if server is not None else TOOL_SCHEMAS
    metadata_src = server.registry.metadata if server is not None else TOOL_METADATA

    tools = []
    for name, schema in schemas_src.items():
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

        meta = metadata_src.get(name, {})
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
                "inputSchema": thaw_owned(schema["inputSchema"]),
                "outputSchema": thaw_owned(schema.get("outputSchema")),
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


def _handle_initialize(request: dict[str, Any]) -> dict[str, Any]:
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

    client_info.get("version", "")

    # Version negotiation
    if protocol_version in SUPPORTED_PROTOCOL_VERSIONS:
        negotiated = protocol_version
    else:
        negotiated = LATEST_SUPPORTED_PROTOCOL_VERSION

    caps = detect_capabilities()
    return {
        "jsonrpc": "2.0",
        "id": request.get("id"),
        "result": {
            "protocolVersion": negotiated,
            "capabilities": {
                "tools": {"listChanged": False},
                "runtime": caps.to_dict(),
            },
            "serverInfo": {
                "name": "eggcalc",
                "version": __version__,
            },
        },
    }


def _handle_list_profiles(
    request: dict[str, Any], server: McpServer | None = None
) -> dict[str, Any]:
    """Handle a profiles/list MCP request.

    When *server* is provided, its config and registry are used instead
    of module-level globals.
    """
    params = request.get("params", {})
    if not isinstance(params, dict):
        return _invalid_request(request.get("id"), "Invalid params: expected object")

    if server is not None:
        active = server.config.profile
        profile_names = tuple(sorted(server.registry.profiles))
        available_profiles = (
            ("full", *profile_names) if "full" not in profile_names else profile_names
        )
        profiles_info = {
            name: {
                "tools": server.registry.get_profile_tools(name),
                "tool_count": len(server.registry.get_profile_tools(name)),
            }
            for name in available_profiles
        }
    else:
        active = get_active_profile()
        available_profiles = tuple(PROFILE_NAMES)
        profiles_info = {
            name: {
                "tools": list(TOOL_PROFILES.get(name, [])),
                "tool_count": len(TOOL_PROFILES.get(name, [])),
            }
            for name in available_profiles
        }

    return {
        "jsonrpc": "2.0",
        "id": request.get("id"),
        "result": {
            "active_profile": active,
            "profiles": profiles_info,
            "available_profiles": list(available_profiles),
        },
    }


_compat_server: McpServer | None = None
_compat_server_lock = threading.Lock()
_compat_server_config_gen: int = 0


def _invalidate_compat_server() -> None:
    """Close and discard the cached compatibility server."""
    global _compat_server
    with _compat_server_lock:
        if _compat_server is not None:
            _compat_server.close()
            _compat_server = None


def _get_compat_server() -> McpServer:
    """Return the lazily-initialized compatibility server.

    The compatibility server is an isolated ``McpServer`` instance used
    only by the deprecated module-level ``handle_request()`` function.
    It owns its own evaluator, registry, executor, and config manager
    so that it never mutates package-global state or explicit servers.
    """
    global _compat_server
    with _compat_server_lock:
        if _compat_server is not None and not _compat_server._closed:
            # Invalidate if module-level MAX_OUTPUT_BYTES changed
            if _compat_server.config.max_output_bytes != MAX_OUTPUT_BYTES:
                _compat_server.close()
                _compat_server = None
        if _compat_server is None or _compat_server._closed:
            _compat_server = McpServer(
                config=McpServerConfig(
                    profile=get_active_profile(),
                    allow_random=False,
                    allow_side_effects=False,
                    max_tool_workers=4,
                    max_tool_queue_size=8,
                    max_tool_timeout_seconds=30,
                    max_output_bytes=MAX_OUTPUT_BYTES,
                ),
            )
    return _compat_server


def close_compatibility_server() -> None:
    """Shut down and release the compatibility server.

    Safe to call repeatedly. Subsequent compatibility requests will
    create a fresh isolated server.
    """
    global _compat_server
    with _compat_server_lock:
        if _compat_server is not None:
            _compat_server.close()
            _compat_server = None


def handle_request(request: Any, session: McpSession | None = None) -> dict[str, Any] | None:
    """Route MCP request to appropriate handler.

    If *session* is ``None`` the request is routed through an isolated
    compatibility ``McpServer`` that owns its own evaluator and state.
    Existing callers that do not perform the handshake will continue to
    work unchanged.  Callers that pass an explicit ``McpSession`` get
    full lifecycle enforcement through the session's server.
    """
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

    # Route through compatibility server when no explicit session is given.
    # The compat session is created in READY state for backward compatibility
    # with callers that do not perform the initialize handshake.
    if session is None:
        warnings.warn(
            "Calling handle_request() without an explicit session is deprecated. "
            "Use McpServer + McpSession for full lifecycle enforcement. "
            "This compatibility path will be removed in a future version.",
            DeprecationWarning,
            stacklevel=2,
        )
        compat = _get_compat_server()
        compat_session = McpSession(initial_state=McpSessionState.READY)
        compat_session._bind_owner(compat)
        return compat.handle_request(request, session=compat_session)

    # Explicit session: route through the session's owner server.
    try:
        owner = session.owner
    except RuntimeError:
        return _invalid_request(None, "Session owner is unavailable or closed")
    return owner.handle_request(request, session=session)


def main() -> int:
    """Main entry point for MCP server.

    Reads JSON-RPC requests from stdin and writes responses to stdout.
    Creates one McpServer and McpSession per connection for lifecycle
    management and state isolation.
    """
    os.environ["EGGCALC_NO_CONFIG"] = "1"
    config = McpServerConfig.from_environment()
    server = McpServer(config=config)
    session = server.create_session(McpSessionState.UNINITIALIZED)
    request_times: deque[float] = deque()
    window = 1.0  # sliding window in seconds
    try:
        for line in sys.stdin:
            try:
                line = line.strip()
                if not line:
                    continue

                response: dict[str, Any] | None = None
                if len(line.encode('utf-8')) > config.max_request_bytes:
                    response = _parse_error(
                        None,
                        f"Request exceeds maximum size of {config.max_request_bytes} bytes",
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

                if len(request_times) >= config.max_requests_per_second:
                    response = _invalid_request_error(
                        request.get("id") if isinstance(request, dict) else None,
                        f"Rate limit exceeded: max {config.max_requests_per_second} requests per second",
                    )
                    print(json.dumps(response), flush=True)
                    continue

                request_times.append(now)

                try:
                    response = server.handle_request(request, session=session)
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
            except (BrokenPipeError, ValueError):
                return 0
        return 0
    finally:
        server.close()


if __name__ == "__main__":
    raise SystemExit(main())


# Build-time alias for MCP entry point
mcp_main = main
