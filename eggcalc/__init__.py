"""
eggcalc - Natural language math expression calculator.

A calculator that accepts natural language expressions and converts them
to mathematical expressions that can be evaluated.

Usage:
    python -m eggcalc "five plus two"
    python -m eggcalc "30m + 100ft"
    python -m eggcalc --help
    python -m eggcalc -i  # Interactive REPL mode

Library usage:
    from eggcalc import evaluate, EvaluationError, UnitValue
    result = evaluate("5 + 3")

    # For webapps with caching:
    from eggcalc import EggCalcApp
    app = EggCalcApp(cache_size=1024)
    result = app.calculate("five plus two")

Note: load_user_config_extended() is not exported as custom number/operator
words via external config are not officially supported.
"""

from .evaluator import (
    DEFAULT_CACHE_SIZE,
    MAX_EXPONENT,
    MAX_FACTORIAL,
    MAX_RESULT_VALUE,
    EggCalcApp,
    EvaluationError,
    Memory,
    TimeoutError,
    clearvars,
    delvar,
    evaluate,
    evaluate_async,
    evaluate_cached,
    evaluate_raw,
    evaluate_with_timeout,
    get_default_evaluator,
    getvar,
    listvars,
    load_user_config,
    memory_add,
    memory_clear,
    memory_list,
    memory_recall,
    memory_store,
    memory_subtract,
    register_constant,
    register_function,
    setvar,
)
from .normalize import (
    MAX_INPUT_LENGTH,
    MAX_NESTING_DEPTH,
    NORMALIZE,
    PATTERNS,
    main,
    normalize_expression,
    normalize_text,
    print_help,
    run,
)
from .units import (
    FLOAT_EPSILON,
    UnitValue,
    are_units_compatible,
    get_all_units,
    get_conversion_factor,
    get_unit_category,
    is_unit,
    normalize_unit,
)

__version__ = "1.1.4"
__author__ = "David Bowman"

__all__ = [
    # Core evaluation
    "evaluate",
    "evaluate_raw",
    "evaluate_cached",
    "evaluate_async",
    "evaluate_with_timeout",
    # Exceptions
    "EvaluationError",
    "TimeoutError",
    # Types
    "UnitValue",
    "Memory",
    # CLI
    "main",
    "run",
    "normalize_text",
    "normalize_expression",
    "print_help",
    # Constants
    "NORMALIZE",
    "PATTERNS",
    "MAX_INPUT_LENGTH",
    "MAX_NESTING_DEPTH",
    "MAX_EXPONENT",
    "MAX_FACTORIAL",
    "MAX_RESULT_VALUE",
    "DEFAULT_CACHE_SIZE",
    # Unit utilities
    "normalize_unit",
    "get_conversion_factor",
    "get_all_units",
    "is_unit",
    "get_unit_category",
    "are_units_compatible",
    "FLOAT_EPSILON",
    # Configuration
    "load_user_config",
    "get_default_evaluator",
    "register_constant",
    "register_function",
    # Webapp
    "EggCalcApp",
    # Memory functions
    "memory_store",
    "memory_recall",
    "memory_add",
    "memory_subtract",
    "memory_clear",
    "memory_list",
    # Variable functions
    "setvar",
    "getvar",
    "delvar",
    "listvars",
    "clearvars",
]

import os as _os

if not _os.environ.get("EGGCALC_NO_CONFIG", ""):
    load_user_config()
