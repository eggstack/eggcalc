"""
MCP server for eggcalc.

Provides stdio-based MCP server for text, Unicode, and measurement tools.
"""

from __future__ import annotations

from eggcalc._protocol import (
    LATEST_SUPPORTED_PROTOCOL_VERSION,
    SUPPORTED_PROTOCOL_VERSIONS,
)

from . import tools
from .schemas import TOOL_SCHEMAS
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
    RuntimeContext,
    ToolExecutor,
    ToolRegistry,
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
    "tools",
    "McpSession",
    "McpSessionState",
    "SUPPORTED_PROTOCOL_VERSIONS",
    "LATEST_SUPPORTED_PROTOCOL_VERSION",
    "McpServerConfig",
    "McpServer",
    "ToolRegistry",
    "ToolExecutor",
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
