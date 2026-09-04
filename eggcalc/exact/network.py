"""Deterministic IP address and CIDR inspection tools.

Provides pure, side-effect-free inspection of IP addresses and CIDR ranges
using Python's ``ipaddress`` module for parsing and canonical formatting.
No network I/O, DNS lookups, or platform-specific behavior is involved.

Special-use classification uses an explicit, version-stable taxonomy rather
than the version-sensitive ``is_private``/``is_global`` convenience
properties, so supported Python minor releases cannot change output.
"""

from __future__ import annotations

import ipaddress
import re
from typing import TypedDict

MAX_TEXT_INPUT_LENGTH = 100_000


class Ipv4MappedInfo(TypedDict):
    """Embedded IPv4 address carried by an IPv4-mapped IPv6 address."""

    address: str
    numeric: str


class IpInspectResult(TypedDict):
    """Result of inspecting a single IP address."""

    address: str
    family: str
    bytes_hex: str
    numeric: str
    special_use: list[str]
    ipv4_mapped: Ipv4MappedInfo | None


class CidrInspectResult(TypedDict):
    """Result of inspecting a CIDR range, with optional containment check."""

    family: str
    cidr: str
    prefix_length: int
    host_bits: int
    network_address: str
    netmask: str
    first_address: str
    last_address: str
    broadcast_address: str | None
    address_count: str
    contains: bool | None
    contains_address: str | None


# Explicit special-use taxonomy: (tag, networks). Tags are sorted
# lexicographically before being returned so output is stable.
_IPV4_SPECIAL_USE: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("unspecified", ("0.0.0.0/32",)),
    ("loopback", ("127.0.0.0/8",)),
    ("private", ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")),
    ("link_local", ("169.254.0.0/16",)),
    ("multicast", ("224.0.0.0/4",)),
    ("documentation", ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24")),
    ("shared", ("100.64.0.0/10",)),
)

_IPV6_SPECIAL_USE: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("unspecified", ("::/128",)),
    ("loopback", ("::1/128",)),
    ("link_local", ("fe80::/10",)),
    ("unique_local", ("fc00::/7",)),
    ("multicast", ("ff00::/8",)),
    ("documentation", ("2001:db8::/32",)),
    ("ipv4_mapped", ("::ffff:0:0/96",)),
)

# Precomputed network objects for the explicit taxonomy (immutable).
_IPV4_SPECIAL_NETWORKS: tuple[tuple[str, tuple[ipaddress.IPv4Network, ...]], ...] = tuple(
    (tag, tuple(ipaddress.IPv4Network(net) for net in nets)) for tag, nets in _IPV4_SPECIAL_USE
)
_IPV6_SPECIAL_NETWORKS: tuple[tuple[str, tuple[ipaddress.IPv6Network, ...]], ...] = tuple(
    (tag, tuple(ipaddress.IPv6Network(net) for net in nets)) for tag, nets in _IPV6_SPECIAL_USE
)

# Exact integer mask for the ::ffff:0:0/96 IPv4-mapped prefix. Only
# addresses under this prefix carry mapped metadata; low-valued IPv6
# addresses such as ::1, ::, or ::192.0.2.1 must not.
_IPV4_MAPPED_MASK = ((1 << 128) - 1) ^ ((1 << 32) - 1)
_IPV4_MAPPED_PREFIX = 0xFFFF << 32

_PREFIX_RE = re.compile(r"[0-9]+")


def _check_text_length(value: str, name: str) -> None:
    """Reject inputs beyond the shared exact text ceiling."""
    if len(value) > MAX_TEXT_INPUT_LENGTH:
        raise ValueError(
            f"Input {name} length {len(value)} exceeds maximum {MAX_TEXT_INPUT_LENGTH}"
        )


def _parse_address(address: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    """Parse an address string, converting stdlib errors to ValueError."""
    if not isinstance(address, str):
        raise ValueError(f"address must be a string, got {type(address).__name__}")
    _check_text_length(address, "'address'")
    try:
        return ipaddress.ip_address(address)
    except ValueError as exc:
        raise ValueError(f"invalid IP address: {address!r}") from exc


def _special_use_tags(
    addr: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> list[str]:
    """Return sorted explicit special-use tags for an address."""
    if isinstance(addr, ipaddress.IPv4Address):
        return sorted(
            tag for tag, nets in _IPV4_SPECIAL_NETWORKS if any(addr in net for net in nets)
        )
    return sorted(tag for tag, nets in _IPV6_SPECIAL_NETWORKS if any(addr in net for net in nets))


def _ipv4_mapped_info(addr: ipaddress.IPv6Address) -> Ipv4MappedInfo | None:
    """Return embedded IPv4 metadata for true ::ffff:0:0/96 addresses."""
    if (int(addr) & _IPV4_MAPPED_MASK) != _IPV4_MAPPED_PREFIX:
        return None
    embedded = ipaddress.IPv4Address(int(addr) & 0xFFFFFFFF)
    return Ipv4MappedInfo(address=str(embedded), numeric=str(int(embedded)))


def ip_inspect(address: str) -> IpInspectResult:
    """Inspect a single IPv4 or IPv6 address.

    Args:
        address: IP address text (e.g. ``"192.0.2.1"``, ``"::ffff:192.0.2.1"``).

    Returns:
        IpInspectResult with canonical address, family (``"ipv4"``/``"ipv6"``),
        packed bytes as lowercase hex, numeric value as decimal text, sorted
        explicit special-use tags, and IPv4-mapped metadata (or None).

    Raises:
        ValueError: If the address is not a string, exceeds the input
            ceiling, or is not a valid IP address.

    Examples:
        >>> ip_inspect("192.0.2.1")["family"]
        'ipv4'
        >>> ip_inspect("::ffff:192.0.2.1")["ipv4_mapped"]
        {'address': '192.0.2.1', 'numeric': '3221225985'}
    """
    addr = _parse_address(address)
    if isinstance(addr, ipaddress.IPv4Address):
        family = "ipv4"
        mapped: Ipv4MappedInfo | None = None
    else:
        family = "ipv6"
        mapped = _ipv4_mapped_info(addr)
    return IpInspectResult(
        address=str(addr),
        family=family,
        bytes_hex=addr.packed.hex(),
        numeric=str(int(addr)),
        special_use=_special_use_tags(addr),
        ipv4_mapped=mapped,
    )


def cidr_inspect(cidr: str, contains: str | None = None) -> CidrInspectResult:
    """Inspect a CIDR range, optionally testing containment of an address.

    The input must contain exactly one ``/`` separator followed by a decimal,
    non-negative prefix with no sign or whitespace. Host-address CIDRs are
    canonicalized to their network boundary.

    Args:
        cidr: CIDR text such as ``"192.0.2.99/24"`` or ``"2001:db8::1/64"``.
        contains: Optional candidate address to test for membership. Must use
            the same address family as the CIDR.

    Returns:
        CidrInspectResult with canonical network CIDR, prefix/host bit
        counts, network/netmask/first/last addresses, IPv4 broadcast (None
        for IPv6), exact address count as decimal text, and the optional
        same-family containment result.

    Raises:
        ValueError: If the CIDR shape, address, or prefix is malformed, the
            prefix exceeds the address width, or the candidate address is
            invalid or cross-family.

    Examples:
        >>> cidr_inspect("192.0.2.99/24")["cidr"]
        '192.0.2.0/24'
        >>> cidr_inspect("192.0.2.0/24", contains="192.0.2.1")["contains"]
        True
    """
    if not isinstance(cidr, str):
        raise ValueError(f"cidr must be a string, got {type(cidr).__name__}")
    _check_text_length(cidr, "'cidr'")
    if cidr.count("/") != 1:
        raise ValueError(f"invalid CIDR (expected exactly one '/'): {cidr!r}")
    address_part, _, prefix_part = cidr.partition("/")
    if not address_part or not prefix_part:
        raise ValueError(f"invalid CIDR (empty address or prefix): {cidr!r}")
    if _PREFIX_RE.fullmatch(prefix_part) is None:
        raise ValueError(f"invalid CIDR prefix (must be decimal digits): {cidr!r}")
    prefix_length = int(prefix_part)
    addr = _parse_address(address_part)
    max_prefix = 32 if isinstance(addr, ipaddress.IPv4Address) else 128
    if prefix_length > max_prefix:
        raise ValueError(f"invalid CIDR prefix {prefix_length} exceeds address width {max_prefix}")
    network = ipaddress.ip_network(f"{addr}/{prefix_length}", strict=False)
    is_v4 = isinstance(network, ipaddress.IPv4Network)
    first = network.network_address
    last = network.broadcast_address
    contains_result: bool | None = None
    contains_address: str | None = None
    if contains is not None:
        candidate = _parse_address(contains)
        if isinstance(candidate, ipaddress.IPv4Address) != is_v4:
            raise ValueError("contains candidate must use the same address family as the CIDR")
        contains_result = candidate in network
        contains_address = str(candidate)
    return CidrInspectResult(
        family="ipv4" if is_v4 else "ipv6",
        cidr=str(network),
        prefix_length=network.prefixlen,
        host_bits=network.max_prefixlen - network.prefixlen,
        network_address=str(first),
        netmask=str(network.netmask),
        first_address=str(first),
        last_address=str(last),
        broadcast_address=str(last) if is_v4 else None,
        address_count=str(network.num_addresses),
        contains=contains_result,
        contains_address=contains_address,
    )
