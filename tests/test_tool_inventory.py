"""Tests for MCP tool registry consistency (Plan 040 authority model).

Ensures that the catalog metadata authority, protocol schemas, derived
handlers, and compatibility snapshot stay in sync.

Authority model:
- TOOL_METADATA owns canonical names, handler locators, and
  selection metadata (tier/tags/category/profiles/...).
- TOOL_SCHEMAS owns protocol shape only (description/inputSchema/
  outputSchema/deprecated).
- TOOL_HANDLERS is derived from TOOL_METADATA handler locators.
- tests/fixtures/mcp_tool_registry_expected.json is a golden
  compatibility snapshot (review-visible public-name set), not runtime
  source of truth.
"""

import json
import pathlib
import re

from eggcalc.mcp.schemas import TOOL_METADATA, TOOL_PROFILES, TOOL_SCHEMAS
from eggcalc.mcp.server import TOOL_HANDLERS

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
EXPECTED_REGISTRY = json.loads((FIXTURES / "mcp_tool_registry_expected.json").read_text())
EXPECTED_TOOLS = sorted(EXPECTED_REGISTRY["tools"])

# Paths to all relevant registries
_INVENTORY_DOC = FIXTURES.parent.parent / "docs" / "tool_inventory.md"
_MCP_DOC = FIXTURES.parent.parent / "docs" / "mcp.md"


class TestToolRegistryFixture:
    """Verify the fixture itself is well-formed (compatibility snapshot)."""

    def test_fixture_has_tools_key(self):
        assert "tools" in EXPECTED_REGISTRY

    def test_fixture_has_schema_version_and_count(self):
        assert EXPECTED_REGISTRY.get("schema_version") == 1
        assert EXPECTED_REGISTRY.get("tool_count") == len(EXPECTED_TOOLS)

    def test_fixture_has_at_least_one_tool(self):
        assert len(EXPECTED_TOOLS) > 0

    def test_fixture_tool_names_are_strings(self):
        for name in EXPECTED_TOOLS:
            assert isinstance(name, str)
            assert name  # non-empty


class TestRuntimeRegistry:
    """Ensure the runtime TOOL_HANDLERS matches the canonical list."""

    def test_handlers_match_expected_names(self):
        actual = sorted(TOOL_HANDLERS.keys())
        assert actual == EXPECTED_TOOLS, (
            f"TOOL_HANDLERS keys differ from fixture.\n"
            f"  Missing from handlers: {set(EXPECTED_TOOLS) - set(actual)}\n"
            f"  Extra in handlers:     {set(actual) - set(EXPECTED_TOOLS)}"
        )

    def test_every_expected_handler_is_callable(self):
        for name in EXPECTED_TOOLS:
            handler = TOOL_HANDLERS[name]
            assert callable(handler), f"Handler for '{name}' is not callable"


class TestSchemaConsistency:
    """Ensure every registered tool has a schema entry."""

    def test_every_handler_has_schema(self):
        schema_keys = set(TOOL_SCHEMAS.keys())
        missing = set(TOOL_HANDLERS.keys()) - schema_keys
        assert not missing, f"Handlers without schemas: {sorted(missing)}"

    def test_every_expected_tool_has_schema(self):
        schema_keys = set(TOOL_SCHEMAS.keys())
        missing = set(EXPECTED_TOOLS) - schema_keys
        assert not missing, f"Expected tools without schemas: {sorted(missing)}"

    def test_schemas_have_description(self):
        for name, schema in TOOL_SCHEMAS.items():
            assert "description" in schema, f"Schema for '{name}' missing 'description'"

    def test_schemas_have_input_schema(self):
        for name, schema in TOOL_SCHEMAS.items():
            assert "inputSchema" in schema, f"Schema for '{name}' missing 'inputSchema'"


class TestTierConsistency:
    """Verify tier/tags live in TOOL_METADATA only (Plan 040 single authority)."""

    def test_all_tiers_are_valid(self):
        for name, meta in TOOL_METADATA.items():
            tier = meta.get("tier")
            assert isinstance(tier, int), f"Tier for '{name}' is not int: {tier}"
            assert 0 <= tier <= 3, f"Tier for '{name}' out of range: {tier}"

    def test_all_tags_are_string_lists(self):
        for name, meta in TOOL_METADATA.items():
            tags = meta.get("tags")
            assert isinstance(tags, list), f"Tags for '{name}' must be list"
            assert all(isinstance(t, str) for t in tags), f"Tags for '{name}'"

    def test_schemas_have_no_tier_or_tags(self):
        for name, schema in TOOL_SCHEMAS.items():
            assert "tier" not in schema, (
                f"Schema for '{name}' must not contain authored 'tier' "
                "(authority: TOOL_METADATA)"
            )
            assert "tags" not in schema, (
                f"Schema for '{name}' must not contain authored 'tags' "
                "(authority: TOOL_METADATA)"
            )


class TestSourceOfTruthConsistency:
    """Compatibility snapshot checks (Plan 040 Workstream D).

    Runtime names come from the TOOL_METADATA catalog authority. The JSON
    fixture is a golden compatibility snapshot: CI compares the derived
    set against it so public additions/removals are explicit in review.
    It never constructs runtime behavior.
    """

    def test_handlers_and_schemas_match(self):
        handler_keys = set(TOOL_HANDLERS.keys())
        schema_keys = set(TOOL_SCHEMAS.keys())
        assert handler_keys == schema_keys, (
            f"TOOL_HANDLERS and TOOL_SCHEMAS disagree.\n"
            f"  In handlers only: {sorted(handler_keys - schema_keys)}\n"
            f"  In schemas only:  {sorted(schema_keys - handler_keys)}"
        )

    def test_fixture_matches_handlers(self):
        fixture_set = set(EXPECTED_TOOLS)
        handler_set = set(TOOL_HANDLERS.keys())
        assert fixture_set == handler_set, (
            f"Fixture and TOOL_HANDLERS disagree.\n"
            f"  In fixture only:  {sorted(fixture_set - handler_set)}\n"
            f"  In handlers only: {sorted(handler_set - fixture_set)}"
        )

    def test_fixture_matches_schemas(self):
        fixture_set = set(EXPECTED_TOOLS)
        schema_set = set(TOOL_SCHEMAS.keys())
        assert fixture_set == schema_set, (
            f"Fixture and TOOL_SCHEMAS disagree.\n"
            f"  In fixture only: {sorted(fixture_set - schema_set)}\n"
            f"  In schemas only: {sorted(schema_set - fixture_set)}"
        )

    def test_fixture_is_alphabetically_sorted(self):
        assert EXPECTED_TOOLS == sorted(
            EXPECTED_TOOLS
        ), "Fixture tools list is not alphabetically sorted"

    def test_fixture_count_matches_handlers(self):
        assert len(EXPECTED_TOOLS) == len(
            TOOL_HANDLERS
        ), f"Fixture has {len(EXPECTED_TOOLS)} tools, handlers has {len(TOOL_HANDLERS)}"

    def test_fixture_count_matches_schemas(self):
        assert len(EXPECTED_TOOLS) == len(
            TOOL_SCHEMAS
        ), f"Fixture has {len(EXPECTED_TOOLS)} tools, schemas has {len(TOOL_SCHEMAS)}"

    def test_inventory_doc_tool_count_matches(self):
        """Verify the inventory doc's total count matches the actual count."""
        if not _INVENTORY_DOC.exists():
            return
        content = _INVENTORY_DOC.read_text()
        match = re.search(r"\*\*Total:\s*(\d+)\s*tools\*\*", content)
        assert match, "Could not find total tool count in inventory doc"
        doc_count = int(match.group(1))
        assert doc_count == len(
            TOOL_HANDLERS
        ), f"Inventory doc says {doc_count} tools, but TOOL_HANDLERS has {len(TOOL_HANDLERS)}"

    def test_inventory_doc_table_row_count_matches(self):
        """Verify the number of rows in the inventory table matches the tool count."""
        if not _INVENTORY_DOC.exists():
            return
        content = _INVENTORY_DOC.read_text()
        # Count rows that start with | and have a tool name
        rows = re.findall(r"^\|\s*\d+\s*\|", content, re.MULTILINE)
        assert len(rows) == len(
            TOOL_HANDLERS
        ), f"Inventory table has {len(rows)} rows, but TOOL_HANDLERS has {len(TOOL_HANDLERS)}"

    def test_inventory_doc_summary_counts_match_table(self):
        """Verify the summary stats match the actual table row data."""
        if not _INVENTORY_DOC.exists():
            return
        content = _INVENTORY_DOC.read_text()
        # Parse table rows: each row has fields separated by |
        table_rows = re.findall(
            r"^\|\s*\d+\s*\|[^|]*\|[^|]*\|[^|]*\|[^|]*\|[^|]*\|[^|]*\|\s*(yes|no)\s*\|",
            content,
            re.MULTILINE,
        )
        have_tests = sum(1 for row in table_rows if row.strip() == "yes")
        missing_tests = sum(1 for row in table_rows if row.strip() == "no")
        # Find summary counts
        have_match = re.search(r"\|\s*Have tests\s*\|\s*(\d+)\s*\|", content)
        missing_match = re.search(r"\|\s*Missing tests\s*\|\s*(\d+)\s*\|", content)
        assert have_match, "Could not find 'Have tests' summary in inventory doc"
        assert missing_match, "Could not find 'Missing tests' summary in inventory doc"
        assert have_tests == int(have_match.group(1)), (
            f"Inventory 'Have tests' says {have_match.group(1)}, "
            f"but table has {have_tests} rows with 'yes'"
        )
        assert missing_tests == int(missing_match.group(1)), (
            f"Inventory 'Missing tests' says {missing_match.group(1)}, "
            f"but table has {missing_tests} rows with 'no'"
        )


HARNESS_TASK_PROFILES = {
    "codegg_preflight",
    "codegg_patch",
    "codegg_config",
    "codegg_shell",
    "codegg_unicode_security",
}

MODEL_FACING_PROFILES = {"default", "codegg_core", "codegg_core_min"}

MATH_CATEGORIES = {"math"}


class TestToolMetadata:
    """Verify TOOL_METADATA is complete and consistent."""

    VALID_CATEGORIES = {
        "math",
        "text",
        "json",
        "toml",
        "config",
        "regex",
        "path",
        "shell",
        "patch",
        "identifier",
        "markdown",
        "version",
        "cargo",
        "list",
        "validation",
        "unicode",
        "manifest",
        "repo",
        "network",
        "encoding",
        "temporal",
    }
    VALID_TIERS = {0, 1, 2, 3}
    VALID_LLM_EXPOSURE = {"default", "contextual", "expert_only", "harness_only", "hidden"}
    VALID_COST = {"cheap", "moderate", "heavy"}
    VALID_STABILITY = {"stable", "experimental", "deprecated"}

    def test_metadata_covers_all_handlers(self):
        handler_keys = set(TOOL_HANDLERS.keys())
        metadata_keys = set(TOOL_METADATA.keys())
        missing = handler_keys - metadata_keys
        assert not missing, f"Handlers without metadata: {sorted(missing)}"

    def test_metadata_covers_all_schemas(self):
        schema_keys = set(TOOL_SCHEMAS.keys())
        metadata_keys = set(TOOL_METADATA.keys())
        missing = schema_keys - metadata_keys
        assert not missing, f"Schemas without metadata: {sorted(missing)}"

    def test_metadata_no_extra_keys(self):
        metadata_keys = set(TOOL_METADATA.keys())
        handler_keys = set(TOOL_HANDLERS.keys())
        extra = metadata_keys - handler_keys
        assert not extra, f"Metadata for non-existent tools: {sorted(extra)}"

    def test_catalog_and_protocol_key_sets_agree(self):
        assert set(TOOL_METADATA.keys()) == set(TOOL_SCHEMAS.keys()), (
            "TOOL_METADATA (catalog authority) and TOOL_SCHEMAS (protocol "
            "authority) must agree on the public tool-name set"
        )
        assert set(TOOL_HANDLERS.keys()) == set(
            TOOL_METADATA.keys()
        ), "Derived TOOL_HANDLERS must equal the catalog metadata key set"

    def test_handler_locators_valid_and_resolve(self):
        from eggcalc.mcp import tools as _tools

        for name, meta in TOOL_METADATA.items():
            handler_attr = meta.get("handler")
            assert (
                isinstance(handler_attr, str) and handler_attr
            ), f"Tool '{name}' missing handler locator"
            assert (
                handler_attr.isidentifier()
            ), f"Tool '{name}' handler {handler_attr!r} must be an identifier"
            resolved = getattr(_tools, handler_attr, None)
            assert callable(
                resolved
            ), f"Tool '{name}' handler {handler_attr!r} not callable in tools"
            assert (
                TOOL_HANDLERS[name] is resolved
            ), f"Derived TOOL_HANDLERS['{name}'] identity mismatch"

    def test_metadata_categories_are_valid(self):
        for name, meta in TOOL_METADATA.items():
            assert (
                meta["category"] in self.VALID_CATEGORIES
            ), f"Invalid category '{meta['category']}' for tool '{name}'"

    def test_metadata_tiers_are_valid(self):
        for name, meta in TOOL_METADATA.items():
            assert (
                meta["tier"] in self.VALID_TIERS
            ), f"Invalid tier {meta['tier']} for tool '{name}'"

    def test_metadata_llm_exposure_is_valid(self):
        for name, meta in TOOL_METADATA.items():
            assert (
                meta["llm_exposure"] in self.VALID_LLM_EXPOSURE
            ), f"Invalid llm_exposure '{meta['llm_exposure']}' for tool '{name}'"

    def test_metadata_cost_is_valid(self):
        for name, meta in TOOL_METADATA.items():
            assert (
                meta["cost"] in self.VALID_COST
            ), f"Invalid cost '{meta['cost']}' for tool '{name}'"

    def test_metadata_stability_is_valid(self):
        for name, meta in TOOL_METADATA.items():
            assert (
                meta["stability"] in self.VALID_STABILITY
            ), f"Invalid stability '{meta['stability']}' for tool '{name}'"

    def test_metadata_profiles_are_lists(self):
        for name, meta in TOOL_METADATA.items():
            assert isinstance(meta["profiles"], list), f"Profiles for '{name}' must be a list"

    def test_metadata_aliases_are_lists(self):
        for name, meta in TOOL_METADATA.items():
            assert isinstance(meta["aliases"], list), f"Aliases for '{name}' must be a list"

    def test_metadata_harness_use_are_lists(self):
        for name, meta in TOOL_METADATA.items():
            assert isinstance(meta["harness_use"], list), f"harness_use for '{name}' must be a list"

    def test_metadata_composite_is_bool(self):
        for name, meta in TOOL_METADATA.items():
            assert isinstance(meta["composite"], bool), f"composite for '{name}' must be bool"


class TestToolProfiles:
    """Verify TOOL_PROFILES is complete and consistent."""

    def test_profiles_dict_exists(self):
        assert isinstance(TOOL_PROFILES, dict)
        assert len(TOOL_PROFILES) > 0

    def test_all_metadata_profile_names_exist_in_profiles_dict(self):
        all_profile_names = set()
        for meta in TOOL_METADATA.values():
            all_profile_names.update(meta.get("profiles", []))
        for name in all_profile_names:
            assert (
                name in TOOL_PROFILES
            ), f"Profile '{name}' referenced in metadata but not in TOOL_PROFILES"

    def test_profile_tool_lists_are_sorted(self):
        for profile_name, tool_list in TOOL_PROFILES.items():
            assert tool_list == sorted(
                tool_list
            ), f"Profile '{profile_name}' tool list is not sorted"

    def test_profile_tool_lists_only_contain_known_tools(self):
        known_tools = set(TOOL_HANDLERS.keys())
        for profile_name, tool_list in TOOL_PROFILES.items():
            unknown = set(tool_list) - known_tools
            assert (
                not unknown
            ), f"Profile '{profile_name}' contains unknown tools: {sorted(unknown)}"

    def test_full_profile_contains_all_non_hidden_tools(self):
        full_tools = set(TOOL_PROFILES.get("full", []))
        expected = {
            name for name, meta in TOOL_METADATA.items() if meta.get("llm_exposure") != "hidden"
        }
        assert full_tools == expected, (
            f"Full profile mismatch.\n"
            f"  Missing: {sorted(expected - full_tools)}\n"
            f"  Extra:   {sorted(full_tools - expected)}"
        )

    def test_codegg_core_min_is_subset_of_codegg_core(self):
        core_min = set(TOOL_PROFILES.get("codegg_core_min", []))
        core = set(TOOL_PROFILES.get("codegg_core", []))
        assert core_min.issubset(core), (
            f"codegg_core_min is not a subset of codegg_core.\n"
            f"  In core_min but not core: {sorted(core_min - core)}"
        )

    def test_profile_names_constant(self):
        from eggcalc.mcp.schemas import PROFILE_NAMES

        assert isinstance(PROFILE_NAMES, list)
        assert len(PROFILE_NAMES) > 0
        # All names should be in TOOL_PROFILES
        from eggcalc.mcp.schemas import TOOL_PROFILES

        for name in PROFILE_NAMES:
            assert name in TOOL_PROFILES, f"PROFILE_NAMES contains '{name}' not in TOOL_PROFILES"


class TestProfileInvariants:
    """Verify cross-profile and metadata/profile consistency invariants."""

    def test_no_harness_only_tool_in_codegg_core_min(self):
        """Invariant 1: codegg_core_min must not expose harness-only tools to LLM."""
        core_min_tools = TOOL_PROFILES.get("codegg_core_min", [])
        violations = []
        for tool in core_min_tools:
            meta = TOOL_METADATA.get(tool, {})
            if meta.get("llm_exposure") == "harness_only":
                violations.append(tool)
        assert not violations, (
            f"harness_only tools in codegg_core_min (should not be exposed to LLM): "
            f"{sorted(violations)}"
        )

    def test_no_harness_only_tool_in_codegg_core(self):
        """Invariant 2: codegg_core must not expose harness-only tools to LLM."""
        core_tools = TOOL_PROFILES.get("codegg_core", [])
        violations = []
        for tool in core_tools:
            meta = TOOL_METADATA.get(tool, {})
            if meta.get("llm_exposure") == "harness_only":
                violations.append(tool)
        assert not violations, (
            f"harness_only tools in codegg_core (should not be exposed to LLM): "
            f"{sorted(violations)}"
        )

    def test_harness_only_tools_covered_by_harness_profiles(self):
        """Invariant 3: every harness_only tool appears in at least one harness/task profile."""
        harness_only_tools = {
            name
            for name, meta in TOOL_METADATA.items()
            if meta.get("llm_exposure") == "harness_only"
        }
        uncovered = []
        for tool in sorted(harness_only_tools):
            tool_profiles = set(TOOL_METADATA[tool].get("profiles", []))
            if not tool_profiles.intersection(HARNESS_TASK_PROFILES):
                uncovered.append(tool)
        assert not uncovered, (
            f"harness_only tools missing from all harness/task profiles "
            f"({sorted(HARNESS_TASK_PROFILES)}): {uncovered}"
        )

    def test_default_composite_tools_in_model_facing_profile(self):
        """Invariant 4: composite tools with default exposure appear in a model-facing profile."""
        default_composites = {
            name
            for name, meta in TOOL_METADATA.items()
            if meta.get("composite") and meta.get("llm_exposure") == "default"
        }
        uncovered = []
        for tool in sorted(default_composites):
            tool_profiles = set(TOOL_METADATA[tool].get("profiles", []))
            if not tool_profiles.intersection(MODEL_FACING_PROFILES):
                uncovered.append(tool)
        assert not uncovered, (
            f"composite tools with llm_exposure=default missing from all model-facing profiles "
            f"({sorted(MODEL_FACING_PROFILES)}): {uncovered}"
        )

    def test_human_math_contains_only_math_category(self):
        """Invariant 6a: human_math profile only contains math-category tools."""
        human_math_tools = TOOL_PROFILES.get("human_math", [])
        non_math = []
        for tool in human_math_tools:
            meta = TOOL_METADATA.get(tool, {})
            if meta.get("category") not in MATH_CATEGORIES:
                non_math.append((tool, meta.get("category")))
        assert not non_math, f"non-math tools in human_math profile: {sorted(non_math)}"

    def test_human_math_excludes_preflight_and_composite(self):
        """Invariant 6b: human_math excludes codegg preflight and composite tools."""
        human_math_tools = set(TOOL_PROFILES.get("human_math", []))
        preflight_composites = {
            name
            for name in human_math_tools
            if name.startswith(
                ("edit_preflight", "command_preflight", "config_preflight", "text_security_inspect")
            )
            or TOOL_METADATA.get(name, {}).get("composite")
            or name in {"patch_apply_check", "path_scope_check"}
        }
        # Also check that no tool in human_math is a codegg_* profile tool
        codegg_preflight_tools = set()
        for profile in HARNESS_TASK_PROFILES:
            codegg_preflight_tools.update(TOOL_PROFILES.get(profile, []))
        violations = human_math_tools.intersection(codegg_preflight_tools).union(
            preflight_composites
        )
        # Filter to only tools that are composite or in a harness profile
        actual_violations = {
            t
            for t in violations
            if TOOL_METADATA.get(t, {}).get("composite")
            or TOOL_METADATA.get(t, {}).get("llm_exposure") == "harness_only"
        }
        assert (
            not actual_violations
        ), f"composite/harness_only tools in human_math profile: {sorted(actual_violations)}"


class TestStandardToolShape:
    """Strict standard Tool object keys (Plan 040 Workstream C).

    tools/list emits standard MCP fields (name/description/inputSchema)
    at standard locations on both eras. Eggcalc selection metadata
    (tier/tags/category/...) remains available for filtering but is
    sourced from TOOL_METADATA, not authored in TOOL_SCHEMAS.
    """

    def _legacy_tools(self):
        from eggcalc.mcp.server import handle_request

        resp = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": {"profile": "full", "schema_detail": "full"},
            }
        )
        assert "result" in resp, resp
        return resp["result"]["tools"]

    def test_standard_keys_present_legacy(self):
        for tool in self._legacy_tools():
            assert isinstance(tool.get("name"), str) and tool["name"]
            assert isinstance(tool.get("description"), str) and tool["description"]
            assert isinstance(tool.get("inputSchema"), dict)
            assert tool["inputSchema"].get("type") == "object"
            assert isinstance(tool.get("annotations"), dict)
            # Selection metadata still emitted (from catalog authority).
            assert isinstance(tool.get("tier"), int)
            assert isinstance(tool.get("tags"), list)
            assert isinstance(tool.get("category"), str)

    def test_standard_keys_present_modern(self):
        from eggcalc.mcp.server import McpServer

        server = McpServer()
        try:
            resp = server.handle_request(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/list",
                    "params": {
                        "profile": "full",
                        "schema_detail": "full",
                        "_meta": {
                            "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                            "io.modelcontextprotocol/clientCapabilities": {},
                        },
                    },
                }
            )
            assert "result" in resp, resp
            assert resp["result"].get("resultType") == "complete"
            for tool in resp["result"]["tools"]:
                assert isinstance(tool.get("name"), str) and tool["name"]
                assert isinstance(tool.get("description"), str)
                assert isinstance(tool.get("inputSchema"), dict)
                assert isinstance(tool.get("annotations"), dict)
        finally:
            server.close()


class TestDocGenerator:
    """Verify the generated tool inventory doc matches current metadata."""

    def test_generated_doc_matches(self):
        """The generator's --check mode should pass against the checked-in doc."""
        import subprocess
        import sys as _sys

        script = pathlib.Path(__file__).parent.parent / "scripts" / "generate_mcp_docs.py"
        if not script.exists():
            return  # generator not present, skip
        result = subprocess.run(
            [_sys.executable, str(script), "--check"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"docs/tool_inventory.md is out of date.\n"
            f"  Run: python scripts/generate_mcp_docs.py\n"
            f"  stdout: {result.stdout.strip()}\n"
            f"  stderr: {result.stderr.strip()}"
        )
