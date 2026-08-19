# transform.py — Text Transformations

712 lines. Deterministic text transformations, escaping, hashing, and fingerprinting.

## Overview

Provides NFC/NFD/NFKC/NFKD normalization, casefolding, trimming, newline normalization, invisible character removal, text escaping/unescaping for multiple formats, cryptographic hashing, and deterministic fingerprinting.

## Key Exports

```python
from eggcalc.exact.transform import (
    text_transform,
    escape_text,
    unescape_text,
    text_hash,
    text_fingerprint,
)
```

## Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `text_transform(text, operations, detail="normal")` | `TextTransformResult` | Applies explicit transformations (NFC, NFD, casefold, trim, newline normalization, zero-width removal, etc.) |
| `escape_text(text, mode)` | `EscapeTextResult` | Escapes text for: `json`, `python`, `rust`, `posix_shell`, `regex`, `markdown_inline_code`, `markdown_code_block`, `html`, `url_component` |
| `unescape_text(text, mode)` | `UnescapeTextResult` | Unescapes text from a target format |
| `text_hash(text, algorithms=["sha256"], encoding="utf-8")` | `TextHashResult` | Computes cryptographic hashes (sha256, sha1, md5, crc32) |
| `text_fingerprint(text, unicode="raw", newline="raw", ...)` | `TextFingerprintResult` | Computes a deterministic fingerprint with canonicalization options |

## Escape Modes

| Mode | Description |
|------|-------------|
| `json` | JSON string escaping (`\n`, `\"`, unicode escapes) |
| `python` | Python string escaping |
| `rust` | Rust string escaping |
| `posix_shell` | POSIX shell quoting |
| `regex` | Regex metacharacter escaping |
| `markdown_inline_code` | Backtick escaping for inline code |
| `markdown_code_block` | Fenced code block wrapping |
| `html` | HTML entity encoding |
| `url_component` | URL percent-encoding |

## Module Dependencies

- `ast`, `hashlib`, `json`, `re`, `unicodedata`, `zlib`, `urllib.parse`

## See Also

- [primitives.md](primitives.md) — Lower-level text primitives (utf8_bytes, codepoints)
