"""Tests for Windows/UNC path normalization fixes."""

from __future__ import annotations

from eggcalc.exact.path_tools import path_compare, path_normalize, path_scope_check


class TestDriveLetterAbsolute:
    def test_drive_backslash_parent_collapse(self):
        result = path_normalize("C:\\foo\\..\\bar", "windows")
        assert result["normalized"] == "C:\\bar"
        assert result["is_absolute"] is True

    def test_drive_forward_slash_parent_collapse(self):
        result = path_normalize("C:/foo/../bar", "windows")
        assert result["normalized"] == "C:\\bar"
        assert result["is_absolute"] is True

    def test_drive_root_only(self):
        result = path_normalize("C:\\", "windows")
        assert result["normalized"] == "C:\\"
        assert result["is_absolute"] is True

    def test_drive_root_forward_slash(self):
        result = path_normalize("C:/", "windows")
        assert result["normalized"] == "C:\\"
        assert result["is_absolute"] is True

    def test_drive_no_separator_is_relative(self):
        result = path_normalize("C:foo", "windows")
        assert result["normalized"] == "C:foo"
        assert result["is_absolute"] is False

    def test_drive_relative_with_components(self):
        result = path_normalize("C:foo\\bar", "windows")
        assert result["normalized"] == "C:foo\\bar"
        assert result["is_absolute"] is False

    def test_drive_absolute_single_component(self):
        result = path_normalize("C:\\foo", "windows")
        assert result["normalized"] == "C:\\foo"
        assert result["is_absolute"] is True

    def test_drive_absolute_deep_parent_collapse(self):
        result = path_normalize("C:\\a\\b\\c\\..\\..\\d", "windows")
        assert result["normalized"] == "C:\\a\\d"
        assert result["is_absolute"] is True


class TestUNCAbsolute:
    def test_unc_server_share_dir_parent(self):
        result = path_normalize("\\\\server\\share\\dir\\..\\file", "windows")
        assert result["normalized"] == "\\\\server\\share\\file"
        assert result["is_absolute"] is True

    def test_unc_forward_slash_mode(self):
        result = path_normalize("//server/share/dir/../file", "windows")
        assert result["normalized"] == "\\\\server\\share\\file"
        assert result["is_absolute"] is True

    def test_unc_root_only(self):
        result = path_normalize("\\\\server\\share", "windows")
        assert result["normalized"] == "\\\\server\\share"
        assert result["is_absolute"] is True

    def test_unc_deep_traversal(self):
        result = path_normalize("\\\\server\\share\\a\\b\\..\\c", "windows")
        assert result["normalized"] == "\\\\server\\share\\a\\c"
        assert result["is_absolute"] is True

    def test_unc_dotdot_cannot_escape_root(self):
        result = path_normalize("\\\\server\\share\\..", "windows")
        assert result["normalized"] == "\\\\server\\share"
        assert result["is_absolute"] is True

    def test_unc_double_dotdot_cannot_escape(self):
        result = path_normalize("\\\\server\\share\\..\\..", "windows")
        assert result["normalized"] == "\\\\server\\share"
        assert result["is_absolute"] is True

    def test_unc_arbitrary_server_share_names(self):
        result = path_normalize("\\\\myserver\\myshare\\file", "windows")
        assert result["normalized"] == "\\\\myserver\\myshare\\file"
        assert result["is_absolute"] is True

    def test_unc_trailing_separator_preserved(self):
        result = path_normalize("\\\\server\\share\\", "windows", preserve_trailing_separator=True)
        assert result["normalized"] == "\\\\server\\share\\"
        assert result["is_absolute"] is True

    def test_unc_empty_after_collapse(self):
        result = path_normalize("\\\\server\\share\\dir\\..", "windows")
        assert result["normalized"] == "\\\\server\\share"
        assert result["is_absolute"] is True


class TestRelativePaths:
    def test_relative_parent_collapse(self):
        result = path_normalize("foo\\..\\bar", "windows")
        assert result["normalized"] == "bar"
        assert result["is_absolute"] is False

    def test_relative_posix_forward_slash(self):
        result = path_normalize("foo/../bar", "posix")
        assert result["normalized"] == "bar"
        assert result["is_absolute"] is False

    def test_excess_leading_dotdot_preserved(self):
        result = path_normalize("..\\..\\x", "windows")
        assert result["normalized"] == "..\\..\\x"
        assert result["is_absolute"] is False

    def test_relative_dotdot_at_start(self):
        result = path_normalize("..\\bar", "windows")
        assert result["normalized"] == "..\\bar"
        assert result["is_absolute"] is False

    def test_single_dot_collapsed(self):
        result = path_normalize("foo\\.\\bar", "windows")
        assert result["normalized"] == "foo\\bar"
        assert result["is_absolute"] is False

    def test_no_collapse_preserves_dots(self):
        result = path_normalize("foo\\..\\bar", "windows", collapse_dot_segments=False)
        assert result["normalized"] == "foo\\..\\bar"
        assert result["is_absolute"] is False

    def test_dotdot_after_exhausted_collapse(self):
        result = path_normalize("a\\..\\..\\x", "windows")
        assert result["normalized"] == "..\\x"
        assert result["is_absolute"] is False


class TestPOSIXUnchanged:
    def test_posix_absolute_parent_collapse(self):
        result = path_normalize("/foo/../bar", "posix")
        assert result["normalized"] == "/bar"
        assert result["is_absolute"] is True

    def test_posix_root_only(self):
        result = path_normalize("/", "posix")
        assert result["normalized"] == "/"
        assert result["is_absolute"] is True

    def test_posix_dotdot_cannot_escape_root(self):
        result = path_normalize("/../bar", "posix")
        assert result["normalized"] == "/bar"
        assert result["is_absolute"] is True

    def test_posix_relative(self):
        result = path_normalize("foo/bar", "posix")
        assert result["normalized"] == "foo/bar"
        assert result["is_absolute"] is False

    def test_posix_trailing_slash_collapsed(self):
        result = path_normalize("/foo/", "posix")
        assert result["normalized"] == "/foo"
        assert result["is_absolute"] is True

    def test_posix_double_slash_collapsed(self):
        result = path_normalize("//foo//bar", "posix")
        assert result["normalized"] == "/foo/bar"
        assert result["is_absolute"] is True

    def test_posix_dot_segments(self):
        result = path_normalize("/a/./b/../c", "posix")
        assert result["normalized"] == "/a/c"
        assert result["is_absolute"] is True


class TestPathCompareRegression:
    def test_compare_unc_paths(self):
        result = path_compare(
            "\\\\server\\share\\file.txt", "\\\\server\\share\\file.txt", platform="windows"
        )
        assert result["equal"] is True

    def test_compare_unc_with_traversal(self):
        result = path_compare(
            "\\\\server\\share\\a\\..\\file.txt",
            "\\\\server\\share\\file.txt",
            platform="windows",
        )
        assert result["equal"] is True

    def test_compare_drive_paths(self):
        result = path_compare("C:\\foo\\bar", "C:\\foo\\bar", platform="windows")
        assert result["equal"] is True

    def test_compare_drive_with_traversal(self):
        result = path_compare("C:\\foo\\..\\bar", "C:\\bar", platform="windows")
        assert result["equal"] is True

    def test_compare_mixed_separators_windows(self):
        result = path_compare("C:/foo/bar", "C:\\foo\\bar", platform="windows")
        assert result["equal"] is True

    def test_compare_unc_forward_slash(self):
        result = path_compare(
            "//server/share/file.txt", "\\\\server\\share\\file.txt", platform="windows"
        )
        assert result["equal"] is True

    def test_compare_different_roots(self):
        result = path_compare("C:\\foo", "D:\\foo", platform="windows")
        assert result["equal"] is False

    def test_compare_unc_different_servers(self):
        result = path_compare("\\\\a\\share\\f", "\\\\b\\share\\f", platform="windows")
        assert result["equal"] is False

    def test_compare_posix_unchanged(self):
        result = path_compare("/a/b/../c", "/a/c", platform="posix")
        assert result["equal"] is True


class TestPathScopeCheckRegression:
    def test_scope_unc_inside(self):
        result = path_scope_check(
            "\\\\server\\share\\root", "\\\\server\\share\\root\\sub\\file", platform="windows"
        )
        assert result["inside_root"] is True
        assert result["relative_path"] == "sub\\file"

    def test_scope_unc_outside(self):
        result = path_scope_check(
            "\\\\server\\share\\root", "\\\\other\\share\\file", platform="windows"
        )
        assert result["inside_root"] is False

    def test_scope_drive_inside(self):
        result = path_scope_check("C:\\Users\\test", "C:\\Users\\test\\docs", platform="windows")
        assert result["inside_root"] is True

    def test_scope_drive_outside(self):
        result = path_scope_check("C:\\Users\\test", "D:\\Other\\file.txt", platform="windows")
        assert result["inside_root"] is False

    def test_scope_drive_mixed_separator(self):
        result = path_scope_check("C:/Users/test", "C:\\Users\\test\\docs", platform="windows")
        assert result["inside_root"] is True

    def test_scope_unc_traversal_stays_inside(self):
        result = path_scope_check(
            "\\\\server\\share\\a",
            "\\\\server\\share\\a\\b\\..\\c",
            platform="windows",
        )
        assert result["inside_root"] is True
        assert result["escapes_via_dotdot"] is True

    def test_scope_unc_traversal_escapes(self):
        result = path_scope_check(
            "\\\\server\\share\\a",
            "\\\\server\\share\\a\\..\\..\\etc\\passwd",
            platform="windows",
        )
        assert result["inside_root"] is False
        assert result["escapes_via_dotdot"] is True

    def test_scope_posix_unchanged(self):
        result = path_scope_check("/home/user", "/home/user/docs/file.txt")
        assert result["inside_root"] is True
        assert result["relative_path"] == "docs/file.txt"

    def test_scope_relative_target(self):
        result = path_scope_check("src", "src/main.rs")
        assert result["inside_root"] is True
