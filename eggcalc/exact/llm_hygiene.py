"""LLM output hygiene tools for detecting common JSON output issues.

Provides deterministic analysis of LLM-generated text to detect:
- Markdown fenced code blocks wrapping JSON
- Leading/trailing prose around JSON content
- JSON parse errors with location info
- Common JSON issues (trailing commas, single quotes, etc.)
- Multiple concatenated JSON objects
"""

from __future__ import annotations

import json
import re
from typing import TypedDict

_MAX_INPUT_LENGTH = 500_000


class JsonFixHint(TypedDict, total=False):
    """A suggested fix for a JSON issue."""

    code: str
    message: str
    line: int
    column: int


class LlmJsonCheckResult(TypedDict, total=False):
    """Result of llm_json_output_check analysis."""

    has_fence: bool
    fence_language: str
    leading_prose: bool
    trailing_prose: bool
    parse_ok: bool
    error_line: int | None
    error_col: int | None
    error_message: str | None
    fix_hints: list[JsonFixHint]
    extracted_content: str | None
    multiple_json_objects: bool
    has_bom: bool
    original_length: int
    extracted_length: int


_FENCE_RE = re.compile(r"^```(\w*)\s*$", re.MULTILINE)
_FENCE_BLOCK_RE = re.compile(r"^```(\w*)\s*\n(.*?)\n\s*```\s*$", re.MULTILINE | re.DOTALL)
_SINGLE_QUOTE_RE = re.compile(r"(?<![\\])'")
_UNQUOTED_KEY_RE = re.compile(r'(?<={|,)\s*(\w+)\s*:', re.MULTILINE)
_TRAILING_COMMA_RE = re.compile(r",\s*([\]}])")
_COMMENT_RE = re.compile(r"(?<!:)//[^\n]*|/\*.*?\*/", re.DOTALL)
_BOM_PREFIX = "\ufeff"
_MULTIPLE_JSON_RE = re.compile(r'(?:\}\s*\{|\]\s*\[|\}\s*\[|\]\s*\{)')


def _count_line_col(text: str, pos: int) -> tuple[int, int]:
    """Convert a string position to 1-based line and column."""
    if pos < 0:
        return 1, 1
    line = text.count("\n", 0, pos) + 1
    last_nl = text.rfind("\n", 0, pos)
    col = pos - last_nl if last_nl >= 0 else pos + 1
    return line, col


def _detect_fence(text: str) -> tuple[bool, str, str | None]:
    """Detect markdown fenced code blocks. Returns (has_fence, language, content)."""
    m = _FENCE_BLOCK_RE.search(text)
    if m:
        lang = m.group(1) or ""
        content = m.group(2)
        return True, lang, content
    return False, "", None


def _detect_prose(text: str) -> tuple[bool, bool]:
    """Detect leading/trailing non-JSON content."""
    stripped = text.strip()
    if not stripped:
        return False, False

    leading = False
    trailing = False

    first_char = stripped[0]
    if first_char not in "{[\"'tfn0123456789-":
        leading = True

    last_char = stripped[-1]
    if last_char not in '}"\'tfn0123456789':
        trailing = True

    return leading, trailing


def _extract_json_from_prose(text: str) -> str:
    """Extract JSON content from text with leading/trailing prose."""
    stripped = text.strip()

    json_start = -1
    for i, ch in enumerate(stripped):
        if ch == "{":
            json_start = i
            break
        if ch == "[":
            json_start = i
            break

    if json_start < 0:
        return stripped

    json_end = len(stripped)
    depth = 0
    in_string = False
    escape = False
    string_char = ""

    for i in range(json_start, len(stripped)):
        ch = stripped[i]
        if escape:
            escape = False
            continue
        if ch == "\\" and in_string:
            escape = True
            continue
        if not in_string:
            if ch in ('"',):
                in_string = True
                string_char = ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    json_end = i + 1
                    break
        else:
            if ch == string_char:
                in_string = False

    return stripped[json_start:json_end]


def _detect_bom(text: str) -> tuple[bool, str]:
    """Detect and strip BOM prefix. Returns (had_bom, stripped_text)."""
    if text.startswith(_BOM_PREFIX):
        return True, text[len(_BOM_PREFIX) :]
    return False, text


def _detect_multiple_objects(content: str) -> bool:
    """Heuristic: detect if multiple JSON objects are concatenated."""
    stripped = content.strip()
    if not stripped:
        return False
    if stripped[0] not in "{[":
        return False
    depth = 0
    in_string = False
    escape = False
    for ch in stripped:
        if escape:
            escape = False
            continue
        if ch == "\\" and in_string:
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
            if depth == 0:
                rest = stripped[stripped.index(ch) + 1 :].strip()
                if rest and rest[0] in "{[":
                    return True
    return False


def _detect_fix_hints(content: str, error_msg: str) -> list[JsonFixHint]:
    """Detect common JSON issues and produce fix hints."""
    hints: list[JsonFixHint] = []

    if "Expecting property name enclosed in double quotes" in error_msg:
        m = _UNQUOTED_KEY_RE.search(content)
        if m:
            line, col = _count_line_col(content, m.start())
            hints.append(
                JsonFixHint(
                    code="UNQUOTED_KEY",
                    message=f"Unquoted key '{m.group(1)}'. Keys must be double-quoted.",
                    line=line,
                    column=col,
                )
            )

    m = _TRAILING_COMMA_RE.search(content)
    if m:
        line, col = _count_line_col(content, m.start())
        hints.append(
            JsonFixHint(
                code="TRAILING_COMMA",
                message="Trailing comma detected. Remove comma before closing bracket.",
                line=line,
                column=col,
            )
        )

    if "'" in content and '"' not in content.split("'")[0][:20]:
        m = _SINGLE_QUOTE_RE.search(content)
        if m:
            line, col = _count_line_col(content, m.start())
            hints.append(
                JsonFixHint(
                    code="SINGLE_QUOTES",
                    message="Single quotes detected. JSON requires double quotes.",
                    line=line,
                    column=col,
                )
            )

    for m in _COMMENT_RE.finditer(content):
        line, col = _count_line_col(content, m.start())
        hints.append(
            JsonFixHint(
                code="JSON_COMMENT",
                message="Comments are not valid in JSON.",
                line=line,
                column=col,
            )
        )
        if len(hints) > 10:
            break

    if content.startswith(_BOM_PREFIX):
        hints.append(
            JsonFixHint(
                code="BOM_PREFIX",
                message="BOM (U+FEFF) detected at start. Strip before parsing.",
                line=1,
                column=1,
            )
        )

    return hints


def llm_json_output_check(text: str) -> LlmJsonCheckResult:
    """Detect and diagnose common LLM JSON output issues.

    Analyzes text for fenced code blocks, leading/trailing prose,
    JSON parse errors, and common formatting issues. Provides
    fix hints and extracted clean JSON content when possible.

    Args:
        text: LLM output text to analyze.

    Returns:
        LlmJsonCheckResult with detection details.
    """
    if not isinstance(text, str):
        return LlmJsonCheckResult(
            parse_ok=False,
            error_message=f"Input must be a string, got {type(text).__name__}",
        )

    original_length = len(text)
    if original_length > _MAX_INPUT_LENGTH:
        return LlmJsonCheckResult(
            parse_ok=False,
            error_message=f"Input exceeds {_MAX_INPUT_LENGTH} character limit",
            original_length=original_length,
        )

    has_bom, clean_text = _detect_bom(text)

    has_fence, fence_lang, fence_content = _detect_fence(clean_text)
    content_to_parse = fence_content if fence_content is not None else clean_text

    leading_prose, trailing_prose = _detect_prose(content_to_parse)

    if leading_prose or trailing_prose:
        content_to_parse = _extract_json_from_prose(content_to_parse)

    multiple_objects = _detect_multiple_objects(content_to_parse)

    parse_ok = False
    error_line: int | None = None
    error_col: int | None = None
    error_message: str | None = None
    fix_hints: list[JsonFixHint] = []

    if content_to_parse.strip():
        try:
            json.loads(content_to_parse)
            parse_ok = True
        except json.JSONDecodeError as e:
            error_line = e.lineno
            error_col = e.colno
            error_message = e.msg
            fix_hints = _detect_fix_hints(content_to_parse, e.msg)

    return LlmJsonCheckResult(
        has_fence=has_fence,
        fence_language=fence_lang,
        leading_prose=leading_prose,
        trailing_prose=trailing_prose,
        parse_ok=parse_ok,
        error_line=error_line,
        error_col=error_col,
        error_message=error_message,
        fix_hints=fix_hints,
        extracted_content=(
            content_to_parse if (has_fence or leading_prose or trailing_prose) else None
        ),
        multiple_json_objects=multiple_objects,
        has_bom=has_bom,
        original_length=original_length,
        extracted_length=len(content_to_parse),
    )
