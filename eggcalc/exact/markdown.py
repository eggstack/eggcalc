"""
Markdown structure analysis and code fence extraction.

Provides deterministic line scanners for:
- Document structure (headings, code fences, links, HTML comments, frontmatter)
- Fenced code block extraction with exact line ranges and fingerprints

These are NOT full CommonMark parsers; they use regex-based line scanning
as documented. Edge cases around nesting and inline parsing are out of scope.
"""

from __future__ import annotations

import hashlib
import re
from typing import TypedDict


class MarkdownHeading(TypedDict):
    """A heading found in Markdown text."""

    level: int
    text: str
    line: int
    slug: str


class MarkdownCodeFence(TypedDict):
    """A code fence found in Markdown text."""

    language: str
    start_line: int
    end_line: int | None
    closed: bool


class MarkdownLink(TypedDict):
    """A Markdown link found in text."""

    visible_text: str
    target: str
    line: int
    mismatch_flags: list[str]


class MarkdownFrontmatter(TypedDict):
    """Frontmatter detection result."""

    present: bool
    format: str
    line_start: int | None
    line_end: int | None


class MarkdownStructureResult(TypedDict):
    """Result of markdown_structure analysis."""

    headings: list[MarkdownHeading]
    code_fences: list[MarkdownCodeFence]
    links: list[MarkdownLink]
    html_comments: list[dict]
    frontmatter: MarkdownFrontmatter
    tables_detected: bool
    findings: list[str]


class CodeFenceBlock(TypedDict):
    """A fenced code block from code_fence_extract."""

    index: int
    language: str
    start_line: int
    end_line: int | None
    closed: bool
    content: str | None
    fingerprint: str


class CodeFenceExtractResult(TypedDict):
    """Result of code_fence_extract analysis."""

    blocks: list[CodeFenceBlock]
    unclosed_fences: list[dict]
    findings: list[str]


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)(?:\s+#+)?\s*$")
_CODE_FENCE_RE = re.compile(r"^(`{3,}|~{3,})(.*)$")
_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->")
_TABLE_SEPARATOR_RE = re.compile(r"^\|?\s*[-:]+[-| :]*$")


def _make_slug(text: str) -> str:
    """Create a GitHub-style heading slug from heading text."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")


def markdown_structure(
    text: str,
    include_sections: bool = True,
    include_links: bool = True,
    include_code_fences: bool = True,
    include_html_comments: bool = True,
) -> MarkdownStructureResult:
    """Parse Markdown structure using a deterministic line scanner.

    This is NOT a full CommonMark parser. It uses regex-based line scanning
    for headings, code fences, links, HTML comments, and frontmatter.
    Nested constructs and inline parsing edge cases are out of scope.

    Args:
        text: Markdown text to analyze.
        include_sections: Include heading detection (default true).
        include_links: Include link detection (default true).
        include_code_fences: Include code fence detection (default true).
        include_html_comments: Include HTML comment detection (default true).

    Returns:
        MarkdownStructureResult with headings, code_fences, links,
        html_comments, frontmatter, tables_detected, and findings.
    """
    lines = text.split("\n")
    headings: list[MarkdownHeading] = []
    code_fences: list[MarkdownCodeFence] = []
    links: list[MarkdownLink] = []
    html_comments: list[dict] = []
    findings: list[str] = []

    # Frontmatter detection
    frontmatter: MarkdownFrontmatter = {
        "present": False,
        "format": "unknown",
        "line_start": None,
        "line_end": None,
    }

    # Tables detection
    tables_detected = False

    # Code fence state
    in_fence = False
    fence_char = ""
    fence_len = 0
    fence_start_line = 0
    fence_lang = ""

    in_frontmatter = False

    for i, line in enumerate(lines):
        line_num = i + 1

        # Frontmatter detection (must be at line 1)
        if i == 0:
            stripped = line.strip()
            if stripped == "---":
                in_frontmatter = True
                frontmatter["present"] = True
                frontmatter["format"] = "yaml"
                frontmatter["line_start"] = line_num
                continue
            elif stripped == "+++":
                in_frontmatter = True
                frontmatter["present"] = True
                frontmatter["format"] = "toml"
                frontmatter["line_start"] = line_num
                continue

        # Frontmatter end detection
        if in_frontmatter:
            stripped = line.strip()
            if stripped == "---" and frontmatter["format"] == "yaml":
                frontmatter["line_end"] = line_num
                in_frontmatter = False
                continue
            elif stripped == "+++" and frontmatter["format"] == "toml":
                frontmatter["line_end"] = line_num
                in_frontmatter = False
                continue
            continue

        # Code fence detection
        if include_code_fences:
            fence_match = _CODE_FENCE_RE.match(line.strip())
            if fence_match:
                fence_opener = fence_match.group(1)
                lang = fence_match.group(2).strip()
                current_fence_char = fence_opener[0]
                current_fence_len = len(fence_opener)

                if not in_fence:
                    in_fence = True
                    fence_char = current_fence_char
                    fence_len = current_fence_len
                    fence_start_line = line_num
                    fence_lang = lang
                elif current_fence_char == fence_char and current_fence_len >= fence_len:
                    # Closing fence
                    code_fences.append(
                        MarkdownCodeFence(
                            language=fence_lang,
                            start_line=fence_start_line,
                            end_line=line_num,
                            closed=True,
                        )
                    )
                    in_fence = False
                continue

        # Heading detection (only outside code fences)
        if include_sections and not in_fence:
            heading_match = _HEADING_RE.match(line.strip())
            if heading_match:
                level = len(heading_match.group(1))
                text_content = heading_match.group(2).strip()
                headings.append(
                    MarkdownHeading(
                        level=level,
                        text=text_content,
                        line=line_num,
                        slug=_make_slug(text_content),
                    )
                )

        # Link detection (only outside code fences)
        if include_links and not in_fence:
            for link_match in _LINK_RE.finditer(line):
                visible = link_match.group(1)
                target = link_match.group(2)
                mismatch_flags: list[str] = []

                # Detect common mismatch patterns
                if visible.startswith("http://") or visible.startswith("https://"):
                    if visible != target:
                        mismatch_flags.append("visible_is_url")

                if re.match(r"^[\w.-]+\.[\w]{2,}$", visible):
                    if visible != target:
                        mismatch_flags.append("visible_is_domain")

                links.append(
                    MarkdownLink(
                        visible_text=visible,
                        target=target,
                        line=line_num,
                        mismatch_flags=mismatch_flags,
                    )
                )

        # HTML comment detection
        if include_html_comments and not in_fence:
            for comment_match in _HTML_COMMENT_RE.finditer(line):
                comment_text = comment_match.group(0)
                html_comments.append(
                    {
                        "text": comment_text,
                        "line": line_num,
                        "start_col": comment_match.start() + 1,
                        "end_col": comment_match.end() + 1,
                    }
                )

        # Table detection (only outside code fences)
        if not tables_detected and not in_fence:
            if _TABLE_SEPARATOR_RE.match(line.strip()):
                # Check if the previous non-empty line has pipe characters
                for j in range(i - 1, -1, -1):
                    prev = lines[j].strip()
                    if prev:
                        if "|" in prev:
                            tables_detected = True
                        break

    # Handle unclosed code fence
    if in_fence:
        code_fences.append(
            MarkdownCodeFence(
                language=fence_lang,
                start_line=fence_start_line,
                end_line=None,
                closed=False,
            )
        )
        findings.append(f"Unclosed code fence starting at line {fence_start_line}")

    # Handle unclosed frontmatter
    if in_frontmatter:
        findings.append("Unclosed frontmatter block")

    return MarkdownStructureResult(
        headings=headings,
        code_fences=code_fences,
        links=links,
        html_comments=html_comments,
        frontmatter=frontmatter,
        tables_detected=tables_detected,
        findings=findings,
    )


def _markdown_fingerprint(content: str) -> str:
    """Compute SHA-256 fingerprint of content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def code_fence_extract(
    text: str,
    language: str | None = None,
    include_content: bool = True,
) -> CodeFenceExtractResult:
    """Extract fenced code blocks with exact line ranges and fingerprints.

    Uses a deterministic line scanner. Does not handle nested fences or
    inline code that might look like fences.

    Args:
        text: Markdown text to scan.
        language: Optional language filter (case-insensitive).
        include_content: Include block content in output (default true, capped).

    Returns:
        CodeFenceExtractResult with blocks, unclosed_fences, and findings.
    """
    lines = text.split("\n")
    blocks: list[CodeFenceBlock] = []
    unclosed_fences: list[dict] = []
    findings: list[str] = []
    index = 0

    in_fence = False
    fence_char = ""
    fence_len = 0
    fence_start_line = 0
    fence_lang = ""
    fence_content_lines: list[str] = []

    for i, line in enumerate(lines):
        line_num = i + 1
        fence_match = _CODE_FENCE_RE.match(line.strip())

        if fence_match:
            fence_opener = fence_match.group(1)
            lang = fence_match.group(2).strip()
            current_fence_char = fence_opener[0]
            current_fence_len = len(fence_opener)

            if not in_fence:
                in_fence = True
                fence_char = current_fence_char
                fence_len = current_fence_len
                fence_start_line = line_num
                fence_lang = lang
                fence_content_lines = []
                continue
            elif current_fence_char == fence_char and current_fence_len >= fence_len:
                # Closing fence
                content_text = "\n".join(fence_content_lines)
                fp = _markdown_fingerprint(content_text)

                # Apply language filter
                if language is None or fence_lang.lower() == language.lower():
                    blocks.append(
                        CodeFenceBlock(
                            index=index,
                            language=fence_lang,
                            start_line=fence_start_line,
                            end_line=line_num,
                            closed=True,
                            content=content_text if include_content else None,
                            fingerprint=fp,
                        )
                    )
                    index += 1

                in_fence = False
                continue

        if in_fence:
            fence_content_lines.append(line)

    # Handle unclosed fences
    if in_fence:
        content_text = "\n".join(fence_content_lines)
        fp = _markdown_fingerprint(content_text)

        unclosed_fences.append(
            {
                "index": index,
                "language": fence_lang,
                "start_line": fence_start_line,
                "end_line": None,
                "content_preview": content_text[:200],
                "fingerprint": fp,
            }
        )

        # Only add to blocks if language filter matches
        if language is None or fence_lang.lower() == language.lower():
            blocks.append(
                CodeFenceBlock(
                    index=index,
                    language=fence_lang,
                    start_line=fence_start_line,
                    end_line=None,
                    closed=False,
                    content=content_text if include_content else None,
                    fingerprint=fp,
                )
            )
            index += 1

        findings.append(f"Unclosed code fence starting at line {fence_start_line}")

    return CodeFenceExtractResult(
        blocks=blocks,
        unclosed_fences=unclosed_fences,
        findings=findings,
    )


# ---------------------------------------------------------------------------
# Markdown link check (lexical, no network)
# ---------------------------------------------------------------------------

_MAX_LINK_CHECK_INPUT = 500_000


class MalformedLink(TypedDict, total=False):
    """A malformed link detected in markdown."""

    line: int
    text: str
    reason: str


class DuplicateAnchor(TypedDict, total=False):
    """A duplicate anchor name from heading links."""

    anchor: str
    lines: list[int]


class UnresolvedRelative(TypedDict, total=False):
    """A relative link that could not be resolved against known paths."""

    line: int
    target: str


class MarkdownLinkCheckResult(TypedDict, total=False):
    """Result of markdown_link_check_lexical analysis."""

    total_links: int
    malformed: list[MalformedLink]
    duplicate_anchors: list[DuplicateAnchor]
    unresolved_relatives: list[UnresolvedRelative]
    external_count: int
    image_count: int


_INLINE_LINK_RE = re.compile(r"!?\[([^\]]*)\]\(([^)]*)\)")
_REFERENCE_LINK_RE = re.compile(r"!?\[([^\]]*)\]\[([^\]]*)\]")
_REFERENCE_DEF_RE = re.compile(r"^\[([^\]]+)\]:\s+(\S+)", re.MULTILINE)
_HEADING_FOR_ANCHOR_RE = re.compile(r"^(#{1,6})\s+(.+?)(?:\s+#+)?\s*$")


def _make_anchor(text: str) -> str:
    """Create a GitHub-style anchor from heading text."""
    anchor = text.lower().strip()
    anchor = re.sub(r"[^\w\s-]", "", anchor)
    anchor = re.sub(r"[\s]+", "-", anchor)
    anchor = re.sub(r"-+", "-", anchor)
    return anchor.strip("-")


def markdown_link_check_lexical(
    text: str,
    known_paths: list[str] | None = None,
) -> MarkdownLinkCheckResult:
    """Lexical markdown link validation (no network).

    Extracts all markdown links and checks for:
    - Malformed link syntax (unclosed brackets, empty URLs)
    - Duplicate anchor names from heading links
    - Unresolved relative links (if known_paths provided)
    - External vs internal link counts
    - Image vs page link counts

    Args:
        text: Markdown text to analyze.
        known_paths: Optional list of known file paths for resolving
            relative links.

    Returns:
        MarkdownLinkCheckResult with analysis details.
    """
    if not isinstance(text, str):
        return MarkdownLinkCheckResult(
            total_links=0,
            malformed=[],
            duplicate_anchors=[],
            unresolved_relatives=[],
            external_count=0,
            image_count=0,
        )

    if len(text) > _MAX_LINK_CHECK_INPUT:
        return MarkdownLinkCheckResult(
            total_links=0,
            malformed=[],
            duplicate_anchors=[],
            unresolved_relatives=[],
            external_count=0,
            image_count=0,
        )

    lines = text.split("\n")
    malformed: list[MalformedLink] = []
    external_count = 0
    image_count = 0
    total_links = 0

    heading_anchors: dict[str, list[int]] = {}
    anchor_links: dict[str, list[int]] = {}
    known_set = set(known_paths) if known_paths else None
    unresolved: list[UnresolvedRelative] = []

    in_fence = False
    fence_char = ""

    for i, line in enumerate(lines):
        line_num = i + 1

        fence_match = _CODE_FENCE_RE.match(line.strip())
        if fence_match:
            opener = fence_match.group(1)
            if not in_fence:
                in_fence = True
                fence_char = opener[0]
            elif opener[0] == fence_char and len(opener) >= 3:
                in_fence = False
            continue

        if in_fence:
            continue

        heading_match = _HEADING_FOR_ANCHOR_RE.match(line.strip())
        if heading_match:
            heading_text = heading_match.group(2).strip()
            anchor = _make_anchor(heading_text)
            heading_anchors.setdefault(anchor, []).append(line_num)

        for m in _INLINE_LINK_RE.finditer(line):
            total_links += 1
            link_text = m.group(1)
            target = m.group(2)
            is_image = line[m.start() : m.start() + 1] == "!"

            if is_image:
                image_count += 1

            if target.startswith("http://") or target.startswith("https://"):
                external_count += 1
                continue

            if target.startswith("#"):
                anchor_name = target[1:]
                anchor_links.setdefault(anchor_name, []).append(line_num)
                continue

            if target.startswith("mailto:"):
                continue

            if not target:
                malformed.append(
                    MalformedLink(
                        line=line_num,
                        text=m.group(0),
                        reason="Empty URL in link",
                    )
                )
                continue

            if known_set is not None and not target.startswith(
                ("http://", "https://", "mailto:", "#")
            ):
                if target not in known_set:
                    unresolved.append(
                        UnresolvedRelative(
                            line=line_num,
                            target=target,
                        )
                    )

        for m in _REFERENCE_LINK_RE.finditer(line):
            total_links += 1
            link_text = m.group(1)
            ref = m.group(2)
            is_image = line[m.start() : m.start() + 1] == "!"

            if is_image:
                image_count += 1

        unclosed_sq = line.count("[") - line.count("]")
        if unclosed_sq > 0 and _INLINE_LINK_RE.search(line) is None:
            if not line.strip().startswith("|"):
                malformed.append(
                    MalformedLink(
                        line=line_num,
                        text=line.strip()[:100],
                        reason="Unclosed bracket (possible malformed link)",
                    )
                )

    duplicate_anchors: list[DuplicateAnchor] = []
    for anchor_name, anchor_lines in anchor_links.items():
        if len(anchor_lines) > 1:
            duplicate_anchors.append(
                DuplicateAnchor(
                    anchor=anchor_name,
                    lines=anchor_lines,
                )
            )

    for anchor_name, heading_lines in heading_anchors.items():
        if len(heading_lines) > 1:
            duplicate_anchors.append(
                DuplicateAnchor(
                    anchor=anchor_name,
                    lines=heading_lines,
                )
            )

    return MarkdownLinkCheckResult(
        total_links=total_links,
        malformed=malformed,
        duplicate_anchors=duplicate_anchors,
        unresolved_relatives=unresolved,
        external_count=external_count,
        image_count=image_count,
    )
