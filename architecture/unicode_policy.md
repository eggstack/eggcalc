# unicode_policy.py — Unicode Safety Policies

930 lines. Named Unicode safety policies and canonicalization profiles.

## Table of Contents

- [Overview](#overview)
- [Type Definitions](#type-definitions)
- [Constants / Limits](#constants--limits)
- [Public Functions](#public-functions)
  - [unicode_policy_check](#unicode_policy_check)
  - [canonicalize_text](#canonicalize_text)
- [Policies](#policies)
- [Canonicalization Profiles](#canonicalization-profiles)
- [Internal Helpers](#internal-helpers)
- [Dependencies](#dependencies)
- [Security Notes](#security-notes)
- [See Also](#see-also)

## Overview

Two deterministic entry points over the same Unicode primitives:

- `unicode_policy_check()` — applies one of six named safety policies and
  returns pass/fail plus structured findings. **Errors fail, warnings
  don't**: `pass_ = (no error-severity findings)`.
- `canonicalize_text()` — applies one of five named canonicalization
  profiles and returns the canonical text, the operations applied, and
  SHA-256 fingerprints before/after (plus an optional char mapping).

Default normalization is NFC for every policy except `domain_like`
(NFKC); pass `normalization="raw"` to skip normalization entirely.
Policies are heuristics, not security guarantees.

## Type Definitions

```python
class PolicyFinding(TypedDict):
    rule: str        # e.g. "bidi_controls", "mixed_scripts", "confusables"
    severity: str    # "error" (fails) | "warning" (passes with note)
    message: str

class UnicodePolicyCheckResult(TypedDict):
    pass_: bool             # True iff zero error-severity findings
    policy: str             # Echo of the requested policy
    normalized_form: str    # Text after normalization ("" on early failure)
    findings: list[PolicyFinding]
    summary: str            # "PASS (policy)" / "FAIL (policy); N error(s)[; M warning(s)]"

class CanonicalizeResult(TypedDict):
    text: str                    # Canonical output
    changed: bool
    operations_applied: list[str]  # e.g. ["casefold"], ["LF_newlines", ...]
    fingerprint_before: str      # SHA-256 hex of input
    fingerprint_after: str       # SHA-256 hex of output
    findings: list[str]

class CanonicalizeResultWithMapping(CanonicalizeResult):
    mapping: list[dict[str, str]] | None
    # Per-char entries when return_mapping=True, else None:
    # {"position", "original", "original_codepoint",
    #  "canonical", "canonical_codepoint"}
```

## Constants / Limits

```python
MAX_TEXT_LENGTH = 100_000   # over-limit check input → pass_=False "input_too_large"

_VALID_POLICIES = frozenset({
    "identifier_strict", "filename_safe", "source_code",
    "human_text", "json_key", "domain_like",
})
_VALID_PROFILES = frozenset({
    "source_file_identity", "identifier_compare", "human_label_compare",
    "json_key_compare", "path_segment_compare",
})

_WINDOWS_RESERVED = frozenset({...})  # CON, PRN, AUX, NUL, COM1-9, LPT1-9 (+ extensions)
_BIDI_CHARS = frozenset({...})        # U+202A–U+202E, U+2066–U+2069, U+200E/U+200F
_ZERO_WIDTH_CHAR_SET = frozenset({...})  # U+200B–U+200D, U+FEFF, ...
_WIN_FORBIDDEN = frozenset({...})     # \ / : * ? " < > | (controls checked separately)
```

## Public Functions

### `unicode_policy_check`

```python
def unicode_policy_check(
    text: str,
    policy: str,
    normalization: str | None = None,
) -> UnicodePolicyCheckResult
```

Unknown policies do **not** raise — they return `pass_=False` with an
`invalid_policy` finding. Invalid normalization forms return `pass_=False`
with `invalid_normalization`.

```python
unicode_policy_check("hello", "identifier_strict")
# → {"pass_": True, "policy": "identifier_strict",
#     "normalized_form": "hello", "findings": [], "summary": "PASS (identifier_strict)"}

unicode_policy_check("a\u200bb", "identifier_strict")["findings"]
# → [{"rule": "zero_width_characters", "severity": "error", ...},
#     {"rule": "invisible_characters", "severity": "error", ...}]

unicode_policy_check("con", "filename_safe")["findings"]
# → [{"rule": "reserved_windows_name", "severity": "error", ...}]

unicode_policy_check("x", "nope")["summary"]  # → "Invalid policy: nope"
```

### `canonicalize_text`

```python
def canonicalize_text(
    text: str,
    profile: str,
    return_mapping: bool = False,
) -> CanonicalizeResult | CanonicalizeResultWithMapping
```

Unknown profiles **raise** `ValueError` (unlike `unicode_policy_check`).
With `return_mapping=True` the result also carries the per-char mapping;
otherwise `mapping` is `None`.

```python
canonicalize_text("AbC", "identifier_compare")["text"]  # → "abc"

canonicalize_text(" Hello  World ", "human_label_compare")
# → {"text": "hello world",
#     "operations_applied": ["casefold", "trim", "collapse_whitespace"], ...}

canonicalize_text("Hello\r\nWorld  ", "source_file_identity")["text"]
# → "Hello\nWorld\n"

canonicalize_text("x", "nope")  # → raises ValueError
```

## Policies

Severity matters more than the rule list: errors fail the check, warnings
only annotate. Verified rule/severity matrix:

| Policy | error rules | warning rules |
|--------|-------------|---------------|
| `identifier_strict` | `mixed_scripts`, `bidi_controls`, `zero_width_characters`, `confusables`, `invisible_characters` | `normalization_instability` (NFC≠NFD, e.g. `café`) |
| `filename_safe` | `control_characters`, `path_separators` (`/`), `bidi_controls`, `zero_width_characters`, `reserved_windows_name` (`con`, `NUL`, `COM1`…) | — |
| `source_code` | `bidi_controls`, `zero_width_characters` | `confusables` |
| `human_text` | — | `bidi_controls`, `zero_width_characters`, `mixed_scripts`, `confusables` |
| `json_key` | `bidi_controls`, `zero_width_characters`, `variation_selectors`, `control_characters` | `confusables` |
| `domain_like` (NFKC default) | `mixed_scripts`, `confusables`, `bidi_controls`, `zero_width_characters` | — |

Notes:

- `identifier_strict` does **not** reject spaces or punctuation
  (`"hello world!"` passes) — it checks scripts/invisibles/confusables,
  not identifier grammar. Use `identifier.py` for naming conventions.
- `normalization_instability` intentionally fires on common precomposed
  characters (`é`); filter to errors-only if too noisy.
- `domain_like` treats confusables as errors (homograph risk);
  `source_code`/`human_text`/`json_key` downgrade them to warnings.

## Canonicalization Profiles

| Profile | Operations (in order) |
|---------|----------------------|
| `source_file_identity` | NFC, `LF_newlines` (`\r\n`→`\n`), `strip_trailing_whitespace`, `ensure_final_newline` |
| `identifier_compare` | NFC, `casefold` |
| `human_label_compare` | NFC, `casefold`, `trim`, `collapse_whitespace` |
| `json_key_compare` | NFC, `casefold` |
| `path_segment_compare` | NFC, `lowercase`, `LF_newlines` |

Fingerprints are SHA-256 hex over UTF-8 bytes, before and after.

## Internal Helpers

| Helper | Role |
|--------|------|
| `_default_normalization(policy)` | Policy→form map (NFKC only for `domain_like`, else NFC) |
| `_check_identifier_strict(text, normalized)` | Mixed scripts, bidi, zero-width, confusables, NFC/NFD instability, invisibles |
| `_check_filename_safe(text, normalized)` | Controls, `/` separators, bidi, zero-width, Windows reserved names |
| `_check_source_code(text, normalized)` | Bidi + zero-width (errors), confusables (warning) |
| `_check_human_text(text, normalized)` | Bidi, zero-width, mixed scripts, confusables — all warnings |
| `_check_json_key(text, normalized)` | Bidi, zero-width, variation selectors, controls (errors), confusables (warning) |
| `_check_domain_like(text, normalized)` | Mixed scripts, confusables, bidi, zero-width — all errors |
| `_build_char_mapping(original, canonical)` | Per-char position/codepoint mapping entries |
| `_canonicalize_source_file_identity / _identifier_compare / _human_label_compare / _json_key_compare / _path_segment_compare` | Profile implementations → `(text, ops, findings)` |

## Dependencies

```
unicode_policy.py
    ├── hashlib, re, unicodedata, typing   (stdlib)
    ├── exact/primitives.py                (find_invisibles, normalize_unicode)
    └── exact/unicode_tools.py             (detect_confusables, detect_mixed_scripts)
```

## Security Notes

- Heuristics, not proofs: a `PASS` means "no known-bad pattern", never
  "safe to execute / render / trust".
- `human_text` never fails — every finding is a warning. Do not use it
  as a gate; use `identifier_strict` / `domain_like` for gates.
- `normalization` accepts any `unicodedata.normalize` form string;
  invalid forms fail closed (`pass_=False`), and `"raw"` skips
  normalization for byte-exact auditing.
- Canonicalization is lossy by design (casefold, whitespace collapse) —
  compare fingerprints, never assume round-trip fidelity.

## See Also

- [unicode_tools.md](unicode_tools.md) — script/confusable detectors used here
- [primitives.md](primitives.md) — `find_invisibles`, `normalize_unicode`
- [inspect_prompt.md](inspect_prompt.md) — findings-style scanner vs pass/fail policies
- [identifier_inspect.md](identifier_inspect.md) — identifier collision detection
