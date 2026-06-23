"""Golden fixture tests - deterministic adversarial test corpus.

Loads JSON fixture files and runs them against the corresponding tools,
comparing output to expected values.
"""

from __future__ import annotations

import pytest

from tests.fixtures import load_all_fixtures


def get_value(result, key, default=None):
    """Safely extract a value from a result dict."""
    if isinstance(result, dict):
        return result.get(key, default)
    return default


# ---------------------------------------------------------------------------
# text_equal fixtures
# ---------------------------------------------------------------------------


class TestTextEqualFixtures:
    """Run all text_equal fixtures."""

    @pytest.fixture(params=load_all_fixtures("unicode"))
    def fixture_data(self, request):
        rel_path, data = request.param
        if data.get("tool") != "text_equal":
            pytest.skip("Not a text_equal fixture")
        return rel_path, data

    def test_text_equal(self, fixture_data):
        from eggcalc.exact import text_equal

        rel_path, data = fixture_data
        for case in data["cases"]:
            inp = case["input"]
            exp = case["expected"]
            result = text_equal(
                inp["a"],
                inp["b"],
                normalization=inp.get("normalization", "raw"),
                casefold=inp.get("casefold", False),
                trim=inp.get("trim", False),
                ignore_newline_style=inp.get("ignore_newline_style", False),
                ignore_trailing_whitespace=inp.get("ignore_trailing_whitespace", False),
                ignore_final_newline=inp.get("ignore_final_newline", False),
            )
            for key, expected_val in exp.items():
                actual = get_value(result, key)
                assert actual == expected_val, (
                    f"Fixture {rel_path} case '{case['name']}': "
                    f"expected {key}={expected_val!r}, got {actual!r}"
                )


# ---------------------------------------------------------------------------
# measure_text fixtures
# ---------------------------------------------------------------------------


class TestMeasureTextFixtures:
    """Run all measure_text fixtures."""

    @pytest.fixture(params=load_all_fixtures("unicode"))
    def fixture_data(self, request):
        rel_path, data = request.param
        if data.get("tool") != "measure_text":
            pytest.skip("Not a measure_text fixture")
        return rel_path, data

    def test_measure_text(self, fixture_data):
        from eggcalc.exact import measure_text

        rel_path, data = fixture_data
        for case in data["cases"]:
            inp = case["input"]
            exp = case["expected"]
            result = measure_text(inp["text"])

            for key, expected_val in exp.items():
                if key == "contains_invisibles":
                    actual = result.get("invisible_chars", 0) > 0
                elif key == "contains_zwj":
                    # Check warnings for ZWJ mention
                    warnings = result.get("warnings", [])
                    actual = any("zero-width joiner" in w.lower() for w in warnings)
                else:
                    actual = get_value(result, key)
                assert actual == expected_val, (
                    f"Fixture {rel_path} case '{case['name']}': "
                    f"expected {key}={expected_val!r}, got {actual!r}"
                )


# ---------------------------------------------------------------------------
# inspect_text fixtures
# ---------------------------------------------------------------------------


class TestInspectTextFixtures:
    """Run all inspect_text fixtures."""

    @pytest.fixture(params=load_all_fixtures("unicode"))
    def fixture_data(self, request):
        rel_path, data = request.param
        if data.get("tool") != "inspect_text":
            pytest.skip("Not an inspect_text fixture")
        return rel_path, data

    def test_inspect_text(self, fixture_data):
        from eggcalc.exact import inspect_text

        rel_path, data = fixture_data
        for case in data["cases"]:
            inp = case["input"]
            exp = case["expected"]
            result = inspect_text(inp["text"])

            for key, expected_val in exp.items():
                if key == "has_bidi_controls":
                    # Bidi chars may show up in warnings or bidi_controls
                    # Bidi control names: RLO, LRO, RLE, LRE, RLI, LRI, FSI, PDF, LRM, RLM
                    bidi_keywords = (
                        "bidi",
                        "right-to-left",
                        "left-to-right",
                        "pop directional",
                        "embedding",
                        "override",
                    )
                    warnings = result.get("warnings", [])
                    bidi_warns = [
                        w
                        for w in warnings
                        if any(kw in w.get("message", "").lower() for kw in bidi_keywords)
                    ]
                    actual = len(result.get("bidi_controls", [])) > 0 or len(bidi_warns) > 0
                elif key == "bidi_count":
                    bidi_keywords = (
                        "bidi",
                        "right-to-left",
                        "left-to-right",
                        "pop directional",
                        "embedding",
                        "override",
                    )
                    warnings = result.get("warnings", [])
                    bidi_warns = [
                        w
                        for w in warnings
                        if any(kw in w.get("message", "").lower() for kw in bidi_keywords)
                    ]
                    actual = len(result.get("bidi_controls", [])) + len(bidi_warns)
                elif key == "mixed_scripts":
                    ms = result.get("mixed_scripts", {})
                    actual = ms.get("mixed_scripts", False) if isinstance(ms, dict) else False
                elif key == "has_confusables":
                    actual = len(result.get("confusables", [])) > 0
                elif key == "confusable_count_min":
                    actual = len(result.get("confusables", []))
                    assert actual >= expected_val, (
                        f"Fixture {rel_path} case '{case['name']}': "
                        f"expected confusable_count >= {expected_val}, got {actual}"
                    )
                    continue
                else:
                    actual = get_value(result, key)
                assert actual == expected_val, (
                    f"Fixture {rel_path} case '{case['name']}': "
                    f"expected {key}={expected_val!r}, got {actual!r}"
                )


# ---------------------------------------------------------------------------
# text_replace_check fixtures
# ---------------------------------------------------------------------------


class TestTextReplaceCheckFixtures:
    """Run all text_replace_check fixtures."""

    @pytest.fixture(params=load_all_fixtures("text"))
    def fixture_data(self, request):
        rel_path, data = request.param
        if data.get("tool") != "text_replace_check":
            pytest.skip("Not a text_replace_check fixture")
        return rel_path, data

    def test_text_replace_check(self, fixture_data):
        from eggcalc.exact import text_replace_check

        rel_path, data = fixture_data
        for case in data["cases"]:
            inp = case["input"]
            exp = case["expected"]
            kwargs = {}
            for key in (
                "mode",
                "expected_count",
                "allow_multiple",
                "newline_policy",
                "return_preview",
                "max_preview_chars",
            ):
                if key in inp:
                    kwargs[key] = inp[key]

            result = text_replace_check(inp["text"], inp["old"], inp["new"], **kwargs)

            for key, expected_val in exp.items():
                if key == "finding_kind":
                    actual_kinds = [f.get("kind") for f in result.get("findings", [])]
                    assert expected_val in actual_kinds, (
                        f"Fixture {rel_path} case '{case['name']}': "
                        f"expected finding kind '{expected_val}' in {actual_kinds}"
                    )
                    continue
                elif key == "has_ambiguous_finding":
                    actual = any(
                        f.get("kind") == "ambiguous_replacement" for f in result.get("findings", [])
                    )
                    assert actual == expected_val, (
                        f"Fixture {rel_path} case '{case['name']}': "
                        f"expected has_ambiguous_finding={expected_val}, got {actual}"
                    )
                    continue
                elif key == "preview_before_max_len":
                    actual_len = len(result.get("preview_before", ""))
                    assert actual_len <= expected_val, (
                        f"Fixture {rel_path} case '{case['name']}': "
                        f"expected preview_before len <= {expected_val}, got {actual_len}"
                    )
                    continue
                elif key.startswith("position_"):
                    # Handle nested position keys like position_line, position_column, position_codepoint_index
                    pos_key = key[len("position_") :]
                    positions = result.get("positions", [])
                    if positions:
                        actual = positions[0].get(pos_key)
                    else:
                        actual = None
                else:
                    actual = get_value(result, key)
                assert actual == expected_val, (
                    f"Fixture {rel_path} case '{case['name']}': "
                    f"expected {key}={expected_val!r}, got {actual!r}"
                )


# ---------------------------------------------------------------------------
# line_range_extract fixtures
# ---------------------------------------------------------------------------


class TestLineRangeExtractFixtures:
    """Run all line_range_extract fixtures."""

    @pytest.fixture(params=load_all_fixtures("text"))
    def fixture_data(self, request):
        rel_path, data = request.param
        if data.get("tool") != "line_range_extract":
            pytest.skip("Not a line_range_extract fixture")
        return rel_path, data

    def test_line_range_extract(self, fixture_data):
        from eggcalc.exact import line_range_extract

        rel_path, data = fixture_data
        for case in data["cases"]:
            inp = case["input"]
            exp = case["expected"]
            kwargs = {}
            for key in ("line_base", "include_line_numbers", "include_fingerprint"):
                if key in inp:
                    kwargs[key] = inp[key]

            result = line_range_extract(inp["text"], inp["start_line"], inp["end_line"], **kwargs)

            for key, expected_val in exp.items():
                if key == "line_count":
                    actual = len(result.get("lines", []))
                elif key == "lines_0_text":
                    lines = result.get("lines", [])
                    actual = lines[0]["text"] if lines else None
                elif key == "finding_kind":
                    actual_kinds = [f.get("kind") for f in result.get("findings", [])]
                    assert expected_val in actual_kinds, (
                        f"Fixture {rel_path} case '{case['name']}': "
                        f"expected finding kind '{expected_val}' in {actual_kinds}"
                    )
                    continue
                else:
                    actual = get_value(result, key)
                assert actual == expected_val, (
                    f"Fixture {rel_path} case '{case['name']}': "
                    f"expected {key}={expected_val!r}, got {actual!r}"
                )


# ---------------------------------------------------------------------------
# line_range_compare fixtures
# ---------------------------------------------------------------------------


class TestLineRangeCompareFixtures:
    """Run all line_range_compare fixtures."""

    @pytest.fixture(params=load_all_fixtures("text"))
    def fixture_data(self, request):
        rel_path, data = request.param
        if data.get("tool") != "line_range_compare":
            pytest.skip("Not a line_range_compare fixture")
        return rel_path, data

    def test_line_range_compare(self, fixture_data):
        from eggcalc.exact import line_range_compare

        rel_path, data = fixture_data
        for case in data["cases"]:
            inp = case["input"]
            exp = case["expected"]
            kwargs = {}
            for key in ("line_base", "comparison_mode"):
                if key in inp:
                    kwargs[key] = inp[key]

            result = line_range_compare(
                inp["left_text"], inp["right_text"], inp["start_line"], inp["end_line"], **kwargs
            )

            for key, expected_val in exp.items():
                if key == "fingerprints_match":
                    actual = result.get("left_fingerprint") == result.get("right_fingerprint")
                elif key == "first_diff_line":
                    fd = result.get("first_difference")
                    actual = fd.get("line_number") if fd else None
                elif key == "first_diff_left":
                    fd = result.get("first_difference")
                    actual = fd.get("left") if fd else None
                elif key == "first_diff_right":
                    fd = result.get("first_difference")
                    actual = fd.get("right") if fd else None
                elif key == "has_different_lengths":
                    actual = "different lengths" in result.get("diff_summary", "")
                elif key == "left_fingerprint_not_empty":
                    actual = result.get("left_fingerprint", "") != ""
                elif key == "right_fingerprint_not_empty":
                    actual = result.get("right_fingerprint", "") != ""
                else:
                    actual = get_value(result, key)
                assert actual == expected_val, (
                    f"Fixture {rel_path} case '{case['name']}': "
                    f"expected {key}={expected_val!r}, got {actual!r}"
                )


# ---------------------------------------------------------------------------
# path_analyze fixtures
# ---------------------------------------------------------------------------


class TestPathAnalyzeFixtures:
    """Run all path_analyze fixtures."""

    @pytest.fixture(params=load_all_fixtures("paths"))
    def fixture_data(self, request):
        rel_path, data = request.param
        if data.get("tool") != "path_analyze":
            pytest.skip("Not a path_analyze fixture")
        return rel_path, data

    def test_path_analyze(self, fixture_data):
        from eggcalc.exact import path_analyze

        rel_path, data = fixture_data
        for case in data["cases"]:
            inp = case["input"]
            exp = case["expected"]
            result = path_analyze(inp["path"], style=inp.get("style", "auto"))

            for key, expected_val in exp.items():
                if key == "warnings_min":
                    actual = len(result.get("warnings", []))
                    assert actual >= expected_val, (
                        f"Fixture {rel_path} case '{case['name']}': "
                        f"expected warnings >= {expected_val}, got {actual}"
                    )
                    continue
                elif key == "suffixes":
                    actual = result.get("suffixes")
                    assert actual == expected_val, (
                        f"Fixture {rel_path} case '{case['name']}': "
                        f"expected suffixes={expected_val!r}, got {actual!r}"
                    )
                    continue
                else:
                    actual = get_value(result, key)
                assert actual == expected_val, (
                    f"Fixture {rel_path} case '{case['name']}': "
                    f"expected {key}={expected_val!r}, got {actual!r}"
                )


# ---------------------------------------------------------------------------
# path_normalize fixtures
# ---------------------------------------------------------------------------


class TestPathNormalizeFixtures:
    """Run all path_normalize fixtures."""

    @pytest.fixture(params=load_all_fixtures("paths"))
    def fixture_data(self, request):
        rel_path, data = request.param
        if data.get("tool") != "path_normalize":
            pytest.skip("Not a path_normalize fixture")
        return rel_path, data

    def test_path_normalize(self, fixture_data):
        from eggcalc.exact import path_normalize

        rel_path, data = fixture_data
        for case in data["cases"]:
            inp = case["input"]
            exp = case["expected"]
            result = path_normalize(
                inp["path"],
                platform=inp.get("platform", "posix"),
                collapse_dot_segments=inp.get("collapse_dot_segments", True),
                preserve_trailing_separator=inp.get("preserve_trailing_separator", False),
            )

            for key, expected_val in exp.items():
                if key == "warnings_min":
                    actual = len(result.get("warnings", []))
                    assert actual >= expected_val, (
                        f"Fixture {rel_path} case '{case['name']}': "
                        f"expected warnings >= {expected_val}, got {actual}"
                    )
                    continue
                else:
                    actual = get_value(result, key)
                assert actual == expected_val, (
                    f"Fixture {rel_path} case '{case['name']}': "
                    f"expected {key}={expected_val!r}, got {actual!r}"
                )
