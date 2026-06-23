"""
Text position conversion utilities.

Converts between byte offsets, codepoint indices, line/column positions,
and UTF-16 offsets for precise text positioning.
"""

from __future__ import annotations

import unicodedata
from typing import TypedDict


class TextPositionResult(TypedDict):
    """Result of text position conversion."""

    valid: bool
    byte_offset: int | None
    codepoint_index: int | None
    utf16_offset: int | None
    line: int | None
    column: int | None
    line_base: int
    column_base: int
    char: str | None
    codepoint: str | None
    name: str | None
    line_text_preview: str | None
    error: str | None
    summary: str


def _utf16_offset_to_codepoint_index(text: str, utf16_offset: int) -> int:
    """Convert UTF-16 code unit offset to Python string index."""
    utf16_count = 0
    for i, char in enumerate(text):
        cp = ord(char)
        if cp <= 0xFFFF:
            utf16_count += 1
        else:
            utf16_count += 2
        if utf16_count > utf16_offset:
            return i
        if utf16_count == utf16_offset:
            return i + 1
    return len(text)


def _codepoint_index_to_utf16_offset(text: str, codepoint_index: int) -> int:
    """Convert Python string index to UTF-16 code unit offset."""
    utf16_offset = 0
    for i, char in enumerate(text):
        if i >= codepoint_index:
            break
        cp = ord(char)
        if cp <= 0xFFFF:
            utf16_offset += 1
        else:
            utf16_offset += 2
    return utf16_offset


def _get_line_col(
    text: str, byte_offset: int | None = None, codepoint_index: int | None = None
) -> tuple[list[str], int, int]:
    """Split text into lines and find line/column for given position.

    Returns (lines, line, column) where line and column are 0-based.
    """
    utf8_bytes = text.encode("utf-8")
    lines = text.splitlines(keepends=True)

    if byte_offset is not None:
        if byte_offset < 0:
            codepoint_index = 0
        elif byte_offset >= len(utf8_bytes):
            codepoint_index = len(text)
        else:
            prefix = utf8_bytes[:byte_offset]
            codepoint_index = len(prefix.decode("utf-8", errors="ignore"))

    if codepoint_index is not None:
        if codepoint_index < 0:
            codepoint_index = 0
        elif codepoint_index > len(text):
            codepoint_index = len(text)

    line_start = 0
    line_num = 0
    current_col = 0

    for i, char in enumerate(text):
        if i == codepoint_index:
            return lines, line_num, current_col

        if char == "\n":
            line_num += 1
            current_col = 0
            line_start = i + 1
        elif char == "\r":
            if i + 1 < len(text) and text[i + 1] == "\n":
                continue
            line_num += 1
            current_col = 0
            line_start = i + 1
        else:
            current_col += 1

    if codepoint_index is not None and codepoint_index == len(text):
        return lines, line_num, current_col

    return lines, line_num, current_col


def _is_valid_byte_offset(text: str, offset: int) -> bool:
    """Check if byte offset is valid (not in middle of multibyte char)."""
    utf8_bytes = text.encode("utf-8")
    if offset < 0 or offset > len(utf8_bytes):
        return False
    if offset == len(utf8_bytes):
        return True

    byte = utf8_bytes[offset]

    if byte < 0x80:
        return True

    if 0xC0 <= byte <= 0xDF:
        if offset + 1 >= len(utf8_bytes):
            return False
        return 0x80 <= utf8_bytes[offset + 1] <= 0xBF

    if 0xE0 <= byte <= 0xEF:
        if offset + 2 >= len(utf8_bytes):
            return False
        return 0x80 <= utf8_bytes[offset + 1] <= 0xBF and 0x80 <= utf8_bytes[offset + 2] <= 0xBF

    if 0xF0 <= byte <= 0xF7:
        if offset + 3 >= len(utf8_bytes):
            return False
        return (
            0x80 <= utf8_bytes[offset + 1] <= 0xBF
            and 0x80 <= utf8_bytes[offset + 2] <= 0xBF
            and 0x80 <= utf8_bytes[offset + 3] <= 0xBF
        )

    return False


def text_position(
    text: str,
    byte_offset: int | None = None,
    codepoint_index: int | None = None,
    line: int | None = None,
    column: int | None = None,
    utf16_offset: int | None = None,
    line_base: int = 1,
    column_base: int = 1,
) -> TextPositionResult:
    """Convert between byte offsets, codepoint indices, line/column positions, and UTF-16 offsets.

    Exactly one locator mode should be provided: byte_offset, codepoint_index,
    line+column, or utf16_offset.

    Args:
        text: Input string.
        byte_offset: UTF-8 byte offset (0-based).
        codepoint_index: Python string index (Unicode scalar index).
        line: 1-based line number (with line_base).
        column: 1-based column number (with column_base).
        utf16_offset: UTF-16 code unit offset for LSP-style positions.
        line_base: Base for line numbers (1 for 1-based, 0 for 0-based).
        column_base: Base for column numbers (1 for 1-based, 0 for 0-based).

    Returns:
        TextPositionResult with all position fields populated.
    """
    mode_parts: list[str] = []
    if byte_offset is not None:
        mode_parts.append("byte_offset")
    if codepoint_index is not None:
        mode_parts.append("codepoint_index")
    if line is not None or column is not None:
        mode_parts.append("line+column")
    if utf16_offset is not None:
        mode_parts.append("utf16_offset")

    if len(mode_parts) != 1:
        return TextPositionResult(
            valid=False,
            byte_offset=None,
            codepoint_index=None,
            utf16_offset=None,
            line=None,
            column=None,
            line_base=line_base,
            column_base=column_base,
            char=None,
            codepoint=None,
            name=None,
            line_text_preview=None,
            error="Exactly one locator mode must be provided: byte_offset, codepoint_index, line+column, or utf16_offset",
            summary="Invalid: multiple or no locator modes provided",
        )

    if not text:
        if byte_offset is not None and byte_offset != 0:
            return TextPositionResult(
                valid=False,
                byte_offset=None,
                codepoint_index=None,
                utf16_offset=None,
                line=None,
                column=None,
                line_base=line_base,
                column_base=column_base,
                char=None,
                codepoint=None,
                name=None,
                line_text_preview=None,
                error="Byte offset 0 is the only valid position for empty text",
                summary="Invalid position for empty text",
            )
        return TextPositionResult(
            valid=True,
            byte_offset=0,
            codepoint_index=0,
            utf16_offset=0,
            line=line_base,
            column=column_base,
            line_base=line_base,
            column_base=column_base,
            char="",
            codepoint=None,
            name=None,
            line_text_preview="",
            error=None,
            summary="Empty text at start position",
        )

    lines: list[str]
    effective_codepoint_index: int

    if byte_offset is not None:
        if byte_offset < 0:
            return TextPositionResult(
                valid=False,
                byte_offset=None,
                codepoint_index=None,
                utf16_offset=None,
                line=None,
                column=None,
                line_base=line_base,
                column_base=column_base,
                char=None,
                codepoint=None,
                name=None,
                line_text_preview=None,
                error="Negative byte offset",
                summary="Invalid byte offset: negative",
            )
        if byte_offset > len(text.encode("utf-8")):
            return TextPositionResult(
                valid=False,
                byte_offset=None,
                codepoint_index=None,
                utf16_offset=None,
                line=None,
                column=None,
                line_base=line_base,
                column_base=column_base,
                char=None,
                codepoint=None,
                name=None,
                line_text_preview=None,
                error="Byte offset exceeds text length",
                summary="Invalid byte offset: beyond text end",
            )
        if not _is_valid_byte_offset(text, byte_offset):
            return TextPositionResult(
                valid=False,
                byte_offset=None,
                codepoint_index=None,
                utf16_offset=None,
                line=None,
                column=None,
                line_base=line_base,
                column_base=column_base,
                char=None,
                codepoint=None,
                name=None,
                line_text_preview=None,
                error="Byte offset falls inside multibyte character",
                summary="Invalid byte offset: inside multibyte character",
            )
        lines, line_num, col = _get_line_col(text, byte_offset=byte_offset)
        effective_codepoint_index = len(
            text.encode("utf-8")[:byte_offset].decode("utf-8", errors="ignore")
        )

    elif codepoint_index is not None:
        if codepoint_index < 0 or codepoint_index > len(text):
            return TextPositionResult(
                valid=False,
                byte_offset=None,
                codepoint_index=None,
                utf16_offset=None,
                line=None,
                column=None,
                line_base=line_base,
                column_base=column_base,
                char=None,
                codepoint=None,
                name=None,
                line_text_preview=None,
                error="Codepoint index out of bounds",
                summary="Invalid codepoint_index: out of bounds",
            )
        lines, line_num, col = _get_line_col(text, codepoint_index=codepoint_index)
        effective_codepoint_index = codepoint_index

    elif utf16_offset is not None:
        if utf16_offset < 0:
            return TextPositionResult(
                valid=False,
                byte_offset=None,
                codepoint_index=None,
                utf16_offset=None,
                line=None,
                column=None,
                line_base=line_base,
                column_base=column_base,
                char=None,
                codepoint=None,
                name=None,
                line_text_preview=None,
                error="Negative UTF-16 offset",
                summary="Invalid utf16_offset: negative",
            )
        effective_codepoint_index = _utf16_offset_to_codepoint_index(text, utf16_offset)
        if effective_codepoint_index > len(text):
            return TextPositionResult(
                valid=False,
                byte_offset=None,
                codepoint_index=None,
                utf16_offset=None,
                line=None,
                column=None,
                line_base=line_base,
                column_base=column_base,
                char=None,
                codepoint=None,
                name=None,
                line_text_preview=None,
                error="UTF-16 offset exceeds text length",
                summary="Invalid utf16_offset: beyond text end",
            )
        lines, line_num, col = _get_line_col(text, codepoint_index=effective_codepoint_index)

    else:
        if line is None or column is None:
            return TextPositionResult(
                valid=False,
                byte_offset=None,
                codepoint_index=None,
                utf16_offset=None,
                line=None,
                column=None,
                line_base=line_base,
                column_base=column_base,
                char=None,
                codepoint=None,
                name=None,
                line_text_preview=None,
                error="Both line and column must be provided for line+column mode",
                summary="Invalid: line and column both required",
            )
        if line < line_base or (line > line_base and line >= line_base + len(text.splitlines())):
            max_line = line_base + len(text.splitlines()) - 1
            actual_lines = len(text.splitlines()) if text else 1
            if line < line_base:
                return TextPositionResult(
                    valid=False,
                    byte_offset=None,
                    codepoint_index=None,
                    utf16_offset=None,
                    line=None,
                    column=None,
                    line_base=line_base,
                    column_base=column_base,
                    char=None,
                    codepoint=None,
                    name=None,
                    line_text_preview=None,
                    error=f"Line {line} is less than minimum line {line_base}",
                    summary="Invalid line: below valid range",
                )
            return TextPositionResult(
                valid=False,
                byte_offset=None,
                codepoint_index=None,
                utf16_offset=None,
                line=None,
                column=None,
                line_base=line_base,
                column_base=column_base,
                char=None,
                codepoint=None,
                name=None,
                line_text_preview=None,
                error=f"Line {line} exceeds maximum line {max_line}",
                summary="Invalid line: beyond text end",
            )
        lines = text.splitlines(keepends=True)
        if column < column_base:
            return TextPositionResult(
                valid=False,
                byte_offset=None,
                codepoint_index=None,
                utf16_offset=None,
                line=None,
                column=None,
                line_base=line_base,
                column_base=column_base,
                char=None,
                codepoint=None,
                name=None,
                line_text_preview=None,
                error=f"Column {column} is less than minimum column {column_base}",
                summary="Invalid column: below valid range",
            )
        line_index = line - line_base
        col_index = column - column_base
        if line_index < len(lines):
            line_text_raw = lines[line_index]
            if line_text_raw.endswith("\r\n"):
                max_col = column_base + len(line_text_raw) - 2
            elif line_text_raw.endswith("\n") or line_text_raw.endswith("\r"):
                max_col = column_base + len(line_text_raw) - 1
            else:
                max_col = column_base + len(line_text_raw)
            if col_index > max_col - column_base + (1 if column_base == 1 else 0):
                if column_base == 1:
                    actual_max = len(line_text_raw.rstrip("\r\n"))
                else:
                    actual_max = len(line_text_raw.rstrip("\r\n")) - 1
                return TextPositionResult(
                    valid=False,
                    byte_offset=None,
                    codepoint_index=None,
                    utf16_offset=None,
                    line=None,
                    column=None,
                    line_base=line_base,
                    column_base=column_base,
                    char=None,
                    codepoint=None,
                    name=None,
                    line_text_preview=None,
                    error=f"Column {column} exceeds line length {actual_max}",
                    summary="Invalid column: beyond line length",
                )
        codepoint_index_to_use = 0
        line_idx = 0
        for i, l_text in enumerate(lines):
            if line_idx == line_index:
                break
            codepoint_index_to_use += len(l_text)
            line_idx = i + 1
        effective_codepoint_index = codepoint_index_to_use + col_index
        lines, line_num, col = _get_line_col(text, codepoint_index=effective_codepoint_index)

    line_1based = line_num + line_base
    col_1based = col + column_base
    char_at_pos = (
        text[effective_codepoint_index] if 0 <= effective_codepoint_index < len(text) else ""
    )
    codepoint_str = f"U+{ord(char_at_pos):04X}" if char_at_pos else None
    name = unicodedata.name(char_at_pos, "<unknown>") if char_at_pos else None

    line_preview: str | None = None
    if 0 <= line_num < len(lines):
        line_preview = lines[line_num].rstrip("\r\n")

    byte_offset_result = text[:effective_codepoint_index].encode("utf-8")
    utf16_result = _codepoint_index_to_utf16_offset(text, effective_codepoint_index)

    return TextPositionResult(
        valid=True,
        byte_offset=len(byte_offset_result),
        codepoint_index=effective_codepoint_index,
        utf16_offset=utf16_result,
        line=line_1based,
        column=col_1based,
        line_base=line_base,
        column_base=column_base,
        char=char_at_pos if char_at_pos else None,
        codepoint=codepoint_str,
        name=name,
        line_text_preview=line_preview,
        error=None,
        summary=f"Line {line_1based}, column {col_1based}",
    )
