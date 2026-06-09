# Evaluator Architecture Review

**Document:** `architecture/evaluator.md`
**Code:** `eggcalc/evaluator.py`
**Date:** 2026-05-29

---

## Summary

The architecture document provides a comprehensive overview of the evaluator module but contains numerous discrepancies between documented and actual behavior. These range from missing functions and incorrect names to incorrect descriptions and missing parameter details. Most discrepancies are minor, but several could mislead users trying to use the API.

---

## Discrepancies

### D1: `Evaluator` Class Not Exported in Key Exports

**Location:** `architecture/evaluator.md:14-34` vs `evaluator.py:30-55`

**Issue:** The Key Exports section shows imports from `eggcalc.evaluator` but does not list `Evaluator` in the example. However, `Evaluator` is actually exported in `__all__` at line 31.

**Severity:** Low (omission in example only)

---

### D2: Non-Underscore Function Aliases Missing from Documentation

**Location:** `architecture/evaluator.md:108-120` vs `evaluator.py:978-988`

**Issue:** The documentation lists bitwise functions as `lshift(a, b)` and `rshift(a, b)`, but the actual implementation uses `bitlshift` and `bitrshift`. The underscore variants exist as aliases but are not documented.

| Documented | Actual (in FUNCTIONS) |
|------------|----------------------|
| `lshift` | `bitlshift` |
| `rshift` | `bitrshift` |

**Severity:** Low (underscore variants available but undocumented)

---

### D3: `seed()` Return Value

**Location:** `architecture/evaluator.md:127` vs `evaluator.py:563-566`

**Issue:** The documentation does not mention that `seed()` returns `None`. The `_seed()` function explicitly returns `None`:
```python
def _seed(s: int | None = None) -> None:
    _random_generator.seed(s)
    return None
```

**Severity:** Very low (implicit in Python conventions)

---

### D4: `evaluate_raw` Description Incomplete

**Location:** `architecture/evaluator.md:228-234` vs `evaluator.py:1313-1336`

**Issue:** The documentation says `evaluate_raw` "Evaluates with NL normalization" but does not mention that it:
1. Calls `normalize_expression` with `skip_validation=True`
2. Internally calls `evaluate()` on the normalized result

This matters because users might expect `evaluate_raw` to handle the same inputs as CLI with full validation.

**Severity:** Low (the example is correct)

---

### D5: `evaluate_async` Calls `evaluate_raw`, Not `evaluate`

**Location:** `architecture/evaluator.md:247-255` vs `evaluator.py:149-161`

**Issue:** The documentation shows:
```python
result = await evaluate_async("5 + 3")           # Awaitable result
result = await evaluate_async("five plus three")  # NL also supported
```

But the implementation at line 157-158 shows:
```python
def _eval() -> float:
    return evaluate_raw(expression)
```

`evaluate_async` always goes through normalization (NL pipeline), so passing pre-normalized expressions offers no optimization. The doc implies both work but doesn't explain the internal flow.

**Severity:** Low (NL support works, but behavior may surprise users expecting `evaluate`-like behavior)

---

### D6: `EggCalcApp` Import Location

**Location:** `architecture/evaluator.md:281-285` vs `evaluator.py`

**Issue:** The example shows:
```python
from eggcalc import EggCalcApp
```

But `EggCalcApp` is defined in `eggcalc/evaluator.py`, not `eggcalc/__init__.py`. Users would need:
```python
from eggcalc.evaluator import EggCalcApp
```

**Severity:** Medium (incorrect example would cause ImportError)

---

### D7: `memory_list()` Return Type

**Location:** `architecture/evaluator.md:184` vs `evaluator.py:766-768`

**Issue:** The documentation example shows `memory_list()` without describing its return. The function returns `dict[str, float]`, which is correct but undocumented.

**Severity:** Very low

---

## Potential Bugs

### B1: `_perm` Function Returns Factorial for Single Argument

**Location:** `evaluator.py:421-429`

```python
def _perm(n: int, r: int | None = None) -> int:
    """Calculate permutations P(n,r) = n!/(n-r)!."""
    n = int(n)
    if r is None:
        return math.factorial(n)
    r = int(r)
    if r > n:
        return 0
    return math.perm(n, r)
```

**Issue:** `perm(n)` returns `n!` (all permutations of n items taken n at a time), which is mathematically correct as P(n,n) = n!. However, the docstring could be clearer that this is intentional.

**Severity:** Informational (correct behavior)

---

### B2: `factorial` and `fact` Aliases

**Location:** `evaluator.py:936-937`

```python
"factorial": _safe_factorial,
"fact": _safe_factorial,
```

**Issue:** No bug - both aliases correctly map to `_safe_factorial`. However, the documentation only mentions `factorial(n)` in the list, not `fact(n)`.

**Severity:** Very low (documentation omission)

---

## Missing Documentation

### M1: Undocumented Functions in `FUNCTIONS`

The following functions are implemented and exported but not mentioned in the architecture document:

| Function | Location | Purpose |
|----------|----------|---------|
| `log1p` | `evaluator.py:922` | log(1+x) for small x |
| `expm1` | `evaluator.py:924` | exp(x)-1 for small x |
| `floor` | `evaluator.py:930` | Floor division |
| `ceil` | `evaluator.py:931` | Ceiling division |
| `trunc` | `evaluator.py:932` | Truncation |
| `degrees` | `evaluator.py:946` | Radians to degrees |
| `radians` | `evaluator.py:947` | Degrees to radians |
| `nPr` | `evaluator.py:942` | Alias for perm |
| `nCr` | `evaluator.py:943` | Alias for comb |
| `var` | `evaluator.py:954` | Alias for variance |
| `variance_sample` | `evaluator.py:955` | Sample variance |
| `vars` | `evaluator.py:956` | Alias for variance_sample |
| `var_sample` | `evaluator.py:957` | Alias for variance_sample |
| `is_prime` | `evaluator.py:982` | Snake_case alias for isprime |
| `prime_factors` | `evaluator.py:983` | Snake_case alias for primefactors |
| `next_prime` | `evaluator.py:986` | Snake_case alias for nextprime |
| `prev_prime` | `evaluator.py:988` | Snake_case alias for prevprime |
| `randrange` | `evaluator.py:992` | Random integer range |
| `uniform` | `evaluator.py:993` | Random float in range |
| `percent_of` | `evaluator.py:999` | Snake_case alias for percentof |
| `as_percent` | `evaluator.py:1001` | Snake_case alias for aspercent |
| `atan2` | `evaluator.py:909` | Two-argument arctangent |
| `convert` | `evaluator.py:1008` | Unit conversion |
| `temp` | `evaluator.py:1006` | Temperature conversion |
| `M` | `evaluator.py:1012` | Memory recall lambda |
| `Mplus` | `evaluator.py:1013` | Memory add lambda |
| `Mminus` | `evaluator.py:1014` | Memory subtract lambda |
| `MC` | `evaluator.py:1015` | Memory clear lambda |
| `MR` | `evaluator.py:1016` | Memory recall lambda (duplicate) |
| `conjugate` | `evaluator.py:965` | Alias for conj |

**Severity:** Medium (significant API surface not documented)

---

### M2: Undocumented Constants in `CONSTANTS`

The following constants are implemented but not listed in the architecture document:

| Constant | Value | Location |
|----------|-------|----------|
| `j` | `1j` | `evaluator.py:840` (alias for `i`) |

**Severity:** Very low

---

## Documentation Clarifications Needed

### C1: `getvar` Return Value

**Location:** `architecture/evaluator.md:200`

The documentation says `getvar("x")  # → 5` but does not specify what happens if the variable doesn't exist. The implementation returns `0` for missing variables (line 802).

**Recommendation:** Add note that `getvar` returns `0` for undefined variables.

---

### C2: Bitwise NOT Type Requirement

**Location:** `architecture/evaluator.md:119` vs `evaluator.py:1189-1190`

The documentation lists `bitnot(a)` without noting it requires integer input. The implementation explicitly checks:
```python
if op_class is ast.Invert and not isinstance(operand, int):
    raise EvaluationError("Bitwise NOT requires an integer operand")
```

**Recommendation:** Add note that bitwise functions require integer operands.

---

### C3: Memory Register Names

**Location:** `architecture/evaluator.md:187-191`

The documentation shows named registers work but doesn't specify valid register naming conventions. The implementation accepts any string as a register name (line 690: `self._registers[register] = new_value`).

---

### C4: `evaluate_with_timeout` Example

**Location:** `architecture/evaluator.md:267`

The docstring example shows:
```python
>>> result = evaluate_with_timeout("sum([i**2 for i in range(100)])", timeout=1.0)
```

This uses a Python list comprehension, which would be rejected by the AST validator since `ast.ListComp` is forbidden (line 1257-1258). The example would fail.

**Recommendation:** Use a valid expression like `evaluate_with_timeout("sum(i**2 for i in range(100))", timeout=1.0)` with a generator expression instead.

---

## Verified Correct Items

The following items were verified as correctly documented and implemented:

- `evaluate()` - Direct AST evaluation without normalization ✓
- `evaluate_cached()` - LRU caching with 1024 entries ✓
- `evaluate_with_timeout()` - ThreadPoolExecutor with timeout ✓
- `EvaluationError` - Custom exception class ✓
- `TimeoutError` - Custom exception for timeouts ✓
- `EggCalcApp` - Thread-safe with caching ✓
- `register_constant()` / `register_function()` - Thread-safe global registration ✓
- Memory functions: `memory_store`, `memory_recall`, `memory_add`, `memory_subtract`, `memory_clear` ✓
- Variable functions: `setvar`, `delvar`, `listvars`, `clearvars` ✓
- Security constants: `MAX_EXPONENT=10000`, `MAX_FACTORIAL=1000`, `MAX_NESTING_DEPTH=100`, `MAX_RESULT_VALUE=1e308`, `DEFAULT_CACHE_SIZE=1024` ✓
- All trigonometric functions: `sin`, `cos`, `tan`, `asin`, `acos`, `atan`, `sinh`, `cosh`, `tanh`, `asinh`, `acosh`, `atanh` ✓
- All logarithmic functions: `log`, `ln`, `log10`, `log2`, `exp`, `sqrt` ✓
- All statistical functions: `mean`, `median`, `std`, `variance`, `sum`, `min`, `max`, `clamp`, `hypot` ✓
- All combinatorics functions: `factorial`/`fact`, `perm`, `comb`, `gcd`, `lcm` ✓
- All complex number functions: `real`, `imag`, `conj`, `phase`, `polar`, `rect` ✓
- All bitwise functions: `bitand`, `bitor`, `bitxor`, `bitnot`, `bitlshift`, `bitrshift` ✓
- All random functions: `random`, `randint`, `randn`, `gauss`, `seed` ✓
- All number theory functions: `isprime`, `primefactors`, `nextprime`, `prevprime` ✓
- All format conversion functions: `bin`, `hex`, `oct` ✓
- All percentage functions: `percentof`, `aspercent` ✓
- All physical constants: `pi`, `e`, `tau`, `inf`, `nan`, `i`, `c`, `c0`, `speedoflight`, `speedoflightvacuum`, `na`, `avogadro`, `avogadros`, `h`, `planck`, `planckconstant`, `k`, `boltzmann`, `boltzmannconstant`, `r`, `gasconstant`, `idealgasconstant`, `g`, `standardgravity`, `elementarycharge`, `echarge`, `f`, `faraday`, `faradayconstant`, `u`, `amu`, `atomicmassunit`, `epsilon0`, `vacuumpermittivity`, `mu0`, `vacuumpermeability`, `G`, `gravitationalconstant`, `me`, `electronmass`, `mp`, `protonmass`, `mn`, `neutronmass`, `re`, `electronradius`, `alpha`, `finestructure`, `rydberg`, `rydbergconstant`, `stefan`, `stefanboltzmann`, `wien`, `wienconstant`, `planckbar`, `hbar`, `reducedplanck` ✓
- Forbidden node types enforcement ✓
- Thread-safe operations using `threading.Lock` ✓
- `_complex_aware()` wrapper for complex number support ✓

---

## Minor Issues

### MIN-1: `getvar` Return Type Annotation

**Location:** `evaluator.py:792-802`

The `getvar` function returns `Any` but the docstring says it returns the variable value or 0 if not found. The return type annotation should be `Any` not missing.

**Severity:** Very low

---

### MIN-2: `Evaluator` Not Referenced in Key Exports

**Location:** `architecture/evaluator.md:14-34`

The Key Exports section shows imports but doesn't mention `Evaluator` (the main class) even though it's exported. This is the class users would need to subclass or instantiate for custom evaluation.

**Severity:** Very low

---

## Recommendations

1. **Fix `EggCalcApp` import example** - Change to `from eggcalc.evaluator import EggCalcApp` or ensure it's re-exported from `eggcalc/__init__.py`

2. **Update function aliases documentation** - Add `lshift`/`rshift` aliases and all snake_case variants (`is_prime`, `prime_factors`, etc.)

3. **Fix `evaluate_with_timeout` example** - Replace list comprehension with generator expression

4. **Clarify `getvar` behavior** - Document that undefined variables return `0`

5. **Add missing functions to documentation** - `floor`, `ceil`, `trunc`, `degrees`, `radians`, `atan2`, `log1p`, `expm1`, `uniform`, `randrange`, etc.

6. **Clarify `evaluate_async` internal behavior** - Note that it calls `evaluate_raw` (normalization pipeline) not `evaluate` directly

7. **Add bitwise type requirements** - Note that bitwise operations require integer operands

---

## Risk Assessment

| Category | Risk Level | Notes |
|----------|------------|-------|
| Security | Low | AST validation is sound; forbidden nodes properly blocked |
| Correctness | Low | Discrepancies are mostly documentation issues |
| Usability | Medium | Several examples would fail; missing API surface |
| Completeness | Medium | ~30+ functions undocumented |

No critical issues found. The core evaluation engine is well-implemented and secure. Most issues are documentation-related rather than functional bugs.
