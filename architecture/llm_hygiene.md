# llm_hygiene.py — LLM JSON Output Hygiene

326 lines. Detects common JSON output issues from LLMs.

## Overview

Detects and diagnoses: markdown fenced code blocks wrapping JSON, leading/trailing prose, JSON parse errors with location info, common JSON issues (trailing commas, single quotes, unquoted keys, comments, BOM), and multiple concatenated JSON objects.

## Key Exports

```python
from eggcalc.exact.llm_hygiene import llm_json_output_check
```

## Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `llm_json_output_check(text)` | `LlmJsonCheckResult` | Detects and diagnoses common LLM JSON output issues |

## Diagnostics Detected

| Diagnostic | Description |
|------------|-------------|
| `has_fence` | Markdown code fence wrapping |
| `leading_prose` | Text before JSON |
| `trailing_prose` | Text after JSON |
| `parse_ok` | Whether JSON parses successfully |
| `fix_hints` | Suggestions for fixing parse errors |
| `multiple_json_objects` | Multiple concatenated JSON objects |
| `has_bom` | Byte order mark present |

## Module Dependencies

- `json`, `re`, `typing`
