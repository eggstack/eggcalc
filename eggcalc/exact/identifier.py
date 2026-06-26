"""
Identifier analysis for naming convention validation across languages.

Provides classification and validation of identifier names for Python,
Rust, JavaScript, and environment variable naming conventions.
"""

from __future__ import annotations

import keyword
import re
from typing import TypedDict


class IdentifierAnalyzeResult(TypedDict):
    text: str
    classification: str
    python_valid: bool
    python_keyword: bool
    rust_valid: bool | None
    javascript_valid: bool | None
    env_valid: bool
    suggestions: dict[str, str]
    warnings: list[str]
    summary: str


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

_ENV_PATTERN = re.compile(r"^[A-Z_][A-Z0-9_]*$")


def _is_valid_ident_chars(text: str, extra_chars: str = "") -> bool:
    for char in text:
        if not (char.isalnum() or char == "_" or char in extra_chars):
            return False
    return True


def _is_snake_case(text: str) -> bool:
    if not text:
        return False
    if "_" not in text:
        return False
    if not _is_valid_ident_chars(text):
        return False
    parts = text.split("_")
    if any(not part.islower() and part for part in parts):
        return False
    return True


def _is_camel_case(text: str) -> bool:
    if not text:
        return False
    if text[0].isupper():
        return False
    if "_" in text or "-" in text:
        return False
    if not text.isidentifier():
        return False
    has_upper = any(c.isupper() for c in text)
    return has_upper


def _is_pascal_case(text: str) -> bool:
    if not text:
        return False
    if text[0].islower():
        return False
    if "_" in text or "-" in text:
        return False
    if not text.isidentifier():
        return False
    has_upper = any(c.isupper() for c in text)
    return has_upper


def _is_kebab_case(text: str) -> bool:
    if not text:
        return False
    if "-" not in text:
        return False
    if not _is_valid_ident_chars(text, "-"):
        return False
    parts = text.split("-")
    if any(not part.islower() and part for part in parts):
        return False
    return True


def _is_screaming_snake_case(text: str) -> bool:
    if not text:
        return False
    if not _is_valid_ident_chars(text):
        return False
    parts = text.split("_")
    if any(not part.isupper() and part for part in parts):
        return False
    return True


def _classify(text: str) -> str:
    if _is_snake_case(text):
        return "snake_case"
    if _is_camel_case(text):
        return "camelCase"
    if _is_pascal_case(text):
        return "PascalCase"
    if _is_kebab_case(text):
        return "kebab-case"
    if _is_screaming_snake_case(text):
        return "SCREAMING_SNAKE_CASE"
    if text.isidentifier():
        return "mixed"
    return "invalid"


def _to_snake_case(text: str) -> str:
    result: list[str] = []
    prev_upper = False
    prev_underscore = False
    for i, char in enumerate(text):
        if char == "_" or char == "-":
            prev_underscore = True
            continue
        if char.isupper():
            if (
                result
                and not prev_underscore
                and (prev_upper or i + 1 < len(text) and text[i + 1].isupper())
            ):
                result.append("_")
            result.append(char.lower())
            prev_upper = True
        else:
            result.append(char)
            prev_upper = False
        prev_underscore = False
    return "".join(result)


def _to_pascal_case(text: str) -> str:
    snake = _to_snake_case(text)
    parts = snake.split("_") if "_" in snake else [snake]
    result = []
    for part in parts:
        if part:
            result.append(part[0].upper() + part[1:].lower())
    return "".join(result)


def _to_camel_case(text: str) -> str:
    pascal = _to_pascal_case(text)
    if pascal:
        return pascal[0].lower() + pascal[1:]
    return pascal


def _to_kebab_case(text: str) -> str:
    return _to_snake_case(text).replace("_", "-")


def _to_screaming_snake_case(text: str) -> str:
    return _to_snake_case(text).upper()


def identifier_analyze(
    text: str,
    languages: list[str] | None = None,
) -> IdentifierAnalyzeResult:
    """Analyze an identifier and classify its naming convention.

    Args:
        text: The identifier to analyze.
        languages: List of languages to validate against.
                   Defaults to ["python", "rust", "javascript", "env"].

    Returns:
        IdentifierAnalyzeResult with classification, validation, and suggestions.
    """
    if languages is None:
        languages = ["python", "rust", "javascript", "env"]

    classification = _classify(text)

    python_valid = False
    python_keyword = False
    if "python" in languages:
        python_valid = text.isidentifier()
        if python_valid:
            python_keyword = keyword.iskeyword(text)

    rust_valid: bool | None = None
    if "rust" in languages:
        if text.isidentifier():
            rust_valid = text not in _RUST_KEYWORDS
        else:
            rust_valid = False

    javascript_valid: bool | None = None
    if "javascript" in languages:
        if text.isidentifier():
            javascript_valid = True
        else:
            javascript_valid = False

    env_valid = False
    if "env" in languages:
        env_valid = bool(_ENV_PATTERN.match(text))

    warnings: list[str] = []
    if python_keyword:
        warnings.append("Python keyword - cannot be used as identifier in Python")
    if rust_valid is False and "rust" in languages:
        warnings.append("Rust keyword - cannot be used as identifier in Rust")
    if classification == "mixed":
        warnings.append("Identifier has mixed naming convention")
    if text.startswith("_"):
        warnings.append(
            "Identifier starts with underscore - typically reserved for private/use-only"
        )

    suggestions = {
        "snake_case": _to_snake_case(text),
        "kebab_case": _to_kebab_case(text),
        "pascal_case": _to_pascal_case(text),
        "camel_case": _to_camel_case(text),
        "screaming_snake_case": _to_screaming_snake_case(text),
    }

    summary_parts = []
    if classification != "invalid":
        summary_parts.append(f"Style: {classification}")
    else:
        summary_parts.append("Invalid identifier")

    valid_langs = []
    if python_valid and not python_keyword:
        valid_langs.append("Python")
    if rust_valid is True:
        valid_langs.append("Rust")
    if javascript_valid is True:
        valid_langs.append("JavaScript")
    if env_valid:
        valid_langs.append("env")

    if valid_langs:
        summary_parts.append(f"Valid in: {', '.join(valid_langs)}")

    if python_keyword:
        summary_parts.append("Python: reserved keyword")

    summary = ". ".join(summary_parts)

    return IdentifierAnalyzeResult(
        text=text,
        classification=classification,
        python_valid=python_valid,
        python_keyword=python_keyword,
        rust_valid=rust_valid,
        javascript_valid=javascript_valid,
        env_valid=env_valid,
        suggestions=suggestions,
        warnings=warnings,
        summary=summary,
    )
