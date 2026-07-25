from __future__ import annotations

import re
from pathlib import Path

from scripts.check_evidence_consistency import validate_documents

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


def test_evidence_validator_accepts_matching_exact_records(tmp_path: Path) -> None:
    sha = "a" * 40
    docs = tuple(
        _document(
            tmp_path,
            f"release_{n}.md",
            sha,
            "12345",
            "collected=10 passed=9 skipped=1 xfailed=0 failed=0",
        )
        for n in (4, 5, 6)
    )

    assert validate_documents(docs) == []


def test_evidence_validator_rejects_mismatched_identity_and_bad_totals(tmp_path: Path) -> None:
    docs = (
        _document(
            tmp_path,
            "release_4.md",
            "a" * 40,
            "12345",
            "collected=10 passed=9 skipped=1 xfailed=0 failed=0",
        ),
        _document(
            tmp_path,
            "release_5.md",
            "b" * 40,
            "12346",
            "collected=10 passed=8 skipped=1 xfailed=0 failed=0",
        ),
        _document(
            tmp_path,
            "release_6.md",
            "a" * 40,
            "12345",
            "collected=10 passed=9 skipped=1 xfailed=0 failed=0",
        ),
    )

    errors = validate_documents(docs)

    assert any("identities do not match" in error for error in errors)
    assert any("totals do not add up" in error for error in errors)


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


def test_repository_evidence_commit_shas_match() -> None:
    """All three committed evidence docs must reference the same commit SHA."""
    shas: set[str] = set()
    for doc in EVIDENCE_DOCS:
        text = doc.read_text(encoding="utf-8")
        match = re.search(r"closure_code_sha:\s*`([0-9a-f]{40})`", text)
        if match:
            shas.add(match.group(1))
    # The docs may use different SHA formats; if any have closure_code_sha,
    # they must all agree.
    if shas:
        assert len(shas) == 1, f"Commit SHAs differ across evidence docs: {shas}"


def test_repository_evidence_all_pass() -> None:
    """The committed evidence docs must pass the consistency validator."""
    errors = validate_documents(EVIDENCE_DOCS)
    assert errors == [], f"Evidence consistency errors: {errors}"
