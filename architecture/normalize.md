# normalize.py — Natural Language Processing Module

Converts mathematical expressions written in natural language into executable mathematical expressions.

## Table of Contents

- [Overview](#overview)
- [Key Exports](#key-exports)
- [Re-exported Symbols](#re-exported-symbols)
- [Constants and Limits](#constants-and-limits)
- [Data Structures](#data-structures)
- [Core Public Functions](#core-public-functions)
- [Internal Functions](#internal-functions)
- [Processing Pipeline](#processing-pipeline)
- [Regex Patterns (PATTERNS)](#regex-patterns-patterns)
- [Configuration Building](#configuration-building)
- [Unit Handling](#unit-handling)
- [Number Handling](#number-handling)
- [Implicit Multiplication](#implicit-multiplication)
- [Thread Safety](#thread-safety)
- [CLI and REPL](#cli-and-repl)
- [Security Notes](#security-notes)
- [Module Dependencies](#module-dependencies)

## Overview

The `normalize` module is the **entry point** for natural language input. It handles:
- Number word conversion (`"five"` → `5`)
- Operator word conversion (`"plus"` → `+`)
- Function name normalization (`"square root"` → `sqrt`)
- Physical constant words (`"avogadro"` → `6.022e23`)
- Unit suffix parsing (`"30m"` → number `30` with unit `m`)
- Filler phrase stripping (`"what's"`, `"calculate"`, etc.)
- Multi-word number phrases (`"twenty one"` → `21`, `"one hundred twenty one thousand"` → `121000`)
- Postfix factorial (`"5!"` → `factorial(5)`)
- Compound unit expressions (`"60mi/h in m/s"` → `convert(60*mi/h,m/s)`)
- Percentage handling (`"50%"` → `0.5`)
- Complex number notation (`"3+4i"` → `3+4j`)
- Angle mode (`"30 degrees"` → `30*pi/180`)
- Implicit multiplication (`"3(4+5)"` → `3*(4+5)`, `"5 sin"` → `5*sin`)
- Compact function arguments (`"sin30"` → `sin 30`)

## Key Exports

```python
from eggcalc.normalize import (
    run,              # Full pipeline: normalize + evaluate
    normalize_text,   # Tokenize and normalize text
    normalize_expression,  # Convert NL to Python syntax
    main,             # CLI entry point
    print_help,       # Show help text
    NORMALIZE,        # Compiled normalization config
    PATTERNS,         # Compiled regex patterns
    MAX_INPUT_LENGTH, # 10000
    MAX_NESTING_DEPTH,# 100
)
```

## Re-exported Symbols

`normalize.py` re-exports symbols from sibling modules for convenience. These are defined in `__all__` and imported at module top level:

```python
from .evaluator import EvaluationError, evaluate
from .units import UnitValue
```

| Symbol | Origin | Purpose |
|--------|--------|---------|
| `evaluate` | `evaluator.py` | AST-based expression evaluation |
| `EvaluationError` | `evaluator.py` | Exception raised on evaluation failures |
| `UnitValue` | `units.py` | Wrapper for numeric values with a unit |

## Constants and Limits

| Constant | Value | Description |
|----------|-------|-------------|
| `MAX_INPUT_LENGTH` | `10000` | Maximum input string length (enforced in `normalize_text`) |
| `MAX_NORMALIZED_LENGTH` | `20000` | Maximum normalized expression length (enforced in `normalize_expression`) |
| `MAX_NESTING_DEPTH` | `100` | Maximum parenthesis nesting depth |

Additional internal limits:
- `MAX_REPL_LINE_LENGTH = 100_000` — maximum line length in REPL mode
- `check_if_number` LRU cache has `maxsize=1024`

## Data Structures

### `OPERATOR_CONVERSIONS`

Maps operator symbols to their word variants:

```python
OPERATOR_CONVERSIONS = {
    "+": ["plus", "positive"],
    "-": ["minus", "negative"],
    "*": ["times", "multiplied by", "of"],  # "of" for "30% of 200"
    "/": ["divided by", "over", "per", "divide"],
    "**": ["raised to", "raised to the power of", "to the power of"],
    ",": [],
    "&": ["bitand", "bit and"],
    "|": ["OR", "or", "bitor", "bit or"],
    "^": ["XOR", "xor", "bitxor", "bit xor"],
    "<<": ["left shift", "shift left", "lshift"],
    ">>": ["right shift", "shift right", "rshift"],
    "~": ["NOT", "not", "bitnot", "bit not"],
    "%": ["mod", "modulo", "remainder"],
    "IN": ["in", "into"],   # Unit conversion keywords
    "TO": ["to", "as"],
}
```

Note: `^` is mapped to bitwise XOR, not exponentiation. Power is handled by `**`.

### `FUNCTION_MAPPINGS`

Maps function name variants to canonical names. Contains 79 entries covering:

- Trigonometric: `sine`→`sin`, `cosine`→`cos`, `tangent`→`tan`, `arcsine`→`asin`, `arccosine`→`acos`, `arctangent`→`atan`
- Hyperbolic: `hyperbolic sine`→`sinh`, `hyperbolic cosine`→`cosh`, `hyperbolic tangent`→`tanh`, `arcsinh`→`asinh`, `arccosh`→`acosh`, `arctanh`→`atanh`
- Logarithmic: `ln`→`log`, `log`→`log`, `log10`→`log10`, `log2`→`log2`, `log1p`→`log1p`
- Exponential: `exp`→`exp`, `expm1`→`expm1`
- Rounding: `absolute`/`magnitude`→`abs`, `ceiling`→`ceil`, `floor`→`floor`, `round`→`round`, `sign`→`sign`, `cbrt`/`cube root`→`cbrt`, `trunc`→`trunc`
- Statistical: `mean`/`average`→`mean`, `median`→`median`, `mode`→`mode`, `std`/`stdev`→`std`, `stds`→`std_sample`, `variance`→`variance`, `var`→`var`, `variance_sample`→`var_sample`, `vars`→`vars`
- Combinatorial: `factorial`/`fact`→`factorial`, `gcd`→`gcd`, `lcm`→`lcm`, `perm`→`perm`, `comb`→`comb`, `nPr`→`nPr`, `nCr`→`nCr`
- Number theory: `isprime`/`is_prime`→`isprime`, `primefactors`/`prime_factors`→`primefactors`, `nextprime`/`next_prime`→`nextprime`, `prevprime`/`prev_prime`→`prevprime`
- Complex: `real`→`real`, `imag`→`imag`, `conj`/`conjugate`→`conj`, `phase`→`phase`, `polar`→`polar`, `rect`→`rect`
- Bitwise: `bitand`→`bitand`, `bitor`→`bitor`, `bitxor`→`bitxor`, `bitnot`→`bitnot`, `bitlshift`→`bitlshift`, `bitrshift`→`bitrshift`
- Random: `random`→`random`, `randint`→`randint`, `randn`→`randn`, `randrange`→`randrange`, `gauss`→`gauss`, `seed`→`seed`, `uniform`→`uniform`
- Conversion: `convert`→`convert`
- Percentage: `percentof`/`percent_of`→`percentof`, `aspercent`/`as_percent`→`aspercent`
- Other: `pow`→`pow`, `hypot`→`hypot`, `clamp`→`clamp`, `degrees`→`degrees`, `radians`→`radians`, `atan2`→`atan2`, `sum`→`sum`, `max`→`max`, `min`→`min`, `sqrt`→`sqrt`
- Calculator memory: `store`→`store`, `recall`→`recall`, `Mplus`→`Mplus`, `Mminus`→`Mminus`, `MC`→`MC`, `MR`/`M`→`MR`
- Variables: `setvar`→`setvar`, `getvar`→`getvar`, `delvar`→`delvar`, `listvars`→`listvars`, `clearvars`→`clearvars`
- Temperature: `temp`→`temp`
- Display: `bin`→`bin`, `hex`→`hex`, `oct`→`oct`

### `NUMBER_WORDS`

Maps number values to word forms. Covers 0–19, tens (20–90), scales (hundred through quintillion), and fractional words:

```python
NUMBER_WORDS = {
    "0": ["zero"], "1": ["one"], ..., "19": ["nineteen"],
    "20": ["twenty"], "30": ["thirty"], ..., "90": ["ninety"],
    "100": ["hundred"], "1000": ["thousand"], "1000000": ["million"],
    "1000000000": ["billion"], "1000000000000": ["trillion"],
    "1000000000000000": ["quadrillion"], "1000000000000000000": ["quintillion"],
    "0.5": ["half"], "0.25": ["quarter"],
    "0.001": ["thousandth"], "0.000001": ["millionth"], "0.000000001": ["billionth"],
}
```

### `CONSTANT_WORDS`

Maps physical constant keys to word forms:

```python
CONSTANT_WORDS = {
    "na": ["avogadro", "avogadros", "avogadro number"],
    "r": ["gas constant", "ideal gas constant", "molar gas constant"],
    "planckconstant": ["planck", "planck constant"],
    "k": ["boltzmann", "boltzmann constant"],
    "c": ["speed of light", "speed of light in vacuum", "c zero"],
    "elementarycharge": ["elementary charge", "e charge"],
    "f": ["faraday", "faraday constant"],
    "u": ["atomic mass", "atomic mass unit", "amu"],
    "epsilon0": ["vacuum permittivity", "permittivity of free space"],
    "mu0": ["vacuum permeability", "permeability of free space", "magnetic constant"],
    "standardgravity": ["gravity", "standard gravity", "earth gravity"],
    "G": ["gravitational constant", "newton constant", "big g"],
    "me": ["electron mass"],
    "mp": ["proton mass"],
    "mn": ["neutron mass"],
    "re": ["electron radius", "classical electron radius"],
    "alpha": ["fine structure constant", "sommerfeld"],
    "rydberg": ["rydberg constant"],
    "stefan": ["stefan boltzmann", "stefan-boltzmann constant"],
    "wien": ["wien constant", "wien displacement"],
}
```

### `STRIPPED_PHRASES`

Filler words removed during normalization. Phrases with `\b` are treated as regex patterns:

```python
STRIPPED_PHRASES = [
    "what's",
    "what is",
    r"\ba\b",
    "?",
    "calculate",
    "compute",
    "tell me",
    "give me",
    "the ",
    "please ",
    "hey ",
    "hi ",
    "can you ",
    "could you ",
    "would you ",
    "i want to know ",
    "i'd like to know ",
    "what's the value of ",
    "what's the result of ",
    "what is the value of ",
    "what is the result of ",
    "the value of ",
    "the result of ",
    "the answer is ",
]
```

### `_MULTI_WORD_FUNCTIONS`

Module-level mapping of multi-word function names (replaced before whitespace removal):

```python
_MULTI_WORD_FUNCTIONS = {
    "square root": "sqrt",
    "cube root": "cbrt",
    "inverse sine": "asin",
    "inverse cosine": "acos",
    "inverse tangent": "atan",
    "arc sine": "asin",
    "arc cosine": "acos",
    "arc tangent": "atan",
    "arc cos": "acos",
    "arc sin": "asin",
    "arc tan": "atan",
    "hyperbolic sine": "sinh",
    "hyperbolic cosine": "cosh",
    "hyperbolic tangent": "tanh",
    "hyperbolic arcsine": "asinh",
    "hyperbolic arccosine": "acosh",
    "hyperbolic arctangent": "atanh",
    "inverse hyperbolic sine": "asinh",
    "inverse hyperbolic cosine": "acosh",
    "inverse hyperbolic tangent": "atanh",
}
```

### `_MULTI_WORD_NUMBERS`

Pre-computed mapping of multi-word number phrases to numeric values. Built at module import time by `_build_multi_word_numbers()`. Handles:
- Single-word × scale: `"one hundred"` → `100`, `"twenty thousand"` → `20000`
- Compound tens + scale: `"twenty one thousand"` → `21000`
- Compound hundreds: `"one hundred forty four"` → `144`
- Compound hundreds × scale: `"one hundred twenty one thousand"` → `121000`
- Standalone compound tens: `"twenty one"` → `21`
- Fraction words: `"one half"` → `0.5`, `"two thirds"` → `0.666...`, `"three quarters"` → `0.75`

Phrases are deduplicated by value, keeping the most natural form (fewer words, presence of scale word, non-tens first word).

## Core Public Functions

### `normalize_text(expression: str, operators: dict, patterns: Mapping[str, Pattern[str]]) -> str`

Normalizes an expression by removing filler words, converting NL tokens, and applying transformations. This is the first stage of the pipeline.

**Parameters:**
- `expression`: Raw input text
- `operators`: Normalization config dict (defaults to `NORMALIZE`)
- `patterns`: Compiled regex patterns (defaults to `PATTERNS`)

**Returns:** Normalized string ready for tokenization.

**Raises:**
- `ValueError` on empty input or input exceeding `MAX_INPUT_LENGTH`

**Key processing steps:**
1. Unicode math operators → ASCII (`×`→`*`, `÷`→`/`, `−`→`-`)
2. Multi-word function names replaced (e.g., `"square root"` → `"sqrt"`)
3. Compact function arguments split (e.g., `"sin30"` → `"sin 30"`)
4. Hyphens between number words converted to spaces (`"twenty-one"` → `"twenty one"`)
5. Implicit multiplication inserted (`"3(4+5)"` → `"3*(4+5)"`)
6. Multi-word number phrases replaced (`"one hundred"` → `"100"`)
7. `"and"` stripped as filler in NL number expressions
8. Short-form power phrases handled (`"3 to the 10"` → `"3**10"`)
9. Binary word patterns validated (`"5 not 6"` → raises error)
10. Lowercase temperature conversion phrases normalized
11. Digit × scale words evaluated (`"5 thousand"` → `"5000"`)
12. Single number words replaced with digits
13. Postfix unit power words normalized (`"m squared"` → `"m**2"`)
14. Spelled unit conversions normalized (`"30 kilometers per hour in miles per hour"` → `convert(...)`)
15. Long filler phrases stripped (before word-to-operator conversion)
16. Combined word replacement (constants, operators, function names) in single pass
17. `"point"` → decimal separator (`"5 point 3"` → `"5.3"`)
18. Decimal digit sequences merged (`"3.1 4"` → `"3.14"`)
19. Short filler phrases stripped
20. Compound unit conversions handled (`"60mi/h in m/s"` → `convert(60*mi/h,m/s)`)
21. Bare compound units handled (`"30 km/h"` → `"30*km/h"`)
22. Split compound unit pairs handled (`"5 km / h"` → `"(5*km)/(h)"`)
23. Percentages converted (`"50%"` → `0.5`)
24. Complex number suffix `i` → `j`
25. Angle mode (`"30 degrees"` → `30*pi/180`)
26. Spaced unit caret exponents normalized (`"5 m ^ 2"` → `"5*m**2"`)
27. `"N percent"` → `"N/100"` for word-number forms
28. Space-separated number sequences joined with `+`
29. Whitespace removal with implicit multiplication insertion
30. Postfix factorial (`"5!"` → `factorial(5)`)

### `normalize_expression(expression: str, operators: dict | None = None, patterns: Mapping[str, Pattern[str]] | None = None, skip_validation: bool = False) -> tuple[str, int]`

Normalizes an expression without evaluating it. This is the main entry point for the normalization pipeline.

**Parameters:**
- `expression`: The raw expression to normalize
- `operators`: Optional operators configuration dict; defaults to `NORMALIZE`
- `patterns`: Optional compiled regex patterns dict; defaults to `PATTERNS`
- `skip_validation`: If True, skip token validation (for custom evaluators)

**Returns:** `(normalized_string, exit_code)` where exit_code is 0 on success, non-zero on error.

**Processing steps:**
1. Call `normalize_text()` to normalize the text
2. Check normalized length against `MAX_NORMALIZED_LENGTH` (20000)
3. `split_at_operators()` — tokenize at operator boundaries
4. `convert_from_human_handler()` — convert number words to digits
5. `_combine_consecutive_numbers()` — combine adjacent numbers
6. `apply_math_functions()` — convert function names to calls
7. `_handle_unit_conversion_from_tokens()` — detect unit conversion patterns
8. `_preprocess_units()` — add multiplication before units, emit canonical unit names
9. `_add_unit_floor_mod_parens()` — wrap unit operands around floor div/mod
10. `validate_for_eval()` — validate all tokens (unless `skip_validation=True`)

### `run(expression: str, operators: dict, patterns: Mapping[str, Pattern[str]], output_format: str = "plain", show_expression: bool = True) -> tuple[Any, int]`

Full pipeline: normalize input, then evaluate. Prints result to stdout.

**Parameters:**
- `expression`: The raw expression
- `operators`: Normalization config dict
- `patterns`: Compiled regex patterns
- `output_format`: `"plain"` or `"json"` — controls output format
- `show_expression`: Accepted for compatibility; plain output remains result-only

**Returns:** `(result, exit_code)` where result is the evaluated value or `None` on error.

**JSON output format:**
```json
{"expression": "<normalized>", "result": "<display>"}
```

**Error handling:**
- `ValueError` → prints `"Error: <msg>: '<expr>'"` to stderr
- `ZeroDivisionError` → prints `"Can't divide by 0: '<expr>'"` to stderr
- `EvaluationError` → prints `"Evaluation error: <msg>"` to stderr
- Other exceptions → prints `"Error: <msg>"` to stderr (or full traceback with `--verbose`)

### `check_if_number(token: str) -> dict`

LRU-cached (maxsize=1024) function that checks if a token represents a number.

**Returns:**
```python
{
    "bool": True/False,        # whether token is a number
    "converted": <parsed>,     # parsed number (int/float/complex) or original string
    "type": <type>,            # Python type object (int, float, complex, or str)
}
```

**Handles:**
- Integers (`"42"`)
- Floats (`"3.14"`)
- Percentages (`"50%"` → `0.5`)
- Complex numbers (`"3i"`, `"-2j"`, `"+i"`)
- Hex (`0xFF`), binary (`0b101`), octal (`0o77`)
- Numbers with units (`"30m"`, `"100ft"`)
- Lowercase temperature units (`"5f"`, `"5c"`, `"5k"`)

**Cache behavior:** LRU cache is cleared during `_rebuild_config()` when custom words are added.

### `validate_for_eval(tokens: list, patterns: Mapping[str, Pattern[str]]) -> bool`

Validates that all tokens are either numbers, valid operations, units, known constants, or balanced parenthesized expressions.

**Raises:** `ValueError` with message `"Invalid token: <token>"` if any token is unrecognized.

**Accepts:**
- Numbers (via `check_if_number`)
- Valid operations (operators, function names, constant keys)
- Unit aliases (via `is_unit`)
- Known evaluator constants
- Balanced parenthesized expressions (skipped, evaluator validates)
- `<num>*<unit>` or `<num>/<unit>` patterns (e.g., `1*m`)
- Unary minus before function names (e.g., `-sqrt`)

## Internal Functions

### `error_message(original: str, exception: BaseException, verbose: bool = False) -> None`

Prints error messages based on exception type. Sanitizes non-printable characters from the original expression before display.

### `combine_number_parts(number_parts: list, patterns: Mapping[str, Pattern[str]], split_tokens: list) -> list`

Combines number parts into a mathematical expression. Rules:
- Consecutive small numbers (tens + ones) combine: `[20, 2]` → `["22"]`
- Hundreds chain with multiplication: `[3, 100, 20, 2]` → `["3", "*100", "+20", "+2"]`
- Handles leading negation from split_tokens

### `convert_numbers(number_info: list, patterns: Mapping[str, Pattern[str]]) -> str`

Converts a token containing number words to a numeric expression. Uses `combine_number_parts()` and validates with `validate_for_eval()`.

### `apply_math_functions(tokens: list, operators: dict, patterns: Mapping[str, Pattern[str]]) -> list`

Converts function names to math function calls. Rules:
- `sin40 + 2` → `sin(40) + 2` (no paren, only first number is arg)
- `sin(40+2)` → `sin(40+2)` (user's parens preserved)
- `sin of 40` → `sin(40)`
- `sqrt * 100` → `sqrt(100)` (skip `*` from "of" replacement)
- `5 factorial` → `factorial(5)` (implicit-mul swap)
- `5 sin` → `sin(5)` (leading number becomes arg)
- Multi-arg "of" chains: `mean*1+2+3` → `mean(1,2,3)`
- Detects unit/function collisions to avoid false function conversion

### `split_at_operators(expression: str, operators: dict, patterns: Mapping[str, Pattern[str]]) -> list`

Splits an expression string at operator boundaries. Handles:
- Standard operator splitting (`+`, `*`, `/`, `%`, etc.)
- Preserves unary minus (e.g., `"-5"` stays intact)
- Splits collapsed subtraction (`"4-5-3"` → `["4", "-", "5", "-", "3"]`)
- Handles trailing minus (`"5-"` in `"5-(3+2)"`)
- Handles double minus (`"5--3"` → `["5", "-", "-3"]`)
- Splits space-separated number sequences

### `convert_from_human_handler(tokens: list, operators: dict, patterns: Mapping[str, Pattern[str]], original: str) -> tuple[list, bool]`

Converts human-readable number words to numeric values. Replaces number words with `@<value>` markers, then calls `convert_numbers()`.

### `_combine_consecutive_numbers(tokens: list, operators: dict, patterns: Mapping[str, Pattern[str]]) -> list`

Combines consecutive number tokens separated by `+` into compound numbers. Uses `_finish_number_group()` and `combine_number_parts()`.

### `_join_number_parts(expression: str) -> str`

Joins space-separated number sequences with `+` operators. Also:
- Splits boundary-attached operators from tokens
- Pre-merges decimal point sequences (`"5" "." "3"` → `"5.3"`)
- Handles leading negation (`"-(100+1)"` not `"-100+1"`)
- Inserts implicit `*` between adjacent number and non-number tokens
- Handles `<<`/`>>` operator merging from space-separated tokens

### `_preprocess_units(expression: str) -> str`

Preprocesses expression to add multiplication before units. Emits canonical unit names (via `UNIT_ALIASES`). Handles:
- Number-unit pairs (`"5in"` → `"5*inch"`)
- Lowercase temperature units (`"5f"` → `"5*F"`)
- Python literal prefixes (`0x...`, `0b...`, `0o...`) passed through unchanged
- `*` before unit aliases (`"5*in"` → `"5*inch"`)
- Unit exponentiation wrapping (`"5m ** 2"` → `"(5*m)**2"`)
- Word boundary checking (prevents false matches on function names)

### `_add_same_unit_division_parens(expression: str) -> str`

Wraps the denominator in parentheses for unit-on-division-right. Fixes precedence: `"5*m/3*s"` → `"5*m/(3*s)"` instead of `"((5*m)/3)*s"`.

### `_add_unit_floor_mod_parens(expression: str) -> str`

Wraps unit operands around floor division and modulo. Fixes: `"7m/s//1s"` → `"(7*m/s)//(1*s)"`.

### `_handle_unit_conversion_from_tokens(tokens: list) -> list`

Detects unit conversion patterns from token lists:
- `[number+unit, 'in'/'to', target_unit]` → `convert(number*unit, target_unit)`
- `[number, 'in'/'to', target_unit]` → treats as multiply
- `[number, '*', unit, 'IN'/'TO', target_unit]` → `convert(number*unit, target_unit)`

Uses `are_units_compatible()` and `get_unit_category()` from `units.py` to validate conversion validity.

### `_should_split_number_minus(token: str) -> bool`

Checks if token matches `^\d+(?:-\d+)+$` — multiple subtraction operators between digit runs.

### `_should_split_double_minus(token: str) -> bool`

Checks if token matches `^\d+--\d+$`.

### `_should_split_trailing_minus(token: str) -> bool`

Checks if token matches `^\d+-$` — digit run with trailing minus.

### `_should_split_number_sequence(token: str) -> bool`

Checks if token is a space-separated number sequence that should be split.

### `_finish_number_group(group: list, patterns: Mapping[str, Pattern[str]]) -> list`

Converts a number group to final tokens. Uses `combine_number_parts()` for compound numbers (≥100 or tens), simple addition for others.

### `_peek_alpha_token_back(result_list: list[str]) -> str`

Returns the trailing alpha-only run from a character list. Used for implicit multiplication detection.

### `_peek_alnum_token_back(result_list: list[str]) -> str`

Returns the trailing identifier-like alnum run (including `_`) from a character list.

### `_binary_word_check(expr: str) -> bool`

Raises `ValueError` if expr contains `<value> not/in/to/as/into <value>` patterns (reserved for unary bitwise NOT or unit conversion).

### `_normalize_lowercase_temperature_conversion(expression: str) -> str`

Canonicalizes compact lowercase temperature conversion phrases like `"100 c in f"` → `"100 C in F"`.

### `_normalize_spelled_unit_conversions(expression: str) -> str`

Canonicalizes spaced word-form unit conversions before operator replacement. E.g., `"30 kilometers per hour in miles per hour"` → `convert(30*km/h,m/h)`.

### `_normalize_postfix_unit_power_words(expression: str) -> str`

Normalizes postfix unit power words: `"m squared"` → `"m**2"`, `"cm cubed"` → `"cm**3"`.

### `_normalize_spaced_unit_caret_exponents(expression: str) -> str`

Normalizes unit exponent shorthand while preserving `^` as XOR. Handles `"5 m ^ 2"` → `"5*m**2"` and `"/ m ^ 2"` → `"/m**2"`.

### `_rewrite_calculator_caret(expression: str) -> str`

Rewrites `^` to `**` (exponentiation) for user-facing calculator syntax. Called during normalization so that `evaluate_raw()` and CLI treat `^` as power, while direct `evaluate()` calls keep `^` as bitwise XOR (Python AST semantics). Word forms `xor` and `bitxor` are not affected by this rewrite — they remain mapped to the `^` operator token and are handled as bitwise XOR by the evaluator.

### `_canonical_power_unit(unit: str, exponent: str) -> str`

Returns the canonical form of a unit raised to an exponent, looking up `UNIT_ALIASES` for shorthand forms.

### `_build_multi_word_numbers() -> dict[str, str]`

Builds the `_MULTI_WORD_NUMBERS` mapping at module import time. Generates all combinations of ones/tens/teens × scale words, including compound hundreds with larger scales.

### `_get_units_by_category() -> dict[str, list[str]]`

Returns units organized by category from `UNIT_CATEGORIES`.

### `_rebuild_config() -> None`

Thread-safe rebuild of `NORMALIZE` and `PATTERNS`. Acquires `_REBUILD_LOCK` (RLock) and clears the `check_if_number` LRU cache.

### `_build_config() -> tuple[dict, dict]`

Builds normalization configuration. Intentionally recompiles all regex patterns on every call for thread safety during config rebuilds. The result is cached at module level.

**Returns:** `(normalize_config, compiled_patterns)`

## Processing Pipeline

```
Input: "what's five plus three hundred twenty two?"
    ↓
1. Strip phrases: "five plus three hundred twenty two"
    ↓
2. Multi-word numbers: "five plus 322" (via _MULTI_WORD_NUMBERS)
    ↓
3. Single word replacement: "5 plus 322"
    ↓
4. Word-to-operator: "5+322"
    ↓
5. Tokenize: ["5", "+", "322"]
    ↓
6. Number word handling (already digits at this point)
    ↓
7. Preprocess units (no units here)
    ↓
8. Join: "5+322"
    ↓
Output: 327
```

More complex example with units:
```
Input: "30m + 100ft"
    ↓
1. No filler phrases to strip
    ↓
2. No multi-word numbers
    ↓
3. No word replacement needed
    ↓
4. Tokenize: ["30m", "+", "100ft"]
    ↓
5. Number word handling (already digits)
    ↓
6. Unit conversion: "30m" → "30*m", "100ft" → "100*foot"
    ↓
7. Preprocess: "30*m+100*foot"
    ↓
8. Join: "30*m+100*foot"
    ↓
Output: UnitValue(60.48, "m")
```

## Regex Patterns (PATTERNS)

| Pattern | Purpose |
|---------|---------|
| `space` | Multiple whitespace |
| `point` | Decimal point |
| `negative` | Negative sign |
| `thousands_separator` | Comma (1,000,000) |
| `parenthesis` | `(` and `)` |
| `operators` | Valid operator symbols |
| `stripped_chars` | Phrases to remove |
| `int` | Integer pattern |
| `float` | Float pattern (accepts trailing decimal like `"5."`) |
| `valid_operations` | Valid operation, function, and constant names |

## Configuration Building

### `_build_config() -> tuple[dict, dict]`

Builds the `NORMALIZE` and `PATTERNS` structures. Called once at module load time and cached as module-level globals. Rebuilt by `_rebuild_config()` when custom words are added at runtime.

**Sort order:** All word mappings are sorted by length descending for correct matching (e.g., `"hundred"` before `"one"`).

**normalize_config contents:**
- `symbols`: `["(", ")", "+", "-", "*", "/", ...]`
- `convert`: `OPERATOR_CONVERSIONS` dict
- `word_to_operator`: Flattened word → operator mapping
- `word_to_number`: Sorted word → number mapping
- `word_to_constant`: Sorted word → constant key mapping
- `word_to_all`: Combined constants + numbers + operators, sorted by length
- `numbers`: NUMBER_WORDS sorted by key descending
- `functions`: `FUNCTION_MAPPINGS` dict

## Unit Handling

Units are parsed as part of the normalization process:

1. Pre-computed sorted units list (`_UNITS_BY_LENGTH`) avoids re-sorting each call
2. Prefix set (`_UNIT_PREFIXES`) provides O(1) lookup for common unit starts
3. `_preprocess_units()` emits canonical unit names and inserts multiplication
4. `_add_same_unit_division_parens()` fixes operator precedence for unit division
5. `_add_unit_floor_mod_parens()` fixes precedence for floor div/mod with units
6. Compound unit expressions (`km/h`, `mi/h`, `m/s`, etc.) handled before tokenization
7. The evaluator handles unit arithmetic and conversion

See [units.md](units.md) for unit conversion details.

## Number Handling

### Multi-word Number System

- `_MULTI_WORD_NUMBERS` maps full phrases to numbers (built at import time)
- `_MULTI_WORD_PATTERN` is a single compiled regex for fast matching (~40,000x faster than per-entry `re.sub`)
- `_MULTI_WORD_PATTERN_LOOKUP` provides lowercase key → value lookup
- Phrases are deduplicated by value, keeping the most natural form

### Digit Scale Words

`_DIGIT_SCALES` maps scale words (`"hundred"`, `"thousand"`, etc.) to their values. Used to evaluate `"N thousand"` → the product.

### Number Combination

`combine_number_parts()` handles the complex logic of combining number sequences:
- `[20, 2]` → `["22"]` (tens + ones)
- `[3, 100, 20, 2]` → `["3", "*100", "+20", "+2"]` (hundreds with multiplication)

## Implicit Multiplication

Several module-level sets control implicit multiplication behavior:

### `_IMPLICIT_MUL_FUNCS`

Set of function names that participate in implicit multiplication with numbers. The whitespace-removal loop inserts `*` between a digit/`)` and these names (e.g., `"5 sin"` → `"5*sin"`). Also used by `apply_math_functions()` for `<num> <func>` → `<func>(<num>)` swap.

### `_IMPLICIT_MUL_CONSTANTS`

Set of constant names that participate in implicit multiplication: `{"pi", "tau"}`. Single-letter `"e"` is excluded because it conflicts with scientific notation (`"1e3"`).

### `_SINGLE_ARG_IMPLICIT_MUL`

Subset of `_IMPLICIT_MUL_FUNCS` that take exactly one argument. Used by `apply_math_functions()` to detect `<num> <func>` → `<func>(<num>)` swap.

### `_MULTI_ARG_OF_FUNCS`

Subset of `_IMPLICIT_MUL_FUNCS` that take multiple arguments. Enables `"of"` chains like `"mean of 1+2+3"` → `"mean(1,2,3)"`. Single-arg functions keep `+`/`-` as real operators (e.g., `"sqrt of 144 + 5"` → `"sqrt(144) + 5"`).

## Thread Safety

- `_REBUILD_LOCK` (`threading.RLock`) protects `NORMALIZE` and `PATTERNS` during rebuilds
- `_rebuild_config()` acquires the lock, rebuilds, and clears the `check_if_number` LRU cache
- There is a brief window where concurrent reads may return stale cached values between the config swap and cache clear; this is acceptable because the stale value is valid for the superseded configuration

## CLI and REPL

### `main() -> int`

Main entry point for CLI. Handles:
- Argument parsing (expression, `--help`, `--usage`, `--version`, `--quiet`, `--verbose`, `--json`, `-e`, `-i`, `--mcp`, `--mcp-profile`, `--mcp-schema-detail`)
- Config loading via `maybe_load_cli_config()`
- Signal handling (SIGPIPE, SIGTERM)
- Shell glob expansion detection
- Text command dispatch via `_cli_text_command()`
- Math evaluation via `run()`

### `maybe_load_cli_config() -> None`

Loads user config for CLI usage. Called once during CLI startup. Disabled by `EGGCALC_NO_CONFIG=1`. Intentionally NOT called from library API functions.

### `_run_repl(show_expression: bool = True) -> int`

Interactive REPL mode. Supports:
- `help` — show help
- `history` — show calculation history
- `clear` — clear history
- `quit`/`exit` — exit
- readline history saved to `~/.eggcalc_history`

### `_cli_text_command(expression: str, json_output: bool = False, argv: list[str] | None = None) -> int`

Handles text commands before math evaluation. Returns 0 if command was handled, 1 if expression should continue to math eval.

**Commands:** `inspect`, `count`, `regex`, `replace-check`, `lines`, `patch-check`, `shell-split`, `md-structure`, `dotenv-check`

All text commands support `--json` for machine-readable output.

### `print_help() -> None`

Prints available operators, functions, constants, and units (organized by category).

## Security Notes

- No `eval()` usage — uses AST parsing in evaluator
- Input length limits enforced (`MAX_INPUT_LENGTH = 10000`)
- Normalized expression length limited (`MAX_NORMALIZED_LENGTH = 20000`)
- Nesting depth limited (`MAX_NESTING_DEPTH = 100`)
- Invalid tokens raise `ValueError`
- Binary word patterns validated to prevent ambiguous expressions
- Input sanitized for terminal display in error messages

## Module Dependencies

```
normalize.py
    ├── evaluator (EvaluationError, evaluate)
    ├── units (UNIT_ALIASES, UNIT_CATEGORIES, UnitValue, is_unit, are_units_compatible, get_unit_category)
    └── exact (inspect_text, count_chars, regex_test, text_replace_check,
               line_range_extract, markdown_structure,
               shell_split, dotenv_validate, patch_apply_check)
```
