"""
Synthesis functions built on exact primitives.

These functions combine primitives to provide higher-level operations
for text inspection, comparison, and measurement.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, TypedDict

from .diff import (
    common_prefix_suffix as _common_prefix_suffix,
)
from .diff import (
    diff_spans as _diff_spans,
)
from .diff import (
    first_diff as _first_diff,
)
from .diff import (
    levenshtein_distance as _levenshtein_distance,
)
from .measure import (
    char_category_metrics as _char_category_metrics,
)
from .measure import (
    line_metrics as _line_metrics,
)
from .measure import (
    word_metrics as _word_metrics,
)
from .primitives import InvisibleCharInfo
from .primitives import casefold_text as _casefold_text
from .primitives import (
    count_graphemes as _count_graphemes,
)
from .primitives import (
    find_invisibles as _find_invisibles,
)
from .primitives import (
    measure_basic as _measure_basic,
)
from .primitives import normalize_unicode as _normalize_unicode
from .primitives import (
    normalized_equal as _normalized_equal,
)
from .primitives import (
    raw_equal as _raw_equal,
)
from .primitives import (
    visible_repr as _visible_repr,
)
from .unicode_tools import ConfusableInfo, MixedScriptsResult
from .unicode_tools import (
    detect_confusables as _detect_confusables,
)
from .unicode_tools import (
    detect_mixed_scripts as _detect_mixed_scripts,
)

MAX_TEXT_LENGTH = 100_000
MAX_DIFF_SPANS = 50


class NormalizationState(TypedDict):
    """Unicode normalization state."""

    is_nfc: bool
    is_nfd: bool
    is_nfkc: bool
    is_nfkd: bool


class UnicodeRisks(TypedDict):
    """Unicode risk signals."""

    contains_invisibles: bool
    contains_bidi_controls: bool
    mixed_scripts: bool
    scripts: list[str]


class MeasureTextResult(TypedDict):
    """Complete text measurement result."""

    bytes_utf8: int
    codepoints: int
    graphemes: int
    words: int
    unique_words_casefolded: int
    lines: int
    nonempty_lines: int
    blank_lines: int
    max_line_length_codepoints: int
    chars_no_whitespace: int
    ascii: int
    non_ascii: int
    letters: int
    digits: int
    punctuation: int
    symbols: int
    spaces: int
    control_chars: int
    combining_marks: int
    invisible_chars: int
    newline_style: str
    ends_with_newline: bool
    normalization: NormalizationState
    unicode_risks: UnicodeRisks
    warnings: list[str]


class TextEqualResult(TypedDict):
    """Text equality comparison result."""

    equal: bool
    mode: dict[str, Any]
    raw_equal: bool
    nfc_equal: bool
    nfd_equal: bool
    nfkc_equal: bool
    nfkd_equal: bool
    casefold_equal: bool
    byte_equal: bool
    lengths: dict[str, int]
    first_difference: dict[str, Any] | None
    classification: str


class DiffInfo(TypedDict):
    """A single diff span with detailed information."""

    kind: str
    a_span: list[int]
    b_span: list[int]
    a_text: str
    b_text: str
    a_visible: str
    b_visible: str
    a_codepoints: list[dict]
    b_codepoints: list[dict]
    note: str


class ExplainDiffResult(TypedDict):
    """Detailed diff explanation result."""

    equal: bool
    classification: str
    summary: dict[str, Any]
    a_metrics: dict[str, int]
    b_metrics: dict[str, int]
    diffs: list[DiffInfo]
    security_findings: list[dict]
    agent_instruction: str


class InspectTextNormalized(TypedDict):
    """Normalized text analysis."""

    form: str
    text: str
    safe_repr: str
    changed: bool
    diff: list[dict]


class NormalizationFinding(TypedDict):
    """A finding from normalization analysis."""

    kind: str
    message: str


class InspectTextResult(TypedDict):
    """Complete text inspection result."""

    safe_repr: str
    metrics: MeasureTextResult
    normalization: dict[str, bool]
    normalization_diff: bool
    normals_repr: str | None
    invisibles: list[InvisibleCharInfo]
    bidi_controls: list[InvisibleCharInfo]
    mixed_scripts: MixedScriptsResult
    confusables: list[ConfusableInfo]
    warnings: list[dict]
    limits_applied: list[str]
    normalize: str
    compare_normalized: bool
    original: dict[str, Any]
    normalized: InspectTextNormalized | None
    normalization_findings: list[NormalizationFinding]


class CountCharsResult(TypedDict):
    """Character counting result."""

    target: str
    normalization: str
    count: int
    positions: list[int]
    text_length_codepoints: int


class ListCompareOrderedResult(TypedDict):
    """Ordered list comparison result."""

    equal: bool
    first_diff_index: int | None
    equal_prefix_length: int
    aligned: list[dict]


class ListCompareSetResult(TypedDict):
    """Set-based list comparison result."""

    equal: bool
    only_in_a: list[str]
    only_in_b: list[str]


class ListCompareMultisetResult(TypedDict):
    """Multiset-based list comparison result."""

    equal: bool
    count_deltas: dict[str, int]
    only_in_a: list[str]
    only_in_b: list[str]


class ListCompareNearMatch(TypedDict):
    """A near match between list items."""

    a: str
    b: str
    distance: int
    classification: str


class ListCompareResult(TypedDict):
    """List comparison result with near-match detection."""

    same_ordered: bool
    same_unordered: bool
    only_in_a: list[str]
    only_in_b: list[str]
    duplicates_a: list[str]
    duplicates_b: list[str]
    near_matches: list[ListCompareNearMatch]


def _detect_special_sequences(s: str) -> dict[str, int]:
    """Detect sequences that cause codepoint/grapheme divergence.

    Returns counts of: combining_marks, zwj_sequences, variation_selectors,
    regional_indicator_pairs, emoji_modifiers.
    """
    result = {
        "combining_marks": 0,
        "zwj_sequences": 0,
        "variation_selectors": 0,
        "regional_indicator_pairs": 0,
        "emoji_modifiers": 0,
    }
    i = 0
    n = len(s)
    while i < n:
        cp = ord(s[i])
        cat = unicodedata.category(s[i])

        if cat.startswith("M"):
            result["combining_marks"] += 1
        elif cp == 0x200D:
            result["zwj_sequences"] += 1
        elif 0xFE00 <= cp <= 0xFE0F:
            result["variation_selectors"] += 1
        elif 0x1F1E6 <= cp <= 0x1F1FF:
            if i + 1 < n and 0x1F1E6 <= ord(s[i + 1]) <= 0x1F1FF:
                result["regional_indicator_pairs"] += 1
                i += 1
        elif 0x1F3FB <= cp <= 0x1F3FF:
            result["emoji_modifiers"] += 1
        i += 1
    return result


def measure_text(text: str) -> MeasureTextResult:
    """Measure text properties combining multiple primitives.

    Args:
        text: Input string.

    Returns:
        Complete text measurement with metrics, normalization, and risk signals.

    Raises:
        ValueError: If text exceeds MAX_TEXT_LENGTH.
    """
    if len(text) > MAX_TEXT_LENGTH:
        raise ValueError(f"Input length {len(text)} exceeds MAX_TEXT_LENGTH {MAX_TEXT_LENGTH}")

    basic = _measure_basic(text)
    lines = _line_metrics(text)
    words = _word_metrics(text)
    categories = _char_category_metrics(text)
    invisibles = _find_invisibles(text)
    scripts = _detect_mixed_scripts(text)
    grapheme_count = _count_graphemes(text)
    special = _detect_special_sequences(text)

    warnings: list[str] = []
    if special["combining_marks"] > 0:
        warnings.append(
            f"Text contains {special['combining_marks']} combining mark(s) - codepoint count diverges from user-perceived characters"
        )
    if special["zwj_sequences"] > 0:
        warnings.append(
            f"Text contains {special['zwj_sequences']} zero-width joiner sequence(s) - sequences may affect display"
        )
    if special["variation_selectors"] > 0:
        warnings.append(
            f"Text contains {special['variation_selectors']} variation selector(s) - display may differ"
        )
    if special["regional_indicator_pairs"] > 0:
        warnings.append(
            f"Text contains {special['regional_indicator_pairs']} regional indicator pair(s) - these render as flag emoji"
        )
    if special["emoji_modifiers"] > 0:
        warnings.append(
            f"Text contains {special['emoji_modifiers']} emoji modifier(s) - modifies base emoji appearance"
        )

    return MeasureTextResult(
        bytes_utf8=basic["bytes_utf8"],
        codepoints=basic["codepoints"],
        graphemes=grapheme_count,
        words=words["words"],
        unique_words_casefolded=words["unique_words_casefolded"],
        lines=lines["lines"],
        nonempty_lines=lines["nonempty_lines"],
        blank_lines=lines["blank_lines"],
        max_line_length_codepoints=lines["max_line_length_codepoints"],
        chars_no_whitespace=basic["chars_no_whitespace"],
        ascii=basic["ascii"],
        non_ascii=basic["non_ascii"],
        letters=categories["letters"],
        digits=categories["digits"],
        punctuation=categories["punctuation"],
        symbols=categories["symbols"],
        spaces=categories["spaces"],
        control_chars=categories["control_chars"],
        combining_marks=categories["combining_marks"],
        invisible_chars=len(invisibles),
        newline_style=lines["newline_style"],
        ends_with_newline=lines["ends_with_newline"],
        normalization=NormalizationState(
            is_nfc=unicodedata.is_normalized("NFC", text),
            is_nfd=unicodedata.is_normalized("NFD", text),
            is_nfkc=unicodedata.is_normalized("NFKC", text),
            is_nfkd=unicodedata.is_normalized("NFKD", text),
        ),
        unicode_risks=UnicodeRisks(
            contains_invisibles=len(invisibles) > 0,
            contains_bidi_controls=any("BIDI" in inv.get("display", "") for inv in invisibles),
            mixed_scripts=scripts["mixed_scripts"],
            scripts=scripts["scripts"],
        ),
        warnings=warnings,
    )


def text_equal(
    a: str,
    b: str,
    normalization: str = "raw",
    casefold: bool = False,
    trim: bool = False,
    ignore_newline_style: bool = False,
    ignore_trailing_whitespace: bool = False,
    ignore_final_newline: bool = False,
) -> TextEqualResult:
    """Compare two strings under various equality modes.

    Args:
        a: First string.
        b: Second string.
        normalization: "raw", "NFC", "NFD", "NFKC", or "NFKD".
        casefold: If True, use casefolded comparison.
        trim: If True, trim whitespace.
        ignore_newline_style: Normalize different newline styles before comparison.
        ignore_trailing_whitespace: Ignore trailing whitespace on each line.
        ignore_final_newline: Ignore trailing newline at end of strings.

    Returns:
        Detailed equality comparison with evidence.
    """
    a_work = a
    b_work = b

    if ignore_final_newline:
        while a_work.endswith("\n") or a_work.endswith("\r"):
            a_work = a_work[:-1]
        while b_work.endswith("\n") or b_work.endswith("\r"):
            b_work = b_work[:-1]

    if ignore_trailing_whitespace:
        lines_a = a_work.replace("\r\n", "\n").replace("\r", "\n").splitlines()
        lines_b = b_work.replace("\r\n", "\n").replace("\r", "\n").splitlines()
        lines_a = [la.rstrip() for la in lines_a]
        lines_b = [lb.rstrip() for lb in lines_b]
        a_work = "\n".join(lines_a)
        b_work = "\n".join(lines_b)

    if ignore_newline_style:
        a_work = a_work.replace("\r\n", "\n").replace("\r", "\n")
        b_work = b_work.replace("\r\n", "\n").replace("\r", "\n")

    if trim:
        a_work = a_work.strip()
        b_work = b_work.strip()

    raw_equal = _raw_equal(a_work, b_work)
    nfc_equal = _normalized_equal(a_work, b_work, "NFC")
    nfd_equal = _normalized_equal(a_work, b_work, "NFD")
    nfkc_equal = _normalized_equal(a_work, b_work, "NFKC")
    nfkd_equal = _normalized_equal(a_work, b_work, "NFKD")
    casefold_equal = _casefold_text(a_work) == _casefold_text(b_work)
    byte_equal = a_work.encode("utf-8") == b_work.encode("utf-8")

    lengths = {
        "a_codepoints": len(a_work),
        "b_codepoints": len(b_work),
        "a_bytes_utf8": len(a_work.encode("utf-8")),
        "b_bytes_utf8": len(b_work.encode("utf-8")),
    }

    first_diff_raw = _first_diff(a_work, b_work)
    first_difference: dict[str, Any] | None = (
        dict(first_diff_raw) if first_diff_raw is not None else None
    )
    if first_difference is not None:
        first_difference["a_visible"] = _visible_repr(
            a_work[first_difference["a_index"] : first_difference["a_index"] + 1]
        )
        first_difference["b_visible"] = _visible_repr(
            b_work[first_difference["b_index"] : first_difference["b_index"] + 1]
        )

    invisibles_a = _find_invisibles(a_work)
    invisibles_b = _find_invisibles(b_work)
    invisibles_detected = bool(invisibles_a or invisibles_b)

    classification = _classify_difference(
        raw_equal,
        nfc_equal,
        casefold_equal,
        byte_equal,
        len(a_work) != len(b_work),
        first_difference,
        invisibles_detected=invisibles_detected,
    )

    if casefold:
        equal = casefold_equal
    elif normalization == "raw":
        equal = raw_equal
    elif normalization in ("NFC", "NFD", "NFKC", "NFKD"):
        equal = _normalized_equal(a_work, b_work, normalization)
    else:
        equal = raw_equal

    return TextEqualResult(
        equal=equal,
        mode={
            "normalization": normalization,
            "casefold": casefold,
            "trim": trim,
            "ignore_newline_style": ignore_newline_style,
            "ignore_trailing_whitespace": ignore_trailing_whitespace,
            "ignore_final_newline": ignore_final_newline,
        },
        raw_equal=raw_equal,
        nfc_equal=nfc_equal,
        nfd_equal=nfd_equal,
        nfkc_equal=nfkc_equal,
        nfkd_equal=nfkd_equal,
        casefold_equal=casefold_equal,
        byte_equal=byte_equal,
        lengths=lengths,
        first_difference=first_difference,
        classification=classification,
    )


def _classify_difference(
    raw_equal: bool,
    nfc_equal: bool,
    casefold_equal: bool,
    byte_equal: bool,
    length_diff: bool,
    first_diff: dict | None,
    invisibles_detected: bool,
) -> str:
    """Classify the type of difference between two strings."""
    if raw_equal:
        return "exact_match"

    if nfc_equal:
        if byte_equal:
            return "exact_match"
        if not casefold_equal:
            return "accent_or_diacritic_difference"
        return "unicode_normalization_only"

    if casefold_equal:
        return "case_only"

    if length_diff:
        return "length_only"

    if invisibles_detected:
        return "invisible_character"

    return "ordinary_text_difference"


def _codepoint_details(s: str, start: int, end: int) -> list[dict]:
    """Get codepoint details for a span."""
    result = []
    for i in range(start, min(end, len(s))):
        char = s[i]
        result.append(
            {
                "char": char,
                "codepoint": f"U+{ord(char):04X}",
                "name": unicodedata.name(char, "<unknown>"),
            }
        )
    return result


def _truncate_diff_spans(
    spans: list[DiffInfo], max_diffs: int, max_equal_context: int = 200
) -> tuple[list[DiffInfo], bool, int]:
    """Truncate diff spans, limiting equal spans and marking truncation.

    Args:
        spans: List of DiffInfo spans.
        max_diffs: Maximum number of diff spans to return.
        max_equal_context: Maximum length for equal spans (0 to skip truncation).

    Returns:
        Tuple of (truncated_spans, truncated, total_diffs_exceeding_limit).
    """
    if len(spans) <= max_diffs:
        if max_equal_context > 0:
            truncated_spans: list[DiffInfo] = []
            for sp in spans:
                if sp["kind"] == "equal" and len(sp["a_text"]) > max_equal_context:
                    sp = DiffInfo(
                        kind="equal",
                        a_span=sp["a_span"],
                        b_span=sp["b_span"],
                        a_text=sp["a_text"][:max_equal_context] + "...",
                        b_text=sp["b_text"][:max_equal_context] + "...",
                        a_visible=sp["a_visible"],
                        b_visible=sp["b_visible"],
                        a_codepoints=sp["a_codepoints"],
                        b_codepoints=sp["b_codepoints"],
                        note=f"(truncated from {len(sp['a_text'])} chars)",
                    )
                truncated_spans.append(sp)
            return truncated_spans, False, 0
        return spans, False, 0

    return spans[:max_diffs], True, len(spans) - max_diffs


def explain_diff(
    a: str,
    b: str,
    max_diffs: int = 20,
    include_codepoints: bool = True,
    include_context: bool = True,
    detail: str = "normal",
) -> ExplainDiffResult:
    """Explain why two strings differ with detailed evidence.

    Args:
        a: First string.
        b: Second string.
        max_diffs: Maximum number of diff spans.
        include_codepoints: Include codepoint details.
        include_context: Include context in notes.
        detail: "summary", "normal", or "full".

    Returns:
        Detailed diff explanation with classification and agent instruction.
    """
    if len(a) > MAX_TEXT_LENGTH or len(b) > MAX_TEXT_LENGTH:
        raise ValueError(f"Input exceeds MAX_TEXT_LENGTH {MAX_TEXT_LENGTH}")

    if detail == "summary":
        max_diffs_to_use = min(max_diffs, 5)
        max_equal_context = 50
    elif detail == "full":
        max_diffs_to_use = max_diffs
        max_equal_context = 0
    else:
        max_diffs_to_use = max_diffs
        max_equal_context = 200

    raw_equal = _raw_equal(a, b)
    nfc_equal = _normalized_equal(a, b, "NFC")
    nfkc_equal = _normalized_equal(a, b, "NFKC")
    casefold_equal = _casefold_text(a) == _casefold_text(b)
    byte_equal = a.encode("utf-8") == b.encode("utf-8")

    same_length_codepoints = len(a) == len(b)
    edit_distance = _levenshtein_distance(a, b) if not raw_equal else 0
    prefix_suffix = _common_prefix_suffix(a, b)

    a_metrics = {
        "bytes_utf8": len(a.encode("utf-8")),
        "codepoints": len(a),
    }
    b_metrics = {
        "bytes_utf8": len(b.encode("utf-8")),
        "codepoints": len(b),
    }

    diffs_raw = _diff_spans(a, b, max_diffs=max_diffs_to_use)
    diffs: list[DiffInfo] = []

    invisibles_a = _find_invisibles(a)
    invisibles_b = _find_invisibles(b)
    invisibles_detected = bool(invisibles_a or invisibles_b)
    confusables_a = _detect_confusables(a)
    confusables_b = _detect_confusables(b)

    classification = _classify_difference(
        raw_equal,
        nfc_equal,
        casefold_equal,
        byte_equal,
        not same_length_codepoints,
        None,
        invisibles_detected,
    )

    if classification == "ordinary_text_difference" and nfkc_equal:
        classification = "compatibility_normalization_only"

    security_findings: list[dict] = []
    if invisibles_a or invisibles_b:
        security_findings.append(
            {
                "kind": "invisible_characters",
                "a_count": len(invisibles_a),
                "b_count": len(invisibles_b),
            }
        )
    if confusables_a or confusables_b:
        security_findings.append(
            {
                "kind": "confusables",
                "a_count": len(confusables_a),
                "b_count": len(confusables_b),
            }
        )

    for d in diffs_raw:
        a_start, a_end = d["a_span"]
        b_start, b_end = d["b_span"]

        a_text = d["a_text"]
        b_text = d["b_text"]

        note = ""
        if d["kind"] == "equal":
            note = "Matching text"
        elif len(a_text) != len(b_text):
            note = f"Length difference: {len(a_text)} vs {len(b_text)} codepoints"
        elif nfc_equal:
            note = "Different raw codepoints, equal after NFC normalization"
        else:
            note = "Different codepoints"

        diff_info = DiffInfo(
            kind=d["kind"],
            a_span=d["a_span"],
            b_span=d["b_span"],
            a_text=a_text,
            b_text=b_text,
            a_visible=_visible_repr(a_text),
            b_visible=_visible_repr(b_text),
            a_codepoints=_codepoint_details(a, a_start, a_end) if include_codepoints else [],
            b_codepoints=_codepoint_details(b, b_start, b_end) if include_codepoints else [],
            note=note,
        )
        diffs.append(diff_info)

        if not classification or classification == "exact_match":
            if d["kind"] == "replace":
                classification = "ordinary_text_difference"

    diffs, truncated, omitted_count = _truncate_diff_spans(
        diffs, max_diffs_to_use, max_equal_context
    )

    agent_instruction = _generate_agent_instruction(
        classification, raw_equal, nfc_equal, byte_equal
    )

    limits_applied: list[str] = []
    if truncated:
        limits_applied.append(f"max_diffs={max_diffs_to_use}")

    return ExplainDiffResult(
        equal=raw_equal,
        classification=classification,
        summary={
            "raw_equal": raw_equal,
            "byte_equal": byte_equal,
            "nfc_equal": nfc_equal,
            "nfkc_equal": nfkc_equal,
            "casefold_equal": casefold_equal,
            "same_length_codepoints": same_length_codepoints,
            "edit_distance": edit_distance,
            "common_prefix_len": prefix_suffix["common_prefix_len"],
            "common_suffix_len": prefix_suffix["common_suffix_len"],
            "truncated": truncated,
            "max_diffs_applied": max_diffs_to_use,
        },
        a_metrics=a_metrics,
        b_metrics=b_metrics,
        diffs=diffs,
        security_findings=security_findings,
        agent_instruction=agent_instruction,
    )


def _generate_agent_instruction(
    classification: str, raw_equal: bool, nfc_equal: bool, byte_equal: bool
) -> str:
    """Generate agent-facing instruction based on classification."""
    if raw_equal:
        return "Strings are identical."
    if classification == "unicode_normalization_only":
        return "Treat these strings as equivalent only if NFC normalization is acceptable. They are not byte-identical."
    if classification == "case_only":
        return (
            "Strings differ only by case. Case-insensitive comparison should treat them as equal."
        )
    if classification == "accent_or_diacritic_difference":
        return "Strings differ by accents or diacritics only (same letters, different marks). NFC normalization will make them equal."
    if classification == "compatibility_normalization_only":
        return "Strings differ in compatibility normalization (NFKC). Treat as equivalent if compatibility normalization is acceptable."
    if not byte_equal:
        return "Strings are not byte-identical and differ in Unicode normalization. Choose appropriate normalization for your use case."
    return "Strings differ. Review diff details for specifics."


MAX_INSPECT_ITEMS = 100


def inspect_text(
    text: str,
    include_codepoints: bool = True,
    include_confusables: bool = True,
    detail: str = "normal",
    normalize: str = "none",
    compare_normalized: bool = False,
) -> InspectTextResult:
    """Inspect text for hidden characters, confusables, and Unicode signals.

    Args:
        text: Input string.
        include_codepoints: Include codepoint details in invisibles.
        include_confusables: Check for confusables.
        detail: "summary", "normal", or "full".
        normalize: Normalization form to analyze ("none", "NFC", "NFD", "NFKC", "NFKD").
        compare_normalized: If True, report both original and normalized analysis.

    Returns:
        Complete text inspection with safe representation.
    """
    if len(text) > MAX_TEXT_LENGTH:
        raise ValueError(f"Input length {len(text)} exceeds MAX_TEXT_LENGTH {MAX_TEXT_LENGTH}")

    if detail == "summary":
        max_items = 10
    elif detail == "full":
        max_items = MAX_INSPECT_ITEMS
    else:
        max_items = MAX_INSPECT_ITEMS

    metrics = measure_text(text)
    all_invisibles = _find_invisibles(text)

    bidi_controls: list[InvisibleCharInfo] = []
    invisibles_truncated: list[InvisibleCharInfo] = []
    for inv in all_invisibles:
        if "BIDI" in inv.get("display", ""):
            bidi_controls.append(inv)
        else:
            invisibles_truncated.append(inv)

    scripts = _detect_mixed_scripts(text)
    all_confusables = _detect_confusables(text) if include_confusables else []

    limits_applied: list[str] = []
    invisibles = invisibles_truncated
    confusables = all_confusables
    if len(invisibles) > max_items:
        invisibles = invisibles[:max_items]
        limits_applied.append(f"invisibles_limited={max_items}")
    if len(confusables) > max_items:
        confusables = confusables[:max_items]
        limits_applied.append(f"confusables_limited={max_items}")

    safe_repr = _visible_repr(text)

    warnings: list[dict] = []
    for inv in invisibles:
        warnings.append(
            {
                "severity": "warning",
                "kind": "invisible_character",
                "message": f"Text contains {inv['name']} at index {inv['index']}",
                "codepoint": inv["codepoint"],
            }
        )
    for bc in bidi_controls:
        warnings.append(
            {
                "severity": "danger",
                "kind": "bidi_control",
                "message": f"Text contains bidirectional control character {bc['name']} at index {bc['index']}",
                "codepoint": bc["codepoint"],
            }
        )
    if metrics["unicode_risks"]["mixed_scripts"]:
        warnings.append(
            {
                "severity": "info",
                "kind": "mixed_scripts",
                "message": f"Text contains mixed scripts: {', '.join(metrics['unicode_risks']['scripts'])}",
            }
        )
    for conf in confusables:
        warnings.append(
            {
                "severity": "warning",
                "kind": "confusable",
                "message": f"Text contains confusable character '{conf['char']}' (looks like '{conf['confusable_with']}')",
                "codepoint": f"U+{ord(conf['char']):04X}",
            }
        )

    limits_applied_info: list[str] = []
    total_invisibles_omitted = len(all_invisibles) - len(invisibles)
    total_bidi_omitted = len(bidi_controls) - len([b for b in bidi_controls if b in warnings])
    total_confusables_omitted = len(all_confusables) - len(confusables)
    if total_invisibles_omitted > 0:
        limits_applied_info.append(f"invisibles_omitted={total_invisibles_omitted}")
    if total_confusables_omitted > 0:
        limits_applied_info.append(f"confusables_omitted={total_confusables_omitted}")

    if limits_applied_info and detail == "summary":
        for msg in limits_applied_info:
            warnings.append(
                {
                    "severity": "info",
                    "kind": "limits_applied",
                    "message": msg,
                }
            )
            limits_applied.append(msg)

    nfc_text = _normalize_unicode(text, "NFC")
    normalization_diff = text != nfc_text

    original_analysis: dict[str, Any] = {
        "safe_repr": safe_repr,
        "confusables": confusables,
        "invisibles": invisibles,
    }

    normalized_analysis: InspectTextNormalized | None = None
    normalization_findings: list[NormalizationFinding] = []

    if normalize != "none" and compare_normalized:
        norm_text = _normalize_unicode(text, normalize)
        norm_safe_repr = _visible_repr(norm_text)
        norm_changed = text != norm_text

        diff_entries: list[dict] = []
        if norm_changed:
            for i, (c1, c2) in enumerate(zip(text, norm_text)):
                if c1 != c2:
                    diff_entries.append(
                        {
                            "index": i,
                            "original": c1,
                            "normalized": c2,
                            "original_codepoint": f"U+{ord(c1):04X}",
                            "normalized_codepoint": f"U+{ord(c2):04X}",
                        }
                    )

        if normalize == "NFKC":
            normalization_findings.append(
                NormalizationFinding(
                    kind="compatibility_fold", message="NFKC changes fullwidth character to ASCII"
                )
            )
        elif normalize == "NFC":
            if norm_changed:
                normalization_findings.append(
                    NormalizationFinding(
                        kind="canonical_composition", message="NFC composes combining characters"
                    )
                )
        elif normalize == "NFD":
            if norm_changed:
                normalization_findings.append(
                    NormalizationFinding(
                        kind="canonical_decomposition", message="NFD decomposes combined characters"
                    )
                )
        elif normalize == "NFKD":
            normalization_findings.append(
                NormalizationFinding(
                    kind="compatibility_decomposition",
                    message="NFKD decomposes and converts compatibility characters",
                )
            )

        normalized_analysis = InspectTextNormalized(
            form=normalize,
            text=norm_text,
            safe_repr=norm_safe_repr,
            changed=norm_changed,
            diff=diff_entries,
        )

    return InspectTextResult(
        safe_repr=safe_repr,
        metrics=metrics,
        normalization={
            "is_nfc": metrics["normalization"]["is_nfc"],
            "is_nfkc": metrics["normalization"]["is_nfkc"],
        },
        normalization_diff=normalization_diff,
        normals_repr=nfc_text if normalization_diff else None,
        invisibles=invisibles,
        bidi_controls=bidi_controls,
        mixed_scripts=scripts,
        confusables=confusables,
        warnings=warnings,
        limits_applied=limits_applied + limits_applied_info,
        normalize=normalize,
        compare_normalized=compare_normalized,
        original=original_analysis,
        normalized=normalized_analysis,
        normalization_findings=normalization_findings,
    )


def count_chars(
    text: str,
    target: str | None = None,
    normalization: str = "raw",
    count_mode: str = "codepoint",
) -> CountCharsResult | dict[str, int]:
    """Count character occurrences or return frequency table.

    Args:
        text: Input string.
        target: Single character to count (None for frequency table).
        normalization: "raw", "NFC", or "NFKC".
        count_mode: "codepoint", "grapheme", "byte", or "substring".

    Returns:
        Counting result or frequency table if target is None.
    """
    if len(text) > MAX_TEXT_LENGTH:
        raise ValueError(f"Input length {len(text)} exceeds MAX_TEXT_LENGTH {MAX_TEXT_LENGTH}")

    valid_modes = {"codepoint", "grapheme", "byte", "substring"}
    if count_mode not in valid_modes:
        raise ValueError(f"Invalid count_mode: {count_mode}. Use one of: {', '.join(valid_modes)}")

    if normalization != "raw":
        text = _normalize_unicode(text, normalization)

    if target is not None and len(target) != 1 and count_mode != "substring":
        raise ValueError("target must be a single character")

    if count_mode == "byte":
        target_bytes = target.encode("utf-8") if target else None
        text_bytes = text.encode("utf-8")
        if target is None:
            freq: dict[str, int] = {}
            for byte_seq in set(text_bytes):
                freq[chr(byte_seq)] = text_bytes.count(byte_seq)
            return freq
        assert target_bytes is not None
        positions = [
            i
            for i in range(len(text_bytes))
            if text_bytes[i : i + len(target_bytes)] == target_bytes
        ]
        return CountCharsResult(
            target=target,
            normalization=normalization,
            count=len(positions),
            positions=positions,
            text_length_codepoints=len(text),
        )
    elif count_mode == "grapheme":
        grapheme_text = list(text)
        if target is None:
            freq_grapheme: dict[str, int] = {}
            for g in grapheme_text:
                freq_grapheme[g] = freq_grapheme.get(g, 0) + 1
            return freq_grapheme
        target_grapheme = list(target)[0] if target else None
        positions = [i for i, g in enumerate(grapheme_text) if g == target_grapheme]
        return CountCharsResult(
            target=target,
            normalization=normalization,
            count=len(positions),
            positions=positions,
            text_length_codepoints=_count_graphemes(text),
        )
    elif count_mode == "substring" and target is not None:
        positions = []
        start = 0
        while start < len(text):
            idx = text.find(target, start)
            if idx == -1:
                break
            positions.append(idx)
            start = idx + 1
        return CountCharsResult(
            target=target,
            normalization=normalization,
            count=len(positions),
            positions=positions,
            text_length_codepoints=len(text),
        )
    else:
        if target is None:
            freq_char: dict[str, int] = {}
            for char in text:
                freq_char[char] = freq_char.get(char, 0) + 1
            return freq_char

        positions = [i for i, c in enumerate(text) if c == target]

        return CountCharsResult(
            target=target,
            normalization=normalization,
            count=len(positions),
            positions=positions,
            text_length_codepoints=len(text),
        )


def list_compare(
    a: list[str],
    b: list[str],
    ignore_order: bool = True,
    casefold: bool = False,
    normalization: str = "NFC",
    trim: bool = False,
    treat_as_multiset: bool = True,
    include_near_matches: bool = False,
    near_match_threshold: int = 2,
) -> ListCompareResult:
    """Compare two lists with optional ignore_order, casefold, normalization.

    Args:
        a: First list.
        b: Second list.
        ignore_order: If True, compare as sets. (legacy, use mode instead)
        casefold: If True, casefold elements before comparison.
        normalization: Unicode normalization form.
        trim: If True, trim whitespace from each element.
        treat_as_multiset: If True, ignore duplicates when comparing sets.
                          If False, duplicate counts matter for equality.
        include_near_matches: If True, include near matches (fuzzy matching).
        near_match_threshold: Maximum edit distance for near matches.

    Returns:
        ListCompareResult with same_ordered, same_unordered, only_in_a,
        only_in_b, duplicates_a, duplicates_b, near_matches.
    """

    def transform(s: str) -> str:
        result = s
        if trim:
            result = result.strip()
        if normalization != "raw":
            result = _normalize_unicode(result, normalization)
        if casefold:
            result = _casefold_text(result)
        return result

    a_transformed = [transform(x) for x in a]
    b_transformed = [transform(x) for x in b]

    a_set = set(a_transformed)
    b_set = set(b_transformed)

    if treat_as_multiset:
        only_in_a = [a[i] for i, x in enumerate(a_transformed) if x not in b_set]
        only_in_b = [b[i] for i, x in enumerate(b_transformed) if x not in a_set]
    else:
        a_counts: dict[str, int] = {}
        b_counts: dict[str, int] = {}
        for x in a_transformed:
            a_counts[x] = a_counts.get(x, 0) + 1
        for x in b_transformed:
            b_counts[x] = b_counts.get(x, 0) + 1
        only_in_a = [
            a[i] for i, x in enumerate(a_transformed) if a_counts.get(x, 0) > b_counts.get(x, 0)
        ]
        only_in_b = [
            b[i] for i, x in enumerate(b_transformed) if b_counts.get(x, 0) > a_counts.get(x, 0)
        ]

    from collections import Counter

    a_counter = Counter(a_transformed)
    b_counter = Counter(b_transformed)
    duplicates_a = [x for x, c in a_counter.items() if c > 1]
    duplicates_b = [x for x, c in b_counter.items() if c > 1]

    near_matches: list[ListCompareNearMatch] = []
    seen_pairs: set[tuple[str, str]] = set()
    if include_near_matches and near_match_threshold > 0:
        for i, (a_item, a_t) in enumerate(zip(a, a_transformed, strict=True)):
            for j, b_t in enumerate(b_transformed):
                if a_t == b_t:
                    continue
                dist = _levenshtein_distance(a_t, b_t)
                if 0 < dist <= near_match_threshold:
                    b_item = b[j]
                    pair = (a_item, b_item) if a_item <= b_item else (b_item, a_item)
                    if pair not in seen_pairs:
                        seen_pairs.add(pair)
                        near_matches.append(
                            ListCompareNearMatch(
                                a=a_item,
                                b=b_item,
                                distance=dist,
                                classification="fuzzy",
                            )
                        )
                    break

    same_ordered = ignore_order or (a_transformed == b_transformed)
    same_unordered = (treat_as_multiset and a_set == b_set) or (
        not treat_as_multiset and a_counter == b_counter
    )

    return ListCompareResult(
        same_ordered=same_ordered,
        same_unordered=same_unordered,
        only_in_a=only_in_a,
        only_in_b=only_in_b,
        duplicates_a=duplicates_a,
        duplicates_b=duplicates_b,
        near_matches=near_matches,
    )


class TextWindowPosition(TypedDict):
    """Position information in text_window."""

    byte_offset: int
    codepoint_index: int
    grapheme_index: int
    line: int
    column: int


class TextWindowResult(TypedDict):
    """Result of text_window operation."""

    position: TextWindowPosition
    line_text: str
    line_visible_repr: str
    before: list[dict]
    after: list[dict]
    newline_style: str
    at_codepoint: dict | None
    warnings: list[str]


def text_window(
    text: str,
    position: dict,
    context_lines: int = 2,
    include_visible_repr: bool = True,
) -> TextWindowResult:
    """Get a window around a position in text with context lines.

    Shows the line at the given position with surrounding context lines.

    Args:
        text: Input string.
        position: Dict with kind (byte_offset/codepoint_index/grapheme_index/line_column)
                  and value (numeric) or line/column for line_column kind.
        context_lines: Number of lines before and after to return.
        include_visible_repr: Include visible representation of the line.

    Returns:
        Dictionary with position info, line_text, before/after context,
        newline_style, at_codepoint info, and warnings.
    """
    from .primitives import (
        byte_offset_to_codepoint_index as _byte_to_cp,
    )
    from .primitives import (
        codepoint_index_to_byte_offset as _cp_to_byte,
    )
    from .primitives import (
        codepoint_index_to_line_column as _cp_to_line_col,
    )
    from .primitives import (
        count_graphemes as _count_graphemes,
    )
    from .primitives import (
        detect_newline_style as _detect_newline,
    )
    from .primitives import (
        get_line_text as _get_line_text,
    )
    from .primitives import (
        get_surrounding_lines as _get_surrounding,
    )
    from .primitives import (
        utf8_bytes as _utf8_bytes,
    )
    from .primitives import (
        visible_repr as _visible_repr,
    )

    warnings: list[str] = []

    kind = position.get("kind", "codepoint_index")
    line_base = position.get("line_base", 1)
    column_base = position.get("column_base", 1)

    n = len(text)
    codepoint_index: int | None = None

    if kind == "byte_offset":
        byte_offset = position.get("value", position.get("byte_offset"))
        if not isinstance(byte_offset, int):
            raise ValueError(f"Invalid byte offset: {byte_offset}")
        try:
            codepoint_index = _byte_to_cp(text, byte_offset)
        except ValueError as e:
            raise ValueError(f"Invalid byte offset: {e}")

    elif kind == "codepoint_index":
        codepoint_index = position.get("value", position.get("codepoint_index"))
        if not isinstance(codepoint_index, int):
            raise ValueError(f"Invalid codepoint index: {codepoint_index}")
        if codepoint_index < 0 or codepoint_index > len(text):
            raise ValueError(f"Codepoint index {codepoint_index} out of range (0-{len(text)})")

    elif kind == "grapheme_index":
        grapheme_index = position.get("value", position.get("grapheme_index"))
        if not isinstance(grapheme_index, int):
            raise ValueError(f"Invalid grapheme index: {grapheme_index}")
        grapheme_count = _count_graphemes(text)
        if grapheme_index < 0 or grapheme_index > grapheme_count:
            raise ValueError(f"Grapheme index {grapheme_index} out of range (0-{grapheme_count})")
        target_grapheme = 0
        i = 0
        n = len(text)
        while i < n:
            if target_grapheme == grapheme_index:
                codepoint_index = i
                break
            target_grapheme += 1
            i += 1
            while i < n:
                cp = ord(text[i])
                from .primitives import _is_extend_char, _is_extended_pictographic

                if _is_extend_char(text[i]):
                    i += 1
                    continue
                if cp == 0x200D:
                    i += 1
                    if i < n and _is_extended_pictographic(text[i]):
                        i += 1
                    continue
                if 0x1F1E6 <= cp <= 0x1F1FF:
                    if i + 1 < n and 0x1F1E6 <= ord(text[i + 1]) <= 0x1F1FF:
                        i += 2
                        continue
                    i += 1
                    continue
                break
        if codepoint_index is None:
            codepoint_index = len(text)

    elif kind == "line_column":
        line = position.get("line", position.get("value"))
        column = position.get("column")
        if line is None or column is None:
            raise ValueError("line_column position requires line and column")
        from .primitives import line_column_to_codepoint_index as _lc_to_cp

        try:
            codepoint_index = _lc_to_cp(text, line, column, line_base, column_base)
        except ValueError as e:
            raise ValueError(f"Invalid line/column: {e}")

    else:
        raise ValueError(f"Unknown position kind: {kind}")

    assert codepoint_index is not None

    line_num, column_num = _cp_to_line_col(text, codepoint_index, 1, 1)

    byte_offset = _cp_to_byte(text, codepoint_index)

    grapheme_idx = 0
    i = 0
    while i < codepoint_index:
        grapheme_idx += 1
        i += 1
        while i < codepoint_index:
            from .primitives import _is_extend_char, _is_extended_pictographic

            if _is_extend_char(text[i]):
                i += 1
                continue
            cp = ord(text[i])
            if cp == 0x200D:
                i += 1
                if i < n and _is_extended_pictographic(text[i]):
                    i += 1
                continue
            if 0x1F1E6 <= cp <= 0x1F1FF:
                if i + 1 < n and 0x1F1E6 <= ord(text[i + 1]) <= 0x1F1FF:
                    i += 2
                    continue
                i += 1
                continue
            break
    grapheme_index = grapheme_idx

    line_text = _get_line_text(text, line_num, 1)
    line_visible = _visible_repr(line_text) if include_visible_repr else ""

    newline_style = _detect_newline(text)

    before_lines, after_lines = _get_surrounding(text, line_num, context_lines, 1)

    before = [{"line": ln, "text": txt} for ln, txt in before_lines]
    after = [{"line": ln, "text": txt} for ln, txt in after_lines]

    at_codepoint = None
    if codepoint_index < len(text):
        char = text[codepoint_index]
        import unicodedata

        codepoint_str = f"U+{ord(char):04X}"
        name = unicodedata.name(char, "<unknown>")
        category = unicodedata.category(char)
        at_codepoint = {
            "char": char,
            "codepoint": codepoint_str,
            "name": name,
            "category": category,
        }

    if byte_offset < len(_utf8_bytes(text)):
        b = text.encode("utf-8")[byte_offset]
        if b >= 0x80 and b < 0xC0:
            warnings.append(
                "Position falls in middle of multi-byte sequence (byte is continuation byte)"
            )

    return TextWindowResult(
        position={
            "byte_offset": byte_offset,
            "codepoint_index": codepoint_index,
            "grapheme_index": grapheme_index,
            "line": line_num,
            "column": column_num,
        },
        line_text=line_text,
        line_visible_repr=line_visible,
        before=before,
        after=after,
        newline_style=newline_style,
        at_codepoint=at_codepoint,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# text_replace_check
# ---------------------------------------------------------------------------

MAX_PREVIEW_CHARS = 2000


class TextReplaceCheckResult(TypedDict):
    """Result of text_replace_check."""

    match_count: int
    unique_match: bool
    expected_count_met: bool
    would_change: bool
    positions: list[dict[str, int]]
    changed_text_fingerprint: str
    newline_style_before: str
    newline_style_after: str
    preview_before: str
    preview_after: str
    findings: list[dict[str, str]]


def text_replace_check(
    text: str,
    old: str,
    new: str,
    mode: str = "exact",
    expected_count: int | None = None,
    allow_multiple: bool = False,
    newline_policy: str = "preserve",
    return_preview: bool = False,
    max_preview_chars: int = MAX_PREVIEW_CHARS,
) -> TextReplaceCheckResult:
    """Check whether a replacement would apply cleanly before editing.

    Args:
        text: Source text.
        old: Text to find.
        new: Replacement text.
        mode: Matching mode (exact, nfc, nfkc, casefold, whitespace_collapse).
        expected_count: Expected number of matches (optional).
        allow_multiple: If False and more than one match, add a finding.
        newline_policy: How to handle newlines (preserve, normalize_lf, normalize_crlf).
        return_preview: If True, include before/after previews.
        max_preview_chars: Maximum characters in preview output.

    Returns:
        TextReplaceCheckResult with match info, positions, and findings.
    """
    if len(text) > MAX_TEXT_LENGTH:
        raise ValueError(f"Input length {len(text)} exceeds MAX_TEXT_LENGTH {MAX_TEXT_LENGTH}")

    valid_modes = {"exact", "nfc", "nfkc", "casefold", "whitespace_collapse"}
    if mode not in valid_modes:
        raise ValueError(f"Invalid mode: {mode}. Use one of: {', '.join(valid_modes)}")

    valid_newline = {"preserve", "normalize_lf", "normalize_crlf"}
    if newline_policy not in valid_newline:
        raise ValueError(
            f"Invalid newline_policy: {newline_policy}. Use one of: {', '.join(valid_newline)}"
        )

    if max_preview_chars < 0:
        raise ValueError("max_preview_chars must be non-negative")

    import hashlib

    from .primitives import (
        codepoint_index_to_line_column as _cp_to_line_col,
    )
    from .primitives import (
        detect_newline_style as _detect_newline_fn,
    )

    findings: list[dict[str, str]] = []

    # Prepare text and old for matching based on mode
    def _normalize_for_match(s: str, m: str) -> str:
        if m == "nfc":
            return _normalize_unicode(s, "NFC")
        elif m == "nfkc":
            return _normalize_unicode(s, "NFKC")
        elif m == "casefold":
            return _casefold_text(s)
        elif m == "whitespace_collapse":
            return re.sub(r"\s+", " ", s)
        return s

    text_norm = _normalize_for_match(text, mode)
    old_norm = _normalize_for_match(old, mode)

    def _norm_offset_to_orig(norm_idx: int) -> int:
        """Map a codepoint offset in text_norm back to an offset in text.

        For modes that alter codepoint count (NFC/NFKC compose or expand;
        casefold expansion; whitespace collapse), the normalized and original
        indices do not coincide. We walk the original text codepoint by
        codepoint, tracking how many normalized codepoints the prefix produces.
        """
        if norm_idx <= 0:
            return 0
        norm_total = len(text_norm)
        if norm_idx >= norm_total:
            return len(text)
        if mode == "exact":
            return min(norm_idx, len(text))
        if mode == "whitespace_collapse":
            out_pos = 0
            prev_was_ws = False
            last_ok = 0
            for orig_i, ch in enumerate(text):
                is_ws = ch.isspace()
                if is_ws:
                    if not prev_was_ws:
                        out_pos += 1
                else:
                    out_pos += 1
                if out_pos > norm_idx:
                    return last_ok
                last_ok = orig_i + 1
                prev_was_ws = is_ws
            return last_ok
        # nfc / nfkc / casefold: progressive prefix normalization.
        prev_norm = ""
        last_ok = 0
        for i, ch in enumerate(text):
            new_norm = _normalize_for_match(prev_norm + ch, mode)
            new_len = len(new_norm)
            if new_len > norm_idx:
                return last_ok
            last_ok = i + 1
            prev_norm = new_norm
        return last_ok

    # Find all matches (non-overlapping)
    positions: list[dict[str, int]] = []
    search_start = 0
    while search_start <= len(text_norm):
        idx = text_norm.find(old_norm, search_start)
        if idx == -1:
            break
        orig_idx = _norm_offset_to_orig(idx)
        orig_end = _norm_offset_to_orig(idx + len(old_norm))
        match_codepoint_length = orig_end - orig_idx
        byte_start = len(text[:orig_idx].encode("utf-8"))
        byte_end = len(text[:orig_end].encode("utf-8"))
        cp_line, cp_col = _cp_to_line_col(text, orig_idx, 1, 1)
        positions.append(
            {
                "codepoint_index": orig_idx,
                "byte_start": byte_start,
                "byte_end": byte_end,
                "line": cp_line,
                "column": cp_col,
                "match_codepoint_length": match_codepoint_length,
            }
        )
        search_start = idx + len(old_norm) if len(old_norm) > 0 else idx + 1

    match_count = len(positions)
    unique_match = match_count == 1
    would_change = match_count > 0

    # Expected count check
    expected_count_met = True
    if expected_count is not None:
        if match_count != expected_count:
            expected_count_met = False
            if match_count == 0:
                findings.append(
                    {
                        "kind": "no_match",
                        "message": f"Expected {expected_count} match(es) but found 0",
                    }
                )
            else:
                findings.append(
                    {
                        "kind": "count_mismatch",
                        "message": f"Expected {expected_count} match(es) but found {match_count}",
                    }
                )

    # Ambiguity warning
    if not allow_multiple and match_count > 1:
        findings.append(
            {
                "kind": "ambiguous_replacement",
                "message": f"Found {match_count} matches but allow_multiple is false; replacement is ambiguous",
            }
        )

    if match_count == 0:
        findings.append(
            {
                "kind": "no_match",
                "message": "No matches found; replacement would not change text",
            }
        )

    # Build changed text for fingerprinting and preview
    if would_change:
        if mode in ("nfc", "nfkc", "casefold"):
            # Rebuild from original so the surrounding codepoints are preserved
            parts = []
            last = 0
            for pos in positions:
                orig_idx = pos["codepoint_index"]
                parts.append(text[last:orig_idx])
                parts.append(new)
                last = orig_idx + pos["match_codepoint_length"]
            parts.append(text[last:])
            changed_text = "".join(parts)
        elif mode == "whitespace_collapse":
            changed_text = re.sub(r"\s+", " ", text).replace(re.sub(r"\s+", " ", old), new)
        else:
            changed_text = text_norm.replace(old_norm, new)
    else:
        changed_text = text

    # Compute fingerprints
    before_fp = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    after_fp = hashlib.sha256(changed_text.encode("utf-8")).hexdigest()[:16]

    # Newline style detection
    newline_before = _detect_newline_fn(text)
    newline_after = _detect_newline_fn(changed_text)

    # Previews
    preview_before = ""
    preview_after = ""
    if return_preview:
        cap = min(max_preview_chars, MAX_PREVIEW_CHARS)
        preview_before = text[:cap]
        preview_after = changed_text[:cap]
        if len(text) > cap:
            findings.append(
                {
                    "kind": "preview_truncated",
                    "message": f"Preview before truncated at {cap} characters",
                }
            )
        if len(changed_text) > cap:
            findings.append(
                {
                    "kind": "preview_truncated",
                    "message": f"Preview after truncated at {cap} characters",
                }
            )

    return TextReplaceCheckResult(
        match_count=match_count,
        unique_match=unique_match,
        expected_count_met=expected_count_met,
        would_change=would_change,
        positions=positions,
        changed_text_fingerprint=after_fp,
        newline_style_before=newline_before,
        newline_style_after=newline_after,
        preview_before=preview_before,
        preview_after=preview_after,
        findings=findings,
    )


# ---------------------------------------------------------------------------
# line_range_extract
# ---------------------------------------------------------------------------


class LineRangeExtractResult(TypedDict):
    """Result of line_range_extract."""

    line_count_total: int
    start_line: int
    end_line: int
    valid_range: bool
    text: str
    lines: list[dict[str, Any]]
    byte_start: int
    byte_end: int
    char_start: int
    char_end: int
    newline_style: str
    ends_with_newline: bool
    fingerprint: str
    findings: list[dict[str, str]]


def line_range_extract(
    text: str,
    start_line: int,
    end_line: int,
    line_base: int = 1,
    include_line_numbers: bool = False,
    include_fingerprint: bool = True,
) -> LineRangeExtractResult:
    """Extract exact line ranges and return stable offsets/fingerprints.

    Args:
        text: Input string.
        start_line: First line to extract.
        end_line: Last line to extract (inclusive).
        line_base: Base for line numbers (1 for 1-based, 0 for 0-based).
        include_line_numbers: If True, include line number in each line dict.
        include_fingerprint: If True, compute SHA-256 fingerprint.

    Returns:
        LineRangeExtractResult with extracted text, offsets, and metadata.
    """
    if len(text) > MAX_TEXT_LENGTH:
        raise ValueError(f"Input length {len(text)} exceeds MAX_TEXT_LENGTH {MAX_TEXT_LENGTH}")

    if start_line > end_line:
        raise ValueError(f"start_line ({start_line}) must be <= end_line ({end_line})")

    import hashlib

    from .primitives import (
        detect_newline_style as _detect_newline_lr,
    )

    findings: list[dict[str, str]] = []

    # Split text into lines (preserving content)
    lines_raw = text.split("\n")
    # Remove trailing empty if text ends with newline
    if text.endswith("\n"):
        total_lines = len(lines_raw) - 1  # last element is empty
    else:
        total_lines = len(lines_raw)

    if total_lines == 0:
        total_lines = 1  # Empty text still has line 1

    # Convert to 1-based for comparison
    start_1based = start_line + (1 - line_base)
    end_1based = end_line + (1 - line_base)

    valid_range = True
    if start_1based < 1:
        valid_range = False
        findings.append(
            {
                "kind": "out_of_range",
                "message": f"start_line {start_line} is before the first line",
            }
        )
    if end_1based > total_lines:
        valid_range = False
        findings.append(
            {
                "kind": "out_of_range",
                "message": f"end_line {end_line} exceeds total lines ({total_lines})",
            }
        )

    if not valid_range:
        # Clamp to valid range
        start_1based = max(1, start_1based)
        end_1based = min(total_lines, end_1based)

    # Compute byte/char offsets for the line range
    # Find start of start_line
    char_start = 0
    current_line = 1
    for i, ch in enumerate(text):
        if current_line == start_1based:
            char_start = i
            break
        if ch == "\n":
            current_line += 1
    else:
        # start_line not found, use end of text
        char_start = len(text)

    # Find end of end_line (exclusive, up to and including newline if present)
    char_end = len(text)
    current_line = 1
    found_start = False
    for i, ch in enumerate(text):
        if current_line == start_1based and not found_start:
            found_start = True
        if ch == "\n":
            if current_line == end_1based:
                char_end = i + 1  # include the newline
                break
            current_line += 1

    # Ensure char_end is at least char_start
    if char_end < char_start:
        char_end = char_start

    byte_start = len(text[:char_start].encode("utf-8"))
    byte_end = len(text[:char_end].encode("utf-8"))

    # Extract lines
    extracted_lines: list[dict[str, Any]] = []
    extracted_text_parts: list[str] = []
    for i in range(start_1based - 1, min(end_1based, len(lines_raw))):
        line_text = lines_raw[i] if i < len(lines_raw) else ""
        line_dict: dict[str, Any] = {"text": line_text}
        if include_line_numbers:
            line_dict["line"] = i + line_base
        extracted_lines.append(line_dict)
        extracted_text_parts.append(line_text)

    extracted_text = "\n".join(extracted_text_parts)

    # Fingerprint
    fingerprint = ""
    if include_fingerprint:
        fingerprint = hashlib.sha256(extracted_text.encode("utf-8")).hexdigest()[:16]

    newline_style = _detect_newline_lr(text)
    ends_with_newline = text.endswith("\n")

    return LineRangeExtractResult(
        line_count_total=total_lines,
        start_line=start_line,
        end_line=end_line,
        valid_range=valid_range,
        text=extracted_text,
        lines=extracted_lines,
        byte_start=byte_start,
        byte_end=byte_end,
        char_start=char_start,
        char_end=char_end,
        newline_style=newline_style,
        ends_with_newline=ends_with_newline,
        fingerprint=fingerprint,
        findings=findings,
    )


# ---------------------------------------------------------------------------
# line_range_compare
# ---------------------------------------------------------------------------


class LineRangeCompareResult(TypedDict):
    """Result of line_range_compare."""

    equal: bool
    left_fingerprint: str
    right_fingerprint: str
    diff_summary: str
    first_difference: dict[str, Any] | None


def line_range_compare(
    left_text: str,
    right_text: str,
    start_line: int,
    end_line: int,
    line_base: int = 1,
    comparison_mode: str = "exact",
) -> LineRangeCompareResult:
    """Compare a line range from two text inputs.

    Args:
        left_text: First text input.
        right_text: Second text input.
        start_line: First line to compare.
        end_line: Last line to compare (inclusive).
        line_base: Base for line numbers.
        comparison_mode: "exact", "ignore_trailing_whitespace", or "normalize_newlines".

    Returns:
        LineRangeCompareResult with equality, fingerprints, and diff info.
    """
    for label, t in [("left_text", left_text), ("right_text", right_text)]:
        if len(t) > MAX_TEXT_LENGTH:
            raise ValueError(f"{label} length {len(t)} exceeds MAX_TEXT_LENGTH {MAX_TEXT_LENGTH}")

    valid_modes = {"exact", "ignore_trailing_whitespace", "normalize_newlines"}
    if comparison_mode not in valid_modes:
        raise ValueError(
            f"Invalid comparison_mode: {comparison_mode}. Use one of: {', '.join(valid_modes)}"
        )

    import hashlib

    def _extract_lines(t: str) -> list[str]:
        raw = t.split("\n")
        if t.endswith("\n"):
            return raw[:-1]  # drop trailing empty
        return raw

    left_lines = _extract_lines(left_text)
    right_lines = _extract_lines(right_text)

    total_left = len(left_lines) or 1
    total_right = len(right_lines) or 1

    # Clamp to available range
    start_1based = start_line + (1 - line_base)
    end_1based = end_line + (1 - line_base)

    left_slice = left_lines[max(0, start_1based - 1) : end_1based]
    right_slice = right_lines[max(0, start_1based - 1) : end_1based]

    def _normalize_for_compare(s: str, mode: str) -> str:
        if mode == "ignore_trailing_whitespace":
            return s.rstrip()
        elif mode == "normalize_newlines":
            # After splitting by \n, trailing \r should be stripped
            return s.rstrip("\r")
        return s

    left_norm = [_normalize_for_compare(l, comparison_mode) for l in left_slice]
    right_norm = [_normalize_for_compare(r, comparison_mode) for r in right_slice]

    equal = left_norm == right_norm

    left_text_slice = "\n".join(left_slice)
    right_text_slice = "\n".join(right_slice)
    left_fp = hashlib.sha256(left_text_slice.encode("utf-8")).hexdigest()[:16]
    right_fp = hashlib.sha256(right_text_slice.encode("utf-8")).hexdigest()[:16]

    diff_summary = "equal" if equal else "different"
    first_diff: dict[str, Any] | None = None

    if not equal:
        for i, (l, r) in enumerate(zip(left_norm, right_norm)):
            if l != r:
                first_diff = {
                    "line_offset": i,
                    "line_number": start_1based + i,
                    "left": left_slice[i],
                    "right": right_slice[i],
                }
                diff_summary = f"differ at line {start_1based + i}"
                break
        if first_diff is None and len(left_norm) != len(right_norm):
            min_len = min(len(left_norm), len(right_norm))
            diff_summary = f"different lengths: {len(left_norm)} vs {len(right_norm)} lines"
            if min_len < max(len(left_norm), len(right_norm)):
                idx = min_len
                first_diff = {
                    "line_offset": idx,
                    "line_number": start_1based + idx,
                    "left": left_slice[idx] if idx < len(left_slice) else None,
                    "right": right_slice[idx] if idx < len(right_slice) else None,
                }

    return LineRangeCompareResult(
        equal=equal,
        left_fingerprint=left_fp,
        right_fingerprint=right_fp,
        diff_summary=diff_summary,
        first_difference=first_diff,
    )
