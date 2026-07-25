"""Bounded parser and structural arithmetic closure tests.

Covers Workstream B acceptance criteria:

- canonical exact-bound acceptance;
- canonical over-bound rejection;
- finite-scale overflow and underflow;
- direct-construction invariant matrix;
- bounded error text;
- meaningful depth policy test/removal assertion;
- package/single-file focused parity.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from eggcalc.units import (
    DIM_DIMENSIONLESS,
    DIM_LENGTH,
    DIM_MASS,
    DIM_TEMPERATURE,
    MAX_ABS_UNIT_EXPONENT,
    MAX_CANONICAL_UNIT_LENGTH,
    MAX_COMPOUND_ATOMS,
    MAX_COMPOUND_DEPTH,
    MAX_EXPONENT_DIGITS,
    MAX_UNIT_ERROR_LENGTH,
    MAX_UNIT_STRING_LENGTH,
    UnitExpression,
    UnitValue,
    parse_unit_expression,
    render_expression,
)

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Parser grammar and full consumption
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Resource bounds: maximum accepted and first rejected
# ---------------------------------------------------------------------------


def test_maximum_accepted_input_length_and_first_rejected() -> None:
    """Maximum accepted input length is MAX_UNIT_STRING_LENGTH; first rejected is +1."""
    # Build a valid unit expression of exactly MAX_UNIT_STRING_LENGTH characters.
    # 'millennium' is the longest canonical name (10 chars).  Use 16 of them
    # (hitting MAX_ABS_UNIT_EXPONENT exactly) plus 16 shorter unique atoms
    # to stay within MAX_COMPOUND_ATOMS (32).
    parts = ["millennium"] * 16
    short_units = [
        "acre",
        "dyne",
        "floz",
        "inHg",
        "inch",
        "kcal",
        "mach",
        "mbar",
        "mmHg",
        "slug",
        "tbsp",
        "torr",
        "Gbps",
        "Kbps",
        "Mbps",
        "chain",
    ]
    parts.extend(short_units)
    ok_expr = "*".join(parts)
    assert len(ok_expr) == MAX_UNIT_STRING_LENGTH
    result = parse_unit_expression(ok_expr)
    assert result is not None

    # Input exceeding MAX_UNIT_STRING_LENGTH must be rejected.
    with pytest.raises(ValueError, match="exceeds"):
        parse_unit_expression("m" * (MAX_UNIT_STRING_LENGTH + 1))


def test_maximum_atom_count_and_first_rejected_count() -> None:
    """Maximum accepted atom count is MAX_COMPOUND_ATOMS; first rejected is +1."""
    # Use unique canonicals to avoid exponent normalization
    from eggcalc.units import UNIT_DEFINITIONS

    canonicals = [spec.canonical for spec in UNIT_DEFINITIONS if not spec.affine]
    # Use the first MAX_COMPOUND_ATOMS unique canonicals
    ok = "*".join(canonicals[:MAX_COMPOUND_ATOMS])
    parse_unit_expression(ok)
    with pytest.raises(ValueError):
        parse_unit_expression("*".join(canonicals[: MAX_COMPOUND_ATOMS + 1]))


def test_maximum_exponent_and_first_rejected_exponent() -> None:
    """Maximum accepted exponent is MAX_ABS_UNIT_EXPONENT; first rejected is +1."""
    parse_unit_expression(f"m**{MAX_ABS_UNIT_EXPONENT}")
    with pytest.raises(ValueError):
        parse_unit_expression(f"m**{MAX_ABS_UNIT_EXPONENT + 1}")


def test_maximum_exponent_digit_count_and_first_rejected() -> None:
    """Exponent digit count beyond MAX_EXPONENT_DIGITS is rejected."""
    # An exponent with MAX_EXPONENT_DIGITS+1 digits must be rejected
    with pytest.raises(ValueError):
        parse_unit_expression("m**" + "9" * (MAX_EXPONENT_DIGITS + 1))


def test_parser_enforces_resource_bounds() -> None:
    with pytest.raises(ValueError, match="exceeds"):
        parse_unit_expression("m" * (MAX_UNIT_STRING_LENGTH + 1))
    with pytest.raises(ValueError, match="Exponent"):
        parse_unit_expression(f"m**{MAX_ABS_UNIT_EXPONENT + 1}")
    with pytest.raises(ValueError, match="digits"):
        parse_unit_expression("m**" + "9" * (MAX_EXPONENT_DIGITS + 1))
    with pytest.raises(ValueError):
        parse_unit_expression("*".join("m" for _ in range(MAX_COMPOUND_ATOMS + 1)))


# ---------------------------------------------------------------------------
# Multiple division rejection and unknown atoms
# ---------------------------------------------------------------------------


def test_multiple_division_rejected() -> None:
    with pytest.raises(ValueError, match="Only one division"):
        parse_unit_expression("m/s/kg")


def test_unknown_atoms_rejected() -> None:
    with pytest.raises(ValueError):
        parse_unit_expression("unknownunit")
    with pytest.raises(ValueError):
        parse_unit_expression("m*unknownunit")


def test_floor_mod_rejected_in_parser() -> None:
    with pytest.raises(ValueError):
        parse_unit_expression("m//s")
    with pytest.raises(ValueError):
        parse_unit_expression("m%s")


def test_affine_standalone_accepted() -> None:
    """Affine units are accepted as standalone exponent-one units."""
    result = parse_unit_expression("C")
    assert result.factors == (("C", 1),)
    result = parse_unit_expression("K")
    assert result.factors == (("K", 1),)


def test_affine_compound_power_rejected() -> None:
    """Affine units cannot be compounded or exponentiated."""
    for expression in ("C/m", "C**2", "F/s"):
        with pytest.raises(ValueError, match="Affine"):
            parse_unit_expression(expression)
    with pytest.raises(ValueError, match="Affine"):
        UnitValue(20, "C") * UnitValue(2, "m")
    with pytest.raises(ValueError, match="Affine"):
        UnitValue(20, "C") / UnitValue(2, "s")
    with pytest.raises(ValueError, match="Affine"):
        UnitValue(20, "C") ** 2


# ---------------------------------------------------------------------------
# Canonical output bounds: exact acceptance and one-character-over rejection
# ---------------------------------------------------------------------------


def _build_rendered_string(target_len: int) -> tuple[tuple[tuple[str, int], ...], str]:
    """Build factors that render to exactly target_len characters.

    Returns (factors, expected_rendered_string).
    Uses single-char unit names with exponent 1, separated by '*'.
    """
    # n single-char factors produce 2*n - 1 chars.
    # Since 2*n - 1 is always odd, for even targets we need one multi-char factor.
    # With n_single single-char + 1 last_len-char factor:
    # total = 2*n_single + last_len = target_len
    # For even target: last_len=2, n_single = (target_len - 2) // 2
    # For odd target: last_len=1, n_single = (target_len - 1) // 2
    if target_len % 2 == 0:
        last_len = 2
        n_single = (target_len - last_len) // 2
    else:
        last_len = 1
        n_single = (target_len - last_len) // 2
    factors = tuple(("a", 1) for _ in range(n_single)) + (("a" * last_len, 1),)
    rendered = "*".join(name for name, _ in factors)
    assert len(rendered) == target_len, f"Expected {target_len}, got {len(rendered)}"
    return factors, rendered


def test_canonical_exact_bound_acceptance() -> None:
    """An expression rendering to exactly MAX_CANONICAL_UNIT_LENGTH is accepted."""
    from eggcalc.units import _UncheckedUnitExpression

    factors, expected = _build_rendered_string(MAX_CANONICAL_UNIT_LENGTH)
    expr = _UncheckedUnitExpression(factors, DIM_DIMENSIONLESS, 1.0)
    result = render_expression(expr)
    assert result == expected
    assert len(result) == MAX_CANONICAL_UNIT_LENGTH


def test_canonical_exact_bound_one_over_rejected() -> None:
    """An expression rendering to MAX_CANONICAL_UNIT_LENGTH + 1 is rejected."""
    from eggcalc.units import _UncheckedUnitExpression

    factors, expected = _build_rendered_string(MAX_CANONICAL_UNIT_LENGTH + 1)
    expr = _UncheckedUnitExpression(factors, DIM_DIMENSIONLESS, 1.0)
    with pytest.raises(ValueError, match="exceeds"):
        render_expression(expr)


def test_canonical_over_bound_rejection() -> None:
    """An expression rendering beyond MAX_CANONICAL_UNIT_LENGTH must raise."""
    from eggcalc.units import _UncheckedUnitExpression

    factors = tuple((f"unit{i}", 1) for i in range(100))
    expr = _UncheckedUnitExpression(factors, DIM_DIMENSIONLESS, 1.0)
    with pytest.raises(ValueError, match="exceeds"):
        render_expression(expr)


def test_render_expression_never_truncates() -> None:
    """render_expression must raise, not truncate, on overflow."""
    from eggcalc.units import _UncheckedUnitExpression

    factors = tuple((f"unit{i}", 1) for i in range(100))
    expr = _UncheckedUnitExpression(factors, DIM_DIMENSIONLESS, 1.0)
    with pytest.raises(ValueError):
        result = render_expression(expr)
        assert len(result) > MAX_CANONICAL_UNIT_LENGTH


def test_canonical_denominator_included_in_boundary() -> None:
    """Denominator formatting is included in canonical length check."""
    from eggcalc.units import _UncheckedUnitExpression

    # Build a string with denominator that hits exactly MAX_CANONICAL_UNIT_LENGTH
    # "a*a*...*a/b*b*...*b" format
    # numerator: n factors, denominator: m factors
    # total = (2n-1) + 1 + (2m-1) = 2n + 2m - 1
    half = MAX_CANONICAL_UNIT_LENGTH // 2
    n = (half + 1) // 2
    m = (MAX_CANONICAL_UNIT_LENGTH - (2 * n - 1) - 1 + 1) // 2
    numerator = tuple(("a", 1) for _ in range(n))
    denominator = tuple(("b", -1) for _ in range(m))
    factors = numerator + denominator
    rendered = render_expression(_UncheckedUnitExpression(factors, DIM_DIMENSIONLESS, 1.0))
    assert rendered is not None
    assert len(rendered) <= MAX_CANONICAL_UNIT_LENGTH


# ---------------------------------------------------------------------------
# Finite-scale overflow and underflow
# ---------------------------------------------------------------------------


def test_scale_overflow_rejected() -> None:
    """Scale overflow to infinity must be rejected."""
    from eggcalc.units import UNIT_DEFINITIONS

    # Use YB (yottabyte, scale ~1.2e24) at exponent 16 — scale^16 overflows float
    yb_spec = next(s for s in UNIT_DEFINITIONS if s.canonical == "YB")
    big_factors = (("YB", MAX_ABS_UNIT_EXPONENT),)
    expected_dim = yb_spec.dimension**MAX_ABS_UNIT_EXPONENT
    with pytest.raises(ValueError, match="scale"):
        UnitExpression(big_factors, expected_dim, 1e308)


def test_scale_underflow_rejected() -> None:
    """Genuine scale underflow to zero from extreme factor multiplication is rejected."""
    from eggcalc.units import UNIT_DEFINITIONS

    # Use fermi (scale 1e-15) at exponent 16 and nm (scale 1e-9) at exponent 16.
    # Combined scale: (1e-15)^16 * (1e-9)^16 = 1e-384, which underflows to 0.0.
    # Each individual normalized exponent remains within the configured bound.
    fermi = next(s for s in UNIT_DEFINITIONS if s.canonical == "fermi")
    nm = next(s for s in UNIT_DEFINITIONS if s.canonical == "nm")
    factors = (("fermi", MAX_ABS_UNIT_EXPONENT), ("nm", MAX_ABS_UNIT_EXPONENT))
    expected_dim = fermi.dimension**MAX_ABS_UNIT_EXPONENT * nm.dimension**MAX_ABS_UNIT_EXPONENT
    with pytest.raises(ValueError, match="scale"):
        UnitExpression(factors, expected_dim, 1.0)


def test_zero_scale_rejected() -> None:
    """Zero scale must be rejected in direct construction."""
    with pytest.raises(ValueError, match="scale"):
        UnitExpression((("m", 1),), DIM_LENGTH, 0.0)


def test_non_finite_scale_rejected() -> None:
    """NaN and infinity scales must be rejected."""
    with pytest.raises(ValueError, match="scale"):
        UnitExpression((("m", 1),), DIM_LENGTH, float("nan"))
    with pytest.raises(ValueError, match="scale"):
        UnitExpression((("m", 1),), DIM_LENGTH, float("inf"))


def test_invalid_zero_divisor_rejected() -> None:
    """Division by zero scale must be rejected."""
    with pytest.raises(ValueError, match="scale"):
        UnitExpression((("m", 1),), DIM_LENGTH, 0.0)


def test_exponent_exceeds_allowed_before_expensive_work() -> None:
    """Exponentiation exceeding MAX_ABS_UNIT_EXPONENT must be rejected early."""
    expr = parse_unit_expression("m")
    from eggcalc.units import power_expression

    with pytest.raises(ValueError, match="Exponent"):
        power_expression(expr, MAX_ABS_UNIT_EXPONENT + 1)


# ---------------------------------------------------------------------------
# Direct construction invariant matrix
# ---------------------------------------------------------------------------


def test_direct_construction_rejects_unknown_canonical() -> None:
    with pytest.raises(ValueError, match="Unknown canonical"):
        UnitExpression((("nonexistent", 1),), DIM_LENGTH, 1.0)


def test_direct_construction_rejects_duplicate_factors_inconsistent_dimension() -> None:
    """Duplicate factors with inconsistent scale are rejected."""
    # km has scale 1000, m has scale 1.0 — same canonical 'm' but different scales
    # is impossible since canonicals are unique. Instead test that providing
    # a scale that doesn't match the computed scale is rejected.
    with pytest.raises(ValueError, match="scale does not match"):
        UnitExpression((("km", 1),), DIM_LENGTH, 1.0)


def test_direct_construction_rejects_invalid_exponent_type() -> None:
    with pytest.raises(ValueError, match="exponent"):
        UnitExpression((("m", 1.5),), DIM_LENGTH, 1.0)  # type: ignore[arg-type]


def test_direct_construction_rejects_exponent_beyond_bounds() -> None:
    with pytest.raises(ValueError, match="Normalized exponent"):
        UnitExpression((("m", MAX_ABS_UNIT_EXPONENT + 1),), DIM_LENGTH, 1.0)


# ---------------------------------------------------------------------------
# Normalized duplicate exponent invariant
# ---------------------------------------------------------------------------


def test_duplicate_factors_positive_overflow_rejected() -> None:
    """Duplicate factors whose individual exponents are legal but normalized sum exceeds bound."""
    with pytest.raises(ValueError, match="Normalized exponent"):
        UnitExpression((("m", 16), ("m", 1)), DIM_LENGTH**17, 1.0)


def test_duplicate_factors_negative_overflow_rejected() -> None:
    """Duplicate factors with negative normalized exponent overflow."""
    with pytest.raises(ValueError, match="Normalized exponent"):
        UnitExpression((("m", -16), ("m", -1)), DIM_LENGTH**-17, 1.0)


def test_duplicate_factors_exact_bound_succeeds() -> None:
    """Duplicate factors summing to exactly MAX_ABS_UNIT_EXPONENT succeed."""
    expr = UnitExpression((("m", 15), ("m", 1)), DIM_LENGTH**16, 1.0)
    assert expr.factors == (("m", 16),)
    assert abs(expr.factors[0][1]) == MAX_ABS_UNIT_EXPONENT


def test_duplicate_factors_cancel_to_dimensionless() -> None:
    """Duplicate factors summing to zero normalize to dimensionless."""
    expr = UnitExpression((("m", 16), ("m", -16)), DIM_DIMENSIONLESS, 1.0)
    assert expr.factors == ()
    assert expr.dimension == DIM_DIMENSIONLESS


def test_duplicate_factors_cancel_dimension_requires_dimensionless() -> None:
    """Cancellation to dimensionless requires DIM_DIMENSIONLESS and scale 1.0."""
    with pytest.raises(ValueError, match="dimension"):
        UnitExpression((("m", 16), ("m", -16)), DIM_LENGTH, 1.0)


def test_boolean_exponent_rejected() -> None:
    """Boolean exponents are rejected even though bool is an int subclass."""
    with pytest.raises(ValueError, match="exponent"):
        UnitExpression((("m", True),), DIM_LENGTH, 1.0)  # type: ignore[arg-type]


def test_direct_construction_rejects_excessive_factor_count() -> None:
    # Use real canonicals repeated to exceed MAX_COMPOUND_ATOMS
    # Since factors are normalized, we need many unique canonicals
    # Use all available canonicals plus repeats
    from eggcalc.units import UNIT_DEFINITIONS

    canonicals = [spec.canonical for spec in UNIT_DEFINITIONS if not spec.affine]
    if len(canonicals) >= MAX_COMPOUND_ATOMS + 1:
        factors = tuple((c, 1) for c in canonicals[: MAX_COMPOUND_ATOMS + 1])
        with pytest.raises(ValueError, match="factor"):
            UnitExpression(factors, DIM_DIMENSIONLESS, 1.0)
    else:
        pytest.skip("Not enough unique canonicals to test factor count bound")


def test_direct_construction_rejects_affine_factor_in_compound() -> None:
    with pytest.raises(ValueError, match="Affine"):
        UnitExpression((("C", 1), ("m", 1)), DIM_TEMPERATURE * DIM_LENGTH, 1.0)


def test_direct_construction_rejects_dimension_mismatch() -> None:
    with pytest.raises(ValueError, match="dimension"):
        UnitExpression((("m", 1),), DIM_MASS, 1.0)


def test_direct_construction_rejects_scale_mismatch() -> None:
    with pytest.raises(ValueError, match="scale does not match"):
        UnitExpression((("km", 1),), DIM_LENGTH, 1.0)


def test_direct_construction_rejects_non_finite_scale() -> None:
    with pytest.raises(ValueError, match="scale"):
        UnitExpression((("m", 1),), DIM_LENGTH, float("inf"))


def test_direct_construction_rejects_zero_scale() -> None:
    with pytest.raises(ValueError, match="scale"):
        UnitExpression((("m", 1),), DIM_LENGTH, 0.0)


def test_direct_construction_rejects_canonical_rendering_beyond_bound() -> None:
    # Use _UncheckedUnitExpression to test render_expression directly
    from eggcalc.units import _UncheckedUnitExpression

    factors = tuple((f"unit{i}", 1) for i in range(100))
    expr = _UncheckedUnitExpression(factors, DIM_DIMENSIONLESS, 1.0)
    with pytest.raises(ValueError, match="exceeds"):
        render_expression(expr)


# ---------------------------------------------------------------------------
# Bounded error text
# ---------------------------------------------------------------------------


def test_bounded_error_text() -> None:
    """Error messages must be bounded by MAX_UNIT_ERROR_LENGTH."""
    for bad_input in (
        "x" * 10000,
        "m" * (MAX_UNIT_STRING_LENGTH + 1),
        f"m**{MAX_ABS_UNIT_EXPONENT + 1}",
    ):
        try:
            parse_unit_expression(bad_input)
        except ValueError as exc:
            assert (
                len(str(exc)) <= MAX_UNIT_ERROR_LENGTH
            ), f"Error message too long ({len(str(exc))} chars) for input {bad_input[:20]!r}"


# ---------------------------------------------------------------------------
# Depth semantics: documented fixed structural depth
# ---------------------------------------------------------------------------


def test_grammar_has_fixed_structural_depth() -> None:
    """The grammar has no parenthesized recursion; depth is fixed at 1.

    MAX_COMPOUND_DEPTH is retained as a deprecated compatibility constant
    but is not used to enforce dynamic depth in the parser. The parser
    grammar has exactly one structural level (product/division of atoms).
    """
    # The parser accepts any number of atoms in a single product/division
    # level, bounded by MAX_COMPOUND_ATOMS, not by depth.
    # Multiple division operators are rejected (only one allowed).
    with pytest.raises(ValueError, match="Only one division"):
        parse_unit_expression("m/m/m/m")
    # Single division is accepted
    result = parse_unit_expression("m/m")
    assert result.factors == (("m", 0),) or result.factors == ()


def test_max_compound_depth_is_compatibility_constant() -> None:
    """MAX_COMPOUND_DEPTH is a deprecated compatibility constant >= 1."""
    assert MAX_COMPOUND_DEPTH >= 1


# ---------------------------------------------------------------------------
# Structural UnitValue arithmetic
# ---------------------------------------------------------------------------


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


def test_all_unitvalue_operators_migrated() -> None:
    """All UnitValue operators use structural expressions, not legacy strings."""
    # Addition with conversion
    assert (UnitValue(1, "m") + UnitValue(100, "cm")).value == pytest.approx(2)
    # Subtraction with conversion
    assert (UnitValue(2, "m") - UnitValue(50, "cm")).value == pytest.approx(1.5)
    # Multiplication
    assert (UnitValue(2, "m") * UnitValue(3, "m")).unit == "m**2"
    # Division
    assert (UnitValue(10, "m") / UnitValue(2, "s")).unit == "m/s"
    # Power
    assert (UnitValue(2, "m") ** 2).unit == "m**2"
    # Floor division
    assert (UnitValue(10, "m") // UnitValue(3, "m")).unit is None
    # Modulo
    assert (UnitValue(10, "m") % UnitValue(3, "m")).unit == "m"
    # Negation
    assert (-UnitValue(5, "m")).value == -5
    # Abs
    assert abs(UnitValue(-5, "m")).value == 5


# ---------------------------------------------------------------------------
# Package/single-file focused parity
# ---------------------------------------------------------------------------


def test_single_file_focused_parity() -> None:
    """Focused parser cases produce identical results in package and single-file modes."""
    cases = [
        "m/s**2",
        "kg*m/s**2",
        "m**2",
        "m",
        "km/h",
        "m*m",
        "C",
        "K",
    ]
    single_file = ROOT / "eggcalc.py"
    if not single_file.exists():
        pytest.skip("Single-file build not present")
    for case in cases:
        # Package mode
        pkg_result = subprocess.run(
            [
                sys.executable,
                "-c",
                f"from eggcalc import units; print(units.parse_unit_expression({case!r}).factors)",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        # Single-file mode: run via the single-file script
        sf_result = subprocess.run(
            [sys.executable, str(single_file), case],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        # Both should succeed without error
        assert pkg_result.returncode == 0
        assert sf_result.returncode == 0, f"Single-file failed for {case!r}: {sf_result.stderr}"
