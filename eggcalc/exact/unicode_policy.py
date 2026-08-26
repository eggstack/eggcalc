"""
Unicode policy checks and canonicalization profiles.

Provides deterministic, named policies for validating text against
Unicode safety heuristics, and named canonicalization profiles for
normalizing text for comparison or identity purposes.

These are deterministic heuristics, not semantic security guarantees.
Policies are documented as heuristics to avoid giving agents false
assurance about complex Unicode edge cases.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import TypedDict

from .primitives import (
    find_invisibles,
    normalize_unicode,
)
from .unicode_tools import (
    detect_confusables,
    detect_mixed_scripts,
)

MAX_TEXT_LENGTH = 100_000


class PolicyFinding(TypedDict):
    """A single finding from a policy check."""

    rule: str
    severity: str
    message: str


class UnicodePolicyCheckResult(TypedDict):
    """Result of a Unicode policy check."""

    pass_: bool
    policy: str
    normalized_form: str
    findings: list[PolicyFinding]
    summary: str


class CanonicalizeResult(TypedDict):
    """Result of text canonicalization."""

    text: str
    changed: bool
    operations_applied: list[str]
    fingerprint_before: str
    fingerprint_after: str
    findings: list[str]


class CanonicalizeResultWithMapping(CanonicalizeResult):
    """Result of text canonicalization with character mapping."""

    mapping: list[dict[str, str]] | None


# --- Policy definitions ---

_VALID_POLICIES = frozenset(
    {
        "identifier_strict",
        "filename_safe",
        "source_code",
        "human_text",
        "json_key",
        "domain_like",
    }
)

# Reserved Windows device names (case-insensitive)
_WINDOWS_RESERVED = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "COM1",
        "COM2",
        "COM3",
        "COM4",
        "COM5",
        "COM6",
        "COM7",
        "COM8",
        "COM9",
        "LPT1",
        "LPT2",
        "LPT3",
        "LPT4",
        "LPT5",
        "LPT6",
        "LPT7",
        "LPT8",
        "LPT9",
    }
)

# Bidi control characters (includes LRM/RLM marks per Unicode Bidirectional Algorithm)
_BIDI_CHARS = frozenset(
    {
        "\u200e",
        "\u200f",  # LEFT-TO-RIGHT MARK, RIGHT-TO-LEFT MARK
        "\u202a",
        "\u202b",
        "\u202c",
        "\u202d",
        "\u202e",
        "\u2066",
        "\u2067",
        "\u2068",
        "\u2069",
    }
)

# Zero-width characters
_ZERO_WIDTH_CHAR_SET = frozenset(
    {
        "\u200b",
        "\u200c",
        "\u200d",
        "\u2060",
    }
)

# Windows forbidden characters
_WIN_FORBIDDEN = frozenset(
    {
        "\\",
        "/",
        ":",
        "*",
        "?",
        "\"",
        "<",
        ">",
        "|",
    }
)


def unicode_policy_check(
    text: str,
    policy: str,
    normalization: str | None = None,
) -> UnicodePolicyCheckResult:
    """Apply a named deterministic Unicode safety policy to input text.

    Policies are deterministic heuristics, not semantic security guarantees.

    Args:
        text: Input text to check.
        policy: One of identifier_strict, filename_safe, source_code,
                human_text, json_key, domain_like.
        normalization: Optional normalization form to apply before checking.
                      Defaults to policy-specific normalizations.

    Returns:
        UnicodePolicyCheckResult with pass/fail, findings, and summary.
    """
    if len(text) > MAX_TEXT_LENGTH:
        return UnicodePolicyCheckResult(
            pass_=False,
            policy=policy,
            normalized_form="",
            findings=[
                PolicyFinding(
                    rule="input_too_large",
                    severity="error",
                    message=f"Input length {len(text)} exceeds MAX_TEXT_LENGTH {MAX_TEXT_LENGTH}",
                )
            ],
            summary=f"Input too large: {len(text)} > {MAX_TEXT_LENGTH}",
        )

    if policy not in _VALID_POLICIES:
        return UnicodePolicyCheckResult(
            pass_=False,
            policy=policy,
            normalized_form="",
            findings=[
                PolicyFinding(
                    rule="invalid_policy",
                    severity="error",
                    message=f"Unknown policy: {policy}. Valid policies: {', '.join(sorted(_VALID_POLICIES))}",
                )
            ],
            summary=f"Invalid policy: {policy}",
        )

    # Determine default normalization for the policy
    if normalization is None:
        normalization = _default_normalization(policy)
    elif normalization == "raw":
        normalization = ""

    # Apply normalization if requested
    if normalization:
        try:
            normalized = normalize_unicode(text, normalization)
        except ValueError:
            return UnicodePolicyCheckResult(
                pass_=False,
                policy=policy,
                normalized_form="",
                findings=[
                    PolicyFinding(
                        rule="invalid_normalization",
                        severity="error",
                        message=f"Invalid normalization form: {normalization}",
                    )
                ],
                summary=f"Invalid normalization: {normalization}",
            )
    else:
        normalized = text

    findings: list[PolicyFinding] = []

    if policy == "identifier_strict":
        findings.extend(_check_identifier_strict(text, normalized))
    elif policy == "filename_safe":
        findings.extend(_check_filename_safe(text, normalized))
    elif policy == "source_code":
        findings.extend(_check_source_code(text, normalized))
    elif policy == "human_text":
        findings.extend(_check_human_text(text, normalized))
    elif policy == "json_key":
        findings.extend(_check_json_key(text, normalized))
    elif policy == "domain_like":
        findings.extend(_check_domain_like(text, normalized))

    # Determine pass/fail: error findings fail, warnings pass
    errors = [f for f in findings if f["severity"] == "error"]
    pass_ = len(errors) == 0

    summary_parts: list[str] = []
    if pass_:
        summary_parts.append(f"PASS ({policy})")
    else:
        summary_parts.append(f"FAIL ({policy})")
        summary_parts.append(f"{len(errors)} error(s)")

    warnings = [f for f in findings if f["severity"] == "warning"]
    if warnings:
        summary_parts.append(f"{len(warnings)} warning(s)")

    return UnicodePolicyCheckResult(
        pass_=pass_,
        policy=policy,
        normalized_form=normalized,
        findings=findings,
        summary="; ".join(summary_parts),
    )


def _default_normalization(policy: str) -> str:
    """Return the default normalization form for a policy."""
    defaults = {
        "identifier_strict": "NFC",
        "filename_safe": "NFC",
        "source_code": "NFC",
        "human_text": "NFC",
        "json_key": "NFC",
        "domain_like": "NFKC",
    }
    return defaults.get(policy, "NFC")


def _check_identifier_strict(text: str, normalized: str) -> list[PolicyFinding]:
    """Check text for identifier_strict policy violations."""
    findings: list[PolicyFinding] = []

    # Mixed scripts
    ms = detect_mixed_scripts(normalized)
    if ms["mixed_scripts"]:
        findings.append(
            PolicyFinding(
                rule="mixed_scripts",
                severity="error",
                message=f"Mixed scripts detected: {', '.join(ms['scripts'])}",
            )
        )

    # Bidi controls
    bidi_found = [c for c in normalized if c in _BIDI_CHARS]
    if bidi_found:
        findings.append(
            PolicyFinding(
                rule="bidi_controls",
                severity="error",
                message=f"Bidi control characters found: {len(bidi_found)}",
            )
        )

    # Zero-width characters
    zw_found = [c for c in normalized if c in _ZERO_WIDTH_CHAR_SET]
    if zw_found:
        findings.append(
            PolicyFinding(
                rule="zero_width_characters",
                severity="error",
                message=f"Zero-width characters found: {len(zw_found)}",
            )
        )

    # Confusables
    confusables = detect_confusables(normalized)
    if confusables:
        findings.append(
            PolicyFinding(
                rule="confusables",
                severity="error",
                message=f"Confusable characters found: {len(confusables)}",
            )
        )

    # Normalization instability (NFC != NFD form)
    # NOTE: This is an intentional heuristic for security-sensitive contexts.
    # It fires on text containing precomposed characters that have combining
    # equivalents (e.g., U+00E9 'é' vs 'e' + U+0301 combining acute).
    # This is expected to have a high false-positive rate for non-ASCII text
    # with common accented characters. Callers should filter by severity
    # ("warning") if this is too noisy for their use case.
    if unicodedata.is_normalized("NFC", normalized) and not unicodedata.is_normalized(
        "NFD", normalized
    ):
        nfd_form = unicodedata.normalize("NFD", normalized)
        if nfd_form != normalized:
            findings.append(
                PolicyFinding(
                    rule="normalization_instability",
                    severity="warning",
                    message="Text has different forms under NFC vs NFD normalization",
                )
            )

    # Invisible characters
    invisibles = find_invisibles(normalized)
    if invisibles:
        findings.append(
            PolicyFinding(
                rule="invisible_characters",
                severity="error",
                message=f"Invisible characters found: {len(invisibles)}",
            )
        )

    return findings


def _check_filename_safe(text: str, normalized: str) -> list[PolicyFinding]:
    """Check text for filename_safe policy violations."""
    findings: list[PolicyFinding] = []

    # Control characters (exclude common whitespace)
    for i, c in enumerate(normalized):
        cat = unicodedata.category(c)
        if cat.startswith("C") and c not in "\n\t\r":
            findings.append(
                PolicyFinding(
                    rule="control_characters",
                    severity="error",
                    message=f"Control character at position {i}: U+{ord(c):04X}",
                )
            )

    # Windows forbidden characters
    forbidden_found = [c for c in normalized if c in _WIN_FORBIDDEN]
    if forbidden_found:
        findings.append(
            PolicyFinding(
                rule="path_separators",
                severity="error",
                message=f"Forbidden path characters found: {', '.join(repr(c) for c in sorted(set(forbidden_found)))}",
            )
        )

    # Bidi controls
    bidi_found = [c for c in normalized if c in _BIDI_CHARS]
    if bidi_found:
        findings.append(
            PolicyFinding(
                rule="bidi_controls",
                severity="error",
                message=f"Bidi control characters found: {len(bidi_found)}",
            )
        )

    # Zero-width characters
    zw_found = [c for c in normalized if c in _ZERO_WIDTH_CHAR_SET]
    if zw_found:
        findings.append(
            PolicyFinding(
                rule="zero_width_characters",
                severity="error",
                message=f"Zero-width characters found: {len(zw_found)}",
            )
        )

    # Reserved Windows names (check stem, handling path-qualified names)
    # Extract the basename before checking to catch names like "dir/CON.txt"
    basename = normalized.split("/")[-1].split("\\")[-1]
    stem = basename.split(".")[0].upper()
    if stem in _WINDOWS_RESERVED:
        findings.append(
            PolicyFinding(
                rule="reserved_windows_name",
                severity="error",
                message=f"Reserved Windows device name: {stem}",
            )
        )

    return findings


def _check_source_code(text: str, normalized: str) -> list[PolicyFinding]:
    """Check text for source_code policy violations."""
    findings: list[PolicyFinding] = []

    # Bidi controls
    bidi_found = [c for c in normalized if c in _BIDI_CHARS]
    if bidi_found:
        findings.append(
            PolicyFinding(
                rule="bidi_controls",
                severity="error",
                message=f"Bidi control characters found: {len(bidi_found)}",
            )
        )

    # Zero-width characters (except word joiner which is sometimes intentional)
    zw_found = [c for c in normalized if c in _ZERO_WIDTH_CHAR_SET and c != "\u2060"]
    if zw_found:
        findings.append(
            PolicyFinding(
                rule="zero_width_characters",
                severity="error",
                message=f"Zero-width characters found: {len(zw_found)}",
            )
        )

    # Confusables (warning level for source code)
    confusables = detect_confusables(normalized)
    if confusables:
        findings.append(
            PolicyFinding(
                rule="confusables",
                severity="warning",
                message=f"Confusable characters found: {len(confusables)}",
            )
        )

    return findings


def _check_human_text(text: str, normalized: str) -> list[PolicyFinding]:
    """Check text for human_text policy violations (less strict)."""
    findings: list[PolicyFinding] = []

    # Bidi controls (warning only for human text)
    bidi_found = [c for c in normalized if c in _BIDI_CHARS]
    if bidi_found:
        findings.append(
            PolicyFinding(
                rule="bidi_controls",
                severity="warning",
                message=f"Bidi control characters found: {len(bidi_found)}",
            )
        )

    # Zero-width characters (warning only)
    zw_found = [c for c in normalized if c in _ZERO_WIDTH_CHAR_SET]
    if zw_found:
        findings.append(
            PolicyFinding(
                rule="zero_width_characters",
                severity="warning",
                message=f"Zero-width characters found: {len(zw_found)}",
            )
        )

    # Mixed scripts (warning only for human text)
    ms = detect_mixed_scripts(normalized)
    if ms["mixed_scripts"]:
        findings.append(
            PolicyFinding(
                rule="mixed_scripts",
                severity="warning",
                message=f"Mixed scripts detected: {', '.join(ms['scripts'])}",
            )
        )

    # Confusables (warning only for human text)
    confusables = detect_confusables(normalized)
    if confusables:
        findings.append(
            PolicyFinding(
                rule="confusables",
                severity="warning",
                message=f"Confusable characters found: {len(confusables)}",
            )
        )

    return findings


def _check_json_key(text: str, normalized: str) -> list[PolicyFinding]:
    """Check text for json_key policy violations."""
    findings: list[PolicyFinding] = []

    # Bidi controls
    bidi_found = [c for c in normalized if c in _BIDI_CHARS]
    if bidi_found:
        findings.append(
            PolicyFinding(
                rule="bidi_controls",
                severity="error",
                message=f"Bidi control characters found: {len(bidi_found)}",
            )
        )

    # Zero-width characters
    zw_found = [c for c in normalized if c in _ZERO_WIDTH_CHAR_SET]
    if zw_found:
        findings.append(
            PolicyFinding(
                rule="zero_width_characters",
                severity="error",
                message=f"Zero-width characters found: {len(zw_found)}",
            )
        )

    # Variation selectors (U+FE00-U+FE0F) — invisible characters that could
    # manipulate JSON key identity
    vs_found = [c for c in normalized if 0xFE00 <= ord(c) <= 0xFE0F]
    if vs_found:
        findings.append(
            PolicyFinding(
                rule="variation_selectors",
                severity="error",
                message=f"Variation selector characters found: {len(vs_found)}",
            )
        )

    # Confusables (warning for JSON keys)
    confusables = detect_confusables(normalized)
    if confusables:
        findings.append(
            PolicyFinding(
                rule="confusables",
                severity="warning",
                message=f"Confusable characters found: {len(confusables)}",
            )
        )

    # Control characters
    for i, c in enumerate(normalized):
        cat = unicodedata.category(c)
        if cat.startswith("C") and c not in "\n\t\r":
            findings.append(
                PolicyFinding(
                    rule="control_characters",
                    severity="error",
                    message=f"Control character at position {i}: U+{ord(c):04X}",
                )
            )

    return findings


def _check_domain_like(text: str, normalized: str) -> list[PolicyFinding]:
    """Check text for domain_like policy violations."""
    findings: list[PolicyFinding] = []

    # Mixed scripts
    ms = detect_mixed_scripts(normalized)
    if ms["mixed_scripts"]:
        findings.append(
            PolicyFinding(
                rule="mixed_scripts",
                severity="error",
                message=f"Mixed scripts detected: {', '.join(ms['scripts'])}",
            )
        )

    # Confusables (error for domain-like)
    confusables = detect_confusables(normalized)
    if confusables:
        findings.append(
            PolicyFinding(
                rule="confusables",
                severity="error",
                message=f"Confusable characters found: {len(confusables)}",
            )
        )

    # Bidi controls
    bidi_found = [c for c in normalized if c in _BIDI_CHARS]
    if bidi_found:
        findings.append(
            PolicyFinding(
                rule="bidi_controls",
                severity="error",
                message=f"Bidi control characters found: {len(bidi_found)}",
            )
        )

    # Zero-width characters
    zw_found = [c for c in normalized if c in _ZERO_WIDTH_CHAR_SET]
    if zw_found:
        findings.append(
            PolicyFinding(
                rule="zero_width_characters",
                severity="error",
                message=f"Zero-width characters found: {len(zw_found)}",
            )
        )

    return findings


# --- Canonicalization profiles ---

_VALID_PROFILES = frozenset(
    {
        "source_file_identity",
        "identifier_compare",
        "human_label_compare",
        "json_key_compare",
        "path_segment_compare",
    }
)


def canonicalize_text(
    text: str,
    profile: str,
    return_mapping: bool = False,
) -> CanonicalizeResult | CanonicalizeResultWithMapping:
    """Apply a named text canonicalization profile.

    Profiles provide a single call to select common normalization
    sequences without manually specifying many low-level flags.

    Args:
        text: Input text to canonicalize.
        profile: One of source_file_identity, identifier_compare,
                 human_label_compare, json_key_compare, path_segment_compare.
        return_mapping: If True, include a character mapping showing
                       what changed at each position.

    Returns:
        CanonicalizeResult with canonicalized text, operations applied,
        fingerprints, and findings.
    """
    if profile not in _VALID_PROFILES:
        result: CanonicalizeResultWithMapping = CanonicalizeResultWithMapping(
            text=text,
            changed=False,
            operations_applied=[],
            fingerprint_before="",
            fingerprint_after="",
            findings=[
                f"Invalid profile: {profile}. Valid profiles: {', '.join(sorted(_VALID_PROFILES))}"
            ],
            mapping=None,
        )
        return result

    if len(text) > MAX_TEXT_LENGTH:
        result = CanonicalizeResultWithMapping(
            text=text,
            changed=False,
            operations_applied=[],
            fingerprint_before="",
            fingerprint_after="",
            findings=[f"Input length {len(text)} exceeds MAX_TEXT_LENGTH {MAX_TEXT_LENGTH}"],
            mapping=None,
        )
        return result

    # Compute fingerprint of original
    fp_before = hashlib.sha256(text.encode("utf-8")).hexdigest()

    current_text = text
    operations: list[str] = []
    findings: list[str] = []

    if profile == "source_file_identity":
        current_text, ops, founds = _canonicalize_source_file_identity(current_text)
        operations.extend(ops)
        findings.extend(founds)

    elif profile == "identifier_compare":
        current_text, ops, founds = _canonicalize_identifier_compare(current_text)
        operations.extend(ops)
        findings.extend(founds)

    elif profile == "human_label_compare":
        current_text, ops, founds = _canonicalize_human_label_compare(current_text)
        operations.extend(ops)
        findings.extend(founds)

    elif profile == "json_key_compare":
        current_text, ops, founds = _canonicalize_json_key_compare(current_text)
        operations.extend(ops)
        findings.extend(founds)

    elif profile == "path_segment_compare":
        current_text, ops, founds = _canonicalize_path_segment_compare(current_text)
        operations.extend(ops)
        findings.extend(founds)

    # Compute fingerprint of result
    fp_after = hashlib.sha256(current_text.encode("utf-8")).hexdigest()

    changed = current_text != text

    # Build mapping if requested
    mapping_list: list[dict[str, str]] | None = None
    if return_mapping and changed:
        mapping_list = _build_char_mapping(text, current_text)

    result_base: CanonicalizeResultWithMapping = CanonicalizeResultWithMapping(
        text=current_text,
        changed=changed,
        operations_applied=operations,
        fingerprint_before=fp_before,
        fingerprint_after=fp_after,
        findings=findings,
        mapping=mapping_list,
    )
    return result_base


def _build_char_mapping(original: str, canonical: str) -> list[dict[str, str]]:
    """Build a character-level mapping between original and canonical text.

    Returns a list of changes at positions where characters differ.
    """
    mapping: list[dict[str, str]] = []
    max_len = max(len(original), len(canonical))

    for i in range(max_len):
        orig_char = original[i] if i < len(original) else ""
        canon_char = canonical[i] if i < len(canonical) else ""

        if orig_char != canon_char:
            entry: dict[str, str] = {"position": str(i)}
            if orig_char:
                entry["original"] = orig_char
                entry["original_codepoint"] = f"U+{ord(orig_char):04X}"
            else:
                entry["original"] = ""
                entry["original_codepoint"] = ""
            if canon_char:
                entry["canonical"] = canon_char
                entry["canonical_codepoint"] = f"U+{ord(canon_char):04X}"
            else:
                entry["canonical"] = ""
                entry["canonical_codepoint"] = ""
            mapping.append(entry)

    return mapping


def _canonicalize_source_file_identity(text: str) -> tuple[str, list[str], list[str]]:
    """Canonicalize for source file identity comparison.

    Operations: NFC normalization, LF newlines, strip trailing whitespace,
    ensure final newline.
    """
    ops: list[str] = []
    findings: list[str] = []
    current = text

    # NFC normalization
    nfc = unicodedata.normalize("NFC", current)
    if nfc != current:
        current = nfc
        ops.append("NFC")

    # LF newlines
    lf = current.replace("\r\n", "\n").replace("\r", "\n")
    if lf != current:
        current = lf
        ops.append("LF_newlines")

    # Strip trailing whitespace per line
    lines = current.split("\n")
    stripped = [line.rstrip() for line in lines]
    new_text = "\n".join(stripped)
    if new_text != current:
        current = new_text
        ops.append("strip_trailing_whitespace")

    # Ensure final newline
    if not current.endswith("\n"):
        current = current + "\n"
        ops.append("ensure_final_newline")
    elif current.endswith("\n\n"):
        # Normalize multiple trailing newlines (strip extras, keep one)
        current = current.rstrip("\n") + "\n"

    return current, ops, findings


def _canonicalize_identifier_compare(text: str) -> tuple[str, list[str], list[str]]:
    """Canonicalize for identifier comparison.

    Operations: NFC normalization, casefold.
    """
    ops: list[str] = []
    findings: list[str] = []
    current = text

    # NFC normalization
    nfc = unicodedata.normalize("NFC", current)
    if nfc != current:
        current = nfc
        ops.append("NFC")

    # Casefold
    folded = current.casefold()
    if folded != current:
        current = folded
        ops.append("casefold")

    return current, ops, findings


def _canonicalize_human_label_compare(text: str) -> tuple[str, list[str], list[str]]:
    """Canonicalize for human label comparison.

    Operations: NFC normalization, casefold, trim, collapse whitespace.
    """
    ops: list[str] = []
    findings: list[str] = []
    current = text

    # NFC normalization
    nfc = unicodedata.normalize("NFC", current)
    if nfc != current:
        current = nfc
        ops.append("NFC")

    # Casefold
    folded = current.casefold()
    if folded != current:
        current = folded
        ops.append("casefold")

    # Trim
    trimmed = current.strip()
    if trimmed != current:
        current = trimmed
        ops.append("trim")

    # Collapse whitespace
    collapsed = re.sub(r"\s+", " ", current)
    if collapsed != current:
        current = collapsed
        ops.append("collapse_whitespace")
        findings.append("Whitespace sequences collapsed to single space")

    return current, ops, findings


def _canonicalize_json_key_compare(text: str) -> tuple[str, list[str], list[str]]:
    """Canonicalize for JSON key comparison.

    Operations: NFC normalization, casefold.
    """
    ops: list[str] = []
    findings: list[str] = []
    current = text

    # NFC normalization
    nfc = unicodedata.normalize("NFC", current)
    if nfc != current:
        current = nfc
        ops.append("NFC")

    # Casefold
    folded = current.casefold()
    if folded != current:
        current = folded
        ops.append("casefold")

    return current, ops, findings


def _canonicalize_path_segment_compare(text: str) -> tuple[str, list[str], list[str]]:
    """Canonicalize for path segment comparison.

    Operations: NFC normalization, lowercase, normalize newlines to LF.
    """
    ops: list[str] = []
    findings: list[str] = []
    current = text

    # NFC normalization
    nfc = unicodedata.normalize("NFC", current)
    if nfc != current:
        current = nfc
        ops.append("NFC")

    # Lowercase
    lowered = current.lower()
    if lowered != current:
        current = lowered
        ops.append("lowercase")

    # LF newlines
    lf = current.replace("\r\n", "\n").replace("\r", "\n")
    if lf != current:
        current = lf
        ops.append("LF_newlines")

    return current, ops, findings
