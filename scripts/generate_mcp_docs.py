#!/usr/bin/env python3
"""Generate MCP tool inventory docs from TOOL_SCHEMAS / TOOL_METADATA.

Usage:
    python scripts/generate_mcp_docs.py              # write docs/tool_inventory.md
    python scripts/generate_mcp_docs.py --check      # dry-run, exit 1 on drift

Standard-library only -- no external deps.
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

# Allow running from repo root without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eggcalc.mcp.schemas import (  # noqa: E402
    PROFILE_NAMES,
    TOOL_METADATA,
    TOOL_PROFILES,
    TOOL_SCHEMAS,
)
from eggcalc.mcp.server import TOOL_HANDLERS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "docs" / "tool_inventory.md"

# ── helpers ──────────────────────────────────────────────────────────────────


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _tools_by_category() -> dict[str, list[str]]:
    cats: dict[str, list[str]] = defaultdict(list)
    for name in TOOL_METADATA:
        cat = TOOL_METADATA[name].get("category", "uncategorized")
        cats[cat].append(name)
    for v in cats.values():
        v.sort()
    return dict(sorted(cats.items()))


def _tool_has_test(name: str) -> bool:
    """Check if a tool has a dedicated test (by name pattern in tests/)."""
    tests_dir = ROOT / "tests"
    if not tests_dir.exists():
        return False
    for f in tests_dir.glob("test_*.py"):
        content = _read_text(f)
        if name in content:
            return True
    return False


def _tool_in_file(name: str, pattern: str) -> bool:
    """Check if tool name appears in files matching pattern."""
    for f in ROOT.glob(pattern):
        content = _read_text(f)
        if name in content:
            return True
    return False


def _tool_description(name: str) -> str:
    """Get short description from schema."""
    schema = TOOL_SCHEMAS.get(name, {})
    desc = schema.get("description", "")
    # Take first sentence, truncate to 80 chars
    if "." in desc:
        desc = desc.split(".")[0] + "."
    if len(desc) > 80:
        desc = desc[:77] + "..."
    return desc


def _sorted_tools() -> list[str]:
    """Tools sorted alphabetically."""
    return sorted(TOOL_METADATA.keys())


# ── sections ─────────────────────────────────────────────────────────────────


def _header() -> list[str]:
    total = len(TOOL_METADATA)
    return [
        "# MCP Tool Inventory",
        "",
        "Canonical reference for all MCP tools exposed by `eggcalc.mcp.server.TOOL_HANDLERS`.",
        "",
        f"**Total: {total} tools**",
        "",
        "> **Auto-generated** -- do not edit manually.",
        "> Run `python scripts/generate_mcp_docs.py` to regenerate.",
        "",
    ]


def _inventory_table() -> list[str]:
    tools = _sorted_tools()
    lines = [
        "## Inventory Table",
        "",
        "| # | Tool Name | Category | Tier | Implemented | README | docs/mcp.md | Tests | Notes |",
        "|---|-----------|----------|------|-------------|--------|-------------|-------|-------|",
    ]
    for i, name in enumerate(tools, 1):
        meta = TOOL_METADATA[name]
        tier = meta.get("tier", "?")
        cat = meta.get("category", "?")
        implemented = "yes" if name in TOOL_HANDLERS else "no"
        in_readme = "yes" if _tool_in_file(name, "README.md") else "no"
        in_mcp_doc = "yes" if _tool_in_file(name, "docs/mcp.md") else "no"
        has_test = "yes" if _tool_has_test(name) else "no"
        desc = _tool_description(name)
        lines.append(
            f"| {i} | `{name}` | {cat} | {tier} | {implemented} | {in_readme} "
            f"| {in_mcp_doc} | {has_test} | {desc} |"
        )
    lines.append("")
    return lines


def _legend() -> list[str]:
    return [
        "## Legend",
        "",
        "- **Tier 0**: Ultra-common, small-schema tools - always available",
        "- **Tier 1**: Default coding-agent sanity tools - low context, recommended default",
        "- **Tier 2**: Heavier analysis tools - moderate context, opt-in for text/unicode/config work",
        "- **Tier 3**: Domain-specific tools - more context, opt-in for specialized workflows",
        "",
    ]


def _summary_stats() -> list[str]:
    tools = _sorted_tools()
    total = len(tools)
    in_readme = sum(1 for t in tools if _tool_in_file(t, "README.md"))
    in_mcp = sum(1 for t in tools if _tool_in_file(t, "docs/mcp.md"))
    have_tests = sum(1 for t in tools if _tool_has_test(t))
    missing_tests = total - have_tests
    return [
        "## Summary Statistics",
        "",
        "| Field | Count |",
        "|-------|------:|",
        f"| Total tools | {total} |",
        f"| Documented in README | {in_readme} |",
        f"| Documented in docs/mcp.md | {in_mcp} |",
        f"| Missing from docs/mcp.md | {total - in_mcp} |",
        f"| Have tests | {have_tests} |",
        f"| Missing tests | {missing_tests} |",
        "",
    ]


def _category_breakdown() -> list[str]:
    cats = _tools_by_category()
    lines = [
        "## Category Breakdown",
        "",
        "| Category | Tools |",
        "|----------|-------|",
    ]
    for cat, tools in cats.items():
        tool_list = ", ".join(f"`{t}`" for t in tools)
        lines.append(f"| {cat} | {tool_list} |")
    lines.append("")
    return lines


def _profile_membership() -> list[str]:
    lines = ["## Profile Membership", ""]
    for pname in PROFILE_NAMES:
        tools = TOOL_PROFILES.get(pname, [])
        lines.append(f"### {pname} ({len(tools)} tools)")
        lines.append("")
        by_cat: dict[str, list[str]] = defaultdict(list)
        for t in tools:
            cat = TOOL_METADATA.get(t, {}).get("category", "?")
            by_cat[cat].append(t)
        lines.append("| Category | Tools |")
        lines.append("|----------|-------|")
        for cat in sorted(by_cat):
            tool_list = ", ".join(f"`{t}`" for t in sorted(by_cat[cat]))
            lines.append(f"| {cat} | {tool_list} |")
        lines.append("")
    return lines


def _schema_detail_section() -> list[str]:
    return [
        "## Schema Detail Levels",
        "",
        "| Level | Description |",
        "|-------|-------------|",
        "| `compact` | Description + tier + tags only (smallest) |",
        "| `normal` | Adds input types, enums, constraints, output structure |",
        "| `full` | Complete JSON Schema with all property descriptions |",
        "",
    ]


def _source_of_truth() -> list[str]:
    return [
        "## Source of Truth",
        "",
        "The canonical tool list lives in `tests/fixtures/mcp_tool_registry_expected.json`.",
        "The test at `tests/test_tool_inventory.py` enforces that `TOOL_HANDLERS` keys match this fixture.",
        "",
    ]


def generate() -> str:
    sections = [
        _header(),
        _inventory_table(),
        _legend(),
        _summary_stats(),
        _category_breakdown(),
        _profile_membership(),
        _schema_detail_section(),
        _source_of_truth(),
    ]
    return "\n".join(line for sec in sections for line in sec)


# ── main ─────────────────────────────────────────────────────────────────────


def main() -> int:
    check_mode = "--check" in sys.argv
    content = generate()

    if check_mode:
        if not OUTPUT.exists():
            print(
                f"FAIL: {OUTPUT} does not exist -- run without --check first",
                file=sys.stderr,
            )
            return 1
        existing = OUTPUT.read_text(encoding="utf-8")
        if existing != content:
            existing_lines = existing.splitlines()
            new_lines = content.splitlines()
            diff_count = sum(1 for a, b in zip(existing_lines, new_lines) if a != b)
            diff_count += abs(len(existing_lines) - len(new_lines))
            print(
                f"FAIL: {OUTPUT} is out of date ({diff_count} lines differ). "
                "Run `python scripts/generate_mcp_docs.py` to regenerate.",
                file=sys.stderr,
            )
            return 1
        print(f"OK: {OUTPUT} is up to date ({len(TOOL_METADATA)} tools)")
        return 0

    OUTPUT.write_text(content, encoding="utf-8")
    print(f"Wrote {OUTPUT} ({len(TOOL_METADATA)} tools)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
