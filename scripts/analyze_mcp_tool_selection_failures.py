#!/usr/bin/env python3
"""Decompose MCP tool-selection reachability and rollout failures.

This is a deterministic, stdlib-only companion to the Plan 043 experiment.
It measures catalog-search ranks for every corpus case and, when supplied,
joins provider-neutral rollout JSONL records to classify observed failures.
It never calls a model and never changes the held-out corpus.

Examples:
    python scripts/analyze_mcp_tool_selection_failures.py
    python scripts/analyze_mcp_tool_selection_failures.py \
        --rollouts /path/to/normalized-rollouts.jsonl \
        --json /tmp/corrective-analysis.json \
        --markdown /tmp/corrective-analysis.md
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CASES = REPO_ROOT / "evals" / "mcp_tool_selection" / "cases.json"
DEFAULT_CANDIDATES = REPO_ROOT / "evals" / "mcp_tool_selection" / "candidate_sets.json"
DEPTHS = (1, 3, 5, 8, 10, 20)

sys.path.insert(0, str(REPO_ROOT))

from eggcalc.mcp.schemas import TOOL_METADATA, TOOL_PROFILES  # noqa: E402
from eggcalc.mcp.server import ToolRegistry  # noqa: E402


def load_cases(path: Path) -> list[dict[str, Any]]:
    """Load and validate the corpus case list."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = payload["cases"] if isinstance(payload, dict) else payload
    if not isinstance(cases, list):
        raise ValueError(f"{path}: expected a case list")
    return cases


def load_candidates(path: Path) -> dict[str, list[str]]:
    """Load evaluation-only candidate name lists."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    sets = payload.get("sets", payload) if isinstance(payload, dict) else payload
    if not isinstance(sets, dict):
        raise ValueError(f"{path}: expected an object of candidate sets")
    result: dict[str, list[str]] = {}
    known = set(TOOL_METADATA)
    for label, names in sets.items():
        if not isinstance(label, str) or not isinstance(names, list):
            raise ValueError(f"{path}: candidate set {label!r} must be list[str]")
        if not all(isinstance(name, str) and name in known for name in names):
            raise ValueError(f"{path}: candidate set {label!r} contains unknown tool")
        if len(names) != len(set(names)):
            raise ValueError(f"{path}: candidate set {label!r} contains duplicates")
        result[label] = sorted(names)
    return result


def load_rollouts(path: Path | None) -> list[dict[str, Any]]:
    """Load optional normalized rollout records."""
    if path is None:
        return []
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno}: invalid JSON: {exc}") from exc
            if not isinstance(record, dict):
                raise ValueError(f"{path}:{lineno}: rollout record must be an object")
            records.append(record)
    return records


def _acceptable(case: dict[str, Any]) -> tuple[set[str], set[str]]:
    primary = set(case.get("acceptable_primary_tools", []))
    supporting = set(case.get("acceptable_supporting_tools", []))
    return primary, primary | supporting


def _ranks(registry: ToolRegistry, prompt: str) -> dict[str, int]:
    """Return the deterministic full-catalog rank for the first 20 matches."""
    return {
        match["name"]: rank for rank, match in enumerate(registry.search_tools(prompt, limit=20), 1)
    }


def _percent(numerator: int, denominator: int) -> float | None:
    if not denominator:
        return None
    return round(numerator / denominator, 4)


def _rank_summary(cases: list[dict[str, Any]], registry: ToolRegistry) -> dict[str, Any]:
    """Measure acceptable-tool recall at each requested shortlist depth."""
    by_split: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        by_split[str(case.get("split", "unknown"))].append(case)

    result: dict[str, Any] = {}
    for split, split_cases in sorted(by_split.items()):
        rows = []
        for case in split_cases:
            primary, acceptable = _acceptable(case)
            if not acceptable:
                continue
            rank = _ranks(registry, case["prompt"])
            first_primary = min((rank[name] for name in primary if name in rank), default=None)
            first_acceptable = min(
                (rank[name] for name in acceptable if name in rank), default=None
            )
            rows.append(
                {
                    "case_id": case["id"],
                    "first_primary_rank": first_primary,
                    "first_acceptable_rank": first_acceptable,
                    "ranks": rank,
                }
            )
        first_acceptable_ranks = [
            row["first_acceptable_rank"] for row in rows if row["first_acceptable_rank"] is not None
        ]
        result[split] = {
            "tool_cases": len(rows),
            "acceptable_recall_at": {
                str(depth): _percent(
                    sum(
                        row["first_acceptable_rank"] is not None
                        and row["first_acceptable_rank"] <= depth
                        for row in rows
                    ),
                    len(rows),
                )
                for depth in DEPTHS
            },
            "primary_recall_at": {
                str(depth): _percent(
                    sum(
                        row["first_primary_rank"] is not None and row["first_primary_rank"] <= depth
                        for row in rows
                    ),
                    len(rows),
                )
                for depth in DEPTHS
            },
            "first_acceptable_rank_median": (
                statistics.median(first_acceptable_ranks) if first_acceptable_ranks else None
            ),
            "first_acceptable_rank_p90": (
                _percentile(first_acceptable_ranks, 0.90) if first_acceptable_ranks else None
            ),
            "no_acceptable_rank_within_20": [
                row["case_id"] for row in rows if row["first_acceptable_rank"] is None
            ],
            "no_primary_rank_within_20": [
                row["case_id"] for row in rows if row["first_primary_rank"] is None
            ],
        }
    return result


def _percentile(values: list[int], fraction: float) -> float:
    """Return a nearest-rank percentile without a numeric dependency."""
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * fraction + 0.5)))
    return float(ordered[index])


def _candidate_summary(
    cases: list[dict[str, Any]],
    candidates: dict[str, list[str]],
    registry: ToolRegistry,
    current_core: set[str],
) -> dict[str, Any]:
    """Summarize static coverage and core-miss coverage for candidates."""
    result: dict[str, Any] = {}
    for label, names in candidates.items():
        name_set = set(names)
        per_split: dict[str, dict[str, Any]] = {}
        for split in ("development", "held_out"):
            rows = [case for case in cases if case.get("split") == split]
            tool_cases = [case for case in rows if _acceptable(case)[1]]
            covered_any = [case for case in tool_cases if _acceptable(case)[1] & name_set]
            covered_primary = [case for case in tool_cases if _acceptable(case)[0] & name_set]
            core_misses = [case for case in tool_cases if not (_acceptable(case)[1] & current_core)]
            avoided_misses = [case for case in core_misses if _acceptable(case)[1] & name_set]
            per_split[split] = {
                "tool_cases": len(tool_cases),
                "static_acceptable_any_count": len(covered_any),
                "static_acceptable_any_rate": _percent(len(covered_any), len(tool_cases)),
                "static_primary_count": len(covered_primary),
                "static_primary_rate": _percent(len(covered_primary), len(tool_cases)),
                "current_core_misses_avoided": len(avoided_misses),
                "covered_case_ids": [case["id"] for case in covered_any],
            }
        result[label] = {
            "tool_count": len(names),
            "tools": names,
            "by_split": per_split,
        }
    return result


def _rollout_score(case: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    """Extract call-path facts needed by the failure decomposition."""
    primary, acceptable = _acceptable(case)
    calls = record.get("tool_calls", []) or []
    names = [call.get("name", "") for call in calls if isinstance(call, dict)]
    return {
        "catalog_config": record.get("catalog_config"),
        "model": record.get("model"),
        "selected_tools": names,
        "called_any_tool": bool(names),
        "first_primary_acceptable": bool(names) and names[0] in primary,
        "acceptable_tool_used": any(name in acceptable for name in names),
    }


def _visible_names(
    record: dict[str, Any],
    case: dict[str, Any],
    registry: ToolRegistry,
    candidates: dict[str, list[str]],
) -> set[str] | None:
    """Infer visible names from explicit evidence or a known config label."""
    for key in ("visible_tools", "discovered_tools"):
        value = record.get(key)
        if isinstance(value, list) and all(isinstance(name, str) for name in value):
            if key == "visible_tools":
                return set(value)
    config = record.get("catalog_config")
    if not isinstance(config, str):
        return None
    if config.startswith("candidate:"):
        label = config.split("/", 1)[0].removeprefix("candidate:")
        return set(candidates.get(label, []))
    if config.startswith("full/"):
        return set(TOOL_METADATA)
    if config.startswith("agent_core"):
        visible = set(TOOL_PROFILES["agent_core"])
        if "+discovery" in config:
            limit = record.get("discovery_limit", 5)
            if not isinstance(limit, int) or not 1 <= limit <= 20:
                limit = 5
            visible.update(
                match["name"] for match in registry.search_tools(case["prompt"], limit=limit)
            )
        return visible
    return None


def _classify_case(
    case: dict[str, Any],
    core: set[str],
    rank: dict[str, int],
    rollout: dict[str, Any] | None,
    visible: set[str] | None,
) -> dict[str, Any]:
    """Classify the earliest relevant deterministic or observed failure."""
    primary, acceptable = _acceptable(case)
    if not acceptable:
        return {"primary_cause": "no-tool-control", "secondary_causes": []}

    static_any = bool(acceptable & core)
    first_acceptable = min((rank[name] for name in acceptable if name in rank), default=None)
    deterministic_secondary: list[str] = []
    if not static_any:
        deterministic_secondary.append("static-core-omission")
    if first_acceptable is None:
        deterministic_secondary.append("discovery-recall-failure")
    elif first_acceptable > 5:
        deterministic_secondary.append("discovery-ranking-depth-failure")

    if rollout is None:
        if not static_any:
            primary_cause = "static-core-omission"
        elif first_acceptable is None:
            primary_cause = "discovery-recall-failure"
        elif first_acceptable > 5:
            primary_cause = "discovery-ranking-depth-failure"
        else:
            primary_cause = "unobserved-selection"
        return {
            "primary_cause": primary_cause,
            "secondary_causes": deterministic_secondary,
        }

    names = rollout["selected_tools"]
    if not names:
        primary_cause = "no-tool-propensity-failure"
    elif rollout["acceptable_tool_used"]:
        primary_cause = "none"
    elif visible is not None and acceptable & visible:
        primary_cause = "exposed-selection-failure"
    elif first_acceptable is None:
        primary_cause = "discovery-recall-failure"
    else:
        primary_cause = "discovery-ranking-depth-failure"
    return {"primary_cause": primary_cause, "secondary_causes": deterministic_secondary}


def analyze(
    cases: list[dict[str, Any]],
    candidates: dict[str, list[str]],
    rollouts: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the complete deterministic and optional rollout report."""
    registry = ToolRegistry()
    core = set(TOOL_PROFILES["agent_core"])
    by_case_config: dict[tuple[str, str], dict[str, Any]] = {}
    for record in rollouts:
        case_id = record.get("case_id")
        config = record.get("catalog_config")
        if isinstance(case_id, str) and isinstance(config, str):
            by_case_config[(case_id, config)] = record

    rows: list[dict[str, Any]] = []
    causes = Counter()
    for case in cases:
        rank = _ranks(registry, case["prompt"])
        primary, acceptable = _acceptable(case)
        rollout_records = [
            record for (case_id, _), record in by_case_config.items() if case_id == case["id"]
        ]
        observations = []
        for record in sorted(rollout_records, key=lambda item: str(item.get("catalog_config"))):
            scored = _rollout_score(case, record)
            visible = _visible_names(record, case, registry, candidates)
            scored["visible_acceptable"] = (
                bool(acceptable & visible) if visible is not None else None
            )
            scored["failure"] = _classify_case(case, core, rank, scored, visible)
            observations.append(scored)
        failure = _classify_case(
            case,
            core,
            rank,
            observations[0] if len(observations) == 1 else None,
            None,
        )
        if observations:
            failure_counts = Counter(obs["failure"]["primary_cause"] for obs in observations)
            # Report the most informative observed result when multiple configs exist.
            failure = observations[0]["failure"]
            if "none" in failure_counts:
                failure = {"primary_cause": "none", "secondary_causes": []}
        causes[failure["primary_cause"]] += 1
        rows.append(
            {
                "case_id": case["id"],
                "split": case.get("split"),
                "domains": case.get("domains", []),
                "acceptable_primary_tools": sorted(primary),
                "acceptable_tools": sorted(acceptable),
                "static_core_acceptable": bool(acceptable & core),
                "static_core_primary": bool(primary & core),
                "first_primary_rank": min(
                    (rank[name] for name in primary if name in rank), default=None
                ),
                "first_acceptable_rank": min(
                    (rank[name] for name in acceptable if name in rank), default=None
                ),
                "acceptable_at": {
                    str(depth): any(rank.get(name, 10**9) <= depth for name in acceptable)
                    for depth in DEPTHS
                },
                "primary_cause": failure["primary_cause"],
                "secondary_causes": failure["secondary_causes"],
                "rollouts": observations,
            }
        )

    return {
        "schema_version": 1,
        "corpus_cases": len(cases),
        "rollout_records": len(rollouts),
        "rollout_evidence_available": bool(rollouts),
        "tool_catalog_count": len(TOOL_METADATA),
        "current_core": sorted(core),
        "rank_summary": _rank_summary(cases, registry),
        "candidate_summary": _candidate_summary(cases, candidates, registry, core),
        "cause_counts": dict(sorted(causes.items())),
        "cases": rows,
    }


def _markdown(report: dict[str, Any]) -> str:
    """Render a bounded human-readable report."""
    lines = [
        "# MCP tool-selection corrective analysis",
        "",
        "Deterministic Plan 043 analysis; no model calls are made.",
        "",
        f"- Corpus cases: {report['corpus_cases']}",
        f"- Rollout records: {report['rollout_records']}",
        f"- Per-case rollout evidence: {'available' if report['rollout_evidence_available'] else 'not supplied'}",
        "",
        "## Failure causes",
        "",
        "| Cause | Cases |",
        "|---|---:|",
    ]
    for cause, count in report["cause_counts"].items():
        lines.append(f"| `{cause}` | {count} |")
    lines.extend(
        [
            "",
            "## Discovery recall",
            "",
            "| Split | Cases | @1 | @3 | @5 | @8 | @10 | @20 |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for split, summary in report["rank_summary"].items():
        recall = summary["acceptable_recall_at"]
        values = " | ".join(
            "—" if recall[str(d)] is None else f"{recall[str(d)]:.4f}" for d in (1, 3, 5, 8, 10, 20)
        )
        lines.append(f"| {split} | {summary['tool_cases']} | {values} |")
    lines.extend(
        [
            "",
            "## Candidate static coverage",
            "",
            "| Candidate | Tools | Dev acceptable | Held-out acceptable | Dev misses avoided |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for label, summary in report["candidate_summary"].items():
        dev = summary["by_split"].get("development", {})
        held = summary["by_split"].get("held_out", {})
        lines.append(
            f"| `{label}` | {summary['tool_count']} | {dev.get('static_acceptable_any_rate', '—')} | "
            f"{held.get('static_acceptable_any_rate', '—')} | {dev.get('current_core_misses_avoided', 0)} |"
        )
    lines.extend(
        [
            "",
            "The candidate lists are evaluation-only and do not add permanent MCP profiles. "
            "Model-selection and end-to-end claims require normalized provider-neutral rollout records.",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", default=str(DEFAULT_CASES))
    parser.add_argument("--candidate-sets", default=str(DEFAULT_CANDIDATES))
    parser.add_argument("--rollouts", default=None, help="Optional normalized rollout JSONL")
    parser.add_argument("--json", dest="json_path", default=None)
    parser.add_argument("--markdown", dest="markdown_path", default=None)
    args = parser.parse_args(argv)

    report = analyze(
        load_cases(Path(args.cases)),
        load_candidates(Path(args.candidate_sets)),
        load_rollouts(Path(args.rollouts) if args.rollouts else None),
    )
    print(json.dumps({key: value for key, value in report.items() if key != "cases"}, indent=2))
    if args.json_path:
        Path(args.json_path).write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"wrote {args.json_path}")
    if args.markdown_path:
        Path(args.markdown_path).write_text(_markdown(report), encoding="utf-8")
        print(f"wrote {args.markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
