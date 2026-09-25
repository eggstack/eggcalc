# llm_hygiene.py — LLM JSON Output Hygiene

326 lines. Diagnosis of common JSON output defects from LLMs.

## Table of Contents

- [Overview](#overview)
- [Type Definitions](#type-definitions)
- [Constants / Limits](#constants--limits)
- [Public Functions](#public-functions)
  - [llm_json_output_check](#llm_json_output_check)
- [Internal Helpers](#internal-helpers)
- [Dependencies](#dependencies)
- [Security Notes](#security-notes)
- [See Also](#see-also)

## Overview

Single diagnostic entry point for the most common ways LLM-generated
"JSON" is not JSON: markdown fence wrapping, leading/trailing prose,
`json.JSONDecodeError` with 1-based line/column, trailing commas, single
quotes, unquoted keys, `//` and `/* */` comments, BOM prefix, and
multiple concatenated objects. Never repairs — reports `fix_hints` and
the `extracted_content` the diagnosis was performed on.

## Type Definitions

```python
class JsonFixHint(TypedDict, total=False):
    code: str      # "TRAILING_COMMA" | "SINGLE_QUOTES" | "UNQUOTED_KEY" | "JSON_COMMENT" | ...
    message: str
    line: int      # 1-based
    column: int    # 1-based

class LlmJsonCheckResult(TypedDict, total=False):
    has_fence: bool
    fence_language: str        # "" when no fence, e.g. "json"
    leading_prose: bool
    trailing_prose: bool
    parse_ok: bool
    error_line: int | None
    error_col: int | None
    error_message: str | None
    fix_hints: list[JsonFixHint]
    extracted_content: str | None  # JSON candidate after fence/prose stripping
    multiple_json_objects: bool
    has_bom: bool
    original_length: int
    extracted_length: int
```

## Constants / Limits

```python
_MAX_INPUT_length = 500_000   # over-limit → parse_ok=False, no raise
_BOM_PREFIX = "\ufeff"

_FENCE_RE           # ^```(\w*)\s*$            (MULTILINE)
_FENCE_BLOCK_RE     # ^```(\w*)\s*\n(.*?)\n\s*```\s*$  (MULTILINE|DOTALL)
_SINGLE_QUOTE_RE    # (?<![\\])'
_UNQUOTED_KEY_RE    # (?<={|,)\s*(\w+)\s*:
_TRAILING_COMMA_RE  # ,\s*([\]}])
_COMMENT_RE         # (?<!:)//[^\n]*|/\*.*?\*/  (DOTALL; excludes `://`)
_MULTIPLE_JSON_RE   # (?:\}\s*\{|\]\s*\[|\}\s*\[|\]\s*\{)
```

## Public Functions

### `llm_json_output_check`

```python
def llm_json_output_check(text: str) -> LlmJsonCheckResult
```

Pure diagnosis: strips one fence pair and surrounding prose/BOM, then
`json.loads` the candidate. Over-limit input returns `parse_ok=False`
with `"Input exceeds 500000 character limit"` instead of raising.

```python
llm_json_output_check('{"a": 1}')["parse_ok"]  # → True

llm_json_output_check('```json\n{"a": 1}\n```')
# → {"has_fence": True, "fence_language": "json",
#     "parse_ok": True, "extracted_content": '{"a": 1}', ...}

llm_json_output_check('Here is your JSON: {"a": 1} hope you like it')
# → {"leading_prose": True, "trailing_prose": False,
#     "parse_ok": True, "extracted_content": '{"a": 1}'}

llm_json_output_check('{"a": 1,}')["fix_hints"]
# → [{"code": "TRAILING_COMMA",
#      "message": "Trailing comma detected. Remove comma before closing bracket.",
#      "line": 1, "column": 8}]

llm_json_output_check("{'a': 1}")["fix_hints"][0]["code"]  # → "SINGLE_QUOTES"
llm_json_output_check("{a: 1}")["fix_hints"][0]["code"]    # → "UNQUOTED_KEY"
llm_json_output_check('{"a": 1} {"b": 2}')["multiple_json_objects"]  # → True
llm_json_output_check('\ufeff{"a": 1}')["has_bom"]  # → True (still parses)
```

## Internal Helpers

| Helper | Role |
|--------|------|
| `_count_line_col(text, pos)` | Offset → 1-based `(line, col)` for error/hint locations |
| `_detect_fence(text)` | `(has_fence, language, inner)` via `_FENCE_BLOCK_RE` |
| `_detect_prose(text)` | `(leading, trailing)` — non-JSON text around the candidate |
| `_extract_json_from_prose(text)` | First `{...}`/`[...]` candidate extraction |
| `_detect_bom(text)` | `(has_bom, stripped)` |
| `_detect_multiple_objects(content)` | `_MULTIPLE_JSON_RE` scan for concatenated values |
| `_detect_fix_hints(content, error_msg)` | Regex triage → `TRAILING_COMMA` / `SINGLE_QUOTES` / `UNQUOTED_KEY` / `JSON_COMMENT` hints |

## Dependencies

```
llm_hygiene.py
    └── (standard library only: json, re, typing)
```

No `exact/` imports — fully standalone leaf.

## Security Notes

- Diagnosis only: `extracted_content` is the *suspect* candidate, not a
  sanitized value. Parse it again with your own `json.loads` and schema
  validation before use.
- Comment detection excludes `://` (avoids flagging URLs), but the
  fence/prose regexes are heuristic — crafted inputs can mislabel which
  span is "prose" vs "JSON". Treat spans as advisory.
- 500,000-char cap bounds `json.loads` worst-case cost; larger model
  outputs must be chunked by the caller.

## See Also

- [validate.md](validate.md) — strict JSON/TOML/regex validation (`json_extract` owns RFC 6901)
- [markdown.md](markdown.md) — fence extraction with fingerprints (structure, not diagnosis)
- [inspect_prompt.md](inspect_prompt.md) — red-flag scanning for untrusted *input* text
