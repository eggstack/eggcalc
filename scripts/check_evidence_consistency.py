#!/usr/bin/env python3
"""Validate synchronized Release 4-6 closure evidence.

Supports two modes:

- ``--candidate-state``: verifies that no placeholder final evidence exists
  and that no stale SHA/workflow claims are present.  Used during the code
  candidate phase before a successful CI run.

- ``--final``: requires the complete proof set including exact candidate SHA,
  workflow run ID, lane totals, mandatory job names, and performance
  identities.  Used after the code candidate receives a green CI run.

The historical portions of the release records are deliberately ignored.  A
document is eligible for final closure validation only after it contains a
``## Final Closure Evidence`` section with exact candidate identity, lane
totals, mandatory job names, and both performance identities.
"""

from __future__ import annotations

import argparse
import re
import sys
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
PLACEHOLDER_SHA = "800832196439558383d22300ef36870c997437da"
PLACEHOLDER_RUN_ID = "0000000000"
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


def _final_section(path: Path) -> str | None:
    """Return the final closure section, or None if not present."""
    text = path.read_text(encoding="utf-8")
    if SECTION_MARKER not in text:
        return None
    return text.split(SECTION_MARKER, 1)[1]


def _is_placeholder_evidence(section: str) -> bool:
    """Check if the section contains only placeholder/unfinalized evidence."""
    lowered = section.lower()
    # If it says "intentionally absent", it's the correct unfinalized state
    if "intentionally absent" in lowered:
        return True
    # If it contains placeholder SHA or run ID, it's stale placeholder data
    if PLACEHOLDER_SHA in section:
        return True
    if PLACEHOLDER_RUN_ID in section:
        return True
    return False


def _has_real_evidence(section: str) -> bool:
    """Check if the section contains real (non-placeholder) evidence."""
    if _is_placeholder_evidence(section):
        return False
    # Must have at least a SHA and run ID
    shas = SHA_RE.findall(section)
    runs = RUN_RE.findall(section)
    return len(shas) >= 1 and len(runs) >= 1


def _one_match(pattern: re.Pattern[str], section: str, label: str, path: Path) -> str:
    matches = pattern.findall(section)
    if len(matches) != 1:
        raise ValueError(f"{path.name}: expected one {label}, found {len(matches)}")
    return matches[0]


def validate_candidate_state(paths: tuple[Path, ...] = DEFAULT_DOCUMENTS) -> list[str]:
    """Validate that no placeholder final evidence exists.

    Used during the code candidate phase.  Accepts either:
    - No Final Closure Evidence section at all
    - A section that says evidence is intentionally absent
    - A section with real (non-placeholder) evidence

    Rejects:
    - Placeholder SHA (80083219...)
    - Placeholder workflow run ID (0000000000)
    - Stale claims that Releases 4-6 are closed with placeholder data
    """
    errors: list[str] = []
    for path in paths:
        try:
            section = _final_section(path)
        except OSError as exc:
            errors.append(str(exc))
            continue

        if section is None:
            # No final section is acceptable in candidate state
            continue

        if _is_placeholder_evidence(section):
            # Intentionally absent is the correct state
            if "intentionally absent" in section.lower():
                continue
            # Stale placeholder data
            if PLACEHOLDER_SHA in section:
                errors.append(f"{path.name}: contains placeholder SHA {PLACEHOLDER_SHA[:12]}...")
            if PLACEHOLDER_RUN_ID in section:
                errors.append(
                    f"{path.name}: contains placeholder workflow run ID {PLACEHOLDER_RUN_ID}"
                )
    return errors


def validate_final(
    paths: tuple[Path, ...] = DEFAULT_DOCUMENTS,
    candidate_sha: str | None = None,
) -> list[str]:
    """Validate complete final evidence.

    Used after the code candidate receives a green CI run.  Requires:
    - All documents have a Final Closure Evidence section
    - All documents reference the same candidate SHA and run ID
    - No placeholder SHAs or run IDs
    - Exact lane totals that add up
    - All mandatory job markers present
    - Performance identities referenced
    - If candidate_sha is provided, all SHAs must match it
    """
    errors: list[str] = []
    identities: list[tuple[str, str]] = []
    sections: list[tuple[Path, str]] = []

    for path in paths:
        try:
            section = _final_section(path)
            if section is None:
                errors.append(f"{path.name}: missing {SECTION_MARKER!r}")
                continue
            if _is_placeholder_evidence(section):
                errors.append(f"{path.name}: contains placeholder/unfinalized evidence")
                continue
            sha = _one_match(SHA_RE, section, "full closure code SHA", path)
            run_id = _one_match(RUN_RE, section, "workflow run ID", path)
        except (OSError, ValueError) as exc:
            errors.append(str(exc))
            continue

        if sha == PLACEHOLDER_SHA:
            errors.append(f"{path.name}: SHA is the known placeholder")
        if run_id == PLACEHOLDER_RUN_ID:
            errors.append(f"{path.name}: workflow run ID is placeholder {PLACEHOLDER_RUN_ID}")
        if candidate_sha and sha != candidate_sha:
            errors.append(
                f"{path.name}: SHA {sha[:12]}... does not match candidate {candidate_sha[:12]}..."
            )

        identities.append((sha, run_id))
        sections.append((path, section))

    if len(set(identities)) > 1:
        errors.append("Release 4-6 closure SHA/workflow identities do not match")

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
        errors.append("Not all Release 4-6 documents contain valid final closure sections")
    return errors


def validate_documents(paths: tuple[Path, ...] = DEFAULT_DOCUMENTS) -> list[str]:
    """Backward-compatible validator: try final mode, fall back to candidate state.

    Returns empty list if either mode passes.  For new code, use
    ``validate_candidate_state`` or ``validate_final`` directly.
    """
    candidate_errors = validate_candidate_state(paths)
    if candidate_errors:
        # Candidate state has issues (stale placeholders) - report them
        return candidate_errors
    # Candidate state is valid. Check if there's real evidence to validate.
    has_any_real = False
    for path in paths:
        section = _final_section(path)
        if section is not None and _has_real_evidence(section):
            has_any_real = True
            break
    if has_any_real:
        return validate_final(paths)
    # No real evidence yet - candidate state is the valid mode
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path, default=list(DEFAULT_DOCUMENTS))
    parser.add_argument(
        "--candidate-state",
        action="store_true",
        help="Validate that no placeholder final evidence exists (code candidate phase)",
    )
    parser.add_argument(
        "--final",
        action="store_true",
        help="Validate complete final evidence (after green CI run)",
    )
    parser.add_argument(
        "--candidate-sha",
        type=str,
        default=None,
        help="Expected candidate SHA for --final mode",
    )
    args = parser.parse_args()

    paths = tuple(args.paths)

    if args.final:
        errors = validate_final(paths, candidate_sha=args.candidate_sha)
    elif args.candidate_state:
        errors = validate_candidate_state(paths)
    else:
        errors = validate_documents(paths)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Release 4-6 evidence is internally consistent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
