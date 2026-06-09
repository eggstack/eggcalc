# Overview Architecture Review

## Document: architecture/overview.md

## Verified Claims

| Claim | Status | Evidence |
|-------|--------|----------|
| evaluator.py line count: 1515 | VERIFIED | `wc -l` confirms 1515 lines |
| units.py line count: 1284 | VERIFIED | `wc -l` confirms 1284 lines |
| evaluator.py: Safe AST-based evaluation (not eval()) | VERIFIED | Uses `ast.NodeVisitor` pattern at line 823 |
| Key exports from evaluator.py | VERIFIED | `__all__` at line 30-55 contains: evaluate, evaluate_raw, evaluate_cached, evaluate_async, evaluate_with_timeout, EggCalcApp, Evaluator |
| Key exports from units.py | VERIFIED | UnitValue (line 24), get_conversion_factor (1089), is_unit (1104), get_unit_category (1252), are_units_compatible (1258), convert_temperature (1068) |
| normalize.py imports evaluator.evaluate() | VERIFIED | Line 25: `from .evaluator import EvaluationError, evaluate` |
| normalize.py imports units | VERIFIED | Line 37: `from .units import UNIT_ALIASES, UNIT_CATEGORIES, UnitValue, is_unit` |
| normalize.py imports exact/ tools | VERIFIED | Lines 26-36 |
| evaluator.py imports units | VERIFIED | Lines 20-28: `from .units import ...` |
| units.py has no dependencies on other eggcalc modules | VERIFIED | No `from .` imports in units.py |
| Physical constants (pi, e, c, h, avogadro, k, G) | VERIFIED | Lines 833-880 in evaluator.py |
| Memory functions (M, M+, MR, MC) | VERIFIED | Lines 1010-1016 |
| Variable functions (setvar, getvar, delvar, listvars) | VERIFIED | Lines 1017-1022 |
| Statistical functions | VERIFIED | mean (213), median (343), mode (355), std (220), variance (369), sum (229), min (241), max (234) |
| Combinatorics functions | VERIFIED | factorial (936), gcd (938 uses math.gcd), lcm (443), perm (421), comb (432) |
| Bitwise functions | VERIFIED | bitand (388), bitor (393), bitxor (398), bitnot (403) |
| Complex number functions | VERIFIED | real (304), imag (311), conj (318), phase (325), polar (330), rect (335) |
| Prime functions | VERIFIED | isprime (456), primefactors (471), nextprime (504), prevprime (513) |
| Random functions | VERIFIED | random (531), randint (536), randn (553), gauss (558), seed (563), uniform (548), randrange (541) |
| Temperature conversion with offset | VERIFIED | TEMPERATURE_CONVERSIONS uses (multiplier, offset) tuples at lines 1050-1083 |
| Data structures in normalize.py | VERIFIED | NUMBER_WORDS (232), OPERATOR_CONVERSIONS (113), FUNCTION_MAPPINGS (135), CONSTANT_WORDS (291) |
| install.py installs to ~/.local/bin/calc | VERIFIED | Line 23: `os.path.join(os.path.expanduser("~"), ".local", "bin")` |
| Build system combines modules | VERIFIED | build_single.py defines MODULES_CALC (3), MODULES_EXACT (18), MODULES_MCP (3) |
| Data flow: run() pipeline | VERIFIED | Input → normalize → normalize_expression → evaluate → Output |

## Discrepancies

1. **[MISMATCH]**: normalize.py line count
   - Document states: 1807 lines
   - Code actually: 1804 lines
   - Discrepancy: 3 lines

2. **[MISMATCH]**: __main__.py line count
   - Document states: "~300 lines"
   - Code actually: 18 lines
   - Discrepancy: The CLI is implemented in normalize.py:main(), not __main__.py. __main__.py merely delegates to normalize.main()

3. **[MISMATCH]**: MODULES_EXACT count
   - Document states: "17 exact/ submodules"
   - Code actually: 18 modules in MODULES_EXACT list (build_single.py:27-46)
   - Extra modules not documented: The list includes 18 modules but docs claim 17

4. **[MISMATCH]**: Test count
   - Document states: "All 1192 tests pass"
   - Code actually: 1231 passed, 32 skipped (pytest run)
   - Discrepancy: 39 additional tests since documentation was written

5. **[MISMATCH]**: eggcalc.py file size
   - Document states: "~394KB"
   - Code actually: ~886KB (885923 bytes)
   - Discrepancy: More than double the documented size

6. **[MISMATCH]**: Unit categories count
   - Document states: "20+ unit categories" and table shows 14 categories
   - Code actually: 17 categories in UNIT_CATEGORIES
   - Missing from documentation table: voltage, current, angle

7. **[INCOMPLETE]**: Random functions listing
   - Document lists: random, randint, randn, gauss, seed
   - Code also has: uniform, randrange
   - These additional functions are not documented

8. **[MISMATCH]**: Architecture diagram shows exact/ tools directly in normalize.py flow
   - The diagram at lines 42-55 shows a simplified flow
   - Actual architecture has normalize.py importing from exact/ package, but the exact/ tools are not part of the calculator evaluation pipeline

## Bugs Identified

| Bug | Location | Severity | Description |
|-----|----------|----------|-------------|
| None | - | - | No implementation bugs found; all documented functionality exists and works |

## Improvements Surface

| Area | Priority | Description |
|------|----------|-------------|
| Documentation Accuracy | High | Line counts, module counts, and file sizes are outdated. Update to reflect current implementation |
| Unit Categories | Medium | The architecture document's table of unit categories is incomplete (missing voltage, current, angle). The "20+" claim is not substantiated by either the table or the code (17 categories) |
| Test Count | Medium | Document claims 1192 tests but 1231 pass - documentation is stale |
| __main__.py Description | Medium | Document describes __main__.py as having ~300 lines with full CLI implementation, when it's actually a thin 18-line delegator to normalize.main() |
| MODULES_EXACT Count | Medium | Document says 17 exact/ submodules but build_single.py defines 18 |
| Random Functions | Low | Documentation lists only 5 random functions but 7 exist (uniform and randrange are undocumented) |

## Notes

- The architecture document provides a good high-level overview of the system design
- The dual-purpose nature (Natural Language Calculator + Unicode Text Analysis Suite) is accurately described
- The dependency diagram at lines 242-281 is mostly accurate but omits some exact/ modules not included in the build (cargo.py, inspect_prompt.py, version.py)
- The Data Flow section (lines 179-217) accurately describes both evaluation paths (run() vs evaluate())
- The API Quick Reference examples (lines 331-369) are accurate
- The Module Dependencies section correctly identifies that units.py has no dependencies on other eggcalc modules
- The core issue is documentation staleness - several numeric claims are outdated (test count, file sizes, line counts, module counts)
