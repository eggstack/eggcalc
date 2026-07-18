"""Tests for runtime capability detection and metadata consistency."""

from __future__ import annotations

import json
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
