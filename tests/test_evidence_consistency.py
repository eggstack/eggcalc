from __future__ import annotations

from pathlib import Path

from scripts.check_evidence_consistency import validate_documents


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
