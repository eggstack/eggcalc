"""Tests for path_compare tool."""

from __future__ import annotations

from eggcalc.exact.path_tools import path_compare


class TestPathCompareBasic:
    def test_identical_paths(self):
        result = path_compare("src/main.rs", "src/main.rs")
        assert result["equal"] is True
        assert result["left_normalized"] == result["right_normalized"]
        assert result["differences"] == []

    def test_different_paths(self):
        result = path_compare("src/main.rs", "src/lib.rs")
        assert result["equal"] is False
        assert len(result["differences"]) > 0

    def test_trailing_slash_normalization(self):
        result = path_compare("src/main.rs/", "src/main.rs")
        assert result["equal"] is True

    def test_double_slash_collapse(self):
        result = path_compare("src//main.rs", "src/main.rs")
        assert result["equal"] is True

    def test_dot_segment_collapse(self):
        result = path_compare("src/./main.rs", "src/main.rs")
        assert result["equal"] is True

    def test_dotdot_collapse(self):
        result = path_compare("src/foo/../main.rs", "src/main.rs")
        assert result["equal"] is True

    def test_dotdot_not_collapsed(self):
        result = path_compare("src/foo/../main.rs", "src/main.rs", collapse_dot_segments=False)
        assert result["equal"] is False


class TestPathCompareCaseInsensitive:
    def test_case_sensitive_default(self):
        result = path_compare("Src/Main.rs", "src/main.rs")
        assert result["equal"] is False

    def test_case_insensitive(self):
        result = path_compare("Src/Main.rs", "src/main.rs", case_sensitive=False)
        assert result["equal"] is True

    def test_case_insensitive_finding(self):
        result = path_compare("A", "a", case_sensitive=False)
        assert "Case-insensitive comparison used" in result["findings"]


class TestPathCompareSeparators:
    def test_posix_slash_normalization(self):
        result = path_compare("src\\main.rs", "src/main.rs", platform="posix")
        assert result["equal"] is True

    def test_windows_backslash_preserved(self):
        result = path_compare("src/main.rs", "src\\main.rs", platform="windows")
        assert result["equal"] is True

    def test_no_separator_normalization(self):
        result = path_compare(
            "src\\main.rs", "src/main.rs", platform="posix", normalize_separators=False
        )
        assert result["equal"] is False


class TestPathComparePlatform:
    def test_windows_unc_path(self):
        result = path_compare(
            "\\\\server\\share\\file.txt", "\\\\server\\share\\file.txt", platform="windows"
        )
        assert result["equal"] is True

    def test_invalid_platform_defaults_posix(self):
        result = path_compare("a/b", "a/b", platform="invalid")
        assert result["equal"] is True


class TestPathCompareFindings:
    def test_findings_populated(self):
        result = path_compare("a/b", "a/b", case_sensitive=False)
        assert len(result["findings"]) > 0

    def test_no_case_finding_default(self):
        result = path_compare("a/b", "a/b")
        assert not any("Case-insensitive" in f for f in result["findings"])
