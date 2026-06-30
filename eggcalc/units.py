"""
Unit definitions and conversions for eggcalc.

Provides comprehensive unit conversion support including:
- Length (meters, feet, inches, miles, lightyears, etc.)
- Time (seconds, hours, days, weeks, years, etc.)
- Data storage (bytes, KB, MB, GB, TB, etc.)
- Data transfer rate (bps, Kbps, Mbps, Gbps)
- Mass (kg, grams, pounds, ounces, etc.)
- Volume (liters, gallons, cups, etc.)
- Pressure (Pa, bar, psi, atm, etc.)
- Energy (J, kJ, cal, kWh, BTU, eV, etc.)
- Power (W, kW, MW, hp, etc.)
"""

from __future__ import annotations

import math
import re
import threading

Numeric = float | int | complex

FLOAT_EPSILON = 1e-10
MAX_RESULT_VALUE = 1e308


def _display_value(v: float | int | complex) -> str:
    """Format a value for display, showing whole-number floats as integers."""
    if isinstance(v, float):
        if v.is_integer():
            return str(int(v))
        if math.isfinite(v):
            return f"{v:.15g}"
    return str(v)


class UnitValue:
    """Represents a numeric value with optional units.

    Supports arithmetic operations with automatic unit conversion
    when adding or subtracting values with compatible units.
    """

    @staticmethod
    def _check_overflow(result: Numeric) -> None:
        """Raise OverflowError if result is not finite or exceeds limits."""
        if isinstance(result, complex):
            if not math.isfinite(result.real) or not math.isfinite(result.imag):
                raise OverflowError("Result too large")
        elif isinstance(result, float) and not math.isfinite(result):
            raise OverflowError("Result too large")
        # For int results, skip magnitude check — digit count is the correct
        # limit for arbitrary-precision ints (enforced by _check_result_size).

    def __init__(self, value: float | complex, unit: str | None = None) -> None:
        # Normalize complex values with zero imaginary part to float
        # to maintain hash contract (complex(5,0) == 5.0 but different hashes)
        if isinstance(value, complex) and value.imag == 0:
            value = value.real
        self.value = value
        self.unit = unit
        if isinstance(value, complex):
            if not math.isfinite(value.real) or not math.isfinite(value.imag):
                raise ValueError(f"UnitValue does not support non-finite values: {value}")
        elif isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f"UnitValue does not support non-finite values: {value}")

    def __repr__(self) -> str:
        if self.unit:
            return f"{_display_value(self.value)} {self.unit}"
        return _display_value(self.value)

    def __str__(self) -> str:
        return self.__repr__()

    def __format__(self, format_spec: str) -> str:
        if self.unit:
            return f"{self.value:{format_spec}} {self.unit}"
        return f"{self.value:{format_spec}}"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, UnitValue):
            return NotImplemented
        if self.unit != other.unit:
            return False
        return self.value == other.value

    def __hash__(self) -> int:
        """Hash consistent with __eq__: real/imag components and unit are compared."""
        if isinstance(self.value, complex):
            return hash((self.value.real, self.value.imag, self.unit))
        return hash((self.value, self.unit))

    def __add__(self, other: Numeric) -> UnitValue:
        if isinstance(other, UnitValue):
            if not are_units_compatible(self.unit, other.unit):
                raise ValueError(f"Cannot add incompatible units: {self.unit} + {other.unit}")
            if self.unit == other.unit:
                result = self.value + other.value
                out_unit = self.unit
            elif other.unit is None:
                result = self.value + other.value
                out_unit = self.unit
            elif self.unit is None:
                result = self.value + other.value
                out_unit = other.unit
            else:
                converted = other.convert_to(self.unit)
                result = self.value + converted.value
                out_unit = self.unit
        else:
            if self.unit is None:
                result = self.value + other
                out_unit = None
            else:
                raise ValueError(
                    f"Cannot add a dimensionless value to {self.unit}; use matching units or convert first"
                )
        UnitValue._check_overflow(result)
        return UnitValue(result, out_unit)

    def __radd__(self, other: Numeric) -> UnitValue:
        return self.__add__(other)

    def __sub__(self, other: Numeric) -> UnitValue:
        if isinstance(other, UnitValue):
            if not are_units_compatible(self.unit, other.unit):
                raise ValueError(f"Cannot subtract incompatible units: {self.unit} - {other.unit}")
            if self.unit == other.unit:
                result = self.value - other.value
                out_unit = self.unit
            elif other.unit is None:
                result = self.value - other.value
                out_unit = self.unit
            elif self.unit is None:
                result = self.value - other.value
                out_unit = other.unit
            else:
                converted = other.convert_to(self.unit)
                result = self.value - converted.value
                out_unit = self.unit
        else:
            if self.unit is None:
                result = self.value - other
                out_unit = None
            else:
                raise ValueError(
                    f"Cannot subtract a dimensionless value from {self.unit}; use matching units or convert first"
                )
        UnitValue._check_overflow(result)
        return UnitValue(result, out_unit)

    def __rsub__(self, other: Numeric) -> UnitValue:
        if isinstance(other, UnitValue):
            return other.__sub__(self)
        if self.unit is None:
            return UnitValue(other - self.value, None)
        raise ValueError("Cannot subtract a unit value from a dimensionless number")

    def __mul__(self, other: Numeric) -> UnitValue:
        if isinstance(other, UnitValue):
            if self.unit and other.unit:
                result = self.value * other.value
                unit = _simplify_unit_string(f"{self.unit}*{other.unit}")
            else:
                result = self.value * other.value
                unit = self.unit or other.unit
        else:
            result = self.value * other
            unit = self.unit
        UnitValue._check_overflow(result)
        return UnitValue(result, unit)

    def __rmul__(self, other: Numeric) -> UnitValue:
        return self.__mul__(other)

    def __truediv__(self, other: Numeric) -> UnitValue:
        if isinstance(other, UnitValue):
            if other.value == 0:
                raise ZeroDivisionError("Cannot divide UnitValue by zero")
            if self.unit and other.unit:
                if self.unit == other.unit:
                    result = self.value / other.value
                    unit = None
                else:
                    result = self.value / other.value
                    unit = _simplify_unit_string(f"{self.unit}/{other.unit}")
            elif other.unit:
                # self is dimensionless, other has a unit -> reciprocal unit
                result = self.value / other.value
                unit = _simplify_unit_string(f"1/{other.unit}")
            else:
                # other is dimensionless; self.unit may be None or a unit
                result = self.value / other.value
                unit = self.unit
        else:
            if other == 0:
                raise ZeroDivisionError("Cannot divide UnitValue by zero")
            result = self.value / other
            unit = self.unit
        UnitValue._check_overflow(result)
        return UnitValue(result, unit)

    def __floordiv__(self, other: Numeric) -> UnitValue:
        if isinstance(other, UnitValue):
            if other.value == 0:
                raise ZeroDivisionError("Cannot divide UnitValue by zero")
            if self.unit and other.unit:
                if self.unit == other.unit:
                    result = self.value // other.value
                    unit = None
                else:
                    result = self.value // other.value
                    unit = _simplify_unit_string(f"{self.unit}//{other.unit}")
            elif other.unit:
                result = self.value // other.value
                unit = _simplify_unit_string(f"1//{other.unit}")
            else:
                result = self.value // other.value
                unit = self.unit
        else:
            if other == 0:
                raise ZeroDivisionError("Cannot divide UnitValue by zero")
            result = self.value // other  # type: ignore[operator]
            unit = self.unit
        UnitValue._check_overflow(result)
        return UnitValue(result, unit)

    def __rfloordiv__(self, other: Numeric) -> UnitValue:
        if self.unit:
            if self.value == 0:
                raise ZeroDivisionError("Cannot divide by zero UnitValue")
            raise ValueError(f"Cannot floor-divide a number by a unit value ('{self.unit}')")
        if self.value == 0:
            raise ZeroDivisionError("Cannot divide by zero UnitValue")
        return UnitValue(other // self.value, None)  # type: ignore[operator]

    def __mod__(self, other: Numeric) -> UnitValue:
        if isinstance(other, UnitValue):
            if other.value == 0:
                raise ZeroDivisionError("Cannot mod UnitValue by zero")
            if self.unit and other.unit:
                if self.unit == other.unit:
                    result = self.value % other.value
                    unit = None
                else:
                    result = self.value % other.value
                    unit = _simplify_unit_string(f"{self.unit}%{other.unit}")
            elif other.unit:
                result = self.value % other.value
                unit = _simplify_unit_string(f"1%{other.unit}")
            else:
                result = self.value % other.value
                unit = self.unit
        else:
            if other == 0:
                raise ZeroDivisionError("Cannot mod UnitValue by zero")
            result = self.value % other  # type: ignore[operator]
            unit = self.unit
        UnitValue._check_overflow(result)
        return UnitValue(result, unit)

    def __rmod__(self, other: Numeric) -> UnitValue:
        if self.unit:
            if self.value == 0:
                raise ZeroDivisionError("Cannot mod by zero UnitValue")
            raise ValueError(f"Cannot take modulo by a unit value ('{self.unit}')")
        if self.value == 0:
            raise ZeroDivisionError("Cannot mod by zero UnitValue")
        return UnitValue(other % self.value, None)  # type: ignore[operator]

    def __rtruediv__(self, other: Numeric) -> UnitValue:
        if self.unit:
            if self.value == 0:
                raise ZeroDivisionError("Cannot divide by zero UnitValue")
            simplified = _simplify_unit_string(f"1/{self.unit}") or f"1/{self.unit}"
            return UnitValue(other / self.value, simplified)
        if self.value == 0:
            raise ZeroDivisionError("Cannot divide by zero UnitValue")
        return UnitValue(other / self.value, None)

    def __pow__(self, other: Numeric) -> UnitValue:
        if isinstance(other, bool):
            other = int(other)
        if self.unit:
            if isinstance(other, int):
                result = self.value**other
                # Anything to the 0th power is dimensionless.
                if other == 0:
                    return UnitValue(result, None)
                unit = _simplify_unit_string(f"{self.unit}**{other}") or f"{self.unit}**{other}"
            elif isinstance(other, float) and other.is_integer():
                int_exp = int(other)
                result = self.value**other
                if int_exp == 0:
                    return UnitValue(result, None)
                unit = _simplify_unit_string(f"{self.unit}**{int_exp}") or f"{self.unit}**{int_exp}"
            else:
                raise ValueError(f"Cannot raise unit '{self.unit}' to non-integer power")
        else:
            result = self.value**other
            unit = self.unit  # type: ignore[assignment]
        UnitValue._check_overflow(result)
        return UnitValue(result, unit)

    def __neg__(self) -> UnitValue:
        return UnitValue(-self.value, self.unit)

    def __pos__(self) -> UnitValue:
        return UnitValue(self.value, self.unit)

    def __abs__(self) -> UnitValue:
        return UnitValue(abs(self.value), self.unit)

    def __round__(self, ndigits: int = 0) -> UnitValue:
        return UnitValue(round(self.value, ndigits), self.unit)  # type: ignore[arg-type]

    def __complex__(self) -> complex:
        return complex(self.value)

    def __int__(self) -> int:
        return int(self.value)  # type: ignore[arg-type]

    def __float__(self) -> float:
        return float(self.value)  # type: ignore[arg-type]

    def convert_to(self, target_unit: str) -> UnitValue:
        """Convert to a different unit of the same type."""

        if self.unit == target_unit:
            return UnitValue(self.value, target_unit)

        if target_unit is None:
            raise ValueError("Target unit cannot be None")

        if self.unit is None:
            raise ValueError("Cannot convert dimensionless value")

        cat = get_unit_category(self.unit)
        target_cat = get_unit_category(target_unit)
        if cat == "temperature" and target_cat == "temperature":
            converted = convert_temperature(self.value, self.unit, target_unit)  # type: ignore[arg-type]
            return UnitValue(converted, target_unit)
        if cat == "temperature" and target_cat != "temperature":
            raise ValueError(
                f"Cannot convert temperature unit '{self.unit}' to non-temperature unit '{target_unit}'. "
                f"Temperature units (K, C, F, R) can only be converted to other temperature units."
            )
        factor = get_conversion_factor(self.unit, target_unit)
        return UnitValue(self.value * factor, target_unit)


# Unit definitions: base unit -> {unit: factor to base}
UNIT_BASE: dict[str, dict[str, float]] = {
    # Length (base: meters)
    "m": {
        "m": 1.0,
        "meter": 1.0,
        "meters": 1.0,
        "km": 1000.0,
        "kilometer": 1000.0,
        "kilometers": 1000.0,
        "cm": 0.01,
        "centimeter": 0.01,
        "centimeters": 0.01,
        "mm": 0.001,
        "millimeter": 0.001,
        "millimeters": 0.001,
        "um": 1e-6,
        "μm": 1e-6,
        "micrometer": 1e-6,
        "micrometers": 1e-6,
        "nm": 1e-9,
        "nanometer": 1e-9,
        "nanometers": 1e-9,
        "pm": 1e-12,
        "picometer": 1e-12,
        "picometers": 1e-12,
        "in": 0.0254,
        "inch": 0.0254,
        "inches": 0.0254,
        "ft": 0.3048,
        "foot": 0.3048,
        "feet": 0.3048,
        "yd": 0.9144,
        "yard": 0.9144,
        "yards": 0.9144,
        "mi": 1609.344,
        "mile": 1609.344,
        "miles": 1609.344,
        "ly": 9.4607304725808e15,
        "lightyear": 9.4607304725808e15,
        "lightyears": 9.4607304725808e15,
        "au": 1.49597870700e11,
        "astronomicalunit": 1.49597870700e11,
        "astronomicalunits": 1.49597870700e11,
        "pc": 3.0856775814913673e16,
        "parsec": 3.0856775814913673e16,
        "parsecs": 3.0856775814913673e16,
        "angstrom": 1e-10,
        "angstroms": 1e-10,
        "fermi": 1e-15,
        "nmi": 1852.0,
        "nauticalmile": 1852.0,
        "nauticalmiles": 1852.0,
        "furlong": 201.168,
        "furlongs": 201.168,
        "chain": 20.1168,
        "chains": 20.1168,
        "rd": 5.0292,
        "rod": 5.0292,
        "rods": 5.0292,
        "fathom": 1.8288,
        "fathoms": 1.8288,
        "smoot": 1.7018,
        "smoots": 1.7018,
    },
    # Time (base: seconds)
    "s": {
        "s": 1.0,
        "second": 1.0,
        "seconds": 1.0,
        "ms": 0.001,
        "millisecond": 0.001,
        "milliseconds": 0.001,
        "us": 1e-6,
        "μs": 1e-6,
        "microsecond": 1e-6,
        "microseconds": 1e-6,
        "ns": 1e-9,
        "nanosecond": 1e-9,
        "nanoseconds": 1e-9,
        "ps": 1e-12,
        "picosecond": 1e-12,
        "picoseconds": 1e-12,
        "min": 60.0,
        "minute": 60.0,
        "minutes": 60.0,
        "h": 3600.0,
        "hr": 3600.0,
        "hour": 3600.0,
        "hours": 3600.0,
        "d": 86400.0,
        "day": 86400.0,
        "days": 86400.0,
        "wk": 604800.0,
        "week": 604800.0,
        "weeks": 604800.0,
        "fortnight": 1209600.0,
        "fortnights": 1209600.0,
        "yr": 31536000.0,
        "year": 31536000.0,
        "years": 31536000.0,
        "decade": 315360000.0,
        "decades": 315360000.0,
        "century": 3153600000.0,
        "centuries": 3153600000.0,
        "millennium": 31536000000.0,
        "millennia": 31536000000.0,
    },
    # Note: Year is defined as 365 days (31536000 seconds), ignoring leap years.
    # Data storage (base: bytes) - uses binary (1024) prefixes per IEEE/ASTM standard
    "B": {
        "B": 1.0,
        "byte": 1.0,
        "bytes": 1.0,
        "bit": 0.125,
        "bits": 0.125,
        "KB": 1024.0,
        "kilobyte": 1024.0,
        "kilobytes": 1024.0,
        "MB": 1048576.0,
        "megabyte": 1048576.0,
        "megabytes": 1048576.0,
        "GB": 1073741824.0,
        "gigabyte": 1073741824.0,
        "gigabytes": 1073741824.0,
        "TB": 1099511627776.0,
        "terabyte": 1099511627776.0,
        "terabytes": 1099511627776.0,
        "PB": 1125899906842624.0,
        "petabyte": 1125899906842624.0,
        "petabytes": 1125899906842624.0,
        "EB": 1152921504606846976.0,
        "exabyte": 1152921504606846976.0,
        "exabytes": 1152921504606846976.0,
        "ZB": 1.1805916207174113e21,
        "zettabyte": 1.1805916207174113e21,
        "zettabytes": 1.1805916207174113e21,
        "YB": 1.2089258196146292e24,
        "yottabyte": 1.2089258196146292e24,
        "yottabytes": 1.2089258196146292e24,
    },
    # Data transfer rate (base: bits per second) - uses decimal (1000) prefixes per SI standard
    "bps": {
        "bps": 1.0,
        "bit/s": 1.0,
        "bits/s": 1.0,
        "Kbps": 1000.0,
        "kilobps": 1000.0,
        "kilobit/s": 1000.0,
        "kilobits/s": 1000.0,
        "Mbps": 1000000.0,
        "megabps": 1000000.0,
        "megabit/s": 1000000.0,
        "megabits/s": 1000000.0,
        "Gbps": 1000000000.0,
        "gigabps": 1000000000.0,
        "gigabit/s": 1000000000.0,
        "gigabits/s": 1000000000.0,
    },
    # Mass (base: kilograms)
    "kg": {
        "kg": 1.0,
        "kilogram": 1.0,
        "kilograms": 1.0,
        "g": 0.001,
        "gram": 0.001,
        "grams": 0.001,
        "mg": 1e-6,
        "milligram": 1e-6,
        "milligrams": 1e-6,
        "ug": 1e-9,
        "μg": 1e-9,
        "microgram": 1e-9,
        "micrograms": 1e-9,
        "ng": 1e-12,
        "nanogram": 1e-12,
        "nanograms": 1e-12,
        "lb": 0.45359237,
        "lbs": 0.45359237,
        "pound": 0.45359237,
        "pounds": 0.45359237,
        "oz": 0.028349523125,
        "ounce": 0.028349523125,
        "ounces": 0.028349523125,
        "ton": 907.18474,
        "tons": 907.18474,
        "tonne": 1000.0,
        "tonnes": 1000.0,
        "long_ton": 1016.0469,
        "imperial_ton": 1016.0469,
        "stone": 6.35029318,
        "stones": 6.35029318,
        "slug": 14.593903,
        "slugs": 14.593903,
        "ct": 0.0002,
        "carat": 0.0002,
        "carats": 0.0002,
        "gr": 6.479891e-5,
        "grain": 6.479891e-5,
        "grains": 6.479891e-5,
        "dr": 0.0017718452,
        "dram": 0.0017718452,
        "drams": 0.0017718452,
    },
    # Volume (base: liters)
    "L": {
        "L": 1.0,
        "liter": 1.0,
        "liters": 1.0,
        "l": 1.0,
        "mL": 0.001,
        "milliliter": 0.001,
        "milliliters": 0.001,
        "uL": 1e-6,
        "μL": 1e-6,
        "microliter": 1e-6,
        "microliters": 1e-6,
        "gal": 3.785411784,
        "gallon": 3.785411784,
        "gallons": 3.785411784,
        "qt": 0.946352946,
        "quart": 0.946352946,
        "quarts": 0.946352946,
        "pt": 0.473176473,
        "pint": 0.473176473,
        "pints": 0.473176473,
        "cup": 0.2365882365,
        "cups": 0.2365882365,
        "floz": 0.02957352954,
        "fl oz": 0.02957352954,
        "fluidounce": 0.02957352954,
        "fluidounces": 0.02957352954,
        "tbsp": 0.01478676477,
        "tablespoon": 0.01478676477,
        "tablespoons": 0.01478676477,
        "tsp": 0.00492892159,
        "teaspoon": 0.00492892159,
        "teaspoons": 0.00492892159,
        "m3": 1000.0,
        "m^3": 1000.0,
        "cubicmeter": 1000.0,
        "cubicmeters": 1000.0,
        "cm3": 0.001,
        "cm^3": 0.001,
        "cc": 0.001,
        "cubiccentimeter": 0.001,
        "cubiccentimeters": 0.001,
        "ft3": 28.316846592,
        "ft^3": 28.316846592,
        "cubicfoot": 28.316846592,
        "cubicfeet": 28.316846592,
        "in3": 0.016387064,
        "in^3": 0.016387064,
        "cubicinch": 0.016387064,
        "cubicinches": 0.016387064,
        "yd3": 764.554857984,
        "yd^3": 764.554857984,
        "cubicyard": 764.554857984,
        "cubicyards": 764.554857984,
        "mm3": 1e-6,
        "mm^3": 1e-6,
        "cubicmillimeter": 1e-6,
        "cubicmillimeters": 1e-6,
        "km3": 1e12,
        "km^3": 1e12,
        "cubickilometer": 1e12,
        "cubickilometers": 1e12,
        "mi3": 4.168181825e12,
        "mi^3": 4.168181825e12,
        "cubicmile": 4.168181825e12,
        "cubicmiles": 4.168181825e12,
    },
    # Pressure (base: Pascal)
    "Pa": {
        "Pa": 1.0,
        "pascal": 1.0,
        "pascals": 1.0,
        "kPa": 1000.0,
        "kilopascal": 1000.0,
        "kilopascals": 1000.0,
        "MPa": 1000000.0,
        "megapascal": 1000000.0,
        "megapascals": 1000000.0,
        "GPa": 1e9,
        "gigapascal": 1e9,
        "gigapascals": 1e9,
        "bar": 100000.0,
        "bars": 100000.0,
        "mbar": 100.0,
        "millibar": 100.0,
        "atm": 101325.0,
        "atmosphere": 101325.0,
        "atmospheres": 101325.0,
        "psi": 6894.757293168,
        "mmHg": 133.32236842105,
        "torr": 133.32236842105,
        "inHg": 3386.389,
        "mmH2O": 9.80665,
        "inH2O": 249.08891,
    },
    # Energy (base: Joules)
    "J": {
        "J": 1.0,
        "joule": 1.0,
        "joules": 1.0,
        "kJ": 1000.0,
        "kilojoule": 1000.0,
        "kilojoules": 1000.0,
        "MJ": 1e6,
        "megajoule": 1e6,
        "megajoules": 1e6,
        "GJ": 1e9,
        "gigajoule": 1e9,
        "gigajoules": 1e9,
        "cal": 4.184,
        "calorie": 4.184,
        "calories": 4.184,
        "kcal": 4184.0,
        "kilocalorie": 4184.0,
        "kilocalories": 4184.0,
        "Wh": 3600.0,
        "watt-hour": 3600.0,
        "watt-hours": 3600.0,
        "kWh": 3600000.0,
        "kilowatt-hour": 3600000.0,
        "kilowatt-hours": 3600000.0,
        "BTU": 1055.05585262,
        "btu": 1055.05585262,
        "eV": 1.602176634e-19,
    },
    # Power (base: Watts)
    "W": {
        "W": 1.0,
        "watt": 1.0,
        "watts": 1.0,
        "kW": 1000.0,
        "kilowatt": 1000.0,
        "kilowatts": 1000.0,
        "MW": 1e6,
        "megawatt": 1e6,
        "megawatts": 1e6,
        "GW": 1e9,
        "gigawatt": 1e9,
        "gigawatts": 1e9,
        "mW": 0.001,
        "milliwatt": 0.001,
        "milliwatts": 0.001,
        "hp": 745.69987158227022,
        "horsepower": 745.69987158227022,
    },
    "N": {
        "N": 1.0,
        "newton": 1.0,
        "newtons": 1.0,
        "kN": 1000.0,
        "kilonewton": 1000.0,
        "mN": 0.001,
        "millinewton": 0.001,
        "dyne": 1e-5,
        "dynes": 1e-5,
        "lbf": 4.4482216152605,
        "poundforce": 4.4482216152605,
    },
    "V": {
        "V": 1.0,
        "volt": 1.0,
        "volts": 1.0,
        "kV": 1000.0,
        "kilovolt": 1000.0,
        "mV": 0.001,
        "millivolt": 0.001,
        "uV": 1e-6,
        "μV": 1e-6,
        "microvolt": 1e-6,
    },
    "A": {
        "A": 1.0,
        "amp": 1.0,
        "ampere": 1.0,
        "amperes": 1.0,
        "mA": 0.001,
        "milliamp": 0.001,
        "milliampere": 0.001,
        "uA": 1e-6,
        "μA": 1e-6,
        "microamp": 1e-6,
        "microampere": 1e-6,
    },
    "rad": {
        "rad": 1.0,
        "radian": 1.0,
        "radians": 1.0,
        "deg": 0.017453292519943295,
        "degree": 0.017453292519943295,
        "degrees": 0.017453292519943295,
    },
    # Speed (base: meters per second)
    "m/s": {
        "m/s": 1.0,
        "mps": 1.0,
        "meterpersecond": 1.0,
        "meterspersecond": 1.0,
        "km/h": 1000 / 3600,
        "kph": 1000 / 3600,
        "kilometerperhour": 1000 / 3600,
        "kilometersperhour": 1000 / 3600,
        "mph": 0.44704,
        "mileperhour": 0.44704,
        "milesperhour": 0.44704,
        "mi/h": 0.44704,
        "kn": 1852 / 3600,
        "knot": 1852 / 3600,
        "knots": 1852 / 3600,
        "kt": 1852 / 3600,
        "mach": 340.29,
    },
    # Area (base: square meters)
    "m2": {
        "m2": 1.0,
        "m^2": 1.0,
        "sqm": 1.0,
        "squaremeter": 1.0,
        "squaremeters": 1.0,
        "km2": 1000000.0,
        "km^2": 1000000.0,
        "squarekilometer": 1000000.0,
        "squarekilometers": 1000000.0,
        "cm2": 0.0001,
        "cm^2": 0.0001,
        "squarecentimeter": 0.0001,
        "squarecentimeters": 0.0001,
        "mm2": 1e-6,
        "mm^2": 1e-6,
        "squaremillimeter": 1e-6,
        "squaremillimeters": 1e-6,
        "ha": 10000.0,
        "hectare": 10000.0,
        "hectares": 10000.0,
        "acre": 4046.8564224,
        "acres": 4046.8564224,
        "ft2": 0.09290304,
        "ft^2": 0.09290304,
        "sqft": 0.09290304,
        "squarefoot": 0.09290304,
        "squarefeet": 0.09290304,
        "in2": 0.00064516,
        "in^2": 0.00064516,
        "sqin": 0.00064516,
        "squareinch": 0.00064516,
        "squareinches": 0.00064516,
        "mi2": 2589988.110336,
        "mi^2": 2589988.110336,
        "sqmi": 2589988.110336,
        "squaremile": 2589988.110336,
        "squaremiles": 2589988.110336,
        "yd2": 0.83612736,
        "yd^2": 0.83612736,
        "sqyd": 0.83612736,
        "squareyard": 0.83612736,
        "squareyards": 0.83612736,
    },
    # Frequency (base: Hertz)
    "Hz": {
        "Hz": 1.0,
        "hertz": 1.0,
        "kHz": 1000.0,
        "kilohertz": 1000.0,
        "MHz": 1000000.0,
        "megahertz": 1000000.0,
        "GHz": 1000000000.0,
        "gigahertz": 1000000000.0,
        "THz": 1000000000000.0,
        "terahertz": 1000000000000.0,
    },
}


# Module-level lock protecting all unit-table mutations.
# Acquired by both _rebuild_conversions() and any code that mutates
# UNIT_BASE / UNIT_ALIASES / UNIT_CATEGORIES (e.g. load_user_config).
_UNITS_LOCK: threading.RLock = threading.RLock()


def _build_unit_conversions() -> dict[tuple[str, str], float]:
    """Build a complete unit conversion lookup table."""
    conversions: dict[tuple[str, str], float] = {}

    # Snapshot UNIT_BASE so concurrent mutations don't cause rehashing
    # mid-iteration. The snapshot is a shallow copy of the outer dict
    # pointing to the same inner dicts; reading dict items is safe.
    with _UNITS_LOCK:
        base_snapshot = {base: dict(units) for base, units in UNIT_BASE.items()}

    for _base_unit, units in base_snapshot.items():
        unit_factors = {unit: factor for unit, factor in units.items()}

        for from_unit, from_factor in unit_factors.items():
            # Skip "in" (inches) as a from_unit because it conflicts with
            # Python's `in` keyword in AST parsing. All callers normalize
            # "in" to "inch" via UNIT_ALIASES before consulting this table,
            # so "in" is never looked up as a from_unit in practice.
            if from_unit == "in":
                continue
            for to_unit, to_factor in unit_factors.items():
                if from_unit != to_unit:
                    key = (from_unit, to_unit)
                    conversions[key] = from_factor / to_factor

    # Compound unit conversions: build factors for derived units (e.g.
    # m**2 <-> cm**2) by composing base unit factors. We do this only
    # for unit signatures we have a category for, which keeps the
    # table focused on well-defined categories. See
    # plans/production_review_2026_07_b.md (B6).
    _add_compound_conversions(conversions, base_snapshot)

    return conversions


def _add_compound_conversions(
    conversions: dict[tuple[str, str], float],
    base_snapshot: dict[str, dict[str, float]],
) -> None:
    """Populate conversions for compound unit signatures.

    For each known derived category, build the conversion factor between
    any two unit expressions that share the same signature. We only
    enumerate the literal units registered in ``_DERIVED_CATEGORIES`` —
    expanding the cartesian product over every variant in
    ``base_snapshot`` would generate tens of millions of entries
    (e.g. 60 length units x 60 length units x 40 time units squared
    for speed/acceleration categories). Limiting to the registered
    expressions keeps the table focused on categories with explicit
    user-visible unit names.
    """
    # Build a per-base lookup that maps a literal unit to its SI factor
    # (e.g. "m" -> 1.0, "km" -> 1000.0, "cm" -> 0.01). This is the
    # INVERSE of base_snapshot which maps base -> {literal: factor}.
    # We also need the canonical SI base for each axis.
    # Build a flat literal->SI_factor mapping from base_snapshot.
    # Multiple bases can register overlapping literals (the SI base
    # is the one with factor 1.0). Last write wins, which is fine
    # because the SI base is always registered with factor 1.0 and
    # appears in base_snapshot along with the prefixed variants.
    literal_factor: dict[str, float] = {}
    for units in base_snapshot.values():
        for lit, fac in units.items():
            literal_factor[lit] = fac

    # For each derived expression, compute its SI factor and group
    # by category, then add pairwise conversion factors.
    grouped: dict[str, list[tuple[str, float]]] = {}
    for unit_name, category in _DERIVED_CATEGORIES.items():
        atoms = _parse_compound_atoms(unit_name)
        if atoms is None:
            continue
        factor = 1.0
        ok = True
        for literal, exp in atoms:
            f = literal_factor.get(literal)
            if f is None:
                ok = False
                break
            factor *= f**exp
        if not ok:
            continue
        grouped.setdefault(category, []).append((unit_name, factor))

    # Pairwise factors within each category
    for category, entries in grouped.items():
        for i, (from_expr, from_factor) in enumerate(entries):
            for j, (to_expr, to_factor) in enumerate(entries):
                if i != j:
                    conversions[(from_expr, to_expr)] = from_factor / to_factor


def _parse_compound_atoms(unit: str) -> list[tuple[str, int]] | None:
    """Parse a unit string into a list of (literal, signed_exponent) atoms.

    Returns None on unparseable input. The list may be empty (e.g. for
    the dimensionless case).
    """
    sig = _parse_compound_signature(unit)
    if sig is None:
        return None
    num, den = sig
    return [(b, e) for b, e in num] + [(b, -e) for b, e in den]


# Pre-computed conversion factors: (from_unit, to_unit) -> factor
UNIT_CONVERSIONS: dict[tuple[str, str], float] = {}


def _rebuild_conversions() -> None:
    """Rebuild UNIT_CONVERSIONS after adding custom units.

    Thread-safe: holds _UNITS_LOCK so concurrent readers see a consistent
    UNIT_CONVERSIONS swap.
    """
    global UNIT_CONVERSIONS
    new_table = _build_unit_conversions()
    with _UNITS_LOCK:
        UNIT_CONVERSIONS = new_table


# Note: the initial _rebuild_conversions() call is deferred to the end
# of this module (after UNIT_ALIASES, UNIT_CATEGORIES, and
# _DERIVED_CATEGORIES are defined).


# Map all unit aliases to canonical forms.
# Self-mappings (e.g., "m": "m") ensure normalize_unit() recognizes canonical
# forms via .get(unit, unit) — without them, canonical forms would pass through
# unmapped and fall back to the raw input.
UNIT_ALIASES: dict[str, str] = {
    # Length
    "m": "m",
    "meter": "m",
    "meters": "m",
    "metre": "m",
    "metres": "m",
    "km": "km",
    "kilometer": "km",
    "kilometers": "km",
    "kilometre": "km",
    "kilometres": "km",
    "cm": "cm",
    "centimeter": "cm",
    "centimeters": "cm",
    "centimetre": "cm",
    "centimetres": "cm",
    "mm": "mm",
    "millimeter": "mm",
    "millimeters": "mm",
    "millimetre": "mm",
    "millimetres": "mm",
    "um": "um",
    "μm": "um",
    "micrometer": "um",
    "micrometers": "um",
    "nm": "nm",
    "nanometer": "nm",
    "nanometers": "nm",
    "pm": "pm",
    "picometer": "pm",
    "picometers": "pm",
    "in": "inch",
    "inch": "inch",
    "inches": "inch",
    "ft": "ft",
    "foot": "ft",
    "feet": "ft",
    "yd": "yd",
    "yard": "yd",
    "yards": "yd",
    "mi": "mi",
    "mile": "mi",
    "miles": "mi",
    "ly": "ly",
    "lightyear": "ly",
    "lightyears": "ly",
    "au": "au",
    "astronomicalunit": "au",
    "astronomicalunits": "au",
    "pc": "pc",
    "parsec": "pc",
    "parsecs": "pc",
    "angstrom": "angstrom",
    "angstroms": "angstrom",
    "fermi": "fermi",
    "nmi": "nmi",
    "nauticalmile": "nmi",
    "nauticalmiles": "nmi",
    "furlong": "furlong",
    "furlongs": "furlong",
    "chain": "chain",
    "chains": "chain",
    "rd": "rd",
    "rod": "rd",
    "rods": "rd",
    "fathom": "fathom",
    "fathoms": "fathom",
    "smoot": "smoot",
    "smoots": "smoot",
    # Time
    "s": "s",
    "sec": "s",
    "secs": "s",
    "second": "s",
    "seconds": "s",
    "ms": "ms",
    "millisecond": "ms",
    "milliseconds": "ms",
    "us": "us",
    "μs": "us",
    "microsecond": "us",
    "microseconds": "us",
    "ns": "ns",
    "nanosecond": "ns",
    "nanoseconds": "ns",
    "ps": "ps",
    "picosecond": "ps",
    "picoseconds": "ps",
    "min": "min",
    "minute": "min",
    "minutes": "min",
    "h": "h",
    "hr": "h",
    "hour": "h",
    "hours": "h",
    "d": "d",
    "day": "d",
    "days": "d",
    "wk": "wk",
    "week": "wk",
    "weeks": "wk",
    "yr": "yr",
    "year": "yr",
    "years": "yr",
    "fortnight": "fortnight",
    "fortnights": "fortnight",
    "decade": "decade",
    "decades": "decade",
    "century": "century",
    "centuries": "century",
    "millennium": "millennium",
    "millennia": "millennium",
    # Data storage
    "B": "B",
    "byte": "B",
    "bytes": "B",
    "bit": "bit",
    "bits": "bit",
    "KB": "KB",
    "kilobyte": "KB",
    "kilobytes": "KB",
    "MB": "MB",
    "megabyte": "MB",
    "megabytes": "MB",
    "GB": "GB",
    "gigabyte": "GB",
    "gigabytes": "GB",
    "TB": "TB",
    "terabyte": "TB",
    "terabytes": "TB",
    "PB": "PB",
    "petabyte": "PB",
    "petabytes": "PB",
    "EB": "EB",
    "exabyte": "EB",
    "exabytes": "EB",
    "ZB": "ZB",
    "zettabyte": "ZB",
    "zettabytes": "ZB",
    "YB": "YB",
    "yottabyte": "YB",
    "yottabytes": "YB",
    # Data transfer
    "bps": "bps",
    "bit/s": "bps",
    "bits/s": "bps",
    "Kbps": "Kbps",
    "kilobps": "Kbps",
    "kilobit/s": "Kbps",
    "kilobits/s": "Kbps",
    "Mbps": "Mbps",
    "megabps": "Mbps",
    "megabit/s": "Mbps",
    "megabits/s": "Mbps",
    "Gbps": "Gbps",
    "gigabps": "Gbps",
    "gigabit/s": "Gbps",
    "gigabits/s": "Gbps",
    # Mass
    "kg": "kg",
    "kilogram": "kg",
    "kilograms": "kg",
    "g": "g",
    "gram": "g",
    "grams": "g",
    "mg": "mg",
    "milligram": "mg",
    "milligrams": "mg",
    "ug": "ug",
    "μg": "ug",
    "microgram": "ug",
    "micrograms": "ug",
    "ng": "ng",
    "nanogram": "ng",
    "nanograms": "ng",
    "lb": "lb",
    "lbs": "lb",
    "pound": "lb",
    "pounds": "lb",
    "oz": "oz",
    "ounce": "oz",
    "ounces": "oz",
    "ton": "ton",
    "tons": "ton",
    "tonne": "tonne",
    "tonnes": "tonne",
    "stone": "stone",
    "stones": "stone",
    "st": "stone",
    "long_ton": "long_ton",
    "imperial_ton": "long_ton",
    "slug": "slug",
    "slugs": "slug",
    "ct": "ct",
    "carat": "ct",
    "carats": "ct",
    "gr": "gr",
    "grain": "gr",
    "grains": "gr",
    "dr": "dr",
    "dram": "dr",
    "drams": "dr",
    # Volume
    "L": "L",
    "l": "L",
    "liter": "L",
    "liters": "L",
    "litre": "L",
    "litres": "L",
    "mL": "mL",
    "milliliter": "mL",
    "milliliters": "mL",
    "millilitre": "mL",
    "millilitres": "mL",
    "uL": "uL",
    "μL": "uL",
    "microliter": "uL",
    "microliters": "uL",
    "gal": "gal",
    "gallon": "gal",
    "gallons": "gal",
    "qt": "qt",
    "quart": "qt",
    "quarts": "qt",
    "pt": "pt",
    "pint": "pt",
    "pints": "pt",
    "cup": "cup",
    "cups": "cup",
    "floz": "floz",
    "fl oz": "floz",
    "fluidounce": "floz",
    "fluidounces": "floz",
    "tbsp": "tbsp",
    "tablespoon": "tbsp",
    "tablespoons": "tbsp",
    "tsp": "tsp",
    "teaspoon": "tsp",
    "teaspoons": "tsp",
    # Cubic volume
    "m3": "m3",
    "m^3": "m3",
    "cubicmeter": "m3",
    "cubicmeters": "m3",
    "cm3": "cm3",
    "cm^3": "cm3",
    "cc": "cm3",
    "cubiccentimeter": "cm3",
    "cubiccentimeters": "cm3",
    "ft3": "ft3",
    "ft^3": "ft3",
    "cubicfoot": "ft3",
    "cubicfeet": "ft3",
    "in3": "in3",
    "in^3": "in3",
    "cubicinch": "in3",
    "cubicinches": "in3",
    "yd3": "yd3",
    "yd^3": "yd3",
    "cubicyard": "yd3",
    "cubicyards": "yd3",
    "mm3": "mm3",
    "mm^3": "mm3",
    "cubicmillimeter": "mm3",
    "cubicmillimeters": "mm3",
    "km3": "km3",
    "km^3": "km3",
    "cubickilometer": "km3",
    "cubickilometers": "km3",
    "mi3": "mi3",
    "mi^3": "mi3",
    "cubicmile": "mi3",
    "cubicmiles": "mi3",
    # Pressure
    "Pa": "Pa",
    "pascal": "Pa",
    "pascals": "Pa",
    "kPa": "kPa",
    "kilopascal": "kPa",
    "kilopascals": "kPa",
    "MPa": "MPa",
    "megapascal": "MPa",
    "megapascals": "MPa",
    "GPa": "GPa",
    "gigapascal": "GPa",
    "gigapascals": "GPa",
    "bar": "bar",
    "bars": "bar",
    "mbar": "mbar",
    "millibar": "mbar",
    "atm": "atm",
    "atmosphere": "atm",
    "atmospheres": "atm",
    "psi": "psi",
    "psia": "psi",
    "mmHg": "mmHg",
    "torr": "torr",
    "inHg": "inHg",
    "mmH2O": "mmH2O",
    "inH2O": "inH2O",
    # Energy
    "J": "J",
    "joule": "J",
    "joules": "J",
    "kJ": "kJ",
    "kilojoule": "kJ",
    "kilojoules": "kJ",
    "MJ": "MJ",
    "megajoule": "MJ",
    "megajoules": "MJ",
    "GJ": "GJ",
    "gigajoule": "GJ",
    "gigajoules": "GJ",
    "cal": "cal",
    "calorie": "cal",
    "calories": "cal",
    "kcal": "kcal",
    "kilocalorie": "kcal",
    "kilocalories": "kcal",
    "Wh": "Wh",
    "watt-hour": "Wh",
    "watt-hours": "Wh",
    "kWh": "kWh",
    "kilowatt-hour": "kWh",
    "kilowatt-hours": "kWh",
    "BTU": "BTU",
    "btu": "BTU",
    "eV": "eV",
    "ev": "eV",
    "electronvolt": "eV",
    "electronvolts": "eV",
    # Power
    "W": "W",
    "watt": "W",
    "watts": "W",
    "kW": "kW",
    "kilowatt": "kW",
    "kilowatts": "kW",
    "MW": "MW",
    "megawatt": "MW",
    "megawatts": "MW",
    "GW": "GW",
    "gigawatt": "GW",
    "gigawatts": "GW",
    "mW": "mW",
    "milliwatt": "mW",
    "milliwatts": "mW",
    "hp": "hp",
    "horsepower": "hp",
    # Force
    "N": "N",
    "newton": "N",
    "newtons": "N",
    "kN": "kN",
    "kilonewton": "kN",
    "mN": "mN",
    "millinewton": "mN",
    "dyne": "dyne",
    "dynes": "dyne",
    "lbf": "lbf",
    "poundforce": "lbf",
    # Voltage
    "V": "V",
    "volt": "V",
    "volts": "V",
    "kV": "kV",
    "kilovolt": "kV",
    "mV": "mV",
    "millivolt": "mV",
    "uV": "μV",
    "μV": "μV",
    "microvolt": "μV",
    # Current
    "A": "A",
    "amp": "A",
    "ampere": "A",
    "amperes": "A",
    "mA": "mA",
    "milliamp": "mA",
    "milliampere": "mA",
    "uA": "μA",
    "μA": "μA",
    "microamp": "μA",
    "microampere": "μA",
    # Angles
    "rad": "rad",
    "radian": "rad",
    "radians": "rad",
    "deg": "deg",
    "degree": "deg",
    "degrees": "deg",
    # Temperature
    "K": "K",
    "kelvin": "K",
    "kelvins": "K",
    "C": "C",
    "celsius": "C",
    "centigrade": "C",
    "F": "F",
    "fahrenheit": "F",
    "Ra": "Ra",
    "rankine": "Ra",
    "degf": "F",
    "degc": "C",
    "degk": "K",
    "degr": "Ra",
    "\u00b0F": "F",
    "\u00b0C": "C",
    "\u00b0K": "K",
    "\u00b0R": "Ra",
    # Speed
    "m/s": "m/s",
    "mps": "m/s",
    "meterpersecond": "m/s",
    "meterspersecond": "m/s",
    "km/h": "km/h",
    "kph": "km/h",
    "kmh": "km/h",
    "kilometerperhour": "km/h",
    "kilometersperhour": "km/h",
    "mph": "mph",
    "mileperhour": "mph",
    "milesperhour": "mph",
    "mi/h": "mph",
    "kn": "kn",
    "knot": "kn",
    "knots": "kn",
    "kt": "kn",
    "mach": "mach",
    # Area
    "m2": "m2",
    "m^2": "m2",
    "sqm": "m2",
    "squaremeter": "m2",
    "squaremeters": "m2",
    "km2": "km2",
    "km^2": "km2",
    "squarekilometer": "km2",
    "squarekilometers": "km2",
    "cm2": "cm2",
    "cm^2": "cm2",
    "squarecentimeter": "cm2",
    "squarecentimeters": "cm2",
    "mm2": "mm2",
    "mm^2": "mm2",
    "squaremillimeter": "mm2",
    "squaremillimeters": "mm2",
    "ha": "ha",
    "hectare": "ha",
    "hectares": "ha",
    "acre": "acre",
    "acres": "acre",
    "ft2": "ft2",
    "ft^2": "ft2",
    "sqft": "ft2",
    "squarefoot": "ft2",
    "squarefeet": "ft2",
    "in2": "in2",
    "in^2": "in2",
    "sqin": "in2",
    "squareinch": "in2",
    "squareinches": "in2",
    "mi2": "mi2",
    "mi^2": "mi2",
    "sqmi": "mi2",
    "squaremile": "mi2",
    "squaremiles": "mi2",
    "yd2": "yd2",
    "yd^2": "yd2",
    "sqyd": "yd2",
    "squareyard": "yd2",
    "squareyards": "yd2",
    # Area: "**" exponent form (used in compound expressions and accepted as
    # a unit alias for direct unit_convert calls; equivalent to the short form)
    "m**2": "m2",
    "cm**2": "cm2",
    "mm**2": "mm2",
    "km**2": "km2",
    "in**2": "in2",
    "ft**2": "ft2",
    "yd**2": "yd2",
    "mi**2": "mi2",
    "m**3": "m3",
    "cm**3": "cm3",
    "mm**3": "mm3",
    "km**3": "km3",
    "in**3": "in3",
    "ft**3": "ft3",
    "yd**3": "yd3",
    "mi**3": "mi3",
    # Frequency
    "Hz": "Hz",
    "hertz": "Hz",
    "kHz": "kHz",
    "kilohertz": "kHz",
    "MHz": "MHz",
    "megahertz": "MHz",
    "GHz": "GHz",
    "gigahertz": "GHz",
    "THz": "THz",
    "terahertz": "THz",
    # Case-insensitive aliases (common capitalizations)
    "KM": "km",
    "KG": "kg",
    "GHZ": "GHz",
    "KHZ": "kHz",
    "MHZ": "MHz",
    "Meters": "m",
    "Miles": "mi",
    "Inches": "inch",
    "Feet": "ft",
    "Pounds": "lb",
    "Ounces": "oz",
    "Celsius": "C",
    "Fahrenheit": "F",
    "Kelvin": "K",
    "Hours": "h",
    "Minutes": "min",
    "Seconds": "s",
    "Kilograms": "kg",
    "Grams": "g",
    "Liters": "L",
    "Newtons": "N",
    "Volts": "V",
    "Amps": "A",
    "Amperes": "A",
    "Watts": "W",
    "Joules": "J",
    "Pascals": "Pa",
}


def normalize_unit(unit: str) -> str:
    """Normalize a unit to its canonical form.

    Tries, in order:
    1. The literal input (exact match)
    2. .lower() (lowercase form)
    3. .upper() (uppercase form)
    4. .title() / .capitalize() (mixed-case common forms)

    If none match, returns the input unchanged.
    """
    if unit in UNIT_ALIASES:
        return UNIT_ALIASES[unit]
    for candidate in (unit.lower(), unit.upper(), unit.title(), unit.capitalize()):
        if candidate in UNIT_ALIASES:
            return UNIT_ALIASES[candidate]
    return unit


TEMPERATURE_CONVERSIONS: dict[tuple[str, str], tuple[float, float]] = {
    # (from, to) -> (multiplier, offset)
    # Note: Offsets are derived from the canonical relationships:
    #   C = K - 273.15,  F = C * 9/5 + 32,  R = F + 459.67
    # We use the most-precise Python representation (e.g. 273.15 * 1.8
    # exactly, not the rounded 491.67) so that direct and indirect conversion
    # paths agree bit-for-bit.
    ("K", "C"): (1.0, -273.15),
    ("C", "K"): (1.0, 273.15),
    ("K", "F"): (1.8, -459.67),
    ("F", "K"): (1.0 / 1.8, 459.67 / 1.8),
    ("C", "F"): (1.8, 32.0),
    ("F", "C"): (1.0 / 1.8, -32.0 / 1.8),
    ("K", "Ra"): (1.8, 0.0),
    ("Ra", "K"): (1.0 / 1.8, 0.0),
    ("C", "Ra"): (1.8, 273.15 * 1.8),
    ("Ra", "C"): (1.0 / 1.8, -273.15),
    ("F", "Ra"): (1.0, 459.67),
    ("Ra", "F"): (1.0, -459.67),
}


def convert_temperature(value: float, from_unit: str, to_unit: str) -> float:
    """Convert temperature values with proper offset handling."""
    from_unit = normalize_unit(from_unit)
    to_unit = normalize_unit(to_unit)

    if from_unit == to_unit:
        if not math.isfinite(value):
            raise ValueError(f"Temperature value must be finite, got {value}")
        return value

    if not math.isfinite(value):
        raise ValueError(f"Temperature value must be finite, got {value}")

    key = (from_unit, to_unit)
    if key in TEMPERATURE_CONVERSIONS:
        multiplier, offset = TEMPERATURE_CONVERSIONS[key]
        return value * multiplier + offset

    raise ValueError(f"Cannot convert temperature from {from_unit} to {to_unit}")


def get_conversion_factor(from_unit: str, to_unit: str) -> float:
    """Get conversion factor from one unit to another."""
    from_unit = normalize_unit(from_unit)
    to_unit = normalize_unit(to_unit)

    if from_unit == to_unit:
        return 1.0

    # The conversion table stores multiple equivalent forms of the same
    # unit (e.g., "m2", "m**2", "m^2"). We try the original pair first,
    # then fall back to looking up either side in any of its equivalent
    # forms so cross-form lookups succeed (e.g., "m**2" -> "acre" stored
    # as "m2" -> "acre").
    key = (from_unit, to_unit)
    if key in UNIT_CONVERSIONS:
        return UNIT_CONVERSIONS[key]

    from_forms = _short_compound_forms(from_unit)
    to_forms = _short_compound_forms(to_unit)
    seen: set[tuple[str, str]] = set()
    seen.add((from_unit, to_unit))
    for f in from_forms:
        for t in to_forms:
            if (f, t) in seen:
                continue
            seen.add((f, t))
            if (f, t) in UNIT_CONVERSIONS:
                return UNIT_CONVERSIONS[(f, t)]
            if (t, f) in UNIT_CONVERSIONS:
                return 1.0 / UNIT_CONVERSIONS[(t, f)]

    # Try the compound-simplification form too (e.g., "m**2/s**2" -> "m2/s2")
    simplified_from = _simplify_unit_string(from_unit)
    if simplified_from is not None and simplified_from != from_unit:
        if (simplified_from, to_unit) in UNIT_CONVERSIONS:
            return UNIT_CONVERSIONS[(simplified_from, to_unit)]
        if (to_unit, simplified_from) in UNIT_CONVERSIONS:
            return 1.0 / UNIT_CONVERSIONS[(to_unit, simplified_from)]
    simplified_to = _simplify_unit_string(to_unit)
    if simplified_to is not None and simplified_to != to_unit:
        if (from_unit, simplified_to) in UNIT_CONVERSIONS:
            return UNIT_CONVERSIONS[(from_unit, simplified_to)]
        if (simplified_to, from_unit) in UNIT_CONVERSIONS:
            return 1.0 / UNIT_CONVERSIONS[(simplified_to, from_unit)]

    raise ValueError(f"Cannot convert from {from_unit} to {to_unit}")


# Map short compound unit forms ("m2", "cm2", "km3", "m2/s2") to the
# equivalent "**" and "^" forms so cross-form conversions work. Used by
# get_conversion_factor; the base aliases remain valid for input parsing.
_SHORT_COMPOUND_FORMS: dict[str, tuple[str, str, str]] = {
    "m2": ("m2", "m**2", "m^2"),
    "cm2": ("cm2", "cm**2", "cm^2"),
    "mm2": ("mm2", "mm**2", "mm^2"),
    "km2": ("km2", "km**2", "km^2"),
    "in2": ("in2", "in**2", "in^2"),
    "ft2": ("ft2", "ft**2", "ft^2"),
    "yd2": ("yd2", "yd**2", "yd^2"),
    "mi2": ("mi2", "mi**2", "mi^2"),
    "m3": ("m3", "m**3", "m^3"),
    "cm3": ("cm3", "cm**3", "cm^3"),
    "mm3": ("mm3", "mm**3", "mm^3"),
    "km3": ("km3", "km**3", "km^3"),
    "in3": ("in3", "in**3", "in^3"),
    "ft3": ("ft3", "ft**3", "ft^3"),
    "yd3": ("yd3", "yd**3", "yd^3"),
    "mi3": ("mi3", "mi**3", "mi^3"),
}
_SHORT_COMPOUND_EXPANSION: dict[str, str] = {
    short: star for short, (_, star, _) in _SHORT_COMPOUND_FORMS.items()
}
_SHORT_COMPOUND_CARET: dict[str, str] = {
    short: caret for short, (_, _, caret) in _SHORT_COMPOUND_FORMS.items()
}
_SHORT_COMPOUND_COLLAPSE: dict[str, str] = {
    star: short for short, (short, star, _) in _SHORT_COMPOUND_FORMS.items()
}


def _expand_short_compound(unit: str) -> str:
    """Expand a short compound form like 'm2' to 'm**2'.

    Returns the input unchanged when no expansion is needed. Only single
    short forms are handled here; cross-form operations on compound
    expressions (e.g., 'm2/s2' vs 'm**2/s**2') rely on
    ``_simplify_unit_string`` to canonicalize first.
    """
    return _SHORT_COMPOUND_EXPANSION.get(unit, unit)


def _collapse_short_compound(unit: str) -> str:
    """Collapse a 'm**2' form to 'm2' (the short compound form).

    Returns the input unchanged when no collapse is needed.
    """
    return _SHORT_COMPOUND_COLLAPSE.get(unit, unit)


def _short_compound_forms(unit: str) -> list[str]:
    """Return all equivalent short-compound forms of the given unit.

    Returns a list including the input and any of {short, "**", "^"}
    forms that are known equivalents. The list is deduplicated and
    preserves order so the original form is checked first.
    """
    forms: list[str] = []
    seen: set[str] = set()
    for f in (unit, _expand_short_compound(unit), _collapse_short_compound(unit)):
        if f not in seen:
            forms.append(f)
            seen.add(f)
    # Also add the caret form if any of the short/expanded forms have one
    for _, (s_short, s_star, s_caret) in _SHORT_COMPOUND_FORMS.items():
        if unit == s_short or unit == s_star or unit == s_caret:
            for f in (s_short, s_star, s_caret):
                if f not in seen:
                    forms.append(f)
                    seen.add(f)
    return forms


def is_unit(text: str) -> bool:
    """Check if text represents a unit (case-insensitive)."""
    if text in UNIT_ALIASES:
        return True
    for candidate in (text.lower(), text.upper(), text.title(), text.capitalize()):
        if candidate in UNIT_ALIASES:
            return True
    return False


UNIT_CATEGORIES: dict[str, str] = {
    base_unit: category for category, units_dict in UNIT_BASE.items() for base_unit in units_dict
}

# Manual category mapping. The base unit names in UNIT_BASE (e.g. "m"
# for length, "kg" for mass) are kept as the category value for
# backwards compatibility with the original public API. The full set
# of categories is documented as a literal below so consumers can
# rely on a fixed, named set.
_BASE_CATEGORY: dict[str, str] = {
    "m": "length",
    "s": "time",
    "B": "data",
    "bps": "data_rate",
    "kg": "mass",
    "L": "volume",
    "Pa": "pressure",
    "J": "energy",
    "W": "power",
    "N": "force",
    "V": "voltage",
    "A": "current",
    "rad": "angle",
    "m/s": "speed",
    "m2": "area",
    "Hz": "frequency",
}
# Remap the auto-derived UNIT_CATEGORIES from the raw base unit (e.g.
# "m") to a friendly category name (e.g. "length") so MCP tools and
# external consumers see stable category strings.
UNIT_CATEGORIES = {unit: _BASE_CATEGORY.get(cat, cat) for unit, cat in UNIT_CATEGORIES.items()}

# Manual categories for units that live outside UNIT_BASE (temperatures
# use offset math and dimensionless categories, neither of which fit the
# multiplicative UNIT_BASE structure). These complete the coverage so
# any unit in UNIT_ALIASES has a category, which is required for
# add/subtract compatibility checks.
UNIT_CATEGORIES_EXTRA: dict[str, str] = {
    "K": "temperature",
    "C": "temperature",
    "F": "temperature",
    "Ra": "temperature",
}
UNIT_CATEGORIES.update(UNIT_CATEGORIES_EXTRA)


def get_unit_category(unit: str) -> str | None:
    """Get the category for a unit (e.g., 'm' -> 'length', 'gal' -> 'volume')."""
    normalized = normalize_unit(unit)
    direct = UNIT_CATEGORIES.get(normalized)
    if direct is not None:
        return direct
    # Fall back to the derived category for compound unit expressions
    # produced by __pow__/__truediv__/__mul__ (e.g. "m**2", "m/s**2",
    # "m*s"). The op separator is irrelevant for categorization — we
    # canonicalize to "/" so that "m//s" and "m/s" both reduce to the
    # same signature.
    return _derived_category(normalized)


def _parse_compound_signature(
    unit: str,
) -> tuple[tuple[tuple[str, int], ...], tuple[tuple[str, int], ...]] | None:
    """Parse a compound unit string into (numerator, denominator) signatures.

    Each signature is a tuple of ``(base_unit, exponent)`` pairs, sorted
    alphabetically with exponents combined for repeated bases. Returns
    ``None`` if the input cannot be parsed as a supported compound
    form.

    Recognized forms:
      - ``"X**N"``     -> ``((X, N),)``, ``()``
      - ``"X**-N"``    -> ``()``,      ``((X, N),)``
      - ``"A*B"``      -> ``((A,1),(B,1))``, ``()``
      - ``"A/B"``      -> ``((A,1),)``, ``((B,1),)``
      - ``"A//B"``     -> same as ``A/B``
      - ``"A%B"``      -> same as ``A/B``

    Mixed forms like ``"m**2*s"`` and ``"m/s**2"`` are also handled.

    Operators ``*``, ``/``, ``//``, and ``%`` are evaluated
    left-to-right with equal precedence (matching standard
    mathematical convention). For example, ``"m/s*s"`` is parsed as
    ``(m/s)*s = m``, not as ``m/(s*s) = m/s**2``. Cancellation of
    repeated bases is performed so that the returned numerator and
    denominator share no base and contain only positive exponents.
    """
    if not unit or not isinstance(unit, str):
        return None

    # Strip a leading "1/" or "1//" or "1%" reciprocal marker (the
    # convention used by __rfloordiv__ / __rmod__). These are
    # semantically identical to having the unit on the other side.
    if unit.startswith("1//"):
        inner = _parse_compound_signature(unit[3:])
        if inner is None:
            return None
        num, den = inner
        return den, num
    if unit.startswith("1/"):
        inner = _parse_compound_signature(unit[2:])
        if inner is None:
            return None
        num, den = inner
        return den, num
    if unit.startswith("1%"):
        inner = _parse_compound_signature(unit[2:])
        if inner is None:
            return None
        num, den = inner
        return den, num

    op_idx, op = _find_last_top_level_op(unit)
    if op_idx != -1:
        left_str = unit[:op_idx]
        right_str = unit[op_idx + len(op) :]
        left = _parse_compound_signature(left_str)
        right = _parse_compound_signature(right_str)
        if left is None or right is None:
            return None
        if op == "*":
            num = left[0] + right[0]
            den = left[1] + right[1]
        else:
            num = left[0] + right[1]
            den = left[1] + right[0]
        merged = _merge_signatures(num, den)
        num_only = tuple((b, e) for b, e in merged if e > 0)
        den_only = tuple((b, -e) for b, e in merged if e < 0)
        return num_only, den_only

    atom = _parse_atom_signature(unit)
    if atom is None:
        return None
    num_only = tuple((b, e) for b, e in atom if e > 0)
    den_only = tuple((b, -e) for b, e in atom if e < 0)
    return num_only, den_only


def _find_last_top_level_op(unit: str) -> tuple[int, str]:
    """Find the rightmost top-level operator in a unit string.

    Operators considered: ``*``, ``/``, ``//``, ``%``. The ``**``
    exponentiation sequence is skipped so that it is not mistaken for
    a multiplication. Returns ``(index, operator)`` of the rightmost
    operator, or ``(-1, "")`` if the string contains no operator.
    """
    i = len(unit) - 1
    while i >= 0:
        c = unit[i]
        if c == "*":
            if i > 0 and unit[i - 1] == "*":
                i -= 2
                continue
            return (i, "*")
        if c == "/":
            if i > 0 and unit[i - 1] == "/":
                return (i - 1, "//")
            return (i, "/")
        if c == "%":
            return (i, "%")
        i -= 1
    return (-1, "")


def _parse_atom_signature(atom: str) -> tuple[tuple[str, int], ...] | None:
    """Parse a single unit atom like "m", "m**2", "m**-1".

    A compound like "m**2*s" is split into its factors and combined.
    Returns None if the atom contains an unrecognized form.
    """
    if not atom:
        return None
    # Match each factor: base (alphanumeric/_+) optionally followed
    # by **<signed integer>. The regex skips over the bare '*' in '**'
    # by matching the base and exponent atomically.
    matches = re.findall(r"([A-Za-z_]+)(?:\*\*(-?\d+))?", atom)
    if not matches:
        return None
    # Verify the entire string is consumed by the match pattern
    reconstructed = ""
    for base, exp_str in matches:
        if not base:
            return None
        reconstructed += base + ("**" + exp_str if exp_str else "")
    if reconstructed != atom:
        return None
    parts: list[tuple[str, int]] = []
    for base, exp_str in matches:
        if exp_str:
            try:
                exp = int(exp_str)
            except ValueError:
                return None
        else:
            exp = 1
        parts.append((base, exp))
    return _merge_signatures(tuple(parts), ())


def _merge_signatures(
    num: tuple[tuple[str, int], ...], den: tuple[tuple[str, int], ...]
) -> tuple[tuple[str, int], ...]:
    """Combine numerator and denominator signatures into a canonical form.

    Exponents from the denominator are subtracted; the result is sorted
    alphabetically by base unit for stable comparison.
    """
    counts: dict[str, int] = {}
    for base, exp in num:
        counts[base] = counts.get(base, 0) + exp
    for base, exp in den:
        counts[base] = counts.get(base, 0) - exp
    # Drop zero exponents (cancelled units)
    counts = {b: e for b, e in counts.items() if e != 0}
    return tuple(sorted(counts.items()))


# Maps a canonical signature (serialized as a string) to a category.
# Signatures are stored as a string like "m**2" or "m/s**2" for easy
# reading and unambiguous comparison. The parser
# (``_parse_compound_signature``) returns the same form, so we can use
# a simple dict lookup.
_DERIVED_CATEGORIES: dict[str, str] = {
    # Area
    "m**2": "area",
    "ft**2": "area",
    "inch**2": "area",
    "yd**2": "area",
    "mi**2": "area",
    "cm**2": "area",
    "mm**2": "area",
    "km**2": "area",
    # Volume
    "m**3": "volume",
    "ft**3": "volume",
    "inch**3": "volume",
    "cm**3": "volume",
    "mm**3": "volume",
    "km**3": "volume",
    "mi**3": "volume",
    "yd**3": "volume",
    # Speed / velocity
    "m/s": "speed",
    "km/h": "speed",
    "mi/h": "speed",
    "ft/s": "speed",
    "m/min": "speed",
    # Acceleration
    "m/s**2": "acceleration",
    "ft/s**2": "acceleration",
    # Energy / work
    "J": "energy",
    "kJ": "energy",
    # Power
    "W": "power",
    "kW": "power",
    "MW": "power",
    # Pressure
    "Pa": "pressure",
    "bar": "pressure",
    "psi": "pressure",
    "atm": "pressure",
    # Frequency
    "Hz": "frequency",
    "kHz": "frequency",
    "MHz": "frequency",
    "GHz": "frequency",
    # Time (single base)
    "s": "time",
    "min": "time",
    "h": "time",
    "day": "time",
    "week": "time",
    "year": "time",
    # Mass
    "kg": "mass",
    "g": "mass",
    "mg": "mass",
    "lb": "mass",
    "oz": "mass",
    # Data
    "B": "data",
    "KB": "data",
    "MB": "data",
    "GB": "data",
    "TB": "data",
    "PB": "data",
    # Data rate (B/s etc.)
    "B/s": "data_rate",
    "KB/s": "data_rate",
    "MB/s": "data_rate",
    "GB/s": "data_rate",
    "bit/s": "data_rate",
}


def _signature_to_canonical_string(
    sig: tuple[tuple[tuple[str, int], ...], tuple[tuple[str, int], ...]],
) -> str | None:
    """Build a canonical unit-string from a (num, den) signature.

    e.g. ``(((("m", 2),), ()))`` -> ``"m**2"``,
    ``((("m",), (("s",),)))`` -> ``"m/s"``.
    Returns None if the signature cannot be represented (empty
    numerator and denominator, or an exponent that cannot be rendered).
    """
    num, den = sig
    if not num and not den:
        return None
    num_parts: list[str] = []
    for base, exp in num:
        if exp == 1:
            num_parts.append(base)
        elif exp > 0:
            num_parts.append(f"{base}**{exp}")
        else:
            return None  # negative exponents belong in the denominator
    den_parts: list[str] = []
    for base, exp in den:
        if exp == 1:
            den_parts.append(base)
        elif exp > 0:
            den_parts.append(f"{base}**{exp}")
        else:
            return None
    num_str = "*".join(num_parts) if num_parts else ""
    den_str = "*".join(den_parts) if den_parts else ""
    if num_str and den_str:
        return f"{num_str}/{den_str}"
    if num_str:
        return num_str
    if den_str:
        return f"1/{den_str}"
    return None


def _derived_category(unit: str) -> str | None:
    """Return the category for a compound unit expression, or None."""
    sig = _parse_compound_signature(unit)
    if sig is None:
        return None
    canonical = _signature_to_canonical_string(sig)
    if canonical is None:
        return None
    return _DERIVED_CATEGORIES.get(canonical)


def _simplify_unit_string(unit: str | None) -> str | None:
    """Parse, cancel, and re-render a compound unit string.

    Returns the canonical form (e.g. ``"m/s*s"`` -> ``"m"``,
    ``"m*m/m"`` -> ``"m"``, ``"m**2*m"`` -> ``"m**3"``). Returns
    ``None`` if the input is ``None``, or if the simplified result
    is fully dimensionless (e.g. ``"m**0"`` -> ``None``,
    ``"m/m"`` -> ``None``). Returns the input unchanged
    if it cannot be parsed as a compound unit.
    """
    if unit is None:
        return None
    sig = _parse_compound_signature(unit)
    if sig is None:
        return unit
    return _signature_to_canonical_string(sig)


def are_units_compatible(unit1: str | None, unit2: str | None) -> bool:
    """Check if two units are compatible for addition/subtraction.

    Returns True if:
    - Both units are None (dimensionless)
    - Both units belong to the same category (e.g., both length)

    Returns False if:
    - Exactly one unit is None (dimensionless cannot be added to dimensional)
    - Units are from different categories
    - One category is known but the other is unknown
    """
    if unit1 is None and unit2 is None:
        return True
    if unit1 is None or unit2 is None:
        return False

    cat1 = get_unit_category(unit1)
    cat2 = get_unit_category(unit2)

    if cat1 is None or cat2 is None:
        return False

    return cat1 == cat2


def get_all_units() -> list[str]:
    """Get list of all supported units."""
    return sorted(UNIT_ALIASES.keys())


# Initial build of UNIT_CONVERSIONS, now that all the unit data
# structures (UNIT_ALIASES, UNIT_CATEGORIES, _DERIVED_CATEGORIES) and
# helper functions are defined. See plans/production_review_2026_07_b.md
# (B6) for the compound-unit support this enables.
_rebuild_conversions()
