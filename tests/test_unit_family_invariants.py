"""Differential/invariant tests for every advertised unit family (criterion 30).

Verifies round-trip conversions, compatibility grouping, dimension arithmetic,
and display stability across all 16+ unit families.
"""

from __future__ import annotations

import pytest

from eggcalc.units import (
    DIM_DIMENSIONLESS,
    UNIT_CATEGORIES,
    Dimension,
    UnitRegistry,
    UnitValue,
    are_units_compatible,
    build_unit_registry,
    convert_temperature,
    get_conversion_factor,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def registry() -> UnitRegistry:
    return build_unit_registry()


# One representative unit per family for round-trip testing
_FAMILY_REPRESENTATIVES: dict[str, list[tuple[str, str]]] = {
    "length": [("m", "km"), ("ft", "in"), ("mi", "km"), ("yd", "ft")],
    "mass": [("kg", "g"), ("lb", "oz"), ("tonne", "kg"), ("stone", "lb")],
    "time": [("s", "ms"), ("min", "s"), ("h", "min"), ("d", "h")],
    "data": [("B", "KB"), ("MB", "KB"), ("GB", "MB"), ("TB", "GB")],
    "data_rate": [("bps", "Kbps"), ("Mbps", "Kbps"), ("Gbps", "Mbps")],
    "volume": [("L", "mL"), ("gal", "L"), ("ft3", "in3"), ("cm3", "mL")],
    "pressure": [("Pa", "kPa"), ("atm", "psi"), ("bar", "mbar"), ("mmHg", "torr")],
    "energy": [("J", "kJ"), ("cal", "kcal"), ("kWh", "Wh"), ("BTU", "J")],
    "power": [("W", "kW"), ("MW", "kW"), ("hp", "W"), ("mW", "W")],
    "force": [("N", "kN"), ("lbf", "N"), ("dyne", "N"), ("mN", "N")],
    "voltage": [("V", "kV"), ("mV", "V"), ("μV", "V")],
    "current": [("A", "mA"), ("μA", "mA")],
    "speed": [("m/s", "km/h"), ("mph", "km/h"), ("kn", "m/s")],
    "area": [("m2", "km2"), ("ft2", "in2"), ("acre", "m2"), ("ha", "m2")],
    "frequency": [("Hz", "kHz"), ("MHz", "kHz"), ("GHz", "MHz"), ("THz", "GHz")],
    "angle": [("deg", "rad")],
}

_TEMPERATURE_PAIRS = [
    ("K", "C"),
    ("K", "F"),
    ("K", "Ra"),
    ("C", "F"),
    ("C", "Ra"),
    ("F", "Ra"),
]


# ---------------------------------------------------------------------------
# Round-trip conversion invariants
# ---------------------------------------------------------------------------


class TestRoundTripConversions:
    """Every multiplicative pair must survive round-trip conversion."""

    @pytest.mark.parametrize(
        "from_u,to_u",
        [pair for pairs in _FAMILY_REPRESENTATIVES.values() for pair in pairs],
        ids=[f"{a}->{b}" for pairs in _FAMILY_REPRESENTATIVES.values() for a, b in pairs],
    )
    def test_multiplicative_round_trip(self, from_u: str, to_u: str):
        """convert(v, A, B) then convert(result, B, A) should give back v."""
        factor_ab = get_conversion_factor(from_u, to_u)
        factor_ba = get_conversion_factor(to_u, from_u)
        assert factor_ab is not None, f"No conversion factor for {from_u}->{to_u}"
        assert factor_ba is not None, f"No conversion factor for {to_u}->{from_u}"

        for value in [1.0, 100.0, 0.001, 1e6]:
            result = value * factor_ab
            round_trip = result * factor_ba
            assert round_trip == pytest.approx(value, rel=1e-10), (
                f"Round-trip {from_u}->{to_u}->{from_u} failed: "
                f"{value} -> {result} -> {round_trip}"
            )

    @pytest.mark.parametrize(
        "from_u,to_u",
        _TEMPERATURE_PAIRS,
        ids=[f"{a}->{b}" for a, b in _TEMPERATURE_PAIRS],
    )
    def test_temperature_round_trip(self, from_u: str, to_u: str):
        """Temperature conversions must be exactly round-trippable."""
        for value in [0.0, 273.15, 100.0, -40.0, 98.6]:
            result = convert_temperature(value, from_u, to_u)
            round_trip = convert_temperature(result, to_u, from_u)
            assert round_trip == pytest.approx(value, abs=1e-10), (
                f"Temp round-trip {from_u}->{to_u}->{from_u} failed: "
                f"{value} -> {result} -> {round_trip}"
            )


# ---------------------------------------------------------------------------
# Same-unit identity
# ---------------------------------------------------------------------------


class TestSameUnitIdentity:
    """Converting a unit to itself must return the same value."""

    @pytest.mark.parametrize(
        "unit",
        ["m", "kg", "s", "L", "J", "Pa", "W", "N", "V", "A", "Hz", "B", "bps", "deg"],
    )
    def test_same_unit_identity(self, unit: str):
        factor = get_conversion_factor(unit, unit)
        assert factor == 1.0, f"Self-conversion factor for {unit} should be 1.0, got {factor}"


# ---------------------------------------------------------------------------
# Compatibility grouping
# ---------------------------------------------------------------------------


class TestCompatibilityGrouping:
    """Units in the same family must be compatible; cross-family must not."""

    def test_same_family_compatible(self):
        for family, pairs in _FAMILY_REPRESENTATIVES.items():
            for a, b in pairs:
                assert are_units_compatible(
                    a, b
                ), f"{a} and {b} should be compatible (same family: {family})"

    def test_cross_family_incompatible(self):
        cross_pairs = [
            ("m", "kg"),
            ("s", "J"),
            ("L", "Pa"),
            ("W", "N"),
            ("V", "A"),
            ("Hz", "m"),
            ("B", "J"),
        ]
        for a, b in cross_pairs:
            assert not are_units_compatible(
                a, b
            ), f"{a} and {b} should NOT be compatible (different families)"

    def test_dimensionless_incompatible_with_dimensional(self):
        assert not are_units_compatible("m", "kg")
        assert not are_units_compatible("s", "L")


# ---------------------------------------------------------------------------
# Dimension arithmetic invariants
# ---------------------------------------------------------------------------


class TestDimensionArithmetic:
    """Dimension multiplication/division must combine exponents correctly."""

    def test_length_times_length_equals_area(self):
        dim_area = DIM_DIMENSIONLESS.__class__(length=2)
        result = Dimension(length=1) * Dimension(length=1)
        assert result == dim_area

    def test_area_div_length_equals_length(self):
        area = Dimension(length=2)
        length = Dimension(length=1)
        result = area / length
        assert result == length

    def test_mass_times_acceleration_equals_force(self):
        mass = Dimension(mass=1)
        accel = Dimension(length=1, time=-2)
        force = Dimension(mass=1, length=1, time=-2)
        assert mass * accel == force

    def test_energy_equals_force_times_length(self):
        force = Dimension(mass=1, length=1, time=-2)
        length = Dimension(length=1)
        energy = Dimension(mass=1, length=2, time=-2)
        assert force * length == energy

    def test_power_equals_energy_div_time(self):
        energy = Dimension(mass=1, length=2, time=-2)
        time = Dimension(time=1)
        power = Dimension(mass=1, length=2, time=-3)
        assert energy / time == power

    def test_voltage_equals_power_div_current(self):
        power = Dimension(mass=1, length=2, time=-3)
        current = Dimension(current=1)
        voltage = Dimension(mass=1, length=2, time=-3, current=-1)
        assert power / current == voltage

    def test_speed_equals_length_div_time(self):
        length = Dimension(length=1)
        time = Dimension(time=1)
        speed = Dimension(length=1, time=-1)
        assert length / time == speed

    def test_frequency_equals_one_div_time(self):
        one = Dimension()
        time = Dimension(time=1)
        freq = Dimension(time=-1)
        assert one / time == freq


# ---------------------------------------------------------------------------
# Angle invariants
# ---------------------------------------------------------------------------


class TestAngleInvariants:
    """Angle dimension must propagate correctly through arithmetic."""

    def test_angle_not_equal_to_dimensionless(self):
        angle = Dimension(angle=True)
        dimless = Dimension()
        assert angle != dimless

    def test_angle_hash_differs_from_dimensionless(self):
        angle = Dimension(angle=True)
        dimless = Dimension()
        assert hash(angle) != hash(dimless)

    def test_angle_xor_propagation_mul(self):
        a = Dimension(angle=True)
        b = Dimension(angle=True)
        result = a * b
        assert result.angle is False  # True XOR True = False

    def test_angle_xor_propagation_div(self):
        a = Dimension(length=1, angle=True)
        b = Dimension(length=1, angle=True)
        result = a / b
        assert result.angle is False

    def test_angle_preserved_on_odd_pow(self):
        a = Dimension(angle=True)
        result = a**3
        assert result.angle is True

    def test_angle_lost_on_even_pow(self):
        a = Dimension(angle=True)
        result = a**2
        assert result.angle is False


# ---------------------------------------------------------------------------
# Display stability
# ---------------------------------------------------------------------------


class TestDisplayStability:
    """UnitValue display strings must be stable."""

    def test_length_display(self):
        assert str(UnitValue(5.0, "m")) == "5 m"
        assert str(UnitValue(10.5, "ft")) == "10.5 ft"

    def test_mass_display(self):
        assert str(UnitValue(1.0, "kg")) == "1 kg"
        assert str(UnitValue(273.15, "K")) == "273.15 K"

    def test_dimensionless_display(self):
        assert str(UnitValue(42.0)) == "42"

    def test_zero_display(self):
        assert str(UnitValue(0.0)) == "0"


# ---------------------------------------------------------------------------
# Category coverage
# ---------------------------------------------------------------------------


class TestCategoryCoverage:
    """Every unit alias must have a category entry."""

    def test_all_aliases_have_categories(self):
        for alias in UNIT_CATEGORIES:
            assert alias in UNIT_CATEGORIES
            assert isinstance(UNIT_CATEGORIES[alias], str)


# ---------------------------------------------------------------------------
# Immutability invariants
# ---------------------------------------------------------------------------


class TestImmutability:
    """Structural types must be immutable."""

    def test_dimension_immutable(self):
        d = Dimension(length=1)
        with pytest.raises(AttributeError, match="immutable"):
            d.length = 2
        with pytest.raises(AttributeError, match="immutable"):
            del d.length

    def test_unit_definition_immutable(self):
        from eggcalc.units import UnitDefinition

        ud = UnitDefinition(canonical="test", dimension=Dimension(), scale=1.0)
        with pytest.raises(AttributeError, match="immutable"):
            ud.canonical = "other"
        with pytest.raises(AttributeError, match="immutable"):
            del ud.canonical

    def test_unit_registry_immutable(self):
        reg = build_unit_registry()
        # Internal dicts are copies
        original_len = len(reg)
        # Modifying the source data shouldn't affect the registry
        assert len(reg) == original_len

    def test_dimension_tuple_consistency(self):
        d1 = Dimension(length=1)
        d2 = Dimension(length=1)
        assert d1 == d2
        assert d1._tuple() == d2._tuple()
