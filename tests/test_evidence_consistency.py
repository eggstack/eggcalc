from __future__ import annotations

import re
from pathlib import Path

from scripts.check_evidence_consistency import (
    validate_candidate_state,
    validate_final,
)

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_DOCS = tuple(ROOT / "docs" / f"release_{n}_evidence.md" for n in (4, 5, 6))


def _document(tmp_path: Path, name: str, sha: str, run_id: str, totals: str) -> Path:
    path = tmp_path / name
    path.write_text(
        f"""# {name}

## Final Closure Evidence

- closure_code_sha: `{sha}`
- closure_workflow_run_id: `{run_id}`
- lane linux: {totals}

ordinary Ruff; Black; ordinary mypy; strict mypy; strict Ruff;
authority-boundary; deterministic build; authority inventory;
source typed consumer; installed-wheel typed consumer; MCP closure;
unit closure; release-surface.

Performance baseline and final identity are recorded.
""",
        encoding="utf-8",
    )
    return path


def _placeholder_document(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    path.write_text(
        f"""# {name}

## Final Closure Evidence

- closure_code_sha: `800832196439558383d22300ef36870c997437da`
- closure_workflow_run_id: `0000000000`
- lane linux: collected=4294 passed=4294 skipped=0 xfailed=0 xpassed=0 failed=0

ordinary Ruff; Black; ordinary mypy; strict mypy; strict Ruff;
authority-boundary; deterministic build; authority inventory;
source typed consumer; installed-wheel typed consumer; MCP closure;
unit closure; release-surface.

Performance baseline and final identity are recorded.
""",
        encoding="utf-8",
    )
    return path


def _absent_document(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    path.write_text(
        f"""# {name}

## Final Closure Evidence

Final closure evidence is intentionally absent until the code candidate receives
a successful GitHub Actions workflow run.
""",
        encoding="utf-8",
    )
    return path


# ---------------------------------------------------------------------------
# Backward-compatible validator
# ---------------------------------------------------------------------------


def test_evidence_validator_accepts_matching_exact_records(tmp_path: Path) -> None:
    sha = "a" * 40
    docs = tuple(
        _document(
            tmp_path,
            f"release_{n}.md",
            sha,
            "12345",
            "collected=10 passed=9 skipped=1 xfailed=0 xpassed=0 failed=0",
        )
        for n in (4, 5, 6)
    )

    # validate_documents falls back to validate_final when real evidence is detected
    errors = validate_final(docs, candidate_sha=sha, check_git_ancestry=False)
    assert errors == []


def test_evidence_validator_rejects_mismatched_identity_and_bad_totals(tmp_path: Path) -> None:
    docs = (
        _document(
            tmp_path,
            "release_4.md",
            "a" * 40,
            "12345",
            "collected=10 passed=9 skipped=1 xfailed=0 xpassed=0 failed=0",
        ),
        _document(
            tmp_path,
            "release_5.md",
            "b" * 40,
            "12346",
            "collected=10 passed=8 skipped=1 xfailed=0 xpassed=0 failed=0",
        ),
        _document(
            tmp_path,
            "release_6.md",
            "a" * 40,
            "12345",
            "collected=10 passed=9 skipped=1 xfailed=0 xpassed=0 failed=0",
        ),
    )

    errors = validate_final(docs, check_git_ancestry=False)

    assert any("identities do not match" in error for error in errors)
    assert any("totals do not add up" in error for error in errors)


# ---------------------------------------------------------------------------
# Candidate-state validator
# ---------------------------------------------------------------------------


def test_candidate_state_accepts_intentionally_absent_evidence(tmp_path: Path) -> None:
    docs = tuple(_absent_document(tmp_path, f"release_{n}.md") for n in (4, 5, 6))
    assert validate_candidate_state(docs, check_repo_files=False) == []


def test_candidate_state_accepts_no_final_section(tmp_path: Path) -> None:
    path = tmp_path / "release_4.md"
    path.write_text("# Release 4\n\nSome content without final section.\n", encoding="utf-8")
    assert validate_candidate_state((path,), check_repo_files=False) == []


def test_candidate_state_rejects_placeholder_sha(tmp_path: Path) -> None:
    docs = tuple(_placeholder_document(tmp_path, f"release_{n}.md") for n in (4, 5, 6))
    errors = validate_candidate_state(docs, check_repo_files=False)
    assert any("placeholder SHA" in error for error in errors)


def test_candidate_state_rejects_placeholder_run_id(tmp_path: Path) -> None:
    docs = tuple(_placeholder_document(tmp_path, f"release_{n}.md") for n in (4, 5, 6))
    errors = validate_candidate_state(docs, check_repo_files=False)
    assert any("placeholder workflow run ID" in error for error in errors)


# ---------------------------------------------------------------------------
# Final validator
# ---------------------------------------------------------------------------


def test_final_validator_accepts_real_evidence(tmp_path: Path) -> None:
    sha = "a" * 40
    docs = tuple(
        _document(
            tmp_path,
            f"release_{n}.md",
            sha,
            "12345",
            "collected=10 passed=9 skipped=1 xfailed=0 xpassed=0 failed=0",
        )
        for n in (4, 5, 6)
    )
    errors = validate_final(docs, candidate_sha=sha, check_git_ancestry=False)
    assert errors == []


def test_final_validator_rejects_placeholder_evidence(tmp_path: Path) -> None:
    docs = tuple(_placeholder_document(tmp_path, f"release_{n}.md") for n in (4, 5, 6))
    errors = validate_final(docs)
    assert any("placeholder" in error.lower() for error in errors)


def test_final_validator_rejects_mismatched_candidate_sha(tmp_path: Path) -> None:
    sha = "a" * 40
    docs = tuple(
        _document(
            tmp_path,
            f"release_{n}.md",
            sha,
            "12345",
            "collected=10 passed=9 skipped=1 xfailed=0 xpassed=0 failed=0",
        )
        for n in (4, 5, 6)
    )
    errors = validate_final(docs, candidate_sha="b" * 40)
    assert any("does not match candidate" in error for error in errors)


def test_final_validator_rejects_zero_run_id(tmp_path: Path) -> None:
    sha = "a" * 40
    docs = tuple(
        _document(
            tmp_path,
            f"release_{n}.md",
            sha,
            "0000000000",
            "collected=10 passed=9 skipped=1 xfailed=0 xpassed=0 failed=0",
        )
        for n in (4, 5, 6)
    )
    errors = validate_final(docs)
    assert any("placeholder" in error.lower() for error in errors)


# ---------------------------------------------------------------------------
# Repository-evidence validation: the committed docs must be self-consistent.
# ---------------------------------------------------------------------------


def test_repository_evidence_documents_have_final_closure_sections() -> None:
    """All three committed evidence docs must have a Final Closure Evidence section."""
    for doc in EVIDENCE_DOCS:
        assert doc.is_file(), f"Missing evidence doc: {doc}"
        text = doc.read_text(encoding="utf-8")
        assert (
            "## Final Closure Evidence" in text
        ), f"{doc.name}: missing Final Closure Evidence section"


def test_repository_evidence_no_placeholder_data() -> None:
    """The committed evidence docs must not contain placeholder SHA or run ID."""
    for doc in EVIDENCE_DOCS:
        text = doc.read_text(encoding="utf-8")
        assert (
            "800832196439558383d22300ef36870c997437da" not in text
        ), f"{doc.name}: contains placeholder SHA"
        if "closure_workflow_run_id" in text:
            match = re.search(r"closure_workflow_run_id:\s*`?(\d+)`?", text)
            if match:
                assert (
                    match.group(1) != "0000000000"
                ), f"{doc.name}: contains placeholder workflow run ID"


def test_repository_evidence_candidate_state_passes() -> None:
    """Candidate-state validation passes when no final evidence files exist.

    In the candidate phase, final evidence files (releases-4-6-final.json,
    releases-4-6-ci-run.json, releases-4-6-inventory.json) should not be
    committed.  When they are absent, candidate-state validation should not
    report file existence errors.
    """
    errors = validate_candidate_state(EVIDENCE_DOCS)
    file_errors = [e for e in errors if "Final evidence file" in e]
    other_errors = [e for e in errors if "Final evidence file" not in e]
    assert other_errors == [], f"Unexpected candidate-state errors: {other_errors}"
    # In candidate state, no evidence files should exist; file_errors should be empty.
    # In finalized state, file_errors would be 3 (expected).
    evidence_exists = all(
        (ROOT / "docs" / "evidence" / name).is_file()
        for name in (
            "releases-4-6-final.json",
            "releases-4-6-ci-run.json",
            "releases-4-6-inventory.json",
        )
    )
    if evidence_exists:
        assert len(file_errors) == 3
    else:
        assert len(file_errors) == 0


# ---------------------------------------------------------------------------
# Git ancestry and diff allowlist
# ---------------------------------------------------------------------------


def test_final_validator_checks_git_ancestry(tmp_path: Path) -> None:
    """Final validator reports Git ancestry errors for mock SHAs."""
    sha = "a" * 40
    docs = tuple(
        _document(
            tmp_path,
            f"release_{n}.md",
            sha,
            "12345",
            "collected=10 passed=9 skipped=1 xfailed=0 xpassed=0 failed=0",
        )
        for n in (4, 5, 6)
    )
    errors = validate_final(docs, candidate_sha=sha)
    # Git ancestry check should produce an error for mock SHA
    assert any("Git ancestry" in e or "evidence commit modifies" in e for e in errors)


def test_candidate_state_rejects_final_files() -> None:
    """Candidate-state validation rejects final evidence files when they exist."""
    evidence_dir = ROOT / "docs" / "evidence"
    has_final = evidence_dir.is_dir() and any(
        evidence_dir.joinpath(n).is_file()
        for n in (
            "releases-4-6-final.json",
            "releases-4-6-ci-run.json",
            "releases-4-6-inventory.json",
        )
    )
    errors = validate_candidate_state(EVIDENCE_DOCS, check_repo_files=True)
    file_errors = [e for e in errors if "Final evidence file" in e]
    if has_final:
        assert len(file_errors) == 3
    else:
        assert len(file_errors) == 0
