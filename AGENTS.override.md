# AGENTS.override.md

## Session-Specific Overrides and Extensions

This file contains overrides and additions specific to this codebase. Items here take precedence over AGENTS.md.

### Important Implementation Notes

**Build Single File Convention:**
The codebase must work when assembled by `build_single.py` into a single file. All code must be in one of the four core modules: `normalize.py`, `evaluator.py`, `units.py`, or `__main__.py`.

**Key Architectural Distinctions:**
- `run()` handles natural language AND unit conversions (normalizes first)
- `evaluate()` handles only valid Python syntax (no normalization)
- When testing NL or unit features, use `run()` or CLI, NOT `evaluate()`

**Unit Aliases Behavior:**
Prefixed units like `kN`, `mV`, `mA` map to themselves in `UNIT_ALIASES`. Word forms like `kilonewton` alias to the prefixed form (e.g., `"kilonewton": "kN"`). This is correct behavior - the word form converts to the symbol form which then properly converts.

**exact/ Module File Organization:**
- `confusables.py` is an auto-generated data file (~176KB, 6580 lines) containing only the CONFUSABLES dict
- TypedDict classes are in their logical modules (validate.py, measure.py, unicode_tools.py, etc.), NOT in confusables.py
- Helper functions like `confusables_count()` should go in `unicode_tools.py`, not `confusables.py`
- `reverse_confusables()` is implemented, exported, and documented in architecture docs

**visible_repr() Check Order is Correct:**
The variation selector check (0xfe00-0xfe0f) comes BEFORE the combining mark check in `visible_repr()`. This is the correct order per AGENTS.md conventions. The code at primitives.py:273-276 is correct.

**Verified NOT Bugs:**
- `synthesis.py:337-338` - `accent_or_diacritic_difference` IS reachable (NFC-equal strings can be byte-different after casefocus when precomposed vs decomposed)
- `normalize.py:693` - `_handle_negative_token` has bounds checking + regex guard, no IndexError possible

**build_single.py Convention:**
- `normalize_main` alias is created by `build_single.py:236` during assembly, does not exist in source `normalize.py`

### Known Bugs - All Fixed (2026-05-29)

All identified bugs have been verified as fixed:

1. **normalize.py:762-763** - Double minus bug - FIXED (bounds check added)
2. **mcp/tools.py:324** - `unit_info()` calls non-existent `list_units()` - FIXED (uses `get_all_units()`)
3. **normalize.py:367,369** - Int regex patterns have erroneous `|` - FIXED (patterns corrected)
4. **mcp/tools.py:839 and 1337** - Duplicate `_VALID_TRANSFORM_OPERATIONS` - FIXED (duplicate removed)
5. **units.py:48-53** - `__eq__` returns NotImplemented for different units - FIXED (returns False)

### Verified as Working (No Action Needed)

The following items were claimed as bugs but are actually working correctly:
- `units.py:66` - `__add__` scalar+dimensional already raises ValueError correctly
- `units.py:80-83` - `__rsub__` scalar+dimensional already raises ValueError correctly  
- `units.py:66` - `__add__` and `__rsub__` correctly reject scalar + dimensional mixing
- `normalize.py:1517` - `--verbose` flag logic is actually correct
- `validate.py:413` - `toml_shape` uses Exception which catches all errors
- `synthesis.py:1072` - `list_compare` operator precedence already has parentheses
- `primitives.py:365` - ZWSP (0x200B) already included in extend character check
- `get_unit_category` import in evaluator.py:27 - import IS present (not a bug)
- `_is_extended_pictographic` name-based fallback includes 'SIGN' keyword which over-matches non-pictographic symbols like © ® ™ (acceptable for text detection purposes)

### Architecture Conventions

**TypedDict vs NamedTuple:**
- All architecture docs use `class Xxx(TypedDict)` correctly
- TypedDict is used throughout for consistency with Python 3.14+ typing patterns
- TypedDict classes do NOT support `__slots__` - only regular classes do

**ConfusableInfo fields:**
- Use `confusable_with` and `confusable_name`, not `confusable_for` or `confusable_codepoint`

**ScriptInfo fields:**
- Use `index`, `char`, `script`, `codepoint` (not `count`, `start`, `end`)

**detect_mixed_scripts return:**
- Returns MixedScriptsResult TypedDict with keys `mixed_scripts`, `scripts`, `positions`

**CommonPrefixSuffix fields:**
- Use `common_prefix_len`, `common_suffix_len` (not `prefix`, `suffix`)

**visible_repr() Check Order:**
- Variation selector check (0xfe00-0xfe0f) comes BEFORE combining mark check
- This is correct per Unicode display recommendations

**validate.py Input Limits:**
- `MAX_INPUT_LENGTH = 100_000` enforced in `check_brackets()` and `validate_json()`
- `MAX_SAMPLE_LENGTH = 10_000` enforced in `regex_test()`
- Functions raise `ValueError` when input exceeds the limit
- Consistent with MCP layer's `MAX_TEXT_LENGTH` constant

### Plan Reference

All implementation items have been verified as completed. The plan files have been archived.

### Architecture Review Findings (2026-05-29)

All 15 architecture modules reviewed. Key findings:

**CLI Output Format Issue:**
- Documentation describes `expression -> result` output format
- Code only outputs `result`
- No code changes made - documentation discrepancy only

**validate.py `list_sort` Parameter:**
- `stable` parameter has no effect - Python's `sorted()` is always stable
- No code changes made - parameter is harmless but meaningless

**API `normalize_expression` Return Type:**
- Documentation shows string return, actual is `tuple[str, int]`
- Examples in docs should show tuple unpacking

### All Tests Pass

```
2251 tests pass
```

(End of file)