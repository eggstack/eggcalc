# confusables.py — Homoglyph Identification Table

60 lines. Auto-generated homoglyph data (6,565 entries, zlib+base85
payload, lazy decode). **Never edit this data file by hand.**

## Table of Contents

- [Overview](#overview)
- [Type Definitions](#type-definitions)
- [Constants / Limits](#constants--limits)
- [Public Surface](#public-surface)
- [Internal Helpers](#internal-helpers)
- [Regeneration](#regeneration)
- [Dependencies](#dependencies)
- [Security Notes](#security-notes)
- [See Also](#see-also)

## Overview

Generated snapshot of Unicode Standard Annex #39 (UTS #39)
`confusables.txt` — the homoglyph table behind `detect_confusables()`.
The 6,565-entry mapping is stored as a ~31 KB zlib-compressed base85
payload (`_PAYLOAD`) and decoded into a `dict[str, str]` on first access,
not at import time, so `import eggcalc.exact.confusables` stays cheap.

Key design facts:

- **Keys** are uppercase hex codepoints prefixed with `U+`
  (e.g. `"U+0430"`). **Values** are space-separated `U+XXXX` sequences —
  a single codepoint (1:1, Cyrillic `а` → Latin `a`) or several (1:N,
  `Æ` → `AE`).
- Character names are resolved at runtime via `unicodedata.name()`; the
  file contains only codepoint mappings.
- The reverse lookup `reverse_confusables()` lives in
  `unicode_tools.py`, not here — this module is forward-map data only.
- Header metadata is authoritative for provenance: Source 17.0.0,
  Source-Date 2025-07-22, Generated 2026-08-03, Entry-Count 6565.

## Type Definitions

No TypedDicts — the module exports a mapping, not records:

```python
CONFUSABLES: Mapping[str, str] = _LazyConfusables()
# e.g. CONFUSABLES["U+0430"] == "U+0061"

__all__ = ["CONFUSABLES"]
```

Downstream record types (`ConfusableInfo` with `index`, `char`,
`codepoint`, `name`, `confusable_with`, `confusable_name`) are defined in
`unicode_tools.py`, which resolves codepoints to characters.

## Constants / Limits

```python
_PAYLOAD: str          # ~31,213 bytes compressed ASCII (6,565 entries);
                       # lines are "U+XXXX|U+YYYY ..." joined pre-compression
Entry-Count: 6565      # len(CONFUSABLES) — verify with len(), entries are fixed per generation
```

Payload line format (post-decompression, pre-dict): `KEY|VALUE` per line,
split on `|` via `line.partition("|")`.

## Public Surface

`CONFUSABLES` is a `collections.abc.Mapping` supporting `__getitem__`,
`__contains__`, `__iter__`, and `__len__`; first use pays the
`b85decode` + `zlib.decompress` + dict-build cost once, then the decoded
dict is cached on the instance.

```python
from eggcalc.exact.confusables import CONFUSABLES

len(CONFUSABLES)          # → 6565
CONFUSABLES["U+0430"]     # → "U+0061" (Cyrillic а → Latin a)
"U+0041" in CONFUSABLES   # → False (plain Latin A needs no entry)

from eggcalc.exact.unicode_tools import reverse_confusables
reverse_confusables("a")[:3]  # → ["æ", "ɑ", "α"] (chars confusable WITH "a")
```

## Internal Helpers

| Helper | Role |
|--------|------|
| `_LazyConfusables` (class, `__slots__ = ("_data",)`) | Lazy `Mapping`: `_decode()` on first `__getitem__`/`__iter__`/`__len__`/`__contains__`, then caches the dict |
| `_LazyConfusables._decode()` | `zlib.decompress(base64.b85decode(_PAYLOAD))` → per-line `KEY\|VALUE` dict |

Module-namespace hygiene: `base64`/`zlib` are imported as `_base64`/`_zlib`
and deleted (`del _base64, _zlib`) after payload definition; `_decode`
re-imports locally so the single-file build keeps working.

## Regeneration

```bash
python3 scripts/generate_confusables.py
```

`scripts/generate_confusables.py` (279 lines) fetches the latest
`confusables.txt` from
`https://www.unicode.org/Public/security/latest/confusables.txt`
(version-pinnable via `get_confusables_url(version)`), parses entries,
and rewrites `eggcalc/exact/confusables.py` with fresh header metadata.
A `data/confusables.txt` cache file avoids re-downloading.

**Do not edit `confusables.py` directly** — any manual change is
overwritten on regeneration and breaks the generated-payload invariant
checked by the build (`test_generated_file_no_eggcalc_import` and
payload-decode tests).

## Dependencies

```
confusables.py
    └── (standard library only: base64, zlib, collections.abc, unicodedata-at-runtime)
```

No `exact/` imports — generated leaf data module.

## Security Notes

- The table is a snapshot: new Unicode versions add confusables, so a
  `PASS` from `detect_confusables()` means "no *known* homoglyph",
  never "no homoglyph". Regenerate when the Unicode source revs.
- 1:N values (`Æ` → `AE`) mean single-character scans can miss
  multi-character spoofs — downstream `detect_confusables` handles this
  per-character; whole-string visual-equivalence needs NFC + script
  analysis on top (see `unicode_policy` `domain_like`).
- Lazy decode is a one-time CPU cost (~31 KB inflate); it happens on
  first confusable lookup, so latency-sensitive paths should warm
  `len(CONFUSABLES)` at startup, not mid-request.

## See Also

- [unicode_tools.md](unicode_tools.md) — `detect_confusables()`, `reverse_confusables()`, mixed scripts
- [unicode_policy.md](unicode_policy.md) — `domain_like` / `identifier_strict` policies consuming this table
- [synthesis.md](synthesis.md) — `inspect_text` / `explain_diff` compose confusable findings
- [primitives.md](primitives.md) — codepoint/name/category foundation
