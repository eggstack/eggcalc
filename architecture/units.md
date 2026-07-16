# units.py — Unit Definitions and Conversions

2136 lines. Provides comprehensive unit conversion support for the calculator.

## Table of Contents

- [Overview](#overview)
- [Key Exports](#key-exports)
- [Type Aliases](#type-aliases)
- [Constants](#constants)
- [UnitValue Class](#unitvalue-class)
- [Unit Categories](#unit-categories)
- [Unit Definition Structure](#unit-definition-structure)
- [Unit Aliases](#unit-aliases)
- [Compound Unit System](#compound-unit-system)
- [Functions](#functions)
- [Internal Functions](#internal-functions)
- [Module Dependencies](#module-dependencies)

## Overview

The `units` module handles:
- Unit value representation with automatic arithmetic
- Conversion between units of the same category
- Temperature conversions (with offset handling)
- Unit aliasing and normalization
- Compound unit parsing and simplification (area, speed, etc.)
- Thread-safe unit table mutations

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
    get_unit_category,      # Get category for a unit
    FLOAT_EPSILON,          # 1e-10 for float comparison
    MAX_RESULT_VALUE,       # 1e308 maximum result magnitude
)
```

## Type Aliases

```python
Numeric = float | int | complex
```

Used throughout the module for type annotations on arithmetic operands and return values.

## Constants

| Constant | Value | Description |
|----------|-------|-------------|
| `FLOAT_EPSILON` | `1e-10` | For float comparison in equality |
| `MAX_RESULT_VALUE` | `1e308` | Maximum result magnitude (matches evaluator) |

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
UnitValue(value: float | complex, unit: str | None = None)
```

- Normalizes complex values with zero imaginary part to `float` (preserves hash contract).
- Raises `ValueError` for non-finite values (`inf`, `nan`).

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `value` | `float \| complex` | Numeric value |
| `unit` | `str \| None` | Unit string |

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `convert_to(target_unit)` | `UnitValue` | Convert to different unit of same category |
| `__repr__()` | `str` | Human-readable representation |
| `__str__()` | `str` | Same as `__repr__` |
| `__format__(format_spec)` | `str` | Formatted value with unit |
| `__eq__(other)` | `bool` | Strict equality (value and unit must match exactly) |
| `__hash__()` | `int` | Hashable for use in sets/dicts |
| `__add__ / __radd__` | `UnitValue` | Addition with unit conversion |
| `__sub__ / __rsub__` | `UnitValue` | Subtraction with unit conversion |
| `__mul__ / __rmul__` | `UnitValue` | Multiplication (may produce compound units) |
| `__truediv__ / __rtruediv__` | `UnitValue` | Division (may produce compound units) |
| `__floordiv__ / __rfloordiv__` | `UnitValue` | Floor division |
| `__mod__ / __rmod__` | `UnitValue` | Modulo |
| `__pow__` | `UnitValue` | Power (integer exponents only for dimensional units) |
| `__neg__` | `UnitValue` | Unary negation |
| `__pos__` | `UnitValue` | Unary positive |
| `__abs__` | `UnitValue` | Absolute value |
| `__round__(ndigits)` | `UnitValue` | Rounding |
| `__complex__()` | `complex` | Complex conversion |
| `__int__()` | `int` | Integer conversion |
| `__float__()` | `float` | Float conversion |

### Arithmetic Operations

| Operation | Result Unit | Notes |
|-----------|-------------|-------|
| `UnitValue + UnitValue` | Common unit | Converts right operand to left operand's unit if compatible |
| `UnitValue - UnitValue` | Common unit | Converts right operand to left operand's unit if compatible |
| `UnitValue * UnitValue` | Compound (e.g. `m*m`) | Auto-aligns compatible units before multiplying |
| `UnitValue / UnitValue` | Compound (e.g. `m/s`) | Auto-aligns compatible units before dividing; same-unit division cancels to dimensionless |
| `UnitValue // UnitValue` | Dimensionless or `EvaluationError` | Floor division of compatible units returns a dimensionless quotient; incompatible units raise `EvaluationError` |
| `UnitValue % UnitValue` | Dimensioned remainder or `EvaluationError` | Same-unit modulo returns a remainder in the divisor unit; incompatible units raise `EvaluationError` |
| `UnitValue ** n` | Power of unit | E.g. `m ** 2` → `m**2`; integer exponents only for dimensional units |

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

### Division Edge Cases

- Dividing a dimensionless `UnitValue` by a dimensional one produces a reciprocal unit: `UnitValue(1, None) / UnitValue(1, "s")` → `1/1 s` (i.e. `1/s`).
- `__rtruediv__` on a dimensional `UnitValue` produces a reciprocal: `5 / UnitValue(2, "m")` → `2.5 1/m`.
- `__rfloordiv__` and `__rmod__` on a dimensional `UnitValue` raise `ValueError`.

### Power Edge Cases

- Raising a dimensional `UnitValue` to the 0th power returns dimensionless: `UnitValue(3, "m") ** 0` → `UnitValue(1, None)`.
- Non-integer exponents on dimensional units raise `ValueError`.
- Compound units are exponentiated across the full expression: `(m/s) ** 2` → `m**2/s**2`.

### Overflow Protection

`UnitValue._check_overflow(result)` is called after every arithmetic operation. It raises `OverflowError` for non-finite float/complex results. Integer results skip the magnitude check (digit count is the relevant limit for arbitrary-precision ints).

## Unit Categories

Units are organized by category (base unit → friendly name):

| Category | Base Key | Friendly Name | Example Units |
|----------|----------|---------------|---------------|
| Length | `m` | `length` | km, cm, mm, in, ft, yd, mi, ly, au, pc, angstrom, fermi, nmi, furlong, chain, rod, fathom, smoot |
| Time | `s` | `time` | ms, us, ns, ps, min, h, d, wk, yr, fortnight, decade, century, millennium |
| Data storage | `B` | `data` | KB, MB, GB, TB, PB, EB, ZB, YB, bit |
| Data rate | `bps` | `data_rate` | Kbps, Mbps, Gbps |
| Mass | `kg` | `mass` | g, mg, ug, ng, lb, oz, ton, tonne, long_ton, stone, slug, ct, gr, dr |
| Volume | `L` | `volume` | mL, uL, gal, qt, pt, cup, floz, tbsp, tsp, m3, cm3, ft3, in3, yd3, mm3, km3, mi3 |
| Pressure | `Pa` | `pressure` | kPa, MPa, GPa, bar, mbar, atm, psi, mmHg, torr, inHg, mmH2O, inH2O |
| Energy | `J` | `energy` | kJ, MJ, GJ, cal, kcal, Wh, kWh, BTU, eV |
| Power | `W` | `power` | mW, kW, MW, GW, hp |
| Force | `N` | `force` | mN, kN, dyne, lbf |
| Voltage | `V` | `voltage` | mV, uV, kV |
| Current | `A` | `current` | mA, uA |
| Angle | `rad` | `angle` | deg |
| Speed | `m/s` | `speed` | km/h, mph, kn, mach |
| Area | `m2` | `area` | km2, cm2, mm2, ha, acre, ft2, in2, mi2, yd2 |
| Frequency | `Hz` | `frequency` | kHz, MHz, GHz, THz |
| Temperature | *(manual)* | `temperature` | K, C, F, Ra (offset-based, not in `UNIT_BASE`) |

**Note:** Temperature conversions use a separate offset-based mechanism via `TEMPERATURE_CONVERSIONS` rather than multiplicative factors in `UNIT_BASE`. Temperature units (`K`, `C`, `F`, `Ra`) are registered in `UNIT_CATEGORIES_EXTRA` and cannot be converted to non-temperature units.

## Unit Definition Structure

### UNIT_BASE

```python
UNIT_BASE: dict[str, dict[str, float]] = {
    "m": {           # Base unit for length
        "m": 1.0,     # meter
        "km": 1000.0,
        "cm": 0.01,
        "mm": 0.001,
        "ft": 0.3048,  # foot
        "in": 0.0254,  # inch (aliased to "inch" in UNIT_ALIASES due to Python keyword conflict)
        ...
    },
    "s": { ... },    # Time (base: seconds)
    "B": { ... },    # Data storage (binary 1024 prefixes)
    "bps": { ... },  # Data transfer rate (decimal 1000 prefixes)
    "kg": { ... },   # Mass (base: kilograms)
    "L": { ... },    # Volume (base: liters)
    "Pa": { ... },   # Pressure (base: Pascal)
    "J": { ... },    # Energy (base: Joules)
    "W": { ... },    # Power (base: Watts)
    "N": { ... },    # Force (base: Newtons)
    "V": { ... },    # Voltage (base: Volts)
    "A": { ... },    # Current (base: Amperes)
    "rad": { ... },  # Angle (base: radians)
    "m/s": { ... },  # Speed (base: meters per second)
    "m2": { ... },   # Area (base: square meters)
    "Hz": { ... },   # Frequency (base: Hertz)
}
```

Each entry maps a base unit key to a dictionary of `{unit_alias: factor_to_base}`. Conversion between two units in the same category is `factor_from / factor_to`.

**Important:** The `"in"` (inches) entry in `UNIT_BASE` is never used as a `from_unit` in the conversion table because it conflicts with Python's `in` keyword in AST parsing. Callers normalize `"in"` to `"inch"` via `UNIT_ALIASES` before consulting the conversion table.

### UNIT_CATEGORIES and UNIT_CATEGORIES_EXTRA

```python
UNIT_CATEGORIES: dict[str, str]  # Auto-derived from UNIT_BASE, remapped via _BASE_CATEGORY
UNIT_CATEGORIES_EXTRA: dict[str, str] = {
    "K": "temperature", "C": "temperature", "F": "temperature", "Ra": "temperature",
}
```

`UNIT_CATEGORIES` is built by iterating `UNIT_BASE` to get `{unit: base_key}`, then remapping each `base_key` to a friendly category name via `_BASE_CATEGORY` (e.g. `"m"` → `"length"`). `UNIT_CATEGORIES_EXTRA` adds temperature units manually since they use offset math rather than multiplicative factors.

### Unit Prefixes

SI prefixes are handled by explicit entries in `UNIT_BASE`, not by a general prefix parser. Supported prefixes:

| Prefix | Symbol | Factor | Example |
|--------|--------|--------|---------|
| micro | u/μ | 1e-6 | um, us, ug, uL, uV, uA |
| milli | m | 0.001 | mm, ms, mg, mL, mV, mA, mbar, mW, mN |
| centi | c | 0.01 | cm |
| kilo | k | 1000 | km, kHz, kN, kV, kPa, kJ, kW |
| mega | M | 1e6 | MHz, MW, MPa, MJ, MB |
| giga | G | 1e9 | GHz, GW, GPa, GJ, GB |
| tera | T | 1e12 | THz, TB |

Data storage uses binary (1024) prefixes. Data transfer rate uses decimal (1000) prefixes.

## Unit Aliases

`UNIT_ALIASES: dict[str, str]` maps all recognized unit strings to their canonical forms. Includes:

- Plurals (`meters` → `m`)
- British spellings (`metre` → `m`, `litre` → `L`)
- Unicode prefixes (`μm` → `um`, `μs` → `us`, `μg` → `ug`, `μL` → `uL`, `μV` → `uV`, `μA` → `uA`)
- Case variants (`KM` → `km`, `KG` → `kg`, `GHZ` → `GHz`, `Meters` → `m`)
- Full words (`kilometer` → `km`, `poundforce` → `lbf`)
- `°F` → `F`, `°C` → `C`, `°K` → `K`, `°R` → `Ra`
- `degf` → `F`, `degc` → `C`, `degk` → `K`, `degr` → `Ra`
- `in` → `inch` (avoids Python keyword conflict)
- Compound exponent forms (`m**2` → `m2`, `m^2` → `m2`)

Self-mappings (e.g. `"m": "m"`) ensure `normalize_unit()` recognizes canonical forms.

## Compound Unit System

The module supports compound/derived units (area, speed, acceleration) via a signature-based parsing and categorization system.

### _DERIVED_CATEGORIES

Maps canonical unit-string expressions to categories. Covers:

| Category | Example Signatures |
|----------|-------------------|
| area | `m**2`, `ft**2`, `cm**2`, `km**2`, `in**2`, `yd**2`, `mi**2` |
| volume | `m**3`, `ft**3`, `cm**3`, `km**3`, `mm**3`, `mi**3`, `yd**3`, `inch**3` |
| speed | `m/s`, `km/h`, `mi/h`, `ft/s`, `m/min` |
| acceleration | `m/s**2`, `ft/s**2` |
| energy | `J`, `kJ` |
| power | `W`, `kW`, `MW` |
| pressure | `Pa`, `bar`, `psi`, `atm` |
| frequency | `Hz`, `kHz`, `MHz`, `GHz` |
| time | `s`, `min`, `h`, `day`, `week`, `year` |
| mass | `kg`, `g`, `mg`, `lb`, `oz` |
| data | `B`, `KB`, `MB`, `GB`, `TB`, `PB` |
| data_rate | `B/s`, `KB/s`, `MB/s`, `GB/s`, `bit/s` |

### _parse_compound_signature

Parses a compound unit string into `(numerator, denominator)` signatures, where each signature is a tuple of `(base_unit, exponent)` pairs sorted alphabetically.

Recognized forms:
- `"X**N"` → `((X, N),)` numerator
- `"A*B"` → `((A,1),(B,1))` numerator
- `"A/B"` → `((A,1),)` numerator, `((B,1),)` denominator
- `"A//B"`, `"A%B"` → same as `A/B`
- `"1/X"` → reciprocal

Operators are evaluated left-to-right with equal precedence. Repeated bases are cancelled (e.g. `"m/s*s"` → `"m"`).

### _simplify_unit_string

Parses, cancels, and re-renders a compound unit string. Returns `None` if fully dimensionless (e.g. `"m/m"` → `None`).

### _add_compound_conversions

Builds pairwise conversion factors between derived unit expressions registered in `_DERIVED_CATEGORIES`. Only the literal registered unit names are enumerated (not the cartesian product of all variants in `UNIT_BASE`) to keep the table manageable.

### _SHORT_COMPOUND_FORMS

Maps short compound forms (`"m2"`, `"ft3"`, etc.) to equivalent forms (`"m2"`, `"m**2"`, `"m^2"`) so cross-form conversions succeed via `get_conversion_factor`.

## Functions

### `normalize_unit(unit: str) -> str`

Normalizes a unit string to canonical form by trying, in order:
1. Exact match in `UNIT_ALIASES`
2. `.lower()` form
3. `.upper()` form
4. `.title()` form
5. `.capitalize()` form

Returns the input unchanged if no match found.

```python
normalize_unit("meters")     # → "m"
normalize_unit("KILOMETERS") # → "km"
normalize_unit("Meters")     # → "m"
```

### `is_unit(text: str) -> bool`

Checks if a string is a valid unit (case-insensitive, same lookup cascade as `normalize_unit`).

```python
is_unit("m")     # → True
is_unit("kg")    # → True
is_unit("foo")   # → False
```

### `get_conversion_factor(from_unit: str, to_unit: str) -> float`

Returns the multiplicative factor to convert from one unit to another. Tries the original pair first, then falls back to equivalent short-compound forms (e.g. `"m**2"` → `"m2"`) and simplified forms.

```python
get_conversion_factor("km", "m")   # → 1000.0
get_conversion_factor("m", "km")   # → 0.001
```

Raises `ValueError` if units are incompatible or unrecognized.

### `are_units_compatible(unit1: str | None, unit2: str | None) -> bool`

Checks if two units can be converted (same category):

```python
are_units_compatible("m", "ft")     # → True (both length)
are_units_compatible("m", "kg")     # → False (length vs mass)
are_units_compatible(None, None)    # → True (both dimensionless)
are_units_compatible("m", None)     # → False (dimensional vs dimensionless)
```

### `get_unit_category(unit: str) -> str | None`

Returns the category for a unit. Looks up the normalized form in `UNIT_CATEGORIES`, then falls back to `_derived_category` for compound expressions.

```python
get_unit_category("m")     # → "length"
get_unit_category("kg")    # → "mass"
get_unit_category("K")     # → "temperature"
get_unit_category("m/s")   # → "speed"
get_unit_category("m**2")  # → "area"
get_unit_category("foo")   # → None
```

### `convert_temperature(value: float, from_unit: str, to_unit: str) -> float`

Converts temperature values with proper offset handling. Normalizes both unit strings before conversion. Raises `ValueError` for non-finite values or unsupported conversion paths.

```python
convert_temperature(0, "C", "F")      # → 32.0
convert_temperature(100, "C", "F")    # → 212.0
convert_temperature(0, "K", "C")      # → -273.15
```

### `get_all_units() -> list[str]`

Returns a sorted list of all unit strings in `UNIT_ALIASES`.

## Temperature Conversions

Temperature uses offset-based conversion via `TEMPERATURE_CONVERSIONS`, not multiplicative factors.

### TEMPERATURE_CONVERSIONS

```python
TEMPERATURE_CONVERSIONS: dict[tuple[str, str], tuple[float, float]]
```

Maps `(from_unit, to_unit)` → `(multiplier, offset)`. Formula: `result = value * multiplier + offset`.

| From/To | Celsius (C) | Fahrenheit (F) | Kelvin (K) | Rankine (Ra) |
|---------|-------------|----------------|------------|-------------|
| Celsius | — | `× 1.8, + 32` | `× 1.0, + 273.15` | `× 1.8, + 491.67` |
| Fahrenheit | `× 1/1.8, - 32/1.8` | — | `× 1/1.8, + 459.67/1.8` | `× 1.0, + 459.67` |
| Kelvin | `× 1.0, - 273.15` | `× 1.8, - 459.67` | — | `× 1.8, + 0` |
| Rankine | `× 1/1.8, - 273.15` | `× 1.0, - 459.67` | `× 1/1.8, + 0` | — |

**Note:** Converting a temperature unit to a non-temperature unit raises `ValueError` (enforced in `UnitValue.convert_to`).

## Internal Functions

### `_display_value(v: float | int | complex) -> str`

Formats a value for display: whole-number floats shown as integers, finite floats use `:.15g` formatting.

### `_build_unit_conversions() -> dict[tuple[str, str], float]`

Builds the complete `UNIT_CONVERSIONS` lookup table from `UNIT_BASE` and `_DERIVED_CATEGORIES`. Takes a snapshot of `UNIT_BASE` under `_UNITS_LOCK` for thread safety.

### `_add_compound_conversions(conversions, base_snapshot) -> None`

Populates conversion factors for compound unit signatures registered in `_DERIVED_CATEGORIES`. Groups units by category and adds pairwise conversion factors.

### `_parse_compound_atoms(unit: str) -> list[tuple[str, int]] | None`

Parses a unit string into `(literal, signed_exponent)` atoms via `_parse_compound_signature`.

### `_find_last_top_level_op(unit: str) -> tuple[int, str]`

Finds the rightmost top-level operator (`*`, `/`, `//`, `%`) in a unit string, skipping `**` exponentiation.

### `_parse_atom_signature(atom: str) -> tuple[tuple[str, int], ...] | None`

Parses a single unit atom like `"m"`, `"m**2"`, `"m**-1"` into a signature tuple.

### `_merge_signatures(num, den) -> tuple[tuple[str, int], ...]`

Combines numerator and denominator signatures into canonical sorted form with exponents merged.

### `_signature_to_canonical_string(sig) -> str | None`

Renders a `(num, den)` signature back to a canonical string (e.g. `"m**2/s"`).

### `_derived_category(unit: str) -> str | None`

Returns the category for a compound unit expression by parsing its signature and looking it up in `_DERIVED_CATEGORIES`.

### `_floor_divide_quantities(left: UnitValue, right: UnitValue) -> UnitValue`

Floor division of two `UnitValue` operands. Compatible same-unit division returns a dimensionless quotient. Incompatible dimensions raise `ValueError`.

### `_modulo_quantities(left: UnitValue, right: UnitValue) -> UnitValue`

Modulo of two `UnitValue` operands. Same-unit modulo returns a dimensioned remainder in the divisor unit (e.g., `5m % 2m → 1 m`). Incompatible dimensions raise `ValueError`.

### `_align_compatible_units(left, right) -> tuple[UnitValue, UnitValue]`

Converts two `UnitValue` operands to a shared unit when they share a category. Used by `__mul__` and `__truediv__` to auto-align before arithmetic.

### `_pow_unit_string(unit: str, exp: int) -> str | None`

Raises a compound unit string to an integer power via signature manipulation (e.g. `"m/s"` raised to 2 → `"m**2/s**2"`). Returns `None` if result is dimensionless.

### `_expand_short_compound(unit: str) -> str`

Expands `"m2"` → `"m**2"`. Returns input unchanged if no expansion needed.

### `_collapse_short_compound(unit: str) -> str`

Collapses `"m**2"` → `"m2"`. Returns input unchanged if no collapse needed.

### `_short_compound_forms(unit: str) -> list[str]`

Returns all equivalent short-compound forms of a unit (short, `**`, `^` variants).

### `_rebuild_conversions() -> None`

Thread-safe rebuild of `UNIT_CONVERSIONS` after custom units are added. Acquires `_UNITS_LOCK` for the swap.

## Module Dependencies

```
units.py → math, re, threading (standard library only)
units.py has no dependencies on other eggcalc modules.
```

### Thread Safety

`_UNITS_LOCK` (a `threading.RLock`) protects all unit-table mutations. Acquired by `_rebuild_conversions()` and any code that mutates `UNIT_BASE` / `UNIT_ALIASES` / `UNIT_CATEGORIES` (e.g. `load_user_config`). The initial `_rebuild_conversions()` call is deferred to the end of the module after all data structures and helper functions are defined.
