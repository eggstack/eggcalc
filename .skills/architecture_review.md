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

# List all architecture docs (38 files; overview.md has the Deep Dive Index)
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
- Use `.venv/bin/python -c "from module import function"` to verify exports (system python may lack the package installed)
- Check `__all__` lists for public API consistency
- Run examples from docs — do not trust doc output comments; execute them
- Run tests to verify functionality

### 4. Important Notes
- Use specific `file:line` references when reporting issues
- Distinguish between bugs (code wrong) vs doc issues (doc wrong)
- For bugs, verify the issue actually causes failure before documenting
- **visible_repr() check order is critical** - Variation selector (U+FE00-U+FE0F) must be checked BEFORE category 'M' checks

### 5. Known Code Patterns
- TypedDict classes don't support `__slots__` (ignored by Python)
- exact/ functions return TypedDicts — plain dicts at runtime; attribute access fails
- `_get_script_heuristic()` is cached with `@lru_cache`
- CONFUSABLES dict has `reverse_confusables()` for reverse lookups
- `unicode_normalization_only` classification is valid and reachable in `text_equal()`/`explain_diff()`, but NOT in `list_compare()` near_matches (removed as dead code)
- `MAX_TEXT_INPUT_LENGTH = 100_000` enforced in validate.py and MCP tools

## Documentation/Code Inconsistencies to Watch For

- TypedDict vs NamedTuple mismatches (code uses TypedDict throughout; exception: `CodepointInfo` in primitives.py is a NamedTuple with an `idx` field)
- Stale line counts in module tables (`wc -l eggcalc/<module>.py` to verify)
- Stale registry counts (unit definitions, tool counts, profile sizes, lookup-table sizes — measure them, don't estimate)
- Example output comments that were never executed (run every snippet before documenting it)
- Missing function aliases (e.g., `mcp_main = main` at the end of server.py)

## Architecture Files Location
- `architecture/` - Module-level documentation (38 docs including overview, authority_inventory, mutable_state_inventory)
- `docs/exact.md` - User-facing exact/ module documentation

## Documentation Maintenance
When updating code:
1. Check if corresponding architecture doc needs update
2. Ensure `build_single.py` still works (code must be in core modules)
3. Run all tests to verify no regressions
4. Update AGENTS.md if new conventions are introduced

See `.skills/documentation_maintenance.md` for the full update checklist.
