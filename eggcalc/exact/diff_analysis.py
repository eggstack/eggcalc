"""
Structural analysis tools for unified diffs and patches.

Provides five pure functions that analyze diff/patch structure:
- diff_touched_paths: classifies files as added/deleted/renamed/modified
- diff_hunk_ranges: extracts hunk ranges with line count classification
- diff_file_headers: extracts metadata from diff file headers
- patch_conflict_markers_inspect: detects conflict markers
- unified_diff_validate: validates diff structural integrity
"""

from __future__ import annotations

import re
from typing import TypedDict

from .patch import (
    MAX_PATCH_LENGTH,
    parse_unified_diff,
)


class DiffTouchedPathsFile(TypedDict):
    """A single file entry from diff_touched_paths."""

    path: str
    kind: str  # "added" | "deleted" | "renamed" | "modified"
    old_path: str | None
    new_path: str | None


class ModeChange(TypedDict):
    """A detected file mode change."""

    file: str
    old_mode: str
    new_mode: str


class DiffTouchedPathsResult(TypedDict):
    """Result of diff_touched_paths."""

    parse_ok: bool
    error: str | None
    added: list[str]
    deleted: list[str]
    renamed: list[dict[str, str]]
    modified: list[str]
    binary_files: list[str]
    mode_changes: list[ModeChange]
    total_files: int


class HunkDetail(TypedDict):
    """Details for a single hunk within a file."""

    old_start: int
    old_count: int
    new_start: int
    new_count: int
    added_lines: int
    deleted_lines: int
    context_lines: int
    header_line: str


class DiffHunkRangesFile(TypedDict):
    """Per-file hunk details from diff_hunk_ranges."""

    old_file: str
    new_file: str
    hunks: list[HunkDetail]
    total_added: int
    total_deleted: int
    total_context: int


class DiffHunkRangesResult(TypedDict):
    """Result of diff_hunk_ranges."""

    parse_ok: bool
    error: str | None
    files: list[DiffHunkRangesFile]


class DiffFileHeaderEntry(TypedDict):
    """Parsed header metadata for a single file."""

    old_file: str
    new_file: str
    diff_git_line: str | None
    index_line: str | None
    old_mode: str | None
    new_mode: str | None
    rename_from: str | None
    rename_to: str | None
    copy_from: str | None
    copy_to: str | None
    is_new_file: bool
    is_deleted_file: bool
    is_binary: bool
    hunks_count: int


class DiffFileHeadersResult(TypedDict):
    """Result of diff_file_headers."""

    parse_ok: bool
    error: str | None
    files: list[DiffFileHeaderEntry]


class ConflictMarkerLocation(TypedDict):
    """Location of a conflict marker."""

    line: int
    kind: str  # "start" | "separator" | "end"


class PatchConflictMarkersResult(TypedDict):
    """Result of patch_conflict_markers_inspect."""

    total_markers: int
    conflict_starts: int
    conflict_separators: int
    conflict_ends: int
    imbalanced: bool
    nested: bool
    locations: list[ConflictMarkerLocation]


class UnifiedDiffValidateResult(TypedDict):
    """Result of unified_diff_validate."""

    parse_ok: bool
    files_count: int
    hunks_total: int
    warnings: list[str]
    structure_valid: bool


_CONFLICT_START = re.compile(r"^<<<<<<<", re.MULTILINE)
_CONFLICT_SEP = re.compile(r"^=======$", re.MULTILINE)
_CONFLICT_END = re.compile(r"^>>>>>>>", re.MULTILINE)


def _diff_normalize_line(line: str) -> str:
    """Normalize a diff line for classification.

    Strips only trailing carriage returns. Trailing whitespace must be
    preserved: a blank context line ``" "`` would otherwise collapse to
    ``""`` and vanish from line-count classification.
    """
    return line.rstrip("\r")


def diff_touched_paths(patch_text: str, max_files: int = 100) -> DiffTouchedPathsResult:
    """Classify files in a unified diff as added, deleted, renamed, or modified.

    Also detects binary diffs and mode changes.
    """
    if not patch_text or not patch_text.strip():
        return DiffTouchedPathsResult(
            parse_ok=False,
            error="Empty patch text",
            added=[],
            deleted=[],
            renamed=[],
            modified=[],
            binary_files=[],
            mode_changes=[],
            total_files=0,
        )

    if len(patch_text) > MAX_PATCH_LENGTH:
        return DiffTouchedPathsResult(
            parse_ok=False,
            error=f"Patch text exceeds maximum length of {MAX_PATCH_LENGTH}",
            added=[],
            deleted=[],
            renamed=[],
            modified=[],
            binary_files=[],
            mode_changes=[],
            total_files=0,
        )

    pr = parse_unified_diff(patch_text)
    if not pr["ok"]:
        return DiffTouchedPathsResult(
            parse_ok=False,
            error=pr["error"],
            added=[],
            deleted=[],
            renamed=[],
            modified=[],
            binary_files=[],
            mode_changes=[],
            total_files=0,
        )

    added: list[str] = []
    deleted: list[str] = []
    renamed: list[dict[str, str]] = []
    modified: list[str] = []
    binary_files: list[str] = []
    mode_changes: list[ModeChange] = []

    files = pr["files"][:max_files]

    has_binary = "Binary files" in patch_text or "GIT binary patch" in patch_text

    mode_pattern = re.compile(r"^(old mode|new mode)\s+(\S+)", re.MULTILINE)
    rename_from_pattern = re.compile(r"^rename from\s+(.+)$", re.MULTILINE)
    rename_to_pattern = re.compile(r"^rename to\s+(.+)$", re.MULTILINE)

    mode_old: dict[str, str] = {}
    mode_new: dict[str, str] = {}
    renames_from: dict[str, str] = {}
    renames_to: dict[str, str] = {}

    for m in mode_pattern.finditer(patch_text):
        kind, mode_val = m.group(1), m.group(2)
        file_ctx = _find_file_context(patch_text, m)
        if kind == "old mode":
            mode_old[file_ctx] = mode_val
        else:
            mode_new[file_ctx] = mode_val

    for m in rename_from_pattern.finditer(patch_text):
        file_ctx = _find_file_context(patch_text, m)
        renames_from[file_ctx] = m.group(1).strip()
    for m in rename_to_pattern.finditer(patch_text):
        file_ctx = _find_file_context(patch_text, m)
        renames_to[file_ctx] = m.group(1).strip()

    for f in files:
        old_file = f["old_file"]
        new_file = f["new_file"]

        file_label = new_file or old_file
        if file_label in mode_old and file_label in mode_new:
            mode_changes.append(
                ModeChange(
                    file=file_label,
                    old_mode=mode_old[file_label],
                    new_mode=mode_new[file_label],
                )
            )

        if file_label in renames_from and file_label in renames_to:
            renamed.append(
                {
                    "from": renames_from[file_label],
                    "to": renames_to[file_label],
                }
            )
        elif old_file == "" and new_file:
            added.append(new_file)
        elif new_file == "" and old_file:
            deleted.append(old_file)
        else:
            modified.append(file_label)

    if has_binary:
        for f in files:
            file_label = f["new_file"] or f["old_file"]
            if file_label and file_label not in binary_files:
                binary_files.append(file_label)

    return DiffTouchedPathsResult(
        parse_ok=True,
        error=None,
        added=added,
        deleted=deleted,
        renamed=renamed,
        modified=modified,
        binary_files=binary_files,
        mode_changes=mode_changes,
        total_files=len(files),
    )


def _find_file_context(patch_text: str, match: re.Match[str]) -> str:
    """Find the file path for a directive by scanning for --- or +++ lines.

    Scans backward for +++ first (most common: directive between +++ and @@),
    then backward for ---, then forward for +++ (handles directives before ---/+++),
    then forward for ---.
    """
    pos = match.start()
    before = patch_text[:pos]
    after = patch_text[match.end() :]

    # Backward: prefer +++ (directive is after +++ line)
    for line in reversed(before.split("\n")):
        line_s = line.rstrip()
        if line_s.startswith("+++ "):
            return line_s[4:].strip()
    for line in reversed(before.split("\n")):
        line_s = line.rstrip()
        if line_s.startswith("--- "):
            return line_s[4:].strip()

    # Forward: scan for the next --- / +++ pair, prefer +++ (new file)
    fwd_old = ""
    fwd_new = ""
    for line in after.split("\n"):
        line_s = line.rstrip()
        if line_s.startswith("--- "):
            fwd_old = line_s[4:].strip()
        elif line_s.startswith("+++ "):
            fwd_new = line_s[4:].strip()
            break
        elif line_s.startswith("@@ ") or line_s.startswith("diff --git"):
            break
    return fwd_new or fwd_old


def diff_hunk_ranges(patch_text: str, max_files: int = 100) -> DiffHunkRangesResult:
    """Extract hunk ranges per file with line count classification."""
    if not patch_text or not patch_text.strip():
        return DiffHunkRangesResult(parse_ok=False, error="Empty patch text", files=[])

    if len(patch_text) > MAX_PATCH_LENGTH:
        return DiffHunkRangesResult(
            parse_ok=False,
            error=f"Patch text exceeds maximum length of {MAX_PATCH_LENGTH}",
            files=[],
        )

    pr = parse_unified_diff(patch_text)
    if not pr["ok"]:
        return DiffHunkRangesResult(parse_ok=False, error=pr["error"], files=[])

    files_result: list[DiffHunkRangesFile] = []

    for f in pr["files"][:max_files]:
        hunks_detail: list[HunkDetail] = []
        total_added = 0
        total_deleted = 0
        total_context = 0

        for hunk in f["hunks"]:
            added = 0
            deleted = 0
            context = 0

            for hline in hunk["lines"]:
                normalized = _diff_normalize_line(hline)
                if normalized.startswith("+"):
                    added += 1
                elif normalized.startswith("-"):
                    deleted += 1
                elif normalized.startswith(" "):
                    context += 1

            total_added += added
            total_deleted += deleted
            total_context += context

            hunks_detail.append(
                HunkDetail(
                    old_start=hunk["old_start"],
                    old_count=hunk["old_count"],
                    new_start=hunk["new_start"],
                    new_count=hunk["new_count"],
                    added_lines=added,
                    deleted_lines=deleted,
                    context_lines=context,
                    header_line=hunk["header_line"],
                )
            )

        files_result.append(
            DiffHunkRangesFile(
                old_file=f["old_file"],
                new_file=f["new_file"],
                hunks=hunks_detail,
                total_added=total_added,
                total_deleted=total_deleted,
                total_context=total_context,
            )
        )

    return DiffHunkRangesResult(parse_ok=True, error=None, files=files_result)


def diff_file_headers(patch_text: str, max_files: int = 100) -> DiffFileHeadersResult:
    """Extract metadata from diff file headers.

    Scans the raw patch text line-by-line to extract diff --git lines,
    index hashes, mode changes, rename/copy directives, and binary file
    indicators, then cross-references with parse_unified_diff for hunk counts.
    """
    if not patch_text or not patch_text.strip():
        return DiffFileHeadersResult(parse_ok=False, error="Empty patch text", files=[])

    if len(patch_text) > MAX_PATCH_LENGTH:
        return DiffFileHeadersResult(
            parse_ok=False,
            error=f"Patch text exceeds maximum length of {MAX_PATCH_LENGTH}",
            files=[],
        )

    pr = parse_unified_diff(patch_text)
    if not pr["ok"]:
        return DiffFileHeadersResult(parse_ok=False, error=pr["error"], files=[])

    git_line_re = re.compile(r"^diff --git\s+(.+)\s+(.+)$")
    rename_from_re = re.compile(r"^rename from\s+(.+)$")
    rename_to_re = re.compile(r"^rename to\s+(.+)$")
    copy_from_re = re.compile(r"^copy from\s+(.+)$")
    copy_to_re = re.compile(r"^copy to\s+(.+)$")
    binary_re = re.compile(r"^Binary files .+ and .+ differ$")

    file_entries: list[DiffFileHeaderEntry] = []
    lines = patch_text.split("\n")

    current_git_line: str | None = None
    current_index: str | None = None
    current_old_mode: str | None = None
    current_new_mode: str | None = None
    current_rename_from: str | None = None
    current_rename_to: str | None = None
    current_copy_from: str | None = None
    current_copy_to: str | None = None
    current_is_new = False
    current_is_deleted = False
    current_is_binary = False
    current_old_file: str | None = None
    current_new_file: str | None = None

    def _emit_file() -> None:
        if current_old_file is not None or current_new_file is not None:
            old_f = current_old_file or ""
            new_f = current_new_file or ""
            hunks_count = 0
            for pf in pr["files"]:
                if pf["old_file"] == old_f and pf["new_file"] == new_f:
                    hunks_count = len(pf["hunks"])
                    break
            file_entries.append(
                DiffFileHeaderEntry(
                    old_file=old_f,
                    new_file=new_f,
                    diff_git_line=current_git_line,
                    index_line=current_index,
                    old_mode=current_old_mode,
                    new_mode=current_new_mode,
                    rename_from=current_rename_from,
                    rename_to=current_rename_to,
                    copy_from=current_copy_from,
                    copy_to=current_copy_to,
                    is_new_file=current_is_new,
                    is_deleted_file=current_is_deleted,
                    is_binary=current_is_binary,
                    hunks_count=hunks_count,
                )
            )

    for i, line in enumerate(lines):
        stripped = line.rstrip()

        if stripped.startswith("diff --git "):
            _emit_file()
            m = git_line_re.match(stripped)
            if m:
                current_git_line = stripped
                current_index = None
                current_old_mode = None
                current_new_mode = None
                current_rename_from = None
                current_rename_to = None
                current_copy_from = None
                current_copy_to = None
                current_is_new = False
                current_is_deleted = False
                current_is_binary = False
                current_old_file = None
                current_new_file = None

        elif stripped.startswith("index ") and current_git_line is not None:
            current_index = stripped

        elif stripped.startswith("old mode ") and current_git_line is not None:
            current_old_mode = stripped.split(None, 2)[-1] if len(stripped.split()) >= 3 else None

        elif stripped.startswith("new mode ") and current_git_line is not None:
            current_new_mode = stripped.split(None, 2)[-1] if len(stripped.split()) >= 3 else None

        elif stripped.startswith("rename from ") and current_git_line is not None:
            m = rename_from_re.match(stripped)
            if m:
                current_rename_from = m.group(1).strip()

        elif stripped.startswith("rename to ") and current_git_line is not None:
            m = rename_to_re.match(stripped)
            if m:
                current_rename_to = m.group(1).strip()

        elif stripped.startswith("copy from ") and current_git_line is not None:
            m = copy_from_re.match(stripped)
            if m:
                current_copy_from = m.group(1).strip()

        elif stripped.startswith("copy to ") and current_git_line is not None:
            m = copy_to_re.match(stripped)
            if m:
                current_copy_to = m.group(1).strip()

        elif stripped.startswith("new file mode") and current_git_line is not None:
            current_is_new = True

        elif stripped.startswith("deleted file mode") and current_git_line is not None:
            current_is_deleted = True

        elif binary_re.match(stripped) and current_git_line is not None:
            current_is_binary = True

        elif stripped.startswith("--- ") and current_git_line is not None:
            current_old_file = stripped[4:].strip()
            if i + 1 < len(lines) and lines[i + 1].rstrip().startswith("+++ "):
                current_new_file = lines[i + 1].rstrip()[4:].strip()

    _emit_file()

    return DiffFileHeadersResult(parse_ok=True, error=None, files=file_entries)


def patch_conflict_markers_inspect(
    text: str,
) -> PatchConflictMarkersResult:
    """Detect conflict markers in text.

    Scans for <<<<<<<, =======, >>>>>>> markers. Reports counts,
    balance, nesting, and line locations.
    """
    if not text:
        return PatchConflictMarkersResult(
            total_markers=0,
            conflict_starts=0,
            conflict_separators=0,
            conflict_ends=0,
            imbalanced=False,
            nested=False,
            locations=[],
        )

    if len(text) > MAX_PATCH_LENGTH:
        return PatchConflictMarkersResult(
            total_markers=0,
            conflict_starts=0,
            conflict_separators=0,
            conflict_ends=0,
            imbalanced=False,
            nested=False,
            locations=[],
        )

    starts = list(_CONFLICT_START.finditer(text))
    seps = list(_CONFLICT_SEP.finditer(text))
    ends = list(_CONFLICT_END.finditer(text))

    conflict_starts_count = len(starts)
    conflict_seps_count = len(seps)
    conflict_ends_count = len(ends)

    all_markers = []
    for m in starts:
        all_markers.append((m.start(), "start"))
    for m in seps:
        all_markers.append((m.start(), "separator"))
    for m in ends:
        all_markers.append((m.start(), "end"))

    all_markers.sort(key=lambda x: x[0])

    locations: list[ConflictMarkerLocation] = []
    for pos, kind in all_markers:
        line_num = text[:pos].count("\n") + 1
        locations.append(ConflictMarkerLocation(line=line_num, kind=kind))

    imbalanced = conflict_starts_count != conflict_ends_count

    nested = False
    depth = 0
    for _, kind in all_markers:
        if kind == "start":
            depth += 1
            if depth > 1:
                nested = True
                break
        elif kind == "end":
            depth = max(0, depth - 1)

    return PatchConflictMarkersResult(
        total_markers=conflict_starts_count + conflict_seps_count + conflict_ends_count,
        conflict_starts=conflict_starts_count,
        conflict_separators=conflict_seps_count,
        conflict_ends=conflict_ends_count,
        imbalanced=imbalanced,
        nested=nested,
        locations=locations,
    )


def unified_diff_validate(
    patch_text: str, check_line_counts: bool = True
) -> UnifiedDiffValidateResult:
    """Validate the structural integrity of a unified diff.

    Checks parse success, hunk header format, line count consistency,
    and stray lines before first hunk.
    """
    warnings: list[str] = []

    if not patch_text or not patch_text.strip():
        return UnifiedDiffValidateResult(
            parse_ok=False,
            files_count=0,
            hunks_total=0,
            warnings=["Empty patch text"],
            structure_valid=False,
        )

    if len(patch_text) > MAX_PATCH_LENGTH:
        return UnifiedDiffValidateResult(
            parse_ok=False,
            files_count=0,
            hunks_total=0,
            warnings=[f"Patch text exceeds maximum length of {MAX_PATCH_LENGTH}"],
            structure_valid=False,
        )

    pr = parse_unified_diff(patch_text)
    if not pr["ok"]:
        return UnifiedDiffValidateResult(
            parse_ok=False,
            files_count=0,
            hunks_total=0,
            warnings=[pr["error"] or "Parse failed"],
            structure_valid=False,
        )

    files_count = len(pr["files"])
    hunks_total = 0

    for f in pr["files"]:
        for hunk in f["hunks"]:
            hunks_total += 1
            parsed = _parse_hunk_header_simple(hunk["header_line"])
            if parsed is None:
                warnings.append(f"Malformed hunk header: {hunk['header_line']!r}")
                continue

            old_s, old_c, new_s, new_c = parsed

            if old_c == 0 and new_c == 0:
                warnings.append(
                    f"Hunk '{hunk['header_line']}' has zero counts for both old and new"
                )

            if check_line_counts:
                total_lines = len(hunk["lines"])
                deleted = sum(1 for l in hunk["lines"] if _diff_normalize_line(l).startswith("-"))
                context = sum(1 for l in hunk["lines"] if _diff_normalize_line(l).startswith(" "))
                added = sum(1 for l in hunk["lines"] if _diff_normalize_line(l).startswith("+"))
                # Warn if body has more lines than header declares
                if old_c > 0 and (deleted + context) > old_c:
                    warnings.append(
                        f"Hunk '{hunk['header_line']}': old count {old_c} "
                        f"but body has {deleted + context} old-side lines"
                    )
                if new_c > 0 and (added + context) > new_c:
                    warnings.append(
                        f"Hunk '{hunk['header_line']}': new count {new_c} "
                        f"but body has {added + context} new-side lines"
                    )

                if old_c > 0 or new_c > 0:
                    if total_lines == 0:
                        warnings.append(
                            f"Hunk '{hunk['header_line']}': header declares lines "
                            f"but hunk body is empty"
                        )

    lines = patch_text.split("\n")
    first_hunk_line = None
    for idx, line in enumerate(lines):
        stripped = line.rstrip()
        if stripped.startswith("@@ ") and first_hunk_line is None:
            first_hunk_line = idx
            break

    if first_hunk_line is not None:
        stray_before = lines[:first_hunk_line]
        stray_lines = [
            l
            for l in stray_before
            if l.strip()
            and not l.strip().startswith("diff --git")
            and not l.strip().startswith("index ")
            and not l.strip().startswith("--- ")
            and not l.strip().startswith("+++ ")
            and not l.strip().startswith("old mode")
            and not l.strip().startswith("new mode")
            and not l.strip().startswith("new file mode")
            and not l.strip().startswith("deleted file mode")
            and not l.strip().startswith("rename from")
            and not l.strip().startswith("rename to")
            and not l.strip().startswith("copy from")
            and not l.strip().startswith("copy to")
            and not l.strip().startswith("similarity")
            and not l.strip().startswith("GIT binary patch")
        ]
        if stray_lines:
            warnings.append(f"Found {len(stray_lines)} stray line(s) before first hunk header")

    structure_valid = pr["ok"] and not warnings

    return UnifiedDiffValidateResult(
        parse_ok=True,
        files_count=files_count,
        hunks_total=hunks_total,
        warnings=warnings,
        structure_valid=structure_valid,
    )


def _parse_hunk_header_simple(line: str) -> tuple[int, int, int, int] | None:
    """Parse a @@ -start,count +start,count @@ header line."""
    m = re.match(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line)
    if not m:
        return None
    old_start = int(m.group(1))
    old_count = int(m.group(2) or "1")
    new_start = int(m.group(3))
    new_count = int(m.group(4) or "1")
    return old_start, old_count, new_start, new_count
