"""Tests for the strict evidence-integrity validator.

This module covers the contradictions that escaped validation in commit
``e7665cc1``:

- Mixed candidate / workflow head / run identities
- Note-based artifact hash exemptions
- Five-sample performance evidence on a different SHA
- Failed CI snapshot coexisting with successful manifest
- Evidence commits that modify non-allowlisted files
- Arbitrary 64-character artifact hashes without workflow provenance
- Git ancestry checks that can be silently skipped

Each negative test asserts at least one specific diagnostic is produced.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import check_evidence_consistency as mod
from scripts.check_evidence_consistency import (
    FINAL_CI_RUN,
    FINAL_INVENTORY,
    FINAL_MANIFEST,
    validate_candidate_state,
    validate_final,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _restore_final_paths() -> object:
    """Snapshot the module-level FINAL_* paths and restore after each test.

    The strict tests reassign ``mod.FINAL_MANIFEST`` / ``mod.FINAL_CI_RUN`` /
    ``mod.FINAL_INVENTORY`` to tmp_path-relative locations. Without this fixture,
    those mutations leak into subsequent tests that read the real repository
    evidence paths (e.g. ``test_evidence_consistency.py``).
    """
    saved = (mod.FINAL_MANIFEST, mod.FINAL_CI_RUN, mod.FINAL_INVENTORY)
    yield None
    mod.FINAL_MANIFEST, mod.FINAL_CI_RUN, mod.FINAL_INVENTORY = saved


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _final_section_text(
    sha: str = "a" * 40,
    run_id: str = "12345",
) -> str:
    return (
        "- closure_code_sha: `" + sha + "`\n"
        "- closure_workflow_run_id: `" + run_id + "`\n"
        "- closure_workflow_attempt: 1\n"
        "- evidence_parent_sha: `" + sha + "`\n"
        "- lane ubuntu-latest 3.11: collected=10 passed=9 skipped=1 xfailed=0 xpassed=0 failed=0\n"
        "- lane ubuntu-latest 3.12: collected=10 passed=9 skipped=1 xfailed=0 xpassed=0 failed=0\n"
        "- lane ubuntu-latest 3.13: collected=10 passed=9 skipped=1 xfailed=0 xpassed=0 failed=0\n"
        "- lane ubuntu-latest 3.14: collected=10 passed=9 skipped=1 xfailed=0 xpassed=0 failed=0\n"
        "- lane macos-latest 3.11: collected=10 passed=9 skipped=1 xfailed=0 xpassed=0 failed=0\n"
        "- lane macos-latest 3.12: collected=10 passed=9 skipped=1 xfailed=0 xpassed=0 failed=0\n"
        "- lane windows-latest 3.11: collected=10 passed=9 skipped=1 xfailed=0 xpassed=0 failed=0\n"
        "- lane windows-latest 3.12: collected=10 passed=9 skipped=1 xfailed=0 xpassed=0 failed=0\n"
        "\nordinary Ruff; Black; ordinary mypy; strict mypy; strict Ruff;\n"
        "authority-boundary; deterministic build; authority inventory;\n"
        "source typed consumer; installed-wheel typed consumer; MCP closure;\n"
        "unit closure; release-surface.\n"
        "\nPerformance baseline and final identity are recorded.\n"
    )


def _write_doc(tmp_path: Path, name: str, section: str) -> Path:
    path = tmp_path / name
    path.write_text(f"# {name}\n\n## Final Closure Evidence\n\n{section}", encoding="utf-8")
    return path


def _write_evidence_docs(tmp_path: Path, sha: str, run_id: str) -> tuple[Path, Path, Path]:
    section = _final_section_text(sha, run_id)
    docs = tuple(_write_doc(tmp_path, f"release_{n}.md", section) for n in (4, 5, 6))
    return docs  # type: ignore[return-value]


def _write_manifest(
    tmp_path: Path,
    *,
    candidate_sha: str,
    workflow_head_sha: str | None = None,
    candidate_workflow_run_id: int = 12345,
    candidate_workflow_attempt: int = 1,
    workflow_conclusion: str = "success",
    final_decision: str = "APPROVED",
    artifacts: dict | None = None,
    performance: dict | None = None,
) -> Path:
    manifest = {
        "schema_version": 1,
        "repository": "eggstack/eggcalc",
        "release_set": [4, 5, 6],
        "candidate_sha": candidate_sha,
        "candidate_parent_sha": "9" * 40,
        "candidate_workflow_run_id": candidate_workflow_run_id,
        "candidate_workflow_attempt": candidate_workflow_attempt,
        "workflow_head_sha": workflow_head_sha if workflow_head_sha is not None else candidate_sha,
        "workflow_conclusion": workflow_conclusion,
        "final_decision": final_decision,
        "jobs": [
            {"name": "package", "conclusion": "success", "database_id": 1},
            {"name": "test (ubuntu-latest, 3.11)", "conclusion": "success", "database_id": 2},
            {"name": "test (ubuntu-latest, 3.12)", "conclusion": "success", "database_id": 3},
            {"name": "test (ubuntu-latest, 3.13)", "conclusion": "success", "database_id": 4},
            {"name": "test (ubuntu-latest, 3.14)", "conclusion": "success", "database_id": 5},
            {"name": "test (macos-latest, 3.11)", "conclusion": "success", "database_id": 6},
            {"name": "test (macos-latest, 3.12)", "conclusion": "success", "database_id": 7},
            {"name": "test (windows-latest, 3.11)", "conclusion": "success", "database_id": 8},
            {"name": "test (windows-latest, 3.12)", "conclusion": "success", "database_id": 9},
        ],
        "lane_totals": {
            "ubuntu-latest 3.11": {
                "conclusion": "success",
                "collected": 10,
                "passed": 9,
                "skipped": 1,
                "xfailed": 0,
                "xpassed": 0,
                "failed": 0,
                "errors": 0,
            },
            "ubuntu-latest 3.12": {
                "conclusion": "success",
                "collected": 10,
                "passed": 9,
                "skipped": 1,
                "xfailed": 0,
                "xpassed": 0,
                "failed": 0,
                "errors": 0,
            },
            "ubuntu-latest 3.13": {
                "conclusion": "success",
                "collected": 10,
                "passed": 9,
                "skipped": 1,
                "xfailed": 0,
                "xpassed": 0,
                "failed": 0,
                "errors": 0,
            },
            "ubuntu-latest 3.14": {
                "conclusion": "success",
                "collected": 10,
                "passed": 9,
                "skipped": 1,
                "xfailed": 0,
                "xpassed": 0,
                "failed": 0,
                "errors": 0,
            },
            "macos-latest 3.11": {
                "conclusion": "success",
                "collected": 10,
                "passed": 9,
                "skipped": 1,
                "xfailed": 0,
                "xpassed": 0,
                "failed": 0,
                "errors": 0,
            },
            "macos-latest 3.12": {
                "conclusion": "success",
                "collected": 10,
                "passed": 9,
                "skipped": 1,
                "xfailed": 0,
                "xpassed": 0,
                "failed": 0,
                "errors": 0,
            },
            "windows-latest 3.11": {
                "conclusion": "success",
                "collected": 10,
                "passed": 9,
                "skipped": 1,
                "xfailed": 0,
                "xpassed": 0,
                "failed": 0,
                "errors": 0,
            },
            "windows-latest 3.12": {
                "conclusion": "success",
                "collected": 10,
                "passed": 9,
                "skipped": 1,
                "xfailed": 0,
                "xpassed": 0,
                "failed": 0,
                "errors": 0,
            },
        },
        "total_lanes": 8,
        "artifact_hashes": artifacts
        or {
            "eggcalc-1.1.6-py3-none-any.whl": {
                "kind": "wheel",
                "name": "eggcalc-1.1.6-py3-none-any.whl",
                "sha256": "1" * 64,
                "workflow_run_id": candidate_workflow_run_id,
                "workflow_attempt": candidate_workflow_attempt,
                "workflow_head_sha": candidate_sha,
                "artifact_id": 100,
                "artifact_bundle_name": "release-artifacts",
                "source_summary_path": "artifact-hashes.json",
            },
        },
        "inventory": {"path": "docs/evidence/releases-4-6-inventory.json", "result": "match"},
        "performance": performance
        or {
            "baseline_sha": "5a1bb34c9efa269ca6159217827f1742faa95d20",
            "candidate_sha": candidate_sha,
            "baseline": {
                "path": "docs/performance/baseline-5a1bb34c.json",
                "hash_sha256": "x" * 64,
            },
            "candidate": {
                "path": f"docs/performance/candidate-{candidate_sha[:12]}.json",
                "hash_sha256": "y" * 64,
            },
            "comparison": {"path": "docs/performance/comparison.json", "hash_sha256": "z" * 64},
        },
    }
    path = tmp_path / "releases-4-6-final.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _write_ci_snapshot(
    tmp_path: Path,
    *,
    candidate_sha: str,
    candidate_workflow_run_id: int = 12345,
    candidate_workflow_attempt: int = 1,
    workflow_conclusion: str = "success",
    lane_failures: dict | None = None,
) -> Path:
    lane_totals: dict[str, dict[str, object]] = {}
    for os_name, py_version in (
        ("ubuntu-latest", "3.11"),
        ("ubuntu-latest", "3.12"),
        ("ubuntu-latest", "3.13"),
        ("ubuntu-latest", "3.14"),
        ("macos-latest", "3.11"),
        ("macos-latest", "3.12"),
        ("windows-latest", "3.11"),
        ("windows-latest", "3.12"),
    ):
        conclusion = "success"
        failed = 0
        errors = 0
        if lane_failures and f"{os_name} {py_version}" in lane_failures:
            entry = lane_failures[f"{os_name} {py_version}"]
            conclusion = entry.get("conclusion", "failure")
            failed = entry.get("failed", 1)
            errors = entry.get("errors", 0)
        lane_totals[f"{os_name} {py_version}"] = {
            "os": os_name,
            "python_version": py_version,
            "conclusion": conclusion,
            "collected": 10,
            "passed": 9,
            "skipped": 1,
            "xfailed": 0,
            "xpassed": 0,
            "failed": failed,
            "errors": errors,
        }
    snapshot = {
        "schema_version": 1,
        "repository": "eggstack/eggcalc",
        "candidate_sha": candidate_sha,
        "candidate_workflow_run_id": candidate_workflow_run_id,
        "candidate_workflow_attempt": candidate_workflow_attempt,
        "workflow_head_sha": candidate_sha,
        "workflow_conclusion": workflow_conclusion,
        "workflow_event": "push",
        "jobs": [
            {"name": "package", "conclusion": "success", "database_id": 1},
            {"name": "test (ubuntu-latest, 3.11)", "conclusion": "success", "database_id": 2},
            {"name": "test (ubuntu-latest, 3.12)", "conclusion": "success", "database_id": 3},
            {"name": "test (ubuntu-latest, 3.13)", "conclusion": "success", "database_id": 4},
            {"name": "test (ubuntu-latest, 3.14)", "conclusion": "success", "database_id": 5},
            {"name": "test (macos-latest, 3.11)", "conclusion": "success", "database_id": 6},
            {"name": "test (macos-latest, 3.12)", "conclusion": "success", "database_id": 7},
            {"name": "test (windows-latest, 3.11)", "conclusion": "success", "database_id": 8},
            {"name": "test (windows-latest, 3.12)", "conclusion": "success", "database_id": 9},
        ],
        "lane_totals": lane_totals,
        "total_lanes": 8,
    }
    path = tmp_path / "releases-4-6-ci-run.json"
    path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _write_inventory(tmp_path: Path, *, candidate_sha: str, run_id: int = 12345) -> Path:
    inv = {
        "schema_version": 1,
        "candidate_sha": candidate_sha,
        "workflow_run_id": run_id,
        "exporter_path": "scripts/export_unit_baseline.py",
        "exporter_hash": "0" * 64,
        "artifacts": {},
        "package": {
            "cli": [],
            "mcp": {"tools": [], "schemas": {}, "metadata": {}, "profiles": {}},
            "units": {"definitions": [], "aliases": {}, "categories": {}, "base": {}},
        },
        "single_file": {
            "cli": [],
            "mcp": {"tools": [], "schemas": {}, "metadata": {}, "profiles": {}},
            "units": {"definitions": [], "aliases": {}, "categories": {}, "base": {}},
        },
        "allowed_differences": [],
    }
    path = tmp_path / "releases-4-6-inventory.json"
    path.write_text(json.dumps(inv, indent=2, sort_keys=True), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Identity mismatch tests
# ---------------------------------------------------------------------------


def test_manifest_candidate_differs_from_workflow_head_fails(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Manifest candidate_sha must equal workflow_head_sha."""
    sha = "a" * 40
    docs = _write_evidence_docs(tmp_path, sha, "12345")
    monkeypatch_set(
        monkeypatch,
        FINAL_MANIFEST,
        _write_manifest(tmp_path, candidate_sha=sha, workflow_head_sha="b" * 40),
    )
    monkeypatch_set(monkeypatch, FINAL_CI_RUN, _write_ci_snapshot(tmp_path, candidate_sha=sha))
    errors = validate_final(docs, candidate_sha=sha, check_git_ancestry=False)
    assert any("candidate_sha != workflow_head_sha" in e for e in errors)


def test_manifest_candidate_differs_from_ci_snapshot_fails(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Manifest candidate_sha must equal CI snapshot candidate_sha."""
    sha = "a" * 40
    docs = _write_evidence_docs(tmp_path, sha, "12345")
    monkeypatch_set(monkeypatch, FINAL_MANIFEST, _write_manifest(tmp_path, candidate_sha=sha))
    monkeypatch_set(monkeypatch, FINAL_CI_RUN, _write_ci_snapshot(tmp_path, candidate_sha="b" * 40))
    errors = validate_final(docs, candidate_sha=sha, check_git_ancestry=False)
    assert any("Cross-record identity mismatch" in e for e in errors)


def test_manifest_run_differs_from_ci_run_fails(tmp_path: Path, monkeypatch: object) -> None:
    """Manifest candidate_workflow_run_id must equal CI snapshot run id."""
    sha = "a" * 40
    docs = _write_evidence_docs(tmp_path, sha, "12345")
    monkeypatch_set(
        monkeypatch,
        FINAL_MANIFEST,
        _write_manifest(tmp_path, candidate_sha=sha, candidate_workflow_run_id=11111),
    )
    monkeypatch_set(
        monkeypatch,
        FINAL_CI_RUN,
        _write_ci_snapshot(tmp_path, candidate_sha=sha, candidate_workflow_run_id=22222),
    )
    errors = validate_final(docs, candidate_sha=sha, check_git_ancestry=False)
    assert any("candidate_workflow_run_id" in e for e in errors)


def test_ci_snapshot_failure_with_manifest_success_fails(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Failed CI snapshot cannot coexist with manifest success."""
    sha = "a" * 40
    docs = _write_evidence_docs(tmp_path, sha, "12345")
    monkeypatch_set(
        monkeypatch,
        FINAL_MANIFEST,
        _write_manifest(tmp_path, candidate_sha=sha, workflow_conclusion="success"),
    )
    monkeypatch_set(
        monkeypatch,
        FINAL_CI_RUN,
        _write_ci_snapshot(tmp_path, candidate_sha=sha, workflow_conclusion="failure"),
    )
    errors = validate_final(docs, candidate_sha=sha, check_git_ancestry=False)
    assert any("'failure'" in e for e in errors)


def test_windows_lane_failure_masked_by_manifest_success_fails(
    tmp_path: Path, monkeypatch: object
) -> None:
    """A lane failure must fail even when the manifest says success."""
    sha = "a" * 40
    docs = _write_evidence_docs(tmp_path, sha, "12345")
    monkeypatch_set(
        monkeypatch,
        FINAL_MANIFEST,
        _write_manifest(tmp_path, candidate_sha=sha, workflow_conclusion="success"),
    )
    monkeypatch_set(
        monkeypatch,
        FINAL_CI_RUN,
        _write_ci_snapshot(
            tmp_path,
            candidate_sha=sha,
            lane_failures={"windows-latest 3.12": {"conclusion": "failure", "failed": 33}},
        ),
    )
    errors = validate_final(docs, candidate_sha=sha, check_git_ancestry=False)
    assert any(
        "did not succeed" in e or "nonzero failed" in e or "lane " in e for e in errors
    ), f"Expected lane failure error, got: {errors}"


def test_performance_candidate_sha_differs_from_manifest_fails(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Performance candidate_sha must equal manifest candidate_sha."""
    sha = "a" * 40
    docs = _write_evidence_docs(tmp_path, sha, "12345")
    perf = {
        "baseline_sha": "5a1bb34c9efa269ca6159217827f1742faa95d20",
        "candidate_sha": "b" * 40,
        "baseline": {"path": "docs/performance/baseline-5a1bb34c.json", "hash_sha256": "x" * 64},
        "candidate": {"path": "docs/performance/candidate-bbbb.json", "hash_sha256": "y" * 64},
        "comparison": {"path": "docs/performance/comparison.json", "hash_sha256": "z" * 64},
    }
    monkeypatch_set(
        monkeypatch, FINAL_MANIFEST, _write_manifest(tmp_path, candidate_sha=sha, performance=perf)
    )
    monkeypatch_set(monkeypatch, FINAL_CI_RUN, _write_ci_snapshot(tmp_path, candidate_sha=sha))
    errors = validate_final(docs, candidate_sha=sha, check_git_ancestry=False)
    assert any("Performance candidate_sha" in e for e in errors)


def test_inventory_candidate_sha_differs_from_manifest_fails(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Inventory candidate_sha must equal manifest candidate_sha."""
    sha = "a" * 40
    docs = _write_evidence_docs(tmp_path, sha, "12345")
    monkeypatch_set(monkeypatch, FINAL_MANIFEST, _write_manifest(tmp_path, candidate_sha=sha))
    monkeypatch_set(monkeypatch, FINAL_CI_RUN, _write_ci_snapshot(tmp_path, candidate_sha=sha))
    monkeypatch_set(
        monkeypatch, FINAL_INVENTORY, _write_inventory(tmp_path, candidate_sha="b" * 40)
    )
    errors = validate_final(docs, candidate_sha=sha, check_git_ancestry=False)
    assert any("Inventory candidate_sha" in e for e in errors)


def test_inventory_run_id_differs_from_manifest_fails(tmp_path: Path, monkeypatch: object) -> None:
    """Inventory workflow_run_id must equal manifest candidate_workflow_run_id."""
    sha = "a" * 40
    docs = _write_evidence_docs(tmp_path, sha, "12345")
    monkeypatch_set(
        monkeypatch,
        FINAL_MANIFEST,
        _write_manifest(tmp_path, candidate_sha=sha, candidate_workflow_run_id=11111),
    )
    monkeypatch_set(
        monkeypatch,
        FINAL_CI_RUN,
        _write_ci_snapshot(tmp_path, candidate_sha=sha, candidate_workflow_run_id=11111),
    )
    monkeypatch_set(
        monkeypatch, FINAL_INVENTORY, _write_inventory(tmp_path, candidate_sha=sha, run_id=22222)
    )
    errors = validate_final(docs, candidate_sha=sha, check_git_ancestry=False)
    assert any("Inventory workflow_run_id" in e for e in errors)


# ---------------------------------------------------------------------------
# Provenance / hash tests
# ---------------------------------------------------------------------------


def test_artifact_with_note_text_exemption_fails(tmp_path: Path, monkeypatch: object) -> None:
    """Note text cannot suppress artifact hash validation."""
    sha = "a" * 40
    docs = _write_evidence_docs(tmp_path, sha, "12345")
    artifacts = {
        "eggcalc-1.1.6-py3-none-any.whl": {
            "kind": "wheel",
            "name": "eggcalc-1.1.6-py3-none-any.whl",
            "sha256": "1" * 64,
            "note": "Built during candidate workflow run 999",
        },
    }
    monkeypatch_set(
        monkeypatch,
        FINAL_MANIFEST,
        _write_manifest(tmp_path, candidate_sha=sha, artifacts=artifacts),
    )
    monkeypatch_set(monkeypatch, FINAL_CI_RUN, _write_ci_snapshot(tmp_path, candidate_sha=sha))
    errors = validate_final(docs, candidate_sha=sha, check_git_ancestry=False)
    assert any("note-based exemption" in e for e in errors)


def test_artifact_run_id_differs_from_manifest_fails(tmp_path: Path, monkeypatch: object) -> None:
    """Artifact provenance run id must match manifest run id."""
    sha = "a" * 40
    docs = _write_evidence_docs(tmp_path, sha, "12345")
    artifacts = {
        "eggcalc-1.1.6-py3-none-any.whl": {
            "kind": "wheel",
            "name": "eggcalc-1.1.6-py3-none-any.whl",
            "sha256": "1" * 64,
            "workflow_run_id": 999,
            "workflow_attempt": 1,
            "workflow_head_sha": sha,
            "artifact_id": 100,
            "artifact_bundle_name": "release-artifacts",
            "source_summary_path": "artifact-hashes.json",
        },
    }
    monkeypatch_set(
        monkeypatch,
        FINAL_MANIFEST,
        _write_manifest(
            tmp_path, candidate_sha=sha, candidate_workflow_run_id=12345, artifacts=artifacts
        ),
    )
    monkeypatch_set(
        monkeypatch,
        FINAL_CI_RUN,
        _write_ci_snapshot(tmp_path, candidate_sha=sha, candidate_workflow_run_id=12345),
    )
    errors = validate_final(docs, candidate_sha=sha, check_git_ancestry=False)
    assert any("workflow_run_id does not match" in e for e in errors)


def test_artifact_missing_structured_fields_fails(tmp_path: Path, monkeypatch: object) -> None:
    """Artifact records must include structured workflow provenance fields."""
    sha = "a" * 40
    docs = _write_evidence_docs(tmp_path, sha, "12345")
    artifacts = {
        "eggcalc-1.1.6-py3-none-any.whl": {
            "kind": "wheel",
            "name": "eggcalc-1.1.6-py3-none-any.whl",
            "sha256": "1" * 64,
        },
    }
    monkeypatch_set(
        monkeypatch,
        FINAL_MANIFEST,
        _write_manifest(tmp_path, candidate_sha=sha, artifacts=artifacts),
    )
    monkeypatch_set(monkeypatch, FINAL_CI_RUN, _write_ci_snapshot(tmp_path, candidate_sha=sha))
    errors = validate_final(docs, candidate_sha=sha, check_git_ancestry=False)
    assert any("missing structured field" in e for e in errors)


def test_artifact_hash_not_64_chars_fails(tmp_path: Path, monkeypatch: object) -> None:
    """An arbitrary 64-char string is not sufficient proof of an artifact."""
    sha = "a" * 40
    docs = _write_evidence_docs(tmp_path, sha, "12345")
    artifacts = {
        "eggcalc-1.1.6-py3-none-any.whl": {
            "kind": "wheel",
            "name": "eggcalc-1.1.6-py3-none-any.whl",
            "sha256": "not-64-chars",
            "workflow_run_id": 12345,
            "workflow_attempt": 1,
            "workflow_head_sha": sha,
            "artifact_id": 100,
            "artifact_bundle_name": "release-artifacts",
            "source_summary_path": "artifact-hashes.json",
        },
    }
    monkeypatch_set(
        monkeypatch,
        FINAL_MANIFEST,
        _write_manifest(tmp_path, candidate_sha=sha, artifacts=artifacts),
    )
    monkeypatch_set(monkeypatch, FINAL_CI_RUN, _write_ci_snapshot(tmp_path, candidate_sha=sha))
    errors = validate_final(docs, candidate_sha=sha, check_git_ancestry=False)
    assert any("missing 64-character SHA-256" in e for e in errors)


def test_approved_with_cross_record_errors_fails(tmp_path: Path, monkeypatch: object) -> None:
    """A manifest that declares APPROVED with cross-record errors is rejected."""
    sha = "a" * 40
    docs = _write_evidence_docs(tmp_path, sha, "12345")
    monkeypatch_set(
        monkeypatch,
        FINAL_MANIFEST,
        _write_manifest(
            tmp_path,
            candidate_sha=sha,
            workflow_head_sha="b" * 40,
            final_decision="APPROVED",
        ),
    )
    monkeypatch_set(monkeypatch, FINAL_CI_RUN, _write_ci_snapshot(tmp_path, candidate_sha=sha))
    errors = validate_final(docs, candidate_sha=sha, check_git_ancestry=False)
    assert any("final_decision=APPROVED but cross-record" in e for e in errors)


# ---------------------------------------------------------------------------
# Performance tests
# ---------------------------------------------------------------------------


def test_candidate_performance_with_five_samples_fails(tmp_path: Path, monkeypatch: object) -> None:
    """Five-sample candidate performance evidence must be rejected."""
    sha = "a" * 40
    docs = _write_evidence_docs(tmp_path, sha, "12345")

    candidate_perf_path = tmp_path / f"candidate-{sha[:12]}.json"
    candidate_perf_path.write_text(
        json.dumps(
            {
                "commit_sha": sha,
                "samples": 5,
                "warmups": 5,
                "os": "Linux",
                "python_version": "3.12.3",
                "architecture": "x86_64",
                "measurements": {},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    baseline_perf_path = tmp_path / "baseline-5a1bb34c.json"
    baseline_perf_path.write_text(
        json.dumps(
            {
                "commit_sha": "5a1bb34c9efa269ca6159217827f1742faa95d20",
                "samples": 15,
                "warmups": 5,
                "os": "Linux",
                "python_version": "3.12.3",
                "architecture": "x86_64",
                "measurements": {},
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    perf = {
        "baseline_sha": "5a1bb34c9efa269ca6159217827f1742faa95d20",
        "candidate_sha": sha,
        "baseline": {"path": str(baseline_perf_path), "hash_sha256": "x" * 64},
        "candidate": {"path": str(candidate_perf_path), "hash_sha256": "y" * 64},
        "comparison": {"path": "docs/performance/comparison.json", "hash_sha256": "z" * 64},
    }
    monkeypatch_set(
        monkeypatch, FINAL_MANIFEST, _write_manifest(tmp_path, candidate_sha=sha, performance=perf)
    )
    monkeypatch_set(monkeypatch, FINAL_CI_RUN, _write_ci_snapshot(tmp_path, candidate_sha=sha))
    errors = validate_final(docs, candidate_sha=sha, check_git_ancestry=False)
    assert any("samples=" in e for e in errors)


def test_candidate_performance_warmups_below_five_fails(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Candidate warmups below five must fail."""
    sha = "a" * 40
    docs = _write_evidence_docs(tmp_path, sha, "12345")

    candidate_perf_path = tmp_path / f"candidate-{sha[:12]}.json"
    candidate_perf_path.write_text(
        json.dumps(
            {
                "commit_sha": sha,
                "samples": 15,
                "warmups": 2,
                "os": "Linux",
                "python_version": "3.12.3",
                "architecture": "x86_64",
                "measurements": {},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    baseline_perf_path = tmp_path / "baseline-5a1bb34c.json"
    baseline_perf_path.write_text(
        json.dumps(
            {
                "commit_sha": "5a1bb34c9efa269ca6159217827f1742faa95d20",
                "samples": 15,
                "warmups": 5,
                "os": "Linux",
                "python_version": "3.12.3",
                "architecture": "x86_64",
                "measurements": {},
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    perf = {
        "baseline_sha": "5a1bb34c9efa269ca6159217827f1742faa95d20",
        "candidate_sha": sha,
        "baseline": {"path": str(baseline_perf_path), "hash_sha256": "x" * 64},
        "candidate": {"path": str(candidate_perf_path), "hash_sha256": "y" * 64},
        "comparison": {"path": "docs/performance/comparison.json", "hash_sha256": "z" * 64},
    }
    monkeypatch_set(
        monkeypatch, FINAL_MANIFEST, _write_manifest(tmp_path, candidate_sha=sha, performance=perf)
    )
    monkeypatch_set(monkeypatch, FINAL_CI_RUN, _write_ci_snapshot(tmp_path, candidate_sha=sha))
    errors = validate_final(docs, candidate_sha=sha, check_git_ancestry=False)
    assert any("warmups=" in e for e in errors)


def test_candidate_performance_environment_mismatch_fails(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Candidate performance environment must match baseline."""
    sha = "a" * 40
    docs = _write_evidence_docs(tmp_path, sha, "12345")

    candidate_perf_path = tmp_path / f"candidate-{sha[:12]}.json"
    candidate_perf_path.write_text(
        json.dumps(
            {
                "commit_sha": sha,
                "samples": 15,
                "warmups": 5,
                "os": "Linux",
                "python_version": "3.12.3",
                "architecture": "x86_64",
                "measurements": {},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    baseline_perf_path = tmp_path / "baseline-5a1bb34c.json"
    baseline_perf_path.write_text(
        json.dumps(
            {
                "commit_sha": "5a1bb34c9efa269ca6159217827f1742faa95d20",
                "samples": 15,
                "warmups": 5,
                "os": "Windows",  # mismatch
                "python_version": "3.12.3",
                "architecture": "x86_64",
                "measurements": {},
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    perf = {
        "baseline_sha": "5a1bb34c9efa269ca6159217827f1742faa95d20",
        "candidate_sha": sha,
        "baseline": {"path": str(baseline_perf_path), "hash_sha256": "x" * 64},
        "candidate": {"path": str(candidate_perf_path), "hash_sha256": "y" * 64},
        "comparison": {"path": "docs/performance/comparison.json", "hash_sha256": "z" * 64},
    }
    monkeypatch_set(
        monkeypatch, FINAL_MANIFEST, _write_manifest(tmp_path, candidate_sha=sha, performance=perf)
    )
    monkeypatch_set(monkeypatch, FINAL_CI_RUN, _write_ci_snapshot(tmp_path, candidate_sha=sha))
    errors = validate_final(docs, candidate_sha=sha, check_git_ancestry=False)
    assert any("environment mismatch" in e for e in errors)


def test_baseline_commit_sha_wrong_fails(tmp_path: Path, monkeypatch: object) -> None:
    """Baseline commit_sha must equal the expected baseline SHA."""
    sha = "a" * 40
    docs = _write_evidence_docs(tmp_path, sha, "12345")

    candidate_perf_path = tmp_path / f"candidate-{sha[:12]}.json"
    candidate_perf_path.write_text(
        json.dumps(
            {
                "commit_sha": sha,
                "samples": 15,
                "warmups": 5,
                "os": "Linux",
                "python_version": "3.12.3",
                "architecture": "x86_64",
                "measurements": {},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    baseline_perf_path = tmp_path / "baseline-5a1bb34c.json"
    baseline_perf_path.write_text(
        json.dumps(
            {
                "commit_sha": "f" * 40,  # wrong baseline
                "samples": 15,
                "warmups": 5,
                "os": "Linux",
                "python_version": "3.12.3",
                "architecture": "x86_64",
                "measurements": {},
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    perf = {
        "baseline_sha": "5a1bb34c9efa269ca6159217827f1742faa95d20",
        "candidate_sha": sha,
        "baseline": {"path": str(baseline_perf_path), "hash_sha256": "x" * 64},
        "candidate": {"path": str(candidate_perf_path), "hash_sha256": "y" * 64},
        "comparison": {"path": "docs/performance/comparison.json", "hash_sha256": "z" * 64},
    }
    monkeypatch_set(
        monkeypatch, FINAL_MANIFEST, _write_manifest(tmp_path, candidate_sha=sha, performance=perf)
    )
    monkeypatch_set(monkeypatch, FINAL_CI_RUN, _write_ci_snapshot(tmp_path, candidate_sha=sha))
    errors = validate_final(docs, candidate_sha=sha, check_git_ancestry=False)
    assert any("baseline commit_sha" in e or "expected baseline" in e for e in errors)


# ---------------------------------------------------------------------------
# Git ancestry tests
# ---------------------------------------------------------------------------


def test_final_mode_outside_git_repo_fails(tmp_path: Path, monkeypatch: object) -> None:
    """Final mode outside a Git checkout must fail when ancestry is enabled."""
    from scripts import check_evidence_consistency as mod

    sha = "a" * 40
    docs = _write_evidence_docs(tmp_path, sha, "12345")
    monkeypatch_set(monkeypatch, FINAL_MANIFEST, _write_manifest(tmp_path, candidate_sha=sha))
    monkeypatch_set(monkeypatch, FINAL_CI_RUN, _write_ci_snapshot(tmp_path, candidate_sha=sha))

    original_head = mod._git_head_sha
    original_parent = mod._git_parent_sha
    mod._git_head_sha = lambda: None  # type: ignore[assignment]
    mod._git_parent_sha = lambda: None  # type: ignore[assignment]
    try:
        errors = validate_final(docs, candidate_sha=sha, check_git_ancestry=True)
    finally:
        mod._git_head_sha = original_head  # type: ignore[assignment]
        mod._git_parent_sha = original_parent  # type: ignore[assignment]
    assert any("not a git repository" in e for e in errors)


def test_evidence_commit_with_non_allowlisted_files_fails(
    tmp_path: Path, monkeypatch: object
) -> None:
    """Adding one non-allowlisted file to the evidence commit must fail."""
    from scripts import check_evidence_consistency as mod

    sha = "a" * 40
    docs = _write_evidence_docs(tmp_path, sha, "12345")
    monkeypatch_set(monkeypatch, FINAL_MANIFEST, _write_manifest(tmp_path, candidate_sha=sha))
    monkeypatch_set(monkeypatch, FINAL_CI_RUN, _write_ci_snapshot(tmp_path, candidate_sha=sha))
    # Mock git ancestry to a single non-allowlisted file change.
    original_diff = mod._git_diff_names
    mod._git_diff_names = lambda p, h: {"eggcalc/evaluator.py"}  # type: ignore[assignment]
    try:
        errors = validate_final(docs, candidate_sha=sha, check_git_ancestry=True)
    finally:
        mod._git_diff_names = original_diff  # type: ignore[assignment]
    assert any("outside allowlist" in e for e in errors)


# ---------------------------------------------------------------------------
# Candidate state tests
# ---------------------------------------------------------------------------


def test_candidate_state_rejects_existing_final_manifest(tmp_path: Path) -> None:
    """Final manifest presence in candidate state is rejected."""
    fake_manifest = tmp_path / "releases-4-6-final.json"
    fake_manifest.write_text("{}", encoding="utf-8")
    monkeypatch_set_2(FINAL_MANIFEST, fake_manifest)
    errors = validate_candidate_state(DEFAULT_DOCUMENTS := DEFAULT_DOCS, check_repo_files=True)
    assert any("Final evidence file" in e for e in errors)


# ---------------------------------------------------------------------------
# Helpers (path monkeypatching without pytest import)
# ---------------------------------------------------------------------------


DEFAULT_DOCS = tuple(ROOT / "docs" / f"release_{n}_evidence.md" for n in (4, 5, 6))


def monkeypatch_set(monkeypatch: object, target: object, value: object) -> None:
    """Replace ``target`` (module attribute or pathlib.Path) for the duration."""
    monkeypatch._last_value = value  # keep alive
    # If target is a Path, set the module's module-level FINAL_* reference.
    name = getattr(target, "name", None)
    if name in {
        "releases-4-6-final.json",
        "releases-4-6-ci-run.json",
        "releases-4-6-inventory.json",
    }:
        # Re-point the module-level Path constants.
        from scripts import check_evidence_consistency as mod

        if name == "releases-4-6-final.json":
            mod.FINAL_MANIFEST = value
        elif name == "releases-4-6-ci-run.json":
            mod.FINAL_CI_RUN = value
        elif name == "releases-4-6-inventory.json":
            mod.FINAL_INVENTORY = value


def monkeypatch_set_2(target: object, value: object) -> None:
    """Single-arg helper for tests without monkeypatch."""
    from scripts import check_evidence_consistency as mod

    name = getattr(target, "name", None)
    if name == "releases-4-6-final.json":
        mod.FINAL_MANIFEST = value
    elif name == "releases-4-6-ci-run.json":
        mod.FINAL_CI_RUN = value
    elif name == "releases-4-6-inventory.json":
        mod.FINAL_INVENTORY = value
