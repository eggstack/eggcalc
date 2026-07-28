#!/usr/bin/env python3
"""Validate synchronized Release 4-6 closure evidence.

Supports two modes:

- ``--candidate-state``: verifies that no placeholder final evidence exists,
  no stale SHA/workflow claims are present, and no final manifest/snapshot
  files exist.  Used during the code candidate phase.

- ``--final``: requires the complete proof set including exact candidate SHA,
  workflow run ID, lane totals, mandatory job names, performance identities,
  Git ancestry, evidence-only diff allowlist, and artifact hash consistency.
  Used after the code candidate receives a green CI run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
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
    r"xfail(?:ed)?=(\d+)\s+xpassed=(\d+)\s+failed=(\d+)\s*$"
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
EVIDENCE_ALLOWLIST = {
    "docs/release_4_evidence.md",
    "docs/release_5_evidence.md",
    "docs/release_6_evidence.md",
    "docs/evidence/releases-4-6-final.json",
    "docs/evidence/releases-4-6-ci-run.json",
    "docs/evidence/releases-4-6-inventory.json",
}
FINAL_MANIFEST = ROOT / "docs" / "evidence" / "releases-4-6-final.json"
FINAL_CI_RUN = ROOT / "docs" / "evidence" / "releases-4-6-ci-run.json"
FINAL_INVENTORY = ROOT / "docs" / "evidence" / "releases-4-6-inventory.json"


def _final_section(path: Path) -> str | None:
    """Return the final closure section, or None if not present."""
    text = path.read_text(encoding="utf-8")
    if SECTION_MARKER not in text:
        return None
    return text.split(SECTION_MARKER, 1)[1]


def _is_placeholder_evidence(section: str) -> bool:
    """Check if the section contains only placeholder/unfinalized evidence."""
    lowered = section.lower()
    if "intentionally absent" in lowered:
        return True
    if PLACEHOLDER_SHA in section:
        return True
    if PLACEHOLDER_RUN_ID in section:
        return True
    return False


def _has_real_evidence(section: str) -> bool:
    """Check if the section contains real (non-placeholder) evidence."""
    if _is_placeholder_evidence(section):
        return False
    shas = SHA_RE.findall(section)
    runs = RUN_RE.findall(section)
    return len(shas) >= 1 and len(runs) >= 1


def _one_match(pattern: re.Pattern[str], section: str, label: str, path: Path) -> str:
    matches = pattern.findall(section)
    if len(matches) != 1:
        raise ValueError(f"{path.name}: expected one {label}, found {len(matches)}")
    return matches[0]


def _git_parent_sha() -> str | None:
    """Return HEAD^ SHA or None if not a git repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD^"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _git_head_sha() -> str | None:
    """Return HEAD SHA or None if not a git repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _git_diff_names(parent_sha: str, head_sha: str) -> set[str]:
    """Return set of file names changed between parent and head."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", parent_sha, head_sha],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return {line.strip() for line in result.stdout.splitlines() if line.strip()}
    except (subprocess.CalledProcessError, FileNotFoundError):
        return set()


def _sha256_file(path: Path) -> str:
    """Compute SHA-256 of a file, normalizing line endings."""
    h = hashlib.sha256()
    h.update(path.read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()


def validate_candidate_state(
    paths: tuple[Path, ...] = DEFAULT_DOCUMENTS,
    *,
    check_repo_files: bool = True,
) -> list[str]:
    """Validate that no placeholder final evidence exists.

    Used during the code candidate phase.  Accepts either:
    - No Final Closure Evidence section at all
    - A section that says evidence is intentionally absent
    - A section with real (non-placeholder) evidence

    Rejects:
    - Placeholder SHA (80083219...)
    - Placeholder workflow run ID (0000000000)
    - Stale claims that Releases 4-6 are closed with placeholder data
    - Existence of final manifest, CI run snapshot, or inventory snapshot
      (only when check_repo_files=True, the default for real repo validation)
    """
    errors: list[str] = []

    # Reject final evidence files in candidate state
    if check_repo_files:
        for final_file in (FINAL_MANIFEST, FINAL_CI_RUN, FINAL_INVENTORY):
            if final_file.is_file():
                errors.append(
                    f"Final evidence file exists during candidate phase: {final_file.name}"
                )

    for path in paths:
        try:
            section = _final_section(path)
        except OSError as exc:
            errors.append(str(exc))
            continue

        if section is None:
            continue

        if _is_placeholder_evidence(section):
            if "intentionally absent" in section.lower():
                continue
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
    *,
    check_git_ancestry: bool = True,
) -> list[str]:
    """Validate complete final evidence.

    Used after the code candidate receives a green CI run.  Requires:
    - All documents have a Final Closure Evidence section
    - All documents reference the same candidate SHA and run ID
    - No placeholder SHAs or run IDs
    - Exact lane totals that add up
    - All mandatory job markers present
    - Performance identities referenced
    - Git ancestry: HEAD^ == candidate SHA
    - Evidence diff is limited to the documented allowlist
    - Artifact hashes match committed files
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
        for collected, passed, skipped, xfailed, xpassed, failed in lanes:
            total = int(passed) + int(skipped) + int(xfailed) + int(xpassed) + int(failed)
            if int(collected) != total:
                errors.append(f"{path.name}: lane totals do not add up")
        if "baseline" not in lowered or "final" not in lowered:
            errors.append(f"{path.name}: performance section lacks baseline/final identity")

    if sections and len(sections) != len(paths):
        errors.append("Not all Release 4-6 documents contain valid final closure sections")

    # --- Git ancestry verification ---
    if candidate_sha and check_git_ancestry:
        head = _git_head_sha()
        parent = _git_parent_sha()
        if head is None:
            errors.append("Cannot verify Git ancestry: not a git repository")
        elif parent is None:
            errors.append("Cannot verify Git ancestry: HEAD has no parent")
        else:
            if parent != candidate_sha:
                errors.append(
                    f"Git ancestry: HEAD^ is {parent[:12]}..., expected candidate {candidate_sha[:12]}..."
                )

            # --- Evidence diff allowlist verification ---
            changed = _git_diff_names(parent, head)
            unexpected = changed - EVIDENCE_ALLOWLIST
            if unexpected:
                errors.append(
                    f"Evidence commit modifies files outside allowlist: {', '.join(sorted(unexpected))}"
                )

    # --- Artifact hash verification ---
    if FINAL_MANIFEST.is_file():
        manifest = json.loads(FINAL_MANIFEST.read_text(encoding="utf-8"))
        artifact_hashes = manifest.get("artifact_hashes", {})
        for artifact_key, entry in artifact_hashes.items():
            # Each entry maps to {"path": "...", "sha256": "...", "note": "..."} or a bare hash.
            if isinstance(entry, dict):
                info = entry
                expected = info.get("sha256")
                rel_path = info.get("path")
                note = info.get("note", "")
            else:
                expected = entry
                rel_path = None
                note = ""
            if not expected or not rel_path:
                continue
            # Built artefacts (wheel/sdist/single_file) are not committed.
            # If the entry is flagged as a built/identity-only record, skip
            # both existence and hash verification — the CI-built artifact
            # has a different hash than any local build.
            if "Built during" in note or "not committed" in note:
                if not (isinstance(expected, str) and len(expected) == 64):
                    errors.append(f"Artifact {artifact_key}: missing 64-char SHA-256")
                continue
            full = ROOT / rel_path
            if not full.is_file():
                errors.append(f"Artifact {artifact_key}: declared path {rel_path} does not exist")
                continue
            actual = _sha256_file(full)
            if actual != expected:
                errors.append(
                    f"Artifact {artifact_key} ({rel_path}): "
                    f"expected {expected[:12]}..., got {actual[:12]}..."
                )

        # Performance identity hash verification
        perf = manifest.get("performance", {})
        for label, info in perf.items():
            if not isinstance(info, dict):
                continue
            rel_path = info.get("path")
            expected = info.get("hash_sha256") or info.get("sha256")
            if not rel_path or not expected:
                continue
            # Skip placeholder sentinel values.
            if expected == "historical":
                continue
            full = ROOT / rel_path
            if not full.is_file():
                errors.append(f"Performance {label}: declared path {rel_path} does not exist")
                continue
            actual = _sha256_file(full)
            if actual != expected:
                errors.append(
                    f"Performance {label} ({rel_path}): "
                    f"expected {expected[:12]}..., got {actual[:12]}..."
                )

    if FINAL_INVENTORY.is_file():
        inventory = json.loads(FINAL_INVENTORY.read_text(encoding="utf-8"))
        inv_hash = inventory.get("exporter_hash")
        exporter_path = ROOT / inventory.get("exporter_path", "")
        if inv_hash and exporter_path.is_file():
            actual = _sha256_file(exporter_path)
            if actual != inv_hash:
                errors.append(
                    f"Inventory exporter hash mismatch: expected {inv_hash[:12]}..., got {actual[:12]}..."
                )

    # --- Candidate code tree unchanged check ---
    if candidate_sha and check_git_ancestry:
        try:
            head = _git_head_sha()
            parent = _git_parent_sha()
            if head and parent:
                result = subprocess.run(
                    [
                        "git",
                        "diff",
                        "--name-only",
                        parent,
                        head,
                        "--",
                        "eggcalc/",
                        "tests/",
                        "scripts/",
                        ".github/",
                        "build_single.py",
                        "pyproject.toml",
                        "mypy-strict.ini",
                        "plans/",
                    ],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                code_changes = {line.strip() for line in result.stdout.splitlines() if line.strip()}
                if code_changes:
                    errors.append(
                        "Candidate code tree changed in evidence commit: "
                        + ", ".join(sorted(code_changes))
                    )
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

    return errors


def validate_documents(paths: tuple[Path, ...] = DEFAULT_DOCUMENTS) -> list[str]:
    """Backward-compatible validator: detect phase and validate accordingly."""
    has_any_real = False
    for path in paths:
        section = _final_section(path)
        if section is not None and _has_real_evidence(section):
            has_any_real = True
            break
    if has_any_real:
        return validate_final(paths)
    return validate_candidate_state(paths)


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
