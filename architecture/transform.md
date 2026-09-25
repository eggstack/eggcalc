# transform.py — Text Transformations

722 lines. Deterministic text transformations, escaping, hashing, and fingerprinting.

## Table of Contents

- [Overview](#overview)
- [Type Definitions](#type-definitions)
- [Constants / Limits](#constants--limits)
- [Public Functions](#public-functions)
  - [text_transform](#text_transform)
  - [escape_text](#escape_text)
  - [unescape_text](#unescape_text)
  - [text_hash](#text_hash)
  - [text_fingerprint](#text_fingerprint)
- [Internal Helpers](#internal-helpers)
- [Dependencies](#dependencies)
- [Security / DoS Notes](#security--dos-notes)
- [See Also](#see-also)
- [Usage Example](#usage-example)

## Overview

Provides explicit, auditable text operations with no I/O:

- Unicode normalization (`NFC`/`NFD`/`NFKC`/`NFKD`), casefolding, trimming
- Newline normalization (`CRLF`/`CR` → `LF`), final-newline ensure/strip
- Invisible-character removal (zero-width set, bidi-control set)
- `visible_repr` delegation (marks invisibles visibly instead of deleting)
- Escaping for 9 output formats and unescaping for 4 input formats
- Cryptographic hashing (`sha256`, `sha1`, `md5`, `crc32`) and SHA-256 fingerprinting with canonicalization options

**Key principles:** deterministic, pure (no filesystem, network, or LLM calls), stdlib-only.
Only explicitly requested operations run. Unknown `text_transform` operation names are
silently ignored by design. Results are plain-dict TypedDicts — use `result["text"]`,
never `result.text`.

## Type Definitions

### RemovedChar (TypedDict)

```python
class RemovedChar(TypedDict):
    index: int      # 0-based index in the pre-removal text
    char: str       # the removed character itself
    codepoint: str  # "U+XXXX" hex form
    name: str       # Unicode name from the removal table (e.g. "ZERO WIDTH SPACE")
```

### TextTransformResult (TypedDict)

```python
class TextTransformResult(TypedDict):
    changed: bool                    # True iff output text != input text
    text: str                        # transformed text
    operations_applied: list[str]    # only ops that actually changed text (lowercase names)
    removed: list[RemovedChar]       # chars removed by remove_zero_width / remove_bidi_controls
    warnings: list[str]              # one entry per removal op that removed >= 1 char
    summary: str                     # "No operations requested" | "No recognized operations applied" | "Applied N operation(s): ...; text changed|unchanged"
```

### EscapeTextResult (TypedDict)

```python
class EscapeTextResult(TypedDict):
    mode: str       # echo of the requested mode
    escaped: str    # escaped output (often wrapped, e.g. quotes or fences)
    changed: bool   # escaped != input
    summary: str    # "Escaped text as <human-readable mode name>"
```

### UnescapeTextResult (TypedDict)

```python
class UnescapeTextResult(TypedDict):
    mode: str            # echo of the requested mode
    unescaped: str       # unescaped output, or the original text on failure
    changed: bool        # unescaped != input
    error: str | None    # failure reason, else None (decode errors do NOT raise)
    summary: str         # "Unescaped <mode>" or "Failed to unescape <mode>: <error>"
```

### TextHashResult (TypedDict)

```python
class TextHashResult(TypedDict):
    encoding: str            # echo of the encoding argument
    bytes: int               # len(text.encode(encoding))
    codepoints: int          # len(text)
    hashes: dict[str, str]   # computed digests keyed by lowercase algo name
    warnings: list[str]      # MD5 notice + one entry per unknown algorithm
    summary: str             # singular ("SHA256 computed for N ... bytes") or plural ("Computed N hashes for ...")
```

### TextFingerprintResult (TypedDict)

```python
class TextFingerprintResult(TypedDict):
    sha256: str                          # hex SHA-256 of the canonicalized text (UTF-8)
    bytes_utf8: int                      # len(canonical.encode("utf-8"))
    codepoints: int                      # len(canonical)
    graphemes: int                       # count_graphemes(canonical)
    newline_style: str                   # "none" | "LF" | "CRLF" | "CR" | "mixed" (of the ORIGINAL text)
    normalization: dict[str, str | bool] # {"input_is_nfc": bool, "applied": unicode}
    summary: str                         # "SHA-256 fingerprint computed for N codepoints"
```

## Constants / Limits

No `MAX_*` input cap exists in this module — inputs are unbounded (see Security notes).

```python
_VALID_OPERATIONS = {
    "normalize_nfc", "normalize_nfd", "normalize_nfkc", "normalize_nfkd",
    "casefold", "trim", "trim_trailing_whitespace",
    "normalize_newlines_lf", "ensure_final_newline", "strip_final_newline",
    "remove_zero_width", "remove_bidi_controls", "visible_repr",
}  # 13 ops; matched case-insensitively via op.lower()

_ZERO_WIDTH_CHARS = {
    "\u200b": "ZERO WIDTH SPACE",
    "\u200c": "ZERO WIDTH NON-JOINER",
    "\u200d": "ZERO WIDTH JOINER",
    "\u2060": "WORD JOINER",
}

_BIDI_CONTROL_CHARS = {
    "\u202a": "LEFT-TO-RIGHT EMBEDDING",
    "\u202b": "RIGHT-TO-LEFT EMBEDDING",
    "\u202c": "POP DIRECTIONAL FORMATTING",
    "\u202d": "LEFT-TO-RIGHT OVERRIDE",
    "\u202e": "RIGHT-TO-LEFT OVERRIDE",
    "\u2066": "LEFT-TO-RIGHT ISOLATE",
    "\u2067": "RIGHT-TO-LEFT ISOLATE",
    "\u2068": "FIRST STRONG ISOLATE",
    "\u2069": "POP DIRECTIONAL ISOLATE",
}

_VALID_ESCAPE_MODES = {
    "json_string", "python_string", "rust_string", "posix_shell_single",
    "regex_literal", "markdown_inline_code", "markdown_code_block",
    "html_text", "url_component",
}

_VALID_UNESCAPE_MODES = {"json_string", "python_string", "unicode_escape", "url_component"}

_SUPPORTED_HASH_ALGORITHMS = {"sha256", "sha1", "md5", "crc32"}
```

`detail` for `text_transform` accepts `"summary"` (suppresses the `removed` list),
`"full"` and `"normal"` (both return the full `removed` list).

## Public Functions

### `text_transform`

```python
def text_transform(text: str, operations: list[str], detail: str = "normal") -> TextTransformResult
```

Applies the requested operations in list order. An op is recorded in
`operations_applied` only when it changes the text. `changed` compares final vs
original text.

Verified examples (via `.venv/bin/python`):

```python
text_transform("  hello  ", ["trim"])["text"]            # → 'hello'
text_transform("café", ["normalize_nfc"])["text"]       # → 'café' (composes e + U+0301)
text_transform("ﬁ", ["normalize_nfkc"])["text"]          # → 'fi' (compatibility fold)
text_transform("HELLO", ["casefold"])["text"]            # → 'hello'
text_transform("a\r\nb\rc", ["normalize_newlines_lf"])["text"]  # → 'a\nb\nc'
text_transform("hi  \nbye  ", ["trim_trailing_whitespace"])["text"]  # → 'hi\nbye'
text_transform("hi", ["ensure_final_newline"])["text"]   # → 'hi\n'
text_transform("hi\n", ["strip_final_newline"])["text"]  # → 'hi' (strips ONE trailing \n)
text_transform("a\u200bb", ["remove_zero_width"])
# → {"changed": True, "text": "ab", "operations_applied": ["remove_zero_width"],
#     "removed": [{"index": 1, "char": "\u200b", "codepoint": "U+200B", "name": "ZERO WIDTH SPACE"}],
#     "warnings": ["Removed 1 invisible/zero-width character(s): ZERO WIDTH SPACE"], ...}
text_transform("a\u202eb", ["remove_bidi_controls"])["operations_applied"]  # → ['remove_bidi_controls']
text_transform("", [])["summary"]        # → 'No operations requested'
text_transform("hi", ["unknown_op"])["summary"]  # → 'No recognized operations applied'
text_transform("hi\n", ["ensure_final_newline"])["operations_applied"]  # → [] (already ends with \n)
```

**Edge cases:**

- Op names are case-insensitive (`"TRIM"` works); unknown names are silently skipped.
- `ensure_final_newline` on `"hi\n\n"` is a no-op (code explicitly passes; only appends when missing).
- `strip_final_newline` strips exactly one trailing `"\n"` (`"hi\n\n"` → `"hi\n"`).
- `detail="summary"` returns `"removed": []` even when chars were removed (warnings still present);
  `"normal"` and `"full"` both return the full list (no truncation).
- `visible_repr` delegates to `primitives.visible_repr` and is recorded only if it changes text.

### `escape_text`

```python
def escape_text(text: str, mode: str) -> EscapeTextResult
```

**Raises:** `ValueError` for an unsupported mode.

| Mode | Behavior | Verified example |
|------|----------|------------------|
| `json_string` | `json.dumps(text)` (double-quoted) | `escape_text('a"b\nc', "json_string")["escaped"]` → `'"a\\"b\\nc"'` |
| `python_string` | Single-quoted literal; escapes `\\`, `'`, `\n`, `\r`, `\t`, `Cc < 0x20` / `0x7F` as `\xNN` | `escape_text("x", "python_string")["escaped"]` → `"'x'"` |
| `rust_string` | Double-quoted; escapes `\\`, `"`, `\n`, `\r`, `\t` | `escape_text("x", "rust_string")["escaped"]` → `'"x"'` |
| `posix_shell_single` | Wraps in `'...'`; each `'` becomes `'\''` | `escape_text("it's", "posix_shell_single")["escaped"]` → `"'it'\\''s'"` |
| `regex_literal` | `re.escape(text)` | `escape_text("a.b*c", "regex_literal")["escaped"]` → `'a\\.b\\*c'` |
| `markdown_inline_code` | Wraps in backticks; fence length = longest run + 1, padded with spaces when a run exists | `escape_text("code", ...)["escaped"]` → `` '`code`' ``; `escape_text("a`b", ...)["escaped"]` → `'`` a`b ``'` |
| `markdown_code_block` | `"```\n" + text + "\n```"` (no language tag, no fence escaping) | `escape_text("body", "markdown_code_block")["escaped"]` → `'```\nbody\n```'` |
| `html_text` | `&` → `&amp;`, `<` → `&lt;`, `>` → `&gt;`, `"` → `&quot;`, `'` → `&#39;` (in that order) | `escape_text("<a>&", "html_text")["escaped"]` → `'&lt;a&gt;&amp;'` |
| `url_component` | `urllib.parse.quote(text, safe="")` | `escape_text("a b/c", "url_component")["escaped"]` → `'a%20b%2Fc'` |

**Edge cases:** output is almost always `changed=True` (wrapping alone counts as a change).
`html_text` escapes `&` first so existing entities double-escape (`"&amp;"` → `"&amp;amp;"`).
`markdown_code_block` does not escape inner triple-backtick runs.

### `unescape_text`

```python
def unescape_text(text: str, mode: str) -> UnescapeTextResult
```

**Raises:** `ValueError` only for an unsupported mode. Decode failures are returned
as `{"unescaped": <original>, "changed": False, "error": <reason>}` — never raised.

| Mode | Behavior | Verified example |
|------|----------|------------------|
| `json_string` | Requires surrounding double quotes; `json.loads` | `unescape_text('"hello"', "json_string")["unescaped"]` → `'hello'`; `unescape_text("not quoted", "json_string")["error"]` → `'Invalid JSON string literal: must be wrapped in double quotes'` |
| `python_string` | `ast.literal_eval` (safe; accepts `'...'` and `"..."`) | `unescape_text("'a\\nb'", "python_string")["unescaped"]` → `'a\nb'` |
| `unicode_escape` | Replaces `\uXXXX` then `\UXXXXXXXX`; anything else left untouched | `unescape_text("A", "unicode_escape")["unescaped"]` → `'A'` (unchanged, `changed=False`) |
| `url_component` | `urllib.parse.unquote` | `unescape_text("hello%20world", "url_component")["unescaped"]` → `'hello world'` |

**Edge cases:** `unicode_escape` does not handle `\n`, `\xNN`, or lone surrogates specially —
only the two `\u`/`\U` patterns. `python_string` errors surface the `literal_eval`
message prefixed with `"Invalid Python string literal: "`.

### `text_hash`

```python
def text_hash(
    text: str,
    algorithms: Sequence[str] = ("sha256",),
    encoding: str = "utf-8",
) -> TextHashResult
```

Encodes with `text.encode(encoding)` (raises `LookupError`/`UnicodeError` for bad
encodings — not wrapped). Algorithm names are matched case-insensitively.

Verified examples:

```python
text_hash("hello", ["sha256"])["hashes"]
# → {'sha256': '2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824'}
text_hash("hello", ["sha256", "md5", "crc32", "bogus"])
# → hashes has sha256 + md5 ('5d41402abc4b2a76b9719d911017c592') + crc32 ('3610a686');
#   warnings == ['MD5 is non-cryptographic and provided for compatibility only',
#                "Unknown algorithm 'bogus', skipping (supported: crc32, md5, sha1, sha256)"];
#   summary == 'Computed 3 hashes for 5 utf-8 bytes'
text_hash("hello")["encoding"]  # → 'utf-8' (default, single sha256)
```

**Edge cases:** `sha1` uses `hashlib.sha1`; `crc32` is `format(zlib.crc32(encoded), "08x")`
(non-cryptographic checksum, zero-padded to 8 hex chars). The MD5 warning is appended
once even if `"md5"` is listed twice. Unknown algorithms contribute a warning but no
`hashes` entry, and still count toward neither the digest total in `summary`.

### `text_fingerprint`

```python
def text_fingerprint(
    text: str,
    unicode: str = "raw",
    newline: str = "raw",
    trim_final_newline: bool = False,
    casefold: bool = False,
) -> TextFingerprintResult
```

Canonicalizes a copy (`unicode` normalization unless `"raw"`; `CRLF`/`CR` → `LF` when
`newline="LF"`; strip one trailing `"\n"` when `trim_final_newline`; `casefold()` when
`casefold=True`), then SHA-256 hashes the canonical UTF-8 bytes. Metrics describe the
**canonical** text; `newline_style` and `normalization["input_is_nfc"]` describe the
**original** text (`newline_style` delegates to `primitives.detect_newline_style`,
so mixed endings report `"mixed"`; `"none"` when no `\n`/`\r` present).

Verified examples:

```python
text_fingerprint("Hello\n")["sha256"]  # → '66a045b452102c59d840ec097d59d9467e13a3f34f6494e539ffd32c1bb35f18'
text_fingerprint("Hello\n")["newline_style"]   # → 'LF'
text_fingerprint("Hello\n")["normalization"]   # → {'input_is_nfc': True, 'applied': 'raw'}
text_fingerprint("Hello\n", unicode="NFC", newline="LF", trim_final_newline=True, casefold=True)["sha256"]
# → '2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824' (== sha256("hello"))
```

**Edge cases:** `unicode` is passed unchecked to `unicodedata.normalize` — an invalid
form raises `ValueError`. `newline` only recognizes `"LF"`; any other value means raw.

## Internal Helpers

- `_get_char_name(char) -> str` — `unicodedata.name` with `f"U+{ord(c):04X}"` fallback.
- `_remove_chars(text, chars_to_remove, operation_name)` — index-preserving removal loop;
  builds `RemovedChar` entries and a single `"Removed N invisible/<op> character(s): <names>"` warning.
- `_escape_json_string` (`json.dumps`), `_escape_python_string` (manual per-char escaper),
  `_escape_rust_string`, `_escape_posix_shell_single`, `_escape_regex_literal` (`re.escape`),
  `_escape_markdown_inline_code` (longest-backtick-run fence), `_escape_markdown_code_block`,
  `_escape_html_text` (ordered `&` → `<` → `>` → `"` → `'`), `_escape_url_component`.
- `_unescape_json_string` (double-quote guard + `json.loads`), `_unescape_python_string`
  (`ast.literal_eval` → `ValueError`), `_unescape_unicode_escape` (two `re.sub` passes),
  `_unescape_url_component`.

## Dependencies

```
transform.py
    ├── stdlib: ast, hashlib, json, re, unicodedata, zlib, urllib.parse, collections.abc, typing
    └── exact (lazy, inside function bodies — never top-level):
            .primitives.visible_repr        (text_transform "visible_repr" op)
            .primitives.count_graphemes     (text_fingerprint grapheme count)
            .primitives.detect_newline_style (text_fingerprint newline_style)
```

Top-level imports stay stdlib-only so the single-file build is unaffected; the
`urllib.parse` import has a `try/except ImportError` fallback that raises `ValueError`
at call time if unavailable.

## Security / DoS Notes

- **No input caps:** unlike `config.py` (`MAX_TEXT_INPUT_length = 100_000`) and `patch.py`
  (`MAX_PATCH_LENGTH = 200_000`), this module enforces no length limit. Hashing and
  normalization are linear, but callers feeding unbounded user input should cap length
  first (CPU/memory proportional to input size).
- `md5` is offered for compatibility only and emits a warning; do not use for security
  decisions. `crc32` is a checksum, not a hash.
- `ast.literal_eval` (python_string unescape) is safe against code execution, unlike `eval`.
- `url_component` uses `safe=""`, so `/`, `?`, `&` are all percent-encoded — safe to embed
  in a single path segment or query value.
- `regex_literal` output is safe to embed as a literal via `re.escape`, but callers must
  still bound pattern length before compiling.

## See Also

- [primitives.md](primitives.md) — `visible_repr`, `count_graphemes`, `detect_newline_style` (delegated here); `normalize_unicode`, `casefold_text`
- [encoding.md](encoding.md) — adjacent hashing/encoding utilities
- [exact.md](exact.md) — package-level overview

## Usage Example

```python
from eggcalc.exact.transform import (
    text_transform, escape_text, unescape_text, text_hash, text_fingerprint,
)

# Auditable cleanup pipeline
r = text_transform("  Héllo\u200b\r\n", ["trim", "normalize_nfc", "normalize_newlines_lf", "remove_zero_width"])
print(r["text"])                # 'Héllo\n'
print(r["operations_applied"])  # ['trim', 'normalize_nfc', 'normalize_newlines_lf', 'remove_zero_width']
print(r["removed"][0]["name"])  # 'ZERO WIDTH SPACE'

# Format-safe embedding
print(escape_text("<hi> & 'bye'", "html_text")["escaped"])  # '&lt;hi&gt; &amp; &#39;bye&#39;'
print(unescape_text('"hi"', "json_string")["unescaped"])    # 'hi'

# Identity checks
print(text_hash("hello", ["sha256"])["hashes"]["sha256"])  # 2cf24dba...
fp = text_fingerprint("Hello\n", unicode="NFC", newline="LF", trim_final_newline=True, casefold=True)
print(fp["sha256"])          # sha256("hello")
print(fp["newline_style"])   # 'LF'
```

(End of file - total 722 lines implementation)
