# Network and Encoding Utility Parity

Status: planned  
Repository: `eggstack/eggcalc`  
Baseline reviewed: `07e0d66c29bdc7a9ab6d5a41033b372b4cec1994`  
Date: 2026-09-04  
Depends on: `plans/029-eggsact-deterministic-utility-parity-roadmap.md`

## 1. Purpose

Implement the four low-complexity deterministic utilities added recently to eggsact:

- `ip_inspect`
- `cidr_inspect`
- `codec_convert`
- `radix_convert`

The implementation must be native Python standard-library code, fit the existing `eggcalc.exact` architecture, and preserve the reviewed eggsact contract without importing or depending on eggsact at runtime.

This plan intentionally stops before temporal/cron work and before final MCP/build/documentation closure. Those are handled by Plans 031 and 032.

## 2. Governing constraints

- Runtime remains standard-library-only.
- Add no network I/O, DNS, filesystem access, environment dependence, locale dependence, or platform-specific behavior.
- Keep the utilities pure and deterministic.
- Reuse existing eggcalc input/resource-limit conventions rather than inventing a second budgeting system.
- Use Python 3.11-compatible APIs only.
- Preserve eggsact's bounded external behavior where Python would otherwise be more permissive or more capable.
- Do not broaden these functions into generalized networking or binary-processing libraries.
- New exact modules must be compatible with `build_single.py`; final manifest integration is Plan 032.

## 3. File ownership

Create:

```text
eggcalc/exact/network.py
eggcalc/exact/encoding.py
```

Keep networking helpers private to `network.py` and encoding/radix helpers private to `encoding.py`. Do not create a generic utility/helper module merely to share trivial validation logic.

The final public exact API may lazily expose the six named tool functions, but this plan only needs to establish the four direct module functions cleanly. Plan 032 owns final export/MCP registration.

## 4. Workstream A - `ip_inspect`

### A1. Parsing and canonicalization

Use `ipaddress.ip_address(address)` for syntactic validation and canonical formatting.

Return the reviewed eggsact fields:

```text
address       canonical address text
family        "ipv4" or "ipv6"
bytes_hex     packed bytes as lowercase hex, no separators
numeric       exact unsigned integer value as decimal string
special_use   sorted list of explicit tags
ipv4_mapped   object or None
```

For mapped IPv6, the object should preserve the eggsact meaning:

```json
{
  "address": "192.0.2.1",
  "numeric": "3221225985"
}
```

### A2. Explicit special-use taxonomy

Do not implement `special_use` as a projection of `ipaddress.is_private`, `is_global`, or similar version-sensitive convenience properties.

Implement the reviewed eggsact ranges explicitly.

IPv4 tags:

- `unspecified`: `0.0.0.0`
- `loopback`: `127.0.0.0/8`
- `private`: `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`
- `link_local`: `169.254.0.0/16`
- `multicast`: `224.0.0.0/4`
- `documentation`: `192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`
- `shared`: `100.64.0.0/10`

IPv6 tags:

- `unspecified`: `::`
- `loopback`: `::1`
- `link_local`: `fe80::/10`
- `unique_local`: `fc00::/7`
- `multicast`: `ff00::/8`
- `documentation`: `2001:db8::/32`
- `ipv4_mapped`: only `::ffff:0:0/96`

Sort tags lexicographically before returning them so the result is stable independent of detection order.

### A3. IPv4-mapped correctness

Do not classify all low-valued IPv6 addresses as mapped. `::1`, `::192.0.2.1`, `::`, and `2001:db8::1` must not produce mapped metadata.

Use an explicit `::ffff:0:0/96` prefix test or an equivalent exact integer mask. `IPv6Address.ipv4_mapped` may be used only after verifying its Python 3.11 semantics match the required prefix contract; add regression tests either way.

## 5. Workstream B - `cidr_inspect`

### B1. Input grammar

Require one and only one `/` separator and a decimal, non-negative prefix with no sign or whitespace syntax accepted inside the prefix token.

Do not allow Python's parser to broaden the visible grammar accidentally. Normalize the parsed address/network only after validating the high-level input shape.

Use `ipaddress.ip_network(..., strict=False)` or equivalent integer arithmetic to canonicalize host-address CIDRs to their network boundary.

### B2. Output fields

Return:

```text
family
cidr
prefix_length
host_bits
network_address
netmask
first_address
last_address
broadcast_address
address_count
contains
contains_address
```

Semantics:

- `first_address` is the network address, not first conventionally usable host;
- `last_address` is the final address in the range;
- IPv4 `broadcast_address` equals the final address;
- IPv6 `broadcast_address` is `None`;
- `address_count` is an exact decimal string;
- `/0`, full-width host routes, and IPv6 `/128` must be exact;
- optional `contains` must use the same address family as the CIDR;
- `contains` is `None` when no candidate is supplied;
- `contains_address` returns the candidate's canonical address when supplied and valid.

Python arbitrary-precision arithmetic naturally supports `2**128`; do not introduce the Rust implementation's internal workaround into public behavior.

### B3. Edge cases

Cover at minimum:

```text
0.0.0.0/0
192.0.2.99/24
192.0.2.1/32
::/0
2001:db8::1/64
2001:db8::1/128
```

Reject:

- missing `/`;
- extra `/`;
- empty address or prefix;
- negative/signed/non-decimal prefix;
- prefix wider than address width;
- invalid candidate address;
- cross-family containment checks.

## 6. Workstream C - `codec_convert`

### C1. Supported formats

Support exactly:

```text
utf8
hex
base64
base64url
```

No aliases, case-insensitive spellings, Base32, Base85, URL percent encoding, compression, or file input.

### C2. Decode contract

`utf8` source:

- bytes are `value.encode("utf-8")`.

`hex` source:

- input length must be even;
- only ASCII hexadecimal characters are allowed;
- prefixes such as `0x` are rejected;
- whitespace is rejected.

`base64` / `base64url` source:

- validate alphabet explicitly before decoding;
- standard alphabet allows ASCII alphanumerics plus `+`, `/`, and terminal `=` padding;
- URL-safe alphabet allows ASCII alphanumerics plus `-`, `_`, and terminal `=` padding;
- reject mixed alphabets;
- reject whitespace;
- reject internal `=`;
- reject more than two terminal `=` characters;
- reject invalid modulo-4 lengths;
- allow canonical unpadded input by adding internal decoding padding only after validation;
- if padding is supplied, require its count and total length to be correct.

Use `base64.b64decode(..., validate=True)` and appropriate `altchars` only after those checks. Catch `binascii.Error` and convert to eggcalc's ordinary validation failure form.

### C3. Encode contract

`utf8` destination:

- decode bytes strictly as UTF-8; invalid sequences are rejected.

`hex` destination:

- lowercase ASCII hex.

`base64` destination:

- canonical standard Base64 with padding.

`base64url` destination:

- URL-safe Base64 without trailing `=` padding.

Return:

```text
value
from
to
byte_length
```

`byte_length` is the length of the decoded byte payload, not the input string length.

### C4. Resource bounds

Apply the existing exact/MCP text input ceiling to encoded input and to decoded/encoded output where required. A small encoded string must not be allowed to expand into output beyond the repository's ordinary bounded-text contract.

Do not create streaming APIs or temp files as a workaround for bounds.

## 7. Workstream D - `radix_convert`

### D1. Grammar

Accept an optional single leading `+` or `-`, followed by at least one ASCII digit from `0-9`, `a-z`, or `A-Z`.

Reject:

- whitespace;
- underscores;
- prefixes such as `0x`, `0o`, `0b`;
- decimal points;
- exponent notation;
- Unicode digits/letters outside ASCII;
- embedded signs.

`from_base` and `to_base` must be integers in `2..=36`.

### D2. Magnitude contract

Parse using checked semantics equivalent to eggsact's `u128` magnitude.

Although Python integers are arbitrary precision, reject magnitudes above:

```text
340282366920938463463374607431768211455
```

This retains cross-implementation parity and bounds resource use.

Negative zero canonicalizes to non-negative zero.

### D3. Output

Return:

```text
value
from_base
to_base
uppercase
negative
magnitude_decimal
```

Canonical output:

- no leading `+`;
- no leading zeroes except the value zero itself;
- lowercase digits `a-z` by default;
- uppercase `A-Z` when requested;
- leading `-` only when magnitude is nonzero and input sign was negative.

## 8. Types and API style

Follow existing `exact/` conventions:

- use `TypedDict` result declarations if neighboring modules expose structured typed results;
- prefer concrete dict values over new result classes;
- raise/return the same validation exception style used by comparable exact functions;
- keep internal helper names private;
- no global mutable state;
- no caches are necessary for these four utilities.

Do not create a generic `NetworkInspector`, `Codec`, or converter class.

## 9. Tests

Add one focused test module or a small pair grouped by implementation module. Avoid spreading one feature across many audit-style files.

Required success vectors include:

### Network

- canonical IPv4 and IPv6 text;
- packed byte hex and decimal numeric forms;
- each special-use boundary and one immediate nonmember where practical;
- true IPv4-mapped address in dotted and hexadecimal IPv6 notation;
- non-mapped low IPv6 addresses;
- CIDR normalization;
- IPv4 and IPv6 containment;
- address counts for IPv4 `/0`, IPv6 `/0`, `/128`.

### Encoding

- `"Hello"` UTF-8 -> hex -> Base64 -> Base64URL round trips;
- padded and unpadded valid Base64 input;
- canonical padded standard output;
- canonical unpadded URL-safe output;
- strict malformed-padding and mixed-alphabet rejection;
- invalid UTF-8 destination rejection.

### Radix

- signed hex -> binary;
- base 36 cases;
- uppercase output;
- `0`, `-0`, `+0` normalization;
- `2**128 - 1` accepted in decimal and hexadecimal;
- `2**128` rejected;
- invalid digits rejected according to selected base.

Where exact expected values already exist in the reviewed eggsact tests, transcribe them into static fixtures. Do not shell out to eggsact from the test suite.

## 10. Completion gate

Plan 030 is complete when:

- `eggcalc/exact/network.py` exists with both reviewed functions;
- `eggcalc/exact/encoding.py` exists with both reviewed functions;
- all four functions use only standard-library imports;
- explicit network classifications are version-stable;
- Base64 parsing is strict rather than convenience-parser permissive;
- radix magnitude is intentionally capped to eggsact's `u128` range;
- focused tests pass on supported Python;
- no unrelated CLI, evaluator, unit, MCP, or packaging behavior changes;
- no general-purpose abstraction was added beyond what the four tools require.

Final MCP registration, build manifest wiring, generated documentation, and package/single-file parity remain Plan 032 work and must not be declared complete here unless they are intentionally landed together in one implementation change.
