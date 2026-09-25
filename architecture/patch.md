# patch.py — Unified Diff Parsing

638 lines. Parses unified diffs and simulates patch application on in-memory text.

## Table of Contents

- [Overview](#overview)
- [Type Definitions](#type-definitions)
- [Constants / Limits](#constants--limits)
- [Public Functions](#public-functions)
  - [parse_unified_diff](#parse_unified_diff)
  - [patch_apply_check](#patch_apply_check)
  - [patch_summary](#patch_summary)
- [Internal Helpers](#internal-helpers)
- [Dependencies](#dependencies)
- [Security / DoS Notes](#security--dos-notes)
- [See Also](#see-also)
- [Usage Example](#usage-example)

## Overview

Deterministic, pure, no I/O and no filesystem writes. Three layers over unified diffs:

- `parse_unified_diff`: splits patch text into files → hunks → lines (structure only).
- `patch_apply_check`: dry-runs hunks against an in-memory original (strict or lenient),
  reporting per-hunk success/failure, affected ranges, newline styles, and a SHA-256
  fingerprint (plus optional bounded result text).
- `patch_summary`: counts files/hunks/additions/deletions and maps line ranges per file,
  with binary-patch sniffing.

Results are plain-dict TypedDicts — use `result["files"]`, never `result.files`.
Line-range dicts are plain `dict[str, int]` (`{"start": int, "end": int}`), and
`renames_detected` is always `[]` (explicit rename directives unsupported — see below).

## Type Definitions

### PatchHunk (TypedDict)

```python
class PatchHunk(TypedDict):
    old_start: int       # 1-based old-file start (from @@ -s[,c] @@; bare -s means count 1)
    old_count: int       # old-file line count
    new_start: int       # 1-based new-file start (from @@ +s[,c] @@)
    new_count: int       # new-file line count
    header_line: str     # verbatim @@ ... @@ line
    lines: list[str]     # hunk body lines WITH their ' '/'+'/'-' prefixes (trailing "" from final \n included)
    raw: str             # header_line + "\n" + "\n".join(lines)
```

### PatchFile (TypedDict)

```python
class PatchFile(TypedDict):
    old_file: str            # from '--- ' ("/dev/null" normalized to ""); "" when absent
    new_file: str            # from '+++ ' (same normalization)
    hunks: list[PatchHunk]   # hunks in source order
    raw: str                 # the ENTIRE patch_text (not per-file slice)
```

### PatchParseResult (TypedDict)

```python
class PatchParseResult(TypedDict):
    ok: bool                  # False for empty text or no file/hunk headers
    files: list[PatchFile]    # [] on failure
    error: str | None         # "Empty patch text" | "No unified diff headers found (-- a/... / +++ b/... or @@ ... @@)"
```

### FailedHunk (TypedDict)

```python
class FailedHunk(TypedDict):
    hunk_index: int               # index into the flattened all-files hunk list
    old_start: int                # echo of the hunk's old_start
    old_count: int                # echo of the hunk's old_count
    expected_context: list[str]   # ' '/'-' body lines with prefix stripped
    actual_context: list[str]     # original lines at [old_start-1 : old_start-1+old_count]
    reason: str                   # e.g. "Context mismatch at line 2: expected 'old', got 'WRONG'"
```

### PatchApplyCheckResult (TypedDict)

```python
class PatchApplyCheckResult(TypedDict):
    patch_parse_ok: bool                        # False when input caps trip or parse fails
    applies: bool                               # True iff hunks_failed == 0
    hunks_total: int                            # flattened hunk count across all files
    hunks_applied: int                          # successes (applied sequentially, mutating current_lines)
    hunks_failed: int                           # failures
    failed_hunks: list[FailedHunk]              # one entry per failure, in hunk order
    affected_line_ranges: list[dict[str, int]]  # per APPLIED hunk: {"start": new_start, "end": new_start+new_count-1}
    newline_style_before: str                   # "CRLF" | "LF" | "mixed" | "none" (of original_text)
    newline_style_after: str                    # same vocabulary (of result or original when no result)
    result_fingerprint: str                     # sha256 hex of result (or "" when return_result_fingerprint=False / on early failure)
    result_text: str | None                     # joined result when return_result_text=True, else None
    findings: list[str]                         # cap/parse/failure notes, e.g. "1 of 1 hunks failed to apply"
```

### PatchSummaryResult (TypedDict)

```python
class PatchSummaryResult(TypedDict):
    files_changed: int                              # len(files)
    hunks_total: int                                # total hunks
    additions: int                                  # body lines starting with '+'
    deletions: int                                  # body lines starting with '-'
    renames_detected: list[dict[str, str]]          # ALWAYS [] — see below
    binary_patch_detected: bool                     # True when "GIT binary patch" in text or "\0" in text
    line_ranges_by_file: dict[str, list[dict[str, int]]]  # file key (new_file or old_file) → [{"start","end"}] per hunk
    findings: list[str]                             # cap/parse/binary notes
```

**Renames:** `renames_detected` is intentionally always empty. `--- a/X` / `+++ b/Y`
headers denote modification source/destination, not renames; true renames need explicit
`rename from`/`rename to` directives which the parser does not surface yet
(see code comment referencing `plans/production_review_2026_07_b.md (B3)`).

## Constants / Limits

```python
MAX_PATCH_LENGTH = 200_000      # enforced by patch_apply_check (both early exits) and patch_summary
MAX_ORIGINAL_LENGTH = 200_000   # enforced by patch_apply_check only
MAX_RESULT_TEXT_LENGTH = 50_000 # DEFINED but NEVER ENFORCED in code (see bug note below)
```

`parse_unified_diff` itself enforces no length cap — bounds live in the two callers.

## Public Functions

### `parse_unified_diff`

```python
def parse_unified_diff(patch_text: str) -> PatchParseResult
```

Splits on `"\n"`; `--- `/`+++ ` lines set pending filenames (`/dev/null` → `""`);
valid `@@ -s[,c] +s[,c] @@` headers open hunks (bare counts default to 1; unparseable
`@@` lines flush a degenerate `PatchFile` entry); all in-hunk lines (including `\ No
newline at end of file` markers and the trailing `""` after a final newline) accumulate
verbatim into `hunk["lines"]`.

Verified examples:

```python
p = "--- a/foo.txt\n+++ b/foo.txt\n@@ -1,3 +1,3 @@\n line1\n-old\n+new\n line3\n"
parse_unified_diff(p)["ok"]                          # → True
parse_unified_diff(p)["files"][0]["old_file"]        # → 'a/foo.txt'
parse_unified_diff(p)["files"][0]["hunks"][0]["old_start"]  # → 1
parse_unified_diff("")                               # → {'ok': False, 'files': [], 'error': 'Empty patch text'}
parse_unified_diff("garbage")
# → {'ok': False, 'files': [], 'error': 'No unified diff headers found (-- a/... / +++ b/... or @@ ... @@)'}
```

**Edge cases:** multi-file patches append one `PatchFile` per `---`/`+++` group at the
end (all share `raw=patch_text`). A patch with headers but zero hunks yields `ok=True`
with `hunks=[]` when filenames are present.

### `patch_apply_check`

```python
def patch_apply_check(
    original_text: str,
    patch_text: str,
    strict: bool = True,
    return_result_fingerprint: bool = True,
    return_result_text: bool = False,
) -> PatchApplyCheckResult
```

Dry-run semantics: hunks apply **sequentially** against a mutating `current_lines`
(`_text_to_lines` strips one trailing `\n`/`\r`, then splits on `\n`). Strict mode
requires exact context match (`' '`/`'-'` body lines vs original slice, same length and
same content after CR-strip); `strict=False` skips the match verification but still
rebuilds lines. `\`-prefixed lines (e.g. `\ No newline...`) are skipped during rebuild.
`affected_line_ranges` uses **new-side** coordinates.

Verified examples:

```python
patch = "--- a/foo.txt\n+++ b/foo.txt\n@@ -1,3 +1,3 @@\n line1\n-old\n+new\n line3\n"
patch_apply_check("line1\nold\nline3\n", patch, return_result_text=True)
# → {'patch_parse_ok': True, 'applies': True, 'hunks_total': 1, 'hunks_applied': 1,
#     'hunks_failed': 0, 'failed_hunks': [], 'affected_line_ranges': [{'start': 1, 'end': 3}],
#     'newline_style_before': 'LF', 'newline_style_after': 'LF',
#     'result_fingerprint': 'a9b761f7...', 'result_text': 'line1\nnew\nline3', 'findings': []}
patch_apply_check("line1\nWRONG\nline3\n", patch, return_result_text=True)["failed_hunks"]
# → [{'hunk_index': 0, 'old_start': 1, 'old_count': 3,
#      'expected_context': ['line1', 'old', 'line3'], 'actual_context': ['line1', 'WRONG', 'line3'],
#      'reason': "Context mismatch at line 2: expected 'old', got 'WRONG'"}]
patch_apply_check("a\n", "not a patch")["findings"]
# → ['Failed to parse patch: No unified diff headers found (-- a/... / +++ b/... or @@ ... @@)']
```

**Edge cases:** over-cap original/patch short-circuit with `patch_parse_ok=False`,
`result_fingerprint=""`, and a `findings` cap note. Zero-hunk (but parseable) patches
return `applies=True` with finding `"No hunks found in patch"`. `result_text=None`
unless `return_result_text=True`; `result_fingerprint=""` when
`return_result_fingerprint=False`.

### `patch_summary`

```python
def patch_summary(patch_text: str) -> PatchSummaryResult
```

Counts `+`/`-` body lines per hunk (after CR-strip; `+++`/`---` headers are not hunk
lines so they never count). File keys prefer `new_file`, falling back to `old_file`.

Verified examples:

```python
patch_summary("--- a/foo.txt\n+++ b/foo.txt\n@@ -1,3 +1,3 @@\n line1\n-old\n+new\n line3\n")
# → {'files_changed': 1, 'hunks_total': 1, 'additions': 1, 'deletions': 1,
#     'renames_detected': [], 'binary_patch_detected': False,
#     'line_ranges_by_file': {'b/foo.txt': [{'start': 1, 'end': 3}]}, 'findings': []}
patch_summary("garbage")["findings"]
# → ['Failed to parse patch: No unified diff headers found (-- a/... / +++ b/... or @@ ... @@)']
patch_summary("--- a/f\n+++ b/f\n@@ -1 +1 @@\n-a\n+b\nGIT binary patch")["binary_patch_detected"]  # → True
```

## Internal Helpers

- `_patch_detect_newline_style(text)` — counts `\r\n` vs bare `\n`: CRLF-only → `"CRLF"`,
  LF-only → `"LF"`, both → `"mixed"`, neither → `"none"`.
- `_parse_hunk_header(line)` — `^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@`; missing counts → 1.
- `_text_to_lines` / `_lines_to_text` — strip-one-trailing-newline split / `"\n".join`.
- `_patch_normalize_line` (`rstrip("\r")`), `_strip_line_prefix` (strip one leading `+`/`-`/` `),
  `_patch_fingerprint` (SHA-256 hex).
- `_apply_hunk(original_lines, hunk, strict)` — strict context verification + rebuild;
  returns `(new_lines | None, error | None)`.

## Dependencies

```
patch.py
    └── stdlib only: hashlib, re, typing (leaf module — no exact/ imports)
```

Stdlib-only; safe for the single-file build.

## Security / DoS Notes

- **Bounded inputs (caller layer):** `patch_apply_check` rejects `len(original_text) >
  200_000` and `len(patch_text) > 200_000`; `patch_summary` rejects `len(patch_text) >
  200_000`. Both return data (never raise) on cap trips. `parse_unified_diff` has no cap —
  always route untrusted patches through the capped entry points.
- **Unenforced constant (bug):** `MAX_RESULT_TEXT_LENGTH = 50_000` is defined but never
  referenced — `return_result_text=True` returns the full joined result regardless of
  size. Callers must truncate `result_text` themselves before rendering.
- Patch application is in-memory only (no file writes, no symlink/hardlink following);
  `affected_line_ranges`/`failed_hunks[].actual_context` echo source lines — truncate
  before display for hostile inputs.
- Binary sniffing is a substring/`\0` heuristic (`"GIT binary patch" in text`), not a
  content guarantee — treat `binary_patch_detected=False` as advisory.

## See Also

- [diff_analysis.md](diff_analysis.md) — structural analysis of unified diffs (shares `MAX_PATCH_LENGTH`)
- [diff.md](diff.md) — string diffing algorithms (`levenshtein_distance`)
- [position.md](position.md) — line/column vocabulary used by `affected_line_ranges`

## Usage Example

```python
from eggcalc.exact.patch import parse_unified_diff, patch_apply_check, patch_summary

patch = "--- a/foo.txt\n+++ b/foo.txt\n@@ -1,3 +1,3 @@\n line1\n-old\n+new\n line3\n"
print(parse_unified_diff(patch)["ok"])                    # True
print(patch_summary(patch)["additions"])                  # 1

check = patch_apply_check("line1\nold\nline3\n", patch, return_result_text=True)
print(check["applies"])        # True
print(check["result_text"])    # 'line1\nnew\nline3'
print(check["result_fingerprint"][:8])  # deterministic SHA-256 prefix
```

(End of file - total 638 lines implementation)
