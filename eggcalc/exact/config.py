"""
Configuration file validation primitives.

Provides deterministic, line-by-line parsers for .env and INI files.
"""

from __future__ import annotations

import re
from typing import TypedDict

DEFAULT_KEY_PATTERN = r"^[A-Za-z_][A-Za-z0-9_]*$"
_EXPANSION_RE = re.compile(r"\$\{[^}]*\}|\$[A-Za-z_][A-Za-z0-9_]*")

MAX_TEXT_INPUT_LENGTH = 100_000


class DotenvEntry(TypedDict):
    """A single parsed .env entry."""

    key: str
    value: str
    value_present: bool
    quote_style: str
    line: int


class IniLine(TypedDict):
    """A single parsed INI line."""

    kind: str
    line: int


class IniSectionLine(IniLine):
    """An INI section header line."""

    name: str


class IniKeyValueLine(IniLine):
    """An INI key-value line."""

    section: str | None
    key: str
    value: str


class DotenvValidateResult(TypedDict):
    """Result of dotenv validation."""

    parse_ok: bool
    entries: list[DotenvEntry]
    duplicates: list[dict[str, object]]
    invalid_lines: list[dict[str, object]]
    requires_quoting: list[str]
    contains_expansion_syntax: list[str]
    findings: list[str]


class IniValidateResult(TypedDict):
    """Result of INI validation."""

    parse_ok: bool
    sections: list[str]
    keys_by_section: dict[str, list[str]]
    duplicates: list[dict[str, object]]
    invalid_lines: list[dict[str, object]]
    findings: list[str]


def dotenv_validate(
    text: str,
    allow_export: bool = True,
    key_pattern: str = DEFAULT_KEY_PATTERN,
    duplicate_policy: str = "warn",
) -> DotenvValidateResult:
    """Validate .env-style key=value text.

    Parses line by line, handling comments, blank lines, quoted values,
    and optional ``export`` prefix.

    Args:
        text: Input text to validate.
        allow_export: If True, allow ``export KEY=VALUE`` syntax.
        key_pattern: Regex pattern that keys must match.
        duplicate_policy: ``warn``, ``error``, or ``allow``.

    Returns:
        Validation result dict.

    Raises:
        ValueError: If text exceeds MAX_TEXT_INPUT_LENGTH.
    """
    if len(text) > MAX_TEXT_INPUT_LENGTH:
        raise ValueError(f"Input length {len(text)} exceeds maximum {MAX_TEXT_INPUT_LENGTH}")
    key_re = re.compile(key_pattern)
    seen_keys: dict[str, int] = {}
    entries: list[DotenvEntry] = []
    duplicates: list[dict[str, object]] = []
    invalid_lines: list[dict[str, object]] = []
    requires_quoting: list[str] = []
    contains_expansion: list[str] = []
    findings: list[str] = []
    parse_ok = True

    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        stripped = raw_line.strip()

        if not stripped or stripped.startswith("#"):
            continue

        line = stripped

        if allow_export and line.startswith("export "):
            line = line[len("export ") :]
        elif line.startswith("export "):
            invalid_lines.append(
                {
                    "line": line_no,
                    "text": raw_line,
                    "reason": "export keyword not allowed",
                }
            )
            parse_ok = False
            continue

        eq_pos = line.find("=")
        if eq_pos < 1:
            invalid_lines.append(
                {
                    "line": line_no,
                    "text": raw_line,
                    "reason": "missing '=' separator",
                }
            )
            parse_ok = False
            continue

        key = line[:eq_pos].strip()
        raw_value = line[eq_pos + 1 :]

        if not key_re.match(key):
            invalid_lines.append(
                {
                    "line": line_no,
                    "text": raw_line,
                    "reason": f"key '{key}' does not match pattern {key_pattern}",
                }
            )
            parse_ok = False
            continue

        quote_style = "none"
        value = raw_value.strip()

        if len(value) >= 2 and value[0] in ("'", '"') and value[-1] == value[0]:
            quote_style = value[0]
            value = value[1:-1]
        else:
            value = value.split("#", 1)[0].rstrip()
            if " " in value and not value.startswith(("{", "[")):
                requires_quoting.append(key)

        value_present = True
        if value == "" or value == "''" or value == '""':
            value_present = True

        if _EXPANSION_RE.search(raw_value):
            contains_expansion.append(key)

        entry: DotenvEntry = {
            "key": key,
            "value": value,
            "value_present": value_present,
            "quote_style": quote_style,
            "line": line_no,
        }
        entries.append(entry)

        if key in seen_keys:
            dup_info: dict[str, object] = {
                "key": key,
                "first_line": seen_keys[key],
                "second_line": line_no,
            }
            duplicates.append(dup_info)
            if duplicate_policy == "error":
                parse_ok = False
                findings.append(
                    f"Duplicate key '{key}' at line {line_no} (first at line {seen_keys[key]})"
                )
            elif duplicate_policy == "warn":
                findings.append(
                    f"Duplicate key '{key}' at line {line_no} (first at line {seen_keys[key]})"
                )
        else:
            seen_keys[key] = line_no

    if not entries and not invalid_lines:
        findings.append("No entries found")

    return DotenvValidateResult(
        parse_ok=parse_ok,
        entries=entries,
        duplicates=duplicates,
        invalid_lines=invalid_lines,
        requires_quoting=requires_quoting,
        contains_expansion_syntax=contains_expansion,
        findings=findings,
    )


def ini_validate(
    text: str,
    duplicate_policy: str = "warn",
) -> IniValidateResult:
    """Validate simple INI-style configuration.

    Supports ``[section]`` headers, ``key = value`` lines, ``;`` and ``#``
    comments, and optional ``key : value`` separator syntax.

    Args:
        text: Input text to validate.
        duplicate_policy: ``warn``, ``error``, or ``allow``.

    Returns:
        Validation result dict.

    Raises:
        ValueError: If text exceeds MAX_TEXT_INPUT_LENGTH.
    """
    if len(text) > MAX_TEXT_INPUT_LENGTH:
        raise ValueError(f"Input length {len(text)} exceeds maximum {MAX_TEXT_INPUT_LENGTH}")
    seen_keys: dict[tuple[str | None, str], int] = {}
    seen_sections: dict[str, int] = {}
    sections: list[str] = []
    keys_by_section: dict[str, list[str]] = {}
    duplicates: list[dict[str, object]] = []
    invalid_lines: list[dict[str, object]] = []
    findings: list[str] = []
    parse_ok = True
    current_section: str | None = None

    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        stripped = raw_line.strip()

        if not stripped or stripped.startswith(("#", ";")):
            continue

        if stripped.startswith("[") and stripped.endswith("]"):
            section_name = stripped[1:-1].strip()
            if not section_name:
                invalid_lines.append(
                    {
                        "line": line_no,
                        "text": raw_line,
                        "reason": "empty section name",
                    }
                )
                parse_ok = False
                continue

            if section_name in seen_sections:
                dup_info: dict[str, object] = {
                    "key": f"[{section_name}]",
                    "first_line": seen_sections[section_name],
                    "second_line": line_no,
                    "section": section_name,
                }
                duplicates.append(dup_info)
                if duplicate_policy == "error":
                    parse_ok = False
                    findings.append(
                        f"Duplicate section '{section_name}' at line {line_no} "
                        f"(first at line {seen_sections[section_name]})"
                    )
                elif duplicate_policy == "warn":
                    findings.append(
                        f"Duplicate section '{section_name}' at line {line_no} "
                        f"(first at line {seen_sections[section_name]})"
                    )
            else:
                seen_sections[section_name] = line_no

            current_section = section_name
            if section_name not in sections:
                sections.append(section_name)
            if section_name not in keys_by_section:
                keys_by_section[section_name] = []
            continue

        eq_match = re.match(r"^([^=:\s]+)\s*[=:]\s*(.*)", stripped)
        if not eq_match:
            invalid_lines.append(
                {
                    "line": line_no,
                    "text": raw_line,
                    "reason": "not a valid key=value line or section header",
                }
            )
            parse_ok = False
            continue

        key = eq_match.group(1).strip()

        section_key = (current_section, key)
        section_label = current_section or "(top-level)"

        if section_key in seen_keys:
            dup_info2: dict[str, object] = {
                "key": key,
                "section": section_label,
                "first_line": seen_keys[section_key],
                "second_line": line_no,
            }
            duplicates.append(dup_info2)
            if duplicate_policy == "error":
                parse_ok = False
                findings.append(
                    f"Duplicate key '{key}' in section '{section_label}' at line {line_no} "
                    f"(first at line {seen_keys[section_key]})"
                )
            elif duplicate_policy == "warn":
                findings.append(
                    f"Duplicate key '{key}' in section '{section_label}' at line {line_no} "
                    f"(first at line {seen_keys[section_key]})"
                )
        else:
            seen_keys[section_key] = line_no

        if current_section is not None:
            keys_by_section.setdefault(current_section, []).append(key)
        else:
            keys_by_section.setdefault("(top-level)", []).append(key)

    if not sections and not keys_by_section.get("(top-level)") and not invalid_lines:
        findings.append("No sections or keys found")

    return IniValidateResult(
        parse_ok=parse_ok,
        sections=sections,
        keys_by_section=keys_by_section,
        duplicates=duplicates,
        invalid_lines=invalid_lines,
        findings=findings,
    )
