"""Tests for UnitSpec, UNIT_DEFINITIONS, and UnitExpression.

Part 1: UnitSpec and UNIT_DEFINITIONS validation
Part 2: Baseline fixture and tests
Part 3: UnitExpression tests
"""

from __future__ import annotations

import json
import math

import pytest

from eggcalc.units import (
    MAX_UNIT_STRING_LENGTH,
    UNIT_ALIASES,
    UNIT_BASE,
    UnitSpec,
    normalize_unit,
    parse_unit_expression,
)

# ---------------------------------------------------------------------------
# Part 1: UNIT_DEFINITIONS validation
# ---------------------------------------------------------------------------


class TestUnitDefinitionsValidation:
    """UNIT_DEFINITIONS must pass validation at module load time."""

    def test_module_loads(self):
        from eggcalc.units import UNIT_DEFINITIONS

        assert len(UNIT_DEFINITIONS) > 0

    def test_all_entries_are_unitspec(self):
        from eggcalc.units import UNIT_DEFINITIONS

        for spec in UNIT_DEFINITIONS:
            assert isinstance(spec, UnitSpec)

    def test_no_duplicate_canonicals(self):
        from eggcalc.units import UNIT_DEFINITIONS

        canonicals = [s.canonical for s in UNIT_DEFINITIONS]
        assert len(canonicals) == len(set(canonicals))

    def test_no_empty_canonicals(self):
        from eggcalc.units import UNIT_DEFINITIONS

        for spec in UNIT_DEFINITIONS:
            assert spec.canonical, f"Empty canonical in {spec}"

    def test_no_empty_aliases(self):
        from eggcalc.units import UNIT_DEFINITIONS

        for spec in UNIT_DEFINITIONS:
            for alias in spec.aliases:
                assert alias, f"Empty alias in {spec.canonical}"

    def test_no_zero_scales(self):
        from eggcalc.units import UNIT_DEFINITIONS

        for spec in UNIT_DEFINITIONS:
            assert spec.scale_to_base != 0, f"Zero scale for {spec.canonical}"

    def test_all_scales_finite(self):
        from eggcalc.units import UNIT_DEFINITIONS

        for spec in UNIT_DEFINITIONS:
            assert math.isfinite(spec.scale_to_base), f"Non-finite scale for {spec.canonical}"


# ---------------------------------------------------------------------------
# Part 2: Baseline coverage tests
# ---------------------------------------------------------------------------


class TestBaselineCoverage:
    """Every existing alias must map to a canonical in UNIT_DEFINITIONS."""

    def test_all_aliases_resolved(self):
        from eggcalc.units import UNIT_DEFINITIONS

        defs_by_canonical = {s.canonical: s for s in UNIT_DEFINITIONS}
        defs_by_alias: dict[str, str] = {}
        for spec in UNIT_DEFINITIONS:
            for alias in spec.aliases:
                defs_by_alias[alias] = spec.canonical

        for alias, canonical in UNIT_ALIASES.items():
            if alias in defs_by_alias:
                assert defs_by_alias[alias] == canonical, (
                    f"Alias {alias!r}: UNIT_ALIASES says {canonical!r}, "
                    f"UNIT_DEFINITIONS says {defs_by_alias[alias]!r}"
                )

    def test_no_duplicate_aliases_in_definitions(self):
        from eggcalc.units import UNIT_DEFINITIONS

        seen: dict[str, str] = {}
        for spec in UNIT_DEFINITIONS:
            for alias in spec.aliases:
                if alias in seen:
                    assert seen[alias] == spec.canonical, (
                        f"Duplicate alias {alias!r}: maps to both "
                        f"{seen[alias]!r} and {spec.canonical!r}"
                    )
                seen[alias] = spec.canonical

    def test_category_coverage_matches(self):
        from eggcalc.units import UNIT_DEFINITIONS

        # Every base unit in UNIT_BASE should appear in UNIT_DEFINITIONS
        for base_key, variants in UNIT_BASE.items():
            for variant_name in variants:
                # variant might be aliased to a different canonical
                alias_canonical = normalize_unit(variant_name)
                found = any(
                    alias_canonical in s.aliases or s.canonical == alias_canonical
                    for s in UNIT_DEFINITIONS
                )
                assert found, (
                    f"Variant {variant_name!r} (base={base_key!r}) "
                    f"not covered by UNIT_DEFINITIONS"
                )

    def test_temperature_units_present(self):
        from eggcalc.units import UNIT_DEFINITIONS

        temp_canonicals = {s.canonical for s in UNIT_DEFINITIONS if s.category == "temperature"}
        assert "K" in temp_canonicals
        assert "C" in temp_canonicals
        assert "F" in temp_canonicals
        assert "Ra" in temp_canonicals

    def test_temperature_conversions_preserved(self):
        """Known temperature conversion values must match TEMPERATURE_CONVERSIONS."""
        from eggcalc.units import UNIT_DEFINITIONS

        defs_by_canonical = {s.canonical: s for s in UNIT_DEFINITIONS}

        # K -> C: value * 1.0 + (-273.15)
        k_spec = defs_by_canonical["K"]
        c_spec = defs_by_canonical["C"]
        assert k_spec.scale_to_base == 1.0
        assert c_spec.scale_to_base == 1.0
        assert c_spec.offset_to_base == 273.15
        assert c_spec.affine is True

        # F -> K: value * (5/9) + 255.3722222222222
        f_spec = defs_by_canonical["F"]
        assert f_spec.scale_to_base == 5.0 / 9.0
        assert f_spec.offset_to_base == 255.3722222222222
        assert f_spec.affine is True

        # Ra -> K: value * (5/9)
        ra_spec = defs_by_canonical["Ra"]
        assert ra_spec.scale_to_base == 5.0 / 9.0
        assert ra_spec.offset_to_base == 0.0
        assert ra_spec.affine is True

    def test_known_conversions_round_trip(self):
        """UNIT_DEFINITIONS scale factors must agree with get_conversion_factor."""
        from eggcalc.units import UNIT_DEFINITIONS, get_conversion_factor

        defs_by_canonical = {s.canonical: s for s in UNIT_DEFINITIONS}
        pairs = [
            ("km", "m"),
            ("ft", "in"),
            ("lb", "kg"),
            ("gal", "L"),
            ("kWh", "J"),
        ]
        for from_u, to_u in pairs:
            from_spec = defs_by_canonical.get(from_u)
            to_spec = defs_by_canonical.get(to_u)
            if from_spec and to_spec:
                expected = from_spec.scale_to_base / to_spec.scale_to_base
                actual = get_conversion_factor(from_u, to_u)
                assert abs(expected - actual) < 1e-10, (
                    f"Scale mismatch {from_u}->{to_u}: "
                    f"UNIT_DEFINITIONS={expected}, get_conversion_factor={actual}"
                )


# ---------------------------------------------------------------------------
# Part 2: Baseline fixture
# ---------------------------------------------------------------------------


class TestBaselineFixture:
    """Generate and validate the baseline fixture."""

    def test_generate_baseline_fixture(self, tmp_path):
        """Generate baseline.json capturing current unit surface."""
        from eggcalc.units import UNIT_DEFINITIONS

        fixture = {}
        for spec in UNIT_DEFINITIONS:
            fixture[spec.canonical] = {
                "aliases": list(spec.aliases),
                "dimension": spec.dimension._tuple(),
                "scale_to_base": spec.scale_to_base,
                "offset_to_base": spec.offset_to_base,
                "affine": spec.affine,
                "category": spec.category,
            }

        fixture_path = tmp_path / "baseline.json"
        fixture_path.write_text(json.dumps(fixture, indent=2))

        # Verify it's valid JSON and has expected structure
        loaded = json.loads(fixture_path.read_text())
        assert len(loaded) == len(UNIT_DEFINITIONS)
        for canonical, data in loaded.items():
            assert "aliases" in data
            assert "dimension" in data
            assert "scale_to_base" in data
            assert "category" in data


# ---------------------------------------------------------------------------
# Part 3: UnitExpression tests
# ---------------------------------------------------------------------------


class TestUnitExpression:
    """UnitExpression parsing and structural representation."""

    def test_simple_unit(self):
        expr = parse_unit_expression("m")
        assert expr.factors == (("m", 1),)
        assert expr.dimension.length == 1
        assert expr.scale_to_base == 1.0

    def test_division(self):
        expr = parse_unit_expression("m/s")
        assert expr.factors == (("m", 1), ("s", -1))
        assert expr.dimension.length == 1
        assert expr.dimension.time == -1

    def test_multiplication(self):
        expr = parse_unit_expression("kg*m/s**2")
        assert expr.factors == (("kg", 1), ("m", 1), ("s", -2))
        assert expr.dimension.mass == 1
        assert expr.dimension.length == 1
        assert expr.dimension.time == -2

    def test_power(self):
        expr = parse_unit_expression("m**2")
        assert expr.factors == (("m", 2),)
        assert expr.dimension.length == 2

    def test_negative_power(self):
        expr = parse_unit_expression("m**-1")
        assert expr.factors == (("m", -1),)
        assert expr.dimension.length == -1

    def test_compound_with_prefix(self):
        expr = parse_unit_expression("km/h")
        assert ("km", 1) in expr.factors
        assert ("h", -1) in expr.factors
        # km = 1000m, h = 3600s
        expected_scale = 1000.0 / 3600.0
        assert abs(expr.scale_to_base - expected_scale) < 1e-10

    def test_cancellation(self):
        """m*m/s should simplify to m**2/s."""
        expr = parse_unit_expression("m*m/s")
        assert ("m", 2) in expr.factors
        assert ("s", -1) in expr.factors

    def test_full_cancellation(self):
        """m/m should be dimensionless (empty factors)."""
        expr = parse_unit_expression("m/m")
        assert expr.factors == ()

    def test_frozen(self):
        """UnitExpression must be immutable."""
        expr = parse_unit_expression("m/s")
        with pytest.raises(AttributeError):
            expr.factors = ()
        with pytest.raises(AttributeError):
            expr.dimension = None

    def test_empty_string_rejected(self):
        with pytest.raises(ValueError, match="Empty"):
            parse_unit_expression("")

    def test_long_string_rejected(self):
        with pytest.raises(ValueError, match="exceeds"):
            parse_unit_expression("m" * (MAX_UNIT_STRING_LENGTH + 1))

    def test_double_slash_rejected(self):
        with pytest.raises(ValueError, match="not allowed"):
            parse_unit_expression("m//s")

    def test_percent_rejected(self):
        with pytest.raises(ValueError, match="not allowed"):
            parse_unit_expression("m%s")

    def test_unknown_unit_rejected(self):
        with pytest.raises(ValueError, match="Unknown unit"):
            parse_unit_expression("frobnicate/s")

    def test_unrecognized_form_rejected(self):
        with pytest.raises(ValueError, match="Cannot parse"):
            parse_unit_expression("!!!invalid!!!")

    def test_dimension_consistency_with_arithmetic(self):
        """parse_unit_expression dimension must match Dimension arithmetic."""
        from eggcalc.units import DIM_LENGTH, DIM_TIME

        expr = parse_unit_expression("m/s")
        expected_dim = DIM_LENGTH / DIM_TIME
        assert expr.dimension == expected_dim

    def test_scale_consistency_with_conversion(self):
        """parse_unit_expression scale must match get_conversion_factor."""
        from eggcalc.units import get_conversion_factor

        expr = parse_unit_expression("km/h")
        # km -> m factor: 1000
        # h -> s factor: 3600
        # km/h -> m/s: 1000/3600
        factor = get_conversion_factor("km/h", "m/s")
        assert abs(expr.scale_to_base - factor) < 1e-10
