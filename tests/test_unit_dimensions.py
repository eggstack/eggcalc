"""Structural unit dimension tests for Release 6 (D8).

Verifies the structural dimension model, authoritative unit registry,
and structural compatibility against the legacy category-based system.
"""

from __future__ import annotations

import math

import pytest

from eggcalc.units import (
    DIM_CURRENT,
    DIM_INFORMATION,
    DIM_LENGTH,
    DIM_MASS,
    DIM_TEMPERATURE,
    DIM_TIME,
    MAX_COMPOUND_DEPTH,
    MAX_UNIT_STRING_LENGTH,
    UnitDefinition,
    UnitRegistry,
    UnitValue,
    _structural_dimension,
    are_units_compatible,
    build_unit_registry,
    get_conversion_factor,
    normalize_unit,
    parse_unit_expression,
)

# ---------------------------------------------------------------------------
# Dimension type tests
# ---------------------------------------------------------------------------


class TestDimensionType:
    """Immutable Dimension type correctness."""

    def test_default_is_dimensionless(self):
        from eggcalc.units import Dimension

        d = Dimension()
        assert d.is_dimensionless
        assert d._tuple() == (0, 0, 0, 0, 0, 0, 0, 0, 0)

    def test_base_dimensions(self):
        assert DIM_LENGTH.length == 1
        assert DIM_MASS.mass == 1
        assert DIM_TIME.time == 1
        assert DIM_CURRENT.current == 1

    def test_equality(self):
        from eggcalc.units import Dimension

        d1 = Dimension(length=2, mass=1)
        d2 = Dimension(length=2, mass=1)
        d3 = Dimension(length=2, mass=2)
        assert d1 == d2
        assert d1 != d3
        assert d1 != "not a dimension"

    def test_angle_distinguishes_dimensions(self):
        from eggcalc.units import Dimension

        d_angle = Dimension(angle=True)
        d_plain = Dimension()
        assert d_angle != d_plain
        assert hash(d_angle) != hash(d_plain)

    def test_angle_equality(self):
        from eggcalc.units import Dimension

        d1 = Dimension(angle=True)
        d2 = Dimension(angle=True)
        assert d1 == d2
        assert hash(d1) == hash(d2)

    def test_hash_consistency(self):
        from eggcalc.units import Dimension

        d1 = Dimension(length=1, time=-1)
        d2 = Dimension(length=1, time=-1)
        assert hash(d1) == hash(d2)
        s = {d1, d2}
        assert len(s) == 1

    def test_immutability(self):
        from eggcalc.units import Dimension

        d = Dimension(length=1)
        with pytest.raises(AttributeError):
            d.length = 5
        with pytest.raises(AttributeError):
            del d.length

    def test_mul(self):
        d = DIM_LENGTH * DIM_MASS
        assert d.length == 1
        assert d.mass == 1

    def test_mul_angle_propagation(self):
        from eggcalc.units import Dimension

        a = Dimension(angle=True)
        b = Dimension()
        # angle × dimensionless = angle (XOR: True != False = True)
        assert (a * b).angle is True
        # dimensionless × angle = angle (XOR: False != True = True)
        assert (b * a).angle is True
        # angle × angle = error (not representable)
        with pytest.raises(ValueError, match="Cannot multiply two angle"):
            a * a
        # angle × length = angle (XOR: True != False = True)
        assert (a * DIM_LENGTH).angle is True

    def test_truediv(self):
        d = DIM_LENGTH / DIM_TIME
        assert d.length == 1
        assert d.time == -1

    def test_truediv_angle_propagation(self):
        from eggcalc.units import Dimension

        a = Dimension(angle=True)
        b = Dimension()
        # angle / dimensionless = angle
        assert (a / b).angle is True
        # angle / angle = no angle (XOR cancels)
        assert (a / a).angle is False

    def test_pow(self):
        d = DIM_LENGTH**3
        assert d.length == 3
        assert d.mass == 0

    def test_pow_angle_propagation(self):
        from eggcalc.units import Dimension

        a = Dimension(angle=True)
        # angle^1 = angle
        assert (a**1).angle is True
        # angle^2 = error (not representable)
        with pytest.raises(ValueError, match="Cannot raise angle"):
            a**2
        # angle^3 = error (not representable)
        with pytest.raises(ValueError, match="Cannot raise angle"):
            a**3
        # angle^0 = dimensionless
        assert (a**0).angle is False

    def test_is_affine(self):
        assert not DIM_LENGTH.is_affine
        from eggcalc.units import DIM_TEMPERATURE

        assert DIM_TEMPERATURE.is_affine

    def test_repr(self):
        from eggcalc.units import Dimension

        d = Dimension(length=1, time=-1)
        r = repr(d)
        assert "L" in r
        assert "T^-1" in r


# ---------------------------------------------------------------------------
# UnitDefinition tests
# ---------------------------------------------------------------------------


class TestUnitDefinition:
    """Immutable UnitDefinition correctness."""

    def test_basic_construction(self):
        ud = UnitDefinition(
            canonical="m",
            dimension=DIM_LENGTH,
            scale=1.0,
            aliases=("meter", "meters"),
        )
        assert ud.canonical == "m"
        assert ud.dimension == DIM_LENGTH
        assert ud.scale == 1.0
        assert ud.aliases == ("meter", "meters")
        assert not ud.affine

    def test_affine_construction(self):
        ud = UnitDefinition(
            canonical="C",
            dimension=DIM_TEMPERATURE,
            scale=1.0,
            offset=273.15,
            affine=True,
        )
        assert ud.affine
        assert ud.offset == 273.15

    def test_reject_zero_scale(self):
        with pytest.raises(ValueError, match="non-zero"):
            UnitDefinition("bad", DIM_LENGTH, 0.0)

    def test_reject_nan_scale(self):
        with pytest.raises(ValueError, match="finite"):
            UnitDefinition("bad", DIM_LENGTH, float("nan"))

    def test_reject_inf_offset(self):
        with pytest.raises(ValueError, match="finite"):
            UnitDefinition("bad", DIM_LENGTH, 1.0, offset=float("inf"))

    def test_immutability(self):
        ud = UnitDefinition("m", DIM_LENGTH, 1.0)
        with pytest.raises(AttributeError):
            ud.canonical = "km"

    def test_equality(self):
        u1 = UnitDefinition("m", DIM_LENGTH, 1.0)
        u2 = UnitDefinition("m", DIM_LENGTH, 1.0)
        u3 = UnitDefinition("km", DIM_LENGTH, 1000.0)
        assert u1 == u2
        assert u1 != u3

    def test_hash(self):
        u1 = UnitDefinition("m", DIM_LENGTH, 1.0)
        u2 = UnitDefinition("m", DIM_LENGTH, 1.0)
        assert hash(u1) == hash(u2)


# ---------------------------------------------------------------------------
# Registry construction and validation
# ---------------------------------------------------------------------------


class TestUnitRegistry:
    """Authoritative unit registry (D4)."""

    def test_build_registry(self):
        reg = build_unit_registry()
        assert isinstance(reg, UnitRegistry)
        assert len(reg) > 400

    def test_every_alias_has_definition(self):
        from eggcalc.units import UNIT_ALIASES

        reg = build_unit_registry()
        for alias in UNIT_ALIASES:
            norm = normalize_unit(alias)
            ud = reg.by_alias(alias) or reg.by_alias(norm)
            assert ud is not None, f"Alias {alias!r} (norm={norm!r}) not in registry"

    def test_canonical_units_lookup(self):
        reg = build_unit_registry()
        for canonical in reg.all_canonicals:
            ud = reg.by_canonical(canonical)
            assert ud is not None
            assert ud.canonical == canonical

    def test_no_duplicate_aliases(self):
        reg = build_unit_registry()
        seen: set[str] = set()
        for alias in reg.all_aliases:
            assert alias not in seen, f"Duplicate alias: {alias}"
            seen.add(alias)

    def test_all_scales_finite_nonzero(self):
        reg = build_unit_registry()
        for alias in reg.all_aliases:
            ud = reg.by_alias(alias)
            assert ud is not None
            assert math.isfinite(ud.scale), f"Non-finite scale for {alias}"
            assert ud.scale != 0.0, f"Zero scale for {alias}"

    def test_all_dimensions_hashable(self):
        reg = build_unit_registry()
        dims = set()
        for alias in reg.all_aliases:
            ud = reg.by_alias(alias)
            dims.add(ud.dimension)
        # Should not raise
        assert len(dims) > 0

    def test_temperature_units_are_affine(self):
        reg = build_unit_registry()
        for temp_unit in ("K", "C", "F", "Ra"):
            ud = reg.by_alias(temp_unit)
            assert ud is not None, f"Temperature unit {temp_unit} not in registry"
            assert ud.affine, f"Temperature unit {temp_unit} not marked affine"

    def test_conversion_factor_parity(self):
        """Registry conversion factors match legacy get_conversion_factor."""
        reg = build_unit_registry()
        pairs = [
            ("km", "m"),
            ("ft", "in"),
            ("lb", "kg"),
            ("mi", "km"),
            ("gal", "L"),
            ("psi", "Pa"),
            ("kWh", "J"),
            ("mph", "m/s"),
            ("acre", "m2"),
            ("GB", "B"),
            ("cm", "mm"),
            ("yd", "ft"),
        ]
        for from_u, to_u in pairs:
            legacy = get_conversion_factor(normalize_unit(from_u), normalize_unit(to_u))
            reg_f = reg.conversion_factor(from_u, to_u)
            assert reg_f is not None, f"Registry returned None for {from_u}→{to_u}"
            assert (
                abs(legacy - reg_f) < 1e-10
            ), f"Factor mismatch {from_u}→{to_u}: legacy={legacy}, reg={reg_f}"

    def test_affine_returns_none(self):
        reg = build_unit_registry()
        assert reg.conversion_factor("K", "C") is None
        assert reg.conversion_factor("C", "F") is None

    def test_incompatible_dimensions_returns_none(self):
        reg = build_unit_registry()
        assert reg.conversion_factor("m", "kg") is None

    def test_unknown_unit_returns_none(self):
        reg = build_unit_registry()
        assert reg.conversion_factor("m", "foo") is None
        assert reg.conversion_factor("foo", "m") is None


# ---------------------------------------------------------------------------
# Structural dimension resolution
# ---------------------------------------------------------------------------


class TestStructuralDimension:
    """Structural dimension lookup for simple and compound units."""

    @pytest.mark.parametrize(
        "unit,expected_dim",
        [
            ("m", DIM_LENGTH),
            ("ft", DIM_LENGTH),
            ("km", DIM_LENGTH),
            ("kg", DIM_MASS),
            ("lb", DIM_MASS),
            ("s", DIM_TIME),
            ("hr", DIM_TIME),
            ("A", DIM_CURRENT),
            ("B", DIM_INFORMATION),
        ],
    )
    def test_simple_units(self, unit, expected_dim):
        dim = _structural_dimension(unit)
        assert dim is not None, f"No dimension for {unit}"
        assert dim == expected_dim, f"dim({unit}) = {dim}, expected {expected_dim}"

    @pytest.mark.parametrize(
        "unit,length,time,mass",
        [
            ("m/s", 1, -1, 0),
            ("m**2", 2, 0, 0),
            ("m**3", 3, 0, 0),
            ("kg*m/s**2", 1, -2, 1),
            ("m/s**2", 1, -2, 0),
        ],
    )
    def test_compound_units(self, unit, length, time, mass):
        from eggcalc.units import Dimension

        dim = _structural_dimension(unit)
        assert dim is not None, f"No dimension for compound {unit}"
        expected = Dimension(length=length, time=time, mass=mass)
        assert dim == expected, f"dim({unit}) = {dim}, expected {expected}"

    def test_same_dimension_different_category(self):
        """m**2 and ft**2 have same dimension despite different categories."""
        dim1 = _structural_dimension("m**2")
        dim2 = _structural_dimension("ft**2")
        assert dim1 is not None
        assert dim2 is not None
        assert dim1 == dim2

    def test_data_rate_vs_storage(self):
        """bps (data rate) differs from B (data storage)."""
        dim_bps = _structural_dimension("bps")
        dim_B = _structural_dimension("B")
        assert dim_bps is not None
        assert dim_B is not None
        assert dim_bps != dim_B


# ---------------------------------------------------------------------------
# Structural compatibility
# ---------------------------------------------------------------------------


class TestStructuralCompatibility:
    """are_units_compatible using structural dimensions."""

    def test_both_none(self):
        assert are_units_compatible(None, None) is True

    def test_one_none(self):
        assert are_units_compatible("m", None) is False
        assert are_units_compatible(None, "m") is False

    def test_same_base(self):
        assert are_units_compatible("m", "ft") is True
        assert are_units_compatible("kg", "lb") is True
        assert are_units_compatible("s", "hr") is True

    def test_different_base(self):
        assert are_units_compatible("m", "kg") is False
        assert are_units_compatible("s", "m") is False

    def test_compound_same_dimension(self):
        assert are_units_compatible("m**2", "ft**2") is True
        assert are_units_compatible("m/s", "mph") is True

    def test_compound_different_dimension(self):
        assert are_units_compatible("m**2", "m") is False
        assert are_units_compatible("m/s", "m") is False

    def test_temperature_same_dimension(self):
        assert are_units_compatible("K", "C") is True
        assert are_units_compatible("C", "F") is True

    def test_temperature_different_from_length(self):
        assert are_units_compatible("K", "m") is False

    def test_force_vs_energy(self):
        """N (force) ≠ J (energy) structurally."""
        assert are_units_compatible("N", "J") is False

    def test_pressure_vs_energy(self):
        """Pa (pressure) ≠ J (energy) structurally."""
        assert are_units_compatible("Pa", "J") is False


# ---------------------------------------------------------------------------
# UnitValue with structural dimensions
# ---------------------------------------------------------------------------


class TestUnitValueStructural:
    """UnitValue operations produce correct structural dimensions."""

    def test_multiplication_dimensions(self):
        result = UnitValue(2, "m") * UnitValue(3, "s")
        assert result.unit == "m*s"

    def test_division_dimensions(self):
        result = UnitValue(10, "m") / UnitValue(2, "s")
        assert result.unit == "m/s"

    def test_power_dimensions(self):
        result = UnitValue(5, "m") ** 2
        assert result.unit == "m**2"

    def test_addition_compatible(self):
        result = UnitValue(1, "m") + UnitValue(2, "ft")
        assert result.value > 0  # 1m + 2ft ≈ 1.6096m

    def test_addition_incompatible(self):
        with pytest.raises(ValueError):
            UnitValue(1, "m") + UnitValue(2, "kg")

    def test_same_unit_division_dimensionless(self):
        result = UnitValue(5, "m") / UnitValue(2, "m")
        assert result.unit is None

    def test_area_volume_distinct(self):
        """m**2 and m**3 are not compatible for addition."""
        with pytest.raises(ValueError):
            UnitValue(1, "m**2") + UnitValue(1, "m**3")


# ---------------------------------------------------------------------------
# Display compatibility (D7)
# ---------------------------------------------------------------------------


class TestDisplayCompatibility:
    """Existing display strings remain stable."""

    @pytest.mark.parametrize(
        "value,unit,expected",
        [
            (5, "m", "5 m"),
            (3.14, "kg", "3.14 kg"),
            (100, "ft", "100 ft"),
            (0, None, "0"),
        ],
    )
    def test_repr_stable(self, value, unit, expected):
        uv = UnitValue(value, unit)
        assert repr(uv) == expected

    def test_whole_float_shows_as_int(self):
        uv = UnitValue(5.0, "m")
        assert repr(uv) == "5 m"

    def test_fractional_float(self):
        uv = UnitValue(1.5, "kg")
        assert repr(uv) == "1.5 kg"


# ---------------------------------------------------------------------------
# Compound parsing resource bounds (C2)
# ---------------------------------------------------------------------------


class TestCompoundParsingBounds:
    """Compound parsing must enforce resource bounds."""

    def test_max_depth_exceeded_returns_none(self):
        """Exceeding MAX_COMPOUND_DEPTH must return None, not stack overflow."""
        # Build a deeply nested expression: "m/m/m/m/..." beyond depth limit
        depth = MAX_COMPOUND_DEPTH + 2
        deeply_nested = "/".join(["m"] * depth)
        with pytest.raises(ValueError):
            parse_unit_expression(deeply_nested)

    def test_max_string_length_exceeded_returns_none(self):
        """Exceeding MAX_UNIT_STRING_LENGTH must raise."""
        long_unit = "m" * (MAX_UNIT_STRING_LENGTH + 1)
        with pytest.raises(ValueError):
            parse_unit_expression(long_unit)

    def test_normal_depth_succeeds(self):
        """Normal compound expressions within bounds must parse successfully."""
        result = parse_unit_expression("m/s**2")
        assert result.factors == (("m", 1), ("s", -2))

    def test_max_depth_boundary_succeeds(self):
        """Expressions at exactly MAX_COMPOUND_DEPTH must parse."""
        depth = MAX_COMPOUND_DEPTH
        nested = "*".join(["m"] * depth)
        result = parse_unit_expression(nested)
        assert result is not None

    def test_max_atoms_exceeded_returns_none(self):
        """Exceeding MAX_COMPOUND_ATOMS must raise."""
        import eggcalc.units as u

        orig = u.MAX_COMPOUND_ATOMS
        try:
            u.MAX_COMPOUND_ATOMS = 3
            # 3 operators = 4 atoms, exceeds limit of 3
            with pytest.raises(ValueError):
                parse_unit_expression("m*s*kg*J")
        finally:
            u.MAX_COMPOUND_ATOMS = orig

    def test_max_atoms_boundary_succeeds(self):
        """Expressions below MAX_COMPOUND_ATOMS must parse."""
        import eggcalc.units as u

        orig = u.MAX_COMPOUND_ATOMS
        try:
            u.MAX_COMPOUND_ATOMS = 4
            # 3 operators = 4 atoms, within limit of 4
            result = parse_unit_expression("m*s*kg*J")
            assert result is not None
        finally:
            u.MAX_COMPOUND_ATOMS = orig


class TestDuplicateAliasRejection:
    """Registry construction must reject conflicting aliases (criterion 25)."""

    def test_conflicting_canonical_rejected(self):
        """Two aliases mapping to different canonicals must fail."""
        from eggcalc.units import DIM_LENGTH, DIM_TIME, UnitSpec, build_unit_registry

        with pytest.raises(ValueError, match="Duplicate alias"):
            build_unit_registry(
                (
                    UnitSpec(
                        "m",
                        ("m", "test_conflict_alias"),
                        DIM_LENGTH,
                        1.0,
                        category="length",
                        base_canonical="m",
                    ),
                    UnitSpec(
                        "s",
                        ("s", "test_conflict_alias"),
                        DIM_TIME,
                        1.0,
                        category="time",
                        base_canonical="s",
                    ),
                )
            )

    def test_no_conflict_succeeds(self):
        """Non-conflicting aliases must build successfully."""
        from eggcalc.units import DIM_LENGTH, UnitSpec, build_unit_registry

        reg = build_unit_registry(
            (
                UnitSpec(
                    "m",
                    ("m", "test_no_conflict"),
                    DIM_LENGTH,
                    1.0,
                    category="length",
                    base_canonical="m",
                ),
            )
        )
        assert "test_no_conflict" in reg.all_aliases


class TestUnitValueSafety:
    """UnitValue instances remain safe to use as hashed values."""

    def test_unit_value_is_immutable(self):
        value = UnitValue(5, "m")
        with pytest.raises(AttributeError):
            value.value = 10
        with pytest.raises(AttributeError):
            value.unit = "s"

    @pytest.mark.parametrize(
        "operation",
        [
            lambda: UnitValue(100, "C") * UnitValue(2),
            lambda: UnitValue(2) * UnitValue(100, "C"),
            lambda: UnitValue(100, "C") / UnitValue(2),
        ],
    )
    def test_affine_scalar_arithmetic_is_rejected(self, operation):
        with pytest.raises(ValueError, match="Affine"):
            operation()

    def test_cross_scale_temperature_addition_is_rejected(self):
        with pytest.raises(ValueError, match="different scales"):
            UnitValue(10, "C") + UnitValue(10, "F")
