"""Single source of truth for MCP protocol versions and eras.

Imported by both ``eggcalc.capabilities`` and ``eggcalc.mcp.server`` to
avoid duplication.  No other eggcalc modules should define protocol
version constants independently.

The finalized ``2026-07-28`` revision starts the stateless *modern* era
(no ``initialize`` handshake, per-request ``_meta`` envelope,
``server/discover`` bootstrap).  ``2024-11-05`` and ``2025-11-25`` form
the stateful *legacy* era (``initialize`` -> ``notifications/initialized``
-> READY session).  Version -> era mapping has exactly one authority:
:func:`protocol_era`.
"""

from __future__ import annotations

LEGACY_PROTOCOL_VERSIONS: tuple[str, ...] = ("2024-11-05", "2025-11-25")
MODERN_PROTOCOL_VERSIONS: tuple[str, ...] = ("2026-07-28",)
SUPPORTED_PROTOCOL_VERSIONS: tuple[str, ...] = LEGACY_PROTOCOL_VERSIONS + MODERN_PROTOCOL_VERSIONS
LATEST_SUPPORTED_PROTOCOL_VERSION: str = SUPPORTED_PROTOCOL_VERSIONS[-1]
LATEST_LEGACY_PROTOCOL_VERSION: str = LEGACY_PROTOCOL_VERSIONS[-1]

# Reserved per-request ``params._meta`` keys (SEP-2575) and the per-result
# ``result._meta`` server-identity key (spec PR #3002).  The
# ``io.modelcontextprotocol/`` prefix is reserved by MCP; eggcalc must not
# invent adjacent keys under it.
PROTOCOL_VERSION_META_KEY = "io.modelcontextprotocol/protocolVersion"
CLIENT_INFO_META_KEY = "io.modelcontextprotocol/clientInfo"
CLIENT_CAPABILITIES_META_KEY = "io.modelcontextprotocol/clientCapabilities"
LOG_LEVEL_META_KEY = "io.modelcontextprotocol/logLevel"
SERVER_INFO_META_KEY = "io.modelcontextprotocol/serverInfo"

# Modern-era wire constants (SEP-2549 cache hints).  Conservative
# ``ttlMs = 0`` / ``cacheScope = "private"`` is the centralized cache
# policy (Plan 039): a nonzero catalog TTL would require proving registry
# immutability plus profile/detail selection as cache keys across
# compatibility-server invalidation, which is not established — so the
# conformance floor is also the final policy.
MODERN_CACHE_TTL_MS = 0
MODERN_CACHE_SCOPE = "private"

# Methods eggcalc serves in the modern era.  Legacy-only lifecycle and
# eggcalc-specific methods are deliberately absent: ``initialize`` /
# ``notifications/initialized`` belong to the handshake era, ``ping`` is
# not defined for the modern era, and ``profiles/list`` is an
# eggcalc-specific extension served to legacy clients only.
MODERN_METHODS: frozenset[str] = frozenset({"server/discover", "tools/list", "tools/call"})


def protocol_era(version: object) -> str | None:
    """Return ``"legacy"`` or ``"modern"`` for a protocol version string.

    Returns ``None`` for unknown versions (including non-strings).
    This is the sole version -> era authority; callers must not
    reimplement the mapping with inline string comparisons.
    """
    if not isinstance(version, str):
        return None
    if version in LEGACY_PROTOCOL_VERSIONS:
        return "legacy"
    if version in MODERN_PROTOCOL_VERSIONS:
        return "modern"
    return None


def is_legacy_version(version: object) -> bool:
    """Return True when *version* names a supported legacy revision."""
    return protocol_era(version) == "legacy"


def is_modern_version(version: object) -> bool:
    """Return True when *version* names a supported modern revision."""
    return protocol_era(version) == "modern"
