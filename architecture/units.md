# units.py — Unit Definitions and Conversions

2093 lines. Provides comprehensive unit conversion support for the calculator.

## Overview

The `units` module handles:
- Unit value representation with automatic arithmetic
- Conversion between units of the same category
- Temperature conversions (with offset handling)
- Unit aliasing and normalization

## Key Exports

```python
from eggcalc.units import (
    UnitValue,              # Value with optional unit
    normalize_unit,         # Normalize unit string
    get_conversion_factor,  # Get conversion factor between units
    get_all_units,          # List all known units
    is_unit,                # Check if string is a valid unit
    are_units_compatible,   # Check if units can be converted
    convert_temperature,    # Temperature conversion
    FLOAT_EPSILON,          # 1e-10 for float comparison
)
```

## UnitValue Class

Represents a numeric value with optional units:

```python
uv = UnitValue(30, "m")  # 30 meters

# Arithmetic with automatic unit conversion
uv + UnitValue(100, "ft")  # → UnitValue(60.48, "m")

# Unit conversion
uv.convert_to("ft")  # → UnitValue(98.425, "ft")
```

### Constructor
```python
UnitValue(value: float, unit: str | None = None)
```

### Properties
| Property | Type | Description |
|----------|------|-------------|
| `value` | float | Numeric value |
| `unit` | str \| None | Unit string |

### Methods
| Method | Returns | Description |
|--------|---------|-------------|
| `convert_to(target_unit)` | UnitValue | Convert to different unit |
| `__repr__()` | str | Human-readable representation |
| `__str__()` | str | String representation (same as `__repr__`) |
| `__format__(format_spec)` | str | Formatted string with unit |
| `__eq__(other)` | bool | Equality comparison with FLOAT_EPSILON |
| `__hash__()` | int | Hashable for use in sets/dicts |
| `__add__ / __radd__` | UnitValue | Addition with unit conversion |
| `__sub__ / __rsub__` | UnitValue | Subtraction with unit conversion |
| `__mul__ / __rmul__` | UnitValue | Multiplication |
| `__truediv__ / __rtruediv__` | UnitValue | Division |
| `__pow__` | UnitValue | Power operation |
| `__neg__` | UnitValue | Unary negation |
| `__pos__` | UnitValue | Unary positive |
| `__abs__` | UnitValue | Absolute value |
| `__round__` | UnitValue | Rounding |
| `__complex__` | complex | Complex conversion |
| `__int__` | int | Integer conversion |
| `__float__` | float | Float conversion |

### Arithmetic Operations

| Operation | Result Unit | Notes |
|-----------|-------------|-------|
| `UnitValue + UnitValue` | Common unit | Converts if compatible |
| `UnitValue - UnitValue` | Common unit | Converts if compatible |
| `UnitValue * UnitValue` | Compound (e.g., `m*m`) | |
| `UnitValue / UnitValue` | Compound (e.g., `m/s`) | |
| `UnitValue ** n` | Same unit | Power of value, keeps unit |

**Important:** Adding/subtracting incompatible units raises `ValueError`.

### Scalar + UnitValue Operations

Adding or subtracting scalars from dimensional UnitValues is **not allowed** and raises
`ValueError`. Dimensionless `UnitValue` instances can be added to scalars or other
dimensionless `UnitValue` instances.

```python
UnitValue(3, "m") + 5                  # → ValueError
5 + UnitValue(3, "m")                  # → ValueError
UnitValue(3, "m") + UnitValue(5, None) # → ValueError
UnitValue(3, None) + 5                 # → UnitValue(8, None)
```

This behavior is intentional — mixing dimensionless values with dimensional values
(like meters) is physically meaningless. Make both operands dimensional when the
quantity should have a unit:

```python
uv = UnitValue(3, "m")
uv + UnitValue(5, "m")     # → UnitValue(8.0, "m") — both have same unit
```

## Unit Categories

Units are organized by category (length, mass, time, etc.):

| Category | Base Unit | Example Units |
|----------|-----------|---------------|
| Length | m | km, cm, mm, in, ft, yd, mi, ly, nm, μm, mi |
| Time | s | ms, us, ns, min, h, d, wk, yr |
| Mass | kg | g, mg, lb, oz, t, kt, Mt |
| Data | B | KB, MB, GB, TB, PB, EB |
| Volume | L | mL, gal, qt, pt, cup, fl oz, bbl |
| Pressure | Pa | kPa, MPa, GPa, bar, mbar, psi, atm |
| Energy | J | kJ, MJ, GJ, cal, kcal, Wh, kWh, BTU, eV |
| Power | W | mW, kW, MW, GW, hp |
| Speed | m/s | km/h, mph, kn, mach, kph, mps |
| Temperature | K | C, F, R (uses offset-based conversion, not UNIT_BASE) |
| Frequency | Hz | kHz, MHz, GHz, THz |
| Force | N | mN, kN, MN, GN, dyne, lbf |
| Voltage | V | mV, μV, kV, MV |
| Current | A | mA, μA, kA |
| Angle | rad | deg (grad, arcmin, arcsec not implemented) |
| Area | m² | km², cm², mm², ha, acre, ft², sqft, in², mi², yd² |
| Data Rate | bps | Kbps, Mbps, Gbps |

**Note:** Temperature conversions use a separate offset-based mechanism via `TEMPERATURE_CONVERSIONS` rather than multiplicative factors in `UNIT_BASE`. This is a special case because temperature conversions require offset math (e.g., C = F × 5/9 - 32).

## Unit Definition Structure (UNIT_BASE)

```python
UNIT_BASE: dict[str, dict[str, float]] = {
    "m": {           # Base unit for length
        "m": 1.0,     # meter
        "km": 1000.0,
        "cm": 0.01,
        "mm": 0.001,
        "ft": 0.3048,  # foot
        "in": 0.0254,  # inch
        ...
    },
    "s": {           # Base unit for time
        "s": 1.0,
        "min": 60.0,
        "h": 3600.0,
        ...
    },
    ...
}
```

## Conversion Factor

Conversion between units uses multiplicative factors:

```python
get_conversion_factor("km", "m")      # → 1000.0
get_conversion_factor("ft", "m")      # → 0.3048
get_conversion_factor("kg", "lb")     # → 0.453592
```

For temperature, special offset math is used (not multiplicative).

## Temperature Conversions

Temperature uses offset-based conversion, not multiplicative factors:

```python
convert_temperature(0, "C", "F")  # → 32.0
convert_temperature(100, "C", "F")  # → 212.0
convert_temperature(0, "K", "C")  # → -273.15
```

### Temperature Scale Formulas

The calculator supports four temperature scales:

| From/To | Celsius (C) | Fahrenheit (F) | Kelvin (K) | Rankine (R) |
|---------|-------------|----------------|------------|-------------|
| Celsius | — | C × 9/5 + 32 | C + 273.15 | (C + 273.15) × 9/5 |
| Fahrenheit | (F - 32) × 5/9 | — | (F - 32) × 5/9 + 273.15 | F + 459.67 |
| Kelvin | K - 273.15 | K × 9/5 - 459.67 | — | K × 9/5 |
| Rankine | R × 5/9 - 273.15 | R - 459.67 | R × 5/9 | — |

**Warning:** Converting temperature to non-temperature units gives physically meaningless results.

## Unit Aliases (UNIT_ALIASES)

Maps unit variations to canonical forms:

```python
UNIT_ALIASES = {
    "meters": "m",
    "kilometers": "km",
    "centimeters": "cm",
    "millimeters": "mm",
    "seconds": "s",
    "minutes": "min",
    "hours": "h",
    "days": "d",
    "grams": "g",
    "kilograms": "kg",
    ...
}
```

Used by `normalize_unit()` to standardize unit input.

## Functions

### `normalize_unit(unit: str) -> str`
Normalizes a unit string to canonical form:
```python
normalize_unit("meters")  # → "m"
normalize_unit("kilometers")  # → "km"
```

### `is_unit(s: str) -> bool`
Checks if a string is a valid unit:
```python
is_unit("m")     # → True
is_unit("kg")    # → True
is_unit("foo")   # → False
```

### `get_conversion_factor(from_unit: str, to_unit: str) -> float`
Returns the multiplicative factor to convert from one unit to another:
```python
get_conversion_factor("km", "m")   # → 1000.0
get_conversion_factor("m", "km")   # → 0.001
```

### `are_units_compatible(unit1: str | None, unit2: str | None) -> bool`
Checks if two units can be converted (same category):
```python
are_units_compatible("m", "ft")     # → True (both length)
are_units_compatible("m", "kg")     # → False (length vs mass)
are_units_compatible(None, None)    # → True (both dimensionless)
are_units_compatible("m", None)     # → False (dimensional vs dimensionless)
```

### `get_unit_category(unit: str) -> str | None`
Returns the category of a unit:
```python
get_unit_category("m")    # → "length"
get_unit_category("kg")   # → "mass"
get_unit_category("K")    # → "temperature"
get_unit_category("foo") # → None
```

### `get_all_units() -> list[str]`
Returns all known unit names.

## Prefixed Units

The system handles SI prefixes:

| Prefix | Symbol | Factor |
|--------|--------|--------|
| milli | m | 0.001 |
| centi | c | 0.01 |
| deci | d | 0.1 |
| kilo | k | 1000 |
| mega | M | 1000000 |
| giga | G | 1000000000 |
| tera | T | 1000000000000 |

Examples: `kN` (kilonewton), `mV` (millivolt), `mA` (milliampere)

## Constants

| Constant | Value | Description |
|----------|-------|-------------|
| `FLOAT_EPSILON` | 1e-10 | For float comparison in equality |
| `MAX_RESULT_VALUE` | 1e308 | Maximum value (matches evaluator) |

## Module Dependencies

```
units.py (no dependencies on other eggcalc modules)
```

Independent module with no imports from other eggcalc modules.
