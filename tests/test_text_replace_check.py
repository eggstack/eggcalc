"""Tests for text_replace_check tool."""

from eggcalc.exact.synthesis import text_replace_check


class TestTextReplaceCheckBasic:
    """Test basic text_replace_check functionality."""

    def test_no_match(self):
        result = text_replace_check("hello world", "xyz", "abc")
        assert result["match_count"] == 0
        assert result["unique_match"] is False
        assert result["would_change"] is False
        assert any(f["kind"] == "no_match" for f in result["findings"])

    def test_single_match(self):
        result = text_replace_check("hello world", "world", "earth")
        assert result["match_count"] == 1
        assert result["unique_match"] is True
        assert result["would_change"] is True
        assert result["positions"][0]["codepoint_index"] == 6
        assert result["positions"][0]["line"] == 1
        assert result["positions"][0]["column"] == 7

    def test_multiple_matches(self):
        result = text_replace_check("aaa bbb aaa ccc aaa", "aaa", "xxx")
        assert result["match_count"] == 3
        assert result["unique_match"] is False
        assert result["would_change"] is True

    def test_multiple_matches_allow_multiple_false(self):
        result = text_replace_check("aaa bbb aaa", "aaa", "xxx", allow_multiple=False)
        assert result["match_count"] == 2
        assert any(f["kind"] == "ambiguous_replacement" for f in result["findings"])

    def test_multiple_matches_allow_multiple_true(self):
        result = text_replace_check("aaa bbb aaa", "aaa", "xxx", allow_multiple=True)
        assert result["match_count"] == 2
        assert not any(f["kind"] == "ambiguous_replacement" for f in result["findings"])

    def test_expected_count_met(self):
        result = text_replace_check("aaa bbb aaa", "aaa", "xxx", expected_count=2)
        assert result["expected_count_met"] is True

    def test_expected_count_not_met(self):
        result = text_replace_check("aaa bbb aaa", "aaa", "xxx", expected_count=3)
        assert result["expected_count_met"] is False
        assert any(f["kind"] == "count_mismatch" for f in result["findings"])


class TestTextReplaceCheckModes:
    """Test matching modes."""

    def test_exact_mode(self):
        result = text_replace_check("Hello World", "World", "Earth", mode="exact")
        assert result["match_count"] == 1

    def test_exact_mode_case_sensitive(self):
        result = text_replace_check("Hello World", "world", "Earth", mode="exact")
        assert result["match_count"] == 0

    def test_casefold_mode(self):
        result = text_replace_check("Hello World", "world", "Earth", mode="casefold")
        assert result["match_count"] == 1

    def test_nfc_mode(self):
        text = "caf\u00e9"  # precomposed
        old = "cafe\u0301"  # decomposed
        result = text_replace_check(text, old, "coffee", mode="nfc")
        assert result["match_count"] == 1

    def test_nfkc_mode(self):
        text = "\uff11\uff12\uff13"  # fullwidth digits
        old = "123"
        result = text_replace_check(text, old, "abc", mode="nfkc")
        assert result["match_count"] == 1

    def test_whitespace_collapse_mode(self):
        result = text_replace_check(
            "hello   world", "hello world", "hi earth", mode="whitespace_collapse"
        )
        assert result["match_count"] == 1


class TestTextReplaceCheckPositions:
    """Test position information."""

    def test_positions_byte_offsets(self):
        result = text_replace_check("hello world", "world", "earth")
        pos = result["positions"][0]
        assert pos["byte_start"] == 6
        assert pos["byte_end"] == 11

    def test_positions_multiline(self):
        text = "line1\nline2\nline3"
        result = text_replace_check(text, "line3", "LINE3")
        pos = result["positions"][0]
        assert pos["line"] == 3
        assert pos["column"] == 1


class TestTextReplaceCheckFingerprint:
    """Test fingerprint generation."""

    def test_fingerprint_changes(self):
        result = text_replace_check("hello world", "world", "earth")
        assert result["changed_text_fingerprint"] != ""

    def test_fingerprint_no_change(self):
        result = text_replace_check("hello world", "xyz", "abc")
        # When no match, fingerprint should still be present (unchanged text)
        assert result["changed_text_fingerprint"] != ""


class TestTextReplaceCheckNewlines:
    """Test newline style detection."""

    def test_lf_newlines(self):
        result = text_replace_check("hello\nworld", "world", "earth")
        assert result["newline_style_before"] == "LF"
        assert result["newline_style_after"] == "LF"

    def test_crlf_newlines(self):
        result = text_replace_check("hello\r\nworld", "world", "earth")
        assert result["newline_style_before"] == "CRLF"


class TestTextReplaceCheckPreview:
    """Test preview functionality."""

    def test_preview_disabled(self):
        result = text_replace_check("hello world", "world", "earth", return_preview=False)
        assert result["preview_before"] == ""
        assert result["preview_after"] == ""

    def test_preview_enabled(self):
        result = text_replace_check("hello world", "world", "earth", return_preview=True)
        assert result["preview_before"] == "hello world"
        assert result["preview_after"] == "hello earth"

    def test_preview_truncation(self):
        long_text = "a" * 5000
        result = text_replace_check(
            long_text, "aaa", "bbb", return_preview=True, max_preview_chars=100
        )
        assert len(result["preview_before"]) == 100


class TestTextReplaceCheckEdgeCases:
    """Test edge cases."""

    def test_empty_old_string(self):
        result = text_replace_check("hello", "", "x")
        # Empty string matches everywhere
        assert result["match_count"] > 0

    def test_unicode_text(self):
        result = text_replace_check("hello 世界", "世界", "earth")
        assert result["match_count"] == 1

    def test_newline_preserved(self):
        result = text_replace_check("hello\nworld", "world", "earth", newline_policy="preserve")
        assert result["newline_style_after"] == "LF"

    def test_newline_normalize_lf(self):
        result = text_replace_check(
            "hello\r\nworld", "world", "earth", newline_policy="normalize_lf"
        )
        assert (
            "\r\n" not in result.get("preview_after", "") or result["newline_style_after"] == "LF"
        )


class TestTextReplaceCheckNormalizedOffsets:
    """Regression tests: offsets must reference the original text, not the
    normalized form. Modes that change codepoint layout (NFC/NFKC compose or
    expand, casefold expansion, whitespace collapse) must still produce
    correct codepoint_index, byte_start, byte_end, line, column, and the
    preview must preserve surrounding codepoints."""

    def test_nfc_offset_after_decomposed_prefix(self):
        # é (NFD: e + combining acute) followed by X. NFC matches X at
        # normalized index 1, but original codepoint index 2. The preview
        # preserves the original decomposed form (NFC matching must not
        # silently rewrite the prefix).
        result = text_replace_check("e\u0301X", "X", "Y", mode="nfc", return_preview=True)
        pos = result["positions"][0]
        assert pos["codepoint_index"] == 2
        assert pos["byte_start"] == 3
        assert pos["byte_end"] == 4
        assert pos["column"] == 3
        assert result["preview_after"] == "e\u0301Y"

    def test_nfkc_offset_after_ligature(self):
        # U+FB03 (ﬃ) decomposes under NFKC to "ffi" (3 codepoints). The X
        # that follows should map to original codepoint index 1 and byte 3,
        # and the preview must keep the original ligature glyph.
        result = text_replace_check("\ufb03X", "X", "Y", mode="nfkc", return_preview=True)
        pos = result["positions"][0]
        assert pos["codepoint_index"] == 1
        assert pos["byte_start"] == 3
        assert pos["byte_end"] == 4
        assert pos["column"] == 2
        assert result["preview_after"] == "ﬃY"

    def test_casefold_preserves_original_casing_in_preview(self):
        # casefold matching should NOT lowercase unmatched surroundings in
        # the rendered change.
        result = text_replace_check(
            "Hello WORLD", "world", "earth", mode="casefold", return_preview=True
        )
        assert result["preview_after"] == "Hello earth"
        assert result["positions"][0]["codepoint_index"] == 6
        assert result["positions"][0]["byte_start"] == 6
        assert result["positions"][0]["byte_end"] == 11
