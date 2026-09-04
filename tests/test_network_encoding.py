"""Tests for deterministic network and encoding utilities.

Covers ``eggcalc.exact.network`` (``ip_inspect``, ``cidr_inspect``) and
``eggcalc.exact.encoding`` (``codec_convert``, ``radix_convert``).

Static parity vectors are transcribed from the reviewed eggsact behavior
(upstream feature commit ``879570e``, corrective commit ``ae2be1d``); the
test suite does not shell out to eggsact.
"""

from __future__ import annotations

import pytest

from eggcalc.exact.encoding import codec_convert, radix_convert
from eggcalc.exact.network import cidr_inspect, ip_inspect

MAX_U128_DECIMAL = "340282366920938463463374607431768211455"


class TestIpInspectCanonical:
    """Canonical forms, packed bytes, and numeric values."""

    def test_ipv4_canonical(self):
        result = ip_inspect("192.0.2.1")
        assert result["address"] == "192.0.2.1"
        assert result["family"] == "ipv4"
        assert result["bytes_hex"] == "c0000201"
        assert result["numeric"] == "3221225985"
        assert result["ipv4_mapped"] is None

    def test_ipv4_small(self):
        result = ip_inspect("1.2.3.4")
        assert result["address"] == "1.2.3.4"
        assert result["bytes_hex"] == "01020304"
        assert result["numeric"] == "16909060"

    def test_ipv4_max(self):
        result = ip_inspect("255.255.255.255")
        assert result["bytes_hex"] == "ffffffff"
        assert result["numeric"] == "4294967295"
        assert result["special_use"] == []

    def test_ipv6_canonical_compression(self):
        result = ip_inspect("2001:0db8:0000:0000:0000:0000:0000:0001")
        assert result["address"] == "2001:db8::1"
        assert result["family"] == "ipv6"
        assert result["bytes_hex"] == "20010db8000000000000000000000001"
        assert result["numeric"] == "42540766411282592856903984951653826561"
        assert result["ipv4_mapped"] is None

    def test_ipv6_loopback_numeric(self):
        result = ip_inspect("::1")
        assert result["bytes_hex"] == "00" * 15 + "01"
        assert result["numeric"] == "1"

    def test_invalid_addresses_rejected(self):
        for bad in ("", "999.1.1.1", "1.2.3", "1.2.3.4.5", "gggg::1", "1.2.3.4/24"):
            with pytest.raises(ValueError):
                ip_inspect(bad)

    def test_non_string_rejected(self):
        with pytest.raises(ValueError):
            ip_inspect(123)  # type: ignore[arg-type]


class TestIpInspectSpecialUse:
    """Explicit special-use taxonomy boundaries and near-miss nonmembers."""

    @pytest.mark.parametrize(
        ("address", "tags"),
        [
            ("0.0.0.0", ["unspecified"]),
            ("127.0.0.1", ["loopback"]),
            ("127.255.255.255", ["loopback"]),
            ("10.0.0.1", ["private"]),
            ("172.16.0.1", ["private"]),
            ("172.31.255.255", ["private"]),
            ("192.168.1.1", ["private"]),
            ("169.254.10.20", ["link_local"]),
            ("224.0.0.1", ["multicast"]),
            ("239.255.255.250", ["multicast"]),
            ("192.0.2.1", ["documentation"]),
            ("198.51.100.7", ["documentation"]),
            ("203.0.113.9", ["documentation"]),
            ("100.64.0.1", ["shared"]),
            ("100.127.255.254", ["shared"]),
            ("::", ["unspecified"]),
            ("::1", ["loopback"]),
            ("fe80::1", ["link_local"]),
            ("fc00::1", ["unique_local"]),
            ("fd12:3456::1", ["unique_local"]),
            ("ff02::1", ["multicast"]),
            ("2001:db8::1", ["documentation"]),
        ],
    )
    def test_special_use_members(self, address: str, tags: list[str]):
        assert ip_inspect(address)["special_use"] == tags

    @pytest.mark.parametrize(
        "address",
        [
            "0.0.0.1",
            "8.8.8.8",
            "9.255.255.255",
            "11.0.0.0",
            "100.63.255.255",
            "100.128.0.0",
            "128.0.0.0",
            "169.253.255.255",
            "169.255.0.1",
            "172.15.255.255",
            "172.32.0.0",
            "192.0.3.1",
            "192.167.255.255",
            "192.169.0.1",
            "223.255.255.255",
            "::2",
            "fe7f::1",
            "fbff::1",
            "feff::1",
            "2001:db9::1",
        ],
    )
    def test_special_use_nonmembers(self, address: str):
        assert ip_inspect(address)["special_use"] == []


class TestIpInspectMapped:
    """True ::ffff:0:0/96 mapped addresses versus lookalikes."""

    def test_mapped_dotted_notation(self):
        result = ip_inspect("::ffff:192.0.2.1")
        assert result["family"] == "ipv6"
        assert result["special_use"] == ["ipv4_mapped"]
        assert result["ipv4_mapped"] == {"address": "192.0.2.1", "numeric": "3221225985"}

    def test_mapped_hex_notation(self):
        result = ip_inspect("::ffff:c000:201")
        assert result["special_use"] == ["ipv4_mapped"]
        assert result["ipv4_mapped"] == {"address": "192.0.2.1", "numeric": "3221225985"}

    @pytest.mark.parametrize("address", ["::1", "::", "::192.0.2.1", "2001:db8::1", "::c000:201"])
    def test_non_mapped_low_addresses(self, address: str):
        result = ip_inspect(address)
        assert result["ipv4_mapped"] is None
        assert "ipv4_mapped" not in result["special_use"]


class TestCidrInspect:
    """CIDR parsing, normalization, ranges, and containment."""

    def test_ipv4_normalization(self):
        result = cidr_inspect("192.0.2.99/24")
        assert result["family"] == "ipv4"
        assert result["cidr"] == "192.0.2.0/24"
        assert result["prefix_length"] == 24
        assert result["host_bits"] == 8
        assert result["network_address"] == "192.0.2.0"
        assert result["netmask"] == "255.255.255.0"
        assert result["first_address"] == "192.0.2.0"
        assert result["last_address"] == "192.0.2.255"
        assert result["broadcast_address"] == "192.0.2.255"
        assert result["address_count"] == "256"
        assert result["contains"] is None
        assert result["contains_address"] is None

    def test_ipv4_zero_prefix(self):
        result = cidr_inspect("0.0.0.0/0")
        assert result["cidr"] == "0.0.0.0/0"
        assert result["prefix_length"] == 0
        assert result["host_bits"] == 32
        assert result["netmask"] == "0.0.0.0"
        assert result["first_address"] == "0.0.0.0"
        assert result["last_address"] == "255.255.255.255"
        assert result["broadcast_address"] == "255.255.255.255"
        assert result["address_count"] == "4294967296"

    def test_ipv4_host_route(self):
        result = cidr_inspect("192.0.2.1/32")
        assert result["prefix_length"] == 32
        assert result["host_bits"] == 0
        assert result["netmask"] == "255.255.255.255"
        assert result["first_address"] == "192.0.2.1"
        assert result["last_address"] == "192.0.2.1"
        assert result["broadcast_address"] == "192.0.2.1"
        assert result["address_count"] == "1"

    def test_ipv6_zero_prefix(self):
        result = cidr_inspect("::/0")
        assert result["family"] == "ipv6"
        assert result["cidr"] == "::/0"
        assert result["prefix_length"] == 0
        assert result["host_bits"] == 128
        assert result["first_address"] == "::"
        assert result["broadcast_address"] is None
        assert result["address_count"] == "340282366920938463463374607431768211456"

    def test_ipv6_normalization(self):
        result = cidr_inspect("2001:db8::1/64")
        assert result["cidr"] == "2001:db8::/64"
        assert result["prefix_length"] == 64
        assert result["host_bits"] == 64
        assert result["network_address"] == "2001:db8::"
        assert result["first_address"] == "2001:db8::"
        assert result["last_address"] == "2001:db8::ffff:ffff:ffff:ffff"
        assert result["broadcast_address"] is None
        assert result["address_count"] == "18446744073709551616"

    def test_ipv6_host_route(self):
        result = cidr_inspect("2001:db8::1/128")
        assert result["address_count"] == "1"
        assert result["first_address"] == "2001:db8::1"
        assert result["last_address"] == "2001:db8::1"

    def test_ipv4_containment(self):
        result = cidr_inspect("192.0.2.0/24", contains="192.0.2.1")
        assert result["contains"] is True
        assert result["contains_address"] == "192.0.2.1"
        outside = cidr_inspect("192.0.2.0/24", contains="192.0.3.1")
        assert outside["contains"] is False
        assert outside["contains_address"] == "192.0.3.1"

    def test_ipv6_containment(self):
        result = cidr_inspect("2001:db8::/32", contains="2001:db8::1")
        assert result["contains"] is True
        assert result["contains_address"] == "2001:db8::1"
        outside = cidr_inspect("2001:db8::/32", contains="2001:db9::1")
        assert outside["contains"] is False

    def test_contains_canonicalizes_candidate(self):
        result = cidr_inspect("2001:db8::/32", contains="2001:0DB8:0:0::1")
        assert result["contains"] is True
        assert result["contains_address"] == "2001:db8::1"

    @pytest.mark.parametrize(
        "cidr",
        [
            "192.0.2.0",
            "192.0.2.0/24/1",
            "/24",
            "192.0.2.0/",
            "192.0.2.0/-1",
            "192.0.2.0/+24",
            "192.0.2.0/ 24",
            "192.0.2.0/24 ",
            "192.0.2.0/0x18",
            "192.0.2.0/2.5",
            "192.0.2.0/33",
            "2001:db8::/129",
            "999.1.1.1/24",
            "",
        ],
    )
    def test_malformed_cidr_rejected(self, cidr: str):
        with pytest.raises(ValueError):
            cidr_inspect(cidr)

    def test_invalid_candidate_rejected(self):
        with pytest.raises(ValueError):
            cidr_inspect("192.0.2.0/24", contains="not-an-address")

    def test_cross_family_containment_rejected(self):
        with pytest.raises(ValueError):
            cidr_inspect("192.0.2.0/24", contains="::1")
        with pytest.raises(ValueError):
            cidr_inspect("2001:db8::/32", contains="192.0.2.1")


class TestCodecConvert:
    """Codec conversion, canonical outputs, and strict rejection."""

    def test_hello_round_trip(self):
        assert codec_convert("Hello", "utf8", "hex") == {
            "value": "48656c6c6f",
            "from": "utf8",
            "to": "hex",
            "byte_length": 5,
        }
        assert codec_convert("48656c6c6f", "hex", "base64")["value"] == "SGVsbG8="
        assert codec_convert("SGVsbG8=", "base64", "base64url")["value"] == "SGVsbG8"
        assert codec_convert("SGVsbG8", "base64url", "utf8")["value"] == "Hello"

    def test_padded_and_unpadded_base64_input(self):
        assert codec_convert("SGVsbG8=", "base64", "utf8")["value"] == "Hello"
        assert codec_convert("SGVsbG8", "base64", "utf8")["value"] == "Hello"
        assert codec_convert("SGVsbG8", "base64url", "utf8")["value"] == "Hello"

    def test_canonical_outputs(self):
        assert codec_convert("Hello", "utf8", "base64")["value"] == "SGVsbG8="
        assert codec_convert("Hello", "utf8", "base64url")["value"] == "SGVsbG8"
        assert codec_convert("SGVsbG8=", "base64", "hex")["value"] == "48656c6c6f"

    def test_url_safe_alphabet_round_trip(self):
        assert codec_convert("fbefff", "hex", "base64")["value"] == "++//"
        assert codec_convert("fbefff", "hex", "base64url")["value"] == "--__"
        assert codec_convert("--__", "base64url", "hex")["value"] == "fbefff"
        assert codec_convert("++//", "base64", "hex")["value"] == "fbefff"

    def test_identity_conversion(self):
        assert codec_convert("Hello", "utf8", "utf8")["value"] == "Hello"
        assert codec_convert("SGVsbG8=", "base64", "base64")["value"] == "SGVsbG8="

    def test_byte_length_is_payload_length(self):
        assert codec_convert("SGVsbG8=", "base64", "hex")["byte_length"] == 5
        assert codec_convert("48656c6c6f", "hex", "utf8")["byte_length"] == 5

    def test_empty_value(self):
        assert codec_convert("", "utf8", "hex")["value"] == ""
        assert codec_convert("", "hex", "base64")["value"] == ""
        assert codec_convert("", "base64", "utf8")["value"] == ""

    @pytest.mark.parametrize(
        ("value", "from_format"),
        [
            ("0x41", "hex"),
            ("41 42", "hex"),
            ("abc", "hex"),
            ("zz", "hex"),
            ("SGVs bG8=", "base64"),
            ("SGVsbG8===", "base64"),
            ("SGVsbG8==", "base64"),
            ("S=GV", "base64"),
            ("A", "base64"),
            ("====", "base64"),
            ("AB-_CD==", "base64"),
            ("SGVsbG8\t", "base64"),
            ("AB+/CD==", "base64url"),
            ("A", "base64url"),
        ],
    )
    def test_malformed_inputs_rejected(self, value: str, from_format: str):
        with pytest.raises(ValueError):
            codec_convert(value, from_format, "utf8")

    def test_invalid_utf8_destination_rejected(self):
        with pytest.raises(ValueError):
            codec_convert("ff", "hex", "utf8")
        with pytest.raises(ValueError):
            codec_convert("80", "hex", "utf8")

    def test_unsupported_formats_rejected(self):
        with pytest.raises(ValueError):
            codec_convert("Hello", "base32", "hex")
        with pytest.raises(ValueError):
            codec_convert("Hello", "utf8", "base32")
        with pytest.raises(ValueError):
            codec_convert("Hello", "UTF8", "hex")
        with pytest.raises(ValueError):
            codec_convert("Hello", "utf8", "HEX")

    def test_input_ceiling_enforced(self):
        with pytest.raises(ValueError):
            codec_convert("ab" * 50001, "hex", "utf8")


class TestRadixConvert:
    """Radix conversion, canonical output, and u128 magnitude cap."""

    def test_signed_hex_to_binary(self):
        result = radix_convert("-ff", 16, 2)
        assert result["value"] == "-11111111"
        assert result["from_base"] == 16
        assert result["to_base"] == 2
        assert result["uppercase"] is False
        assert result["negative"] is True
        assert result["magnitude_decimal"] == "255"

    def test_explicit_plus_sign(self):
        result = radix_convert("+101", 2, 16)
        assert result["value"] == "5"
        assert result["negative"] is False

    def test_base36(self):
        assert radix_convert("z", 36, 10)["value"] == "35"
        assert radix_convert("10", 36, 10)["value"] == "36"
        assert radix_convert("hello", 36, 10)["value"] == "29234652"
        assert radix_convert("29234652", 10, 36)["value"] == "hello"

    def test_uppercase_output(self):
        assert radix_convert("ff", 16, 16, uppercase=True)["value"] == "FF"
        assert radix_convert("ff", 16, 16)["value"] == "ff"
        assert radix_convert("255", 10, 16, uppercase=True)["value"] == "FF"
        assert radix_convert("255", 10, 16)["value"] == "ff"

    def test_uppercase_input_accepted(self):
        assert radix_convert("FF", 16, 10)["value"] == "255"
        assert radix_convert("Hello", 36, 10)["value"] == "29234652"

    @pytest.mark.parametrize("zero", ["0", "-0", "+0", "-00"])
    def test_zero_normalization(self, zero: str):
        result = radix_convert(zero, 10, 16)
        assert result["value"] == "0"
        assert result["negative"] is False
        assert result["magnitude_decimal"] == "0"

    def test_leading_zeroes_stripped(self):
        assert radix_convert("000ff", 16, 10)["value"] == "255"

    def test_u128_max_accepted(self):
        assert radix_convert(MAX_U128_DECIMAL, 10, 16)["value"] == "f" * 32
        assert radix_convert("f" * 32, 16, 10)["value"] == MAX_U128_DECIMAL
        assert radix_convert("F" * 32, 16, 10)["magnitude_decimal"] == MAX_U128_DECIMAL

    @pytest.mark.parametrize(
        "value",
        [
            "340282366920938463463374607431768211456",
            "1" + "0" * 39,
            "1" + "0" * 200,
        ],
    )
    def test_u128_overflow_rejected(self, value: str):
        with pytest.raises(ValueError):
            radix_convert(value, 10, 10)

    def test_u128_hex_overflow_rejected(self):
        with pytest.raises(ValueError):
            radix_convert("1" + "0" * 32, 16, 10)

    @pytest.mark.parametrize(
        ("value", "from_base"),
        [
            ("2", 2),
            ("g", 16),
            ("z", 35),
            ("", 10),
            ("-", 10),
            ("+", 10),
            ("--1", 10),
            ("+-1", 10),
            ("1_0", 10),
            ("1 0", 10),
            ("0x1", 16),
            ("0b1", 2),
            ("1.0", 10),
            ("1e3", 10),
            (" 1", 10),
            ("1 ", 10),
            ("\u0661", 10),
        ],
    )
    def test_invalid_digits_rejected(self, value: str, from_base: int):
        with pytest.raises(ValueError):
            radix_convert(value, from_base, 10)

    @pytest.mark.parametrize("base", [0, 1, 37, -2, 100])
    def test_invalid_bases_rejected(self, base: int):
        with pytest.raises(ValueError):
            radix_convert("10", base, 10)
        with pytest.raises(ValueError):
            radix_convert("10", 10, base)

    def test_non_integer_base_rejected(self):
        with pytest.raises(ValueError):
            radix_convert("10", "16", 10)  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            radix_convert("10", 10, 16.0)  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            radix_convert("10", True, 10)  # type: ignore[arg-type]


class TestExactLazyExports:
    """New utilities are available through the lazy exact package surface."""

    def test_lazy_imports(self):
        import eggcalc.exact as exact

        assert callable(exact.ip_inspect)
        assert callable(exact.cidr_inspect)
        assert callable(exact.codec_convert)
        assert callable(exact.radix_convert)
        assert exact.ip_inspect("127.0.0.1")["special_use"] == ["loopback"]
        assert exact.radix_convert("ff", 16, 10)["value"] == "255"
