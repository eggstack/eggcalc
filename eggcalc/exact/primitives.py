"""
Low-level Unicode text primitives.

These primitives are deterministic, independently testable, and do not
perform semantic interpretation or call LLMs.

All modules in exact/ build on these primitives.
"""

from __future__ import annotations

import unicodedata
from typing import Literal, NamedTuple, TypedDict, cast


class CodepointInfo(NamedTuple):
    """Information about a single codepoint."""

    idx: int
    char: str
    codepoint: str
    name: str
    category: str


class MeasureBasic(TypedDict):
    """Basic text measurements."""

    bytes_utf8: int
    codepoints: int
    graphemes_estimate: int
    chars_no_whitespace: int
    ascii: int
    non_ascii: int


class InvisibleCharInfo(TypedDict):
    """Information about an invisible character."""

    index: int
    char: str
    codepoint: str
    name: str
    category: str
    display: str


# Invisible characters to detect
_INVISIBLE_CHARS: dict[str, tuple[str, str]] = {
    "\u200b": ("ZERO WIDTH SPACE", "ZWSP"),
    "\u200c": ("ZERO WIDTH NON-JOINER", "ZWNJ"),
    "\u200d": ("ZERO WIDTH JOINER", "ZWJ"),
    "\u200e": ("LEFT-TO-RIGHT MARK", "LRM"),
    "\u200f": ("RIGHT-TO-LEFT MARK", "RLM"),
    "\ufeff": ("ZERO WIDTH NO-BREAK SPACE", "BOM"),
    "\u00a0": ("NO-BREAK SPACE", "NBSP"),
    "\u2028": ("LINE SEPARATOR", "LINE SEP"),
    "\u2029": ("PARAGRAPH SEPARATOR", "PARA SEP"),
    "\u202a": ("LEFT-TO-RIGHT EMBEDDING", "LRE"),
    "\u202b": ("RIGHT-TO-LEFT EMBEDDING", "RLE"),
    "\u202c": ("POP DIRECTIONAL FORMATTING", "PDF"),
    "\u202d": ("LEFT-TO-RIGHT OVERRIDE", "LRO"),
    "\u202e": ("RIGHT-TO-LEFT OVERRIDE", "RLO"),
    "\u2066": ("LEFT-TO-RIGHT ISOLATE", "LRI"),
    "\u2067": ("RIGHT-TO-LEFT ISOLATE", "RLI"),
    "\u2068": ("FIRST STRONG ISOLATE", "FSI"),
    "\u2069": ("POP DIRECTIONAL ISOLATE", "PDI"),
    "\u2060": ("WORD JOINER", "WORD JOINER"),
    "\u00ad": ("SOFT HYPHEN", "SHY"),
    "\u180e": ("MONGOLIAN VOWEL SEPARATOR", "MVS"),
    "\u034f": ("COMBINING GRAPHEME JOINER", "CGJ"),
}

# Variation selectors (U+FE00 to U+FE0F)
_VARIATION_SELECTORS = set(range(0xFE00, 0xFE10))


def utf8_bytes(s: str) -> bytes:
    """Return raw UTF-8 bytes of the string.

    Args:
        s: Input string.

    Returns:
        UTF-8 encoded bytes.
    """
    return s.encode("utf-8")


def codepoints(s: str) -> list[CodepointInfo]:
    """Return detailed information about each codepoint in the string.

    Args:
        s: Input string.

    Returns:
        List of CodepointInfo namedtuples with index, char, codepoint (U+XXXX),
        Unicode name, and category.
    """
    result: list[CodepointInfo] = []
    for index, char in enumerate(s):
        codepoint_str = f"U+{ord(char):04X}"
        name = unicodedata.name(char, "<unknown>")
        category = unicodedata.category(char)
        result.append(CodepointInfo(index, char, codepoint_str, name, category))
    return result


def normalize_unicode(s: str, form: str) -> str:
    """Normalize Unicode string to the specified form.

    Args:
        s: Input string.
        form: Normalization form - one of NFC, NFD, NFKC, NFKD.

    Returns:
        Normalized string.

    Raises:
        ValueError: If form is not a recognized normalization form.
    """
    valid_forms = {"NFC", "NFD", "NFKC", "NFKD"}
    form_upper = form.upper()
    if form_upper not in valid_forms:
        raise ValueError(
            f"Unsupported normalization form: {form}. Use one of: {', '.join(valid_forms)}"
        )
    return unicodedata.normalize(cast(Literal["NFC", "NFD", "NFKC", "NFKD"], form_upper), s)


def casefold_text(s: str) -> str:
    """Return casefolded version of the string for case-insensitive comparison.

    Args:
        s: Input string.

    Returns:
        Casefolded string using str.casefold().
    """
    return s.casefold()


def raw_equal(a: str, b: str) -> bool:
    """Check if two strings are exactly equal (byte identity).

    Args:
        a: First string.
        b: Second string.

    Returns:
        True if strings are identical, False otherwise.
    """
    return a == b


def normalized_equal(a: str, b: str, form: str = "NFC") -> bool:
    """Check if two strings are equal after Unicode normalization.

    Args:
        a: First string.
        b: Second string.
        form: Normalization form - one of NFC, NFD, NFKC, NFKD.

    Returns:
        True if strings are equal after normalization.
    """
    return normalize_unicode(a, form) == normalize_unicode(b, form)


def measure_basic(s: str) -> MeasureBasic:
    """Return basic text measurements.

    Args:
        s: Input string.

    Returns:
        Dictionary with bytes_utf8, codepoints, graphemes_estimate,
        chars_no_whitespace, ascii, and non_ascii counts.
    """
    bytes_utf8 = len(s.encode("utf-8"))
    codepoints_count = len(s)
    grapheme_count = count_graphemes(s)
    chars_no_whitespace = sum(1 for c in s if not c.isspace())
    ascii_count = sum(1 for c in s if ord(c) < 128)
    non_ascii = codepoints_count - ascii_count

    return MeasureBasic(
        bytes_utf8=bytes_utf8,
        codepoints=codepoints_count,
        graphemes_estimate=grapheme_count,
        chars_no_whitespace=chars_no_whitespace,
        ascii=ascii_count,
        non_ascii=non_ascii,
    )


def find_invisibles(s: str) -> list[InvisibleCharInfo]:
    """Find all invisible or control characters in the string.

    Detects zero-width spaces, joiners, BOM, word joiner, soft hyphen,
    variation selectors, bidi controls, and combining marks.

    Args:
        s: Input string.

    Returns:
        List of InvisibleCharInfo dicts with position, char, codepoint,
        name, category, and display marker.
    """
    result: list[InvisibleCharInfo] = []

    for index, char in enumerate(s):
        codepoint_val = ord(char)
        display = None
        name = None

        # Check known invisible chars
        if char in _INVISIBLE_CHARS:
            name, display = _INVISIBLE_CHARS[char]
        # Check variation selectors
        elif codepoint_val in _VARIATION_SELECTORS:
            name = "VARIATION SELECTOR"
            display = "VS"
        # Check format characters in U+2061-U+2065 range
        elif 0x2061 <= codepoint_val <= 0x2065:
            name = unicodedata.name(char, "<unknown>")
            display = f"FORMAT:{name.split()[-1]}" if name else "FORMAT"
        # Check bidi control characters (U+2066 to U+206F)
        elif 0x2066 <= codepoint_val <= 0x206F:
            name = unicodedata.name(char, "<unknown>")
            display = f"BIDI:{name.split()[-1]}" if name else "BIDI"
        # Check combining marks (category M*)
        elif unicodedata.category(char).startswith("M"):
            name = unicodedata.name(char, "<unknown>")
            display = "CM"
        # Check other control characters (category C*) but exclude newlines
        elif unicodedata.category(char).startswith("C") and char not in "\n\t\r":
            name = (
                unicodedata.name(char, "<unknown>") if unicodedata.name(char, None) else "CONTROL"
            )
            display = "CTRL"

        if display:
            codepoint_str = f"U+{codepoint_val:04X}"
            category = unicodedata.category(char)
            result.append(
                InvisibleCharInfo(
                    index=index,
                    char=char,
                    codepoint=codepoint_str,
                    name=name or "<unknown>",
                    category=category,
                    display=display,
                )
            )

    return result


def visible_repr(s: str) -> str:
    """Return a display-safe representation of the string.

    Maps invisible or ambiguous characters to display-safe markers.

    Args:
        s: Input string.

    Returns:
        String with invisible chars replaced by markers like ␠ (space),
        ␉ (tab), ⟦ZWSP⟧, etc.
    """
    result: list[str] = []

    for char in s:
        if char == " ":
            result.append("␠")
        elif char == "\t":
            result.append("␉")
        elif char == "\n":
            result.append("␊")
        elif char == "\r":
            result.append("␍")
        elif char in _INVISIBLE_CHARS:
            _, display = _INVISIBLE_CHARS[char]
            result.append(f"⟦{display}⟧")
        elif 0xFE00 <= ord(char) <= 0xFE0F:
            result.append("⟦VS⟧")
        elif unicodedata.category(char).startswith("M"):
            result.append(f"◌{char}")
        elif 0x2061 <= ord(char) <= 0x2065:
            name = unicodedata.name(char, "<unknown>")
            label = name.split()[-1] if name else "FORMAT"
            result.append(f"⟦FORMAT:{label}⟧")
        elif 0x2066 <= ord(char) <= 0x206F:
            bidi_names = {
                0x2066: "LRI",
                0x2067: "RLI",
                0x2068: "FSI",
                0x2069: "PDI",
                0x202A: "LRE",
                0x202B: "RLE",
                0x202C: "PDF",
                0x202D: "LRO",
                0x202E: "RLO",
            }
            name = bidi_names.get(ord(char), "BIDI")
            result.append(f"⟦{name}⟧")
        else:
            result.append(char)

    return "".join(result)


def _advance_grapheme(s: str, i: int, n: int) -> int:
    """Advance past one grapheme cluster starting at position i.

    Handles GB9 (Extend), GB11 (ZWJ emoji), GB12/GB13 (Regional Indicator pairs).

    Args:
        s: Input string.
        i: Start position (must be a valid index into s).
        n: Length of s.

    Returns:
        Index immediately after the grapheme cluster.
    """
    cp = ord(s[i])

    # GB12/GB13: Regional Indicator pairs for flags.
    # Count pairs from the run start: every two consecutive RIs = 1 grapheme.
    if 0x1F1E6 <= cp <= 0x1F1FF:
        i += 1
        if i < n and 0x1F1E6 <= ord(s[i]) <= 0x1F1FF:
            i += 1  # consume the paired RI
        # Consume any trailing Extend characters (GB9)
        while i < n and _is_extend_char(s[i]):
            i += 1
        return i

    i += 1  # Move past base character

    # Process Extend characters and ZWJ sequences (GB9, GB11)
    while i < n:
        cp = ord(s[i])

        # GB9: Extend characters (combining marks, ZWNJ, VS)
        if _is_extend_char(s[i]):
            i += 1
            continue

        # GB11: Emoji ZWJ sequences
        # Pattern: Extended_Pictographic (ZWJ Extend*)* ZWJ Extended_Pictographic
        if cp == 0x200D:  # ZWJ
            i += 1  # Skip ZWJ
            # If next is pictographic, consume it as part of this grapheme
            if i < n and _is_extended_pictographic(s[i]):
                i += 1
                # After pictographic, continue checking for more extends/ZWJ
                continue
            # No pictographic after ZWJ, break and let main loop handle
            break

        # Not an extend or ZWJ, this is the start of next grapheme
        break

    return i


def count_graphemes(s: str) -> int:
    """Count extended grapheme clusters in a string.

    A grapheme cluster is what a user would perceive as a single character.
    For example, 'é' as precomposed (U+00E9) or decomposed ('e' + combining
    acute) both count as 1 grapheme. Emoji sequences like '🏳️' or '👨‍👩‍👧‍👦'
    each count as 1 grapheme.

    Handles GB9 (Extend), GB11 (ZWJ emoji), GB12/GB13 (RI pairs) per UAX #29.

    Args:
        s: Input string.

    Returns:
        Number of grapheme clusters in the string.
    """
    count = 0
    i = 0
    n = len(s)

    while i < n:
        count += 1
        i = _advance_grapheme(s, i, n)

    return count


def _is_extend_char(char: str) -> bool:
    """Check if char is an Extend-class character per UAX #29 GB9.

    Note: ZWJ (U+200D) is NOT included here because it's part of emoji
    ZWJ sequences (GB11) and must be handled specially in grapheme
    boundary detection.
    """
    cat = unicodedata.category(char)
    cp = ord(char)

    # Extend: Mn (nonspacing mark), Me (enclosing mark), Mc (spacing combining mark)
    # Also: ZWNJ (U+200C), Variation Selectors (U+FE00-U+FE0F)
    if cat.startswith('M'):
        return True
    if cp == 0x200C:  # ZWNJ
        return True
    if 0xFE00 <= cp <= 0xFE0F:  # Variation selectors
        return True
    return False


def _is_extended_pictographic(char: str) -> bool:
    """Check if char is an Extended Pictographic (for emoji ZWJ sequences).

    Uses codepoint ranges for common emoji blocks.
    """
    cp = ord(char)
    if (
        0x1F300 <= cp <= 0x1F9FF  # Emoticons, Transport, Symbols and Pictographs Extended-A
        or 0x2600 <= cp <= 0x26FF  # Misc symbols
        or 0x2700 <= cp <= 0x27BF
    ):  # Dingbats
        return True
    # Check if it's an emoji via category and name patterns
    cat = unicodedata.category(char)
    if cat == 'So':
        name = unicodedata.name(char, '')
        if 'EMOJI' in name or 'FACE' in name or 'SYMBOL' in name or 'SIGN' in name:
            return True
    return False


def truncate_to_grapheme(s: str, max_graphemes: int) -> str:
    """Truncate a string to at most max_graphemes grapheme clusters.

    This ensures the result doesn't cut mid-grapheme, preserving emoji,
    combining sequences, and flag sequences intact.

    Args:
        s: Input string.
        max_graphemes: Maximum number of grapheme clusters to return.

    Returns:
        Truncated string with at most max_graphemes grapheme clusters.
    """
    if max_graphemes <= 0:
        return ""

    if len(s) == 0:
        return s

    result: list[str] = []
    grapheme_count = 0
    i = 0
    n = len(s)

    while i < n and grapheme_count < max_graphemes:
        start = i
        i = _advance_grapheme(s, i, n)
        result.append(s[start:i])
        grapheme_count += 1

    return "".join(result)


def byte_offset_to_codepoint_index(s: str, byte_offset: int) -> int:
    """Convert a UTF-8 byte offset to a codepoint index.

    Args:
        s: Input string.
        byte_offset: UTF-8 byte offset (0-based).

    Returns:
        Codepoint index (0-based).

    Raises:
        ValueError: If byte_offset is inside a multi-byte character.
    """
    encoded = s.encode("utf-8")
    if byte_offset < 0 or byte_offset > len(encoded):
        raise ValueError(f"Byte offset {byte_offset} out of range (0-{len(encoded)})")

    if byte_offset == len(encoded):
        return len(s)

    decoded_pos = 0
    byte_pos = 0
    while byte_pos < byte_offset:
        if byte_pos >= len(encoded):
            break
        b = encoded[byte_pos]
        if b < 0x80:
            byte_pos += 1
        elif b < 0xE0:
            if byte_pos + 1 >= len(encoded):
                raise ValueError(f"Byte offset {byte_offset} falls inside multi-byte character")
            byte_pos += 2
        elif b < 0xF0:
            if byte_pos + 2 >= len(encoded):
                raise ValueError(f"Byte offset {byte_offset} falls inside multi-byte character")
            byte_pos += 3
        else:
            if byte_pos + 3 >= len(encoded):
                raise ValueError(f"Byte offset {byte_offset} falls inside multi-byte character")
            byte_pos += 4
        decoded_pos += 1

    if byte_pos != byte_offset:
        raise ValueError(f"Byte offset {byte_offset} falls inside multi-byte character")

    return decoded_pos


def codepoint_index_to_byte_offset(s: str, codepoint_index: int) -> int:
    """Convert a codepoint index to a UTF-8 byte offset.

    Args:
        s: Input string.
        codepoint_index: Codepoint index (0-based).

    Returns:
        UTF-8 byte offset (0-based).

    Raises:
        ValueError: If codepoint_index is out of range.
    """
    if codepoint_index < 0 or codepoint_index > len(s):
        raise ValueError(f"Codepoint index {codepoint_index} out of range (0-{len(s)})")

    encoded = s.encode("utf-8")
    decoded_pos = 0
    byte_pos = 0
    for char in s:
        if decoded_pos >= codepoint_index:
            break
        char_bytes = len(char.encode("utf-8"))
        byte_pos += char_bytes
        decoded_pos += 1

    return byte_pos


def codepoint_index_to_line_column(
    s: str, codepoint_index: int, line_base: int = 1, column_base: int = 1
) -> tuple[int, int]:
    """Convert a codepoint index to line and column (1-based by default).

    Args:
        s: Input string.
        codepoint_index: Codepoint index (0-based).
        line_base: Base for line numbers (1 for 1-based, 0 for 0-based).
        column_base: Base for column numbers (1 for 1-based, 0 for 0-based).

    Returns:
        Tuple of (line, column), both integers according to bases.

    Raises:
        ValueError: If codepoint_index is out of range.
    """
    if codepoint_index < 0 or codepoint_index > len(s):
        raise ValueError(f"Codepoint index {codepoint_index} out of range (0-{len(s)})")

    line = line_base
    column = column_base

    for i in range(codepoint_index):
        if s[i] == "\n":
            line += 1
            column = column_base
        else:
            column += 1

    return line, column


def line_column_to_codepoint_index(
    s: str, line: int, column: int, line_base: int = 1, column_base: int = 1
) -> int:
    """Convert line and column to a codepoint index.

    Args:
        s: Input string.
        line: Line number (1-based by default).
        column: Column number (1-based by default).
        line_base: Base for line numbers (1 for 1-based, 0 for 0-based).
        column_base: Base for column numbers (1 for 1-based, 0 for 0-based).

    Returns:
        Codepoint index (0-based).

    Raises:
        ValueError: If line or column is out of range.
    """
    target_line = line + (line_base - 1)
    target_column = column + (column_base - 1)

    current_line = 1
    current_column = 1
    codepoint_index = 0

    for i, char in enumerate(s):
        if current_line == target_line:
            if current_column == target_column:
                return i
            if current_column > target_column:
                raise ValueError(f"Column {column} out of range for line {line}")
        elif current_line > target_line:
            raise ValueError(f"Line {line} out of range ({current_line} lines in text)")

        if char == "\n":
            current_line += 1
            current_column = 1
        else:
            current_column += 1

    if current_line < target_line:
        raise ValueError(f"Line {line} out of range ({current_line - 1} lines in text)")
    if current_line == target_line and current_column < target_column:
        raise ValueError(f"Column {column} out of range for line {line}")

    return len(s)


def get_line_text(s: str, line: int, line_base: int = 1) -> str:
    """Extract the text of a specific line.

    Args:
        s: Input string.
        line: Line number (1-based by default).
        line_base: Base for line numbers (1 for 1-based, 0 for 0-based).

    Returns:
        The text of the line (without newline), or empty string if line doesn't exist.
    """
    target_line = line + (line_base - 1)
    current_line = 1
    start = 0
    i = 0

    while i < len(s):
        if current_line == target_line:
            start = i
            break
        if s[i] == "\n":
            current_line += 1
        i += 1

    if current_line < target_line:
        return ""

    end = start
    while end < len(s) and s[end] != "\n":
        end += 1

    return s[start:end]


def get_surrounding_lines(
    s: str, line: int, context_lines: int, line_base: int = 1
) -> tuple[list[tuple[int, str]], list[tuple[int, str]]]:
    """Get lines before and after a given line.

    Args:
        s: Input string.
        line: Target line number (1-based by default).
        context_lines: Number of context lines to return.
        line_base: Base for line numbers (1 for 1-based, 0 for 0-based).

    Returns:
        Tuple of (before_lines, after_lines), each a list of (line_number, text) tuples.
    """
    target_line = line + (line_base - 1)

    lines_data: list[tuple[int, str]] = []
    current_line = 1
    line_start = 0

    for i, char in enumerate(s):
        if char == "\n":
            lines_data.append((current_line, s[line_start:i]))
            line_start = i + 1
            current_line += 1

    if line_start < len(s):
        lines_data.append((current_line, s[line_start:]))

    before: list[tuple[int, str]] = []
    after: list[tuple[int, str]] = []

    for ln, text in lines_data:
        if ln < target_line:
            if ln >= target_line - context_lines:
                before.append((ln, text))
        elif ln > target_line:
            if ln <= target_line + context_lines:
                after.append((ln, text))

    return before, after


def detect_newline_style(s: str) -> str:
    """Detect the newline style of a string.

    Args:
        s: Input string.

    Returns:
        "CRLF", "LF", "CR", or "mixed" if multiple styles found.
    """
    has_crlf = "\r\n" in s
    has_lf = "\n" in s and not has_crlf
    has_cr = "\r" in s and not has_crlf and not has_lf

    if has_crlf and (has_lf or has_cr):
        return "mixed"
    if has_crlf:
        return "CRLF"
    if has_lf:
        return "LF"
    if has_cr:
        return "CR"
    return "LF"
