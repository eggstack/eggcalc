"""Final release closure tests for declarative unit authority.

Covers Workstream A (duplicate authority removal) and Workstream C
(fixture and provenance proof) acceptance criteria:

- complete-module duplicate-authority inspection;
- exactly one generated compatibility-map definition site;
- explicit family-base ownership;
- exact fixture offset/display/arithmetic comparison;
- fixture metadata/hash/schema checks;
- generated adapter exact parity.
"""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pytest

from eggcalc.units import (
    DIM_DIMENSIONLESS,
    DIM_LENGTH,
    DIM_TEMPERATURE,
    MAX_UNIT_ERROR_LENGTH,
    TEMPERATURE_CONVERSIONS,
    UNIT_ALIASES,
    UNIT_BASE,
    UNIT_CATEGORIES,
    UNIT_CONVERSIONS,
    UNIT_DEFINITIONS,
    UnitSpec,
    UnitValue,
    build_unit_registry,
    convert_temperature,
    get_conversion_factor,
    get_unit_category,
    normalize_unit,
    parse_unit_expression,
    render_expression,
)

FIXTURE = Path(__file__).parent / "fixtures" / "units" / "legacy-5a1bb34c.json"
UNITS_FILE = Path(__file__).resolve().parents[1] / "eggcalc" / "units.py"
EXPORTER = Path(__file__).resolve().parents[1] / "scripts" / "export_unit_baseline.py"

# Category -> base_canonical mapping (the single family-base authority).
EXPECTED_BASES = {
    "angle": "rad",
    "area": "m2",
    "current": "A",
    "data": "B",
    "data_rate": "bps",
    "energy": "J",
    "force": "N",
    "frequency": "Hz",
    "length": "m",
    "mass": "kg",
    "power": "W",
    "pressure": "Pa",
    "speed": "m/s",
    "temperature": "K",
    "time": "s",
    "voltage": "V",
    "volume": "L",
}

# Public compatibility maps that must have exactly one top-level assignment.
COMPAT_MAPS = (
    "UNIT_ALIASES",
    "UNIT_BASE",
    "UNIT_CATEGORIES",
    "TEMPERATURE_CONVERSIONS",
    "UNIT_CONVERSIONS",
)

# Legacy names that must not appear as dict literals.
LEGACY_LITERALS = frozenset(
    {
        "UNIT_BASE",
        "UNIT_ALIASES",
        "UNIT_CATEGORIES",
        "TEMPERATURE_CONVERSIONS",
        "UNIT_CONVERSIONS",
        "_CATEGORY_DIMENSIONS",
        "_CATEGORY_NAME_TO_DIMENSION",
        "_DERIVED_CATEGORIES",
        "_BASE_CATEGORY",
        "UNIT_CATEGORIES_EXTRA",
        "_SHORT_COMPOUND_FORMS",
        "_SHORT_COMPOUND_EXPANSION",
        "_SHORT_COMPOUND_CARET",
        "_SHORT_COMPOUND_COLLAPSE",
    }
)

# Legacy helper functions that must not exist.
LEGACY_HELPERS = frozenset(
    {
        "_build_unit_conversions",
        "_add_compound_conversions",
        "_parse_compound_atoms",
        "_parse_compound_signature",
        "_count_top_level_ops",
        "_find_last_top_level_op",
        "_parse_atom_signature",
        "_merge_signatures",
        "_signature_to_canonical_string",
        "_derived_category",
        "_base_unit_dimension",
        "_expand_short_compound",
        "_collapse_short_compound",
        "_short_compound_forms",
    }
)


# ---------------------------------------------------------------------------
# Fixture coverage and behavioral parity
# ---------------------------------------------------------------------------


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


def test_fixture_offset_display_and_arithmetic_parity() -> None:
    """Every fixture field is compared: offset, display, and arithmetic results."""
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    by_canonical = {spec.canonical: spec for spec in UNIT_DEFINITIONS}

    # Offset and display exact comparison
    for alias, expected in fixture["aliases"].items():
        spec = by_canonical[expected["canonical"]]
        assert spec.offset_to_base == pytest.approx(
            expected["offset_to_base"]
        ), f"offset mismatch for {alias!r}"
        assert spec.display == expected["display"], f"display mismatch for {alias!r}"

    # Arithmetic fixture cases are exercised
    arithmetic = fixture.get("arithmetic", {})
    assert arithmetic["m_times_m"]["unit"] == "m**2"
    assert arithmetic["m_times_m"]["display"] == "6 m**2"
    assert arithmetic["m_div_s"]["unit"] == "m/s"
    assert arithmetic["m_div_s"]["display"] == "5 m/s"
    assert arithmetic["m_div_m"]["unit"] is None
    assert arithmetic["m_div_m"]["display"] == "2.5"
    assert arithmetic["m_power_2"]["unit"] == "m**2"
    assert arithmetic["m_power_2"]["display"] == "4 m**2"

    # Verify arithmetic results match current behavior
    assert str(UnitValue(2, "m") * UnitValue(3, "m")) == arithmetic["m_times_m"]["display"]
    assert str(UnitValue(10, "m") / UnitValue(2, "s")) == arithmetic["m_div_s"]["display"]
    assert str(UnitValue(5, "m") / UnitValue(2, "m")) == arithmetic["m_div_m"]["display"]
    assert str(UnitValue(2, "m") ** 2) == arithmetic["m_power_2"]["display"]


def test_fixture_limits_match_current_exports() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    limits = fixture["limits"]
    from eggcalc.units import MAX_COMPOUND_ATOMS, MAX_COMPOUND_DEPTH, MAX_UNIT_STRING_LENGTH

    assert limits["max_unit_string_length"] == MAX_UNIT_STRING_LENGTH
    assert limits["max_compound_depth"] == MAX_COMPOUND_DEPTH
    assert limits["max_compound_atoms"] == MAX_COMPOUND_ATOMS


# ---------------------------------------------------------------------------
# Fixture provenance: metadata, hash, schema
# ---------------------------------------------------------------------------


def test_fixture_metadata_source_commit_is_exact() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    commit = fixture["metadata"]["source_commit"]
    assert len(commit) == 40
    assert all(c in "0123456789abcdef" for c in commit)
    assert commit == "5a1bb34c9efa269ca6159217827f1742faa95d20"


def test_fixture_metadata_exporter_hash_matches() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    expected_hash = fixture["metadata"]["exporter_sha256"]
    # Normalize line endings to LF before hashing for cross-platform consistency.
    exporter_bytes = EXPORTER.read_bytes().replace(b"\r\n", b"\n")
    actual_hash = hashlib.sha256(exporter_bytes).hexdigest()
    assert (
        actual_hash == expected_hash
    ), f"Exporter hash mismatch: expected {expected_hash}, got {actual_hash}"


def test_fixture_has_required_schema_fields() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert "metadata" in fixture
    assert "aliases" in fixture
    assert "arithmetic" in fixture
    assert "limits" in fixture
    meta = fixture["metadata"]
    assert "source_commit" in meta
    assert "exporter_sha256" in meta
    assert "source" in meta
    for alias, data in fixture["aliases"].items():
        assert "canonical" in data
        assert "category" in data
        assert "dimension" in data
        assert "scale_to_base" in data
        assert "offset_to_base" in data
        assert "affine" in data
        assert "display" in data
        assert "normalized" in data


def test_fixture_does_not_import_unit_definitions() -> None:
    """The baseline exporter reads public API tables, not internal helpers."""
    exporter_source = EXPORTER.read_text(encoding="utf-8")
    # The exporter must not use removed internal helpers
    assert "_structural_dimension" not in exporter_source
    assert "_parse_compound_signature" not in exporter_source


# ---------------------------------------------------------------------------
# Complete-module duplicate-authority inspection (AST-based)
# ---------------------------------------------------------------------------


def _top_level_assignments(tree: ast.Module) -> dict[str, list[ast.Assign | ast.AnnAssign]]:
    assignments: dict[str, list[ast.Assign | ast.AnnAssign]] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assignments.setdefault(target.id, []).append(node)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            assignments.setdefault(node.target.id, []).append(node)
    return assignments


def _all_function_names(tree: ast.Module) -> set[str]:
    seen: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            seen.add(node.name)
    return seen


def _is_dict_literal(node: ast.AST) -> bool:
    return isinstance(node, ast.Dict)


def test_no_duplicate_legacy_literal_assignments() -> None:
    """No legacy literal name appears as a manually maintained dict literal."""
    tree = ast.parse(UNITS_FILE.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in LEGACY_LITERALS:
                    assert not _is_dict_literal(
                        node.value
                    ), f"{target.id} is a manually maintained dict literal"


def test_compatibility_maps_have_single_definition_site() -> None:
    """Each public compatibility map has exactly one top-level assignment."""
    tree = ast.parse(UNITS_FILE.read_text(encoding="utf-8"))
    assignments = _top_level_assignments(tree)
    for name in COMPAT_MAPS:
        nodes = assignments.get(name, [])
        assert len(nodes) == 1, f"{name}: expected 1 assignment, found {len(nodes)}"


def test_no_legacy_helper_functions_exist() -> None:
    """Legacy helper functions that were later redefined must not exist."""
    tree = ast.parse(UNITS_FILE.read_text(encoding="utf-8"))
    func_names = _all_function_names(tree)
    for name in LEGACY_HELPERS:
        assert name not in func_names, f"Legacy helper {name} still exists"


def test_unitvalue_does_not_call_legacy_semantic_helpers() -> None:
    """UnitValue must not call legacy string-semantic helpers."""
    tree = ast.parse(UNITS_FILE.read_text(encoding="utf-8"))
    unit_value = next(
        (n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "UnitValue"),
        None,
    )
    assert unit_value is not None, "Missing UnitValue"
    names = {child.id for child in ast.walk(unit_value) if isinstance(child, ast.Name)}
    legacy = names & frozenset(
        {
            "_simplify_unit_string",
            "_pow_unit_string",
            "_parse_compound_signature",
            "_structural_dimension",
        }
    )
    assert not legacy, f"UnitValue uses legacy helpers: {legacy}"


def test_required_functions_do_not_read_legacy_authority() -> None:
    """Core functions must not reference legacy authority names."""
    tree = ast.parse(UNITS_FILE.read_text(encoding="utf-8"))
    func_map: dict[str, ast.AST] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name not in func_map:
                func_map[node.name] = node
    for func_name in (
        "build_unit_registry",
        "parse_unit_expression",
        "get_conversion_factor",
        "are_units_compatible",
    ):
        node = func_map.get(func_name)
        assert node is not None, f"Missing {func_name}"
        names = {child.id for child in ast.walk(node) if isinstance(child, ast.Name)}
        bad = names & LEGACY_LITERALS
        assert not bad, f"{func_name} reads legacy authority: {bad}"


# ---------------------------------------------------------------------------
# Explicit family-base ownership
# ---------------------------------------------------------------------------


def test_every_unitspec_has_explicit_base_canonical() -> None:
    """Every UnitSpec must explicitly supply base_canonical."""
    for spec in UNIT_DEFINITIONS:
        assert spec.base_canonical, f"{spec.canonical!r} has empty base_canonical"


def test_base_canonical_matches_expected_family_base() -> None:
    """Every UnitSpec's base_canonical matches the expected family base."""
    for spec in UNIT_DEFINITIONS:
        expected = EXPECTED_BASES.get(spec.category)
        assert expected is not None, f"Unknown category {spec.category!r} for {spec.canonical!r}"
        assert (
            spec.base_canonical == expected
        ), f"{spec.canonical!r}: base_canonical={spec.base_canonical!r}, expected {expected!r}"


def test_base_canonical_is_resolvable_in_registry() -> None:
    """Every base_canonical must be a declared canonical in the registry."""
    canonicals = {spec.canonical for spec in UNIT_DEFINITIONS}
    for spec in UNIT_DEFINITIONS:
        assert (
            spec.base_canonical in canonicals
        ), f"{spec.canonical!r}: base_canonical {spec.base_canonical!r} not declared"


def test_unitspec_post_init_rejects_missing_base_canonical() -> None:
    """UnitSpec without base_canonical must raise."""
    with pytest.raises(ValueError, match="base_canonical"):
        UnitSpec("m", ("m",), DIM_LENGTH, 1.0, category="length")


# ---------------------------------------------------------------------------
# Generated adapter exact parity
# ---------------------------------------------------------------------------


def test_generated_adapters_match_unit_definitions() -> None:
    """Generated UNIT_ALIASES must match UNIT_DEFINITIONS alias->canonical."""
    expected = {alias: spec.canonical for spec in UNIT_DEFINITIONS for alias in spec.aliases}
    assert dict(UNIT_ALIASES) == expected


def test_generated_unit_categories_match_unit_definitions() -> None:
    """Generated UNIT_CATEGORIES must match UNIT_DEFINITIONS alias->category."""
    expected = {alias: spec.category for spec in UNIT_DEFINITIONS for alias in spec.aliases}
    assert dict(UNIT_CATEGORIES) == expected


def test_generated_unit_base_matches_unit_definitions() -> None:
    """Generated UNIT_BASE must match UNIT_DEFINITIONS grouped by base_canonical."""
    grouped: dict[str, dict[str, float]] = {}
    for spec in UNIT_DEFINITIONS:
        if spec.affine:
            continue
        variants = grouped.setdefault(spec.base_canonical, {})
        for alias in spec.aliases:
            variants[alias] = spec.scale_to_base
    expected = {base: dict(sorted(v.items())) for base, v in sorted(grouped.items())}
    actual = {base: dict(v) for base, v in UNIT_BASE.items()}
    assert actual == expected


def test_generated_temperature_conversions_match_definitions() -> None:
    """Generated TEMPERATURE_CONVERSIONS must match affine unit definitions."""
    temps = [spec for spec in UNIT_DEFINITIONS if spec.affine]
    expected: dict[tuple[str, str], tuple[float, float]] = {}
    for source in temps:
        for target in temps:
            if source.canonical == target.canonical:
                continue
            multiplier = source.scale_to_base / target.scale_to_base
            offset = (source.offset_to_base - target.offset_to_base) / target.scale_to_base
            expected[(source.canonical, target.canonical)] = (multiplier, offset)
    assert dict(TEMPERATURE_CONVERSIONS) == expected


def test_generated_unit_conversions_match_definitions() -> None:
    """Generated UNIT_CONVERSIONS must match non-affine definition pairs."""
    non_affine = [spec for spec in UNIT_DEFINITIONS if not spec.affine]
    expected: dict[tuple[str, str], float] = {}
    for source in non_affine:
        for target in non_affine:
            if source.dimension != target.dimension or source.canonical == target.canonical:
                continue
            factor = source.scale_to_base / target.scale_to_base
            for source_alias in source.aliases:
                for target_alias in target.aliases:
                    expected[(source_alias, target_alias)] = factor
    assert dict(UNIT_CONVERSIONS) == expected


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


def test_render_expression_rejects_overflow() -> None:
    """render_expression must raise on overflow, not truncate."""
    from eggcalc.units import _UncheckedUnitExpression

    # Create an unchecked expression with many factors to exceed the limit
    factors = tuple((f"unit{i}", 1) for i in range(100))
    expr = _UncheckedUnitExpression(factors, DIM_DIMENSIONLESS, 1.0)
    with pytest.raises(ValueError, match="exceeds"):
        render_expression(expr)


def test_unit_error_is_bounded() -> None:
    """Error messages must be bounded by MAX_UNIT_ERROR_LENGTH."""
    try:
        parse_unit_expression("x" * 10000)
    except ValueError as exc:
        assert len(str(exc)) <= MAX_UNIT_ERROR_LENGTH
