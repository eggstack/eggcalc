# Implementation Patterns for eggcalc

## Purpose
Guide agents implementing fixes and features across the codebase.

## Key Conventions

### Testing API Selection
Critical distinction between `evaluate()` and `run()`:

| Use Case | API | Example |
|----------|-----|---------|
| Pure math | `evaluate()` | `evaluate("5 + 3")` |
| Natural language | CLI or `run()` | `run("five plus three", NORMALIZE, PATTERNS)` |
| Units with operators | CLI or `run()` | `run("30m + 100ft", NORMALIZE, PATTERNS)` |

### Common Fix Patterns

#### Adding complex-aware math function
1. Create wrapper with `_complex_aware()` decorator
2. Update FUNCTIONS dict to use wrapper
```python
_sinh = _complex_aware(math.sinh, cmath.sinh)
FUNCTIONS["sinh"] = _sinh
```

#### Temperature conversion fix
Temperature units use offset math, not multiplicative factors. When converting within temperature category:
```python
if cat == "temperature" and target_cat == "temperature":
    converted = convert_temperature(self.value, self.unit, target_unit)
    return UnitValue(converted, target_unit)
```

#### Bitwise float check
Add check in `visit_BinOp` before calling BINOPS:
```python
is_bitwise = op_class in (ast.BitAnd, ast.BitOr, ast.BitXor, ast.LShift, ast.RShift)
if is_bitwise and (isinstance(left_val, float) or isinstance(right_val, float)):
    raise EvaluationError("Bitwise operations require integer operands, not floats")
```

#### Text classification (accent/diacritic vs case)
The `_classify_difference()` function in synthesis.py returns different classifications:
- `exact_match` - strings are identical
- `case_only` - casefold makes them equal (e.g., "HELLO" vs "hello")
- `accent_or_diacritic_difference` - NFC equal but casefold differs (e.g., "café" vs "cafe\u0301")
- `unicode_normalization_only` - NFC equal and casefold equal but not raw equal
- `length_only` - different lengths
- `invisible_character` - invisible characters detected
- `ordinary_text_difference` - other differences

### Module Organization

#### Core modules (combined by build_single.py)
- `eggcalc/units.py` - Unit definitions, conversions
- `eggcalc/evaluator.py` - AST evaluation, EggCalcApp
- `eggcalc/normalize.py` - NL processing
- `eggcalc/cli.py` - CLI dispatch, REPL, text commands
- `eggcalc/capabilities.py` - Runtime capability detection
- `eggcalc/_protocol.py` - MCP protocol version constants
- `eggcalc/__main__.py` - Thin entry point (not in build manifest)

#### exact/ modules (26 submodules, always separate)
- `primitives.py` - UTF-8, codepoints, visible_repr
- `unicode_tools.py` - Script detection, confusables (forward and reverse)
- `confusables.py` - Auto-generated data file (CONFUSABLES dict only)
- `diff.py` - Levenshtein, diff_spans, `__all__` exports
- `diff_analysis.py` - Diff analysis and classification
- `measure.py` - Line/word metrics
- `validate.py` - Bracket/JSON/regex validation with input limits
- `synthesis.py` - Text comparison/explanation
- `unicode_policy.py` - Unicode canonicalization policies
- `identifier.py` - Identifier table inspection
- `identifier_inspect.py` - Identifier analysis
- `transform.py` - Text transformation operations
- `position.py` - Positional text operations
- `patch.py` - Patch apply/summary tools
- `path_tools.py` - Path comparison and scoping
- `shell.py` - Shell split/quote/compare
- `markdown.py` - Markdown structure analysis
- `config.py` - dotenv/INI validation
- `cargo.py` - Cargo.toml inspection
- `version.py` - Semver/cargo constraint checking
- `inspect_prompt.py` - Prompt injection detection
- `glob.py` - Glob pattern matching
- `manifests.py` - Manifest inspection tools
- `llm_hygiene.py` - LLM hygiene analysis
- `repo_audit.py` - Repository audit tools
- `__init__.py` - Package exports

### Always Run Tests
After any change:
```bash
.venv/bin/python build_single.py && .venv/bin/python -m pytest tests/ -x -q
```

### Build Single File Notes
When modifying `build_single.py`:
- The script renames `main()` to `normalize_main()` and `mcp_main()` to avoid conflicts
- Aliased imports like `count_graphemes as _count_graphemes` in synthesis need explicit de-aliasing
- Use `code.replace("_funcname(", "funcname(")` for each aliased function

### Docstring Updates
When adding new functions, update:
1. The function docstring
2. `eggcalc/exact/__init__.py` exports if public API
3. AGENTS.md Implementation Notes if notable pattern