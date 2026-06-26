"""
Unicode script detection and confusable character detection.

Provides functions to detect Unicode scripts and identify confusable
homoglyphs that could be used for spoofing attacks.

The confusables table is derived from Unicode Standard Annex #39:
https://www.unicode.org/reports/tr39/
The full confusables.txt can be loaded at build time for comprehensive detection.
"""

from __future__ import annotations

import functools
import unicodedata
from typing import TypedDict

from .confusables import CONFUSABLES


class ScriptInfo(TypedDict):
    """Information about a script detection result."""

    index: int
    char: str
    script: str
    codepoint: str


class ConfusableInfo(TypedDict):
    """Information about a confusable character."""

    # Position of the character in the input string
    index: int
    # The confusable character itself
    char: str
    # Unicode codepoint in "U+XXXX" format
    codepoint: str
    # Unicode character name (e.g., "LATIN SMALL LETTER A")
    name: str
    # Character(s) this character is confusable with (can be multi-character)
    confusable_with: str
    # Unicode name(s) of the confusable character(s)
    confusable_name: str


class MixedScriptsResult(TypedDict):
    """Result of mixed script detection."""

    # True if multiple scripts present (excluding Common/Inherited/Other)
    mixed_scripts: bool
    # Distinct scripts found (excluding Common/Inherited/Other)
    scripts: list[str]
    # Position details for non-Common/Inherited/Other characters
    positions: list[ScriptInfo]


# Unicode script ranges for heuristic detection
_SCRIPT_RANGES: list[tuple[int, int, str]] = [
    (0x0041, 0x005A, "Latin"),
    (0x0061, 0x007A, "Latin"),
    (0x00C0, 0x00FF, "Latin"),
    (0x0100, 0x017F, "Latin"),
    (0x0180, 0x024F, "Latin"),
    (0x0400, 0x04FF, "Cyrillic"),
    (0x0500, 0x052F, "Cyrillic"),
    (0x0370, 0x03FF, "Greek"),
    (0x1F00, 0x1FFF, "Greek"),
    (0x4E00, 0x9FFF, "Han"),
    (0x3000, 0x303F, "CJK"),
    (0x3040, 0x309F, "Hiragana"),
    (0x30A0, 0x30FF, "Katakana"),
    (0x0600, 0x06FF, "Arabic"),
    (0x0590, 0x05FF, "Hebrew"),
    (0x0900, 0x097F, "Devanagari"),
    (0x0E00, 0x0E7F, "Thai"),
    (0xAC00, 0xD7AF, "Hangul"),
    (0x10A0, 0x10FF, "Georgian"),
    (0x0530, 0x058F, "Armenian"),
    (0x13A0, 0x13FF, "Cherokee"),
    (0x1400, 0x167F, "Canadian_Aboriginal"),
]


@functools.lru_cache(maxsize=128)
def _get_script_heuristic(char: str) -> str:
    """Determine script for a character using unicodedata.script() with fallback.

    Tries unicodedata.script() first (available in Python 3.14+), falling back
    to range-based heuristic detection for compatibility.

    Args:
        char: Single character.

    Returns:
        Script name or 'Other'.
    """
    # Try unicodedata.script() first (Python 3.14+)
    try:
        script: str = unicodedata.script(char)  # type: ignore[attr-defined]
        if script != "Unknown":
            return script
    except (AttributeError, ValueError):
        pass

    # Fallback: heuristic range-based detection
    codepoint = ord(char)

    # Check if it's a combining mark
    if unicodedata.category(char).startswith("M"):
        return "Inherited"

    # Check predefined scripts via unicodedata.name for Common script
    try:
        name = unicodedata.name(char, "")
        if "COMMON" in name.upper():
            return "Common"
        # Check for inherited scripts by name patterns
        if "INHERITED" in name.upper():
            return "Inherited"
    except ValueError:
        pass

    # Use range heuristic for script detection
    for start, end, script_name in _SCRIPT_RANGES:
        if start <= codepoint <= end:
            return script_name

    return "Other"


def unicode_script(char: str) -> str:
    """Determine the Unicode script of a single character.

    Uses Unicode script property with heuristic fallback for
    characters where the property returns Unknown.

    Args:
        char: Single character.

    Returns:
        Script name (Latin, Cyrillic, Greek, Han, Hiragana,
        Katakana, Arabic, Hebrew, Devanagari, Common, Inherited, Other).
    """
    if len(char) != 1:
        raise ValueError("char must be a single character")

    return _get_script_heuristic(char)


def unicode_scripts(s: str) -> list[str]:
    """Determine the Unicode scripts for all characters in a string.

    Args:
        s: Input string.

    Returns:
        List of script names for each character.
    """
    return [_get_script_heuristic(char) for char in s]


def detect_mixed_scripts(s: str) -> MixedScriptsResult:
    """Detect if string contains mixed scripts.

    Ignores Common, Inherited, and Other scripts for the mixed-script
    verdict. Characters classified as "Other" (digits, punctuation,
    whitespace, etc.) are excluded from the mixed-script analysis.

    Args:
        s: Input string.

    Returns:
        MixedScriptsResult with mixed_scripts (bool), scripts (list of distinct
        scripts excluding Common/Inherited/Other), and positions (list of
        ScriptInfo dicts for non-Common/Inherited/Other chars).
    """
    positions: list[ScriptInfo] = []
    scripts: set[str] = set()

    for index, char in enumerate(s):
        script = _get_script_heuristic(char)
        if script not in ("Common", "Inherited", "Other"):
            scripts.add(script)
            codepoint_str = f"U+{ord(char):04X}"
            positions.append(
                ScriptInfo(
                    index=index,
                    char=char,
                    script=script,
                    codepoint=codepoint_str,
                )
            )

    return MixedScriptsResult(
        mixed_scripts=len(scripts) > 1,
        scripts=sorted(scripts),
        positions=positions,
    )


def detect_confusables(s: str) -> list[ConfusableInfo]:
    """Detect confusable homoglyph characters in the string.

    Uses the full Unicode confusables table (UTS #39) loaded from
    confusables.py, which was generated from confusables.txt.

    Args:
        s: Input string.

    Returns:
        List of ConfusableInfo dicts with position, char, codepoint,
        name, confusable_with, and confusable_name.
    """
    result: list[ConfusableInfo] = []

    for index, char in enumerate(s):
        key = f"U+{ord(char):04X}"
        if key in CONFUSABLES:
            sub_str = CONFUSABLES[key]
            codepoint_str = f"U+{ord(char):04X}"
            name = unicodedata.name(char, "<unknown>")

            # Parse substitution codepoints back to characters
            confusable_with = "".join(chr(int(cp[2:], 16)) for cp in sub_str.split())

            confusable_name = ""
            for c in confusable_with:
                n = unicodedata.name(c, "")
                if n:
                    confusable_name += n + " "
                else:
                    confusable_name += c
            confusable_name = confusable_name.strip()

            result.append(
                ConfusableInfo(
                    index=index,
                    char=char,
                    codepoint=codepoint_str,
                    name=name,
                    confusable_with=confusable_with,
                    confusable_name=confusable_name,
                )
            )

    return result


def confusables_count(s: str) -> int:
    """Count confusable homoglyph characters in the string.

    Args:
        s: Input string.

    Returns:
        Count of confusable characters.
    """
    count = 0
    for char in s:
        key = f"U+{ord(char):04X}"
        if key in CONFUSABLES:
            count += 1
    return count


@functools.lru_cache(maxsize=1)
def _build_reverse_index() -> dict[str, list[str]]:
    """Build inverted index mapping target codepoints to source characters.

    Returns:
        Dict mapping target codepoint strings (e.g., "U+004F") to lists
        of source characters that confusable-map to them.
    """
    index: dict[str, list[str]] = {}
    for source_cp, target_cps_str in CONFUSABLES.items():
        for target_cp in target_cps_str.split():
            if target_cp not in index:
                index[target_cp] = []
            source_char = chr(int(source_cp[2:], 16))
            index[target_cp].append(source_char)
    return index


def reverse_confusables(char: str) -> list[str]:
    """Find all characters that are confusable with the given character.

    Given a character, returns all characters from the confusables table
    that confusable-map TO this character (i.e., characters that look
    like the given character and could be confused with it).

    Args:
        char: Single character to look up.

    Returns:
        List of characters that are confusable with the input.

    Raises:
        ValueError: If input is not a single character.

    Example:
        >>> "0" in reverse_confusables("O")  # digit 0 looks like letter O
        True
    """
    if len(char) != 1:
        raise ValueError("char must be a single character")

    target_cp = f"U+{ord(char):04X}"
    reverse_index = _build_reverse_index()
    return reverse_index.get(target_cp, [])
