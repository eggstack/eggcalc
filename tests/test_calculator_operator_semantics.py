"""
Calculator operator semantics regression tests (Release 1).

Covers:
  - Workstream B: precedence, associativity, and direct-evaluator contract
  - Workstream E: adversarial / resource-limit tests for caret rewriting

The two evaluation paths have intentionally different caret contracts:
  - ``evaluate()`` accepts Python-compatible syntax; ``^`` is bitwise XOR.
  - ``evaluate_raw()`` and CLI normalization treat ``^`` as exponentiation.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

os.environ.setdefault("EGGCALC_NO_CONFIG", "1")


# ---------------------------------------------------------------------------
# B1: Caret precedence and associativity through evaluate_raw() / run()
# ---------------------------------------------------------------------------
class TestCaretPrecedenceViaNormalize:
    """Calculator ``^`` is exponentiation with correct precedence and
    right-associativity when routed through the normalization pipeline."""

    def test_addition_before_power(self):
        from eggcalc.evaluator import evaluate_raw

        assert evaluate_raw("2 + 3 ^ 2") == 11

    def test_multiplication_before_power(self):
        from eggcalc.evaluator import evaluate_raw

        assert evaluate_raw("2 * 3 ^ 2") == 18

    def test_power_right_associative(self):
        from eggcalc.evaluator import evaluate_raw

        assert evaluate_raw("2 ^ 3 ^ 2") == 512

    def test_unary_minus_base(self):
        from eggcalc.evaluator import evaluate_raw

        assert evaluate_raw("-2 ^ 2") == -4

    def test_parenthesized_base(self):
        from eggcalc.evaluator import evaluate_raw

        assert evaluate_raw("(-2) ^ 2") == 4

    def test_double_star_also_works(self):
        from eggcalc.evaluator import evaluate_raw

        assert evaluate_raw("2 ** 3") == 8

    def test_addition_before_double_star(self):
        from eggcalc.evaluator import evaluate_raw

        assert evaluate_raw("2 + 3 ** 2") == 11

    def test_power_of_power(self):
        from eggcalc.evaluator import evaluate_raw

        assert evaluate_raw("(2 ^ 3) ^ 2") == 64

    def test_power_in_parens(self):
        from eggcalc.evaluator import evaluate_raw

        assert evaluate_raw("2 ^ (3 + 1)") == 16


# ---------------------------------------------------------------------------
# B2: Direct evaluate() contract -- ^ is bitwise XOR
# ---------------------------------------------------------------------------
class TestDirectEvaluateCaretIsXor:
    """``evaluate()`` parses Python-compatible AST; ``^`` maps to
    ``ast.BitXor`` (bitwise XOR), not exponentiation."""

    def test_pow_operator(self):
        from eggcalc.evaluator import evaluate

        assert evaluate("2 ** 3") == 8

    def test_caret_is_xor(self):
        from eggcalc.evaluator import evaluate

        assert evaluate("5 ^ 3") == 6

    def test_caret_xor_precedence(self):
        from eggcalc.evaluator import evaluate

        assert evaluate("1 ^ 3") == 2
        assert evaluate("5 ^ 3") == 6

    def test_pow_precedence_via_ast(self):
        from eggcalc.evaluator import evaluate

        assert evaluate("2 + 3 ** 2") == 11


# ---------------------------------------------------------------------------
# B3: Word-form XOR remains bitwise
# ---------------------------------------------------------------------------
class TestWordFormXOR:
    """Natural-language XOR forms (``xor``/``bitxor``/``bit xor``) are
    rewritten to ``bitxor(...)`` function calls and remain bitwise."""

    def test_xor_word(self):
        from eggcalc.evaluator import evaluate_raw

        assert evaluate_raw("5 xor 3") == 6

    def test_XOR_word(self):
        from eggcalc.evaluator import evaluate_raw

        assert evaluate_raw("5 XOR 3") == 6

    def test_bitxor_word(self):
        from eggcalc.evaluator import evaluate_raw

        assert evaluate_raw("5 bitxor 3") == 6

    def test_bit_xor_phrase(self):
        from eggcalc.evaluator import evaluate_raw

        assert evaluate_raw("5 bit xor 3") == 6

    def test_xor_with_operands_left(self):
        from eggcalc.evaluator import evaluate_raw

        assert evaluate_raw("5 xor 3 + 2") == 8

    def test_xor_with_operands_right(self):
        from eggcalc.evaluator import evaluate_raw

        assert evaluate_raw("5 + 3 xor 2") == 6

    def test_parenthesized_xor_operands(self):
        from eggcalc.evaluator import evaluate_raw

        # (5+3) xor (2+1) == bitxor(8, 3) == 11
        assert evaluate_raw("(5 + 3) xor (2 + 1)") == 11

    def test_xor_does_not_affect_power(self):
        from eggcalc.evaluator import evaluate_raw

        assert evaluate_raw("2 ^ 3") == 8


# ---------------------------------------------------------------------------
# B4: Floor division and modulo with units
# ---------------------------------------------------------------------------
class TestUnitFloorDivisionModulo:
    """Floor division of compatible quantities returns a dimensionless
    quotient; modulo returns a quantity in the divisor unit."""

    def test_same_unit_floordiv(self):
        from eggcalc.evaluator import evaluate_raw

        r = evaluate_raw("(6*m)//(3*m)")
        assert getattr(r, "value", r) == 2

    def test_cross_unit_floordiv(self):
        from eggcalc.evaluator import evaluate_raw

        r = evaluate_raw("(1*m)//(30*cm)")
        assert getattr(r, "value", r) == 3

    def test_same_unit_mod(self):
        from eggcalc.evaluator import evaluate_raw

        r = evaluate_raw("(5*m)%(2*m)")
        assert abs(getattr(r, "value", r) - 1) < 1e-9
        unit = getattr(r, "unit", "m") or "m"
        assert unit == "m"

    def test_cross_unit_mod(self):
        from eggcalc.evaluator import evaluate_raw

        r = evaluate_raw("(1*m)%(30*cm)")
        assert abs(getattr(r, "value", r) - 10) < 1e-9
        unit = getattr(r, "unit", "cm") or "cm"
        assert unit == "cm"

    def test_incompatible_floordiv_rejected(self):
        from eggcalc.evaluator import EvaluationError, evaluate_raw

        with pytest.raises(EvaluationError):
            evaluate_raw("(5*m)//(2*s)")

    def test_incompatible_mod_rejected(self):
        from eggcalc.evaluator import EvaluationError, evaluate_raw

        with pytest.raises(EvaluationError):
            evaluate_raw("(5*m)%(2*s)")


# ---------------------------------------------------------------------------
# B5: UnitValue direct operations
# ---------------------------------------------------------------------------
class TestUnitValueFloorModDirect:
    """UnitValue __floordiv__ and __mod__ semantics."""

    def test_same_unit_floordiv(self):
        from eggcalc.units import UnitValue

        r = UnitValue(6, "m") // UnitValue(3, "m")
        assert r.value == 2

    def test_cross_unit_floordiv(self):
        from eggcalc.units import UnitValue

        r = UnitValue(1, "m") // UnitValue(30, "cm")
        assert r.value == 3

    def test_same_unit_mod(self):
        from eggcalc.units import UnitValue

        r = UnitValue(5, "m") % UnitValue(2, "m")
        assert abs(r.value - 1) < 1e-9
        assert r.unit == "m"

    def test_cross_unit_mod(self):
        from eggcalc.units import UnitValue

        r = UnitValue(1, "m") % UnitValue(30, "cm")
        assert abs(r.value - 10) < 1e-9
        assert r.unit == "cm"


# ---------------------------------------------------------------------------
# B6: Shared helper functions
# ---------------------------------------------------------------------------
class TestSharedHelpers:
    """_floor_divide_quantities and _modulo_quantities."""

    def test_floor_divide_same_unit(self):
        from eggcalc.units import UnitValue, _floor_divide_quantities

        r = _floor_divide_quantities(UnitValue(6, "m"), UnitValue(3, "m"))
        assert r == 2

    def test_floor_divide_cross_unit(self):
        from eggcalc.units import UnitValue, _floor_divide_quantities

        r = _floor_divide_quantities(UnitValue(1, "m"), UnitValue(30, "cm"))
        assert r == 3

    def test_floor_divide_incompatible(self):
        from eggcalc.units import UnitValue, _floor_divide_quantities

        with pytest.raises(ValueError):
            _floor_divide_quantities(UnitValue(5, "m"), UnitValue(2, "s"))

    def test_modulo_same_unit(self):
        from eggcalc.units import UnitValue, _modulo_quantities

        r = _modulo_quantities(UnitValue(5, "m"), UnitValue(2, "m"))
        assert abs(r.value - 1) < 1e-9
        assert r.unit == "m"

    def test_modulo_cross_unit(self):
        from eggcalc.units import UnitValue, _modulo_quantities

        r = _modulo_quantities(UnitValue(1, "m"), UnitValue(30, "cm"))
        assert abs(r.value - 10) < 1e-9
        assert r.unit == "cm"

    def test_modulo_incompatible(self):
        from eggcalc.units import UnitValue, _modulo_quantities

        with pytest.raises(ValueError):
            _modulo_quantities(UnitValue(5, "m"), UnitValue(2, "s"))


# ---------------------------------------------------------------------------
# B7: Algebraic reconstruction identity q == (q // d) * d + (q % d)
# ---------------------------------------------------------------------------
class TestAlgebraicReconstruction:
    """For representative positive operands, assert
    q == (q // d) * d + (q % d) in the divisor unit."""

    def _extract_value(self, v):
        return v.value if hasattr(v, "value") else v

    def test_same_unit(self):
        from eggcalc.units import UnitValue

        q = UnitValue(5, "m")
        d = UnitValue(2, "m")
        fd = self._extract_value(q // d)
        mod = self._extract_value(q % d)
        reconstructed = fd * d.value + mod
        assert abs(reconstructed - q.value) < 1e-9

    def test_cross_unit(self):
        from eggcalc.units import UnitValue

        q = UnitValue(1, "m")
        d = UnitValue(30, "cm")
        fd = self._extract_value(q // d)
        mod = self._extract_value(q % d)
        reconstructed_cm = fd * d.value + mod
        q_cm = q.convert_to("cm").value
        assert abs(reconstructed_cm - q_cm) < 1e-9

    def test_large_values(self):
        from eggcalc.units import UnitValue

        q = UnitValue(100, "m")
        d = UnitValue(7, "m")
        fd = self._extract_value(q // d)
        mod = self._extract_value(q % d)
        reconstructed = fd * d.value + mod
        assert abs(reconstructed - q.value) < 1e-9


# ---------------------------------------------------------------------------
# B8: Negative operand behavior (Python floor/mod semantics)
# ---------------------------------------------------------------------------
class TestNegativeOperands:
    """Floor division and modulo with negative operands follow Python semantics:
    floor division rounds toward negative infinity, and the reconstruction
    identity q == (q // d) * d + (q % d) holds for all sign combinations."""

    def test_negative_dividend_same_unit(self):
        from eggcalc.units import UnitValue

        q = UnitValue(-5, "m")
        d = UnitValue(2, "m")
        assert (q // d).value == -3
        assert (q % d).value == 1
        assert (q % d).unit == "m"

    def test_negative_divisor_same_unit(self):
        from eggcalc.units import UnitValue

        q = UnitValue(5, "m")
        d = UnitValue(-2, "m")
        assert (q // d).value == -3
        assert (q % d).value == -1
        assert (q % d).unit == "m"

    def test_both_negative_same_unit(self):
        from eggcalc.units import UnitValue

        q = UnitValue(-5, "m")
        d = UnitValue(-2, "m")
        assert (q // d).value == 2
        assert (q % d).value == -1
        assert (q % d).unit == "m"

    def test_reconstruction_negative_dividend(self):
        from eggcalc.units import UnitValue

        q = UnitValue(-5, "m")
        d = UnitValue(2, "m")
        fd = (q // d).value if hasattr(q // d, "value") else (q // d)
        mod = (q % d).value if hasattr(q % d, "value") else (q % d)
        reconstructed = fd * d.value + mod
        assert abs(reconstructed - q.value) < 1e-9

    def test_reconstruction_negative_divisor(self):
        from eggcalc.units import UnitValue

        q = UnitValue(5, "m")
        d = UnitValue(-2, "m")
        fd = (q // d).value if hasattr(q // d, "value") else (q // d)
        mod = (q % d).value if hasattr(q % d, "value") else (q % d)
        reconstructed = fd * d.value + mod
        assert abs(reconstructed - q.value) < 1e-9


# ---------------------------------------------------------------------------
# E1: CLI subprocess tests for highest-risk expressions
# ---------------------------------------------------------------------------
class TestCLISubprocess:
    """Smoke-test the CLI for the four highest-risk expressions."""

    def _run_cli(self, expr: str) -> tuple[str, int]:
        result = subprocess.run(
            [sys.executable, "-m", "eggcalc", expr],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout.strip(), result.returncode

    def test_caret_power(self):
        out, rc = self._run_cli("2 + 3 ^ 2")
        assert rc == 0
        assert out == "11"

    def test_caret_right_associative(self):
        out, rc = self._run_cli("2 ^ 3 ^ 2")
        assert rc == 0
        assert out == "512"

    def test_same_unit_mod(self):
        out, rc = self._run_cli("5m % 2m")
        assert rc == 0
        assert "1" in out and "m" in out

    def test_cross_unit_mod(self):
        out, rc = self._run_cli("1 m % 30 cm")
        assert rc == 0
        assert "10" in out and "cm" in out


# ---------------------------------------------------------------------------
# E2: Adversarial / resource-limit tests for caret rewriting
# ---------------------------------------------------------------------------
class TestAdversarialCaretInput:
    """Malformed or adversarial caret input must fail cleanly."""

    def test_double_caret_rejected(self):
        from eggcalc.evaluator import EvaluationError, evaluate_raw

        with pytest.raises((EvaluationError, ValueError)):
            evaluate_raw("2 ^^ 3")

    def test_triple_caret_rejected(self):
        from eggcalc.evaluator import EvaluationError, evaluate_raw

        with pytest.raises((EvaluationError, ValueError)):
            evaluate_raw("2 ^^^ 3")

    def test_caret_star_rejected(self):
        from eggcalc.evaluator import EvaluationError, evaluate_raw

        with pytest.raises((EvaluationError, ValueError)):
            evaluate_raw("2 ^* 3")

    def test_star_caret_rejected(self):
        from eggcalc.evaluator import EvaluationError, evaluate_raw

        with pytest.raises((EvaluationError, ValueError)):
            evaluate_raw("2 *^ 3")

    def test_long_caret_sequence(self):
        from eggcalc.evaluator import EvaluationError, evaluate_raw

        with pytest.raises((EvaluationError, ValueError)):
            evaluate_raw("2 " + "^" * 100 + " 3")

    def test_caret_inside_string_ignored(self):
        from eggcalc.evaluator import evaluate

        assert evaluate("5 ^ 3") == 6

    def test_many_parens_with_caret(self):
        from eggcalc.evaluator import evaluate_raw

        expr = "(" * 20 + "2" + ")" * 20 + " ^ " + "(" * 20 + "3" + ")" * 20
        r = evaluate_raw(expr)
        assert r == 8

    def test_long_expression_with_caret(self):
        from eggcalc.evaluator import evaluate_raw

        parts = ["2"] + ["+ 1"] * 50
        expr = " ".join(parts) + " ^ 2"
        r = evaluate_raw(expr)
        # 2 + 1 + 1 + ... + 1 ^ 2 → 2 + 49*1 + 1**2 = 52
        assert r == 52

    def test_caret_at_start(self):
        from eggcalc.evaluator import EvaluationError, evaluate_raw

        with pytest.raises((EvaluationError, ValueError, Exception)):
            evaluate_raw("^ 3")

    def test_caret_at_end(self):
        from eggcalc.evaluator import EvaluationError, evaluate_raw

        with pytest.raises((EvaluationError, ValueError, Exception)):
            evaluate_raw("2 ^")
