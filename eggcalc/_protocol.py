"""Single source of truth for MCP protocol versions.

Imported by both ``eggcalc.capabilities`` and ``eggcalc.mcp.server`` to
avoid duplication.  No other eggcalc modules should define protocol
version constants independently.
"""

from __future__ import annotations

SUPPORTED_PROTOCOL_VERSIONS: tuple[str, ...] = ("2024-11-05", "2025-11-25")
LATEST_SUPPORTED_PROTOCOL_VERSION: str = SUPPORTED_PROTOCOL_VERSIONS[-1]
