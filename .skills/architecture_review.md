# Architecture Review Skill

## Purpose
Guide agents through systematic architecture document review against implementation code.

## When to Use
- Reviewing architecture documents (`.md` files in `architecture/`)
- Verifying implementation matches documentation
- Identifying bugs, inconsistencies, or missing features
- Adding new features to the codebase

## Review Process

### 1. Gather Information
```bash
# Read architecture document
cat architecture/<module>.md

# Read corresponding implementation
cat eggcalc/<module>.py

# List all architecture docs
ls architecture/
```

### 2. Focus Areas Checklist
For each module, examine:
1. **Completeness** - All documented features implemented?
2. **Correctness** - Implementation matches behavior?
3. **Consistency** - Doc and code contradict?
4. **Edge Cases** - Unhandled cases?
5. **Performance** - Efficiency concerns?
6. **Security** - Potential issues?
7. **Maintainability** - Code quality?
8. **Test Coverage** - Adequate tests?

### 3. Verification Steps
- Use `grep` to find specific function definitions
- Use `python3 -c "from module import function"` to verify exports
- Check `__all__` lists for public API consistency
- Run tests to verify functionality

### 4. Important Notes
- Use specific `file:line` references when reporting issues
- Distinguish between bugs (code wrong) vs doc issues (doc wrong)
- For bugs, verify the issue actually causes failure before documenting
- **visible_repr() check order is critical** - Variation selector (U+FE00-U+FE0F) must be checked BEFORE category 'M' checks

### 5. Known Code Patterns
- TypedDict classes don't support `__slots__` (ignored by Python)
- `_get_script_heuristic()` is cached with `@lru_cache`
- CONFUSABLES dict has `reverse_confusables()` for reverse lookups
- `unicode_normalization_only` classification is valid and reachable in `text_equal()`/`explain_diff()`, but NOT in `list_compare()` near_matches (removed as dead code)
- `MAX_INPUT_LENGTH = 100_000` enforced in validate.py and MCP tools

## Common Issues Found in This Codebase

**These issues were identified during architecture review and have been resolved:**

1. **Combine consecutive numbers** - `split_at_operators` now properly handles whitespace-separated number words
2. **TypedDict `__slots__`** - Removed from all TypedDict classes (they don't support `__slots__`)
3. **Missing exports in exact/__init__.py** - `unicode_scripts`, `confusables_count`, `longest_common_subsequence` now exported
4. **Text classification order** - `_classify_difference()` checks NFC equality before casefold equality
5. **MCP response consistency** - `math_eval` returns direct result dict
6. **Temperature conversion crash** - Now raises descriptive ValueError
7. **list_compare() dead code** - Removed unreachable `unicode_normalization_only` loop
8. **Float regex pipe bug** - Fixed `[-|+]?` to `[-+]?`
9. **Duplicate constants table entries** - Fixed (removed duplicate `G` entry)
10. **UnitValue methods undocumented** - Now documented (`__str__`, `__format__`, `__eq__`, `__hash__`, etc.)

**Documentation/Code inconsistencies to watch for:**

- TypedDict vs NamedTuple mismatches (code uses TypedDict throughout)
- Missing function aliases (check `mcp_main = main` at server.py:234)
- Data structure field mismatches (verify against actual code)
- Parameter name alignment (docs sometimes use different names than code)

**Note:** The architecture review has been completed. All 15 module reviews were performed and findings incorporated into the documentation.

## Architecture Review Findings (2026-05-28 through 2026-05-29)

The architecture review identified issues across all modules. **All 35 actionable items implemented/fixed.**

### HIGH Priority Bugs (FIXED)
- `units.py:146-164` - Temperature-to-non-temperature conversion crash → now raises clear ValueError
- `synthesis.py:704-714` - `unicode_normalization_only` near_match unreachable → code removed
- `normalize.py:368` - Float regex `[-|+]?` → fixed to `[-+]?`

### HIGH Priority Documentation Issues (FIXED)
- `normalize_expression()` documented as returning `str` but actually returns `tuple[str, int]`
- Missing constants `g`/`standardgravity` and `wien`/`wienconstant` in constants table
- All `common_prefix_suffix` examples returned wrong values
- `FirstDiff` TypedDict showed 3 fields but code has 6
- `normalize_main` alias documented but doesn't exist in source
- `reverse_confusables()` undocumented public function
- `UnitValue` public methods not documented

### Review Process Notes
- All modules reviewed with improvement plans generated
- Complete findings consolidated in architecture documentation
- 35 actionable items across 5 waves implemented and verified
- All items resolved

### Known Documentation Discrepancies (2026-05-29)
- CLI output format: docs describe `expression -> result`, code only outputs `result`
- `validate.py` `list_sort` `stable` parameter has no effect (Python's `sorted()` is always stable)
- `normalize_expression()` documented as returning `str` but actually returns `tuple[str, int]`

## Architecture Files Location
- `architecture/` - Module-level documentation
- `docs/exact.md` - exact/ module documentation

## Documentation Maintenance
When updating code:
1. Check if corresponding architecture doc needs update
2. Ensure `build_single.py` still works (code must be in core modules)
3. Run all tests to verify no regressions
4. Update AGENTS.md if new conventions are introduced