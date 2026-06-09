# API Architecture Review

**Document:** `architecture/api.md`
**Code:** `eggcalc/__init__.py`, `eggcalc/evaluator.py`
**Date:** 2026-05-29

---

## Summary

The architecture document accurately describes the majority of the public API. However, several discrepancies were identified between the documented behavior and actual implementation, including one potential security concern, multiple documentation inconsistencies, and some missing exports.

---

## Discrepancies

### D1: `normalize_expression` Return Type Documentation

**Location:** `architecture/api.md:144` vs `eggcalc/normalize.py`

**Issue:** The documentation shows:
```python
normalize_expression("five plus three")  # "5+3"
```

But `normalize_expression()` returns a `tuple[str, int]`, not a bare string. The second element is an exit code. The example omits the exit code.

**Severity:** Low (documentation example is incomplete)

**Recommendation:** Update examples to show tuple unpacking:
```python
normalized, exit_code = normalize_expression("five plus three")
# normalized = "5+3", exit_code = 0
```

---

### D2: `EggCalcApp` Default Cache Size Example

**Location:** `architecture/api.md:62` vs `evaluator.py:1413`

**Issue:** The documentation shows `app = EggCalcApp(cache_size=1000)` but the actual default is `DEFAULT_CACHE_SIZE` which equals `1024`.

**Severity:** Low (example uses non-default value without noting it)

---

### D3: `load_user_config_extended` Not Exported

**Location:** `architecture/api.md` (not documented) vs `evaluator.py:164-183`

**Issue:** The function `load_user_config_extended()` exists in `evaluator.py` but is NOT exported in `__init__.py`. This appears intentional per `__init__.py:22-23` which states custom number/operator words via external config are not officially supported.

**Note:** The parent plan (`plans/plan.md:15`) explicitly defers this item: "D3: `load_user_config_extended` - Not exported by design - thread-safety concerns"

**Severity:** Informational (by design, but function exists and is undocumented)

---

## Potential Bugs

### B1: Shallow Copy for Instance Isolation

**Location:** `evaluator.py:1055-1056`

```python
self.CONSTANTS = self.__class__.CONSTANTS.copy()
self.FUNCTIONS = self.__class__.FUNCTIONS.copy()
```

**Issue:** EggCalcApp advertises "Instance-isolated constants/functions" but uses shallow copies. Nested mutable objects (e.g., lists used as values) would be shared across instances.

**Example:**
```python
app1 = EggCalcApp()
app2 = EggCalcApp()
# If CONSTANTS contained a list value, both apps would share it
```

**Severity:** Medium (documented isolation suggests deep isolation)

**Recommendation:** Use `copy.deepcopy()` if true instance isolation is required, or clarify that only top-level key/value pairs are isolated.

---

## Missing Documentation

### M1: Unexported but Implemented Functions

The following functions exist in `evaluator.py` but are not documented in `architecture/api.md`:

| Function | Location | Purpose |
|----------|----------|---------|
| `load_user_config_extended()` | `evaluator.py:164` | Extended config loading for custom NL words |
| `_cached_normalize_and_evaluate()` | `evaluator.py:122` | Internal cache for `evaluate_cached()` |
| `_ensure_config_loaded()` | `evaluator.py:114` | Lazy config loading wrapper |
| `_safe_pow()` | `evaluator.py:186` | Power with exponent limits |

**Severity:** Low (internal APIs, not meant for public use)

---

### M2: Internal Helper Functions

Numerous internal helper functions exist but are not documented:

- Statistical: `_mean`, `_std`, `_median`, `_mode`, `_variance`, `_variance_sample`
- Bitwise: `_bitand`, `_bitor`, `_bitxor`, `_bitnot`, `_bitlshift`, `_bitrshift`
- Combinatorics: `_perm`, `_comb`
- Random: `_random`, `_randint`, `_randrange`, `_uniform`, `_randn`, `_gauss`, `_seed`
- Complex: `_real`, `_imag`, `_conj`, `_phase`, `_polar`, `_rect`
- Unit: `_convert`, `_temp`
- And many more...

These are internal implementation details.

---

## Documentation Clarifications Needed

### C1: `Evaluator.visit()` Usage Example

**Location:** `architecture/api.md:77-79`

```python
evaluator = Evaluator()
evaluator.visit(ast.parse("5 + 3"))
```

**Issue:** The example shows calling `visit()` directly on a parsed AST. However:
1. `visit()` is designed to visit individual nodes, not trees
2. The correct usage would be `evaluator.visit(tree.body)` where `tree.body` is the actual expression node

**Recommendation:** Either clarify this is pseudocode, or correct to:
```python
tree = ast.parse("5 + 3")
evaluator.visit(tree.body)  # Visit the expression body
```

---

### C2: Timeout Units

**Location:** `architecture/api.md:46`

The timeout parameter description does not explicitly state the units. The implementation uses seconds (from Python's `concurrent.futures`).

**Recommendation:** Add units to the description.

---

### C3: Memory Class vs Functions

**Location:** `architecture/api.md:201-203`

The documentation states `Memory` class is "available for type hints" but doesn't clarify that the `memory_*` functions operate on a global `Memory` instance and return floats, not `Memory` objects.

---

## Verified Correct Items

The following items were verified as correctly documented and implemented:

- `evaluate()` - Direct AST evaluation without normalization ✓
- `evaluate_raw()` - Full normalization pipeline ✓
- `evaluate_cached()` - LRU caching with 1024 entries ✓
- `evaluate_async()` - Async wrapper using thread pool ✓
- `evaluate_with_timeout()` - ThreadPoolExecutor with timeout ✓
- `EggCalcApp` - Thread-safe with caching and async support ✓
- `register_constant()` / `register_function()` - Thread-safe global registration ✓
- All memory functions: `memory_store`, `memory_recall`, etc. ✓
- All variable functions: `setvar`, `getvar`, `delvar`, etc. ✓
- Security constants: `MAX_EXPONENT=10000`, `MAX_FACTORIAL=1000`, etc. ✓
- Exception classes: `EvaluationError`, `TimeoutError` ✓
- `UnitValue` type with `value` and `unit` attributes ✓
- `TimeoutError` raised on timeout expiration ✓
- Thread-safe operations using `threading.Lock` ✓

---

## Minor Issues

### MIN-1: Line Ordering in `__init__.py`

**Location:** `eggcalc/__init__.py:140` vs lines 82-138

`load_user_config()` is called at line 140, before the `__all__` list definition at line 82. This works but is unconventional ordering.

**Severity:** Very low

---

### MIN-2: Docstring Cut-off

**Location:** `architecture/api.md:109-111`

```python
register_function("square", lambda x: x ** 2)
```

This appears to be a stray example that doesn't match the preceding `get_default_evaluator()` documentation.

**Severity:** Very low

---

## Recommendations

1. **Update `normalize_expression` examples** to show tuple return type
2. **Clarify or correct** the `Evaluator.visit()` usage example
3. **Consider** using `deepcopy` in EggCalcApp if true instance isolation is required
4. **Add timeout units** to documentation
5. **Remove or relocate** the stray `register_function` example at line 109-111

---

## Risk Assessment

| Category | Risk Level | Notes |
|----------|------------|-------|
| Security | Low | AST validation appears sound; no eval() usage |
| Correctness | Low | Minor doc discrepancies, one shallow-copy concern |
| Usability | Low | Some examples could be clearer |
| Completeness | Medium | Several internal functions not documented |

No critical issues found that would prevent the API from functioning as documented.
