"""
Unified diff parsing and simulation tools.

Provides functions to parse unified diffs, check if patches apply to
in-memory text, and summarize patch contents without modifying files.
"""

from __future__ import annotations

import hashlib
import re
from typing import TypedDict

MAX_PATCH_LENGTH = 200_000
MAX_ORIGINAL_LENGTH = 200_000
MAX_RESULT_TEXT_LENGTH = 50_000


class PatchHunk(TypedDict):
    """A single hunk parsed from a unified diff."""

    old_start: int
    old_count: int
    new_start: int
    new_count: int
    header_line: str
    lines: list[str]
    raw: str


class PatchFile(TypedDict):
    """A single file parsed from a unified diff."""

    old_file: str
    new_file: str
    hunks: list[PatchHunk]
    raw: str


class PatchParseResult(TypedDict):
    """Result of parsing a unified diff."""

    ok: bool
    files: list[PatchFile]
    error: str | None


class FailedHunk(TypedDict):
    """Information about a hunk that failed to apply."""

    hunk_index: int
    old_start: int
    old_count: int
    expected_context: list[str]
    actual_context: list[str]
    reason: str


class PatchApplyCheckResult(TypedDict):
    """Result of checking whether a patch applies cleanly."""

    patch_parse_ok: bool
    applies: bool
    hunks_total: int
    hunks_applied: int
    hunks_failed: int
    failed_hunks: list[FailedHunk]
    affected_line_ranges: list[dict[str, int]]
    newline_style_before: str
    newline_style_after: str
    result_fingerprint: str
    result_text: str | None
    findings: list[str]


class PatchSummaryResult(TypedDict):
    """Result of summarizing a unified diff."""

    files_changed: int
    hunks_total: int
    additions: int
    deletions: int
    renames_detected: list[dict[str, str]]
    binary_patch_detected: bool
    line_ranges_by_file: dict[str, list[dict[str, int]]]
    findings: list[str]


def _patch_detect_newline_style(text: str) -> str:
    """Detect newline style in text."""
    crlf_count = text.count("\r\n")
    lf_count = text.count("\n") - crlf_count
    if crlf_count > 0 and lf_count == 0:
        return "CRLF"
    elif lf_count > 0 and crlf_count == 0:
        return "LF"
    elif crlf_count > 0 and lf_count > 0:
        return "mixed"
    return "none"


def _parse_hunk_header(line: str) -> tuple[int, int, int, int] | None:
    """Parse a @@ -start,count +start,count @@ header line."""
    m = re.match(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', line)
    if not m:
        return None
    old_start = int(m.group(1))
    old_count = int(m.group(2) or "1")
    new_start = int(m.group(3))
    new_count = int(m.group(4) or "1")
    return old_start, old_count, new_start, new_count


def parse_unified_diff(patch_text: str) -> PatchParseResult:
    """Parse a unified diff string into structured data.

    Args:
        patch_text: Raw unified diff text.

    Returns:
        PatchParseResult with parsed files and hunks.
    """
    if not patch_text or not patch_text.strip():
        return PatchParseResult(ok=False, files=[], error="Empty patch text")

    files: list[PatchFile] = []
    lines = patch_text.split("\n")
    i = 0
    current_old_file = ""
    current_new_file = ""
    current_hunks: list[PatchHunk] = []
    current_hunk_lines: list[str] = []
    current_hunk_header = ""
    current_hunk_info: tuple[int, int, int, int] | None = None
    in_hunk = False

    while i < len(lines):
        line = lines[i]

        if line.startswith("--- ") or line.startswith("+++ "):
            if in_hunk and current_hunk_info:
                old_s, old_c, new_s, new_c = current_hunk_info
                raw = current_hunk_header + "\n" + "\n".join(current_hunk_lines)
                current_hunks.append(
                    PatchHunk(
                        old_start=old_s,
                        old_count=old_c,
                        new_start=new_s,
                        new_count=new_c,
                        header_line=current_hunk_header,
                        lines=list(current_hunk_lines),
                        raw=raw,
                    )
                )
                in_hunk = False
                current_hunk_lines = []
                current_hunk_info = None

            if line.startswith("--- "):
                current_old_file = line[4:].strip()
                if current_old_file == "/dev/null":
                    current_old_file = ""
            elif line.startswith("+++ "):
                current_new_file = line[4:].strip()
                if current_new_file == "/dev/null":
                    current_new_file = ""

            if current_old_file and current_new_file:
                if not in_hunk:
                    if i + 1 < len(lines):
                        next_line = lines[i + 1]
                        if next_line.startswith("@@ "):
                            pass
                        elif current_old_file or current_new_file:
                            pass

        elif line.startswith("@@ "):
            if in_hunk and current_hunk_info:
                old_s, old_c, new_s, new_c = current_hunk_info
                raw = current_hunk_header + "\n" + "\n".join(current_hunk_lines)
                current_hunks.append(
                    PatchHunk(
                        old_start=old_s,
                        old_count=old_c,
                        new_start=new_s,
                        new_count=new_c,
                        header_line=current_hunk_header,
                        lines=list(current_hunk_lines),
                        raw=raw,
                    )
                )
                current_hunk_lines = []

            parsed = _parse_hunk_header(line)
            if parsed:
                current_hunk_info = parsed
                current_hunk_header = line
                in_hunk = True
            else:
                files.append(
                    PatchFile(
                        old_file=current_old_file,
                        new_file=current_new_file,
                        hunks=list(current_hunks),
                        raw=patch_text,
                    )
                )
                current_old_file = ""
                current_new_file = ""
                current_hunks = []
                in_hunk = False
        elif in_hunk:
            current_hunk_lines.append(line)

        i += 1

    if in_hunk and current_hunk_info:
        old_s, old_c, new_s, new_c = current_hunk_info
        raw = current_hunk_header + "\n" + "\n".join(current_hunk_lines)
        current_hunks.append(
            PatchHunk(
                old_start=old_s,
                old_count=old_c,
                new_start=new_s,
                new_count=new_c,
                header_line=current_hunk_header,
                lines=list(current_hunk_lines),
                raw=raw,
            )
        )

    if current_old_file or current_new_file or current_hunks:
        files.append(
            PatchFile(
                old_file=current_old_file,
                new_file=current_new_file,
                hunks=list(current_hunks),
                raw=patch_text,
            )
        )

    if not files:
        return PatchParseResult(
            ok=False,
            files=[],
            error="No unified diff headers found (-- a/... / +++ b/... or @@ ... @@)",
        )

    return PatchParseResult(ok=True, files=files, error=None)


def _text_to_lines(text: str) -> list[str]:
    """Convert text to list of lines, stripping trailing newline if present."""
    if text.endswith("\n"):
        text = text[:-1]
    if text.endswith("\r"):
        text = text[:-1]
    return text.split("\n")


def _lines_to_text(lines: list[str]) -> str:
    """Convert list of lines back to text."""
    return "\n".join(lines)


def _patch_normalize_line(line: str) -> str:
    """Normalize a diff line for comparison (strip CRLF)."""
    return line.rstrip("\r")


def _strip_line_prefix(line: str) -> str:
    """Strip the diff prefix (space, +, -) from a line."""
    if line.startswith("+"):
        return line[1:]
    elif line.startswith("-"):
        return line[1:]
    elif line.startswith(" "):
        return line[1:]
    return line


def _patch_fingerprint(text: str) -> str:
    """Compute SHA-256 fingerprint of text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _apply_hunk(
    original_lines: list[str],
    hunk: PatchHunk,
    strict: bool = True,
) -> tuple[list[str] | None, str | None]:
    """Try to apply a single hunk to original lines.

    Args:
        original_lines: Lines of the original text.
        hunk: The parsed hunk to apply.
        strict: If True, context lines must match exactly.

    Returns:
        Tuple of (new_lines, error_message). If application fails, new_lines is None.
    """
    old_start = hunk["old_start"] - 1  # Convert to 0-based
    old_count = hunk["old_count"]

    if old_start < 0:
        return None, f"Invalid hunk start: {hunk['old_start']}"

    actual_context: list[str] = []
    expected_context: list[str] = []

    for hline in hunk["lines"]:
        normalized = _patch_normalize_line(hline)
        if normalized.startswith(" ") or normalized.startswith("-"):
            expected_context.append(_strip_line_prefix(normalized))

    actual_end = old_start + old_count
    if actual_end > len(original_lines):
        if strict:
            return None, (
                f"Hunk references lines {hunk['old_start']}-{hunk['old_start'] + old_count - 1} "
                f"but original has only {len(original_lines)} lines"
            )
        actual_context = original_lines[old_start:]
    else:
        actual_context = original_lines[old_start:actual_end]

    if strict and len(expected_context) != len(actual_context):
        return None, (
            f"Context length mismatch: hunk expects {len(expected_context)} lines, "
            f"actual has {len(actual_context)} lines"
        )

    for idx, (expected, actual) in enumerate(zip(expected_context, actual_context, strict=False)):
        if strict and _patch_normalize_line(expected) != _patch_normalize_line(actual):
            return None, (
                f"Context mismatch at line {hunk['old_start'] + idx}: "
                f"expected {_patch_normalize_line(expected)!r}, got {_patch_normalize_line(actual)!r}"
            )

    new_lines: list[str] = []
    new_idx = 0
    hunk_idx = 0

    while hunk_idx < len(hunk["lines"]):
        hline = _patch_normalize_line(hunk["lines"][hunk_idx])
        if hline.startswith(" "):
            if new_idx < len(original_lines):
                new_lines.append(original_lines[new_idx])
            else:
                new_lines.append(_strip_line_prefix(hline))
            new_idx += 1
            hunk_idx += 1
        elif hline.startswith("-"):
            new_idx += 1
            hunk_idx += 1
        elif hline.startswith("+"):
            new_lines.append(_strip_line_prefix(hline))
            hunk_idx += 1
        elif hline.startswith("\\"):
            hunk_idx += 1
        else:
            hunk_idx += 1

    while new_idx < len(original_lines):
        new_lines.append(original_lines[new_idx])
        new_idx += 1

    return new_lines, None


def patch_apply_check(
    original_text: str,
    patch_text: str,
    strict: bool = True,
    return_result_fingerprint: bool = True,
    return_result_text: bool = False,
) -> PatchApplyCheckResult:
    """Check whether a unified diff applies cleanly to original text.

    Args:
        original_text: The original source text.
        patch_text: The unified diff patch.
        strict: If True, context lines must match exactly.
        return_result_fingerprint: If True, compute SHA-256 of result.
        return_result_text: If True, include the resulting text (bounded).

    Returns:
        PatchApplyCheckResult with application status and details.
    """
    findings: list[str] = []
    failed_hunks: list[FailedHunk] = []
    affected_line_ranges: list[dict[str, int]] = []

    if len(original_text) > MAX_ORIGINAL_LENGTH:
        return PatchApplyCheckResult(
            patch_parse_ok=False,
            applies=False,
            hunks_total=0,
            hunks_applied=0,
            hunks_failed=0,
            failed_hunks=[],
            affected_line_ranges=[],
            newline_style_before=_patch_detect_newline_style(original_text),
            newline_style_after=_patch_detect_newline_style(original_text),
            result_fingerprint="",
            result_text=None,
            findings=[f"Original text exceeds maximum length of {MAX_ORIGINAL_LENGTH}"],
        )

    if len(patch_text) > MAX_PATCH_LENGTH:
        return PatchApplyCheckResult(
            patch_parse_ok=False,
            applies=False,
            hunks_total=0,
            hunks_applied=0,
            hunks_failed=0,
            failed_hunks=[],
            affected_line_ranges=[],
            newline_style_before=_patch_detect_newline_style(original_text),
            newline_style_after=_patch_detect_newline_style(original_text),
            result_fingerprint="",
            result_text=None,
            findings=[f"Patch text exceeds maximum length of {MAX_PATCH_LENGTH}"],
        )

    newline_before = _patch_detect_newline_style(original_text)

    parse_result = parse_unified_diff(patch_text)
    if not parse_result["ok"]:
        return PatchApplyCheckResult(
            patch_parse_ok=False,
            applies=False,
            hunks_total=0,
            hunks_applied=0,
            hunks_failed=0,
            failed_hunks=[],
            affected_line_ranges=[],
            newline_style_before=newline_before,
            newline_style_after=newline_before,
            result_fingerprint="",
            result_text=None,
            findings=[f"Failed to parse patch: {parse_result['error']}"],
        )

    original_lines = _text_to_lines(original_text)
    all_hunks: list[PatchHunk] = []
    for file_entry in parse_result["files"]:
        all_hunks.extend(file_entry["hunks"])

    hunks_total = len(all_hunks)
    if hunks_total == 0:
        return PatchApplyCheckResult(
            patch_parse_ok=True,
            applies=True,
            hunks_total=0,
            hunks_applied=0,
            hunks_failed=0,
            failed_hunks=[],
            affected_line_ranges=[],
            newline_style_before=newline_before,
            newline_style_after=newline_before,
            result_fingerprint=_patch_fingerprint(original_text),
            result_text=original_text if return_result_text else None,
            findings=["No hunks found in patch"],
        )

    current_lines = list(original_lines)
    hunks_applied = 0
    hunks_failed = 0

    for hunk_idx, hunk in enumerate(all_hunks):
        result, error = _apply_hunk(current_lines, hunk, strict=strict)
        if result is not None:
            current_lines = result
            hunks_applied += 1
            affected_line_ranges.append(
                {
                    "start": hunk["new_start"],
                    "end": hunk["new_start"] + hunk["new_count"] - 1,
                }
            )
        else:
            hunks_failed += 1
            expected_ctx = [
                _strip_line_prefix(_patch_normalize_line(line))
                for line in hunk["lines"]
                if _patch_normalize_line(line).startswith(" ")
                or _patch_normalize_line(line).startswith("-")
            ]
            actual_end = min(hunk["old_start"] - 1 + hunk["old_count"], len(current_lines))
            actual_ctx = (
                current_lines[hunk["old_start"] - 1 : actual_end]
                if hunk["old_start"] - 1 < len(current_lines)
                else []
            )

            failed_hunks.append(
                FailedHunk(
                    hunk_index=hunk_idx,
                    old_start=hunk["old_start"],
                    old_count=hunk["old_count"],
                    expected_context=expected_ctx,
                    actual_context=actual_ctx,
                    reason=error or "Unknown error",
                )
            )

    applies = hunks_failed == 0
    result_text = _lines_to_text(current_lines) if return_result_text else None
    newline_after = _patch_detect_newline_style(result_text or original_text)

    if hunks_failed > 0:
        findings.append(f"{hunks_failed} of {hunks_total} hunks failed to apply")

    result_fingerprint = (
        _patch_fingerprint(result_text or original_text) if return_result_fingerprint else ""
    )

    return PatchApplyCheckResult(
        patch_parse_ok=True,
        applies=applies,
        hunks_total=hunks_total,
        hunks_applied=hunks_applied,
        hunks_failed=hunks_failed,
        failed_hunks=failed_hunks,
        affected_line_ranges=affected_line_ranges,
        newline_style_before=newline_before,
        newline_style_after=newline_after,
        result_fingerprint=result_fingerprint,
        result_text=result_text,
        findings=findings,
    )


def patch_summary(patch_text: str) -> PatchSummaryResult:
    """Summarize a unified diff without applying it.

    Args:
        patch_text: The unified diff text.

    Returns:
        PatchSummaryResult with summary statistics.
    """
    findings: list[str] = []

    if len(patch_text) > MAX_PATCH_LENGTH:
        return PatchSummaryResult(
            files_changed=0,
            hunks_total=0,
            additions=0,
            deletions=0,
            renames_detected=[],
            binary_patch_detected=False,
            line_ranges_by_file={},
            findings=[f"Patch text exceeds maximum length of {MAX_PATCH_LENGTH}"],
        )

    parse_result = parse_unified_diff(patch_text)

    if not parse_result["ok"]:
        return PatchSummaryResult(
            files_changed=0,
            hunks_total=0,
            additions=0,
            deletions=0,
            renames_detected=[],
            binary_patch_detected=False,
            line_ranges_by_file={},
            findings=[f"Failed to parse patch: {parse_result['error']}"],
        )

    files_changed = len(parse_result["files"])
    hunks_total = 0
    additions = 0
    deletions = 0
    renames_detected: list[dict[str, str]] = []
    binary_patch_detected = False
    line_ranges_by_file: dict[str, list[dict[str, int]]] = {}

    for file_entry in parse_result["files"]:
        old_file = file_entry["old_file"]
        new_file = file_entry["new_file"]

        # Renames are NOT inferred from `--- a/X` / `+++ b/Y` headers:
        # in a standard unified diff those are the source/destination
        # paths of a modification, which are normally different
        # (e.g. a/foo.txt vs b/foo.txt). True renames require an
        # explicit `rename from X` / `rename to Y` directive in an
        # extended diff format (e.g. `git diff -M`). The current
        # parser does not yet surface that metadata, so this list
        # stays empty until explicit rename support is added.
        # See plans/production_review_2026_07_b.md (B3).

        file_key = new_file or old_file
        file_ranges: list[dict[str, int]] = []

        for hunk in file_entry["hunks"]:
            hunks_total += 1
            hunk_additions = 0
            hunk_deletions = 0

            for hline in hunk["lines"]:
                normalized = _patch_normalize_line(hline)
                if normalized.startswith("+"):
                    hunk_additions += 1
                elif normalized.startswith("-"):
                    hunk_deletions += 1

            additions += hunk_additions
            deletions += hunk_deletions

            file_ranges.append(
                {
                    "start": hunk["new_start"],
                    "end": hunk["new_start"] + hunk["new_count"] - 1,
                }
            )

        if file_key:
            line_ranges_by_file[file_key] = file_ranges

    if "GIT binary patch" in patch_text or "\0" in patch_text:
        binary_patch_detected = True
        findings.append("Binary patch content detected")

    if not parse_result["files"]:
        findings.append("No file headers found in patch")

    return PatchSummaryResult(
        files_changed=files_changed,
        hunks_total=hunks_total,
        additions=additions,
        deletions=deletions,
        renames_detected=renames_detected,
        binary_patch_detected=binary_patch_detected,
        line_ranges_by_file=line_ranges_by_file,
        findings=findings,
    )
