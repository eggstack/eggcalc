"""Authority consolidation invariants (plan 034).

Covers:
- RFC 6901 JSON Pointer parity: json_query delegates to json_extract.
- SemVer authority: version_compare(scheme="semver") uses exact.version.
- Protocol authority: server/capabilities equal _protocol.
"""

from __future__ import annotations


class TestJsonPointerParity:
    """Shared RFC 6901 fixture corpus for json_extract / json_query."""

    def _query(self, text: str, pointer: str = ""):
        from eggcalc.exact.validate import json_query

        return json_query(text, pointer)

    def _extract(self, text: str, pointer: str = "", **kwargs):
        from eggcalc.exact.validate import json_extract

        return json_extract(text, pointer, **kwargs)

    def _assert_parity(self, text: str, pointer: str):
        ex = self._extract(text, pointer)
        q = self._query(text, pointer)
        assert q["pointer"] == ex["pointer"] == pointer
        assert q["found"] == ex["found"]
        if not ex["valid_json"]:
            assert q["reason"] == "invalid_json"
            assert q["type"] is None
            assert q["error"] == ex["error"]
            assert q["line"] == ex["line"]
            assert q["column"] == ex["column"]
            return
        if not ex["found"]:
            assert q["reason"] == ex["reason"]
            assert q["missing_at"] == ex["missing_at"]
            assert q["type"] == ex["value_type"]
            return
        # Found: value identical; type folds integer -> number.
        assert q["value"] == ex["value"]
        expected_type = "number" if ex["value_type"] in ("integer", "number") else ex["value_type"]
        assert q["type"] == expected_type

    def test_empty_pointer_root(self):
        self._assert_parity('{"foo": "bar"}', "")
        ex = self._extract('{"foo": "bar"}', "")
        assert ex["found"] is True
        assert ex["valid_json"] is True

    def test_object_key_lookup(self):
        self._assert_parity('{"foo": "bar", "baz": 123}', "/foo")
        q = self._query('{"foo": "bar"}', "/foo")
        assert q["value"] == "bar"
        assert q["type"] == "string"

    def test_array_indexes(self):
        self._assert_parity('{"items": [10, 20, 30]}', "/items/1")
        q = self._query('{"items": [10, 20, 30]}', "/items/1")
        assert q["value"] == 20
        # Historical query contract reports ints as "number".
        assert q["type"] == "number"
        ex = self._extract('{"items": [10, 20, 30]}', "/items/1")
        assert ex["value_type"] == "integer"

    def test_tilde_escapes(self):
        self._assert_parity('{"a~b": "tilde_value"}', "/a~0b")
        self._assert_parity('{"a/b": "slash_value"}', "/a~1b")

    def test_empty_key(self):
        self._assert_parity('{"": "empty"}', "/")

    def test_missing_object_key(self):
        self._assert_parity('{"foo": "bar"}', "/missing")
        q = self._query('{"foo": "bar"}', "/missing")
        assert q["reason"] == "key_not_found"
        assert q["type"] == "object"

    def test_invalid_array_index(self):
        self._assert_parity('{"items": [1, 2]}', "/items/10")
        q = self._query('{"items": [1, 2]}', "/items/10")
        assert q["reason"] == "index_out_of_range"

    def test_pointer_syntax_error_non_integer_index(self):
        self._assert_parity('{"items": [1, 2]}', "/items/abc")
        q = self._query('{"items": [1, 2]}', "/items/abc")
        assert q["reason"] == "invalid_pointer_syntax"

    def test_scalar_traversal_failure(self):
        self._assert_parity('{"a": 1}', "/a/b")
        q = self._query('{"a": 1}', "/a/b")
        assert q["found"] is False
        assert q["reason"] == "invalid_pointer_syntax"

    def test_malformed_json(self):
        self._assert_parity('{"invalid": json}', "")
        q = self._query('{"invalid": json}', "")
        assert q["reason"] == "invalid_json"

    def test_truncation_only_in_extract(self):
        from eggcalc.exact.validate import json_extract

        big = {"key": "x" * 5000}
        import json as _json

        text = _json.dumps(big)
        full = json_extract(text, "/key", max_output_chars=4000)
        assert full["found"] is True
        assert full["truncated"] is True
        assert full["value"] == "x" * 5000
        # Query adapter preserves the full value (no max_output_chars param).
        q = self._query(text, "/key")
        assert q["value"] == "x" * 5000

    def test_nested_path(self):
        self._assert_parity('{"a": {"b": {"c": 42}}}', "/a/b/c")


class TestSemVerAuthority:
    """SemVer corpus: version_compare agrees with exact.version."""

    def _compare(self, a: str, b: str) -> int:
        from eggcalc.exact.validate import version_compare

        return version_compare(a, b)["comparison"]  # type: ignore[return-value]

    def test_equal(self):
        assert self._compare("1.0.0", "1.0.0") == 0

    def test_major_minor_patch_ordering(self):
        assert self._compare("1.0.0", "2.0.0") == -1
        assert self._compare("2.0.0", "1.0.0") == 1
        assert self._compare("1.0.0", "1.1.0") == -1
        assert self._compare("1.1.0", "1.0.0") == 1
        assert self._compare("1.0.0", "1.0.1") == -1
        assert self._compare("1.0.1", "1.0.0") == 1

    def test_prerelease_lower_than_release(self):
        assert self._compare("1.0.0-alpha", "1.0.0") == -1
        assert self._compare("1.0.0", "1.0.0-alpha") == 1

    def test_prerelease_identifier_ordering(self):
        assert self._compare("1.0.0-alpha", "1.0.0-beta") == -1
        assert self._compare("1.0.0-alpha.1", "1.0.0-alpha.2") == -1
        assert self._compare("1.0.0-alpha", "1.0.0-alpha.1") == -1

    def test_numeric_vs_alphanumeric_identifiers(self):
        # Numeric identifiers sort lower than alphanumeric per SemVer.
        assert self._compare("1.0.0-1", "1.0.0-alpha") == -1
        assert self._compare("1.0.0-alpha", "1.0.0-1") == 1

    def test_multiple_prerelease_components(self):
        assert self._compare("1.0.0-alpha.1.2", "1.0.0-alpha.1.10") == -1

    def test_build_metadata_ignored(self):
        assert self._compare("1.0.0+build.1", "1.0.0+build.2") == 0
        assert self._compare("1.0.0-alpha+build", "1.0.0-alpha") == 0

    def test_malformed_versions_invalid(self):
        from eggcalc.exact.validate import version_compare

        for bad in ("not-a-version", "1.2", "1.2.3.4", "v1.2.3", ""):
            result = version_compare(bad, "1.0.0")
            assert result["valid"] is False, bad

    def test_agrees_with_canonical_comparator(self):
        from eggcalc.exact.validate import version_compare
        from eggcalc.exact.version import compare_versions, parse_version

        pairs = [
            ("1.0.0", "1.0.0"),
            ("1.0.0-alpha", "1.0.0"),
            ("1.0.0-alpha", "1.0.0-beta"),
            ("1.0.0-alpha.1", "1.0.0-alpha.2"),
            ("1.0.0-1", "1.0.0-alpha"),
            ("1.0.0+build.1", "1.0.0+build.2"),
            ("2.1.3-rc.1", "2.1.3"),
        ]
        for a, b in pairs:
            pa = parse_version(a)
            pb = parse_version(b)
            assert pa is not None and pb is not None
            assert version_compare(a, b)["comparison"] == compare_versions(pa, pb)

    def test_cargo_constraint_versions_do_not_diverge(self):
        # Versions exercised by Cargo constraint tests must parse identically.
        from eggcalc.exact.version import parse_version

        for v in ("1.2.3", "0.2.3", "0.0.3", "1.2.3-alpha.1", "1.5.0"):
            assert parse_version(v) is not None

    def test_loose_preserved(self):
        from eggcalc.exact.validate import version_compare

        assert version_compare("1.2", "1.2.0", scheme="loose")["comparison"] == 0
        assert version_compare("1.2.3", "1.2.10", scheme="loose")["comparison"] == -1
        assert version_compare("1.2.3-beta", "1.2.3-alpha", scheme="loose")["comparison"] == 0


class TestProtocolAuthority:
    """Protocol versions live in _protocol; server/capabilities import them."""

    def test_server_matches_protocol(self):
        from eggcalc import _protocol
        from eggcalc.mcp.server import (
            LATEST_SUPPORTED_PROTOCOL_VERSION,
            SUPPORTED_PROTOCOL_VERSIONS,
        )

        assert tuple(SUPPORTED_PROTOCOL_VERSIONS) == tuple(_protocol.SUPPORTED_PROTOCOL_VERSIONS)
        assert LATEST_SUPPORTED_PROTOCOL_VERSION == _protocol.LATEST_SUPPORTED_PROTOCOL_VERSION

    def test_capabilities_matches_protocol(self):
        from eggcalc import _protocol
        from eggcalc.capabilities import detect_capabilities

        caps = detect_capabilities()
        assert tuple(caps.supported_protocol_versions) == tuple(
            _protocol.SUPPORTED_PROTOCOL_VERSIONS
        )


class TestMcpExposure:
    """Deprecated json_query must not be preferred over json_extract."""

    def test_tier_not_preferred(self):
        from eggcalc.mcp.schemas import TOOL_METADATA, TOOL_SCHEMAS

        assert TOOL_SCHEMAS["json_query"]["tier"] >= TOOL_SCHEMAS["json_extract"]["tier"]
        assert TOOL_METADATA["json_query"]["tier"] >= TOOL_METADATA["json_extract"]["tier"]
        assert TOOL_METADATA["json_query"]["stability"] == "deprecated"
        assert TOOL_SCHEMAS["json_query"].get("deprecated") is True

    def test_json_query_not_in_default_profile(self):
        from eggcalc.mcp.schemas import TOOL_METADATA

        assert "default" not in TOOL_METADATA["json_query"]["profiles"]

    def test_json_query_marks_replacement(self):
        from eggcalc.mcp.tools import json_query as json_query_tool

        resp = json_query_tool('{"a": 1}', "/a")
        assert resp["ok"] is True
        assert resp.get("recommended_next_tool") == "json_extract"
        assert any("json_extract" in w for w in resp.get("warnings", []))
