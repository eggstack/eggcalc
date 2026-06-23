"""Integration tests for CLI text commands (inspect, count, regex, replace-check, lines, etc.).

These tests exercise the CLI layer through subprocess to ensure
the commands work correctly from the command line.
"""

import json
import subprocess
import sys

import pytest


def run_calc(args: list[str]) -> tuple[int, str, str]:
    """Run calc command and return (returncode, stdout, stderr)."""
    result = subprocess.run(
        [sys.executable, "eggcalc.py"] + args,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


class TestCLIInspect:
    """Tests for calc inspect command."""

    def test_inspect_clean_text(self):
        """Clean text should show no hidden characters."""
        code, stdout, stderr = run_calc(["inspect", "hello"])
        assert code == 0
        assert "No hidden characters" in stdout
        assert "\u2713" in stdout  # checkmark

    def test_inspect_clean_text_unicode(self):
        """Clean Unicode text should pass inspection."""
        code, stdout, stderr = run_calc(["inspect", "héllo"])
        assert code == 0
        assert "No hidden characters" in stdout

    def test_inspect_confusable(self):
        """Confusable characters should be detected."""
        # Cyrillic 'а' (U+0430) looks like Latin 'a' (U+0061)
        code, stdout, stderr = run_calc(["inspect", "аbc"])
        assert code == 0
        assert "CONFUSABLE" in stdout

    def test_inspect_zero_width_space(self):
        """Zero-width space should be detected with name."""
        code, stdout, stderr = run_calc(["-e", "inspect hello\u200bworld"])
        assert code == 0
        assert "ZERO WIDTH SPACE" in stdout
        assert "U+200B" not in stdout

    def test_inspect_missing_text(self):
        """Missing text argument should error."""
        code, stdout, stderr = run_calc(["inspect"])
        assert code == 1
        assert "Usage" in stderr


class TestCLICount:
    """Tests for calc count command."""

    def test_count_single_char(self):
        """Count single character."""
        code, stdout, stderr = run_calc(["count", "hello"])
        assert code == 0
        assert "5" in stdout

    def test_count_specific_char(self):
        """Count specific character occurrence."""
        code, stdout, stderr = run_calc(["count", "hello", "l"])
        assert code == 0
        assert "2" in stdout
        assert "'l'" in stdout

    def test_count_multiple_words(self):
        """Count with frequency table for multiple words."""
        code, stdout, stderr = run_calc(["count", "hello world"])
        assert code == 0
        assert "11" in stdout  # total characters

    def test_count_space_char(self):
        """Count space character."""
        code, stdout, stderr = run_calc(["count", "hello world", " "])
        assert code == 0
        assert "1" in stdout

    def test_count_missing_text(self):
        """Missing text argument should error."""
        code, stdout, stderr = run_calc(["count"])
        assert code == 1
        assert "Usage" in stderr


class TestCLIRegex:
    """Tests for calc regex command."""

    def test_regex_match(self):
        """Match should succeed."""
        code, stdout, stderr = run_calc(["regex", r"^\d+$", "12345"])
        assert code == 0
        assert "Match" in stdout
        assert "\u2713" in stdout

    def test_regex_no_match(self):
        """No match should be reported."""
        code, stdout, stderr = run_calc(["regex", r"^hello", "world"])
        assert code == 0
        assert "No match" in stdout
        assert "\u2717" in stdout

    def test_regex_with_groups(self):
        """Capture groups should be displayed."""
        code, stdout, stderr = run_calc(["regex", r"(\d+)-(\d+)", "555-1234"])
        assert code == 0
        assert "Match" in stdout
        assert "555" in stdout

    def test_regex_invalid_pattern(self):
        """Invalid pattern should error."""
        code, stdout, stderr = run_calc(["regex", r"[invalid", "test"])
        assert code == 1

    def test_regex_missing_args(self):
        """Missing arguments should error."""
        code, stdout, stderr = run_calc(["regex", "pattern"])
        assert code == 1
        assert "Usage" in stderr

    def test_regex_json_output(self):
        """JSON output should be valid JSON."""
        code, stdout, stderr = run_calc(["--json", "regex", r"^\d+$", "12345"])
        assert code == 0
        data = json.loads(stdout)
        assert data["results"][0]["matches"] is True


class TestCLIReplaceCheck:
    """Tests for calc replace-check command."""

    def test_single_match(self):
        """Single match should report clean replacement."""
        code, stdout, stderr = run_calc(["replace-check", "foo", "|||", "bar", "|||", "foo baz"])
        assert code == 0
        assert "cleanly" in stdout
        assert "1 match" in stdout

    def test_multiple_matches(self):
        """Multiple matches should report ambiguity."""
        code, stdout, stderr = run_calc(["replace-check", "foo", "|||", "bar", "|||", "foo baz foo"])
        assert code == 0
        assert "ambiguous" in stdout
        assert "2 matches" in stdout

    def test_no_match(self):
        """No match should be reported."""
        code, stdout, stderr = run_calc(["replace-check", "xyz", "|||", "bar", "|||", "foo baz"])
        assert code == 0
        assert "No match" in stdout

    def test_json_output(self):
        """JSON output should be valid JSON."""
        code, stdout, stderr = run_calc(["--json", "replace-check", "foo", "|||", "bar", "|||", "foo baz"])
        assert code == 0
        data = json.loads(stdout)
        assert data["match_count"] == 1

    def test_missing_delimiter(self):
        """Missing delimiter should show usage."""
        code, stdout, stderr = run_calc(["replace-check", "foo", "bar"])
        assert code == 1
        assert "Usage" in stderr

    def test_missing_args(self):
        """Missing arguments should show usage."""
        code, stdout, stderr = run_calc(["replace-check"])
        assert code == 1
        assert "Usage" in stderr


class TestCLILines:
    """Tests for calc lines command."""

    def test_extract_range(self):
        """Line range extraction should work."""
        text = "line1\nline2\nline3\nline4\nline5"
        code, stdout, stderr = run_calc(["-e", f"lines 2-4 {text}"])
        assert code == 0
        assert "2: line2" in stdout
        assert "3: line3" in stdout
        assert "4: line4" in stdout

    def test_single_line(self):
        """Single line extraction should work."""
        text = "line1\nline2\nline3"
        code, stdout, stderr = run_calc(["-e", f"lines 2 {text}"])
        assert code == 0
        assert "line2" in stdout

    def test_out_of_range(self):
        """Out of range should report error."""
        text = "line1\nline2"
        code, stdout, stderr = run_calc(["-e", f"lines 5-10 {text}"])
        assert code == 1

    def test_json_output(self):
        """JSON output should be valid JSON."""
        text = "line1\nline2\nline3"
        code, stdout, stderr = run_calc(["--json", "-e", f"lines 1-2 {text}"])
        assert code == 0
        data = json.loads(stdout)
        assert data["valid_range"] is True
        assert data["start_line"] == 1
        assert data["end_line"] == 2

    def test_missing_args(self):
        """Missing arguments should show usage."""
        code, stdout, stderr = run_calc(["lines"])
        assert code == 1
        assert "Usage" in stderr


class TestCLIShellSplit:
    """Tests for calc shell-split command."""

    def test_simple_command(self):
        """Simple command should parse correctly."""
        code, stdout, stderr = run_calc(["-e", "shell-split git commit -m fix"])
        assert code == 0
        assert "4 token(s)" in stdout
        assert "git" in stdout

    def test_quoted_args(self):
        """Quoted arguments should be preserved."""
        code, stdout, stderr = run_calc(["-e", 'shell-split git commit -m "hello world"'])
        assert code == 0
        assert "4 token(s)" in stdout
        assert "hello world" in stdout

    def test_features_detected(self):
        """Risky features should be detected."""
        code, stdout, stderr = run_calc(["-e", "shell-split cat file | grep foo"])
        assert code == 0
        assert "pipe" in stdout.lower()

    def test_json_output(self):
        """JSON output should be valid JSON."""
        code, stdout, stderr = run_calc(["--json", "-e", "shell-split ls -la"])
        assert code == 0
        data = json.loads(stdout)
        assert data["parse_ok"] is True
        assert data["argc"] == 2

    def test_missing_args(self):
        """Missing arguments should show usage."""
        code, stdout, stderr = run_calc(["shell-split"])
        assert code == 1
        assert "Usage" in stderr


class TestCLIMdStructure:
    """Tests for calc md-structure command."""

    def test_headings_and_links(self):
        """Headings and links should be detected."""
        code, stdout, stderr = run_calc(["-e", 'md-structure # Hello\n\nA [link](http://example.com)'])
        assert code == 0
        assert "heading" in stdout.lower()
        assert "link" in stdout.lower()

    def test_code_fence(self):
        """Code fences should be detected."""
        code, stdout, stderr = run_calc(["-e", 'md-structure # Title\n\n```python\nprint(\'hi\')\n```\n'])
        assert code == 0
        assert "code fence" in stdout.lower()

    def test_unclosed_fence(self):
        """Unclosed code fence should be reported."""
        code, stdout, stderr = run_calc(["-e", 'md-structure # Title\n\n```python\nprint(\'hi\')'])
        assert code == 0
        assert "unclosed" in stdout.lower()

    def test_empty_markdown(self):
        """Empty markdown should report no elements."""
        code, stdout, stderr = run_calc(["-e", "md-structure just some text"])
        assert code == 0

    def test_json_output(self):
        """JSON output should be valid JSON."""
        code, stdout, stderr = run_calc(["--json", "-e", 'md-structure # Hello\n\nA [link](http://x.com)'])
        assert code == 0
        data = json.loads(stdout)
        assert len(data["headings"]) == 1
        assert len(data["links"]) == 1

    def test_missing_args(self):
        """Missing arguments should show usage."""
        code, stdout, stderr = run_calc(["md-structure"])
        assert code == 1
        assert "Usage" in stderr


class TestCLIDotenvCheck:
    """Tests for calc dotenv-check command."""

    def test_valid_env(self):
        """Valid .env should pass."""
        code, stdout, stderr = run_calc(["-e", "dotenv-check DB_HOST=localhost DB_PORT=5432"])
        assert code == 0
        assert "Valid" in stdout
        assert "\u2713" in stdout

    def test_invalid_env(self):
        """Invalid .env should fail."""
        code, stdout, stderr = run_calc(["-e", "dotenv-check NO_EQUALS_SIGN"])
        assert code == 0
        assert "Invalid" in stdout
        assert "\u2717" in stdout

    def test_json_output(self):
        """JSON output should be valid JSON."""
        code, stdout, stderr = run_calc(["--json", "-e", "dotenv-check KEY=value"])
        assert code == 0
        data = json.loads(stdout)
        assert data["parse_ok"] is True
        assert len(data["entries"]) == 1

    def test_missing_args(self):
        """Missing arguments should show usage."""
        code, stdout, stderr = run_calc(["dotenv-check"])
        assert code == 1
        assert "Usage" in stderr


class TestCLIPatchCheck:
    """Tests for calc patch-check command."""

    def test_clean_patch(self):
        """Patch that applies cleanly should report success."""
        original = "line1\nline2\nline3"
        patch = "--- a/file\n+++ b/file\n@@ -1,3 +1,3 @@\n line1\n-old\n+new\n line3\n"
        code, stdout, stderr = run_calc(["-e", f"patch-check {original} ||| {patch}"])
        assert code == 0

    def test_json_output(self):
        """JSON output should be valid JSON."""
        original = "line1\nline2\nline3"
        patch = "--- a/file\n+++ b/file\n@@ -1,3 +1,3 @@\n line1\n-old\n+new\n line3\n"
        code, stdout, stderr = run_calc(["--json", "-e", f"patch-check {original} ||| {patch}"])
        assert code == 0
        data = json.loads(stdout)
        assert "patch_parse_ok" in data

    def test_missing_delimiter(self):
        """Missing delimiter should show usage."""
        code, stdout, stderr = run_calc(["patch-check", "original"])
        assert code == 1
        assert "Usage" in stderr


class TestCLIMathStillWorks:
    """Ensure math expressions still work alongside text commands."""

    def test_basic_math(self):
        """Basic math should still work."""
        code, stdout, stderr = run_calc(["5", "+", "3"])
        assert code == 0
        assert "8" in stdout

    def test_natural_language_math(self):
        """Natural language math should work."""
        code, stdout, stderr = run_calc(["five", "plus", "three"])
        assert code == 0
        assert "8" in stdout

    def test_unit_conversion(self):
        """Unit conversions should work."""
        code, stdout, stderr = run_calc(["30m", "+", "100ft"])
        assert code == 0
        # Should have result with meters


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
