"""Runtime capability detection for eggcalc.

Provides a frozen, immutable snapshot of platform capabilities that
MCP tool registration, CLI diagnostics, and release-surface checks
can depend on.
"""

from __future__ import annotations

import json
import multiprocessing
import os
import sys
from dataclasses import dataclass

from ._protocol import SUPPORTED_PROTOCOL_VERSIONS as _SUPPORTED_PROTOCOL_VERSIONS


@dataclass(frozen=True)
class RuntimeCapabilities:
    """Immutable snapshot of the current runtime environment."""

    python_version: tuple[int, int, int]
    platform: str
    implementation: str
    has_tomllib: bool
    has_math_cbrt: bool
    supports_fork: bool
    supports_spawn: bool
    supports_posix_paths: bool
    supports_windows_paths: bool
    eggcalc_version: str
    supported_protocol_versions: tuple[str, ...]
    multiprocessing_start_method: str
    mode: str

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable dictionary of capabilities."""
        return {
            "python_version": list(self.python_version),
            "platform": self.platform,
            "implementation": self.implementation,
            "has_tomllib": self.has_tomllib,
            "has_math_cbrt": self.has_math_cbrt,
            "supports_fork": self.supports_fork,
            "supports_spawn": self.supports_spawn,
            "supports_posix_paths": self.supports_posix_paths,
            "supports_windows_paths": self.supports_windows_paths,
            "eggcalc_version": self.eggcalc_version,
            "supported_protocol_versions": list(self.supported_protocol_versions),
            "multiprocessing_start_method": self.multiprocessing_start_method,
            "mode": self.mode,
        }

    def to_json(self, *, indent: int | None = None) -> str:
        """Return a JSON string of capabilities."""
        return json.dumps(self.to_dict(), indent=indent)


def _detect_mode() -> str:
    """Detect whether running as package or single-file distribution."""
    main_mod = sys.modules.get("__main__")
    main_file = getattr(main_mod, "__file__", None)
    if main_file is None:
        return "package"
    if os.path.basename(main_file) == "eggcalc.py":
        return "single-file"
    return "package"


def detect_capabilities() -> RuntimeCapabilities:
    """Detect and return the current runtime capabilities.

    This function probes observable runtime facts and returns an
    immutable snapshot. It has no side effects and does not read
    user configuration.
    """
    ver = sys.version_info
    plat = sys.platform
    impl = sys.implementation.name

    has_tomllib = ver >= (3, 11)
    has_math_cbrt = ver >= (3, 11)
    supports_fork = hasattr(os, "fork")
    supports_spawn = True
    supports_posix_paths = plat != "win32"
    supports_windows_paths = plat == "win32" or "msys" in plat or "cygwin" in plat

    try:
        from importlib.metadata import version as _pkg_version

        eggcalc_version = _pkg_version("eggcalc")
    except Exception:
        eggcalc_version = "unknown"

    try:
        start_method = multiprocessing.get_start_method()
    except RuntimeError:
        start_method = "unknown"

    return RuntimeCapabilities(
        python_version=(ver.major, ver.minor, ver.micro),
        platform=plat,
        implementation=impl,
        has_tomllib=has_tomllib,
        has_math_cbrt=has_math_cbrt,
        supports_fork=supports_fork,
        supports_spawn=supports_spawn,
        supports_posix_paths=supports_posix_paths,
        supports_windows_paths=supports_windows_paths,
        eggcalc_version=eggcalc_version,
        supported_protocol_versions=_SUPPORTED_PROTOCOL_VERSIONS,
        multiprocessing_start_method=start_method,
        mode=_detect_mode(),
    )


def capability_summary() -> str:
    """Return a human-readable summary of runtime capabilities."""
    caps = detect_capabilities()
    lines = [
        "eggcalc runtime capabilities",
        f"  Version: {caps.eggcalc_version}",
        f"  Python: {'.'.join(str(v) for v in caps.python_version)} ({caps.implementation})",
        f"  Platform: {caps.platform}",
        f"  Mode: {caps.mode}",
        f"  tomllib: {'yes' if caps.has_tomllib else 'no'}",
        f"  math.cbrt: {'yes' if caps.has_math_cbrt else 'no'}",
        f"  fork: {'yes' if caps.supports_fork else 'no'}",
        f"  spawn: {'yes' if caps.supports_spawn else 'no'}",
        f"  POSIX paths: {'yes' if caps.supports_posix_paths else 'no'}",
        f"  Windows paths: {'yes' if caps.supports_windows_paths else 'no'}",
        f"  Protocol versions: {', '.join(caps.supported_protocol_versions)}",
        f"  Multiprocessing start method: {caps.multiprocessing_start_method}",
    ]
    return "\n".join(lines)
