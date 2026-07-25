#!/usr/bin/env python3
"""Validate synchronized Release 4–6 closure evidence.

The historical portions of the release records are deliberately ignored.  A
document is eligible for closure validation only after it contains a
``## Final Closure Evidence`` section with exact candidate identity, lane
totals, mandatory job names, and both performance identities.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DOCUMENTS = tuple(
    ROOT / "docs" / name
    for name in (
        "release_4_evidence.md",
        "release_5_evidence.md",
        "release_6_evidence.md",
    )
)
SECTION_MARKER = "## Final Closure Evidence"
SHA_RE = re.compile(r"(?mi)^-\s*(?:closure_code_sha|code_sha):\s*`?([0-9a-f]{40})`?\s*$")
RUN_RE = re.compile(r"(?mi)^-\s*(?:closure_workflow_run_id|workflow_run_id):\s*`?(\d+)`?\s*$")
LANE_RE = re.compile(
    r"(?mi)^-\s*lane\s+[^:]+:\s*"
    r"collected=(\d+)\s+passed=(\d+)\s+skipped=(\d+)\s+"
    r"xfail(?:ed)?=(\d+)\s+failed=(\d+)\s*$"
)
MANDATORY_MARKERS = (
    "ordinary ruff",
    "black",
    "ordinary mypy",
    "strict mypy",
    "strict ruff",
    "authority-boundary",
    "deterministic build",
    "authority inventory",
    "source typed consumer",
    "installed-wheel typed consumer",
    "mcp closure",
    "unit closure",
    "release-surface",
)


def _final_section(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if SECTION_MARKER not in text:
        raise ValueError(f"{path.name}: missing {SECTION_MARKER!r}")
    return text.split(SECTION_MARKER, 1)[1]


def _one_match(pattern: re.Pattern[str], section: str, label: str, path: Path) -> str:
    matches = pattern.findall(section)
    if len(matches) != 1:
        raise ValueError(f"{path.name}: expected one {label}, found {len(matches)}")
    return matches[0]


def validate_documents(paths: tuple[Path, ...] = DEFAULT_DOCUMENTS) -> list[str]:
    """Return deterministic validation errors for synchronized evidence files."""
    errors: list[str] = []
    identities: list[tuple[str, str]] = []
    sections: list[tuple[Path, str]] = []
    for path in paths:
        try:
            section = _final_section(path)
            sha = _one_match(SHA_RE, section, "full closure code SHA", path)
            run_id = _one_match(RUN_RE, section, "workflow run ID", path)
        except (OSError, ValueError) as exc:
            errors.append(str(exc))
            continue
        identities.append((sha, run_id))
        sections.append((path, section))

    if len(set(identities)) > 1:
        errors.append("Release 4–6 closure SHA/workflow identities do not match")

    for path, section in sections:
        lowered = section.lower()
        if re.search(r"~\s*\d+|\ball\s+(?:checks|tests)\s+pass\b", lowered):
            errors.append(f"{path.name}: approximate or non-numeric final count claim")
        if "release 6" in lowered and "registry" in lowered and "legacy" in lowered:
            errors.append(f"{path.name}: final evidence still claims legacy registry authority")
        if "windows" in lowered and "current" in lowered and "failed" in lowered:
            errors.append(f"{path.name}: historical Windows failure is labeled current")
        missing = [marker for marker in MANDATORY_MARKERS if marker not in lowered]
        if missing:
            errors.append(f"{path.name}: missing mandatory jobs: {', '.join(missing)}")

        lanes = LANE_RE.findall(section)
        if not lanes:
            errors.append(f"{path.name}: no exact lane totals found")
        for collected, passed, skipped, xfailed, failed in lanes:
            if int(collected) != int(passed) + int(skipped) + int(xfailed) + int(failed):
                errors.append(f"{path.name}: lane totals do not add up")
        if "baseline" not in lowered or "final" not in lowered:
            errors.append(f"{path.name}: performance section lacks baseline/final identity")

    if sections and len(sections) != len(paths):
        errors.append("Not all Release 4–6 documents contain valid final closure sections")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*", type=Path, default=list(DEFAULT_DOCUMENTS))
    args = parser.parse_args()
    errors = validate_documents(tuple(args.paths))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Release 4–6 evidence is internally consistent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
