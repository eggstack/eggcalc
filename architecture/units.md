# units.py — Unit Definitions and Conversions

3894 lines. Provides comprehensive unit conversion support for the calculator.

## Table of Contents

- [Overview](#overview)
- [Key Exports](#key-exports)
- [Type Aliases](#type-aliases)
- [Constants](#constants)
- [UnitValue Class](#unitvalue-class)
- [UnitSpec — Declarative Unit Specifications](#unitspec--declarative-unit-specifications)
- [UNIT_DEFINITIONS](#unit_definitions)
- [Unit Categories](#unit-categories)
- [Unit Definition Structure](#unit-definition-structure)
- [Unit Aliases](#unit-aliases)
- [Compound Unit System](#compound-unit-system)
- [UnitExpression — Structural Compound Units](#unitexpression--structural-compound-units)
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
    register_custom_units,  # Register user units (config extension point)
    unregister_custom_units,  # Remove user units
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
uv.convert_to("ft")  # → UnitValue(98.4251968503937, "ft")
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

**Temperature asymmetry (intentional):** adding absolute temperatures from
*different scales* is rejected (`UnitValue(100, "C") + UnitValue(212, "F")` →
`ValueError`) because mixing absolute temperatures across scales is
ill-defined. *Subtraction* remains allowed in that case: it produces a
well-defined interval delta (`UnitValue(100, "C") - UnitValue(212, "F")`).
This `__add__`-rejects / `__sub__`-allows split is a documented design
decision covered by regression tests.

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

## UnitSpec — Declarative Unit Specifications

`UnitSpec` is a frozen dataclass for declarative unit definitions:

```python
@dataclass(frozen=True)
class UnitSpec:
    canonical: str              # Canonical unit name (e.g. "m", "ft")
    aliases: tuple[str, ...]    # All recognized aliases
    dimension: Dimension        # Structural dimension
    scale_to_base: float        # Multiplicative factor to base unit
    offset_to_base: float = 0.0 # Additive offset (for temperature)
    affine: bool = False        # Whether offset conversion is affine
    display: str | None = None  # Display form
    category: str = ""          # Category name
```

Each `UnitSpec` fully describes a unit: its canonical name, all aliases, its structural dimension, and the scale/offset to convert to the base unit of its category. This replaces scattered lookup tables with a single authoritative data source.

## UNIT_DEFINITIONS

```python
UNIT_DEFINITIONS: tuple[UnitSpec, ...] = (...)
```

A tuple of 150+ `UnitSpec` entries covering all built-in units. Validated at module load time for: duplicate canonical names, duplicate aliases across specs, and zero scale values.

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
| Temperature | *(affine)* | `temperature` | K, C, F, Ra (offset-based, not multiplicative factors) |

Long-duration units use the common 365-day year (`yr` = 31,536,000 seconds),
not the astronomical Julian year of 365.25 days. Decades, centuries, and
millennia use that same convention.

**Note:** Temperature conversions use a separate offset-based mechanism via `TEMPERATURE_CONVERSIONS` rather than multiplicative factors. Temperature units (`K`, `C`, `F`, `Ra`) carry affine (`scale_to_base` / `offset_to_base`) definitions in the registry and cannot be converted to non-temperature units.

## Unit Definition Structure

### UNIT_DEFINITIONS (declarative source)

```python
UNIT_DEFINITIONS: tuple[UnitSpec, ...] = (
    UnitSpec(canonical="m", aliases=("m", "meter", "meters", ...), ...),
    ...
)
```

The single declarative source: 150 frozen `UnitSpec` entries (canonical name, aliases, dimension, scale/offset, category). Everything else is generated from it at import by `_install_generated_adapters()`:

- `UNIT_ALIASES: dict[str, str]` — alias → canonical (~508 entries)
- `UNIT_CATEGORIES: dict[str, str]` — alias → category (17 categories)
- `UNIT_BASE` — base-unit factor tables (kept as a generated compatibility adapter)
- `TEMPERATURE_CONVERSIONS` — affine conversion rules (Kelvin is base; Fahrenheit/Rankine use `scale=5/9`)
- `UNIT_CONVERSIONS` — lazy `_LazyUnitConversions` mapping computing pairwise factors on demand

The public adapters (except the lazy conversions) are immutable `MappingProxyType` objects installed once at import and rebound atomically on custom-unit registration — there is no unit-table lock.

```python
# Representative entries (see units.py for the full table):
#   "m": length base — km: 1000.0, cm: 0.01, mm: 0.001, ft: 0.3048, inch: 0.0254, ...
#   "s": time base (seconds)   "B": data storage (binary 1024 prefixes)
#   "bps": data transfer rate (decimal 1000 prefixes)   "kg": mass base
#   "L": volume base (liters)  "Pa"/"J"/"W"/"N"/"V"/"A": pressure/energy/power/force/voltage/current
#   "rad": angle base (radians)   "m/s": speed   "m2": area   "Hz": frequency
```

Conversion between two units in the same category is `factor_from / factor_to` (temperature uses affine math instead).

**Important:** The `"in"` (inches) entry is never used as a `from_unit` in conversion because it conflicts with Python's `in` keyword in AST parsing. Callers normalize `"in"` to `"inch"` via `UNIT_ALIASES` before consulting the conversion table.

### UNIT_CATEGORIES

```python
UNIT_CATEGORIES: dict[str, str]  # generated alias → category map, e.g. {"m": "length", "K": "temperature"}
```

Built from the registry at import (temperature included — it is a first-class category with affine definitions, not a manual extra).

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

The module supports compound/derived units (area, speed, acceleration) via `UnitExpression` structural parsing and categorization (see [UnitExpression — Structural Compound Units](#unitexpression--structural-compound-units) below). Categories covered include:

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

Retired in the registry refactor (historical names, no longer in source): `_DERIVED_CATEGORIES`, `_parse_compound_signature`, `_SHORT_COMPOUND_FORMS`. Compound parsing now goes through `parse_unit_expression()`; short-compound handling (`"m2"` ↔ `"m**2"`) lives in that path.

### `_simplify_unit_string(unit: str | None) -> str | None`

Parses, cancels, and re-renders a compound unit string (private compatibility helper; public parsing and arithmetic use the bounded grammar/structural operations). Returns `None` for `None` input or fully-dimensionless results (e.g. `"m/m"` → `None`).

## UnitExpression — Structural Compound Units

`UnitExpression` is a frozen dataclass for structural compound unit representation:

```python
@dataclass(frozen=True)
class UnitExpression:
    factors: tuple[tuple[str, int], ...]  # sorted (canonical_unit, exponent) pairs
    dimension: Dimension
    scale_to_base: float
```

### `parse_unit_expression(unit_str: str) -> UnitExpression`

Parses a compound unit string into a frozen `UnitExpression`. Handles forms like `"m/s"`, `"kg*m/s**2"`, `"m**2"`. Rejects `"//"` and `"%"` as separators. Enforces resource bounds: `MAX_UNIT_STRING_LENGTH` (256), `MAX_COMPOUND_ATOMS` (32), `MAX_COMPOUND_DEPTH` (16, maximum structural depth of the compound unit grammar), `MAX_ABS_UNIT_EXPONENT` (16, enforced post-merge on duplicate factors). Fully consumes input — raises `ValueError` on leftover characters.

```python
expr = parse_unit_expression("m/s")
# UnitExpression(factors=(('m', 1), ('s', -1)), dimension=Dimension(length=1, time=-1), ...)
```

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

**Note:** `are_units_compatible()` compares units by their `Dimension` objects directly. It no longer falls back to category-string matching, which was imprecise for compound and structural dimensions like angle.

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

### `register_custom_units(custom_units: Mapping[str, Mapping[str, object]], custom_aliases: Mapping[str, str] | None = None) -> None`

Registers user-defined units at runtime (used by `load_user_config()` for `CUSTOM_UNITS` / `CUSTOM_ALIASES`). Atomically rebinds the immutable `MappingProxyType` adapters (`UNIT_ALIASES`, `UNIT_BASE`, `UNIT_CATEGORIES`, `TEMPERATURE_CONVERSIONS`) and refreshes the lazy `UNIT_CONVERSIONS` mapping.

### `unregister_custom_units(names: Mapping[str, object] | set[str] | tuple[str, ...]) -> None`

Removes previously registered custom units and rebinds the adapters. Accepts a mapping, set, or tuple of names.

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

### `_build_unit_conversions()`

Retired in the registry refactor: pairwise factors are no longer precomputed into a lookup table. `UNIT_CONVERSIONS` is a lazy `_LazyUnitConversions` mapping computed on demand from the canonical `UnitRegistry`; `_rebuild_conversions()` (below) is the remaining compatibility hook.

### `_floor_divide_quantities(left: UnitValue, right: UnitValue) -> UnitValue`

Floor division of two `UnitValue` operands. Compatible same-unit division returns a dimensionless quotient. Incompatible dimensions raise `ValueError`.

### `_modulo_quantities(left: UnitValue, right: UnitValue) -> UnitValue`

Modulo of two `UnitValue` operands. Same-unit modulo returns a dimensioned remainder in the divisor unit (e.g., `5m % 2m → 1 m`). Incompatible dimensions raise `ValueError`.

### `_align_compatible_units(left, right) -> tuple[UnitValue, UnitValue]`

Converts two `UnitValue` operands to a shared unit when they share a category. Used by `__mul__` and `__truediv__` to auto-align before arithmetic.

### `_pow_unit_string(unit: str, exp: int) -> str | None`

Raises a compound unit string to an integer power via signature manipulation (e.g. `"m/s"` raised to 2 → `"m**2/s**2"`). Returns `None` if result is dimensionless.

### `_expand_short_compound` / `_collapse_short_compound` / `_short_compound_forms`

Retired in the registry refactor: short-compound handling (`"m2"` ↔ `"m**2"`) now lives in the `UnitExpression` parsing path (`parse_unit_expression`), not in standalone helpers.

### `_rebuild_conversions() -> None`

Compatibility hook; conversion behavior is registry-owned. Replaces `UNIT_CONVERSIONS` with a fresh `_LazyUnitConversions` over the current registry (used after custom units are added).

## Dimension Semantics

### Dimension Equality and Hashing

`Dimension` equality and hashing now include the `angle` field. Two `Dimension` instances are equal only if all their fields (including `angle`) match. This ensures that angle dimensions are treated as a distinct structural axis, not conflated with dimensionless or other categories.

```python
Dimension() == Dimension(angle=True)  # → False
hash(Dimension()) != hash(Dimension(angle=True))
```

### Angle Propagation

Angle propagates via XOR in multiplication and division. When multiplying or dividing two units, the `angle` flag of the result is the XOR of the operands' `angle` flags:

- `rad * rad` → angle XOR angle = not angle (dimensionless-like)
- `rad * m` → angle XOR not angle = angle
- `m * m` → not angle XOR not angle = not angle

This models the physical intuition that angle is a ratio (length/length) and cancels when like dimensions multiply.

### Angle Algebra Bounds

The `Dimension.angle` boolean flag can only represent angle exponents of 0 or 1. Bounded guards in `__mul__`, `__truediv__`, and `__pow__` reject operations that would require richer representations:

| Operation | Result | Reason |
|-----------|--------|--------|
| `deg**0` | dimensionless | Any dimension to the 0th power is dimensionless |
| `deg**1` | angle | Identity exponent, preserved |
| `deg**2` | `ValueError` | Angle exponent 2 not representable |
| `deg**-1` | `ValueError` | Inverse angle not representable |
| `deg*rad` | `ValueError` | Multiplying two angle-bearing dimensions |
| `1/deg` | `ValueError` | Dividing non-angle by angle-bearing |
| `deg/rad` | dimensionless | Angle XOR angle = not angle (cancels) |
| `(deg/s)*s` | angle | Angle XOR not angle = angle |
| `(deg/s)*(rad/s)` | `ValueError` | Both angle-bearing |

Supported compound expressions like `30*deg/s` and `(30*deg/s) * (2*s)` continue to work. Trig functions accept direct angles (`90*deg`) but reject angular velocity (`deg/s`).

## Module Dependencies

```
units.py → math, re, collections.abc, dataclasses, functools, types (standard library only)
units.py has no dependencies on other eggcalc modules.
```

### Thread Safety

There is no unit-table lock: the public adapters (`UNIT_ALIASES`, `UNIT_BASE`, `UNIT_CATEGORIES`, `TEMPERATURE_CONVERSIONS`) are immutable `MappingProxyType` objects installed once at import by `_install_generated_adapters()` and atomically rebound on custom-unit registration; pairwise factors compute statelessly via the lazy `_LazyUnitConversions` mapping. The lazy module registry (`_unit_registry`) builds once on first access via `_get_unit_registry()`.
