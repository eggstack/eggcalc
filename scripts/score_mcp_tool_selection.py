#!/usr/bin/env python3
"""Score provider-neutral tool-selection rollouts (Plan 041 Workstream H).

Reads a JSONL file of rollout records (one per evaluated case; see
`evals/mcp_tool_selection/README.md` for the interchange format produced
by codegg, Codex, Claude Code, or any external harness) and scores them
against `evals/mcp_tool_selection/cases.json`.

Stdlib only. Missing provider token fields are accepted; deterministic
call-path metrics are always computed. LLM evaluation itself stays
outside the repo: CI validates corpus + scorer, never network calls.

Example:
    python scripts/score_mcp_tool_selection.py rollouts.jsonl
    python scripts/score_mcp_tool_selection.py rollouts.jsonl --split held_out
    python scripts/score_mcp_tool_selection.py rollouts.jsonl --footprint surface.json
    python scripts/score_mcp_tool_selection.py --help
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CASES = REPO_ROOT / "evals" / "mcp_tool_selection" / "cases.json"

sys.path.insert(0, str(REPO_ROOT))

from eggcalc.mcp.schemas import TOOL_METADATA  # noqa: E402

CATALOG_TOOLS = frozenset(TOOL_METADATA)


def load_cases(path: Path) -> dict[str, dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = payload["cases"] if isinstance(payload, dict) else payload
    return {c["case_id" if "case_id" in c else "id"]: c for c in cases}


def load_rollouts(path: Path) -> list[dict]:
    records = []
    with path.open(encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno}: invalid JSON: {exc}") from exc
    return records


def score_record(case: dict, record: dict) -> dict:
    """Score one rollout record against its case."""
    primary = set(case.get("acceptable_primary_tools", []))
    supporting = set(case.get("acceptable_supporting_tools", []))
    acceptable = primary | supporting
    calls = record.get("tool_calls", []) or []
    names = [c.get("name", "") for c in calls if isinstance(c, dict)]

    invalid_names = [n for n in names if n not in CATALOG_TOOLS]
    invalid_args = sum(
        1 for c in calls if isinstance(c, dict) and c.get("arguments_valid") is False
    )
    valid_names = [n for n in names if n in CATALOG_TOOLS]
    redundant = len(valid_names) - len(set(valid_names)) if valid_names else 0
    irrelevant = sum(1 for n in valid_names if n not in acceptable)

    if not acceptable:
        # No-tool case: any call is irrelevant; success means silence.
        first_ok = len(names) == 0
        any_ok = len(names) == 0
    else:
        first_ok = bool(names) and names[0] in primary
        any_ok = any(n in acceptable for n in names)

    return {
        "case_id": record.get("case_id"),
        "acceptable_first_tool": first_ok,
        "acceptable_tool_used": any_ok,
        "irrelevant_calls": irrelevant,
        "redundant_calls": max(redundant, 0),
        "invalid_names": len(invalid_names),
        "invalid_name_list": invalid_names,
        "invalid_arguments": invalid_args,
        "total_calls": len(names),
        "completed": bool(record.get("completed", False)),
        "task_correct": record.get("task_correct"),  # may be None (not reported)
        "input_tokens": record.get("input_tokens"),
        "output_tokens": record.get("output_tokens"),
    }


def aggregate(scored: list[dict]) -> dict:
    n = len(scored)
    if not n:
        return {"n": 0}
    reported = [s for s in scored if s["task_correct"] is not None]
    token_pairs = [
        (s["input_tokens"], s["output_tokens"])
        for s in scored
        if isinstance(s["input_tokens"], int) and isinstance(s["output_tokens"], int)
    ]
    return {
        "n": n,
        "first_tool_rate": round(sum(s["acceptable_first_tool"] for s in scored) / n, 4),
        "acceptable_anywhere_rate": round(
            sum(s["acceptable_tool_used"] for s in scored) / n, 4
        ),
        "task_correct_rate": (
            round(sum(bool(s["task_correct"]) for s in reported) / len(reported), 4)
            if reported
            else None
        ),
        "task_correct_reported": len(reported),
        "mean_total_calls": round(sum(s["total_calls"] for s in scored) / n, 2),
        "mean_irrelevant_calls": round(sum(s["irrelevant_calls"] for s in scored) / n, 2),
        "mean_redundant_calls": round(sum(s["redundant_calls"] for s in scored) / n, 2),
        "total_invalid_names": sum(s["invalid_names"] for s in scored),
        "total_invalid_arguments": sum(s["invalid_arguments"] for s in scored),
        "mean_input_tokens": (
            round(sum(p[0] for p in token_pairs) / len(token_pairs), 1) if token_pairs else None
        ),
        "mean_output_tokens": (
            round(sum(p[1] for p in token_pairs) / len(token_pairs), 1) if token_pairs else None
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rollouts", help="JSONL rollout records file")
    parser.add_argument("--cases", default=str(DEFAULT_CASES))
    parser.add_argument(
        "--split",
        default=None,
        choices=["development", "held_out"],
        help="Score only one corpus split.",
    )
    parser.add_argument(
        "--footprint",
        default=None,
        help="surface JSON from measure_mcp_tool_surface.py --json; attaches "
        "catalog bytes for the rollout catalog_config when it matches a "
        "'<profile>/<detail>' key.",
    )
    parser.add_argument("--json", dest="json_path", default=None)
    args = parser.parse_args(argv)

    cases = load_cases(Path(args.cases))
    records = load_rollouts(Path(args.rollouts))
    if args.split:
        records = [
            r for r in records if cases.get(r.get("case_id", ""), {}).get("split") == args.split
        ]

    footprint: dict[str, dict] = {}
    if args.footprint:
        payload = json.loads(Path(args.footprint).read_text(encoding="utf-8"))
        for cfg in payload.get("configs", []):
            footprint[f"{cfg['profile']}/{cfg['schema_detail']}"] = cfg

    scored = []
    errors = []
    for record in records:
        case_id = record.get("case_id")
        case = cases.get(case_id)
        if case is None:
            errors.append(f"unknown case_id: {case_id!r}")
            continue
        entry = score_record(case, record)
        entry["split"] = case.get("split")
        entry["domains"] = case.get("domains", [])
        cfg = record.get("catalog_config")
        entry["catalog_config"] = cfg
        fp = footprint.get(cfg) if isinstance(cfg, str) else None
        entry["catalog_bytes"] = fp["total_bytes"] if fp else None
        entry["catalog_tool_count"] = fp["tool_count"] if fp else None
        scored.append(entry)

    by_split: dict[str, list[dict]] = defaultdict(list)
    by_domain: dict[str, list[dict]] = defaultdict(list)
    for s in scored:
        by_split[s.get("split", "?")].append(s)
        for d in s.get("domains", []):
            by_domain[d].append(s)

    report = {
        "rollouts": len(records),
        "scored": len(scored),
        "errors": errors,
        "overall": aggregate(scored),
        "by_split": {k: aggregate(v) for k, v in sorted(by_split.items())},
        "by_domain": {k: aggregate(v) for k, v in sorted(by_domain.items())},
        "cases": scored,
    }

    print(f"rollouts: {len(records)} scored: {len(scored)} errors: {len(errors)}")
    for err in errors[:10]:
        print(f"  ERROR: {err}")
    print(json.dumps({k: v for k, v in report.items() if k != "cases"}, indent=2))
    if args.json_path:
        Path(args.json_path).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {args.json_path}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
