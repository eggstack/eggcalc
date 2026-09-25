# markdown.py — Markdown Structure Analysis

642 lines. Regex-based Markdown structure parsing and code fence extraction.

## Table of Contents

- [Overview](#overview)
- [Type Definitions](#type-definitions)
- [Constants / Limits](#constants--limits)
- [Public Functions](#public-functions)
  - [markdown_structure](#markdown_structure)
  - [code_fence_extract](#code_fence_extract)
  - [markdown_link_check_lexical](#markdown_link_check_lexical)
- [Internal Helpers](#internal-helpers)
- [Dependencies](#dependencies)
- [Security Notes](#security-notes)
- [See Also](#see-also)

## Overview

Deterministic line-scanner toolkit for Markdown — **not** a CommonMark
parser. Nested constructs and inline-parsing edge cases are out of scope.
Three entry points:

- `markdown_structure()` — headings, code fences, links, HTML comments,
  frontmatter, table detection in one pass.
- `code_fence_extract()` — fenced code blocks with exact 1-based line
  ranges and SHA-256 fingerprints; unclosed fences reported, never raised.
- `markdown_link_check_lexical()` — lexical link hygiene (malformed links,
  duplicate `#anchors`, unresolved relative paths) with zero filesystem
  or network access.

## Type Definitions

```python
class MarkdownHeading(TypedDict):
    level: int   # 1..6
    text: str    # Heading text, closing #'s stripped
    line: int    # 1-based line number
    slug: str    # GitHub-style anchor slug

class MarkdownCodeFence(TypedDict):
    language: str
    start_line: int
    end_line: int | None   # None when unclosed
    closed: bool

class MarkdownLink(TypedDict):
    visible_text: str
    target: str
    line: int              # 1-based
    mismatch_flags: list[str]

class MarkdownFrontmatter(TypedDict):
    present: bool
    format: str            # "yaml" | "toml" | "json" | "unknown"
    line_start: int | None
    line_end: int | None

class MarkdownStructureResult(TypedDict):
    headings: list[MarkdownHeading]
    code_fences: list[MarkdownCodeFence]
    links: list[MarkdownLink]
    html_comments: list[dict]
    frontmatter: MarkdownFrontmatter
    tables_detected: bool
    findings: list[str]

class CodeFenceBlock(TypedDict):
    index: int             # 0-based block ordinal
    language: str
    start_line: int
    end_line: int | None   # None when unclosed
    closed: bool
    content: str | None    # None when include_content=False
    fingerprint: str       # SHA-256 hex of content

class CodeFenceExtractResult(TypedDict):
    blocks: list[CodeFenceBlock]
    unclosed_fences: list[dict]  # {"index","language","start_line",
                                 #  "end_line": None, "content_preview" (≤200 chars),
                                 #  "fingerprint"}
    findings: list[str]

class MalformedLink(TypedDict, total=False):
    line: int
    text: str
    reason: str

class DuplicateAnchor(TypedDict, total=False):
    anchor: str
    lines: list[int]

class UnresolvedRelative(TypedDict, total=False):
    line: int
    target: str

class MarkdownLinkCheckResult(TypedDict, total=False):
    total_links: int
    malformed: list[MalformedLink]
    duplicate_anchors: list[DuplicateAnchor]
    unresolved_relatives: list[UnresolvedRelative]
    external_count: int
    image_count: int
```

## Constants / Limits

```python
_MAX_LINK_CHECK_INPUT = 500_000   # markdown_link_check_lexical cap

_HEADING_RE          # ^(#{1,6})\s+(.+?)(?:\s+#+)?\s*$
_CODE_FENCE_RE       # ^(`{3,}|~{3,})(.*)$  — backtick or tilde fences
_LINK_RE             # \[([^\]]*)\]\(([^)]+)\)
_HTML_COMMENT_RE     # <!--.*?-->
_TABLE_SEPARATOR_RE  # ^\|?\s*[-:]+[-| :]*$
_INLINE_LINK_RE      # !?\[([^\]]*)\]\(([^)]*)\)
_REFERENCE_LINK_RE   # !?\[([^\]]*)\]\[([^\]]*)\]
_REFERENCE_DEF_RE    # ^\[([^\]]+)\]:\s+(\S+)  (MULTILINE)
_HEADING_FOR_ANCHOR_RE
```

Content previews for unclosed fences are capped at 200 chars. No explicit
input cap on `markdown_structure` / `code_fence_extract` (linear scan).

## Public Functions

### `markdown_structure`

```python
def markdown_structure(
    text: str,
    include_sections: bool = True,
    include_links: bool = True,
    include_code_fences: bool = True,
    include_html_comments: bool = True,
) -> MarkdownStructureResult
```

One-pass line scan returning every structural signal. Toggle groups with
the `include_*` flags.

```python
markdown_structure("# Hello\n\nText with [link](http://example.com)\n")["headings"]
# → [{"level": 1, "text": "Hello", "line": 1, "slug": "hello"}]

markdown_structure("---\ntitle: x\n---\n# H\n")["frontmatter"]
# → {"present": True, "format": "yaml", "line_start": 1, "line_end": 3}
```

### `code_fence_extract`

```python
def code_fence_extract(
    text: str,
    language: str | None = None,
    include_content: bool = True,
) -> CodeFenceExtractResult
```

Extracts fenced blocks. A fence opened with N backticks/tildes closes only
on the same char with length ≥ N. `language` filters case-insensitively.
Unclosed fences appear in **both** `blocks` (`closed=False`,
`end_line=None`) and `unclosed_fences` (with 200-char `content_preview`),
plus a `"Unclosed code fence starting at line N"` finding.

```python
code_fence_extract("```python\nprint(1)\n```\n")["blocks"][0]
# → {"index": 0, "language": "python", "start_line": 1, "end_line": 3,
#     "closed": True, "content": "print(1)",
#     "fingerprint": "d287bb7f9d15abdc5b6e98536263815744b6ef21c8f3c839fc434ca70d8efe99"}

code_fence_extract("```python\nunclosed\n")["unclosed_fences"][0]["end_line"]
# → None
```

### `markdown_link_check_lexical`

```python
def markdown_link_check_lexical(
    text: str,
    known_paths: list[str] | None = None,
) -> MarkdownLinkCheckResult
```

Lexical link hygiene only — no filesystem reads, no HTTP. Counts total /
external / image links; reports malformed targets, duplicate `#anchors`
(from `# Headings`), and relative targets missing from `known_paths`.

```python
markdown_link_check_lexical("[a](#hello) [b](http://x.com) ![](img.png)\n# Hello\n")
# → {"total_links": 3, "malformed": [], "duplicate_anchors": [],
#     "unresolved_relatives": [], "external_count": 1, "image_count": 1}
```

## Internal Helpers

| Helper | Role |
|--------|------|
| `_make_slug(text)` | GitHub-style slug: lowercase, strip punctuation, spaces→`-`, collapse dashes |
| `_make_anchor(text)` | Heading→`#anchor` derivation for duplicate-anchor checks |
| `_markdown_fingerprint(content)` | `hashlib.sha256(content.encode("utf-8")).hexdigest()` |

## Dependencies

```
markdown.py
    └── (standard library only: hashlib, re, typing)
```

No `exact/` imports — fully standalone leaf.

## Security Notes

- Output is lexical, not rendered: a link the scanner reports may render
  differently in a full CommonMark engine (nested brackets, titles,
  reference definitions spanning lines). Treat mismatch flags as leads.
- Fingerprints are SHA-256 over raw block bytes — stable and suitable for
  dedupe, but they fingerprint *content*, not provenance.
- `markdown_link_check_lexical` never fetches URLs and never touches the
  filesystem; `known_paths` is a caller-supplied allowlist, so path
  confusion (case, `..`, encoding) must be normalized by the caller.

## See Also

- [inspect_prompt.md](inspect_prompt.md) — markdown-link red flags in untrusted input
- [transform.md](transform.md) — escaping (incl. markdown) and hashing
- [diff_analysis.md](diff_analysis.md) — structural diff inspection, same line-scan style
