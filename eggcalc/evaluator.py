"""
Safe AST-based expression evaluator for eggcalc.

Provides a secure way to evaluate mathematical expressions without
using the unsafe eval() function. Supports arithmetic operations,
trigonometric functions, logarithms, constants, and unit conversions.
"""

from __future__ import annotations

import ast
import cmath
import contextvars
import logging
import math
import multiprocessing
import os
import random
import re
import threading
from collections import OrderedDict
from queue import Empty as _QueueEmpty
from typing import Any, cast

from .units import (
    UNIT_ALIASES,
    UNIT_CONVERSIONS,
    UnitValue,
    _align_compatible_units,
    _floor_divide_quantities,
    _modulo_quantities,
    _pow_unit_string,
    _simplify_unit_string,
    are_units_compatible,
    convert_temperature,
    get_unit_category,
    normalize_unit,
)

__all__ = [
    "EvaluationError",
    "Evaluator",
    "evaluate",
    "evaluate_raw",
    "evaluate_cached",
    "evaluate_async",
    "evaluate_with_timeout",
    "get_default_evaluator",
    "get_config_generation",
    "register_constant",
    "register_function",
    "load_user_config",
    "EggCalcApp",
    "TimeoutError",
    "memory_store",
    "memory_recall",
    "memory_add",
    "memory_subtract",
    "memory_clear",
    "memory_list",
    "setvar",
    "getvar",
    "delvar",
    "listvars",
    "clearvars",
]


_lock = threading.Lock()
_config_loaded = False
_mcp_mode = False
_MAX_CONCURRENT_EVAL_SPAWNS = 4
_EVAL_SPAWN_SEMAPHORE = multiprocessing.BoundedSemaphore(_MAX_CONCURRENT_EVAL_SPAWNS)
_EVAL_SPAWN_ACQUIRE_TIMEOUT = 10  # seconds to wait for a spawn slot before failing
_config_generation = 0


class _EvalSpawnPermit:
    """RAII permit for an acquired eval spawn slot.

    The underlying semaphore count is released when the permit exits
    (including on exception or early return). This mirrors the
    _SpawnPermit pattern used by the MCP tools and the Rust
    WorkerPermit/ToolPermit guards.
    """

    def __init__(self, sem: Any) -> None:
        self._sem = sem

    def __enter__(self) -> _EvalSpawnPermit:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        try:
            self._sem.release()
        except Exception:
            pass


MAX_EXPONENT = 10000
MAX_FACTORIAL = 1000
MAX_NESTING_DEPTH = 100
MAX_RESULT_VALUE = 1e308
MAX_RESULT_DIGITS = 10000
MAX_SHIFT_COUNT = 50000
MAX_INPUT_LENGTH = 10_000  # max characters in expression string
MAX_USER_VARIABLES = 1000  # cap on setvar entries per evaluator
DEFAULT_CACHE_SIZE = 1024
MAX_CACHE_BYTES = 64 * 1024 * 1024  # 64 MB soft cap for _cache
_SORTED_UNIT_ALIASES: list[str] = sorted(UNIT_ALIASES.keys(), key=len, reverse=True)

# Functions whose output is non-deterministic (depend on global random state).
# These are opt-in: Evaluator(allow_random=False) rejects calls to them. The
# default CLI evaluator leaves them enabled; the MCP-mode default evaluator
# disables them so that "Deterministically evaluate" is true by default for
# agents consuming the math_eval tool.
_RANDOM_FUNCTIONS: frozenset[str] = frozenset(
    {
        "random",
        "randint",
        "randrange",
        "uniform",
        "randn",
        "gauss",
        "seed",
    }
)

# Functions that mutate Evaluator state across calls (memory registers,
# user variables). In MCP mode these are disabled to prevent cross-request
# state pollution and uncontrolled memory growth.
_SIDE_EFFECT_FUNCTIONS: frozenset[str] = frozenset(
    {
        "store",
        "recall",
        "M",
        "Mplus",
        "Mminus",
        "MC",
        "MR",
        "setvar",
        "getvar",
        "delvar",
        "listvars",
        "clearvars",
    }
)

# Functions that require a dimensionless argument. Calling these with a
# UnitValue previously silently stripped the unit (e.g. ``fact(5m) -> 120``,
# ``ceil(3.7m) -> 4``), which is misleading because the unit looks like it
# participates in the computation. We now reject UnitValue with a unit and
# raise a clear EvaluationError.
_DIMENSIONLESS_REQUIRED_FUNCTIONS: frozenset[str] = frozenset(
    {
        "abs",
        "floor",
        "ceil",
        "trunc",
        "round",
        "sign",
        "factorial",
        "fact",
        "gcd",
        "lcm",
        "perm",
        "comb",
        "nPr",
        "nCr",
        "pow",
        "expm1",
        "bin",
        "hex",
        "oct",
        "bitand",
        "bitor",
        "bitxor",
        "bitnot",
        "bitlshift",
        "bitrshift",
        "isprime",
        "is_prime",
        "primefactors",
        "prime_factors",
        "nextprime",
        "next_prime",
        "prevprime",
        "prev_prime",
        "randint",
        "randrange",
    }
)

# Functions whose first argument is a variable name (string). The argument
# is preserved as a raw string even if it collides with a constant or unit
# name (e.g., setvar("pi", 5) should bind the variable "pi" rather than
# replace math.pi). The visit_Call handler keeps these as plain strings
# before the generic constant-resolution path would otherwise rewrite them.
_STRING_NAME_FUNCTIONS: frozenset[str] = frozenset(
    {
        "setvar",
        "getvar",
        "delvar",
    }
)

# Historical note: some one-letter constant names (e.g., 'c', 'k', 'r') are
# effectively shadowed by UNIT_ALIASES in visit_Name's lookup order, but
# the set below is not used in any logic. It exists purely as documentation
# for users who might be surprised that 'c' resolves to "speed of light in
# vacuum" unit rather than the speed-of-light constant. Use long-form names
# ('speedoflight', 'boltzmann', 'gasconstant') for clarity.
_UNREACHABLE_CONSTANT_ALIASES: frozenset[str] = frozenset()


# Set of child processes that survived terminate+kill in MCP mode.
# Checked by MCP server's _cleanup_orphaned_processes for defensive cleanup.
# Bounded to prevent unbounded growth across many timeouts; oldest entries
# are evicted when the cap is reached.
MAX_ORPHANED_PROCESSES = 256
_orphaned_eval_processes: set[multiprocessing.Process] = set()
_orphaned_eval_order: list[multiprocessing.Process] = []
_orphaned_eval_lock: threading.Lock = threading.Lock()


def _check_constant_unit_collisions() -> None:
    """Warn at import time if any CONSTANTS entry collides with a UNIT_ALIASES.

    With the visit_Name order (units first, then constants), one-letter
    constant names like 'h' (Planck), 'g' (gravity), 'k' (Boltzmann), 'c'
    (speed of light), 'G' (gravitational), 'f' (Faraday) are unreachable as
    constants because they collide with common unit names (hour, gram, kelvin,
    etc.). Long forms ('planck', 'gravity', 'boltzmann', 'speedoflight',
    'gravitationalconstant', 'faraday') remain accessible.

    The gas constant is accessible as both 'r' and 'R' (no collision with
    Rankine, which uses the 'Ra' alias). Rankine is accessible as 'Ra',
    'rankine', 'degr', and '°R'.

    The warning is emitted at most once per process. A process-wide sentinel
    is stashed on the ``warnings`` module (a singleton) so the package and
    the inlined single-file build share the flag.
    """
    import warnings

    if getattr(warnings, "_eggcalc_collision_warned", False):
        return
    warnings._eggcalc_collision_warned = True  # type: ignore[attr-defined]
    # In assembled single-file mode, UNIT_ALIASES is inlined at the top.
    # In package mode, _IS_ASSEMBLED is False and we use the imported name.
    aliases = UNIT_ALIASES
    collisions: list[str] = []
    for c in Evaluator.CONSTANTS:
        if c in aliases:
            collisions.append(c)
    if collisions:
        import sys

        print(
            f"Warning: UNIT_ALIASES shadow CONSTANTS (unreachable as "
            f"constants; use long form): {sorted(collisions)}",
            file=sys.stderr,
        )


def _check_result_size(result: Any) -> Any:
    """Raise EvaluationError if a result has too many digits or is NaN/inf."""
    if isinstance(result, UnitValue):
        if isinstance(result.value, complex):
            if (
                math.isnan(result.value.real)
                or math.isnan(result.value.imag)
                or math.isinf(result.value.real)
                or math.isinf(result.value.imag)
            ):
                raise EvaluationError("Result too large")
            if abs(result.value) > MAX_RESULT_VALUE:
                raise EvaluationError("Result too large")
        elif isinstance(result.value, int) and not isinstance(result.value, bool):
            # Int values: skip float-specific checks, rely on digit count below
            pass
        else:
            try:
                if not math.isfinite(result.value):
                    raise EvaluationError("Result too large")
                if abs(result.value) > MAX_RESULT_VALUE:
                    raise EvaluationError("Result too large")
            except (OverflowError, ValueError):
                raise EvaluationError("Result too large")
        if isinstance(result.value, int) and not isinstance(result.value, bool):
            if _int_digit_count(result.value) > MAX_RESULT_DIGITS:
                raise EvaluationError(f"Result has too many digits (max {MAX_RESULT_DIGITS})")
    if isinstance(result, complex):
        if (
            math.isnan(result.real)
            or math.isnan(result.imag)
            or math.isinf(result.real)
            or math.isinf(result.imag)
        ):
            raise EvaluationError("Result too large")
        if abs(result) > MAX_RESULT_VALUE:
            raise EvaluationError("Result too large")
    elif isinstance(result, float):
        if math.isnan(result) or math.isinf(result):
            raise EvaluationError("Result too large")
        if abs(result) > MAX_RESULT_VALUE:
            raise EvaluationError("Result too large")
    if isinstance(result, int) and not isinstance(result, bool):
        if _int_digit_count(result) > MAX_RESULT_DIGITS:
            raise EvaluationError(f"Result has too many digits (max {MAX_RESULT_DIGITS})")
    return result


def register_constant(name: str, value: float) -> None:
    """Register a user-defined constant (thread-safe)."""
    with _lock:
        _default_evaluator.CONSTANTS[name] = value
    _clear_global_cache()


def register_function(name: str, func: Any) -> None:
    """Register a user-defined function (thread-safe).

    Args:
        name: Function name (must be a valid Python identifier).
        func: Callable to register. Must be a function or callable object.

    Raises:
        TypeError: If func is not callable.
        ValueError: If name is not a valid identifier.
    """
    if not callable(func):
        raise TypeError(f"func must be callable, got {type(func).__name__}")
    if not name.isidentifier():
        raise ValueError(f"name must be a valid identifier, got {name!r}")
    with _lock:
        _default_evaluator.FUNCTIONS[name] = func
    _clear_global_cache()


def load_user_config() -> None:
    """Load user-defined configuration from eggcalc_config.py (thread-safe).

    CUSTOM_UNITS supports two value formats per (base, name) entry:
    - A plain number ``{"xu": 0.1}`` (backward compatible): the category is
      inferred from the first existing unit in this base, or from the base
      key itself.
    - A ``(factor, category)`` tuple ``{"xu": (0.1, "length")}`` (preferred):
      the category is recorded explicitly so the unit can be added to or
      subtracted from other units in the same category.

    Trust boundary note: This function imports eggcalc_config from the
    current working directory. In production deployments (e.g., MCP server),
    the CWD must be controlled by the deployment operator, not by end users.
    An attacker who can place a malicious eggcalc_config.py in the CWD gains
    arbitrary code execution through the import.

    Config loading can be disabled by setting the EGGCALC_NO_CONFIG
    environment variable to a non-empty string.

    Library API policy: evaluate_raw() and related full-pipeline APIs do NOT
    call this function by default. Set EGGCALC_LOAD_CONFIG=1 to enable lazy
    config loading for library APIs, or call load_user_config() explicitly.
    """
    global _config_loaded
    if _mcp_mode:
        _config_loaded = True
        return
    if os.environ.get("EGGCALC_NO_CONFIG", ""):
        _config_loaded = True
        return
    config_changed = False
    # Only suppress the precise case where eggcalc_config is absent.
    # Syntax errors, internal import errors, and runtime exceptions
    # inside the config file propagate to the caller.
    import importlib.util

    spec = importlib.util.find_spec("eggcalc_config")
    if spec is None:
        # Config module doesn't exist — nothing to load.
        pass
    else:
        import eggcalc.normalize as normalize_mod  # noqa: F401
        import eggcalc_config as config  # type: ignore[import-not-found]

        for name, value in getattr(config, "CUSTOM_CONSTANTS", {}).items():
            _default_evaluator.CONSTANTS[name] = value
            config_changed = True

        for name, func in getattr(config, "CUSTOM_FUNCTIONS", {}).items():
            _default_evaluator.FUNCTIONS[name] = func
            config_changed = True

        from . import units

        with units._UNITS_LOCK:
            for base, unit_dict in getattr(config, "CUSTOM_UNITS", {}).items():
                config_changed = True
                if base in units.UNIT_BASE:
                    units.UNIT_BASE[base].update(unit_dict)
                else:
                    units.UNIT_BASE[base] = unit_dict
                for unit_name, value in unit_dict.items():
                    if isinstance(value, tuple) and len(value) == 2:
                        _factor, category = value
                        units.UNIT_CATEGORIES[unit_name] = category
                    else:
                        # Infer category from the first existing unit in this
                        # base, or fall back to the base key itself.
                        existing = next(
                            iter(
                                units.UNIT_CATEGORIES.get(u)
                                for u in units.UNIT_BASE[base]
                                if u in units.UNIT_CATEGORIES
                            ),
                            None,
                        )
                        units.UNIT_CATEGORIES[unit_name] = existing or base

            for unit, canonical in getattr(config, "CUSTOM_ALIASES", {}).items():
                units.UNIT_ALIASES[unit] = canonical
                config_changed = True

            for key, (mult, offset) in getattr(config, "CUSTOM_TEMP_CONVERSIONS", {}).items():
                units.TEMPERATURE_CONVERSIONS[key] = (mult, offset)
                config_changed = True

        units._rebuild_conversions()

    _config_loaded = True
    if config_changed:
        _clear_global_cache()


def _ensure_config_loaded() -> None:
    """Ensure user config is loaded (lazy loading) if explicitly opted in.

    Library API calls (evaluate_raw, evaluate_cached, etc.) do NOT load
    cwd-local eggcalc_config.py by default. Set EGGCALC_LOAD_CONFIG=1 to
    enable lazy config loading for library APIs. CLI loads config by default
    via maybe_load_cli_config(). MCP never loads config.
    """
    global _config_loaded
    if _mcp_mode:
        return
    if not _config_loaded:
        if os.environ.get("EGGCALC_LOAD_CONFIG", ""):
            load_user_config()
        else:
            _config_loaded = True


_cache: OrderedDict[str, Any] = OrderedDict()
_cache_lock = threading.Lock()
_cache_bytes: int = 0


def _entry_size(key: str, value: Any) -> int:
    """Approximate size of a cache entry in bytes.

    Uses the key length and the str() of the value as a simple proxy.
    """
    if isinstance(value, int) and not isinstance(value, bool):
        return len(key) + _int_digit_count(value)
    return len(key) + len(str(value))


def _evict_until_under_cap() -> None:
    """Evict LRU entries from _cache until total size <= MAX_CACHE_BYTES.

    Called under _cache_lock. The MAX_CACHE_BYTES cap is soft: if a single
    entry alone exceeds the cap, it is still inserted (we don't lose
    correctness by storing a single oversized entry), but we don't
    attempt to evict further on its behalf.
    """
    global _cache_bytes
    while _cache and _cache_bytes > MAX_CACHE_BYTES:
        old_key, old_value = _cache.popitem(last=False)
        _cache_bytes -= _entry_size(old_key, old_value)
    if _cache_bytes < 0:
        _cache_bytes = 0


def _remove_cache_entry(expression: str) -> None:
    """Remove one global cache entry and keep byte accounting in sync."""
    global _cache_bytes
    with _cache_lock:
        old_value = _cache.pop(expression, None)
        if old_value is not None:
            _cache_bytes -= _entry_size(expression, old_value)
        if _cache_bytes < 0:
            _cache_bytes = 0


def _clear_global_cache() -> None:
    """Clear the module-level evaluation cache after evaluator state changes.

    Increments the config generation counter so that any cached results
    from a prior configuration are treated as stale.
    """
    global _cache_bytes, _config_generation
    _config_generation += 1
    cache = globals().get("_cache")
    cache_lock = globals().get("_cache_lock")
    if cache is None or cache_lock is None:
        return
    with cache_lock:
        cache.clear()
        _cache_bytes = 0


def get_config_generation() -> int:
    """Return the current configuration generation counter.

    Increments each time user configuration is loaded or cleared.
    Useful for detecting whether cached results may be stale.
    """
    return _config_generation


def _store_cache_entry(expression: str, result: Any) -> None:
    """Store one result in the global LRU cache with consistent accounting."""
    global _cache_bytes
    with _cache_lock:
        old_value = _cache.pop(expression, None)
        if old_value is not None:
            _cache_bytes -= _entry_size(expression, old_value)
        while len(_cache) >= DEFAULT_CACHE_SIZE:
            old_key, old_value = _cache.popitem(last=False)
            _cache_bytes -= _entry_size(old_key, old_value)
        _cache[expression] = result
        _cache_bytes += _entry_size(expression, result)
        _evict_until_under_cap()


def _cached_normalize_and_evaluate(expression: str) -> Any:
    """Cache for normalized and evaluated expressions."""
    # Bypass the cache for non-deterministic or stateful expressions so
    # repeated calls execute instead of returning stale results.
    if _expression_bypasses_cache(expression):
        return _normalize_and_evaluate_uncached(expression)
    with _cache_lock:
        if expression in _cache:
            _cache.move_to_end(expression)
            return _cache[expression]

    _ensure_config_loaded()
    from .normalize import NORMALIZE, PATTERNS, normalize_expression

    normalized, exit_code = normalize_expression(
        expression, NORMALIZE, PATTERNS, skip_validation=True
    )
    if exit_code != 0:
        raise EvaluationError(f"Invalid expression: {expression}")

    result = _default_evaluator.evaluate(normalized)

    _store_cache_entry(expression, result)

    return result


def _normalize_and_evaluate_uncached(expression: str) -> Any:
    """Run the normalize-then-evaluate pipeline without consulting the cache."""
    _ensure_config_loaded()
    from .normalize import NORMALIZE, PATTERNS, normalize_expression

    normalized, exit_code = normalize_expression(
        expression, NORMALIZE, PATTERNS, skip_validation=True
    )
    if exit_code != 0:
        raise EvaluationError(f"Invalid expression: {expression}")
    return _default_evaluator.evaluate(normalized)


def _expression_bypasses_cache(expression: str) -> bool:
    """Return True for expressions whose calls must execute every time."""
    uncacheable = _RANDOM_FUNCTIONS | _SIDE_EFFECT_FUNCTIONS
    return any(
        re.search(rf"(?<![A-Za-z0-9_]){re.escape(name)}\s*\(", expression, re.IGNORECASE)
        is not None
        for name in uncacheable
    )


def evaluate_cached(expression: str) -> Any:
    """Evaluate an expression with caching (for repeated identical expressions).

    Handles natural language input and caching. Uses LRU cache with 1024 entries.
    Best for webapps with repeated queries.
    """
    try:
        return _cached_normalize_and_evaluate(expression)
    except EvaluationError:
        raise
    except (ValueError, SyntaxError, RecursionError):
        _remove_cache_entry(expression)
        raise


async def evaluate_async(expression: str) -> Any:
    """Evaluate an expression asynchronously (for use with async web frameworks).

    Handles natural language input. Runs evaluation in a thread pool to avoid
    blocking the event loop.
    """
    import asyncio

    def _eval() -> Any:
        return evaluate_raw(expression)

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _eval)


def load_user_config_extended() -> None:
    """Load user-defined configuration including normalize (call after normalize is loaded)."""
    try:
        import eggcalc.normalize as normalize_mod  # noqa: F401
        import eggcalc_config as config

        for word, num in getattr(config, "CUSTOM_NUMBER_WORDS", {}).items():
            normalize_mod.NUMBER_WORDS[num] = normalize_mod.NUMBER_WORDS.get(num, [])
            normalize_mod.NUMBER_WORDS[num].append(word)

        for word, op in getattr(config, "CUSTOM_OPERATOR_WORDS", {}).items():
            if op not in normalize_mod.OPERATOR_CONVERSIONS:
                normalize_mod.OPERATOR_CONVERSIONS[op] = []
            normalize_mod.OPERATOR_CONVERSIONS[op].append(word)

        if hasattr(normalize_mod, "_rebuild_config"):
            normalize_mod._rebuild_config()

    except ImportError:
        pass


def _safe_pow(base: float, exp: float) -> float | int | complex:
    """Safe power function with exponent limits to prevent DoS."""
    if abs(exp) > MAX_EXPONENT:
        raise EvaluationError(f"Exponent too large (max {MAX_EXPONENT})")
    if not isinstance(base, complex) and base < 0:
        if isinstance(exp, complex):
            if abs(exp.imag) > 1e-9 or not math.isclose(exp.real, round(exp.real), rel_tol=1e-9):
                raise EvaluationError("Cannot raise negative number to non-integer power")
            exp = int(round(exp.real))
        else:
            try:
                if not math.isclose(exp, round(exp), rel_tol=1e-9):
                    raise EvaluationError("Cannot raise negative number to non-integer power")
                exp = int(round(exp))
            except (TypeError, ValueError):
                raise EvaluationError("Cannot raise negative number to non-integer power")
    try:
        # For float base with large integer exponent, use int arithmetic
        # to avoid float overflow (e.g., pow(5.0, 500) overflows but 5**500 is exact)
        # Only apply when base is an exact integer (5.0, not 5.1) to avoid truncation.
        if (
            isinstance(base, float)
            and isinstance(exp, int)
            and abs(exp) > 300
            and base.is_integer()
        ):
            result = pow(int(base), exp)
        else:
            result = pow(base, exp)
    except ZeroDivisionError:
        raise EvaluationError("Cannot raise zero to a negative power") from None
    except OverflowError:
        raise EvaluationError("Result too large") from None
    if isinstance(result, complex):
        if (
            math.isnan(result.real)
            or math.isnan(result.imag)
            or math.isinf(result.real)
            or math.isinf(result.imag)
        ):
            raise EvaluationError("Result too large")
    elif isinstance(result, float):
        if math.isnan(result) or math.isinf(result):
            raise EvaluationError("Result too large")
    # For int results, skip the magnitude check — _check_result_size enforces
    # MAX_RESULT_DIGITS which is the correct limit for arbitrary-precision ints.
    if not isinstance(result, int) and abs(result) > MAX_RESULT_VALUE:
        raise EvaluationError("Result too large")
    return cast(float | int | complex, result)


def _require_int(value: Any, name: str) -> int:
    """Coerce a value to int, rejecting UnitValue, bool, complex, and non-integer float.

    Used by functions that semantically require an integer (factorial, gcd,
    comb, perm, etc.) to prevent silent coercion of, e.g., ``gcd(12.0, 8.0)``
    or ``fact(5m)``.
    """
    if isinstance(value, UnitValue):
        raise EvaluationError(
            f"{name}() requires a dimensionless argument, got value with unit '{value.unit}'"
        )
    if isinstance(value, bool):
        raise EvaluationError(f"{name}() requires an integer argument, got bool")
    if isinstance(value, complex):
        raise EvaluationError(f"{name}() requires an integer argument, got complex")
    if isinstance(value, float):
        if not value.is_integer():
            raise EvaluationError(
                f"{name}() requires an integer argument, got non-integer float {value}"
            )
        return int(value)
    if isinstance(value, int):
        return value
    raise EvaluationError(f"{name}() requires an integer argument, got {type(value).__name__}")


def _int_digit_count(n: int) -> int:
    """Count digits of an integer, safely handling Python 3.11+ str() limits."""
    try:
        s = str(n)
        return len(s) - (1 if s.startswith('-') else 0)
    except ValueError:
        # Python 3.11+ raises ValueError for integers with >4300 str digits
        # Use bit_length as an upper bound: digits <= bit_length * log10(2) + 1
        return int(n.bit_length() * math.log10(2)) + 1


def _safe_factorial(n: int) -> int:
    """Safe factorial with input bounds checking to prevent DoS."""
    n = _require_int(n, "factorial")
    if n < 0:
        raise EvaluationError("factorial requires non-negative input")
    if n > MAX_FACTORIAL:
        raise EvaluationError(f"factorial input too large (max {MAX_FACTORIAL})")
    result = math.factorial(n)
    if _int_digit_count(result) > MAX_RESULT_DIGITS:
        raise EvaluationError(f"Result has too many digits (max {MAX_RESULT_DIGITS})")
    return result


def _mean(*args: float) -> float:
    """Calculate arithmetic mean."""
    if not args:
        raise EvaluationError("mean requires at least one argument")
    return sum(args) / len(args)


def _std(*args: float) -> float:
    """Calculate population standard deviation."""
    if len(args) < 2:
        raise EvaluationError("std requires at least two arguments")
    m = sum(args) / len(args)
    variance = sum((x - m) ** 2 for x in args) / len(args)
    return math.sqrt(variance)


def _std_sample(*args: float) -> float:
    """Calculate sample standard deviation (n-1 denominator)."""
    if len(args) < 2:
        raise EvaluationError("std_sample requires at least two arguments")
    m = sum(args) / len(args)
    variance = sum((x - m) ** 2 for x in args) / (len(args) - 1)
    return math.sqrt(variance)


def _sum(*args: float) -> float:
    """Sum all arguments."""
    return sum(args)


def _max(*args: float) -> float:
    """Return maximum of arguments."""
    if not args:
        raise EvaluationError("max requires at least one argument")
    return max(args)


def _min(*args: float) -> float:
    """Return minimum of arguments."""
    if not args:
        raise EvaluationError("min requires at least one argument")
    return min(args)


def _to_bin(x: int) -> str:
    """Convert integer to binary string."""
    x = _require_int(x, "bin")
    return bin(x)


def _to_hex(x: int) -> str:
    """Convert integer to hexadecimal string."""
    x = _require_int(x, "hex")
    return hex(x)


def _to_oct(x: int) -> str:
    """Convert integer to octal string."""
    x = _require_int(x, "oct")
    return oct(x)


_TEMP_UNIT_FLOAT_MAP: dict[float, str] = {
    1.0: "K",
}


def _temp(value: float, from_unit: float | str, to_unit: float | str) -> float:
    """Convert temperature between units."""
    try:
        if isinstance(from_unit, float):
            mapped = _TEMP_UNIT_FLOAT_MAP.get(from_unit)
            if mapped is None:
                raise EvaluationError(
                    f"Unrecognized temperature unit value: {from_unit}. "
                    f"Expected a unit name string (e.g., 'C', 'K', 'F') or a known constant."
                )
            from_unit = mapped
        if isinstance(to_unit, float):
            mapped = _TEMP_UNIT_FLOAT_MAP.get(to_unit)
            if mapped is None:
                raise EvaluationError(
                    f"Unrecognized temperature unit value: {to_unit}. "
                    f"Expected a unit name string (e.g., 'C', 'K', 'F') or a known constant."
                )
            to_unit = mapped
        return convert_temperature(value, str(from_unit), str(to_unit))
    except (TypeError, ValueError) as e:
        raise EvaluationError(str(e)) from None


def _convert(value: Any, to_unit: str | Any) -> Any:
    """Convert a value with units to a different unit.

    Args:
        value: A number or UnitValue to convert
        to_unit: The target unit to convert to (can be str, UnitValue, or callable)

    Returns:
        UnitValue with the converted value and unit
    """
    try:
        # Handle case where to_unit is passed as a function (e.g., min function instead of "min" unit)
        if callable(to_unit) and not isinstance(to_unit, UnitValue):
            to_unit = to_unit.__name__ if hasattr(to_unit, '__name__') else str(to_unit)
        # Handle case where to_unit is passed as a UnitValue (unit name like 'ft')
        if isinstance(to_unit, UnitValue):
            to_unit = to_unit.unit if to_unit.unit else str(to_unit.value)
        if not isinstance(to_unit, str):
            raise EvaluationError(
                f"Invalid target unit for convert(): expected a unit string, got {type(to_unit).__name__} ({to_unit!r})"
            )

        if isinstance(value, UnitValue):
            # Check for temperature conversions (special handling needed)
            cat = get_unit_category(value.unit) if value.unit else None
            if cat == "temperature" and value.unit:
                converted_val = convert_temperature(cast(float, value.value), value.unit, to_unit)
                return UnitValue(converted_val, to_unit)
            return value.convert_to(to_unit)
        # If it's just a number without units, assume it's a dimensionless value
        # and try to convert (will fail if not a valid unit)
        try:
            return UnitValue(float(value), None).convert_to(to_unit)
        except ValueError as e:
            raise EvaluationError(str(e)) from None
    except (TypeError, ValueError, AttributeError) as e:
        if isinstance(e, EvaluationError):
            raise
        raise EvaluationError(str(e)) from None


# === Complex number functions ===


def _real(z: complex) -> float:
    """Return the real part of a complex number."""
    if isinstance(z, complex):
        return z.real
    return float(z)


def _imag(z: complex) -> float:
    """Return the imaginary part of a complex number."""
    if isinstance(z, complex):
        return z.imag
    return 0.0


def _conj(z: complex) -> complex:
    """Return the complex conjugate."""
    if isinstance(z, complex):
        return z.conjugate()
    return complex(z, 0)


def _phase(z: complex) -> float:
    """Return the phase (argument) of a complex number in radians."""
    return cmath.phase(z)


def _polar(z: complex) -> tuple[float, float]:
    """Return polar coordinates (r, phi) of a complex number."""
    return cmath.polar(z)


def _polar_from_coords(r: float, phi: float) -> tuple[float, float]:
    """Return polar coordinates (r, phi) from scalar inputs.

    Accepts the (r, phi) signature users typically expect, and returns
    a (r, phi) tuple so the public name reads naturally.
    """
    r_f = float(r)
    phi_f = float(phi)
    if r_f < 0:
        raise EvaluationError("polar(): r must be non-negative")
    return (r_f, phi_f)


def _rect(r: float, phi: float) -> complex:
    """Return complex number from polar coordinates."""
    return cmath.rect(r, phi)


# === Statistical functions ===


def _median(*args: float) -> float:
    """Calculate median of arguments."""
    if not args:
        raise EvaluationError("median requires at least one argument")
    sorted_args = sorted(args)
    n = len(sorted_args)
    mid = n // 2
    if n % 2 == 0:
        return (sorted_args[mid - 1] + sorted_args[mid]) / 2
    return sorted_args[mid]


def _mode(*args: float) -> float:
    """Calculate mode of arguments.

    When multiple values share the highest frequency, the first one encountered
    (in argument order) is returned, since Counter preserves insertion order.
    """
    if not args:
        raise EvaluationError("mode requires at least one argument")
    from collections import Counter

    counts = Counter(args)
    max_count = max(counts.values())
    modes = [x for x, c in counts.items() if c == max_count]
    return modes[0]


def _variance(*args: float) -> float:
    """Calculate population variance."""
    if len(args) < 2:
        raise EvaluationError("variance requires at least two arguments")
    m = sum(args) / len(args)
    return sum((x - m) ** 2 for x in args) / len(args)


def _variance_sample(*args: float) -> float:
    """Calculate sample variance (n-1 denominator)."""
    if len(args) < 2:
        raise EvaluationError("variance_sample requires at least two arguments")
    m = sum(args) / len(args)
    return sum((x - m) ** 2 for x in args) / (len(args) - 1)


# === Bitwise operations ===


def _bitand(a: int, b: int) -> int:
    """Bitwise AND."""
    return _require_int(a, "bitand") & _require_int(b, "bitand")


def _bitor(a: int, b: int) -> int:
    """Bitwise OR."""
    return _require_int(a, "bitor") | _require_int(b, "bitor")


def _bitxor(a: int, b: int) -> int:
    """Bitwise XOR."""
    return _require_int(a, "bitxor") ^ _require_int(b, "bitxor")


def _bitnot(a: int) -> int:
    """Bitwise NOT (inverts all bits)."""
    return ~_require_int(a, "bitnot")


def _bitlshift_safe(a: int, b: int) -> int:
    """Left shift with bounds checks."""
    a = _require_int(a, "bitlshift")
    b = _require_int(b, "bitlshift")
    if b < 0:
        raise EvaluationError("Shift count must be non-negative")
    if b > MAX_SHIFT_COUNT:
        raise EvaluationError(f"Shift count too large (max {MAX_SHIFT_COUNT}, got {b})")
    # Pre-check: a << b would have ~a.bit_length() + b bits, which
    # corresponds to roughly (a.bit_length() + b) * log10(2) digits. Bail
    # before computing so we don't allocate huge ints in the worker.
    if a.bit_length() + b > MAX_RESULT_DIGITS * 3:
        raise EvaluationError(
            f"Left shift would produce an integer with more than " f"{MAX_RESULT_DIGITS} digits"
        )
    return a << b


def _bitrshift_safe(a: int, b: int) -> int:
    """Right shift with non-negative check."""
    a = _require_int(a, "bitrshift")
    b = _require_int(b, "bitrshift")
    if b < 0:
        raise EvaluationError("Shift count must be non-negative")
    return a >> b


# === Combinatorics ===


def _perm(n: int, r: int | None = None) -> int:
    """Calculate permutations P(n,r) = n!/(n-r)!."""
    n = _require_int(n, "perm")
    if n < 0:
        raise EvaluationError("perm requires non-negative input")
    if n > 10000:
        raise EvaluationError(f"perm input too large (max 10000, got {n})")
    if r is None:
        result = math.factorial(n)
        if _int_digit_count(result) > MAX_RESULT_DIGITS:
            raise EvaluationError(f"Result has too many digits (max {MAX_RESULT_DIGITS})")
        return result
    r = _require_int(r, "perm")
    if r < 0:
        raise EvaluationError("perm requires non-negative arguments")
    if r > n:
        return 0
    if r > 10000:
        raise EvaluationError(f"perm input too large (max 10000, got {r})")
    result = math.perm(n, r)
    if _int_digit_count(result) > MAX_RESULT_DIGITS:
        raise EvaluationError(f"Result has too many digits (max {MAX_RESULT_DIGITS})")
    return result


def _comb(n: int, r: int) -> int:
    """Calculate combinations C(n,r) = n!/(r!(n-r)!)."""
    n = _require_int(n, "comb")
    r = _require_int(r, "comb")
    if n < 0 or r < 0:
        raise EvaluationError("comb requires non-negative arguments")
    if n > 10000:
        raise EvaluationError(f"comb input too large (max 10000, got {n})")
    if r > n:
        return 0
    if r > 10000:
        raise EvaluationError(f"comb input too large (max 10000, got {r})")
    return math.comb(n, r)


# === LCM ===


def _lcm(*args: int) -> int:
    """Calculate least common multiple."""
    if not args:
        raise EvaluationError("lcm requires at least one argument")
    validated = [_require_int(a, "lcm") for a in args]
    result = abs(validated[0])
    for arg in validated[1:]:
        g = math.gcd(result, arg)
        if g == 0:
            return 0
        result = abs(result * arg) // g
    if isinstance(result, int) and _int_digit_count(result) > MAX_RESULT_DIGITS:
        raise EvaluationError(f"Result has too many digits (max {MAX_RESULT_DIGITS})")
    return result


def _gcd(*args: int) -> int:
    """Calculate greatest common divisor."""
    if not args:
        raise EvaluationError("gcd requires at least one argument")
    validated = [_require_int(a, "gcd") for a in args]
    result = abs(validated[0])
    for arg in validated[1:]:
        result = math.gcd(result, arg)
    return result


# === Prime functions ===


def _is_prime(n: int) -> bool:
    """Check if a number is prime using deterministic Miller-Rabin for large n."""
    n = _require_int(n, "isprime")
    if n > 10**12:
        raise EvaluationError("primality test not available for numbers > 10^12")
    if n < 2:
        return False
    if n == 2 or n == 3:
        return True
    if n % 2 == 0 or n % 3 == 0:
        return False
    # Small numbers: trial division is faster
    if n < 1000:
        i = 5
        while i * i <= n:
            if n % i == 0 or n % (i + 2) == 0:
                return False
            i += 6
        return True
    # Deterministic Miller-Rabin (sufficient for n < 2.15 × 10^12)
    d = n - 1
    r = 0
    while d % 2 == 0:
        d //= 2
        r += 1
    for a in (2, 3, 5, 7, 11):
        if a >= n:
            continue
        x = pow(a, d, n)
        if x == 1 or x == n - 1:
            continue
        for _ in range(r - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


def _prime_factors(n: int) -> str:
    """Return prime factorization as a formatted string.

    Returns a string of the form "2^2 × 3 × 5" where each prime factor
    is separated by " × ". Factors with exponent 1 appear as the prime
    itself (e.g. "3"), while factors with higher exponents include the
    exponent (e.g. "2^2"). For n < 2, returns the number as a string.
    """
    n = _require_int(n, "primefactors")
    if n > 10**12:
        raise EvaluationError("factorization not available for numbers > 10^12")
    if n < 2:
        return str(n)

    factors: dict[int, int] = {}
    d = 2
    temp = n
    while d * d <= temp:
        while temp % d == 0:
            factors[d] = factors.get(d, 0) + 1
            temp //= d
        d += 1
    if temp > 1:
        factors[temp] = factors.get(temp, 0) + 1

    parts = []
    for prime in sorted(factors.keys()):
        exp = factors[prime]
        if exp == 1:
            parts.append(str(prime))
        else:
            parts.append(f"{prime}^{exp}")
    return " × ".join(parts)


def _next_prime(n: int) -> int:
    """Return the next prime after n."""
    n = _require_int(n, "nextprime")
    if n > 10**12:
        raise EvaluationError("primality test not available for numbers > 10^12")
    candidate = n + 1
    max_iterations = 10000
    iterations = 0
    while not _is_prime(candidate):
        candidate += 1
        iterations += 1
        if iterations > max_iterations:
            raise EvaluationError("nextprime: search exceeded iteration limit (10000)")
    return candidate


def _prev_prime(n: int) -> int:
    """Return the previous prime before n."""
    n = _require_int(n, "prevprime")
    if n <= 2:
        raise EvaluationError("No prime less than 2")
    if n > 10**12:
        raise EvaluationError("primality test not available for numbers > 10^12")
    candidate = n - 1
    max_iterations = 10000
    iterations = 0
    while candidate > 1 and not _is_prime(candidate):
        candidate -= 1
        iterations += 1
        if iterations > max_iterations:
            raise EvaluationError("prevprime: search exceeded iteration limit (10000)")
    if candidate < 2:
        raise EvaluationError("No prime less than 2")
    return candidate


# === Random functions ===

# NOTE: This generator is shared across all Evaluator instances.
# Calling seed() on it affects every evaluator's random output.
_random_generator = random.Random()


def _random() -> float:
    """Return random float in [0, 1)."""
    return _random_generator.random()


def _randint(a: int, b: int) -> int:
    """Return random integer in [a, b]."""
    return _random_generator.randint(_require_int(a, "randint"), _require_int(b, "randint"))


def _randrange(a: int, b: int | None = None) -> int:
    """Return random integer in [a, b) or [0, a) if b is None."""
    if b is None:
        return _random_generator.randrange(_require_int(a, "randrange"))
    return _random_generator.randrange(_require_int(a, "randrange"), _require_int(b, "randrange"))


def _uniform(a: float, b: float) -> float:
    """Return random float in [a, b]."""
    return _random_generator.uniform(float(a), float(b))


def _randn() -> float:
    """Return random float from standard normal distribution."""
    return _random_generator.gauss(0, 1)


def _gauss(mu: float, sigma: float) -> float:
    """Return random float from normal distribution with mean mu and std sigma."""
    return _random_generator.gauss(float(mu), float(sigma))


def _seed(s: int | None = None) -> None:
    """Seed the random number generator."""
    _random_generator.seed(s)
    return None


# === Percentage functions ===


def _percent_of(p: float, x: float) -> float:
    """Calculate p percent of x."""
    return (p / 100) * x


def _as_percent(x: float, total: float) -> float:
    """Calculate what percent x is of total."""
    if total == 0:
        raise EvaluationError("Cannot divide by zero")
    if abs(total) < 1e-100:
        raise EvaluationError("Near-zero divisor could cause overflow")
    return (x / total) * 100


# === Rounding ===


def _round(x: float, ndigits: int = 0) -> float:
    """Round to ndigits decimal places."""
    return round(float(x), _require_int(ndigits, "round"))


def _sign(x: float) -> int:
    """Return sign of x: -1, 0, or 1."""
    if x > 0:
        return 1
    elif x < 0:
        return -1
    return 0


# === Clamping ===


def _clamp(x: float, lo: float, hi: float) -> float:
    """Clamp x to range [lo, hi]. If lo > hi, raise ValueError."""
    if lo > hi:
        raise ValueError(f"clamp: lower bound {lo} exceeds upper bound {hi}")
    return max(lo, min(hi, x))


# === Hypot ===


def _hypot(*args: float) -> float:
    """Calculate hypotenuse: sqrt(sum(x**2))."""
    return math.hypot(*[float(x) for x in args])


def _complex_aware(
    real_func: Any,
    cmplx_func: Any = None,
    *,
    use_complex_for_negative: bool = False,
    use_complex_for_abs_gt_one: bool = False,
) -> Any:
    """Create a function that handles both real and complex inputs.

    Args:
        real_func: Function for real numbers (from math module)
        cmplx_func: Function for complex numbers (from cmath module). Defaults to real_func.
        use_complex_for_negative: If True, use complex function for negative real inputs
        use_complex_for_abs_gt_one: If True, use complex function when abs(x) > 1

    Returns:
        A function that handles both real and complex inputs appropriately.
    """
    if cmplx_func is None:
        cmplx_func = getattr(cmath, real_func.__name__, real_func)

    def wrapper(x: Any, *args: Any) -> Any:
        if isinstance(x, complex):
            return cmplx_func(x, *args)
        if use_complex_for_negative and x < 0:
            return cmplx_func(x, *args)
        if use_complex_for_abs_gt_one and abs(x) > 1:
            return cmplx_func(x, *args)
        return real_func(x, *args)

    wrapper.__name__ = real_func.__name__
    wrapper.__doc__ = f"{real_func.__name__} that handles complex numbers."
    return wrapper


_sqrt = _complex_aware(math.sqrt, cmath.sqrt, use_complex_for_negative=True)

_log_complex = _complex_aware(math.log, cmath.log, use_complex_for_negative=True)
_log10_complex = _complex_aware(math.log10, cmath.log10, use_complex_for_negative=True)
_log2_complex = _complex_aware(math.log2, lambda x: cmath.log(x, 2), use_complex_for_negative=True)


def _safe_log(*args: Any) -> Any:
    try:
        return _log_complex(*args)
    except ValueError:
        if args and isinstance(args[0], (int, float)) and args[0] <= 0:
            raise EvaluationError("Logarithm undefined for non-positive values")
        raise


def _safe_log10(*args: Any) -> Any:
    try:
        return _log10_complex(*args)
    except ValueError:
        if args and isinstance(args[0], (int, float)) and args[0] <= 0:
            raise EvaluationError("Logarithm undefined for non-positive values")
        raise


def _safe_log2(*args: Any) -> Any:
    try:
        return _log2_complex(*args)
    except ValueError:
        if args and isinstance(args[0], (int, float)) and args[0] <= 0:
            raise EvaluationError("Logarithm undefined for non-positive values")
        raise


_log = _safe_log
_log10 = _safe_log10
_log2 = _safe_log2
_exp = _complex_aware(math.exp, cmath.exp)
_sin = _complex_aware(math.sin, cmath.sin)
_cos = _complex_aware(math.cos, cmath.cos)
_tan = _complex_aware(math.tan, cmath.tan)
_asin = _complex_aware(math.asin, cmath.asin, use_complex_for_abs_gt_one=True)
_acos = _complex_aware(math.acos, cmath.acos, use_complex_for_abs_gt_one=True)
_atan = _complex_aware(math.atan, cmath.atan)
_sinh = _complex_aware(math.sinh, cmath.sinh)
_cosh = _complex_aware(math.cosh, cmath.cosh)
_tanh = _complex_aware(math.tanh, cmath.tanh)
_asinh = _complex_aware(math.asinh, cmath.asinh)


def _acosh(x: Any) -> Any:
    """acosh that handles complex numbers for out-of-domain real inputs."""
    if isinstance(x, complex):
        return cmath.acosh(x)
    if x < 1:
        return cmath.acosh(x)
    return math.acosh(x)


_atanh = _complex_aware(math.atanh, cmath.atanh, use_complex_for_abs_gt_one=True)


def _cbrt_impl(x: float) -> float:
    return math.cbrt(x)


def _cbrt_complex(x: complex) -> complex:
    """Complex cube root using principal branch."""
    return x ** (1 / 3)


_cbrt = _complex_aware(_cbrt_impl, _cbrt_complex)


class EvaluationError(Exception):
    """Raised when an expression contains unsafe or unsupported operations."""

    pass


# ContextVar tracking the "current" Evaluator during evaluation.
# FUNCTIONS dict entries (store, setvar, etc.) consult this to use
# the per-instance state of the evaluator actually running the expression.
_current_evaluator: contextvars.ContextVar[Evaluator | None] = contextvars.ContextVar(
    "_current_evaluator", default=None
)


def _get_current_evaluator() -> Evaluator:
    """Return the Evaluator currently executing an expression, or the default.

    Used by FUNCTIONS dict entries so memory/setvar/clearvars/etc. operate on
    the state of the Evaluator that is actually running the expression.
    """
    ev = _current_evaluator.get()
    return ev if ev is not None else _default_evaluator


# Per-instance wrappers for FUNCTIONS dict entries. They consult the
# _current_evaluator ContextVar so behavior is correctly scoped to the
# active Evaluator (e.g. inside a EggCalcApp instance).


def _fn_store(value: float, register: str = "M") -> float:
    return _get_current_evaluator()._memory.store(value, register)


def _fn_recall(register: str = "M") -> float:
    return _get_current_evaluator()._memory.recall(register)


def _fn_add(value: float, register: str = "M") -> float:
    return _get_current_evaluator()._memory.add(value, register)


def _fn_subtract(value: float, register: str = "M") -> float:
    return _get_current_evaluator()._memory.subtract(value, register)


def _fn_clear(register: str | None = None) -> None:
    _get_current_evaluator()._memory.clear(register)
    return None


def _set_user_variable(ev: Evaluator, name: Any, value: Any) -> Any:
    """Validate and store a user variable on the given evaluator.

    Used by both the expression-level ``setvar()`` (``_fn_setvar``) and
    the public Python API (``setvar()``) so the cap and identifier
    rules apply uniformly. See plans/production_review_2026_07_b.md
    (B4).
    """
    if not isinstance(name, str) or not name:
        raise EvaluationError("setvar: name must be a non-empty string")
    if not name.isidentifier():
        raise EvaluationError(f"setvar: name must be a valid identifier, got {name!r}")
    with ev._var_lock:
        # Cap _user_variables size to prevent unbounded memory growth from
        # repeated setvar calls with unique names. Oldest entries (in
        # insertion order) are evicted.
        if name not in ev._user_variables and len(ev._user_variables) >= MAX_USER_VARIABLES:
            oldest_key = next(iter(ev._user_variables))
            del ev._user_variables[oldest_key]
        ev._user_variables[name] = value
    return value


def _fn_setvar(name: str, value: Any) -> Any:
    ev = _get_current_evaluator()
    return _set_user_variable(ev, name, value)


def _fn_getvar(name: str, default: Any = 0) -> Any:
    ev = _get_current_evaluator()
    with ev._var_lock:
        return ev._user_variables.get(name, default)


def _fn_delvar(name: str) -> None:
    ev = _get_current_evaluator()
    with ev._var_lock:
        ev._user_variables.pop(name, None)
    return None


def _fn_listvars() -> dict[str, Any]:
    ev = _get_current_evaluator()
    with ev._var_lock:
        return dict(ev._user_variables)


def _fn_clearvars() -> None:
    ev = _get_current_evaluator()
    with ev._var_lock:
        ev._user_variables.clear()
    return None


class Memory:
    """Memory registers for storing values (like scientific calculator memory)."""

    def __init__(self) -> None:
        self._registers: dict[str, float] = {}
        self._default_register: float = 0.0
        self._lock = threading.Lock()

    def _get_and_set(self, register: str, new_value: float) -> float:
        """Set a register value and return it (internal, assumes lock held)."""
        if register == "M":
            self._default_register = new_value
            return new_value
        self._registers[register] = new_value
        return new_value

    def _get(self, register: str) -> float:
        """Get a register value (internal, assumes lock held)."""
        if register == "M":
            return self._default_register
        return self._registers.get(register, 0.0)

    def store(self, value: float, register: str = "M") -> float:
        """Store value in register (default: M)."""
        with self._lock:
            return self._get_and_set(register, float(value))

    def recall(self, register: str = "M") -> float:
        """Recall value from register (default: M)."""
        with self._lock:
            return self._get(register)

    def add(self, value: float, register: str = "M") -> float:
        """Add value to register (M+)."""
        with self._lock:
            return self._get_and_set(register, self._get(register) + float(value))

    def subtract(self, value: float, register: str = "M") -> float:
        """Subtract value from register (M-)."""
        with self._lock:
            return self._get_and_set(register, self._get(register) - float(value))

    def clear(self, register: str | None = None) -> None:
        """Clear register (or all if register is None)."""
        with self._lock:
            if register is None:
                self._default_register = 0.0
                self._registers.clear()
            elif register == "M":
                self._default_register = 0.0
            else:
                self._registers.pop(register, None)

    def list_registers(self) -> dict[str, float]:
        """List all registers and their values."""
        with self._lock:
            result = {"M": self._default_register}
            result.update(self._registers.copy())
            return result


# Global memory instance (default evaluator; replaced by per-instance below)
_memory: Memory = Memory()


def memory_store(value: float, register: str = "M") -> float:
    """Store value in memory register (proxies to the default evaluator)."""
    return _default_evaluator._memory.store(value, register)


def memory_recall(register: str = "M") -> float:
    """Recall value from memory register (proxies to the default evaluator)."""
    return _default_evaluator._memory.recall(register)


def memory_add(value: float, register: str = "M") -> float:
    """Add value to memory register (M+) on the default evaluator."""
    return _default_evaluator._memory.add(value, register)


def memory_subtract(value: float, register: str = "M") -> float:
    """Subtract value from memory register (M-) on the default evaluator."""
    return _default_evaluator._memory.subtract(value, register)


def memory_clear(register: str | None = None) -> None:
    """Clear memory register(s) on the default evaluator."""
    _default_evaluator._memory.clear(register)


def memory_list() -> dict[str, float]:
    """List all memory registers on the default evaluator."""
    return _default_evaluator._memory.list_registers()


# === Variable storage (proxies to default evaluator) ===


def setvar(name: str, value: Any) -> Any:
    """Set a user variable on the default evaluator.

    Args:
        name: Variable name (must be a valid Python identifier).
        value: Variable value.

    Returns:
        The value that was set.

    Raises:
        EvaluationError: If ``name`` is not a non-empty string, is not a
            valid Python identifier, or if the variable store is at
            capacity (the oldest entry is evicted before insertion).
    """
    return _set_user_variable(_default_evaluator, name, value)


def getvar(name: str) -> Any:
    """Get a user variable from the default evaluator.

    Args:
        name: Variable name

    Returns:
        The variable value or 0 if not found
    """
    ev = _default_evaluator
    with ev._var_lock:
        return ev._user_variables.get(name, 0)


def delvar(name: str) -> None:
    """Delete a user variable on the default evaluator."""
    ev = _default_evaluator
    with ev._var_lock:
        ev._user_variables.pop(name, None)


def listvars() -> dict[str, Any]:
    """List all user variables on the default evaluator."""
    ev = _default_evaluator
    with ev._var_lock:
        return dict(ev._user_variables)


def clearvars() -> None:
    """Clear all user variables on the default evaluator."""
    ev = _default_evaluator
    with ev._var_lock:
        ev._user_variables.clear()


# === AST allow-list (M7) ===
# Built at module import time by walking a set of known-safe expressions
# and recording every reachable ast.expr subclass. Used by
# Evaluator._validate_node to reject any node type not in this set.

_SAFE_AST_EXPRESSIONS: tuple[str, ...] = (
    "1",
    "1+1",
    "1-1",
    "1*1",
    "1/1",
    "1**1",
    "a",
    "a+b",
    "a-b",
    "a*b",
    "a/b",
    "a**b",
    "a(1)",
    "a(1, 2, 3)",
    "-a",
    "+a",
    "~a",
    "1j",
    "(1j)*(1j)",
    "a + b * c",
    "(a + b) * c",
    "math.sin(1)",
    "math.cos(0)",
    "math.tan(0)",
    "(1).real",
    "(1).imag",
    "(1).conjugate()",
    "a.real + b.imag",
    "1 & 3",
    "1 | 3",
    "1 ^ 3",
    "1 << 2",
    "1 >> 2",
)


def _build_allowed_ast_types() -> frozenset[type[ast.AST]]:
    """Compute the set of AST node types reachable from safe expressions.

    Also includes all ast.operator, ast.unaryop, ast.expr_context,
    ast.cmpop, ast.boolop subclasses so sub-nodes (e.g. Add, Load)
    are not erroneously rejected.
    """
    allowed: set[type[ast.AST]] = set()
    for expr in _SAFE_AST_EXPRESSIONS:
        try:
            tree = ast.parse(expr, mode="eval")
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.expr):
                allowed.add(type(node))

    allowed.add(ast.Expression)
    for name in dir(ast):
        obj = getattr(ast, name)
        if (
            isinstance(obj, type)
            and issubclass(obj, ast.AST)
            and (
                issubclass(obj, ast.operator)
                or issubclass(obj, ast.unaryop)
                or issubclass(obj, ast.expr_context)
                or issubclass(obj, ast.cmpop)
                or issubclass(obj, ast.boolop)
            )
        ):
            allowed.add(obj)
    return frozenset(allowed)


_ALLOWED_AST_TYPES: frozenset[type[ast.AST]] = _build_allowed_ast_types()


class Evaluator(ast.NodeVisitor):
    """Safe AST-based expression evaluator.

    Evaluates mathematical expressions without using eval().
    Supports arithmetic operators, trig functions, constants,
    logarithms, and unit conversions.
    """

    # Safe mathematical constants
    # Note: inf and nan are intentionally excluded — they cannot be accessed
    # as bare names (visit_Name rejects them as unknown names), preventing
    # accidental NaN/inf propagation from user expressions.
    CONSTANTS: dict[str, Any] = {
        "pi": math.pi,
        "e": math.e,
        "tau": math.tau,
        # Imaginary unit
        "i": 1j,
        "j": 1j,
        # Physical constants
        "na": 6.02214076e23,
        "avogadro": 6.02214076e23,
        "avogadros": 6.02214076e23,
        "r": 8.314462618,
        "R": 8.314462618,
        "gasconstant": 8.314462618,
        "idealgasconstant": 8.314462618,
        "planck": 6.62607015e-34,
        "planckconstant": 6.62607015e-34,
        "k": 1.380649e-23,
        "boltzmann": 1.380649e-23,
        "boltzmannconstant": 1.380649e-23,
        "c": 299792458,
        "c0": 299792458,
        "speedoflight": 299792458,
        "speedoflightvacuum": 299792458,
        "elementarycharge": 1.602176634e-19,
        "echarge": 1.602176634e-19,
        "f": 96485.33212,
        "faraday": 96485.33212,
        "faradayconstant": 96485.33212,
        "u": 1.66053906660e-27,
        "amu": 1.66053906660e-27,
        "atomicmassunit": 1.66053906660e-27,
        "epsilon0": 8.8541878128e-12,
        "vacuumpermittivity": 8.8541878128e-12,
        # Electromagnetism
        "mu0": 1.25663706212e-6,
        "vacuumpermeability": 1.25663706212e-6,
        "standardgravity": 9.80665,
        # Gravitation
        "G": 6.67430e-11,
        "gravitationalconstant": 6.67430e-11,
        # Spectroscopy
        "rydberg": 10973731.568160,
        "rydbergconstant": 10973731.568160,
        # Thermodynamics
        "stefan": 5.670374419e-8,
        "stefanboltzmann": 5.670374419e-8,
        "planckbar": 1.054571817e-34,
        "hbar": 1.054571817e-34,
        "reducedplanck": 1.054571817e-34,
        # Atomic/particle physics
        "me": 9.1093837015e-31,
        "electronmass": 9.1093837015e-31,
        "mp": 1.67262192369e-27,
        "protonmass": 1.67262192369e-27,
        "mn": 1.67493e-27,
        "neutronmass": 1.67493e-27,
        "re": 2.8179403262e-15,
        "electronradius": 2.8179403262e-15,
        "alpha": 7.2973525693e-3,
        "finestructure": 7.2973525693e-3,
        "wien": 2.897771955e-3,
        "wienconstant": 2.897771955e-3,
    }

    # Safe mathematical functions
    FUNCTIONS: dict[str, Any] = {
        # Trigonometric (complex-aware)
        "sin": _sin,
        "cos": _cos,
        "tan": _tan,
        "asin": _asin,
        "acos": _acos,
        "atan": _atan,
        "atan2": math.atan2,
        # Hyperbolic (complex-aware)
        "sinh": _sinh,
        "cosh": _cosh,
        "tanh": _tanh,
        "asinh": _asinh,
        "acosh": _acosh,
        "atanh": _atanh,
        # Logarithmic (complex-aware)
        "log": _log,
        "ln": _log,
        "log10": _log10,
        "log2": _log2,
        "log1p": _complex_aware(
            math.log1p, lambda x: cmath.log(1 + x), use_complex_for_negative=True
        ),
        "exp": _exp,
        "expm1": _complex_aware(math.expm1, lambda x: cmath.exp(x) - 1),
        # Power and root (complex-aware)
        "sqrt": _sqrt,
        "pow": _safe_pow,
        # Rounding and absolute — visit_Call rejects UnitValue-with-unit
        # for these via _DIMENSIONLESS_REQUIRED_FUNCTIONS, so the functions
        # themselves can stay as plain builtins.
        "abs": abs,
        "floor": math.floor,
        "ceil": math.ceil,
        "trunc": math.trunc,
        "round": _round,
        "sign": _sign,
        # Factorial and combinatorics
        "factorial": _safe_factorial,
        "fact": _safe_factorial,
        "gcd": _gcd,
        "lcm": _lcm,
        "perm": _perm,
        "comb": _comb,
        "nPr": _perm,
        "nCr": _comb,
        "cbrt": _cbrt,
        # Angle conversion
        "degrees": math.degrees,
        "radians": math.radians,
        # Statistical functions
        "mean": _mean,
        "median": _median,
        "mode": _mode,
        "std": _std,
        "std_sample": _std_sample,
        "stds": _std_sample,
        "variance": _variance,
        "var": _variance,
        "variance_sample": _variance_sample,
        "vars": _variance_sample,
        "var_sample": _variance_sample,
        "sum": _sum,
        "max": _max,
        "min": _min,
        # Complex number functions
        "real": _real,
        "imag": _imag,
        "conj": _conj,
        "conjugate": _conj,
        "phase": _phase,
        "polar": _polar_from_coords,
        "rect": _rect,
        # Base conversion
        "bin": _to_bin,
        "hex": _to_hex,
        "oct": _to_oct,
        # Bitwise operations
        "bitand": _bitand,
        "bitor": _bitor,
        "bitxor": _bitxor,
        "bitnot": _bitnot,
        "bitlshift": _bitlshift_safe,
        "bitrshift": _bitrshift_safe,
        # Prime functions
        "isprime": _is_prime,
        "is_prime": _is_prime,
        "primefactors": _prime_factors,
        "prime_factors": _prime_factors,
        "nextprime": _next_prime,
        "next_prime": _next_prime,
        "prevprime": _prev_prime,
        "prev_prime": _prev_prime,
        # Random functions
        "random": _random,
        "randint": _randint,
        "randrange": _randrange,
        "uniform": _uniform,
        "randn": _randn,
        "gauss": _gauss,
        "seed": _seed,
        # Percentage
        "percentof": _percent_of,
        "percent_of": _percent_of,
        "aspercent": _as_percent,
        "as_percent": _as_percent,
        # Utility
        "clamp": _clamp,
        "hypot": _hypot,
        # Temperature conversion
        "temp": _temp,
        # Unit conversion
        "convert": _convert,
        # Memory functions
        "store": _fn_store,
        "recall": _fn_recall,
        "M": lambda: _fn_recall("M"),
        "Mplus": lambda x: _fn_add(x, "M"),
        "Mminus": lambda x: _fn_subtract(x, "M"),
        "MC": lambda: _fn_clear("M"),
        "MR": lambda: _fn_recall("M"),
        # Variable functions
        "setvar": _fn_setvar,
        "getvar": _fn_getvar,
        "delvar": _fn_delvar,
        "listvars": _fn_listvars,
        "clearvars": _fn_clearvars,
    }

    # Safe binary operators
    @staticmethod
    def _safe_div(a: float, b: float) -> float:
        if b == 0:
            raise EvaluationError("Cannot divide by zero")
        return a / b

    @staticmethod
    def _safe_floordiv(a: float, b: float) -> float:
        if b == 0:
            raise EvaluationError("Cannot divide by zero")
        return a // b

    @staticmethod
    def _safe_mod(a: float, b: float) -> float:
        if b == 0:
            raise EvaluationError("Cannot divide by zero")
        return a % b

    BINOPS: dict[type[ast.operator], Any] = {
        ast.Add: (lambda a, b: a + b),
        ast.Sub: (lambda a, b: a - b),
        ast.Mult: (lambda a, b: a * b),
        ast.Div: _safe_div,
        ast.FloorDiv: _safe_floordiv,
        ast.Mod: _safe_mod,
        ast.Pow: _safe_pow,
        # Bitwise operators
        ast.LShift: _bitlshift_safe,
        ast.RShift: _bitrshift_safe,
        ast.BitOr: (lambda a, b: a | b),
        ast.BitXor: (lambda a, b: _require_int(a, "bitxor") ^ _require_int(b, "bitxor")),
        ast.BitAnd: (lambda a, b: a & b),
    }

    # Safe unary operators
    UNARYOPS: dict[type[ast.unaryop], Any] = {
        ast.UAdd: (lambda x: x),
        ast.USub: (lambda x: -x),
        ast.Invert: (lambda x: ~int(x)),
    }

    def __init__(
        self,
        allow_random: bool = True,
        allow_side_effects: bool = True,
    ) -> None:
        """Initialize evaluator with instance-level state.

        Each Evaluator instance has its own copy of constants, functions,
        user variables, and memory registers. This enables true instance
        isolation in EggCalcApp: variables set on one instance are not
        visible to other instances or the module-level default evaluator.

        Args:
            allow_random: If False, calls to random functions (random,
                randint, randrange, uniform, randn, gauss, seed) raise
                EvaluationError. Use to guarantee deterministic output.
            allow_side_effects: If False, calls to state-mutating functions
                (store/recall/M/Mplus/.../setvar/getvar/clearvars/...) raise
                EvaluationError. Use to prevent cross-request state pollution
                in long-running servers.
        """
        self.CONSTANTS = self.__class__.CONSTANTS.copy()
        self.FUNCTIONS = self.__class__.FUNCTIONS.copy()
        self._memory = Memory()
        self._user_variables: dict[str, Any] = {}
        self._var_lock = threading.Lock()
        self._depth = 0
        self._allow_random = allow_random
        self._allow_side_effects = allow_side_effects

    def visit(self, node: ast.AST) -> Any:
        """Visit a node with depth tracking to prevent deep recursion."""
        self._depth += 1
        if self._depth > MAX_NESTING_DEPTH:
            self._depth -= 1
            raise EvaluationError(f"Expression too deeply nested (max {MAX_NESTING_DEPTH})")
        try:
            return super().visit(node)
        finally:
            self._depth -= 1

    def _parse_unit(self, text: str) -> tuple[float, str | None]:
        """Parse a string that may contain a number and unit."""
        text = text.strip()

        # Check for unit suffix
        for unit in _SORTED_UNIT_ALIASES:
            if text.endswith(unit):
                num_str = text[: -len(unit)].strip()
                if num_str:
                    try:
                        num = float(num_str)
                        return num, UNIT_ALIASES[unit]
                    except ValueError:
                        pass

        # Check if it's just a unit
        if text in UNIT_ALIASES:
            return 1.0, UNIT_ALIASES[text]

        # Try to parse as plain number
        try:
            return float(text), None
        except ValueError:
            raise EvaluationError(f"Cannot parse: '{text}'")

    def _get_conversion_factor(self, from_unit: str, to_unit: str) -> float:
        """Get conversion factor from one unit to another.

        We read UNIT_CONVERSIONS via the units module to pick up the
        live binding (build_single-time imports are stale after
        _rebuild_conversions rebinds the global).
        """
        import sys

        _units: Any = None
        try:
            from . import units as _units
        except ImportError:
            # Assembled single-file mode: try sys.modules
            if "." in __name__:
                _units = sys.modules.get(__name__.rsplit(".", 1)[0] + ".units")
            else:
                _units = sys.modules.get("units")

        from_unit = normalize_unit(from_unit)
        to_unit = normalize_unit(to_unit)

        if from_unit == to_unit:
            return 1.0

        # Cross-form compound normalization: "m2" <-> "m**2", "cm3" <-> "cm**3", etc.
        if _units is not None and hasattr(_units, "_simplify_unit_string"):
            simplified_from = _units._simplify_unit_string(from_unit)
            if simplified_from is not None and simplified_from != from_unit:
                from_unit = simplified_from
            simplified_to = _units._simplify_unit_string(to_unit)
            if simplified_to is not None and simplified_to != to_unit:
                to_unit = simplified_to
            if _units is not None and hasattr(_units, "_expand_short_compound"):
                expanded_from = _units._expand_short_compound(from_unit)
                if expanded_from != from_unit:
                    from_unit = expanded_from
                expanded_to = _units._expand_short_compound(to_unit)
                if expanded_to != to_unit:
                    to_unit = expanded_to

        if from_unit == to_unit:
            return 1.0

        # Use the live binding if we found the units module, else the
        # import-time binding (which works when nothing was rebuilt).
        conversions = _units.UNIT_CONVERSIONS if _units is not None else UNIT_CONVERSIONS
        key = (from_unit, to_unit)
        if key in conversions:
            return conversions[key]

        raise EvaluationError(f"Cannot convert from '{from_unit}' to '{to_unit}'")

    def visit_Constant(self, node: ast.Constant) -> Any:
        """Visit a constant node."""
        if isinstance(node.value, bool):
            raise EvaluationError("Boolean literals are not supported")
        if isinstance(node.value, (int, float, complex)):
            return node.value
        if isinstance(node.value, str):
            if node.value in self.CONSTANTS:
                return self.CONSTANTS[node.value]
            # Check if it looks like a number with unit
            for unit in _SORTED_UNIT_ALIASES:
                if node.value.endswith(unit) and len(node.value) > len(unit):
                    num_part = node.value[: -len(unit)].strip()
                    if num_part:
                        try:
                            num = float(num_part)
                            return UnitValue(num, UNIT_ALIASES[unit])
                        except ValueError:
                            pass
            # Return plain string as-is (for function arguments like setvar("x", 10))
            return node.value
        if isinstance(node.value, bytes):
            raise EvaluationError(f"Unsupported constant: {node.value!r}")
        raise EvaluationError(f"Unsupported constant: '{node.value}'")

    def visit_Name(self, node: ast.Name) -> Any:
        """Visit a name node.

        Lookup order:
        1. UNIT_ALIASES (unit names; common short names like 'g', 'h', 'k')
        2. CONSTANTS (physical constants; 'r'/'R' for gas constant, long names like 'planck')
        3. FUNCTIONS (rejected as used-without-args)
        4. Per-instance user variables
        """
        if node.id in UNIT_ALIASES:
            return UnitValue(1.0, UNIT_ALIASES[node.id])
        if node.id in self.CONSTANTS:
            return self.CONSTANTS[node.id]
        if node.id in self.FUNCTIONS:
            raise EvaluationError(f"Function '{node.id}' used without arguments")
        with self._var_lock:
            if node.id in self._user_variables:
                return self._user_variables[node.id]
        raise EvaluationError(f"Unknown name: '{node.id}'")

    def visit_BinOp(self, node: ast.BinOp) -> Any:
        """Visit a binary operation node."""
        left = self.visit(node.left)
        right = self.visit(node.right)
        op_class = type(node.op)

        # Get the name of the right operand if it's a Name node (for compound unit detection)
        right_name: str | None = None
        right_unit_name: str | None = None
        if isinstance(node.right, ast.Name):
            right_name = node.right.id
            if right_name in UNIT_ALIASES:
                right_unit_name = UNIT_ALIASES[right_name]

        # Also detect a trailing unit on the right side when it is itself
        # a parenthesized or preprocessed expression. E.g., "(5m) / (2s)"
        # or "5m / 2*s" — the AST BinOp right is itself a BinOp/Name whose
        # visited value is a UnitValue. We handle that via right being a
        # UnitValue below, but we also accept a name-typed right whose
        # normalized form is a unit.
        if right_unit_name is None and isinstance(right, UnitValue) and right.unit:
            right_unit_name = right.unit

        # Extract values and units
        left_val = left.value if isinstance(left, UnitValue) else left
        left_unit = normalize_unit(left.unit) if isinstance(left, UnitValue) and left.unit else None
        right_val = right.value if isinstance(right, UnitValue) else right
        right_unit = (
            normalize_unit(right.unit) if isinstance(right, UnitValue) and right.unit else None
        )

        # Check if operation is addition/subtraction with incompatible units.
        # Reject the case where exactly one side has units and the other doesn't
        # — adding a dimensionless scalar to a unit (e.g., 5 + 3m) is not
        # well-defined and previously produced silently wrong results.
        is_add_sub = op_class in (ast.Add, ast.Sub)
        if is_add_sub:
            one_has_unit = bool(left_unit) != bool(right_unit)
            if one_has_unit:
                raise EvaluationError(
                    f"Cannot add/subtract a dimensionless value and a value with units "
                    f"('{left_unit or 'dimensionless'}' vs '{right_unit or 'dimensionless'}')"
                )
        if is_add_sub and not are_units_compatible(left_unit, right_unit):
            raise EvaluationError(
                f"Cannot add/subtract incompatible units: '{left_unit}' and '{right_unit}'"
            )

        # Handle unit conversion (only for addition/subtraction, not multiply/divide).
        # Temperature conversions are not multiplicative (they have an offset),
        # so use convert_temperature when both sides are temperatures.
        if is_add_sub and left_unit and right_unit and left_unit != right_unit:
            left_cat = get_unit_category(left_unit)
            right_cat = get_unit_category(right_unit)
            if left_cat == "temperature" and right_cat == "temperature":
                # Cross-scale addition of absolute temperatures (e.g. 10*C + 10*F)
                # is physically meaningless: the offset shifts the operand and yields
                # a plausible-looking but invalid temperature value. Subtraction is
                # permitted as a temperature delta.
                if op_class is ast.Add:
                    raise EvaluationError(
                        f"Cannot add absolute temperatures across scales: "
                        f"'{left_unit}' and '{right_unit}'. "
                        f"Convert one operand to the other scale first (e.g. via convert()), "
                        f"or subtract to get a temperature delta."
                    )
                try:
                    right_val = convert_temperature(cast(float, right_val), right_unit, left_unit)
                    right_unit = left_unit
                except Exception as e:
                    raise EvaluationError(
                        f"Cannot convert between temperatures '{right_unit}' and '{left_unit}': {e}"
                    )
            else:
                try:
                    factor = self._get_conversion_factor(right_unit, left_unit)
                    right_val = right_val * factor
                    right_unit = left_unit
                except EvaluationError:
                    try:
                        factor = self._get_conversion_factor(left_unit, right_unit)
                        left_val = left_val * factor
                        left_unit = right_unit
                    except EvaluationError:
                        raise EvaluationError(
                            f"Cannot convert between incompatible units: '{left_unit}' and '{right_unit}'"
                        )

        result_unit = left_unit or right_unit

        is_bitwise = op_class in (ast.BitAnd, ast.BitOr, ast.BitXor, ast.LShift, ast.RShift)
        if is_bitwise and (isinstance(left_val, float) or isinstance(right_val, float)):
            raise EvaluationError("Bitwise operations require integer operands, not floats")

        if op_class not in self.BINOPS:
            raise EvaluationError(f"Unsupported binary operator: '{node.op.__class__.__name__}'")

        try:
            result = self.BINOPS[op_class](left_val, right_val)
        except TypeError:
            raise EvaluationError(
                f"Cannot apply {op_class.__name__} to {type(left_val).__name__} and {type(right_val).__name__}"
            )
        except ZeroDivisionError:
            raise EvaluationError("Cannot divide by zero")

        # Check for NaN/inf in float/complex results (int results cannot be NaN/inf)
        if isinstance(result, complex):
            if (
                math.isnan(result.real)
                or math.isnan(result.imag)
                or math.isinf(result.real)
                or math.isinf(result.imag)
            ):
                raise EvaluationError("Result too large")
        elif isinstance(result, float):
            if math.isnan(result) or math.isinf(result):
                raise EvaluationError("Result too large")
            if abs(result) > MAX_RESULT_VALUE:
                raise EvaluationError("Result too large")

        # Check digit count for large int results from Add/Sub/Mult/Shift/Xor
        if isinstance(result, int) and op_class in (
            ast.Add,
            ast.Sub,
            ast.Mult,
            ast.BitXor,
            ast.LShift,
            ast.RShift,
        ):
            if _int_digit_count(result) > MAX_RESULT_DIGITS:
                raise EvaluationError(f"Result has too many digits (max {MAX_RESULT_DIGITS})")

        # Power operator with a unit on the right is physically nonsensical
        # (e.g., 2 ** 5m). Reject explicitly rather than silently dropping the
        # right-hand unit, which would let nonsense like "32.0 m" pass.
        is_pow_dispatch = op_class is ast.Pow
        if is_pow_dispatch and isinstance(right, UnitValue) and right.unit:
            raise EvaluationError(f"Cannot raise a value to a power with units ('{right.unit}')")

        # Power operator: handle unit exponentiation (e.g., 5m ** 2 -> 25 m**2)
        if is_pow_dispatch and isinstance(left, UnitValue) and left.unit:
            if isinstance(right, int):
                if right == 0:
                    return result  # anything**0 is dimensionless
                simplified = _pow_unit_string(left.unit, right) or f"{left.unit}**{right}"
                return UnitValue(result, simplified)
            if isinstance(right, float) and right.is_integer():
                int_exp = int(right)
                if int_exp == 0:
                    return result
                simplified = _pow_unit_string(left.unit, int_exp) or f"{left.unit}**{int_exp}"
                return UnitValue(result, simplified)
            # Non-integer exponent on a unit is physically nonsensical
            raise EvaluationError(f"Cannot raise unit '{left.unit}' to non-integer power")

        # Compound unit detection for division:
        # 0. UnitValue / UnitValue with same units -> dimensionless (e.g., 5m / 3m -> 1.666...)
        # 1. UnitValue / UnitValue with different units -> "left_unit/right_unit" (simplified)
        # 2. UnitValue / number whose AST name is a unit -> "left_unit/name" (e.g., km/h, mi/h)
        # 3. number / UnitValue with a unit -> "1/right_unit" (e.g., 5 / 2s -> 2.5 1/s)
        if op_class is ast.Div and isinstance(right, UnitValue) and right.unit:
            if isinstance(left, UnitValue) and left.unit:
                aligned_left, aligned_right = _align_compatible_units(left, right)
                if aligned_left.unit == aligned_right.unit:
                    return aligned_left.value / aligned_right.value
                compound = _simplify_unit_string(f"{aligned_left.unit}/{aligned_right.unit}")
                return UnitValue(aligned_left.value / aligned_right.value, compound)
            if not isinstance(left, UnitValue) and right_unit_name is None:
                compound = _simplify_unit_string(f"1/{right.unit}")
                if compound is None:
                    return left_val / right_val
                return UnitValue(left_val / right_val, compound)
            if not isinstance(left, UnitValue) and right_unit_name:
                compound = _simplify_unit_string(f"1/{right_unit_name}")
                if compound is None:
                    return left_val / right_val
                return UnitValue(left_val / right_val, compound)
        if op_class is ast.Div and isinstance(left, UnitValue) and left.unit:
            if not isinstance(right, UnitValue) and right_unit_name:
                compound = _simplify_unit_string(f"{left.unit}/{right_unit_name}")
                return UnitValue(left_val / right_val, compound)

        # Compound unit detection for floor division and modulo:
        # Same-unit floor division -> dimensionless (e.g., 6m // 3m -> 2).
        # Same-unit modulo -> remainder in divisor unit (e.g., 5m % 2m -> 1 m).
        # Compatible different-units scale to avoid precision loss (1 m // 1 cm -> 100, not 99).
        # Both cases delegate to the shared helpers in units.py so that
        # UnitValue.__floordiv__/__mod__ and the evaluator share one semantic path.
        if op_class in (ast.FloorDiv, ast.Mod) and isinstance(left, UnitValue) and left.unit:
            if isinstance(right, UnitValue) and right.unit:
                try:
                    if op_class is ast.FloorDiv:
                        return _floor_divide_quantities(left, right)
                    return _modulo_quantities(left, right)
                except ValueError as exc:
                    raise EvaluationError(str(exc)) from exc

        # Compound unit detection for multiplication:
        # UnitValue * UnitValue -> simplified "left_unit*right_unit" (m*m -> m**2)
        # UnitValue * number whose AST name is a unit -> "left_unit*name"
        if op_class is ast.Mult and isinstance(left, UnitValue) and left.unit:
            if isinstance(right, UnitValue) and right.unit:
                aligned_left, aligned_right = _align_compatible_units(left, right)
                compound = _simplify_unit_string(f"{aligned_left.unit}*{aligned_right.unit}")
                return UnitValue(aligned_left.value * aligned_right.value, compound)
            if not isinstance(right, UnitValue) and right_unit_name:
                compound = _simplify_unit_string(f"{left.unit}*{right_unit_name}")
                return UnitValue(left_val * right_val, compound)

        if result_unit is None:
            return result
        return UnitValue(result, result_unit)

    def visit_UnaryOp(self, node: ast.UnaryOp) -> Any:
        """Visit a unary operation node."""
        operand = self.visit(node.operand)
        op_class = type(node.op)

        if op_class not in self.UNARYOPS:
            raise EvaluationError(f"Unsupported unary operator: '{node.op.__class__.__name__}'")

        if op_class is ast.Invert and not isinstance(operand, int):
            raise EvaluationError("Bitwise NOT requires an integer operand")

        # UAdd is the identity — return operand directly to avoid nesting UnitValue.
        if op_class is ast.UAdd:
            return operand

        result = self.UNARYOPS[op_class](operand)

        # If the operation already returned a UnitValue (e.g., negating a UnitValue),
        # return it directly to avoid nesting UnitValue inside UnitValue.
        if isinstance(result, UnitValue):
            return result
        if isinstance(operand, UnitValue):
            return UnitValue(result, operand.unit)
        return result

    def visit_Attribute(self, node: ast.Attribute) -> Any:
        """Visit an attribute access node (e.g., (1+2j).real)."""
        value = self.visit(node.value)
        attr = node.attr
        if attr in ("real", "imag", "conjugate"):
            if isinstance(value, UnitValue):
                raw = value.value
            else:
                raw = value
            if attr == "real":
                return raw.real if isinstance(raw, complex) else raw
            elif attr == "imag":
                return raw.imag if isinstance(raw, complex) else 0.0
            elif attr == "conjugate":
                return raw.conjugate() if isinstance(raw, complex) else raw
        raise EvaluationError(f"Unsupported attribute access: '{attr}'")

    def visit_Call(self, node: ast.Call) -> Any:
        """Visit a function call node."""
        if node.keywords:
            raise EvaluationError("Keyword arguments are not supported")

        func_name = None
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "math":
                func_name = node.func.attr

        if func_name is None:
            raise EvaluationError(
                "Only simple function calls are supported " "(e.g. sin(x), sqrt(y))"
            )
        if func_name not in self.FUNCTIONS:
            raise EvaluationError(f"Function '{func_name}' is not allowed")

        if not self._allow_random and func_name in _RANDOM_FUNCTIONS:
            raise EvaluationError(
                f"Function '{func_name}' is non-deterministic and is disabled "
                f"in this Evaluator (allow_random=False)"
            )
        if not self._allow_side_effects and func_name in _SIDE_EFFECT_FUNCTIONS:
            raise EvaluationError(
                f"Function '{func_name}' mutates evaluator state and is "
                f"disabled in this Evaluator (allow_side_effects=False)"
            )

        # Special handling for temp function to preserve unit names
        if func_name == "temp":
            temp_args: list[Any] = []
            for i, arg in enumerate(node.args):
                result = self.visit(arg)
                if i > 0 and isinstance(result, UnitValue):
                    temp_args.append(result.unit or "K")
                elif isinstance(result, str):
                    temp_args.append(result)
                else:
                    temp_args.append(result)
            try:
                return self.FUNCTIONS[func_name](*temp_args)
            except (TypeError, ValueError) as e:
                raise EvaluationError(str(e)) from None

        # Special handling for convert function to preserve UnitValue arguments
        if func_name == "convert":
            convert_args: list[Any] = []
            for i, arg in enumerate(node.args):
                result = self.visit(arg)
                # Pass the full UnitValue, not just the value
                convert_args.append(result)
            try:
                return self.FUNCTIONS[func_name](*convert_args)
            except (TypeError, ValueError) as e:
                raise EvaluationError(str(e)) from None

        # Special handling for variable-management functions (setvar/getvar/delvar):
        # the first argument is a variable name (string), which must remain a
        # string even if it happens to collide with a constant or unit name
        # (e.g., setvar("pi", 5) should bind "pi", not replace math.pi).
        if func_name in _STRING_NAME_FUNCTIONS:
            name_args: list[Any] = []
            for i, arg in enumerate(node.args):
                if i == 0 and isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    name_args.append(arg.value)
                else:
                    name_args.append(self.visit(arg))
            try:
                return self.FUNCTIONS[func_name](*name_args)
            except (TypeError, ValueError) as e:
                raise EvaluationError(str(e)) from None

        # Extract values from arguments, handling UnitValues
        args: list[Any] = []
        for arg in node.args:
            result = self.visit(arg)
            # Reject UnitValue-with-unit for functions that semantically
            # require a dimensionless argument. The previous behavior was
            # to silently strip the unit and return a misleading
            # dimensionless result (e.g. fact(5m) -> 120).
            if (
                func_name in _DIMENSIONLESS_REQUIRED_FUNCTIONS
                and isinstance(result, UnitValue)
                and result.unit is not None
            ):
                raise EvaluationError(
                    f"Function '{func_name}()' requires a dimensionless "
                    f"argument, got value with unit '{result.unit}'"
                )
            if isinstance(result, UnitValue):
                args.append(result.value)
            else:
                args.append(result)

        try:
            return self.FUNCTIONS[func_name](*args)
        except OverflowError:
            raise EvaluationError("Result too large") from None
        except (ValueError, TypeError, ZeroDivisionError) as e:
            raise EvaluationError(str(e)) from None

    def _validate_node(self, node: ast.AST) -> None:
        """Validate that a node is safe to evaluate.

        Uses the precomputed _ALLOWED_AST_TYPES allowlist (built from
        known-safe expression patterns) as the primary security gate.
        Attribute access gets additional domain-specific validation.
        """
        node_type = type(node)

        # Primary allowlist check — covers Expression, BinOp, UnaryOp,
        # Constant, Name, Call, and all operator/unaryop/expr_context subclasses.
        if node_type in _ALLOWED_AST_TYPES:
            # Attribute access needs extra validation (restrict to math.* and real/imag/conjugate)
            if node_type is ast.Attribute:
                # Only allow attribute access on math module and
                # real/imag/conjugate on complex numbers
                attr_node = cast(ast.Attribute, node)
                if isinstance(attr_node.value, ast.Name) and attr_node.value.id == "math":
                    # Allow math.* - validated at call time
                    pass
                elif attr_node.attr in ("real", "imag", "conjugate"):
                    pass
                else:
                    raise EvaluationError(f"Attribute access '{attr_node.attr}' is not allowed")
            return

        # Explicit forbidden types with helpful error messages
        if node_type is ast.Compare:
            raise EvaluationError("Comparison operators are not supported")
        if node_type is ast.BoolOp:
            raise EvaluationError("Boolean operators are not supported")

        raise EvaluationError(f"Unsupported node type: '{node_type.__name__}'")

    def evaluate(self, expression: str) -> Any:
        """Evaluate an expression and return the result."""
        token = _current_evaluator.set(self)
        try:
            if not isinstance(expression, str):
                raise EvaluationError(
                    f"Expression must be a string, got {type(expression).__name__}"
                )
            if len(expression) > MAX_INPUT_LENGTH:
                raise EvaluationError(
                    f"Expression too long (max {MAX_INPUT_LENGTH} characters, got {len(expression)})"
                )
            try:
                tree = ast.parse(expression, mode="eval")
            except SyntaxError as e:
                raise EvaluationError(f"Invalid syntax: '{expression}'") from e

            # Cap total AST node count to bound the cost of validation/visit.
            # A long expression can contain many small nodes (e.g. 1+1+1+1+...)
            # that would each trigger _validate_node, so an explicit count cap
            # prevents CPU DoS by attackers crafting adversarial shapes.
            _MAX_AST_NODES = 10_000
            node_count = sum(1 for _ in ast.walk(tree))
            if node_count > _MAX_AST_NODES:
                raise EvaluationError(
                    f"Expression has too many AST nodes (max {_MAX_AST_NODES}, got {node_count})"
                )

            # Validate all nodes
            for node in ast.walk(tree):
                self._validate_node(node)

            result = self.visit(tree.body)

            # Handle result
            if isinstance(result, UnitValue):
                return _check_result_size(result)
            if isinstance(result, str):
                # Allow string results from function calls (e.g. primefactors),
                # but reject bare string literals as standalone expressions.
                if isinstance(tree.body, ast.Constant) and isinstance(tree.body.value, str):
                    raise EvaluationError(
                        "String literals are not supported as standalone expressions"
                    )
                return result
            if result is None:
                return None  # Functions like seed() and clearvars() return None
            if isinstance(result, (tuple, list)):
                return result
            if isinstance(result, dict):
                return result
            if not isinstance(result, (int, float, complex)):
                raise EvaluationError(f"Result must be a number, got '{type(result)}'")
            return _check_result_size(result)
        finally:
            _current_evaluator.reset(token)


def evaluate(expression: str) -> Any:
    """Evaluate a pre-normalized Python-AST-compatible expression.

    For raw input with spaces or natural language, use evaluate_raw() instead.

    This function never loads cwd-local config — it performs direct AST
    evaluation only.
    """
    return _default_evaluator.evaluate(expression)


def evaluate_raw(expression: str) -> Any:
    """Evaluate a raw expression with spaces and/or natural language.

    This function processes the expression through the full normalization
    pipeline, handling spaces inside parentheses and natural language conversion.

    Config loading: By default, library API calls do NOT load cwd-local
    eggcalc_config.py. Set EGGCALC_LOAD_CONFIG=1 to enable lazy config
    loading. CLI loads config by default via maybe_load_cli_config().

    Args:
        expression: A raw expression string (e.g., "(2 * 3)" or "five plus three")

    Returns:
        The result of the evaluation (int, float, str, or UnitValue).

    Raises:
        EvaluationError: If the expression is invalid or contains unsupported operations.
    """
    _ensure_config_loaded()
    from .normalize import NORMALIZE, PATTERNS, normalize_expression

    normalized, exit_code = normalize_expression(
        expression, NORMALIZE, PATTERNS, skip_validation=True
    )
    if exit_code != 0:
        raise EvaluationError(f"Invalid expression: {expression}")
    return _default_evaluator.evaluate(normalized)


class TimeoutError(Exception):
    """Raised when expression evaluation times out."""

    pass


def _evaluate_with_timeout_worker(
    expr: str,
    result_queue: multiprocessing.Queue,
    allow_random: bool = True,
    allow_side_effects: bool = True,
) -> None:
    """Run evaluation in a child process and put result in queue.

    Must be a module-level function (not nested) so it can be pickled
    by the 'spawn' multiprocessing start method.

    The ``allow_random`` and ``allow_side_effects`` flags configure the
    child process's default evaluator to match the parent's policy. In
    MCP mode the parent passes ``False`` for both, so children inherit
    the same restrictions without sharing any module-level state.

    Note: ``resource.setrlimit(RLIMIT_AS, ...)`` is a Linux/POSIX feature.
    On macOS, the kernel silently ignores ``RLIMIT_AS`` and the
    ``setrlimit`` call may return ``EINVAL`` for some process types, so
    the bound below is best-effort. Production deployments that need a
    hard memory cap on a hostile expression should run this on Linux
    or pair it with a cgroup/jail container-level limit.
    """
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
    except (ImportError, ValueError, OSError):
        # RLIMIT_AS may not be supported or enforced on all platforms (e.g., macOS).
        # On failure, we rely solely on the time-based timeout for protection.
        pass
    try:
        _ensure_config_loaded()
        configure_default_evaluator(
            allow_random=allow_random,
            allow_side_effects=allow_side_effects,
        )
        result = evaluate_raw(expr)
        result_queue.put(("ok", result))
    except Exception as exc:
        result_queue.put(("error", f"{type(exc).__name__}: {exc}"))


def _get_eval_multiprocessing_context() -> multiprocessing.context.BaseContext:
    """Return the multiprocessing context for timeout evaluation workers."""
    # Prefer spawn over fork: fork() in a multi-threaded process (e.g.
    # when called from the MCP server's ThreadPoolExecutor) can deadlock
    # the child because locks held by other threads are left in an
    # acquired state that the child cannot release.  spawn is ~300-400ms
    # slower due to re-importing, but it is safe in all contexts.
    if os.name != "nt" and "spawn" in multiprocessing.get_all_start_methods():
        return multiprocessing.get_context("spawn")
    if os.name != "nt" and "fork" in multiprocessing.get_all_start_methods():
        return multiprocessing.get_context("fork")
    return multiprocessing.get_context("spawn")


def evaluate_with_timeout(
    expression: str,
    timeout: float = 5.0,
    allow_random: bool | None = None,
    allow_side_effects: bool | None = None,
) -> Any:
    """Evaluate an expression with a timeout for untrusted input.

    This is the recommended function for evaluating expressions from
    untrusted sources (web requests, user input, etc.).

    Uses multiprocessing.Process to run evaluation in a separate process
    that can be reliably terminated.
    A ThreadPoolExecutor's future.cancel() does NOT stop a running thread.

    Concurrency is bounded by _EVAL_SPAWN_SEMAPHORE to prevent fork-bomb
    scenarios when multiple callers invoke this function simultaneously.

    Args:
        expression: A raw expression string (with spaces, natural language, etc.)
        timeout: Maximum time in seconds (default: 5.0)
        allow_random: If provided, configures the child process's default
            evaluator to permit or deny random functions (random, randint,
            ...). When ``None`` (the default), the parent process's current
            setting is forwarded.
        allow_side_effects: If provided, configures the child process's
            default evaluator to permit or deny state-mutating functions
            (setvar, store, ...). When ``None``, the parent process's
            current setting is forwarded.

    Returns:
        The result of the evaluation (int, float, str, or UnitValue).

    Raises:
        TimeoutError: If evaluation exceeds the timeout.
        EvaluationError: If expression is invalid or contains unsupported operations.

    Note:
        Expressions that exceed MAX_EXPONENT (10000) or MAX_FACTORIAL (1000)
        will fail with EvaluationError before the timeout is reached.

    Example:
        >>> result = evaluate_with_timeout("sum([i**2 for i in range(100)])", timeout=1.0)
        # May raise TimeoutError for slow expressions
    """
    if allow_random is None:
        allow_random = _default_evaluator._allow_random
    if allow_side_effects is None:
        allow_side_effects = _default_evaluator._allow_side_effects
    ctx = _get_eval_multiprocessing_context()
    queue: multiprocessing.Queue = ctx.Queue()
    proc: Any = None
    # RAII permit for the eval spawn semaphore. Acquire (with timeout) or raise.
    # The permit's __exit__ guarantees release even if the worker is cancelled,
    # panics, or returns early before we reach the end of the block.
    # This replaces the previous manual acquire + scattered release calls
    # (including the unconditional release inside the finally after child cleanup).
    if not _EVAL_SPAWN_SEMAPHORE.acquire(timeout=_EVAL_SPAWN_ACQUIRE_TIMEOUT):
        raise EvaluationError(
            f"Could not acquire spawn slot after {_EVAL_SPAWN_ACQUIRE_TIMEOUT}s "
            f"(all {_MAX_CONCURRENT_EVAL_SPAWNS} slots busy)"
        )
    permit = _EvalSpawnPermit(_EVAL_SPAWN_SEMAPHORE)
    with permit:
        try:
            proc = ctx.Process(  # type: ignore[attr-defined]
                target=_evaluate_with_timeout_worker,
                args=(expression, queue, allow_random, allow_side_effects),
            )
            proc.start()
        except Exception:
            # Permit will release on this raise path.
            raise

        try:
            status, value = queue.get(timeout=timeout)
        except _QueueEmpty:
            if proc is not None and not proc.is_alive():
                exitcode = proc.exitcode
                raise EvaluationError(
                    "Evaluation worker exited before returning a result"
                    + (f" (exit code {exitcode})" if exitcode is not None else "")
                )
            raise TimeoutError(f"Evaluation timed out after {timeout} seconds")
        except Exception as exc:
            logging.warning(
                "Unexpected exception reading evaluation result: %s",
                type(exc).__name__,
                exc_info=True,
            )
            raise TimeoutError(f"Evaluation timed out after {timeout} seconds")
        finally:
            try:
                queue.close()
            except Exception:
                pass
            try:
                queue.join_thread()
            except Exception:
                pass
            if proc is not None:
                if proc.is_alive():
                    proc.terminate()
                    proc.join(timeout=2)
                if proc.is_alive():
                    proc.kill()
                    proc.join(timeout=1)
                # If the process survived terminate+kill, register it for
                # defensive cleanup by the MCP server's orphan tracker.
                if proc.is_alive() and _mcp_mode:
                    with _orphaned_eval_lock:
                        _orphaned_eval_processes.add(proc)
                        _orphaned_eval_order.append(proc)
                        while len(_orphaned_eval_order) > MAX_ORPHANED_PROCESSES:
                            oldest = _orphaned_eval_order.pop(0)
                            _orphaned_eval_processes.discard(oldest)
                try:
                    proc.close()
                except Exception:
                    pass

        if status == "error":
            raise EvaluationError(value)
        return value
    # Permit released on exit of the `with` (normal return, exception during
    # spawn/queue.get, or cancellation). The guard owns the slot accounting;
    # there are no remaining manual release() calls for this semaphore in this
    # function.


_default_evaluator = Evaluator(
    allow_random=not _mcp_mode,
    allow_side_effects=not _mcp_mode,
)


_check_constant_unit_collisions()


def configure_default_evaluator(
    allow_random: bool | None = None,
    allow_side_effects: bool | None = None,
) -> None:
    """Update the default evaluator's allow-flags at runtime.

    This is intended to be called by transport layers (e.g. the MCP server's
    ``main()``) after setting ``_mcp_mode``. Pass only the flags you want
    to change; ``None`` leaves the current setting intact.

    Args:
        allow_random: New value for ``Evaluator._allow_random`` (or None to keep).
        allow_side_effects: New value for ``Evaluator._allow_side_effects``
            (or None to keep).
    """
    if allow_random is not None:
        _default_evaluator._allow_random = allow_random
    if allow_side_effects is not None:
        _default_evaluator._allow_side_effects = allow_side_effects


def get_default_evaluator() -> Evaluator:
    """Get the default evaluator instance.

    Returns:
        The default Evaluator instance used by module-level functions.
    """
    return _default_evaluator


def create_evaluator(
    allow_random: bool = False,
    allow_side_effects: bool = False,
) -> Evaluator:
    """Create an isolated Evaluator instance with specified policy.

    This is the recommended way to create evaluator instances for MCP
    servers or other contexts that need dedicated evaluation policy
    without mutating the global default evaluator.

    Args:
        allow_random: If False, random functions raise EvaluationError.
        allow_side_effects: If False, state-mutating functions raise EvaluationError.

    Returns:
        A new Evaluator instance with independent constants, functions,
        user variables, and memory.
    """
    return Evaluator(allow_random=allow_random, allow_side_effects=allow_side_effects)


class EggCalcApp:
    """Thread-safe wrapper for eggcalc, optimized for webapp usage.

    Provides caching, instance isolation, and async support for
    long-running applications like web servers.

    Each EggCalcApp instance has its own isolated evaluator with its own
    constants and functions. Registering constants/functions on one instance
    does not affect other instances.

    Usage:
        app = EggCalcApp()
        result = app.calculate("5 + 3")
        result = app.calculate("30m + 100ft")  # with units
    """

    def __init__(
        self,
        cache_size: int = DEFAULT_CACHE_SIZE,
        enable_cache: bool = True,
    ) -> None:
        """Initialize EggCalcApp.

        Args:
            cache_size: LRU cache size (default 1000)
            enable_cache: Whether to enable caching (default True)
        """
        self._evaluator = Evaluator()
        self._enable_cache = enable_cache
        self._cache: OrderedDict[str, Any] | None = OrderedDict() if enable_cache else None
        self._lock = threading.Lock()
        self._cache_max_size = max(0, cache_size)

    def calculate(self, expression: str) -> Any:
        """Evaluate an expression (thread-safe).

        Args:
            expression: Math expression (e.g., "5 + 3" or "five plus two")

        Returns:
            Result (int, float, str, or UnitValue)

        Raises:
            EvaluationError: If expression is invalid
        """
        use_cache = self._cache is not None and not _expression_bypasses_cache(expression)

        if use_cache:
            with self._lock:
                assert self._cache is not None
                if expression in self._cache:
                    self._cache.move_to_end(expression)
                    return self._cache[expression]

        result = self._evaluate_internal(expression)

        if use_cache:
            with self._lock:
                assert self._cache is not None
                if self._cache_max_size == 0:
                    return result
                while len(self._cache) >= self._cache_max_size:
                    self._cache.popitem(last=False)
                self._cache[expression] = result

        return result

    async def calculate_async(self, expression: str) -> Any:
        """Evaluate an expression asynchronously (thread-safe).

        Args:
            expression: Math expression

        Returns:
            Result (int, float, str, or UnitValue)
        """
        import asyncio

        def _eval() -> Any:
            return self.calculate(expression)

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _eval)

    def _evaluate_internal(self, expression: str) -> Any:
        """Internal evaluation that uses the instance's evaluator."""
        from .normalize import NORMALIZE, PATTERNS, normalize_expression

        normalized, exit_code = normalize_expression(
            expression, NORMALIZE, PATTERNS, skip_validation=True
        )
        if exit_code != 0:
            raise EvaluationError(f"Invalid expression: {expression}")

        return self._evaluator.evaluate(normalized)

    def register_constant(self, name: str, value: float) -> None:
        """Register a custom constant on this instance (thread-safe).

        Unlike the global register_constant function, this only affects
        this EggCalcApp instance.
        """
        with self._lock:
            self._evaluator.CONSTANTS[name] = value
        self.clear_cache()

    def register_function(self, name: str, func: Any) -> None:
        """Register a custom function on this instance (thread-safe).

        Unlike the global register_function function, this only affects
        this EggCalcApp instance.
        """
        with self._lock:
            self._evaluator.FUNCTIONS[name] = func
        self.clear_cache()

    def clear_cache(self) -> None:
        """Clear the evaluation cache."""
        if self._cache is not None:
            with self._lock:
                self._cache.clear()

    @property
    def cache_size(self) -> int:
        """Return current cache size."""
        if self._cache is None:
            return 0
        with self._lock:
            return len(self._cache)
