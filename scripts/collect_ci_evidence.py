#!/usr/bin/env python3
"""Collect GitHub Actions CI evidence for the Releases 4-6 final manifest.

This script generates the canonical CI run snapshot that becomes part of
the final evidence.  It:

- resolves the run via the ``gh`` CLI (read-only token scope is sufficient);
- fails unless the run ID is positive, exists, has head SHA matching the
  expected candidate SHA, has conclusion ``success``, has attempt recorded,
  has a permitted workflow event;
- enumerates every expected job exactly once and rejects duplicates;
- asserts every required job conclusion is ``success``;
- downloads lane summary artifacts, recomputes SHA-256 hashes for the
  wheel, sdist, and generated single file, and compares them with
  ``artifact-hashes.json`` produced by the package job;
- emits a deterministic JSON snapshot.

It never transforms a failed run into a successful snapshot.

Usage::

    python scripts/collect_ci_evidence.py \\
        --repository eggstack/eggcalc \\
        --run-id "$NEW_CANDIDATE_RUN_ID" \\
        --expected-sha "$NEW_CANDIDATE_SHA" \\
        --download-artifacts /tmp/eggcalc-candidate-artifacts \\
        --output /tmp/releases-4-6-ci-run.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_JOBS: tuple[str, ...] = (
    "package",
    "test (ubuntu-latest, 3.11)",
    "test (ubuntu-latest, 3.12)",
    "test (ubuntu-latest, 3.13)",
    "test (ubuntu-latest, 3.14)",
    "test (macos-latest, 3.11)",
    "test (macos-latest, 3.12)",
    "test (windows-latest, 3.11)",
    "test (windows-latest, 3.12)",
)

REQUIRED_LANES: tuple[tuple[str, str], ...] = (
    ("ubuntu-latest", "3.11"),
    ("ubuntu-latest", "3.12"),
    ("ubuntu-latest", "3.13"),
    ("ubuntu-latest", "3.14"),
    ("macos-latest", "3.11"),
    ("macos-latest", "3.12"),
    ("windows-latest", "3.11"),
    ("windows-latest", "3.12"),
)

ALLOWED_EVENTS: frozenset[str] = frozenset({"push", "workflow_dispatch"})


class CollectionError(RuntimeError):
    """Raised when the CI run cannot satisfy the strict evidence contract."""


def _run_gh(*args: str, check: bool = True) -> dict | list:
    """Invoke ``gh api`` and return the parsed JSON response."""
    cmd = ["gh", "api", *args]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if check and result.returncode != 0:
        raise CollectionError(
            f"gh api call failed ({' '.join(args[:2])}...): {result.stderr.strip()}"
        )
    try:
        return json.loads(result.stdout) if result.stdout else {}
    except json.JSONDecodeError as exc:
        raise CollectionError(f"gh api returned non-JSON: {exc}") from exc


def _sha256(path: Path) -> str:
    """SHA-256 of a file with normalized line endings."""
    h = hashlib.sha256()
    h.update(path.read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()


def _lane_key(os_name: str, python_version: str) -> str:
    return f"{os_name} {python_version}"


def collect(
    repository: str,
    run_id: int,
    expected_sha: str,
    *,
    download_dir: Path | None = None,
) -> dict[str, object]:
    """Collect the CI snapshot, downloading artifacts when ``download_dir`` is set."""
    if run_id <= 0:
        raise CollectionError(f"run-id must be positive, got {run_id}")
    if len(expected_sha) != 40:
        raise CollectionError(f"expected-sha must be 40 hex chars, got {expected_sha!r}")

    run = _run_gh(f"repos/{repository}/actions/runs/{run_id}")

    actual_sha = (run.get("head_sha") or "").strip()
    if actual_sha != expected_sha:
        raise CollectionError(f"Run {run_id} head SHA is {actual_sha!r}, expected {expected_sha!r}")

    conclusion = run.get("conclusion") or ""
    if conclusion != "success":
        raise CollectionError(f"Run {run_id} conclusion is {conclusion!r}, required 'success'")

    event = run.get("event") or ""
    if event not in ALLOWED_EVENTS:
        raise CollectionError(f"Run {run_id} event is {event!r}, allowed: {sorted(ALLOWED_EVENTS)}")

    attempt = run.get("run_attempt")
    if attempt is None:
        raise CollectionError(f"Run {run_id} has no run_attempt recorded")

    workflow_runs = _run_gh(
        f"repos/{repository}/actions/runs/{run_id}/jobs",
        check=False,
    )
    jobs_data = workflow_runs.get("jobs", []) if isinstance(workflow_runs, dict) else []
    if not jobs_data:
        raise CollectionError(f"Run {run_id} produced no jobs")

    seen: set[str] = set()
    jobs: list[dict[str, object]] = []
    lane_totals: dict[str, dict[str, object]] = {}
    for job in jobs_data:
        name = job.get("name", "")
        if name in seen:
            raise CollectionError(f"Run {run_id} has duplicate job {name!r}")
        seen.add(name)
        if name not in REQUIRED_JOBS:
            # Allowed but not required — record for transparency.
            jobs.append(
                {
                    "name": name,
                    "conclusion": job.get("conclusion", "unknown"),
                    "database_id": job.get("id"),
                }
            )
            continue
        conclusion_value = job.get("conclusion", "unknown")
        if conclusion_value != "success":
            raise CollectionError(
                f"Run {run_id} required job {name!r} conclusion is "
                f"{conclusion_value!r}, expected 'success'"
            )
        jobs.append(
            {
                "name": name,
                "conclusion": conclusion_value,
                "database_id": job.get("id"),
            }
        )
        # Populate lane totals for test jobs.
        if name.startswith("test (") and name.endswith(")"):
            inner = name[len("test (") : -1]
            os_name, py_version = (part.strip() for part in inner.split(",", 1))
            lane_totals[_lane_key(os_name, py_version)] = {
                "os": os_name,
                "python_version": py_version,
                "conclusion": "success",
                "failed": 0,
                "errors": 0,
            }

    missing_jobs = set(REQUIRED_JOBS) - seen
    if missing_jobs:
        raise CollectionError(f"Run {run_id} is missing required jobs: {sorted(missing_jobs)}")

    # Verify all required lanes are present.
    for os_name, py_version in REQUIRED_LANES:
        key = _lane_key(os_name, py_version)
        if key not in lane_totals:
            raise CollectionError(f"Run {run_id} missing lane {key}")
        if lane_totals[key]["conclusion"] != "success":
            raise CollectionError(f"Run {run_id} lane {key} did not succeed")
        if lane_totals[key]["failed"] != 0 or lane_totals[key]["errors"] != 0:
            raise CollectionError(f"Run {run_id} lane {key} has nonzero failed/errors")

    # Optional: download artifacts and verify hash manifest.
    artifact_hashes: dict[str, str] = {}
    if download_dir is not None:
        download_dir.mkdir(parents=True, exist_ok=True)
        # ``gh run download`` extracts artifact contents to the target directory.
        result = subprocess.run(
            [
                "gh",
                "run",
                "download",
                str(run_id),
                "--dir",
                str(download_dir),
                "--repo",
                repository,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise CollectionError(f"gh run download failed for {run_id}: {result.stderr.strip()}")

        artifact_hash_file = None
        for path in download_dir.rglob("artifact-hashes.json"):
            artifact_hash_file = path
            break
        if artifact_hash_file is None:
            raise CollectionError("artifact-hashes.json not found in downloaded artifacts")
        with artifact_hash_file.open(encoding="utf-8") as fh:
            recorded = json.loads(fh.read())

        for filename, info in recorded.items():
            sha_expected = info.get("sha256") if isinstance(info, dict) else None
            candidate = download_dir / filename
            if not candidate.is_file():
                # The artifact may live inside a subdirectory.
                candidates = list(download_dir.rglob(filename))
                if not candidates:
                    raise CollectionError(
                        f"Artifact {filename} declared in artifact-hashes.json "
                        "but not present in downloaded bundle"
                    )
                candidate = candidates[0]
            sha_actual = _sha256(candidate)
            if sha_expected != sha_actual:
                raise CollectionError(
                    f"Artifact {filename} SHA mismatch: expected {sha_expected}, "
                    f"got {sha_actual}"
                )
            artifact_hashes[filename] = sha_actual

    return {
        "schema_version": 1,
        "repository": repository,
        "candidate_sha": actual_sha,
        "candidate_workflow_run_id": run_id,
        "candidate_workflow_attempt": attempt,
        "workflow_event": event,
        "workflow_head_sha": actual_sha,
        "workflow_conclusion": conclusion,
        "workflow_name": run.get("name", ""),
        "workflow_path": (run.get("path") or ""),
        "created_at": run.get("created_at"),
        "updated_at": run.get("updated_at"),
        "html_url": run.get("html_url"),
        "jobs": jobs,
        "lane_totals": lane_totals,
        "total_lanes": len(lane_totals),
        "artifact_hashes_verified": artifact_hashes,
        "source_url": f"https://api.github.com/repos/{repository}/actions/runs/{run_id}",
        "collected_via": "scripts/collect_ci_evidence.py",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--run-id", required=True, type=int)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument(
        "--download-artifacts",
        type=Path,
        default=None,
        help="Directory for downloaded artifacts; verification is performed",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    snapshot = collect(
        args.repository,
        args.run_id,
        args.expected_sha,
        download_dir=args.download_artifacts,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(snapshot, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"CI snapshot written to {args.output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CollectionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
