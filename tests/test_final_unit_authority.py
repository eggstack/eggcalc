"""Final release closure tests for declarative unit authority."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eggcalc.units import (
    DIM_LENGTH,
    DIM_TEMPERATURE,
    UNIT_ALIASES,
    UNIT_BASE,
    UNIT_CATEGORIES,
    UNIT_DEFINITIONS,
    UnitSpec,
    build_unit_registry,
    convert_temperature,
    get_conversion_factor,
    get_unit_category,
    normalize_unit,
    parse_unit_expression,
)

FIXTURE = Path(__file__).parent / "fixtures" / "units" / "legacy-5a1bb34c.json"


def test_committed_legacy_fixture_has_exact_alias_coverage() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    aliases = fixture["aliases"]
    definitions_by_alias = {
        alias: spec.canonical for spec in UNIT_DEFINITIONS for alias in spec.aliases
    }
    assert set(definitions_by_alias) == set(aliases)
    assert definitions_by_alias == {alias: data["canonical"] for alias, data in aliases.items()}
    assert fixture["metadata"]["source_commit"] == "5a1bb34c9efa269ca6159217827f1742faa95d20"


def test_committed_fixture_matches_current_public_unit_behavior() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    by_canonical = {spec.canonical: spec for spec in UNIT_DEFINITIONS}
    for alias, expected in fixture["aliases"].items():
        spec = by_canonical[expected["canonical"]]
        assert normalize_unit(alias) == expected["normalized"]
        assert get_unit_category(alias) == expected["category"]
        expression = parse_unit_expression(alias)
        assert list(expression.dimension._tuple()) == expected["dimension"]
        assert spec.affine is expected["affine"]
        if expected["scale_to_base"] is not None:
            assert expression.scale_to_base == pytest.approx(expected["scale_to_base"])


def test_generated_compatibility_adapters_are_immutable() -> None:
    with pytest.raises(TypeError):
        UNIT_ALIASES["closure-test"] = "m"  # type: ignore[index]
    with pytest.raises(TypeError):
        UNIT_CATEGORIES["closure-test"] = "length"  # type: ignore[index]
    with pytest.raises(TypeError):
        UNIT_BASE["m"]["closure-test"] = 1.0  # type: ignore[index]


def test_temperature_declarations_are_registry_driven() -> None:
    assert convert_temperature(68.0, "F", "C") == pytest.approx(20.0)
    assert convert_temperature(20.0, "C", "F") == pytest.approx(68.0)
    assert convert_temperature(0.0, "C", "K") == pytest.approx(273.15)
    assert get_conversion_factor("km", "m") == pytest.approx(1000.0)
    assert all(spec.dimension == DIM_TEMPERATURE for spec in UNIT_DEFINITIONS if spec.affine)


def test_definition_validation_rejects_conflicting_semantics() -> None:
    base = UnitSpec("m", ("m",), DIM_LENGTH, 1.0, category="length", base_canonical="m")

    with pytest.raises(ValueError, match="Duplicate canonical"):
        build_unit_registry((base, base))
    with pytest.raises(ValueError, match="Canonical"):
        build_unit_registry(
            (UnitSpec("m", ("other",), DIM_LENGTH, 1.0, category="length", base_canonical="m"),)
        )
    with pytest.raises(ValueError, match="Base canonical"):
        build_unit_registry(
            (UnitSpec("m", ("m",), DIM_LENGTH, 1.0, category="length", base_canonical="missing"),)
        )
    with pytest.raises(ValueError, match="Affine"):
        build_unit_registry(
            (
                UnitSpec(
                    "m",
                    ("m",),
                    DIM_LENGTH,
                    1.0,
                    affine=True,
                    category="length",
                    base_canonical="m",
                ),
            )
        )
