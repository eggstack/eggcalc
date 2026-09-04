# network.py — IP Address and CIDR Inspection

240 lines. Deterministic IP/CIDR inspection with an explicit, version-stable special-use taxonomy.

## Overview

Pure parsing and classification of IPv4/IPv6 addresses and CIDR ranges using Python's `ipaddress` module for syntactic validation and canonical formatting. No network I/O, DNS lookups, filesystem access, or platform-specific behavior.

Special-use classification is an explicit range table, not a projection of the version-sensitive `is_private`/`is_global` convenience properties, so standard-library IANA-table updates cannot change deterministic output.

## Key Exports

```python
from eggcalc.exact.network import (
    ip_inspect,
    cidr_inspect,
)
```

## Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `ip_inspect(address)` | `IpInspectResult` | Canonical address, family, packed-bytes hex, decimal numeric, sorted special-use tags, IPv4-mapped metadata |
| `cidr_inspect(cidr, contains=None)` | `CidrInspectResult` | Canonical network CIDR, prefix/host bits, network/netmask/first/last, IPv4 broadcast (`None` for IPv6), exact address count, optional same-family containment |

## IpInspectResult TypedDict

```python
IpInspectResult(
    address=str,            # Canonical address text
    family=str,             # "ipv4" or "ipv6"
    bytes_hex=str,          # Packed bytes as lowercase hex, no separators
    numeric=str,            # Exact unsigned integer value as decimal text
    special_use=list[str],  # Sorted explicit tags (see below)
    ipv4_mapped=Ipv4MappedInfo | None,  # {"address", "numeric"} or None
)
```

## Explicit Special-Use Taxonomy

IPv4: `unspecified` (`0.0.0.0`), `loopback` (`127.0.0.0/8`), `private` (RFC 1918 triple), `link_local` (`169.254.0.0/16`), `multicast` (`224.0.0.0/4`), `documentation` (TEST-NET-1/2/3), `shared` (`100.64.0.0/10`).

IPv6: `unspecified` (`::`), `loopback` (`::1`), `link_local` (`fe80::/10`), `unique_local` (`fc00::/7`), `multicast` (`ff00::/8`), `documentation` (`2001:db8::/32`), `ipv4_mapped` (only `::ffff:0:0/96`).

Tags are sorted lexicographically before return. IPv4-mapped detection uses an exact integer mask for `::ffff:0:0/96` — low-valued addresses such as `::1`, `::`, or `::192.0.2.1` never produce mapped metadata.

## CidrInspectResult TypedDict

```python
CidrInspectResult(
    family=str,
    cidr=str,               # Canonical network CIDR (host bits cleared)
    prefix_length=int,
    host_bits=int,
    network_address=str,
    netmask=str,
    first_address=str,      # Network address (not first usable host)
    last_address=str,       # Final address in range
    broadcast_address=str | None,  # Final address for IPv4, None for IPv6
    address_count=str,      # Exact decimal text (arbitrary precision, e.g. 2**128)
    contains=bool | None,   # None when no candidate supplied
    contains_address=str | None,  # Candidate canonical address when supplied
)
```

Input grammar requires exactly one `/` and a decimal, non-negative, ASCII-digit prefix with no sign or whitespace; over-wide prefixes, invalid candidates, and cross-family containment checks raise `ValueError`.

## Module Dependencies

- `ipaddress`, `re`, `typing`
