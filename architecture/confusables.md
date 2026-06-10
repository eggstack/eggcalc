# confusables.py - Homoglyph Identification Table

## Purpose

Contains the confusables table derived from Unicode Standard Annex #39 for detecting homoglyph attacks.

## Data Source

The confusables table is generated from the official Unicode `confusables.txt` file available at:
https://www.unicode.org/Public/security/latest/confusables.txt

## Data Structure

```python
CONFUSABLES: dict[str, str] = {
    # key: "U+XXXX" (codepoint of confusable character)
    # value: space-separated codepoints of the confusable sequence
    #        (single or multi-codepoint substitution)
    "U+0430": "U+0061",            # Cyrillic 'а' → Latin 'a'
    "U+0022": "U+0027 U+0027",    # quotation mark → two apostrophes
    "U+0025": "U+00BA U+002F U+2080",  # percent sign → 'º/₀'
    "U+00C6": "U+0041 U+0045",    # 'Æ' → 'AE'
    "U+00D8": "U+004F U+0338",    # 'Ø' → 'O' + combining solidus
    ...
}
```

## How Confusables Work

Each entry maps a character to its confusable sequence. The value may contain multiple codepoints. For example:
- `U+0430` (Cyrillic small letter A) → `U+0061` (Latin small letter A) — 1:1
- `U+00C6` (Latin AE) → `U+0041 U+0045` (Latin A + E) — 1:2 decomposition

When `unicode_tools.detect_confusables()` scans text, it looks up each character in this table.

## Generating the Table

The `confusables.py` file is auto-generated data (approximately 176KB, 6580 lines). It contains only the `CONFUSABLES` dictionary mapping characters to their confusable equivalents. The file is maintained as a static data file and should not be edited manually.

## Security Applications

This table enables detection of:
- **Homoglyph attacks**: "pаypal" (Cyrillic 'а') looks like "paypal"
- **IDN homograph attacks**: Internationalized domain names using visually identical characters
- **Social engineering**: Using similar-looking characters to mislead users

## Index

See [overview.md](overview.md) for the module index.