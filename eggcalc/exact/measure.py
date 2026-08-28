"""
Text measurement primitives.

Provides higher-level text measurement functions including line metrics,
word metrics, and combined character categorization metrics.
"""

from __future__ import annotations

import re
import unicodedata
from typing import TypedDict


class LineMetrics(TypedDict):
    """Line-level metrics."""

    lines: int
    nonempty_lines: int
    blank_lines: int
    max_line_length_codepoints: int
    trailing_whitespace_lines: list[int]
    newline_style: str  # "LF", "CRLF", "CR", "mixed", "none"
    ends_with_newline: bool


class WordMetrics(TypedDict):
    """Word-level metrics."""

    words: int
    unique_words_casefolded: int
    sentences_estimate: int
    paragraphs: int
    average_word_length: float


class CharCategoryMetrics(TypedDict):
    """Character category metrics."""

    letters: int
    digits: int
    punctuation: int
    symbols: int
    spaces: int
    control_chars: int
    combining_marks: int


def _measure_detect_newline_style(s: str) -> str:
    """Detect the newline style used in the string."""
    has_crlf = "\r\n" in s
    standalone_cr = s.count("\r") - s.count("\r\n")
    standalone_lf = s.count("\n") - s.count("\r\n")

    if has_crlf and (standalone_cr > 0 or standalone_lf > 0):
        return "mixed"
    if standalone_cr > 0 and standalone_lf > 0:
        return "mixed"
    if has_crlf:
        return "CRLF"
    elif standalone_cr > 0:
        return "CR"
    elif standalone_lf > 0:
        return "LF"
    else:
        return "none"


def line_metrics(s: str) -> LineMetrics:
    """Calculate line-level metrics for a string.

    Args:
        s: Input string. None is treated as empty string (returns zero metrics).

    Returns:
        Dictionary with lines, nonempty_lines, blank_lines,
        max_line_length_codepoints, trailing_whitespace_lines (1-based line numbers),
        newline_style (LF/CRLF/CR/mixed/none), ends_with_newline.
    """
    if not s:
        return LineMetrics(
            lines=0,
            nonempty_lines=0,
            blank_lines=0,
            max_line_length_codepoints=0,
            trailing_whitespace_lines=[],
            newline_style="none",
            ends_with_newline=False,
        )

    lines = s.splitlines()
    num_lines = len(lines)

    # Check how string ends
    ends_with_newline = s.endswith(("\n", "\r"))

    # Detect newline style
    newline_style = _measure_detect_newline_style(s)

    # Analyze each line
    nonempty_lines = 0
    blank_lines = 0
    max_line_length = 0
    trailing_whitespace_lines: list[int] = []

    for line_num, line in enumerate(lines, start=1):
        line_length = len(line)

        if line_length > 0:
            nonempty_lines += 1
            if line_length > max_line_length:
                max_line_length = line_length

            # Check for trailing whitespace
            if line != line.rstrip():
                trailing_whitespace_lines.append(line_num)
        else:
            blank_lines += 1

    return LineMetrics(
        lines=num_lines,
        nonempty_lines=nonempty_lines,
        blank_lines=blank_lines,
        max_line_length_codepoints=max_line_length,
        trailing_whitespace_lines=trailing_whitespace_lines,
        newline_style=newline_style,
        ends_with_newline=ends_with_newline,
    )


def word_metrics(s: str) -> WordMetrics:
    """Calculate word-level metrics for a string.

    Splits on whitespace and counts words, unique words (casefolded),
    estimates sentences, paragraphs, and average word length.

    Args:
        s: Input string. None is treated as empty string (returns zero metrics).

    Returns:
        Dictionary with words, unique_words_casefolded, sentences_estimate,
        paragraphs, average_word_length.
    """
    if not s:
        return WordMetrics(
            words=0,
            unique_words_casefolded=0,
            sentences_estimate=0,
            paragraphs=0,
            average_word_length=0.0,
        )

    # Split into words (whitespace-separated tokens)
    tokens = s.split()

    # Filter out tokens that don't contain letters (keep word-like tokens)
    words = [t for t in tokens if any(c.isalpha() for c in t)]

    num_words = len(words)

    # Unique words (casefolded)
    casefolded = {w.casefold() for w in words}
    unique_words = len(casefolded)

    # Average word length
    if num_words > 0:
        total_length = sum(len(w) for w in words)
        avg_word_length = total_length / num_words
    else:
        avg_word_length = 0.0

    # Estimate sentences (count . ! ? that are ellipses or sentence terminators)
    # Simple heuristic: count sentence-ending punctuation
    sentence_pattern = r"[.!?]+(?:\s|$)|[.!?]+(?=[A-Z])"
    sentences = re.findall(sentence_pattern, s)
    sentences_estimate = len(sentences) if sentences else 0

    # Paragraphs (separated by blank lines)
    paragraphs = 0
    current_paragraph_has_content = False
    for line in s.splitlines():
        stripped = line.strip()
        if stripped:
            if not current_paragraph_has_content:
                paragraphs += 1
                current_paragraph_has_content = True
        else:
            current_paragraph_has_content = False

    # Ensure at least 1 paragraph if there's any content
    if paragraphs == 0 and any(c.isalpha() for c in s):
        paragraphs = 1

    return WordMetrics(
        words=num_words,
        unique_words_casefolded=unique_words,
        sentences_estimate=sentences_estimate,
        paragraphs=paragraphs,
        average_word_length=round(avg_word_length, 2),
    )


def char_category_metrics(s: str) -> CharCategoryMetrics:
    """Calculate character category metrics.

    Categorizes each character by Unicode general category.

    Args:
        s: Input string. None is treated as empty string (returns zero metrics).

    Returns:
        Dictionary with counts for letters, digits, punctuation,
        symbols, spaces, control_chars, combining_marks.
    """
    if not s:
        return CharCategoryMetrics(
            letters=0,
            digits=0,
            punctuation=0,
            symbols=0,
            spaces=0,
            control_chars=0,
            combining_marks=0,
        )

    letters = 0
    digits = 0
    punctuation = 0
    symbols = 0
    spaces = 0
    control_chars = 0
    combining_marks = 0

    for char in s:
        cat = unicodedata.category(char)

        if cat.startswith("L"):  # Letters
            letters += 1
        elif cat.startswith("N"):  # Numbers
            digits += 1
        elif cat.startswith("P"):  # Punctuation
            punctuation += 1
        elif cat.startswith("S"):  # Symbols
            symbols += 1
        elif cat.startswith("Z"):  # Separators (spaces)
            spaces += 1
        elif cat.startswith("C"):  # Other (control, format, etc.)
            if cat == "Cf":  # Format characters (e.g., U+FEFF BOM)
                pass  # Cf excluded from control_chars count per UTS #55
            else:
                control_chars += 1  # Cc, Co, Cn all count
        elif cat.startswith("M"):  # Mark categories
            combining_marks += 1
        else:  # Defensive: all valid Unicode categories are L/N/P/S/Z/C/M
            pass

    return CharCategoryMetrics(
        letters=letters,
        digits=digits,
        punctuation=punctuation,
        symbols=symbols,
        spaces=spaces,
        control_chars=control_chars,
        combining_marks=combining_marks,
    )
