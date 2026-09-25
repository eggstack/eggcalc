# network.py — IP Address and CIDR Inspection

240 lines. Deterministic IP/CIDR inspection with an explicit,
version-stable special-use taxonomy. **Standalone leaf: stdlib-only,
no `exact/` dependencies.**

## Table of Contents

- [Overview](#overview)
- [Type Definitions](#type-definitions)
- [Constants / Limits](#constants--limits)
- [Public Functions](#public-functions)
  - [ip_inspect](#ip_inspect)
  - [cidr_inspect](#cidr_inspect)
- [Internal Helpers](#internal-helpers)
- [Dependencies](#dependencies)
- [Security Notes](#security-notes)
- [See Also](#see-also)

## Overview

Pure parsing and classification of IPv4/IPv6 addresses and CIDR ranges.
`ipaddress` handles syntactic validation and canonical formatting; an
explicit range table (not the version-sensitive `is_private`/`is_global`
convenience properties) assigns special-use tags, so standard-library
IANA-table updates cannot change deterministic output.

No network I/O, DNS lookups, filesystem access, or platform-specific
behavior.

## Type Definitions

```python
class Ipv4MappedInfo(TypedDict):
    address: str   # dotted-quad of the embedded IPv4 address
    numeric: str   # exact decimal value of the embedded address

class IpInspectResult(TypedDict):
    address: str                 # canonical address text
    family: str                  # "ipv4" | "ipv6"
    bytes_hex: str               # packed bytes, lowercase hex, no separators
    numeric: str                 # exact unsigned integer as decimal text
    special_use: list[str]       # sorted explicit tags (taxonomy below)
    ipv4_mapped: Ipv4MappedInfo | None

class CidrInspectResult(TypedDict):
    family: str
    cidr: str                    # canonical network CIDR (host bits cleared)
    prefix_length: int
    host_bits: int
    network_address: str
    netmask: str
    first_address: str           # network address (not first usable host)
    last_address: str            # final address in range
    broadcast_address: str | None  # final address for IPv4, None for IPv6
    address_count: str           # exact decimal text (arbitrary precision)
    contains: bool | None        # None when no candidate supplied
    contains_address: str | None # candidate canonical address when supplied
```

## Constants / Limits

```python
MAX_TEXT_INPUT_LENGTH = 100_000   # address/CIDR text cap (ValueError when exceeded)

_PREFIX_RE = re.compile(r"[0-9]+")  # ASCII-digit prefix grammar
```

Explicit special-use taxonomy (sorted lexicographically before return):

- IPv4: `unspecified` (`0.0.0.0`), `loopback` (`127.0.0.0/8`),
  `private` (RFC 1918 triple), `link_local` (`169.254.0.0/16`),
  `multicast` (`224.0.0.0/4`), `documentation` (TEST-NET-1/2/3),
  `shared` (`100.64.0.0/10`).
- IPv6: `unspecified` (`::`), `loopback` (`::1`),
  `link_local` (`fe80::/10`), `unique_local` (`fc00::/7`),
  `multicast` (`ff00::/8`), `documentation` (`2001:db8::/32`),
  `ipv4_mapped` (only `::ffff:0:0/96`, exact integer mask).

Input grammar: exactly one `/`, decimal non-negative ASCII-digit prefix
with no sign or whitespace. Over-wide prefixes, invalid candidates, and
cross-family containment checks raise `ValueError`.

## Public Functions

### `ip_inspect`

```python
def ip_inspect(address: str) -> IpInspectResult
```

```python
ip_inspect("127.0.0.1")
# → {"address": "127.0.0.1", "family": "ipv4",
#     "bytes_hex": "7f000001", "numeric": "2130706433",
#     "special_use": ["loopback"], "ipv4_mapped": None}

ip_inspect("::ffff:192.0.2.1")["ipv4_mapped"]
# → {"address": "192.0.2.1", "numeric": "3221225985"}

ip_inspect("8.8.8.8")["special_use"]  # → [] (global unicast, no tag)
```

Low-valued IPv6 addresses (`::1`, `::`, `::192.0.2.1`) never produce
mapped metadata — only the exact `::ffff:0:0/96` mask does.

### `cidr_inspect`

```python
def cidr_inspect(cidr: str, contains: str | None = None) -> CidrInspectResult
```

```python
cidr_inspect("192.168.0.0/24")
# → {"family": "ipv4", "cidr": "192.168.0.0/24", "prefix_length": 24,
#     "host_bits": 8, "network_address": "192.168.0.0",
#     "netmask": "255.255.255.0", "first_address": "192.168.0.0",
#     "last_address": "192.168.0.255", "broadcast_address": "192.168.0.255",
#     "address_count": "256", "contains": None, "contains_address": None}

cidr_inspect("10.0.0.1/8", contains="10.5.5.5")
# → {"cidr": "10.0.0.0/8", ..., "address_count": "16777216",
#     "contains": True, "contains_address": "10.5.5.5"}
```

Host bits are cleared (`10.0.0.1/8` → `10.0.0.0/8`). IPv6 ranges report
`broadcast_address=None` and full-precision counts (up to 2**128).

## Internal Helpers

| Helper | Role |
|--------|------|
| `_check_text_length(value, name)` | Enforces `MAX_TEXT_INPUT_length` (raises `ValueError`) |
| `_parse_address(address)` | `ipaddress.ip_address` wrapper with uniform errors |
| `_special_use_tags(addr)` | Explicit range-table classification → sorted tags |
| `_ipv4_mapped_info(addr)` | Exact-mask `::ffff:0:0/96` probe → `Ipv4MappedInfo \| None` |

## Dependencies

```
network.py
    └── (standard library only: ipaddress, re, typing)
```

No `exact/` imports — fully standalone leaf.

## Security Notes

- Classification is syntactic, not authoritative: tags describe address
  *allocation*, never reachability, ownership, or trust. A missing
  `private` tag does not mean "safe to dial".
- No DNS, no sockets: hostnames are rejected (parse error), never
  resolved — DNS-rebinding payloads are inert here.
- `contains` is same-family only; cross-family queries raise rather than
  return `False`, so callers cannot silently misread a v4/v6 mixup.

## See Also

- [encoding.md](encoding.md) — strict codec conversion, same fail-closed style
- [validate.md](validate.md) — regex/bracket/JSON validation companion
- [repo_audit.md](repo_audit.md) — file-inventory signals for allowlist review
