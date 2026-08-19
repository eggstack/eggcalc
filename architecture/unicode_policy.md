# unicode_policy.py — Unicode Safety Policies

930 lines. Named Unicode safety policies and canonicalization profiles.

## Overview

Deterministic, named policies for validating text against Unicode safety heuristics. Six policies (`identifier_strict`, `filename_safe`, `source_code`, `human_text`, `json_key`, `domain_like`) and five canonicalization profiles (`source_file_identity`, `identifier_compare`, `human_label_compare`, `json_key_compare`, `path_segment_compare`).

## Key Exports

```python
from eggcalc.exact.unicode_policy import (
    unicode_policy_check,
    canonicalize_text,
)
```

## Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `unicode_policy_check(text, policy, normalization=None)` | `UnicodePolicyCheckResult` | Applies a named Unicode safety policy |
| `canonicalize_text(text, profile, return_mapping=False)` | `CanonicalizeResult` | Applies a named canonicalization profile |

## Policies

| Policy | Description |
|--------|-------------|
| `identifier_strict` | Strict identifier validation (ASCII-ish, no invisible chars) |
| `filename_safe` | Filename-safe characters only |
| `source_code` | Source code safety checks |
| `human_text` | Human-readable text validation |
| `json_key` | JSON key validation |
| `domain_like` | Domain-like text validation |

## Canonicalization Profiles

| Profile | Description |
|---------|-------------|
| `source_file_identity` | Canonical form for source file comparison |
| `identifier_compare` | Canonical form for identifier comparison |
| `human_label_compare` | Canonical form for human label comparison |
| `json_key_compare` | Canonical form for JSON key comparison |
| `path_segment_compare` | Canonical form for path segment comparison |

## Module Dependencies

- `hashlib`, `re`, `unicodedata`, `typing`
- `.primitives` (`find_invisibles`, `normalize_unicode`)
- `.unicode_tools` (`detect_confusables`, `detect_mixed_scripts`)

## See Also

- [unicode_tools.md](unicode_tools.md) — Script detection and confusable identification
- [primitives.md](primitives.md) — Core text primitives
