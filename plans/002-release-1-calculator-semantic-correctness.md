# Release 1 Plan — Calculator Semantic Correctness

Status: ready for implementation handoff  
Depends on: current `main`  
Roadmap: `plans/001-correctness-protocol-hardening-roadmap.md`

## 1. Release objective

Correct calculator grammar and dimensional semantics without weakening the separation between the direct evaluator and the user-facing normalization pipeline.

This release addresses two known correctness risks:

1. Calculator caret syntax is currently reinterpreted after Python has already parsed it with bitwise-XOR precedence and associativity.
2. Modulo produces inconsistent dimensions depending on whether compatible operands use identical or different unit spellings.

No new calculator features should be added during this release. The goal is to establish a reliable semantic baseline and comprehensive regression matrix.

## 2. Required behavioral contract

### 2.1 Evaluation path contract

`evaluate(expr)`:

- Accepts already-normalized, Python-AST-compatible mathematical syntax.
- Retains Python parsing semantics.
- `^` remains bitwise XOR if accepted through this direct path.
- `**` is exponentiation.
- Does not perform natural-language conversion or calculator-specific caret rewriting.

`evaluate_raw(expr)` and CLI/run normalization:

- Accept natural language, units, and calculator syntax.
- Treat `^` as exponentiation.
- Rewrite natural-language `xor`, `bitxor`, and `bit xor` forms to `bitxor(...)`.
- Produce Python-compatible normalized syntax before calling the evaluator.

This distinction must be reflected in tests and documentation.

### 2.2 Unit floor-division and modulo contract

For compatible dimensions:

- `quantity // quantity` returns a dimensionless floor quotient.
- `quantity % quantity` returns a quantity whose display unit is the divisor unit.

Examples:

```text
6 m // 3 m   -> 2
1 m // 30 cm -> 3
5 m % 2 m    -> 1 m
1 m % 30 cm  -> 10 cm
```

For incompatible dimensions, both operations must reject the expression rather than synthesize misleading compound `//` or `%` unit strings.

## 3. Workstream A — Caret syntax preprocessing

### A1. Locate the normalization boundary

Identify the final user-facing normalization stage immediately before the normalized expression is handed to `evaluate()`/`ast.parse()`.

The caret rewrite must occur:

- After natural-language XOR words have been transformed into `bitxor(...)` calls.
- Before AST parsing.
- Before any validation that assumes Python-compatible operator syntax, if that validation currently rejects `**` differently from `^`.

Avoid implementing exponent semantics in `Evaluator.BINOPS[ast.BitXor]`.

### A2. Implement a tokenizer-aware caret rewrite

Add a private helper with a narrow contract, for example:

```python
def _rewrite_calculator_caret(expression: str) -> str:
    ...
```

Requirements:

- Rewrite standalone calculator `^` tokens to `**`.
- Do not rewrite characters inside string literals.
- Reject malformed repeated caret forms such as `^^`, `^^^`, or mixed `^*` forms with a clear normalization error.
- Preserve surrounding whitespace where practical.
- Maintain bounded linear-time behavior.
- Do not use recursive regex replacement.

A standard-library tokenizer-based implementation is preferred if it can operate on the accepted expression subset without introducing source-encoding complexity. A small explicit scanner is acceptable if it handles quoted strings, escapes, and malformed sequences correctly.

### A3. Restore evaluator operator semantics

Change direct evaluator dispatch so:

- `ast.Pow` maps to `_safe_pow`.
- `ast.BitXor` maps to integer bitwise XOR.
- Bitwise float/unit guards include `ast.BitXor` again.
- Unit exponentiation special handling applies only to `ast.Pow`.

Remove comments and tests that describe `ast.BitXor` as calculator power dispatch.

### A4. Preserve word-form XOR

Keep or improve `_normalize_xor_word_to_bitxor_call()`.

Add cases for:

- `5 xor 3`
- `5 XOR 3`
- `5 bitxor 3`
- `5 bit xor 3`
- Parenthesized operands.
- Mixed arithmetic boundaries.
- Rejection or explicit semantics for chained XOR phrases.

Ensure the caret rewrite does not alter `bitxor(...)` function calls.

## 4. Workstream B — Precedence and associativity regression matrix

Create a dedicated test module, preferably:

```text
tests/test_calculator_operator_semantics.py
```

Required tests through `evaluate_raw()` and CLI-compatible `run()`:

```text
2 + 3 ^ 2       == 11
2 * 3 ^ 2       == 18
2 ^ 3 ^ 2       == 512
-2 ^ 2          == -4
(-2) ^ 2        == 4
2 ** 3          == 8
2 + 3 ** 2      == 11
```

Required tests through direct `evaluate()`:

```text
evaluate("2 ** 3") == 8
evaluate("5 ^ 3") == 6
```

Also cover:

- Powers around multiplication and division.
- Powers around unary plus/minus.
- Parenthesized bases and exponents.
- Unit-valued bases.
- Unit-valued exponents rejected.
- Exponent bounds still enforced.
- Right-associative chains.
- Single-file parity for representative cases.

Add CLI subprocess tests for at least the four highest-risk expressions.

## 5. Workstream C — Shared compatible-unit floor/mod implementation

### C1. Extract alignment logic

Avoid maintaining separate semantics in `UnitValue.__floordiv__`, `UnitValue.__mod__`, and `Evaluator.visit_BinOp`.

Introduce shared private helpers in `units.py`, for example:

```python
def _floor_divide_quantities(left: UnitValue, right: UnitValue) -> int | float:
    ...

def _modulo_quantities(left: UnitValue, right: UnitValue) -> UnitValue:
    ...
```

The evaluator should delegate to `UnitValue` operations or these helpers rather than reimplementing conversion and unit policy.

### C2. Define conversion direction

For compatible different units, convert the dividend into the divisor unit before floor division or modulo.

This avoids precision loss and makes the modulo output unit deterministic:

```text
1 m % 30 cm -> 100 cm % 30 cm -> 10 cm
```

Use existing conversion-factor machinery and existing floating-point tolerances. Do not add ad hoc decimal rounding that changes general arithmetic behavior.

### C3. Correct same-unit modulo

Change same-unit modulo from dimensionless output to a remainder carrying the divisor unit.

Required direct `UnitValue` cases:

```text
UnitValue(5, "m") % UnitValue(2, "m") -> UnitValue(1, "m")
UnitValue(1, "m") % UnitValue(30, "cm") -> UnitValue(10, "cm")
```

### C4. Reject incompatible dimensions

Expressions such as:

```text
5 m % 2 s
5 m // 2 s
```

must produce a clear error. Do not create units such as `m%s` or `m//s`.

### C5. Validate algebraic reconstruction

For representative positive operands, assert:

```text
q == (q // d) * d + (q % d)
```

Perform comparison in the divisor unit and use a tolerance for floating-point conversions.

Also specify behavior for negative dividends/divisors according to Python floor/mod semantics and add tests that preserve the reconstruction identity.

## 6. Workstream D — Documentation and API corrections

Update:

- `README.md`
- `AGENTS.md`
- `docs/api.md`
- `docs/functions.md` or operator documentation
- `architecture/evaluator.md`
- `architecture/normalize.md`
- CLI help or quickstart documentation
- `CHANGELOG.md`

Required documentation statements:

- Direct `evaluate()` uses Python-compatible syntax and `^` is XOR.
- User-facing calculator syntax uses `^` for exponentiation.
- `xor`/`bitxor` are the supported calculator-level XOR forms.
- Modulo of quantities returns a dimensioned remainder in the divisor unit.
- Floor division of compatible quantities returns a dimensionless quotient.

Regenerate generated documentation and tool inventory if schemas or tool descriptions change.

## 7. Workstream E — Resource and security verification

Confirm:

- Caret rewriting is O(n).
- Malformed quote or escape input fails without unbounded scanning.
- Input and normalized-length limits remain enforced.
- Exponent bounds still apply after caret rewriting.
- Nested power expressions remain subject to nesting limits.
- No use of `eval()` or `compile()` is introduced.
- Error output does not expose internal stack traces in MCP mode.

Add adversarial tests for long sequences of carets, quotes, backslashes, and parentheses near the input limit.

## 8. Test execution matrix

Run at minimum:

```bash
python -m pytest tests/test_calculator_operator_semantics.py -v
python -m pytest tests/test_bugs_2026_07_regressions.py -v
python -m pytest tests/ -v
ruff check eggcalc tests
black --check eggcalc tests
mypy eggcalc --ignore-missing-imports
python build_single.py
python scripts/generate_mcp_docs.py --check
python scripts/smoke_release_surfaces.py
```

Then manually smoke-test package and single-file forms:

```bash
python -m eggcalc "2 + 3 ^ 2"
python eggcalc.py "2 + 3 ^ 2"
python -m eggcalc "1 m % 30 cm"
python eggcalc.py "1 m % 30 cm"
```

## 9. Acceptance criteria

Release 1 is complete when all of the following are true:

- Calculator caret is rewritten before AST parsing.
- `evaluate()` and `evaluate_raw()` have intentionally different documented caret contracts.
- Mixed-precedence and right-associative power tests pass.
- Word-form XOR remains bitwise.
- Same-unit modulo preserves a unit.
- Cross-unit modulo preserves the divisor unit.
- Incompatible floor/mod dimensions are rejected.
- Unit and evaluator implementations share one semantic path.
- Package, CLI, wheel, and single-file representative outputs match.
- Full CI, docs drift, type checking, and release-surface smoke tests pass.

## 10. Non-goals

Do not include in this release:

- A full unit-dimension representation rewrite.
- New natural-language grammar.
- New unit categories.
- MCP lifecycle restructuring.
- General parser replacement.
- Changes to standard-library-only runtime policy.

## 11. Handoff notes

Implement in small commits with tests accompanying each semantic change. Recommended commit sequence:

1. Add failing precedence and direct-evaluator contract tests.
2. Add caret preprocessing and restore `ast.BitXor` semantics.
3. Add failing modulo dimension tests.
4. Consolidate floor/mod logic and correct unit behavior.
5. Add adversarial/resource tests.
6. Update documentation, changelog, and generated artifacts.
7. Run full release-surface verification.
