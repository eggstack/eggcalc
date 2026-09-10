"""
MCP server for eggcalc.

Provides stdio-based MCP server for text, Unicode, and measurement tools.
"""

from __future__ import annotations

from eggcalc._protocol import (
    LATEST_SUPPORTED_PROTOCOL_VERSION,
    LEGACY_PROTOCOL_VERSIONS,
    MODERN_PROTOCOL_VERSIONS,
    SUPPORTED_PROTOCOL_VERSIONS,
)

from . import tools
from .schemas import (
    DEFAULT_TOOL_ANNOTATIONS,
    TOOL_ANNOTATIONS,
    TOOL_SCHEMAS,
    ToolAnnotations,
    get_tool_annotations,
)
from .server import (
    ConfigCandidate,
    ConfigError,
    ConfigManager,
    ConfigSnapshot,
    EvaluationPolicy,
    McpServer,
    McpServerConfig,
    McpSession,
    McpSessionState,
    ModernRequestContext,
    RuntimeContext,
    ToolExecutor,
    ToolRegistry,
    ToolWireResult,
    close_compatibility_server,
    freeze_owned,
    handle_request,
    main,
    parse_config_snapshot,
    thaw_owned,
)

__all__ = [
    "main",
    "handle_request",
    "close_compatibility_server",
    "TOOL_SCHEMAS",
    "TOOL_ANNOTATIONS",
    "DEFAULT_TOOL_ANNOTATIONS",
    "ToolAnnotations",
    "get_tool_annotations",
    "tools",
    "McpSession",
    "McpSessionState",
    "ModernRequestContext",
    "SUPPORTED_PROTOCOL_VERSIONS",
    "LEGACY_PROTOCOL_VERSIONS",
    "MODERN_PROTOCOL_VERSIONS",
    "LATEST_SUPPORTED_PROTOCOL_VERSION",
    "McpServerConfig",
    "McpServer",
    "ToolRegistry",
    "ToolExecutor",
    "ToolWireResult",
    "ConfigSnapshot",
    "ConfigManager",
    "ConfigError",
    "parse_config_snapshot",
    "EvaluationPolicy",
    "ConfigCandidate",
    "RuntimeContext",
    "freeze_owned",
    "thaw_owned",
]
