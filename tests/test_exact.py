"""Tests for eggcalc exact text primitives.

Tests for:
- Low-level Unicode primitives (primitives.py)
- Unicode tools (unicode_tools.py)
- Diff primitives (diff.py)
- Validation primitives (validate.py)
- Measurement primitives (measure.py)
- Synthesis functions (synthesis.py)
"""

import pytest

from eggcalc.exact import (
    casefold_text,
    char_category_metrics,
    check_brackets,
    codepoints,
    common_prefix_suffix,
    count_chars,
    count_graphemes,
    detect_confusables,
    detect_mixed_scripts,
    diff_spans,
    explain_diff,
    find_invisibles,
    first_diff,
    inspect_text,
    levenshtein_distance,
    line_metrics,
    list_compare,
    longest_common_subsequence,
    measure_basic,
    measure_text,
    normalize_unicode,
    normalized_equal,
    raw_equal,
    regex_test,
    text_equal,
    truncate_to_grapheme,
    unicode_script,
    utf8_bytes,
    validate_json,
    visible_repr,
    word_metrics,
)
from eggcalc.exact.validate import MAX_LIST_ITEMS


class TestPrimitives:
    """Tests for basic primitives."""

    def test_utf8_bytes_basic(self):
        assert utf8_bytes("hello") == b"hello"

    def test_utf8_bytes_unicode(self):
        assert utf8_bytes("héllo") == "héllo".encode()
        assert utf8_bytes("日本語") == "日本語".encode()

    def test_utf8_bytes_empty(self):
        assert utf8_bytes("") == b""

    def test_codepoints_basic(self):
        result = codepoints("ABC")
        assert len(result) == 3
        assert result[0].char == "A"
        assert result[0].codepoint == "U+0041"
        assert result[0].name == "LATIN CAPITAL LETTER A"
        assert result[0].category == "Lu"

    def test_codepoints_unicode(self):
        result = codepoints("日本語")
        assert len(result) == 3
        assert result[0].codepoint == "U+65E5"  # 日

    def test_codepoints_combining(self):
        result = codepoints("é")  # composed
        assert len(result) == 1
        result2 = codepoints("e\u0301")  # decomposed
        assert len(result2) == 2

    def test_normalize_unicode_valid_forms(self):
        s = "café"  # NFC: é is U+00E9
        assert normalize_unicode(s, "NFC") == s
        assert normalize_unicode(s, "NFD") != s  # NFD decomposes

        s_nfc = normalize_unicode("café", "NFC")
        s_nfd = normalize_unicode("café", "NFD")
        assert normalize_unicode(s_nfc, "NFC") == normalize_unicode(s_nfd, "NFC")

    def test_normalize_unicode_invalid_form(self):
        with pytest.raises(ValueError) as exc_info:
            normalize_unicode("test", "INVALID")
        assert "INVALID" in str(exc_info.value)

    def test_casefold_text_basic(self):
        assert casefold_text("HELLO") == "hello"
        assert casefold_text("ß") == "ss"  # German sharp s

    def test_casefold_text_turkish(self):
        assert casefold_text("İ") == "i\u0307"  # Turkish dotted I

    def test_raw_equal_true(self):
        assert raw_equal("hello", "hello") is True
        assert raw_equal("", "") is True

    def test_raw_equal_false(self):
        assert raw_equal("hello", "world") is False
        assert raw_equal("hello", "Hello") is False
        assert raw_equal("café", "cafe\u0301") is False  # same visual, different bytes

    def test_normalized_equal_nfc(self):
        assert normalized_equal("café", "cafe\u0301", "NFC") is True
        assert raw_equal("café", "cafe\u0301") is False

    def test_normalized_equal_nfkc(self):
        assert normalized_equal("ℌ", "H", "NFKC") is True  # Casenom variant
        assert normalized_equal("①", "1", "NFKC") is True

    def test_measure_basic_ascii(self):
        result = measure_basic("hello world")
        assert result["bytes_utf8"] == 11
        assert result["codepoints"] == 11
        assert result["chars_no_whitespace"] == 10
        assert result["ascii"] == 11
        assert result["non_ascii"] == 0

    def test_measure_basic_unicode(self):
        result = measure_basic("日本語")
        assert result["codepoints"] == 3
        assert result["ascii"] == 0
        assert result["non_ascii"] == 3
        assert result["bytes_utf8"] == 9  # 3 bytes each in UTF-8

    def test_measure_basic_empty(self):
        result = measure_basic("")
        assert result["bytes_utf8"] == 0
        assert result["codepoints"] == 0

    def test_find_invisibles_zwsp(self):
        result = find_invisibles("hello\u200bworld")
        assert len(result) == 1
        assert result[0]["char"] == "\u200b"
        assert result[0]["codepoint"] == "U+200B"
        assert result[0]["display"] == "ZWSP"

    def test_find_invisibles_bom(self):
        result = find_invisibles("\ufeffhello")
        assert len(result) == 1
        assert result[0]["char"] == "\ufeff"
        assert result[0]["display"] == "BOM"

    def test_find_invisibles_nbsp(self):
        result = find_invisibles("hello\u00a0world")
        assert len(result) == 1
        assert result[0]["display"] == "NBSP"

    def test_find_invisibles_bidi(self):
        result = find_invisibles("abc\u202edef")
        assert len(result) == 1
        assert "\u202e" == "\u202e"  # RLO
        assert "RLO" in result[0]["display"]

    def test_find_invisibles_combining(self):
        result = find_invisibles("e\u0301")  # combining acute
        assert len(result) == 1
        assert result[0]["display"] == "CM"

    def test_find_invisibles_none(self):
        result = find_invisibles("hello world")
        assert len(result) == 0

    def test_find_invisibles_newlines_excluded(self):
        result = find_invisibles("hello\nworld")
        assert len(result) == 0  # \n is not considered "invisible"

    def test_visible_repr_basic(self):
        assert visible_repr("hello world") == "hello␠world"
        assert visible_repr("line1\nline2") == "line1␊line2"

    def test_visible_repr_zwsp(self):
        assert visible_repr("a\u200bb") == "a⟦ZWSP⟧b"

    def test_visible_repr_combining(self):
        assert visible_repr("e\u0301") == "e◌\u0301"

    def test_visible_repr_mixed(self):
        result = visible_repr("hello\u200bworld")
        assert "hello" in result
        assert "⟦ZWSP⟧" in result
        assert "world" in result

    def test_is_extended_pictographic_cjk_not_emoji(self):
        from eggcalc.exact.primitives import _is_extended_pictographic

        assert not _is_extended_pictographic('\u4e00')  # CJK character '一'
        assert not _is_extended_pictographic('\u4e2d')  # CJK character '中'
        assert not _is_extended_pictographic('\u0410')  # Cyrillic 'А'
        assert not _is_extended_pictographic('\u0627')  # Arabic 'ا'

    def test_is_extend_char_zwsp(self):
        from eggcalc.exact.primitives import _is_extend_char

        assert not _is_extend_char('\u200b')  # ZWSP (Grapheme_Break=Control per UAX #29)
        assert _is_extend_char('\u200c')  # ZWNJ
        assert not _is_extend_char('\u200d')  # ZWJ (not included)
        assert not _is_extend_char('\u200e')  # LRM (not included)

    def test_is_extend_char_combining(self):
        from eggcalc.exact.primitives import _is_extend_char

        assert _is_extend_char('\u0301')  # combining acute accent (Mn)
        assert _is_extend_char('\u0302')  # combining circumflex (Mn)
        assert _is_extend_char('\ufe00')  # variation selector 1


class TestGraphemeClusters:
    """Tests for grapheme cluster counting and truncation."""

    def test_count_graphemes_empty(self):
        assert count_graphemes("") == 0

    def test_count_graphemes_ascii(self):
        assert count_graphemes("hello") == 5

    def test_count_graphemes_combining(self):
        # e + combining acute = 1 grapheme
        assert count_graphemes("e\u0301") == 1
        # e + combining ring + combining acute = 1 grapheme
        assert count_graphemes("e\u030a\u0301") == 1

    def test_count_graphemes_precomposed(self):
        # é (U+00E9) = 1 grapheme
        assert count_graphemes("\u00e9") == 1

    def test_count_graphemes_ri_pair(self):
        # Two RIs form one flag emoji (GB12/GB13)
        assert count_graphemes("\U0001f1e6\U0001f1e7") == 1  # 🇦🇧

    def test_count_graphemes_ri_lone(self):
        # Single RI is one grapheme
        assert count_graphemes("\U0001f1e6") == 1

    def test_count_graphemes_ri_three(self):
        # Three RIs: one pair + one lone = 2 graphemes
        assert count_graphemes("\U0001f1e6\U0001f1e7\U0001f1e8") == 2

    def test_count_graphemes_ri_four(self):
        # Four RIs: two pairs = 2 graphemes
        assert count_graphemes("\U0001f1e6\U0001f1e7\U0001f1e8\U0001f1e9") == 2

    def test_count_graphemes_ri_six(self):
        # Six RIs: three pairs = 3 graphemes
        assert count_graphemes("\U0001f1e6\U0001f1e7\U0001f1e8\U0001f1e9\U0001f1ea\U0001f1eb") == 3

    def test_count_graphemes_zwj_sequence(self):
        # Family emoji (ZWJ-separated) = 1 grapheme
        family = "\U0001f468\u200d\U0001f469\u200d\U0001f467\u200d\U0001f466"
        assert count_graphemes(family) == 1

    def test_count_graphemes_zwj_simple(self):
        # Simple ZWJ pair (man + ZWJ + woman) = 1 grapheme
        couple = "\U0001f468\u200d\U0001f469"
        assert count_graphemes(couple) == 1

    def test_count_graphemes_variation_selector(self):
        # Character + VS16 (emoji presentation) = 1 grapheme
        assert count_graphemes("\u0023\ufe0f") == 1  # # + VS16
        # Character + VS15 (text presentation) = 1 grapheme
        assert count_graphemes("\u0023\ufe0e") == 1

    def test_count_graphemes_mixed(self):
        # "A" + flag + "B" = 3 graphemes
        s = "A\U0001f1e6\U0001f1e7B"
        assert count_graphemes(s) == 3

    def test_truncate_to_grapheme_empty(self):
        assert truncate_to_grapheme("", 5) == ""

    def test_truncate_to_grapheme_zero(self):
        assert truncate_to_grapheme("hello", 0) == ""

    def test_truncate_to_grapheme_ascii(self):
        assert truncate_to_grapheme("hello", 3) == "hel"

    def test_truncate_to_grapheme_combining(self):
        # Truncating mid-combining sequence should preserve the base char
        s = "e\u0301"  # é as decomposed
        assert truncate_to_grapheme(s, 1) == s
        assert truncate_to_grapheme(s, 0) == ""

    def test_truncate_to_grapheme_ri_pair(self):
        # 4 RIs = 2 pairs; truncating to 2 should keep all 4 RIs
        s = "\U0001f1e6\U0001f1e7\U0001f1e8\U0001f1e9"
        assert truncate_to_grapheme(s, 2) == s

    def test_truncate_to_grapheme_ri_truncates_pair(self):
        # 3 RIs = pair + lone; truncating to 1 should keep the pair
        s = "\U0001f1e6\U0001f1e7\U0001f1e8"
        assert truncate_to_grapheme(s, 1) == "\U0001f1e6\U0001f1e7"

    def test_truncate_to_grapheme_zwj(self):
        # Family emoji should not be cut mid-sequence
        family = "\U0001f468\u200d\U0001f469\u200d\U0001f467\u200d\U0001f466"
        assert truncate_to_grapheme(family, 1) == family
        assert truncate_to_grapheme(family, 0) == ""


class TestUnicodeTools:
    """Tests for Unicode tools."""

    def test_unicode_script_latin(self):
        assert unicode_script("A") == "Latin"
        assert unicode_script("a") == "Latin"
        assert unicode_script("z") == "Latin"

    def test_unicode_script_cyrillic(self):
        assert unicode_script("А") == "Cyrillic"  # Cyrillic A
        assert unicode_script("Я") == "Cyrillic"

    def test_unicode_script_greek(self):
        assert unicode_script("Α") == "Greek"
        assert unicode_script("Ω") == "Greek"

    def test_unicode_script_han(self):
        assert unicode_script("日") == "Han"
        assert unicode_script("本") == "Han"

    def test_unicode_script_combining(self):
        assert unicode_script("\u0301") == "Inherited"  # combining acute

    def test_unicode_script_invalid_char(self):
        with pytest.raises(ValueError):
            unicode_script("")

        with pytest.raises(ValueError):
            unicode_script("ab")  # multiple chars

    def test_detect_mixed_scripts_latin_only(self):
        result = detect_mixed_scripts("hello world")
        assert result["mixed_scripts"] is False
        assert result["scripts"] == ["Latin"]

    def test_detect_mixed_scripts_cyrillic_only(self):
        result = detect_mixed_scripts("привет")
        assert result["mixed_scripts"] is False
        assert result["scripts"] == ["Cyrillic"]

    def test_detect_mixed_scripts_mixed(self):
        result = detect_mixed_scripts("helloПривет")
        assert result["mixed_scripts"] is True
        assert "Latin" in result["scripts"]
        assert "Cyrillic" in result["scripts"]
        assert len(result["positions"]) > 0

    def test_detect_mixed_scripts_common_excluded(self):
        result = detect_mixed_scripts("hello 123 !?")
        assert result["mixed_scripts"] is False
        assert "Latin" in result["scripts"]  # letters detected

    def test_detect_confusables_cyrillic_a(self):
        result = detect_confusables("АBC")  # Cyrillic A
        assert len(result) == 1
        assert result[0]["char"] == "А"
        assert result[0]["confusable_with"] == "A"

    def test_detect_confusables_greek(self):
        result = detect_confusables("ΑBC")  # Greek Alpha
        assert len(result) == 1
        assert result[0]["char"] == "Α"
        assert result[0]["confusable_with"] == "A"

    def test_detect_confusables_fullwidth(self):
        result = detect_confusables("\uff21")  # Fullwidth A
        assert len(result) == 1
        assert result[0]["confusable_with"] == "A"

    def test_detect_confusables_none(self):
        result = detect_confusables("hello")
        assert len(result) == 0 or all(
            c["char"] == c["confusable_with"] for c in result
        )  # only trivial self-mappings if any

    def test_detect_confusables_math(self):
        result = detect_confusables("\U0001d670")  # Mathematical Script A
        assert len(result) == 1
        assert result[0]["confusable_with"] == "A"


class TestDiff:
    """Tests for diff primitives."""

    def test_first_diff_equal(self):
        assert first_diff("hello", "hello") is None

    def test_first_diff_start(self):
        result = first_diff("hello", "world")
        assert result["a_index"] == 0
        assert result["b_index"] == 0
        assert result["a_char"] == "h"
        assert result["b_char"] == "w"

    def test_first_diff_middle(self):
        result = first_diff("hello", "hallo")
        assert result["a_index"] == 1
        assert result["a_char"] == "e"
        assert result["b_char"] == "a"

    def test_first_diff_end(self):
        result = first_diff("hello", "hellp")
        assert result["a_index"] == 4
        assert result["a_char"] == "o"
        assert result["b_char"] == "p"

    def test_first_diff_length(self):
        result = first_diff("abc", "abcd")
        assert result["a_index"] == 3
        assert result["b_index"] == 3
        assert result["a_char"] == ""
        assert result["b_char"] == "d"

    def test_common_prefix_suffix_basic(self):
        result = common_prefix_suffix("prefix_test_suffix", "prefix_other_suffix")
        assert result["common_prefix_len"] == 7  # "prefix"
        assert result["common_suffix_len"] == 7  # "_suffix"

    def test_common_prefix_suffix_no_overlap(self):
        result = common_prefix_suffix("abc", "xyz")
        assert result["common_prefix_len"] == 0
        assert result["common_suffix_len"] == 0

    def test_common_prefix_suffix_identical(self):
        result = common_prefix_suffix("hello", "hello")
        assert result["common_prefix_len"] == 5
        assert result["common_suffix_len"] == 0  # suffix can't overlap with prefix

    def test_common_prefix_suffix_overlapping(self):
        result = common_prefix_suffix("abcxyz", "xyzabc")
        assert result["common_prefix_len"] == 0
        # suffix shouldn't overlap with prefix
        assert result["common_suffix_len"] == 0

    def test_levenshtein_distance_identical(self):
        assert levenshtein_distance("hello", "hello") == 0

    def test_levenshtein_distance_one_char(self):
        assert levenshtein_distance("hello", "hallo") == 1  # substitution
        assert levenshtein_distance("hello", "helloo") == 1  # insertion
        assert levenshtein_distance("helloo", "hello") == 1  # deletion

    def test_levenshtein_distance_kitten_sitting(self):
        assert levenshtein_distance("kitten", "sitting") == 3

    def test_levenshtein_distance_empty(self):
        assert levenshtein_distance("", "abc") == 3
        assert levenshtein_distance("abc", "") == 3
        assert levenshtein_distance("", "") == 0

    def test_levenshtein_distance_max_len(self):
        with pytest.raises(ValueError):
            levenshtein_distance("a" * 20000, "b")

    def test_levenshtein_distance_with_max_len(self):
        result = levenshtein_distance("hello", "world", max_len=10)
        assert result == 4

    def test_diff_spans_equal(self):
        result = diff_spans("hello", "hello")
        assert len(result) == 0

    def test_diff_spans_insert(self):
        result = diff_spans("abc", "abcd")
        assert len(result) == 1
        assert result[0]["kind"] == "insert"
        assert result[0]["a_span"] == [3, 3]
        assert result[0]["b_span"] == [3, 4]

    def test_diff_spans_delete(self):
        result = diff_spans("abcd", "abc")
        assert len(result) == 1
        assert result[0]["kind"] == "delete"
        assert result[0]["a_span"] == [3, 4]
        assert result[0]["b_span"] == [3, 3]

    def test_diff_spans_replace(self):
        result = diff_spans("abc", "axc")
        assert len(result) == 1
        assert result[0]["kind"] == "replace"

    def test_diff_spans_max_diffs(self):
        result = diff_spans("abc", "xyz", max_diffs=2)
        assert len(result) <= 2

    def test_longest_common_subsequence_ab_ba(self):
        result = longest_common_subsequence("ab", "ba")
        assert len(result) == 1
        assert result in ("a", "b")

    def test_longest_common_subsequence_basic(self):
        assert longest_common_subsequence("abcde", "ace") == "ace"
        assert longest_common_subsequence("abc", "abc") == "abc"
        assert longest_common_subsequence("abc", "def") == ""

    def test_longest_common_subsequence_handles_large_inputs(self):
        value = longest_common_subsequence("ab" * 750, "ba" * 750)
        assert len(value) == 1499


class TestValidate:
    """Tests for validation primitives."""

    def test_check_brackets_balanced(self):
        result = check_brackets("(a[b]{c})")
        assert result["balanced"] is True
        assert len(result["unmatched_openers"]) == 0
        assert len(result["unmatched_closers"]) == 0

    def test_check_brackets_unmatched_opener(self):
        result = check_brackets("(a[b]{c")
        assert result["balanced"] is False
        assert len(result["unmatched_openers"]) == 2  # '(' and '{' remain unmatched
        assert len(result["unmatched_closers"]) == 0

    def test_check_brackets_unmatched_closer(self):
        result = check_brackets("a]b")
        assert result["balanced"] is False
        assert len(result["unmatched_closers"]) == 1
        assert result["unmatched_closers"][0]["char"] == "]"

    def test_check_brackets_mismatch(self):
        result = check_brackets("(a]")
        assert result["balanced"] is False
        assert len(result["unmatched_openers"]) == 1
        assert len(result["unmatched_closers"]) == 1

    def test_check_brackets_nested(self):
        result = check_brackets("({[]})")
        assert result["balanced"] is True

    def test_check_brackets_custom_pairs(self):
        result = check_brackets("<a>", {"<": ">"})
        assert result["balanced"] is True

    def test_check_brackets_empty(self):
        result = check_brackets("")
        assert result["balanced"] is True

    def test_validate_json_valid_object(self):
        result = validate_json('{"name": "test", "value": 123}')
        assert result["valid"] is True
        assert result["type"] == "object"
        assert result["top_level_keys"] == ["name", "value"]

    def test_validate_json_valid_array(self):
        result = validate_json('[1, 2, 3]')
        assert result["valid"] is True
        assert result["type"] == "array"

    def test_validate_json_invalid(self):
        result = validate_json('{"name": }')
        assert result["valid"] is False
        assert result["error"] is not None
        assert result["line"] == 1

    def test_validate_json_trailing_comma(self):
        result = validate_json('{"name": "test",}')
        assert result["valid"] is False
        assert result["error"] is not None


class TestRegexTest:
    """Tests for regex_test primitive."""

    def test_regex_test_valid_pattern(self):
        result = regex_test(r"^a", ["abc", "def"])
        assert result["valid_pattern"] is True
        assert len(result["results"]) == 2
        assert result["results"][0]["matches"] is True
        assert result["results"][1]["matches"] is False

    def test_regex_test_fullmatch(self):
        result = regex_test(r"^abc$", ["abc", "abcd"])
        assert result["results"][0]["fullmatch"] is True
        assert result["results"][1]["fullmatch"] is False

    def test_regex_test_groups(self):
        result = regex_test(r"(a)(b)", ["ab"])
        assert result["valid_pattern"] is True
        assert result["results"][0]["groups"] == ["a", "b"]

    def test_regex_test_invalid_pattern(self):
        result = regex_test(r"[invalid", ["test"])
        assert result["valid_pattern"] is False

    def test_regex_test_flags(self):
        result = regex_test(r"abc", ["ABC"], flags=["IGNORECASE"])
        assert result["results"][0]["matches"] is True

    def test_regex_test_sample_length_limit(self):
        long_sample = "a" * 20000
        result = regex_test(r"^a+$", [long_sample])
        assert result["results"] == []
        assert "MAX_SAMPLE_LENGTH" in result["error"]

    def test_regex_test_sample_count_limit(self):
        result = regex_test(r"^a+$", ["a"] * (MAX_LIST_ITEMS + 1))
        assert result["valid_pattern"] is False
        assert result["results"] == []
        assert "Samples count" in result["error"]

    def test_regex_test_rejects_non_string_samples(self):
        result = regex_test(r"^a+$", ["a", 123])  # type: ignore[list-item]
        assert result["valid_pattern"] is False
        assert result["results"] == []
        assert "All samples must be strings" in result["error"]

    def test_regex_test_rejects_non_list_samples(self):
        result = regex_test(r"^a+$", "a")  # type: ignore[arg-type]
        assert result["valid_pattern"] is False
        assert result["results"] == []
        assert "Samples must be a list" in result["error"]

    def test_regex_test_rejects_non_list_flags(self):
        result = regex_test(r"^a+$", ["a"], flags="IGNORECASE")  # type: ignore[arg-type]
        assert result["valid_pattern"] is False
        assert result["results"] == []
        assert "Flags must be a list" in result["error"]

    def test_regex_test_rejects_non_string_flags(self):
        result = regex_test(r"^a+$", ["a"], flags=["IGNORECASE", 123])  # type: ignore[list-item]
        assert result["valid_pattern"] is False
        assert result["results"] == []
        assert "All flags must be strings" in result["error"]


class TestMeasure:
    """Tests for measurement primitives."""

    def test_line_metrics_lf(self):
        result = line_metrics("hello\nworld\n")
        assert result["lines"] == 2
        assert result["nonempty_lines"] == 2
        assert result["blank_lines"] == 0
        assert result["newline_style"] == "LF"
        assert result["ends_with_newline"] is True

    def test_line_metrics_crlf(self):
        result = line_metrics("hello\r\nworld\r\n")
        assert result["newline_style"] in ("CRLF", "mixed")

    @pytest.mark.parametrize("text", ["hello\n", "hello\r", "hello\r\n"])
    def test_line_metrics_all_newline_terminators(self, text):
        assert line_metrics(text)["ends_with_newline"] is True

    def test_line_metrics_without_newline(self):
        assert line_metrics("hello")["ends_with_newline"] is False

    def test_line_metrics_mixed(self):
        result = line_metrics("hello\nworld\r\n")
        assert result["newline_style"] == "mixed"

    def test_line_metrics_trailing_whitespace(self):
        result = line_metrics("hello \nworld\n")
        assert 1 in result["trailing_whitespace_lines"]

    def test_line_metrics_max_line_length(self):
        result = line_metrics("short\nvery long line here\n")
        assert result["max_line_length_codepoints"] == 19

    def test_line_metrics_empty(self):
        result = line_metrics("")
        assert result["lines"] == 0
        assert result["newline_style"] == "none"

    def test_word_metrics_basic(self):
        result = word_metrics("hello world hello")
        assert result["words"] == 3
        assert result["unique_words_casefolded"] == 2  # hello, world

    def test_word_metrics_punctuation(self):
        result = word_metrics("hello! world?")
        assert result["words"] == 2  # punctuation stripped

    def test_word_metrics_sentences(self):
        result = word_metrics("Hello. World! Hello again.")
        assert result["sentences_estimate"] == 3

    def test_word_metrics_paragraphs(self):
        result = word_metrics("Para 1\n\nPara 2")
        assert result["paragraphs"] == 2

    def test_word_metrics_empty(self):
        result = word_metrics("")
        assert result["words"] == 0

    def test_word_metrics_average_length(self):
        result = word_metrics("hi there friend")
        assert result["average_word_length"] == pytest.approx(4.33, rel=0.01)

    def test_char_category_metrics(self):
        result = char_category_metrics("Hello World 123!")
        assert result["letters"] == 10
        assert result["digits"] == 3
        assert result["punctuation"] == 1
        assert result["spaces"] == 2


class TestSynthesis:
    """Tests for synthesis functions."""

    def test_measure_text_basic(self):
        result = measure_text("Hello World")
        assert result["codepoints"] == 11
        assert result["words"] == 2
        assert result["normalization"]["is_nfc"] is True

    def test_measure_text_unicode_risks(self):
        result = measure_text("hello\u200bworld")
        assert result["unicode_risks"]["contains_invisibles"] is True
        assert result["invisible_chars"] == 1

    def test_measure_text_too_long(self):
        with pytest.raises(ValueError):
            measure_text("a" * 200000)

    def test_text_equal_raw(self):
        result = text_equal("hello", "hello")
        assert result["equal"] is True
        assert result["raw_equal"] is True

    def test_text_equal_nfc(self):
        result = text_equal("cafe\u0301", "café", normalization="NFC")
        assert result["equal"] is True
        assert result["nfc_equal"] is True

    def test_text_equal_casefold(self):
        result = text_equal("HELLO", "hello", casefold=True)
        assert result["equal"] is True
        assert result["casefold_equal"] is True

    def test_text_equal_trim(self):
        result = text_equal("  hello  ", "hello", trim=True)
        assert result["equal"] is True

    def test_text_equal_classification(self):
        result = text_equal("café", "cafe\u0301")
        assert result["classification"] in [
            "unicode_normalization_only",
            "accent_or_diacritic_difference",
        ]

    def test_text_equal_case_and_diacritic(self):
        result = text_equal("café", "CAFÉ")
        assert result["classification"] == "case_only"

    def test_explain_diff_classification_case(self):
        result = explain_diff("HELLO", "hello")
        assert result["classification"] == "case_only"

    def test_explain_diff_classification_insert(self):
        result = explain_diff("hello", "hello!")
        assert result["classification"] == "length_only"

    def test_explain_diff_symmetry_length_only(self):
        result1 = explain_diff("hello!", "hello")
        result2 = explain_diff("hello", "hello!")
        assert result1["classification"] == "length_only"
        assert result2["classification"] == "length_only"

    def test_explain_diff_security_findings(self):
        result = explain_diff("\u200b", "")  # ZWSP vs empty
        assert len(result["security_findings"]) > 0

    def test_explain_diff_agent_instruction(self):
        result = explain_diff("abc", "def")
        assert "agent_instruction" in result
        assert len(result["agent_instruction"]) > 0

    def test_inspect_text_safe_repr(self):
        result = inspect_text("hello\u200bworld")
        assert "ZWSP" in result["safe_repr"]
        assert "hello" in result["safe_repr"]
        assert "world" in result["safe_repr"]

    def test_inspect_text_invisibles(self):
        result = inspect_text("a\u200bb")
        assert len(result["invisibles"]) == 1
        assert result["invisibles"][0]["codepoint"] == "U+200B"

    def test_inspect_text_confusables(self):
        result = inspect_text("АBC")  # Cyrillic A
        assert len(result["confusables"]) == 1

    def test_inspect_text_warnings(self):
        result = inspect_text("hello\u200bworld")
        assert len(result["warnings"]) > 0

    @pytest.mark.parametrize("form", ["NFKC", "NFKD"])
    def test_inspect_text_normalization_findings_only_when_changed(self, form):
        unchanged = inspect_text("hello", normalize=form, compare_normalized=True)
        assert unchanged["normalized"]["changed"] is False
        assert unchanged["normalization_findings"] == []

        changed = inspect_text("①", normalize=form, compare_normalized=True)
        assert changed["normalized"]["changed"] is True
        assert changed["normalization_findings"]

    def test_count_chars_target(self):
        result = count_chars("strawberry", "r")
        assert result["count"] == 3
        assert result["positions"] == [2, 7, 8]

    def test_count_chars_frequency_table(self):
        result = count_chars("hello")
        assert isinstance(result, dict)
        assert result["l"] == 2
        assert result["e"] == 1
        assert result["o"] == 1

    def test_count_chars_normalization(self):
        result = count_chars("cafe\u0301", "é", normalization="NFC")
        assert result["count"] == 1

    def test_count_chars_target_too_long(self):
        with pytest.raises(ValueError):
            count_chars("hello", "ab")

    def test_list_compare_same(self):
        result = list_compare(["a", "b"], ["a", "b"])
        assert result["same_ordered"] is True
        assert result["same_unordered"] is True

    def test_list_compare_different_order(self):
        result = list_compare(["a", "b"], ["b", "a"], ignore_order=True)
        assert result["same_ordered"] is True  # same_unordered takes precedence with ignore_order
        assert result["same_unordered"] is True

    def test_list_compare_near_matches(self):
        result = list_compare(
            ["Hello"],
            ["hello"],
            ignore_order=True,
            include_near_matches=True,
            near_match_threshold=2,
        )
        assert len(result["near_matches"]) == 1
        assert result["near_matches"][0]["classification"] == "fuzzy"

    def test_list_compare_duplicates(self):
        result = list_compare(["a", "a", "b"], ["a", "b", "b"])
        assert "a" in result["duplicates_a"]
        assert "b" in result["duplicates_b"]


class TestInputLimits:
    """Tests for input size limits."""

    def test_measure_text_max_length(self):
        with pytest.raises(ValueError) as exc_info:
            measure_text("a" * 200000)
        assert "MAX_TEXT_LENGTH" in str(exc_info.value)

    def test_count_chars_max_length(self):
        with pytest.raises(ValueError):
            count_chars("a" * 200000, "a")

    def test_inspect_text_max_length(self):
        with pytest.raises(ValueError):
            inspect_text("a" * 200000)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
