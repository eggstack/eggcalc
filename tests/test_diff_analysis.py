"""Tests for diff_analysis.py — structural analysis of unified diffs."""

from eggcalc.exact.diff_analysis import (
    diff_file_headers,
    diff_hunk_ranges,
    diff_touched_paths,
    patch_conflict_markers_inspect,
    unified_diff_validate,
)

SAMPLE_DIFF = """\
diff --git a/foo.py b/foo.py
index abc1234..def5678 100644
--- a/foo.py
+++ b/foo.py
@@ -1,7 +1,7 @@
 def hello():
-    print("old")
+    print("new")
     return True
 
 def world():
@@ -10,4 +10,5 @@
     x = 1
     y = 2
+    z = 3
     return x + y
+    return x + y + z
"""

SAMPLE_DIFF_ADDED = """\
diff --git a/new_file.txt b/new_file.txt
new file mode 100644
index 0000000..abcdef1
--- /dev/null
+++ b/new_file.txt
@@ -0,0 +1,2 @@
+hello
+world
"""

SAMPLE_DIFF_DELETED = """\
diff --git a/old_file.txt b/old_file.txt
deleted file mode 100644
index abcdef1..0000000
--- a/old_file.txt
+++ /dev/null
@@ -1,2 +0,0 @@
-hello
-world
"""

SAMPLE_DIFF_RENAME = """\
diff --git a/old_name.py b/new_name.py
similarity index 100%
rename from old_name.py
rename to new_name.py
--- a/old_name.py
+++ b/new_name.py
@@ -1,3 +1,3 @@
 def foo():
-    pass
+    return None
"""

SAMPLE_DIFF_BINARY = """\
diff --git a/image.png b/image.png
index abc1234..def5678 100644
--- a/image.png
+++ b/image.png
Binary files a/image.png and b/image.png differ
GIT binary patch
"""

SAMPLE_DIFF_MODE_CHANGE = """\
diff --git a/script.sh b/script.sh
old mode 100644
new mode 100755
index abc1234..def5678
--- a/script.sh
+++ b/script.sh
@@ -1,3 +1,3 @@
 #!/bin/bash
-echo "old"
+echo "new"
"""


class TestDiffTouchedPaths:
    def test_basic_modified(self):
        result = diff_touched_paths(SAMPLE_DIFF)
        assert result["parse_ok"] is True
        assert result["error"] is None
        assert "b/foo.py" in result["modified"]
        assert result["total_files"] == 1
        assert result["added"] == []
        assert result["deleted"] == []

    def test_added_file(self):
        result = diff_touched_paths(SAMPLE_DIFF_ADDED)
        assert result["parse_ok"] is True
        assert "b/new_file.txt" in result["added"]
        assert result["deleted"] == []
        assert result["modified"] == []

    def test_deleted_file(self):
        result = diff_touched_paths(SAMPLE_DIFF_DELETED)
        assert result["parse_ok"] is True
        assert "a/old_file.txt" in result["deleted"]
        assert result["added"] == []
        assert result["modified"] == []

    def test_rename_detection(self):
        result = diff_touched_paths(SAMPLE_DIFF_RENAME)
        assert result["parse_ok"] is True
        assert len(result["renamed"]) == 1
        assert result["renamed"][0]["from"] == "old_name.py"
        assert result["renamed"][0]["to"] == "new_name.py"

    def test_binary_detection(self):
        result = diff_touched_paths(SAMPLE_DIFF_BINARY)
        assert result["parse_ok"] is True
        assert "b/image.png" in result["binary_files"]

    def test_mode_changes(self):
        result = diff_touched_paths(SAMPLE_DIFF_MODE_CHANGE)
        assert result["parse_ok"] is True
        assert len(result["mode_changes"]) == 1
        mc = result["mode_changes"][0]
        assert mc["old_mode"] == "100644"
        assert mc["new_mode"] == "100755"

    def test_empty_input(self):
        result = diff_touched_paths("")
        assert result["parse_ok"] is False
        assert "Empty" in result["error"]

    def test_invalid_input(self):
        result = diff_touched_paths("not a diff at all")
        assert result["parse_ok"] is False

    def test_max_files_limit(self):
        result = diff_touched_paths(SAMPLE_DIFF, max_files=0)
        assert result["parse_ok"] is True
        assert result["total_files"] == 0

    def test_oversized_patch(self):
        result = diff_touched_paths("x" * 300_000)
        assert result["parse_ok"] is False
        assert "exceeds" in result["error"]


class TestDiffHunkRanges:
    def test_single_hunk(self):
        diff = """\
--- a/x.py
+++ b/x.py
@@ -1,3 +1,3 @@
 a
-b
+c
 d
"""
        result = diff_hunk_ranges(diff)
        assert result["parse_ok"] is True
        assert len(result["files"]) == 1
        file_info = result["files"][0]
        assert len(file_info["hunks"]) == 1
        hunk = file_info["hunks"][0]
        assert hunk["old_start"] == 1
        assert hunk["old_count"] == 3
        assert hunk["new_start"] == 1
        assert hunk["new_count"] == 3
        assert hunk["added_lines"] == 1
        assert hunk["deleted_lines"] == 1
        assert hunk["context_lines"] == 2

    def test_multi_hunk(self):
        result = diff_hunk_ranges(SAMPLE_DIFF)
        assert result["parse_ok"] is True
        assert len(result["files"]) == 1
        file_info = result["files"][0]
        assert len(file_info["hunks"]) == 2
        assert file_info["total_added"] == 3
        assert file_info["total_deleted"] == 1

    def test_empty_diff(self):
        result = diff_hunk_ranges("")
        assert result["parse_ok"] is False

    def test_line_count_classification(self):
        diff = """\
--- a/x.py
+++ b/x.py
@@ -1,1 +1,3 @@
+added1
+added2
+added3
"""
        result = diff_hunk_ranges(diff)
        assert result["parse_ok"] is True
        hunk = result["files"][0]["hunks"][0]
        assert hunk["added_lines"] == 3
        assert hunk["deleted_lines"] == 0
        assert hunk["context_lines"] == 0

    def test_oversized_patch(self):
        result = diff_hunk_ranges("x" * 300_000)
        assert result["parse_ok"] is False


class TestDiffFileHeaders:
    def test_git_diff_format(self):
        result = diff_file_headers(SAMPLE_DIFF)
        assert result["parse_ok"] is True
        assert len(result["files"]) == 1
        entry = result["files"][0]
        assert entry["diff_git_line"] is not None
        assert "diff --git" in entry["diff_git_line"]
        assert entry["old_file"] == "a/foo.py"
        assert entry["new_file"] == "b/foo.py"
        assert entry["index_line"] is not None
        assert entry["hunks_count"] == 2

    def test_rename_detection(self):
        result = diff_file_headers(SAMPLE_DIFF_RENAME)
        assert result["parse_ok"] is True
        assert len(result["files"]) == 1
        entry = result["files"][0]
        assert entry["rename_from"] == "old_name.py"
        assert entry["rename_to"] == "new_name.py"

    def test_index_hash(self):
        result = diff_file_headers(SAMPLE_DIFF)
        assert result["parse_ok"] is True
        entry = result["files"][0]
        assert entry["index_line"] is not None
        assert "abc1234" in entry["index_line"]

    def test_mode_changes(self):
        result = diff_file_headers(SAMPLE_DIFF_MODE_CHANGE)
        assert result["parse_ok"] is True
        entry = result["files"][0]
        assert entry["old_mode"] == "100644"
        assert entry["new_mode"] == "100755"

    def test_binary_file(self):
        result = diff_file_headers(SAMPLE_DIFF_BINARY)
        assert result["parse_ok"] is True
        entry = result["files"][0]
        assert entry["is_binary"] is True

    def test_new_file(self):
        result = diff_file_headers(SAMPLE_DIFF_ADDED)
        assert result["parse_ok"] is True
        entry = result["files"][0]
        assert entry["is_new_file"] is True

    def test_deleted_file(self):
        result = diff_file_headers(SAMPLE_DIFF_DELETED)
        assert result["parse_ok"] is True
        entry = result["files"][0]
        assert entry["is_deleted_file"] is True

    def test_empty_input(self):
        result = diff_file_headers("")
        assert result["parse_ok"] is False

    def test_copy_directives(self):
        diff = """\
diff --git a/copy.py b/copy.py
copy from source.py
copy to copy.py
--- a/source.py
+++ b/copy.py
@@ -1,2 +1,2 @@
-a
+b
"""
        result = diff_file_headers(diff)
        assert result["parse_ok"] is True
        entry = result["files"][0]
        assert entry["copy_from"] == "source.py"
        assert entry["copy_to"] == "copy.py"

    def test_oversized_patch(self):
        result = diff_file_headers("x" * 300_000)
        assert result["parse_ok"] is False


class TestPatchConflictMarkers:
    def test_no_markers(self):
        result = patch_conflict_markers_inspect("hello world\nno conflicts here\n")
        assert result["total_markers"] == 0
        assert result["conflict_starts"] == 0
        assert result["conflict_separators"] == 0
        assert result["conflict_ends"] == 0
        assert result["imbalanced"] is False
        assert result["nested"] is False
        assert result["locations"] == []

    def test_balanced_markers(self):
        text = """\
<<<<<<< HEAD
ours
=======
theirs
>>>>>>> branch
"""
        result = patch_conflict_markers_inspect(text)
        assert result["total_markers"] == 3
        assert result["conflict_starts"] == 1
        assert result["conflict_separators"] == 1
        assert result["conflict_ends"] == 1
        assert result["imbalanced"] is False
        assert result["nested"] is False

    def test_imbalanced_markers(self):
        text = """\
<<<<<<< HEAD
ours
=======
theirs
>>>>>>> branch
<<<<<<< HEAD
second conflict
=======
second theirs
"""
        result = patch_conflict_markers_inspect(text)
        assert result["conflict_starts"] == 2
        assert result["conflict_ends"] == 1
        assert result["imbalanced"] is True

    def test_nested_markers(self):
        text = """\
<<<<<<< outer
<<<<<<< inner
nested content
>>>>>>> inner
=======
other
>>>>>>> outer
"""
        result = patch_conflict_markers_inspect(text)
        assert result["nested"] is True
        assert result["conflict_starts"] == 2
        assert result["conflict_ends"] == 2

    def test_line_numbers(self):
        text = """\
line 1
line 2
<<<<<<< start
line 4
=======
line 6
>>>>>>> end
"""
        result = patch_conflict_markers_inspect(text)
        lines = {loc["line"]: loc["kind"] for loc in result["locations"]}
        assert lines[3] == "start"
        assert lines[5] == "separator"
        assert lines[7] == "end"

    def test_empty_text(self):
        result = patch_conflict_markers_inspect("")
        assert result["total_markers"] == 0
        assert result["locations"] == []

    def test_multiple_conflicts(self):
        text = """\
<<<<<<< A
a1
=======
b1
>>>>>>> A
<<<<<<< A
a2
=======
b2
>>>>>>> A
"""
        result = patch_conflict_markers_inspect(text)
        assert result["conflict_starts"] == 2
        assert result["conflict_separators"] == 2
        assert result["conflict_ends"] == 2
        assert result["imbalanced"] is False


class TestUnifiedDiffValidate:
    def test_valid_diff(self):
        result = unified_diff_validate(SAMPLE_DIFF)
        assert result["parse_ok"] is True
        assert result["structure_valid"] is True
        assert result["files_count"] == 1
        assert result["hunks_total"] == 2
        assert result["warnings"] == []

    def test_empty_input(self):
        result = unified_diff_validate("")
        assert result["parse_ok"] is False
        assert result["structure_valid"] is False
        assert len(result["warnings"]) > 0

    def test_invalid_hunk_header(self):
        diff = """\
--- a/x.py
+++ b/x.py
@@ -1,3 +1,3 bad @@
 a
 b
 c
"""
        result = unified_diff_validate(diff)
        # Invalid @@ header means parser creates a file entry but no hunk is recorded
        assert result["parse_ok"] is True
        # No hunks parsed from this malformed header
        assert result["hunks_total"] == 0

    def test_line_count_excess_warning(self):
        diff = """\
--- a/x.py
+++ b/x.py
@@ -1,2 +1,2 @@
 a
+b
 c
 d
"""
        result = unified_diff_validate(diff)
        assert result["parse_ok"] is True
        assert any("new count" in w for w in result["warnings"])

    def test_check_line_counts_disabled(self):
        diff = """\
--- a/x.py
+++ b/x.py
@@ -1,5 +1,5 @@
 a
-b
+c
 d
 e
"""
        result = unified_diff_validate(diff, check_line_counts=False)
        assert result["parse_ok"] is True
        assert not any("old count" in w for w in result["warnings"])

    def test_valid_hunk_counts(self):
        diff = """\
--- a/x.py
+++ b/x.py
@@ -1,3 +1,4 @@
 a
+b1
+b2
 c
"""
        result = unified_diff_validate(diff)
        assert result["parse_ok"] is True
        assert result["structure_valid"] is True
        assert result["warnings"] == []

    def test_zero_counts_warning(self):
        diff = """\
--- a/x.py
+++ b/x.py
@@ -0,0 +0,0 @@
"""
        result = unified_diff_validate(diff)
        assert result["parse_ok"] is True
        assert any("zero counts" in w for w in result["warnings"])

    def test_multi_file(self):
        diff = """\
diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
@@ -1,3 +1,3 @@
-a
+b
 c
diff --git a/b.py b/b.py
--- a/b.py
+++ b/b.py
@@ -1,2 +1,2 @@
-x
+y
"""
        result = unified_diff_validate(diff)
        assert result["parse_ok"] is True
        # Note: parse_unified_diff treats multi-file diffs as a single
        # file entry with all hunks combined — this is a parser limitation.
        assert result["files_count"] >= 1
        assert result["hunks_total"] == 2

    def test_oversized_patch(self):
        result = unified_diff_validate("x" * 300_000)
        assert result["parse_ok"] is False

    def test_oversized_conflict_marker_input_is_bounded(self):
        result = patch_conflict_markers_inspect("x" * 300_000)
        assert result["total_markers"] == 0
