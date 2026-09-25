# encoding.py — Codec and Radix Conversion

282 lines. Deterministic text-codec and integer-radix conversion with
strict input validation. **Standalone leaf: stdlib-only, no `exact/`
dependencies.**

## Table of Contents

- [Overview](#overview)
- [Type Definitions](#type-definitions)
- [Constants / Limits](#constants--limits)
- [Public Functions](#public-functions)
  - [codec_convert](#codec_convert)
  - [radix_convert](#radix_convert)
- [Internal Helpers](#internal-helpers)
- [Dependencies](#dependencies)
- [Security Notes](#security-notes)
- [See Also](#see-also)

## Overview

Pure, side-effect-free conversion between `utf8`, `hex`, `base64`, and
`base64url` codecs, plus signed-magnitude integer conversion between
bases 2–36. No network I/O, filesystem access, locale dependence, or
platform-specific behavior.

Base64 inputs are validated against explicit alphabet, padding, and
length rules before `base64.b64decode(..., validate=True)` runs, so
whitespace, mixed alphabets, misplaced padding, and invalid lengths are
rejected. Radix magnitudes are capped at `2**128 - 1` for
cross-implementation parity even though Python integers are unbounded.

## Type Definitions

```python
# Functional-syntax TypedDict ("from" is a keyword, so class syntax is impossible):
CodecConvertResult = TypedDict("CodecConvertResult", {
    "value": str,         # canonical converted text
    "from": str,          # source format
    "to": str,            # destination format
    "byte_length": int,   # decoded payload length in bytes (not input length)
})

class RadixConvertResult(TypedDict):
    value: str               # canonical: no "+", no leading zeroes, "-" only if negative nonzero
    from_base: int
    to_base: int
    uppercase: bool
    negative: bool
    magnitude_decimal: str   # exact decimal magnitude
```

Access the codec source key as `result["from"]` (never attribute syntax).

## Constants / Limits

```python
MAX_TEXT_INPUT_length = 100_000   # encoded input AND converted output cap

_CODEC_FORMATS = ("utf8", "hex", "base64", "base64url")  # exact, case-sensitive, no aliases
_DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz"
_DIGIT_VALUES = {ch: idx for idx, ch in enumerate(_DIGITS)}
_HEX_CHARS = frozenset("0123456789abcdefABCDEF")
_B64_STD_CHARS = frozenset("A-Za-z0-9+/")
_B64_URL_CHARS = frozenset("A-Za-z0-9-_")
_MAX_U128 = (1 << 128) - 1
_MAX_U128_DECIMAL = "340282366920938463463374607431768211455"
```

Codec contract: hex requires even length and ASCII hex only (no `0x`, no
whitespace); standard Base64 output is padded, Base64URL output is
unpadded, hex output is lowercase, `utf8` destinations decode strictly.

Radix grammar: optional single leading `+`/`-`, then one or more ASCII
digits valid in `from_base`. Whitespace, underscores, `0x`/`0o`/`0b`
prefixes, decimal points, exponents, and Unicode digits are rejected.
Negative zero normalizes to non-negative zero.

## Public Functions

### `codec_convert`

```python
def codec_convert(value: str, from_format: str, to_format: str) -> CodecConvertResult
```

```python
codec_convert("hello", "utf8", "hex")
# → {"value": "68656c6c6f", "from": "utf8", "to": "hex", "byte_length": 5}

codec_convert("hello", "utf8", "base64")
# → {"value": "aGVsbG8=", "from": "utf8", "to": "base64", "byte_length": 5}

codec_convert("aGVsbG8=", "base64", "utf8")["value"]  # → "hello"
```

Unknown formats, odd-length hex, bad padding, or mixed alphabets raise
`ValueError` (`binascii.Error` subclasses `ValueError`, so one except
covers both).

### `radix_convert`

```python
def radix_convert(
    value: str, from_base: int, to_base: int, uppercase: bool = False
) -> RadixConvertResult
```

```python
radix_convert("ff", 16, 10)["value"]   # → "255"
radix_convert("255", 10, 16)["value"]  # → "ff"
radix_convert("-ff", 16, 10)
# → {"value": "-255", "negative": True, "magnitude_decimal": "255", ...}
radix_convert("255", 10, 16, uppercase=True)["value"]  # → "FF"
```

Bases outside 2–36 and magnitudes above `2**128 - 1` raise `ValueError`.

## Internal Helpers

| Helper | Role |
|--------|------|
| `_check_text_length(value, name)` | Enforces `MAX_TEXT_INPUT_length` (raises `ValueError`) |
| `_check_format(name)` | Validates codec name, returns it unchanged |
| `_decode_hex(value)` | Strict hex decode (even length, ASCII hex, no prefixes) |
| `_validate_base64(value, url_safe)` | Alphabet/padding/length pre-check |
| `_decode_base64(value, url_safe)` | Validated `b64decode(validate=True)` |
| `_max_digits_for_base(base)` | Digit-length bound backing the u128 cap |

## Dependencies

```
encoding.py
    └── (standard library only: base64, typing)
```

No `exact/` imports — fully standalone leaf.

## Security Notes

- Strict-decode discipline: mixed-alphabet Base64, embedded whitespace,
  and misplaced padding raise instead of "helpfully" decoding — callers
  cannot be tricked by visually similar but differently-encoded
  payloads.
- `byte_length` is payload bytes, not input chars: use it (not
  `len(value)`) when sizing buffers or enforcing wire limits.
- The u128 magnitude cap is a parity choice, not a security boundary;
  `from_base`/`to_base` are validated ints, and digit validation is
  ASCII-only so Unicode-lookalike digits never slip through.

## See Also

- [transform.md](transform.md) — escaping, hashing, fingerprinting
- [network.md](network.md) — same fail-closed strict-validation style
- [temporal.md](temporal.md) — exact decimal strings instead of floats, same philosophy
