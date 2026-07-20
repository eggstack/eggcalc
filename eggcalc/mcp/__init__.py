"""
MCP server for eggcalc.

Provides stdio-based MCP server for text, Unicode, and measurement tools.
"""

from __future__ import annotations

from . import tools
from .schemas import TOOL_SCHEMAS
from .server import (
    LATEST_SUPPORTED_PROTOCOL_VERSION,
    SUPPORTED_PROTOCOL_VERSIONS,
    ConfigManager,
    ConfigSnapshot,
    McpServer,
    McpServerConfig,
    McpSession,
    McpSessionState,
    ToolExecutor,
    ToolRegistry,
    handle_request,
    main,
)

__all__ = [
    "main",
    "handle_request",
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
]
