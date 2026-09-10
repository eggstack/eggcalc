#!/usr/bin/env python3
"""Measure the serialized MCP tool-surface footprint (Plan 041 Workstream B).

Deterministic stdlib-only measurement of what `tools/list` actually sends
for each (profile, schema-detail) exposure strategy. Renders through the
real server code path (`_handle_list_tools` on a `full`-configured
`McpServer`) and serializes canonically, so bytes are identical across
runs, processes, and platforms.

Example:
    python scripts/measure_mcp_tool_surface.py
    python scripts/measure_mcp_tool_surface.py --json /tmp/surface.json
    python scripts/measure_mcp_tool_surface.py --profiles full agent_core --details full compact
    python scripts/measure_mcp_tool_surface.py --discover "validate unified diff" --limit 3

Metric notes:
- No tokenizer dependency: the repository metric is serialized UTF-8
  bytes/characters so CI reproduces it everywhere. External evaluation
  reports may additionally record provider input tokens.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eggcalc.mcp.server import (  # noqa: E402
    McpServer,
    McpServerConfig,
    _handle_list_tools,
)

CANONICAL_DUMPS_KWARGS = {"sort_keys": True, "separators": (",", ":")}

DEFAULT_PROFILES = ["full", "default", "codegg_core", "codegg_core_min", "agent_core"]
DEFAULT_DETAILS = ["full", "normal", "compact"]


def _utf8_len(obj: object) -> int:
    return len(json.dumps(obj, **CANONICAL_DUMPS_KWARGS).encode("utf-8"))


def measure_surface(
    server: McpServer, profile: str, detail: str, names: list[str] | None = None
) -> dict:
    """Render tools/list for (profile, detail[, names]) and measure it."""
    params: dict = {"profile": profile, "schema_detail": detail}
    if names is not None:
        params["names"] = names
    request = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": params}
    response = _handle_list_tools(request, server)
    if "error" in response:
        raise ValueError(f"tools/list failed for {profile}/{detail}: {response['error']}")
    tools = response["result"]["tools"]

    total_bytes = _utf8_len(tools)
    description_bytes = sum(len((t.get("description") or "").encode("utf-8")) for t in tools)
    input_bytes = sum(_utf8_len(t.get("inputSchema")) for t in tools)
    output_bytes = sum(_utf8_len(t.get("outputSchema")) for t in tools)
    annotation_bytes = sum(_utf8_len(t.get("annotations")) for t in tools)

    per_tool = sorted(
        ((t["name"], _utf8_len(t)) for t in tools), key=lambda kv: (-kv[1], kv[0])
    )
    categories: dict[str, int] = {}
    tiers: dict[str, int] = {}
    for t in tools:
        categories[str(t.get("category"))] = categories.get(str(t.get("category")), 0) + 1
        tiers[str(t.get("tier"))] = tiers.get(str(t.get("tier")), 0) + 1

    return {
        "profile": profile,
        "schema_detail": detail,
        "names_filter": names,
        "tool_count": len(tools),
        "total_bytes": total_bytes,
        "description_bytes": description_bytes,
        "input_schema_bytes": input_bytes,
        "output_schema_bytes": output_bytes,
        "annotation_bytes": annotation_bytes,
        "other_bytes": total_bytes - description_bytes - input_bytes - output_bytes
        - annotation_bytes,
        "largest_tools": [{"name": n, "bytes": b} for n, b in per_tool[:5]],
        "categories": dict(sorted(categories.items())),
        "tiers": dict(sorted(tiers.items())),
    }


def summarize(measurements: list[dict]) -> list[dict]:
    """Attach baseline-relative reduction percentages (baseline: full/full)."""
    baseline = next(
        (
            m
            for m in measurements
            if m["profile"] == "full"
            and m["schema_detail"] == "full"
            and not m["names_filter"]
        ),
        None,
    )
    base_bytes = baseline["total_bytes"] if baseline else 0
    for m in measurements:
        if base_bytes:
            m["reduction_vs_full_full_pct"] = round(
                100.0 * (base_bytes - m["total_bytes"]) / base_bytes, 1
            )
        else:
            m["reduction_vs_full_full_pct"] = 0.0
    return measurements


def format_table(measurements: list[dict]) -> str:
    header = (
        f"{'profile':<16}{'detail':<8}{'tools':>6}{'total B':>10}"
        f"{'desc B':>9}{'in B':>9}{'out B':>9}{'reduct%':>9}"
    )
    rows = [header, "-" * len(header)]
    for m in measurements:
        label = m["profile"]
        if m["names_filter"]:
            label += f"+{len(m['names_filter'])}names"
        rows.append(
            f"{label:<16}{m['schema_detail']:<8}{m['tool_count']:>6}"
            f"{m['total_bytes']:>10}{m['description_bytes']:>9}"
            f"{m['input_schema_bytes']:>9}{m['output_schema_bytes']:>9}"
            f"{m['reduction_vs_full_full_pct']:>8.1f}%"
        )
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profiles", nargs="*", default=DEFAULT_PROFILES)
    parser.add_argument("--details", nargs="*", default=DEFAULT_DETAILS)
    parser.add_argument("--json", dest="json_path", default=None)
    parser.add_argument(
        "--discover",
        default=None,
        help="Also measure agent_core/compact plus a names-filtered subset "
        "discovered via ToolRegistry.search_tools for this query.",
    )
    parser.add_argument("--limit", type=int, default=3)
    args = parser.parse_args(argv)

    server = McpServer(config=McpServerConfig(profile="full"))
    try:
        measurements = [
            measure_surface(server, profile, detail)
            for profile in args.profiles
            for detail in args.details
        ]
        if args.discover is not None:
            matches = server.registry.search_tools(args.discover, limit=args.limit)
            names = [m["name"] for m in matches]
            print(f"discovered for {args.discover!r}: {names}")
            measurements.append(measure_surface(server, "full", "full", names=names))
    finally:
        server.close()

    measurements = summarize(measurements)
    print(format_table(measurements))
    if args.json_path:
        payload = {"configs": measurements}
        Path(args.json_path).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"wrote {args.json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
