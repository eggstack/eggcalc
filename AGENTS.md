# AGENTS.md

## Overview
`eggcalc` is a natural language math expression calculator that uses only Python's standard library. It parses math expressions in English (like "five plus three") and converts them to numeric results, with support for unit conversions.

## Architecture

### Build Process
The codebase is designed to be assembled into a **single self-contained Python script** for portability:

1. **`build_single.py`** - Combines modules into `eggcalc.py`:
   - `units.py` - Unit definitions and conversion factors
   - `evaluator.py` - AST-based expression evaluation
   - `normalize.py` - Natural language processing
   - `__main__.py` - CLI entry point

2. **`install.py`** - Calls `build_single.py` then installs the result to `~/.local/bin/calc`

**Critical:** When modifying the codebase, ensure changes work with `build_single.py` assembling everything into one file. All code must be in one of the four core modules.

### Processing Pipeline
Understanding the two evaluation paths is critical:

1. **`run()` (full pipeline)** - `normalize.py` processes input first, then passes to evaluator:
   ```
   Input → Normalization → Tokenization → Unit Conversion → Evaluation → Result
   ```
   - Handles natural language ("five plus three")
   - Handles unit syntax ("30m + 100ft")
   - Uses `evaluate()` internally after normalization

2. **`evaluate()` (direct AST)** - Skips normalization, directly parses via Python AST:
   ```
   Input → Python AST Parse → Evaluation → Result
   ```
   - Expects valid Python syntax
   - Does NOT handle NL input
   - Does NOT handle unit suffixes like "km" or "m"

**Example of what each handles:**
```python
run("five plus three", NORMALIZE, PATTERNS)  # ✓ Works
run("30m + 100ft", NORMALIZE, PATTERNS)      # ✓ Works
evaluate("5 + 3")                            # ✓ Works
evaluate("five plus three")                  # ✗ Fails (invalid Python)
evaluate("1km in m")                         # ✗ Fails (invalid Python)
```

### Output Format
The CLI prints **only the result** — no echo of the input, no arrows, no extra characters:
```bash
calc "5 + 3"      # → 8
calc "sqrt(144)"  # → 12.0
calc "30m + 100ft"  # → 60.48 m
```
This applies to both single-expression mode and interactive REPL. History in REPL also shows result only. Use `-e` for quiet/piped mode, `--json` for structured output.

### Core Modules

| Module | Purpose |
|--------|---------|
| `eggcalc/normalize.py` | NL tokenization, number word conversion, expression normalization |
| `eggcalc/evaluator.py` | AST parsing and evaluation, mathematical operations |
| `eggcalc/units.py` | Unit definitions, conversion factors, temperature conversions |
| `eggcalc/__main__.py` | CLI entry point (delegates to `normalize.py:main()`) |

### Supporting Modules (exact/)

Located in `eggcalc/exact/` - Provides low-level Unicode text primitives for detecting hidden characters, confusables, and text metrics:

| Module | Purpose |
|--------|---------|
| `primitives.py` | UTF-8 encoding, codepoint iteration, Unicode normalization |
| `unicode_tools.py` | Script detection, confusable character detection |
| `unicode_policy.py` | Named Unicode safety policies and canonicalization profiles |
| `confusables.py` | Confusable character identification (homoglyphs) - large file (~180KB) |
| `validate.py` | JSON/bracket/regex/TOML validation |
| `diff.py` | String diffing algorithms |
| `measure.py` | Text metrics (words, lines, categories) |
| `synthesis.py` | Higher-level text analysis tools |
| `patch.py` | Unified diff parsing, patch application simulation, patch summary |
| `shell.py` | Shell command parsing, quoting, and argv comparison |
| `config.py` | .env and INI config validation |
| `markdown.py` | Markdown structure analysis and code fence extraction |
| `path_tools.py` | Path lexical analysis, normalization, comparison, scope checking |
| `identifier.py` | Identifier naming convention classification |
| `identifier_inspect.py` | Identifier collision detection and confusable analysis |
| `transform.py` | Text transformations, escaping, hashing, fingerprinting |
| `position.py` | Text position conversion (byte offsets, line/column, UTF-16) |
| `glob.py` | Glob pattern matching |
| `inspect_prompt.py` | Prompt injection detection (hidden chars, instruction phrases, ANSI escapes) |
| `cargo.py` | Cargo.toml inspection (package metadata, dependencies) |
| `version.py` | Semver/cargo version constraint parsing and checking |

### Supporting Modules (mcp/)

Located in `eggcalc/mcp/` - Model Context Protocol server for AI agent tool access:

| Module | Purpose |
|--------|---------|
| `server.py` | MCP server implementation, stdio-based request handling |
| `tools.py` | MCP tool definitions |
| `schemas.py` | JSON schemas for MCP tool definitions |

### Key Data Structures

- **`NUMBER_WORDS`** - Dictionary mapping number values to word variants ("one", "five", etc.)
- **`OPERATOR_CONVERSIONS`** - Maps operator words to symbols ("plus" → "+")
- **`FUNCTION_MAPPINGS`** - Maps function name variants to canonical names (e.g., "square root" → "sqrt")
- **`CONSTANT_WORDS`** - Maps physical constant names (avogadro, planck, etc.) to symbols
- **`STRIPPED_PHRASES`** - Filler words removed during normalization ("what's", "calculate", etc.)
- **`UNIT_BASE`** - Base units and their conversion factors
- **`UNIT_CONVERSIONS`** - Cached pairwise conversion factors
- **`UNIT_ALIASES`** - Maps all unit variants to canonical forms

## Guardrails

### Dependencies
- **Standard library only** - No external packages allowed
- All imports must be from: `argparse`, `os`, `sys`, `re`, `math`, `ast`, `functools`, `typing`, `stat`, `shutil`, `subprocess`, `traceback`

### Typing
- Use type annotations for function signatures
- Use `Mapping[str, Pattern]` from `typing` for pattern collections
- Return types must be declared

### Testing
- All tests must pass (`python -m pytest tests/`)
- New tests must use the correct API:
  - For NL/unit functionality → use `run()` or test through CLI
  - For pure math expressions → use `evaluate()`
- 2163 tests currently pass (as of 2026-06-16)

### Code Style
- Follow existing patterns in the codebase
- Use `lru_cache` for expensive operations that can be memoized
- All code must work when inlined by `build_single.py`

## Working with Tests

### Current Test Structure
```
tests/
├── conftest.py              # Shared fixtures
├── test_build_single.py     # Build script tests
├── test_cargo_inspect.py    # Cargo.toml inspection tests
├── test_cli_text.py         # CLI text tools tests
├── test_clicalc.py          # Core functional tests
├── test_config_validation.py # dotenv/INI validation tests
├── test_exact.py            # Exact module tests
├── test_golden_fixtures.py  # Golden fixture tests
├── test_identifier_table.py # Identifier table inspection tests
├── test_line_range.py       # Line range extract/compare tests
├── test_markdown_tools.py   # Markdown structure tests
├── test_math_edge_cases.py  # Math edge case tests
├── test_math_identities.py  # Mathematical laws verification
├── test_mcp_server.py       # MCP server integration tests
├── test_mcp_tools_new.py    # MCP integration tests for new tools
├── test_normalize.py        # Normalization tests
├── test_patch_tools.py      # Patch apply/summary tools tests
├── test_path_compare.py     # Path comparison tests
├── test_path_scope.py       # Path scope check tests
├── test_production_review_2026_07_b.py # Production review tests
├── test_prompt_inspect.py   # Prompt injection detection tests
├── test_repl_and_cli.py     # REPL and CLI integration tests
├── test_security_fuzz.py    # Security/fuzz tests
├── test_shell_tools.py      # Shell split/quote/compare tests
├── test_text_replace_check.py # Text replacement check tests
├── test_tokenization.py     # Tokenization edge cases
├── test_tool_inventory.py   # Tool registry consistency tests
├── test_unicode_policy.py   # Unicode policy/canonicalization tests
├── test_unit_namespace.py   # Unit namespace tests
├── test_version_constraint.py # Version constraint tests
└── fixtures/                # Test fixtures directory
```

### API Usage Reminder
- `evaluate("five plus three")` → Fails (invalid Python syntax)
- `evaluate("1km in m")` → Fails (invalid Python syntax)
- `evaluate("30m + 100ft")` → Fails (invalid Python syntax)

These work through `run()` because normalization converts NL to Python first.

**When writing tests:**
1. For mathematical operations (`5+3`, `2**10`) → `evaluate()`
2. For natural language (`"five plus three"`) → Use CLI or `run()`
3. For unit conversions with operators → Use CLI or `run()`
4. Direct unit suffix parsing (`"1km"`) does not work with `evaluate()`

### Helper Patterns
```python
def get_value(result):
    """Extract numeric value from result, handling UnitValue."""
    if isinstance(result, UnitValue):
        return result.value
    return result

def val(expr):
    """Evaluate and extract value, handling UnitValue."""
    result = evaluate(expr)
    if isinstance(result, UnitValue):
        return result.value
    return result
```

## Architecture Documentation Index

The `architecture/` directory contains module-level developer documentation:

| Document | Module | Purpose |
|----------|--------|---------|
| [overview.md](architecture/overview.md) | — | High-level architecture, data flow, module dependencies |
| [api.md](architecture/api.md) | — | Public API reference |
| [cli.md](architecture/cli.md) | `__main__.py` | CLI entry point |
| [normalize.md](architecture/normalize.md) | `normalize.py` | NL normalization pipeline |
| [evaluator.md](architecture/evaluator.md) | `evaluator.py` | AST-based expression evaluation |
| [units.md](architecture/units.md) | `units.py` | Unit definitions & conversions |
| [exact.md](architecture/exact.md) | `exact/` | Package overview for text analysis tools |
| [primitives.md](architecture/primitives.md) | `exact/primitives.py` | UTF-8, codepoints, normalization |
| [unicode_tools.md](architecture/unicode_tools.md) | `exact/unicode_tools.py` | Script detection, confusables |
| [confusables.md](architecture/confusables.md) | `exact/confusables.py` | Homoglyph identification data |
| [diff.md](architecture/diff.md) | `exact/diff.py` | String diffing algorithms |
| [measure.md](architecture/measure.md) | `exact/measure.py` | Text metrics |
| [synthesis.md](architecture/synthesis.md) | `exact/synthesis.py` | Higher-level text analysis |
| [validate.md](architecture/validate.md) | `exact/validate.py` | JSON/bracket/regex validation |
| [mcp.md](architecture/mcp.md) | `mcp/` | MCP server architecture |
| [review_plan.md](architecture/review_plan.md) | — | Architecture review orchestration |

## Common Patterns

### Adding a New Math Function
1. Add to `FUNCTION_MAPPINGS` in `normalize.py`
2. Implement in `evaluator.py`
3. Add test in `test_clicalc.py`

### Adding a New Unit
1. Add to appropriate category in `UNIT_BASE` in `units.py`
2. Rebuild `UNIT_CONVERSIONS` cache (automatic)
3. Add test via CLI or `run()`

### Adding Number Word Support
1. Add word to `NUMBER_WORDS` in `normalize.py`
2. The normalization pipeline handles word-to-number conversion

## File Locations

- **CLI entry**: `eggcalc/__main__.py` (18 lines)
- **Normalize functions**: `eggcalc/normalize.py` (3291 lines)
- **Evaluator functions**: `eggcalc/evaluator.py` (2765 lines)
- **Unit definitions**: `eggcalc/units.py` (2086 lines total)
- **Tests**: `tests/` (29 test files, 2163 tests)
- **Build script**: `build_single.py`
- **Install script**: `install.py`


## Debugging Tips

### Checking what `evaluate()` returns
```python
from eggcalc import evaluate, UnitValue
result = evaluate("5 + 3")
print(f"Type: {type(result)}, Value: {result}")
if isinstance(result, UnitValue):
    print(f"Unit: {result.unit}, Value: {result.value}")
```

### Checking normalization
```python
from eggcalc.normalize import normalize, NORMALIZE, PATTERNS
normalized = normalize("five plus three", NORMALIZE, PATTERNS)
print(f"Normalized: {normalized}")  # Should show "5+3"
```

### Checking unit conversion
```python
from eggcalc.units import get_conversion_factor
factor = get_conversion_factor("km", "m")
print(f"km to m factor: {factor}")  # Should be 1000.0
```

## Implementation Notes

### exact/ Module Conventions
- **`utf8_bytes()` returns `bytes`** - Not an int count, returns actual UTF-8 encoded bytes
- **`visible_repr()` display order matters** - Variation selector checks must come BEFORE combining mark checks (U+FE00-U+FE0F should be checked before category 'M'). The code at primitives.py:273-276 is correct.
- **WORD JOINER (U+2060)** - Now handled by `_INVISIBLE_CHARS` dict lookup, redundant explicit check removed
- **Newline detection `mixed` value** - The `mixed` newline style can be returned but was not properly detected in original implementation
- **`_get_script_heuristic()` benefits from caching** - Now has `@functools.lru_cache` decorator
- **Cf (format) characters intentionally excluded** - `control_chars` in `measure.py` excludes `Cf` category; format characters are silently ignored per UTS #55
- **confusables.py is a data file** - The file `eggcalc/exact/confusables.py` is auto-generated data only (~176KB, 6580 lines). TypedDict classes are in their logical modules, NOT in confusables.py
- **`confusables_count()` helper** - Fast function to count confusables without building full list (unicode_tools.py)
- **`reverse_confusables()` helper** - Given a character, returns all characters that confusable-map TO it using a cached inverted index (unicode_tools.py)
- **`unicode_scripts()` batch function** - Returns script list for all chars in string (unicode_tools.py)
- **`longest_common_subsequence()`** - Implemented in diff.py using dynamic programming
- **`accent_or_diacritic_difference` classification** - Returned when NFC equal but casefold differs (e.g., "café" vs "cafe\u0301"). This IS reachable - verified with precomposed vs decomposed forms.
- **`common_prefix_suffix()` examples fixed** - Docstring now has working examples showing overlap prevention behavior
- **validate.py input limits** - `MAX_INPUT_LENGTH = 100_000` enforced in `check_brackets()` and `validate_json()`, raises `ValueError`
- **`_INVISIBLE_CHARS` contains 22 characters** - Documentation only shows 12; missing: U+180e, U+034f, U+202b-202e, U+2066-2069
- **`unicode_policy.py`** - Named policy checks and canonicalization profiles for Unicode safety. Policies are deterministic heuristics, not semantic security guarantees. Use `unicode_policy_check()` for validation and `canonicalize_text()` for normalization profiles.
- **`shell.py`** - Shell command parsing, quoting, and argv comparison. Uses `shlex` for POSIX-like lexical parsing. Not full shell evaluation.
- **`config.py`** - .env and INI config validation. Line-by-line parsers for common config formats.
- **`markdown.py`** - Markdown structure analysis and code fence extraction. Deterministic line scanner, not a full CommonMark parser.

### TypedDict vs NamedTuple
- Architecture docs may show `@dataclass class Xxx(NamedTuple)` but code uses `class Xxx(TypedDict)`
- TypedDict is used throughout for consistency with Python 3.14+ typing patterns
- Always check actual code for exact return type signatures
- **TypedDict classes do NOT support `__slots__`** - Only regular classes (with actual implementations) support `__slots__`

### MCP Server Conventions
- Tool names in `schemas.py` and `server.py` are now unified via `TOOL_SCHEMAS`
- Response handling is now consistent - `math_eval` returns direct result dict
- `MAX_TEXT_LENGTH` is enforced on `math_eval` tool
- Error messages are sanitized for non-ASCII characters
- Case-insensitive tool matching with suggestions for unknown tools
- `mcp_main` is defined in `server.py:234` as `mcp_main = main`

### Unit Conversion Conventions
- Prefixed units like `kN`, `mV`, `mA` map to themselves in `UNIT_ALIASES`
- Temperature conversions use offset math, not multiplicative factors
- `mps` (meters per second) is in `UNIT_CATEGORIES` as "speed"
- `UNIT_CATEGORIES` is auto-derived from `UNIT_BASE` (multiplicative categories like length, mass) plus manual entries for temperature. British spellings (`metre`/`metres`, `litre`/`litres`, `kilometre`/...) are included in `UNIT_ALIASES` and therefore in the derived category map.
- Gas constant is accessible as `r` and `R` (standard physics symbol). Rankine temperature unit is accessible as `Ra`, `rankine`, `degr`, and `°R`. The `r`/`R` identifiers are NOT Rankine — they are the gas constant (8.314462618 J/(mol·K)).

### Unit Power and Division Semantics
- `5m ** 2` evaluates to `25.0 m**2` (power binds the unit, not the base). The preprocessor wraps `<num>*<unit>` in parens when followed by `**` to preserve correct precedence.
- `5m / 2s` evaluates to `2.5 m/s` (the right-hand `*<unit>` is bound to the denominator). `_add_same_unit_division_parens` always wraps the denominator in parens.
- Multiplication of same units simplifies via `_simplify_unit_string`: `5m * 5m` -> `25.0 m**2`, `5m * 5m * 5m` -> `125.0 m**3`.

## Deferred Items

All implementation plan items are complete. No outstanding deferred items.

(End of file)
