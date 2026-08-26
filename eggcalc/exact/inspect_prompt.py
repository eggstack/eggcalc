"""
Deterministic prompt/input inspection for humans and agents.

Surfaces red flags in text that may influence agents or humans unexpectedly.
Does NOT infer intent. Reports observable features only.

Checks include:
- Unicode hidden characters (zero-width, bidi, variation selectors)
- Bidirectional control characters
- HTML comments (which may hide instructions)
- Markdown link text/target mismatches
- ANSI escape sequences
- Terminal control sequences
- Base64-like blobs
- Instruction-like phrases
- Very long minified lines
"""

from __future__ import annotations

import functools
import re
import unicodedata
from typing import Any, TypedDict

from .primitives import find_invisibles as _find_invisibles

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_TEXT_LENGTH = 100_000
MAX_FINDINGS = 1_000

ALL_CHECKS = frozenset(
    {
        "unicode_hidden",
        "bidi",
        "html_comments",
        "markdown_links",
        "ansi_escapes",
        "terminal_controls",
        "base64_like_blobs",
        "instruction_phrases",
        "long_minified_lines",
    }
)

DEFAULT_CHECKS = frozenset(ALL_CHECKS)

# Severity weights for risk score
_SEVERITY_WEIGHTS = {
    "info": 1,
    "warn": 3,
    "error": 5,
}

# Default instruction phrases (case-insensitive)
DEFAULT_INSTRUCTION_PHRASES = [
    "ignore previous",
    "ignore all previous",
    "disregard previous",
    "disregard all previous",
    "forget everything",
    "new instructions",
    "override instructions",
    "system prompt",
    "you are now",
    "act as",
    "pretend you are",
    "roleplay as",
    "do not follow",
    "ignore the above",
    "ignore the following",
    "disregard the above",
    "disregard the following",
    "override safety",
    "bypass safety",
    "jailbreak",
    "do anything now",
    " DAN",
]

# Regex patterns
_ANSI_ESCAPE_RE = re.compile(
    r"\x1b\["  # ESC [
    r"[0-9;]*"  # parameters
    r"[A-Za-z]"  # final byte
)

_ANSI_OSC_RE = re.compile(
    r"\x1b\]"  # ESC ]
    r".*?"  # any content
    r"(?:\x07|\x1b\\)",  # ST (BEL or ESC \)
)

# Terminal control sequences (C1 controls, CSI sequences)
_TERMINAL_CONTROL_RE = re.compile(
    r"[\x00-\x08\x0e-\x1f\x7f]"  # C0 + DEL + some C1
    r"|"
    r"\x1b[()][AB012]"  # charset selection
    r"|"
    r"\x1b[=>78]"  # cursor keys, etc.
)

# Base64-like blob detection: 64+ chars of [A-Za-z0-9+/=] with no whitespace
_BASE64_LIKE_RE = re.compile(
    r"(?:[A-Za-z0-9+/]{4}){16,}"  # at least 64 base64 chars
    r"(?:[A-Za-z0-9+/]{0,3})?"
    r"(?:=){0,2}"
)

# Markdown link: [text](url)
_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]{1,2000})\]\(([^)]{1,2000})\)")

# HTML comment: <!-- ... -->
_HTML_COMMENT_CONTENT_RE = re.compile(
    r"<!--(.*?)-->",
    re.DOTALL,
)


class PromptInspectionFinding(TypedDict, total=False):
    """A single finding from prompt inspection."""

    code: str
    severity: str  # "info" | "warn" | "error"
    message: str
    span: dict[str, int]  # char_start, char_end
    details: dict[str, Any]


class PromptInspectionResult(TypedDict, total=False):
    """Result of prompt/input inspection."""

    findings: list[PromptInspectionFinding]
    summary: str
    risk_score: int
    recommended_next_tool: str | list[str] | None
    text_length: int
    checks_run: list[str]
    findings_truncated: bool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@functools.lru_cache(maxsize=64)
def _build_instruction_regex(phrase_patterns: tuple[str, ...] | None) -> re.Pattern[str]:
    """Build a combined regex for instruction phrases.

    Empty or whitespace-only patterns are filtered out. If no patterns
    remain, returns a never-match regex.
    """
    phrases = list(phrase_patterns) if phrase_patterns else DEFAULT_INSTRUCTION_PHRASES
    phrases = [p for p in phrases if p]
    if not phrases:
        return re.compile(r"(?!)")
    escaped = [re.escape(p) for p in phrases]
    combined = "|".join(escaped)
    return re.compile(combined, re.IGNORECASE)


def _get_instruction_re(phrase_patterns: list[str] | None = None) -> re.Pattern[str]:
    """Get or build the instruction regex.

    The result is cached per tuple of patterns.
    """
    if phrase_patterns is None:
        return _build_instruction_regex(None)
    return _build_instruction_regex(tuple(phrase_patterns))


def _char_span(index: int, length: int = 1) -> dict[str, int]:
    """Create a span dict from a char index."""
    return {"char_start": index, "char_end": index + length}


def _find_bidi_controls(text: str) -> list[PromptInspectionFinding]:
    """Find bidirectional control characters."""
    findings: list[PromptInspectionFinding] = []
    bidi_names = {
        0x202A: "LEFT-TO-RIGHT EMBEDDING (LRE)",
        0x202B: "RIGHT-TO-LEFT EMBEDDING (RLE)",
        0x202C: "POP DIRECTIONAL FORMATTING (PDF)",
        0x202D: "LEFT-TO-RIGHT OVERRIDE (LRO)",
        0x202E: "RIGHT-TO-LEFT OVERRIDE (RLO)",
        0x2066: "LEFT-TO-RIGHT ISOLATE (LRI)",
        0x2067: "RIGHT-TO-LEFT ISOLATE (RLI)",
        0x2068: "FIRST STRONG ISOLATE (FSI)",
        0x2069: "POP DIRECTIONAL ISOLATE (PDI)",
        0x200E: "LEFT-TO-RIGHT MARK (LRM)",
        0x200F: "RIGHT-TO-LEFT MARK (RLM)",
    }
    for index, char in enumerate(text):
        cp = ord(char)
        if cp in bidi_names:
            findings.append(
                PromptInspectionFinding(
                    code="BIDI_CONTROL",
                    severity="warn",
                    message=f"Bidi control character: {bidi_names[cp]} at position {index}",
                    span=_char_span(index),
                    details={"codepoint": f"U+{cp:04X}", "name": bidi_names[cp]},
                )
            )
    return findings


def _find_unicode_hidden(text: str) -> list[PromptInspectionFinding]:
    """Find hidden Unicode characters using find_invisibles."""
    findings: list[PromptInspectionFinding] = []
    invisibles = _find_invisibles(text)
    for inv in invisibles:
        severity = "warn"
        # Zero-width characters are more suspicious — commonly used for
        # prompt injection to hide instructions from human reviewers
        if inv["codepoint"] in ("U+200B", "U+200C", "U+200D", "U+2060", "U+FEFF"):
            severity = "error"
        findings.append(
            PromptInspectionFinding(
                code="HIDDEN_CHAR",
                severity=severity,
                message=f"Hidden character: {inv['name']} ({inv['codepoint']}) at position {inv['index']}",
                span=_char_span(inv["index"]),
                details={
                    "codepoint": inv["codepoint"],
                    "name": inv["name"],
                    "category": inv["category"],
                    "display": inv["display"],
                },
            )
        )
    return findings


def _find_html_comments(text: str) -> list[PromptInspectionFinding]:
    """Find HTML comments which may hide instructions."""
    findings: list[PromptInspectionFinding] = []
    for match in _HTML_COMMENT_CONTENT_RE.finditer(text):
        content = match.group(1).strip()
        severity = "warn" if content else "info"
        message = f"HTML comment at position {match.start()}"
        if content:
            message += f": {content[:100]}{'...' if len(content) > 100 else ''}"
        findings.append(
            PromptInspectionFinding(
                code="HTML_COMMENT",
                severity=severity,
                message=message,
                span={"char_start": match.start(), "char_end": match.end()},
                details={"content": content[:500]},
            )
        )
    return findings


def _find_markdown_links(text: str) -> list[PromptInspectionFinding]:
    """Find Markdown links where display text and target may mismatch."""
    findings: list[PromptInspectionFinding] = []
    for match in _MARKDOWN_LINK_RE.finditer(text):
        link_text = match.group(1)
        link_target = match.group(2)
        severity = "info"
        details: dict[str, Any] = {"text": link_text, "target": link_target}

        # Flag if target is a URL but text doesn't look like a URL description
        if link_target.startswith(("http://", "https://", "ftp://")):
            # Check if text looks like it's trying to be a different URL
            if re.search(r"https?://", link_text):
                severity = "warn"
                details["mismatch"] = "text contains URL while target is also a URL"
        # Flag data URIs
        if link_target.startswith("data:"):
            severity = "warn"
            details["mismatch"] = "data URI target"

        findings.append(
            PromptInspectionFinding(
                code="MARKDOWN_LINK",
                severity=severity,
                message=f"Markdown link at position {match.start()}: [{link_text[:50]}]({link_target[:80]})",
                span={"char_start": match.start(), "char_end": match.end()},
                details=details,
            )
        )
    return findings


def _find_ansi_escapes(text: str) -> list[PromptInspectionFinding]:
    """Find ANSI escape sequences."""
    findings: list[PromptInspectionFinding] = []
    for match in _ANSI_ESCAPE_RE.finditer(text):
        findings.append(
            PromptInspectionFinding(
                code="ANSI_ESCAPE",
                severity="warn",
                message=f"ANSI escape sequence at position {match.start()}",
                span={"char_start": match.start(), "char_end": match.end()},
                details={"sequence": repr(match.group())},
            )
        )
    return findings


def _find_terminal_controls(text: str) -> list[PromptInspectionFinding]:
    """Find terminal control sequences."""
    findings: list[PromptInspectionFinding] = []
    for match in _TERMINAL_CONTROL_RE.finditer(text):
        char = match.group()
        cp = f"U+{ord(char):04X}"
        name = unicodedata.name(char, "CONTROL")
        findings.append(
            PromptInspectionFinding(
                code="TERMINAL_CONTROL",
                severity="info",
                message=f"Terminal control character {name} ({cp}) at position {match.start()}",
                span={"char_start": match.start(), "char_end": match.end()},
                details={"codepoint": cp, "name": name},
            )
        )
    return findings


def _find_base64_blobs(text: str) -> list[PromptInspectionFinding]:
    """Find base64-like blobs that may encode hidden content."""
    findings: list[PromptInspectionFinding] = []
    for match in _BASE64_LIKE_RE.finditer(text):
        blob = match.group()
        # Skip if it's just a common identifier or hex string
        if len(blob) < 64:
            continue
        # Check it has mixed case + digits (typical base64)
        has_upper = any(c.isupper() for c in blob)
        has_lower = any(c.islower() for c in blob)
        has_digit = any(c.isdigit() for c in blob)
        if has_upper and has_lower and has_digit:
            findings.append(
                PromptInspectionFinding(
                    code="BASE64_BLOB",
                    severity="warn",
                    message=f"Base64-like blob ({len(blob)} chars) at position {match.start()}",
                    span={"char_start": match.start(), "char_end": match.end()},
                    details={"length": len(blob), "preview": blob[:100]},
                )
            )
    return findings


def _find_instruction_phrases(
    text: str,
    phrase_patterns: list[str] | None = None,
) -> list[PromptInspectionFinding]:
    """Find instruction-like phrases that could manipulate agents.

    Note: phrase_patterns are treated as literal strings (escaped with re.escape),
    not as regex patterns. This prevents ReDoS from user-supplied patterns.
    """
    findings: list[PromptInspectionFinding] = []
    if phrase_patterns:
        # Defense-in-depth: reject overly long individual patterns
        for p in phrase_patterns:
            if len(p) > 1000:
                continue
    regex = _get_instruction_re(phrase_patterns)
    for match in regex.finditer(text):
        matched = match.group()
        findings.append(
            PromptInspectionFinding(
                code="INSTRUCTION_PHRASE",
                severity="warn",
                message=f"Instruction-like phrase at position {match.start()}: '{matched}'",
                span={"char_start": match.start(), "char_end": match.end()},
                details={"phrase": matched},
            )
        )
    return findings


def _find_long_minified_lines(text: str) -> list[PromptInspectionFinding]:
    """Find very long lines that may be minified or obfuscated."""
    findings: list[PromptInspectionFinding] = []
    lines = text.split("\n")
    offset = 0
    for line in lines:
        if len(line) > 1000:
            findings.append(
                PromptInspectionFinding(
                    code="LONG_LINE",
                    severity="info",
                    message=f"Very long line ({len(line)} chars) at position {offset}",
                    span={"char_start": offset, "char_end": offset + len(line)},
                    details={"length": len(line)},
                )
            )
        offset += len(line) + 1  # +1 for \n
    return findings


def _compute_risk_score(findings: list[PromptInspectionFinding]) -> int:
    """Compute a deterministic risk score from findings."""
    score = 0
    for f in findings:
        score += _SEVERITY_WEIGHTS.get(f.get("severity", "info"), 1)
    return score


def _build_summary(findings: list[PromptInspectionFinding], risk_score: int) -> str:
    """Build a human-readable summary."""
    if not findings:
        return "No red flags detected in the input text."

    codes: dict[str, int] = {}
    for f in findings:
        code = f.get("code", "UNKNOWN")
        codes[code] = codes.get(code, 0) + 1

    parts = [f"{count} {code}" for code, count in sorted(codes.items())]
    severity_counts: dict[str, int] = {}
    for f in findings:
        sev = f.get("severity", "info")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    sev_parts = []
    for sev in ("error", "warn", "info"):
        if sev in severity_counts:
            sev_parts.append(f"{severity_counts[sev]} {sev}")

    return (
        f"{len(findings)} finding(s): {', '.join(parts)}. "
        f"Severity: {', '.join(sev_parts)}. "
        f"Risk score: {risk_score}."
    )


def _recommend_next_tool(findings: list[PromptInspectionFinding]) -> str | list[str] | None:
    """Recommend follow-up tools based on findings."""
    if not findings:
        return None

    codes = {f.get("code") for f in findings}
    recommendations: list[str] = []

    if "HIDDEN_CHAR" in codes or "BIDI_CONTROL" in codes:
        recommendations.append("text_inspect")
    if "ANSI_ESCAPE" in codes or "TERMINAL_CONTROL" in codes:
        recommendations.append("text_transform")
    if "BASE64_BLOB" in codes:
        recommendations.append("text_inspect")
    if "HTML_COMMENT" in codes or "MARKDOWN_LINK" in codes:
        recommendations.append("markdown_structure")
    if "INSTRUCTION_PHRASE" in codes:
        recommendations.append("text_inspect")

    if not recommendations:
        return None
    if len(recommendations) == 1:
        return recommendations[0]
    return recommendations


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------


def prompt_input_inspect(
    text: str,
    checks: list[str] | None = None,
    phrase_patterns: list[str] | None = None,
) -> PromptInspectionResult:
    """Inspect text for deterministic red flags.

    Surfaces observable features that may influence agents or humans
    unexpectedly. Does NOT infer intent or detect prompt injection
    semantically.

    Args:
        text: The text to inspect.
        checks: Subset of check names to run. None runs all checks.
        phrase_patterns: Optional literal strings or safe regexes to detect
                        as instruction-like phrases.

    Returns:
        PromptInspectionResult with findings, summary, risk_score, and
        recommended_next_tool.

    Raises:
        ValueError: If text exceeds MAX_TEXT_LENGTH or checks are invalid.
    """
    if len(text) > MAX_TEXT_LENGTH:
        raise ValueError(f"Input length {len(text)} exceeds MAX_TEXT_LENGTH {MAX_TEXT_LENGTH}")

    active_checks = set(checks) if checks is not None else set(ALL_CHECKS)
    invalid = active_checks - ALL_CHECKS
    if invalid:
        raise ValueError(
            f"Unknown check(s): {', '.join(sorted(invalid))}. "
            f"Valid checks: {', '.join(sorted(ALL_CHECKS))}"
        )

    findings: list[PromptInspectionFinding] = []

    if "unicode_hidden" in active_checks:
        findings.extend(_find_unicode_hidden(text))
    if "bidi" in active_checks:
        findings.extend(_find_bidi_controls(text))
    if "html_comments" in active_checks:
        findings.extend(_find_html_comments(text))
    if "markdown_links" in active_checks:
        findings.extend(_find_markdown_links(text))
    if "ansi_escapes" in active_checks:
        findings.extend(_find_ansi_escapes(text))
    if "terminal_controls" in active_checks:
        findings.extend(_find_terminal_controls(text))
    if "base64_like_blobs" in active_checks:
        findings.extend(_find_base64_blobs(text))
    if "instruction_phrases" in active_checks:
        findings.extend(_find_instruction_phrases(text, phrase_patterns))
    if "long_minified_lines" in active_checks:
        findings.extend(_find_long_minified_lines(text))

    # Deduplicate findings by (position, codepoint) to avoid double-counting
    # bidi characters that appear in both unicode_hidden and bidi checks
    seen: set[tuple[int, str]] = set()
    deduped: list[PromptInspectionFinding] = []
    for f in findings:
        span = f.get("span", {})
        pos = span.get("char_start", -1)
        codepoint = f.get("details", {}).get("codepoint", f.get("code", "UNKNOWN"))
        key = (pos, codepoint)
        if key not in seen:
            seen.add(key)
            deduped.append(f)
    findings = deduped

    findings_truncated = False
    if len(findings) > MAX_FINDINGS:
        # Sort by severity (errors first, then warnings, then info) before truncating
        # so high-severity findings are not dropped when low-severity findings fill the limit
        severity_order = {"error": 0, "warn": 1, "info": 2}
        findings.sort(key=lambda f: severity_order.get(f.get("severity", "info"), 2))
        findings = findings[:MAX_FINDINGS]
        findings_truncated = True

    risk_score = _compute_risk_score(findings)
    summary = _build_summary(findings, risk_score)
    recommended = _recommend_next_tool(findings)

    return PromptInspectionResult(
        findings=findings,
        summary=summary,
        risk_score=risk_score,
        recommended_next_tool=recommended,
        text_length=len(text),
        checks_run=sorted(active_checks),
        findings_truncated=findings_truncated,
    )
