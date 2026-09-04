"""Command and capabilities inventory parity tests.

Verifies that every CLI text command has a corresponding MCP tool and
that both surfaces stay in sync.  Also checks that RuntimeCapabilities
fields are stable and JSON-serializable.
"""

from __future__ import annotations

import json

import pytest

from eggcalc.capabilities import detect_capabilities
from eggcalc.cli import COMMANDS
from eggcalc.mcp.schemas import TOOL_SCHEMAS

# ---------------------------------------------------------------------------
# CLI command → MCP tool mapping
# ---------------------------------------------------------------------------

# Every CLI command must have an MCP tool with the same handler symbol.
# This dict is the authoritative mapping; add new commands/tools here.
_CLI_TO_MCP: dict[str, str] = {
    "inspect": "text_inspect",
    "count": "text_count",
    "regex": "validate_regex",
    "replace-check": "text_replace_check",
    "lines": "line_range_extract",
    "patch-check": "patch_apply_check",
    "shell-split": "shell_split",
    "md-structure": "markdown_structure",
    "dotenv-check": "dotenv_validate",
}


class TestCLICommandToMCPParity:
    """Every CLI command must have a corresponding MCP tool."""

    def test_all_cli_commands_have_mcp_mapping(self):
        cli_names = {spec["name"] for spec in COMMANDS}
        mapped = set(_CLI_TO_MCP.keys())
        missing = cli_names - mapped
        assert not missing, (
            f"CLI commands without MCP mapping: {missing}. "
            f"Add them to _CLI_TO_MCP in this test file."
        )

    def test_all_mcp_mappings_reference_existing_tools(self):
        for cli_name, mcp_tool in _CLI_TO_MCP.items():
            assert mcp_tool in TOOL_SCHEMAS, (
                f"CLI command {cli_name!r} maps to MCP tool {mcp_tool!r} "
                f"which does not exist in TOOL_SCHEMAS"
            )

    @pytest.mark.parametrize(
        "cli_name,mcp_tool",
        list(_CLI_TO_MCP.items()),
        ids=[f"{k}->{v}" for k, v in _CLI_TO_MCP.items()],
    )
    def test_mcp_tool_has_input_schema(self, cli_name: str, mcp_tool: str):
        schema = TOOL_SCHEMAS[mcp_tool]
        assert "inputSchema" in schema, (
            f"MCP tool {mcp_tool!r} (mapped from CLI {cli_name!r}) " f"has no inputSchema"
        )

    def test_no_duplicate_mcp_targets(self):
        values = list(_CLI_TO_MCP.values())
        dupes = [v for v in values if values.count(v) > 1]
        assert not dupes, f"Duplicate MCP tool targets: {set(dupes)}"


# ---------------------------------------------------------------------------
# MCP tools not exposed via CLI (expected extras)
# ---------------------------------------------------------------------------

_MCP_EXTRAS_EXPECTED = {
    "math_eval",
    "unit_convert",
    "unit_info",
    "constant_lookup",
    "text_measure",
    "text_equal",
    "text_diff_explain",
    "text_truncate",
    "text_transform",
    "text_position",
    "text_hash",
    "text_fingerprint",
    "text_window",
    "escape_text",
    "unescape_text",
    "text_security_inspect",
    "prompt_input_inspect",
    "line_range_compare",
    "validate_brackets",
    "validate_json",
    "validate_toml",
    "validate_schema_light",
    "regex_finditer",
    "regex_safety_check",
    "json_extract",
    "json_compare",
    "json_canonicalize",
    "json_shape",
    "json_query",
    "path_normalize",
    "path_analyze",
    "path_compare",
    "path_scope_check",
    "shell_quote_join",
    "argv_compare",
    "list_compare",
    "list_dedupe",
    "list_sort",
    "identifier_inspect",
    "identifier_analyze",
    "identifier_table_inspect",
    "code_fence_extract",
    "markdown_link_check_lexical",
    "patch_summary",
    "patch_conflict_markers_inspect",
    "diff_touched_paths",
    "diff_hunk_ranges",
    "diff_file_headers",
    "unified_diff_validate",
    "ini_validate",
    "toml_shape",
    "version_compare",
    "version_constraint_check",
    "glob_match",
    "pyproject_inspect",
    "package_json_inspect",
    "requirements_inspect",
    "go_mod_inspect",
    "lockfile_summary",
    "cargo_toml_inspect",
    "unicode_policy_check",
    "canonicalize_text",
    "llm_json_output_check",
    "edit_preflight",
    "command_preflight",
    "config_preflight",
    "structured_data_compare",
    "repo_file_inventory",
    "ip_inspect",
    "cidr_inspect",
    "codec_convert",
    "radix_convert",
    "datetime_convert",
    "cron_inspect",
}


class TestMCPExtraToolsDocumented:
    """MCP tools beyond the CLI mapping must be in the expected extras set."""

    def test_all_mcp_tools_accounted_for(self):
        cli_targets = set(_CLI_TO_MCP.values())
        all_tools = set(TOOL_SCHEMAS.keys())
        extras = all_tools - cli_targets
        unknown = extras - _MCP_EXTRAS_EXPECTED
        assert not unknown, (
            f"New MCP tools not in _MCP_EXTRAS_EXPECTED: {unknown}. "
            f"Add them to the expected set."
        )

    def test_expected_extras_still_exist(self):
        cli_targets = set(_CLI_TO_MCP.values())
        all_tools = set(TOOL_SCHEMAS.keys())
        extras = all_tools - cli_targets
        missing = _MCP_EXTRAS_EXPECTED - extras
        assert not missing, (
            f"Expected MCP extras no longer present (removed from schemas?): " f"{missing}"
        )


# ---------------------------------------------------------------------------
# RuntimeCapabilities stability
# ---------------------------------------------------------------------------


class TestCapabilitiesStability:
    """RuntimeCapabilities must be JSON-serializable and have stable keys."""

    def test_to_dict_has_all_fields(self):
        caps = detect_capabilities()
        d = caps.to_dict()
        expected_keys = {
            "python_version",
            "platform",
            "implementation",
            "has_tomllib",
            "has_math_cbrt",
            "supports_fork",
            "supports_spawn",
            "supports_posix_paths",
            "supports_windows_paths",
            "eggcalc_version",
            "supported_protocol_versions",
            "multiprocessing_start_method",
            "mode",
        }
        assert set(d.keys()) == expected_keys

    def test_to_json_is_valid_json(self):
        caps = detect_capabilities()
        raw = caps.to_json()
        parsed = json.loads(raw)
        assert isinstance(parsed, dict)
        assert "python_version" in parsed
        assert "platform" in parsed

    def test_to_json_indent(self):
        caps = detect_capabilities()
        raw = caps.to_json(indent=2)
        parsed = json.loads(raw)
        assert isinstance(parsed, dict)

    def test_frozen_dataclass(self):
        caps = detect_capabilities()
        with pytest.raises(AttributeError):
            caps.platform = "nope"  # type: ignore[misc]
