# config.py — Config File Validation

368 lines. Deterministic line-by-line parsers for `.env` and INI files.

## Table of Contents

- [Overview](#overview)
- [Type Definitions](#type-definitions)
- [Constants / Limits](#constants--limits)
- [Public Functions](#public-functions)
  - [dotenv_validate](#dotenv_validate)
  - [ini_validate](#ini_validate)
- [Internal Helpers](#internal-helpers)
- [Dependencies](#dependencies)
- [Security / DoS Notes](#security--dos-notes)
- [See Also](#see-also)
- [Usage Example](#usage-example)

## Overview

Deterministic, pure, no I/O. Two lexical line-by-line validators for configuration text:

- `dotenv_validate`: `.env`-style `KEY=VALUE` lines with `#` comments, blank lines,
  optional `export` prefix, single/double quoting, inline-`#` stripping for unquoted
  values, duplicate tracking, expansion-syntax detection, quoting hints.
- `ini_validate`: simple INI with `[section]` headers, `key = value` / `key : value`
  lines, `#` and `;` comments, duplicate sections and per-section duplicate keys.

Both return `parse_ok=False` (never raise, except over the length cap) when any line is
structurally invalid or — under `duplicate_policy="error"` — when a duplicate appears.
`findings` carries human-readable notes; structured details live in `duplicates` and
`invalid_lines` (plain dicts with verified shapes below — field names copied verbatim
from code, not invented).

Results are plain-dict TypedDicts — use `result["entries"]`, never `result.entries`.

## Type Definitions

### DotenvEntry (TypedDict)

```python
class DotenvEntry(TypedDict):
    key: str            # stripped key text
    value: str          # processed value (quotes removed, escapes expanded for "...", inline # stripped for bare)
    value_present: bool # always True in the current implementation
    quote_style: str    # "none" | "'" | '"'
    line: int           # 1-based source line number
```

### DotenvValidateResult (TypedDict)

```python
class DotenvValidateResult(TypedDict):
    parse_ok: bool                          # False on any invalid line, or duplicates when policy="error"
    entries: list[DotenvEntry]              # valid entries in source order
    duplicates: list[dict[str, object]]     # each: {"key": str, "first_line": int, "second_line": int}
    invalid_lines: list[dict[str, object]]  # each: {"line": int, "text": str, "reason": str}
    requires_quoting: list[str]             # keys whose bare value contains a space (and isn't {/[ -prefixed)
    contains_expansion_syntax: list[str]    # keys whose RAW value matches ${...} or $NAME
    findings: list[str]                     # duplicate notes + ["No entries found"] when empty-and-clean
```

### IniLine / IniSectionLine / IniKeyValueLine (TypedDicts)

```python
class IniLine(TypedDict):
    kind: str   # base shape (subclasses add fields; the parser builds dicts inline)
    line: int   # 1-based source line number

class IniSectionLine(IniLine):
    name: str   # section name without brackets

class IniKeyValueLine(IniLine):
    section: str | None  # enclosing section, or None for top-level
    key: str
    value: str
```

Note: these three classes document the conceptual line shapes; the validator's output
accumulates into `IniValidateResult` rather than returning line objects.

### IniValidateResult (TypedDict)

```python
class IniValidateResult(TypedDict):
    parse_ok: bool                          # False on any invalid line, or duplicates when policy="error"
    sections: list[str]                     # section names in first-appearance order
    keys_by_section: dict[str, list[str]]   # section → keys in source order; top-level under "(top-level)"
    duplicates: list[dict[str, object]]     # sections: {"key": "[name]", "first_line": int,
                                            #   "second_line": int, "section": str};
                                            # keys: {"key": str, "section": str, "first_line": int,
                                            #   "second_line": int} (section label "(top-level)" when unsectioned)
    invalid_lines: list[dict[str, object]]  # each: {"line": int, "text": str, "reason": str}
    findings: list[str]                     # duplicate notes + ["No sections or keys found"] when empty-and-clean
```

## Constants / Limits

```python
DEFAULT_KEY_PATTERN = r"^[A-Za-z_][A-Za-z0-9_]*$"   # default key_pattern for dotenv_validate
_EXPANSION_RE = re.compile(r"\$\{[^}]*\}|\$[A-Za-z_][A-Za-z0-9_]*")  # ${...} or $NAME over the RAW value
MAX_TEXT_INPUT_length = 100_000  # note lowercase "length"; enforced by BOTH validators (len(text) > cap → ValueError)
```

`duplicate_policy` accepts `"warn"` (record + finding, `parse_ok` unchanged),
`"error"` (record + finding + `parse_ok=False`), or `"allow"` (record silently —
duplicates still listed, no finding, `parse_ok` unchanged).

## Public Functions

### `dotenv_validate`

```python
def dotenv_validate(
    text: str,
    allow_export: bool = True,
    key_pattern: str = DEFAULT_KEY_PATTERN,
    duplicate_policy: str = "warn",
) -> DotenvValidateResult
```

**Raises:** `ValueError` when `len(text) > MAX_TEXT_INPUT_length` (verified:
101-char-over input raises `"Input length 100001 exceeds maximum 100000"`).

Parsing rules (verified by execution):

- Blank lines and `#`-leading lines (after strip) are skipped.
- `export KEY=...` is stripped when `allow_export=True`; when `False`, the line is
  invalid with `reason="export keyword not allowed"`.
- The first `=` splits key/value; `eq_pos < 1` (no `=`, or `=...` with empty key) is
  invalid with `reason="missing '=' separator"`.
- Key must fully... actually partially match: `key_re.match(key)` (prefix match, not
  fullmatch) against `key_pattern`; failure is invalid with
  `reason="key '<k>' does not match pattern <pat>"`.
- `'...'` / `"..."` fully-wrapped values: quotes stripped, `quote_style` recorded.
  Double-quoted values expand `\\n → \n`, `\\r`, `\\t`, `\\"`, `\\'`, `\\\\`, and any
  other `\\x` → `x`; single-quoted values stay literal.
- Bare values: inline `#` comment stripped (`value.split("#", 1)[0].rstrip()`); a remaining
  space flags `requires_quoting` unless the value starts with `{` or `[`.
- `_EXPANSION_RE` runs over the **raw** post-`=` text (before quote processing), so even
  single-quoted `'$HOME'` flags `contains_expansion_syntax`.

Verified examples:

```python
dotenv_validate("FOO=bar\n")["entries"]
# → [{'key': 'FOO', 'value': 'bar', 'value_present': True, 'quote_style': 'none', 'line': 1}]
dotenv_validate('BAZ="a b"\n')["entries"][0]["value"]  # → 'a b' (quote_style '"')
dotenv_validate("SPACED=hello world\n")["requires_quoting"]  # → ['SPACED']
dotenv_validate("EXP=$HOME/x\n")["contains_expansion_syntax"]  # → ['EXP']
dotenv_validate("FOO=1\nFOO=2\n")["duplicates"]  # → [{'key': 'FOO', 'first_line': 1, 'second_line': 2}]
dotenv_validate("BAD LINE\n")["invalid_lines"]
# → [{'line': 1, 'text': 'BAD LINE', 'reason': "missing '=' separator"}]
dotenv_validate("export FOO=1\n", allow_export=False)["invalid_lines"]
# → [{'line': 1, 'text': 'export FOO=1', 'reason': 'export keyword not allowed'}]
dotenv_validate("A=1\nA=2\n", duplicate_policy="error")["parse_ok"]  # → False
dotenv_validate("")["findings"]  # → ['No entries found']
```

### `ini_validate`

```python
def ini_validate(
    text: str,
    duplicate_policy: str = "warn",
) -> IniValidateResult
```

**Raises:** `ValueError` when `len(text) > MAX_TEXT_INPUT_length`.

Parsing rules (verified by execution):

- Blank lines and `#`/`;`-leading lines skipped.
- `[name]` (stripped, must start with `[` and end with `]`, non-empty inside) opens a
  section; `[]` is invalid (`reason="empty section name"`). Re-opening a section records a
  duplicate with `key="[name]"` but keeps appending keys to the same section entry.
- Other lines must match `^([^=:\s]+)\s*[=:]\s*(.*)` — so `k: v` is accepted, `badline`
  is invalid (`reason="not a valid key=value line or section header"`). Keys cannot
  contain whitespace (first class is `[^=:\s]+`).
- Duplicate keys are scoped per `(section, key)`; top-level keys group under
  `"(top-level)"` in `keys_by_section` and use `section="(top-level)"` in duplicates.

Verified examples:

```python
ini_validate("[a]\nx=1\n")["sections"]          # → ['a']
ini_validate("[a]\nx=1\n")["keys_by_section"]   # → {'a': ['x']}
ini_validate("k: v\n")["keys_by_section"]       # → {'(top-level)': ['k']} (colon separator OK)
ini_validate("[a]\nx=1\n[a]\nx=2\nbadline\n")
# → parse_ok False;
#   duplicates [{'key': '[a]', 'first_line': 1, 'second_line': 3, 'section': 'a'},
#               {'key': 'x', 'section': 'a', 'first_line': 2, 'second_line': 4}];
#   invalid_lines [{'line': 5, 'text': 'badline', 'reason': 'not a valid key=value line or section header'}]
ini_validate("")["findings"]  # → ['No sections or keys found']
```

## Internal Helpers

None — both validators are self-contained loops over `text.splitlines()` with inline
regexes (`re.compile(key_pattern)` per call for dotenv; one inline `re.match` per line
for INI) and inline escape expansion. The only shared private is the module-level
`_EXPANSION_RE`.

## Dependencies

```
config.py
    └── stdlib only: re, typing (leaf module — no exact/ imports)
```

Stdlib-only; safe for the single-file build.

## Security / DoS Notes

- **Bounded inputs:** both entry points reject `len(text) > 100_000` (`MAX_TEXT_INPUT_length`)
  with `ValueError` before parsing. Per-line work is linear (split/strip/regex); total cost
  O(n) in input length. The odd lowercase-`length` name is verbatim from code — use
  `MAX_TEXT_INPUT_length` when importing it.
- `key_pattern` is compiled with `re.compile` on every `dotenv_validate` call — a hostile
  caller-supplied pattern could ReDoS the validator; only pass trusted patterns (default is
  a linear anchored class). Note matching uses `.match` (prefix), so a custom pattern like
  `"A+"` accepts `"AX"` — anchor with `$`/fullmatch semantics if strictness matters.
- Findings echo raw input (`invalid_lines[].text` is the verbatim source line); truncate
  before rendering untrusted configs in fixed-width UIs.
- Duplicate tracking stores one small dict per repeat — adversarial inputs with ~100k
  alternating keys stay linear; no exponential blowup.

## See Also

- [encoding.md](encoding.md) — adjacent `MAX_TEXT_INPUT_length` (100 000) convention
- [validate.md](validate.md) — JSON/config value validation companion
- [shell.md](shell.md) — `.env` expansion-syntax consumers (quoting/escaping context)
- [exact.md](exact.md) — package-level overview

## Usage Example

```python
from eggcalc.exact.config import dotenv_validate, ini_validate

env = dotenv_validate('FOO=bar\nBAZ="a b"\nFOO=dup\nBAD LINE\nSPACED=hello world\nEXP=$HOME/x\n')
print(env["parse_ok"])                   # False (BAD LINE)
print(env["duplicates"])                 # [{'key': 'FOO', 'first_line': 1, 'second_line': 3}]
print(env["requires_quoting"])           # ['SPACED']
print(env["contains_expansion_syntax"])  # ['EXP']

ini = ini_validate("[server]\nhost = example.com\nport = 8080\n")
print(ini["parse_ok"])            # True
print(ini["keys_by_section"])     # {'server': ['host', 'port']}
```

(End of file - total 368 lines implementation)
