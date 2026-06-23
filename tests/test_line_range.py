"""Tests for line_range_extract and line_range_compare tools."""

from eggcalc.exact.synthesis import line_range_compare, line_range_extract


class TestLineRangeExtractBasic:
    """Test basic line_range_extract functionality."""

    def test_single_line(self):
        text = "line1\nline2\nline3"
        result = line_range_extract(text, 1, 1)
        assert result["line_count_total"] == 3
        assert result["start_line"] == 1
        assert result["end_line"] == 1
        assert result["valid_range"] is True
        assert result["text"] == "line1"
        assert len(result["lines"]) == 1
        assert result["lines"][0]["text"] == "line1"

    def test_multiple_lines(self):
        text = "line1\nline2\nline3"
        result = line_range_extract(text, 1, 2)
        assert result["text"] == "line1\nline2"
        assert len(result["lines"]) == 2

    def test_all_lines(self):
        text = "line1\nline2\nline3"
        result = line_range_extract(text, 1, 3)
        assert result["text"] == "line1\nline2\nline3"
        assert len(result["lines"]) == 3

    def test_single_line_out_of_range(self):
        text = "line1\nline2"
        result = line_range_extract(text, 5, 5)
        assert result["valid_range"] is False
        assert any(f["kind"] == "out_of_range" for f in result["findings"])

    def test_range_exceeds_total(self):
        text = "line1\nline2"
        result = line_range_extract(text, 1, 10)
        assert result["valid_range"] is False
        assert any(f["kind"] == "out_of_range" for f in result["findings"])


class TestLineRangeExtractOffsets:
    """Test byte and char offset computation."""

    def test_byte_offsets_simple(self):
        text = "abc\ndef\nghi"
        result = line_range_extract(text, 2, 2)
        assert result["byte_start"] == 4
        # byte_end includes the newline character
        assert result["byte_end"] == 8

    def test_char_offsets_simple(self):
        text = "abc\ndef\nghi"
        result = line_range_extract(text, 2, 2)
        assert result["char_start"] == 4
        # char_end includes the newline character
        assert result["char_end"] == 8

    def test_multiline_offsets(self):
        text = "abc\ndef\nghi"
        result = line_range_extract(text, 1, 2)
        assert result["char_start"] == 0
        # char_end includes the newline after line 2
        assert result["char_end"] == 8


class TestLineRangeExtractOptions:
    """Test extract options."""

    def test_include_line_numbers(self):
        text = "line1\nline2\nline3"
        result = line_range_extract(text, 1, 3, include_line_numbers=True)
        assert result["lines"][0]["line"] == 1
        assert result["lines"][1]["line"] == 2
        assert result["lines"][2]["line"] == 3

    def test_line_base_zero(self):
        text = "line1\nline2\nline3"
        result = line_range_extract(text, 0, 1, line_base=0, include_line_numbers=True)
        assert result["lines"][0]["line"] == 0
        assert result["lines"][1]["line"] == 1

    def test_include_fingerprint(self):
        text = "hello\nworld"
        result = line_range_extract(text, 1, 2, include_fingerprint=True)
        assert result["fingerprint"] != ""

    def test_exclude_fingerprint(self):
        text = "hello\nworld"
        result = line_range_extract(text, 1, 2, include_fingerprint=False)
        assert result["fingerprint"] == ""


class TestLineRangeExtractNewlines:
    """Test newline handling."""

    def test_lf_newlines(self):
        text = "line1\nline2\nline3"
        result = line_range_extract(text, 1, 3)
        assert result["newline_style"] == "LF"
        assert result["ends_with_newline"] is False

    def test_crlf_newlines(self):
        text = "line1\r\nline2\r\nline3"
        result = line_range_extract(text, 1, 2)
        assert result["newline_style"] == "CRLF"
        assert result["ends_with_newline"] is False

    def test_ends_with_newline(self):
        text = "line1\nline2\n"
        result = line_range_extract(text, 1, 2)
        assert result["ends_with_newline"] is True


class TestLineRangeExtractUnicode:
    """Test with Unicode text."""

    def test_unicode_text(self):
        text = "hello 世界\nfoo bar\nbaz qux"
        result = line_range_extract(text, 1, 1)
        assert result["text"] == "hello 世界"

    def test_unicode_multiline(self):
        text = "line1 日本語\nline2 中文\nline3 한국어"
        result = line_range_extract(text, 1, 2)
        assert "line1 日本語" in result["text"]
        assert "line2 中文" in result["text"]


class TestLineRangeCompareBasic:
    """Test basic line_range_compare functionality."""

    def test_equal_ranges(self):
        text = "line1\nline2\nline3"
        result = line_range_compare(text, text, 1, 2)
        assert result["equal"] is True
        assert result["left_fingerprint"] == result["right_fingerprint"]
        assert result["diff_summary"] == "equal"

    def test_different_ranges(self):
        left = "line1\nline2\nline3"
        right = "line1\nLINE2\nline3"
        result = line_range_compare(left, right, 2, 2)
        assert result["equal"] is False
        assert result["diff_summary"] != "equal"
        assert result["first_difference"] is not None

    def test_first_difference_info(self):
        left = "aaa\nbbb\nccc"
        right = "aaa\nBBB\nccc"
        result = line_range_compare(left, right, 1, 3)
        assert result["first_difference"]["line_number"] == 2
        assert result["first_difference"]["left"] == "bbb"
        assert result["first_difference"]["right"] == "BBB"


class TestLineRangeCompareModes:
    """Test comparison modes."""

    def test_exact_mode_trailing_whitespace(self):
        left = "hello  \nworld"
        right = "hello\nworld"
        result = line_range_compare(left, right, 1, 1, comparison_mode="exact")
        assert result["equal"] is False

    def test_ignore_trailing_whitespace(self):
        left = "hello  \nworld"
        right = "hello\nworld"
        result = line_range_compare(left, right, 1, 1, comparison_mode="ignore_trailing_whitespace")
        assert result["equal"] is True

    def test_normalize_newlines(self):
        left = "hello\r\nworld"
        right = "hello\nworld"
        result = line_range_compare(left, right, 1, 1, comparison_mode="normalize_newlines")
        assert result["equal"] is True

    def test_normalize_newlines_still_different(self):
        left = "hello\r\nworld"
        right = "hello\nWORLD"
        # Compare both lines to catch the case difference
        result = line_range_compare(left, right, 1, 2, comparison_mode="normalize_newlines")
        assert result["equal"] is False


class TestLineRangeCompareOptions:
    """Test compare options."""

    def test_line_base_zero(self):
        text = "aaa\nbbb\nccc"
        result = line_range_compare(text, text, 0, 1, line_base=0)
        assert result["equal"] is True

    def test_fingerprints_present(self):
        text = "aaa\nbbb"
        result = line_range_compare(text, text, 1, 1)
        assert result["left_fingerprint"] != ""
        assert result["right_fingerprint"] != ""


class TestLineRangeCompareValidation:
    """Test input validation for line_range_compare via MCP tool handler."""

    def _call_compare(self, left_text, right_text, start_line, end_line):
        from eggcalc.mcp.tools import line_range_compare

        return line_range_compare(left_text, right_text, start_line, end_line)

    def test_reject_bool_start_line(self):
        result = self._call_compare("line1\nline2", "line1\nline2", True, 2)
        assert result["ok"] is False
        assert result["error_type"] == "invalid_arguments"
        assert "start_line" in result["error"]

    def test_reject_bool_end_line(self):
        result = self._call_compare("line1\nline2", "line1\nline2", 1, False)
        assert result["ok"] is False
        assert result["error_type"] == "invalid_arguments"
        assert "end_line" in result["error"]

    def test_reject_negative_start_line(self):
        result = self._call_compare("line1\nline2", "line1\nline2", -1, 2)
        assert result["ok"] is False
        assert result["error_type"] == "invalid_arguments"
        assert "start_line" in result["error"]

    def test_reject_negative_end_line(self):
        result = self._call_compare("line1\nline2", "line1\nline2", 1, -1)
        assert result["ok"] is False
        assert result["error_type"] == "invalid_arguments"
        assert "end_line" in result["error"]

    def test_reject_start_line_greater_than_end_line(self):
        result = self._call_compare("line1\nline2\nline3", "line1\nline2\nline3", 3, 1)
        assert result["ok"] is False
        assert result["error_type"] == "invalid_arguments"
        assert "start_line" in result["error"]

    def test_reject_string_start_line(self):
        result = self._call_compare("line1\nline2", "line1\nline2", "1", 2)
        assert result["ok"] is False
        assert result["error_type"] == "invalid_arguments"
        assert "start_line" in result["error"]

    def test_reject_string_end_line(self):
        result = self._call_compare("line1\nline2", "line1\nline2", 1, "2")
        assert result["ok"] is False
        assert result["error_type"] == "invalid_arguments"
        assert "end_line" in result["error"]

    def test_reject_float_start_line(self):
        result = self._call_compare("line1\nline2", "line1\nline2", 1.5, 2)
        assert result["ok"] is False
        assert result["error_type"] == "invalid_arguments"
        assert "start_line" in result["error"]

    def test_reject_float_end_line(self):
        result = self._call_compare("line1\nline2", "line1\nline2", 1, 2.5)
        assert result["ok"] is False
        assert result["error_type"] == "invalid_arguments"
        assert "end_line" in result["error"]


class TestLineRangeCompareEdgeCases:
    """Test edge cases."""

    def test_empty_lines(self):
        left = "\n\n"
        right = "\n\n"
        result = line_range_compare(left, right, 1, 2)
        assert result["equal"] is True

    def test_different_lengths(self):
        left = "aaa\nbbb"
        right = "aaa"
        result = line_range_compare(left, right, 1, 3)
        assert result["equal"] is False
        assert "different lengths" in result["diff_summary"]

    def test_unicode_comparison(self):
        left = "hello 世界\nfoo"
        right = "hello 世界\nfoo"
        result = line_range_compare(left, right, 1, 1)
        assert result["equal"] is True
