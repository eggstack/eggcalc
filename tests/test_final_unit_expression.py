"""Bounded parser and structural arithmetic closure tests."""

from __future__ import annotations

import pytest

from eggcalc.units import (
    MAX_ABS_UNIT_EXPONENT,
    MAX_COMPOUND_ATOMS,
    MAX_COMPOUND_DEPTH,
    MAX_EXPONENT_DIGITS,
    MAX_UNIT_STRING_LENGTH,
    UnitValue,
    parse_unit_expression,
)


def test_parser_grammar_and_full_consumption() -> None:
    assert parse_unit_expression("m/s**2").factors == (("m", 1), ("s", -2))
    assert parse_unit_expression("kg*m/s**2").factors == (
        ("kg", 1),
        ("m", 1),
        ("s", -2),
    )
    for expression in ("m//s", "m%s", "m/s/ kg", "m**999999999"):
        with pytest.raises(ValueError):
            parse_unit_expression(expression)


def test_parser_enforces_resource_bounds() -> None:
    with pytest.raises(ValueError, match="exceeds"):
        parse_unit_expression("m" * (MAX_UNIT_STRING_LENGTH + 1))
    with pytest.raises(ValueError, match="Exponent"):
        parse_unit_expression(f"m**{MAX_ABS_UNIT_EXPONENT + 1}")
    with pytest.raises(ValueError, match="digits"):
        parse_unit_expression("m**" + "9" * (MAX_EXPONENT_DIGITS + 1))
    with pytest.raises(ValueError):
        parse_unit_expression("*".join("m" for _ in range(MAX_COMPOUND_ATOMS + 1)))
    assert MAX_COMPOUND_DEPTH >= 1


def test_affine_units_cannot_be_compounded() -> None:
    for expression in ("C/m", "C**2", "F/s"):
        with pytest.raises(ValueError, match="Affine"):
            parse_unit_expression(expression)
    with pytest.raises(ValueError, match="Affine"):
        UnitValue(20, "C") * UnitValue(2, "m")
    with pytest.raises(ValueError, match="Affine"):
        UnitValue(20, "C") / UnitValue(2, "s")
    with pytest.raises(ValueError, match="Affine"):
        UnitValue(20, "C") ** 2


def test_structural_unitvalue_arithmetic_and_legacy_floor_mod_policy() -> None:
    assert (UnitValue(1, "m") + UnitValue(100, "cm")).value == pytest.approx(2)
    assert (UnitValue(2, "m") * UnitValue(3, "m")).unit == "m**2"
    assert (UnitValue(10, "m") / UnitValue(2, "s")).unit == "m/s"
    assert (UnitValue(5, "m") / UnitValue(2, "m")).unit is None
    assert UnitValue(68, "F").convert_to("C").value == pytest.approx(20)
    assert (UnitValue(10, "m") // UnitValue(3, "m")).unit is None
    assert (UnitValue(10, "m") % UnitValue(3, "m")).unit == "m"
    with pytest.raises(ValueError):
        UnitValue(1, "m") // UnitValue(1, "s")


def test_dimensionless_cancellation_is_structural() -> None:
    result = UnitValue(5, "m") / UnitValue(2, "m")
    assert result.unit is None
    assert result._unit_expr.factors == ()
