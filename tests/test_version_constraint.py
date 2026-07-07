"""Tests for version constraint checking (Phase 11).

Tests for:
- Semver parsing
- Exact version match
- Comparison operators
- Pre-release ordering
- Cargo caret, tilde, wildcard constraints
- Comma-separated ranges
- Invalid inputs and error handling
- MCP wrapper integration
"""

from eggcalc.exact.version import (
    check_version_constraint,
    parse_version,
    version_equal,
    version_gt,
    version_gte,
    version_less_than,
    version_lte,
)


class TestParseVersion:
    """Tests for semver parsing."""

    def test_basic(self):
        v = parse_version("1.2.3")
        assert v is not None
        assert v["major"] == 1
        assert v["minor"] == 2
        assert v["patch"] == 3
        assert v["pre_release"] == []
        assert v["build"] == ""

    def test_with_prerelease(self):
        v = parse_version("1.2.3-alpha.1")
        assert v is not None
        assert v["pre_release"] == ["alpha", "1"]

    def test_prerelease_identifier_may_contain_hyphen(self):
        v = parse_version("1.2.3-alpha-beta.1")
        assert v is not None
        assert v["pre_release"] == ["alpha-beta", "1"]

    def test_with_build(self):
        v = parse_version("1.2.3+build.42")
        assert v is not None
        assert v["build"] == "build.42"
        assert v["pre_release"] == []

    def test_full(self):
        v = parse_version("1.2.3-beta.2+build.42")
        assert v is not None
        assert v["pre_release"] == ["beta", "2"]
        assert v["build"] == "build.42"

    def test_invalid(self):
        assert parse_version("not-a-version") is None
        assert parse_version("") is None
        assert parse_version("1.2") is None
        assert parse_version("01.2.3") is None
        assert parse_version("1.02.3") is None
        assert parse_version("1.2.03") is None
        assert parse_version("1.2.3-alpha..1") is None
        assert parse_version("1.2.3-alpha.01") is None
        assert parse_version("1.2.3+build..42") is None

    def test_whitespace(self):
        v = parse_version("  1.2.3  ")
        assert v is not None
        assert v["major"] == 1

    def test_zeros(self):
        v = parse_version("0.0.0")
        assert v is not None
        assert v["major"] == 0
        assert v["minor"] == 0
        assert v["patch"] == 0


class TestVersionComparison:
    """Tests for version comparison functions."""

    def test_equal(self):
        a = parse_version("1.2.3")
        b = parse_version("1.2.3")
        assert version_equal(a, b)

    def test_equal_prerelease(self):
        a = parse_version("1.2.3-alpha.1")
        b = parse_version("1.2.3-alpha.1")
        assert version_equal(a, b)

    def test_not_equal_prerelease(self):
        a = parse_version("1.2.3-alpha.1")
        b = parse_version("1.2.3-beta.1")
        assert not version_equal(a, b)

    def test_less_than_major(self):
        a = parse_version("1.0.0")
        b = parse_version("2.0.0")
        assert version_less_than(a, b)

    def test_less_than_minor(self):
        a = parse_version("1.2.0")
        b = parse_version("1.3.0")
        assert version_less_than(a, b)

    def test_less_than_patch(self):
        a = parse_version("1.2.3")
        b = parse_version("1.2.4")
        assert version_less_than(a, b)

    def test_less_than_prerelease(self):
        a = parse_version("1.0.0-alpha.1")
        b = parse_version("1.0.0")
        assert version_less_than(a, b)

    def test_prerelease_ordering(self):
        a = parse_version("1.0.0-alpha.1")
        b = parse_version("1.0.0-beta.1")
        c = parse_version("1.0.0-rc.1")
        assert version_less_than(a, b)
        assert version_less_than(b, c)
        assert version_less_than(a, c)

    def test_prerelease_numeric_lexical_mix(self):
        a = parse_version("1.0.0-alpha.1")
        b = parse_version("1.0.0-alpha.2")
        assert version_less_than(a, b)

    def test_prerelease_hyphenated_identifier_ordering(self):
        a = parse_version("1.0.0-alpha")
        b = parse_version("1.0.0-alpha-beta")
        assert version_less_than(a, b)

    def test_gte(self):
        a = parse_version("1.2.3")
        b = parse_version("1.2.3")
        assert version_gte(a, b)
        assert version_gte(parse_version("2.0.0"), b)

    def test_lte(self):
        a = parse_version("1.2.3")
        b = parse_version("1.2.3")
        assert version_lte(a, b)
        assert version_lte(parse_version("0.9.0"), b)

    def test_gt(self):
        assert version_gt(parse_version("2.0.0"), parse_version("1.0.0"))
        assert not version_gt(parse_version("1.0.0"), parse_version("1.0.0"))


class TestSemverConstraints:
    """Tests for semver scheme constraints."""

    def test_exact_match(self):
        result = check_version_constraint("1.2.3", "1.2.3")
        assert result["satisfies"] is True

    def test_exact_no_match(self):
        result = check_version_constraint("1.2.3", "1.2.4")
        assert result["satisfies"] is False

    def test_gte(self):
        result = check_version_constraint("1.5.0", ">=1.2.3")
        assert result["satisfies"] is True

    def test_gte_boundary(self):
        result = check_version_constraint("1.2.3", ">=1.2.3")
        assert result["satisfies"] is True

    def test_gte_fail(self):
        result = check_version_constraint("1.2.2", ">=1.2.3")
        assert result["satisfies"] is False

    def test_gt(self):
        result = check_version_constraint("2.0.0", ">1.2.3")
        assert result["satisfies"] is True

    def test_gt_boundary(self):
        result = check_version_constraint("1.2.3", ">1.2.3")
        assert result["satisfies"] is False

    def test_lte(self):
        result = check_version_constraint("1.2.3", "<=1.2.3")
        assert result["satisfies"] is True

    def test_lte_fail(self):
        result = check_version_constraint("1.2.4", "<=1.2.3")
        assert result["satisfies"] is False

    def test_lt(self):
        result = check_version_constraint("1.2.2", "<1.2.3")
        assert result["satisfies"] is True

    def test_lt_boundary(self):
        result = check_version_constraint("1.2.3", "<1.2.3")
        assert result["satisfies"] is False

    def test_not_equal(self):
        result = check_version_constraint("1.2.3", "!=1.2.4")
        assert result["satisfies"] is True

    def test_not_equal_fail(self):
        result = check_version_constraint("1.2.3", "!=1.2.3")
        assert result["satisfies"] is False

    def test_equal_operator(self):
        result = check_version_constraint("1.2.3", "=1.2.3")
        assert result["satisfies"] is True

    def test_double_equal(self):
        result = check_version_constraint("1.2.3", "==1.2.3")
        assert result["satisfies"] is True

    def test_comma_range(self):
        result = check_version_constraint("1.5.0", ">=1.2,<2.0")
        assert result["satisfies"] is True

    def test_comma_range_lower_exclusive_fail(self):
        result = check_version_constraint("1.0.0", ">=1.2,<2.0")
        assert result["satisfies"] is False

    def test_comma_range_upper_exclusive_fail(self):
        result = check_version_constraint("2.0.0", ">=1.2,<2.0")
        assert result["satisfies"] is False

    def test_prerelease_satisfies(self):
        result = check_version_constraint("1.2.3-alpha.1", ">=1.2.3-alpha.1")
        assert result["satisfies"] is True

    def test_prerelease_less_than_release(self):
        result = check_version_constraint("1.2.3-alpha.1", "<1.2.3")
        assert result["satisfies"] is True

    def test_prerelease_range(self):
        result = check_version_constraint("1.2.3-beta.1", ">=1.2.3-alpha.1,<1.2.3")
        assert result["satisfies"] is True

    def test_invalid_version(self):
        result = check_version_constraint("not-a-version", ">=1.0.0")
        assert result["satisfies"] is False
        assert "Invalid version" in result["explanation"]

    def test_invalid_constraint_version(self):
        result = check_version_constraint("1.2.3", ">=not-a-version")
        assert result["satisfies"] is False

    def test_result_structure(self):
        result = check_version_constraint("1.2.3", ">=1.0.0")
        assert "satisfies" in result
        assert "parsed_version" in result
        assert "parsed_constraint" in result
        assert "scheme" in result
        assert "explanation" in result
        assert "findings" in result
        assert result["scheme"] == "semver"
        assert result["parsed_version"] is not None
        assert result["parsed_constraint"] is not None
        assert result["parsed_constraint"]["type"] == "comparison"
        assert result["parsed_constraint"]["components"][0]["operator"] == ">="


class TestCargoConstraints:
    """Tests for cargo scheme constraints."""

    def test_caret_major(self):
        result = check_version_constraint("1.5.0", "^1.2.3", scheme="cargo")
        assert result["satisfies"] is True

    def test_caret_major_upper(self):
        result = check_version_constraint("2.0.0", "^1.2.3", scheme="cargo")
        assert result["satisfies"] is False

    def test_caret_minor(self):
        result = check_version_constraint("0.2.5", "^0.2.3", scheme="cargo")
        assert result["satisfies"] is True

    def test_caret_minor_upper(self):
        result = check_version_constraint("0.3.0", "^0.2.3", scheme="cargo")
        assert result["satisfies"] is False

    def test_caret_patch(self):
        result = check_version_constraint("0.0.3", "^0.0.3", scheme="cargo")
        assert result["satisfies"] is True

    def test_caret_patch_upper(self):
        result = check_version_constraint("0.0.4", "^0.0.3", scheme="cargo")
        assert result["satisfies"] is False

    def test_caret_zero_zero(self):
        result = check_version_constraint("0.0.0", "^0.0.0", scheme="cargo")
        assert result["satisfies"] is True

    def test_tilde(self):
        result = check_version_constraint("1.2.5", "~1.2.3", scheme="cargo")
        assert result["satisfies"] is True

    def test_tilde_upper(self):
        result = check_version_constraint("1.3.0", "~1.2.3", scheme="cargo")
        assert result["satisfies"] is False

    def test_tilde_major_only(self):
        result = check_version_constraint("1.5.0", "~1", scheme="cargo")
        assert result["satisfies"] is True

    def test_tilde_major_only_upper(self):
        result = check_version_constraint("2.0.0", "~1", scheme="cargo")
        assert result["satisfies"] is False

    def test_wildcard_major(self):
        result = check_version_constraint("1.5.0", "1.*", scheme="cargo")
        assert result["satisfies"] is True

    def test_wildcard_major_upper(self):
        result = check_version_constraint("2.0.0", "1.*", scheme="cargo")
        assert result["satisfies"] is False

    def test_wildcard_minor(self):
        result = check_version_constraint("1.2.5", "1.2.*", scheme="cargo")
        assert result["satisfies"] is True

    def test_wildcard_minor_upper(self):
        result = check_version_constraint("1.3.0", "1.2.*", scheme="cargo")
        assert result["satisfies"] is False

    def test_wildcard_requires_cargo(self):
        result = check_version_constraint("1.5.0", "1.*", scheme="semver")
        assert result["satisfies"] is True
        assert any("cargo" in f for f in result["findings"])

    def test_caret_prerelease(self):
        # Pre-release is less than the base version per semver spec
        # 1.2.3-alpha.1 < 1.2.3, so ^1.2.3 (= >=1.2.3, <2.0.0) does NOT match
        result = check_version_constraint("1.2.3-alpha.1", "^1.2.3", scheme="cargo")
        assert result["satisfies"] is False

    def test_caret_with_prerelease_constraint(self):
        # ^1.2.3-alpha.1 = >=1.2.3-alpha.1, <2.0.0
        result = check_version_constraint("1.2.3-alpha.1", "^1.2.3-alpha.1", scheme="cargo")
        assert result["satisfies"] is True

    def test_tilde_prerelease(self):
        # Pre-release is less than the base version per semver spec
        # 1.2.3-alpha.1 < 1.2.3, so ~1.2.3 (= >=1.2.3, <1.3.0) does NOT match
        result = check_version_constraint("1.2.3-alpha.1", "~1.2.3", scheme="cargo")
        assert result["satisfies"] is False

    def test_tilde_with_prerelease_constraint(self):
        # ~1.2.3-alpha.1 = >=1.2.3-alpha.1, <1.3.0
        result = check_version_constraint("1.2.3-alpha.1", "~1.2.3-alpha.1", scheme="cargo")
        assert result["satisfies"] is True

    def test_caret_result_type(self):
        result = check_version_constraint("1.5.0", "^1.2.3", scheme="cargo")
        assert result["parsed_constraint"] is not None
        assert result["parsed_constraint"]["type"] == "caret"

    def test_tilde_result_type(self):
        result = check_version_constraint("1.2.5", "~1.2.3", scheme="cargo")
        assert result["parsed_constraint"] is not None
        assert result["parsed_constraint"]["type"] == "tilde"

    def test_wildcard_result_type(self):
        result = check_version_constraint("1.5.0", "1.*", scheme="cargo")
        assert result["parsed_constraint"] is not None
        assert result["parsed_constraint"]["type"] == "wildcard"


class TestUnsupportedSchemes:
    """Tests for unsupported schemes and inputs."""

    def test_unsupported_scheme(self):
        result = check_version_constraint("1.2.3", ">=1.0", scheme="pep440")
        assert result["satisfies"] is False
        assert "Unsupported scheme" in result["explanation"]

    def test_empty_version(self):
        result = check_version_constraint("", ">=1.0")
        assert result["satisfies"] is False

    def test_empty_constraint(self):
        result = check_version_constraint("1.2.3", "")
        assert result["satisfies"] is False

    def test_no_operator_exact(self):
        result = check_version_constraint("1.2.3", "1.2.3")
        assert result["satisfies"] is True

    def test_caret_invalid_version(self):
        result = check_version_constraint("1.0.0", "^not-a-version", scheme="cargo")
        assert result["satisfies"] is False


class TestMcpWrapper:
    """Tests for the MCP wrapper function."""

    def test_basic_satisfies(self):
        from eggcalc.mcp.tools import version_constraint_check_mcp

        resp = version_constraint_check_mcp("1.2.3", ">=1.0.0")
        assert resp["ok"] is True
        assert resp["result"]["satisfies"] is True

    def test_basic_fails(self):
        from eggcalc.mcp.tools import version_constraint_check_mcp

        resp = version_constraint_check_mcp("0.9.0", ">=1.0.0")
        assert resp["ok"] is True
        assert resp["result"]["satisfies"] is False

    def test_cargo_scheme(self):
        from eggcalc.mcp.tools import version_constraint_check_mcp

        resp = version_constraint_check_mcp("1.5.0", "^1.2.3", scheme="cargo")
        assert resp["ok"] is True
        assert resp["result"]["satisfies"] is True

    def test_cargo_prerelease_constraint(self):
        from eggcalc.mcp.tools import version_constraint_check_mcp

        resp = version_constraint_check_mcp("1.2.3-alpha.1", "^1.2.3-alpha.1", scheme="cargo")
        assert resp["ok"] is True
        assert resp["result"]["satisfies"] is True

    def test_invalid_scheme(self):
        from eggcalc.mcp.tools import version_constraint_check_mcp

        resp = version_constraint_check_mcp("1.2.3", ">=1.0", scheme="bad")
        assert resp["ok"] is False
        assert resp["error_type"] == "invalid_arguments"

    def test_empty_version(self):
        from eggcalc.mcp.tools import version_constraint_check_mcp

        resp = version_constraint_check_mcp("", ">=1.0")
        assert resp["ok"] is False
        assert resp["error_type"] == "invalid_arguments"

    def test_empty_constraint(self):
        from eggcalc.mcp.tools import version_constraint_check_mcp

        resp = version_constraint_check_mcp("1.2.3", "")
        assert resp["ok"] is False
        assert resp["error_type"] == "invalid_arguments"

    def test_prerelease(self):
        from eggcalc.mcp.tools import version_constraint_check_mcp

        resp = version_constraint_check_mcp("1.0.0-alpha.1", "<1.0.0")
        assert resp["ok"] is True
        assert resp["result"]["satisfies"] is True

    def test_findings_on_prerelease(self):
        from eggcalc.mcp.tools import version_constraint_check_mcp

        resp = version_constraint_check_mcp("1.0.0-alpha.1", "<1.0.0")
        assert resp["ok"] is True
        assert resp["result"]["findings"] == []

    def test_machine_code_not_satisfied(self):
        from eggcalc.mcp.tools import version_constraint_check_mcp

        resp = version_constraint_check_mcp("0.5.0", ">=1.0.0")
        assert resp["ok"] is True
        assert resp["machine_code"] == "CONSTRAINT_NOT_SATISFIED"

    def test_comma_range(self):
        from eggcalc.mcp.tools import version_constraint_check_mcp

        resp = version_constraint_check_mcp("1.5.0", ">=1.2,<2.0")
        assert resp["ok"] is True
        assert resp["result"]["satisfies"] is True
        assert resp["result"]["parsed_constraint"]["type"] == "range"

    def test_invalid_version_in_mcp(self):
        from eggcalc.mcp.tools import version_constraint_check_mcp

        resp = version_constraint_check_mcp("not-a-version", ">=1.0")
        assert resp["ok"] is True
        assert resp["result"]["satisfies"] is False
        assert resp["result"]["parsed_version"] is None

    def test_invalid_constraint_in_mcp(self):
        from eggcalc.mcp.tools import version_constraint_check_mcp

        resp = version_constraint_check_mcp("1.2.3", ">=not-a-version")
        assert resp["ok"] is True
        assert resp["result"]["satisfies"] is False


class TestToolInventory:
    """Verify tool is properly registered."""

    def test_tool_in_schemas(self):
        from eggcalc.mcp.schemas import TOOL_SCHEMAS

        assert "version_constraint_check" in TOOL_SCHEMAS
        schema = TOOL_SCHEMAS["version_constraint_check"]
        assert schema["tier"] == 3
        assert "semver" in str(schema["inputSchema"])
        assert "cargo" in str(schema["inputSchema"])

    def test_tool_in_handlers(self):
        from eggcalc.mcp.server import TOOL_HANDLERS

        assert "version_constraint_check" in TOOL_HANDLERS


class TestVersionCompareSchemes:
    """Tests for version_compare scheme support and boundaries."""

    def test_semver_basic_equal(self):
        from eggcalc.exact.validate import version_compare

        result = version_compare("1.2.3", "1.2.3")
        assert result["comparison"] == 0
        assert result["valid"] is True
        assert result["scheme"] == "semver"

    def test_semver_basic_less(self):
        from eggcalc.exact.validate import version_compare

        result = version_compare("1.2.3", "1.2.4")
        assert result["comparison"] == -1
        assert result["valid"] is True

    def test_semver_basic_greater(self):
        from eggcalc.exact.validate import version_compare

        result = version_compare("2.0.0", "1.0.0")
        assert result["comparison"] == 1
        assert result["valid"] is True

    def test_semver_prerelease_ignored_in_compare(self):
        from eggcalc.exact.validate import version_compare

        result = version_compare("1.0.0-alpha", "1.0.0-beta")
        assert result["comparison"] == 0
        assert result["valid"] is True

    def test_semver_build_metadata_ignored(self):
        from eggcalc.exact.validate import version_compare

        result = version_compare("1.0.0+build.1", "1.0.0+build.2")
        assert result["comparison"] == 0
        assert result["valid"] is True

    def test_semver_invalid_returns_invalid(self):
        from eggcalc.exact.validate import version_compare

        result = version_compare("not-a-version", "1.0.0")
        assert result["valid"] is False
        assert "Invalid semver" in result["summary"]

    def test_semver_both_invalid(self):
        from eggcalc.exact.validate import version_compare

        result = version_compare("foo", "bar")
        assert result["valid"] is False

    def test_loose_basic_equal(self):
        from eggcalc.exact.validate import version_compare

        result = version_compare("1.2.3", "1.2.3", scheme="loose")
        assert result["comparison"] == 0
        assert result["valid"] is True
        assert result["scheme"] == "loose"

    def test_loose_basic_less(self):
        from eggcalc.exact.validate import version_compare

        result = version_compare("1.2.3", "1.2.10", scheme="loose")
        assert result["comparison"] == -1
        assert result["valid"] is True

    def test_loose_numeric_parts_only(self):
        from eggcalc.exact.validate import version_compare

        result = version_compare("1.2.3", "1.2.3.4", scheme="loose")
        assert result["comparison"] == -1

    def test_loose_non_numeric_suffix(self):
        from eggcalc.exact.validate import version_compare

        result = version_compare("1.2.3-beta", "1.2.3-alpha", scheme="loose")
        assert result["comparison"] == 0

    def test_loose_different_lengths(self):
        from eggcalc.exact.validate import version_compare

        result = version_compare("1.2", "1.2.0", scheme="loose")
        assert result["comparison"] == 0

    def test_pep440_rejected_by_validate(self):
        from eggcalc.exact.validate import version_compare

        result = version_compare("1.0.0", "2.0.0", scheme="pep440")
        assert result["valid"] is False
        assert "not supported" in result["summary"].lower()

    def test_unknown_scheme_rejected(self):
        from eggcalc.exact.validate import version_compare

        result = version_compare("1.0.0", "2.0.0", scheme="unknown")
        assert result["valid"] is False


class TestVersionCompareMcpRejection:
    """Tests for MCP wrapper rejection of unsupported schemes."""

    def test_pep440_rejected(self):
        from eggcalc.mcp.tools import version_compare_mcp

        resp = version_compare_mcp("1.0.0", "2.0.0", scheme="pep440")
        assert resp["ok"] is False
        assert resp["error_type"] == "invalid_arguments"
        assert "pep440" in resp["error"].lower()

    def test_unknown_scheme_rejected(self):
        from eggcalc.mcp.tools import version_compare_mcp

        resp = version_compare_mcp("1.0.0", "2.0.0", scheme="bad")
        assert resp["ok"] is False
        assert resp["error_type"] == "invalid_arguments"

    def test_semver_accepted(self):
        from eggcalc.mcp.tools import version_compare_mcp

        resp = version_compare_mcp("1.0.0", "2.0.0", scheme="semver")
        assert resp["ok"] is True
        assert resp["result"]["comparison"] == -1

    def test_loose_accepted(self):
        from eggcalc.mcp.tools import version_compare_mcp

        resp = version_compare_mcp("1.0.0", "2.0.0", scheme="loose")
        assert resp["ok"] is True
        assert resp["result"]["comparison"] == -1

    def test_invalid_input_returns_error(self):
        from eggcalc.mcp.tools import version_compare_mcp

        resp = version_compare_mcp(123, "2.0.0")
        assert resp["ok"] is False


class TestVersionConstraintSchemeRejection:
    """Tests for version_constraint_check rejecting unsupported schemes."""

    def test_pep440_rejected(self):
        from eggcalc.mcp.tools import version_constraint_check_mcp

        resp = version_constraint_check_mcp("1.0.0", ">=1.0", scheme="pep440")
        assert resp["ok"] is False
        assert resp["error_type"] == "invalid_arguments"

    def test_loose_rejected(self):
        from eggcalc.mcp.tools import version_constraint_check_mcp

        resp = version_constraint_check_mcp("1.0.0", ">=1.0", scheme="loose")
        assert resp["ok"] is False
        assert resp["error_type"] == "invalid_arguments"

    def test_semver_accepted(self):
        from eggcalc.mcp.tools import version_constraint_check_mcp

        resp = version_constraint_check_mcp("1.5.0", ">=1.0")
        assert resp["ok"] is True
        assert resp["result"]["satisfies"] is True

    def test_cargo_accepted(self):
        from eggcalc.mcp.tools import version_constraint_check_mcp

        resp = version_constraint_check_mcp("1.5.0", "^1.2.3", scheme="cargo")
        assert resp["ok"] is True
        assert resp["result"]["satisfies"] is True


class TestSemverComparisonTable:
    """Table-driven tests for semver comparison ordering."""

    def _compare(self, a, b):
        from eggcalc.exact.validate import version_compare

        return version_compare(a, b)["comparison"]

    def test_equal_versions(self):
        assert self._compare("1.0.0", "1.0.0") == 0
        assert self._compare("0.0.0", "0.0.0") == 0
        assert self._compare("999.999.999", "999.999.999") == 0

    def test_major_ordering(self):
        assert self._compare("1.0.0", "2.0.0") == -1
        assert self._compare("2.0.0", "1.0.0") == 1

    def test_minor_ordering(self):
        assert self._compare("1.0.0", "1.1.0") == -1
        assert self._compare("1.1.0", "1.0.0") == 1

    def test_patch_ordering(self):
        assert self._compare("1.0.0", "1.0.1") == -1
        assert self._compare("1.0.1", "1.0.0") == 1


class TestLooseComparisonTable:
    """Table-driven tests for loose comparison ordering."""

    def _compare(self, a, b):
        from eggcalc.exact.validate import version_compare

        return version_compare(a, b, scheme="loose")["comparison"]

    def test_equal(self):
        assert self._compare("1.0.0", "1.0.0") == 0

    def test_different_lengths(self):
        assert self._compare("1.0", "1.0.0") == 0
        assert self._compare("1.0.0", "1.0.0.0") == 0

    def test_numeric_dominance(self):
        assert self._compare("1.2.3", "1.2.10") == -1
        assert self._compare("1.2.10", "1.2.3") == 1

    def test_non_numeric_ignored(self):
        assert self._compare("1.0.0-alpha", "1.0.0") == 0
        assert self._compare("1.0.0+build", "1.0.0") == 0


class TestConstraintOperators:
    """Table-driven tests for all supported constraint operators."""

    def test_exact_equal(self):
        result = check_version_constraint("1.2.3", "1.2.3")
        assert result["satisfies"] is True

    def test_exact_not_equal(self):
        result = check_version_constraint("1.2.3", "1.2.4")
        assert result["satisfies"] is False

    def test_operator_eq(self):
        assert check_version_constraint("1.0.0", "=1.0.0")["satisfies"] is True
        assert check_version_constraint("1.0.0", "=1.0.1")["satisfies"] is False

    def test_operator_double_eq(self):
        assert check_version_constraint("1.0.0", "==1.0.0")["satisfies"] is True
        assert check_version_constraint("1.0.0", "==1.0.1")["satisfies"] is False

    def test_operator_ne(self):
        assert check_version_constraint("1.0.0", "!=1.0.0")["satisfies"] is False
        assert check_version_constraint("1.0.0", "!=1.0.1")["satisfies"] is True

    def test_operator_gt(self):
        assert check_version_constraint("1.0.1", ">1.0.0")["satisfies"] is True
        assert check_version_constraint("1.0.0", ">1.0.0")["satisfies"] is False
        assert check_version_constraint("0.9.9", ">1.0.0")["satisfies"] is False

    def test_operator_gte(self):
        assert check_version_constraint("1.0.0", ">=1.0.0")["satisfies"] is True
        assert check_version_constraint("1.0.1", ">=1.0.0")["satisfies"] is True
        assert check_version_constraint("0.9.9", ">=1.0.0")["satisfies"] is False

    def test_operator_lt(self):
        assert check_version_constraint("0.9.9", "<1.0.0")["satisfies"] is True
        assert check_version_constraint("1.0.0", "<1.0.0")["satisfies"] is False
        assert check_version_constraint("1.0.1", "<1.0.0")["satisfies"] is False

    def test_operator_lte(self):
        assert check_version_constraint("1.0.0", "<=1.0.0")["satisfies"] is True
        assert check_version_constraint("0.9.9", "<=1.0.0")["satisfies"] is True
        assert check_version_constraint("1.0.1", "<=1.0.0")["satisfies"] is False

    def test_comma_range_all_satisfied(self):
        result = check_version_constraint("1.5.0", ">=1.0.0,<2.0.0")
        assert result["satisfies"] is True

    def test_comma_range_lower_fail(self):
        result = check_version_constraint("0.9.0", ">=1.0.0,<2.0.0")
        assert result["satisfies"] is False

    def test_comma_range_upper_fail(self):
        result = check_version_constraint("2.0.0", ">=1.0.0,<2.0.0")
        assert result["satisfies"] is False
