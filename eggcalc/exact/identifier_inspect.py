"""
Identifier inspection for collision and validity checking.

Provides detection of identifier collisions across multiple identifiers
including confusables, normalization issues, and casefold collisions.
"""

from __future__ import annotations

import keyword
import re
import unicodedata
from typing import Literal, TypedDict, cast

from .diff import levenshtein_distance
from .unicode_tools import ConfusableInfo, detect_confusables


class IdentifierInspectResult(TypedDict):
    """Result of identifier inspection."""

    identifiers: list[IdentifierInfo]
    collisions: list[CollisionInfo]


class IdentifierInfo(TypedDict):
    """Information about a single identifier."""

    raw: str
    normalized: str
    valid: bool
    scripts: list[str]
    has_invisibles: bool
    has_confusables: bool
    warnings: list[str]


class CollisionInfo(TypedDict):
    """Information about a collision between two identifiers."""

    kind: str
    a: str
    b: str


_JS_KEYWORDS: frozenset[str] = frozenset(
    {
        "break",
        "case",
        "catch",
        "const",
        "continue",
        "debugger",
        "default",
        "delete",
        "do",
        "else",
        "enum",
        "export",
        "extends",
        "false",
        "finally",
        "for",
        "function",
        "if",
        "import",
        "in",
        "instanceof",
        "let",
        "new",
        "null",
        "return",
        "static",
        "super",
        "switch",
        "this",
        "throw",
        "true",
        "try",
        "typeof",
        "var",
        "void",
        "while",
        "with",
        "yield",
    }
)


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


def _identifier_script_heuristic(char: str) -> str:
    """Determine script for a character using heuristic detection."""
    codepoint = ord(char)

    if unicodedata.category(char).startswith("M"):
        return "Inherited"

    for start, end, script_name in _SCRIPT_RANGES:
        if start <= codepoint <= end:
            return script_name

    return "Other"


def _normalize_nfc(text: str) -> str:
    """Normalize text to NFC form."""
    return unicodedata.normalize("NFC", text)


def _identifier_casefold(text: str) -> str:
    """Casefold text for case-insensitive comparison."""
    return text.casefold()


def _has_invisibles(text: str) -> bool:
    """Check if text contains invisible characters."""
    invisible_chars = {
        "\u200b",
        "\u200c",
        "\u200d",
        "\u200e",
        "\u200f",
        "\ufeff",
        "\u00a0",
        "\u2028",
        "\u2029",
        "\u202a",
        "\u202b",
        "\u202c",
        "\u202d",
        "\u202e",
        "\u2066",
        "\u2067",
        "\u2068",
        "\u2069",
        "\u2060",
    }
    for char in text:
        if char in invisible_chars:
            return True
    return False


def _check_python_valid(text: str) -> bool:
    """Check if identifier is valid Python identifier."""
    if not text:
        return False
    if not text.isidentifier():
        return False
    if keyword.iskeyword(text):
        return False
    return True


def _check_js_valid(text: str) -> bool:
    """Check if identifier is valid JavaScript identifier."""
    if not text:
        return False
    if text in _JS_KEYWORDS:
        return False
    if not text.isidentifier():
        return False
    return True


def _get_scripts(text: str) -> list[str]:
    """Get list of Unicode scripts used in text."""
    scripts: set[str] = set()
    for char in text:
        script = _identifier_script_heuristic(char)
        if script not in ("Common", "Inherited", "Unknown", "Other"):
            scripts.add(script)
    return sorted(list(scripts))


def identifier_inspect(
    identifiers: list[str],
    language: str = "generic",
    normalization: str = "NFC",
    casefold: bool = False,
    check_confusables: bool = True,
) -> IdentifierInspectResult:
    """Inspect a list of identifiers for validity and collisions.

    Detects confusables, mixed scripts, normalization issues, and
    casefold collisions across identifiers.

    Args:
        identifiers: List of identifier strings to inspect.
        language: Language for validation ("generic", "python", "rust",
                  "javascript", "typescript", "json_key").
        normalization: Unicode normalization form ("NFC", "NFD", etc).
        casefold: Apply casefolding for collision detection.
        check_confusables: Check for confusable characters.

    Returns:
        IdentifierInspectResult with per-identifier info and collisions.

    Example:
        >>> result = identifier_inspect(["paypal", "pаypal"], language="python")
        >>> result["collisions"]
        [{'kind': 'confusable', 'a': 'paypal', 'b': 'pаypal'}]
    """
    normalized_ids: list[str] = []
    id_infos: list[IdentifierInfo] = []
    collisions: list[CollisionInfo] = []
    confusables_by_norm: dict[str, list[ConfusableInfo]] = {}

    for raw_id in identifiers:
        normalized = raw_id
        if normalization != "raw":
            normalized = unicodedata.normalize(
                cast(Literal["NFC", "NFD", "NFKC", "NFKD"], normalization), raw_id
            )

        scripts = _get_scripts(normalized)
        has_invisibles = _has_invisibles(raw_id)

        confusables_found = []
        if check_confusables:
            if normalized not in confusables_by_norm:
                confusables_by_norm[normalized] = detect_confusables(normalized)
            confusables_found = confusables_by_norm[normalized]

        has_confusables = len(confusables_found) > 0

        valid = True
        warnings: list[str] = []

        if language == "python":
            valid = _check_python_valid(normalized)
            if not valid:
                warnings.append("Invalid Python identifier")
        elif language in ("javascript", "typescript"):
            valid = _check_js_valid(normalized)
            if not valid:
                warnings.append(f"Invalid {language} identifier")

        if has_invisibles:
            warnings.append("Contains invisible characters")

        if has_confusables:
            warnings.append("Contains confusable characters")

        if len(scripts) > 1:
            warnings.append("Mixed script identifier")

        id_infos.append(
            IdentifierInfo(
                raw=raw_id,
                normalized=normalized,
                valid=valid,
                scripts=scripts,
                has_invisibles=has_invisibles,
                has_confusables=has_confusables,
                warnings=warnings,
            )
        )
        normalized_ids.append(normalized)

    collision_pairs: set[tuple[str, str]] = set()

    if check_confusables:
        for i, a_raw in enumerate(identifiers):
            for j, b_raw in enumerate(identifiers):
                if i >= j:
                    continue
                # Identical raw entries are duplicates, not collisions.
                if a_raw == b_raw:
                    continue

                a_norm = normalized_ids[i]
                b_norm = normalized_ids[j]

                a_confusables = confusables_by_norm[a_norm]
                b_confusables = confusables_by_norm[b_norm]

                if a_confusables and b_confusables:
                    a_targets = {c["confusable_with"] for c in a_confusables}
                    b_targets = {c["confusable_with"] for c in b_confusables}
                    shared_targets = a_targets & b_targets
                    if shared_targets:
                        pair = (a_raw, b_raw) if a_raw <= b_raw else (b_raw, a_raw)
                        if pair not in collision_pairs:
                            collision_pairs.add(pair)
                            collisions.append(
                                CollisionInfo(
                                    kind="confusable",
                                    a=a_raw,
                                    b=b_raw,
                                )
                            )
                        continue

                for a_conf in a_confusables:
                    if a_conf["confusable_with"] in b_norm:
                        pair = (a_raw, b_raw) if a_raw <= b_raw else (b_raw, a_raw)
                        if pair not in collision_pairs:
                            collision_pairs.add(pair)
                            collisions.append(
                                CollisionInfo(
                                    kind="confusable",
                                    a=a_raw,
                                    b=b_raw,
                                )
                            )
                        break

                for b_conf in b_confusables:
                    if b_conf["confusable_with"] in a_norm:
                        pair = (a_raw, b_raw) if a_raw <= b_raw else (b_raw, a_raw)
                        if pair not in collision_pairs:
                            collision_pairs.add(pair)
                            collisions.append(
                                CollisionInfo(
                                    kind="confusable",
                                    a=a_raw,
                                    b=b_raw,
                                )
                            )
                        break

    if casefold:
        casefold_map: dict[str, list[str]] = {}
        for i, (raw, norm) in enumerate(zip(identifiers, normalized_ids)):
            cf_key = _identifier_casefold(norm)
            if cf_key not in casefold_map:
                casefold_map[cf_key] = []
            casefold_map[cf_key].append(raw)

        for cf_key, items in casefold_map.items():
            if len(items) > 1:
                for i in range(len(items)):
                    for j in range(i + 1, len(items)):
                        if items[i] == items[j]:
                            continue
                        pair = (
                            (items[i], items[j]) if items[i] <= items[j] else (items[j], items[i])
                        )
                        if pair not in collision_pairs:
                            collision_pairs.add(pair)
                            collisions.append(
                                CollisionInfo(
                                    kind="casefold",
                                    a=items[i],
                                    b=items[j],
                                )
                            )

    if normalization != "raw":
        norm_map: dict[str, list[str]] = {}
        for raw, norm in zip(identifiers, normalized_ids):
            if norm not in norm_map:
                norm_map[norm] = []
            norm_map[norm].append(raw)

        for norm_key, items in norm_map.items():
            if len(items) > 1:
                for i in range(len(items)):
                    for j in range(i + 1, len(items)):
                        if items[i] == items[j]:
                            continue
                        pair = (
                            (items[i], items[j]) if items[i] <= items[j] else (items[j], items[i])
                        )
                        if pair not in collision_pairs:
                            collision_pairs.add(pair)
                            collisions.append(
                                CollisionInfo(
                                    kind="normalization",
                                    a=items[i],
                                    b=items[j],
                                )
                            )

    return IdentifierInspectResult(
        identifiers=id_infos,
        collisions=collisions,
    )


class TableIdentifierEntry(TypedDict, total=False):
    """An identifier entry in the table passed to identifier_table_inspect."""

    name: str
    kind: str
    file: str
    line: int


class TableCollisionInfo(TypedDict):
    """Information about a collision between identifiers in a table."""

    kind: str
    names: list[str]
    detail: str


class ReservedKeywordHit(TypedDict):
    """An identifier that is a reserved keyword in the target language."""

    name: str
    language: str
    file: str
    line: int


class MixedStyleGroup(TypedDict):
    """A group of identifiers with the same stripped form but different styles."""

    stripped: str
    names: list[str]
    styles: list[str]


class IdentifierTableInspectResult(TypedDict):
    """Result of identifier table inspection."""

    count: int
    collisions: list[TableCollisionInfo]
    reserved_keyword_hits: list[ReservedKeywordHit]
    mixed_style_groups: list[MixedStyleGroup]
    findings: list[str]


_RUST_KEYWORDS: frozenset[str] = frozenset(
    {
        "as",
        "async",
        "await",
        "break",
        "const",
        "continue",
        "crate",
        "dyn",
        "else",
        "enum",
        "extern",
        "false",
        "fn",
        "for",
        "if",
        "impl",
        "in",
        "let",
        "loop",
        "match",
        "mod",
        "move",
        "mut",
        "pub",
        "ref",
        "return",
        "self",
        "Self",
        "static",
        "struct",
        "super",
        "trait",
        "true",
        "type",
        "unsafe",
        "use",
        "where",
        "while",
    }
)

_TS_KEYWORDS: frozenset[str] = _JS_KEYWORDS | frozenset(
    {
        "any",
        "boolean",
        "constructor",
        "declare",
        "get",
        "module",
        "require",
        "number",
        "set",
        "string",
        "symbol",
        "type",
        "from",
        "of",
        "readonly",
        "abstract",
        "as",
        "async",
        "await",
        "enum",
        "export",
        "implements",
        "interface",
        "is",
        "keyof",
        "namespace",
        "package",
        "private",
        "protected",
        "public",
        "static",
        "override",
    }
)

_LANG_KEYWORDS: dict[str, frozenset[str]] = {
    "python": frozenset(keyword.kwlist),
    "rust": _RUST_KEYWORDS,
    "javascript": _JS_KEYWORDS,
    "typescript": _TS_KEYWORDS,
}


def _classify_style(name: str) -> str:
    """Classify the naming style of an identifier."""
    if not name:
        return "invalid"
    if name[0].isupper():
        if (
            "_" not in name
            and "-" not in name
            and name.isidentifier()
            and any(c.isupper() for c in name)
        ):
            return "PascalCase"
    if "_" in name and "-" not in name:
        parts = name.split("_")
        if all(p.islower() or not p for p in parts):
            return "snake_case"
        if all(p.isupper() or not p for p in parts):
            return "SCREAMING_SNAKE_CASE"
    if "-" in name and "_" not in name:
        parts = name.split("-")
        if all(p.islower() or not p for p in parts):
            return "kebab-case"
    if name[0].islower() and "_" not in name and "-" not in name and name.isidentifier():
        if any(c.isupper() for c in name):
            return "camelCase"
    if name.isidentifier():
        return "mixed"
    return "invalid"


def _strip_style(name: str) -> str:
    """Strip case and style separators to get a canonical comparison form."""
    stripped = re.sub(r"[_\-]", "", name)
    return stripped.lower()


def identifier_table_inspect(
    identifiers: list[dict],
    language: str = "python",
    checks: list[str] | None = None,
) -> IdentifierTableInspectResult:
    """Inspect a table of identifiers for collisions, reserved keywords, and mixed styles.

    Args:
        identifiers: List of dicts with required 'name' (str), optional 'kind' (str),
                     'file' (str), 'line' (int).
        language: Target language for keyword checking ('python', 'rust',
                  'javascript', 'typescript', 'json_key', 'generic').
        checks: Subset of checks to run. Defaults to all checks:
                ['casefold', 'normalization', 'confusable', 'style', 'reserved', 'mixed_style'].

    Returns:
        IdentifierTableInspectResult with collisions, keyword hits, and mixed style groups.

    Example:
        >>> result = identifier_table_inspect([{'name': 'myVar'}, {'name': 'MyVar'}])
        >>> result['collisions']
        [{'kind': 'casefold', 'names': ['myVar', 'MyVar'], ...}]
    """
    if checks is None:
        checks = ["casefold", "normalization", "confusable", "style", "reserved", "mixed_style"]

    valid_checks = {"casefold", "normalization", "confusable", "style", "reserved", "mixed_style"}
    active_checks = [c for c in checks if c in valid_checks]

    count = len(identifiers)
    collisions: list[TableCollisionInfo] = []
    reserved_hits: list[ReservedKeywordHit] = []
    mixed_style_groups: list[MixedStyleGroup] = []
    findings: list[str] = []

    names = [entry.get("name", "") for entry in identifiers]

    if "casefold" in active_checks:
        cf_map: dict[str, list[str]] = {}
        for name in names:
            cf_key = name.casefold()
            cf_map.setdefault(cf_key, []).append(name)
        for cf_key, group in cf_map.items():
            if len(group) > 1:
                collisions.append(
                    TableCollisionInfo(
                        kind="casefold",
                        names=group,
                        detail=f"Casefold collision: {', '.join(group)}",
                    )
                )
        if cf_map and any(len(g) > 1 for g in cf_map.values()):
            findings.append("Casefold collisions detected")

    if "normalization" in active_checks:
        nfc_map: dict[str, list[str]] = {}
        for name in names:
            nfc_key = unicodedata.normalize("NFC", name)
            nfc_map.setdefault(nfc_key, []).append(name)
        for nfc_key, group in nfc_map.items():
            originals = list(set(group))
            if len(originals) > 1:
                collisions.append(
                    TableCollisionInfo(
                        kind="normalization",
                        names=originals,
                        detail=f"Normalization collision (NFC '{nfc_key}'): {', '.join(originals)}",
                    )
                )
        if nfc_map and any(len(set(g)) > 1 for g in nfc_map.values()):
            findings.append("Normalization collisions detected")

    if "confusable" in active_checks:
        checked_pairs: set[tuple[str, str]] = set()
        for i, entry_a in enumerate(identifiers):
            for j, entry_b in enumerate(identifiers):
                if i >= j:
                    continue
                name_a = entry_a.get("name", "")
                name_b = entry_b.get("name", "")
                pair = (name_a, name_b) if name_a <= name_b else (name_b, name_a)
                if pair in checked_pairs:
                    continue

                confusables_a = detect_confusables(name_a)
                confusables_b = detect_confusables(name_b)

                is_confusable = False
                if confusables_a and confusables_b:
                    a_targets = {c["confusable_with"] for c in confusables_a}
                    b_targets = {c["confusable_with"] for c in confusables_b}
                    if a_targets & b_targets:
                        is_confusable = True

                if not is_confusable:
                    for c in confusables_a:
                        if c["confusable_with"] in name_b:
                            is_confusable = True
                            break
                if not is_confusable:
                    for c in confusables_b:
                        if c["confusable_with"] in name_a:
                            is_confusable = True
                            break

                if not is_confusable:
                    try:
                        dist = levenshtein_distance(name_a, name_b, max_len=200)
                        max_len_val = max(len(name_a), len(name_b))
                        if max_len_val > 0 and dist <= 1 and name_a != name_b:
                            is_confusable = True
                    except ValueError:
                        pass

                if is_confusable:
                    checked_pairs.add(pair)
                    collisions.append(
                        TableCollisionInfo(
                            kind="confusable",
                            names=[name_a, name_b],
                            detail=f"Confusable/near-collision: '{name_a}' and '{name_b}'",
                        )
                    )
        if checked_pairs:
            findings.append("Confusable characters or near-collisions detected")

    if "style" in active_checks:
        style_map: dict[str, list[tuple[str, str]]] = {}
        for name in names:
            stripped = _strip_style(name)
            if not stripped:
                continue
            style = _classify_style(name)
            style_map.setdefault(stripped, []).append((name, style))
        for stripped, entries in style_map.items():
            styles_present = list({s for _, s in entries})
            if len(styles_present) > 1:
                group_names = [n for n, _ in entries]
                collisions.append(
                    TableCollisionInfo(
                        kind="style_variant",
                        names=group_names,
                        detail=f"Style variants for '{stripped}': {', '.join(styles_present)}",
                    )
                )
        if any(len({s for _, s in e}) > 1 for e in style_map.values()):
            findings.append("Style variant collisions detected")

    if "reserved" in active_checks:
        kw_set = _LANG_KEYWORDS.get(language, frozenset())
        for i, entry in enumerate(identifiers):
            name = names[i]
            if name in kw_set:
                reserved_hits.append(
                    ReservedKeywordHit(
                        name=name,
                        language=language,
                        file=entry.get("file", ""),
                        line=entry.get("line", 0),
                    )
                )
        if reserved_hits:
            findings.append(f"{len(reserved_hits)} reserved keyword hit(s) in {language}")

    if "mixed_style" in active_checks:
        style_map2: dict[str, list[tuple[str, str]]] = {}
        for name in names:
            stripped = _strip_style(name)
            if not stripped:
                continue
            style = _classify_style(name)
            style_map2.setdefault(stripped, []).append((name, style))
        for stripped, entries in style_map2.items():
            styles_present = list({s for _, s in entries})
            if len(styles_present) > 1:
                mixed_style_groups.append(
                    MixedStyleGroup(
                        stripped=stripped,
                        names=[n for n, _ in entries],
                        styles=styles_present,
                    )
                )
        if mixed_style_groups:
            findings.append(f"{len(mixed_style_groups)} mixed-style group(s) detected")

    return IdentifierTableInspectResult(
        count=count,
        collisions=collisions,
        reserved_keyword_hits=reserved_hits,
        mixed_style_groups=mixed_style_groups,
        findings=findings,
    )
