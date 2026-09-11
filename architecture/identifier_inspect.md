# identifier_inspect.py — Identifier Collision Detection

766 lines. Multi-identifier collision and validity checking with confusable detection.

## Overview

Inspects lists of identifiers for collisions caused by confusables, mixed scripts, normalization differences, and casefold. Table-level inspection adds reserved keyword detection and mixed-style grouping.

## Key Exports

```python
from eggcalc.exact.identifier_inspect import (
    identifier_inspect,
    identifier_table_inspect,
)
```

## Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `identifier_inspect(identifiers, language="generic", normalization="NFC", casefold=False, check_confusables=True)` | `IdentifierInspectResult` | Inspects identifiers for validity and collisions (confusables, mixed scripts, normalization, casefold) |
| `identifier_table_inspect(identifiers, language="python", checks=None)` | `IdentifierTableInspectResult` | Inspects a table of identifier dicts for collisions, reserved keywords, and mixed naming styles |

## TypedDicts

- `IdentifierInspectResult` — `identifiers: list[IdentifierInfo]`, `collisions: list[CollisionInfo]`
- `IdentifierInfo` — `raw`, `normalized`, `valid`, `scripts`, `has_invisibles`, `has_confusables`, `warnings`
- `IdentifierTableInspectResult` — `count`, `collisions`, `reserved_keyword_hits`, `mixed_style_groups`, `findings`

## Module Dependencies

- `keyword`, `re`, `unicodedata`
- `.diff` (`levenshtein_distance`)
- `.unicode_tools` (`detect_confusables`)

## See Also

- [identifier.md](identifier.md) — Single-identifier naming convention analysis
- [unicode_tools.md](unicode_tools.md) — Script detection and confusable identification
