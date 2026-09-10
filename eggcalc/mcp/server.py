"""
MCP server implementation for eggcalc.

Provides a stdio-based MCP server that exposes exact text, Unicode,
and measurement tools to agents.
"""

from __future__ import annotations

import atexit
import enum
import inspect
import json
import logging
import math
import multiprocessing
import os
import re
import sys
import threading
import time
import unicodedata
import warnings
import weakref
from collections import deque
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from dataclasses import dataclass as _dataclass
from dataclasses import field as _field
from types import MappingProxyType
from typing import Any, TypedDict, cast

from .. import __version__
from .. import evaluator as _evaluator
from ..capabilities import detect_capabilities
from .schemas import (
    PROFILE_NAMES,
    SCHEMA_DETAIL_FULL,
    SELECTION_KEYWORD_MAX_LENGTH,
    SELECTION_KEYWORDS_MAX_COUNT,
    SELECTION_SUMMARY_MAX_LENGTH,
    TOOL_METADATA,
    TOOL_PROFILES,
    TOOL_SCHEMAS,
    compact_schema,
    get_tool_annotations,
    normal_schema,
)
from .tools import _sanitize_error


def _build_tool_handlers(
    metadata: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Derive public tool-name -> handler mapping from catalog metadata.

    Plan 040 Workstream A: TOOL_METADATA owns the handler locator
    (attribute name in eggcalc.mcp.tools). Lookup is eager and
    deterministic at import so bad bindings fail fast rather than on
    the first agent call.

    Single-file note: the build inlines all modules into one namespace
    (conflict handlers under the _mcp_ prefix), so globals() is checked
    first and the tools-module import below never executes there.
    """
    handlers: dict[str, Any] = {}
    for tool_name, meta in metadata.items():
        attr = meta.get("handler")
        if not isinstance(attr, str) or not attr:
            raise ValueError(f"Tool {tool_name!r} has missing/empty handler locator")
        if not attr.isidentifier():
            raise ValueError(
                f"Tool {tool_name!r} has invalid handler locator {attr!r}: "
                "must be a Python attribute identifier in eggcalc.mcp.tools"
            )
        handler = globals().get(attr)
        if handler is None:
            handler = globals().get(f"_mcp_{attr}")
        if handler is None:
            from . import tools as _tools_mod

            handler = getattr(_tools_mod, attr, None)
        if not callable(handler):
            raise ValueError(
                f"Tool {tool_name!r} handler {attr!r} did not resolve "
                "to a callable in eggcalc.mcp.tools"
            )
        handlers[tool_name] = handler
    return handlers


TOOL_HANDLERS: dict[str, Any] = _build_tool_handlers(TOOL_METADATA)


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
    CLIENT_CAPABILITIES_META_KEY,
    CLIENT_INFO_META_KEY,
    LATEST_LEGACY_PROTOCOL_VERSION,
    # LATEST_SUPPORTED_PROTOCOL_VERSION and MODERN_PROTOCOL_VERSIONS are
    # re-exported for compatibility, see architecture/authority_inventory.md.
    # They stay inside this parenthesized block on purpose: build_single.py
    # strips top-level multi-line imports, while single-line eggcalc imports
    # would survive into the single-file build as live package imports.
    LATEST_SUPPORTED_PROTOCOL_VERSION,  # noqa: F401
    LEGACY_PROTOCOL_VERSIONS,
    MODERN_CACHE_SCOPE,
    MODERN_CACHE_TTL_MS,
    MODERN_METHODS,
    MODERN_PROTOCOL_VERSIONS,  # noqa: F401
    PROTOCOL_VERSION_META_KEY,
    SERVER_INFO_META_KEY,
    SUPPORTED_PROTOCOL_VERSIONS,
    protocol_era,
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
    # Adopt orphans tracked by the evaluator and regex tool paths.
    try:
        from ..evaluator import (
            _orphaned_eval_lock,
            _orphaned_eval_order,
            _orphaned_eval_processes,
        )

        with _orphaned_eval_lock:
            with _orphaned_lock:
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
            with _orphaned_lock:
                _orphaned_processes.update(_orphaned_regex_processes)
            _orphaned_regex_processes.clear()
            _orphaned_regex_order.clear()
    except Exception:
        pass
    # Iterate over a snapshot; never hold the lock across blocking joins.
    with _orphaned_lock:
        snapshot = list(_orphaned_processes)
    for proc in snapshot:
        try:
            if not proc.is_alive():
                try:
                    proc.close()
                except Exception:
                    pass
                with _orphaned_lock:
                    _orphaned_processes.discard(proc)
                logging.debug("Reaped finished orphaned child process pid=%s", proc.pid)
                continue
            proc.terminate()
            proc.join(timeout=1)
            if proc.is_alive():
                proc.kill()
                proc.join(timeout=1)
            if not proc.is_alive():
                try:
                    proc.close()
                except Exception:
                    pass
                with _orphaned_lock:
                    _orphaned_processes.discard(proc)
                logging.debug("Cleaned up orphaned child process pid=%s", proc.pid)
            # Still alive after terminate+kill: remain tracked for a later pass.
        except Exception:
            pass


atexit.register(_cleanup_orphaned_processes)


def _tracked_orphan_count() -> int:
    """Number of child processes currently held for defensive orphan cleanup."""
    with _orphaned_lock:
        return len(_orphaned_processes)


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


def _invalid_jsonrpc_id_reason(request_id: Any) -> str | None:
    """Return an error message when *request_id* is not a legal JSON-RPC id.

    Legal ids per JSON-RPC 2.0 are strings, numbers, or null. ``bool`` is
    rejected explicitly even though it subclasses ``int`` (JSON ``true``
    is not a valid id), and non-finite floats are rejected because they
    have no JSON representation. ``None`` means "absent or null" and is
    left for callers to interpret.
    """
    if request_id is None:
        return None
    if isinstance(request_id, bool):
        return "'id' must be a string, number, or null"
    if isinstance(request_id, float) and not math.isfinite(request_id):
        return "'id' must be a string, number, or null"
    if not isinstance(request_id, (str, int, float)):
        return "'id' must be a string, number, or null"
    return None


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


# ---------------------------------------------------------------------------
# Modern (2026-07-28) stateless era
#
# The modern era has no initialize handshake and no protocol-level session.
# Each request carries its protocol version and client capabilities in
# ``params._meta`` under reserved ``io.modelcontextprotocol/*`` keys, and
# every result carries server identity in ``result._meta``.  All dispatch
# here is server-owned: modern requests never touch ``McpSession`` state.
# ---------------------------------------------------------------------------

#: Concise server instructions shared by modern ``server/discover`` and
#: the legacy ``initialize`` response.  One authority; do not maintain
#: a second prose copy.
SERVER_INSTRUCTIONS = (
    "Prefer composite preflight tools (edit_preflight, command_preflight, "
    "config_preflight) for general safety checks and specialist primitives "
    "when exact domain evidence is required. Prefer json_extract over the "
    "deprecated json_query. Use math_eval for deterministic calculations "
    "and unit expressions rather than model arithmetic. All tools are local "
    "and deterministic; they do not access the network or filesystem."
)

#: Bounds for request-local modern metadata (defense in depth on top of the
#: request-size boundary; the envelope is never persisted).
_MAX_MODERN_META_KEYS = 64
_MAX_MODERN_CAPABILITY_KEYS = 64
_MAX_MODERN_CLIENT_INFO_FIELD = 256


def _modern_server_info() -> dict[str, str]:
    """Return the self-reported server identity stamp for modern results."""
    return {"name": "eggcalc", "version": __version__}


def _attach_modern_server_info(result: dict[str, Any]) -> dict[str, Any]:
    """Stamp a modern result with server identity in ``_meta``.

    A handler-authored ``_meta`` mapping wins on key conflicts except for
    the reserved server-identity key, which always reflects this server.
    """
    meta = result.get("_meta")
    if not isinstance(meta, dict):
        meta = {}
    else:
        meta = dict(meta)
    meta[SERVER_INFO_META_KEY] = _modern_server_info()
    result["_meta"] = meta
    return result


@_dataclass(frozen=True)
class ModernRequestContext:
    """Request-scoped modern client metadata.

    Immutable and never persisted: modern behavior must not depend on a
    previous request from the same stdio process.  Holds only the
    request-scoped information eggcalc needs (protocol version, client
    capabilities, optional validated client info).
    """

    protocol_version: str = "2026-07-28"
    client_capabilities: Mapping[str, Any] = _field(default_factory=lambda: MappingProxyType({}))
    client_info: Mapping[str, Any] | None = None


def _unsupported_version_error(
    request_id: Any, requested: Any, supported: tuple[str, ...] | None = None
) -> dict[str, Any]:
    """Build the spec-defined unsupported-version error (-32022).

    Carries ``data.supported`` so the client can retry with a mutually
    supported revision instead of falling back silently.  Defaults to the
    authoritative ``SUPPORTED_PROTOCOL_VERSIONS``; pass the owning
    server's configured versions when serving a real request.
    """
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": -32022,
            "message": f"Unsupported protocol version: {requested}",
            "data": {
                "supported": list(
                    supported if supported is not None else SUPPORTED_PROTOCOL_VERSIONS
                ),
                "requested": requested,
            },
        },
    }


def _validate_modern_envelope(
    request: dict[str, Any],
    supported_versions: tuple[str, ...] | None = None,
) -> tuple[ModernRequestContext | None, dict[str, Any] | None]:
    """Validate the modern ``params._meta`` envelope of a candidate request.

    Returns ``(context, None)`` on success or ``(None, error_response)``
    when the envelope is malformed (``-32602``) or names a revision the
    server does not serve (``-32022``).  Missing ``clientInfo`` is
    accepted (SHOULD, not MUST); present-but-malformed ``clientInfo`` is
    rejected.
    """
    request_id = request.get("id")
    supported = (
        supported_versions if supported_versions is not None else SUPPORTED_PROTOCOL_VERSIONS
    )
    params = request.get("params")
    if not isinstance(params, dict):
        return None, _invalid_params(request_id, "Modern requests require params object")
    meta = params.get("_meta")
    if not isinstance(meta, dict):
        return None, _invalid_params(request_id, "Modern requests require params._meta object")
    if len(meta) > _MAX_MODERN_META_KEYS:
        return None, _invalid_params(request_id, "Modern params._meta has too many entries")

    version = meta.get(PROTOCOL_VERSION_META_KEY)
    if not isinstance(version, str) or not version.strip():
        return None, _invalid_params(
            request_id, "Modern params._meta requires 'io.modelcontextprotocol/protocolVersion'"
        )
    if version not in supported:
        return None, _unsupported_version_error(request_id, version, supported)

    capabilities = meta.get(CLIENT_CAPABILITIES_META_KEY)
    if not isinstance(capabilities, dict):
        return None, _invalid_params(
            request_id,
            "Modern params._meta requires 'io.modelcontextprotocol/clientCapabilities'",
        )
    if len(capabilities) > _MAX_MODERN_CAPABILITY_KEYS:
        return None, _invalid_params(request_id, "Modern clientCapabilities has too many entries")

    raw_info = meta.get(CLIENT_INFO_META_KEY)
    client_info: Mapping[str, Any] | None = None
    if raw_info is not None:
        if not isinstance(raw_info, dict):
            return None, _invalid_params(request_id, "Modern clientInfo must be an object")
        name = raw_info.get("name")
        if not isinstance(name, str) or not name.strip():
            return None, _invalid_params(
                request_id, "Modern clientInfo.name must be a non-empty string"
            )
        if len(name) > _MAX_MODERN_CLIENT_INFO_FIELD:
            return None, _invalid_params(request_id, "Modern clientInfo.name is too long")
        version_info = raw_info.get("version", "")
        if not isinstance(version_info, str):
            return None, _invalid_params(request_id, "Modern clientInfo.version must be a string")
        if len(version_info) > _MAX_MODERN_CLIENT_INFO_FIELD:
            return None, _invalid_params(request_id, "Modern clientInfo.version is too long")
        client_info = MappingProxyType({"name": name, "version": version_info})

    return (
        ModernRequestContext(
            protocol_version=version,
            client_capabilities=MappingProxyType(dict(capabilities)),
            client_info=client_info,
        ),
        None,
    )


def _classify_request_era(
    request: Any,
    supported_versions: tuple[str, ...] | None = None,
) -> tuple[str | None, dict[str, Any] | None, ModernRequestContext | None]:
    """Classify an incoming request into exactly one protocol era.

    Returns ``(era, error, context)`` where *era* is ``"modern"``,
    ``"legacy"``, or ``None`` when classification itself failed.  A
    request is a modern candidate only when ``params._meta`` carries a
    reserved ``io.modelcontextprotocol/`` key — the method name alone
    (including ``server/discover``) never selects the modern era.  An
    explicitly unsupported protocol revision yields a ``-32022`` error
    and never falls through into the legacy state machine.  A modern
    envelope naming a supported *legacy* revision is served by the
    legacy session path (the handshake era owns those revisions).
    """
    if not isinstance(request, dict):
        return "legacy", None, None
    params = request.get("params")
    if not isinstance(params, dict):
        return "legacy", None, None
    meta = params.get("_meta")
    if not isinstance(meta, dict):
        return "legacy", None, None
    if not any(isinstance(key, str) and key.startswith("io.modelcontextprotocol/") for key in meta):
        return "legacy", None, None
    context, error = _validate_modern_envelope(request, supported_versions)
    if error is not None:
        return None, error, None
    assert context is not None
    if protocol_era(context.protocol_version) == "modern":
        return "modern", None, context
    return "legacy", None, None


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
    if isinstance(value, dict):
        return {k: thaw_owned(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [thaw_owned(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return {thaw_owned(v) for v in value}
    return value


class ToolMatch(TypedDict):
    """Deterministic lexical match for harness-side tool discovery (Plan 041).

    Returned by :meth:`ToolRegistry.search_tools`. Carries ranking evidence
    (``score``/``matched_on``) but never full input/output schemas — the
    harness loads those via the registry or ``tools/list(names=[...])`` only
    for shortlisted names. Discovery never changes call authorization.
    """

    name: str
    score: int
    category: str
    selection_summary: str
    matched_on: list[str]


#: Maximum query text examined by ToolRegistry.search_tools (Plan 041: 2-4 KiB).
MAX_SEARCH_QUERY_LENGTH = 4096
#: Minimum/maximum result counts accepted by ToolRegistry.search_tools.
MIN_SEARCH_LIMIT = 1
MAX_SEARCH_LIMIT = 20

#: Integer ranking weights for deterministic lexical discovery (Plan 041
#: Workstream D). Higher evidence tiers strictly outrank lower ones so exact
#: name/alias lookups always beat weak description overlap. The exact-match
#: weights sit above the stacking ceiling of all lower tiers combined
#: (60 + 45 + 20 + 40 + 10 + 10 = 185), so an exact lookup can never lose
#: to accumulated weak overlap.
_SEARCH_WEIGHT_NAME_EXACT = 300
_SEARCH_WEIGHT_ALIAS_EXACT = 250
_SEARCH_WEIGHT_NAME_TOKEN = 60
_SEARCH_WEIGHT_NAME_PREFIX = 50
_SEARCH_WEIGHT_KEYWORD_PHRASE = 45
_SEARCH_WEIGHT_KEYWORD_TOKEN = 15
_SEARCH_WEIGHT_KEYWORD_TOKEN_CAP = 45
_SEARCH_WEIGHT_CATEGORY = 20
_SEARCH_WEIGHT_SUMMARY_TOKEN = 8
_SEARCH_WEIGHT_SUMMARY_TOKEN_CAP = 40
_SEARCH_WEIGHT_DESCRIPTION_TOKEN = 2
_SEARCH_WEIGHT_DESCRIPTION_TOKEN_CAP = 10
_SEARCH_WEIGHT_TAG_TOKEN = 2
_SEARCH_WEIGHT_TAG_TOKEN_CAP = 10


def _normalize_search_text(text: str) -> str:
    """NFKC-normalize and casefold search text (stdlib only, bounded)."""
    return unicodedata.normalize("NFKC", text).casefold()


def _tokenize_search_text(text: str) -> list[str]:
    """Split normalized text into alphanumeric tokens.

    Tokenizes on whitespace, punctuation, and underscore/hyphen boundaries
    so ``patch_apply_check``, ``patch-apply-check``, and ``patch apply
    check`` all produce the same token stream. Single-character tokens
    (stray digits, articles) are dropped as noise.
    """
    return [tok for tok in re.findall(r"[a-z0-9]+", _normalize_search_text(text)) if len(tok) >= 2]


def _score_search_tool(
    query: str,
    query_tokens: list[str],
    query_token_set: set[str],
    name: str,
    meta: Mapping[str, Any],
    description: str,
) -> tuple[int, list[str]]:
    """Score one catalog tool against a normalized query.

    Returns ``(score, matched_on)`` with integer weights and evidence
    strings. Score 0 means no evidence matched.
    """
    score = 0
    matched_on: list[str] = []
    normalized_query = _normalize_search_text(query).strip()

    name_tokens = name.casefold().replace("-", "_").split("_")
    name_token_set = set(name_tokens)

    # 1. Exact tool-name match (separator-insensitive).
    name_flat = _normalize_search_text(name).replace("_", "").replace("-", "")
    query_flat = re.sub(r"[^a-z0-9]", "", normalized_query)
    if query_flat and query_flat == name_flat:
        score += _SEARCH_WEIGHT_NAME_EXACT
        matched_on.append("name:exact")
        return score, matched_on

    # 2. Exact alias match.
    aliases = meta.get("aliases", []) or []
    for alias in aliases:
        if not isinstance(alias, str):
            continue
        alias_flat = re.sub(r"[^a-z0-9]", "", _normalize_search_text(alias))
        if query_flat and query_flat == alias_flat:
            score += _SEARCH_WEIGHT_ALIAS_EXACT
            matched_on.append(f"alias:{alias}")
            return score, matched_on

    # 3. Tool-name token/prefix match.
    token_hits = query_token_set & name_token_set
    if token_hits:
        score += _SEARCH_WEIGHT_NAME_TOKEN
        matched_on.append(f"name-token:{sorted(token_hits)[0]}")
    else:
        for qtok in query_token_set:
            if len(qtok) < 3:
                continue
            for ntok in name_token_set:
                if ntok.startswith(qtok) or qtok.startswith(ntok):
                    score += _SEARCH_WEIGHT_NAME_PREFIX
                    matched_on.append(f"name-prefix:{qtok}")
                    break
            else:
                continue
            break

    # 4. Keyword phrase/token match (authored discovery synonyms).
    keywords = meta.get("keywords", []) or []
    phrase_hit = False
    for keyword in keywords:
        if not isinstance(keyword, str) or not keyword:
            continue
        norm_kw = _normalize_search_text(keyword).strip()
        if norm_kw and norm_kw in normalized_query:
            score += _SEARCH_WEIGHT_KEYWORD_PHRASE
            matched_on.append(f"keyword:{keyword}")
            phrase_hit = True
            break
    if not phrase_hit:
        kw_token_hits = 0
        for keyword in keywords:
            if not isinstance(keyword, str):
                continue
            for ktok in _tokenize_search_text(keyword):
                if ktok in query_token_set:
                    kw_token_hits += 1
        if kw_token_hits:
            capped = min(
                kw_token_hits * _SEARCH_WEIGHT_KEYWORD_TOKEN, _SEARCH_WEIGHT_KEYWORD_TOKEN_CAP
            )
            score += capped
            matched_on.append(f"keyword-tokens:+{kw_token_hits}")

    # 5. Category match.
    category = str(meta.get("category", ""))
    if category:
        cat_tokens = set(_tokenize_search_text(category))
        if query_token_set & cat_tokens:
            score += _SEARCH_WEIGHT_CATEGORY
            matched_on.append(f"category:{category}")

    # 6. Selection-summary token overlap (authored selection signal).
    summary = str(meta.get("selection_summary", ""))
    if summary:
        overlap = len(query_token_set & set(_tokenize_search_text(summary)))
        if overlap:
            score += min(overlap * _SEARCH_WEIGHT_SUMMARY_TOKEN, _SEARCH_WEIGHT_SUMMARY_TOKEN_CAP)
            matched_on.append(f"summary:+{overlap}")

    # 7. Full description/tags as low-weight fallback.
    if description:
        overlap = len(query_token_set & set(_tokenize_search_text(description)))
        if overlap:
            score += min(
                overlap * _SEARCH_WEIGHT_DESCRIPTION_TOKEN,
                _SEARCH_WEIGHT_DESCRIPTION_TOKEN_CAP,
            )
            matched_on.append(f"description:+{overlap}")
    tags = meta.get("tags", []) or []
    tag_overlap = 0
    for tag in tags:
        if isinstance(tag, str):
            tag_overlap += len(query_token_set & set(_tokenize_search_text(tag)))
    if tag_overlap:
        score += min(tag_overlap * _SEARCH_WEIGHT_TAG_TOKEN, _SEARCH_WEIGHT_TAG_TOKEN_CAP)
        matched_on.append(f"tags:+{tag_overlap}")

    return score, matched_on


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
    _VALID_TIERS: frozenset[int] = frozenset({0, 1, 2, 3})
    _VALID_CATEGORIES: frozenset[str] = frozenset(
        {
            "math",
            "text",
            "json",
            "toml",
            "config",
            "regex",
            "path",
            "shell",
            "patch",
            "identifier",
            "markdown",
            "version",
            "cargo",
            "list",
            "validation",
            "unicode",
            "manifest",
            "repo",
            "network",
            "encoding",
            "temporal",
        }
    )
    _VALID_COST: frozenset[str] = frozenset({"cheap", "moderate", "heavy"})
    _VALID_STABILITY: frozenset[str] = frozenset({"stable", "experimental", "deprecated"})
    _VALID_ANNOTATION_KEYS: frozenset[str] = frozenset(
        {
            "title",
            "readOnlyHint",
            "destructiveHint",
            "idempotentHint",
            "openWorldHint",
        }
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

        # Plan 040 Workstream F: catalog and protocol authorities must agree
        # on the public tool-name set (no extra/missing entries either way).
        if metadata_names != schema_names:
            raise ValueError(
                "Metadata/schema key mismatch: "
                f"metadata-only={sorted(metadata_names - schema_names)} "
                f"schema-only={sorted(schema_names - metadata_names)}"
            )

        for name, handler in self._handlers.items():
            if not callable(handler):
                raise ValueError(f"Handler for {name!r} is not callable")

        for name in self._metadata:
            meta = self._metadata[name]
            # Lenient for custom/test registries (which use {} or partial
            # metadata): only validate fields when present. The canonical
            # catalog is strictly validated at import by
            # schemas._validate_catalog_metadata().
            if "handler" in meta:
                handler_loc = meta.get("handler")
                if not isinstance(handler_loc, str) or not handler_loc:
                    raise ValueError(f"Tool {name!r} has missing/empty handler locator")
                if not handler_loc.isidentifier():
                    raise ValueError(f"Tool {name!r} has invalid handler locator {handler_loc!r}")
            if "tags" in meta:
                tags = meta.get("tags")
                if not isinstance(tags, (list, tuple)) or not all(isinstance(t, str) for t in tags):
                    raise ValueError(f"Tool {name!r} has invalid tags: must be list[str]")
            if "selection_summary" in meta:
                summary = meta.get("selection_summary")
                if not isinstance(summary, str) or not summary:
                    raise ValueError(f"Tool {name!r} has missing/empty selection_summary")
                if len(summary) > SELECTION_SUMMARY_MAX_LENGTH:
                    raise ValueError(
                        f"Tool {name!r} selection_summary exceeds "
                        f"{SELECTION_SUMMARY_MAX_LENGTH} chars"
                    )
            if "keywords" in meta:
                keywords = meta.get("keywords")
                if not isinstance(keywords, (list, tuple)) or not all(
                    isinstance(k, str) for k in keywords
                ):
                    raise ValueError(f"Tool {name!r} has invalid keywords: must be list[str]")
                if len(keywords) > SELECTION_KEYWORDS_MAX_COUNT:
                    raise ValueError(f"Tool {name!r} has too many keywords")
                for keyword in keywords:
                    if not keyword or len(keyword) > SELECTION_KEYWORD_MAX_LENGTH:
                        raise ValueError(f"Tool {name!r} has invalid keyword {keyword!r}")
            if "tier" in meta and meta.get("tier") not in self._VALID_TIERS:
                raise ValueError(f"Tool {name!r} has invalid tier {meta.get('tier')!r}")
            if "category" in meta and meta.get("category") not in self._VALID_CATEGORIES:
                raise ValueError(f"Tool {name!r} has invalid category {meta.get('category')!r}")
            if "cost" in meta and meta.get("cost") not in self._VALID_COST:
                raise ValueError(f"Tool {name!r} has invalid cost {meta.get('cost')!r}")
            if "stability" in meta and meta.get("stability") not in self._VALID_STABILITY:
                raise ValueError(f"Tool {name!r} has invalid stability {meta.get('stability')!r}")
            if "profiles" in meta and not isinstance(meta.get("profiles"), (list, tuple)):
                raise ValueError(f"Tool {name!r} has invalid profiles: must be list")
            if "aliases" in meta and not isinstance(meta.get("aliases"), (list, tuple)):
                raise ValueError(f"Tool {name!r} has invalid aliases: must be list")
            if "harness_use" in meta and not isinstance(meta.get("harness_use"), (list, tuple)):
                raise ValueError(f"Tool {name!r} has invalid harness_use: must be list")
            if "composite" in meta and not isinstance(meta.get("composite"), bool):
                raise ValueError(f"Tool {name!r} has invalid composite: must be bool")
            exposure = meta.get("llm_exposure")
            if exposure is not None and exposure not in self._VALID_LLM_EXPOSURE:
                raise ValueError(
                    f"Unsupported llm_exposure {exposure!r} for tool {name!r}; "
                    f"must be one of {sorted(self._VALID_LLM_EXPOSURE)}"
                )
            annotations = get_tool_annotations(name)
            for key, value in annotations.items():
                if key not in self._VALID_ANNOTATION_KEYS:
                    raise ValueError(f"Tool {name!r} has unsupported annotation {key!r}")
                if key == "title":
                    if not isinstance(value, str):
                        raise ValueError(f"Tool {name!r} annotation {key!r} must be str")
                elif not isinstance(value, bool):
                    raise ValueError(f"Tool {name!r} annotation {key!r} must be bool")

        # Protocol schemas must not carry authored selection metadata
        # (Plan 040 Workstream B: tier/tags live in TOOL_METADATA only).
        for name in self._schemas:
            schema = self._schemas[name]
            if isinstance(schema, Mapping):
                if "tier" in schema:
                    raise ValueError(
                        f"Schema for {name!r} must not contain authored 'tier' "
                        "(authority: TOOL_METADATA)"
                    )
                if "tags" in schema:
                    raise ValueError(
                        f"Schema for {name!r} must not contain authored 'tags' "
                        "(authority: TOOL_METADATA)"
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
            # Note: canonical profiles from _build_profiles() are sorted
            # deterministically (checked by test_tool_inventory); custom
            # registries are not required to be sorted here to avoid
            # breaking isolated executor tests.

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
        result: dict[str, Any] = thaw_owned(dict(schema))
        return result

    def get_metadata(self, name: str) -> dict[str, Any]:
        meta = self._metadata.get(name)
        if meta is None:
            return {}
        result: dict[str, Any] = thaw_owned(dict(meta))
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

    def search_tools(
        self,
        query: str,
        *,
        profile: str = "full",
        limit: int = 5,
    ) -> list[ToolMatch]:
        """Rank catalog tools against natural-language task text (Plan 041).

        Deterministic stdlib-only lexical ranking over the fixed catalog —
        no embeddings, no network, no model. Intended for aware harnesses
        (e.g. codegg) implementing progressive disclosure: start from a
        small core profile, search with the user task text, then load full
        definitions for the shortlisted names via the registry or
        ``tools/list(names=[...])``.

        Scoring evidence tiers (highest first): exact tool-name match,
        exact alias match, tool-name token/prefix match, keyword
        phrase/token match, category match, selection-summary token
        overlap, full description/tags fallback. Ties break by canonical
        tool name, so results are identical across runs and processes.

        The query is truncated to ``MAX_SEARCH_QUERY_LENGTH`` chars and
        ``limit`` is clamped to ``MIN_SEARCH_LIMIT..MAX_SEARCH_LIMIT``.
        Only tools visible under ``profile`` are ranked; search results
        never make a tool callable outside the configured profile —
        discovery and call authorization stay separate. Tools scoring
        zero are omitted, so an unrelated query returns ``[]``.
        """
        if not isinstance(query, str):
            raise ValueError(f"search query must be str, got {type(query).__name__}")
        if not isinstance(limit, int) or isinstance(limit, bool):
            raise ValueError(f"search limit must be int, got {limit!r}")
        if limit < MIN_SEARCH_LIMIT or limit > MAX_SEARCH_LIMIT:
            raise ValueError(
                f"search limit must be {MIN_SEARCH_LIMIT}..{MAX_SEARCH_LIMIT}, " f"got {limit!r}"
            )
        candidates = self.get_profile_tools(profile)
        truncated = query[:MAX_SEARCH_QUERY_LENGTH]
        if not truncated.strip():
            return []
        query_tokens = _tokenize_search_text(truncated)
        if not query_tokens:
            return []
        query_token_set = set(query_tokens)

        scored: list[tuple[int, str, ToolMatch]] = []
        for name in candidates:
            meta = self._metadata.get(name, {})
            schema = self._schemas.get(name, {})
            description = ""
            if isinstance(schema, Mapping):
                raw_desc = schema.get("description", "")
                if isinstance(raw_desc, str):
                    description = raw_desc
            score, matched_on = _score_search_tool(
                truncated, query_tokens, query_token_set, name, meta, description
            )
            if score <= 0:
                continue
            category = meta.get("category", "")
            summary = meta.get("selection_summary", "")
            scored.append(
                (
                    score,
                    name,
                    ToolMatch(
                        name=name,
                        score=score,
                        category=category if isinstance(category, str) else "",
                        selection_summary=summary if isinstance(summary, str) else "",
                        matched_on=matched_on,
                    ),
                )
            )
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [match for _, _, match in scored[:limit]]


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
        modern: bool = False,
    ) -> dict[str, Any]:
        """Execute a tool call with validation, timeout, and cancellation.

        Uses the evaluator captured from the request context when provided;
        falls back to the executor's own evaluator for backward compatibility.

        Result boundary (Plan 039): the handler return value is split once
        via :func:`_split_tool_wire_result` into compatibility text
        (the full envelope) and ``structuredContent``
        (``text_envelope["result"]``) built from the same in-memory
        object. Success payloads are validated against the declared
        ``outputSchema`` before emission; a mismatch is a server defect
        and returns a sanitized ``-32000`` error (never a traceback).
        Error envelopes stay ``isError`` without a success payload.

        ``structuredContent`` is emitted on both eras when the declared
        output schema is object-rooted (all current tools); only the
        modern (2026-07-28) path additionally carries ``resultType``.
        The ``max_output_bytes`` bound applies to the canonical handler
        envelope JSON (not the duplicated wire form); both
        representations are serialized only after the envelope passes.
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
                with self._accounting_lock:
                    total_inflight = self._total_inflight
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32000,
                        "message": (
                            f"Server busy: {total_inflight} requests in flight "
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
                        return _run_handler_in_thread(
                            handler,
                            arguments,
                            active_evaluator,
                            timeout_seconds=self._config.max_tool_timeout_seconds,
                        )
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
            result_payload: dict[str, Any] = {
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
            }
            if modern:
                result_payload["resultType"] = "complete"
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": result_payload,
            }

        if isinstance(result, dict) and result.get("ok") is False:
            serialized = json.dumps(result)
            error_payload: dict[str, Any] = {
                "content": [{"type": "text", "text": serialized}],
                "isError": True,
            }
            if modern:
                error_payload["resultType"] = "complete"
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": error_payload,
            }

        wire = _split_tool_wire_result(result)
        if wire.is_error:
            # Non-success handler shape: preserve existing error contract.
            # (The ok=False branch above already returned; this covers
            # non-dict handler results.) The single output bound still
            # applies so a malformed huge payload cannot escape unbounded.
            wire_serialized = json.dumps(wire.text_envelope)
            if len(wire_serialized.encode("utf-8")) > self._config.max_output_bytes:
                wire_serialized = json.dumps(
                    {
                        "ok": False,
                        "tool": name,
                        "error_type": "output_too_large",
                        "error": (
                            f"Output exceeds {self._config.max_output_bytes} "
                            "bytes and was truncated"
                        ),
                        "hints": ["Try reducing input size or using a summary/detail option"],
                        "warnings": ["Output was truncated due to size limit"],
                    }
                )
            wire_error_payload: dict[str, Any] = {
                "content": [{"type": "text", "text": wire_serialized}],
                "isError": True,
            }
            if modern:
                wire_error_payload["resultType"] = "complete"
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": wire_error_payload,
            }

        output_error = _validate_output_payload(
            name, wire.structured_content, schemas=self._registry.schemas
        )
        if output_error is not None:
            logging.error(
                "Output-schema mismatch for tool %r: %s",
                name,
                output_error,
            )
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32000,
                    "message": f"Tool execution error: output validation failed for tool '{name}'",
                },
            }

        serialized = json.dumps(wire.text_envelope)
        if len(serialized.encode("utf-8")) > self._config.max_output_bytes:
            truncated = {
                "ok": False,
                "tool": name,
                "error_type": "output_too_large",
                "error": f"Output exceeds {self._config.max_output_bytes} bytes and was truncated",
                "hints": ["Try reducing input size or using a summary/detail option"],
                "warnings": ["Output was truncated due to size limit"],
            }
            truncated_payload: dict[str, Any] = {
                "content": [{"type": "text", "text": json.dumps(truncated)}],
                "isError": True,
            }
            if modern:
                truncated_payload["resultType"] = "complete"
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": truncated_payload,
            }

        success_payload: dict[str, Any] = {"content": [{"type": "text", "text": serialized}]}
        if modern:
            success_payload["resultType"] = "complete"
        if _is_object_rooted_output_schema(name, schemas=self._registry.schemas):
            success_payload["structuredContent"] = wire.structured_content
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": success_payload,
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
        """Shut down the thread pool, cancelling queued futures.

        The wait for active work is bounded: a handler that already overran
        its timeout cannot be cancelled and may never finish, so shutdown
        gives up after one timeout period instead of blocking forever.
        """
        with self._lock:
            self._closed = True
            executor = self._executor
            self._executor = None
        if executor is not None:
            shutdown_done = threading.Event()

            def _shutdown() -> None:
                executor.shutdown(wait=True, cancel_futures=True)
                shutdown_done.set()

            reaper = threading.Thread(target=_shutdown, name="mcp-tool-shutdown", daemon=True)
            reaper.start()
            if not shutdown_done.wait(timeout=self._config.max_tool_timeout_seconds):
                logging.warning(
                    "ToolExecutor shutdown exceeded %ss; abandoning still-running handlers",
                    self._config.max_tool_timeout_seconds,
                )
        # Release any QUEUED reservations that were cancelled by
        # cancel_futures=True before the worker wrapper could run.
        # ACTIVE reservations are intentionally left in the set: their
        # handlers are still running and will release them through the
        # normal path, keeping len(_reservations) == _total_inflight
        # (and the other accounting invariants) true throughout shutdown.
        with self._accounting_lock:
            for res in list(self._reservations):
                if res.state == ReservationState.QUEUED:
                    res.state = ReservationState.RELEASED
                    self._queued_count -= 1
                    self._total_inflight -= 1
                    self._reservations.discard(res)
            abandoned = sum(1 for res in self._reservations if res.state == ReservationState.ACTIVE)
            if abandoned:
                logging.warning(
                    "ToolExecutor closed with %d abandoned active reservation(s); "
                    "counters settle when their handlers finish",
                    abandoned,
                )

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


def _deep_freeze(value: Any) -> Any:
    """Recursively freeze JSON-like structures for deep immutability.

    Dicts become ``MappingProxyType``, lists become tuples, tuples are
    recursed into, and sets become frozensets; leaves (scalars,
    callables) pass through unchanged.
    """
    if isinstance(value, dict):
        return MappingProxyType({key: _deep_freeze(val) for key, val in value.items()})
    if isinstance(value, list):
        return tuple(_deep_freeze(val) for val in value)
    if isinstance(value, tuple):
        return tuple(_deep_freeze(val) for val in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_deep_freeze(val) for val in value)
    return value


def _to_plain(value: Any) -> Any:
    """Inverse of :func:`_deep_freeze`: rebuild plain dicts/lists."""
    if isinstance(value, dict):
        return {key: _to_plain(val) for key, val in value.items()}
    if isinstance(value, Mapping):
        return {key: _to_plain(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_plain(val) for val in value]
    return value


@_dataclass(frozen=True)
class ConfigSnapshot:
    """Deeply immutable configuration snapshot for atomic replacement.

    Dict fields are defensively deep-copied on construction and stored
    as ``MappingProxyType`` so callers cannot mutate the snapshot through
    constructor inputs or returned field values. Nested dicts/lists are
    frozen recursively so the structure is immutable at every level.
    """

    generation: int = 0
    constants: Mapping[str, Any] = _field(default_factory=dict)
    functions: Mapping[str, Any] = _field(default_factory=dict)
    units: Mapping[str, Any] = _field(default_factory=dict)
    policy: EvaluationPolicy | str = EvaluationPolicy.DEFAULT

    def __post_init__(self) -> None:
        # Deep copy mutable defaults to prevent external mutation, then
        # wrap in MappingProxyType for deep immutability.
        object.__setattr__(self, "constants", MappingProxyType(dict(_deep_freeze(self.constants))))
        object.__setattr__(self, "functions", MappingProxyType(dict(_deep_freeze(self.functions))))
        object.__setattr__(self, "units", MappingProxyType(dict(_deep_freeze(self.units))))
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
            "constants": _to_plain(self.constants),
            "functions": {k: getattr(v, "__name__", str(v)) for k, v in self.functions.items()},
            "units": _to_plain(self.units),
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

    Delegates to parse_config_snapshot for validation, then extracts
    the fields into a ConfigCandidate.  Raises ConfigError on invalid input.
    """
    snapshot = parse_config_snapshot(
        constants=constants,
        functions=functions,
        units=units,
        policy=policy,
    )
    resolved_policy = (
        snapshot.policy
        if isinstance(snapshot.policy, EvaluationPolicy)
        else EvaluationPolicy(snapshot.policy)
    )
    return ConfigCandidate(
        constants=snapshot.constants,
        functions=snapshot.functions,
        policy=resolved_policy,
    )


def _effective_policy(policy: EvaluationPolicy) -> EvaluationPolicy:
    """Resolve the effective evaluation policy.

    PERMISSIVE is a compatibility alias for DEFAULT behavior.
    Only STRICT has a distinct runtime effect (disabling both
    allow_random and allow_side_effects).
    """
    if policy is EvaluationPolicy.PERMISSIVE:
        return EvaluationPolicy.DEFAULT
    return policy


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
    # Normalize PERMISSIVE to DEFAULT (they are equivalent).
    effective = _effective_policy(policy)
    # STRICT always disables both; DEFAULT (including PERMISSIVE alias)
    # follows config flags.
    if effective == EvaluationPolicy.STRICT:
        allow_random, allow_side_effects = False, False
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

        Validates all input through parse_config_snapshot before constructing
        the snapshot.  Returns the new snapshot on success.  On failure the
        prior state is preserved unchanged.
        """
        owner = self._owner_ref() if self._owner_ref is not None else None
        if owner is not None:
            current = owner.runtime_context.snapshot
            snap = parse_config_snapshot(
                constants=constants if constants is not None else dict(current.constants),
                functions=functions if functions is not None else dict(current.functions),
                units=units if units is not None else dict(current.units),
                policy=policy if policy is not None else current.policy,
            )
            validated_snap = ConfigSnapshot(
                generation=current.generation + 1,
                constants=snap.constants,
                functions=snap.functions,
                units=snap.units,
                policy=snap.policy,
            )
            owner.activate_snapshot(validated_snap)
            return validated_snap
        with self._lock:
            new_gen = self._snapshot.generation + 1
            prev = self._snapshot
            snap = parse_config_snapshot(
                constants=constants if constants is not None else dict(prev.constants),
                functions=functions if functions is not None else dict(prev.functions),
                units=units if units is not None else dict(prev.units),
                policy=policy if policy is not None else prev.policy,
            )
            validated_snap = ConfigSnapshot(
                generation=new_gen,
                constants=snap.constants,
                functions=snap.functions,
                units=snap.units,
                policy=snap.policy,
            )
            self._validate_next(validated_snap)
            self._set_snapshot(validated_snap)
            return validated_snap

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

    def __init__(self, *, initial_state: McpSessionState = McpSessionState.UNINITIALIZED):
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
        # Monotonic timestamp for each recorded cancellation, used to
        # retire records that predate a later request reusing the id.
        self._cancelled_times: dict[Any, float] = {}

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

        # Retire cancellation records that predate this request: JSON-RPC
        # allows id reuse, so a late notifications/cancelled for an
        # already-completed request must not cancel this one.
        if (
            request_id is not None
            and method != "notifications/cancelled"
            and self._cancelled_requests
        ):
            self._discard_stale_cancellation(request_id, time.monotonic())

        response = self._dispatch_message(request, method, server, context)

        # A produced response retires any leftover cancellation record for
        # this id (the executor consumed it or the cancel raced completion).
        if (
            response is not None
            and "id" in request
            and (self._cancelled_requests or self._cancelled_times)
        ):
            self._discard_cancellation_record(request_id)

        return response

    def _dispatch_message(
        self,
        request: dict[str, Any],
        method: str,
        server: McpServer | None,
        context: RuntimeContext | None,
    ) -> dict[str, Any] | None:
        """Route a validated message to its handler (no lifecycle logic)."""
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
            if "id" not in request:
                return None
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
            return _invalid_params(request.get("id"), "Invalid params: expected object")

        name = params.get("name", "")
        arguments = params.get("arguments", {})
        if not isinstance(name, str) or not name:
            return _invalid_params(request.get("id"), "Invalid params: missing tool name")
        if not isinstance(arguments, dict):
            return _invalid_params(request.get("id"), "Invalid arguments: expected object")

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

        # Version negotiation: the handshake era negotiates legacy revisions
        # only.  Modern revisions are served statelessly via the per-request
        # _meta envelope and never via initialize; a handshake asking for a
        # modern (or unknown) revision falls back to the latest legacy
        # revision, matching the historical unsupported-version behavior.
        configured_versions = (
            server.config.supported_protocol_versions
            if server is not None
            else SUPPORTED_PROTOCOL_VERSIONS
        )
        legacy_supported = tuple(v for v in configured_versions if v in LEGACY_PROTOCOL_VERSIONS)
        latest_version = (
            legacy_supported[-1] if legacy_supported else (LATEST_LEGACY_PROTOCOL_VERSION)
        )
        if protocol_version in legacy_supported:
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
                # Same concise authority as modern server/discover.
                "instructions": SERVER_INSTRUCTIONS,
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
                self._cancelled_times[cancelled_id] = time.monotonic()
                while len(self._cancelled_requests) > max_cancelled:
                    oldest = self._cancelled_requests_order.popleft()
                    self._cancelled_requests.discard(oldest)
                    self._cancelled_times.pop(oldest, None)

    def _discard_cancellation_record(self, request_id: Any) -> None:
        """Remove any cancellation record for *request_id* (best effort)."""
        with self._cancelled_lock:
            if request_id in self._cancelled_requests or request_id in self._cancelled_times:
                self._cancelled_requests.discard(request_id)
                self._cancelled_times.pop(request_id, None)
                try:
                    self._cancelled_requests_order.remove(request_id)
                except ValueError:
                    pass

    def _discard_stale_cancellation(self, request_id: Any, started_at: float) -> None:
        """Drop a cancellation record that predates *started_at*.

        A late notifications/cancelled for an already-completed request
        must not silently cancel a future request that reuses the id.

        The comparison is ``<=`` (not ``<``) on purpose: the record is only
        consulted for requests dispatched after it was stored, so a record
        present at dispatch entry necessarily predates this request. A
        strict ``<`` misfires on platforms with coarse monotonic clocks
        (Windows granularity is ~15.6 ms), where the pre-request
        cancellation and the request start can share one tick and a
        genuinely stale record would falsely cancel the new request.
        """
        with self._cancelled_lock:
            recorded_at = self._cancelled_times.get(request_id)
            if recorded_at is not None and recorded_at <= started_at:
                self._cancelled_requests.discard(request_id)
                del self._cancelled_times[request_id]
                try:
                    self._cancelled_requests_order.remove(request_id)
                except ValueError:
                    pass


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

        Dual-era dispatch: requests carrying a modern (2026-07-28)
        ``params._meta`` envelope are served statelessly without touching
        any session, so one server process serves both eras concurrently
        with no cross-era state leakage.  All other requests follow the
        legacy ``McpSession`` lifecycle.

        Validation mirrors the module-level handle_request shim: JSON-RPC
        version, id type/length, and method presence/type are enforced here
        so direct library calls get the same protocol conformance as the
        stdin loop.
        """
        if self._closed:
            # Notifications never receive responses; otherwise echo the id
            # when it is detectable so clients can correlate the error.
            if isinstance(request, dict):
                if "id" not in request:
                    return None
                return _invalid_request(request.get("id"), "Server is closed")
            return _invalid_request(None, "Server is closed")

        if not isinstance(request, dict):
            return _invalid_request(None, "Invalid Request: expected JSON object")

        # Validate JSON-RPC version.
        jsonrpc_version = request.get("jsonrpc")
        if jsonrpc_version != "2.0":
            return _invalid_request(
                request.get("id"),
                f"Invalid Request: jsonrpc must be '2.0', got '{jsonrpc_version}'",
            )

        # Validate request ID type and length using server config.
        # Shares one validator with the module-level handle_request so
        # both paths agree (reject bool, accept str/int/float/null).
        request_id = request.get("id")
        # Explicit null id on a request is rejected: requests must have a
        # non-null string or integer id.  Notifications omit "id" entirely.
        if "id" in request and request_id is None and "method" in request:
            return _invalid_request(
                None,
                "Invalid Request: 'id' must be a string or integer, not null",
            )
        if request_id is not None:
            id_error = _invalid_jsonrpc_id_reason(request_id)
            if id_error is not None:
                return _invalid_request(None, f"Invalid Request: {id_error}")
            id_str = str(request_id)
            if len(id_str) > self._config.max_request_id_length:
                return _invalid_request(
                    None,
                    f"Invalid Request: 'id' exceeds maximum length of {self._config.max_request_id_length}",
                )

        # Missing or non-string method is an Invalid Request (-32600),
        # not a method-not-found dispatch failure.
        if "method" not in request:
            return _invalid_request(request_id, "Invalid Request: missing 'method'")
        if not isinstance(request["method"], str):
            return _invalid_request(
                request.get("id"),
                "Invalid Request: 'method' must be a string",
            )

        # Era classification precedes all session logic: modern requests
        # are server-owned and must not mutate session state, while
        # malformed modern traffic receives a deterministic protocol
        # error instead of falling into the legacy state machine.
        # Modern notifications produce no response on either path.
        era, modern_error, modern_ctx = _classify_request_era(
            request, self._config.supported_protocol_versions
        )
        if era == "modern" or modern_error is not None:
            if "id" not in request:
                return None
            if modern_error is not None:
                return modern_error
            assert modern_ctx is not None
            return _handle_modern_request(request, self, modern_ctx)

        if session is None:
            session = self.create_session()
            auto_created = True
        elif session._closed:
            # Notifications never receive responses, even on closed sessions.
            if "id" not in request:
                return None
            return _invalid_request(request_id, "Session is closed")
        elif session._owner_ref is None:
            return _invalid_request(request_id, "Session is not bound to a server")
        else:
            auto_created = False
            owner = session._owner_ref()
            if owner is None:
                return _invalid_request(request_id, "Session owner is unavailable")
            if owner is not self:
                return _invalid_request(request_id, "Session belongs to another server")

        # Capture one immutable context before dispatch.
        context = self._runtime_context
        if auto_created:
            try:
                return session.handle_message(request, server=self, context=context)
            finally:
                session.close()
        return session.handle_message(request, server=self, context=context)

    def close(self) -> None:
        """Shut down the server, releasing workers and cleaning up."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
        self._executor.close()
        _cleanup_orphaned_processes()
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
            "orphan_count": _tracked_orphan_count(),
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
        if param.kind in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue
        if param.default is inspect.Parameter.empty and name not in arguments:
            return f"Missing required argument: {name}"

    return None


def _run_handler_in_thread(
    handler: Any,
    arguments: dict[str, Any],
    evaluator: _evaluator.Evaluator | None = None,
    timeout_seconds: float | None = None,
) -> Any:
    """Run a tool handler on a pool thread, returning the result or raising.

    If an evaluator is provided, sets the ``_current_evaluator`` ContextVar
    so that ``evaluate_raw`` and ``evaluate_with_timeout`` use it instead of
    the module-level default. This binds MCP math execution to the
    server-owned evaluator without modifying handler signatures.
    """
    if timeout_seconds is not None and handler is TOOL_HANDLERS.get("math_eval"):
        arguments = {**arguments, "timeout": timeout_seconds}
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
    value: Any,
    prop: Mapping[str, Any],
    path: str,
    max_depth: int = 10,
    allow_additional_default: bool = False,
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

    When a schema omits ``additionalProperties``, *allow_additional_default*
    decides: inputs use ``False`` (strict), output payloads use ``True``
    (spec-default permissive — declared fields are still type-checked).
    An explicit ``additionalProperties`` in the schema always wins.
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
        sub_additional = prop.get("additionalProperties", allow_additional_default)

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
                        sub_val,
                        sub_props[sub_key],
                        f"{path}.{sub_key}",
                        max_depth=max_depth - 1,
                        allow_additional_default=allow_additional_default,
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
                    item,
                    items_schema,
                    f"{path}[{i}]",
                    max_depth=max_depth - 1,
                    allow_additional_default=allow_additional_default,
                )
                if err:
                    return err

    return None


@_dataclass(frozen=True)
class ToolWireResult:
    """Result-boundary mapping for one handler return value (Plan 039).

    Owned by the MCP protocol layer (not per-handler knowledge):

    - success ``{ok: true, result: X, ...}`` → text is the full
      compatibility envelope, ``structured_content`` is ``X``;
    - error ``{ok: false, ...}`` → text is the full error envelope,
      ``structured_content`` is ``None``.
    """

    text_envelope: dict[str, Any]
    structured_content: Any | None
    is_error: bool


def _split_tool_wire_result(handler_result: Any) -> ToolWireResult:
    """Map a handler return value to its wire representations.

    Both representations are built from the same in-memory object so
    the text envelope and ``structuredContent`` cannot drift apart.
    Non-dict or missing-``ok`` shapes are treated as errors (no success
    payload is advertised).
    """
    if isinstance(handler_result, dict) and handler_result.get("ok") is True:
        return ToolWireResult(
            text_envelope=handler_result,
            structured_content=handler_result.get("result"),
            is_error=False,
        )
    if isinstance(handler_result, dict):
        return ToolWireResult(
            text_envelope=handler_result,
            structured_content=None,
            is_error=True,
        )
    return ToolWireResult(
        text_envelope={
            "ok": False,
            "error_type": "internal_error",
            "error": "Tool returned a non-dict result",
            "hints": [],
            "tool": None,
            "warnings": [],
        },
        structured_content=None,
        is_error=True,
    )


def _validate_output_payload(
    name: str,
    payload: Any,
    schemas: Mapping[str, dict[str, Any]] | None = None,
) -> str | None:
    """Validate a success payload against its declared ``outputSchema``.

    Validates ``handler_result["result"]`` (the ``structuredContent``
    authority), not the outer compatibility envelope. Output schemas are
    descriptive: declared fields are type-checked and ``required`` is
    enforced, but undeclared extra fields are permitted (JSON Schema
    default) so intentionally partial schemas do not false-positive.
    Returns None if valid (or when no outputSchema is declared).
    """
    source = schemas if schemas is not None else TOOL_SCHEMAS
    schema = source.get(name, {}).get("outputSchema")
    if not schema:
        return None
    return _validate_value_against_schema(payload, schema, name, allow_additional_default=True)


def _is_object_rooted_output_schema(name: str, schemas: Any = None) -> bool:
    """Return True when *name* declares an object-rooted output schema.

    Legacy eras define structured tool output only for object roots, so
    this gates ``structuredContent`` emission on the legacy path. All 83
    current tools are object-rooted; non-object or missing schemas emit
    text-only results.
    """
    source = schemas if schemas is not None else TOOL_SCHEMAS
    try:
        schema = source.get(name, {}).get("outputSchema")
    except Exception:
        return False
    return isinstance(schema, (dict, Mapping)) and schema.get("type") == "object"


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


def _handle_list_tools(
    request: dict[str, Any],
    server: McpServer | None = None,
    modern: ModernRequestContext | None = None,
) -> dict[str, Any]:
    """Handle a tools/list MCP request with optional filtering.

    When *server* is provided, its config and registry are used instead
    of module-level globals, giving callers full state isolation.

    Tools are emitted in canonical sorted-name order so the catalog is
    stable across unrelated source reorderings.  When *modern* is
    provided (2026-07-28 era), the result also carries the required
    ``resultType``/cache-hint wire fields and the server-identity
    ``_meta`` stamp; legacy results keep their historical shape.
    """
    params = request.get("params", {})
    request_id = request.get("id")
    if not isinstance(params, dict):
        return _invalid_params(request_id, "Invalid params: expected object")

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
            if profile_filter is not None and profile_filter != server.config.profile:
                # Per-request profile overrides may narrow but never broaden
                # beyond the configured profile (least-privilege guard).
                configured_tools = set(server.registry.get_profile_tools(server.config.profile))
                requested_tools = set(server.registry.get_profile_tools(profile_filter))
                if not requested_tools <= configured_tools:
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": -32602,
                            "message": (
                                f"Profile '{profile_filter}' exceeds the tools "
                                f"available in the configured profile "
                                f"'{server.config.profile}'"
                            ),
                        },
                    }
            default_profile = (
                profile_filter if profile_filter is not None else server.config.profile
            )
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
    for name, schema in sorted(schemas_src.items()):
        if name not in profile_tools:
            continue

        if names_filter is not None:
            if name not in names_filter:
                continue

        if tier_filter is not None:
            # Plan 040: tier authority is TOOL_METADATA (catalog), not TOOL_SCHEMAS.
            if metadata_src.get(name, {}).get("tier") != tier_filter:
                continue

        if tags_filter is not None:
            tool_tags = set(metadata_src.get(name, {}).get("tags", []))
            if not all(tag in tool_tags for tag in tags_filter):
                continue

        meta = metadata_src.get(name, {})
        annotations = get_tool_annotations(name)
        if use_compact:
            # Plan 041: compact descriptions carry the authored selection
            # signal, not a truncation of the full description.
            selection_summary = meta.get("selection_summary")
            # thaw_owned: registry schemas are frozen (MappingProxyType);
            # compact_schema passes some values (e.g. items) through by
            # reference, so thaw before the entry reaches the JSON wire.
            entry = thaw_owned(
                compact_schema(
                    schema,
                    (
                        selection_summary
                        if isinstance(selection_summary, str) and selection_summary
                        else None
                    ),
                )
            )
            entry["name"] = name
            entry["category"] = meta.get("category")
            entry["llm_exposure"] = meta.get("llm_exposure")
            entry["cost"] = meta.get("cost")
            entry["annotations"] = annotations
        elif schema_detail == "normal":
            # See compact branch: thaw frozen registry values before wiring.
            entry = thaw_owned(normal_schema(schema))
            entry["name"] = name
            entry["tier"] = meta.get("tier")
            entry["tags"] = list(meta.get("tags", []))
            entry["category"] = meta.get("category")
            entry["llm_exposure"] = meta.get("llm_exposure")
            entry["cost"] = meta.get("cost")
            entry["annotations"] = annotations
        else:
            entry = {
                "name": name,
                "description": schema["description"],
                "inputSchema": thaw_owned(schema["inputSchema"]),
                "outputSchema": thaw_owned(schema.get("outputSchema")),
                "annotations": annotations,
                "tier": meta.get("tier"),
                "tags": list(meta.get("tags", [])),
                "deprecated": schema.get("deprecated", False),
                "category": meta.get("category"),
                "llm_exposure": meta.get("llm_exposure"),
                "cost": meta.get("cost"),
            }
        tools.append(entry)

    list_result: dict[str, Any] = {"tools": tools}
    if modern is not None:
        list_result = {
            "resultType": "complete",
            "tools": tools,
            "ttlMs": MODERN_CACHE_TTL_MS,
            "cacheScope": MODERN_CACHE_SCOPE,
        }
        list_result = _attach_modern_server_info(list_result)
    return {
        "jsonrpc": "2.0",
        "id": request.get("id"),
        "result": list_result,
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
        profiles_info = {}
        for name in available_profiles:
            profile_tools = server.registry.get_profile_tools(name)
            profiles_info[name] = {"tools": profile_tools, "tool_count": len(profile_tools)}
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


def _handle_discover(request: dict[str, Any], server: McpServer) -> dict[str, Any]:
    """Handle server/discover on the modern path (no session required).

    Discovery data comes from existing authorities: supported versions
    from the server config (defaulting to ``_protocol``), protocol-only
    capabilities (never runtime diagnostics), server identity via the
    result ``_meta`` stamp, and the shared ``SERVER_INSTRUCTIONS``
    authority.
    """
    result: dict[str, Any] = {
        "resultType": "complete",
        "supportedVersions": list(server.config.supported_protocol_versions),
        "capabilities": {"tools": {"listChanged": False}},
        "instructions": SERVER_INSTRUCTIONS,
        "ttlMs": MODERN_CACHE_TTL_MS,
        "cacheScope": MODERN_CACHE_SCOPE,
    }
    result = _attach_modern_server_info(result)
    return {"jsonrpc": "2.0", "id": request.get("id"), "result": result}


def _handle_call_tool_modern(
    request: dict[str, Any], server: McpServer, context: RuntimeContext | None = None
) -> dict[str, Any]:
    """Handle tools/call on the modern path using server-owned state only.

    Identical profile/handler admission to the legacy session path, but
    never consults legacy session cancellation sets or negotiated client
    state.  Only request-local metadata and immutable server state apply.
    """
    params = request.get("params", {})
    if not isinstance(params, dict):
        return _invalid_params(request.get("id"), "Invalid params: expected object")

    name = params.get("name", "")
    arguments = params.get("arguments", {})
    if not isinstance(name, str) or not name:
        return _invalid_params(request.get("id"), "Invalid params: missing tool name")
    if not isinstance(arguments, dict):
        return _invalid_params(request.get("id"), "Invalid arguments: expected object")

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
    response = server._executor.call_tool(
        name=name,
        arguments=arguments,
        request_id=request.get("id"),
        evaluator=evaluator,
        modern=True,
    )
    if isinstance(response.get("result"), dict):
        response["result"] = _attach_modern_server_info(response["result"])
    return response


def _handle_modern_request(
    request: dict[str, Any], server: McpServer, modern_ctx: ModernRequestContext
) -> dict[str, Any] | None:
    """Dispatch a validated modern request without touching session state.

    Captures one immutable ``RuntimeContext`` before tool admission so the
    request sees a single evaluator/config generation from validation
    through execution.  Only the methods in ``MODERN_METHODS`` are served;
    legacy lifecycle methods (``initialize``,
    ``notifications/initialized``), liveness ``ping`` (not defined for the
    modern era), and eggcalc-specific legacy methods are rejected as
    unknown on this path.
    """
    if "id" not in request:
        return None
    request_id = request.get("id")
    method = request.get("method", "")
    if method not in MODERN_METHODS:
        display = method[:100] + "..." if len(method) > 100 else method
        return _method_not_found(request_id, display)
    context = server._runtime_context
    if method == "server/discover":
        return _handle_discover(request, server)
    if method == "tools/list":
        return _handle_list_tools(request, server=server, modern=modern_ctx)
    return _handle_call_tool_modern(request, server, context)


_compat_server: McpServer | None = None
_compat_server_lock = threading.Lock()


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
        # Shared validator: bool is a subclass of int in Python, so exclude
        # it explicitly; floats are legal JSON-RPC (Number) ids.
        id_error = _invalid_jsonrpc_id_reason(request_id)
        if id_error is not None:
            return _invalid_request(
                None,
                f"Invalid Request: {id_error}",
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
        try:
            return compat.handle_request(request, session=compat_session)
        finally:
            compat_session.close()

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
    rate = config.max_requests_per_second
    rate_capacity = max(1.0, rate)
    rate_tokens = rate_capacity
    last_refill = time.monotonic()
    try:
        for line in sys.stdin:
            try:
                line = line.strip()
                if not line:
                    continue

                response: Any = None
                if len(line.encode('utf-8')) > config.max_request_bytes:
                    response = _parse_error(
                        None,
                        f"Request exceeds maximum size of {config.max_request_bytes} bytes",
                    )
                    print(json.dumps(response), flush=True)
                    continue

                try:
                    request = json.loads(line)
                except json.JSONDecodeError:
                    response = _parse_error(None, "Parse error: invalid JSON")
                    print(json.dumps(response), flush=True)
                    continue

                now = time.monotonic()
                rate_tokens = min(rate_capacity, rate_tokens + (now - last_refill) * rate)
                last_refill = now
                batch_size = len(request) if isinstance(request, list) else 1
                if rate_tokens < batch_size:
                    response = _invalid_request_error(
                        request.get("id") if isinstance(request, dict) else None,
                        f"Rate limit exceeded: max {config.max_requests_per_second} requests per second",
                    )
                    print(json.dumps(response), flush=True)
                    continue

                rate_tokens -= batch_size

                if isinstance(request, list):
                    if not request:
                        response = _invalid_request_error(None, "Invalid Request: empty batch")
                    else:
                        # Notifications (entries without "id") must never receive a response.
                        response = [
                            _invalid_request_error(
                                entry.get("id"), "Batch requests are not supported"
                            )
                            for entry in request
                            if isinstance(entry, dict) and "id" in entry
                        ]
                    if response:
                        print(json.dumps(response), flush=True)
                    continue

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
