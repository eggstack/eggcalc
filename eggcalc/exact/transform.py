"""
Deterministic text transformations and normalization.

These transformations are explicit and auditable - only explicitly
requested operations are performed.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import unicodedata
import zlib
from collections.abc import Sequence
from typing import Literal, TypedDict, cast

try:
    from urllib.parse import quote as _url_quote
    from urllib.parse import unquote as _url_unquote
except ImportError:
    _url_quote = None  # type: ignore[assignment]
    _url_unquote = None  # type: ignore[assignment]


class EscapeTextResult(TypedDict):
    """Result of escape_text operation."""

    mode: str
    escaped: str
    changed: bool
    summary: str


class UnescapeTextResult(TypedDict):
    """Result of unescape_text operation."""

    mode: str
    unescaped: str
    changed: bool
    error: str | None
    summary: str


class RemovedChar(TypedDict):
    """A character that was removed during transformation."""

    index: int
    char: str
    codepoint: str
    name: str


class TextTransformResult(TypedDict):
    """Result of text transformation."""

    changed: bool
    text: str
    operations_applied: list[str]
    removed: list[RemovedChar]
    warnings: list[str]
    summary: str


_VALID_OPERATIONS = {
    "normalize_nfc",
    "normalize_nfd",
    "normalize_nfkc",
    "normalize_nfkd",
    "casefold",
    "trim",
    "trim_trailing_whitespace",
    "normalize_newlines_lf",
    "ensure_final_newline",
    "strip_final_newline",
    "remove_zero_width",
    "remove_bidi_controls",
    "visible_repr",
}

_ZERO_WIDTH_CHARS = {
    "\u200b": "ZERO WIDTH SPACE",
    "\u200c": "ZERO WIDTH NON-JOINER",
    "\u200d": "ZERO WIDTH JOINER",
    "\u2060": "WORD JOINER",
}

_BIDI_CONTROL_CHARS = {
    "\u202a": "LEFT-TO-RIGHT EMBEDDING",
    "\u202b": "RIGHT-TO-LEFT EMBEDDING",
    "\u202c": "POP DIRECTIONAL FORMATTING",
    "\u202d": "LEFT-TO-RIGHT OVERRIDE",
    "\u202e": "RIGHT-TO-LEFT OVERRIDE",
    "\u2066": "LEFT-TO-RIGHT ISOLATE",
    "\u2067": "RIGHT-TO-LEFT ISOLATE",
    "\u2068": "FIRST STRONG ISOLATE",
    "\u2069": "POP DIRECTIONAL ISOLATE",
}


def _get_char_name(char: str) -> str:
    """Get Unicode name for a character."""
    name = unicodedata.name(char, None)
    if name:
        return name
    return f"U+{ord(char):04X}"


def _remove_chars(
    text: str,
    chars_to_remove: dict[str, str],
    operation_name: str,
) -> tuple[str, list[RemovedChar], list[str]]:
    """Remove specified characters from text.

    Args:
        text: Input text.
        chars_to_remove: Dict mapping char to name.
        operation_name: Name of operation for warnings.

    Returns:
        Tuple of (transformed text, removed chars list, warnings).
    """
    removed: list[RemovedChar] = []
    result: list[str] = []

    for index, char in enumerate(text):
        if char in chars_to_remove:
            removed.append(
                RemovedChar(
                    index=index,
                    char=char,
                    codepoint=f"U+{ord(char):04X}",
                    name=chars_to_remove[char],
                )
            )
        else:
            result.append(char)

    warnings: list[str] = []
    if removed:
        count = len(removed)
        names = ", ".join({r["name"] for r in removed})
        warnings.append(f"Removed {count} invisible/{operation_name} character(s): {names}")

    return "".join(result), removed, warnings


def text_transform(
    text: str,
    operations: list[str],
    detail: str = "normal",
) -> TextTransformResult:
    """Apply explicit text transformations.

    Args:
        text: Input string to transform.
        operations: List of operations to apply. Unknown operations
            are silently ignored (per design - only apply explicitly
            requested operations).
        detail: Detail level ("summary", "normal", "full"). Controls
            how much detail is in removed characters list.

    Returns:
        TextTransformResult with transformed text, operations applied,
        any removed characters, warnings, and summary.
    """
    if not operations:
        return TextTransformResult(
            changed=False,
            text=text,
            operations_applied=[],
            removed=[],
            warnings=[],
            summary="No operations requested",
        )

    current_text = text
    operations_applied: list[str] = []
    all_removed: list[RemovedChar] = []
    all_warnings: list[str] = []

    for op in operations:
        op_lower = op.lower()

        if op_lower == "normalize_nfc":
            normalized = unicodedata.normalize("NFC", current_text)
            if normalized != current_text:
                current_text = normalized
                operations_applied.append("normalize_nfc")

        elif op_lower == "normalize_nfd":
            normalized = unicodedata.normalize("NFD", current_text)
            if normalized != current_text:
                current_text = normalized
                operations_applied.append("normalize_nfd")

        elif op_lower == "normalize_nfkc":
            normalized = unicodedata.normalize("NFKC", current_text)
            if normalized != current_text:
                current_text = normalized
                operations_applied.append("normalize_nfkc")

        elif op_lower == "normalize_nfkd":
            normalized = unicodedata.normalize("NFKD", current_text)
            if normalized != current_text:
                current_text = normalized
                operations_applied.append("normalize_nfkd")

        elif op_lower == "casefold":
            casefolded = current_text.casefold()
            if casefolded != current_text:
                current_text = casefolded
                operations_applied.append("casefold")

        elif op_lower == "trim":
            trimmed = current_text.strip()
            if trimmed != current_text:
                current_text = trimmed
                operations_applied.append("trim")

        elif op_lower == "trim_trailing_whitespace":
            lines = current_text.split("\n")
            trimmed_lines = [line.rstrip() for line in lines]
            new_text = "\n".join(trimmed_lines)
            if new_text != current_text:
                current_text = new_text
                operations_applied.append("trim_trailing_whitespace")

        elif op_lower == "normalize_newlines_lf":
            normalized = current_text.replace("\r\n", "\n").replace("\r", "\n")
            if normalized != current_text:
                current_text = normalized
                operations_applied.append("normalize_newlines_lf")

        elif op_lower == "ensure_final_newline":
            if not current_text.endswith("\n"):
                current_text = current_text + "\n"
                operations_applied.append("ensure_final_newline")
            elif current_text.endswith("\n\n"):
                pass
            else:
                pass

        elif op_lower == "strip_final_newline":
            if current_text.endswith("\n"):
                stripped = current_text[:-1]
                if stripped != current_text:
                    current_text = stripped
                    operations_applied.append("strip_final_newline")

        elif op_lower == "remove_zero_width":
            result_text, removed, warnings = _remove_chars(
                current_text, _ZERO_WIDTH_CHARS, "zero-width"
            )
            if result_text != current_text:
                current_text = result_text
                all_removed.extend(removed)
                all_warnings.extend(warnings)
                operations_applied.append("remove_zero_width")

        elif op_lower == "remove_bidi_controls":
            result_text, removed, warnings = _remove_chars(
                current_text, _BIDI_CONTROL_CHARS, "bidi"
            )
            if result_text != current_text:
                current_text = result_text
                all_removed.extend(removed)
                all_warnings.extend(warnings)
                operations_applied.append("remove_bidi_controls")

        elif op_lower == "visible_repr":
            from .primitives import visible_repr as _visible_repr_impl

            current_text = _visible_repr_impl(current_text)
            operations_applied.append("visible_repr")

    changed = current_text != text

    if detail == "summary":
        removed_for_output: list[RemovedChar] = []
    elif detail == "full":
        removed_for_output = all_removed
    else:
        removed_for_output = all_removed

    if operations_applied:
        ops_str = ", ".join(operations_applied)
        if changed:
            summary = f"Applied {len(operations_applied)} operation(s): {ops_str}; text changed"
        else:
            summary = f"Applied {len(operations_applied)} operation(s): {ops_str}; text unchanged"
    else:
        summary = "No recognized operations applied"

    return TextTransformResult(
        changed=changed,
        text=current_text,
        operations_applied=operations_applied,
        removed=removed_for_output,
        warnings=all_warnings,
        summary=summary,
    )


_VALID_ESCAPE_MODES = {
    "json_string",
    "python_string",
    "rust_string",
    "posix_shell_single",
    "regex_literal",
    "markdown_inline_code",
    "markdown_code_block",
    "html_text",
    "url_component",
}

_VALID_UNESCAPE_MODES = {
    "json_string",
    "python_string",
    "unicode_escape",
    "url_component",
}


def _escape_json_string(text: str) -> str:
    """Escape text as JSON string literal."""
    return json.dumps(text)


def _escape_python_string(text: str) -> str:
    """Escape text as Python string literal."""
    return (
        "'"
        + text.replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
        .replace("\x00", "\\0")
        + "'"
    )


def _escape_rust_string(text: str) -> str:
    """Escape text as Rust string literal."""
    escaped = (
        text.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )
    return '"' + escaped + '"'


def _escape_posix_shell_single(text: str) -> str:
    """Escape text for POSIX shell single-quoted string."""
    escaped = text.replace("'", "'\\''")
    return "'" + escaped + "'"


def _escape_regex_literal(text: str) -> str:
    """Escape text as regex literal - escape all special chars."""
    return re.escape(text)


def _escape_markdown_inline_code(text: str) -> str:
    """Escape text for inline markdown code (wrap in backticks)."""
    if "`" in text:
        return "`` " + text + " ``"
    return "`" + text + "`"


def _escape_markdown_code_block(text: str) -> str:
    """Escape text for markdown code block."""
    return "```\n" + text + "\n```"


def _escape_html_text(text: str) -> str:
    """Escape text for HTML display."""
    result = text
    result = result.replace("&", "&amp;")
    result = result.replace("<", "&lt;")
    result = result.replace(">", "&gt;")
    result = result.replace('"', "&quot;")
    result = result.replace("'", "&#39;")
    return result


def _escape_url_component(text: str) -> str:
    """Escape text as URL component."""
    if _url_quote is None:
        raise ValueError("URL escaping not available (urllib.parse not found)")
    return _url_quote(text, safe="")


def escape_text(text: str, mode: str) -> EscapeTextResult:
    """Escape text for various output formats.

    Args:
        text: Input string to escape.
        mode: Escape mode (json_string, python_string, rust_string,
              posix_shell_single, regex_literal, markdown_inline_code,
              markdown_code_block, html_text, url_component).

    Returns:
        EscapeTextResult with escaped text and metadata.

    Raises:
        ValueError: If mode is not supported.
    """
    if mode not in _VALID_ESCAPE_MODES:
        raise ValueError(
            f"Unsupported escape mode: {mode}. Valid modes: {', '.join(sorted(_VALID_ESCAPE_MODES))}"
        )

    original_text = text

    if mode == "json_string":
        escaped = _escape_json_string(text)
    elif mode == "python_string":
        escaped = _escape_python_string(text)
    elif mode == "rust_string":
        escaped = _escape_rust_string(text)
    elif mode == "posix_shell_single":
        escaped = _escape_posix_shell_single(text)
    elif mode == "regex_literal":
        escaped = _escape_regex_literal(text)
    elif mode == "markdown_inline_code":
        escaped = _escape_markdown_inline_code(text)
    elif mode == "markdown_code_block":
        escaped = _escape_markdown_code_block(text)
    elif mode == "html_text":
        escaped = _escape_html_text(text)
    elif mode == "url_component":
        escaped = _escape_url_component(text)

    changed = escaped != original_text

    mode_names = {
        "json_string": "JSON string literal",
        "python_string": "Python string literal",
        "rust_string": "Rust string literal",
        "posix_shell_single": "POSIX shell single-quoted string",
        "regex_literal": "regex literal",
        "markdown_inline_code": "inline markdown code",
        "markdown_code_block": "markdown code block",
        "html_text": "HTML text",
        "url_component": "URL component",
    }

    summary = f"Escaped text as {mode_names.get(mode, mode)}"

    return EscapeTextResult(
        mode=mode,
        escaped=escaped,
        changed=changed,
        summary=summary,
    )


def _unescape_json_string(text: str) -> str:
    """Unescape JSON string literal."""
    if not text.startswith('"') or not text.endswith('"'):
        raise ValueError("Invalid JSON string literal: must be wrapped in double quotes")
    parsed = json.loads(text)
    return cast(str, parsed)


def _unescape_python_string(text: str) -> str:
    """Unescape Python string literal using ast.literal_eval."""
    try:
        return cast(str, ast.literal_eval(text))
    except (ValueError, SyntaxError) as e:
        raise ValueError(f"Invalid Python string literal: {e}")


def _unescape_unicode_escape(text: str) -> str:
    """Unescape Unicode escape sequences (\\\\uXXXX, \\\\UXXXXXXXX)."""

    def replace_unicode(match: re.Match[str]) -> str:
        code = match.group(1)
        return chr(int(code, 16))

    result = re.sub(r"\\u([0-9a-fA-F]{4})", replace_unicode, text)
    result = re.sub(r"\\U([0-9a-fA-F]{8})", replace_unicode, result)
    return result


def _unescape_url_component(text: str) -> str:
    """Unescape URL component."""
    if _url_unquote is None:
        raise ValueError("URL unescaping not available (urllib.parse not found)")
    return _url_unquote(text)


def unescape_text(text: str, mode: str) -> UnescapeTextResult:
    """Unescape text from various formats.

    Args:
        text: Input string to unescape.
        mode: Unescape mode (json_string, python_string,
              unicode_escape, url_component).

    Returns:
        UnescapeTextResult with unescaped text and metadata.

    Raises:
        ValueError: If mode is not supported or unescape fails.
    """
    if mode not in _VALID_UNESCAPE_MODES:
        raise ValueError(
            f"Unsupported unescape mode: {mode}. Valid modes: {', '.join(sorted(_VALID_UNESCAPE_MODES))}"
        )

    original_text = text
    error: str | None = None

    try:
        if mode == "json_string":
            unescaped = _unescape_json_string(text)
        elif mode == "python_string":
            unescaped = _unescape_python_string(text)
        elif mode == "unicode_escape":
            unescaped = _unescape_unicode_escape(text)
        elif mode == "url_component":
            unescaped = _unescape_url_component(text)
    except ValueError as e:
        error = str(e)
        unescaped = original_text

    changed = unescaped != original_text

    mode_names = {
        "json_string": "JSON string literal",
        "python_string": "Python string literal",
        "unicode_escape": "Unicode escape sequences",
        "url_component": "URL component",
    }

    if error:
        summary = f"Failed to unescape {mode_names.get(mode, mode)}: {error}"
    else:
        summary = f"Unescaped {mode_names.get(mode, mode)}"

    return UnescapeTextResult(
        mode=mode,
        unescaped=unescaped,
        changed=changed,
        error=error,
        summary=summary,
    )


class TextHashResult(TypedDict):
    """Result of text hashing."""

    encoding: str
    bytes: int
    codepoints: int
    hashes: dict[str, str]
    warnings: list[str]
    summary: str


class TextFingerprintResult(TypedDict):
    """Result of text fingerprinting."""

    sha256: str
    bytes_utf8: int
    codepoints: int
    graphemes: int
    newline_style: str
    normalization: dict[str, str | bool]
    summary: str


_SUPPORTED_HASH_ALGORITHMS = {"sha256", "sha1", "md5", "crc32"}


def text_hash(
    text: str,
    algorithms: Sequence[str] = ("sha256",),
    encoding: str = "utf-8",
) -> TextHashResult:
    """Compute cryptographic hashes of text for identity checking.

    Args:
        text: Input string to hash.
        algorithms: List of hash algorithms to compute (sha256, sha1, md5, crc32).
        encoding: Text encoding for byte conversion (utf-8, ascii, etc).

    Returns:
        TextHashResult with encoding, byte/codepoint counts, hash values,
        warnings, and summary.
    """
    warnings: list[str] = []

    encoded = text.encode(encoding)
    byte_count = len(encoded)
    codepoint_count = len(text)

    hashes: dict[str, str] = {}
    for algo in algorithms:
        algo_lower = algo.lower()
        if algo_lower == "sha256":
            hashes["sha256"] = hashlib.sha256(encoded).hexdigest()
        elif algo_lower == "sha1":
            hashes["sha1"] = hashlib.sha1(encoded).hexdigest()
        elif algo_lower == "md5":
            hashes["md5"] = hashlib.md5(encoded).hexdigest()
            if "md5" not in warnings:
                warnings.append("MD5 is non-cryptographic and provided for compatibility only")
        elif algo_lower == "crc32":
            hashes["crc32"] = format(zlib.crc32(encoded), "08x")
        else:
            supported = ", ".join(sorted(_SUPPORTED_HASH_ALGORITHMS))
            warnings.append(f"Unknown algorithm '{algo}', skipping (supported: {supported})")

    algo_count = len(hashes)
    if algo_count == 1:
        algo_name = list(hashes.keys())[0].upper()
        summary = f"{algo_name} computed for {byte_count} {encoding} bytes"
    else:
        summary = f"Computed {algo_count} hashes for {byte_count} {encoding} bytes"

    return TextHashResult(
        encoding=encoding,
        bytes=byte_count,
        codepoints=codepoint_count,
        hashes=hashes,
        warnings=warnings,
        summary=summary,
    )


def text_fingerprint(
    text: str,
    unicode: str = "raw",
    newline: str = "raw",
    trim_final_newline: bool = False,
    casefold: bool = False,
) -> TextFingerprintResult:
    """Compute a deterministic fingerprint of text for identity comparison.

    The fingerprint canonicalizes the text according to the specified options
    and then computes SHA-256 for stable identity checking.

    Args:
        text: Input string to fingerprint.
        unicode: Unicode normalization ("raw", "NFC", "NFD", "NFKC", "NFKD").
        newline: Newline normalization ("raw", "LF").
        trim_final_newline: Remove trailing newline before hashing.
        casefold: Apply casefolding before hashing.

    Returns:
        TextFingerprintResult with SHA-256 hash, metrics, and normalization info.

    Example:
        >>> result = text_fingerprint("Hello, world!\\n")
        >>> result["sha256"]  # 256-bit hash of the text
        >>> result["bytes_utf8"]  # UTF-8 byte count
    """
    canonical = text

    if unicode != "raw":
        canonical = unicodedata.normalize(
            cast(Literal["NFC", "NFD", "NFKC", "NFKD"], unicode), canonical
        )

    if newline == "LF":
        canonical = canonical.replace("\r\n", "\n").replace("\r", "\n")

    if trim_final_newline and canonical.endswith("\n"):
        canonical = canonical[:-1]

    if casefold:
        canonical = canonical.casefold()

    import hashlib

    sha256_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    from .primitives import count_graphemes as _count_graphemes

    is_nfc = unicodedata.is_normalized("NFC", text)

    # Delegate to the authoritative detector so mixed line endings are
    # labeled "mixed" instead of being misreported as "CRLF".
    if "\n" not in text and "\r" not in text:
        newline_style = "none"
    else:
        from .primitives import detect_newline_style

        newline_style = detect_newline_style(text)

    return TextFingerprintResult(
        sha256=sha256_hash,
        bytes_utf8=len(canonical.encode("utf-8")),
        codepoints=len(canonical),
        graphemes=_count_graphemes(canonical),
        newline_style=newline_style,
        normalization={
            "input_is_nfc": is_nfc,
            "applied": unicode,
        },
        summary=f"SHA-256 fingerprint computed for {len(canonical)} codepoints",
    )
