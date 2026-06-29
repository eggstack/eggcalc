"""
Natural language to math expression normalizer.

Converts mathematical expressions written in natural language
(e.g., "sixteen plus five hundred twenty two") into executable
mathematical expressions.

Usage:
    python -m eggcalc "five plus two"
    python -m eggcalc "30m + 100ft"
    python -m eggcalc --help
"""

from __future__ import annotations

import argparse
import re
import sys
import traceback
from collections.abc import Mapping
from functools import lru_cache
from re import Pattern
from typing import Any

from .evaluator import EvaluationError, evaluate
from .exact import (
    count_chars,
    dotenv_validate,
    inspect_text,
    line_range_extract,
    markdown_structure,
    patch_apply_check,
    regex_test,
    shell_split,
    text_replace_check,
)
from .units import UNIT_ALIASES, UNIT_CATEGORIES, UnitValue, is_unit

__all__ = [
    "evaluate",
    "EvaluationError",
    "UnitValue",
    "run",
    "normalize",
    "normalize_expression",
    "main",
    "print_help",
    "NORMALIZE",
    "PATTERNS",
    "MAX_INPUT_LENGTH",
    "MAX_NESTING_DEPTH",
]

MAX_INPUT_LENGTH = 10000
MAX_NORMALIZED_LENGTH = 20000
MAX_NESTING_DEPTH = 100

# Decimal Python numeric literal subset used after unit preprocessing. It
# intentionally excludes non-decimal prefixes because 0x/0b/0o literals are
# passed through before suffix-unit handling.
_DECIMAL_NUMBER_TOKEN_RE = (
    r"(?:\d[\d_]*(?:\.\d[\d_]*)?|\.\d[\d_]*|\d[\d_]*\.)(?:[eE][+-]?\d[\d_]*)?"
)

# Pre-computed sorted units list for performance (avoid re-sorting each call)
_UNITS_BY_LENGTH: list[str] = sorted(UNIT_ALIASES.keys(), key=len, reverse=True)

# Regex alternation for matching any known unit name (for "in"/"into" disambiguation)
_UNIT_NAMES_ALTERNATION: str = "|".join(
    re.escape(u) for u in sorted(UNIT_ALIASES.keys(), key=len, reverse=True)
)

# Lowercase temperature abbreviations that should map to canonical uppercase forms
_LOWERCASE_TEMP_UNITS: dict[str, str] = {"f": "F", "c": "C", "k": "K"}

# Common unit prefixes for faster lookup (most frequently used units first)
_COMMON_UNITS: list[str] = [
    "m",
    "km",
    "cm",
    "mm",
    "s",
    "ms",
    "us",
    "ns",
    "min",
    "h",
    "d",
    "g",
    "kg",
    "mg",
    "lb",
    "oz",
    "L",
    "mL",
    "gal",
    "J",
    "kJ",
    "W",
    "kW",
    "Pa",
    "atm",
    "N",
    "V",
    "A",
    "Hz",
    "B",
    "KB",
    "MB",
    "GB",
    "in",
    "ft",
    "yd",
    "mi",
    "yr",
    "K",
    "C",
    "F",
]

# Build a prefix set for O(1) lookup of common unit starts
_UNIT_PREFIXES: set[str] = set()
for unit in _COMMON_UNITS:
    for i in range(1, len(unit) + 1):
        _UNIT_PREFIXES.add(unit[:i])


# Operator conversions: operator -> list of word representations
OPERATOR_CONVERSIONS: dict[str, list[str]] = {
    "+": ["plus", "positive"],
    "-": ["minus", "negative"],
    "*": ["times", "multiplied by", "of"],  # "of" for "30% of 200"
    "/": ["divided by", "over", "per", "divide"],
    "**": ["raised to", "raised to the power of", "to the power of"],
    # "point" handled separately to avoid ".5" issues at expression start
    ",": [],
    "&": ["bitand", "bit and"],
    "|": ["OR", "or", "bitor", "bit or"],
    "^": ["XOR", "xor", "bitxor", "bit xor"],
    "<<": ["left shift", "shift left", "lshift"],
    ">>": ["right shift", "shift right", "rshift"],
    "~": ["NOT", "not", "bitnot", "bit not"],
    "%": ["mod", "modulo", "remainder"],
    # Unit conversion words - these get split out as tokens
    "IN": ["in", "into"],
    "TO": ["to", "as"],
}

# Function name mappings (for function name normalization)
# Maps common names/aliases to canonical function names
FUNCTION_MAPPINGS: dict[str, str] = {
    "square root": "sqrt",
    "sqrt": "sqrt",
    "sine": "sin",
    "sin": "sin",
    "cosine": "cos",
    "cos": "cos",
    "tangent": "tan",
    "tan": "tan",
    "arcsine": "asin",
    "asin": "asin",
    "arccosine": "acos",
    "arccos": "acos",
    "acos": "acos",
    "arctangent": "atan",
    "arctan": "atan",
    "atan": "atan",
    "sinh": "sinh",
    "hyperbolic sine": "sinh",
    "cosh": "cosh",
    "hyperbolic cosine": "cosh",
    "tanh": "tanh",
    "hyperbolic tangent": "tanh",
    "arcsinh": "asinh",
    "asinh": "asinh",
    "inverse hyperbolic sine": "asinh",
    "arccosh": "acosh",
    "acosh": "acosh",
    "inverse hyperbolic cosine": "acosh",
    "arctanh": "atanh",
    "atanh": "atanh",
    "inverse hyperbolic tangent": "atanh",
    "absolute": "abs",
    "abs": "abs",
    "magnitude": "abs",
    "ln": "log",
    "log": "log",
    "log10": "log10",
    "log2": "log2",
    "log1p": "log1p",
    "exp": "exp",
    "expm1": "expm1",
    "temp": "temp",
    "bin": "bin",
    "hex": "hex",
    "oct": "oct",
    "mean": "mean",
    "average": "mean",
    "median": "median",
    "mode": "mode",
    "std": "std",
    "stdev": "std",
    "std_sample": "std_sample",
    "stds": "std_sample",
    "variance": "variance",
    "var": "var",
    "var_sample": "var_sample",
    "variance_sample": "var_sample",
    "vars": "vars",
    "sum": "sum",
    "max": "max",
    "min": "min",
    "gcd": "gcd",
    "lcm": "lcm",
    "perm": "perm",
    "comb": "comb",
    "nPr": "nPr",
    "nCr": "nCr",
    "factorial": "factorial",
    "fact": "factorial",
    "real": "real",
    "imag": "imag",
    "conj": "conj",
    "conjugate": "conj",
    "phase": "phase",
    "polar": "polar",
    "rect": "rect",
    "bitand": "bitand",
    "bitor": "bitor",
    "bitxor": "bitxor",
    "bitnot": "bitnot",
    "bitlshift": "bitlshift",
    "bitrshift": "bitrshift",
    "isprime": "isprime",
    "is_prime": "isprime",
    "primefactors": "primefactors",
    "prime_factors": "primefactors",
    "nextprime": "nextprime",
    "next_prime": "nextprime",
    "prevprime": "prevprime",
    "prev_prime": "prevprime",
    "random": "random",
    "randint": "randint",
    "randn": "randn",
    "randrange": "randrange",
    "gauss": "gauss",
    "seed": "seed",
    "percentof": "percentof",
    "percent_of": "percentof",
    "aspercent": "aspercent",
    "as_percent": "aspercent",
    "clamp": "clamp",
    "hypot": "hypot",
    "round": "round",
    "sign": "sign",
    "cbrt": "cbrt",
    "cube root": "cbrt",
    "ceil": "ceil",
    "ceiling": "ceil",
    "floor": "floor",
    "trunc": "trunc",
    "degrees": "degrees",
    "radians": "radians",
    "atan2": "atan2",
    "pow": "pow",
    "store": "store",
    "recall": "recall",
    "Mplus": "Mplus",
    "Mminus": "Mminus",
    "MC": "MC",
    "MR": "MR",
    "M": "MR",
    "setvar": "setvar",
    "getvar": "getvar",
    "delvar": "delvar",
    "listvars": "listvars",
    "clearvars": "clearvars",
    "convert": "convert",
    "uniform": "uniform",
}

# Number words
NUMBER_WORDS: dict[str, list[str]] = {
    "0": ["zero"],
    "1": ["one"],
    "2": ["two"],
    "3": ["three"],
    "4": ["four"],
    "5": ["five"],
    "6": ["six"],
    "7": ["seven"],
    "8": ["eight"],
    "9": ["nine"],
    "10": ["ten"],
    "11": ["eleven"],
    "12": ["twelve"],
    "13": ["thirteen"],
    "14": ["fourteen"],
    "15": ["fifteen"],
    "16": ["sixteen"],
    "17": ["seventeen"],
    "18": ["eighteen"],
    "19": ["nineteen"],
    "20": ["twenty"],
    "30": ["thirty"],
    "40": ["forty"],
    "50": ["fifty"],
    "60": ["sixty"],
    "70": ["seventy"],
    "80": ["eighty"],
    "90": ["ninety"],
    "100": ["hundred"],
    "1000": ["thousand"],
    "1000000": ["million"],
    "1000000000": ["billion"],
    "1000000000000": ["trillion"],
    "1000000000000000": ["quadrillion"],
    "1000000000000000000": ["quintillion"],
    "0.5": ["half"],
    "0.25": ["quarter"],
    "0.001": ["thousandth"],
    "0.000001": ["millionth"],
    "0.000000001": ["billionth"],
}

# Phrases to strip from input
STRIPPED_PHRASES: list[str] = [
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

# Physical constants word mappings
CONSTANT_WORDS: dict[str, list[str]] = {
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


def _build_config() -> tuple[dict, dict]:
    """Build normalization configuration.

    Recompiles all regex patterns on every call intentionally. This ensures
    thread safety during config rebuilds (via _rebuild_config) because callers
    always get freshly compiled patterns rather than sharing potentially stale
    references. The resulting config is cached at module level via
    ``NORMALIZE, PATTERNS = _build_config()`` and only rebuilt when new custom
    words are added at runtime.
    """
    # Sort numbers by key descending for matching
    sorted_numbers = {k: NUMBER_WORDS[k] for k in sorted(NUMBER_WORDS.keys(), reverse=True)}

    # Build symbols list
    symbols = ["(", ")"] + list(OPERATOR_CONVERSIONS.keys())

    # Build word to operator mapping
    word_to_operator: dict[str, str] = {}
    for operator, words in OPERATOR_CONVERSIONS.items():
        for word in words:
            word_to_operator[word] = operator

    # Build word to number mapping (sorted by length for correct replacement)
    word_to_number: dict[str, str] = {}
    for num_val, words in NUMBER_WORDS.items():
        for word in words:
            word_to_number[word] = num_val
    sorted_word_to_number = dict(
        sorted(word_to_number.items(), key=lambda x: len(x[0]), reverse=True)
    )

    # Build word to constant mapping
    word_to_constant: dict[str, str] = {}
    for const_key, words in CONSTANT_WORDS.items():
        for word in words:
            word_to_constant[word] = const_key
    sorted_word_to_constant = dict(
        sorted(word_to_constant.items(), key=lambda x: len(x[0]), reverse=True)
    )

    # Build combined word replacement regex for performance (constants + operators)
    all_words = {}
    all_words.update(sorted_word_to_constant)
    all_words.update(sorted_word_to_number)
    all_words.update(word_to_operator)

    # Sort by length descending for correct matching
    sorted_all_words = dict(sorted(all_words.items(), key=lambda x: len(x[0]), reverse=True))

    # Build normalize config
    normalize_config = {
        "symbols": symbols,
        "convert": OPERATOR_CONVERSIONS,
        "word_to_operator": word_to_operator,
        "word_to_number": sorted_word_to_number,
        "word_to_constant": sorted_word_to_constant,
        "word_to_all": sorted_all_words,
        "numbers": sorted_numbers,
        "functions": FUNCTION_MAPPINGS,
    }

    # Compile regex patterns
    _wb = r"\b"
    compiled_patterns: dict[str, re.Pattern[str]] = {
        "space": re.compile(r"\s+"),
        "point": re.compile(r"\."),
        "negative": re.compile(r"\-"),
        "thousands_separator": re.compile(r","),
        "parenthesis": re.compile(r"\(|\)"),
        "operators": re.compile(f"^({'|'.join([re.escape(s) for s in symbols])}){{1}}$"),
        # Handle stripped_chars: literals get escaped, but regex patterns like \bof\b are preserved
        "stripped_chars": re.compile(
            f"({'|'.join([re.escape(p) if not (p.startswith(_wb) or _wb in p) else p for p in sorted(STRIPPED_PHRASES, key=len, reverse=True)])})"
        ),
        "int": re.compile(r"^[-+]?[0-9]\d*$"),
        # Float regex accepts a trailing decimal point ("5." -> 5.0) so
        # users can write Python-style shorthand. Both ".5" and "5." are
        # accepted; "5." is normalized to "5.0" before evaluation.
        "float": re.compile(r"^[-+]?(?:[0-9]\d*(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?$"),
        "valid_operations": re.compile(
            f"^({'|'.join([re.escape(s) for s in symbols] + [re.escape(f) for f in FUNCTION_MAPPINGS.values()] + [re.escape(c) for c in CONSTANT_WORDS.keys()])}){{1}}$"
        ),
    }

    return normalize_config, compiled_patterns


import threading as _threading

# Module-level config (computed once)
NORMALIZE, PATTERNS = _build_config()

# Lock protecting config rebuilds. Acquired by _rebuild_config() so that
# concurrent readers see a consistent (NORMALIZE, PATTERNS) pair. Also
# acquired by consumers (e.g., check_if_number via NORMALIZE/PATTERNS
# access) when atomicity is required.
_REBUILD_LOCK: _threading.RLock = _threading.RLock()


def _rebuild_config() -> None:
    """Rebuild NORMALIZE and PATTERNS after adding custom words.

    Thread-safe: holds _REBUILD_LOCK so that consumers see a consistent
    (NORMALIZE, PATTERNS) pair. Also clears the check_if_number LRU cache
    so cached results from before the rebuild don't leak into the new config.
    """
    global NORMALIZE, PATTERNS
    with _REBUILD_LOCK:
        new_normalize, new_patterns = _build_config()
        NORMALIZE = new_normalize
        PATTERNS = new_patterns
        check_if_number.cache_clear()


@lru_cache(maxsize=1024)
def check_if_number(token: str) -> dict:
    """Check if a token represents a number.

    The LRU cache is cleared during _rebuild_config() so that cached results
    from before a config rebuild don't leak into the new configuration. There
    is a brief window where concurrent reads may return stale cached values
    between the config swap and the cache clear; this is acceptable because
    the cache is per-process and any stale value would still be valid for the
    (now-superseded) old configuration.

    Returns a dict with:
        bool: whether the token is a number
        converted: the parsed number or original string
        type: the original input type
    """
    patterns = PATTERNS
    if len(token) == 0:
        return {"bool": False, "converted": token, "type": type(token)}

    # Remove thousands separator
    cleaned = patterns["thousands_separator"].sub("", token)

    # Check for percentage (e.g., "50%")
    if cleaned.endswith("%"):
        num_part = cleaned[:-1]
        try:
            val = float(num_part) / 100
            return {"bool": True, "converted": val, "type": type(token)}
        except ValueError:
            pass

    # Check for complex number suffix (e.g., "3i", "4j")
    if cleaned.endswith(("i", "j")) and len(cleaned) > 1:
        num_part = cleaned[:-1]
        if num_part in ("+", "-"):
            # Just "+i" or "-i"
            return {
                "bool": True,
                "converted": complex(0, 1 if num_part == "+" else -1),
                "type": type(token),
            }
        try:
            val = float(num_part)
            return {"bool": True, "converted": complex(0, val), "type": type(token)}
        except ValueError:
            pass

    # Check for hex prefix (0x)
    if cleaned.lower().startswith("0x"):
        try:
            val = int(cleaned, 16)
            return {"bool": True, "converted": val, "type": int}
        except ValueError:
            pass

    # Check for binary prefix (0b)
    if cleaned.lower().startswith("0b"):
        try:
            val = int(cleaned, 2)
            return {"bool": True, "converted": val, "type": int}
        except ValueError:
            pass

    # Check for octal prefix (0o)
    if cleaned.lower().startswith("0o"):
        try:
            val = int(cleaned, 8)
            return {"bool": True, "converted": val, "type": int}
        except ValueError:
            pass

    # Check if it's a plain number
    if patterns["int"].match(cleaned):
        return {"bool": True, "converted": int(cleaned), "type": type(token)}
    if patterns["float"].match(cleaned):
        return {"bool": True, "converted": float(cleaned), "type": type(token)}

    # Check if it's a number with unit (use pre-computed sorted list)
    for unit in _UNITS_BY_LENGTH:
        if cleaned.endswith(unit):
            num_part = cleaned[: -len(unit)]
            if num_part:
                try:
                    val = float(num_part)
                    return {"bool": True, "converted": val, "type": type(token)}
                except ValueError:
                    pass

    # Check lowercase temperature units (e.g., "5f", "5c", "5k") that are not
    # in UNIT_ALIASES but are handled by _preprocess_units via _LOWERCASE_TEMP_UNITS.
    for temp_unit in _LOWERCASE_TEMP_UNITS:
        if cleaned.endswith(temp_unit) and len(cleaned) > len(temp_unit):
            num_part = cleaned[: -len(temp_unit)]
            if num_part:
                try:
                    val = float(num_part)
                    return {"bool": True, "converted": val, "type": type(token)}
                except ValueError:
                    pass

    return {"bool": False, "converted": token, "type": type(token)}


def validate_for_eval(tokens: list, patterns: Mapping[str, Pattern[str]]) -> bool:
    """Validate that all tokens are either numbers, valid operations, units, or known constants."""
    from .evaluator import _default_evaluator

    known_constants = set(_default_evaluator.CONSTANTS.keys())

    for token in tokens:
        # Skip tokens containing parentheses — these are function calls or
        # sub-expressions handled by the AST evaluator (e.g., "convert(1*m,ft)").
        # Validate only the content between balanced outer parentheses when present.
        check_token = token
        if "(" in check_token or ")" in check_token:
            # Allow tokens that are balanced parenthesized expressions like "(5+3)"
            # or function calls like "convert(...)" — the evaluator validates them.
            # But still reject tokens with unbalanced parens or junk around them.
            depth = 0
            balanced = True
            for ch in check_token:
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                if depth < 0:
                    balanced = False
                    break
            if balanced and depth == 0:
                continue  # Balanced parens — skip validation, evaluator handles it
            # Unbalanced — fall through to validate the raw token
        if not check_if_number(check_token)["bool"]:
            if not patterns["valid_operations"].match(check_token):
                if not is_unit(check_token):
                    if check_token not in known_constants:
                        # Accept '<num>*<unit>' or '<num>/<unit>' patterns
                        # (e.g., '1*m' from "1 in m" unit conversion)
                        # Pattern: number (int/float/scientific) followed by
                        # optional operator-unit pairs like *m, /s, *m/s
                        if re.match(
                            r"^[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?(?:[*/][a-zA-Z]+(?:/[a-zA-Z]+)*)*$",
                            check_token,
                        ):
                            continue
                        # Allow unary minus before function names (e.g., "-sqrt")
                        if check_token.startswith("-") and check_token[1:] in _IMPLICIT_MUL_FUNCS:
                            continue
                        raise ValueError(f"Invalid token: {check_token}")
    return True


def combine_number_parts(
    number_parts: list, patterns: Mapping[str, Pattern[str]], split_tokens: list
) -> list:
    """Combine number parts into a single mathematical expression.

    Rules:
    - Consecutive small numbers (tens + ones) combine: [20, 2] -> [22], [30, 5] -> [35]
    - Hundreds chain with multiplication: [3, 100, 20, 2] -> [3, '*', 100, '+', 20, '+', 2]
    """
    if not number_parts:
        return []

    result = []
    skip_next = False

    for i, part in enumerate(number_parts):
        if skip_next:
            skip_next = False
            continue

        if i == len(number_parts) - 1:
            result.append(str(part))
            continue

        next_part = number_parts[i + 1]

        if i == 0:
            if part < 10 and next_part == 10:
                result.append(str(part + next_part))
                skip_next = True
            elif part == 10 and next_part < 10:
                result.append(str(part + next_part))
                skip_next = True
            elif _is_tens(part) and next_part < 10:
                result.append(str(part + next_part))
                skip_next = True
            elif part < 10 and next_part >= 100:
                result.append(f"{part}*{next_part}")
                skip_next = True
            elif part != 10:
                result.append(str(part))
            else:
                result.append(str(part))
        else:
            if part == 10 and number_parts[i - 1] < 10:
                pass
            elif _is_tens(part) and next_part < 10:
                result.append(f"+{part + next_part}")
                skip_next = True
            elif part < 10:
                result.append(f"+{part}")
            elif number_parts[i - 1] < 10 and part < 100:
                result.append(f"+{part}")
            elif number_parts[i - 1] < 100:
                result.append(f"*{part}")
            else:
                result.append(f"+{part}")

    if split_tokens and patterns["negative"].match(split_tokens[0]):
        result.insert(0, "-")

    return result


def _is_tens(value: int) -> bool:
    """Check if value is a tens (20, 30, 40, etc.)"""
    return 20 <= value < 100 and value % 10 == 0


def convert_numbers(number_info: list, patterns: Mapping[str, Pattern[str]]) -> str:
    """Convert a token that may contain number words to a numeric expression."""
    if number_info[1]["bool"]:
        return str(number_info[0])

    split_tokens = number_info[0].split("@")
    number_parts = []

    for token in split_tokens:
        check_result = check_if_number(token)
        if check_result["bool"]:
            number_parts.append(check_result["converted"])

    combined = combine_number_parts(number_parts, patterns, split_tokens)

    if validate_for_eval(combined, patterns):
        joined = "".join(combined)
        if joined:
            try:
                result = evaluate(joined)
                if isinstance(result, UnitValue):
                    return str(result.value)
                return str(result)
            except EvaluationError:
                return str(number_info[0])
        return str(number_info[0])

    return str(number_info[0])


def apply_math_functions(
    tokens: list, operators: dict, patterns: Mapping[str, Pattern[str]]
) -> list:
    """Convert function names to math function calls.

    Rules:
    - sin40 + 2 -> math.sin(40) + 2 (no paren means only first number is args)
    - sin(40+2) -> math.sin(40+2) (user's parens preserved)
    - sin of 40 -> math.sin(40)
    - sqrt * 100 -> math.sqrt(100) (skip * from "of" replacement)
    - 5 factorial -> factorial(5)  (implicit-mul swap: leading number becomes the arg)
    - 5 sin -> sin(5)
    """

    def _is_pure_num_token(tok: str) -> bool:
        stripped = tok.strip("+-")
        return stripped.isdigit() and not any(c.isalpha() for c in stripped)

    def _is_unit_suffix_context(output_tokens: list, input_tokens: list, index: int) -> bool:
        """Return True when a function/unit collision is acting as a unit suffix."""
        token = input_tokens[index]
        if token not in UNIT_ALIASES and token.lower() not in UNIT_ALIASES:
            return False
        if index + 1 < len(input_tokens) and input_tokens[index + 1] == "(":
            return False
        if len(output_tokens) < 2 or output_tokens[-1] != "*":
            return False
        prev = output_tokens[-2]
        return (
            prev == ")"
            or check_if_number(prev)["bool"]
            or prev in UNIT_ALIASES
            or prev.lower() in UNIT_ALIASES
        )

    output_tokens: list[str] = []
    i = 0
    while i < len(tokens):
        token = tokens[i]

        if token in operators["functions"]:
            func_name = operators["functions"][token]

            if _is_unit_suffix_context(output_tokens, tokens, i):
                output_tokens.append(token)
                i += 1
                continue

            # Check if this token is actually a unit being used in a conversion
            # context (e.g., "min" in "10 min in seconds"). Skip function conversion
            # if the next non-* token is "IN" or "TO" followed by a known unit name.
            _is_unit_conversion = False
            if token.lower() in UNIT_ALIASES or token in UNIT_ALIASES:
                scan_idx = i + 1
                while scan_idx < len(tokens) and tokens[scan_idx] == "*":
                    scan_idx += 1
                if scan_idx < len(tokens) and tokens[scan_idx] in ("IN", "TO"):
                    after_in = scan_idx + 1
                    if after_in < len(tokens):
                        candidate = tokens[after_in]
                        if candidate in UNIT_ALIASES or candidate.lower() in UNIT_ALIASES:
                            _is_unit_conversion = True

            if _is_unit_conversion:
                output_tokens.append(token)
                i += 1
                continue
            # Implicit-mul swap: <num>[*] <single-arg-func> -> <func>(<num>)
            # Only swap if there is no value (number) immediately after the function
            # name in the token stream; otherwise the trailing value is the argument
            # (e.g., "2 sqrt 9" -> "2*sqrt(9)", but "5 factorial" -> "factorial(5)").
            if token in _SINGLE_ARG_IMPLICIT_MUL and output_tokens:
                # Check whether the next non-* token in the input is a value
                next_idx = i + 1
                while next_idx < len(tokens) and tokens[next_idx] == "*":
                    next_idx += 1
                has_trailing_value = (
                    next_idx < len(tokens)
                    and tokens[next_idx] not in operators["functions"]
                    and tokens[next_idx] != ")"
                    and (
                        tokens[next_idx] == "(" or not patterns["operators"].match(tokens[next_idx])
                    )
                )
                if not has_trailing_value and output_tokens:
                    if output_tokens[-1] == "*":
                        output_tokens.pop()
                    if output_tokens and _is_pure_num_token(output_tokens[-1]):
                        num = output_tokens.pop()
                        output_tokens.append(func_name)
                        output_tokens.append("(")
                        output_tokens.append(num)
                        output_tokens.append(")")
                        i += 1
                        continue

            output_tokens.append(func_name)
            next_token = tokens[i + 1] if i + 1 < len(tokens) else None

            if next_token is not None and next_token == "(":
                pass
            else:
                output_tokens.append("(")

                # Skip * that came from "of" replacement (e.g., "sqrt * 100")
                skipped_of = False
                if next_token == "*" and i + 2 < len(tokens):
                    skipped_of = True
                    i += 1
                    next_token = tokens[i + 1] if i + 1 < len(tokens) else None

                while i + 1 < len(tokens):
                    next_token = tokens[i + 1]
                    is_operator = patterns["operators"].match(next_token) is not None

                    if next_token == ")":
                        break

                    # Stop at function names (they'll be processed separately)
                    if next_token in operators["functions"]:
                        break

                    if is_operator:
                        if next_token == ".":
                            pass  # continue collecting
                        elif (
                            skipped_of and next_token in ("+", "-") and token in _MULTI_ARG_OF_FUNCS
                        ):
                            # "of" chains: replace +/- with , for multi-arg functions
                            # e.g., mean*1+2+3 -> mean(1,2,3)
                            # Restricted to multi-arg functions; for single-arg
                            # functions like sqrt, "sqrt of 144 + 5" stays as sqrt(144)+5.
                            output_tokens.append(",")
                            i += 1
                            continue
                        else:
                            break

                    output_tokens.append(next_token)
                    i += 1

                output_tokens.append(")")
        else:
            output_tokens.append(token)

        i += 1

    return output_tokens


def error_message(original: str, exception: BaseException, verbose: bool = False) -> None:
    """Print an error message based on the exception type."""
    # Sanitize input for safe terminal display
    safe_original = ''.join(
        (
            c
            if c.isprintable()
            and c not in '\x00\x01\x02\x03\x04\x05\x06\x07\x08\x0a\x0b\x0c\x0d\x0e\x0f'
            else '?'
        )
        for c in original
    )
    exc_type = type(exception)
    if exc_type is ValueError:
        print(f"Error: {exception}: '{safe_original}'", file=sys.stderr)
    elif exc_type is ZeroDivisionError:
        print(f"Can't divide by 0: '{safe_original}'", file=sys.stderr)
    elif exc_type is EvaluationError:
        print(f"Evaluation error: {exception}", file=sys.stderr)
    else:
        if verbose:
            traceback.print_exc()
        else:
            print(f"Error: {exception}", file=sys.stderr)


def convert_from_human_handler(
    tokens: list,
    operators: dict,
    patterns: Mapping[str, Pattern[str]],
    original: str,
) -> tuple[list, bool]:
    """Convert human-readable number words to numeric values."""
    is_valid = False

    for i in range(len(tokens)):
        is_number = check_if_number(tokens[i])

        if not is_number["bool"]:
            replaced = tokens[i]
            word_to_number = operators.get("word_to_number", {})
            for word, num_val in word_to_number.items():
                # Word-boundary replacement so substrings inside other words
                # (e.g. "one" inside "None", "Phone", "stone") are not mutated.
                replaced = re.sub(rf"\b{re.escape(word)}\b", f"@{num_val}", replaced)
            tokens[i] = {0: replaced, 1: is_number}
        else:
            tokens[i] = {0: tokens[i], 1: is_number}

        try:
            tokens[i] = convert_numbers(tokens[i], patterns)
            is_valid = True
        except ValueError:
            tokens[i] = tokens[i][0] if isinstance(tokens[i], dict) else tokens[i]

    return tokens, is_valid


def _should_split_number_minus(token: str) -> bool:
    """Check if token matches pattern: digit-sequence minus digit-sequence.

    Matches one or more subtraction operators between digit runs, e.g.
    ``4-5-3`` or ``4-5-3-2``. Used by ``split_at_operators`` to split
    arithmetic expressions where multiple subtraction operators were
    collapsed into a single token (because the splitter deliberately
    leaves bare ``-`` alone to avoid splitting unary ``-5``).
    """
    return bool(re.match(r"^\d+(?:-\d+)+$", token))


def _should_split_double_minus(token: str) -> bool:
    """Check if token matches pattern: digit-sequence -- digit-sequence."""
    return bool(re.match(r"^\d+--\d+$", token))


def _should_split_trailing_minus(token: str) -> bool:
    """Check if token ends with a subtraction operator that the splitter
    failed to isolate (e.g., ``"5-"`` when followed by a parenthesized
    expression). Returns True when the token is a digit run followed
    by a single trailing ``-`` that wasn't picked up by the symbol
    replacement pass.
    """
    return bool(re.match(r"^\d+-$", token))


def split_at_operators(
    expression: str, operators: dict, patterns: Mapping[str, Pattern[str]]
) -> list:
    """Split an expression string at operator boundaries."""
    for symbol in operators["symbols"]:
        if symbol != "-":
            if symbol == "+":
                # Use negative lookbehind to preserve "e+" in scientific notation
                expression = re.sub(r'(?<![eE])\+', f"\\\\{symbol}\\\\", expression)
            else:
                expression = expression.replace(symbol, f"\\{symbol}\\")

    tokens = [t.strip() for t in expression.split("\\") if t.strip()]

    # We split on the other operators, but leave bare "-" alone (to avoid
    # splitting the unary "-" of "-5"). However, that means "4-5-3" comes
    # through as a single token "4-5-3" and a digit-then-paren like
    # "5-(3+2)" becomes the token "5-". Walk the tokens with a while-loop
    # so newly-inserted tokens can be re-checked in the same pass, and
    # recompute len(tokens) each iteration to handle the inserts.
    i = 0
    while i < len(tokens):
        is_num = check_if_number(tokens[i])["bool"]
        is_op = patterns["operators"].match(tokens[i]) is not None

        if not is_num and not is_op:
            if _should_split_number_minus(tokens[i]):
                token = tokens[i]
                # Split on the FIRST '-' only; subsequent iterations of the
                # while-loop handle the remainder. This matches the
                # left-associative semantics of Python's '-' operator.
                parts = token.split("-", 1)
                tokens[i] = parts[0]
                tokens.insert(i + 1, "-")
                tokens.insert(i + 2, parts[1])
                # Don't advance — let the next iteration split the new
                # "<num>-<num>" token at the head, so "4-5-3" becomes
                # ["4", "-", "5", "-", "3"] rather than stopping at
                # ["4", "-", "5-3"].
                continue
            elif _should_split_trailing_minus(tokens[i]):
                # Trailing minus the symbol-replacer missed (e.g., "5-" in
                # "5-(3+2)"). Split off the minus so the next token can be
                # processed correctly.
                token = tokens[i]
                tokens[i] = token[:-1]
                tokens.insert(i + 1, "-")
                continue
            elif _should_split_double_minus(tokens[i]):
                token = tokens[i]
                parts = token.split("--", 1)
                tokens[i] = parts[0]
                tokens.insert(i + 1, "-")
                tokens.insert(i + 2, f"-{parts[1]}")
            elif _should_split_number_sequence(tokens[i]):
                parts = tokens[i].split()
                tokens[i : i + 1] = parts
        i += 1

    return tokens


def _finish_number_group(group: list, patterns: Mapping[str, Pattern[str]]) -> list:
    """Convert a number group to final tokens.

    For compound numbers like [3, 100, 20, 2], combine_number_parts handles
    the multiplication (3*100) and addition (20+2=22) correctly.

    For simple additions like [5, 3], we just return them with '+' between.
    """
    numbers_only = [x for x in group if x != "+"]
    if not numbers_only:
        return []

    # Only use combine_number_parts for real numbers (int or float), not complex
    def is_real(n: Any) -> bool:
        return isinstance(n, (int, float)) and not isinstance(n, complex)

    def is_compound_real(n: Any) -> bool:
        return is_real(n) and (n >= 100 or (20 <= n < 100))

    has_compound = any(is_compound_real(n) for n in numbers_only)

    if has_compound and len(numbers_only) > 1:
        combined = combine_number_parts(numbers_only, patterns, [])
        return combined
    else:
        # Simple addition: 5 + 3 should stay as ['5', '+', '3']
        result = []
        for i, n in enumerate(numbers_only):
            if i > 0:
                result.append("+")
            result.append(str(n))
        return result


def _combine_consecutive_numbers(
    tokens: list,
    operators: dict,
    patterns: Mapping[str, Pattern[str]],
) -> list:
    """Combine consecutive number tokens separated by + into compound numbers.

    After convert_from_human_handler, tokens like ['5', '+', '3', '+', '100', '+', '20', '+', '2']
    need to have the numbers 3, 100, 20, 2 combined as 322 using combine_number_parts.

    Only combines pure numeric tokens (no units or other letters attached).

    The algorithm:
    1. Look for numbers followed by '+' and another pure number
    2. Collect the full sequence of number + number + number...
    3. Use combine_number_parts to properly combine them
    4. Output any non-number or unit-having tokens as-is

    Preserves the original token text so leading zeros (e.g., "0.015")
    are not lost when re-emitting.
    """
    if not tokens:
        return tokens

    def _is_pure_number(token: str) -> bool:
        stripped = token.strip("+-")
        return stripped.isdigit() and not any(c.isalpha() for c in stripped)

    result = []
    i = 0

    while i < len(tokens):
        token = tokens[i]
        num_info = check_if_number(token)

        if not num_info["bool"] or not _is_pure_number(token):
            result.append(token)
            i += 1
            continue

        number_parts: list[tuple[Any, str]] = [(num_info["converted"], token)]
        original_tokens: list[str] = [token]

        while True:
            if i + 1 < len(tokens):
                next_token = tokens[i + 1]
                next_is_num = check_if_number(next_token)["bool"] and _is_pure_number(next_token)
                if next_is_num:
                    number_parts.append((check_if_number(next_token)["converted"], next_token))
                    original_tokens.append(next_token)
                    i += 1
                else:
                    break
            else:
                break

        if len(number_parts) > 1:
            values = [v for v, _ in number_parts]
            combined = _finish_number_group(values, patterns)
            if len(combined) == 1 and combined[0] == "+".join(original_tokens):
                result.append(combined[0])
            else:
                result.extend(combined)
        else:
            result.append(original_tokens[0])

        i += 1

    return result


def _should_split_number_sequence(token: str) -> bool:
    """Check if token is a space-separated number sequence that should be split.

    For example, "3 100 20 2" should be split into ['3', '100', '20', '2']
    so each can be properly converted as a number word.
    """
    if ' ' not in token:
        return False
    parts = token.split()
    if len(parts) < 2:
        return False
    for part in parts:
        stripped = part.strip('+-')
        if not stripped.replace('.', '').replace('e', '').replace('E', '').isdigit():
            return False
    return True


# Module-level binary-word validation. Detects <value> not/in/to/as/into <value>
# patterns and raises a clear error (e.g., "5 not 6" -> SyntaxError rather than
# the silent "5~6" that would be produced by naive word substitution).
_BINARY_WORD_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?|\((?:[^()]|\([^()]*\))*\))\s+" r"(not|in|to|as|into)\s+" r"(\d+(?:\.\d+)?)\b",
    flags=re.IGNORECASE,
)


# Module-level set of function names that participate in implicit multiplication.
# Used by the whitespace-removal loop to insert '*' between a digit/') and a
# function name, and (in apply_math_functions) to swap leading numbers into
# the function's argument list when the function takes exactly one argument.
_IMPLICIT_MUL_FUNCS: set[str] = {
    "sqrt",
    "sin",
    "cos",
    "tan",
    "asin",
    "acos",
    "atan",
    "sinh",
    "cosh",
    "tanh",
    "log",
    "ln",
    "log10",
    "log2",
    "exp",
    "abs",
    "factorial",
    "fact",
    "cbrt",
    "floor",
    "ceil",
    "round",
    "sign",
    "mean",
    "median",
    "mode",
    "std",
    "variance",
    "var",
    "gcd",
    "lcm",
    "perm",
    "comb",
    "nPr",
    "nCr",
    "isprime",
    "nextprime",
    "prevprime",
    "primefactors",
    "random",
    "randint",
    "gauss",
    "sum",
    "max",
    "min",
    "hypot",
    "clamp",
    "sine",
    "cosine",
    "tangent",
    "absolute",
    "ceiling",
    "stdev",
    "average",
}

# Named constants that participate in implicit multiplication with numbers.
# Only multi-letter constants to avoid conflicts (e.g., "2e3" is scientific notation).
# Single-letter "e" is excluded because it conflicts with scientific notation
# like "1e3" and with reserved identifiers — use "2.71828" or "(pi tau)" instead.
_IMPLICIT_MUL_CONSTANTS: set[str] = {
    "pi",
    "tau",
}

# Subset of _IMPLICIT_MUL_FUNCS that take exactly one argument. Used by
# apply_math_functions to detect "<num> <func>" -> "<func>(<num>)" swap.
_SINGLE_ARG_IMPLICIT_MUL: set[str] = {
    "sqrt",
    "sin",
    "cos",
    "tan",
    "asin",
    "acos",
    "atan",
    "sinh",
    "cosh",
    "tanh",
    "log",
    "ln",
    "log10",
    "log2",
    "exp",
    "abs",
    "factorial",
    "fact",
    "cbrt",
    "floor",
    "ceil",
    "round",
    "sign",
    "isprime",
    "nextprime",
    "prevprime",
    "random",
    "primefactors",
    "sine",
    "cosine",
    "tangent",
    "absolute",
    "ceiling",
}

# Subset of _IMPLICIT_MUL_FUNCS that take multiple arguments. Used by
# apply_math_functions to allow "of" chains like "mean of 1+2+3" ->
# "mean(1,2,3)". Single-arg functions keep "+" / "-" as real operators
# (e.g., "sqrt of 144 + 5" -> "sqrt(144) + 5").
_MULTI_ARG_OF_FUNCS: set[str] = {
    "mean",
    "median",
    "mode",
    "std",
    "variance",
    "var",
    "gcd",
    "lcm",
    "perm",
    "comb",
    "nPr",
    "nCr",
    "sum",
    "max",
    "min",
    "clamp",
    "gauss",
    "hypot",
    "randint",
}


def _binary_word_check(expr: str) -> bool:
    """Raise ValueError if expr contains <value> not/in/to/as/into <value>.

    These words are reserved for unary bitwise NOT or unit conversion. When
    they appear between two numeric values (e.g., "5 not 6", "1 in 2"), we
    would produce invalid Python (e.g., "5~6", "1IN2") and the meaning is
    ambiguous. Raises a clear error instead.
    """
    m = _BINARY_WORD_PATTERN.search(expr)
    if m:
        raise ValueError(
            f"Syntax error: '{m.group(2).lower()}' is not a binary operator in this context. "
            f"Use parentheses for unary 'not' (e.g., '~(5+6)'); "
            f"for unit conversion, follow the pattern '<value> in <unit>'."
        )
    return True


def _normalize_lowercase_temperature_conversion(expression: str) -> str:
    """Canonicalize compact lowercase temperature conversion phrases.

    Lowercase ``c``/``f``/``k`` are accepted as temperature units by the unit
    preprocessor, but conversion words are replaced before token handling. A
    phrase like ``100 c in f`` otherwise collapses into ``100cINf`` and the
    conversion detector never sees separate source/target unit tokens.
    """
    temp_unit = r"(?:[cfk]|celsius|fahrenheit|kelvin|rankine|degc|degf|degk|degr|ra)"

    def _canon_temp_unit(unit: str) -> str:
        lower = unit.lower()
        if lower in _LOWERCASE_TEMP_UNITS:
            return _LOWERCASE_TEMP_UNITS[lower]
        return UNIT_ALIASES.get(unit, UNIT_ALIASES.get(lower, unit))

    def _replace(m: re.Match[str]) -> str:
        from_unit = _canon_temp_unit(m.group(2))
        to_unit = _canon_temp_unit(m.group(4))
        return f"{m.group(1)} {from_unit} {m.group(3)} {to_unit}"

    return re.sub(
        rf"(\d+(?:\.\d+)?)\s+({temp_unit})\s+(in|to|as|into)\s+({temp_unit})\b",
        _replace,
        expression,
        flags=re.IGNORECASE,
    )


def _normalize_spelled_unit_conversions(expression: str) -> str:
    """Canonicalize unit conversion phrases before operator words are replaced.

    This catches spaced word forms like ``30 kilometers per hour in miles per
    hour``. If left until the generic word replacement pass, ``per`` becomes
    ``/`` and ``in`` becomes ``IN``, then whitespace stripping can glue the
    target into invalid identifiers such as ``hourINmiles``.
    """
    unit_alt = _UNIT_NAMES_ALTERNATION

    def _canon_unit(unit: str) -> str:
        lower = unit.lower()
        if lower in _LOWERCASE_TEMP_UNITS:
            return _LOWERCASE_TEMP_UNITS[lower]
        return UNIT_ALIASES.get(unit, UNIT_ALIASES.get(lower, unit))

    def _canon_unit_expr(numerator: str, denominator: str | None) -> str:
        num = _canon_unit(numerator)
        if denominator is None:
            return num
        den = _canon_unit(denominator)
        compound = f"{num}/{den}"
        return UNIT_ALIASES.get(compound, UNIT_ALIASES.get(compound.lower(), compound))

    def _replace(m: re.Match[str]) -> str:
        from_unit = _canon_unit_expr(m.group("from_num_unit"), m.group("from_den_unit"))
        to_unit = _canon_unit_expr(m.group("to_num_unit"), m.group("to_den_unit"))
        return f"convert({m.group('number')}*{from_unit},{to_unit})"

    return re.sub(
        rf"(?<![A-Za-z0-9_.+\-])(?P<number>[+-]?\d+(?:\.\d+)?)\s*"
        rf"(?P<from_num_unit>{unit_alt})(?![A-Za-z0-9_])"
        rf"(?:\s*(?:/|per)\s*(?P<from_den_unit>{unit_alt})(?![A-Za-z0-9_]))?"
        rf"\s+(in|to|as|into)\s+"
        rf"(?P<to_num_unit>{unit_alt})(?![A-Za-z0-9_])"
        rf"(?:\s*(?:/|per)\s*(?P<to_den_unit>{unit_alt})(?![A-Za-z0-9_]))?",
        _replace,
        expression,
        flags=re.IGNORECASE,
    )


def _canonical_power_unit(unit: str, exponent: str) -> str:
    canonical = UNIT_ALIASES.get(unit, UNIT_ALIASES.get(unit.lower(), unit))
    return (
        UNIT_ALIASES.get(f"{canonical}^{exponent}")
        or UNIT_ALIASES.get(f"{unit}^{exponent}")
        or UNIT_ALIASES.get(f"{unit.lower()}^{exponent}")
        or UNIT_ALIASES.get(f"{canonical}{exponent}")
        or f"{canonical}**{exponent}"
    )


def _normalize_postfix_unit_power_words(expression: str) -> str:
    """Normalize postfix unit power words like ``m squared`` and ``cm cubed``.

    Prefix forms such as ``square meters`` are already handled by UNIT_ALIASES
    after whitespace removal. This covers the common postfix phrasing while
    preserving the established shorthand meaning: ``5 m squared`` is ``5*m2``.
    """
    unit_alt = _UNIT_NAMES_ALTERNATION

    def _replace(m: re.Match[str]) -> str:
        exponent = "2" if m.group("power").lower() == "squared" else "3"
        return _canonical_power_unit(m.group("unit"), exponent)

    return re.sub(
        rf"(?<![A-Za-z0-9_])(?P<unit>{unit_alt})(?![A-Za-z0-9_])\s+" rf"(?P<power>squared|cubed)\b",
        _replace,
        expression,
        flags=re.IGNORECASE,
    )


def _normalize_spaced_unit_caret_exponents(expression: str) -> str:
    """Normalize unit exponent shorthand while preserving ``^`` as XOR.

    Numeric ``^`` remains bitwise XOR by design, but users reasonably write
    unit shorthands such as ``5 m ^ 2`` or ``5 m/s^2``. Compact ``5m^2`` was
    already accepted because ``m^2`` is a unit alias; this makes spaced forms
    follow the same path before generic operator splitting turns ``^`` into
    XOR.
    """
    unit_alt = _UNIT_NAMES_ALTERNATION

    def _replace_attached_quantity(m: re.Match[str]) -> str:
        return f"{m.group(1)} {_canonical_power_unit(m.group(2), m.group(3))}"

    expression = re.sub(
        rf"(\d+(?:\.\d+)?)\s+({unit_alt})\s*\^\s*([23])\b",
        _replace_attached_quantity,
        expression,
        flags=re.IGNORECASE,
    )

    def _replace_denominator(m: re.Match[str]) -> str:
        canonical = UNIT_ALIASES.get(m.group(1), UNIT_ALIASES.get(m.group(1).lower(), m.group(1)))
        return f"/{canonical}**{m.group(2)}"

    expression = re.sub(
        rf"/\s*({unit_alt})\s*\^\s*(\d+)\b",
        _replace_denominator,
        expression,
        flags=re.IGNORECASE,
    )

    def _replace_parenthesized_denominator(m: re.Match[str]) -> str:
        canonical = UNIT_ALIASES.get(m.group(1), UNIT_ALIASES.get(m.group(1).lower(), m.group(1)))
        return f"/({canonical})**{m.group(2)}"

    return re.sub(
        rf"/\(\s*({unit_alt})\s*\)\s*\^\s*(\d+)\b",
        _replace_parenthesized_denominator,
        expression,
        flags=re.IGNORECASE,
    )


# Module-level multi-word function name mappings (constant, no need to recreate each call)
_MULTI_WORD_FUNCTIONS: dict[str, str] = {
    "square root": "sqrt",
    "cube root": "cbrt",
    "inverse sine": "asin",
    "inverse cosine": "acos",
    "inverse tangent": "atan",
    # "arc X" forms (alternative to "inverse X")
    "arc sine": "asin",
    "arc cosine": "acos",
    "arc tangent": "atan",
    "arc cos": "acos",
    "arc sin": "asin",
    "arc tan": "atan",
    # Hyperbolic variants
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

# --- Pre-computed constants for normalize() (avoid per-call rebuild) ---

_NUMBER_SCALES: dict[str, list[str]] = {
    "100": ["hundred"],
    "1000": ["thousand"],
    "1000000": ["million"],
    "1000000000": ["billion"],
    "1000000000000": ["trillion"],
    "1000000000000000": ["quadrillion"],
    "1000000000000000000": ["quintillion"],
}

_NUMBER_WORDS_SINGLE: dict[str, list[str]] = {
    "1": ["one"],
    "2": ["two"],
    "3": ["three"],
    "4": ["four"],
    "5": ["five"],
    "6": ["six"],
    "7": ["seven"],
    "8": ["eight"],
    "9": ["nine"],
}

_NUMBER_WORDS_TEENS: dict[str, list[str]] = {
    "10": ["ten"],
    "11": ["eleven"],
    "12": ["twelve"],
    "13": ["thirteen"],
    "14": ["fourteen"],
    "15": ["fifteen"],
    "16": ["sixteen"],
    "17": ["seventeen"],
    "18": ["eighteen"],
    "19": ["nineteen"],
}

_NUMBER_WORDS_TENS: dict[str, list[str]] = {
    "20": ["twenty"],
    "30": ["thirty"],
    "40": ["forty"],
    "50": ["fifty"],
    "60": ["sixty"],
    "70": ["seventy"],
    "80": ["eighty"],
    "90": ["ninety"],
}


def _build_multi_word_numbers() -> dict[str, str]:
    """Build mapping of multi-word number phrases to their numeric values.

    E.g., "one hundred" -> "100", "twenty one thousand" -> "21000".
    Computed once at module import time.
    """
    result: dict[str, str] = {}
    all_small = {**_NUMBER_WORDS_SINGLE, **_NUMBER_WORDS_TEENS, **_NUMBER_WORDS_TENS}
    for num_val, words in all_small.items():
        for scale_val, scale_words in _NUMBER_SCALES.items():
            for word in words:
                for scale_word in scale_words:
                    key = f"{word} {scale_word}"
                    result[key] = str(int(num_val) * int(scale_val))
    for tens_val, tens_words in _NUMBER_WORDS_TENS.items():
        for ones_val, ones_words in {**_NUMBER_WORDS_SINGLE, **_NUMBER_WORDS_TEENS}.items():
            for scale_val, scale_words in _NUMBER_SCALES.items():
                for tens_word in tens_words:
                    for ones_word in ones_words:
                        for scale_word in scale_words:
                            key = f"{tens_word} {ones_word} {scale_word}"
                            result[key] = str((int(tens_val) + int(ones_val)) * int(scale_val))
    # Compound hundreds with larger scales: "X hundred Y thousand" -> (X*100+Y)*1000
    # E.g., "one hundred twenty one thousand" -> 121000
    larger_scales = {sv: sw for sv, sw in _NUMBER_SCALES.items() if int(sv) > 100}
    all_ones = {**_NUMBER_WORDS_SINGLE, **_NUMBER_WORDS_TEENS}
    for hundred_val, hundred_words in _NUMBER_WORDS_SINGLE.items():
        for scale_val, scale_words in larger_scales.items():
            for hundred_word in hundred_words:
                for scale_word in scale_words:
                    # "X hundred scale" = X*100*scale (e.g., "one hundred thousand" = 100000)
                    key = f"{hundred_word} hundred {scale_word}"
                    result[key] = str(int(hundred_val) * 100 * int(scale_val))
                    # "X hundred tens scale" for tens only (e.g., "one hundred twenty thousand")
                    for tens_val, tens_words in _NUMBER_WORDS_TENS.items():
                        tens_only = int(tens_val)
                        combined = int(hundred_val) * 100 + tens_only
                        for tens_word in tens_words:
                            key = f"{hundred_word} hundred " f"{tens_word} {scale_word}"
                            result[key] = str(combined * int(scale_val))
                    # "X hundred tens ones scale" for tens+ones (e.g., "one hundred twenty one thousand")
                    for tens_val, tens_words in _NUMBER_WORDS_TENS.items():
                        for ones_val, ones_words in all_ones.items():
                            y_val = int(tens_val) + int(ones_val)
                            combined = int(hundred_val) * 100 + y_val
                            for tens_word in tens_words:
                                for ones_word in ones_words:
                                    key = (
                                        f"{hundred_word} hundred "
                                        f"{tens_word} {ones_word} {scale_word}"
                                    )
                                    result[key] = str(combined * int(scale_val))
                    # "X hundred teen scale" for teens (e.g., "one hundred twelve thousand")
                    for teen_val, teen_words in _NUMBER_WORDS_TEENS.items():
                        combined = int(hundred_val) * 100 + int(teen_val)
                        for teen_word in teen_words:
                            key = f"{hundred_word} hundred " f"{teen_word} {scale_word}"
                            result[key] = str(combined * int(scale_val))
                    # "X hundred ones scale" for ones (e.g., "one hundred one thousand")
                    for ones_val, ones_words in _NUMBER_WORDS_SINGLE.items():
                        combined = int(hundred_val) * 100 + int(ones_val)
                        for ones_word in ones_words:
                            key = f"{hundred_word} hundred " f"{ones_word} {scale_word}"
                            result[key] = str(combined * int(scale_val))
    # Standalone compound numbers (tens + ones, no scale word)
    # E.g., "twenty one" -> 21, "forty two" -> 42
    for tens_val, tens_words in _NUMBER_WORDS_TENS.items():
        for ones_val, ones_words in all_ones.items():
            combined = int(tens_val) + int(ones_val)
            for tens_word in tens_words:
                for ones_word in ones_words:
                    key = f"{tens_word} {ones_word}"
                    result[key] = str(combined)
    # Standalone compound hundreds (X hundred Y, no trailing scale word)
    # E.g., "one hundred forty four" -> 144, "two hundred" -> 200
    for hundred_val, hundred_words in _NUMBER_WORDS_SINGLE.items():
        for hundred_word in hundred_words:
            # "X hundred" alone is already handled by the basic scale section
            # "X hundred tens" (e.g., "one hundred forty")
            for tens_val, tens_words in _NUMBER_WORDS_TENS.items():
                combined = int(hundred_val) * 100 + int(tens_val)
                for tens_word in tens_words:
                    key = f"{hundred_word} hundred {tens_word}"
                    result[key] = str(combined)
            # "X hundred tens ones" (e.g., "one hundred forty four")
            for tens_val, tens_words in _NUMBER_WORDS_TENS.items():
                for ones_val, ones_words in all_ones.items():
                    combined = int(hundred_val) * 100 + int(tens_val) + int(ones_val)
                    for tens_word in tens_words:
                        for ones_word in ones_words:
                            key = f"{hundred_word} hundred {tens_word} {ones_word}"
                            result[key] = str(combined)
            # "X hundred teen" (e.g., "one hundred twelve" -> 112)
            for teen_val, teen_words in _NUMBER_WORDS_TEENS.items():
                combined = int(hundred_val) * 100 + int(teen_val)
                for teen_word in teen_words:
                    key = f"{hundred_word} hundred {teen_word}"
                    result[key] = str(combined)
            # "X hundred ones" (e.g., "one hundred one" -> 101)
            for ones_val, ones_words in _NUMBER_WORDS_SINGLE.items():
                combined = int(hundred_val) * 100 + int(ones_val)
                for ones_word in ones_words:
                    key = f"{hundred_word} hundred {ones_word}"
                    result[key] = str(combined)
    return result


_MULTI_WORD_NUMBERS: dict[str, str] = _build_multi_word_numbers()
# Compound fraction words (e.g., "one half" → 0.5)
_MULTI_WORD_NUMBERS["one half"] = "0.5"
_MULTI_WORD_NUMBERS["one quarter"] = "0.25"
_MULTI_WORD_NUMBERS["one third"] = "0.3333333333333333"
_MULTI_WORD_NUMBERS["two thirds"] = "0.6666666666666666"
_MULTI_WORD_NUMBERS["three quarters"] = "0.75"

# Set of all number words (for hyphen detection)
_ALL_NUMBER_WORDS_SET: frozenset[str] = frozenset(
    word for words in NUMBER_WORDS.values() for word in words
)
_NUMBER_WORDS_HYPHEN_PATTERN: str = "|".join(sorted(_ALL_NUMBER_WORDS_SET, key=len, reverse=True))

# Flattened word -> digit mapping (for single-word replacement)
_ALL_NUMBER_WORDS_FLAT: dict[str, str] = {}
for _val, _words in NUMBER_WORDS.items():
    for _word in _words:
        _ALL_NUMBER_WORDS_FLAT[_word] = _val
_SORTED_ALL_NUMBER_WORDS: list[tuple[str, str]] = sorted(
    _ALL_NUMBER_WORDS_FLAT.items(), key=lambda x: len(x[0]), reverse=True
)

# Long filler phrases (>10 chars) for stripping
_LONG_PHRASES: list[str] = [p for p in STRIPPED_PHRASES if len(p) > 10]
_LONG_PHRASES_PATTERN: str = (
    "|".join(sorted([re.escape(p) for p in _LONG_PHRASES], key=len, reverse=True))
    if _LONG_PHRASES
    else ""
)

# Sorted multi-word number phrases for replacement (longest first)
_SORTED_MULTI_WORD_NUMBERS: list[tuple[str, str]] = sorted(
    _MULTI_WORD_NUMBERS.items(), key=lambda x: len(x[0]), reverse=True
)

# Digit scale words for "N thousand" -> evaluated result conversion
_DIGIT_SCALES: dict[str, str] = {
    "hundred": "100",
    "thousand": "1000",
    "million": "1000000",
    "billion": "1000000000",
    "trillion": "1000000000000",
    "quadrillion": "1000000000000000",
    "quintillion": "1000000000000000000",
}


def normalize(expression: str, operators: dict, patterns: Mapping[str, Pattern[str]]) -> str:
    """Normalize an expression by removing filler words and applying conversions."""
    if not expression or not expression.strip():
        raise ValueError("Empty expression")
    if len(expression) > MAX_INPUT_LENGTH:
        raise ValueError(f"Input too long (max {MAX_INPUT_LENGTH} characters)")

    # Replace unicode math operators with ASCII equivalents before any
    # tokenization or whitespace processing. Must happen early because
    # the whitespace-removal loop treats these as alpha characters.
    expression = expression.replace("\u00d7", "*")  # × → *
    expression = expression.replace("\u00f7", "/")  # ÷ → /
    expression = expression.replace("\u2212", "-")  # − → -

    # Replace multi-word function names before whitespace removal collapses them
    # e.g., "square root" -> "sqrt", "cube root" -> "cbrt"
    for phrase, replacement in sorted(
        _MULTI_WORD_FUNCTIONS.items(), key=lambda x: len(x[0]), reverse=True
    ):
        expression = re.sub(
            r"\b" + re.escape(phrase) + r"\b", replacement, expression, flags=re.IGNORECASE
        )

    # Accept compact single-argument function forms promised by the parser
    # comments, e.g. "sin30" -> "sin 30" and "2sqrt9" -> "2sqrt 9".
    # Guard names that already end in digits so "log10" and "log2" remain
    # function identifiers instead of being split as "log 10" / "log 2".
    digit_ending_functions = {
        name.lower() for name in operators["functions"] if name[-1:].isdigit()
    }
    compact_arg_functions = [
        name
        for name in operators["functions"]
        if name in _SINGLE_ARG_IMPLICIT_MUL and not name[-1:].isdigit()
    ]
    if compact_arg_functions:
        compact_arg_pattern = re.compile(
            r"(?<![A-Za-z_])("
            + "|".join(
                re.escape(name) for name in sorted(compact_arg_functions, key=len, reverse=True)
            )
            + r")([+-]?\d+(?:\.\d+)?)(?![A-Za-z_])",
            flags=re.IGNORECASE,
        )

        def _split_compact_function_arg(m: re.Match[str]) -> str:
            compact = (m.group(1) + m.group(2)).lower()
            if any(compact.startswith(name) for name in digit_ending_functions):
                return m.group(0)
            return f"{m.group(1)} {m.group(2)}"

        expression = compact_arg_pattern.sub(_split_compact_function_arg, expression)

    # Convert hyphens between number words to spaces
    # e.g., "twenty-one" -> "twenty one" (prevents hyphen being treated as minus)
    expression = re.sub(
        rf"\b({_NUMBER_WORDS_HYPHEN_PATTERN})-({_NUMBER_WORDS_HYPHEN_PATTERN})\b",
        r"\1 \2",
        expression,
        flags=re.IGNORECASE,
    )

    # Insert implicit multiplication between a number and a following "("
    # so "3(4+5)" parses as "3*(4+5)" = 27 instead of a syntax error.
    # Do not split function names ending in digits, such as log10(100).
    def _implicit_digit_paren(m: re.Match) -> str:
        token = str(m.group(1))
        if token in operators["functions"]:
            return token
        return token + "*"

    expression = re.sub(r"([A-Za-z_][A-Za-z0-9_]*\d|\d)(?=\()", _implicit_digit_paren, expression)

    # Replace multi-word number phrases to prevent incorrect joining
    # e.g., "one hundred" -> "100", "two thousand" -> "2000"
    for phrase, replacement in _SORTED_MULTI_WORD_NUMBERS:
        expression = re.sub(
            r"\b" + re.escape(phrase) + r"\b", replacement, expression, flags=re.IGNORECASE
        )

    # Strip "and" as a filler word in NL number expressions
    expression = re.sub(r"\band\b", "", expression, flags=re.IGNORECASE)

    # Handle short-form power phrases BEFORE individual word replacement so
    # that "2 to the 10" doesn't become "2 TO 10". Long forms like
    # "to the power of" and "raised to" are handled by the word_to_all
    # loop below; this catches the abbreviated form "N to the M".
    # Also handles word numbers like "three to the ten" by matching both
    # digit and word number patterns.
    expression = re.sub(
        r"(\d+(?:\.\d+)?)\s+to\s+the\s+(\d+(?:\.\d+)?)",
        r"\1**\2",
        expression,
        flags=re.IGNORECASE,
    )
    # Also handle mixed digit/word: "3 to the ten", "three to the 10"
    # by running a second pass after word replacement (see below)

    _binary_word_check(expression)
    expression = _normalize_lowercase_temperature_conversion(expression)

    for scale_word, scale_val in _DIGIT_SCALES.items():
        # Convert "N thousand" to the evaluated product (e.g., "5 thousand" -> "5000").
        # Produces a clean digit token so _join_number_parts doesn't insert spurious *.
        # Use int() when the product is a whole number to avoid ".0" suffix that
        # would corrupt the decimal merge loop downstream.
        def _scale_product(m: re.Match[str], sv: str = scale_val) -> str:
            v = float(m.group(1)) * float(sv)
            return str(int(v)) if v == int(v) else str(v)

        expression = re.sub(
            r"\b(\d+(?:\.\d+)?)\s*" + re.escape(scale_word) + r"\b",
            _scale_product,
            expression,
            flags=re.IGNORECASE,
        )
        # Handle "(N) thousand" -> "(N)*1000" (scale word after closing paren)
        expression = re.sub(
            r"(\))\s*" + re.escape(scale_word) + r"\b",
            f"*{scale_val}",
            expression,
            flags=re.IGNORECASE,
        )

    # Replace single number words with digits BEFORE _join_number_parts runs
    # This ensures unrecognized number words are converted to digits for the fallback path.
    # Compound numbers like "twenty one" are already resolved by _MULTI_WORD_NUMBERS above.
    for word, replacement in _SORTED_ALL_NUMBER_WORDS:
        expression = re.sub(
            r"\b" + re.escape(word) + r"\b", replacement, expression, flags=re.IGNORECASE
        )

    # Handle short-form power phrases AFTER word replacement to support
    # word numbers like "three to the ten" → "3**10". This must run after
    # number word replacement but before word_to_all replaces "to" with "TO".
    expression = re.sub(
        r"(\d+(?:\.\d+)?)\s+to\s+the\s+(\d+(?:\.\d+)?)",
        r"\1**\2",
        expression,
        flags=re.IGNORECASE,
    )

    expression = _normalize_postfix_unit_power_words(expression)
    expression = _normalize_spelled_unit_conversions(expression)

    # Strip longer filler phrases before word-to-operator conversion so that
    # "the value of pi" → "pi" (not "value * pi" after "of" → "*").
    # Short phrases like "the " are stripped AFTER word_to_all to avoid
    # corrupting operator phrases like "to the power of".
    if _LONG_PHRASES_PATTERN:
        expression = re.sub(f"({_LONG_PHRASES_PATTERN})", "", expression)

    # Use combined word replacement for efficiency (single pass)
    # Use word boundaries to avoid replacing parts of words
    word_to_all = operators.get("word_to_all", {})
    _binary_word_check(expression)
    # Disambiguate inch conversion before the generic word replacement. In
    # "5 in in cm", the first "in" is the inch unit and the second "in" is
    # the conversion operator; a global preservation of "in" would merge the
    # whole tail into the invalid identifier "inincm".
    expression = re.sub(
        rf"((?:\d|\))\s+)in(\s+in\s+(?:{_UNIT_NAMES_ALTERNATION})\b)",
        r"\1inch\2",
        expression,
        flags=re.IGNORECASE,
    )
    for word, replacement in sorted(word_to_all.items(), key=lambda x: len(x[0]), reverse=True):
        # Special case: don't convert "in"/"into" when it appears to be a unit suffix
        # (preceded by a digit, no following unit, or followed by something that
        # isn't a unit). E.g., "5 in" or "5 in to cm" where "in" is a unit, not a keyword.
        if word.lower() in ("in", "into"):
            # Preserve "in" as a unit (not keyword) when:
            # 1. At end of expression ("5 in" = 5 inches), OR
            # 2. Followed by a conversion keyword ("in"/"to"/"as") - e.g., "5 in in cm"
            if re.search(
                r"(?:\d|\))\s+" + re.escape(word) + r"(?:\s*$|\s+(?:in|to|as)\b)",
                expression,
                flags=re.IGNORECASE,
            ):
                continue
        expression = re.sub(
            r"\b" + re.escape(word) + r"\b", replacement, expression, flags=re.IGNORECASE
        )

    # Handle "point" as decimal separator: only when preceded by a digit or ')'
    # This avoids ".5" at expression start while still allowing "5 point 3" -> "5.3"
    expression = re.sub(r"(?<=[\d)])\s*point\s*", ".", expression, flags=re.IGNORECASE)

    # Merge digits following a decimal point: "3.1 4" -> "3.14"
    # After "point" replacement, space-separated digit words after the decimal
    # become separate tokens (e.g., "three point one four" -> "3 point 1 4" ->
    # "3.1 4"). Iteratively concatenate them into a single decimal number.
    prev_expr = None
    while prev_expr != expression:
        prev_expr = expression
        expression = re.sub(r"(\d+\.\d*)\s+(\d)", lambda m: m.group(1) + m.group(2), expression)

    # Strip short filler phrases after word-to-operator conversion
    expression = patterns["stripped_chars"].sub("", expression)

    # Handle compound unit conversions after stripping
    # e.g., "60mi/h in m/s" -> "convert(60*mi/h,m/s)"
    # e.g., "30 km/h in mph" -> "convert(30*km/h,mph)"
    # The / in unit names would be tokenized as division, so we must handle this first.
    # Note: "in"/"to" may have been replaced with "IN"/"TO" already; handle both forms.
    # Also accept the optional "*" between the number and the unit (from
    # the bare compound unit handling below).
    _COMPOUND_UNITS = ["km/h", "mi/h", "m/s", "km/s", "mi/s"]
    # Also allow single units as targets (e.g., "30 km/h in mph")
    _SINGLE_UNITS_FOR_CONVERSION = ["mph", "kph", "knot", "ft/s", "ft/min"]

    def _compound_unit_pattern(unit: str) -> str:
        """Match a compound unit while ignoring spaces around slash separators."""
        return r"\s*/\s*".join(re.escape(part) for part in unit.split("/"))

    for from_unit in _COMPOUND_UNITS:
        for to_unit in _COMPOUND_UNITS + _SINGLE_UNITS_FOR_CONVERSION:
            if from_unit != to_unit:
                pattern = (
                    rf"(\d+(?:\.\d+)?)\s*\*?\s*{_compound_unit_pattern(from_unit)}"
                    rf"\s*(?:in|to|IN|TO)\s*{_compound_unit_pattern(to_unit)}"
                )
                replacement_fn = (
                    lambda m, fu=from_unit, tu=to_unit: f"convert({m.group(1)}*{fu},{tu})"
                )
                expression = re.sub(pattern, replacement_fn, expression, flags=re.IGNORECASE)

    # Handle single-unit sources converting to compound targets
    # e.g., "100 mph to km/h" -> "convert(100*mph,km/h)"
    # The / in the target would be split by split_at_operators, so we must
    # handle this before tokenization.
    for from_unit in _SINGLE_UNITS_FOR_CONVERSION:
        for to_unit in _COMPOUND_UNITS:
            if from_unit != to_unit:
                pattern = (
                    rf"(\d+(?:\.\d+)?)\s*\*?\s*{_compound_unit_pattern(from_unit)}"
                    rf"\s*(?:in|to|IN|TO)\s*{_compound_unit_pattern(to_unit)}"
                )
                replacement_fn = (
                    lambda m, fu=from_unit, tu=to_unit: f"convert({m.group(1)}*{fu},{tu})"
                )
                expression = re.sub(pattern, replacement_fn, expression, flags=re.IGNORECASE)

    # Handle bare compound unit expressions: "30 km/h" -> "30*km/h"
    # (without this, "/h" would be tokenized as division and the unit interpretation
    # would be lost). Only insert "*" between the number and the compound unit.
    for unit in _COMPOUND_UNITS:
        pattern = rf"(\d+(?:\.\d+)?)(\s*)({re.escape(unit)})\b"
        expression = re.sub(
            pattern, lambda m: f"{m.group(1)}*{m.group(3)}", expression, flags=re.IGNORECASE
        )

    # Handle "<num> <unit> / <unit>" expressions (e.g., "5 km / h") - convert
    # to a form the evaluator can handle without naming `h` as a Planck constant.
    # We emit convert(N*unit1, base_unit) / convert(1*unit2, base_unit2) form.
    _COMPOUND_SPLIT_PAIRS: list[tuple[str, str]] = [
        ("km", "h"),
        ("mi", "h"),
        ("m", "s"),
        ("km", "s"),
        ("mi", "s"),
        ("km", "hr"),
        ("mi", "hr"),
        ("m", "sec"),
        ("km", "sec"),
        ("mi", "sec"),
        ("km", "min"),
        ("mi", "min"),
    ]
    for u1, u2 in _COMPOUND_SPLIT_PAIRS:
        pattern = rf"(\d+(?:\.\d+)?)\s*{re.escape(u1)}\s*/\s*{re.escape(u2)}\b"
        replacement_fn = lambda m, uu1=u1, uu2=u2: f"({m.group(1)}*{uu1})/({uu2})"
        expression = re.sub(pattern, replacement_fn, expression, flags=re.IGNORECASE)

    # Convert percentages (e.g., 50% -> 0.5, but not 5%3 which is modulo)
    # Match % directly attached to a number or with optional space, NOT followed by optional whitespace + digit
    # (negative lookahead ensures "5%3" and "10 % 3" stay as modulo, not "0.05" + "3")
    # Use a lookahead to add a space after % when followed by * (from "of" conversion)
    # to prevent "100%*200" from becoming "1.0**200" (exponentiation) instead of "1.0*200" (multiplication)
    def _pct_replace(m: re.Match) -> str:
        val = str(float(m.group(1)) / 100)
        # Leave any following operator in the original expression. Including
        # it here would duplicate "100%*200" into "1.0**200".
        return val

    expression = re.sub(r"(\d+(?:\.\d+)?)\s*%(?!\s*\d)", _pct_replace, expression)

    # Convert 'i' suffix to 'j' for complex numbers (e.g., 3+4i -> 3+4j)
    # Match: number followed by 'i' (not preceded by another letter)
    expression = re.sub(r"(\d)i\b", r"\1j", expression)
    # Handle standalone 'i' preceded by operators or at start
    expression = re.sub(r"(^|[+\-*/(])i\b", r"\g<1>1j", expression)

    # Handle angle mode: <number> degrees -> <number>*pi/180
    # This makes sin(30 degrees) interpret the argument as degrees rather than radians.
    # Must be done BEFORE the 'i' -> 'j' substitution (no conflict) and BEFORE
    # whitespace removal. Use word boundaries and case-insensitive matching.
    # Also handle "degrees in <unit>" by converting the full phrase.
    # Temperature units are skipped so "100 degrees in fahrenheit" is handled
    # by the unit conversion system, not the angle conversion.
    _TEMP_UNITS = frozenset(
        {
            "f",
            "c",
            "k",
            "fahrenheit",
            "celsius",
            "kelvin",
            "rankine",
            "degf",
            "degc",
            "degk",
            "degr",
            "ra",
        }
    )
    # Use a placeholder to prevent subsequent regexes from re-matching temperature expressions.
    _DEG_PLACEHOLDER = "\x00DEG_TEMP\x00"

    def _degrees_temp_handler(m: re.Match) -> str:
        if m.group(2).lower() in _TEMP_UNITS:
            # "100 degrees in fahrenheit" → "100 fahrenheit" (temperature, not angle)
            return f"{m.group(1)} {_DEG_PLACEHOLDER}{m.group(2)}"
        return f"(({m.group(1)}*pi/180)*{m.group(2)}/rad)"

    expression = re.sub(
        r"(\d+(?:\.\d+)?)\s*(?:degrees?|deg)\b\s+(?:in|IN|to|TO)\s+(\w+)",
        _degrees_temp_handler,
        expression,
        flags=re.IGNORECASE,
    )

    def _degrees_temp_no_in_handler(m: re.Match) -> str:
        if m.group(2).lower() in _TEMP_UNITS:
            # "100 degrees fahrenheit" → "100 fahrenheit" (temperature, not angle)
            return f"{m.group(1)} {_DEG_PLACEHOLDER}{m.group(2)}"
        if is_unit(m.group(2)):
            return f"({m.group(1)}*pi/180) {m.group(2)}"
        return f"({m.group(1)}*pi/180)"

    expression = re.sub(
        r"(\d+(?:\.\d+)?)\s*(?:degrees?|deg)\b\s+(\w+)",
        _degrees_temp_no_in_handler,
        expression,
        flags=re.IGNORECASE,
    )
    expression = re.sub(
        r"(\d+(?:\.\d+)?)\s*(?:degrees?|deg)\b",
        lambda m: f"({m.group(1)}*pi/180)",
        expression,
        flags=re.IGNORECASE,
    )
    # Restore temperature expressions from placeholder (strip "degrees", keep unit)
    expression = expression.replace(_DEG_PLACEHOLDER, "")
    expression = _normalize_spaced_unit_caret_exponents(expression)

    # Handle "N percent" -> "N/100" BEFORE _join_number_parts so compound
    # numbers like "twenty five percent" → "20 5 percent" → "(20+5)/100" = 0.25
    # Match digit sequences (possibly space-separated) followed by "percent"
    expression = re.sub(
        r"(\d+(?:\.\d+)?(?:\s+\d+(?:\.\d+)?)*)\s+percent\b",
        lambda m: f"({m.group(1).replace(' ', '+')})/100",
        expression,
        flags=re.IGNORECASE,
    )

    # Join space-separated number sequences with + for proper evaluation.
    # Compound numbers like "twenty one" are already resolved by _MULTI_WORD_NUMBERS,
    # but fallback sequences (e.g., from unrecognized patterns) still need joining.
    expression = _join_number_parts(expression)

    # Replace whitespace outside parentheses with nothing
    # Preserve whitespace inside parentheses to separate function args
    # Also insert * between function names and following digits (e.g., "sqrt 144" -> "sqrt*144")
    # And between a digit/`) and a function name (e.g., "5 sin" -> "5*sin", "2 sqrt 9" -> "2*sqrt 9")
    result: list[str] = []
    depth = 0
    prev_was_func_end = False
    i = 0
    n = len(expression)
    while i < n:
        char = expression[i]
        if char == "(":
            if result and result[-1] == ")":
                # Implicit multiplication: ")(" -> ")*("
                result.append("*")
            elif result and result[-1].isdigit():
                # Implicit multiplication: "<digit>(" -> "<digit>*(".
                # This branch handles cases where earlier whitespace-aware
                # token joining preserved a structural "(" token, such as
                # "3 ( 4 + 5 )".
                prev_alnum_token = _peek_alnum_token_back(result)
                if prev_alnum_token not in operators["functions"]:
                    result.append("*")
            depth += 1
            if depth > MAX_NESTING_DEPTH:
                raise ValueError(f"Expression nesting too deep (max {MAX_NESTING_DEPTH})")
            result.append(char)
            prev_was_func_end = False
            i += 1
        elif char == ")":
            depth -= 1
            result.append(char)
            prev_was_func_end = False
            i += 1
        elif char.isspace():
            if depth > 0:
                result.append(char)  # Keep space inside parentheses
            # Skip space outside parentheses
            i += 1
        else:
            # Detect: digit, ")", or alpha-constant followed by a
            # function/constant name (e.g., "5 sin" -> "5*sin",
            # "pi tau" -> "pi*tau", "2 sqrt 9" -> "2*sqrt 9").
            prev_back_token = _peek_alpha_token_back(result)
            is_prev_constant = prev_back_token in _IMPLICIT_MUL_CONSTANTS
            if (
                char.isalpha()
                and result
                and (result[-1] in "0123456789)" or (result[-1].isalpha() and is_prev_constant))
            ):
                # Look ahead to see if current alpha sequence matches an implicit-mul function
                trail: list[str] = []
                j = i
                while j < n and (expression[j].isalpha() or expression[j].isdigit()):
                    trail.append(expression[j])
                    j += 1
                candidate = "".join(trail)
                # Skip if the candidate is a unit alias (e.g., "30 min" -> "30min", not "30*min()")
                if (
                    (candidate in _IMPLICIT_MUL_FUNCS or candidate in _IMPLICIT_MUL_CONSTANTS)
                    and candidate not in UNIT_ALIASES
                    and candidate.lower() not in UNIT_ALIASES
                ):
                    result.append("*")
                    for c in candidate:
                        result.append(c)
                    i = j
                    prev_was_func_end = candidate in _IMPLICIT_MUL_FUNCS
                    continue

            if prev_was_func_end and char.isdigit():
                # Only insert '*' if the alpha run is actually a known
                # function name and the next char is a non-alphanumeric
                # separator (whitespace or '('). For "log10", the alpha
                # run is "log" but it is NOT a function in this context;
                # "log10" is the actual function name. We detect this by
                # looking ahead: if the next char is alphanumeric and the
                # alpha+next forms a longer function name, do NOT insert
                # '*'. The expanded alpha run is handled in the
                # implicit-mul block above, but for safety we also check
                # the trailing digit pattern here.
                #
                # Look at the alpha run we just emitted
                trail = []
                for c in reversed(result):
                    if c.isalpha():
                        trail.append(c)
                    else:
                        break
                alpha_run = "".join(reversed(trail))
                # Build the would-be full name including the upcoming digit
                full_name = alpha_run + char
                # If the full name is a function in the implicit-mul set,
                # do NOT insert '*' — keep them together.
                if (
                    full_name not in _IMPLICIT_MUL_FUNCS
                    and full_name not in _IMPLICIT_MUL_CONSTANTS
                ):
                    result.append("*")
            if result and result[-1] == ")" and (char.isdigit() or char == "("):
                # Implicit multiplication: ")(" or ")<digit>" -> ")*(" or ")*<digit>"
                # (e.g., "(2+3)4" -> "(2+3)*4", "(2+3)(4+5)" -> "(2+3)*(4+5)")
                result.append("*")
            if result and result[-1].isdigit() and char == "(":
                # Implicit multiplication: "<digit>(" -> "<digit>*("
                # (e.g., "3(4+5)" -> "3*(4+5)", "2(3+4)" -> "2*(3+4)")
                # Do not split function names ending in digits, such as
                # log10(100), log2(8), or expm1(1).
                prev_alnum_token = _peek_alnum_token_back(result)
                if prev_alnum_token not in operators["functions"]:
                    result.append("*")
            result.append(char)
            # Check if we just completed a function name. Only mark
            # prev_was_func_end if the current char is alphanumeric AND
            # the next non-alphanumeric char is a real separator
            # (whitespace or '('). Otherwise the alpha run is part of a
            # longer identifier (e.g. "log" in "log10").
            if char.isalpha():
                # Look back to see if the current alpha sequence is a function name
                trail = []
                for c in reversed(result):
                    if c.isalpha():
                        trail.append(c)
                    else:
                        break
                cand = "".join(reversed(trail))
                # Look ahead: if the next char is alphanumeric, this is
                # not yet a complete function name (e.g. "log" in
                # "log10" — wait for "log10" before deciding).
                next_is_alnum = i + 1 < n and (expression[i + 1].isalnum())
                if next_is_alnum:
                    # Don't set prev_was_func_end yet — wait for the
                    # alpha run to complete.
                    prev_was_func_end = False
                else:
                    prev_was_func_end = cand in _IMPLICIT_MUL_FUNCS
            else:
                prev_was_func_end = False
            i += 1

    expression = "".join(result)

    # Postfix factorial: "<n>!" -> "factorial(<n>)". Apply AFTER whitespace
    # removal so we get the bare "<num>!" form. Skip cases like "!=" or
    # is not by requiring the "!" to immediately follow a number or a
    # closing paren (no whitespace between). Handles nested parentheses.
    def _replace_factorial(m: re.Match) -> str:
        content = m.group(1)
        bangs = m.group(2)
        result = f"factorial({content})"
        if len(bangs) > 1:
            result += "!" * (len(bangs) - 1)
        return result

    # Iteratively replace factorial: handle any depth of nesting by
    # repeatedly matching "factorial(...stuff...)!" and wrapping.
    prev = None
    while prev != expression:
        prev = expression
        # Match: number!, (expr)!, or func(args)!
        # The func(args) pattern matches any function call before !
        expression = re.sub(
            r"(\d+(?:\.\d+)?|\((?:[^()]*|\([^()]*\))*\)|[a-zA-Z_]\w*\((?:[^()]*|\([^()]*\))*\))(\!+)",
            _replace_factorial,
            expression,
        )

    return expression


def _join_number_parts(expression: str) -> str:
    """Join space-separated number parts with + operators.

    Detects sequences of space-separated tokens that are all numbers
    (or simple expressions evaluating to numbers) and joins them with +.
    This ensures fallback number sequences like "3 100 20 2" -> "3+100+20+2",
    not "3100202". (Compound numbers like "twenty one" are typically resolved
    earlier by _MULTI_WORD_NUMBERS and never reach this function.)

    Also inserts implicit '*' between adjacent number and non-number non-operator
    tokens (e.g., "sqrt 144" -> "sqrt*144", "2 sqrt 9" -> "2*sqrt*9").
    Operators like '+', '-', '*', '/', '&', '|', '^' are passed through unchanged.
    Unit aliases (e.g., 'm', 'min', 'kg') are NOT treated as function names, so
    no '*' is inserted between a number and a unit (deferred to _preprocess_units).
    """
    tokens = expression.split()
    if len(tokens) <= 1:
        return expression

    # When users space only one side of an operator ("20 *20", "20/ 20"),
    # shell-style whitespace splitting leaves tokens like "*20" or "20/".
    # Treat those as operator+number, not opaque text that triggers implicit
    # multiplication. Keep compact expressions ("20*20") untouched because the
    # later split_at_operators pass already handles them.
    expanded_tokens: list[str] = []
    operator_split_re = re.compile(r"(\*\*|//|<<|>>|(?<![eE])[+\-]|[*/%&|^])")
    boundary_operator_re = re.compile(r"(\*\*|//|<<|>>|(?<![eE])[+\-]|[*/%&|^])")

    def _split_boundary_operators(token: str) -> list[str]:
        """Split operators attached at token edges without tokenizing internals.

        This handles whitespace-derived tokens such as "+(4*5)", "m2+", and
        "m**" while preserving compact expressions like "100cm**2" for the
        later unit preprocessor.
        """
        parts: list[str] = []
        rest = token
        while rest:
            match = boundary_operator_re.match(rest)
            if match and match.end() < len(rest):
                parts.append(match.group(1))
                rest = rest[match.end() :]
                continue
            break

        suffixes: list[str] = []
        while rest:
            op_match: str | None = None
            for op in ("**", "//", "<<", ">>", "+", "-", "*", "/", "%", "&", "|", "^"):
                if rest.endswith(op) and len(rest) > len(op):
                    op_match = op
                    break
            if op_match is None:
                break
            suffixes.append(op_match)
            rest = rest[: -len(op_match)]

        if rest:
            parts.append(rest)
        parts.extend(reversed(suffixes))
        return parts

    for token in tokens:
        if not re.search(r"[A-Za-z_()]", token) and operator_split_re.search(token):
            expanded_tokens.extend(part for part in operator_split_re.split(token) if part)
        elif re.search(r"[A-Za-z_()]", token) and boundary_operator_re.search(token):
            expanded_tokens.extend(_split_boundary_operators(token))
        else:
            expanded_tokens.append(token)
    tokens = expanded_tokens

    # Be tolerant of spaces within two-character symbolic operators, matching
    # existing behavior for "* *" and "/ /" while adding "<<"/">>".
    merged_ops: list[str] = []
    mi = 0
    while mi < len(tokens):
        if mi + 1 < len(tokens) and tokens[mi] == "<" and tokens[mi + 1] == "<":
            merged_ops.append("<<")
            mi += 2
        elif mi + 1 < len(tokens) and tokens[mi] == ">" and tokens[mi + 1] == ">":
            merged_ops.append(">>")
            mi += 2
        else:
            merged_ops.append(tokens[mi])
            mi += 1
    tokens = merged_ops

    _OPERATOR_TOKENS: set[str] = {
        "+",
        "-",
        "*",
        "/",
        "//",
        "**",
        "%",
        "&",
        "|",
        "^",
        "<<",
        ">>",
        "~",
        "(",
        ")",
        "!",
        "IN",
        "TO",
        "MOD",
    }

    def _is_digit_token(tok: str) -> bool:
        stripped = tok.strip('+-')
        return stripped.replace('.', '').replace('e', '').replace('E', '').isdigit()

    def _is_unit_token(tok: str) -> bool:
        return tok in UNIT_ALIASES or tok.lower() in UNIT_ALIASES

    # Pre-merge decimal point sequences: "5" "." "3" -> "5.3"
    # This handles 'point' -> '.' conversions where spaces separate the tokens.
    merged: list[str] = []
    mi = 0
    while mi < len(tokens):
        if (
            _is_digit_token(tokens[mi])
            and mi + 2 < len(tokens)
            and tokens[mi + 1] == "."
            and _is_digit_token(tokens[mi + 2])
        ):
            merged.append(tokens[mi] + "." + tokens[mi + 2])
            mi += 3
        else:
            merged.append(tokens[mi])
            mi += 1
    tokens = merged

    result: list[str] = []
    current_number_seq: list[str] = []

    def _flush_number_seq() -> None:
        if not current_number_seq:
            return
        if len(current_number_seq) == 1:
            result.append(current_number_seq[0])
        else:
            joined = '+'.join(current_number_seq)
            # If this compound is preceded by a leading '-' (from "negative"
            # word conversion), wrap so negation applies to the whole sum:
            # "-(100+1)" not "-100+1". Only triggers when '-' is the sole
            # preceding token (i.e., the compound starts at expression start).
            if len(result) == 1 and result[0] == '-':
                result.pop()
                result.append(f'-({joined})')
            else:
                result.append(joined)
        current_number_seq.clear()

    prev_kind: str | None = None

    for token in tokens:
        if token in _OPERATOR_TOKENS:
            _flush_number_seq()
            result.append(token)
            prev_kind = "op"
        elif _is_digit_token(token):
            if prev_kind == "other" and not _is_unit_token(token):
                result.append("*")
            current_number_seq.append(token)
            prev_kind = "num"
        else:
            _flush_number_seq()
            is_unit = _is_unit_token(token)
            if prev_kind == "num":
                result.append("*")
            elif prev_kind == "unit" and is_unit:
                result.append("*")
            result.append(token)
            prev_kind = "unit" if is_unit else "other"

    _flush_number_seq()
    return ''.join(result)


def _preprocess_units(expression: str) -> str:
    """Preprocess expression to add multiplication before units.

    Emits the canonical form of each unit (via UNIT_ALIASES) so that the
    evaluator's visit_Name lookup is deterministic. E.g., "5in" -> "5*inch"
    (canonical 'inch' instead of alias 'in'), "10 m" -> "10*m", etc.
    Also handles cases where '*' is already present (e.g., "5*in" -> "5*inch").
    """
    result = []
    i = 0
    depth = 0
    units = _UNITS_BY_LENGTH  # Use pre-computed list
    prefixes = _UNIT_PREFIXES  # Use pre-computed prefix set

    while i < len(expression):
        char = expression[i]

        if char == "(":
            depth += 1
            result.append(char)
            i += 1
        elif char == ")":
            depth -= 1
            result.append(char)
            i += 1
        elif char.isdigit():
            # Detect Python integer-literal prefixes (0x..., 0b..., 0o...)
            # and pass the whole literal through unchanged. Without this, the
            # trailing hex/binary/octal digit sequence (e.g., "1F", "0A") is
            # misread as "<num>*<unit>" (F/A = Fahrenheit/Ampere), corrupting
            # the literal into nonsense like "0x1*F".
            if (
                char == "0"
                and i + 1 < len(expression)
                and expression[i + 1] in ("x", "X", "b", "B", "o", "O")
            ):
                j = i + 2
                # Hex letters; binary/octal digits are already matched below.
                while j < len(expression) and (
                    expression[j].isdigit()
                    or expression[j]
                    in ("a", "b", "c", "d", "e", "f", "A", "B", "C", "D", "E", "F", "_")
                ):
                    j += 1
                result.append(expression[i:j])
                i = j
                continue

            # Look for number followed by optional whitespace and unit
            num_start = i
            while i < len(expression) and (expression[i].isdigit() or expression[i] == "."):
                i += 1
            num = expression[num_start:i]

            # Skip whitespace between number and unit
            while i < len(expression) and expression[i].isspace():
                i += 1

            if i < len(expression):
                remaining = expression[i:]
                # Check for unit using pre-computed sorted list
                found_unit = False
                for unit in units:
                    if remaining.startswith(unit):
                        # Word boundary check: next char after unit must not be alphanumeric
                        end_pos = len(unit)
                        if end_pos < len(remaining) and remaining[end_pos].isalnum():
                            continue
                        # Emit the canonical form (e.g., "in" -> "inch") so
                        # the evaluator doesn't depend on the alias ordering.
                        canonical = UNIT_ALIASES.get(unit, unit)
                        # If the next non-whitespace token is "**", the unit
                        # is being exponentiated. Wrap "<num>*<unit>" in
                        # parens so the unit participates in the exponent,
                        # not the base: "5m ** 2" -> "(5*m)**2" = 25 m**2.
                        # Without the parens, "5*m**2" parses as
                        # "5*(m**2)" and the unit's own value (1) makes
                        # the multiplication a no-op.
                        k = i + len(unit)
                        while k < len(expression) and expression[k].isspace():
                            k += 1
                        if (
                            k + 1 < len(expression)
                            and expression[k] == "*"
                            and expression[k + 1] == "*"
                        ):
                            result.append("(")
                            result.append(num)
                            result.append("*")
                            result.append(canonical)
                            result.append(")")
                        else:
                            result.append(num)
                            result.append("*")
                            result.append(canonical)
                        i += len(unit)
                        found_unit = True
                        break
                # Handle lowercase temperature units (f, c, k)
                if not found_unit and remaining:
                    first_char = remaining[0]
                    if first_char.lower() in _LOWERCASE_TEMP_UNITS:
                        # Skip if this looks like a hex literal (0x...) —
                        # the 'f'/'c'/'k' suffix is part of the hex digits,
                        # not a temperature unit.
                        is_hex = len(result) >= 2 and result[-1] in ("x", "X") and result[-2] == "0"
                        if not is_hex:
                            temp_canonical = _LOWERCASE_TEMP_UNITS[first_char.lower()]
                            # If followed by "**", wrap "<num>*<unit>" in
                            # parens so the unit participates in the
                            # exponent: "5c ** 2" -> "(5*C)**2" = 25 C**2.
                            k = i + 1
                            while k < len(expression) and expression[k].isspace():
                                k += 1
                            if (
                                k + 1 < len(expression)
                                and expression[k] == "*"
                                and expression[k + 1] == "*"
                            ):
                                result.append("(")
                                result.append(num)
                                result.append("*")
                                result.append(temp_canonical)
                                result.append(")")
                            else:
                                result.append(num)
                                result.append("*")
                                result.append(temp_canonical)
                            i += 1
                            found_unit = True
                if not found_unit:
                    result.append(num)
            else:
                result.append(num)
        elif (
            char == "*"
            and result
            and (result[-1][-1:].isdigit() or result[-1][-1:] == ")")
            and i + 1 < len(expression)
        ):
            # "*" preceded by a digit. Check if the next alpha-only token is a
            # unit alias. Find the longest prefix that matches a unit alias.
            # (E.g., for "5*inTOcm", find "in" even though "i" alone isn't a unit.)
            result.append("*")
            i += 1
            unit_tok = ""
            j = i
            best_end = i
            while j < len(expression) and expression[j].isalpha():
                candidate = expression[i : j + 1]
                if candidate in UNIT_ALIASES or candidate.lower() in UNIT_ALIASES:
                    unit_tok = candidate
                    best_end = j + 1
                    j += 1
                else:
                    j += 1
                    # Don't break; keep trying longer prefixes in case a longer
                    # one matches (e.g., "in" matches even though "i" doesn't).
                    # But stop if we've clearly passed any plausible unit length
                    # (units are typically <= 20 chars).
                    if j - i > 25:
                        break
            if unit_tok:
                # Word boundary check: the next char after the unit must not be
                # alphanumeric, otherwise this is a function name (e.g., "log",
                # "lcm", "round"), not a unit.
                if best_end < len(expression) and expression[best_end].isalnum():
                    # Not a unit; emit the first char as-is
                    if i < len(expression) and expression[i].isalpha():
                        result.append(expression[i])
                        i += 1
                else:
                    canonical = UNIT_ALIASES.get(
                        unit_tok, UNIT_ALIASES.get(unit_tok.lower(), unit_tok)
                    )
                    result.append(canonical)
                    i = best_end
            else:
                # Not a unit alias; emit as-is
                if i < len(expression) and expression[i].isalpha():
                    result.append(expression[i])
                    i += 1
        else:
            result.append(char)
            i += 1

    return _add_same_unit_division_parens("".join(result))


def _peek_alpha_token_back(result_list: list[str]) -> str:
    """Return the trailing alpha-only run from a list of characters.

    Used to detect a preceding identifier in the implicit-mul whitespace
    loop. For example, after emitting 'p', 'i' the previous token is
    'pi' and we can decide whether to insert '*' before the next token.
    Returns the empty string if the list is empty or the trailing run
    is not a contiguous alpha sequence.
    """
    trail: list[str] = []
    for c in reversed(result_list):
        if c.isalpha():
            trail.append(c)
        else:
            break
    return "".join(reversed(trail))


def _peek_alnum_token_back(result_list: list[str]) -> str:
    """Return the trailing identifier-like alnum run from a character list."""
    trail: list[str] = []
    for c in reversed(result_list):
        if c.isalnum() or c == "_":
            trail.append(c)
        else:
            break
    return "".join(reversed(trail))


def _add_same_unit_division_parens(expression: str) -> str:
    """Wrap the denominator in parentheses for unit-on-division-right.

    Detects patterns like "5*m/3*s" or "10*km/5*hr" where the right
    operand of a division has a trailing unit, and wraps the entire
    right operand in parens to preserve correct operator precedence.
    Without this fix, "5*m/3*s" parses as "((5*m)/3)*s" which yields
    the wrong unit "m*s" instead of "m/s".

    Also handles same-unit division: "5*m/3*m" -> "5*m/(3*m)" so the
    units cancel and the result is dimensionless.
    """

    unit_token = r"(?:[^\W\d]\w*)(?:/(?:[^\W\d]\w*))*"
    number_token = _DECIMAL_NUMBER_TOKEN_RE
    canonical_units = set(UNIT_ALIASES.values())

    def _is_known_unit(unit: str) -> bool:
        return unit in canonical_units or unit in UNIT_ALIASES

    def _replace_unit_left(match: re.Match) -> str:
        left_unit = match.group(1)
        denom = match.group(2)
        right_unit = match.group(3)
        if not (_is_known_unit(left_unit) and _is_known_unit(right_unit)):
            return match.group(0)
        # Always wrap the denominator in parens so the trailing unit
        # is bound to the right operand, not pulled out as a
        # postfix multiplication. This makes "5*m/3*s" evaluate as
        # "5*m/(3*s)" = "1.666... m/s" instead of the buggy
        # "((5*m)/3)*s" = "1.666... m*s".
        return f"{left_unit}/({denom}*{right_unit})"

    def _replace_scalar_left(match: re.Match) -> str:
        numerator = match.group(1)
        denom = match.group(2)
        right_unit = match.group(3)
        if not _is_known_unit(right_unit):
            return match.group(0)
        return f"{numerator}/({denom}*{right_unit})"

    expression = re.sub(
        rf"(?<!\w)({unit_token})/({number_token})\*({unit_token})(?!\w)",
        _replace_unit_left,
        expression,
    )
    return re.sub(
        rf"(?<![\w.])({number_token})/({number_token})\*({unit_token})(?!\w)",
        _replace_scalar_left,
        expression,
    )


def _add_unit_floor_mod_parens(expression: str) -> str:
    """Wrap unit operands around floor division and modulo.

    After unit preprocessing, "7m/s//1s" becomes "7*m/s//1*s". Python parses
    that as "((7*m)/s)//1*s", which incorrectly multiplies the result by the
    trailing "s". Wrapping both operands preserves the intended unit grouping.
    """

    number_token = _DECIMAL_NUMBER_TOKEN_RE
    unit_atom = r"[a-zA-Z_][a-zA-Z0-9_]*(?:\*\*-?\d+)?"
    unit_expr = rf"{unit_atom}(?:(?:\*(?!\*)|/){unit_atom})*"
    unit_operand = rf"{number_token}\*{unit_expr}"

    chain = rf"{unit_operand}(?:(?://|%){unit_operand})+"

    def _replace(match: re.Match) -> str:
        parts = re.split(r"(//|%)", match.group(0))
        grouped = f"({parts[0]}){parts[1]}({parts[2]})"
        for i in range(3, len(parts), 2):
            grouped = f"({grouped}){parts[i]}({parts[i + 1]})"
        return grouped

    return re.sub(rf"(?<![\w.])({chain})(?![\w.])", _replace, expression)


def _handle_unit_conversion_from_tokens(tokens: list) -> list:
    """Handle unit conversion patterns from tokens like ['2 meters', 'in', 'feet'].

    Detects patterns like:
    - [number+unit, 'in'/'to'/'into'/'as', target_unit] -> convert(number*unit, target_unit)
    - [number, 'in'/'to'/'into'/'as', target_unit] -> convert(number, target_unit) (treated as multiply)
    - [number, '*', unit, 'in'/'to'/'into'/'as', target_unit] -> convert(number*unit, target_unit)
      (e.g., from "5 in to cm" -> tokens ['5', '*', 'in', 'TO', 'cm'])
    """
    if len(tokens) < 3:
        return tokens

    for i in range(len(tokens) - 2):
        token = tokens[i]
        from_unit = None
        from_unit_normalized = None
        num_part = None
        advance = 1  # How many tokens to skip after the conversion
        for unit in _UNITS_BY_LENGTH:
            if token.endswith(unit):
                num_part = token[: -len(unit)]
                if num_part and num_part[-1].isdigit():
                    from_unit = unit
                    from_unit_normalized = UNIT_ALIASES.get(from_unit, from_unit)
                    break
        if from_unit is None:
            last_char = token[-1:] if token else ""
            if last_char.lower() in _LOWERCASE_TEMP_UNITS:
                candidate_num = token[:-1]
                if candidate_num and candidate_num[-1].isdigit():
                    from_unit = last_char
                    from_unit_normalized = _LOWERCASE_TEMP_UNITS[last_char.lower()]
                    num_part = candidate_num

        # Pattern: <num> '*' <unit> <IN/TO> <target>  (e.g., ['5', '*', 'in', 'TO', 'cm'])
        if (
            from_unit is None
            and token
            and (token[0].isdigit() or token[0] == "-")
            and token[-1].isdigit()
            and i + 2 < len(tokens)
            and tokens[i + 1] == "*"
        ):
            unit_token = tokens[i + 2]
            if unit_token in UNIT_ALIASES or unit_token.lower() in UNIT_ALIASES:
                from_unit = unit_token
                from_unit_normalized = UNIT_ALIASES.get(unit_token, unit_token)
                if from_unit_normalized == unit_token:
                    from_unit_normalized = UNIT_ALIASES.get(unit_token.lower(), unit_token)
                num_part = token
                advance = 3  # Skip '*' and the unit token

        # Bare-number source: e.g., tokens[i] is just "1" (no unit suffix)
        bare_number = False
        if (
            from_unit is None
            and token
            and (token[0].isdigit() or token[0] == "-")
            and token[-1].isdigit()
        ):
            try:
                float(token)
                bare_number = True
                num_part = token
                from_unit_normalized = ""
            except ValueError:
                pass

        if from_unit is not None or bare_number:
            next_idx = i + advance
            if next_idx >= len(tokens):
                continue
            conv_word = tokens[next_idx].upper()
            if conv_word in {"IN", "TO"}:
                to_idx = next_idx + 1
                if to_idx >= len(tokens):
                    continue
                to_token = tokens[to_idx]
                to_unit_normalized = None

                for unit2 in _UNITS_BY_LENGTH:
                    if to_token == unit2 or to_token.endswith(unit2):
                        to_unit_normalized = UNIT_ALIASES.get(unit2, unit2)
                        break
                if to_unit_normalized is None and to_token.lower() in _LOWERCASE_TEMP_UNITS:
                    to_unit_normalized = _LOWERCASE_TEMP_UNITS[to_token.lower()]

                if bare_number:
                    if to_unit_normalized:
                        new_tokens = (
                            tokens[:i]
                            + [f"{num_part}*{to_unit_normalized}"]
                            + tokens[next_idx + 2 :]
                        )
                        return new_tokens
                elif to_unit_normalized and from_unit_normalized in UNIT_ALIASES:
                    from .units import are_units_compatible, get_unit_category

                    cat1 = get_unit_category(from_unit_normalized)
                    cat2 = get_unit_category(to_unit_normalized)

                    if (
                        cat1
                        and cat2
                        and are_units_compatible(from_unit_normalized, to_unit_normalized)
                    ):
                        new_tokens = (
                            tokens[:i]
                            + [f"convert({num_part}*{from_unit_normalized},{to_unit_normalized})"]
                            + tokens[next_idx + 2 :]
                        )
                        return new_tokens

    return tokens


def normalize_expression(
    expression: str,
    operators: dict,
    patterns: Mapping[str, Pattern[str]],
    skip_validation: bool = False,
) -> tuple[str, int]:
    """Normalize an expression without evaluating it.

    This is useful when you want to use a custom evaluator.

    Args:
        expression: The raw expression to normalize
        operators: The operators configuration dict
        patterns: The compiled regex patterns dict
        skip_validation: If True, skip token validation (for custom evaluators)

    Returns:
        tuple: (normalized_expression, exit_code) - normalized_expression is the
               normalized string, exit_code is 0 on success, non-zero on error
    """
    if not expression or not expression.strip():
        return "", 1
    if len(expression) > MAX_INPUT_LENGTH:
        return f"Error: Input too long (max {MAX_INPUT_LENGTH} characters)", 2

    expression = normalize(expression, operators, patterns)

    if len(expression) > MAX_NORMALIZED_LENGTH:
        return f"Error: Normalized expression too long (max {MAX_NORMALIZED_LENGTH} characters)", 2
    tokens = split_at_operators(expression, operators, patterns)
    tokens, is_valid = convert_from_human_handler(tokens, operators, patterns, expression)

    if not is_valid:
        return "", 1

    tokens = _combine_consecutive_numbers(tokens, operators, patterns)
    tokens = apply_math_functions(tokens, operators, patterns)

    # Handle unit conversion patterns from tokens (e.g., "2m in feet" -> tokens ['2m', 'in', 'feet'])
    tokens = _handle_unit_conversion_from_tokens(tokens)
    joined = "".join(tokens)

    joined = _preprocess_units(joined)

    joined = _add_unit_floor_mod_parens(joined)

    if not skip_validation:
        try:
            validate_for_eval(tokens, patterns)
        except ValueError:
            return "", 1

    return joined, 0


def run(
    expression: str,
    operators: dict,
    patterns: Mapping[str, Pattern[str]],
    output_format: str = "plain",
    show_expression: bool = True,
) -> tuple[Any, int]:
    """Process a single expression: normalize, convert, evaluate, and print result.

    Returns:
        tuple: (result, exit_code) - result is the evaluated value or None on error
    """
    original = expression
    try:
        joined, exit_code = normalize_expression(expression, operators, patterns)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return None, 1
    except Exception as e:
        error_message(original, e)
        return None, 1

    if exit_code != 0:
        if exit_code == 2:
            print(joined, file=sys.stderr)
        return None, exit_code

    try:
        result = evaluate(joined)
        display = str(result)
        if output_format == "json":
            import json

            print(json.dumps({"expression": joined, "result": display}))
        else:
            print(display)
        return result, 0
    except ZeroDivisionError as e:
        error_message(original, e)
        return None, 1
    except EvaluationError as e:
        error_message(original, e)
        return None, 1
    except Exception as e:
        error_message(original, e)
        return None, 1


def _run_repl(show_expression: bool = True) -> int:
    """Run interactive REPL mode."""

    import atexit
    import os

    try:
        import readline
    except ImportError:
        readline = None  # type: ignore[assignment]

    print("eggcalc interactive mode. Type 'help' for available commands, 'quit' or 'exit' to exit.")
    print()

    history: list[tuple[str, Any]] = []

    history_path = os.path.expanduser("~/.eggcalc_history")
    if readline is not None:
        try:
            readline.read_history_file(history_path)
        except OSError:
            pass

        def _save_history() -> None:
            try:
                readline.write_history_file(history_path)
                os.chmod(history_path, 0o600)
            except OSError:
                pass

        atexit.register(_save_history)

    MAX_REPL_LINE_LENGTH = 100_000
    while True:
        try:
            line = input(">>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if len(line) > MAX_REPL_LINE_LENGTH:
            print(f"Input too long ({len(line)} chars, max {MAX_REPL_LINE_LENGTH})")
            continue

        if not line:
            continue

        if line.lower() in ("quit", "quit()", "exit", "exit()"):
            break

        if line.lower() == "help":
            print_help()
            continue

        if line.lower() == "history":
            for expr, result in history:
                print(f"{expr} = {result}")
            continue

        if line.lower() == "clear":
            history.clear()
            continue

        try:
            result, exit_code = run(line, NORMALIZE, PATTERNS, "plain", show_expression)
        except KeyboardInterrupt:
            print()
            continue

        if exit_code == 0 and result is not None:
            history.append((line, result))

    return 0


def _get_units_by_category() -> dict[str, list[str]]:
    """Get units organized by category from UNIT_CATEGORIES."""
    categories: dict[str, set[str]] = {}
    for unit, category in UNIT_CATEGORIES.items():
        if category not in categories:
            categories[category] = set()
        categories[category].add(unit)
    # Sort units within each category
    result = {}
    for cat in sorted(categories.keys()):
        result[cat] = sorted(categories[cat])
    return result


def print_help() -> None:
    """Print available operators, functions, and units."""
    # Get units by category programmatically
    units_by_cat = _get_units_by_category()

    lines = [
        "Usage:",
        "  calc <expression>          Evaluate math expression",
        "  calc inspect <text>       Check for hidden characters/confusables",
        "  calc count <text>         Count characters (or count <text> <char>)",
        "  calc regex <pat> <text>  Test regex pattern against text",
        "",
        "Text tools:",
        "  calc replace-check <old> ||| <new> ||| <text>",
        "  calc lines <start[-end]> <text>",
        "  calc patch-check <original> ||| <patch>",
        "  calc shell-split <command>",
        "  calc md-structure <text>",
        "  calc dotenv-check <text>",
        "",
        "Flags:",
        "  --json                    Output result as JSON",
        "",
        "Operators:",
        "  Arithmetic: +  -  *  /  **",
        "  Words: plus, minus, times, divided by, over, raised to",
        "",
        "Functions:",
        "  Trigonometry: sin, cos, tan, asin, acos, atan, atan2",
        "  Hyperbolic: sinh, cosh, tanh, asinh, acosh, atanh",
        "  Logarithmic: log, log10, log2, log1p, exp, expm1",
        "  Rounding: abs, floor, ceil, trunc, round, sign",
        "  Other: sqrt, pow, factorial, gcd, lcm, mean, median",
        "",
        "Constants:",
        "  pi, e, tau",
        "  avogadro, gasconstant, planck, boltzmann",
        "  c (speed of light), elementarycharge, faraday, amu",
        "",
        "Units:",
    ]

    unit_lines = []
    for category, units in units_by_cat.items():
        if len(units) > 15:
            display_units = units[:12] + ["..."]
        else:
            display_units = units
        unit_lines.append(f"  {category.capitalize()}: {', '.join(display_units)}")

    lines += unit_lines + [
        "",
        "Unit conversion examples:",
        "  calc 30m + 100ft",
        "  calc 1km in miles",
        "  calc 100F to C",
        "  calc 1kg in lb",
        "",
        "Text tools examples:",
        '  calc inspect "hello"',
        "  calc inspect \"p\u0430ypal\"  ( Cyrillic 'a' instead of Latin)",
        '  calc count "hello world"',
        '  calc count "hello" l',
        '  calc regex "^\\d+$" "12345"',
        '  calc replace-check "foo" ||| "bar" ||| "foo baz foo"',
        '  calc lines 2-4 "line1\\nline2\\nline3\\nline4\\nline5"',
        '  calc shell-split "git commit -m \\"fix\\""',
        '  calc md-structure "# Hello\\n\\nA [link](http://x.com)"',
        '  calc dotenv-check "DB_HOST=localhost\\nDB_PORT=5432"',
        "",
        "All text commands support --json for machine-readable output.",
    ]

    for line in lines:
        print(line)


_DELIM = "|||"


def _cli_text_command(expression: str, json_output: bool = False) -> int:
    """Handle text commands before math evaluation.

    Returns:
        0 if command was handled, 1 if expression should continue to math eval
    """
    parts = expression.strip().split()
    if not parts:
        return 1

    cmd = parts[0].lower()

    if cmd == "inspect":
        if len(parts) < 2:
            print("Usage: calc inspect <text>", file=sys.stderr)
            return 1
        text = " ".join(parts[1:])
        try:
            result: Any = inspect_text(text, include_codepoints=False, include_confusables=True)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        if json_output:
            import json

            print(json.dumps(result))
            return 0

        if result["warnings"]:
            for w in result["warnings"]:
                kind = w["kind"].upper()
                print(f"\u2717 {kind}: {w['message']}")
        else:
            print("\u2713 No hidden characters")

        if result["confusables"]:
            print(f"\nConfusables found: {len(result['confusables'])}")
            for c in result["confusables"][:5]:
                print(f"  '{c['char']}' (looks like '{c['confusable_with']}') at {c['index']}")
        return 0

    if cmd == "count":
        if len(parts) < 2:
            print("Usage: calc count <text> [char]", file=sys.stderr)
            return 1
        text = " ".join(parts[1:])

        # Check if last part is a single char to count
        if len(parts) >= 3 and len(parts[-1]) == 1:
            char = parts[-1]
            text = " ".join(parts[1:-1])
            try:
                result = count_chars(text, target=char)
            except ValueError as e:
                print(f"Error: {e}", file=sys.stderr)
                return 1
            if json_output:
                import json

                print(json.dumps(result))
                return 0
            print(f"'{char}' appears {result['count']} time(s) in \"{text}\"")
            return 0

        # Default: show frequency table for multi-word, simple count for single
        try:
            if " " in text:
                result = count_chars(text)
                if json_output:
                    import json

                    print(json.dumps(result))
                    return 0
                if isinstance(result, dict):
                    print(f"\"{text}\":")
                    print(f"  {len(text)} characters")
                    sorted_chars = sorted(result.items(), key=lambda x: (-x[1], x[0]))
                    for char, count in sorted_chars[:10]:
                        display = repr(char) if char != " " else "(space)"
                        print(f"  {display}: {count}")
                    if len(result) > 10:
                        print(f"  ... and {len(result) - 10} more unique chars")
                return 0
            else:
                result = count_chars(text)
                if json_output:
                    import json

                    print(json.dumps(result))
                    return 0
                print(f"\"{text}\": {len(text)} character(s)")
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        return 0

    if cmd == "regex":
        if len(parts) < 3:
            print("Usage: calc regex <pattern> <text>", file=sys.stderr)
            return 1
        pattern = parts[1]
        text = " ".join(parts[2:])
        try:
            result = regex_test(pattern, [text])
        except re.error as e:
            print(f"Error: Invalid regex pattern: {e}", file=sys.stderr)
            return 1

        if not result["valid_pattern"]:
            print(f"\u2717 Invalid regex pattern: {pattern}", file=sys.stderr)
            return 1

        if json_output:
            import json

            print(json.dumps(result))
            return 0

        if result["results"]:
            r = result["results"][0]
            if r["matches"]:
                print(f"\u2713 Match: '{r['sample']}'")
                if r["groups"]:
                    print(f"  Groups: {r['groups']}")
                if r["groupdict"]:
                    print(f"  Named groups: {r['groupdict']}")
            else:
                print("\u2717 No match")
        else:
            print("\u2717 No match")
        return 0

    if cmd == "replace-check":
        if _DELIM not in expression:
            print(
                f"Usage: calc replace-check <old> {_DELIM} <new> {_DELIM} <text>", file=sys.stderr
            )
            return 1
        raw = expression[len(cmd) :].strip()
        segments = raw.split(_DELIM)
        if len(segments) < 3:
            print(
                f"Usage: calc replace-check <old> {_DELIM} <new> {_DELIM} <text>", file=sys.stderr
            )
            return 1
        old = segments[0].strip()
        new = segments[1].strip()
        text = segments[2].strip()
        try:
            result = text_replace_check(text, old, new, return_preview=True)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        if json_output:
            import json

            print(json.dumps(result))
            return 0

        count = result["match_count"]
        if count == 0:
            print("\u2717 No match for replacement.")
        elif count == 1:
            print("\u2713 Replacement would apply cleanly to 1 match.")
        else:
            print(f"\u221d Replacement is ambiguous: {count} matches found.")
        for f in result["findings"]:
            print(f"  {f['kind']}: {f['message']}")
        return 0

    if cmd == "lines":
        # Split into at most 3 parts to preserve text content (including newlines)
        split_parts = expression.strip().split(None, 2)
        if len(split_parts) < 3:
            print("Usage: calc lines <start[-end]> <text>", file=sys.stderr)
            return 1
        range_str = split_parts[1]
        text = split_parts[2]
        # Parse range: "1-5" or just "3" (single line)
        if "-" in range_str:
            try:
                start_str, end_str = range_str.split("-", 1)
                start_line = int(start_str)
                end_line = int(end_str)
            except ValueError:
                print(f"Error: Invalid line range '{range_str}'", file=sys.stderr)
                return 1
        else:
            try:
                start_line = int(range_str)
                end_line = start_line
            except ValueError:
                print(f"Error: Invalid line number '{range_str}'", file=sys.stderr)
                return 1
        try:
            result = line_range_extract(text, start_line, end_line, include_line_numbers=True)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        if json_output:
            import json

            print(json.dumps(result))
            return 0

        if not result["valid_range"]:
            for f in result["findings"]:
                print(f"  {f['kind']}: {f['message']}")
            return 1
        for line_info in result["lines"]:
            num = line_info.get("line", "")
            content = line_info.get("text", "")
            print(f"{num}: {content}")
        return 0

    if cmd == "patch-check":
        if _DELIM not in expression:
            print(f"Usage: calc patch-check <original> {_DELIM} <patch>", file=sys.stderr)
            return 1
        raw = expression[len(cmd) :].strip()
        segments = raw.split(_DELIM, 1)
        if len(segments) < 2:
            print(f"Usage: calc patch-check <original> {_DELIM} <patch>", file=sys.stderr)
            return 1
        original = segments[0].strip()
        patch_text = segments[1].strip()
        try:
            result = patch_apply_check(original, patch_text)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        if json_output:
            import json

            print(json.dumps(result))
            return 0

        if not result["patch_parse_ok"]:
            print("\u2717 Failed to parse patch.")
            for f in result["findings"]:
                print(f"  {f}")
            return 1
        total = result["hunks_total"]
        applied = result["hunks_applied"]
        failed = result["hunks_failed"]
        if result["applies"]:
            print(f"\u2713 Patch applies cleanly. {applied}/{total} hunks applied.")
        else:
            print(f"\u2717 Patch fails: {failed}/{total} hunks failed.")
        for f in result["findings"]:
            print(f"  {f}")
        return 0

    if cmd == "shell-split":
        if len(parts) < 2:
            print("Usage: calc shell-split <command>", file=sys.stderr)
            return 1
        command = " ".join(parts[1:])
        try:
            result = shell_split(command)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        if json_output:
            import json

            print(json.dumps(result))
            return 0

        if not result["parse_ok"]:
            print("\u2717 Parse failed.")
            for f in result["findings"]:
                print(f"  {f}")
            return 1
        argv = result["argv"]
        print(f"Parsed {result['argc']} token(s): {argv}")
        features = result["features"]
        active = [k.replace("has_", "") for k, v in features.items() if v]
        if active:
            print(f"Contains: {', '.join(active)}")
        for f in result["findings"]:
            print(f"  {f}")
        return 0

    if cmd == "md-structure":
        # Split into at most 2 parts to preserve text content (including newlines)
        split_parts = expression.strip().split(None, 1)
        if len(split_parts) < 2:
            print("Usage: calc md-structure <text>", file=sys.stderr)
            return 1
        text = split_parts[1]
        try:
            result = markdown_structure(text)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        if json_output:
            import json

            print(json.dumps(result))
            return 0

        headings = result["headings"]
        fences = result["code_fences"]
        links = result["links"]
        unclosed = [f for f in fences if not f["closed"]]
        parts_out = []
        if headings:
            parts_out.append(f"{len(headings)} heading(s)")
        if fences:
            label = "code fence(s)" if len(fences) != 1 else "code fence"
            if unclosed:
                parts_out.append(f"{len(fences)} {label} ({len(unclosed)} unclosed)")
            else:
                parts_out.append(f"{len(fences)} {label}")
        if links:
            parts_out.append(f"{len(links)} link(s)")
        if result["frontmatter"]["present"]:
            parts_out.append(f"frontmatter ({result['frontmatter']['format']})")
        if result["tables_detected"]:
            parts_out.append("table(s)")
        if parts_out:
            print(f"Markdown contains: {', '.join(parts_out)}.")
        else:
            print("Markdown is empty or has no structural elements.")
        for f in result["findings"]:
            print(f"  {f}")
        return 0

    if cmd == "dotenv-check":
        if len(parts) < 2:
            print("Usage: calc dotenv-check <text>", file=sys.stderr)
            return 1
        text = " ".join(parts[1:])
        try:
            result = dotenv_validate(text)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        if json_output:
            import json

            print(json.dumps(result))
            return 0

        entries = result["entries"]
        if result["parse_ok"] and not result["invalid_lines"]:
            print(f"\u2713 Valid .env: {len(entries)} entry/entries.")
        else:
            print(f"\u2717 Invalid .env: {len(result['invalid_lines'])} invalid line(s).")
        for f in result["findings"]:
            print(f"  {f}")
        return 0

    return 1  # Not a text command, continue to math eval


def main() -> int:
    """Main entry point for CLI."""
    import os
    import signal

    import eggcalc

    try:
        signal.signal(signal.SIGPIPE, signal.SIG_IGN)
    except (AttributeError, OSError):
        pass

    def _sigterm_handler(signum: int, frame: object) -> None:
        raise SystemExit(0)

    try:
        signal.signal(signal.SIGTERM, _sigterm_handler)
    except (AttributeError, OSError):
        pass

    parser = argparse.ArgumentParser(
        description="Natural language math expression calculator",
        add_help=False,
    )
    parser.add_argument(
        "expression", nargs="*", help="Expression to evaluate (e.g., 'five plus two')"
    )
    parser.add_argument(
        "-h", "--help", action="store_true", help="Show help and available operators"
    )
    parser.add_argument(
        "--usage", action="store_true", help="Show full usage information and examples"
    )
    parser.add_argument("-v", "--version", action="store_true", help="Show version information")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress expression in output")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Accepted for compatibility; plain output remains result-only",
    )
    parser.add_argument("--json", action="store_true", help="Output result as JSON")
    parser.add_argument(
        "-e",
        "--expression",
        dest="single_expr",
        metavar="<expr>",
        help="Evaluate a single expression (useful for piping)",
    )
    parser.add_argument(
        "-i", "--interactive", action="store_true", help="Start interactive REPL mode"
    )
    parser.add_argument(
        "-s",
        "--show",
        action="store_true",
        help="Accepted for compatibility; plain output remains result-only",
    )
    parser.add_argument("--mcp", action="store_true", help="Run as MCP server for exact text tools")
    parser.add_argument(
        "--mcp-profile",
        default=None,
        help="MCP profile to use (default: full, or EGGCALC_MCP_PROFILE env var)",
    )
    parser.add_argument(
        "--mcp-schema-detail",
        default=None,
        choices=["compact", "normal", "full"],
        help="MCP schema detail level (default: full, or EGGCALC_MCP_SCHEMA_DETAIL env var)",
    )

    args = parser.parse_args()

    if args.mcp:
        if args.mcp_profile:
            from eggcalc.mcp.server import set_active_profile

            set_active_profile(args.mcp_profile)
        if args.mcp_schema_detail:
            from eggcalc.mcp.server import set_schema_detail

            set_schema_detail(args.mcp_schema_detail)
        from eggcalc.mcp.server import mcp_main

        return mcp_main()

    if args.version:
        print(f"eggcalc {eggcalc.__version__}")
        return 0

    if args.usage:
        print_help()
        return 0

    if args.help or (not args.expression and not args.single_expr and not args.interactive):
        parser.print_help()
        return 0

    if args.interactive:
        return _run_repl(show_expression=True)

    if args.single_expr:
        expression = args.single_expr
        quiet_by_default = True
    else:
        expression = " ".join(args.expression)
        quiet_by_default = False

    # Detect shell glob expansion (e.g., "python eggcalc.py 30 * 3" expands "*" to files)
    if args.expression and len(args.expression) > 1:
        # Check if any argument is a file or directory that exists (likely from glob expansion)
        cwd = os.getcwd()
        glob_indicators = []
        for arg in args.expression:
            path = os.path.join(cwd, arg)
            if (
                os.path.exists(path)
                and arg not in (".", "..")
                and not arg.startswith("./")
                and not arg.startswith("../")
            ):
                glob_indicators.append(arg)

        if glob_indicators:
            error_lines = [
                "Error: Possible shell glob expansion detected.",
                f"The '*' character was expanded to file(s): {glob_indicators[:5]}{'...' if len(glob_indicators) > 5 else ''}",
                "Please quote your expression:",
                f'  calc "{" ".join(args.expression)}"',
                "Or use -e flag:",
                f'  calc -e "{" ".join(args.expression)}"',
            ]
            for line in error_lines:
                print(line, file=sys.stderr)
            return 1

    # Try text commands first (inspect, count, regex, etc.)
    cmd_result = _cli_text_command(expression, json_output=args.json)
    if cmd_result == 0:
        return 0  # Command was handled

    output_format = "json" if args.json else "plain"
    show_expression = not args.quiet and ((args.verbose or args.show) or not quiet_by_default)

    _, exit_code = run(expression, NORMALIZE, PATTERNS, output_format, show_expression)
    return exit_code


if __name__ == "__main__":
    main()
