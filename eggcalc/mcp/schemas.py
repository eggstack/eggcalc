"""
MCP tool schemas for eggcalc.

Defines input/output schemas for each MCP tool following the
consistency requirements in the plan.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypedDict


class FindingSpan(TypedDict, total=False):
    """Location span within a finding."""

    byte_start: int
    byte_end: int
    char_start: int
    char_end: int
    line: int
    column: int


class Finding(TypedDict, total=False):
    """Structured finding emitted by MCP tools."""

    code: str
    severity: str  # "info" | "warn" | "error"
    message: str
    span: FindingSpan
    details: dict[str, Any]


class ErrorEnvelope(TypedDict):
    """Standard error envelope for MCP tool responses."""

    ok: bool
    error_type: str
    error: str
    hints: list[str]
    tool: str | None
    warnings: list[str]


class ToolAnnotations(TypedDict, total=False):
    """Standard MCP tool annotations (hints, not security enforcement).

    All eggcalc tools are local, deterministic, closed-world operations
    over caller-supplied arguments (no network, filesystem writes, or
    destructive mutations). The uniform posture below reflects that;
    profile permissions and evaluator side-effect policy remain the
    authoritative enforcement and never consult these hints.
    """

    title: str
    readOnlyHint: bool
    destructiveHint: bool
    idempotentHint: bool
    openWorldHint: bool


#: Uniform annotation posture for every tool. Stored alongside the
#: catalog authority (TOOL_SCHEMAS/TOOL_METADATA) so Plan 040 can migrate
#: it mechanically into a consolidated catalog record.
DEFAULT_TOOL_ANNOTATIONS: ToolAnnotations = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}


def get_tool_annotations(name: str) -> ToolAnnotations:
    """Return the standard MCP annotations for *name*.

    Currently uniform across the catalog; per-tool overrides (if a
    future tool performs I/O) belong here, not in server emission code.
    """
    override = TOOL_ANNOTATIONS.get(name)
    if override is not None:
        merged = dict(DEFAULT_TOOL_ANNOTATIONS)
        merged.update(override)
        return merged  # type: ignore[return-value]
    return dict(DEFAULT_TOOL_ANNOTATIONS)  # type: ignore[return-value]


#: Per-tool annotation overrides. Empty while every tool shares the
#: uniform read-only/closed-world posture; entries here merge over
#: DEFAULT_TOOL_ANNOTATIONS via get_tool_annotations().
TOOL_ANNOTATIONS: dict[str, ToolAnnotations] = {}


TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "math_eval": {
        "description": "Evaluate arithmetic, unit conversions, constants, and scientific expressions deterministically. State-mutating functions (setvar, store, etc.) and non-deterministic functions (random, randint, gauss, etc.) are disabled. Use for math and unit tasks instead of asking the model to calculate.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Math expression to evaluate (e.g., '5 + 3', '30m + 100ft', 'five plus three')",
                    "maxLength": 10000,
                },
            },
            "required": ["expression"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "value": {"type": "string", "description": "Evaluation result as string"},
                "type": {"type": "string", "description": "Python type name of the result"},
                "unit": {
                    "type": ["string", "null"],
                    "description": "Unit name (only when result has units)",
                },
                "display": {
                    "type": ["string", "null"],
                    "description": "Human-readable result with units (only when result has units)",
                },
            },
        },
    },
    "unit_convert": {
        "description": "Convert a numeric value from one unit to another using pre-defined conversion factors.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "value": {
                    "type": "number",
                    "description": "Numeric value to convert (must be finite; NaN and infinity are rejected)",
                },
                "from_unit": {
                    "type": "string",
                    "description": "Source unit (e.g., 'km', 'ft', 'kg')",
                },
                "to_unit": {"type": "string", "description": "Target unit (e.g., 'm', 'in', 'lb')"},
            },
            "required": ["value", "from_unit", "to_unit"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "value": {"type": "number", "description": "Converted value"},
                "from_unit": {"type": "string"},
                "to_unit": {"type": "string"},
                "factor": {
                    "type": ["number", "null"],
                    "description": "Conversion factor used (null for temperature conversions)",
                },
            },
        },
    },
    "unit_info": {
        "description": "Get information about a unit including its canonical form and category.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "unit": {
                    "type": "string",
                    "description": "Unit name or alias (e.g., 'km', 'kilogram', '℃')",
                },
            },
            "required": ["unit"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "unit": {"type": "string"},
                "canonical": {"type": "string", "description": "Canonical unit name"},
                "category": {
                    "type": "string",
                    "description": "Unit category (e.g., 'length', 'mass', 'temperature')",
                },
                "is_valid": {"type": "boolean"},
            },
        },
    },
    "constant_lookup": {
        "description": "Look up physical constant values and symbols (Avogadro, Planck, speed of light, etc.).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Constant name (e.g., 'avogadro', 'planck', 'c', 'G')",
                },
            },
            "required": ["name"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "value": {"type": "number", "description": "Constant value"},
                "symbol": {
                    "type": "string",
                    "description": "Display symbol (e.g., 'N_A', 'h', 'c')",
                },
                "display_name": {"type": "string", "description": "Human-readable name"},
            },
        },
    },
    "text_measure": {
        "description": "Measure exact text properties: UTF-8 byte length, codepoint count, words, lines, whitespace, newline style, Unicode normalization state, invisibles, and mixed-script signals.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Input string to measure",
                },
                "detail": {
                    "type": "string",
                    "enum": ["summary", "normal", "full"],
                    "default": "normal",
                    "description": "Detail level for output",
                },
            },
            "required": ["text"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "bytes_utf8": {"type": "integer"},
                "codepoints": {"type": "integer"},
                "graphemes": {"type": "integer"},
                "words": {"type": "integer"},
                "unique_words_casefolded": {"type": "integer"},
                "lines": {"type": "integer"},
                "nonempty_lines": {"type": "integer"},
                "blank_lines": {"type": "integer"},
                "max_line_length_codepoints": {"type": "integer"},
                "chars_no_whitespace": {"type": "integer"},
                "ascii": {"type": "integer"},
                "non_ascii": {"type": "integer"},
                "letters": {"type": "integer"},
                "digits": {"type": "integer"},
                "punctuation": {"type": "integer"},
                "symbols": {"type": "integer"},
                "spaces": {"type": "integer"},
                "control_chars": {"type": "integer"},
                "combining_marks": {"type": "integer"},
                "invisible_chars": {"type": "integer"},
                "newline_style": {"type": "string"},
                "ends_with_newline": {"type": "boolean"},
                "normalization": {"type": "object"},
                "unicode_risks": {"type": "object"},
                "warnings": {"type": "array"},
            },
        },
    },
    "text_equal": {
        "description": "Compare two strings under raw, Unicode-normalized, casefolded, or trimmed modes and report exact equality evidence.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "a": {"type": "string", "description": "First string"},
                "b": {"type": "string", "description": "Second string"},
                "normalization": {
                    "type": "string",
                    "enum": ["raw", "NFC", "NFD", "NFKC", "NFKD"],
                    "default": "raw",
                    "description": "Unicode normalization form",
                },
                "casefold": {
                    "type": "boolean",
                    "default": False,
                    "description": "Use casefolded comparison",
                },
                "trim": {
                    "type": "boolean",
                    "default": False,
                    "description": "Trim whitespace",
                },
                "ignore_newline_style": {
                    "type": "boolean",
                    "default": False,
                    "description": "Normalize different newline styles before comparison",
                },
                "ignore_trailing_whitespace": {
                    "type": "boolean",
                    "default": False,
                    "description": "Ignore trailing whitespace on each line",
                },
                "ignore_final_newline": {
                    "type": "boolean",
                    "default": False,
                    "description": "Ignore trailing newline at end of strings",
                },
            },
            "required": ["a", "b"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "equal": {"type": "boolean"},
                "mode": {"type": "object"},
                "raw_equal": {"type": "boolean"},
                "nfc_equal": {"type": "boolean"},
                "nfd_equal": {"type": "boolean"},
                "nfkc_equal": {"type": "boolean"},
                "nfkd_equal": {"type": "boolean"},
                "casefold_equal": {"type": "boolean"},
                "byte_equal": {"type": "boolean"},
                "lengths": {"type": "object"},
                "first_difference": {"type": ["object", "null"]},
                "classification": {"type": "string"},
            },
        },
    },
    "text_diff_explain": {
        "description": "Explain why two strings differ, including spans, codepoints, Unicode names, normalization equivalence, confusables, invisibles, and agent-facing classification.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "a": {"type": "string", "description": "First string"},
                "b": {"type": "string", "description": "Second string"},
                "max_diffs": {
                    "type": "integer",
                    "default": 20,
                    "minimum": 0,
                    "maximum": 10000,
                    "description": "Maximum diff spans to return",
                },
                "include_codepoints": {
                    "type": "boolean",
                    "default": True,
                    "description": "Include codepoint details",
                },
                "include_context": {
                    "type": "boolean",
                    "default": True,
                    "description": "Include context notes",
                },
                "detail": {
                    "type": "string",
                    "enum": ["summary", "normal", "full"],
                    "default": "normal",
                    "description": "Detail level: summary (compact), normal, or full",
                },
            },
            "required": ["a", "b"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "equal": {"type": "boolean"},
                "classification": {"type": "string"},
                "summary": {"type": "object"},
                "a_metrics": {"type": "object"},
                "b_metrics": {"type": "object"},
                "diffs": {"type": "array"},
                "security_findings": {"type": "array"},
                "agent_instruction": {"type": "string"},
            },
        },
    },
    "text_inspect": {
        "description": "Inspect a string for hidden characters, Unicode confusables, mixed scripts, normalization state, and display-safe representation. Can report both original and normalized text analysis.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Input string to inspect"},
                "include_codepoints": {
                    "type": "boolean",
                    "default": True,
                    "description": "Include codepoint details in invisibles",
                },
                "include_confusables": {
                    "type": "boolean",
                    "default": True,
                    "description": "Check for confusables",
                },
                "detail": {
                    "type": "string",
                    "enum": ["summary", "normal", "full"],
                    "default": "normal",
                    "description": "Detail level: summary (compact), normal, or full",
                },
                "normalize": {
                    "type": "string",
                    "enum": ["none", "NFC", "NFD", "NFKC", "NFKD"],
                    "default": "none",
                    "description": "Normalization form to analyze",
                },
                "compare_normalized": {
                    "type": "boolean",
                    "default": False,
                    "description": "Report both original and normalized analysis",
                },
            },
            "required": ["text"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "safe_repr": {"type": "string"},
                "metrics": {"type": "object"},
                "normalization": {"type": "object"},
                "normalization_diff": {"type": "boolean"},
                "normals_repr": {"type": ["string", "null"]},
                "invisibles": {"type": "array"},
                "bidi_controls": {"type": "array"},
                "mixed_scripts": {"type": "object"},
                "confusables": {"type": "array"},
                "warnings": {"type": "array"},
                "limits_applied": {"type": "array"},
                "normalize": {"type": "string"},
                "compare_normalized": {"type": "boolean"},
                "original": {"type": "object"},
                "normalized": {"type": ["object", "null"]},
                "normalization_findings": {"type": "array"},
            },
        },
    },
    "text_count": {
        "description": "Count exact characters or produce a character frequency table with codepoint positions, grapheme clusters, bytes, or substring matches.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Input string"},
                "target": {
                    "type": ["string", "null"],
                    "default": None,
                    "description": "Single character to count (None for frequency table)",
                },
                "normalization": {
                    "type": "string",
                    "enum": ["raw", "NFC", "NFKC"],
                    "default": "raw",
                    "description": "Unicode normalization form",
                },
                "count_mode": {
                    "type": "string",
                    "enum": ["codepoint", "grapheme", "byte", "substring"],
                    "default": "codepoint",
                    "description": "Count mode: codepoint (Python str), grapheme (user-perceived), byte (UTF-8), substring",
                },
            },
            "required": ["text"],
        },
        "outputSchema": {
            "type": "object",
            "description": "With target: {count, positions, target, normalization, text_length_codepoints}. Without target: character frequency table as {char: count} pairs.",
            "properties": {
                "count": {"type": "integer"},
                "positions": {"type": "array"},
                "target": {"type": ["string", "null"]},
                "normalization": {"type": ["string", "null"]},
                "text_length_codepoints": {"type": "integer"},
            },
            "additionalProperties": True,
        },
    },
    "text_truncate": {
        "description": "Truncate a string to a specified number of grapheme clusters (user-perceived characters). Preserves emoji, combining sequences, and flag sequences intact. Useful for AI agent prompts where visual length matters.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Input string to truncate"},
                "max_graphemes": {
                    "type": "integer",
                    "description": "Maximum number of grapheme clusters to return",
                    "minimum": 0,
                    "maximum": 1000000,
                },
            },
            "required": ["text", "max_graphemes"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Result string (truncated if truncation occurred)",
                },
                "original_graphemes": {"type": "integer", "description": "Original grapheme count"},
                "truncated_graphemes": {
                    "type": "integer",
                    "description": "Grapheme count in result",
                },
                "truncated": {"type": "boolean", "description": "True if text was truncated"},
            },
        },
    },
    "text_transform": {
        "description": "Apply deterministic text transformations: Unicode normalization (NFC/NFD/NFKC/NFKD), casefold, trim, newline normalization, zero-width removal, bidi control stripping, and visible representation.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Input string to transform"},
                "operations": {
                    "type": "array",
                    "items": {"type": "string"},
                    "maxItems": 100,
                    "description": "Operations to apply: normalize_nfc, normalize_nfd, normalize_nfkc, normalize_nfkd, casefold, trim, trim_trailing_whitespace, normalize_newlines_lf, ensure_final_newline, strip_final_newline, remove_zero_width, remove_bidi_controls, visible_repr",
                },
                "detail": {
                    "type": "string",
                    "enum": ["summary", "normal", "full"],
                    "default": "normal",
                },
            },
            "required": ["text", "operations"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "changed": {"type": "boolean"},
                "text": {"type": "string"},
                "operations_applied": {"type": "array", "items": {"type": "string"}},
                "removed": {"type": "array"},
                "warnings": {"type": "array", "items": {"type": "string"}},
                "summary": {"type": "string"},
            },
        },
    },
    "validate_brackets": {
        "description": "Check whether delimiters are structurally balanced and report unmatched delimiters with line/column positions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Input string"},
                "pairs": {
                    "type": "object",
                    "description": "Bracket pair mapping (default: () [] {} <>)",
                },
            },
            "required": ["text"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "balanced": {"type": "boolean"},
                "unmatched_openers": {"type": "array"},
                "unmatched_closers": {"type": "array"},
            },
        },
    },
    "validate_json": {
        "description": "Validate JSON and report precise parse errors or top-level structure information.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Input string to validate as JSON"},
            },
            "required": ["text"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "valid": {"type": "boolean"},
                "error": {"type": ["string", "null"]},
                "line": {"type": ["integer", "null"]},
                "column": {"type": ["integer", "null"]},
                "position": {"type": ["integer", "null"]},
                "type": {"type": ["string", "null"]},
                "top_level_keys": {"type": ["array", "null"], "items": {"type": "string"}},
            },
        },
    },
    "validate_regex": {
        "description": "Test a Python regular expression against sample strings and report match/fullmatch status, spans, groups, and errors.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Regular expression pattern",
                    "maxLength": 1000,
                },
                "samples": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of strings to test against",
                    "maxItems": 100,
                },
                "flags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Flag names (IGNORECASE, MULTILINE, etc.)",
                    "maxItems": 10,
                },
                "ignore_case": {
                    "type": "boolean",
                    "default": False,
                    "description": "Use IGNORECASE flag",
                },
                "multiline": {
                    "type": "boolean",
                    "default": False,
                    "description": "Use MULTILINE flag",
                },
                "dotall": {
                    "type": "boolean",
                    "default": False,
                    "description": "Use DOTALL flag",
                },
                "ascii": {
                    "type": "boolean",
                    "default": False,
                    "description": "Use ASCII flag",
                },
            },
            "required": ["pattern", "samples"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "valid_pattern": {"type": "boolean"},
                "results": {"type": "array"},
                "error": {"type": ["string", "null"]},
                "flags_used": {"type": "object"},
            },
        },
    },
    "list_compare": {
        "description": "Compare two lists with explicit modes: ordered ( LCS-based alignment), set (presence only), multiset (count deltas). Near matches are optional and never replace exact missing/extra results.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "a": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "First list",
                    "maxItems": 10000,
                },
                "b": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Second list",
                    "maxItems": 10000,
                },
                "mode": {
                    "type": "string",
                    "enum": ["ordered", "set", "multiset"],
                    "default": "set",
                    "description": "Comparison mode: ordered (first diff, aligned ops), set (presence only), multiset (count deltas)",
                },
                "casefold": {
                    "type": "boolean",
                    "default": False,
                    "description": "Casefold elements before comparison",
                },
                "normalization": {
                    "type": "string",
                    "enum": ["raw", "NFC", "NFD", "NFKC", "NFKD"],
                    "default": "NFC",
                    "description": "Unicode normalization form",
                },
                "trim": {
                    "type": "boolean",
                    "default": False,
                    "description": "Trim whitespace from each element",
                },
                "include_near_matches": {
                    "type": "boolean",
                    "default": False,
                    "description": "Include near matches (fuzzy matching)",
                },
                "near_match_threshold": {
                    "type": "integer",
                    "default": 2,
                    "description": "Maximum edit distance for near matches",
                },
                "ignore_order": {
                    "type": "boolean",
                    "description": "Legacy: use mode=set or mode=multiset instead",
                },
                "treat_as_multiset": {
                    "type": "boolean",
                    "description": "Legacy: use mode=multiset instead",
                },
            },
            "required": ["a", "b"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "equal": {"type": "boolean"},
                "first_diff_index": {
                    "type": ["integer", "null"],
                    "description": "Index of first difference (ordered mode)",
                },
                "equal_prefix_length": {
                    "type": "integer",
                    "description": "Length of equal prefix (ordered mode)",
                },
                "aligned": {"type": "array", "description": "Aligned operations (ordered mode)"},
                "count_deltas": {
                    "type": "object",
                    "description": "Count differences (multiset mode)",
                },
                "only_in_a": {"type": "array"},
                "only_in_b": {"type": "array"},
                "missing_in_a": {"type": "array", "description": "Alias for only_in_b"},
                "missing_in_b": {"type": "array", "description": "Alias for only_in_a"},
                "duplicates_in_a": {"type": "array"},
                "duplicates_in_b": {"type": "array"},
                "near_matches": {
                    "type": "array",
                    "description": "Items that differ only by edit distance",
                },
            },
        },
    },
    "validate_toml": {
        "description": "Validate TOML configuration files (Cargo.toml, pyproject.toml, etc.) and report parse errors with line/column positions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "TOML document string to validate"},
                "detail": {
                    "type": "string",
                    "enum": ["summary", "normal", "full"],
                    "default": "normal",
                },
            },
            "required": ["text"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "valid": {"type": "boolean"},
                "error": {"type": ["string", "null"]},
                "line": {"type": ["integer", "null"]},
                "column": {"type": ["integer", "null"]},
                "position": {"type": ["integer", "null"]},
                "type": {"type": ["string", "null"]},
                "top_level_keys": {"type": ["array", "null"]},
                "tables": {"type": ["array", "null"]},
            },
        },
    },
    "json_extract": {
        "description": "Extract a value from JSON using RFC 6901 JSON Pointer (e.g., /foo/bar/0). Navigate nested objects and arrays.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "JSON document string"},
                "pointer": {
                    "type": "string",
                    "default": "",
                    "description": "RFC 6901 JSON Pointer path (e.g., /dependencies/tokio)",
                },
                "detail": {
                    "type": "string",
                    "enum": ["summary", "normal", "full"],
                    "default": "normal",
                },
                "max_output_chars": {"type": "integer", "default": 4000},
            },
            "required": ["text"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "valid_json": {"type": "boolean"},
                "found": {"type": "boolean"},
                "pointer": {"type": "string"},
                "value_type": {"type": ["string", "null"]},
                "value": {"description": "Extracted value"},
                "preview": {"type": ["string", "null"]},
                "child_keys": {"type": ["array", "null"], "items": {"type": "string"}},
                "array_length": {"type": ["integer", "null"]},
                "truncated": {"type": "boolean"},
                "missing_at": {"type": ["string", "null"]},
                "reason": {"type": ["string", "null"]},
                "available_keys": {"type": ["array", "null"], "items": {"type": "string"}},
                "error": {"type": ["string", "null"]},
                "line": {"type": ["integer", "null"]},
                "column": {"type": ["integer", "null"]},
                "summary": {"type": "string"},
            },
        },
    },
    "json_compare": {
        "description": "Compare two JSON documents semantically, ignoring formatting and key order.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "a": {"type": "string", "description": "First JSON document"},
                "b": {"type": "string", "description": "Second JSON document"},
                "ignore_object_order": {"type": "boolean", "default": True},
                "ignore_array_order": {"type": "boolean", "default": False},
                "numeric_string_equivalence": {"type": "boolean", "default": False},
                "casefold_keys": {"type": "boolean", "default": False},
                "treat_missing_null_as_equal": {"type": "boolean", "default": False},
                "max_diffs": {"type": "integer", "default": 50, "minimum": 0, "maximum": 10000},
                "detail": {
                    "type": "string",
                    "enum": ["summary", "normal", "full"],
                    "default": "normal",
                },
            },
            "required": ["a", "b"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "valid_json_a": {"type": "boolean"},
                "valid_json_b": {"type": "boolean"},
                "equal": {"type": "boolean"},
                "same_type": {"type": "boolean"},
                "diff_count": {"type": "integer"},
                "diffs": {"type": "array", "description": "List of differences"},
                "truncated": {"type": "boolean"},
                "summary": {"type": "string"},
            },
        },
    },
    "text_position": {
        "description": "Convert between byte offsets, codepoint indices, line/column positions, and UTF-16 offsets.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "byte_offset": {"type": "integer", "minimum": 0, "maximum": 1000000000},
                "codepoint_index": {"type": "integer", "minimum": 0, "maximum": 1000000000},
                "line": {"type": "integer", "minimum": 0, "maximum": 1000000000},
                "column": {"type": "integer", "minimum": 0, "maximum": 1000000000},
                "utf16_offset": {"type": "integer", "minimum": 0, "maximum": 1000000000},
                "line_base": {"type": "integer", "default": 1, "minimum": 0, "maximum": 1},
                "column_base": {"type": "integer", "default": 1, "minimum": 0, "maximum": 1},
                "detail": {
                    "type": "string",
                    "enum": ["summary", "normal", "full"],
                    "default": "normal",
                },
            },
            "required": ["text"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "valid": {"type": "boolean"},
                "byte_offset": {"type": ["integer", "null"]},
                "codepoint_index": {"type": ["integer", "null"]},
                "utf16_offset": {"type": ["integer", "null"]},
                "line": {"type": ["integer", "null"]},
                "column": {"type": ["integer", "null"]},
                "line_base": {"type": "integer"},
                "column_base": {"type": "integer"},
                "char": {"type": ["string", "null"]},
                "codepoint": {"type": ["string", "null"]},
                "name": {"type": ["string", "null"]},
                "line_text_preview": {"type": ["string", "null"]},
                "error": {"type": ["string", "null"]},
                "summary": {"type": "string"},
            },
        },
    },
    "text_hash": {
        "description": "Compute cryptographic hashes of text for identity checking.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "algorithms": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Hash algorithms (sha256, sha1, md5, crc32)",
                    "default": ["sha256"],
                    "maxItems": 10,
                },
                "encoding": {"type": "string", "default": "utf-8"},
                "detail": {
                    "type": "string",
                    "enum": ["summary", "normal", "full"],
                    "default": "normal",
                },
            },
            "required": ["text"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "encoding": {"type": "string"},
                "bytes": {"type": "integer"},
                "codepoints": {"type": "integer"},
                "hashes": {"type": "object", "description": "Map of algorithm to hash value"},
                "warnings": {"type": "array", "items": {"type": "string"}},
                "summary": {"type": "string"},
            },
        },
    },
    "escape_text": {
        "description": "Escape text for various output formats.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "mode": {
                    "type": "string",
                    "enum": [
                        "json_string",
                        "python_string",
                        "rust_string",
                        "posix_shell_single",
                        "regex_literal",
                        "markdown_inline_code",
                        "markdown_code_block",
                        "html_text",
                        "url_component",
                    ],
                },
                "detail": {
                    "type": "string",
                    "enum": ["summary", "normal", "full"],
                    "default": "normal",
                },
            },
            "required": ["text", "mode"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "mode": {"type": "string"},
                "escaped": {"type": "string"},
                "changed": {"type": "boolean"},
                "summary": {"type": "string"},
            },
        },
    },
    "unescape_text": {
        "description": "Unescape text from various formats.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "mode": {
                    "type": "string",
                    "enum": ["json_string", "python_string", "unicode_escape", "url_component"],
                },
                "detail": {
                    "type": "string",
                    "enum": ["summary", "normal", "full"],
                    "default": "normal",
                },
            },
            "required": ["text", "mode"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "mode": {"type": "string"},
                "unescaped": {"type": "string"},
                "changed": {"type": "boolean"},
                "error": {"type": ["string", "null"]},
                "summary": {"type": "string"},
            },
        },
    },
    "identifier_analyze": {
        "description": "Classify and validate identifier naming conventions across languages.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "languages": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Languages to check (python, rust, javascript, env)",
                    "default": ["python", "rust", "javascript", "env"],
                },
                "detail": {
                    "type": "string",
                    "enum": ["summary", "normal", "full"],
                    "default": "normal",
                },
            },
            "required": ["text"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "classification": {"type": "string"},
                "python_valid": {"type": "boolean"},
                "python_keyword": {"type": "boolean"},
                "rust_valid": {"type": ["boolean", "null"]},
                "javascript_valid": {"type": ["boolean", "null"]},
                "env_valid": {"type": "boolean"},
                "suggestions": {
                    "type": "object",
                    "description": "Map of language to suggested name",
                },
                "warnings": {"type": "array", "items": {"type": "string"}},
                "summary": {"type": "string"},
            },
        },
    },
    "regex_finditer": {
        "description": "Find all regex matches in text with positions, line/column info, and capture groups.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Regular expression pattern",
                    "maxLength": 1000,
                },
                "text": {"type": "string", "description": "Input string to search"},
                "flags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Flag names (IGNORECASE, MULTILINE, DOTALL, etc.)",
                    "maxItems": 10,
                },
                "max_matches": {
                    "type": "integer",
                    "default": 100,
                    "description": "Maximum matches to return",
                    "maximum": 1000,
                },
                "include_line_column": {
                    "type": "boolean",
                    "default": True,
                    "description": "Include line and column info",
                },
                "include_groups": {
                    "type": "boolean",
                    "default": True,
                    "description": "Include capture groups",
                },
            },
            "required": ["pattern", "text"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "valid_pattern": {"type": "boolean"},
                "matches": {
                    "type": "array",
                    "description": "List of regex matches with positions and groups",
                },
                "truncated": {"type": "boolean"},
                "match_count": {"type": "integer"},
                "error": {"type": ["string", "null"]},
            },
        },
    },
    "regex_safety_check": {
        "description": "Heuristic check for potential catastrophic backtracking risks in regex patterns. Flags nested quantifiers, repeated alternations, ambiguous dot-star, and backreferences.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regular expression pattern to check"},
            },
            "required": ["pattern"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "valid_pattern": {"type": "boolean"},
                "risk": {"type": "string", "enum": ["low", "medium", "high"]},
                "findings": {
                    "type": "array",
                    "description": "Safety findings with kind, span, and message",
                    "items": {
                        "type": "object",
                        "properties": {
                            "kind": {"type": "string"},
                            "span": {"type": "array", "items": {"type": "integer"}},
                            "message": {"type": "string"},
                        },
                    },
                },
            },
        },
    },
    "validate_schema_light": {
        "description": "Validate JSON against a simple schema format with type, required, enum, pattern, and nested constraints.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "JSON document to validate"},
                "schema": {"type": "object", "description": "Schema to validate against"},
                "detail": {
                    "type": "string",
                    "enum": ["summary", "normal", "full"],
                    "default": "normal",
                },
            },
            "required": ["text", "schema"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "valid": {"type": "boolean"},
                "violations": {
                    "type": "array",
                    "description": "Schema violations with path and message",
                    "items": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "message": {"type": "string"},
                            "value_type": {"type": ["string", "null"]},
                            "expected_type": {"type": ["string", "null"]},
                        },
                    },
                },
                "truncated": {"type": "boolean"},
                "summary": {"type": "string"},
            },
        },
    },
    "path_normalize": {
        "description": "Normalize a path using posixpath or ntpath semantics. Collapse dot segments, resolve components.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path string to normalize"},
                "platform": {
                    "type": "string",
                    "enum": ["posix", "windows"],
                    "default": "posix",
                    "description": "Platform semantics to use",
                },
                "collapse_dot_segments": {
                    "type": "boolean",
                    "default": True,
                    "description": "Collapse dot and dot-dot segments",
                },
                "preserve_trailing_separator": {
                    "type": "boolean",
                    "default": False,
                    "description": "Preserve trailing separator",
                },
            },
            "required": ["path"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "normalized": {"type": "string"},
                "is_absolute": {"type": "boolean"},
                "components": {"type": "array", "items": {"type": "string"}},
                "warnings": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
    "path_analyze": {
        "description": "Analyze path components, extensions, hidden status, and traversal without filesystem access.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "style": {
                    "type": "string",
                    "enum": ["auto", "posix", "windows"],
                    "default": "auto",
                },
                "detail": {
                    "type": "string",
                    "enum": ["summary", "normal", "full"],
                    "default": "normal",
                },
            },
            "required": ["path"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "input": {"type": "string"},
                "style": {"type": "string"},
                "absolute": {"type": "boolean"},
                "has_traversal": {"type": "boolean"},
                "components": {"type": "array", "items": {"type": "string"}},
                "parent": {"type": ["string", "null"]},
                "name": {"type": ["string", "null"]},
                "stem": {"type": ["string", "null"]},
                "suffix": {"type": ["string", "null"]},
                "suffixes": {"type": "array", "items": {"type": "string"}},
                "hidden": {"type": "boolean"},
                "normalized_lexical": {"type": "string"},
                "warnings": {"type": "array", "items": {"type": "string"}},
                "summary": {"type": "string"},
            },
        },
    },
    "path_compare": {
        "description": "Compare two paths under explicit normalization rules: separator normalization, dot-segment collapsing, and optional case-insensitive comparison.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "left": {"type": "string", "description": "First path string"},
                "right": {"type": "string", "description": "Second path string"},
                "platform": {
                    "type": "string",
                    "enum": ["posix", "windows"],
                    "default": "posix",
                    "description": "Platform semantics",
                },
                "case_sensitive": {
                    "type": "boolean",
                    "default": True,
                    "description": "Case-sensitive comparison",
                },
                "normalize_separators": {
                    "type": "boolean",
                    "default": True,
                    "description": "Normalize path separators",
                },
                "collapse_dot_segments": {
                    "type": "boolean",
                    "default": True,
                    "description": "Collapse . and .. segments",
                },
            },
            "required": ["left", "right"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "equal": {
                    "type": "boolean",
                    "description": "Whether paths are equal under normalization",
                },
                "left_normalized": {"type": "string", "description": "Normalized left path"},
                "right_normalized": {"type": "string", "description": "Normalized right path"},
                "differences": {"type": "array", "description": "List of differences found"},
                "findings": {"type": "array", "description": "Normalization notes"},
            },
        },
    },
    "path_scope_check": {
        "description": "Determine whether a target path remains lexically inside a declared root. Lexical only, does not resolve symlinks.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root": {"type": "string", "description": "Root directory path"},
                "target": {"type": "string", "description": "Target path to check"},
                "platform": {
                    "type": "string",
                    "enum": ["posix", "windows"],
                    "default": "posix",
                    "description": "Platform semantics",
                },
                "case_sensitive": {
                    "type": "boolean",
                    "default": True,
                    "description": "Case-sensitive comparison",
                },
            },
            "required": ["root", "target"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "inside_root": {
                    "type": "boolean",
                    "description": "Whether target is lexically inside root",
                },
                "root_normalized": {"type": "string", "description": "Normalized root path"},
                "target_normalized": {"type": "string", "description": "Normalized target path"},
                "relative_path": {
                    "type": "string",
                    "description": "Relative path from root to target (if inside)",
                },
                "escapes_via_dotdot": {
                    "type": "boolean",
                    "description": "Whether target contains parent traversal",
                },
                "absolute_target": {"type": "string", "description": "Absolute form of target"},
                "findings": {"type": "array", "description": "Analysis notes"},
            },
        },
    },
    "json_shape": {
        "description": "Analyze the structure of a JSON document without returning values. Shows type, keys, and nested structure with configurable depth limits.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "JSON document string to analyze"},
                "max_depth": {
                    "type": "integer",
                    "default": 4,
                    "description": "Maximum depth for nested structure",
                },
                "max_keys": {
                    "type": "integer",
                    "default": 100,
                    "description": "Maximum keys to show per object",
                },
                "max_array_items": {
                    "type": "integer",
                    "default": 5,
                    "description": "Maximum array item previews",
                },
            },
            "required": ["text"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "valid": {"type": "boolean"},
                "shape": {
                    "type": ["object", "null"],
                    "description": "Nested shape structure with type, keys, and counts",
                    "properties": {
                        "type": {"type": "string"},
                        "keys": {"type": ["object", "null"]},
                        "key_count": {"type": ["integer", "null"]},
                        "item_types": {"type": ["array", "null"]},
                        "item_count": {"type": ["integer", "null"]},
                    },
                },
                "truncated": {"type": "boolean"},
                "summary": {"type": "string"},
            },
        },
    },
    "text_window": {
        "description": "Get a window around a position in text with context lines. Shows line at position with surrounding context, position metrics, and character details.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Input string to analyze"},
                "position": {
                    "type": "object",
                    "description": "Position specification with kind and value",
                    "properties": {
                        "kind": {
                            "type": "string",
                            "enum": [
                                "byte_offset",
                                "codepoint_index",
                                "grapheme_index",
                                "line_column",
                            ],
                        },
                        "value": {
                            "type": "integer",
                            "description": "Value for byte_offset, codepoint_index, or grapheme_index",
                        },
                        "byte_offset": {
                            "type": "integer",
                            "description": "UTF-8 byte offset (alternative to value)",
                        },
                        "codepoint_index": {
                            "type": "integer",
                            "description": "Codepoint index (alternative to value)",
                        },
                        "grapheme_index": {
                            "type": "integer",
                            "description": "Grapheme index (alternative to value)",
                        },
                        "line": {
                            "type": "integer",
                            "description": "Line number for line_column kind",
                        },
                        "column": {
                            "type": "integer",
                            "description": "Column number for line_column kind",
                        },
                        "line_base": {
                            "type": "integer",
                            "default": 1,
                            "description": "Base for line numbers (1 for 1-based)",
                        },
                        "column_base": {
                            "type": "integer",
                            "default": 1,
                            "description": "Base for column numbers (1 for 1-based)",
                        },
                    },
                    "required": ["kind"],
                },
                "context_lines": {
                    "type": "integer",
                    "default": 2,
                    "description": "Number of context lines before and after",
                },
                "include_visible_repr": {
                    "type": "boolean",
                    "default": True,
                    "description": "Include visible representation of the line",
                },
            },
            "required": ["text", "position"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "position": {
                    "type": "object",
                    "description": "Resolved position with byte_offset, codepoint_index, grapheme_index, line, column",
                },
                "line_text": {"type": "string"},
                "line_visible_repr": {"type": "string"},
                "before": {"type": "array", "description": "Context lines before"},
                "after": {"type": "array", "description": "Context lines after"},
                "newline_style": {"type": "string"},
                "at_codepoint": {"type": ["object", "null"]},
                "warnings": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
    "json_canonicalize": {
        "description": "Canonicalize JSON with deterministic formatting, key ordering, duplicate key detection, and stable hashes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Input JSON string to canonicalize"},
                "sort_keys": {
                    "type": "boolean",
                    "default": True,
                    "description": "Sort object keys alphabetically",
                },
                "indent": {
                    "type": ["integer", "null"],
                    "description": "Indentation spaces (null for minified)",
                },
                "ensure_ascii": {
                    "type": "boolean",
                    "default": False,
                    "description": "Use ASCII escaping for non-ASCII characters",
                },
                "detect_duplicate_keys": {
                    "type": "boolean",
                    "default": True,
                    "description": "Report duplicate keys in the input",
                },
                "trailing_newline": {
                    "type": "boolean",
                    "default": False,
                    "description": "Add a trailing newline to the canonical form",
                },
            },
            "required": ["text"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "valid": {"type": "boolean"},
                "canonical": {"type": ["string", "null"]},
                "minified": {"type": ["string", "null"]},
                "sha256": {"type": ["string", "null"]},
                "duplicate_keys": {"type": "array", "items": {"type": "string"}},
                "top_level_type": {"type": ["string", "null"]},
                "top_level_keys": {"type": ["array", "null"], "items": {"type": "string"}},
                "error": {"type": ["string", "null"]},
                "line": {"type": ["integer", "null"]},
                "column": {"type": ["integer", "null"]},
            },
        },
    },
    "json_query": {
        "description": "Extract a value from JSON using RFC 6901 JSON Pointer. Navigate nested objects and arrays. Deprecated: use json_extract instead, which provides richer output including available_keys, missing_at, and detail levels.",
        "deprecated": True,
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "JSON document string"},
                "pointer": {
                    "type": "string",
                    "default": "",
                    "description": "RFC 6901 JSON Pointer path (e.g., /foo/bar/0)",
                },
            },
            "required": ["text"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "found": {"type": "boolean"},
                "pointer": {"type": "string"},
                "value": {"description": "Extracted value"},
                "type": {"type": ["string", "null"]},
                "missing_at": {"type": ["string", "null"]},
                "reason": {"type": ["string", "null"]},
                "error": {"type": ["string", "null"]},
                "line": {"type": ["integer", "null"]},
                "column": {"type": ["integer", "null"]},
            },
        },
    },
    "glob_match": {
        "description": "Match a glob pattern against a path with explicit semantics: * matches within one segment, ** matches zero or more segments, ? matches one char. Python fnmatch limitations around ** are documented.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern to match (e.g., src/**/*.rs)",
                },
                "path": {"type": "string", "description": "Path string to match against"},
                "platform": {
                    "type": "string",
                    "enum": ["posix", "windows"],
                    "default": "posix",
                    "description": "Path platform",
                },
                "case_sensitive": {
                    "type": "boolean",
                    "default": True,
                    "description": "Case-sensitive matching",
                },
            },
            "required": ["pattern", "path"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "matches": {"type": "boolean"},
                "normalized_pattern": {"type": "string"},
                "normalized_path": {"type": "string"},
                "matched_segment": {"type": ["string", "null"]},
                "unmatched_segment": {"type": ["string", "null"]},
                "summary": {"type": "string"},
            },
        },
    },
    "text_fingerprint": {
        "description": "Compute a deterministic SHA-256 fingerprint of text with canonicalization options for Unicode normalization, newline style, casefold, and final newline trimming.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Input string to fingerprint"},
                "unicode": {
                    "type": "string",
                    "enum": ["raw", "NFC", "NFD", "NFKC", "NFKD"],
                    "default": "raw",
                    "description": "Unicode normalization form",
                },
                "newline": {
                    "type": "string",
                    "enum": ["raw", "LF"],
                    "default": "raw",
                    "description": "Newline normalization",
                },
                "trim_final_newline": {
                    "type": "boolean",
                    "default": False,
                    "description": "Remove trailing newline before hashing",
                },
                "casefold": {
                    "type": "boolean",
                    "default": False,
                    "description": "Apply casefolding before hashing",
                },
            },
            "required": ["text"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "sha256": {"type": "string"},
                "bytes_utf8": {"type": "integer"},
                "codepoints": {"type": "integer"},
                "graphemes": {"type": "integer"},
                "newline_style": {"type": "string"},
                "normalization": {"type": "object", "description": "Normalization state details"},
                "summary": {"type": "string"},
            },
        },
    },
    "identifier_inspect": {
        "description": "Inspect identifiers for validity and collisions. Detects confusables, mixed scripts, normalization issues, and casefold collisions across a list of identifiers.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "identifiers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of identifier strings to inspect",
                    "maxItems": 10000,
                },
                "language": {
                    "type": "string",
                    "enum": ["generic", "python", "rust", "javascript", "typescript", "json_key"],
                    "default": "generic",
                    "description": "Language for validation",
                },
                "normalization": {
                    "type": "string",
                    "enum": ["raw", "NFC", "NFD", "NFKC", "NFKD"],
                    "default": "NFC",
                    "description": "Unicode normalization form",
                },
                "casefold": {
                    "type": "boolean",
                    "default": False,
                    "description": "Apply casefolding for collision detection",
                },
                "check_confusables": {
                    "type": "boolean",
                    "default": True,
                    "description": "Check for confusable characters",
                },
            },
            "required": ["identifiers"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "identifiers": {
                    "type": "array",
                    "description": "Per-identifier analysis with raw, normalized, valid, scripts, and issues",
                },
                "collisions": {
                    "type": "array",
                    "description": "Detected collisions between identifiers",
                },
            },
        },
    },
    "version_compare": {
        "description": "Compare two version strings with explicit scheme. Supports semver (strict SemVer precedence: pre-release sorts lower than release, build metadata ignored) and loose (numeric parts only). PEP 440 is not supported.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "a": {"type": "string", "description": "First version string"},
                "b": {"type": "string", "description": "Second version string"},
                "scheme": {
                    "type": "string",
                    "enum": ["semver", "loose"],
                    "default": "semver",
                    "description": "Version scheme ('semver' for major.minor.patch with pre-release/build metadata, 'loose' for numeric-part-only comparison)",
                },
            },
            "required": ["a", "b"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "comparison": {
                    "type": "integer",
                    "description": "Comparison result: -1 (a < b), 0 (equal), 1 (a > b)",
                },
                "valid": {
                    "type": "boolean",
                    "description": "Whether versions are valid for the scheme",
                },
                "scheme": {"type": "string"},
                "summary": {"type": "string"},
            },
        },
    },
    "toml_shape": {
        "description": "Analyze the structure of a TOML document: top-level keys, tables, and nesting hierarchy.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "TOML document string"},
                "max_tables": {
                    "type": "integer",
                    "default": 100,
                    "minimum": 1,
                    "maximum": 100000,
                    "description": "Maximum tables to return",
                },
                "detail": {
                    "type": "string",
                    "enum": ["summary", "normal", "full"],
                    "default": "normal",
                },
            },
            "required": ["text"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "valid": {"type": "boolean"},
                "top_level_keys": {"type": ["array", "null"], "items": {"type": "string"}},
                "tables": {"type": ["array", "null"], "items": {"type": "string"}},
                "truncated": {"type": "boolean"},
                "summary": {"type": "string"},
            },
        },
    },
    "list_dedupe": {
        "description": "Remove duplicates from a list while preserving order. Supports Unicode normalization and casefolding.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of strings to dedupe",
                    "maxItems": 10000,
                },
                "normalization": {
                    "type": "string",
                    "enum": ["raw", "NFC", "NFD", "NFKC", "NFKD"],
                    "default": "NFC",
                },
                "casefold": {
                    "type": "boolean",
                    "default": False,
                    "description": "Apply casefolding before comparison",
                },
                "stable": {
                    "type": "boolean",
                    "default": True,
                    "description": "Accepted for compatibility; deduplication keeps first occurrence order",
                },
            },
            "required": ["items"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "items": {"type": "array", "items": {"type": "string"}},
                "original_count": {"type": "integer"},
                "deduped_count": {"type": "integer"},
                "duplicates_removed": {"type": "integer"},
            },
        },
    },
    "list_sort": {
        "description": "Sort a list of strings with Unicode normalization and casefold support.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of strings to sort",
                    "maxItems": 10000,
                },
                "normalization": {
                    "type": "string",
                    "enum": ["raw", "NFC", "NFD", "NFKC", "NFKD"],
                    "default": "NFC",
                },
                "casefold": {
                    "type": "boolean",
                    "default": False,
                    "description": "Apply casefolding for sorting",
                },
                "reverse": {
                    "type": "boolean",
                    "default": False,
                    "description": "Sort in descending order",
                },
                "stable": {
                    "type": "boolean",
                    "default": True,
                    "description": "Accepted for compatibility; Python sorting is always stable",
                },
            },
            "required": ["items"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "items": {"type": "array", "items": {"type": "string"}},
                "original_count": {"type": "integer"},
                "sorted_count": {"type": "integer"},
            },
        },
    },
    "text_replace_check": {
        "description": "Check whether a text replacement would apply cleanly before an agent attempts to edit. Reports match count, positions, ambiguity, and optional preview of before/after.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Source text to search in"},
                "old": {"type": "string", "description": "Text to find"},
                "new": {"type": "string", "description": "Replacement text"},
                "mode": {
                    "type": "string",
                    "enum": ["exact", "nfc", "nfkc", "casefold", "whitespace_collapse"],
                    "default": "exact",
                    "description": "Matching mode",
                },
                "expected_count": {
                    "type": "integer",
                    "description": "Expected number of matches (optional)",
                },
                "allow_multiple": {
                    "type": "boolean",
                    "default": False,
                    "description": "If False and more than one match, add a finding",
                },
                "newline_policy": {
                    "type": "string",
                    "enum": ["preserve", "normalize_lf", "normalize_crlf"],
                    "default": "preserve",
                    "description": "How to handle newlines",
                },
                "return_preview": {
                    "type": "boolean",
                    "default": False,
                    "description": "If True, include before/after text previews",
                },
                "max_preview_chars": {
                    "type": "integer",
                    "default": 2000,
                    "description": "Maximum characters in preview output",
                },
            },
            "required": ["text", "old", "new"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "match_count": {"type": "integer", "description": "Number of matches found"},
                "unique_match": {"type": "boolean", "description": "True if exactly one match"},
                "expected_count_met": {
                    "type": "boolean",
                    "description": "True if match count matches expected_count",
                },
                "would_change": {
                    "type": "boolean",
                    "description": "True if replacement would change text",
                },
                "positions": {
                    "type": "array",
                    "description": "Match positions with byte offsets and line/column",
                },
                "changed_text_fingerprint": {
                    "type": "string",
                    "description": "SHA-256 fingerprint of changed text",
                },
                "newline_style_before": {"type": "string"},
                "newline_style_after": {"type": "string"},
                "preview_before": {"type": "string"},
                "preview_after": {"type": "string"},
                "findings": {"type": "array", "description": "Warnings and info messages"},
            },
        },
    },
    "line_range_extract": {
        "description": "Extract exact line ranges from text and return stable offsets, byte positions, line counts, and optional fingerprint.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Input text"},
                "start_line": {
                    "type": "integer",
                    "description": "First line to extract",
                    "minimum": 0,
                    "maximum": 100000000,
                },
                "end_line": {
                    "type": "integer",
                    "description": "Last line to extract (inclusive)",
                    "minimum": 0,
                    "maximum": 100000000,
                },
                "line_base": {
                    "type": "integer",
                    "default": 1,
                    "description": "Base for line numbers (1 for 1-based, 0 for 0-based)",
                    "minimum": 0,
                    "maximum": 1,
                },
                "include_line_numbers": {
                    "type": "boolean",
                    "default": False,
                    "description": "Include line number in each line dict",
                },
                "include_fingerprint": {
                    "type": "boolean",
                    "default": True,
                    "description": "Compute SHA-256 fingerprint of extracted text",
                },
            },
            "required": ["text", "start_line", "end_line"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "line_count_total": {"type": "integer", "description": "Total line count in input"},
                "start_line": {"type": "integer"},
                "end_line": {"type": "integer"},
                "valid_range": {"type": "boolean", "description": "True if range is within bounds"},
                "text": {"type": "string", "description": "Extracted text (lines joined by LF)"},
                "lines": {"type": "array", "description": "Structured line list"},
                "byte_start": {"type": "integer", "description": "UTF-8 byte offset of start"},
                "byte_end": {"type": "integer", "description": "UTF-8 byte offset of end"},
                "char_start": {"type": "integer", "description": "Codepoint index of start"},
                "char_end": {"type": "integer", "description": "Codepoint index of end"},
                "newline_style": {"type": "string"},
                "ends_with_newline": {"type": "boolean"},
                "fingerprint": {"type": "string"},
                "findings": {"type": "array"},
            },
        },
    },
    "line_range_compare": {
        "description": "Compare a line range from two text inputs with exact, trailing-whitespace-ignoring, or newline-normalizing comparison.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "left_text": {"type": "string", "description": "First text input"},
                "right_text": {"type": "string", "description": "Second text input"},
                "start_line": {
                    "type": "integer",
                    "description": "First line to compare",
                    "minimum": 0,
                    "maximum": 100000000,
                },
                "end_line": {
                    "type": "integer",
                    "description": "Last line to compare (inclusive)",
                    "minimum": 0,
                    "maximum": 100000000,
                },
                "line_base": {
                    "type": "integer",
                    "default": 1,
                    "description": "Base for line numbers",
                    "minimum": 0,
                    "maximum": 1,
                },
                "comparison_mode": {
                    "type": "string",
                    "enum": ["exact", "ignore_trailing_whitespace", "normalize_newlines"],
                    "default": "exact",
                    "description": "Comparison mode",
                },
            },
            "required": ["left_text", "right_text", "start_line", "end_line"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "equal": {
                    "type": "boolean",
                    "description": "True if ranges are equal under the chosen mode",
                },
                "left_fingerprint": {
                    "type": "string",
                    "description": "SHA-256 fingerprint of left range",
                },
                "right_fingerprint": {
                    "type": "string",
                    "description": "SHA-256 fingerprint of right range",
                },
                "diff_summary": {"type": "string", "description": "Human-readable diff summary"},
                "first_difference": {
                    "type": ["object", "null"],
                    "description": "First differing line (null when ranges are equal)",
                },
            },
        },
    },
    "shell_split": {
        "description": "Parse a shell-like command string into argv tokens and report risky lexical features (pipes, redirections, command substitution, variable expansion, globs, control operators). Lexical POSIX-like parsing only, not full shell evaluation.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command string to parse",
                },
                "shell": {
                    "type": "string",
                    "enum": ["posix"],
                    "default": "posix",
                    "description": "Shell dialect (only posix is supported)",
                },
                "detect_risky_features": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to detect risky lexical features",
                },
            },
            "required": ["command"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "parse_ok": {
                    "type": "boolean",
                    "description": "True if the command parsed successfully",
                },
                "argv": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Parsed argument tokens",
                },
                "argc": {"type": "integer", "description": "Number of arguments"},
                "features": {
                    "type": "object",
                    "description": "Detected risky features",
                    "properties": {
                        "has_pipe": {"type": "boolean"},
                        "has_redirection": {"type": "boolean"},
                        "has_command_substitution": {"type": "boolean"},
                        "has_variable_expansion": {"type": "boolean"},
                        "has_glob_pattern": {"type": "boolean"},
                        "has_control_operator": {"type": "boolean"},
                        "has_unbalanced_quotes": {"type": "boolean"},
                    },
                },
                "findings": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Analysis notes and warnings",
                },
            },
        },
    },
    "shell_quote_join": {
        "description": "Safely quote a list of argv tokens into a POSIX-like shell string. Verifies round-trip safety with shell_split.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "argv": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of argument strings to join",
                    "maxItems": 10000,
                },
                "shell": {
                    "type": "string",
                    "enum": ["posix"],
                    "default": "posix",
                    "description": "Shell dialect (only posix is supported)",
                },
            },
            "required": ["argv"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Safely quoted command string"},
                "roundtrip_ok": {
                    "type": "boolean",
                    "description": "True if shell_split(quote_join(argv)) produces equivalent argv",
                },
                "findings": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Analysis notes",
                },
            },
        },
    },
    "argv_compare": {
        "description": "Compare two command strings or argv lists by parsed argv tokens rather than raw text. Supports command strings, pre-parsed argv lists, or both.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "left_command": {
                    "type": "string",
                    "description": "Left command string to parse and compare",
                },
                "right_command": {
                    "type": "string",
                    "description": "Right command string to parse and compare",
                },
                "left_argv": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Left pre-parsed argv list",
                    "maxItems": 10000,
                },
                "right_argv": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Right pre-parsed argv list",
                    "maxItems": 10000,
                },
                "shell": {
                    "type": "string",
                    "enum": ["posix"],
                    "default": "posix",
                    "description": "Shell dialect (only posix is supported)",
                },
            },
            # XOR required: exactly one of left_command/left_argv and one of right_command/right_argv.
            # JSON Schema cannot express XOR, so required is empty; validation is in the handler.
            "required": [],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "argv_equal": {
                    "type": "boolean",
                    "description": "True if parsed argv lists are identical",
                },
                "left_argv": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Resolved left argv",
                },
                "right_argv": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Resolved right argv",
                },
                "first_difference": {
                    "type": ["integer", "null"],
                    "description": "Index of first differing token, or null if equal",
                },
                "findings": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Analysis notes",
                },
            },
        },
    },
    "markdown_structure": {
        "description": "Parse Markdown structure with a deterministic line scanner: headings (level, text, slug), code fences (language, open/close state), links (visible vs target mismatch), HTML comments, frontmatter detection, and table detection. Not a full CommonMark parser.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Markdown text to analyze"},
                "include_sections": {
                    "type": "boolean",
                    "default": True,
                    "description": "Include heading detection",
                },
                "include_links": {
                    "type": "boolean",
                    "default": True,
                    "description": "Include link detection",
                },
                "include_code_fences": {
                    "type": "boolean",
                    "default": True,
                    "description": "Include code fence detection",
                },
                "include_html_comments": {
                    "type": "boolean",
                    "default": True,
                    "description": "Include HTML comment detection",
                },
            },
            "required": ["text"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "headings": {
                    "type": "array",
                    "description": "Headings with level, text, line, slug",
                },
                "code_fences": {
                    "type": "array",
                    "description": "Code fences with language, lines, closed state",
                },
                "links": {
                    "type": "array",
                    "description": "Links with visible text, target, mismatch flags",
                },
                "html_comments": {
                    "type": "array",
                    "description": "HTML comments with text and position",
                },
                "frontmatter": {
                    "type": "object",
                    "description": "Frontmatter detection (present, format, line range)",
                },
                "tables_detected": {
                    "type": "boolean",
                    "description": "Whether Markdown tables were detected",
                },
                "findings": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Warnings and findings",
                },
            },
        },
    },
    "code_fence_extract": {
        "description": "Extract fenced code blocks from Markdown with exact line ranges, optional language filter, content, and SHA-256 fingerprints. Reports unclosed fences.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Markdown text to scan"},
                "language": {
                    "type": "string",
                    "description": "Optional language filter (case-insensitive)",
                },
                "include_content": {
                    "type": "boolean",
                    "default": True,
                    "description": "Include block content in output",
                },
            },
            "required": ["text"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "blocks": {
                    "type": "array",
                    "description": "Extracted code blocks with index, language, lines, content, fingerprint",
                },
                "unclosed_fences": {"type": "array", "description": "Unclosed code fences found"},
                "findings": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Warnings and findings",
                },
            },
        },
    },
    "dotenv_validate": {
        "description": "Validate .env-style key=value configuration text. Detects invalid keys, duplicate keys, missing quotes, and variable expansion syntax. Line-by-line parser, no shell evaluation.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": ".env file content to validate"},
                "allow_export": {
                    "type": "boolean",
                    "default": True,
                    "description": "Allow export KEY=VALUE syntax",
                },
                "key_pattern": {
                    "type": "string",
                    "default": "^[A-Za-z_][A-Za-z0-9_]*$",
                    "description": "Regex pattern keys must match",
                },
                "duplicate_policy": {
                    "type": "string",
                    "enum": ["warn", "error", "allow"],
                    "default": "warn",
                    "description": "How to handle duplicate keys",
                },
            },
            "required": ["text"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "parse_ok": {"type": "boolean", "description": "True if no parse errors found"},
                "entries": {
                    "type": "array",
                    "description": "Parsed entries with key, value, quote_style, line",
                },
                "duplicates": {
                    "type": "array",
                    "description": "Duplicate key entries with line numbers",
                },
                "invalid_lines": {"type": "array", "description": "Lines that failed to parse"},
                "requires_quoting": {
                    "type": "array",
                    "description": "Keys whose values contain spaces and should be quoted",
                },
                "contains_expansion_syntax": {
                    "type": "array",
                    "description": "Keys with ${VAR} or $VAR expansion syntax",
                },
                "findings": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Human-readable findings",
                },
            },
        },
    },
    "ini_validate": {
        "description": "Validate simple INI-style configuration files. Supports [section] headers, key=value and key:value lines, comments. Detects duplicate sections, duplicate keys, and malformed lines.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "INI file content to validate"},
                "duplicate_policy": {
                    "type": "string",
                    "enum": ["warn", "error", "allow"],
                    "default": "warn",
                    "description": "How to handle duplicate keys/sections",
                },
            },
            "required": ["text"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "parse_ok": {"type": "boolean", "description": "True if no parse errors found"},
                "sections": {"type": "array", "description": "Ordered list of section names"},
                "keys_by_section": {"type": "object", "description": "Keys grouped by section"},
                "duplicates": {
                    "type": "array",
                    "description": "Duplicate keys/sections with line numbers",
                },
                "invalid_lines": {"type": "array", "description": "Lines that failed to parse"},
                "findings": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Human-readable findings",
                },
            },
        },
    },
    "patch_apply_check": {
        "description": "Validate and simulate a unified diff against provided in-memory files/text without touching the filesystem. Reports parse status, application success, failed hunks with context, and optional result fingerprint.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "original_text": {
                    "type": "string",
                    "description": "The original source text to apply the patch to",
                },
                "patch_text": {
                    "type": "string",
                    "description": "The unified diff patch text",
                },
                "strict": {
                    "type": "boolean",
                    "default": True,
                    "description": "If True, context lines must match exactly",
                },
                "return_result_fingerprint": {
                    "type": "boolean",
                    "default": True,
                    "description": "If True, compute SHA-256 fingerprint of the result",
                },
                "return_result_text": {
                    "type": "boolean",
                    "default": False,
                    "description": "If True, include the resulting text (bounded to 50000 chars)",
                },
            },
            "required": ["original_text", "patch_text"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "patch_parse_ok": {
                    "type": "boolean",
                    "description": "True if patch parsed successfully",
                },
                "applies": {"type": "boolean", "description": "True if all hunks applied cleanly"},
                "hunks_total": {"type": "integer", "description": "Total number of hunks in patch"},
                "hunks_applied": {
                    "type": "integer",
                    "description": "Number of hunks that applied successfully",
                },
                "hunks_failed": {
                    "type": "integer",
                    "description": "Number of hunks that failed to apply",
                },
                "failed_hunks": {
                    "type": "array",
                    "description": "Details of each failed hunk",
                    "items": {
                        "type": "object",
                        "properties": {
                            "hunk_index": {"type": "integer"},
                            "old_start": {"type": "integer"},
                            "old_count": {"type": "integer"},
                            "expected_context": {"type": "array", "items": {"type": "string"}},
                            "actual_context": {"type": "array", "items": {"type": "string"}},
                            "reason": {"type": "string"},
                        },
                    },
                },
                "affected_line_ranges": {
                    "type": "array",
                    "description": "Line ranges affected by successful hunks",
                    "items": {
                        "type": "object",
                        "properties": {
                            "start": {"type": "integer"},
                            "end": {"type": "integer"},
                        },
                    },
                },
                "newline_style_before": {
                    "type": "string",
                    "description": "Newline style in original text",
                },
                "newline_style_after": {
                    "type": "string",
                    "description": "Newline style in result text",
                },
                "result_fingerprint": {
                    "type": "string",
                    "description": "SHA-256 of the result text",
                },
                "result_text": {
                    "type": ["string", "null"],
                    "description": "Resulting text if requested",
                },
                "findings": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Analysis notes and warnings",
                },
            },
        },
    },
    "patch_summary": {
        "description": "Summarize a unified diff without applying it. Reports file counts, hunk counts, additions, deletions, renames, and line ranges by file.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "patch_text": {
                    "type": "string",
                    "description": "The unified diff text to summarize",
                },
            },
            "required": ["patch_text"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "files_changed": {"type": "integer", "description": "Number of files changed"},
                "hunks_total": {
                    "type": "integer",
                    "description": "Total number of hunks across all files",
                },
                "additions": {"type": "integer", "description": "Total number of added lines"},
                "deletions": {"type": "integer", "description": "Total number of deleted lines"},
                "renames_detected": {
                    "type": "array",
                    "description": "Detected file renames",
                    "items": {
                        "type": "object",
                        "properties": {
                            "from": {"type": "string"},
                            "to": {"type": "string"},
                        },
                    },
                },
                "binary_patch_detected": {
                    "type": "boolean",
                    "description": "True if binary patch content detected",
                },
                "line_ranges_by_file": {
                    "type": "object",
                    "description": "Line ranges affected per file",
                    "additionalProperties": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "start": {"type": "integer"},
                                "end": {"type": "integer"},
                            },
                        },
                    },
                },
                "findings": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Analysis notes and warnings",
                },
            },
        },
    },
    "diff_touched_paths": {
        "description": "Classify files in a unified diff as added, deleted, renamed, or modified. Also detects binary diffs and file mode changes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "patch_text": {
                    "type": "string",
                    "description": "The unified diff text to analyze",
                },
                "max_files": {
                    "type": "integer",
                    "description": "Maximum number of files to process",
                    "default": 100,
                },
            },
            "required": ["patch_text"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "parse_ok": {"type": "boolean"},
                "error": {"type": ["string", "null"]},
                "added": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Newly added files",
                },
                "deleted": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Deleted files",
                },
                "renamed": {
                    "type": "array",
                    "description": "Renamed files with from/to paths",
                    "items": {
                        "type": "object",
                        "properties": {
                            "from": {"type": "string"},
                            "to": {"type": "string"},
                        },
                    },
                },
                "modified": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Modified files",
                },
                "binary_files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Files with binary content",
                },
                "mode_changes": {
                    "type": "array",
                    "description": "File mode changes detected",
                    "items": {
                        "type": "object",
                        "properties": {
                            "file": {"type": "string"},
                            "old_mode": {"type": "string"},
                            "new_mode": {"type": "string"},
                        },
                    },
                },
                "total_files": {
                    "type": "integer",
                    "description": "Total number of files processed",
                },
            },
        },
    },
    "diff_hunk_ranges": {
        "description": "Extract hunk ranges per file with line count classification (added/deleted/context) from a unified diff.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "patch_text": {
                    "type": "string",
                    "description": "The unified diff text to analyze",
                },
                "max_files": {
                    "type": "integer",
                    "description": "Maximum number of files to process",
                    "default": 100,
                },
            },
            "required": ["patch_text"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "parse_ok": {"type": "boolean"},
                "error": {"type": ["string", "null"]},
                "files": {
                    "type": "array",
                    "description": "Per-file hunk details",
                    "items": {
                        "type": "object",
                        "properties": {
                            "old_file": {"type": "string"},
                            "new_file": {"type": "string"},
                            "hunks": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "old_start": {"type": "integer"},
                                        "old_count": {"type": "integer"},
                                        "new_start": {"type": "integer"},
                                        "new_count": {"type": "integer"},
                                        "added_lines": {"type": "integer"},
                                        "deleted_lines": {"type": "integer"},
                                        "context_lines": {"type": "integer"},
                                        "header_line": {"type": "string"},
                                    },
                                },
                            },
                            "total_added": {"type": "integer"},
                            "total_deleted": {"type": "integer"},
                            "total_context": {"type": "integer"},
                        },
                    },
                },
            },
        },
    },
    "diff_file_headers": {
        "description": "Extract metadata from diff file headers: diff --git line, index hash, mode changes, rename/copy directives, and binary indicators.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "patch_text": {
                    "type": "string",
                    "description": "The unified diff text to analyze",
                },
                "max_files": {
                    "type": "integer",
                    "description": "Maximum number of files to process",
                    "default": 100,
                },
            },
            "required": ["patch_text"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "parse_ok": {"type": "boolean"},
                "error": {"type": ["string", "null"]},
                "files": {
                    "type": "array",
                    "description": "Parsed header metadata per file",
                    "items": {
                        "type": "object",
                        "properties": {
                            "old_file": {"type": "string"},
                            "new_file": {"type": "string"},
                            "diff_git_line": {
                                "type": ["string", "null"],
                                "description": "The diff --git line",
                            },
                            "index_line": {
                                "type": ["string", "null"],
                                "description": "The index hash line",
                            },
                            "old_mode": {
                                "type": ["string", "null"],
                                "description": "Old file mode",
                            },
                            "new_mode": {
                                "type": ["string", "null"],
                                "description": "New file mode",
                            },
                            "rename_from": {
                                "type": ["string", "null"],
                                "description": "Rename source path",
                            },
                            "rename_to": {
                                "type": ["string", "null"],
                                "description": "Rename destination path",
                            },
                            "copy_from": {
                                "type": ["string", "null"],
                                "description": "Copy source path",
                            },
                            "copy_to": {
                                "type": ["string", "null"],
                                "description": "Copy destination path",
                            },
                            "is_new_file": {
                                "type": "boolean",
                                "description": "True if file is newly added",
                            },
                            "is_deleted_file": {
                                "type": "boolean",
                                "description": "True if file was deleted",
                            },
                            "is_binary": {
                                "type": "boolean",
                                "description": "True if file is binary",
                            },
                            "hunks_count": {
                                "type": "integer",
                                "description": "Number of hunks in this file",
                            },
                        },
                    },
                },
            },
        },
    },
    "patch_conflict_markers_inspect": {
        "description": "Detect and analyze conflict markers (<<<<<<<, =======, >>>>>>>) in text. Reports counts, balance, nesting, and line locations.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text to scan for conflict markers",
                },
            },
            "required": ["text"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "total_markers": {
                    "type": "integer",
                    "description": "Total number of conflict markers found",
                },
                "conflict_starts": {
                    "type": "integer",
                    "description": "Count of <<<<<<< markers",
                },
                "conflict_separators": {
                    "type": "integer",
                    "description": "Count of ======= markers",
                },
                "conflict_ends": {
                    "type": "integer",
                    "description": "Count of >>>>>>> markers",
                },
                "imbalanced": {
                    "type": "boolean",
                    "description": "True if start and end markers are unbalanced",
                },
                "nested": {
                    "type": "boolean",
                    "description": "True if conflict markers are nested",
                },
                "locations": {
                    "type": "array",
                    "description": "Line numbers and types of each marker",
                    "items": {
                        "type": "object",
                        "properties": {
                            "line": {"type": "integer"},
                            "kind": {
                                "type": "string",
                                "enum": ["start", "separator", "end"],
                            },
                        },
                    },
                },
            },
        },
    },
    "unified_diff_validate": {
        "description": "Validate the structural integrity of a unified diff. Checks parse success, hunk header format, line count consistency, and stray lines.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "patch_text": {
                    "type": "string",
                    "description": "The unified diff text to validate",
                },
                "check_line_counts": {
                    "type": "boolean",
                    "description": "If True, validate hunk header line counts",
                    "default": True,
                },
            },
            "required": ["patch_text"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "parse_ok": {
                    "type": "boolean",
                    "description": "Whether the diff parsed successfully",
                },
                "files_count": {
                    "type": "integer",
                    "description": "Number of files in the diff",
                },
                "hunks_total": {
                    "type": "integer",
                    "description": "Total number of hunks",
                },
                "warnings": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Validation warnings",
                },
                "structure_valid": {
                    "type": "boolean",
                    "description": "True if the diff structure is valid",
                },
            },
        },
    },
    "unicode_policy_check": {
        "description": "Apply a named deterministic Unicode safety policy to input text. Policies include identifier_strict (mixed scripts, bidi, confusables), filename_safe (control chars, path separators, reserved names), source_code, human_text (warn-only), json_key, and domain_like.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Input text to check"},
                "policy": {
                    "type": "string",
                    "enum": [
                        "identifier_strict",
                        "filename_safe",
                        "source_code",
                        "human_text",
                        "json_key",
                        "domain_like",
                    ],
                    "description": "Policy to apply",
                },
                "normalization": {
                    "type": "string",
                    "enum": ["raw", "NFC", "NFD", "NFKC", "NFKD"],
                    "description": "Normalization form (default: policy-specific)",
                },
            },
            "required": ["text", "policy"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "pass_": {
                    "type": "boolean",
                    "description": "True if text passes the policy (no errors)",
                },
                "policy": {"type": "string", "description": "Policy name that was applied"},
                "normalized_form": {"type": "string", "description": "Text after normalization"},
                "findings": {
                    "type": "array",
                    "description": "Policy findings with rule, severity, and message",
                    "items": {
                        "type": "object",
                        "properties": {
                            "rule": {"type": "string"},
                            "severity": {"type": "string"},
                            "message": {"type": "string"},
                        },
                    },
                },
                "summary": {"type": "string", "description": "Human-readable summary"},
            },
        },
    },
    "canonicalize_text": {
        "description": "Apply a named text canonicalization profile. Profiles include source_file_identity (NFC + LF + newline), identifier_compare (NFC + casefold), human_label_compare (NFC + casefold + whitespace collapse), json_key_compare (NFC + casefold), and path_segment_compare (NFC + lowercase + LF).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Input text to canonicalize"},
                "profile": {
                    "type": "string",
                    "enum": [
                        "source_file_identity",
                        "identifier_compare",
                        "human_label_compare",
                        "json_key_compare",
                        "path_segment_compare",
                    ],
                    "description": "Canonicalization profile to apply",
                },
                "return_mapping": {
                    "type": "boolean",
                    "default": False,
                    "description": "If True, include a character mapping of changes",
                },
            },
            "required": ["text", "profile"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Canonicalized text"},
                "changed": {"type": "boolean", "description": "True if text was modified"},
                "operations_applied": {
                    "type": "array",
                    "description": "List of operations applied",
                },
                "fingerprint_before": {"type": "string", "description": "SHA-256 of original text"},
                "fingerprint_after": {
                    "type": "string",
                    "description": "SHA-256 of canonicalized text",
                },
                "mapping": {
                    "type": ["array", "null"],
                    "description": "Character mapping if return_mapping was True (null otherwise)",
                },
                "findings": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Analysis notes and warnings",
                },
            },
        },
    },
    "identifier_table_inspect": {
        "description": "Inspect a table of identifiers for casefold collisions, normalization collisions, confusable/near-collisions, style variants, reserved keyword hits, and mixed naming style groups. Accepts structured entries with name, kind, file, and line metadata.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "identifiers": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Identifier name (required)"},
                            "kind": {"type": "string", "description": "Optional kind/category"},
                            "file": {"type": "string", "description": "Source file path"},
                            "line": {"type": "integer", "description": "Line number"},
                        },
                        "required": ["name"],
                    },
                    "description": "List of identifier entries to inspect",
                    "maxItems": 10000,
                },
                "language": {
                    "type": "string",
                    "enum": ["generic", "python", "rust", "javascript", "typescript", "json_key"],
                    "default": "python",
                    "description": "Target language for reserved keyword checking",
                },
                "checks": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Subset of checks: casefold, normalization, confusable, style, reserved, mixed_style",
                },
            },
            "required": ["identifiers"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "count": {"type": "integer", "description": "Number of identifiers inspected"},
                "collisions": {
                    "type": "array",
                    "description": "Detected collisions",
                    "items": {
                        "type": "object",
                        "properties": {
                            "kind": {"type": "string"},
                            "names": {"type": "array", "items": {"type": "string"}},
                            "detail": {"type": "string"},
                        },
                    },
                },
                "reserved_keyword_hits": {
                    "type": "array",
                    "description": "Identifiers matching reserved keywords",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "language": {"type": "string"},
                            "file": {"type": "string"},
                            "line": {"type": "integer"},
                        },
                    },
                },
                "mixed_style_groups": {
                    "type": "array",
                    "description": "Groups with mixed naming styles",
                    "items": {
                        "type": "object",
                        "properties": {
                            "stripped": {"type": "string"},
                            "names": {"type": "array", "items": {"type": "string"}},
                            "styles": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                },
                "findings": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
    "version_constraint_check": {
        "description": "Check whether a version satisfies a constraint under a declared versioning scheme. Supports semver exact/comparison/range constraints and cargo caret, tilde, and wildcard constraints.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "version": {
                    "type": "string",
                    "description": "Version string to check (e.g., '1.2.3', '0.5.0-beta.1')",
                },
                "constraint": {
                    "type": "string",
                    "description": "Version constraint (e.g., '>=1.0,<2.0', '^1.2.3', '~0.5', '1.*')",
                },
                "scheme": {
                    "type": "string",
                    "enum": ["semver", "cargo"],
                    "default": "semver",
                    "description": "Versioning scheme to use for parsing and evaluation",
                },
            },
            "required": ["version", "constraint"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "satisfies": {
                    "type": "boolean",
                    "description": "Whether the version satisfies the constraint",
                },
                "parsed_version": {
                    "type": ["object", "null"],
                    "description": "Parsed version components (null when unparseable)",
                },
                "parsed_constraint": {
                    "type": ["object", "null"],
                    "description": "Parsed constraint components (null when unparseable)",
                },
                "scheme": {"type": "string", "description": "Versioning scheme used"},
                "explanation": {"type": "string", "description": "Human-readable explanation"},
                "findings": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Analysis notes and warnings",
                },
            },
        },
    },
    "cargo_toml_inspect": {
        "description": "Inspect Cargo.toml text without network or filesystem access. Reports package metadata, workspace configuration, dependency forms (version/path/git/workspace), path dependencies, suspicious or confusable dependency names, and structural findings.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The Cargo.toml content to inspect",
                },
                "check_workspace": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to analyze [workspace] section",
                },
                "check_dependencies": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to analyze dependency sections",
                },
            },
            "required": ["text"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "parse_ok": {"type": "boolean", "description": "Whether TOML parsed successfully"},
                "package": {
                    "type": "object",
                    "description": "Package metadata from [package] section",
                    "properties": {
                        "name": {"type": "string"},
                        "version": {"type": "string"},
                        "edition": {"type": "string"},
                        "license": {"type": "string"},
                        "repository": {"type": "string"},
                        "readme": {"type": "string"},
                    },
                },
                "workspace": {
                    "type": "object",
                    "description": "Workspace section information",
                    "properties": {
                        "present": {"type": "boolean"},
                        "members": {"type": "array", "items": {"type": "string"}},
                        "exclude": {"type": "array", "items": {"type": "string"}},
                    },
                },
                "dependencies": {
                    "type": "object",
                    "description": "Dependencies by section",
                },
                "path_dependencies": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Extracted path dependency values",
                },
                "suspicious_dependency_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Dependency names with suspicious patterns",
                },
                "duplicate_or_confusable_dependency_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Dependency names that normalize to the same form",
                },
                "findings": {
                    "type": "array",
                    "description": "Structured findings with code, severity, message, line, column",
                    "items": {
                        "type": "object",
                        "properties": {
                            "code": {"type": "string"},
                            "severity": {"type": "string"},
                            "message": {"type": "string"},
                            "line": {"type": "integer"},
                            "column": {"type": "integer"},
                        },
                    },
                },
            },
        },
    },
    "prompt_input_inspect": {
        "description": "Deterministically inspect text for red flags that may influence agents or humans unexpectedly. Detects hidden Unicode characters, bidirectional controls, HTML comments, Markdown link mismatches, ANSI escapes, terminal controls, base64-like blobs, instruction-like phrases, and very long minified lines. This is NOT a prompt-injection detector -- it reports observable features only, not intent.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The text to inspect for red flags",
                },
                "checks": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Subset of checks to run: unicode_hidden, bidi, html_comments, markdown_links, ansi_escapes, terminal_controls, base64_like_blobs, instruction_phrases, long_minified_lines",
                },
                "phrase_patterns": {
                    "type": ["array", "null"],
                    "items": {"type": "string"},
                    "description": "Optional literal strings or safe regexes to detect as instruction-like phrases. Pass null for no custom patterns.",
                },
            },
            "required": ["text"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "findings": {
                    "type": "array",
                    "description": "Structured findings with code, severity, message, span, and details",
                    "items": {
                        "type": "object",
                        "properties": {
                            "code": {"type": "string"},
                            "severity": {"type": "string"},
                            "message": {"type": "string"},
                            "span": {"type": "object"},
                            "details": {"type": "object"},
                        },
                    },
                },
                "summary": {"type": "string", "description": "Human-readable summary"},
                "risk_score": {"type": "integer", "description": "Deterministic risk score"},
                "recommended_next_tool": {
                    "type": ["string", "array", "null"],
                    "description": "Recommended follow-up tool(s) (null when none)",
                },
                "text_length": {"type": "integer", "description": "Input text length"},
                "checks_run": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Checks that were executed",
                },
                "findings_truncated": {
                    "type": "boolean",
                    "description": "True if findings were truncated due to limits",
                },
            },
        },
    },
    "text_security_inspect": {
        "description": "Composite security-oriented text hygiene pass. Runs text_inspect, unicode_policy_check, canonicalize_text, prompt_input_inspect, and identifier_inspect depending on policy. Returns a verdict (allow/review/block) plus structured findings and machine codes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Input text to inspect"},
                "policy": {
                    "type": "string",
                    "enum": ["default", "source_code", "prompt", "markdown", "identifier"],
                    "default": "default",
                    "description": "Security policy to apply",
                },
                "normalize": {
                    "type": "string",
                    "enum": ["none", "NFC", "NFD", "NFKC", "NFKD"],
                    "default": "none",
                    "description": "Normalization form to analyze",
                },
                "compare_normalized": {
                    "type": "boolean",
                    "default": False,
                    "description": "Report both original and normalized analysis",
                },
                "detail": {
                    "type": "string",
                    "enum": ["summary", "normal", "full"],
                    "default": "summary",
                    "description": "Detail level: summary (compact verdict only), normal, or full (includes subresults)",
                },
            },
            "required": ["text"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "verdict": {"type": "string", "enum": ["allow", "review", "block"]},
                "policy": {"type": "string"},
                "findings": {"type": "array"},
                "machine_code": {"type": "string"},
                "normalized_changed": {"type": "boolean"},
                "recommended_action": {"type": "string"},
                "summary": {"type": "string"},
                "subresults": {"type": "object"},
            },
        },
    },
    "edit_preflight": {
        "description": "Composite: validate a proposed edit before applying it. Calls text_replace_check, patch_apply_check, line_range_extract, text_fingerprint, and text_diff_explain as needed. Returns ok_to_apply verdict with findings and machine codes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "original": {"type": "string", "description": "Original source text"},
                "replacement_mode": {
                    "type": "string",
                    "enum": ["literal", "patch", "line_range"],
                    "default": "literal",
                    "description": "Edit mode: literal (old/new), patch (unified diff), or line_range",
                },
                "old": {"type": "string", "description": "Text to find (literal mode)"},
                "new": {"type": "string", "description": "Replacement text (literal mode)"},
                "patch": {"type": "string", "description": "Unified diff patch (patch mode)"},
                "start_line": {"type": "integer", "description": "First line (line_range mode)"},
                "end_line": {
                    "type": "integer",
                    "description": "Last line inclusive (line_range mode)",
                },
                "expected_fingerprint": {
                    "type": "string",
                    "description": "Expected SHA-256 fingerprint for verification",
                },
                "strict": {
                    "type": "boolean",
                    "default": True,
                    "description": "Strict mode for patch matching",
                },
            },
            "required": ["original"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "ok_to_apply": {"type": "boolean"},
                "mode": {"type": "string"},
                "findings": {"type": "array"},
                "machine_code": {"type": "string"},
                "recommended_next_tool": {"type": ["string", "null"]},
                "summary": {"type": "string"},
                "subresults": {"type": "object"},
            },
        },
    },
    "command_preflight": {
        "description": "Composite: analyze a command before user approval or execution. Calls shell_split and regex_safety_check. Returns parsed argv, shell operators, risk findings, and a verdict. Must not execute anything.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Command string to analyze"},
                "platform": {
                    "type": "string",
                    "enum": ["posix", "windows", "auto"],
                    "default": "posix",
                    "description": "Target platform",
                },
                "policy": {
                    "type": "string",
                    "enum": ["default", "strict", "permissive"],
                    "default": "default",
                    "description": "Analysis policy",
                },
                "working_directory": {
                    "type": "string",
                    "description": "Working directory context (informational)",
                },
            },
            "required": ["command"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "verdict": {"type": "string", "enum": ["allow", "review", "block"]},
                "command": {"type": "string"},
                "platform": {"type": "string"},
                "policy": {"type": "string"},
                "findings": {"type": "array"},
                "machine_code": {"type": "string"},
                "summary": {"type": "string"},
                "subresults": {"type": "object"},
            },
        },
    },
    "config_preflight": {
        "description": "Composite: validate generated config text. Auto-detects format and runs the appropriate validator. Returns valid/invalid, detected format, parse error location, and machine code.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Config text to validate"},
                "format": {
                    "type": "string",
                    "enum": ["auto", "json", "toml", "dotenv", "ini", "cargo_toml"],
                    "default": "auto",
                    "description": "Config format (auto-detect if not specified)",
                },
                "schema": {"type": "object", "description": "Optional JSON schema for validation"},
                "strict": {
                    "type": "boolean",
                    "default": False,
                    "description": "Strict validation mode",
                },
            },
            "required": ["text"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "valid": {"type": "boolean"},
                "verdict": {"type": "string", "enum": ["valid", "valid_with_warnings", "invalid"]},
                "format": {"type": "string"},
                "findings": {"type": "array"},
                "machine_code": {"type": "string"},
                "summary": {"type": "string"},
                "subresults": {"type": "object"},
            },
        },
    },
    "structured_data_compare": {
        "description": "Composite: compare structured config/data output. Calls json_compare, json_canonicalize, and json_shape. Returns equal/not-equal verdict with structured diffs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "a": {"type": "string", "description": "First JSON string"},
                "b": {"type": "string", "description": "Second JSON string"},
                "format": {
                    "type": "string",
                    "enum": ["json"],
                    "default": "json",
                    "description": "Data format (json only for now)",
                },
                "ignore_object_order": {
                    "type": "boolean",
                    "default": True,
                    "description": "Ignore object key order",
                },
                "ignore_array_order": {
                    "type": "boolean",
                    "default": False,
                    "description": "Sort arrays before comparison",
                },
                "max_diffs": {
                    "type": "integer",
                    "default": 50,
                    "description": "Maximum differences to report",
                },
            },
            "required": ["a", "b"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "equal": {"type": "boolean"},
                "valid_a": {"type": "boolean"},
                "valid_b": {"type": "boolean"},
                "findings": {"type": "array"},
                "machine_code": {"type": "string"},
                "summary": {"type": "string"},
                "subresults": {"type": "object"},
            },
        },
    },
    # ── Manifest / package inspection tools ─────────────────────────────────
    "pyproject_inspect": {
        "description": "Inspect pyproject.toml text: project name/version, build backend, dependencies, optional groups, scripts, tool sections, package-manager signals. Deterministic, no network.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The pyproject.toml content to inspect"},
            },
            "required": ["text"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "parse_ok": {"type": "boolean"},
                "project_name": {"type": "string"},
                "project_version": {"type": "string"},
                "build_backend": {
                    "type": ["string", "null"],
                    "description": "Build backend string from build-system.build-backend",
                },
                "build_requirements": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Build system requires list",
                },
                "build_backend_path": {
                    "type": ["array", "null"],
                    "items": {"type": "string"},
                    "description": "Build backend path",
                },
                "requires_python": {"type": "string"},
                "dependencies_count": {"type": "integer"},
                "optional_dependency_groups": {"type": "object"},
                "scripts": {"type": "object"},
                "tool_sections": {"type": "array"},
                "package_manager_signals": {"type": "array"},
                "dynamic": {
                    "type": ["array", "null"],
                    "items": {"type": "string"},
                    "description": "Dynamic project fields",
                },
                "entry_points": {"type": ["object", "null"], "description": "Project entry points"},
                "gui_scripts": {
                    "type": ["object", "null"],
                    "description": "GUI script entry points",
                },
                "urls": {"type": ["object", "null"], "description": "Project URLs"},
                "findings": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "code": {"type": "string"},
                            "severity": {"type": "string"},
                            "message": {"type": "string"},
                            "line": {"type": "integer"},
                            "column": {"type": "integer"},
                        },
                    },
                },
            },
        },
    },
    "package_json_inspect": {
        "description": "Inspect package.json text: name, version, scripts, dependency counts, engines, packageManager, workspaces. Deterministic, no network.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The package.json content to inspect"},
            },
            "required": ["text"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "parse_ok": {"type": "boolean"},
                "name": {"type": "string"},
                "version": {"type": "string"},
                "private": {"type": "boolean"},
                "package_type": {"type": "string"},
                "scripts_keys": {"type": "array"},
                "dependencies_count": {"type": "integer"},
                "dev_dependencies_count": {"type": "integer"},
                "engines": {"type": "object"},
                "package_manager": {"type": "string"},
                "workspaces": {"type": "array"},
                "findings": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "code": {"type": "string"},
                            "severity": {"type": "string"},
                            "message": {"type": "string"},
                            "line": {"type": "integer"},
                            "column": {"type": "integer"},
                        },
                    },
                },
            },
        },
    },
    "requirements_inspect": {
        "description": "Inspect requirements.txt-style text: package specs, editable refs, direct URLs, VCS refs, comments, environment markers, suspicious lines. Deterministic, no network.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The requirements.txt content to inspect",
                },
            },
            "required": ["text"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "parse_ok": {"type": "boolean"},
                "total_lines": {"type": "integer"},
                "package_specs": {"type": "array"},
                "editable_refs": {"type": "array"},
                "direct_urls": {"type": "array"},
                "vcs_refs": {"type": "array"},
                "comments": {"type": "array"},
                "requirement_includes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Requirement include lines (-r/--requirement)",
                },
                "constraints_includes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Constraint include lines (-c/--constraint) only",
                },
                "index_options": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Index/find-links/trusted-host options",
                },
                "hash_options": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Hash pinning options (--hash=...)",
                },
                "environment_markers": {"type": "array"},
                "suspicious_lines": {"type": "array"},
                "findings": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "code": {"type": "string"},
                            "severity": {"type": "string"},
                            "message": {"type": "string"},
                            "line": {"type": "integer"},
                            "column": {"type": "integer"},
                        },
                    },
                },
            },
        },
    },
    "go_mod_inspect": {
        "description": "Inspect go.mod text: module path, go version, toolchain, require count, replace/exclude directives. Deterministic, no network.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The go.mod content to inspect"},
            },
            "required": ["text"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "parse_ok": {"type": "boolean"},
                "module_path": {"type": ["string", "null"]},
                "go_version": {"type": ["string", "null"]},
                "toolchain": {"type": ["string", "null"]},
                "require_count": {"type": "integer"},
                "replace_directives": {"type": "array"},
                "exclude_directives": {"type": "array"},
                "findings": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "code": {"type": "string"},
                            "severity": {"type": "string"},
                            "message": {"type": "string"},
                            "line": {"type": "integer"},
                            "column": {"type": "integer"},
                        },
                    },
                },
            },
        },
    },
    "lockfile_summary": {
        "description": "Shallow lockfile summary: detect kind (npm/pnpm/yarn/poetry/uv/cargo/go), approximate package count, ecosystem. Intentionally shallow, no full parse.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The lockfile content to summarize"},
                "kind": {
                    "type": "string",
                    "enum": [
                        "auto",
                        "package-lock",
                        "pnpm-lock",
                        "yarn-lock",
                        "poetry-lock",
                        "uv-lock",
                        "cargo-lock",
                        "go-sum",
                    ],
                    "default": "auto",
                    "description": "Lockfile kind (auto-detect if not specified)",
                },
            },
            "required": ["text"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "parse_ok": {"type": "boolean"},
                "detected_kind": {"type": "string"},
                "ecosystem": {"type": ["string", "null"]},
                "approximate_package_count": {"type": "integer"},
                "warnings": {"type": "array"},
                "findings": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "code": {"type": "string"},
                            "severity": {"type": "string"},
                            "message": {"type": "string"},
                            "line": {"type": "integer"},
                            "column": {"type": "integer"},
                        },
                    },
                },
            },
        },
    },
    # ── LLM output hygiene tools ──────────────────────────────────────────
    "llm_json_output_check": {
        "description": "Detect and diagnose common LLM JSON output issues: fenced code blocks, leading/trailing prose, parse errors with location, fix hints for trailing commas/single quotes/unquoted keys, and multiple concatenated objects.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "LLM output text to analyze for JSON issues",
                },
            },
            "required": ["text"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "has_fence": {
                    "type": "boolean",
                    "description": "True if JSON is wrapped in markdown code fence",
                },
                "fence_language": {"type": "string", "description": "Language tag from code fence"},
                "leading_prose": {
                    "type": "boolean",
                    "description": "True if non-JSON content precedes the JSON",
                },
                "trailing_prose": {
                    "type": "boolean",
                    "description": "True if non-JSON content follows the JSON",
                },
                "parse_ok": {"type": "boolean", "description": "True if JSON parsed successfully"},
                "error_line": {
                    "type": ["integer", "null"],
                    "description": "Line number of first parse error",
                },
                "error_col": {
                    "type": ["integer", "null"],
                    "description": "Column number of first parse error",
                },
                "error_message": {"type": ["string", "null"], "description": "Parse error message"},
                "fix_hints": {
                    "type": "array",
                    "description": "Suggested fixes for detected issues",
                    "items": {
                        "type": "object",
                        "properties": {
                            "code": {"type": "string"},
                            "message": {"type": "string"},
                            "line": {"type": "integer"},
                            "column": {"type": "integer"},
                        },
                    },
                },
                "extracted_content": {
                    "type": ["string", "null"],
                    "description": "Cleaned JSON content if fence/prose was detected",
                },
                "multiple_json_objects": {
                    "type": "boolean",
                    "description": "True if multiple JSON objects concatenated",
                },
                "has_bom": {"type": "boolean", "description": "True if BOM prefix detected"},
                "original_length": {"type": "integer", "description": "Original input length"},
                "extracted_length": {"type": "integer", "description": "Extracted content length"},
            },
        },
    },
    # ── Markdown link check tools ─────────────────────────────────────────
    "markdown_link_check_lexical": {
        "description": "Lexical markdown link validation (no network). Detects malformed links, duplicate anchors, unresolved relative links, and counts external/image links.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Markdown text to analyze",
                },
                "known_paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of known file paths for resolving relative links",
                },
            },
            "required": ["text"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "total_links": {"type": "integer", "description": "Total number of links found"},
                "malformed": {
                    "type": "array",
                    "description": "Malformed links with line and reason",
                    "items": {
                        "type": "object",
                        "properties": {
                            "line": {"type": "integer"},
                            "text": {"type": "string"},
                            "reason": {"type": "string"},
                        },
                    },
                },
                "duplicate_anchors": {
                    "type": "array",
                    "description": "Duplicate anchor names",
                    "items": {
                        "type": "object",
                        "properties": {
                            "anchor": {"type": "string"},
                            "lines": {"type": "array", "items": {"type": "integer"}},
                        },
                    },
                },
                "unresolved_relatives": {
                    "type": "array",
                    "description": "Relative links not in known_paths",
                    "items": {
                        "type": "object",
                        "properties": {
                            "line": {"type": "integer"},
                            "target": {"type": "string"},
                        },
                    },
                },
                "external_count": {
                    "type": "integer",
                    "description": "Number of external (http/https) links",
                },
                "image_count": {"type": "integer", "description": "Number of image links"},
            },
        },
    },
    # ── Repo audit tools ──────────────────────────────────────────────────
    "repo_file_inventory": {
        "description": "Analyze file inventory for repo structure signals (no filesystem access). Detects language/ecosystem signals, counts files by category, identifies config/vendor/generated files, and finds suspicious paths.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of file paths to analyze",
                    "maxItems": 50000,
                },
                "sizes": {
                    "type": "object",
                    "description": "Optional mapping of path to file size in bytes",
                    "additionalProperties": {"type": "integer"},
                },
                "hashes": {
                    "type": "object",
                    "description": "Optional mapping of path to content hash for duplicate detection",
                    "additionalProperties": {"type": "string"},
                },
            },
            "required": ["paths"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "total_files": {"type": "integer", "description": "Total number of files analyzed"},
                "by_extension": {
                    "type": "object",
                    "description": "File count by extension",
                },
                "by_category": {
                    "type": "object",
                    "description": "File count by category (source, test, config, doc, data, hidden, other)",
                },
                "language_signals": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Detected programming languages/ecosystems",
                },
                "config_files_found": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Common config files detected",
                },
                "hidden_files": {"type": "integer", "description": "Number of hidden files"},
                "generated_candidates": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Paths that appear to be generated files",
                },
                "vendor_candidates": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Paths in vendor directories",
                },
                "suspicious_paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Paths with suspicious patterns",
                },
                "largest_files": {
                    "type": "array",
                    "description": "Top 10 largest files by size",
                    "items": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "size": {"type": "integer"},
                        },
                    },
                },
                "duplicate_hashes": {
                    "type": "array",
                    "description": "Groups of files with identical content hashes",
                    "items": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "total_size": {
                    "type": ["integer", "null"],
                    "description": "Total size in bytes (if sizes provided)",
                },
                "truncation_warning": {
                    "type": "boolean",
                    "description": "True if input was truncated due to size limits",
                },
            },
        },
    },
    # ── Network utilities ─────────────────────────────────────────────────
    "ip_inspect": {
        "description": "Inspect a single IPv4 or IPv6 address: canonical text, family, packed bytes, numeric value, and explicit special-use tags. Pure computation, no network access.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "address": {
                    "type": "string",
                    "description": "IP address text (e.g., '192.0.2.1', '::ffff:192.0.2.1')",
                    "maxLength": 100000,
                },
            },
            "required": ["address"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "address": {"type": "string", "description": "Canonical address text"},
                "family": {
                    "type": "string",
                    "enum": ["ipv4", "ipv6"],
                    "description": "Address family",
                },
                "bytes_hex": {
                    "type": "string",
                    "description": "Packed bytes as lowercase hex, no separators",
                },
                "numeric": {
                    "type": "string",
                    "description": "Exact unsigned integer value as decimal string",
                },
                "special_use": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Sorted explicit special-use tags",
                },
                "ipv4_mapped": {
                    "type": ["object", "null"],
                    "description": "Embedded IPv4 metadata for ::ffff:0:0/96 addresses, else null",
                    "properties": {
                        "address": {"type": "string"},
                        "numeric": {"type": "string"},
                    },
                },
            },
        },
    },
    "cidr_inspect": {
        "description": "Inspect a CIDR range: canonical network, prefix/host bits, range bounds, exact address count, and optional same-family containment. Pure computation, no network access.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "cidr": {
                    "type": "string",
                    "description": "CIDR text such as '192.0.2.99/24' or '2001:db8::1/64'",
                    "maxLength": 100000,
                },
                "contains": {
                    "type": "string",
                    "description": "Optional candidate address to test for membership (must use the same family)",
                    "maxLength": 100000,
                },
            },
            "required": ["cidr"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "family": {"type": "string", "enum": ["ipv4", "ipv6"]},
                "cidr": {"type": "string", "description": "Canonical network CIDR"},
                "prefix_length": {"type": "integer"},
                "host_bits": {"type": "integer"},
                "network_address": {"type": "string"},
                "netmask": {"type": "string"},
                "first_address": {"type": "string"},
                "last_address": {"type": "string"},
                "broadcast_address": {
                    "type": ["string", "null"],
                    "description": "Final address for IPv4, null for IPv6",
                },
                "address_count": {
                    "type": "string",
                    "description": "Exact address count as decimal string",
                },
                "contains": {
                    "type": ["boolean", "null"],
                    "description": "Containment result, null when no candidate supplied",
                },
                "contains_address": {
                    "type": ["string", "null"],
                    "description": "Candidate canonical address, null when none supplied",
                },
            },
        },
    },
    # ── Encoding utilities ────────────────────────────────────────────────
    "codec_convert": {
        "description": "Convert text between utf8, hex, base64, and base64url codecs with strict validation and canonical outputs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "value": {
                    "type": "string",
                    "description": "Encoded input text in the source format",
                    "maxLength": 100000,
                },
                "from": {
                    "type": "string",
                    "enum": ["utf8", "hex", "base64", "base64url"],
                    "description": "Source codec format",
                },
                "to": {
                    "type": "string",
                    "enum": ["utf8", "hex", "base64", "base64url"],
                    "description": "Destination codec format",
                },
            },
            "required": ["value", "from", "to"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "value": {"type": "string", "description": "Canonical converted text"},
                "from": {"type": "string"},
                "to": {"type": "string"},
                "byte_length": {
                    "type": "integer",
                    "description": "Decoded payload length in bytes",
                },
            },
        },
    },
    "radix_convert": {
        "description": "Convert a signed ASCII integer between bases 2 and 36. Magnitude is capped at 2**128 - 1 for cross-implementation parity.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "value": {
                    "type": "string",
                    "description": "Integer text with optional single leading +/- and ASCII digits",
                    "maxLength": 100000,
                },
                "from_base": {
                    "type": "integer",
                    "minimum": 2,
                    "maximum": 36,
                    "description": "Source base",
                },
                "to_base": {
                    "type": "integer",
                    "minimum": 2,
                    "maximum": 36,
                    "description": "Destination base",
                },
                "uppercase": {
                    "type": "boolean",
                    "default": False,
                    "description": "Use uppercase A-Z digits instead of lowercase",
                },
            },
            "required": ["value", "from_base", "to_base"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "value": {"type": "string", "description": "Canonical converted value"},
                "from_base": {"type": "integer"},
                "to_base": {"type": "integer"},
                "uppercase": {"type": "boolean"},
                "negative": {"type": "boolean"},
                "magnitude_decimal": {
                    "type": "string",
                    "description": "Decimal magnitude string",
                },
            },
        },
    },
    # ── Temporal utilities ────────────────────────────────────────────────
    "datetime_convert": {
        "description": "Convert between RFC3339 timestamps and Unix seconds/milliseconds/nanoseconds with exact nanosecond precision and fixed offsets. No named timezones or DST database.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "value": {
                    "type": "string",
                    "description": "Timestamp text: RFC3339 or signed decimal Unix integer string",
                    "maxLength": 100000,
                },
                "format": {
                    "type": "string",
                    "enum": ["rfc3339", "unix_seconds", "unix_milliseconds", "unix_nanoseconds"],
                    "description": "Input format of value",
                },
                "output_offset": {
                    "type": "string",
                    "pattern": "^(Z|[+-][0-9]{2}:[0-9]{2})$",
                    "maxLength": 100000,
                    "description": "Optional fixed display offset (Z or +/-HH:MM)",
                },
            },
            "required": ["value", "format"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "rfc3339": {"type": "string"},
                "utc_rfc3339": {"type": "string"},
                "unix_seconds": {"type": "string"},
                "unix_milliseconds": {"type": "string"},
                "unix_nanoseconds": {"type": "string"},
                "offset_seconds": {"type": "integer"},
                "selected_offset": {"type": "string"},
                "components": {
                    "type": "object",
                    "description": "Calendar components in the selected offset",
                },
            },
        },
    },
    "cron_inspect": {
        "description": "Inspect a five-field cron expression and list strictly-later runs at a fixed offset. Corrected Vixie/Cronie DOM/DOW star-syntax semantics; bounded search over one 400-year Gregorian cycle.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Five whitespace-delimited fields: minute hour day-of-month month day-of-week",
                    "maxLength": 100000,
                },
                "after": {
                    "type": "string",
                    "description": "RFC3339 reference instant; results are strictly later and reuse its fixed offset",
                    "maxLength": 100000,
                },
                "count": {
                    "type": "integer",
                    "default": 5,
                    "minimum": 1,
                    "maximum": 32,
                    "description": "Requested run count",
                },
            },
            "required": ["expression", "after"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "expression": {"type": "string"},
                "normalized_expression": {"type": "string"},
                "parsed_values": {
                    "type": "object",
                    "description": "Sorted normalized integer sets per field",
                },
                "offset": {"type": "string"},
                "offset_seconds": {"type": "integer"},
                "satisfiable": {"type": "boolean"},
                "next_runs": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Strictly-later runs in the same fixed offset",
                },
                "count": {
                    "type": "integer",
                    "description": "Actual entries in next_runs",
                },
            },
        },
    },
}

# ---------------------------------------------------------------------------
# Catalog metadata authority (Plan 040).
#
# TOOL_METADATA is the single authored authority for catalog/selection
# concerns: canonical public tool name, handler binding, and
# agent-selection metadata. TOOL_SCHEMAS owns only protocol shape
# (description, inputSchema, outputSchema, deprecated/title).
#
# Fields:
#   handler     – attribute name in eggcalc.mcp.tools (narrow locator, not
#                 an arbitrary import path). Resolved by server._build_tool_handlers.
#   category    – tool domain (math, text, json, path, shell, etc.)
#   tier        – 0 = ultra-common, 1 = default coding, 2 = contextual, 3 = specialized
#   tags        – selection/discovery keywords (sole authored authority;
#                 TOOL_SCHEMAS no longer carries tier/tags copies)
#   selection_summary – one-line authored selection signal answering "when
#                 should an agent choose this tool rather than a neighbor?"
#                 (Plan 041; <= SELECTION_SUMMARY_MAX_LENGTH chars; used as
#                 the compact description and search/ranking material, never
#                 a truncation of the full description)
#   keywords    – small authored synonym/concept list for lexical discovery
#                 (Plan 041; <= SELECTION_KEYWORDS_MAX_COUNT items, each
#                 <= SELECTION_KEYWORD_MAX_LENGTH chars; true alternate names
#                 still belong in aliases)
#   profiles    – named profiles that include this tool
#   aliases     – alternative names (future use)
#   llm_exposure – default | contextual | expert_only | harness_only | hidden
#   harness_use – preflight categories this tool serves
#   cost        – cheap | moderate | heavy
#   stability   – stable | experimental | deprecated
#   composite   – True if this tool wraps other primitives
#
# Annotations remain owned by TOOL_ANNOTATIONS / get_tool_annotations()
# (uniform read-only/closed-world posture); they are not duplicated here.
# Every key in TOOL_METADATA must have a corresponding entry in TOOL_SCHEMAS,
# and TOOL_HANDLERS is derived from these handler locators.
# ---------------------------------------------------------------------------

TOOL_METADATA: dict[str, dict[str, Any]] = {
    # ── Tier 0: Ultra-common ──────────────────────────────────────────────
    "math_eval": {
        "handler": "math_eval",
        "category": "math",
        "tier": 0,
        "tags": ["math", "evaluation", "arithmetic", "units", "constants"],
        "selection_summary": (
            'Evaluate math, unit-conversion, and physical-constant expressions; use '
            'unit_convert for one known unit pair or constant_lookup for constant '
            'metadata.'
        ),
        "keywords": [
            'calculate',
            'arithmetic',
            'unit conversion',
            'expression',
            'square root',
            'percent',
        ],
        "profiles": ["full", "default", "human_math", "agent_core"],
        "aliases": [],
        "llm_exposure": "default",
        "harness_use": ["none"],
        "cost": "moderate",
        "stability": "stable",
        "composite": False,
    },
    "text_equal": {
        "handler": "text_equal",
        "category": "text",
        "tier": 0,
        "tags": ["text", "comparison", "equality", "unicode"],
        "selection_summary": (
            'Test whether two strings are equal under normalization/casefold/trim '
            'modes; use text_diff_explain to explain why they differ.'
        ),
        "keywords": ['compare strings', 'string equality'],
        "profiles": ["full", "default", "codegg_core", "agent_core"],
        "aliases": [],
        "llm_exposure": "default",
        "harness_use": ["none"],
        "cost": "cheap",
        "stability": "stable",
        "composite": False,
    },
    "text_count": {
        "handler": "text_count",
        "category": "text",
        "tier": 0,
        "tags": ["text", "count", "character", "frequency"],
        "selection_summary": (
            'Count occurrences of a character or build a frequency table; use '
            'text_measure for aggregate size metrics.'
        ),
        "keywords": ['count characters', 'frequency', 'character count'],
        "profiles": ["full", "default"],
        "aliases": [],
        "llm_exposure": "default",
        "harness_use": ["none"],
        "cost": "cheap",
        "stability": "stable",
        "composite": False,
    },
    "text_measure": {
        "handler": "text_measure",
        "category": "text",
        "tier": 0,
        "tags": ["text", "measurement", "unicode", "metrics"],
        "selection_summary": (
            'Measure text size and shape (bytes, words, lines, normalization state); '
            'use text_inspect for hidden-character security analysis.'
        ),
        "keywords": ['text length', 'word count', 'measure text'],
        "profiles": ["full", "default"],
        "aliases": [],
        "llm_exposure": "default",
        "harness_use": ["none"],
        "cost": "cheap",
        "stability": "stable",
        "composite": False,
    },
    "text_fingerprint": {
        "handler": "text_fingerprint_mcp",
        "category": "text",
        "tier": 0,
        "tags": ["text", "hash", "fingerprint", "sha256", "identity", "canonicalization"],
        "selection_summary": (
            'Fingerprint text with canonicalization options for stable identity; use '
            'text_hash for raw multi-algorithm hashes.'
        ),
        "keywords": ['fingerprint', 'identity hash', 'canonical hash'],
        "profiles": ["full", "default", "codegg_core", "codegg_repo_audit"],
        "aliases": [],
        "llm_exposure": "default",
        "harness_use": ["edit_preflight"],
        "cost": "cheap",
        "stability": "stable",
        "composite": False,
    },
    "validate_json": {
        "handler": "validate_json",
        "category": "validation",
        "tier": 0,
        "tags": ["validation", "json", "structured-data"],
        "selection_summary": (
            'Validate JSON syntax and report parse errors; use json_extract to read '
            'values or json_compare to diff two documents.'
        ),
        "keywords": ['json valid', 'parse json', 'validate json'],
        "profiles": [
            "full",
            "default",
            "codegg_core",
            "codegg_core_min",
            "codegg_config",
            "agent_core",
        ],
        "aliases": [],
        "llm_exposure": "default",
        "harness_use": ["config_preflight"],
        "cost": "cheap",
        "stability": "stable",
        "composite": False,
    },
    "path_normalize": {
        "handler": "path_normalize",
        "category": "path",
        "tier": 0,
        "tags": ["text", "path", "filesystem", "normalize"],
        "selection_summary": (
            'Normalize one path (dot segments, separators); use path_compare to '
            'compare two paths or path_analyze for components.'
        ),
        "keywords": ['normalize path', 'clean path'],
        "profiles": ["full", "default", "codegg_core", "agent_core"],
        "aliases": [],
        "llm_exposure": "default",
        "harness_use": ["path_preflight"],
        "cost": "cheap",
        "stability": "stable",
        "composite": False,
    },
    # ── Tier 1: Default coding-agent sanity ───────────────────────────────
    "text_diff_explain": {
        "handler": "text_diff_explain",
        "category": "text",
        "tier": 1,
        "tags": ["text", "diff", "comparison", "unicode"],
        "selection_summary": (
            'Explain why two strings differ (spans, confusables, invisibles); use '
            'text_equal for a boolean equality verdict.'
        ),
        "keywords": ['why different', 'string diff', 'diff explain'],
        "profiles": ["full", "default", "codegg_core", "codegg_patch", "agent_core"],
        "aliases": [],
        "llm_exposure": "default",
        "harness_use": ["edit_preflight"],
        "cost": "moderate",
        "stability": "stable",
        "composite": False,
    },
    "text_inspect": {
        "handler": "text_inspect",
        "category": "text",
        "tier": 1,
        "tags": ["text", "unicode", "inspection", "security"],
        "selection_summary": (
            'Inspect one string for hidden characters, confusables, and mixed '
            'scripts; use text_security_inspect for a policy verdict across checks.'
        ),
        "keywords": ['hidden characters', 'confusable', 'inspect text', 'invisible'],
        "profiles": ["full", "default", "codegg_core", "codegg_unicode_security"],
        "aliases": [],
        "llm_exposure": "default",
        "harness_use": ["prompt_input_preflight"],
        "cost": "moderate",
        "stability": "stable",
        "composite": False,
    },
    "text_replace_check": {
        "handler": "text_replace_check",
        "category": "text",
        "tier": 1,
        "tags": ["text", "replace", "edit", "safety", "check"],
        "selection_summary": (
            'Check whether a text replacement would apply cleanly (match count, '
            'ambiguity, preview); use edit_preflight for a full approval verdict.'
        ),
        "keywords": ['replace check', 'safe edit', 'find and replace', 'edit preview'],
        "profiles": [
            "full",
            "default",
            "codegg_core",
            "codegg_core_min",
            "codegg_patch",
            "agent_core",
        ],
        "aliases": [],
        "llm_exposure": "default",
        "harness_use": ["edit_preflight"],
        "cost": "cheap",
        "stability": "stable",
        "composite": False,
    },
    "line_range_extract": {
        "handler": "line_range_extract",
        "category": "text",
        "tier": 1,
        "tags": ["text", "line", "range", "extract", "offset"],
        "selection_summary": (
            'Extract exact line ranges with stable offsets and fingerprints; use '
            'line_range_compare to diff ranges.'
        ),
        "keywords": ['extract lines', 'line range', 'get lines'],
        "profiles": ["full", "default", "codegg_patch"],
        "aliases": [],
        "llm_exposure": "default",
        "harness_use": ["edit_preflight"],
        "cost": "cheap",
        "stability": "stable",
        "composite": False,
    },
    "json_compare": {
        "handler": "json_compare",
        "category": "json",
        "tier": 1,
        "tags": ["json", "structured-data", "comparison", "config"],
        "selection_summary": (
            'Semantically diff two JSON documents ignoring formatting; use '
            'json_extract for one value or structured_data_compare for a multi-tool '
            'verdict.'
        ),
        "keywords": ['compare json', 'json diff'],
        "profiles": ["full", "default", "codegg_config"],
        "aliases": [],
        "llm_exposure": "default",
        "harness_use": ["config_preflight"],
        "cost": "moderate",
        "stability": "stable",
        "composite": False,
    },
    "json_canonicalize": {
        "handler": "json_canonicalize",
        "category": "json",
        "tier": 1,
        "tags": ["json", "canonical", "hash", "deterministic", "format"],
        "selection_summary": (
            'Canonicalize JSON (sorted keys, stable hash, duplicate detection); use '
            'json_compare to diff two docs.'
        ),
        "keywords": ['canonical json', 'sort keys', 'stable hash', 'normalize json'],
        "profiles": ["full", "default", "codegg_config"],
        "aliases": [],
        "llm_exposure": "default",
        "harness_use": ["config_preflight"],
        "cost": "moderate",
        "stability": "stable",
        "composite": False,
    },
    "json_query": {
        "handler": "json_query",
        "category": "json",
        "tier": 2,
        "tags": ["json", "pointer", "extraction", "query", "rfc6901"],
        "selection_summary": (
            'Deprecated RFC 6901 extractor; use json_extract for richer output with '
            'available_keys and detail levels.'
        ),
        "keywords": ['json pointer (deprecated)'],
        "profiles": ["full"],
        "aliases": [],
        "llm_exposure": "contextual",
        "harness_use": ["none"],
        "cost": "moderate",
        "stability": "deprecated",
        "composite": False,
    },
    "validate_toml": {
        "handler": "validate_toml",
        "category": "validation",
        "tier": 1,
        "tags": ["validation", "structured-data", "toml", "config", "rust", "python"],
        "selection_summary": (
            'Validate TOML syntax with error locations; use toml_shape for structure '
            'or pyproject_inspect for manifest semantics.'
        ),
        "keywords": ['validate toml', 'toml parse'],
        "profiles": ["full", "default", "codegg_core", "codegg_config"],
        "aliases": [],
        "llm_exposure": "default",
        "harness_use": ["config_preflight"],
        "cost": "cheap",
        "stability": "stable",
        "composite": False,
    },
    "validate_brackets": {
        "handler": "validate_brackets",
        "category": "validation",
        "tier": 1,
        "tags": ["validation", "brackets", "delimiters"],
        "selection_summary": (
            'Check delimiter balance with unmatched positions; use validate_json or '
            'validate_toml for format-aware validation.'
        ),
        "keywords": ['brackets', 'balanced', 'parentheses'],
        "profiles": ["full", "default"],
        "aliases": [],
        "llm_exposure": "default",
        "harness_use": ["none"],
        "cost": "cheap",
        "stability": "stable",
        "composite": False,
    },
    "validate_regex": {
        "handler": "validate_regex",
        "category": "regex",
        "tier": 1,
        "tags": ["text", "regex", "validation", "pattern"],
        "selection_summary": (
            'Test a regex against sample strings (match spans and groups); use '
            'regex_safety_check for backtracking risk.'
        ),
        "keywords": ['test regex', 'regex match'],
        "profiles": ["full", "default"],
        "aliases": [],
        "llm_exposure": "default",
        "harness_use": ["command_preflight"],
        "cost": "moderate",
        "stability": "stable",
        "composite": False,
    },
    "regex_finditer": {
        "handler": "regex_finditer",
        "category": "regex",
        "tier": 1,
        "tags": ["text", "regex", "search", "find", "pattern"],
        "selection_summary": (
            'Find all regex matches with spans and groups; use validate_regex to test '
            'a pattern against samples first.'
        ),
        "keywords": ['find regex', 'search pattern', 'regex matches'],
        "profiles": ["full", "default"],
        "aliases": [],
        "llm_exposure": "default",
        "harness_use": ["none"],
        "cost": "moderate",
        "stability": "stable",
        "composite": False,
    },
    "regex_safety_check": {
        "handler": "regex_safety_check",
        "category": "regex",
        "tier": 1,
        "tags": ["text", "regex", "safety", "security", "backtracking"],
        "selection_summary": (
            'Score a regex for catastrophic-backtracking risk; use validate_regex to '
            'test what it matches.'
        ),
        "keywords": ['regex safe', 'backtracking', 'ReDoS', 'regex risk'],
        "profiles": ["full", "default", "codegg_shell"],
        "aliases": [],
        "llm_exposure": "default",
        "harness_use": ["command_preflight"],
        "cost": "cheap",
        "stability": "stable",
        "composite": False,
    },
    "glob_match": {
        "handler": "glob_match_mcp",
        "category": "path",
        "tier": 1,
        "tags": ["text", "glob", "pattern", "path", "wildcard"],
        "selection_summary": (
            'Test a glob pattern against a path (*, **, ? semantics); use '
            'regex_finditer for regex search.'
        ),
        "keywords": ['glob', 'wildcard', 'fnmatch', 'pattern match'],
        "profiles": ["full", "default"],
        "aliases": [],
        "llm_exposure": "default",
        "harness_use": ["none"],
        "cost": "cheap",
        "stability": "stable",
        "composite": False,
    },
    "identifier_inspect": {
        "handler": "identifier_inspect_mcp",
        "category": "identifier",
        "tier": 1,
        "tags": ["text", "identifier", "collision", "confusable", "security", "validation"],
        "selection_summary": (
            'Inspect one/few identifier strings; use identifier_table_inspect for '
            'collision analysis across a table.'
        ),
        "keywords": ['identifier check', 'name collision', 'confusable name'],
        "profiles": ["full", "default", "codegg_core", "codegg_unicode_security"],
        "aliases": [],
        "llm_exposure": "default",
        "harness_use": ["reasoning_only"],
        "cost": "moderate",
        "stability": "stable",
        "composite": False,
    },
    "escape_text": {
        "handler": "escape_text",
        "category": "text",
        "tier": 1,
        "tags": ["text", "escape", "encoding", "shell", "json", "regex"],
        "selection_summary": (
            'Escape text for json/python/rust/shell/regex/markdown/html/url output; '
            'use unescape_text for the reverse.'
        ),
        "keywords": ['escape', 'quote', 'shell escape'],
        "profiles": ["full", "default"],
        "aliases": [],
        "llm_exposure": "default",
        "harness_use": ["none"],
        "cost": "cheap",
        "stability": "stable",
        "composite": False,
    },
    "unescape_text": {
        "handler": "unescape_text",
        "category": "text",
        "tier": 1,
        "tags": ["text", "escape", "encoding", "shell", "json", "regex"],
        "selection_summary": (
            'Decode escaped text (json/python/unicode/url); use escape_text to encode '
            'for an output format.'
        ),
        "keywords": ['unescape', 'decode escapes', 'unquote'],
        "profiles": ["full", "default"],
        "aliases": [],
        "llm_exposure": "default",
        "harness_use": ["none"],
        "cost": "cheap",
        "stability": "stable",
        "composite": False,
    },
    "text_window": {
        "handler": "text_window",
        "category": "text",
        "tier": 1,
        "tags": ["text", "position", "context", "unicode", "window"],
        "selection_summary": (
            'Show a text window with context lines around a position; use '
            'text_position for offset conversion.'
        ),
        "keywords": ['context lines', 'show around', 'text window'],
        "profiles": ["full", "default"],
        "aliases": [],
        "llm_exposure": "default",
        "harness_use": ["none"],
        "cost": "cheap",
        "stability": "stable",
        "composite": False,
    },
    "list_dedupe": {
        "handler": "list_dedupe_mcp",
        "category": "list",
        "tier": 1,
        "tags": ["list", "dedupe", "unique", "normalization"],
        "selection_summary": (
            'Remove duplicate list items preserving order; use list_sort to order or '
            'list_compare to diff.'
        ),
        "keywords": ['dedupe', 'unique list', 'remove duplicates'],
        "profiles": ["full", "default"],
        "aliases": [],
        "llm_exposure": "default",
        "harness_use": ["none"],
        "cost": "cheap",
        "stability": "stable",
        "composite": False,
    },
    "list_sort": {
        "handler": "list_sort_mcp",
        "category": "list",
        "tier": 1,
        "tags": ["list", "sort", "order", "normalization"],
        "selection_summary": (
            'Sort string lists with normalization/casefold options; use list_dedupe '
            'to drop duplicates first.'
        ),
        "keywords": ['sort list', 'order list'],
        "profiles": ["full", "default"],
        "aliases": [],
        "llm_exposure": "default",
        "harness_use": ["none"],
        "cost": "cheap",
        "stability": "stable",
        "composite": False,
    },
    # ── Tier 2: Contextual / heavier analysis ─────────────────────────────
    "unit_convert": {
        "handler": "unit_convert",
        "category": "math",
        "tier": 2,
        "tags": ["math", "units", "conversion"],
        "selection_summary": (
            'Convert one value between two known units; use math_eval for full '
            'expressions mixing values and units.'
        ),
        "keywords": ['convert units', 'km to m', 'unit conversion'],
        "profiles": ["full", "human_math"],
        "aliases": [],
        "llm_exposure": "contextual",
        "harness_use": ["none"],
        "cost": "cheap",
        "stability": "stable",
        "composite": False,
    },
    "unit_info": {
        "handler": "unit_info",
        "category": "math",
        "tier": 2,
        "tags": ["math", "units", "information"],
        "selection_summary": (
            "Look up a unit's canonical name and category; use unit_convert to "
            'convert values between units.'
        ),
        "keywords": ['unit info', 'unit category', 'canonical unit'],
        "profiles": ["full", "human_math"],
        "aliases": [],
        "llm_exposure": "contextual",
        "harness_use": ["none"],
        "cost": "cheap",
        "stability": "stable",
        "composite": False,
    },
    "constant_lookup": {
        "handler": "constant_lookup",
        "category": "math",
        "tier": 2,
        "tags": ["math", "constants", "physics", "lookup"],
        "selection_summary": (
            "Look up a physical constant's value and symbol; use math_eval to compute "
            'expressions containing constants.'
        ),
        "keywords": ['physical constant', 'avogadro', 'planck', 'speed of light'],
        "profiles": ["full", "human_math"],
        "aliases": [],
        "llm_exposure": "contextual",
        "harness_use": ["none"],
        "cost": "cheap",
        "stability": "stable",
        "composite": False,
    },
    "json_extract": {
        "handler": "json_extract",
        "category": "json",
        "tier": 2,
        "tags": ["json", "structured-data", "extraction", "config", "pointer"],
        "selection_summary": (
            'Extract one value via RFC 6901 pointer; use json_shape for '
            'structure-only views or json_compare for whole-document diffs.'
        ),
        "keywords": ['json pointer', 'extract json', 'get json value'],
        "profiles": ["full", "codegg_config"],
        "aliases": [],
        "llm_exposure": "contextual",
        "harness_use": ["none"],
        "cost": "moderate",
        "stability": "stable",
        "composite": False,
    },
    "list_compare": {
        "handler": "list_compare",
        "category": "list",
        "tier": 2,
        "tags": ["text", "list", "comparison", "set"],
        "selection_summary": (
            'Compare two string lists as ordered/set/multiset with missing/extra '
            'deltas; use list_dedupe or list_sort to normalize one list.'
        ),
        "keywords": ['compare lists', 'list diff'],
        "profiles": ["full"],
        "aliases": [],
        "llm_exposure": "contextual",
        "harness_use": ["none"],
        "cost": "moderate",
        "stability": "stable",
        "composite": False,
    },
    "line_range_compare": {
        "handler": "line_range_compare",
        "category": "text",
        "tier": 2,
        "tags": ["text", "line", "range", "compare", "diff"],
        "selection_summary": (
            'Compare the same line range across two texts; use line_range_extract to '
            'read one range.'
        ),
        "keywords": ['compare lines', 'diff lines'],
        "profiles": ["full", "codegg_patch"],
        "aliases": [],
        "llm_exposure": "contextual",
        "harness_use": ["edit_preflight"],
        "cost": "moderate",
        "stability": "stable",
        "composite": False,
    },
    "markdown_structure": {
        "handler": "markdown_structure_mcp",
        "category": "markdown",
        "tier": 2,
        "tags": ["markdown", "structure", "headings", "code-fences", "links", "frontmatter"],
        "selection_summary": (
            'Parse markdown headings/fences/links/comments/frontmatter lexically; use '
            'code_fence_extract for code blocks only.'
        ),
        "keywords": ['markdown structure', 'headings', 'frontmatter'],
        "profiles": ["full", "codegg_repo_audit"],
        "aliases": [],
        "llm_exposure": "contextual",
        "harness_use": ["none"],
        "cost": "moderate",
        "stability": "stable",
        "composite": False,
    },
    "code_fence_extract": {
        "handler": "code_fence_extract_mcp",
        "category": "markdown",
        "tier": 2,
        "tags": ["markdown", "code-fences", "extraction", "fingerprint"],
        "selection_summary": (
            'Extract fenced code blocks with line ranges and fingerprints; use '
            'markdown_structure for full outline.'
        ),
        "keywords": ['code fence', 'extract code', 'code block'],
        "profiles": ["full", "codegg_repo_audit"],
        "aliases": [],
        "llm_exposure": "contextual",
        "harness_use": ["none"],
        "cost": "moderate",
        "stability": "stable",
        "composite": False,
    },
    "patch_apply_check": {
        "handler": "patch_apply_check_mcp",
        "category": "patch",
        "tier": 2,
        "tags": ["patch", "diff", "unified", "validation", "apply"],
        "selection_summary": (
            'Dry-run apply a unified diff against in-memory files; use edit_preflight '
            'for an approval verdict.'
        ),
        "keywords": ['apply patch', 'dry run patch', 'patch applicability'],
        "profiles": ["full", "codegg_preflight", "codegg_patch"],
        "aliases": [],
        "llm_exposure": "harness_only",
        "harness_use": ["edit_preflight"],
        "cost": "moderate",
        "stability": "stable",
        "composite": False,
    },
    "patch_summary": {
        "handler": "patch_summary_mcp",
        "category": "patch",
        "tier": 2,
        "tags": ["patch", "diff", "unified", "summary", "statistics"],
        "selection_summary": (
            'Summarize a diff (files, hunks, +/- counts) without applying; use '
            'patch_apply_check to test application.'
        ),
        "keywords": ['patch summary', 'diff stats', 'diffstat'],
        "profiles": ["full", "codegg_patch"],
        "aliases": [],
        "llm_exposure": "contextual",
        "harness_use": ["none"],
        "cost": "moderate",
        "stability": "stable",
        "composite": False,
    },
    "diff_touched_paths": {
        "handler": "diff_touched_paths_mcp",
        "category": "patch",
        "tier": 2,
        "tags": ["patch", "diff", "unified", "classification", "files"],
        "selection_summary": (
            'List files touched by a diff (added/deleted/renamed/modified); use '
            'patch_summary for counts.'
        ),
        "keywords": ['touched files', 'changed files', 'diff files'],
        "profiles": ["full", "codegg_patch", "codegg_repo_audit"],
        "aliases": [],
        "llm_exposure": "contextual",
        "harness_use": ["none"],
        "cost": "cheap",
        "stability": "stable",
        "composite": False,
    },
    "diff_hunk_ranges": {
        "handler": "diff_hunk_ranges_mcp",
        "category": "patch",
        "tier": 2,
        "tags": ["patch", "diff", "unified", "hunks", "ranges"],
        "selection_summary": (
            'Extract per-file hunk line ranges from a diff; use diff_touched_paths '
            'for file lists.'
        ),
        "keywords": ['hunk ranges', 'diff hunks', 'hunk lines'],
        "profiles": ["full", "codegg_patch", "codegg_repo_audit"],
        "aliases": [],
        "llm_exposure": "contextual",
        "harness_use": ["none"],
        "cost": "cheap",
        "stability": "stable",
        "composite": False,
    },
    "diff_file_headers": {
        "handler": "diff_file_headers_mcp",
        "category": "patch",
        "tier": 2,
        "tags": ["patch", "diff", "unified", "headers", "metadata"],
        "selection_summary": (
            'Extract diff file-header metadata (git/index/mode/rename/binary); use '
            'patch_summary for change counts.'
        ),
        "keywords": ['diff headers', 'git diff metadata', 'rename detect'],
        "profiles": ["full", "codegg_patch", "codegg_repo_audit"],
        "aliases": [],
        "llm_exposure": "contextual",
        "harness_use": ["none"],
        "cost": "cheap",
        "stability": "stable",
        "composite": False,
    },
    "patch_conflict_markers_inspect": {
        "handler": "patch_conflict_markers_inspect_mcp",
        "category": "patch",
        "tier": 2,
        "tags": ["patch", "diff", "conflict", "markers", "merge"],
        "selection_summary": (
            'Detect merge-conflict markers and their balance/locations; use '
            'unified_diff_validate for diff syntax.'
        ),
        "keywords": ['conflict markers', 'merge conflict', 'merge markers'],
        "profiles": ["full", "codegg_patch", "codegg_repo_audit"],
        "aliases": [],
        "llm_exposure": "contextual",
        "harness_use": ["none"],
        "cost": "cheap",
        "stability": "stable",
        "composite": False,
    },
    "unified_diff_validate": {
        "handler": "unified_diff_validate_mcp",
        "category": "patch",
        "tier": 2,
        "tags": ["patch", "diff", "unified", "validation", "lint"],
        "selection_summary": (
            'Validate unified-diff syntax (hunks, counts, stray lines); use '
            'patch_apply_check to test application.'
        ),
        "keywords": ['validate diff', 'unified diff', 'diff lint'],
        "profiles": ["full", "codegg_patch", "codegg_repo_audit"],
        "aliases": [],
        "llm_exposure": "contextual",
        "harness_use": ["none"],
        "cost": "cheap",
        "stability": "stable",
        "composite": False,
    },
    "path_analyze": {
        "handler": "path_analyze_mcp",
        "category": "path",
        "tier": 2,
        "tags": ["text", "path", "filesystem", "lexical"],
        "selection_summary": (
            'Break a path into components, extension, and hidden/traversal signals; '
            'use path_normalize to collapse it first.'
        ),
        "keywords": ['analyze path', 'path parts', 'extension'],
        "profiles": ["full"],
        "aliases": [],
        "llm_exposure": "contextual",
        "harness_use": ["none"],
        "cost": "cheap",
        "stability": "stable",
        "composite": False,
    },
    "path_compare": {
        "handler": "path_compare_mcp",
        "category": "path",
        "tier": 2,
        "tags": ["text", "path", "filesystem", "comparison"],
        "selection_summary": (
            'Compare two paths under explicit normalization rules; use path_normalize '
            'for single-path cleanup.'
        ),
        "keywords": ['compare paths', 'same path'],
        "profiles": ["full"],
        "aliases": [],
        "llm_exposure": "contextual",
        "harness_use": ["none"],
        "cost": "cheap",
        "stability": "stable",
        "composite": False,
    },
    "path_scope_check": {
        "handler": "path_scope_check_mcp",
        "category": "path",
        "tier": 2,
        "tags": ["text", "path", "filesystem", "security", "scope"],
        "selection_summary": (
            'Check a target stays lexically inside a root (no symlink resolution); '
            'use path_analyze for component detail.'
        ),
        "keywords": ['path traversal', 'inside root', 'scope check', 'sandbox'],
        "profiles": ["full", "codegg_preflight"],
        "aliases": [],
        "llm_exposure": "harness_only",
        "harness_use": ["path_preflight"],
        "cost": "cheap",
        "stability": "stable",
        "composite": False,
    },
    "shell_split": {
        "handler": "shell_split",
        "category": "shell",
        "tier": 2,
        "tags": ["shell", "argv", "parsing", "security", "sanity"],
        "selection_summary": (
            'Parse a shell command into argv tokens and flag risky operators; use '
            'command_preflight for an approval verdict.'
        ),
        "keywords": ['parse shell', 'split command', 'argv'],
        "profiles": ["full", "codegg_preflight", "codegg_shell"],
        "aliases": [],
        "llm_exposure": "harness_only",
        "harness_use": ["command_preflight"],
        "cost": "cheap",
        "stability": "stable",
        "composite": False,
    },
    "shell_quote_join": {
        "handler": "shell_quote_join",
        "category": "shell",
        "tier": 2,
        "tags": ["shell", "argv", "quoting", "safety"],
        "selection_summary": (
            'Quote argv tokens into a safe shell string; use shell_split to parse or '
            'argv_compare to compare.'
        ),
        "keywords": ['quote shell', 'join argv', 'shell quoting'],
        "profiles": ["full", "codegg_shell"],
        "aliases": [],
        "llm_exposure": "contextual",
        "harness_use": ["none"],
        "cost": "cheap",
        "stability": "stable",
        "composite": False,
    },
    "argv_compare": {
        "handler": "shell_argv_compare",
        "category": "shell",
        "tier": 2,
        "tags": ["shell", "argv", "comparison", "sanity"],
        "selection_summary": (
            'Compare two commands by parsed argv tokens, not raw text; use '
            'shell_split to inspect one command.'
        ),
        "keywords": ['compare commands', 'argv diff'],
        "profiles": ["full", "codegg_shell"],
        "aliases": [],
        "llm_exposure": "contextual",
        "harness_use": ["command_preflight"],
        "cost": "cheap",
        "stability": "stable",
        "composite": False,
    },
    "validate_schema_light": {
        "handler": "validate_schema_light",
        "category": "validation",
        "tier": 3,
        "tags": ["validation", "json", "schema", "structured-data"],
        "selection_summary": (
            'Validate JSON against a small structural schema; use validate_json for '
            'syntax-only checks.'
        ),
        "keywords": ['json schema', 'validate structure', 'required fields'],
        "profiles": ["full", "codegg_config"],
        "aliases": [],
        "llm_exposure": "contextual",
        "harness_use": ["config_preflight"],
        "cost": "moderate",
        "stability": "stable",
        "composite": False,
    },
    "toml_shape": {
        "handler": "toml_shape_mcp",
        "category": "toml",
        "tier": 2,
        "tags": ["toml", "structure", "shape", "config", "validation"],
        "selection_summary": (
            'Show TOML structure (keys, tables, nesting); use validate_toml for ' 'syntax errors.'
        ),
        "keywords": ['toml structure', 'toml shape'],
        "profiles": ["full", "codegg_config"],
        "aliases": [],
        "llm_exposure": "contextual",
        "harness_use": ["none"],
        "cost": "moderate",
        "stability": "stable",
        "composite": False,
    },
    "version_compare": {
        "handler": "version_compare_mcp",
        "category": "version",
        "tier": 2,
        "tags": ["version", "semver", "comparison"],
        "selection_summary": (
            'Compare two concrete versions; use version_constraint_check for '
            'range/constraint satisfaction.'
        ),
        "keywords": ['compare versions', 'semver', 'newer version'],
        "profiles": ["full", "codegg_config"],
        "aliases": [],
        "llm_exposure": "contextual",
        "harness_use": ["none"],
        "cost": "cheap",
        "stability": "stable",
        "composite": False,
    },
    "unicode_policy_check": {
        "handler": "unicode_policy_check_mcp",
        "category": "unicode",
        "tier": 2,
        "tags": ["text", "unicode", "policy", "security", "validation"],
        "selection_summary": (
            'Apply a named Unicode safety policy '
            '(identifier/filename/source/human/key/domain); use text_inspect for raw '
            'finding detail.'
        ),
        "keywords": ['unicode policy', 'identifier strict', 'filename safe'],
        "profiles": ["full", "codegg_preflight", "codegg_unicode_security"],
        "aliases": [],
        "llm_exposure": "harness_only",
        "harness_use": ["prompt_input_preflight"],
        "cost": "moderate",
        "stability": "stable",
        "composite": False,
    },
    "canonicalize_text": {
        "handler": "canonicalize_text_mcp",
        "category": "unicode",
        "tier": 2,
        "tags": ["text", "unicode", "canonicalization", "normalization", "identity"],
        "selection_summary": (
            'Canonicalize text under a named profile '
            '(identifier/file/label/key/path); use text_transform for ad-hoc '
            'operation lists.'
        ),
        "keywords": ['canonicalize', 'normalize profile', 'identifier compare'],
        "profiles": ["full", "codegg_unicode_security"],
        "aliases": [],
        "llm_exposure": "contextual",
        "harness_use": ["prompt_input_preflight"],
        "cost": "moderate",
        "stability": "stable",
        "composite": False,
    },
    "prompt_input_inspect": {
        "handler": "prompt_input_inspect_mcp",
        "category": "text",
        "tier": 2,
        "tags": ["text", "security", "inspection", "prompt", "unicode", "hidden"],
        "selection_summary": (
            'Report observable prompt-text red flags (hidden chars, ANSI, '
            'instruction-like lines); not an injection verdict — use '
            'text_security_inspect for a verdict.'
        ),
        "keywords": ['prompt inspect', 'hidden prompt', 'injection screen'],
        "profiles": ["full", "codegg_unicode_security", "codegg_preflight"],
        "aliases": [],
        "llm_exposure": "harness_only",
        "harness_use": ["prompt_input_preflight"],
        "cost": "moderate",
        "stability": "stable",
        "composite": False,
    },
    "text_hash": {
        "handler": "text_hash",
        "category": "text",
        "tier": 2,
        "tags": ["text", "hash", "identity", "security"],
        "selection_summary": (
            'Hash text (sha256/sha1/md5/crc32) for identity checks; use '
            'text_fingerprint for canonicalized fingerprints.'
        ),
        "keywords": ['hash text', 'sha256', 'checksum'],
        "profiles": ["full"],
        "aliases": [],
        "llm_exposure": "contextual",
        "harness_use": ["none"],
        "cost": "moderate",
        "stability": "stable",
        "composite": False,
    },
    "text_position": {
        "handler": "text_position",
        "category": "text",
        "tier": 2,
        "tags": ["text", "position", "offset", "unicode", "lsp"],
        "selection_summary": (
            'Convert between byte/codepoint/line-column/UTF-16 offsets; use '
            'text_window for surrounding context lines.'
        ),
        "keywords": ['offset', 'line column', 'codepoint', 'byte offset'],
        "profiles": ["full", "codegg_unicode_security"],
        "aliases": [],
        "llm_exposure": "contextual",
        "harness_use": ["none"],
        "cost": "cheap",
        "stability": "stable",
        "composite": False,
    },
    "text_transform": {
        "handler": "text_transform",
        "category": "text",
        "tier": 2,
        "tags": ["text", "unicode", "transform", "normalization", "sanitation"],
        "selection_summary": (
            'Apply normalization/casefold/trim/newline transforms to text; use '
            'canonicalize_text for a named canonicalization profile.'
        ),
        "keywords": ['normalize text', 'casefold', 'trim', 'transform text'],
        "profiles": ["full", "codegg_unicode_security"],
        "aliases": [],
        "llm_exposure": "contextual",
        "harness_use": ["none"],
        "cost": "moderate",
        "stability": "stable",
        "composite": False,
    },
    "dotenv_validate": {
        "handler": "dotenv_validate_mcp",
        "category": "config",
        "tier": 2,
        "tags": ["validation", "config", "env", "dotenv"],
        "selection_summary": (
            'Validate .env key=value text (keys, duplicates, quoting); use '
            'config_preflight for auto-detected config formats.'
        ),
        "keywords": ['dotenv', 'env file', 'validate env'],
        "profiles": ["full", "codegg_config"],
        "aliases": [],
        "llm_exposure": "contextual",
        "harness_use": ["config_preflight"],
        "cost": "cheap",
        "stability": "stable",
        "composite": False,
    },
    "ini_validate": {
        "handler": "ini_validate_mcp",
        "category": "config",
        "tier": 2,
        "tags": ["validation", "config", "ini"],
        "selection_summary": (
            'Validate INI text (sections, keys, duplicates); use config_preflight for '
            'auto-detected config formats.'
        ),
        "keywords": ['ini file', 'validate ini', 'config'],
        "profiles": ["full", "codegg_config"],
        "aliases": [],
        "llm_exposure": "contextual",
        "harness_use": ["config_preflight"],
        "cost": "cheap",
        "stability": "stable",
        "composite": False,
    },
    # ── Tier 3: Specialized / domain-specific ──────────────────────────────
    "identifier_analyze": {
        "handler": "identifier_analyze",
        "category": "identifier",
        "tier": 3,
        "tags": ["text", "identifier", "naming", "validation", "language"],
        "selection_summary": (
            "Classify one identifier's naming convention and language validity; use "
            'identifier_table_inspect for collision analysis across many names.'
        ),
        "keywords": ['identifier', 'variable name', 'naming convention'],
        "profiles": ["full"],
        "aliases": [],
        "llm_exposure": "expert_only",
        "harness_use": ["none"],
        "cost": "moderate",
        "stability": "stable",
        "composite": False,
    },
    "identifier_table_inspect": {
        "handler": "identifier_table_inspect_mcp",
        "category": "identifier",
        "tier": 3,
        "tags": ["text", "identifier", "collision", "naming", "style", "reserved", "validation"],
        "selection_summary": (
            'Analyze a table of identifiers for collisions and style drift; use '
            'identifier_inspect for one or few names.'
        ),
        "keywords": ['identifier table', 'collision analysis', 'naming audit'],
        "profiles": ["full", "codegg_repo_audit"],
        "aliases": [],
        "llm_exposure": "expert_only",
        "harness_use": ["repo_audit"],
        "cost": "moderate",
        "stability": "stable",
        "composite": False,
    },
    "json_shape": {
        "handler": "json_shape",
        "category": "json",
        "tier": 3,
        "tags": ["json", "structured-data", "shape", "schema"],
        "selection_summary": (
            'Show JSON structure (types/keys) without returning values; use '
            'json_extract to read values.'
        ),
        "keywords": ['json structure', 'json shape', 'schema of json'],
        "profiles": ["full", "codegg_repo_audit"],
        "aliases": [],
        "llm_exposure": "expert_only",
        "harness_use": ["none"],
        "cost": "moderate",
        "stability": "stable",
        "composite": False,
    },
    "text_truncate": {
        "handler": "text_truncate",
        "category": "text",
        "tier": 3,
        "tags": ["text", "truncation", "grapheme", "unicode"],
        "selection_summary": (
            'Truncate to N grapheme clusters without splitting emoji or combining '
            'marks; use line_range_extract for line-based slicing.'
        ),
        "keywords": ['truncate', 'grapheme', 'shorten text'],
        "profiles": ["full"],
        "aliases": [],
        "llm_exposure": "expert_only",
        "harness_use": ["none"],
        "cost": "cheap",
        "stability": "stable",
        "composite": False,
    },
    "version_constraint_check": {
        "handler": "version_constraint_check_mcp",
        "category": "version",
        "tier": 3,
        "tags": ["version", "semver", "cargo", "constraint", "satisfiability"],
        "selection_summary": (
            'Test a version against a semver/cargo range constraint; use '
            'version_compare for direct A-vs-B ordering.'
        ),
        "keywords": ['version range', 'constraint', 'caret', 'satisfies version'],
        "profiles": ["full"],
        "aliases": [],
        "llm_exposure": "expert_only",
        "harness_use": ["none"],
        "cost": "cheap",
        "stability": "stable",
        "composite": False,
    },
    "cargo_toml_inspect": {
        "handler": "cargo_toml_inspect_mcp",
        "category": "cargo",
        "tier": 3,
        "tags": ["rust", "cargo", "toml", "dependencies", "workspace", "inspection"],
        "selection_summary": (
            'Inspect Cargo.toml semantics (package, workspace, dependency forms); use '
            'validate_toml for syntax-only checks.'
        ),
        "keywords": ['cargo.toml', 'rust manifest', 'cargo dependencies'],
        "profiles": ["full", "codegg_core", "codegg_repo_audit"],
        "aliases": [],
        "llm_exposure": "expert_only",
        "harness_use": ["config_preflight"],
        "cost": "moderate",
        "stability": "stable",
        "composite": False,
    },
    "text_security_inspect": {
        "handler": "text_security_inspect",
        "category": "text",
        "tier": 1,
        "tags": ["text", "unicode", "security", "composite", "prompt", "inspection"],
        "selection_summary": (
            'Composite text-hygiene verdict (allow/review/block) across '
            'inspect/policy/canonicalize/prompt checks; use text_inspect for '
            'single-string detail.'
        ),
        "keywords": ['text security', 'prompt safety', 'unicode verdict'],
        "profiles": [
            "full",
            "codegg_core",
            "codegg_core_min",
            "codegg_preflight",
            "codegg_unicode_security",
            "agent_core",
        ],
        "aliases": [],
        "llm_exposure": "default",
        "harness_use": ["prompt_input_preflight"],
        "cost": "heavy",
        "stability": "stable",
        "composite": True,
    },
    "edit_preflight": {
        "handler": "edit_preflight",
        "category": "patch",
        "tier": 1,
        "tags": ["patch", "edit", "preflight", "composite", "text"],
        "selection_summary": (
            'Composite edit verdict (ok_to_apply) for a proposed text or patch edit; '
            'use text_replace_check for one replacement or patch_apply_check for '
            'dry-run apply.'
        ),
        "keywords": [
            'edit check',
            'safe to edit',
            'preflight edit',
            'apply patch safely',
        ],
        "profiles": [
            "full",
            "codegg_core",
            "codegg_core_min",
            "codegg_preflight",
            "codegg_patch",
            "agent_core",
        ],
        "aliases": [],
        "llm_exposure": "default",
        "harness_use": ["edit_preflight"],
        "cost": "heavy",
        "stability": "stable",
        "composite": True,
    },
    "command_preflight": {
        "handler": "command_preflight",
        "category": "shell",
        "tier": 1,
        "tags": ["shell", "command", "preflight", "composite", "security"],
        "selection_summary": (
            'Composite command verdict before approval/execution (argv, operators, '
            'regex risk); use shell_split for raw token parsing.'
        ),
        "keywords": [
            'command check',
            'safe command',
            'preflight command',
            'approve shell',
            'safe to run',
        ],
        "profiles": [
            "full",
            "codegg_core",
            "codegg_core_min",
            "codegg_preflight",
            "codegg_shell",
            "agent_core",
        ],
        "aliases": [],
        "llm_exposure": "default",
        "harness_use": ["command_preflight"],
        "cost": "heavy",
        "stability": "stable",
        "composite": True,
    },
    "config_preflight": {
        "handler": "config_preflight",
        "category": "config",
        "tier": 1,
        "tags": ["config", "validation", "json", "toml", "preflight", "composite"],
        "selection_summary": (
            'Composite config verdict with auto-detected format; use '
            'validate_json/validate_toml/dotenv_validate/ini_validate for a known '
            'format.'
        ),
        "keywords": ['config check', 'validate config', 'preflight config'],
        "profiles": [
            "full",
            "codegg_core",
            "codegg_core_min",
            "codegg_preflight",
            "codegg_config",
            "agent_core",
        ],
        "aliases": [],
        "llm_exposure": "default",
        "harness_use": ["config_preflight"],
        "cost": "heavy",
        "stability": "stable",
        "composite": True,
    },
    "structured_data_compare": {
        "handler": "structured_data_compare",
        "category": "json",
        "tier": 2,
        "tags": ["json", "comparison", "config", "structured-data", "composite"],
        "selection_summary": (
            'Composite verdict comparing structured data via '
            'compare/canonicalize/shape; use json_compare for a single pairwise diff.'
        ),
        "keywords": ['compare config', 'structured diff', 'data compare'],
        "profiles": ["full", "codegg_core", "codegg_config"],
        "aliases": [],
        "llm_exposure": "contextual",
        "harness_use": ["config_preflight"],
        "cost": "heavy",
        "stability": "stable",
        "composite": True,
    },
    # ── Manifest / package inspection tools ─────────────────────────────────
    "pyproject_inspect": {
        "handler": "pyproject_inspect_mcp",
        "category": "manifest",
        "tier": 2,
        "tags": ["python", "pyproject", "toml", "manifest", "dependencies", "inspection"],
        "selection_summary": (
            'Inspect pyproject.toml semantics (project, backend, deps, scripts); use '
            'validate_toml for syntax-only checks.'
        ),
        "keywords": ['pyproject.toml', 'python manifest', 'project dependencies'],
        "profiles": ["full", "codegg_core", "codegg_repo_audit", "codegg_config"],
        "aliases": [],
        "llm_exposure": "contextual",
        "harness_use": ["config_preflight"],
        "cost": "cheap",
        "stability": "stable",
        "composite": False,
    },
    "package_json_inspect": {
        "handler": "package_json_inspect_mcp",
        "category": "manifest",
        "tier": 2,
        "tags": ["node", "npm", "package.json", "manifest", "dependencies", "inspection"],
        "selection_summary": (
            'Inspect package.json semantics (scripts, deps, engines, workspaces); use '
            'validate_json for syntax-only checks.'
        ),
        "keywords": ['package.json', 'npm manifest', 'node dependencies'],
        "profiles": ["full", "codegg_core", "codegg_repo_audit", "codegg_config"],
        "aliases": [],
        "llm_exposure": "contextual",
        "harness_use": ["config_preflight"],
        "cost": "cheap",
        "stability": "stable",
        "composite": False,
    },
    "requirements_inspect": {
        "handler": "requirements_inspect_mcp",
        "category": "manifest",
        "tier": 2,
        "tags": ["python", "requirements", "pip", "dependencies", "inspection"],
        "selection_summary": (
            'Inspect requirements.txt lines (specs, URLs, markers); use manifest '
            'inspectors for other ecosystems.'
        ),
        "keywords": ['requirements.txt', 'pip dependencies', 'python requirements'],
        "profiles": ["full", "codegg_core", "codegg_repo_audit", "codegg_config"],
        "aliases": [],
        "llm_exposure": "contextual",
        "harness_use": ["config_preflight"],
        "cost": "cheap",
        "stability": "stable",
        "composite": False,
    },
    "go_mod_inspect": {
        "handler": "go_mod_inspect_mcp",
        "category": "manifest",
        "tier": 2,
        "tags": ["go", "golang", "go.mod", "manifest", "dependencies", "inspection"],
        "selection_summary": (
            'Inspect go.mod semantics (module, go version, requires); use '
            'lockfile_summary for lockfile-level overview.'
        ),
        "keywords": ['go.mod', 'go dependencies', 'golang manifest'],
        "profiles": ["full", "codegg_core", "codegg_repo_audit", "codegg_config"],
        "aliases": [],
        "llm_exposure": "contextual",
        "harness_use": ["config_preflight"],
        "cost": "cheap",
        "stability": "stable",
        "composite": False,
    },
    "lockfile_summary": {
        "handler": "lockfile_summary_mcp",
        "category": "manifest",
        "tier": 2,
        "tags": ["lockfile", "dependencies", "package-manager", "inspection"],
        "selection_summary": (
            'Identify lockfile kind and approximate package counts (shallow); use '
            'manifest inspectors for per-file semantics.'
        ),
        "keywords": ['lockfile', 'package lock', 'dependency count'],
        "profiles": ["full", "codegg_core", "codegg_repo_audit", "codegg_config"],
        "aliases": [],
        "llm_exposure": "contextual",
        "harness_use": ["config_preflight"],
        "cost": "cheap",
        "stability": "stable",
        "composite": False,
    },
    # ── LLM output hygiene tools ──────────────────────────────────────────
    "llm_json_output_check": {
        "handler": "llm_json_output_check_mcp",
        "category": "text",
        "tier": 2,
        "tags": ["text", "json", "llm", "hygiene", "validation", "preflight"],
        "selection_summary": (
            'Diagnose LLM JSON output failures (fences, prose, trailing commas); use '
            'validate_json for plain syntax checks.'
        ),
        "keywords": ['llm json', 'json fix', 'fenced json', 'json repair hints'],
        "profiles": ["full", "default", "codegg_preflight", "codegg_core"],
        "aliases": [],
        "llm_exposure": "default",
        "harness_use": ["config_preflight"],
        "cost": "cheap",
        "stability": "stable",
        "composite": False,
    },
    # ── Markdown link check tools ─────────────────────────────────────────
    "markdown_link_check_lexical": {
        "handler": "markdown_link_check_lexical_mcp",
        "category": "text",
        "tier": 2,
        "tags": ["text", "markdown", "links", "validation", "hygiene"],
        "selection_summary": (
            'Lexically validate markdown links (no network); use markdown_structure '
            'for full document structure.'
        ),
        "keywords": ['markdown links', 'broken links', 'link check'],
        "profiles": ["full", "codegg_core", "codegg_repo_audit"],
        "aliases": [],
        "llm_exposure": "contextual",
        "harness_use": ["none"],
        "cost": "cheap",
        "stability": "stable",
        "composite": False,
    },
    # ── Repo audit tools ──────────────────────────────────────────────────
    "repo_file_inventory": {
        "handler": "repo_file_inventory_mcp",
        "category": "repo",
        "tier": 2,
        "tags": ["repo", "audit", "inventory", "filesystem", "structure"],
        "selection_summary": (
            'Summarize repo file signals (languages, config/vendor/generated, '
            'suspicious paths); use manifest inspectors for file semantics.'
        ),
        "keywords": ['repo audit', 'file inventory', 'repo structure'],
        "profiles": ["full", "codegg_repo_audit"],
        "aliases": [],
        "llm_exposure": "contextual",
        "harness_use": ["repo_audit"],
        "cost": "moderate",
        "stability": "stable",
        "composite": False,
    },
    # ── Network / encoding / temporal utilities (full-only contextual) ────
    "ip_inspect": {
        "handler": "ip_inspect_mcp",
        "category": "network",
        "tier": 2,
        "tags": ["network", "ip", "inspection", "address"],
        "selection_summary": (
            'Inspect one IP address (family, bytes, numeric, special-use); use '
            'cidr_inspect for ranges.'
        ),
        "keywords": ['ip address', 'ipv4', 'ipv6', 'inspect ip'],
        "profiles": ["full"],
        "aliases": [],
        "llm_exposure": "contextual",
        "harness_use": ["none"],
        "cost": "cheap",
        "stability": "stable",
        "composite": False,
    },
    "cidr_inspect": {
        "handler": "cidr_inspect_mcp",
        "category": "network",
        "tier": 2,
        "tags": ["network", "ip", "cidr", "inspection", "range"],
        "selection_summary": (
            'Inspect a CIDR range (network, bounds, address count, containment); use '
            'ip_inspect for single addresses.'
        ),
        "keywords": ['cidr', 'subnet', 'network range', 'prefix'],
        "profiles": ["full"],
        "aliases": [],
        "llm_exposure": "contextual",
        "harness_use": ["none"],
        "cost": "cheap",
        "stability": "stable",
        "composite": False,
    },
    "codec_convert": {
        "handler": "codec_convert_mcp",
        "category": "encoding",
        "tier": 2,
        "tags": ["encoding", "codec", "conversion", "base64", "hex"],
        "selection_summary": (
            'Convert text between utf8/hex/base64/base64url; use radix_convert for '
            'integer base conversion.'
        ),
        "keywords": ['base64', 'hex encode', 'codec', 'decode base64'],
        "profiles": ["full"],
        "aliases": [],
        "llm_exposure": "contextual",
        "harness_use": ["none"],
        "cost": "cheap",
        "stability": "stable",
        "composite": False,
    },
    "radix_convert": {
        "handler": "radix_convert_mcp",
        "category": "encoding",
        "tier": 2,
        "tags": ["encoding", "radix", "conversion", "base", "integer"],
        "selection_summary": (
            'Convert an integer between bases 2-36 (capped at 2**128-1); use '
            'codec_convert for text codecs.'
        ),
        "keywords": ['base convert', 'hex to decimal', 'radix', 'binary'],
        "profiles": ["full"],
        "aliases": [],
        "llm_exposure": "contextual",
        "harness_use": ["none"],
        "cost": "cheap",
        "stability": "stable",
        "composite": False,
    },
    "datetime_convert": {
        "handler": "datetime_convert_mcp",
        "category": "temporal",
        "tier": 2,
        "tags": ["temporal", "datetime", "conversion", "timestamp", "rfc3339"],
        "selection_summary": (
            'Convert between RFC3339 and Unix seconds/millis/nanos (fixed offsets '
            'only); use cron_inspect for schedules.'
        ),
        "keywords": ['timestamp', 'unix time', 'rfc3339', 'datetime convert'],
        "profiles": ["full"],
        "aliases": [],
        "llm_exposure": "contextual",
        "harness_use": ["none"],
        "cost": "cheap",
        "stability": "stable",
        "composite": False,
    },
    "cron_inspect": {
        "handler": "cron_inspect_mcp",
        "category": "temporal",
        "tier": 2,
        "tags": ["temporal", "cron", "inspection", "schedule"],
        "selection_summary": (
            'Inspect a cron expression and list upcoming runs; use datetime_convert '
            'for timestamp conversion.'
        ),
        "keywords": ['cron', 'schedule', 'next run'],
        "profiles": ["full"],
        "aliases": [],
        "llm_exposure": "contextual",
        "harness_use": ["none"],
        "cost": "moderate",
        "stability": "stable",
        "composite": False,
    },
}


_VALID_CATEGORIES = frozenset(
    {
        "math",
        "text",
        "json",
        "toml",
        "config",
        "regex",
        "path",
        "shell",
        "patch",
        "identifier",
        "markdown",
        "version",
        "cargo",
        "list",
        "validation",
        "unicode",
        "manifest",
        "repo",
        "network",
        "encoding",
        "temporal",
    }
)
_VALID_TIERS = frozenset({0, 1, 2, 3})
_VALID_LLM_EXPOSURE = frozenset({"default", "contextual", "expert_only", "harness_only", "hidden"})
_VALID_COST = frozenset({"cheap", "moderate", "heavy"})
_VALID_STABILITY = frozenset({"stable", "experimental", "deprecated"})

#: Bound for authored `selection_summary` text (Plan 041 Workstream C).
SELECTION_SUMMARY_MAX_LENGTH = 240
#: Bound for authored `keywords` list length (Plan 041 Workstream C).
SELECTION_KEYWORDS_MAX_COUNT = 8
#: Bound for each authored keyword (Plan 041 Workstream C).
SELECTION_KEYWORD_MAX_LENGTH = 48


def _validate_catalog_metadata() -> None:
    """Fail fast on malformed catalog metadata (Plan 040 Workstream F).

    Checks handler locators are non-empty valid Python identifiers,
    tags are string lists, and tier/category/exposure/cost/stability
    come from bounded vocabularies. Called once at import time so bad
    catalog bindings fail deterministically, not on first agent call.
    """
    for name, meta in TOOL_METADATA.items():
        handler = meta.get("handler")
        if not isinstance(handler, str) or not handler:
            raise ValueError(f"Tool {name!r} has missing/empty handler locator")
        if not handler.isidentifier():
            raise ValueError(
                f"Tool {name!r} has invalid handler locator {handler!r}: "
                "must be a Python attribute identifier in eggcalc.mcp.tools"
            )
        tags = meta.get("tags")
        if not isinstance(tags, (list, tuple)) or not all(isinstance(t, str) for t in tags):
            raise ValueError(f"Tool {name!r} has invalid tags: must be list[str]")
        summary = meta.get("selection_summary")
        if not isinstance(summary, str) or not summary:
            raise ValueError(f"Tool {name!r} has missing/empty selection_summary")
        if len(summary) > SELECTION_SUMMARY_MAX_LENGTH:
            raise ValueError(
                f"Tool {name!r} selection_summary exceeds "
                f"{SELECTION_SUMMARY_MAX_LENGTH} chars ({len(summary)})"
            )
        keywords = meta.get("keywords")
        if not isinstance(keywords, (list, tuple)) or not all(isinstance(k, str) for k in keywords):
            raise ValueError(f"Tool {name!r} has invalid keywords: must be list[str]")
        if len(keywords) > SELECTION_KEYWORDS_MAX_COUNT:
            raise ValueError(
                f"Tool {name!r} has too many keywords ({len(keywords)} > "
                f"{SELECTION_KEYWORDS_MAX_COUNT})"
            )
        for keyword in keywords:
            if not keyword or len(keyword) > SELECTION_KEYWORD_MAX_LENGTH:
                raise ValueError(
                    f"Tool {name!r} has invalid keyword {keyword!r}: must be "
                    f"1..{SELECTION_KEYWORD_MAX_LENGTH} chars"
                )
        if meta.get("tier") not in _VALID_TIERS:
            raise ValueError(f"Tool {name!r} has invalid tier {meta.get('tier')!r}")
        if meta.get("category") not in _VALID_CATEGORIES:
            raise ValueError(f"Tool {name!r} has invalid category {meta.get('category')!r}")
        if meta.get("llm_exposure") not in _VALID_LLM_EXPOSURE:
            raise ValueError(f"Tool {name!r} has invalid llm_exposure {meta.get('llm_exposure')!r}")
        if meta.get("cost") not in _VALID_COST:
            raise ValueError(f"Tool {name!r} has invalid cost {meta.get('cost')!r}")
        if meta.get("stability") not in _VALID_STABILITY:
            raise ValueError(f"Tool {name!r} has invalid stability {meta.get('stability')!r}")
        if not isinstance(meta.get("profiles"), list):
            raise ValueError(f"Tool {name!r} has invalid profiles: must be list")
        if not isinstance(meta.get("aliases"), list):
            raise ValueError(f"Tool {name!r} has invalid aliases: must be list")
        if not isinstance(meta.get("harness_use"), list):
            raise ValueError(f"Tool {name!r} has invalid harness_use: must be list")
        if not isinstance(meta.get("composite"), bool):
            raise ValueError(f"Tool {name!r} has invalid composite: must be bool")


_validate_catalog_metadata()


def get_tool_tier(name: str) -> int:
    """Return the catalog tier for *name* (sole authored authority: TOOL_METADATA).

    Compatibility accessor so callers never read tier from TOOL_SCHEMAS,
    which owns only protocol shape since Plan 040.
    """
    return int(TOOL_METADATA[name]["tier"])


def get_tool_tags(name: str) -> list[str]:
    """Return a copy of the catalog tags for *name* (authority: TOOL_METADATA)."""
    return list(TOOL_METADATA[name].get("tags", []))


def get_tool_handler_name(name: str) -> str:
    """Return the handler locator for *name* (attribute in eggcalc.mcp.tools)."""
    return str(TOOL_METADATA[name]["handler"])


def get_tool_selection_summary(name: str) -> str:
    """Return the authored selection summary for *name* (authority: TOOL_METADATA).

    The summary answers "when should an agent choose this tool rather than a
    neighboring tool?" It backs compact descriptions and lexical discovery.
    """
    return str(TOOL_METADATA[name]["selection_summary"])


def get_tool_keywords(name: str) -> list[str]:
    """Return a copy of the authored discovery keywords for *name*."""
    return list(TOOL_METADATA[name].get("keywords", []))


# ---------------------------------------------------------------------------
# Profile definitions.  A profile is a named set of tool names computed
# from TOOL_METADATA.  Each entry maps a profile name to the sorted
# list of tool names that include that profile in their metadata.
# ---------------------------------------------------------------------------


def _build_profiles() -> dict[str, list[str]]:
    """Build profile → tool list from TOOL_METADATA."""
    profiles: dict[str, list[str]] = {}
    for tool_name, meta in TOOL_METADATA.items():
        for profile in meta.get("profiles", []):
            profiles.setdefault(profile, []).append(tool_name)
    for tool_list in profiles.values():
        tool_list.sort()
    return profiles


TOOL_PROFILES: dict[str, list[str]] = _build_profiles()

# Canonical profile names in recommended order.
PROFILE_NAMES: list[str] = [
    "full",
    "default",
    "codegg_core_min",
    "codegg_core",
    "codegg_preflight",
    "codegg_patch",
    "codegg_config",
    "codegg_unicode_security",
    "codegg_shell",
    "codegg_repo_audit",
    "human_math",
    "agent_core",
]

# Schema detail levels
SCHEMA_DETAIL_FULL = "full"
SCHEMA_DETAIL_NORMAL = "normal"
SCHEMA_DETAIL_COMPACT = "compact"


def compact_schema(schema: dict[str, Any], selection_summary: str | None = None) -> dict[str, Any]:
    """Produce a compact version of a tool schema.

    Compact mode preserves:
    - Tool name, description, required args, types, enums
    - Input/output schema structure
    - Output property keys and types (top-level only) for composite tools

    The compact description is the authored ``selection_summary`` when
    provided (Plan 041: selection signal, not truncation); otherwise the
    full description is truncated to 120 chars as a fallback.

    Compact mode removes:
    - Long description text, examples, verbose help
    - Default values (they're handled by Python kwargs)
    - Catalog selection metadata (tier/tags live in TOOL_METADATA,
      surfaced by tools/list from the registry, not from this schema)
    - Nested output schema detail
    """
    result: dict[str, Any] = {}

    # Description: authored selection signal when available, else truncate.
    if selection_summary:
        desc = selection_summary
    else:
        desc = schema.get("description", "")
        if len(desc) > 120:
            desc = desc[:117] + "..."
    result["description"] = desc

    # Deprecated flag
    if schema.get("deprecated"):
        result["deprecated"] = True

    # Compact input schema: keep types, required, enums; drop defaults and descriptions
    input_schema = schema.get("inputSchema", {})
    compact_input = _compact_input_schema(input_schema)
    result["inputSchema"] = compact_input

    # Output schema: preserve top-level property keys and types
    output_schema = schema.get("outputSchema", {})
    result["outputSchema"] = _compact_output_schema(output_schema)

    return result


def normal_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Produce a normal-detail version of a tool schema.

    Normal mode preserves:
    - Tool name, description (truncated to 240 chars)
    - Required args, types, enums, constraints (minLength, maxLength, minimum, etc.)
    - Input property descriptions (truncated to 120 chars)
    - Output schema structure (top-level property keys, types, descriptions)
    - Deprecated flag (protocol field; tier/tags are catalog metadata
      in TOOL_METADATA and are added by tools/list, not here)

    Normal mode removes:
    - Verbose examples and long help text
    - Default values (handled by Python kwargs)
    - Nested output schema detail beyond top-level
    """
    result: dict[str, Any] = {}

    # Description: truncate to 240 chars
    desc = schema.get("description", "")
    if len(desc) > 240:
        desc = desc[:237] + "..."
    result["description"] = desc

    # Deprecated flag
    if schema.get("deprecated"):
        result["deprecated"] = True

    # Input schema: keep types, required, enums, constraints, descriptions
    input_schema = schema.get("inputSchema", {})
    result["inputSchema"] = _normal_input_schema(input_schema)

    # Output schema: keep top-level property keys, types, and descriptions
    output_schema = schema.get("outputSchema", {})
    result["outputSchema"] = _normal_output_schema(output_schema)

    return result


def _compact_output_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Compact an output schema by keeping top-level property keys/types only."""
    if not isinstance(schema, (dict, Mapping)):
        return {"type": "object"}

    result: dict[str, Any] = {"type": schema.get("type", "object")}

    props = schema.get("properties", {})
    if props:
        compact_props: dict[str, Any] = {}
        for prop_name, prop_def in props.items():
            if isinstance(prop_def, (dict, Mapping)):
                cp: dict[str, Any] = {}
                if "type" in prop_def:
                    cp["type"] = prop_def["type"]
                if "enum" in prop_def:
                    cp["enum"] = list(prop_def["enum"])
                compact_props[prop_name] = cp
            else:
                compact_props[prop_name] = {}
        result["properties"] = compact_props

    return result


def _compact_input_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Compact an input schema by stripping defaults and long descriptions."""
    if not isinstance(schema, (dict, Mapping)):
        return schema

    compact: dict[str, Any] = {}
    compact["type"] = schema.get("type", "object")

    props = schema.get("properties", {})
    compact_props: dict[str, Any] = {}
    for prop_name, prop_def in props.items():
        if not isinstance(prop_def, (dict, Mapping)):
            compact_props[prop_name] = prop_def
            continue
        cp: dict[str, Any] = {}
        # Keep type
        if "type" in prop_def:
            cp["type"] = prop_def["type"]
        # Keep enum
        if "enum" in prop_def:
            cp["enum"] = list(prop_def["enum"])
        # Keep required sub-fields
        if "required" in prop_def:
            cp["required"] = list(prop_def["required"])
        # Keep items for arrays
        if "items" in prop_def:
            cp["items"] = prop_def["items"]
        # Keep constraints
        for key in (
            "minimum",
            "maximum",
            "exclusiveMinimum",
            "exclusiveMaximum",
            "minLength",
            "maxLength",
            "pattern",
            "minItems",
            "maxItems",
            "multipleOf",
        ):
            if key in prop_def:
                cp[key] = prop_def[key]
        # Truncated description
        desc = prop_def.get("description", "")
        if desc:
            if len(desc) > 80:
                desc = desc[:77] + "..."
            cp["description"] = desc
        compact_props[prop_name] = cp

    compact["properties"] = compact_props

    # Keep required at top level
    if "required" in schema:
        compact["required"] = schema["required"]

    return compact


def _normal_input_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Normal-detail input schema: keep types, required, enums, constraints, descriptions."""
    if not isinstance(schema, (dict, Mapping)):
        return schema

    result: dict[str, Any] = {}
    result["type"] = schema.get("type", "object")

    props = schema.get("properties", {})
    normal_props: dict[str, Any] = {}
    for prop_name, prop_def in props.items():
        if not isinstance(prop_def, (dict, Mapping)):
            normal_props[prop_name] = prop_def
            continue
        np: dict[str, Any] = {}
        # Keep type
        if "type" in prop_def:
            np["type"] = prop_def["type"]
        # Keep enum
        if "enum" in prop_def:
            np["enum"] = list(prop_def["enum"])
        # Keep required sub-fields
        if "required" in prop_def:
            np["required"] = list(prop_def["required"])
        # Keep items for arrays
        if "items" in prop_def:
            np["items"] = prop_def["items"]
        # Keep all constraints
        for key in (
            "minimum",
            "maximum",
            "exclusiveMinimum",
            "exclusiveMaximum",
            "minLength",
            "maxLength",
            "pattern",
            "minItems",
            "maxItems",
            "multipleOf",
        ):
            if key in prop_def:
                np[key] = prop_def[key]
        # Truncated description (120 chars — longer than compact's 80)
        desc = prop_def.get("description", "")
        if desc:
            if len(desc) > 120:
                desc = desc[:117] + "..."
            np["description"] = desc
        normal_props[prop_name] = np

    result["properties"] = normal_props

    # Keep required at top level
    if "required" in schema:
        result["required"] = schema["required"]

    return result


def _normal_output_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Normal-detail output schema: keep top-level property keys, types, and descriptions."""
    if not isinstance(schema, (dict, Mapping)):
        return {"type": "object"}

    result: dict[str, Any] = {"type": schema.get("type", "object")}

    props = schema.get("properties", {})
    if props:
        normal_props: dict[str, Any] = {}
        for prop_name, prop_def in props.items():
            if isinstance(prop_def, (dict, Mapping)):
                np: dict[str, Any] = {}
                if "type" in prop_def:
                    np["type"] = prop_def["type"]
                if "enum" in prop_def:
                    np["enum"] = list(prop_def["enum"])
                # Include descriptions for output fields (truncated to 100 chars)
                desc = prop_def.get("description", "")
                if desc:
                    if len(desc) > 100:
                        desc = desc[:97] + "..."
                    np["description"] = desc
                normal_props[prop_name] = np
            else:
                normal_props[prop_name] = {}
        result["properties"] = normal_props

    return result
