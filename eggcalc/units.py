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
from collections.abc import Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType

Numeric = float | int | complex

FLOAT_EPSILON = 1e-10
MAX_RESULT_VALUE = 1e308

# Resource bounds for compound unit parsing
MAX_COMPOUND_DEPTH = 16
MAX_COMPOUND_ATOMS = 32
MAX_UNIT_STRING_LENGTH = 256


# ---------------------------------------------------------------------------
# Structural dimension model (D1-D2)
# ---------------------------------------------------------------------------


class Dimension:
    """Immutable structural dimension for unit classification.

    Encodes exponents for the eight SI base dimensions.  Two units are
    compatible for addition/subtraction if and only if their dimensions
    are equal (after normalising to a shared base).

    Angles are dimensionless with semantic metadata (``angle=True``).
    """

    __slots__ = (
        "length",
        "mass",
        "time",
        "current",
        "temperature",
        "amount",
        "luminous_intensity",
        "information",
        "angle",
    )

    # Type annotations for __slots__ attributes (mypy needs these)
    length: int
    mass: int
    time: int
    current: int
    temperature: int
    amount: int
    luminous_intensity: int
    information: int
    angle: bool

    def __init__(
        self,
        length: int = 0,
        mass: int = 0,
        time: int = 0,
        current: int = 0,
        temperature: int = 0,
        amount: int = 0,
        luminous_intensity: int = 0,
        information: int = 0,
        angle: bool = False,
    ) -> None:
        object.__setattr__(self, "length", length)
        object.__setattr__(self, "mass", mass)
        object.__setattr__(self, "time", time)
        object.__setattr__(self, "current", current)
        object.__setattr__(self, "temperature", temperature)
        object.__setattr__(self, "amount", amount)
        object.__setattr__(self, "luminous_intensity", luminous_intensity)
        object.__setattr__(self, "information", information)
        object.__setattr__(self, "angle", angle)

    # Immutability --------------------------------------------------------

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("Dimension is immutable")

    def __delattr__(self, name: str) -> None:
        raise AttributeError("Dimension is immutable")

    # Identity / comparison -----------------------------------------------

    def _tuple(self) -> tuple[int, ...]:
        return (
            self.length,
            self.mass,
            self.time,
            self.current,
            self.temperature,
            self.amount,
            self.luminous_intensity,
            self.information,
            int(self.angle),
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Dimension):
            return NotImplemented
        return self._tuple() == other._tuple()

    def __hash__(self) -> int:
        return hash(self._tuple())

    def __reduce__(
        self,
    ) -> tuple[type[Dimension], tuple[int, int, int, int, int, int, int, int, bool]]:
        """Support multiprocessing transport without weakening immutability."""
        return (
            type(self),
            (
                self.length,
                self.mass,
                self.time,
                self.current,
                self.temperature,
                self.amount,
                self.luminous_intensity,
                self.information,
                self.angle,
            ),
        )

    def __repr__(self) -> str:
        parts = []
        names = ["L", "M", "T", "I", "Θ", "N", "J", "Q"]
        vals = self._tuple()
        for name, val in zip(names, vals):
            if val != 0:
                parts.append(f"{name}^{val}" if val != 1 else name)
        if self.angle:
            parts.append("∠")
        return f"Dimension({', '.join(parts)})" if parts else "Dimension()"

    # Arithmetic (for compound unit derivation) ---------------------------

    def __mul__(self, other: Dimension) -> Dimension:
        if not isinstance(other, Dimension):
            return NotImplemented
        return Dimension(
            length=self.length + other.length,
            mass=self.mass + other.mass,
            time=self.time + other.time,
            current=self.current + other.current,
            temperature=self.temperature + other.temperature,
            amount=self.amount + other.amount,
            luminous_intensity=self.luminous_intensity + other.luminous_intensity,
            information=self.information + other.information,
            angle=self.angle != other.angle,
        )

    def __truediv__(self, other: Dimension) -> Dimension:
        if not isinstance(other, Dimension):
            return NotImplemented
        return Dimension(
            length=self.length - other.length,
            mass=self.mass - other.mass,
            time=self.time - other.time,
            current=self.current - other.current,
            temperature=self.temperature - other.temperature,
            amount=self.amount - other.amount,
            luminous_intensity=self.luminous_intensity - other.luminous_intensity,
            information=self.information - other.information,
            angle=self.angle != other.angle,
        )

    def __pow__(self, n: int) -> Dimension:
        if not isinstance(n, int):
            return NotImplemented
        return Dimension(
            length=self.length * n,
            mass=self.mass * n,
            time=self.time * n,
            current=self.current * n,
            temperature=self.temperature * n,
            amount=self.amount * n,
            luminous_intensity=self.luminous_intensity * n,
            information=self.information * n,
            angle=self.angle if n % 2 != 0 else False,
        )

    @property
    def is_dimensionless(self) -> bool:
        """True if all exponents are zero and not angle-tagged (purely dimensionless quantity)."""
        return self._tuple() == (0, 0, 0, 0, 0, 0, 0, 0, 0)

    @property
    def is_affine(self) -> bool:
        """True if the dimension has a non-zero temperature exponent.

        Affine dimensions require offset-aware conversion and cannot
        participate in arbitrary multiplication/division.
        """
        return self.temperature != 0


# Pre-built base dimensions for the eight SI base quantities.
DIM_LENGTH = Dimension(length=1)
DIM_MASS = Dimension(mass=1)
DIM_TIME = Dimension(time=1)
DIM_CURRENT = Dimension(current=1)
DIM_TEMPERATURE = Dimension(temperature=1)
DIM_AMOUNT = Dimension(amount=1)
DIM_LUMINOUS = Dimension(luminous_intensity=1)
DIM_INFORMATION = Dimension(information=1)
DIM_DIMENSIONLESS = Dimension()


# ---------------------------------------------------------------------------
# Declarative unit authority (Workstream E)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UnitSpec:
    """Declarative specification for a built-in unit."""

    canonical: str
    aliases: tuple[str, ...]
    dimension: Dimension
    scale_to_base: float
    offset_to_base: float = 0.0
    affine: bool = False
    display: str | None = None
    category: str = ""
    base_canonical: str = ""

    def __post_init__(self) -> None:
        if not self.base_canonical:
            raise ValueError(f"base_canonical must be explicitly supplied for {self.canonical!r}")


UNIT_DEFINITIONS: tuple[UnitSpec, ...] = (
    UnitSpec(
        canonical='deg',
        aliases=(
            'deg',
            'degree',
            'degrees',
        ),
        dimension=Dimension(angle=True),
        scale_to_base=0.017453292519943295,
        display='deg',
        category='angle',
        base_canonical='rad',
    ),
    UnitSpec(
        canonical='rad',
        aliases=(
            'rad',
            'radian',
            'radians',
        ),
        dimension=Dimension(angle=True),
        scale_to_base=1.0,
        display='rad',
        category='angle',
        base_canonical='rad',
    ),
    UnitSpec(
        canonical='acre',
        aliases=(
            'acre',
            'acres',
        ),
        dimension=Dimension(length=2),
        scale_to_base=4046.8564224,
        display='acre',
        category='area',
        base_canonical='m2',
    ),
    UnitSpec(
        canonical='cm2',
        aliases=(
            'cm**2',
            'cm2',
            'cm^2',
            'squarecentimeter',
            'squarecentimeters',
        ),
        dimension=Dimension(length=2),
        scale_to_base=0.0001,
        display='cm2',
        category='area',
        base_canonical='m2',
    ),
    UnitSpec(
        canonical='ft2',
        aliases=(
            'ft**2',
            'ft2',
            'ft^2',
            'sqft',
            'squarefeet',
            'squarefoot',
        ),
        dimension=Dimension(length=2),
        scale_to_base=0.09290304,
        display='ft2',
        category='area',
        base_canonical='m2',
    ),
    UnitSpec(
        canonical='ha',
        aliases=(
            'ha',
            'hectare',
            'hectares',
        ),
        dimension=Dimension(length=2),
        scale_to_base=10000.0,
        display='ha',
        category='area',
        base_canonical='m2',
    ),
    UnitSpec(
        canonical='in2',
        aliases=(
            'in**2',
            'in2',
            'in^2',
            'sqin',
            'squareinch',
            'squareinches',
        ),
        dimension=Dimension(length=2),
        scale_to_base=0.00064516,
        display='in2',
        category='area',
        base_canonical='m2',
    ),
    UnitSpec(
        canonical='km2',
        aliases=(
            'km**2',
            'km2',
            'km^2',
            'squarekilometer',
            'squarekilometers',
        ),
        dimension=Dimension(length=2),
        scale_to_base=1000000.0,
        display='km2',
        category='area',
        base_canonical='m2',
    ),
    UnitSpec(
        canonical='m2',
        aliases=(
            'm**2',
            'm2',
            'm^2',
            'sqm',
            'squaremeter',
            'squaremeters',
        ),
        dimension=Dimension(length=2),
        scale_to_base=1.0,
        display='m2',
        category='area',
        base_canonical='m2',
    ),
    UnitSpec(
        canonical='mi2',
        aliases=(
            'mi**2',
            'mi2',
            'mi^2',
            'sqmi',
            'squaremile',
            'squaremiles',
        ),
        dimension=Dimension(length=2),
        scale_to_base=2589988.110336,
        display='mi2',
        category='area',
        base_canonical='m2',
    ),
    UnitSpec(
        canonical='mm2',
        aliases=(
            'mm**2',
            'mm2',
            'mm^2',
            'squaremillimeter',
            'squaremillimeters',
        ),
        dimension=Dimension(length=2),
        scale_to_base=1e-06,
        display='mm2',
        category='area',
        base_canonical='m2',
    ),
    UnitSpec(
        canonical='yd2',
        aliases=(
            'squareyard',
            'squareyards',
            'sqyd',
            'yd**2',
            'yd2',
            'yd^2',
        ),
        dimension=Dimension(length=2),
        scale_to_base=0.83612736,
        display='yd2',
        category='area',
        base_canonical='m2',
    ),
    UnitSpec(
        canonical='A',
        aliases=(
            'A',
            'Amperes',
            'Amps',
            'amp',
            'ampere',
            'amperes',
        ),
        dimension=DIM_CURRENT,
        scale_to_base=1.0,
        display='A',
        category='current',
        base_canonical='A',
    ),
    UnitSpec(
        canonical='mA',
        aliases=(
            'mA',
            'milliamp',
            'milliampere',
        ),
        dimension=DIM_CURRENT,
        scale_to_base=0.001,
        display='mA',
        category='current',
        base_canonical='A',
    ),
    UnitSpec(
        canonical='μA',
        aliases=(
            'microamp',
            'microampere',
            'uA',
            'μA',
        ),
        dimension=DIM_CURRENT,
        scale_to_base=1e-06,
        display='μA',
        category='current',
        base_canonical='A',
    ),
    UnitSpec(
        canonical='B',
        aliases=(
            'B',
            'byte',
            'bytes',
        ),
        dimension=DIM_INFORMATION,
        scale_to_base=1.0,
        display='B',
        category='data',
        base_canonical='B',
    ),
    UnitSpec(
        canonical='EB',
        aliases=(
            'EB',
            'exabyte',
            'exabytes',
        ),
        dimension=DIM_INFORMATION,
        scale_to_base=1.152921504606847e18,
        display='EB',
        category='data',
        base_canonical='B',
    ),
    UnitSpec(
        canonical='GB',
        aliases=(
            'GB',
            'gigabyte',
            'gigabytes',
        ),
        dimension=DIM_INFORMATION,
        scale_to_base=1073741824.0,
        display='GB',
        category='data',
        base_canonical='B',
    ),
    UnitSpec(
        canonical='KB',
        aliases=(
            'KB',
            'kilobyte',
            'kilobytes',
        ),
        dimension=DIM_INFORMATION,
        scale_to_base=1024.0,
        display='KB',
        category='data',
        base_canonical='B',
    ),
    UnitSpec(
        canonical='MB',
        aliases=(
            'MB',
            'megabyte',
            'megabytes',
        ),
        dimension=DIM_INFORMATION,
        scale_to_base=1048576.0,
        display='MB',
        category='data',
        base_canonical='B',
    ),
    UnitSpec(
        canonical='PB',
        aliases=(
            'PB',
            'petabyte',
            'petabytes',
        ),
        dimension=DIM_INFORMATION,
        scale_to_base=1125899906842624.0,
        display='PB',
        category='data',
        base_canonical='B',
    ),
    UnitSpec(
        canonical='TB',
        aliases=(
            'TB',
            'terabyte',
            'terabytes',
        ),
        dimension=DIM_INFORMATION,
        scale_to_base=1099511627776.0,
        display='TB',
        category='data',
        base_canonical='B',
    ),
    UnitSpec(
        canonical='YB',
        aliases=(
            'YB',
            'yottabyte',
            'yottabytes',
        ),
        dimension=DIM_INFORMATION,
        scale_to_base=1.2089258196146292e24,
        display='YB',
        category='data',
        base_canonical='B',
    ),
    UnitSpec(
        canonical='ZB',
        aliases=(
            'ZB',
            'zettabyte',
            'zettabytes',
        ),
        dimension=DIM_INFORMATION,
        scale_to_base=1.1805916207174113e21,
        display='ZB',
        category='data',
        base_canonical='B',
    ),
    UnitSpec(
        canonical='bit',
        aliases=(
            'bit',
            'bits',
        ),
        dimension=DIM_INFORMATION,
        scale_to_base=0.125,
        display='bit',
        category='data',
        base_canonical='B',
    ),
    UnitSpec(
        canonical='Gbps',
        aliases=(
            'Gbps',
            'gigabit/s',
            'gigabits/s',
            'gigabps',
        ),
        dimension=Dimension(information=1, time=-1),
        scale_to_base=1000000000.0,
        display='Gbps',
        category='data_rate',
        base_canonical='bps',
    ),
    UnitSpec(
        canonical='Kbps',
        aliases=(
            'Kbps',
            'kilobit/s',
            'kilobits/s',
            'kilobps',
        ),
        dimension=Dimension(information=1, time=-1),
        scale_to_base=1000.0,
        display='Kbps',
        category='data_rate',
        base_canonical='bps',
    ),
    UnitSpec(
        canonical='Mbps',
        aliases=(
            'Mbps',
            'megabit/s',
            'megabits/s',
            'megabps',
        ),
        dimension=Dimension(information=1, time=-1),
        scale_to_base=1000000.0,
        display='Mbps',
        category='data_rate',
        base_canonical='bps',
    ),
    UnitSpec(
        canonical='bps',
        aliases=(
            'bit/s',
            'bits/s',
            'bps',
        ),
        dimension=Dimension(information=1, time=-1),
        scale_to_base=1.0,
        display='bps',
        category='data_rate',
        base_canonical='bps',
    ),
    UnitSpec(
        canonical='BTU',
        aliases=(
            'BTU',
            'btu',
        ),
        dimension=Dimension(mass=1, length=2, time=-2),
        scale_to_base=1055.05585262,
        display='BTU',
        category='energy',
        base_canonical='J',
    ),
    UnitSpec(
        canonical='GJ',
        aliases=(
            'GJ',
            'gigajoule',
            'gigajoules',
        ),
        dimension=Dimension(mass=1, length=2, time=-2),
        scale_to_base=1000000000.0,
        display='GJ',
        category='energy',
        base_canonical='J',
    ),
    UnitSpec(
        canonical='J',
        aliases=(
            'J',
            'Joules',
            'joule',
            'joules',
        ),
        dimension=Dimension(mass=1, length=2, time=-2),
        scale_to_base=1.0,
        display='J',
        category='energy',
        base_canonical='J',
    ),
    UnitSpec(
        canonical='MJ',
        aliases=(
            'MJ',
            'megajoule',
            'megajoules',
        ),
        dimension=Dimension(mass=1, length=2, time=-2),
        scale_to_base=1000000.0,
        display='MJ',
        category='energy',
        base_canonical='J',
    ),
    UnitSpec(
        canonical='Wh',
        aliases=(
            'Wh',
            'watt-hour',
            'watt-hours',
        ),
        dimension=Dimension(mass=1, length=2, time=-2),
        scale_to_base=3600.0,
        display='Wh',
        category='energy',
        base_canonical='J',
    ),
    UnitSpec(
        canonical='cal',
        aliases=(
            'cal',
            'calorie',
            'calories',
        ),
        dimension=Dimension(mass=1, length=2, time=-2),
        scale_to_base=4.184,
        display='cal',
        category='energy',
        base_canonical='J',
    ),
    UnitSpec(
        canonical='eV',
        aliases=(
            'eV',
            'electronvolt',
            'electronvolts',
            'ev',
        ),
        dimension=Dimension(mass=1, length=2, time=-2),
        scale_to_base=1.602176634e-19,
        display='eV',
        category='energy',
        base_canonical='J',
    ),
    UnitSpec(
        canonical='kJ',
        aliases=(
            'kJ',
            'kilojoule',
            'kilojoules',
        ),
        dimension=Dimension(mass=1, length=2, time=-2),
        scale_to_base=1000.0,
        display='kJ',
        category='energy',
        base_canonical='J',
    ),
    UnitSpec(
        canonical='kWh',
        aliases=(
            'kWh',
            'kilowatt-hour',
            'kilowatt-hours',
        ),
        dimension=Dimension(mass=1, length=2, time=-2),
        scale_to_base=3600000.0,
        display='kWh',
        category='energy',
        base_canonical='J',
    ),
    UnitSpec(
        canonical='kcal',
        aliases=(
            'kcal',
            'kilocalorie',
            'kilocalories',
        ),
        dimension=Dimension(mass=1, length=2, time=-2),
        scale_to_base=4184.0,
        display='kcal',
        category='energy',
        base_canonical='J',
    ),
    UnitSpec(
        canonical='N',
        aliases=(
            'N',
            'Newtons',
            'newton',
            'newtons',
        ),
        dimension=Dimension(mass=1, length=1, time=-2),
        scale_to_base=1.0,
        display='N',
        category='force',
        base_canonical='N',
    ),
    UnitSpec(
        canonical='dyne',
        aliases=(
            'dyne',
            'dynes',
        ),
        dimension=Dimension(mass=1, length=1, time=-2),
        scale_to_base=1e-05,
        display='dyne',
        category='force',
        base_canonical='N',
    ),
    UnitSpec(
        canonical='kN',
        aliases=(
            'kN',
            'kilonewton',
        ),
        dimension=Dimension(mass=1, length=1, time=-2),
        scale_to_base=1000.0,
        display='kN',
        category='force',
        base_canonical='N',
    ),
    UnitSpec(
        canonical='lbf',
        aliases=(
            'lbf',
            'poundforce',
        ),
        dimension=Dimension(mass=1, length=1, time=-2),
        scale_to_base=4.4482216152605,
        display='lbf',
        category='force',
        base_canonical='N',
    ),
    UnitSpec(
        canonical='mN',
        aliases=(
            'mN',
            'millinewton',
        ),
        dimension=Dimension(mass=1, length=1, time=-2),
        scale_to_base=0.001,
        display='mN',
        category='force',
        base_canonical='N',
    ),
    UnitSpec(
        canonical='GHz',
        aliases=(
            'GHZ',
            'GHz',
            'gigahertz',
        ),
        dimension=Dimension(time=-1),
        scale_to_base=1000000000.0,
        display='GHz',
        category='frequency',
        base_canonical='Hz',
    ),
    UnitSpec(
        canonical='Hz',
        aliases=(
            'Hz',
            'hertz',
        ),
        dimension=Dimension(time=-1),
        scale_to_base=1.0,
        display='Hz',
        category='frequency',
        base_canonical='Hz',
    ),
    UnitSpec(
        canonical='MHz',
        aliases=(
            'MHZ',
            'MHz',
            'megahertz',
        ),
        dimension=Dimension(time=-1),
        scale_to_base=1000000.0,
        display='MHz',
        category='frequency',
        base_canonical='Hz',
    ),
    UnitSpec(
        canonical='THz',
        aliases=(
            'THz',
            'terahertz',
        ),
        dimension=Dimension(time=-1),
        scale_to_base=1000000000000.0,
        display='THz',
        category='frequency',
        base_canonical='Hz',
    ),
    UnitSpec(
        canonical='kHz',
        aliases=(
            'KHZ',
            'kHz',
            'kilohertz',
        ),
        dimension=Dimension(time=-1),
        scale_to_base=1000.0,
        display='kHz',
        category='frequency',
        base_canonical='Hz',
    ),
    UnitSpec(
        canonical='angstrom',
        aliases=(
            'angstrom',
            'angstroms',
        ),
        dimension=DIM_LENGTH,
        scale_to_base=1e-10,
        display='angstrom',
        category='length',
        base_canonical='m',
    ),
    UnitSpec(
        canonical='au',
        aliases=(
            'astronomicalunit',
            'astronomicalunits',
            'au',
        ),
        dimension=DIM_LENGTH,
        scale_to_base=149597870700.0,
        display='au',
        category='length',
        base_canonical='m',
    ),
    UnitSpec(
        canonical='chain',
        aliases=(
            'chain',
            'chains',
        ),
        dimension=DIM_LENGTH,
        scale_to_base=20.1168,
        display='chain',
        category='length',
        base_canonical='m',
    ),
    UnitSpec(
        canonical='cm',
        aliases=(
            'centimeter',
            'centimeters',
            'centimetre',
            'centimetres',
            'cm',
        ),
        dimension=DIM_LENGTH,
        scale_to_base=0.01,
        display='cm',
        category='length',
        base_canonical='m',
    ),
    UnitSpec(
        canonical='fathom',
        aliases=(
            'fathom',
            'fathoms',
        ),
        dimension=DIM_LENGTH,
        scale_to_base=1.8288,
        display='fathom',
        category='length',
        base_canonical='m',
    ),
    UnitSpec(
        canonical='fermi',
        aliases=('fermi',),
        dimension=DIM_LENGTH,
        scale_to_base=1e-15,
        display='fermi',
        category='length',
        base_canonical='m',
    ),
    UnitSpec(
        canonical='ft',
        aliases=(
            'Feet',
            'feet',
            'foot',
            'ft',
        ),
        dimension=DIM_LENGTH,
        scale_to_base=0.3048,
        display='ft',
        category='length',
        base_canonical='m',
    ),
    UnitSpec(
        canonical='furlong',
        aliases=(
            'furlong',
            'furlongs',
        ),
        dimension=DIM_LENGTH,
        scale_to_base=201.168,
        display='furlong',
        category='length',
        base_canonical='m',
    ),
    UnitSpec(
        canonical='inch',
        aliases=(
            'Inches',
            'in',
            'inch',
            'inches',
        ),
        dimension=DIM_LENGTH,
        scale_to_base=0.0254,
        display='inch',
        category='length',
        base_canonical='m',
    ),
    UnitSpec(
        canonical='km',
        aliases=(
            'KM',
            'kilometer',
            'kilometers',
            'kilometre',
            'kilometres',
            'km',
        ),
        dimension=DIM_LENGTH,
        scale_to_base=1000.0,
        display='km',
        category='length',
        base_canonical='m',
    ),
    UnitSpec(
        canonical='ly',
        aliases=(
            'lightyear',
            'lightyears',
            'ly',
        ),
        dimension=DIM_LENGTH,
        scale_to_base=9460730472580800.0,
        display='ly',
        category='length',
        base_canonical='m',
    ),
    UnitSpec(
        canonical='m',
        aliases=(
            'Meters',
            'm',
            'meter',
            'meters',
            'metre',
            'metres',
        ),
        dimension=DIM_LENGTH,
        scale_to_base=1.0,
        display='m',
        category='length',
        base_canonical='m',
    ),
    UnitSpec(
        canonical='mi',
        aliases=(
            'Miles',
            'mi',
            'mile',
            'miles',
        ),
        dimension=DIM_LENGTH,
        scale_to_base=1609.344,
        display='mi',
        category='length',
        base_canonical='m',
    ),
    UnitSpec(
        canonical='mm',
        aliases=(
            'millimeter',
            'millimeters',
            'millimetre',
            'millimetres',
            'mm',
        ),
        dimension=DIM_LENGTH,
        scale_to_base=0.001,
        display='mm',
        category='length',
        base_canonical='m',
    ),
    UnitSpec(
        canonical='nm',
        aliases=(
            'nanometer',
            'nanometers',
            'nm',
        ),
        dimension=DIM_LENGTH,
        scale_to_base=1e-09,
        display='nm',
        category='length',
        base_canonical='m',
    ),
    UnitSpec(
        canonical='nmi',
        aliases=(
            'nauticalmile',
            'nauticalmiles',
            'nmi',
        ),
        dimension=DIM_LENGTH,
        scale_to_base=1852.0,
        display='nmi',
        category='length',
        base_canonical='m',
    ),
    UnitSpec(
        canonical='pc',
        aliases=(
            'parsec',
            'parsecs',
            'pc',
        ),
        dimension=DIM_LENGTH,
        scale_to_base=3.085677581491367e16,
        display='pc',
        category='length',
        base_canonical='m',
    ),
    UnitSpec(
        canonical='pm',
        aliases=(
            'picometer',
            'picometers',
            'pm',
        ),
        dimension=DIM_LENGTH,
        scale_to_base=1e-12,
        display='pm',
        category='length',
        base_canonical='m',
    ),
    UnitSpec(
        canonical='rd',
        aliases=(
            'rd',
            'rod',
            'rods',
        ),
        dimension=DIM_LENGTH,
        scale_to_base=5.0292,
        display='rd',
        category='length',
        base_canonical='m',
    ),
    UnitSpec(
        canonical='smoot',
        aliases=(
            'smoot',
            'smoots',
        ),
        dimension=DIM_LENGTH,
        scale_to_base=1.7018,
        display='smoot',
        category='length',
        base_canonical='m',
    ),
    UnitSpec(
        canonical='um',
        aliases=(
            'micrometer',
            'micrometers',
            'um',
            'μm',
        ),
        dimension=DIM_LENGTH,
        scale_to_base=1e-06,
        display='um',
        category='length',
        base_canonical='m',
    ),
    UnitSpec(
        canonical='yd',
        aliases=(
            'yard',
            'yards',
            'yd',
        ),
        dimension=DIM_LENGTH,
        scale_to_base=0.9144,
        display='yd',
        category='length',
        base_canonical='m',
    ),
    UnitSpec(
        canonical='ct',
        aliases=(
            'carat',
            'carats',
            'ct',
        ),
        dimension=DIM_MASS,
        scale_to_base=0.0002,
        display='ct',
        category='mass',
        base_canonical='kg',
    ),
    UnitSpec(
        canonical='dr',
        aliases=(
            'dr',
            'dram',
            'drams',
        ),
        dimension=DIM_MASS,
        scale_to_base=0.0017718452,
        display='dr',
        category='mass',
        base_canonical='kg',
    ),
    UnitSpec(
        canonical='g',
        aliases=(
            'Grams',
            'g',
            'gram',
            'grams',
        ),
        dimension=DIM_MASS,
        scale_to_base=0.001,
        display='g',
        category='mass',
        base_canonical='kg',
    ),
    UnitSpec(
        canonical='gr',
        aliases=(
            'gr',
            'grain',
            'grains',
        ),
        dimension=DIM_MASS,
        scale_to_base=6.479891e-05,
        display='gr',
        category='mass',
        base_canonical='kg',
    ),
    UnitSpec(
        canonical='kg',
        aliases=(
            'KG',
            'Kilograms',
            'kg',
            'kilogram',
            'kilograms',
        ),
        dimension=DIM_MASS,
        scale_to_base=1.0,
        display='kg',
        category='mass',
        base_canonical='kg',
    ),
    UnitSpec(
        canonical='lb',
        aliases=(
            'Pounds',
            'lb',
            'lbs',
            'pound',
            'pounds',
        ),
        dimension=DIM_MASS,
        scale_to_base=0.45359237,
        display='lb',
        category='mass',
        base_canonical='kg',
    ),
    UnitSpec(
        canonical='long_ton',
        aliases=(
            'imperial_ton',
            'long_ton',
        ),
        dimension=DIM_MASS,
        scale_to_base=1016.0469,
        display='long_ton',
        category='mass',
        base_canonical='kg',
    ),
    UnitSpec(
        canonical='mg',
        aliases=(
            'mg',
            'milligram',
            'milligrams',
        ),
        dimension=DIM_MASS,
        scale_to_base=1e-06,
        display='mg',
        category='mass',
        base_canonical='kg',
    ),
    UnitSpec(
        canonical='ng',
        aliases=(
            'nanogram',
            'nanograms',
            'ng',
        ),
        dimension=DIM_MASS,
        scale_to_base=1e-12,
        display='ng',
        category='mass',
        base_canonical='kg',
    ),
    UnitSpec(
        canonical='oz',
        aliases=(
            'Ounces',
            'ounce',
            'ounces',
            'oz',
        ),
        dimension=DIM_MASS,
        scale_to_base=0.028349523125,
        display='oz',
        category='mass',
        base_canonical='kg',
    ),
    UnitSpec(
        canonical='slug',
        aliases=(
            'slug',
            'slugs',
        ),
        dimension=DIM_MASS,
        scale_to_base=14.593903,
        display='slug',
        category='mass',
        base_canonical='kg',
    ),
    UnitSpec(
        canonical='stone',
        aliases=(
            'st',
            'stone',
            'stones',
        ),
        dimension=DIM_MASS,
        scale_to_base=6.35029318,
        display='stone',
        category='mass',
        base_canonical='kg',
    ),
    UnitSpec(
        canonical='ton',
        aliases=(
            'ton',
            'tons',
        ),
        dimension=DIM_MASS,
        scale_to_base=907.18474,
        display='ton',
        category='mass',
        base_canonical='kg',
    ),
    UnitSpec(
        canonical='tonne',
        aliases=(
            'tonne',
            'tonnes',
        ),
        dimension=DIM_MASS,
        scale_to_base=1000.0,
        display='tonne',
        category='mass',
        base_canonical='kg',
    ),
    UnitSpec(
        canonical='ug',
        aliases=(
            'microgram',
            'micrograms',
            'ug',
            'μg',
        ),
        dimension=DIM_MASS,
        scale_to_base=1e-09,
        display='ug',
        category='mass',
        base_canonical='kg',
    ),
    UnitSpec(
        canonical='GW',
        aliases=(
            'GW',
            'gigawatt',
            'gigawatts',
        ),
        dimension=Dimension(mass=1, length=2, time=-3),
        scale_to_base=1000000000.0,
        display='GW',
        category='power',
        base_canonical='W',
    ),
    UnitSpec(
        canonical='MW',
        aliases=(
            'MW',
            'megawatt',
            'megawatts',
        ),
        dimension=Dimension(mass=1, length=2, time=-3),
        scale_to_base=1000000.0,
        display='MW',
        category='power',
        base_canonical='W',
    ),
    UnitSpec(
        canonical='W',
        aliases=(
            'W',
            'Watts',
            'watt',
            'watts',
        ),
        dimension=Dimension(mass=1, length=2, time=-3),
        scale_to_base=1.0,
        display='W',
        category='power',
        base_canonical='W',
    ),
    UnitSpec(
        canonical='hp',
        aliases=(
            'horsepower',
            'hp',
        ),
        dimension=Dimension(mass=1, length=2, time=-3),
        scale_to_base=745.6998715822702,
        display='hp',
        category='power',
        base_canonical='W',
    ),
    UnitSpec(
        canonical='kW',
        aliases=(
            'kW',
            'kilowatt',
            'kilowatts',
        ),
        dimension=Dimension(mass=1, length=2, time=-3),
        scale_to_base=1000.0,
        display='kW',
        category='power',
        base_canonical='W',
    ),
    UnitSpec(
        canonical='mW',
        aliases=(
            'mW',
            'milliwatt',
            'milliwatts',
        ),
        dimension=Dimension(mass=1, length=2, time=-3),
        scale_to_base=0.001,
        display='mW',
        category='power',
        base_canonical='W',
    ),
    UnitSpec(
        canonical='GPa',
        aliases=(
            'GPa',
            'gigapascal',
            'gigapascals',
        ),
        dimension=Dimension(mass=1, length=-1, time=-2),
        scale_to_base=1000000000.0,
        display='GPa',
        category='pressure',
        base_canonical='Pa',
    ),
    UnitSpec(
        canonical='MPa',
        aliases=(
            'MPa',
            'megapascal',
            'megapascals',
        ),
        dimension=Dimension(mass=1, length=-1, time=-2),
        scale_to_base=1000000.0,
        display='MPa',
        category='pressure',
        base_canonical='Pa',
    ),
    UnitSpec(
        canonical='Pa',
        aliases=(
            'Pa',
            'Pascals',
            'pascal',
            'pascals',
        ),
        dimension=Dimension(mass=1, length=-1, time=-2),
        scale_to_base=1.0,
        display='Pa',
        category='pressure',
        base_canonical='Pa',
    ),
    UnitSpec(
        canonical='atm',
        aliases=(
            'atm',
            'atmosphere',
            'atmospheres',
        ),
        dimension=Dimension(mass=1, length=-1, time=-2),
        scale_to_base=101325.0,
        display='atm',
        category='pressure',
        base_canonical='Pa',
    ),
    UnitSpec(
        canonical='bar',
        aliases=(
            'bar',
            'bars',
        ),
        dimension=Dimension(mass=1, length=-1, time=-2),
        scale_to_base=100000.0,
        display='bar',
        category='pressure',
        base_canonical='Pa',
    ),
    UnitSpec(
        canonical='inH2O',
        aliases=('inH2O',),
        dimension=Dimension(mass=1, length=-1, time=-2),
        scale_to_base=249.08891,
        display='inH2O',
        category='pressure',
        base_canonical='Pa',
    ),
    UnitSpec(
        canonical='inHg',
        aliases=('inHg',),
        dimension=Dimension(mass=1, length=-1, time=-2),
        scale_to_base=3386.389,
        display='inHg',
        category='pressure',
        base_canonical='Pa',
    ),
    UnitSpec(
        canonical='kPa',
        aliases=(
            'kPa',
            'kilopascal',
            'kilopascals',
        ),
        dimension=Dimension(mass=1, length=-1, time=-2),
        scale_to_base=1000.0,
        display='kPa',
        category='pressure',
        base_canonical='Pa',
    ),
    UnitSpec(
        canonical='mbar',
        aliases=(
            'mbar',
            'millibar',
        ),
        dimension=Dimension(mass=1, length=-1, time=-2),
        scale_to_base=100.0,
        display='mbar',
        category='pressure',
        base_canonical='Pa',
    ),
    UnitSpec(
        canonical='mmH2O',
        aliases=('mmH2O',),
        dimension=Dimension(mass=1, length=-1, time=-2),
        scale_to_base=9.80665,
        display='mmH2O',
        category='pressure',
        base_canonical='Pa',
    ),
    UnitSpec(
        canonical='mmHg',
        aliases=('mmHg',),
        dimension=Dimension(mass=1, length=-1, time=-2),
        scale_to_base=133.32236842105,
        display='mmHg',
        category='pressure',
        base_canonical='Pa',
    ),
    UnitSpec(
        canonical='psi',
        aliases=(
            'psi',
            'psia',
        ),
        dimension=Dimension(mass=1, length=-1, time=-2),
        scale_to_base=6894.757293168,
        display='psi',
        category='pressure',
        base_canonical='Pa',
    ),
    UnitSpec(
        canonical='torr',
        aliases=('torr',),
        dimension=Dimension(mass=1, length=-1, time=-2),
        scale_to_base=133.32236842105,
        display='torr',
        category='pressure',
        base_canonical='Pa',
    ),
    UnitSpec(
        canonical='km/h',
        aliases=(
            'kilometerperhour',
            'kilometersperhour',
            'km/h',
            'kmh',
            'kph',
        ),
        dimension=Dimension(length=1, time=-1),
        scale_to_base=0.2777777777777778,
        display='km/h',
        category='speed',
        base_canonical='m/s',
    ),
    UnitSpec(
        canonical='kn',
        aliases=(
            'kn',
            'knot',
            'knots',
            'kt',
        ),
        dimension=Dimension(length=1, time=-1),
        scale_to_base=0.5144444444444445,
        display='kn',
        category='speed',
        base_canonical='m/s',
    ),
    UnitSpec(
        canonical='m/s',
        aliases=(
            'm/s',
            'meterpersecond',
            'meterspersecond',
            'mps',
        ),
        dimension=Dimension(length=1, time=-1),
        scale_to_base=1.0,
        display='m/s',
        category='speed',
        base_canonical='m/s',
    ),
    UnitSpec(
        canonical='mach',
        aliases=('mach',),
        dimension=Dimension(length=1, time=-1),
        scale_to_base=340.29,
        display='mach',
        category='speed',
        base_canonical='m/s',
    ),
    UnitSpec(
        canonical='mph',
        aliases=(
            'mi/h',
            'mileperhour',
            'milesperhour',
            'mph',
        ),
        dimension=Dimension(length=1, time=-1),
        scale_to_base=0.44704,
        display='mph',
        category='speed',
        base_canonical='m/s',
    ),
    UnitSpec(
        canonical='century',
        aliases=(
            'centuries',
            'century',
        ),
        dimension=DIM_TIME,
        scale_to_base=3153600000.0,
        display='century',
        category='time',
        base_canonical='s',
    ),
    UnitSpec(
        canonical='d',
        aliases=(
            'd',
            'day',
            'days',
        ),
        dimension=DIM_TIME,
        scale_to_base=86400.0,
        display='d',
        category='time',
        base_canonical='s',
    ),
    UnitSpec(
        canonical='decade',
        aliases=(
            'decade',
            'decades',
        ),
        dimension=DIM_TIME,
        scale_to_base=315360000.0,
        display='decade',
        category='time',
        base_canonical='s',
    ),
    UnitSpec(
        canonical='fortnight',
        aliases=(
            'fortnight',
            'fortnights',
        ),
        dimension=DIM_TIME,
        scale_to_base=1209600.0,
        display='fortnight',
        category='time',
        base_canonical='s',
    ),
    UnitSpec(
        canonical='h',
        aliases=(
            'Hours',
            'h',
            'hour',
            'hours',
            'hr',
        ),
        dimension=DIM_TIME,
        scale_to_base=3600.0,
        display='h',
        category='time',
        base_canonical='s',
    ),
    UnitSpec(
        canonical='millennium',
        aliases=(
            'millennia',
            'millennium',
        ),
        dimension=DIM_TIME,
        scale_to_base=31536000000.0,
        display='millennium',
        category='time',
        base_canonical='s',
    ),
    UnitSpec(
        canonical='min',
        aliases=(
            'Minutes',
            'min',
            'minute',
            'minutes',
        ),
        dimension=DIM_TIME,
        scale_to_base=60.0,
        display='min',
        category='time',
        base_canonical='s',
    ),
    UnitSpec(
        canonical='ms',
        aliases=(
            'millisecond',
            'milliseconds',
            'ms',
        ),
        dimension=DIM_TIME,
        scale_to_base=0.001,
        display='ms',
        category='time',
        base_canonical='s',
    ),
    UnitSpec(
        canonical='ns',
        aliases=(
            'nanosecond',
            'nanoseconds',
            'ns',
        ),
        dimension=DIM_TIME,
        scale_to_base=1e-09,
        display='ns',
        category='time',
        base_canonical='s',
    ),
    UnitSpec(
        canonical='ps',
        aliases=(
            'picosecond',
            'picoseconds',
            'ps',
        ),
        dimension=DIM_TIME,
        scale_to_base=1e-12,
        display='ps',
        category='time',
        base_canonical='s',
    ),
    UnitSpec(
        canonical='s',
        aliases=(
            'Seconds',
            's',
            'sec',
            'second',
            'seconds',
            'secs',
        ),
        dimension=DIM_TIME,
        scale_to_base=1.0,
        display='s',
        category='time',
        base_canonical='s',
    ),
    UnitSpec(
        canonical='us',
        aliases=(
            'microsecond',
            'microseconds',
            'us',
            'μs',
        ),
        dimension=DIM_TIME,
        scale_to_base=1e-06,
        display='us',
        category='time',
        base_canonical='s',
    ),
    UnitSpec(
        canonical='wk',
        aliases=(
            'week',
            'weeks',
            'wk',
        ),
        dimension=DIM_TIME,
        scale_to_base=604800.0,
        display='wk',
        category='time',
        base_canonical='s',
    ),
    UnitSpec(
        canonical='yr',
        aliases=(
            'year',
            'years',
            'yr',
        ),
        dimension=DIM_TIME,
        scale_to_base=31536000.0,
        display='yr',
        category='time',
        base_canonical='s',
    ),
    UnitSpec(
        canonical='V',
        aliases=(
            'V',
            'Volts',
            'volt',
            'volts',
        ),
        dimension=Dimension(mass=1, length=2, time=-3, current=-1),
        scale_to_base=1.0,
        display='V',
        category='voltage',
        base_canonical='V',
    ),
    UnitSpec(
        canonical='kV',
        aliases=(
            'kV',
            'kilovolt',
        ),
        dimension=Dimension(mass=1, length=2, time=-3, current=-1),
        scale_to_base=1000.0,
        display='kV',
        category='voltage',
        base_canonical='V',
    ),
    UnitSpec(
        canonical='mV',
        aliases=(
            'mV',
            'millivolt',
        ),
        dimension=Dimension(mass=1, length=2, time=-3, current=-1),
        scale_to_base=0.001,
        display='mV',
        category='voltage',
        base_canonical='V',
    ),
    UnitSpec(
        canonical='μV',
        aliases=(
            'microvolt',
            'uV',
            'μV',
        ),
        dimension=Dimension(mass=1, length=2, time=-3, current=-1),
        scale_to_base=1e-06,
        display='μV',
        category='voltage',
        base_canonical='V',
    ),
    UnitSpec(
        canonical='L',
        aliases=(
            'L',
            'Liters',
            'l',
            'liter',
            'liters',
            'litre',
            'litres',
        ),
        dimension=Dimension(length=3),
        scale_to_base=1.0,
        display='L',
        category='volume',
        base_canonical='L',
    ),
    UnitSpec(
        canonical='cm3',
        aliases=(
            'cc',
            'cm**3',
            'cm3',
            'cm^3',
            'cubiccentimeter',
            'cubiccentimeters',
        ),
        dimension=Dimension(length=3),
        scale_to_base=0.001,
        display='cm3',
        category='volume',
        base_canonical='L',
    ),
    UnitSpec(
        canonical='cup',
        aliases=(
            'cup',
            'cups',
        ),
        dimension=Dimension(length=3),
        scale_to_base=0.2365882365,
        display='cup',
        category='volume',
        base_canonical='L',
    ),
    UnitSpec(
        canonical='floz',
        aliases=(
            'fl oz',
            'floz',
            'fluidounce',
            'fluidounces',
        ),
        dimension=Dimension(length=3),
        scale_to_base=0.02957352954,
        display='floz',
        category='volume',
        base_canonical='L',
    ),
    UnitSpec(
        canonical='ft3',
        aliases=(
            'cubicfeet',
            'cubicfoot',
            'ft**3',
            'ft3',
            'ft^3',
        ),
        dimension=Dimension(length=3),
        scale_to_base=28.316846592,
        display='ft3',
        category='volume',
        base_canonical='L',
    ),
    UnitSpec(
        canonical='gal',
        aliases=(
            'gal',
            'gallon',
            'gallons',
        ),
        dimension=Dimension(length=3),
        scale_to_base=3.785411784,
        display='gal',
        category='volume',
        base_canonical='L',
    ),
    UnitSpec(
        canonical='in3',
        aliases=(
            'cubicinch',
            'cubicinches',
            'in**3',
            'in3',
            'in^3',
        ),
        dimension=Dimension(length=3),
        scale_to_base=0.016387064,
        display='in3',
        category='volume',
        base_canonical='L',
    ),
    UnitSpec(
        canonical='km3',
        aliases=(
            'cubickilometer',
            'cubickilometers',
            'km**3',
            'km3',
            'km^3',
        ),
        dimension=Dimension(length=3),
        scale_to_base=1000000000000.0,
        display='km3',
        category='volume',
        base_canonical='L',
    ),
    UnitSpec(
        canonical='m3',
        aliases=(
            'cubicmeter',
            'cubicmeters',
            'm**3',
            'm3',
            'm^3',
        ),
        dimension=Dimension(length=3),
        scale_to_base=1000.0,
        display='m3',
        category='volume',
        base_canonical='L',
    ),
    UnitSpec(
        canonical='mL',
        aliases=(
            'mL',
            'milliliter',
            'milliliters',
            'millilitre',
            'millilitres',
        ),
        dimension=Dimension(length=3),
        scale_to_base=0.001,
        display='mL',
        category='volume',
        base_canonical='L',
    ),
    UnitSpec(
        canonical='mi3',
        aliases=(
            'cubicmile',
            'cubicmiles',
            'mi**3',
            'mi3',
            'mi^3',
        ),
        dimension=Dimension(length=3),
        scale_to_base=4168181825000.0,
        display='mi3',
        category='volume',
        base_canonical='L',
    ),
    UnitSpec(
        canonical='mm3',
        aliases=(
            'cubicmillimeter',
            'cubicmillimeters',
            'mm**3',
            'mm3',
            'mm^3',
        ),
        dimension=Dimension(length=3),
        scale_to_base=1e-06,
        display='mm3',
        category='volume',
        base_canonical='L',
    ),
    UnitSpec(
        canonical='pt',
        aliases=(
            'pint',
            'pints',
            'pt',
        ),
        dimension=Dimension(length=3),
        scale_to_base=0.473176473,
        display='pt',
        category='volume',
        base_canonical='L',
    ),
    UnitSpec(
        canonical='qt',
        aliases=(
            'qt',
            'quart',
            'quarts',
        ),
        dimension=Dimension(length=3),
        scale_to_base=0.946352946,
        display='qt',
        category='volume',
        base_canonical='L',
    ),
    UnitSpec(
        canonical='tbsp',
        aliases=(
            'tablespoon',
            'tablespoons',
            'tbsp',
        ),
        dimension=Dimension(length=3),
        scale_to_base=0.01478676477,
        display='tbsp',
        category='volume',
        base_canonical='L',
    ),
    UnitSpec(
        canonical='tsp',
        aliases=(
            'teaspoon',
            'teaspoons',
            'tsp',
        ),
        dimension=Dimension(length=3),
        scale_to_base=0.00492892159,
        display='tsp',
        category='volume',
        base_canonical='L',
    ),
    UnitSpec(
        canonical='uL',
        aliases=(
            'microliter',
            'microliters',
            'uL',
            'μL',
        ),
        dimension=Dimension(length=3),
        scale_to_base=1e-06,
        display='uL',
        category='volume',
        base_canonical='L',
    ),
    UnitSpec(
        canonical='yd3',
        aliases=(
            'cubicyard',
            'cubicyards',
            'yd**3',
            'yd3',
            'yd^3',
        ),
        dimension=Dimension(length=3),
        scale_to_base=764.554857984,
        display='yd3',
        category='volume',
        base_canonical='L',
    ),
    UnitSpec(
        canonical='K',
        aliases=(
            'K',
            'Kelvin',
            'degk',
            'kelvin',
            'kelvins',
            '°K',
        ),
        dimension=DIM_TEMPERATURE,
        scale_to_base=1.0,
        affine=True,
        display='K',
        category="temperature",
        base_canonical='K',
    ),
    UnitSpec(
        canonical='C',
        aliases=(
            'C',
            'Celsius',
            'celsius',
            'centigrade',
            'degc',
            '°C',
        ),
        dimension=DIM_TEMPERATURE,
        scale_to_base=1.0,
        offset_to_base=273.15,
        affine=True,
        display='C',
        category="temperature",
        base_canonical='K',
    ),
    UnitSpec(
        canonical='F',
        aliases=(
            'F',
            'Fahrenheit',
            'degf',
            'fahrenheit',
            '°F',
        ),
        dimension=DIM_TEMPERATURE,
        scale_to_base=5.0 / 9.0,
        offset_to_base=255.3722222222222,
        affine=True,
        display='F',
        category="temperature",
        base_canonical='K',
    ),
    UnitSpec(
        canonical='Ra',
        aliases=(
            'Ra',
            'degr',
            'rankine',
            '°R',
        ),
        dimension=DIM_TEMPERATURE,
        scale_to_base=5.0 / 9.0,
        offset_to_base=0.0,
        affine=True,
        display='Ra',
        category="temperature",
        base_canonical='K',
    ),
)


def _validate_unit_definitions(defs: tuple[UnitSpec, ...]) -> None:
    supported_categories = frozenset(
        {
            "length",
            "area",
            "time",
            "data",
            "data_rate",
            "mass",
            "volume",
            "pressure",
            "energy",
            "power",
            "force",
            "voltage",
            "current",
            "angle",
            "speed",
            "frequency",
            "temperature",
        }
    )
    canonicals: dict[str, UnitSpec] = {}
    all_aliases: dict[str, tuple[str, UnitSpec]] = {}
    for spec in defs:
        if not spec.canonical:
            raise ValueError("Empty canonical name")
        if spec.canonical in canonicals:
            raise ValueError(f"Duplicate canonical: {spec.canonical}")
        if not spec.category or spec.category not in supported_categories:
            raise ValueError(f"Unsupported or empty category for {spec.canonical!r}")
        if not spec.base_canonical:
            raise ValueError(f"Empty base canonical for {spec.canonical!r}")
        if not isinstance(spec.dimension, Dimension):
            raise ValueError(f"Unsupported dimension type for {spec.canonical!r}")
        if any(
            not isinstance(value, int) for value in spec.dimension._tuple()[:-1]
        ) or not isinstance(spec.dimension.angle, bool):
            raise ValueError(f"Unsupported dimension exponents for {spec.canonical!r}")
        if not math.isfinite(spec.scale_to_base) or spec.scale_to_base == 0:
            raise ValueError(f"Scale must be finite and non-zero for {spec.canonical!r}")
        if not math.isfinite(spec.offset_to_base):
            raise ValueError(f"Offset must be finite for {spec.canonical!r}")
        if spec.affine and spec.dimension != DIM_TEMPERATURE:
            raise ValueError(
                f"Affine unit must have pure temperature dimension: {spec.canonical!r}"
            )
        if spec.display is not None and (not spec.display or "%" in spec.display):
            raise ValueError(f"Invalid display token for {spec.canonical!r}")
        if spec.affine and (
            any(token in spec.canonical for token in ("*", "/", "%"))
            or any(token in alias for alias in spec.aliases for token in ("*", "/", "%"))
        ):
            raise ValueError(f"Affine unit cannot be compound: {spec.canonical!r}")
        if spec.canonical not in spec.aliases:
            raise ValueError(f"Canonical {spec.canonical!r} is missing from its aliases")
        canonicals[spec.canonical] = spec
        for alias in spec.aliases:
            if not alias:
                raise ValueError(f"Empty alias in {spec.canonical}")
            if alias in all_aliases:
                existing_alias, existing_spec = all_aliases[alias]
                raise ValueError(
                    f"Duplicate alias {alias!r}: {existing_alias!r} and {spec.canonical!r}"
                )
            all_aliases[alias] = (alias, spec)

    canonical_names = set(canonicals)
    normalized_aliases: dict[str, tuple[str, str]] = {}
    for alias, (_, spec) in all_aliases.items():
        key = alias.casefold()
        previous = normalized_aliases.get(key)
        if (
            previous is not None
            and previous[0] != alias
            and previous[1] != spec.canonical
            and previous[0] not in canonical_names
            and alias not in canonical_names
        ):
            raise ValueError(
                f"Normalized alias collision: {previous[0]!r} ({previous[1]!r}) "
                f"and {alias!r} ({spec.canonical!r})"
            )
        normalized_aliases[key] = (alias, spec.canonical)
        if alias in canonical_names and alias != spec.canonical:
            raise ValueError(
                f"Alias {alias!r} collides with canonical {alias!r} " f"from {spec.canonical!r}"
            )

    for spec in defs:
        base = canonicals.get(spec.base_canonical)
        if base is None:
            raise ValueError(
                f"Base canonical {spec.base_canonical!r} for {spec.canonical!r} is not declared"
            )
        if base.category != spec.category or base.dimension != spec.dimension:
            raise ValueError(
                f"Base canonical {spec.base_canonical!r} conflicts with {spec.canonical!r} "
                f"category/dimension"
            )
        if spec.canonical == spec.base_canonical and not spec.affine:
            if spec.scale_to_base != 1.0 or spec.offset_to_base != 0.0:
                raise ValueError(f"Non-unit scale for family base {spec.canonical!r}")


_validate_unit_definitions(UNIT_DEFINITIONS)


# ---------------------------------------------------------------------------
# Structural UnitExpression and bounded parser
# ---------------------------------------------------------------------------

MAX_ABS_UNIT_EXPONENT = 16
MAX_EXPONENT_DIGITS = 3
MAX_CANONICAL_UNIT_LENGTH = 256
MAX_UNIT_ERROR_LENGTH = 512


def _unit_error(message: str) -> ValueError:
    return ValueError(message[:MAX_UNIT_ERROR_LENGTH])


@dataclass(frozen=True)
class UnitExpression:
    """Immutable, self-validating structural representation of a unit."""

    factors: tuple[tuple[str, int], ...]
    dimension: Dimension
    scale_to_base: float

    def __post_init__(self) -> None:
        registry = _get_unit_registry()
        if registry is None:
            raise _unit_error("Unit registry is unavailable")
        combined: dict[str, int] = {}
        for canonical, exponent in self.factors:
            if not isinstance(canonical, str) or not canonical:
                raise _unit_error("Unit expression factors must use canonical names")
            if not isinstance(exponent, int) or isinstance(exponent, bool):
                raise _unit_error(f"Invalid exponent for {canonical!r}")
            if abs(exponent) > MAX_ABS_UNIT_EXPONENT:
                raise _unit_error(f"Exponent exceeds {MAX_ABS_UNIT_EXPONENT}")
            definition = registry.by_canonical(canonical)
            if definition is None:
                raise _unit_error(f"Unknown canonical unit: {canonical!r}")
            combined[canonical] = combined.get(canonical, 0) + exponent

        combined = {name: exponent for name, exponent in combined.items() if exponent}
        if len(combined) > MAX_COMPOUND_ATOMS:
            raise _unit_error(f"Unit expression exceeds {MAX_COMPOUND_ATOMS} factors")
        normalized = tuple(sorted(combined.items()))
        expected_dimension = DIM_DIMENSIONLESS
        expected_scale = 1.0
        affine_factors = []
        for canonical, exponent in normalized:
            definition = registry.by_canonical(canonical)
            assert definition is not None
            if definition.affine:
                affine_factors.append((definition, exponent))
            expected_dimension = expected_dimension * (definition.dimension**exponent)
            try:
                expected_scale *= definition.scale**exponent
            except (OverflowError, ValueError) as exc:
                raise _unit_error("Unit expression scale overflow") from exc
            if not math.isfinite(expected_scale) or expected_scale == 0:
                raise _unit_error("Unit expression scale is not finite and non-zero")
        if affine_factors and (len(normalized) != 1 or affine_factors[0][1] != 1):
            raise _unit_error("Affine units may only be standalone exponent-one units")
        if expected_dimension != self.dimension:
            raise _unit_error("Unit expression dimension does not match its factors")
        if not math.isfinite(self.scale_to_base) or self.scale_to_base == 0:
            raise _unit_error("Unit expression scale is not finite and non-zero")
        if not math.isclose(self.scale_to_base, expected_scale, rel_tol=1e-12, abs_tol=1e-15):
            raise _unit_error("Unit expression scale does not match its factors")
        # Validate canonical rendering without recursive construction.
        # render_expression raises on overflow; None is returned only for
        # the fully dimensionless (empty) case which is always valid.
        render_expression(_UncheckedUnitExpression(normalized, expected_dimension, expected_scale))
        object.__setattr__(self, "factors", normalized)
        object.__setattr__(self, "dimension", expected_dimension)
        object.__setattr__(self, "scale_to_base", expected_scale)

    def __reduce__(self) -> tuple[type[UnitExpression], tuple[object, ...]]:
        """Support multiprocessing transport for timeout evaluation results."""
        return type(self), (self.factors, self.dimension, self.scale_to_base)


class _UncheckedUnitExpression:
    """Internal render-only expression that avoids recursive validation."""

    def __init__(self, factors: tuple[tuple[str, int], ...], dimension: Dimension, scale: float):
        self.factors = factors
        self.dimension = dimension
        self.scale_to_base = scale


def _resolve_atom(unit_str: str) -> tuple[str, Dimension, float, bool] | None:
    registry = _get_unit_registry()
    if registry is None:
        return None
    candidates = (
        unit_str,
        unit_str.lower(),
        unit_str.upper(),
        unit_str.title(),
        unit_str.capitalize(),
    )
    for candidate in candidates:
        definition = registry.by_alias(candidate) or registry.by_canonical(candidate)
        if definition is not None:
            return definition.canonical, definition.dimension, definition.scale, definition.affine
    return None


def _registered_direct_unit(unit_str: str) -> UnitExpression | None:
    resolved = _resolve_atom(unit_str)
    if resolved is None:
        return None
    canonical, dimension, scale, affine = resolved
    return UnitExpression(((canonical, 1),), dimension, scale)


def parse_unit_expression(unit_str: str) -> UnitExpression:
    """Parse one bounded product/division unit expression."""
    if not isinstance(unit_str, str) or not unit_str:
        raise _unit_error("Empty unit string")
    if len(unit_str) > MAX_UNIT_STRING_LENGTH:
        raise _unit_error(f"Unit string exceeds {MAX_UNIT_STRING_LENGTH} characters")
    if "//" in unit_str or "%" in unit_str:
        raise _unit_error("Unit separators '//' and '%' are not allowed")
    leading_dimensionless = unit_str.startswith("1/")
    parse_text = unit_str[2:] if leading_dimensionless else unit_str
    if not parse_text:
        raise _unit_error("Unit expression is missing a denominator")
    direct_definition = _lookup_definition(unit_str)
    if (
        direct_definition is not None
        and not direct_definition.affine
        and "/" not in direct_definition.canonical
        and "*" not in direct_definition.canonical
    ):
        power_alias = re.fullmatch(r"([^*/]+)\*\*([+-]?\d+)", unit_str)
        if power_alias is not None:
            base_definition = _lookup_definition(power_alias.group(1))
            exponent = int(power_alias.group(2))
            if base_definition is not None and abs(exponent) <= MAX_ABS_UNIT_EXPONENT:
                try:
                    expected_scale = base_definition.scale**exponent
                except (OverflowError, ValueError) as exc:
                    raise _unit_error("Unit expression scale overflow") from exc
                if not math.isfinite(expected_scale) or expected_scale == 0:
                    raise _unit_error("Unit expression scale is not finite and non-zero")
                expected_dimension = base_definition.dimension**exponent
                if expected_dimension == direct_definition.dimension and math.isclose(
                    expected_scale,
                    direct_definition.scale,
                    rel_tol=1e-12,
                    abs_tol=1e-15,
                ):
                    return UnitExpression(
                        ((base_definition.canonical, exponent),),
                        expected_dimension,
                        expected_scale,
                    )
        return UnitExpression(
            ((direct_definition.canonical, 1),),
            direct_definition.dimension,
            direct_definition.scale,
        )
    if "^" in unit_str:
        direct = _registered_direct_unit(unit_str)
        if direct is not None:
            return direct
        raise _unit_error(f"Cannot parse unit expression: {unit_str!r}")

    registry = _get_unit_registry()
    if registry is None:
        raise _unit_error("Unit registry is unavailable")

    factors: dict[str, int] = {}
    dimension = DIM_DIMENSIONLESS
    scale = 1.0
    atom_count = 0
    # The grammar has no parenthesized recursion; a product/division has one
    # structural level.  Keep the explicit bound for future grammar growth.
    depth = 1
    position = 0
    denominator = leading_dimensionless
    unit_str = parse_text

    while position < len(unit_str):
        if unit_str[position] in "*/":
            raise _unit_error(f"Unexpected operator at position {position}")
        atom_start = position
        while position < len(unit_str) and unit_str[position] not in "*/":
            position += 1
        atom = unit_str[atom_start:position]
        if not atom:
            raise _unit_error("Missing unit atom")
        resolved = _resolve_atom(atom)
        exponent = 1
        if position < len(unit_str) and unit_str.startswith("**", position):
            position += 2
            sign = 1
            if position < len(unit_str) and unit_str[position] in "+-":
                sign = -1 if unit_str[position] == "-" else 1
                position += 1
            digits_start = position
            while position < len(unit_str) and unit_str[position].isdigit():
                position += 1
            digit_count = position - digits_start
            if digit_count == 0 or digit_count > MAX_EXPONENT_DIGITS:
                raise _unit_error("Exponent has too many or no digits")
            exponent = sign * int(unit_str[digits_start:position])
        if resolved is None:
            # Some legacy aliases contain a slash and are registered as one
            # compatibility atom.  Use that atom only after grammar parsing
            # has failed to resolve its components.
            direct = _registered_direct_unit(unit_str)
            if direct is not None:
                return direct
            raise _unit_error(f"Cannot parse unit expression; Unknown unit: {atom!r}")
        canonical, atom_dimension, atom_scale, affine = resolved
        effective_exponent = -exponent if denominator else exponent
        if abs(effective_exponent) > MAX_ABS_UNIT_EXPONENT:
            raise _unit_error(f"Exponent exceeds {MAX_ABS_UNIT_EXPONENT}")
        if affine and (atom_count or effective_exponent != 1 or position < len(unit_str)):
            raise _unit_error("Affine units cannot be compound or exponentiated")
        atom_count += 1
        if atom_count > MAX_COMPOUND_ATOMS or depth > MAX_COMPOUND_DEPTH:
            raise _unit_error("Unit expression exceeds parser resource limits")
        factors[canonical] = factors.get(canonical, 0) + effective_exponent
        dimension = dimension * (atom_dimension**effective_exponent)
        try:
            scale *= atom_scale**effective_exponent
        except (OverflowError, ValueError) as exc:
            raise _unit_error("Unit expression scale overflow") from exc
        if not math.isfinite(scale) or scale == 0:
            raise _unit_error("Unit expression scale is not finite and non-zero")
        if position == len(unit_str):
            break
        if unit_str[position] == "/":
            if denominator:
                raise _unit_error("Only one division operator is supported")
            denominator = True
        elif unit_str[position] != "*":
            raise _unit_error(f"Unexpected character at position {position}")
        position += 1

    factors = {canonical: exponent for canonical, exponent in factors.items() if exponent}
    if len(factors) > MAX_COMPOUND_ATOMS:
        raise _unit_error("Unit expression exceeds factor limit")
    return UnitExpression(tuple(sorted(factors.items())), dimension, scale)


def render_expression(expression: UnitExpression | _UncheckedUnitExpression) -> str | None:
    """Render structural factors without reparsing a generated string."""
    numerator: list[str] = []
    denominator: list[str] = []
    for canonical, exponent in expression.factors:
        target = numerator if exponent > 0 else denominator
        magnitude = abs(exponent)
        target.append(canonical if magnitude == 1 else f"{canonical}**{magnitude}")
    if not numerator and not denominator:
        return None
    result = "*".join(numerator) if numerator else "1"
    if denominator:
        result += "/" + "*".join(denominator)
    if len(result) > MAX_CANONICAL_UNIT_LENGTH:
        raise _unit_error(
            f"Canonical unit expression exceeds {MAX_CANONICAL_UNIT_LENGTH} characters"
        )
    return result


def _combine_expressions(left: UnitExpression, right: UnitExpression, sign: int) -> UnitExpression:
    factors: dict[str, int] = dict(left.factors)
    for canonical, exponent in right.factors:
        factors[canonical] = factors.get(canonical, 0) + sign * exponent
    factors = {canonical: exponent for canonical, exponent in factors.items() if exponent}
    dimension = left.dimension * right.dimension if sign == 1 else left.dimension / right.dimension
    try:
        scale = (
            left.scale_to_base * right.scale_to_base
            if sign == 1
            else left.scale_to_base / right.scale_to_base
        )
    except (OverflowError, ValueError) as exc:
        raise _unit_error("Unit expression scale overflow") from exc
    if not math.isfinite(scale) or scale == 0:
        raise _unit_error("Unit expression scale is not finite and non-zero")
    return UnitExpression(tuple(sorted(factors.items())), dimension, scale)


def multiply_expressions(left: UnitExpression, right: UnitExpression) -> UnitExpression:
    if left.dimension.is_affine or right.dimension.is_affine:
        raise ValueError("Affine units cannot participate in multiplication")
    return _combine_expressions(left, right, 1)


def divide_expressions(left: UnitExpression, right: UnitExpression) -> UnitExpression:
    if left.dimension.is_affine or right.dimension.is_affine:
        raise ValueError("Affine units cannot participate in division")
    return _combine_expressions(left, right, -1)


def power_expression(expression: UnitExpression, exponent: int) -> UnitExpression:
    if not isinstance(exponent, int) or isinstance(exponent, bool):
        raise ValueError("Unit expressions require integer powers")
    if abs(exponent) > MAX_ABS_UNIT_EXPONENT:
        raise ValueError(f"Exponent exceeds {MAX_ABS_UNIT_EXPONENT}")
    if expression.dimension.is_affine:
        raise ValueError("Affine units cannot be exponentiated")
    factors = tuple((canonical, power * exponent) for canonical, power in expression.factors)
    try:
        scale = expression.scale_to_base**exponent
    except (OverflowError, ValueError) as exc:
        raise _unit_error("Unit expression scale overflow") from exc
    if not math.isfinite(scale) or scale == 0:
        raise _unit_error("Unit expression scale is not finite and non-zero")
    return UnitExpression(factors, expression.dimension**exponent, scale)


class UnitDefinition:
    """Immutable definition of a single unit within the structural registry.

    Stores the canonical name, structural :class:`Dimension`, multiplicative
    scale factor (relative to the dimension's base unit), optional affine
    offset, and the full set of user-facing aliases.
    """

    __slots__ = (
        "canonical",
        "dimension",
        "scale",
        "offset",
        "affine",
        "aliases",
        "display",
        "category",
        "base_canonical",
    )

    # Type annotations for __slots__ attributes (mypy needs these)
    canonical: str
    dimension: Dimension
    scale: float
    offset: float
    affine: bool
    aliases: tuple[str, ...]
    display: str | None
    category: str
    base_canonical: str

    def __init__(
        self,
        canonical: str,
        dimension: Dimension,
        scale: float,
        offset: float = 0.0,
        affine: bool = False,
        aliases: tuple[str, ...] = (),
        display: str | None = None,
        category: str = "",
        base_canonical: str = "",
    ) -> None:
        if not math.isfinite(scale) or scale == 0.0:
            raise ValueError(f"Scale must be a non-zero finite number, got {scale}")
        if not math.isfinite(offset):
            raise ValueError(f"Offset must be finite, got {offset}")
        object.__setattr__(self, "canonical", canonical)
        object.__setattr__(self, "dimension", dimension)
        object.__setattr__(self, "scale", scale)
        object.__setattr__(self, "offset", offset)
        object.__setattr__(self, "affine", affine)
        object.__setattr__(self, "aliases", aliases)
        object.__setattr__(self, "display", display)
        object.__setattr__(self, "category", category)
        object.__setattr__(self, "base_canonical", base_canonical)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("UnitDefinition is immutable")

    def __delattr__(self, name: str) -> None:
        raise AttributeError("UnitDefinition is immutable")

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, UnitDefinition):
            return NotImplemented
        return (
            self.canonical == other.canonical
            and self.dimension == other.dimension
            and self.scale == other.scale
            and self.offset == other.offset
            and self.affine == other.affine
            and self.category == other.category
            and self.base_canonical == other.base_canonical
        )

    def __hash__(self) -> int:
        return hash(
            (
                self.canonical,
                self.dimension,
                self.scale,
                self.offset,
                self.affine,
                self.category,
                self.base_canonical,
            )
        )

    def __repr__(self) -> str:
        return (
            f"UnitDefinition(canonical={self.canonical!r}, "
            f"dim={self.dimension!r}, scale={self.scale}, "
            f"offset={self.offset}, affine={self.affine})"
        )


# ---------------------------------------------------------------------------
# Authoritative unit registry (D4)
# ---------------------------------------------------------------------------


class UnitRegistry:
    """Immutable registry mapping every known unit to its structural definition.

    Built by :func:`build_unit_registry` from the declarative
    :data:`UNIT_DEFINITIONS` tuple.  The legacy mapping names remain generated
    read-only adapters for callers that still import them.  Provides:

    * alias → :class:`UnitDefinition` lookup
    * canonical → :class:`UnitDefinition` lookup
    * structural :class:`Dimension` lookup
    * conversion factor computation (scale-ratio for multiplicative,
      offset-aware for affine)
    """

    __slots__ = (
        "_by_alias",
        "_by_canonical",
        "_dimensions",
        "_all_aliases",
        "_all_canonicals",
    )

    # Type annotations for __slots__ attributes (mypy needs these)
    _by_alias: MappingProxyType[str, UnitDefinition]
    _by_canonical: MappingProxyType[str, UnitDefinition]
    _dimensions: MappingProxyType[str, Dimension]
    _all_aliases: frozenset[str]
    _all_canonicals: frozenset[str]

    def __init__(
        self,
        by_alias: dict[str, UnitDefinition],
        by_canonical: dict[str, UnitDefinition],
        dimensions: dict[str, Dimension],
    ) -> None:
        object.__setattr__(self, "_by_alias", MappingProxyType(dict(by_alias)))
        object.__setattr__(self, "_by_canonical", MappingProxyType(dict(by_canonical)))
        object.__setattr__(self, "_dimensions", MappingProxyType(dict(dimensions)))
        object.__setattr__(self, "_all_aliases", frozenset(by_alias))
        object.__setattr__(self, "_all_canonicals", frozenset(by_canonical))

    # -- lookups ----------------------------------------------------------

    def by_alias(self, alias: str) -> UnitDefinition | None:
        return self._by_alias.get(alias)

    def by_canonical(self, canonical: str) -> UnitDefinition | None:
        return self._by_canonical.get(canonical)

    def dimension_of(self, unit: str) -> Dimension | None:
        ud = self._by_alias.get(unit) or self._by_canonical.get(unit)
        return ud.dimension if ud is not None else None

    def is_known(self, unit: str) -> bool:
        return unit in self._by_alias or unit in self._by_canonical

    # -- conversion -------------------------------------------------------

    def conversion_factor(self, from_unit: str, to_unit: str) -> float | None:
        """Return multiplicative factor ``from_unit → to_unit``, or None."""
        from_ud = self._by_alias.get(from_unit) or self._by_canonical.get(from_unit)
        to_ud = self._by_alias.get(to_unit) or self._by_canonical.get(to_unit)
        if from_ud is None or to_ud is None:
            return None
        if from_ud.dimension != to_ud.dimension:
            return None
        if from_ud.affine or to_ud.affine:
            return None  # use convert_temperature for affine units
        if to_ud.scale == 0:
            return None
        return from_ud.scale / to_ud.scale

    # -- introspection ----------------------------------------------------

    @property
    def all_aliases(self) -> frozenset[str]:
        return self._all_aliases

    @property
    def all_canonicals(self) -> frozenset[str]:
        return self._all_canonicals

    @property
    def dimensions(self) -> dict[str, Dimension]:
        return dict(self._dimensions)

    @property
    def definitions(self) -> tuple[UnitDefinition, ...]:
        return tuple(self._by_canonical.values())

    def __len__(self) -> int:
        return len(self._by_alias)

    def __repr__(self) -> str:
        return f"UnitRegistry(aliases={len(self._by_alias)}, canonicals={len(self._by_canonical)})"


def build_unit_registry(
    definitions: tuple[UnitSpec, ...] = UNIT_DEFINITIONS,
) -> UnitRegistry:
    """Build the registry solely from the declarative unit specifications."""
    _validate_unit_definitions(definitions)
    by_alias: dict[str, UnitDefinition] = {}
    by_canonical: dict[str, UnitDefinition] = {}
    dimensions: dict[str, Dimension] = {}

    for spec in definitions:
        definition = UnitDefinition(
            canonical=spec.canonical,
            dimension=spec.dimension,
            scale=spec.scale_to_base,
            offset=spec.offset_to_base,
            affine=spec.affine,
            aliases=spec.aliases,
            display=spec.display,
            category=spec.category,
            base_canonical=spec.base_canonical,
        )
        by_canonical[spec.canonical] = definition
        dimensions[spec.canonical] = spec.dimension
        for alias in spec.aliases:
            by_alias[alias] = definition
            dimensions[alias] = spec.dimension

    return UnitRegistry(by_alias, by_canonical, dimensions)


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

    def __init__(self, value: Numeric, unit: str | None = None) -> None:
        # Normalize complex values with zero imaginary part to float
        # to maintain hash contract (complex(5,0) == 5.0 but different hashes)
        if isinstance(value, complex) and value.imag == 0:
            value = value.real
        self.value = value
        self._display_unit = unit
        self._unit_expr = (
            parse_unit_expression(unit) if unit is not None else DIMENSIONLESS_EXPRESSION
        )
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

    def __add__(self, other: Numeric | UnitValue) -> UnitValue:
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

    def __radd__(self, other: Numeric | UnitValue) -> UnitValue:
        return self.__add__(other)

    def __sub__(self, other: Numeric | UnitValue) -> UnitValue:
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

    def __rsub__(self, other: Numeric | UnitValue) -> UnitValue:
        if isinstance(other, UnitValue):
            return other.__sub__(self)
        if self.unit is None:
            return UnitValue(other - self.value, None)
        raise ValueError("Cannot subtract a unit value from a dimensionless number")

    def __mul__(self, other: Numeric | UnitValue) -> UnitValue:
        if isinstance(other, UnitValue):
            if self.unit and other.unit:
                if self._unit_expr.dimension.is_affine or other._unit_expr.dimension.is_affine:
                    raise ValueError("Affine units cannot participate in multiplication")
                left, right = _align_compatible_units(self, other)
                result = left.value * right.value
                assert left._unit_expr is not None and right._unit_expr is not None
                expression = multiply_expressions(left._unit_expr, right._unit_expr)
                unit = render_expression(expression)
            else:
                result = self.value * other.value
                unit = self.unit or other.unit
        else:
            result = self.value * other
            unit = self.unit
        UnitValue._check_overflow(result)
        return UnitValue(result, unit)

    def __rmul__(self, other: Numeric | UnitValue) -> UnitValue:
        return self.__mul__(other)

    def __truediv__(self, other: Numeric | UnitValue) -> UnitValue:
        if isinstance(other, UnitValue):
            if other.value == 0:
                raise ZeroDivisionError("Cannot divide UnitValue by zero")
            if self.unit and other.unit:
                if self._unit_expr.dimension.is_affine or other._unit_expr.dimension.is_affine:
                    raise ValueError("Affine units cannot participate in division")
                left, right = _align_compatible_units(self, other)
                if left.unit == right.unit:
                    result = left.value / right.value
                    unit = None
                else:
                    result = left.value / right.value
                    assert left._unit_expr is not None and right._unit_expr is not None
                    expression = divide_expressions(left._unit_expr, right._unit_expr)
                    unit = render_expression(expression)
            elif other.unit:
                # self is dimensionless, other has a unit -> reciprocal unit
                result = self.value / other.value
                assert other._unit_expr is not None
                expression = divide_expressions(DIMENSIONLESS_EXPRESSION, other._unit_expr)
                unit = render_expression(expression)
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

    def __floordiv__(self, other: Numeric | UnitValue) -> UnitValue:
        if isinstance(other, UnitValue):
            if other.value == 0:
                raise ZeroDivisionError("Cannot divide UnitValue by zero")
            if self.unit or other.unit:
                if (self.unit and self._unit_expr.dimension.is_affine) or (
                    other.unit and other._unit_expr.dimension.is_affine
                ):
                    raise ValueError("Affine units cannot participate in floor division")
                quotient = _floor_divide_quantities(self, other)
                UnitValue._check_overflow(quotient)
                return UnitValue(quotient, None)
            result = self.value // other.value  # type: ignore[operator]
            UnitValue._check_overflow(result)
            return UnitValue(result, None)
        if other == 0:
            raise ZeroDivisionError("Cannot divide UnitValue by zero")
        result = self.value // other  # type: ignore[operator]
        UnitValue._check_overflow(result)
        return UnitValue(result, self.unit)

    def __rfloordiv__(self, other: Numeric | UnitValue) -> UnitValue:
        if isinstance(other, UnitValue):
            return other.__floordiv__(self)
        if self.unit:
            if self.value == 0:
                raise ZeroDivisionError("Cannot divide by zero UnitValue")
            raise ValueError(f"Cannot floor-divide a number by a unit value ('{self.unit}')")
        if self.value == 0:
            raise ZeroDivisionError("Cannot divide by zero UnitValue")
        return UnitValue(other // self.value, None)  # type: ignore[operator]

    def __mod__(self, other: Numeric | UnitValue) -> UnitValue:
        if isinstance(other, UnitValue):
            if other.value == 0:
                raise ZeroDivisionError("Cannot mod UnitValue by zero")
            if self.unit or other.unit:
                if (self.unit and self._unit_expr.dimension.is_affine) or (
                    other.unit and other._unit_expr.dimension.is_affine
                ):
                    raise ValueError("Affine units cannot participate in modulo")
                remainder = _modulo_quantities(self, other)
                UnitValue._check_overflow(remainder.value)
                return remainder
            result = self.value % other.value  # type: ignore[operator]
            UnitValue._check_overflow(result)
            return UnitValue(result, None)
        if other == 0:
            raise ZeroDivisionError("Cannot mod UnitValue by zero")
        result = self.value % other  # type: ignore[operator]
        UnitValue._check_overflow(result)
        return UnitValue(result, self.unit)

    def __rmod__(self, other: Numeric | UnitValue) -> UnitValue:
        if isinstance(other, UnitValue):
            return other.__mod__(self)
        if self.unit:
            if self.value == 0:
                raise ZeroDivisionError("Cannot mod by zero UnitValue")
            raise ValueError(f"Cannot take modulo by a unit value ('{self.unit}')")
        if self.value == 0:
            raise ZeroDivisionError("Cannot mod by zero UnitValue")
        return UnitValue(other % self.value, None)  # type: ignore[operator]

    def __rtruediv__(self, other: Numeric | UnitValue) -> UnitValue:
        if isinstance(other, UnitValue):
            return other.__truediv__(self)
        if self.unit:
            if self.value == 0:
                raise ZeroDivisionError("Cannot divide by zero UnitValue")
            assert self._unit_expr is not None
            expression = divide_expressions(DIMENSIONLESS_EXPRESSION, self._unit_expr)
            return UnitValue(other / self.value, render_expression(expression))
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
                assert self._unit_expr is not None
                unit = render_expression(power_expression(self._unit_expr, other))
            elif isinstance(other, float) and other.is_integer():
                int_exp = int(other)
                result = self.value**other
                if int_exp == 0:
                    return UnitValue(result, None)
                assert self._unit_expr is not None
                unit = render_expression(power_expression(self._unit_expr, int_exp))
            else:
                raise ValueError(f"Cannot raise unit '{self.unit}' to non-integer power")
        else:
            result = self.value**other
            unit = self.unit
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
        if target_unit is None:
            raise ValueError("Target unit cannot be None")
        if self.unit is None:
            raise ValueError("Cannot convert dimensionless value")
        source = self._unit_expr
        target = parse_unit_expression(target_unit)
        if source is None or source.dimension != target.dimension:
            raise ValueError(f"Cannot convert incompatible units: {self.unit} -> {target_unit}")
        source_definition = _single_definition(source)
        target_definition = _single_definition(target)
        if (
            source_definition is not None
            and target_definition is not None
            and (source_definition.affine or target_definition.affine)
        ):
            base_value = self.value * source_definition.scale + source_definition.offset
            converted = (base_value - target_definition.offset) / target_definition.scale
        else:
            if source.dimension.is_affine:
                raise ValueError("Affine units must be standalone temperature units")
            converted = self.value * (source.scale_to_base / target.scale_to_base)
        return UnitValue(converted, target_unit)


# Pre-computed conversion factors: (from_unit, to_unit) -> factor.
# These are empty placeholders, populated as immutable MappingProxyType
# adapters by _install_generated_adapters() from UNIT_DEFINITIONS.
UNIT_ALIASES: dict[str, str] = {}
UNIT_BASE: dict[str, dict[str, float]] = {}
UNIT_CATEGORIES: dict[str, str] = {}
TEMPERATURE_CONVERSIONS: dict[tuple[str, str], tuple[float, float]] = {}
UNIT_CONVERSIONS: dict[tuple[str, str], float] = {}


# Compatibility hook; conversion behavior remains registry-owned.
# _rebuild_conversions() is defined at the end of this module.


def _floor_divide_quantities(left: UnitValue, right: UnitValue) -> int | float:
    """Floor-divide two compatible UnitValues, returning a dimensionless quotient.

    For same-unit operands, returns ``left.value // right.value``.
    For compatible different-unit operands, converts the dividend into the
    divisor's unit first to avoid floating-point precision loss.
    Raises ``ValueError`` if the units are incompatible.
    """
    if left.unit and right.unit:
        if left.unit == right.unit:
            return left.value // right.value  # type: ignore[operator]
        # Convert left into right's unit before floor division.
        converted = left.convert_to(right.unit)
        return converted.value // right.value  # type: ignore[operator]
    if right.unit:
        raise ValueError(f"Cannot floor-divide a number by a unit value ('{right.unit}')")
    return left.value // right.value  # type: ignore[operator]


def _modulo_quantities(left: UnitValue, right: UnitValue) -> UnitValue:
    """Compute the modulo of two compatible UnitValues.

    Returns a ``UnitValue`` whose display unit is the divisor's unit.
    For same-unit operands, the result carries the (shared) unit.
    For compatible different-unit operands, the dividend is converted into
    the divisor's unit first.
    Raises ``ValueError`` if the units are incompatible.
    """
    if left.unit and right.unit:
        if left.unit == right.unit:
            return UnitValue(left.value % right.value, right.unit)  # type: ignore[operator]
        # Convert left into right's unit before modulo.
        converted = left.convert_to(right.unit)
        return UnitValue(converted.value % right.value, right.unit)  # type: ignore[operator]
    if right.unit:
        raise ValueError(f"Cannot compute modulo by a unit value ('{right.unit}')")
    return UnitValue(left.value % right.value, left.unit)  # type: ignore[operator]


# Module-level registry instance (built lazily on first access).
_unit_registry: UnitRegistry | None = None


def _get_unit_registry() -> UnitRegistry | None:
    """Return the module-level :class:`UnitRegistry`, building it on first call."""
    global _unit_registry
    if _unit_registry is None:
        _unit_registry = build_unit_registry()
    return _unit_registry


def get_all_units() -> list[str]:
    """Get list of all supported units."""
    return sorted(UNIT_ALIASES.keys())


# ---------------------------------------------------------------------------
# Generated compatibility adapters and registry-owned public helpers
# ---------------------------------------------------------------------------


def _single_definition(expression: UnitExpression) -> UnitDefinition | None:
    if len(expression.factors) != 1 or expression.factors[0][1] != 1:
        return None
    registry = _get_unit_registry()
    if registry is None:
        return None
    return registry.by_canonical(expression.factors[0][0])


def _generated_temperature_conversions(
    registry: UnitRegistry,
) -> MappingProxyType[tuple[str, str], tuple[float, float]]:
    temperatures = [
        definition for definition in registry.definitions if definition.category == "temperature"
    ]
    result: dict[tuple[str, str], tuple[float, float]] = {}
    for source in temperatures:
        for target in temperatures:
            if source.canonical == target.canonical:
                continue
            multiplier = source.scale / target.scale
            offset = (source.offset - target.offset) / target.scale
            result[(source.canonical, target.canonical)] = (multiplier, offset)
    return MappingProxyType(result)


_BUILTIN_UNIT_DEFINITIONS = UNIT_DEFINITIONS
_CUSTOM_UNIT_DEFINITIONS: dict[str, UnitSpec] = {}


def _refresh_compatibility_consumers() -> None:
    """Refresh legacy evaluator bindings after a declaration extension."""
    import sys

    namespaces = [globals()]
    evaluator_module = sys.modules.get("eggcalc.evaluator")
    if evaluator_module is not None:
        namespaces.append(vars(evaluator_module))
    for namespace in namespaces:
        if "UNIT_ALIASES" in namespace:
            namespace["UNIT_ALIASES"] = UNIT_ALIASES
            namespace["_SORTED_UNIT_ALIASES"] = sorted(UNIT_ALIASES, key=len, reverse=True)


def _install_generated_adapters(
    definitions: tuple[UnitSpec, ...] | None = None,
) -> None:
    global UNIT_ALIASES, UNIT_BASE, UNIT_CATEGORIES
    global UNIT_CONVERSIONS, TEMPERATURE_CONVERSIONS, _unit_registry
    registry = build_unit_registry(
        _BUILTIN_UNIT_DEFINITIONS if definitions is None else definitions
    )
    _unit_registry = registry
    UNIT_ALIASES = MappingProxyType(  # type: ignore[assignment]
        {alias: definition.canonical for alias, definition in registry._by_alias.items()}
    )
    UNIT_CATEGORIES = MappingProxyType(  # type: ignore[assignment]
        {alias: definition.category for alias, definition in registry._by_alias.items()}
    )
    grouped: dict[str, dict[str, float]] = {}
    for definition in registry.definitions:
        if definition.affine:
            continue
        variants = grouped.setdefault(definition.base_canonical, {})
        for alias in definition.aliases:
            variants[alias] = definition.scale
    UNIT_BASE = MappingProxyType(  # type: ignore[assignment]
        {
            base: MappingProxyType(dict(sorted(variants.items())))
            for base, variants in grouped.items()
        }
    )
    TEMPERATURE_CONVERSIONS = _generated_temperature_conversions(registry)  # type: ignore[assignment]
    pairwise: dict[tuple[str, str], float] = {}
    non_affine = [definition for definition in registry.definitions if not definition.affine]
    for source in non_affine:
        for target in non_affine:
            if source.dimension != target.dimension or source.canonical == target.canonical:
                continue
            factor = source.scale / target.scale
            for source_alias in source.aliases:
                for target_alias in target.aliases:
                    pairwise[(source_alias, target_alias)] = factor
    UNIT_CONVERSIONS = MappingProxyType(pairwise)  # type: ignore[assignment]
    _refresh_compatibility_consumers()


def register_custom_units(
    custom_units: Mapping[str, Mapping[str, object]],
    custom_aliases: Mapping[str, str] | None = None,
) -> None:
    """Extend the declaration registry with validated user units.

    User configuration is an extension layer, not a mutation of the public
    compatibility adapters.  The active registry and adapters are rebuilt as
    one immutable snapshot from built-in declarations plus these extensions.
    """
    additions = dict(_CUSTOM_UNIT_DEFINITIONS)
    registry = build_unit_registry(_BUILTIN_UNIT_DEFINITIONS + tuple(additions.values()))
    for base, unit_dict in custom_units.items():
        base_definition = registry.by_alias(base) or registry.by_canonical(base)
        if base_definition is None:
            raise ValueError(f"Unknown custom-unit family base: {base!r}")
        for canonical, raw_value in unit_dict.items():
            category = base_definition.category
            factor_value = raw_value
            if isinstance(raw_value, tuple) and len(raw_value) == 2:
                factor_value, configured_category = raw_value
                if not isinstance(configured_category, str):
                    raise ValueError(f"Invalid custom-unit category for {canonical!r}")
                category = configured_category
            if not isinstance(canonical, str) or not isinstance(factor_value, (int, float)):
                raise ValueError(f"Invalid custom-unit declaration for {canonical!r}")
            aliases = [canonical]
            if custom_aliases:
                aliases.extend(
                    alias for alias, target in custom_aliases.items() if target == canonical
                )
            additions[canonical] = UnitSpec(
                canonical=canonical,
                aliases=tuple(dict.fromkeys(aliases)),
                dimension=base_definition.dimension,
                scale_to_base=float(factor_value),
                display=canonical,
                category=category,
                base_canonical=base_definition.base_canonical,
            )

    definitions = list(_BUILTIN_UNIT_DEFINITIONS) + list(additions.values())
    if custom_aliases:
        by_canonical = {definition.canonical: definition for definition in definitions}
        for alias, target in custom_aliases.items():
            target_definition = by_canonical.get(target)
            if target_definition is None:
                raise ValueError(f"Unknown custom-unit alias target: {target!r}")
            if alias not in target_definition.aliases:
                replacement = replace(
                    target_definition,
                    aliases=(*target_definition.aliases, alias),
                )
                definitions = [
                    replacement if definition.canonical == target else definition
                    for definition in definitions
                ]
    _CUSTOM_UNIT_DEFINITIONS.clear()
    _CUSTOM_UNIT_DEFINITIONS.update(additions)
    _install_generated_adapters(tuple(definitions))


def unregister_custom_units(names: Mapping[str, object] | set[str] | tuple[str, ...]) -> None:
    """Remove named user-unit extensions and restore generated adapters."""
    for name in names:
        _CUSTOM_UNIT_DEFINITIONS.pop(name, None)
    definitions = _BUILTIN_UNIT_DEFINITIONS + tuple(_CUSTOM_UNIT_DEFINITIONS.values())
    _install_generated_adapters(definitions)


def _lookup_definition(unit: str) -> UnitDefinition | None:
    registry = _get_unit_registry()
    if registry is None:
        return None
    candidates = (unit, unit.lower(), unit.upper(), unit.title(), unit.capitalize())
    for candidate in candidates:
        definition = registry.by_alias(candidate) or registry.by_canonical(candidate)
        if definition is not None:
            return definition
    return None


def normalize_unit(unit: str) -> str:  # noqa: F811
    """Return the registry canonical for a known alias."""
    definition = _lookup_definition(unit)
    return definition.canonical if definition is not None else unit


def is_unit(text: str) -> bool:  # noqa: F811
    try:
        parse_unit_expression(text)
        return True
    except (TypeError, ValueError):
        return False


def get_unit_category(unit: str) -> str | None:  # noqa: F811
    definition = _lookup_definition(unit)
    if definition is not None:
        return definition.category
    try:
        dimension = parse_unit_expression(unit).dimension
    except (TypeError, ValueError):
        return None
    known = {
        DIM_LENGTH**2: "area",
        DIM_LENGTH**3: "volume",
        DIM_LENGTH / DIM_TIME: "speed",
        Dimension(length=1, time=-2): "acceleration",
        DIM_TIME**-1: "frequency",
    }
    return known.get(dimension)


def are_units_compatible(unit1: str | None, unit2: str | None) -> bool:  # noqa: F811
    if unit1 is None and unit2 is None:
        return True
    if unit1 is None or unit2 is None:
        return False
    try:
        return parse_unit_expression(unit1).dimension == parse_unit_expression(unit2).dimension
    except (TypeError, ValueError):
        return False


def get_conversion_factor(from_unit: str, to_unit: str) -> float:  # noqa: F811
    source = parse_unit_expression(from_unit)
    target = parse_unit_expression(to_unit)
    if source.dimension != target.dimension:
        raise ValueError(f"Cannot convert from {from_unit} to {to_unit}")
    if source.dimension.is_affine:
        raise ValueError("Affine temperature conversion requires convert_temperature")
    factor = source.scale_to_base / target.scale_to_base
    if not math.isfinite(factor):
        raise ValueError("Conversion factor is not finite")
    return factor


def convert_temperature(value: float, from_unit: str, to_unit: str) -> float:  # noqa: F811
    if not math.isfinite(value):
        raise ValueError(f"Temperature value must be finite, got {value}")
    source = parse_unit_expression(from_unit)
    target = parse_unit_expression(to_unit)
    source_definition = _single_definition(source)
    target_definition = _single_definition(target)
    if (
        source_definition is None
        or target_definition is None
        or not source_definition.affine
        or not target_definition.affine
    ):
        raise ValueError(f"Cannot convert temperature from {from_unit} to {to_unit}")
    if source.dimension != target.dimension:
        raise ValueError(f"Cannot convert temperature from {from_unit} to {to_unit}")
    base_value = value * source_definition.scale + source_definition.offset
    result = (base_value - target_definition.offset) / target_definition.scale
    if not math.isfinite(result):
        raise ValueError("Temperature conversion result is not finite")
    if math.isclose(result, round(result), rel_tol=0.0, abs_tol=1e-12):
        result = float(round(result))
    return result


def _simplify_unit_string(unit: str | None) -> str | None:
    if unit is None:
        return None
    try:
        # Keep the private compatibility helper's historical left-to-right
        # rendering contract.  Public parsing and arithmetic use the bounded
        # grammar/structural operations above.
        def parse_compat_factor(text: str) -> UnitExpression:
            power = re.fullmatch(r"([^*/]+)\*\*([+-]?\d+)", text)
            if power is not None:
                return power_expression(parse_unit_expression(power.group(1)), int(power.group(2)))
            return parse_unit_expression(text)

        parts = re.split(r"(?<!\*)/(?!/)|(?<!\*)\*(?!\*)", unit)
        operators = re.findall(r"(?<!\*)/(?!/)|(?<!\*)\*(?!\*)", unit)
        if len(parts) == 1:
            return render_expression(parse_compat_factor(unit))
        expression = parse_compat_factor(parts[0])
        for operator, part in zip(operators, parts[1:]):
            right = parse_compat_factor(part)
            expression = (
                multiply_expressions(expression, right)
                if operator == "*"
                else divide_expressions(expression, right)
            )
        return render_expression(expression)
    except ValueError:
        return unit


def _pow_unit_string(unit: str, exp: int) -> str | None:
    try:
        return render_expression(power_expression(parse_unit_expression(unit), exp))
    except ValueError:
        return None


def _structural_dimension(unit: str) -> Dimension | None:
    try:
        return parse_unit_expression(unit).dimension
    except (TypeError, ValueError):
        return None


def _align_compatible_units(left: UnitValue, right: UnitValue) -> tuple[UnitValue, UnitValue]:
    if left.unit is None or right.unit is None:
        return left, right
    assert left._unit_expr is not None and right._unit_expr is not None
    if left._unit_expr.dimension != right._unit_expr.dimension:
        return left, right
    if left.unit == right.unit:
        return left, right
    converted = right.convert_to(left.unit)
    return left, converted


DIMENSIONLESS_EXPRESSION = UnitExpression((), DIM_DIMENSIONLESS, 1.0)
_install_generated_adapters()


def _rebuild_conversions() -> None:
    """Compatibility hook; conversion behavior remains registry-owned."""
    global UNIT_CONVERSIONS
    registry = _get_unit_registry()
    if registry is not None:
        # Recreate the immutable adapter from the declarations only.
        UNIT_CONVERSIONS = MappingProxyType({})  # type: ignore[assignment]
