"""
Regression tests for the 2026-07-b production review findings.

Each test class is named after the bug it locks in. The tests use the
public API (or the MCP server entry point) and assert the expected
post-fix behavior. They will FAIL on the unfixed code.
"""

from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("EGGCALC_NO_CONFIG", "1")


# ---------------------------------------------------------------------------
# B1: JSON-RPC id must reject booleans
# ---------------------------------------------------------------------------
class TestJSONRPCBoolID:
    """server.py handle_request: bool ids are not valid per JSON-RPC 2.0."""

    def test_bool_true_rejected(self):
        from eggcalc.mcp.server import handle_request
        r = handle_request({
            "jsonrpc": "2.0", "id": True, "method": "ping", "params": {},
        })
        assert "error" in r, f"bool id should be rejected, got: {r}"
        assert r["error"]["code"] == -32600
        assert "id" in r["error"]["message"].lower()

    def test_bool_false_rejected(self):
        from eggcalc.mcp.server import handle_request
        r = handle_request({
            "jsonrpc": "2.0", "id": False, "method": "ping", "params": {},
        })
        assert "error" in r, f"bool id should be rejected, got: {r}"
        assert r["error"]["code"] == -32600

    def test_int_id_still_accepted(self):
        from eggcalc.mcp.server import handle_request
        r = handle_request({
            "jsonrpc": "2.0", "id": 42, "method": "ping", "params": {},
        })
        assert "result" in r
        assert r["id"] == 42

    def test_string_id_still_accepted(self):
        from eggcalc.mcp.server import handle_request
        r = handle_request({
            "jsonrpc": "2.0", "id": "abc", "method": "ping", "params": {},
        })
        assert "result" in r
        assert r["id"] == "abc"


# ---------------------------------------------------------------------------
# B2: identifier_table_inspect local variable shadow
# ---------------------------------------------------------------------------
class TestIdentifierTableInspectLanguage:
    """tools.py identifier_table_inspect_mcp must use the top-level
    language parameter, not the per-entry language field."""

    def test_default_language_is_python(self):
        from eggcalc.mcp.server import handle_request
        r = handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {
                "name": "identifier_table_inspect",
                "arguments": {
                    "identifiers": [{"name": "for"}, {"name": "x"}],
                },
            },
        })
        text = json.loads(r["result"]["content"][0]["text"])
        assert text["ok"], text
        # 'for' is a Python keyword; default language is python
        hits = text["result"].get("reserved_keyword_hits", [])
        names = {h["name"] for h in hits}
        assert "for" in names, f"expected 'for' to be flagged, got {hits}"

    def test_explicit_language_works(self):
        from eggcalc.mcp.server import handle_request
        r = handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {
                "name": "identifier_table_inspect",
                "arguments": {
                    "identifiers": [{"name": "x"}],
                    "language": "rust",
                },
            },
        })
        text = json.loads(r["result"]["content"][0]["text"])
        assert text["ok"], text


# ---------------------------------------------------------------------------
# B3: patch_summary must not report renames for normal diffs
# ---------------------------------------------------------------------------
class TestPatchSummaryRenames:
    """patch.py: --- a\\n+++ b headers are file names, not renames."""

    def test_simple_diff_not_a_rename(self):
        from eggcalc.mcp.server import handle_request
        r = handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {
                "name": "patch_summary",
                "arguments": {
                    "patch_text": (
                        "--- a/foo.txt\n"
                        "+++ b/foo.txt\n"
                        "@@ -1,1 +1,1 @@\n"
                        "-old\n"
                        "+new\n"
                    ),
                },
            },
        })
        text = json.loads(r["result"]["content"][0]["text"])
        assert text["ok"], text
        assert text["result"]["renames_detected"] == [], (
            f"normal diff should not be reported as a rename, "
            f"got {text['result']['renames_detected']}"
        )

    def test_same_filename_not_a_rename(self):
        from eggcalc.mcp.server import handle_request
        r = handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {
                "name": "patch_summary",
                "arguments": {
                    "patch_text": (
                        "--- foo\n"
                        "+++ foo\n"
                        "@@ -1,1 +1,1 @@\n"
                        "-old\n"
                        "+new\n"
                    ),
                },
            },
        })
        text = json.loads(r["result"]["content"][0]["text"])
        assert text["ok"], text
        assert text["result"]["renames_detected"] == []


# ---------------------------------------------------------------------------
# B4: setvar() public API must enforce MAX_USER_VARIABLES
# ---------------------------------------------------------------------------
class TestSetvarPublicAPICap:
    """evaluator.py: public setvar() must respect the documented cap."""

    def test_cap_enforced(self):
        from eggcalc import clearvars, setvar
        from eggcalc.evaluator import MAX_USER_VARIABLES, _default_evaluator

        clearvars()
        # Setting more than the cap should still work but evict the oldest
        for i in range(MAX_USER_VARIABLES + 50):
            setvar(f"v{i}", i)

        size = len(_default_evaluator._user_variables)
        assert size <= MAX_USER_VARIABLES, (
            f"setvar() must enforce the {MAX_USER_VARIABLES} cap, "
            f"got {size} entries"
        )
        # The oldest entries should have been evicted
        assert _default_evaluator._user_variables.get("v0") is None, (
            "v0 should have been evicted as the oldest entry"
        )
        # The most recent should be present
        assert _default_evaluator._user_variables.get(
            f"v{MAX_USER_VARIABLES + 49}"
        ) is not None
        clearvars()

    def test_name_must_be_identifier(self):
        from eggcalc import EvaluationError, setvar
        with pytest.raises(EvaluationError):
            setvar("", 5)
        with pytest.raises(EvaluationError):
            setvar("123abc", 5)
        with pytest.raises(EvaluationError):
            setvar("with space", 5)


# ---------------------------------------------------------------------------
# B5: UnitValue loses unit on dimensionless / unit division
# ---------------------------------------------------------------------------
class TestUnitValueDimensionlessDivUnit:
    """units.py: 1 / m should produce a unit of '1/m' or 'm**-1', not None."""

    def test_dimensionless_div_unit_preserves_unit(self):
        from eggcalc.units import UnitValue
        result = UnitValue(1, None) / UnitValue(1, "m")
        assert result.unit is not None, (
            f"1/m should have a unit, got {result.unit!r}"
        )
        assert result.value == 1.0

    def test_unit_div_dimensionless_preserves_unit(self):
        from eggcalc.units import UnitValue
        # 2m / 1 = 2m (already works)
        result = UnitValue(2, "m") / 1
        assert result.unit == "m"


# ---------------------------------------------------------------------------
# B6: compound units (m**2, m**3, m/s**2) have no category
# ---------------------------------------------------------------------------
class TestCompoundUnitCategory:
    """units.py: derived units must be categorizable so addition works."""

    def test_m_squared_has_category(self):
        from eggcalc.units import get_unit_category
        cat = get_unit_category("m**2")
        assert cat is not None, "m**2 must have a category for area"

    def test_m_squared_self_addition(self):
        from eggcalc.units import UnitValue
        r = UnitValue(5, "m**2") + UnitValue(3, "m**2")
        assert r.value == 8
        # 8 m**2 in some normalized form
        assert r.unit is not None

    def test_m_squared_to_cm_squared_conversion_factor(self):
        from eggcalc.units import get_conversion_factor
        f = get_conversion_factor("m**2", "cm**2")
        assert f == 10000.0, f"m**2 -> cm**2 factor should be 10000, got {f}"

    def test_m_per_s_squared_has_category(self):
        from eggcalc.units import get_unit_category
        cat = get_unit_category("m/s**2")
        assert cat is not None, "m/s**2 must have a category for acceleration"
