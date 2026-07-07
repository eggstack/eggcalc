"""
User-defined configuration for eggcalc.

This file allows you to add custom units, constants, and functions.
Edit this file to extend eggcalc's functionality.

Examples:
---------

# Add a custom constant:
CUSTOM_CONSTANTS = {
    "myconst": 42.0,
}

# Add custom units (base_unit -> {unit: factor_to_base}):
CUSTOM_UNITS = {
    "dozen": {
        "dozen": 12.0,
        "dz": 12.0,
    },
}

# Add custom unit aliases:
CUSTOM_ALIASES = {
    "dozen": "dozen",
    "dz": "dozen",
}

# Add custom functions:
CUSTOM_FUNCTIONS = {
    "mylog": lambda x: math.log(x, 10),  # base-10 log
}

# Add temperature conversions (from, to) -> (multiplier, offset):
CUSTOM_TEMP_CONVERSIONS = {
    ("R", "K"): (5.0/9.0, 0),
    ("K", "R"): (9.0/5.0, 0),
    ("R", "F"): (1.0, -459.67),
    ("F", "R"): (1.0, 255.372222),
    ("R", "C"): (5.0/9.0, -273.15),
    ("C", "R"): (9.0/5.0, 273.15),
}

# Add custom word-to-number mappings:
CUSTOM_NUMBER_WORDS = {
    "dozen": "12",
}

# Add custom operator words:
CUSTOM_OPERATOR_WORDS = {
    "plus": "+",
    "minus": "-",
}
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

CUSTOM_CONSTANTS: dict[str, float] = {}

CUSTOM_UNITS: dict[str, dict[str, float]] = {}

CUSTOM_ALIASES: dict[str, str] = {}

CUSTOM_FUNCTIONS: dict[str, Callable[..., Any]] = {}

CUSTOM_TEMP_CONVERSIONS: dict[tuple[str, str], tuple[float, float]] = {}

CUSTOM_NUMBER_WORDS: dict[str, str] = {}

CUSTOM_OPERATOR_WORDS: dict[str, str] = {}
