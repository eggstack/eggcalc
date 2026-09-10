"""Deterministic tests for agent tool discovery and selection (Plan 041).

Covers the pieces that do not require an LLM:

- evaluation corpus shape (parses, unique ids, known tools, split hygiene,
  domain coverage);
- catalog selection metadata bounds (selection_summary/keywords);
- deterministic lexical discovery (ranking, determinism, profile
  restriction, hidden-tool isolation, output bounds);
- agent_core profile invariants (strict subset of full, size, exposure);
- compact schema contract (selection signal + required inputs/types/enums);
- footprint-measurement determinism;
- provider-neutral scorer behavior on complete and partial records.

LLM evaluations remain an explicit external/manual/release experiment
(see evals/mcp_tool_selection/README.md). CI validates corpus + scorer,
never network calls.
"""

import importlib.util
import json
import pathlib

import pytest

from eggcalc.mcp.schemas import (
    SELECTION_KEYWORD_MAX_LENGTH,
    SELECTION_KEYWORDS_MAX_COUNT,
    SELECTION_SUMMARY_MAX_LENGTH,
    TOOL_METADATA,
    TOOL_PROFILES,
    TOOL_SCHEMAS,
    compact_schema,
    get_tool_keywords,
    get_tool_selection_summary,
)
from eggcalc.mcp.server import McpServer, McpServerConfig, ToolRegistry

EVAL_DIR = pathlib.Path(__file__).parent.parent / "evals" / "mcp_tool_selection"
CASES_PATH = EVAL_DIR / "cases.json"
SCRIPTS_DIR = pathlib.Path(__file__).parent.parent / "scripts"

REQUIRED_CASE_KEYS = frozenset(
    {
        "id",
        "prompt",
        "domains",
        "acceptable_primary_tools",
        "acceptable_supporting_tools",
        "required_capabilities",
        "split",
        "notes",
    }
)


def _load_cases() -> list[dict]:
    return json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]


def _load_script(name: str):
    path = SCRIPTS_DIR / name
    spec = importlib.util.spec_from_file_location(f"eggcalc_scripts_{path.stem}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestEvaluationCorpus:
    def test_cases_file_parses(self):
        cases = _load_cases()
        assert len(cases) >= 100, f"expected >=100 cases, got {len(cases)}"

    def test_ids_unique_and_nonempty(self):
        cases = _load_cases()
        ids = [c["id"] for c in cases]
        assert all(isinstance(i, str) and i for i in ids)
        assert len(set(ids)) == len(ids), "duplicate case ids"

    def test_required_keys_present(self):
        for case in _load_cases():
            missing = REQUIRED_CASE_KEYS - set(case)
            assert not missing, f"case {case.get('id')}: missing keys {sorted(missing)}"

    def test_split_values_explicit(self):
        splits = {c["split"] for c in _load_cases()}
        assert splits <= {"development", "held_out"}, f"unexpected splits: {splits}"
        assert splits == {"development", "held_out"}, "both splits must be present"

    def test_referenced_tools_exist(self):
        known = set(TOOL_METADATA)
        for case in _load_cases():
            for tool in case["acceptable_primary_tools"] + case["acceptable_supporting_tools"]:
                assert tool in known, f"case {case['id']}: unknown tool {tool!r}"

    def test_prompts_nonempty(self):
        for case in _load_cases():
            assert isinstance(case["prompt"], str) and case["prompt"].strip(), case["id"]

    def test_domain_minimum_coverage(self):
        from collections import Counter

        counts = Counter(d for c in _load_cases() for d in c["domains"])
        for domain, count in sorted(counts.items()):
            assert count >= 2, f"domain {domain!r} has only {count} case(s)"
        # Core workflow domains must appear in both splits.
        for domain in ("patch", "shell", "json", "text", "config"):
            splits = {c["split"] for c in _load_cases() if domain in c["domains"]}
            assert splits == {
                "development",
                "held_out",
            }, f"domain {domain!r} missing a split: {splits}"


class TestSelectionMetadata:
    def test_summaries_nonempty_and_bounded(self):
        for name, meta in TOOL_METADATA.items():
            summary = meta.get("selection_summary")
            assert isinstance(summary, str) and summary, f"{name}: empty selection_summary"
            assert len(summary) <= SELECTION_SUMMARY_MAX_LENGTH, (
                f"{name}: selection_summary {len(summary)} chars exceeds "
                f"{SELECTION_SUMMARY_MAX_LENGTH}"
            )

    def test_summaries_not_truncated_descriptions(self):
        # The summary must be authored selection signal, not a prefix of the
        # full description (which compact mode used to truncate).
        for name, meta in TOOL_METADATA.items():
            summary = meta["selection_summary"]
            full_desc = TOOL_SCHEMAS[name]["description"]
            assert (
                summary != full_desc[: len(summary)]
            ), f"{name}: selection_summary looks like a truncated description"

    def test_keywords_bounded(self):
        for name, meta in TOOL_METADATA.items():
            keywords = meta.get("keywords")
            assert isinstance(keywords, list), f"{name}: keywords must be a list"
            assert (
                len(keywords) <= SELECTION_KEYWORDS_MAX_COUNT
            ), f"{name}: too many keywords ({len(keywords)})"
            for keyword in keywords:
                assert isinstance(keyword, str) and keyword, f"{name}: empty keyword"
                assert (
                    len(keyword) <= SELECTION_KEYWORD_MAX_LENGTH
                ), f"{name}: keyword {keyword!r} exceeds {SELECTION_KEYWORD_MAX_LENGTH}"

    def test_accessors(self):
        assert get_tool_selection_summary("version_compare").startswith(
            "Compare two concrete versions"
        )
        assert "caret" in get_tool_keywords("version_constraint_check")
        keywords = get_tool_keywords("math_eval")
        keywords.append("mutated")
        assert "mutated" not in get_tool_keywords("math_eval"), "must return a copy"


class TestCatalogSearch:
    def test_exact_name_match_ranks_first(self):
        registry = ToolRegistry()
        for name in (
            "math_eval",
            "text_truncate",
            "version_constraint_check",
            "markdown_link_check_lexical",
            "patch_conflict_markers_inspect",
        ):
            top = registry.search_tools(name, limit=5)
            assert top, f"no results for exact name {name!r}"
            assert (
                top[0]["name"] == name
            ), f"exact name {name!r} did not rank first: {[t['name'] for t in top]}"
            assert top[0]["matched_on"] == ["name:exact"]

    def test_separator_insensitive_exact_match(self):
        registry = ToolRegistry()
        top = registry.search_tools("patch apply check", limit=3)
        assert top[0]["name"] == "patch_apply_check"

    def test_keyword_phrase_match(self):
        registry = ToolRegistry()
        top = registry.search_tools("is this cron schedule going to run soon", limit=5)
        assert any(t["name"] == "cron_inspect" for t in top)

    def test_deterministic_across_calls_and_registries(self):
        queries = [
            "validate this unified diff patch before applying",
            "convert 5 km to miles",
            "compare two JSON documents ignoring key order",
            "check my shell command before running it",
        ]
        first = ToolRegistry()
        for query in queries:
            expected = first.search_tools(query, limit=5)
            assert first.search_tools(query, limit=5) == expected
            assert ToolRegistry().search_tools(query, limit=5) == expected

    def test_tie_break_by_name(self):
        registry = ToolRegistry()
        for query in ("json", "text compare", "validate config"):
            results = registry.search_tools(query, limit=10)
            keys = [(-r["score"], r["name"]) for r in results]
            assert keys == sorted(keys), f"non-deterministic order for {query!r}"

    def test_profile_restriction(self):
        registry = ToolRegistry()
        core = set(registry.get_profile_tools("agent_core"))
        results = registry.search_tools("json pointer extract value", profile="agent_core")
        assert results, "expected agent_core results"
        assert all(r["name"] in core for r in results)
        with pytest.raises(ValueError):
            registry.search_tools("anything", profile="no_such_profile")

    def test_full_profile_default(self):
        registry = ToolRegistry()
        results = registry.search_tools("cidr subnet range", limit=5)
        assert any(r["name"] == "cidr_inspect" for r in results)

    def test_hidden_tools_never_surfaced(self):
        def _handler(**kwargs):
            return {"ok": True}

        hidden_meta = {
            "t_hidden": {
                "handler": "t_hidden",
                "category": "text",
                "llm_exposure": "hidden",
                "selection_summary": "Hidden specialist for testing.",
                "keywords": ["hidden specialist probe"],
            },
            "t_shown": {
                "handler": "t_shown",
                "category": "text",
                "llm_exposure": "default",
                "selection_summary": "Visible specialist for testing.",
                "keywords": ["visible specialist probe"],
            },
        }
        schemas = {
            "t_hidden": {
                "description": "Hidden specialist for testing.",
                "inputSchema": {"type": "object", "properties": {}},
            },
            "t_shown": {
                "description": "Visible specialist for testing.",
                "inputSchema": {"type": "object", "properties": {}},
            },
        }
        registry = ToolRegistry(
            handlers={"t_hidden": _handler, "t_shown": _handler},
            schemas=schemas,
            metadata=hidden_meta,
            profiles={"custom": ["t_shown"]},
        )
        assert not registry.is_tool_visible("t_hidden", "full")
        results = registry.search_tools("specialist probe", profile="full", limit=5)
        assert [r["name"] for r in results] == ["t_shown"]

    def test_search_never_authorizes_calls(self):
        # Discovery is ranking only: a search hit outside the configured
        # profile must still be invisible/callable-gated by the profile.
        registry = ToolRegistry()
        assert registry.search_tools("cidr subnet", profile="agent_core", limit=10) == [] or all(
            r["name"] in set(registry.get_profile_tools("agent_core"))
            for r in registry.search_tools("cidr subnet", profile="agent_core", limit=10)
        )
        assert not registry.is_tool_visible("cidr_inspect", "agent_core")

    def test_output_bounded(self):
        registry = ToolRegistry()
        assert registry.search_tools("   ") == []
        assert registry.search_tools("", limit=5) == []
        with pytest.raises(ValueError):
            registry.search_tools("json", limit=0)
        with pytest.raises(ValueError):
            registry.search_tools("json", limit=21)
        # Over-long queries are truncated, not rejected.
        assert isinstance(registry.search_tools("x " * 5000, limit=5), list)
        results = registry.search_tools("validate", limit=3)
        assert len(results) <= 3

    def test_result_shape(self):
        registry = ToolRegistry()
        (match,) = registry.search_tools("math_eval", limit=1)
        assert set(match) == {"name", "score", "category", "selection_summary", "matched_on"}
        assert isinstance(match["score"], int) and match["score"] > 0
        assert match["category"] == "math"
        assert match["selection_summary"] == get_tool_selection_summary("math_eval")
        assert isinstance(match["matched_on"], list) and match["matched_on"]


class TestAgentCoreProfile:
    def test_agent_core_is_strict_subset_of_full(self):
        full = set(TOOL_PROFILES["full"])
        core = set(TOOL_PROFILES["agent_core"])
        assert core, "agent_core must not be empty"
        assert core < full, "agent_core must be a strict subset of full"

    def test_excluded_tools_remain_in_full(self):
        full = set(TOOL_PROFILES["full"])
        core = set(TOOL_PROFILES["agent_core"])
        for name in full - core:
            assert name in full  # present via full/appropriate profile
        assert len(full - core) > 0

    def test_agent_core_small(self):
        core = TOOL_PROFILES["agent_core"]
        assert 6 <= len(core) <= 12, f"agent_core should stay small, got {len(core)}"

    def test_no_harness_only_in_agent_core(self):
        violations = [
            t
            for t in TOOL_PROFILES["agent_core"]
            if TOOL_METADATA[t].get("llm_exposure") == "harness_only"
        ]
        assert not violations, f"harness_only tools in agent_core: {violations}"

    def test_all_profiles_still_present(self):
        for profile in (
            "full",
            "default",
            "codegg_core_min",
            "codegg_core",
            "codegg_preflight",
            "codegg_patch",
            "codegg_config",
            "codegg_unicode_security",
            "codegg_shell",
            "codegg_repo_audit",
            "human_math",
        ):
            assert profile in TOOL_PROFILES, f"profile {profile!r} missing"

    def test_registry_profile_parity(self):
        registry = ToolRegistry()
        assert registry.get_profile_tools("agent_core") == TOOL_PROFILES["agent_core"]


class TestCompactContract:
    def test_compact_description_is_selection_summary(self):
        for name, schema in TOOL_SCHEMAS.items():
            compact = compact_schema(schema, get_tool_selection_summary(name))
            assert compact["description"] == get_tool_selection_summary(name), name

    def test_compact_fallback_truncates(self):
        schema = {"description": "x" * 200, "inputSchema": {"type": "object"}}
        assert compact_schema(schema)["description"] == "x" * 117 + "..."

    def test_compact_retains_required_types_enums(self):
        for name, schema in TOOL_SCHEMAS.items():
            full_input = schema.get("inputSchema", {})
            compact = compact_schema(schema, "summary")["inputSchema"]
            assert compact.get("required", []) == full_input.get("required", []), name
            for prop, prop_def in full_input.get("properties", {}).items():
                if not isinstance(prop_def, dict):
                    continue
                slim = compact["properties"][prop]
                if "type" in prop_def:
                    assert slim.get("type") == prop_def["type"], f"{name}.{prop} type"
                if "enum" in prop_def:
                    assert slim.get("enum") == list(prop_def["enum"]), f"{name}.{prop} enum"

    def test_wire_compact_matches_selection_summary(self):
        from eggcalc.mcp.server import handle_request

        response = handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": {"profile": "agent_core", "schema_detail": "compact"},
            }
        )
        tools = response["result"]["tools"]
        assert {t["name"] for t in tools} == set(TOOL_PROFILES["agent_core"])
        for tool in tools:
            assert tool["description"] == get_tool_selection_summary(tool["name"])


class TestFootprintDeterminism:
    def test_measure_surface_deterministic(self):
        measure = _load_script("measure_mcp_tool_surface.py")
        server = McpServer(config=McpServerConfig(profile="full"))
        try:
            first = measure.measure_surface(server, "agent_core", "compact")
            second = measure.measure_surface(server, "agent_core", "compact")
            assert first == second
        finally:
            server.close()

    def test_agent_core_compact_reduction_gate(self):
        measure = _load_script("measure_mcp_tool_surface.py")
        server = McpServer(config=McpServerConfig(profile="full"))
        try:
            full = measure.measure_surface(server, "full", "full")
            core = measure.measure_surface(server, "agent_core", "compact")
            reduction = 100.0 * (full["total_bytes"] - core["total_bytes"]) / full["total_bytes"]
            assert reduction >= 70.0, f"reduction {reduction:.1f}% below 70% gate"
        finally:
            server.close()


class TestSelectionScorer:
    def _write_rollouts(self, tmp_path, lines: list[dict]) -> str:
        path = tmp_path / "rollouts.jsonl"
        path.write_text("\n".join(json.dumps(r) for r in lines) + "\n", encoding="utf-8")
        return str(path)

    def test_complete_and_partial_records(self, tmp_path):
        scorer = _load_script("score_mcp_tool_selection.py")
        cases = {c["id"]: c for c in _load_cases()}
        path = self._write_rollouts(
            tmp_path,
            [
                {
                    "case_id": "patch-001",
                    "model": "test/m",
                    "catalog_config": "agent_core/compact",
                    "tool_calls": [{"name": "text_replace_check", "arguments_valid": True}],
                    "completed": True,
                    "task_correct": True,
                    "input_tokens": 10,
                    "output_tokens": 5,
                },
                {
                    # Partial record: no token fields, no task_correct.
                    "case_id": "math-003",
                    "tool_calls": [{"name": "unit_convert"}],
                },
                {
                    # No-tool case scored by silence.
                    "case_id": "ambig-001",
                    "tool_calls": [],
                    "completed": True,
                },
            ],
        )
        records = scorer.load_rollouts(pathlib.Path(path))
        scored = [scorer.score_record(cases[r["case_id"]], r) for r in records]
        assert scored[0]["acceptable_first_tool"] is True
        assert scored[0]["total_calls"] == 1
        assert scored[1]["acceptable_first_tool"] is True
        assert scored[1]["task_correct"] is None
        assert scored[2]["acceptable_first_tool"] is True
        assert scored[2]["acceptable_tool_used"] is True
        agg = scorer.aggregate(scored)
        assert agg["n"] == 3
        assert agg["first_tool_rate"] == 1.0
        assert agg["task_correct_reported"] == 1

    def test_irrelevant_redundant_invalid_counts(self, tmp_path):
        scorer = _load_script("score_mcp_tool_selection.py")
        cases = {c["id"]: c for c in _load_cases()}
        record = {
            "case_id": "shell-006",
            "tool_calls": [
                {"name": "regex_finditer", "arguments_valid": True},
                {"name": "regex_finditer", "arguments_valid": True},
                {"name": "math_eval", "arguments_valid": False},
                {"name": "nope_missing", "arguments_valid": True},
            ],
        }
        scored = scorer.score_record(cases["shell-006"], record)
        assert scored["acceptable_first_tool"] is True
        assert scored["redundant_calls"] == 1
        assert scored["invalid_names"] == 1
        assert scored["invalid_arguments"] == 1
        # math_eval is valid but irrelevant here.
        assert scored["irrelevant_calls"] == 1

    def test_no_tool_violation_detected(self, tmp_path):
        scorer = _load_script("score_mcp_tool_selection.py")
        cases = {c["id"]: c for c in _load_cases()}
        record = {"case_id": "ambig-001", "tool_calls": [{"name": "math_eval"}]}
        scored = scorer.score_record(cases["ambig-001"], record)
        assert scored["acceptable_first_tool"] is False
        assert scored["irrelevant_calls"] == 1
