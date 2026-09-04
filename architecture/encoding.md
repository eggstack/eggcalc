# encoding.py — Codec and Radix Conversion

282 lines. Deterministic text-codec and integer-radix conversion with strict input validation.

## Overview

Pure, side-effect-free conversion between `utf8`, `hex`, `base64`, and `base64url` codecs, plus signed-magnitude integer conversion between bases 2–36. No network I/O, filesystem access, locale dependence, or platform-specific behavior.

Base64 inputs are validated against explicit alphabet, padding, and length rules before `base64.b64decode(..., validate=True)` runs, so whitespace, mixed alphabets, misplaced padding, and invalid lengths are rejected. Radix magnitudes are capped at `2**128 - 1` for cross-implementation parity even though Python integers are unbounded.

## Key Exports

```python
from eggcalc.exact.encoding import (
    codec_convert,
    radix_convert,
)
```

## Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `codec_convert(value, from_format, to_format)` | `CodecConvertResult` | Convert between `utf8`/`hex`/`base64`/`base64url`; canonical outputs, payload byte length |
| `radix_convert(value, from_base, to_base, uppercase=False)` | `RadixConvertResult` | Convert signed ASCII integer text between bases 2–36 with `u128` magnitude cap |

## CodecConvertResult TypedDict

```python
CodecConvertResult(
    value=str,          # Canonical converted text
    from=str,           # Source format (functional-syntax key: "from" is a keyword)
    to=str,             # Destination format
    byte_length=int,    # Decoded payload length in bytes (not input length)
)
```

Codec contract: exactly `utf8`, `hex`, `base64`, `base64url` (no aliases, case-sensitive). Hex requires even length and ASCII hex only (no `0x`, no whitespace). Standard Base64 output is padded; Base64URL output is unpadded; hex output is lowercase; `utf8` destinations decode strictly. Encoded input and converted output are both bounded by `MAX_TEXT_INPUT_LENGTH` (100,000).

## RadixConvertResult TypedDict

```python
RadixConvertResult(
    value=str,               # Canonical value: no "+", no leading zeroes, "-" only if negative and nonzero
    from_base=int,
    to_base=int,
    uppercase=bool,
    negative=bool,
    magnitude_decimal=str,   # Exact decimal magnitude
)
```

Grammar: optional single leading `+`/`-`, then one or more ASCII digits valid in `from_base` (whitespace, underscores, `0x`/`0o`/`0b` prefixes, decimal points, exponents, and Unicode digits rejected). Negative zero normalizes to non-negative zero. Magnitudes above `340282366920938463463374607431768211455` (`2**128 - 1`) raise `ValueError`.

## Module Dependencies

- `base64`, `typing` (`binascii.Error` needs no import: it subclasses `ValueError`)
