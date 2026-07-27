#!/usr/bin/env python3
"""Compare architecture cost measurements between baseline and candidate.

Produces canonical JSON and Markdown with per-metric baseline/candidate
statistics, absolute and percentage deltas, threshold status, and
explanation fields for regressions over 15%.

Usage::

    python scripts/compare_architecture_costs.py \\
        --baseline /tmp/eggcalc-baseline.json \\
        --candidate /tmp/eggcalc-candidate.json \\
        --json-output /tmp/eggcalc-comparison.json \\
        --markdown-output /tmp/eggcalc-comparison.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _delta_pct(baseline: float, candidate: float) -> float:
    """Percentage change from baseline to candidate."""
    if baseline == 0:
        return 0.0 if candidate == 0 else float("inf")
    return round(((candidate - baseline) / baseline) * 100, 2)


def compare(baseline: dict[str, object], candidate: dict[str, object]) -> dict[str, object]:
    """Compare two architecture cost reports."""
    baseline_meas = baseline.get("measurements", {})
    candidate_meas = candidate.get("measurements", {})

    metrics: list[dict[str, object]] = []
    regressions: list[str] = []

    all_keys = sorted(set(baseline_meas.keys()) | set(candidate_meas.keys()))

    for key in all_keys:
        b = baseline_meas.get(key, {})
        c = candidate_meas.get(key, {})
        if not isinstance(b, dict) or not isinstance(c, dict):
            continue

        b_median = float(b.get("median_ms", 0))
        c_median = float(c.get("median_ms", 0))
        b_mean = float(b.get("mean_ms", 0))
        c_mean = float(c.get("mean_ms", 0))
        b_stdev = float(b.get("stdev_ms", 0))
        c_stdev = float(c.get("stdev_ms", 0))
        b_min = float(b.get("min_ms", 0))
        c_min = float(c.get("min_ms", 0))
        b_max = float(b.get("max_ms", 0))
        c_max = float(c.get("max_ms", 0))
        b_samples = int(b.get("samples", 0))
        c_samples = int(c.get("samples", 0))

        delta_median = round(c_median - b_median, 4)
        pct_median = _delta_pct(b_median, c_median)

        status = "OK"
        explanation = ""
        if pct_median > 15:
            status = "REGRESSION"
            explanation = (
                f"Median time increased by {pct_median:.1f}% "
                f"(+{delta_median:.2f}ms). "
                f"Baseline: {b_median:.2f}ms, Candidate: {c_median:.2f}ms."
            )
            regressions.append(key)
        elif pct_median < -15:
            status = "IMPROVEMENT"

        metric: dict[str, object] = {
            "metric": key,
            "baseline_median_ms": b_median,
            "candidate_median_ms": c_median,
            "delta_median_ms": delta_median,
            "delta_median_pct": pct_median,
            "baseline_mean_ms": b_mean,
            "candidate_mean_ms": c_mean,
            "baseline_stdev_ms": b_stdev,
            "candidate_stdev_ms": c_stdev,
            "baseline_min_ms": b_min,
            "candidate_min_ms": c_min,
            "baseline_max_ms": b_max,
            "candidate_max_ms": c_max,
            "baseline_samples": b_samples,
            "candidate_samples": c_samples,
            "status": status,
            "explanation": explanation,
        }

        # Optional: peak_bytes and loaded_modules
        if "peak_bytes" in b or "peak_bytes" in c:
            metric["baseline_peak_bytes"] = b.get("peak_bytes", 0)
            metric["candidate_peak_bytes"] = c.get("peak_bytes", 0)
        if "loaded_modules" in b or "loaded_modules" in c:
            metric["baseline_loaded_modules"] = b.get("loaded_modules", 0)
            metric["candidate_loaded_modules"] = c.get("loaded_modules", 0)

        metrics.append(metric)

    return {
        "baseline_sha": baseline.get("commit_sha"),
        "candidate_sha": candidate.get("commit_sha"),
        "baseline_label": baseline.get("label"),
        "candidate_label": candidate.get("label"),
        "baseline_environment": {
            "os": baseline.get("os"),
            "python": baseline.get("python_version"),
            "architecture": baseline.get("architecture"),
        },
        "candidate_environment": {
            "os": candidate.get("os"),
            "python": candidate.get("python_version"),
            "architecture": candidate.get("architecture"),
        },
        "metrics": metrics,
        "regressions": regressions,
        "total_metrics": len(metrics),
        "total_regressions": len(regressions),
    }


def to_markdown(result: dict[str, object]) -> str:
    """Format comparison result as Markdown."""
    lines: list[str] = []
    lines.append("# Architecture Cost Comparison\n")
    lines.append(f"- Baseline SHA: `{result.get('baseline_sha', 'unknown')}`")
    lines.append(f"- Candidate SHA: `{result.get('candidate_sha', 'unknown')}`")

    b_env = result.get("baseline_environment", {})
    c_env = result.get("candidate_environment", {})
    lines.append(
        f"- Baseline: {b_env.get('os')} Python {b_env.get('python')} {b_env.get('architecture')}"
    )
    lines.append(
        f"- Candidate: {c_env.get('os')} Python {c_env.get('python')} {c_env.get('architecture')}"
    )
    lines.append("")

    lines.append("## Results\n")
    lines.append("| Metric | Baseline (ms) | Candidate (ms) | Delta | % Change | Status |")
    lines.append("|--------|---------------|----------------|-------|----------|--------|")

    for m in result.get("metrics", []):
        b = m.get("baseline_median_ms", 0)
        c = m.get("candidate_median_ms", 0)
        d = m.get("delta_median_ms", 0)
        p = m.get("delta_median_pct", 0)
        s = m.get("status", "")
        lines.append(f"| {m.get('metric')} | {b:.2f} | {c:.2f} | {d:+.2f} | {p:+.1f}% | {s} |")

    lines.append("")

    regressions = result.get("regressions", [])
    if regressions:
        lines.append(f"## Regressions ({len(regressions)})\n")
        for m in result.get("metrics", []):
            if m.get("status") == "REGRESSION":
                lines.append(f"- **{m['metric']}**: {m.get('explanation', '')}")
        lines.append("")
    else:
        lines.append("## No Regressions\n")
        lines.append("All metrics within 15% threshold.\n")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    args = parser.parse_args()

    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    candidate = json.loads(args.candidate.read_text(encoding="utf-8"))

    result = compare(baseline, candidate)

    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"JSON written to {args.json_output}")

    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(to_markdown(result), encoding="utf-8")
        print(f"Markdown written to {args.markdown_output}")

    if not args.json_output and not args.markdown_output:
        print(json.dumps(result, indent=2, sort_keys=True))

    if result.get("total_regressions", 0) > 0:
        print(f"\nWARNING: {result['total_regressions']} regression(s) detected.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
