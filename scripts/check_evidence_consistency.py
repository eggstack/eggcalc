#!/usr/bin/env python3
"""Validate synchronized Release 4-6 closure evidence.

Supports three modes:

- ``--candidate-state``: verifies that no placeholder final evidence exists,
  no stale SHA/workflow claims are present, and no final manifest/snapshot
  files exist.  Used during the code candidate phase.

- ``--final``: requires the complete proof set including exact candidate SHA,
  workflow run ID, lane totals, mandatory job names, performance identities,
  Git ancestry, evidence-only diff allowlist, and artifact hash consistency.
  Used after the code candidate receives a green CI run.

- ``--final-cross``: strict cross-record identity check that loads the
  committed manifest, CI snapshot, inventory, and performance files, and
  rejects any mismatch.  Refuses to emit ``APPROVED`` when identities
  disagree or required fields are missing.

The validator derives ``HEAD`` and ``HEAD^`` independently of CLI arguments.
Git ancestry is required in all final modes; the CLI argument is an
additional assertion, never the source of truth.
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
    "docs/performance/baseline-5a1bb34c.json",
    "docs/performance/comparison.json",
    "docs/performance/comparison.md",
}
# Performance files follow the canonical candidate-<short-sha>.json naming.
# Accept any candidate-<12hex>.json file in docs/performance/ via dynamic match.
FINAL_MANIFEST = ROOT / "docs" / "evidence" / "releases-4-6-final.json"
FINAL_CI_RUN = ROOT / "docs" / "evidence" / "releases-4-6-ci-run.json"
FINAL_INVENTORY = ROOT / "docs" / "evidence" / "releases-4-6-inventory.json"
PERFORMANCE_DIR = ROOT / "docs" / "performance"
BASELINE_PERFORMANCE = PERFORMANCE_DIR / "baseline-5a1bb34c.json"
CANDIDATE_SHA = "candidate"
PERFORMANCE_SHA_PREFIX = "candidate-"
CANDIDATE_SHA_RE = re.compile(rf"^{PERFORMANCE_SHA_PREFIX}([0-9a-f]{{12}})\.json$")


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


def _candidate_performance_files() -> list[Path]:
    """Return all candidate-<short-sha>.json files in docs/performance/."""
    if not PERFORMANCE_DIR.is_dir():
        return []
    return [path for path in PERFORMANCE_DIR.iterdir() if CANDIDATE_SHA_RE.match(path.name)]


def _actual_candidate_performance_allowlist() -> set[str]:
    """Allowlist of evidence-allowlisted performance file paths.

    Returns the dynamic set of all candidate-<short-sha>.json files relative
    to ROOT. Used to verify performance files committed alongside evidence
    are within the allowlist.
    """
    allowlist = set()
    for path in _candidate_performance_files():
        try:
            allowlist.add(str(path.relative_to(ROOT)))
        except ValueError:
            pass
    return allowlist


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
    - Existence of current-candidate performance files (5-sample 71dd343
      data and comparison.md/.json derived from it)
    """
    errors: list[str] = []

    if check_repo_files:
        for final_file in (FINAL_MANIFEST, FINAL_CI_RUN, FINAL_INVENTORY):
            if final_file.is_file():
                errors.append(
                    f"Final evidence file exists during candidate phase: {final_file.name}"
                )

        # Reject any candidate performance file or comparison artifact that
        # claims to be the current closure candidate. Candidate state means
        # no candidate SHA has been frozen yet.
        for candidate_file in _candidate_performance_files():
            errors.append(
                f"Candidate performance file exists during candidate phase: "
                f"{candidate_file.relative_to(ROOT)}"
            )
        for comparison_file in (
            PERFORMANCE_DIR / "comparison.json",
            PERFORMANCE_DIR / "comparison.md",
        ):
            if comparison_file.is_file():
                errors.append(
                    f"Candidate-state comparison artifact exists: "
                    f"{comparison_file.relative_to(ROOT)}"
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

    Git ancestry verification is mandatory in production final mode and
    cannot be skipped by omitting ``--candidate-sha``: the validator
    independently derives ``HEAD`` and ``HEAD^`` and fails if either
    cannot be resolved.
    """
    errors: list[str] = []
    identities: list[tuple[str, str]] = []
    sections: list[tuple[Path, str]] = []

    # Git metadata must always resolve in production final mode.
    head_sha = _git_head_sha()
    parent_sha = _git_parent_sha()
    if head_sha is None and check_git_ancestry:
        errors.append("Cannot verify Git ancestry: not a git repository")
    if parent_sha is None and check_git_ancestry:
        errors.append("Cannot verify Git ancestry: HEAD has no parent")

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
    if candidate_sha and check_git_ancestry and head_sha is not None and parent_sha is not None:
        if parent_sha != candidate_sha:
            errors.append(
                f"Git ancestry: HEAD^ is {parent_sha[:12]}..., expected candidate {candidate_sha[:12]}..."
            )

        # --- Evidence diff allowlist verification ---
        changed = _git_diff_names(parent_sha, head_sha)
        # The allowlist also covers any candidate-<short-sha>.json that may
        # exist as a sibling performance file. Document those dynamically.
        allowlist = EVIDENCE_ALLOWLIST | _actual_candidate_performance_allowlist()
        unexpected = changed - allowlist
        if unexpected:
            errors.append(
                f"Evidence commit modifies files outside allowlist: "
                f"{', '.join(sorted(unexpected))}"
            )

    # --- Artifact hash verification ---
    if FINAL_MANIFEST.is_file():
        manifest = json.loads(FINAL_MANIFEST.read_text(encoding="utf-8"))

        # --- Strict cross-record identity check ---
        identities, lane_errors = _extract_manifest_identities(manifest)
        errors.extend(lane_errors)
        # The manifest candidate_sha must match the workflow_head_sha and
        # match the candidate_sha argument (which itself was derived from
        # HEAD^ via the caller). Additionally, all nested provenance fields
        # must be internally consistent.
        ci_sha = identities.get("ci_candidate_sha")
        ci_run = identities.get("ci_workflow_run_id")
        ci_conclusion = identities.get("ci_workflow_conclusion")
        manifest_candidate_sha = identities.get("candidate_sha")
        manifest_workflow_head = identities.get("workflow_head_sha")
        manifest_run = identities.get("candidate_workflow_run_id")
        manifest_conclusion = identities.get("workflow_conclusion")

        if (
            manifest_candidate_sha
            and manifest_workflow_head
            and manifest_candidate_sha != manifest_workflow_head
        ):
            errors.append("Manifest identity mismatch: candidate_sha != workflow_head_sha")
        if ci_sha and manifest_candidate_sha and ci_sha != manifest_candidate_sha:
            errors.append(
                f"Cross-record identity mismatch: manifest.candidate_sha "
                f"({manifest_candidate_sha[:12]}...) != ci_snapshot.candidate_sha "
                f"({ci_sha[:12]}...)"
            )
        if manifest_workflow_head and ci_sha and manifest_workflow_head != ci_sha:
            errors.append(
                "Cross-record identity mismatch: manifest.workflow_head_sha "
                "!= ci_snapshot.candidate_sha"
            )
        if ci_run and manifest_run and ci_run != manifest_run:
            errors.append(
                "Cross-record identity mismatch: manifest.candidate_workflow_run_id "
                "!= ci_snapshot.candidate_workflow_run_id"
            )
        if manifest_conclusion != "success":
            errors.append(
                f"Manifest workflow_conclusion is {manifest_conclusion!r}, expected 'success'"
            )
        if ci_conclusion != "success":
            errors.append(
                f"CI snapshot workflow_conclusion is {ci_conclusion!r}, expected 'success'"
            )

        artifact_hashes = manifest.get("artifact_hashes", {})
        for artifact_key, entry in artifact_hashes.items():
            if not isinstance(entry, dict):
                errors.append(f"Artifact {artifact_key}: must be a structured dict")
                continue
            info = entry
            expected = info.get("sha256")
            rel_path = info.get("path")
            note = info.get("note", "")
            if not expected or not isinstance(expected, str) or len(expected) != 64:
                errors.append(f"Artifact {artifact_key}: missing 64-character SHA-256")
                continue
            if "Built during" in note or "not committed" in note:
                errors.append(
                    f"Artifact {artifact_key}: note-based exemption text "
                    f"{note!r} is not permitted in final evidence"
                )
                continue
            # Structured provenance is mandatory in final mode.
            for field_name in (
                "workflow_run_id",
                "workflow_attempt",
                "workflow_head_sha",
            ):
                if field_name not in info:
                    errors.append(
                        f"Artifact {artifact_key}: missing structured field {field_name!r}"
                    )
            if candidate_sha and manifest_candidate_sha:
                if info.get("workflow_head_sha") != manifest_candidate_sha:
                    errors.append(
                        f"Artifact {artifact_key}: workflow_head_sha does not match manifest"
                    )
                if info.get("workflow_run_id") != manifest_run:
                    errors.append(
                        f"Artifact {artifact_key}: workflow_run_id does not match manifest"
                    )

        # --- Performance identity cross-check ---
        perf = manifest.get("performance", {})
        if isinstance(perf, dict):
            perf_candidate_sha = perf.get("candidate_sha")
            if (
                manifest_candidate_sha
                and perf_candidate_sha
                and perf_candidate_sha != manifest_candidate_sha
            ):
                errors.append(
                    f"Performance candidate_sha ({perf_candidate_sha[:12]}...) does not "
                    f"match manifest candidate_sha ({manifest_candidate_sha[:12]}...)"
                )

            # Verify the candidate performance file exists, has at least 15
            # samples and 5 warmups, and its internal commit_sha equals the
            # manifest candidate_sha.
            candidate_perf = perf.get("candidate")
            if isinstance(candidate_perf, dict):
                rel_path = candidate_perf.get("path")
                if rel_path:
                    full = ROOT / rel_path
                    if not full.is_file():
                        errors.append(f"Performance candidate path does not exist: {rel_path}")
                    else:
                        perf_doc = json.loads(full.read_text(encoding="utf-8"))
                        if perf_doc.get("samples", 0) < 15:
                            errors.append(
                                f"Performance candidate samples={perf_doc.get('samples')}, "
                                f"expected >=15"
                            )
                        if perf_doc.get("warmups", 0) < 5:
                            errors.append(
                                f"Performance candidate warmups={perf_doc.get('warmups')}, "
                                f"expected >=5"
                            )
                        if (
                            manifest_candidate_sha
                            and perf_doc.get("commit_sha") != manifest_candidate_sha
                        ):
                            errors.append(
                                "Performance candidate commit_sha does not match manifest"
                            )
                        # Environment must match baseline environment.
                        baseline_perf = perf.get("baseline")
                        if isinstance(baseline_perf, dict):
                            baseline_rel = baseline_perf.get("path")
                            if baseline_rel:
                                baseline_full = ROOT / baseline_rel
                                if baseline_full.is_file():
                                    baseline_doc = json.loads(
                                        baseline_full.read_text(encoding="utf-8")
                                    )
                                    for env_key in (
                                        "os",
                                        "python_version",
                                        "architecture",
                                    ):
                                        if perf_doc.get(env_key) != baseline_doc.get(env_key):
                                            errors.append(
                                                f"Performance environment mismatch: "
                                                f"candidate.{env_key}={perf_doc.get(env_key)!r} "
                                                f"!= baseline.{env_key}={baseline_doc.get(env_key)!r}"
                                            )

            baseline_perf = perf.get("baseline")
            if isinstance(baseline_perf, dict):
                rel_path = baseline_perf.get("path")
                if rel_path:
                    full = ROOT / rel_path
                    if not full.is_file():
                        errors.append(f"Performance baseline path does not exist: {rel_path}")
                    else:
                        baseline_doc = json.loads(full.read_text(encoding="utf-8"))
                        expected_baseline_sha = "5a1bb34c9efa269ca6159217827f1742faa95d20"
                        if baseline_doc.get("commit_sha") != expected_baseline_sha:
                            errors.append(
                                f"Performance baseline commit_sha "
                                f"({baseline_doc.get('commit_sha', '')[:12]}...) does not "
                                f"match required {expected_baseline_sha[:12]}..."
                            )

        # Refuse APPROVED when any invariant is violated.
        if manifest.get("final_decision") == "APPROVED" and errors:
            errors.append(
                "Manifest declares final_decision=APPROVED but cross-record "
                "validation produced errors"
            )

    if FINAL_INVENTORY.is_file():
        inventory = json.loads(FINAL_INVENTORY.read_text(encoding="utf-8"))
        inv_hash = inventory.get("exporter_hash")
        exporter_path = ROOT / inventory.get("exporter_path", "")
        if inv_hash and exporter_path.is_file():
            actual = _sha256_file(exporter_path)
            if actual != inv_hash:
                errors.append(
                    f"Inventory exporter hash mismatch: expected {inv_hash[:12]}..., "
                    f"got {actual[:12]}..."
                )

        # Inventory candidate/run identity must match manifest when present.
        inv_candidate = inventory.get("candidate_sha")
        inv_run = inventory.get("workflow_run_id")
        if FINAL_MANIFEST.is_file() and (inv_candidate or inv_run):
            manifest = json.loads(FINAL_MANIFEST.read_text(encoding="utf-8"))
            manifest_candidate = manifest.get("candidate_sha")
            manifest_run = manifest.get("candidate_workflow_run_id")
            if inv_candidate and manifest_candidate and inv_candidate != manifest_candidate:
                errors.append(
                    f"Inventory candidate_sha ({inv_candidate[:12]}...) does not "
                    f"match manifest ({manifest_candidate[:12]}...)"
                )
            if inv_run and manifest_run and inv_run != manifest_run:
                errors.append(
                    f"Inventory workflow_run_id ({inv_run}) does not match "
                    f"manifest ({manifest_run})"
                )

    # --- Candidate code tree unchanged check ---
    if candidate_sha and check_git_ancestry and head_sha is not None and parent_sha is not None:
        try:
            result = subprocess.run(
                [
                    "git",
                    "diff",
                    "--name-only",
                    parent_sha,
                    head_sha,
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


def _extract_manifest_identities(manifest: dict) -> tuple[dict[str, object], list[str]]:
    """Extract identity fields from manifest and CI snapshot if loaded.

    Returns a tuple ``(identities, lane_errors)`` where ``lane_errors``
    surfaces per-lane failures so that the validator can refuse to mark
    ``final_decision=APPROVED`` when any lane is failing.
    """
    identities: dict[str, object] = {
        "candidate_sha": manifest.get("candidate_sha"),
        "candidate_workflow_run_id": manifest.get("candidate_workflow_run_id"),
        "workflow_head_sha": manifest.get("workflow_head_sha"),
        "workflow_conclusion": manifest.get("workflow_conclusion"),
    }
    lane_errors: list[str] = []
    if FINAL_CI_RUN.is_file():
        try:
            ci = json.loads(FINAL_CI_RUN.read_text(encoding="utf-8"))
            identities["ci_candidate_sha"] = ci.get("candidate_sha")
            identities["ci_workflow_head_sha"] = ci.get("workflow_head_sha")
            identities["ci_workflow_run_id"] = ci.get("candidate_workflow_run_id")
            identities["ci_workflow_conclusion"] = ci.get("workflow_conclusion")
            lanes = ci.get("lane_totals", {})
            for lane_name, lane_info in lanes.items():
                if not isinstance(lane_info, dict):
                    continue
                if lane_info.get("conclusion") != "success":
                    lane_errors.append(
                        f"CI snapshot lane {lane_name!r} conclusion is "
                        f"{lane_info.get('conclusion')!r}, expected 'success'"
                    )
                if lane_info.get("failed", 0) != 0:
                    lane_errors.append(
                        f"CI snapshot lane {lane_name!r} failed="
                        f"{lane_info.get('failed')}, expected 0"
                    )
                if lane_info.get("errors", 0) != 0:
                    lane_errors.append(
                        f"CI snapshot lane {lane_name!r} errors="
                        f"{lane_info.get('errors')}, expected 0"
                    )
        except json.JSONDecodeError:
            identities["ci_workflow_conclusion"] = "invalid_json"
    return identities, lane_errors


def validate_documents(paths: tuple[Path, ...] = DEFAULT_DOCUMENTS) -> list[str]:
    """Backward-compatible validator: detect phase and validate accordingly.

    Note: production CI must call ``--candidate-state`` or ``--final``
    explicitly; this auto-detection entry point is retained for external
    callers but cannot return success for contradictory final evidence.
    """
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
        "--final-cross",
        action="store_true",
        help="Strict cross-record identity check (loads manifest + CI + inventory + perf)",
    )
    parser.add_argument(
        "--candidate-sha",
        type=str,
        default=None,
        help="Expected candidate SHA for --final mode",
    )
    args = parser.parse_args()

    paths = tuple(args.paths)

    if args.final_cross:
        # Cross-record check always loads the final manifest.
        errors = validate_final(paths, candidate_sha=args.candidate_sha)
    elif args.final:
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
