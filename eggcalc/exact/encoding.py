"""Deterministic codec and radix conversion tools.

Provides pure, side-effect-free conversion between text encodings
(UTF-8, hexadecimal, standard Base64, URL-safe Base64) and between integer
radixes (bases 2-36). No network I/O, filesystem access, or locale-dependent
behavior is involved.

Base64 parsing is strict: inputs are validated against the explicit
alphabet, padding, and length rules before decoding, so whitespace, mixed
alphabets, misplaced padding, and invalid lengths are rejected rather than
silently accepted. Radix magnitudes are capped at ``2**128 - 1`` to preserve
cross-implementation parity even though Python integers are unbounded.
"""

from __future__ import annotations

import base64
from typing import TypedDict

MAX_TEXT_INPUT_LENGTH = 100_000

_CODEC_FORMATS = ("utf8", "hex", "base64", "base64url")

CodecConvertResult = TypedDict(
    "CodecConvertResult",
    {"value": str, "from": str, "to": str, "byte_length": int},
)


class RadixConvertResult(TypedDict):
    """Result of converting an integer between radixes."""

    value: str
    from_base: int
    to_base: int
    uppercase: bool
    negative: bool
    magnitude_decimal: str


_DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz"
_DIGIT_VALUES = {ch: idx for idx, ch in enumerate(_DIGITS)}

_HEX_CHARS = frozenset("0123456789abcdefABCDEF")
_B64_STD_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/")
_B64_URL_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")

_MAX_U128 = (1 << 128) - 1
_MAX_U128_DECIMAL = "340282366920938463463374607431768211455"


def _check_text_length(value: str, name: str) -> None:
    """Reject inputs beyond the shared exact text ceiling."""
    if len(value) > MAX_TEXT_INPUT_LENGTH:
        raise ValueError(
            f"Input {name} length {len(value)} exceeds maximum {MAX_TEXT_INPUT_LENGTH}"
        )


def _check_format(name: str) -> str:
    """Validate a codec format name, returning it unchanged."""
    if name not in _CODEC_FORMATS:
        raise ValueError(
            f"unsupported codec format: {name!r} (expected one of {', '.join(_CODEC_FORMATS)})"
        )
    return name


def _decode_hex(value: str) -> bytes:
    """Decode strict lowercase-or-uppercase hex with no prefixes/whitespace."""
    if len(value) % 2 != 0:
        raise ValueError("invalid hex input: length must be even")
    if value and (not value.isascii() or any(ch not in _HEX_CHARS for ch in value)):
        raise ValueError("invalid hex input: only ASCII hexadecimal characters allowed")
    try:
        return bytes.fromhex(value)
    except ValueError as exc:
        raise ValueError(f"invalid hex input: {value!r}") from exc


def _validate_base64(value: str, url_safe: bool) -> str:
    """Validate strict Base64 input, returning it with decoding padding added.

    Rejects whitespace, mixed alphabets, internal padding, more than two
    terminal padding characters, invalid modulo-4 lengths, and incorrect
    padding counts. Canonical unpadded input is accepted; padding needed only
    for decoding is added internally after validation.
    """
    allowed = _B64_URL_CHARS if url_safe else _B64_STD_CHARS
    wrong_alphabet = _B64_STD_CHARS if url_safe else _B64_URL_CHARS
    kind = "base64url" if url_safe else "base64"
    if not value.isascii() or any(ch not in allowed and ch != "=" for ch in value):
        if any(ch in wrong_alphabet for ch in value):
            raise ValueError(f"invalid {kind} input: mixed alphabets are rejected")
        raise ValueError(f"invalid {kind} input: characters outside the {kind} alphabet")
    if "=" in value:
        core = value.rstrip("=")
        padding = len(value) - len(core)
        if "=" in core:
            raise ValueError(f"invalid {kind} input: misplaced '=' padding")
        if padding > 2:
            raise ValueError(f"invalid {kind} input: more than two terminal '=' characters")
        if not core:
            raise ValueError(f"invalid {kind} input: padding without encoded data")
        if len(value) % 4 != 0:
            raise ValueError(f"invalid {kind} input: incorrect padded length")
        return value
    if len(value) % 4 == 1:
        raise ValueError(f"invalid {kind} input: invalid length")
    return value + "=" * (-len(value) % 4)


def _decode_base64(value: str, url_safe: bool) -> bytes:
    """Decode strictly validated standard or URL-safe Base64 input."""
    kind = "base64url" if url_safe else "base64"
    padded = _validate_base64(value, url_safe)
    altchars = b"-_" if url_safe else None
    try:
        return base64.b64decode(padded, altchars=altchars, validate=True)
    except ValueError as exc:
        raise ValueError(f"invalid {kind} input: {value!r}") from exc


def codec_convert(value: str, from_format: str, to_format: str) -> CodecConvertResult:
    """Convert text between utf8, hex, base64, and base64url codecs.

    Args:
        value: Encoded input text in the source format.
        from_format: Source format (``"utf8"``, ``"hex"``, ``"base64"``,
            ``"base64url"``). No aliases or case-insensitive spellings.
        to_format: Destination format (same vocabulary).

    Returns:
        CodecConvertResult with the canonical converted text, the resolved
        ``from``/``to`` formats, and the decoded payload length in bytes.
        Standard Base64 output is padded; Base64URL output is unpadded;
        hex output is lowercase ASCII; ``utf8`` output is strict UTF-8.

    Raises:
        ValueError: If a format is unsupported, the input exceeds the text
            ceiling, decoding fails (odd-length/non-ASCII hex, malformed
            Base64, invalid UTF-8 destination), or the output exceeds the
            text ceiling.

    Examples:
        >>> codec_convert("Hello", "utf8", "hex")["value"]
        '48656c6c6f'
        >>> codec_convert("48656c6c6f", "hex", "base64")["value"]
        'SGVsbG8='
    """
    if not isinstance(value, str):
        raise ValueError(f"value must be a string, got {type(value).__name__}")
    _check_text_length(value, "'value'")
    source = _check_format(from_format)
    dest = _check_format(to_format)
    if source == "utf8":
        payload = value.encode("utf-8")
    elif source == "hex":
        payload = _decode_hex(value)
    elif source == "base64":
        payload = _decode_base64(value, url_safe=False)
    else:
        payload = _decode_base64(value, url_safe=True)
    if dest == "utf8":
        try:
            converted = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("invalid utf8 output: decoded bytes are not valid UTF-8") from exc
    elif dest == "hex":
        converted = payload.hex()
    elif dest == "base64":
        converted = base64.b64encode(payload).decode("ascii")
    else:
        converted = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    if len(converted) > MAX_TEXT_INPUT_LENGTH:
        raise ValueError(f"Output length {len(converted)} exceeds maximum {MAX_TEXT_INPUT_LENGTH}")
    result: CodecConvertResult = {
        "value": converted,
        "from": source,
        "to": dest,
        "byte_length": len(payload),
    }
    return result


def _max_digits_for_base(base: int) -> int:
    """Return a digit count above which any value exceeds 2**128 - 1."""
    bits = 0
    width = base
    while width <= _MAX_U128:
        width *= base
        bits += 1
    return bits + 2


def radix_convert(
    value: str, from_base: int, to_base: int, uppercase: bool = False
) -> RadixConvertResult:
    """Convert a signed-magnitude integer between bases 2 and 36.

    The input is an optional single leading ``+``/``-`` followed by at least
    one ASCII digit; magnitude is capped at ``2**128 - 1``.

    Args:
        value: Integer text such as ``"-ff"``, ``"+101"``, ``"z"``.
        from_base: Source base, an integer in 2..=36.
        to_base: Destination base, an integer in 2..=36.
        uppercase: Use uppercase ``A-Z`` digits instead of lowercase.

    Returns:
        RadixConvertResult with the canonical converted value (no leading
        ``+``, no leading zeroes, leading ``-`` only for nonzero negative
        inputs), the bases, the uppercase flag, the negative flag, and the
        decimal magnitude string. Negative zero normalizes to zero.

    Raises:
        ValueError: If the grammar, bases, digits, or magnitude are invalid,
            or the input exceeds the text ceiling.

    Examples:
        >>> radix_convert("-ff", 16, 2)["value"]
        '-11111111'
        >>> radix_convert("+0", 10, 16)["negative"]
        False
    """
    if not isinstance(value, str):
        raise ValueError(f"value must be a string, got {type(value).__name__}")
    _check_text_length(value, "'value'")
    for name, base in (("from_base", from_base), ("to_base", to_base)):
        if not isinstance(base, int) or isinstance(base, bool):
            raise ValueError(f"{name} must be an integer in 2..=36, got {base!r}")
        if base < 2 or base > 36:
            raise ValueError(f"{name} must be an integer in 2..=36, got {base!r}")
    upper = bool(uppercase)
    body = value
    negative = False
    if body.startswith(("+", "-")):
        negative = body.startswith("-")
        body = body[1:]
    if not body or not body.isascii():
        raise ValueError(f"invalid base-{from_base} integer: {value!r}")
    if any(ch.lower() not in _DIGIT_VALUES for ch in body):
        raise ValueError(f"invalid base-{from_base} integer: {value!r}")
    digits: list[int] = []
    for ch in body:
        digit = _DIGIT_VALUES[ch.lower()]
        if digit >= from_base:
            raise ValueError(f"invalid base-{from_base} integer: {value!r}")
        digits.append(digit)
    if len(digits) > _max_digits_for_base(from_base):
        raise ValueError(
            f"magnitude exceeds maximum {_MAX_U128_DECIMAL} for base-{from_base} integer"
        )
    magnitude = 0
    for digit in digits:
        magnitude = magnitude * from_base + digit
    if magnitude > _MAX_U128:
        raise ValueError(
            f"magnitude exceeds maximum {_MAX_U128_DECIMAL} for base-{from_base} integer"
        )
    if magnitude == 0:
        negative = False
        converted = "0"
    else:
        parts: list[str] = []
        remainder = magnitude
        while remainder:
            remainder, digit = divmod(remainder, to_base)
            parts.append(_DIGITS[digit])
        converted = "".join(reversed(parts))
        if upper:
            converted = converted.upper()
        if negative:
            converted = "-" + converted
    return RadixConvertResult(
        value=converted,
        from_base=from_base,
        to_base=to_base,
        uppercase=upper,
        negative=negative,
        magnitude_decimal=str(magnitude),
    )
