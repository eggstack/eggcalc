# identifier.py — Identifier Analysis

311 lines. Naming convention analysis for identifiers across Python, Rust, JavaScript, and environment variables.

## Table of Contents

- [Overview](#overview)
- [Type Definitions](#type-definitions)
- [Constants / Limits](#constants--limits)
- [Public Functions](#public-functions)
  - [identifier_analyze](#identifier_analyze)
- [Internal Helpers](#internal-helpers)
- [Dependencies](#dependencies)
- [Security / DoS Notes](#security--dos-notes)
- [See Also](#see-also)
- [Usage Example](#usage-example)

## Overview

Deterministic, pure, no I/O. Classifies a single identifier string into one naming
convention and validates it against up to four language surfaces (Python, Rust,
JavaScript, env). Always returns all five conversion suggestions and a warning list,
regardless of validity.

Classification vocabulary (exact strings): `"snake_case"`, `"camelCase"`,
`"PascalCase"`, `"kebab-case"`, `"SCREAMING_SNAKE_CASE"`, `"mixed"` (a valid
`str.isidentifier()` matching none of the above), `"invalid"` (not an identifier at all).

Results are plain-dict TypedDicts — use `result["classification"]`, never `result.classification`.

## Type Definitions

### IdentifierAnalyzeResult (TypedDict)

Verified against `eggcalc/exact/identifier.py:15-25`:

```python
class IdentifierAnalyzeResult(TypedDict):
    text: str                    # echo of the input
    classification: str          # one of the 7 strings above
    python_valid: bool           # text.isidentifier() (False when "python" not in languages)
    python_keyword: bool         # keyword.iskeyword(text) — only when python_valid, else False
    rust_valid: bool | None      # None when "rust" not requested; else isidentifier() and not a Rust keyword
    javascript_valid: bool | None  # None when "javascript" not requested; else text.isidentifier()
    env_valid: bool              # full match against _ENV_PATTERN (False when "env" not requested)
    suggestions: dict[str, str]  # keys: snake_case, kebab_case, pascal_case, camel_case, screaming_snake_case
    warnings: list[str]          # keyword / invalid-Rust / mixed-style / leading-underscore warnings
    summary: str                 # "Style: X. Valid in: ..." or "Invalid identifier[...]"
```

Note the asymmetry the stub omitted: `python_valid` is `bool` (never `None`), while
`rust_valid` / `javascript_valid` are `bool | None` (`None` = language not requested).
`javascript_valid` does **not** check keywords — any `isidentifier()` passes (so `"for"`
is `javascript_valid=True`). `python_valid` is `True` even for keywords
(`"for"` → `python_valid=True, python_keyword=True`); validity-with-usability is
expressed via the summary (`"Valid in: ..."` excludes keyword-blocked Python).

## Constants / Limits

No `MAX_*` cap — input is a single short string (unbounded by code; see Security notes).

```python
_RUST_KEYWORDS: frozenset[str]  # 38 entries: as, async, await, break, const, continue, crate, dyn,
                                # else, enum, extern, false, fn, for, if, impl, in, let, loop, match,
                                # mod, move, mut, pub, ref, return, self, Self, static, struct, super,
                                # trait, true, type, unsafe, use, where, while
_ENV_PATTERN = re.compile(r"^[A-Z_][A-Z0-9_]*$")  # classic env-var shape; no lowercase allowed
```

## Public Functions

### `identifier_analyze`

```python
def identifier_analyze(text: str, languages: list[str] | None = None) -> IdentifierAnalyzeResult
```

Defaults to `["python", "rust", "javascript", "env"]`. Any subset may be requested;
unrequested languages report `False` (`python_valid`, `env_valid`) or `None`
(`rust_valid`, `javascript_valid`), and their warnings are skipped.

Verified examples (via `.venv/bin/python`):

```python
identifier_analyze("my_var")["classification"]       # → 'snake_case'
identifier_analyze("myVar")["classification"]        # → 'camelCase'
identifier_analyze("MyClass")["classification"]      # → 'PascalCase'
identifier_analyze("MY_CONST")["classification"]     # → 'SCREAMING_SNAKE_CASE'
identifier_analyze("my-var")["classification"]       # → 'kebab-case'
identifier_analyze("for")["classification"]          # → 'mixed' (isidentifier, matches no style)
identifier_analyze("bad name")["classification"]     # → 'invalid'
identifier_analyze("for")["python_valid"]            # → True  (isidentifier passes)
identifier_analyze("for")["python_keyword"]          # → True
identifier_analyze("for")["rust_valid"]              # → False (+ "Rust keyword ..." warning)
identifier_analyze("for")["javascript_valid"]        # → True  (no keyword check!)
identifier_analyze("MY_CONST")["env_valid"]          # → True
identifier_analyze("my_var")["env_valid"]            # → False (lowercase rejected)
identifier_analyze("myVar", languages=["python", "env"])["rust_valid"]  # → None (not requested)
identifier_analyze("_priv")["warnings"]
# → ['Identifier starts with underscore - typically reserved for private/use-only']
identifier_analyze("for")["summary"]
# → 'Style: mixed. Valid in: JavaScript. Python: reserved keyword'
identifier_analyze("")["classification"]  # → 'invalid'
```

**Classification rules (order matters — first match wins):**

1. `snake_case`: contains `_`, all-alnum/`_` chars, every `_`-separated part is lowercase-or-empty
   (so `"_priv"` and `"my_var"` qualify; `"MY_CONST"` does not).
2. `camelCase`: starts lowercase, no `_`/`-`, `isidentifier()`, contains an uppercase letter.
3. `PascalCase`: starts uppercase, no `_`/`-`, `isidentifier()`, contains an uppercase letter.
4. `kebab-case`: contains `-`, all-alnum/`_`/`-` chars, every `-`-separated part lowercase-or-empty.
5. `SCREAMING_SNAKE_CASE`: all-alnum/`_` chars, every `_`-separated part uppercase-or-empty
   (single words like `"HELLO"` and `"A1"` also qualify — no `_` required).
6. `mixed`: `isidentifier()` but none of the above (e.g. `"for"`, `"a1"`, `"myVar2x"` without case split).
7. `invalid`: everything else (`"bad name"`, `"my-var"` for identifier purposes, `""`).

**Suggestions:** always all five keys (`snake_case`, `kebab_case`, `pascal_case`,
`camel_case`, `screaming_snake_case`), computed via `_to_snake_case` pivots.
`suggestions` values are best-effort rewrites, not validations (e.g. `"bad name"` maps to
itself for `snake_case`).

**Warnings (exact strings):**

- `"Python keyword - cannot be used as identifier in Python"` (when `python_keyword`)
- `"Rust keyword - cannot be used as identifier in Rust"` (Rust keyword hit)
- `"Invalid Rust identifier - cannot be used as identifier in Rust"` (non-keyword Rust invalid)
- `"Identifier has mixed naming convention"` (classification == `"mixed"`)
- `"Identifier starts with underscore - typically reserved for private/use-only"`

## Internal Helpers

- `_is_valid_ident_chars(text, extra_chars="")` — alnum/`_` (plus extras) gate for snake/kebab/screaming checks.
- `_is_snake_case` / `_is_camel_case` / `_is_pascal_case` / `_is_kebab_case` / `_is_screaming_snake_case` — ordered predicates above.
- `_classify(text)` — first-match dispatcher with `mixed`/`invalid` fallbacks.
- `_to_snake_case` — case-boundary splitter (inserts `_` on upper runs); pivot for all suggestions.
- `_to_pascal_case` / `_to_camel_case` / `_to_kebab_case` / `_to_screaming_snake_case` — derived rewrites.

## Dependencies

```
identifier.py
    └── stdlib only: keyword, re, typing (leaf module — no exact/ imports)
```

Stdlib-only; safe for the single-file build.

## Security / DoS Notes

- **Bounded input by contract:** single identifier string; no file, network, or regex-backtracking
  risk (`_ENV_PATTERN` is a linear anchored class match). No `MAX_*` cap is enforced in code,
  so callers accepting unbounded user input should cap length (suggestions allocate O(n)).
- No code execution: validation uses `str.isidentifier()` and set membership only.
- `javascript_valid` intentionally ignores keywords — do not use it as a JS-reserved-word gate
  (use `identifier_inspect` table checks with `language="javascript"` for keyword hits).

## See Also

- [identifier_inspect.md](identifier_inspect.md) — multi-identifier collision detection (confusables, casefold, normalization, table keyword/style checks)
- [unicode_tools.md](unicode_tools.md) — script detection and confusable identification
- [exact.md](exact.md) — package-level overview

## Usage Example

```python
from eggcalc.exact.identifier import identifier_analyze

r = identifier_analyze("myVar")
print(r["classification"])            # 'camelCase'
print(r["python_valid"])              # True
print(r["suggestions"]["snake_case"]) # 'myvar'
print(r["summary"])                   # 'Style: camelCase. Valid in: Python, Rust, JavaScript'

k = identifier_analyze("for")
print(k["python_keyword"])  # True
print(k["warnings"])        # ['Python keyword - ...', 'Rust keyword - ...', 'Identifier has mixed naming convention']
```

(End of file - total 311 lines implementation)
