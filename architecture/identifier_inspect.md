# identifier_inspect.py — Identifier Collision Detection

766 lines. Multi-identifier collision and validity checking with confusable detection.

## Table of Contents

- [Overview](#overview)
- [Type Definitions](#type-definitions)
- [Constants / Limits](#constants--limits)
- [Public Functions](#public-functions)
  - [identifier_inspect](#identifier_inspect)
  - [identifier_table_inspect](#identifier_table_inspect)
- [Internal Helpers](#internal-helpers)
- [Dependencies](#dependencies)
- [Security / DoS Notes](#security--dos-notes)
- [See Also](#see-also)
- [Usage Example](#usage-example)

## Overview

Deterministic, pure, no I/O. Two entry points over the same threat model (look-alike
identifiers that collide after normalization, case folding, or visual confusion):

- `identifier_inspect`: per-identifier validity/scripts/invisibles/confusables plus
  pairwise collisions (`confusable`, `casefold`, `normalization`).
- `identifier_table_inspect`: table-level audit over `{"name", "kind", "file", "line"}`
  dicts — casefold/normalization/confusable/style-variant collisions, reserved-keyword
  hits, and mixed-style groups.

Results are plain-dict TypedDicts — use `result["collisions"]`, never `result.collisions`.
Finding vocab here is the module's own (`kind`/`a`/`b`, `kind`/`names`/`detail`,
`name`/`language`/`file`/`line`, `stripped`/`names`/`styles`, `findings: list[str]`) —
field names below are verified verbatim against code, not invented.

## Type Definitions

### IdentifierInspectResult (TypedDict)

```python
class IdentifierInspectResult(TypedDict):
    identifiers: list[IdentifierInfo]  # one entry per input, in input order
    collisions: list[CollisionInfo]    # pairwise, each pair reported at most once
```

### IdentifierInfo (TypedDict)

```python
class IdentifierInfo(TypedDict):
    raw: str                # original input string
    normalized: str         # unicodedata.normalize(normalization, raw), or raw when normalization="raw"
    valid: bool             # language-gated: python / javascript+typescript checked; all other languages default True
    scripts: list[str]      # sorted heuristic scripts, excluding Common/Inherited/Unknown/Other
    has_invisibles: bool    # any char in the 19-entry invisible set
    has_confusables: bool   # detect_confusables(normalized) non-empty
    warnings: list[str]     # subset of: "Invalid Python identifier", "Invalid <lang> identifier",
                            # "Contains invisible characters", "Contains confusable characters",
                            # "Mixed script identifier"
```

### CollisionInfo (TypedDict)

```python
class CollisionInfo(TypedDict):
    kind: str  # "confusable" | "casefold" | "normalization"
    a: str     # first raw identifier
    b: str     # second raw identifier
```

### TableIdentifierEntry (TypedDict, total=False)

```python
class TableIdentifierEntry(TypedDict, total=False):
    name: str   # required in practice (code uses entry.get("name", ""))
    kind: str   # optional (e.g. "variable", "function")
    file: str   # optional; echoed into reserved_keyword_hits
    line: int   # optional; echoed into reserved_keyword_hits
```

### TableCollisionInfo (TypedDict)

```python
class TableCollisionInfo(TypedDict):
    kind: str         # "casefold" | "normalization" | "confusable" | "style_variant"
    names: list[str]  # the colliding group (>= 2; duplicates preserved for casefold)
    detail: str       # human-readable, e.g. "Casefold collision: myVar, MyVar"
```

### ReservedKeywordHit (TypedDict)

```python
class ReservedKeywordHit(TypedDict):
    name: str      # the identifier text
    language: str  # echo of the language argument
    file: str      # entry.get("file", "")
    line: int      # entry.get("line", 0)
```

### MixedStyleGroup (TypedDict)

```python
class MixedStyleGroup(TypedDict):
    stripped: str       # _strip_style(name): separators removed, lowercased
    names: list[str]    # members sharing the stripped form
    styles: list[str]   # distinct _classify_style outputs for the group
```

### IdentifierTableInspectResult (TypedDict)

```python
class IdentifierTableInspectResult(TypedDict):
    count: int                                   # len(identifiers)
    collisions: list[TableCollisionInfo]         # all active check kinds, in check order
    reserved_keyword_hits: list[ReservedKeywordHit]
    mixed_style_groups: list[MixedStyleGroup]
    findings: list[str]                          # e.g. "Casefold collisions detected",
                                                 # "1 reserved keyword hit(s) in python"
```

## Constants / Limits

```python
_JS_KEYWORDS: frozenset[str]   # 38 entries: break..yield (see code lines 46-87)
_RUST_KEYWORDS: frozenset[str] # 38 entries incl. Self (capital-S); same list as identifier.py
_TS_KEYWORDS = _JS_KEYWORDS | {any, boolean, constructor, declare, get, module, require,
    number, set, string, symbol, type, from, of, readonly, abstract, as, async, await,
    enum, export, implements, interface, is, keyof, namespace, package, private,
    protected, public, static, override}
_LANG_KEYWORDS = {"python": frozenset(keyword.kwlist), "rust": ..., "javascript": ..., "typescript": ...}
_SCRIPT_RANGES: list[tuple[int, int, str]]  # 22 ranges: Latin x3, Cyrillic x2, Greek x2, Han,
    # CJK, Hiragana, Katakana, Arabic, Hebrew, Devanagari, Thai, Hangul, Georgian, Armenian,
    # Cherokee, Canadian_Aboriginal
```

Bounded inputs:

- `identifier_table_inspect` confusable fallback calls
  `levenshtein_distance(name_a, name_b, max_len=200)` and swallows `ValueError`
  (over-long inputs simply skip the near-collision check).
- No `MAX_*` length cap is enforced on the identifier lists themselves; pairwise
  collision loops are O(n²) in the number of identifiers (see Security notes).

## Public Functions

### `identifier_inspect`

```python
def identifier_inspect(
    identifiers: list[str],
    language: str = "generic",
    normalization: str = "NFC",
    casefold: bool = False,
    check_confusables: bool = True,
) -> IdentifierInspectResult
```

`language` only gates `valid`: `"python"` uses `isidentifier()` + not-keyword;
`"javascript"`/`"typescript"` use `isidentifier()` + not-in-`_JS_KEYWORDS`;
`"generic"`, `"rust"`, `"json_key"`, and anything else always report `valid=True`.
`normalization="raw"` skips normalization; any other value is passed to
`unicodedata.normalize` (invalid forms raise `ValueError`).

Collision kinds (each unordered pair emitted at most once via `collision_pairs`):

- `confusable`: shared `confusable_with` targets, or one side's target substring-present
  in the other normalized form. Identical raw pairs are skipped (duplicates ≠ collisions).
- `casefold`: only when `casefold=True`; groups by `norm.casefold()`.
- `normalization`: only when `normalization != "raw"`; groups by normalized form
  (identical raws skipped).

Verified examples:

```python
identifier_inspect(["paypal", "pаypal"], language="python")["collisions"]
# → [{'kind': 'confusable', 'a': 'paypal', 'b': 'pаypal'}]  # second 'a' is Cyrillic U+0430
identifier_inspect(["paypal", "pаypal"])["identifiers"][1]
# → {'raw': 'pаypal', 'normalized': 'pаypal', 'valid': True, 'scripts': ['Cyrillic', 'Latin'],
#     'has_invisibles': False, 'has_confusables': True,
#     'warnings': ['Contains confusable characters', 'Mixed script identifier']}
identifier_inspect(["Foo", "foo"], casefold=True)["collisions"]
# → [{'kind': 'casefold', 'a': 'Foo', 'b': 'foo'}]
identifier_inspect(["Foo", "foo"])["collisions"]  # → [] (casefold off by default)
identifier_inspect(["ok", "bad name", "for"], language="python")["identifiers"]
# → [('ok', True, []), ('bad name', False, ['Invalid Python identifier', 'Contains confusable characters']),
#     ('for', False, ['Invalid Python identifier'])]
identifier_inspect(["café", "café"])["collisions"]  # → [] (identical raws are duplicates, not collisions)
```

**Edge cases:** combining marks report script `"Inherited"` (excluded from `scripts`, so
`"café"` → `['Latin']`). The invisible set is 19 chars (`\u200b-\u200f` family, `\ufeff`,
`\u00a0`, `\u2028/\u2029`, `\u202a-\u202e`, `\u2066-\u2069`, `\u2060`) — checked against
the **raw** id. `valid` for `"rust"`/`"generic"` is always `True` (no Rust validation here;
use `identifier_analyze` or table `reserved` checks for Rust keywords).

### `identifier_table_inspect`

```python
def identifier_table_inspect(
    identifiers: list[dict],
    language: str = "python",
    checks: list[str] | None = None,
) -> IdentifierTableInspectResult
```

Default `checks`: `["casefold", "normalization", "confusable", "style", "reserved",
"mixed_style"]`; unknown names are silently dropped. Each check appends in that order.

| Check | Rule | Verified behavior |
|-------|------|-------------------|
| `casefold` | Group by `name.casefold()`; group > 1 → `TableCollisionInfo(kind="casefold")` | `[{"name": "x"}, {"name": "x"}]` (exact dupes) still collide here, unlike `identifier_inspect` |
| `normalization` | Group by `unicodedata.normalize("NFC", name)`; distinct originals in one group → `kind="normalization"` | detail: `"Normalization collision (NFC '<key>'): ..."` |
| `confusable` | Shared-target / substring confusable, else `levenshtein_distance <= 1` (max_len=200) → `kind="confusable"` | `myVar` vs `MyVar` collide (distance 1); identical names skipped |
| `style` | Group by `_strip_style`; > 1 distinct `_classify_style` → `kind="style_variant"` | `myVar` (camelCase) vs `MyVar` (PascalCase) share stripped `"myvar"` |
| `reserved` | `name in _LANG_KEYWORDS[language]` → `ReservedKeywordHit` (unknown language → empty set, no hits) | `{"name": "for", "file": "a.py", "line": 1}` → hit with those echoes |
| `mixed_style` | Same grouping as `style`, but emits `MixedStyleGroup(stripped, names, styles)` | parallels `style` collisions |

Verified example:

```python
identifier_table_inspect([{"name": "myVar"}, {"name": "MyVar"}, {"name": "for", "file": "a.py", "line": 1}])
# → {"count": 3,
#     "collisions": [
#       {"kind": "casefold", "names": ["myVar", "MyVar"], "detail": "Casefold collision: myVar, MyVar"},
#       {"kind": "confusable", "names": ["myVar", "MyVar"], "detail": "Confusable/near-collision: 'myVar' and 'MyVar'"},
#       {"kind": "style_variant", "names": ["myVar", "MyVar"], "detail": "Style variants for 'myvar': PascalCase, camelCase"}],
#     "reserved_keyword_hits": [{"name": "for", "language": "python", "file": "a.py", "line": 1}],
#     "mixed_style_groups": [{"stripped": "myvar", "names": ["myVar", "MyVar"], "styles": ["PascalCase", "camelCase"]}],
#     "findings": ["Casefold collisions detected", "Confusable characters or near-collisions detected",
#                  "Style variant collisions detected", "1 reserved keyword hit(s) in python",
#                  "1 mixed-style group(s) detected"]}
identifier_table_inspect([{"name": "x"}, {"name": "x"}], checks=["casefold"])["collisions"]
# → [{'kind': 'casefold', 'names': ['x', 'x'], ...}]  (table check counts exact dupes)
```

**Edge cases:** `checks=[]` runs nothing (all outputs empty except `count`). Missing
`"name"` defaults to `""` (empty names group together under casefold). `style` and
`mixed_style` skip names whose stripped form is empty.

## Internal Helpers

- `_identifier_script_heuristic(char)` — combining marks → `"Inherited"`; else first
  `_SCRIPT_RANGES` hit; else `"Other"`.
- `_normalize_nfc` / `_identifier_casefold` — thin `unicodedata.normalize` / `casefold` wrappers.
- `_has_invisibles` — 19-char set membership test.
- `_check_python_valid` (`isidentifier()` + not keyword), `_check_js_valid` (keyword set + `isidentifier()`), `_get_scripts` (filtered, sorted).
- `_classify_style(name)` — `PascalCase` / `snake_case` / `SCREAMING_SNAKE_CASE` / `kebab-case` / `camelCase` / `mixed` / `invalid` (table-local variant; leading-`_` names fall to `mixed`).
- `_strip_style(name)` — `re.sub(r"[_\-]", "", name).lower()` canonical form.

## Dependencies

```
identifier_inspect.py
    ├── stdlib: keyword, re, unicodedata, typing
    └── exact: .diff.levenshtein_distance (near-collision fallback, max_len=200)
               .unicode_tools.detect_confusables + ConfusableInfo (visual-confusion source)
```

Stdlib + two leaf `exact/` modules; no I/O anywhere in the chain.

## Security / DoS Notes

- **Pairwise cost:** both `identifier_inspect` (confusable/casefold/normalization) and the
  table `confusable` check loop O(n²) over identifiers, each step potentially calling
  `detect_confusables` (cached per normalized form in `identifier_inspect`; uncached per
  pair in the table path) and `levenshtein_distance`. Cap list size caller-side
  (hundreds, not tens of thousands) for untrusted input.
- **`max_len=200` guard:** the Levenshtein fallback raises `ValueError` past the cap and
  is swallowed — long identifiers silently skip near-collision detection rather than
  burning CPU. Do not rely on it for very long tokens.
- Normalization-form input is passed to `unicodedata.normalize` unchecked (except
  `"raw"`); validate against `NFC/NFD/NFKC/NFKD` before exposing directly to users.
- Findings are data (`list[str]` + structured dicts with `line`/`file` echoes), never
  executed — safe to render, but `file`/`line` echoes are caller-supplied, not verified.

## See Also

- [identifier.md](identifier.md) — single-identifier naming convention analysis and suggestions
- [unicode_tools.md](unicode_tools.md) — `detect_confusables` authority and script detection
- [diff.md](diff.md) — `levenshtein_distance` (near-collision fallback)
- [primitives.md](primitives.md) — invisible-character primitives

## Usage Example

```python
from eggcalc.exact.identifier_inspect import identifier_inspect, identifier_table_inspect

# Homoglyph audit: Latin 'a' vs Cyrillic 'а'
r = identifier_inspect(["paypal", "pаypal"], language="python", casefold=True)
print(r["collisions"])              # [{'kind': 'confusable', 'a': 'paypal', 'b': 'pаypal'}]
print(r["identifiers"][1]["warnings"])  # ['Contains confusable characters', 'Mixed script identifier']

# Table audit for a rename review
t = identifier_table_inspect([{"name": "myVar"}, {"name": "MyVar"}, {"name": "for"}])
print(t["reserved_keyword_hits"])  # [{'name': 'for', 'language': 'python', 'file': '', 'line': 0}]
print(t["mixed_style_groups"])     # [{'stripped': 'myvar', ...}]
```

(End of file - total 766 lines implementation)
