"""Tests for runtime capability detection and metadata consistency."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from eggcalc.capabilities import capability_summary, detect_capabilities


class TestRuntimeCapabilitiesImmutability:
    def test_frozen_dataclass(self) -> None:
        caps = detect_capabilities()
        with pytest.raises(AttributeError):
            caps.platform = "test"  # type: ignore[misc]

    def test_cannot_add_attribute(self) -> None:
        caps = detect_capabilities()
        with pytest.raises(AttributeError):
            caps.new_field = True  # type: ignore[attr-defined]


class TestCapabilitySerialization:
    def test_to_dict_returns_dict(self) -> None:
        caps = detect_capabilities()
        d = caps.to_dict()
        assert isinstance(d, dict)

    def test_to_dict_contains_expected_keys(self) -> None:
        caps = detect_capabilities()
        d = caps.to_dict()
        expected_keys = {
            "python_version",
            "platform",
            "implementation",
            "has_tomllib",
            "has_math_cbrt",
            "supports_fork",
            "supports_spawn",
            "supports_posix_paths",
            "supports_windows_paths",
            "eggcalc_version",
            "supported_protocol_versions",
            "multiprocessing_start_method",
            "mode",
        }
        assert expected_keys == set(d.keys())

    def test_to_dict_python_version_is_list(self) -> None:
        caps = detect_capabilities()
        d = caps.to_dict()
        assert isinstance(d["python_version"], list)
        assert len(d["python_version"]) == 3

    def test_to_json_is_valid_json(self) -> None:
        caps = detect_capabilities()
        j = caps.to_json()
        parsed = json.loads(j)
        assert isinstance(parsed, dict)

    def test_to_json_with_indent(self) -> None:
        caps = detect_capabilities()
        j = caps.to_json(indent=2)
        assert "\n" in j
        parsed = json.loads(j)
        assert "python_version" in parsed


class TestCapabilityValues:
    def test_has_tomllib(self) -> None:
        caps = detect_capabilities()
        assert caps.has_tomllib is True

    def test_has_math_cbrt(self) -> None:
        caps = detect_capabilities()
        assert caps.has_math_cbrt is True

    def test_python_version_matches_sys(self) -> None:
        caps = detect_capabilities()
        assert caps.python_version == (
            sys.version_info.major,
            sys.version_info.minor,
            sys.version_info.micro,
        )

    def test_platform_matches_sys(self) -> None:
        caps = detect_capabilities()
        assert caps.platform == sys.platform

    def test_supports_spawn(self) -> None:
        caps = detect_capabilities()
        assert caps.supports_spawn is True

    def test_supports_posix_paths_on_non_windows(self) -> None:
        if sys.platform == "win32":
            pytest.skip("POSIX path test not applicable on Windows")
        caps = detect_capabilities()
        assert caps.supports_posix_paths is True

    def test_supports_windows_paths_on_windows(self) -> None:
        if sys.platform != "win32":
            pytest.skip("Windows path test only on Windows")
        caps = detect_capabilities()
        assert caps.supports_windows_paths is True

    def test_eggcalc_version_is_string(self) -> None:
        caps = detect_capabilities()
        assert isinstance(caps.eggcalc_version, str)
        assert len(caps.eggcalc_version) > 0

    def test_supported_protocol_versions_is_tuple(self) -> None:
        caps = detect_capabilities()
        assert isinstance(caps.supported_protocol_versions, tuple)
        assert len(caps.supported_protocol_versions) > 0
        assert all(isinstance(v, str) for v in caps.supported_protocol_versions)

    def test_multiprocessing_start_method_is_string(self) -> None:
        caps = detect_capabilities()
        assert isinstance(caps.multiprocessing_start_method, str)

    def test_mode_is_package_or_single_file(self) -> None:
        caps = detect_capabilities()
        assert caps.mode in ("package", "single-file")


class TestCapabilitySummary:
    def test_summary_returns_string(self) -> None:
        s = capability_summary()
        assert isinstance(s, str)

    def test_summary_contains_python_version(self) -> None:
        s = capability_summary()
        assert "Python:" in s

    def test_summary_contains_platform(self) -> None:
        s = capability_summary()
        assert "Platform:" in s


class TestMetadataConsistency:
    def test_requires_python_matches_pyproject(self) -> None:
        """Verify pyproject.toml requires-python is >= 3.11."""
        pyproject = Path(__file__).parent.parent / "pyproject.toml"
        content = pyproject.read_text()
        assert 'requires-python = ">=3.11"' in content

    def test_no_310_classifier(self) -> None:
        """Verify pyproject.toml does not include Python 3.10 classifier."""
        pyproject = Path(__file__).parent.parent / "pyproject.toml"
        content = pyproject.read_text()
        assert "Programming Language :: Python :: 3.10" not in content

    def test_current_python_meets_minimum(self) -> None:
        """Verify the running Python meets the minimum version."""
        assert sys.version_info >= (
            3,
            11,
        ), f"Running Python {sys.version_info} does not meet minimum 3.11"


class TestCapabilitiesCLI:
    """Verify --capabilities flag works in CLI."""

    def test_capabilities_module_cli(self) -> None:
        """python -m eggcalc --capabilities should output valid JSON."""
        result = subprocess.run(
            [sys.executable, "-m", "eggcalc", "--capabilities"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        data = json.loads(result.stdout)
        assert "python_version" in data
        assert "platform" in data
        assert isinstance(data["python_version"], list)

    def test_capabilities_single_file_cli(self) -> None:
        """eggcalc.py --capabilities should output valid JSON."""
        single_file = Path(__file__).parent.parent / "eggcalc.py"
        if not single_file.exists():
            pytest.skip("eggcalc.py not found (run build_single.py)")
        result = subprocess.run(
            [sys.executable, str(single_file), "--capabilities"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        data = json.loads(result.stdout)
        assert "python_version" in data
        assert "has_tomllib" in data

    def test_capabilities_matches_detect(self) -> None:
        """CLI --capabilities output should match detect_capabilities()."""
        result = subprocess.run(
            [sys.executable, "-m", "eggcalc", "--capabilities"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        cli_caps = json.loads(result.stdout)
        detected = detect_capabilities()
        assert cli_caps["python_version"] == list(detected.python_version)
        assert cli_caps["platform"] == detected.platform
        assert cli_caps["has_tomllib"] == detected.has_tomllib


class TestMultiprocessingCapabilities:
    """Verify multiprocessing capability detection across platforms."""

    def test_fork_matches_os_module(self) -> None:
        caps = detect_capabilities()
        assert caps.supports_fork == hasattr(os, "fork")

    def test_spawn_always_true(self) -> None:
        caps = detect_capabilities()
        assert caps.supports_spawn is True

    def test_posix_windows_exclusivity(self) -> None:
        caps = detect_capabilities()
        if sys.platform == "win32":
            assert caps.supports_posix_paths is False
            assert caps.supports_windows_paths is True
        else:
            assert caps.supports_posix_paths is True


class TestTimeoutReliability:
    """Verify timeout behavior works reliably across platforms."""

    def test_evaluate_with_timeout_succeeds(self) -> None:
        from eggcalc import evaluate_with_timeout

        result = evaluate_with_timeout("2+2", timeout=5.0)
        val = result.value if hasattr(result, "value") else result
        assert val == 4

    def test_evaluate_with_timeout_raises_on_slow(self) -> None:
        import time

        from eggcalc import TimeoutError, evaluate_with_timeout

        start = time.monotonic()
        try:
            evaluate_with_timeout("0+0+0+0+0", timeout=0.5)
        except TimeoutError:
            pass
        elapsed = time.monotonic() - start
        assert elapsed < 5.0, f"Timeout took {elapsed:.2f}s"


class TestPackageSingleFileParity:
    """Verify package and single-file have matching tool inventories."""

    def test_single_file_has_same_handlers(self) -> None:
        """Single-file TOOL_HANDLERS should match package TOOL_HANDLERS."""
        single_file = Path(__file__).parent.parent / "eggcalc.py"
        if not single_file.exists():
            pytest.skip("eggcalc.py not found (run build_single.py)")

        from eggcalc.mcp.server import TOOL_HANDLERS

        package_tools = sorted(TOOL_HANDLERS.keys())

        result = subprocess.run(
            [
                sys.executable,
                "-c",
                f"import sys; sys.path.insert(0, '{single_file.parent}'); "
                "ns = {}; exec(open(sys.argv[1]).read(), ns); "
                "print('\\n'.join(sorted(ns['TOOL_HANDLERS'].keys())))",
                str(single_file),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"Failed to load single-file: {result.stderr}"
        single_tools = sorted(
            line.strip() for line in result.stdout.strip().split("\n") if line.strip()
        )
        assert single_tools == package_tools, (
            f"Single-file tools differ from package.\n"
            f"  Missing: {set(package_tools) - set(single_tools)}\n"
            f"  Extra:   {set(single_tools) - set(package_tools)}"
        )

    def test_single_file_has_same_schemas(self) -> None:
        """Single-file TOOL_SCHEMAS should match package TOOL_SCHEMAS."""
        single_file = Path(__file__).parent.parent / "eggcalc.py"
        if not single_file.exists():
            pytest.skip("eggcalc.py not found (run build_single.py)")

        from eggcalc.mcp.schemas import TOOL_SCHEMAS

        package_schemas = sorted(TOOL_SCHEMAS.keys())

        result = subprocess.run(
            [
                sys.executable,
                "-c",
                f"import sys; sys.path.insert(0, '{single_file.parent}'); "
                "ns = {}; exec(open(sys.argv[1]).read(), ns); "
                "print('\\n'.join(sorted(ns['TOOL_SCHEMAS'].keys())))",
                str(single_file),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"Failed to load single-file: {result.stderr}"
        single_schemas = sorted(
            line.strip() for line in result.stdout.strip().split("\n") if line.strip()
        )
        assert single_schemas == package_schemas, (
            f"Single-file schemas differ from package.\n"
            f"  Missing: {set(package_schemas) - set(single_schemas)}\n"
            f"  Extra:   {set(single_schemas) - set(package_schemas)}"
        )
