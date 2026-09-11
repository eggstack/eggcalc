# transform.py — Text Transformations

722 lines. Deterministic text transformations, escaping, hashing, and fingerprinting.

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
| `escape_text(text, mode)` | `EscapeTextResult` | Escapes text for: `json_string`, `python_string`, `rust_string`, `posix_shell_single`, `regex_literal`, `markdown_inline_code`, `markdown_code_block`, `html_text`, `url_component` |
| `unescape_text(text, mode)` | `UnescapeTextResult` | Unescapes text from: `json_string`, `python_string`, `unicode_escape`, `url_component` |
| `text_hash(text, algorithms=["sha256"], encoding="utf-8")` | `TextHashResult` | Computes cryptographic hashes (sha256, sha1, md5, crc32) |
| `text_fingerprint(text, unicode="raw", newline="raw", ...)` | `TextFingerprintResult` | Computes a deterministic fingerprint with canonicalization options |

## Escape Modes (`escape_text`)

| Mode | Description |
|------|-------------|
| `json_string` | JSON string escaping (`\n`, `\"`, unicode escapes) |
| `python_string` | Python string escaping |
| `rust_string` | Rust string escaping |
| `posix_shell_single` | POSIX shell single-quoting |
| `regex_literal` | Regex metacharacter escaping |
| `markdown_inline_code` | Backtick escaping for inline code |
| `markdown_code_block` | Fenced code block wrapping |
| `html_text` | HTML entity encoding |
| `url_component` | URL percent-encoding |

## Unescape Modes (`unescape_text`)

| Mode | Description |
|------|-------------|
| `json_string` | JSON string unescaping |
| `python_string` | Python string unescaping |
| `unicode_escape` | Unicode escape (`\uXXXX`) decoding |
| `url_component` | URL percent-decoding |

## Module Dependencies

- `ast`, `hashlib`, `json`, `re`, `unicodedata`, `zlib`, `urllib.parse`

## See Also

- [primitives.md](primitives.md) — Lower-level text primitives (utf8_bytes, codepoints)
