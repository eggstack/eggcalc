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
        # The family base is explicit in the declaration model.  The default
        # keeps older positional construction source-compatible while making
        # the mapping deterministic and independent of declaration order.
        if not self.base_canonical:
            base_by_category = {
                "length": "m",
                "area": "m2",
                "time": "s",
                "data": "B",
                "data_rate": "bps",
                "mass": "kg",
                "volume": "L",
                "pressure": "Pa",
                "energy": "J",
                "power": "W",
                "force": "N",
                "voltage": "V",
                "current": "A",
                "angle": "rad",
                "speed": "m/s",
                "frequency": "Hz",
                "temperature": "K",
            }
            base = base_by_category.get(self.category)
            if base is None:
                raise ValueError(f"Unsupported unit category: {self.category!r}")
            object.__setattr__(self, "base_canonical", base)


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
    ),
    UnitSpec(
        canonical='fermi',
        aliases=('fermi',),
        dimension=DIM_LENGTH,
        scale_to_base=1e-15,
        display='fermi',
        category='length',
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
    ),
    UnitSpec(
        canonical='inH2O',
        aliases=('inH2O',),
        dimension=Dimension(mass=1, length=-1, time=-2),
        scale_to_base=249.08891,
        display='inH2O',
        category='pressure',
    ),
    UnitSpec(
        canonical='inHg',
        aliases=('inHg',),
        dimension=Dimension(mass=1, length=-1, time=-2),
        scale_to_base=3386.389,
        display='inHg',
        category='pressure',
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
    ),
    UnitSpec(
        canonical='mmH2O',
        aliases=('mmH2O',),
        dimension=Dimension(mass=1, length=-1, time=-2),
        scale_to_base=9.80665,
        display='mmH2O',
        category='pressure',
    ),
    UnitSpec(
        canonical='mmHg',
        aliases=('mmHg',),
        dimension=Dimension(mass=1, length=-1, time=-2),
        scale_to_base=133.32236842105,
        display='mmHg',
        category='pressure',
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
    ),
    UnitSpec(
        canonical='torr',
        aliases=('torr',),
        dimension=Dimension(mass=1, length=-1, time=-2),
        scale_to_base=133.32236842105,
        display='torr',
        category='pressure',
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
    ),
    UnitSpec(
        canonical='mach',
        aliases=('mach',),
        dimension=Dimension(length=1, time=-1),
        scale_to_base=340.29,
        display='mach',
        category='speed',
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
        rendered = render_expression(
            _UncheckedUnitExpression(normalized, expected_dimension, expected_scale)
        )
        if rendered is not None and len(rendered) > MAX_CANONICAL_UNIT_LENGTH:
            raise _unit_error("Canonical unit expression exceeds maximum length")
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
                expected_scale = base_definition.scale**exponent
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
    return result[:MAX_CANONICAL_UNIT_LENGTH]


def _combine_expressions(left: UnitExpression, right: UnitExpression, sign: int) -> UnitExpression:
    factors: dict[str, int] = dict(left.factors)
    for canonical, exponent in right.factors:
        factors[canonical] = factors.get(canonical, 0) + sign * exponent
    factors = {canonical: exponent for canonical, exponent in factors.items() if exponent}
    dimension = left.dimension * right.dimension if sign == 1 else left.dimension / right.dimension
    scale = (
        left.scale_to_base * right.scale_to_base
        if sign == 1
        else left.scale_to_base / right.scale_to_base
    )
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
    return UnitExpression(
        factors, expression.dimension**exponent, expression.scale_to_base**exponent
    )


# Mapping from UNIT_BASE category keys to their structural dimensions.
_CATEGORY_DIMENSIONS: dict[str, Dimension] = {
    "m": DIM_LENGTH,
    "s": DIM_TIME,
    "B": DIM_INFORMATION,
    "bps": Dimension(information=1, time=-1),
    "kg": DIM_MASS,
    "L": Dimension(length=3),
    "Pa": Dimension(mass=1, length=-1, time=-2),
    "J": Dimension(mass=1, length=2, time=-2),
    "W": Dimension(mass=1, length=2, time=-3),
    "N": Dimension(mass=1, length=1, time=-2),
    "V": Dimension(mass=1, length=2, time=-3, current=-1),
    "A": DIM_CURRENT,
    "rad": Dimension(angle=True),
    "m/s": Dimension(length=1, time=-1),
    "m2": Dimension(length=2),
    "Hz": Dimension(time=-1),
}

# Reverse mapping from friendly category names (as stored in
# UNIT_CATEGORIES) to structural Dimensions.  Used by
# _structural_dimension to resolve dynamically-registered custom units
# that aren't in the built-time registry.
_CATEGORY_NAME_TO_DIMENSION: dict[str, Dimension] = {
    "length": DIM_LENGTH,
    "time": DIM_TIME,
    "data": DIM_INFORMATION,
    "data_rate": Dimension(information=1, time=-1),
    "mass": DIM_MASS,
    "volume": Dimension(length=3),
    "pressure": Dimension(mass=1, length=-1, time=-2),
    "energy": Dimension(mass=1, length=2, time=-2),
    "power": Dimension(mass=1, length=2, time=-3),
    "force": Dimension(mass=1, length=1, time=-2),
    "voltage": Dimension(mass=1, length=2, time=-3, current=-1),
    "current": DIM_CURRENT,
    "angle": Dimension(angle=True),
    "speed": Dimension(length=1, time=-1),
    "area": Dimension(length=2),
    "frequency": Dimension(time=-1),
    "temperature": Dimension(temperature=1),
}


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
    _depth: int = 0,
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

    # Resource bounds
    if len(unit) > MAX_UNIT_STRING_LENGTH:
        return None
    if _depth > MAX_COMPOUND_DEPTH:
        return None

    # Atom-count bound: count top-level operators (each creates a split).
    # The total atoms = operators + 1, so reject if operators >= MAX_COMPOUND_ATOMS.
    _op_count, _ = _count_top_level_ops(unit)
    if _op_count >= MAX_COMPOUND_ATOMS:
        return None

    # Strip a leading "1/" or "1//" or "1%" reciprocal marker (the
    # convention used by __rfloordiv__ / __rmod__). These are
    # semantically identical to having the unit on the other side.
    if unit.startswith("1//"):
        inner = _parse_compound_signature(unit[3:], _depth + 1)
        if inner is None:
            return None
        num, den = inner
        return den, num
    if unit.startswith("1/"):
        inner = _parse_compound_signature(unit[2:], _depth + 1)
        if inner is None:
            return None
        num, den = inner
        return den, num
    if unit.startswith("1%"):
        inner = _parse_compound_signature(unit[2:], _depth + 1)
        if inner is None:
            return None
        num, den = inner
        return den, num

    op_idx, op = _find_last_top_level_op(unit)
    if op_idx != -1:
        left_str = unit[:op_idx]
        right_str = unit[op_idx + len(op) :]
        left = _parse_compound_signature(left_str, _depth + 1)
        right = _parse_compound_signature(right_str, _depth + 1)
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


def _count_top_level_ops(unit: str) -> tuple[int, str]:
    """Count top-level operators in a unit string.

    Returns ``(count, last_op)`` where ``count`` is the number of
    top-level ``*``, ``/``, ``//``, ``%`` operators (excluding those
    inside ``**`` exponentiation sequences) and ``last_op`` is the
    rightmost such operator string.
    """
    count = 0
    last_op = ""
    i = 0
    while i < len(unit):
        c = unit[i]
        if c == "*" and i + 1 < len(unit) and unit[i + 1] == "*":
            i += 2
            continue
        if c == "*":
            count += 1
            last_op = "*"
        elif c == "/" and i + 1 < len(unit) and unit[i + 1] == "/":
            count += 1
            last_op = "//"
            i += 2
            continue
        elif c == "/":
            count += 1
            last_op = "/"
        elif c == "%":
            count += 1
            last_op = "%"
        i += 1
    return count, last_op


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


def _align_compatible_units(left: UnitValue, right: UnitValue) -> tuple[UnitValue, UnitValue]:
    """Convert two UnitValues to a shared unit when they share a category.

    Returns a ``(left, right)`` pair with both values expressed in the
    same unit (chosen to be ``left``'s unit). When the units are already
    equal or belong to different categories, the pair is returned
    unchanged.
    """
    if left.unit is None or right.unit is None:
        return left, right
    if left.unit == right.unit:
        return left, right
    lcat = get_unit_category(left.unit)
    rcat = get_unit_category(right.unit)
    if lcat is None or rcat is None or lcat != rcat:
        return left, right
    converted = right.convert_to(left.unit)
    return left, UnitValue(converted.value, converted.unit)


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


def _pow_unit_string(unit: str, exp: int) -> str | None:
    """Raise a (possibly compound) unit string to an integer power.

    Works on the parsed signature so that compound units like
    ``"m/s"`` are exponentiated across the full expression
    (``(m/s)**2`` -> ``"m**2/s**2"``) rather than only on the
    trailing denominator (``"m/s**2"``). Returns ``None`` if the
    result is fully dimensionless (so the caller can produce a
    UnitValue with no unit), and ``None`` if ``unit`` cannot be
    parsed as a compound form.
    """
    sig = _parse_compound_signature(unit)
    if sig is None:
        return None
    num, den = sig
    scaled = (tuple((b, e * exp) for b, e in num), tuple((b, e * exp) for b, e in den))
    return _signature_to_canonical_string(scaled)


def are_units_compatible(unit1: str | None, unit2: str | None) -> bool:
    """Check if two units are compatible for addition/subtraction.

    Uses structural :class:`Dimension` comparison. Unknown units are
    treated as incompatible.

    Returns True if:
    - Both units are None (dimensionless)
    - Both units have the same structural dimension

    Returns False if:
    - Exactly one unit is None (dimensionless cannot be added to dimensional)
    - Units have different structural dimensions
    - One or both units have unknown dimensions
    """
    if unit1 is None and unit2 is None:
        return True
    if unit1 is None or unit2 is None:
        return False

    dim1 = _structural_dimension(unit1)
    dim2 = _structural_dimension(unit2)

    if dim1 is not None and dim2 is not None:
        return dim1 == dim2

    # Unknown units are incompatible (no category-string fallback)
    return False


def _structural_dimension(unit: str) -> Dimension | None:
    """Resolve the structural :class:`Dimension` for a unit string.

    Handles both simple units (``"m"``) and compound expressions
    (``"m/s"``, ``"kg*m**2"``) by parsing the unit signature and
    combining base dimensions.  Also resolves dynamically-registered
    custom units via their ``UNIT_CATEGORIES`` entry.
    """
    # Fast path: direct alias lookup
    normalized = normalize_unit(unit)
    _reg = _get_unit_registry()
    if _reg is not None:
        ud = _reg.by_alias(normalized)
        if ud is not None:
            return ud.dimension

    # Slow path: parse compound expression
    sig = _parse_compound_signature(normalized)
    if sig is not None:
        num, den = sig
        dim = DIM_DIMENSIONLESS
        ok = True
        for base, exp in num:
            base_dim = _base_unit_dimension(base)
            if base_dim is None:
                ok = False
                break
            dim = dim * (base_dim**exp)
        if ok:
            for base, exp in den:
                base_dim = _base_unit_dimension(base)
                if base_dim is None:
                    ok = False
                    break
                dim = dim / (base_dim**exp)
        if ok:
            return dim

    # Fallback: resolve dynamically-registered units via category mapping
    cat = UNIT_CATEGORIES.get(normalized)
    if cat is not None:
        return _CATEGORY_NAME_TO_DIMENSION.get(cat)

    return None


def _base_unit_dimension(unit: str) -> Dimension | None:
    """Return the Dimension for a base unit key used in compound signatures."""
    _dims: dict[str, Dimension] = {
        "m": DIM_LENGTH,
        "s": DIM_TIME,
        "B": DIM_INFORMATION,
        "bps": Dimension(information=1, time=-1),
        "kg": DIM_MASS,
        "L": Dimension(length=3),
        "Pa": Dimension(mass=1, length=-1, time=-2),
        "J": Dimension(mass=1, length=2, time=-2),
        "W": Dimension(mass=1, length=2, time=-3),
        "N": Dimension(mass=1, length=1, time=-2),
        "V": Dimension(mass=1, length=2, time=-3, current=-1),
        "A": DIM_CURRENT,
        "rad": Dimension(angle=True),
        "m/s": Dimension(length=1, time=-1),
        "m2": Dimension(length=2),
        "Hz": Dimension(time=-1),
    }
    return _dims.get(unit)


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


def normalize_unit(unit: str) -> str:  # type: ignore[no-redef]  # noqa: F811
    """Return the registry canonical for a known alias."""
    definition = _lookup_definition(unit)
    return definition.canonical if definition is not None else unit


def is_unit(text: str) -> bool:  # type: ignore[no-redef]  # noqa: F811
    try:
        parse_unit_expression(text)
        return True
    except (TypeError, ValueError):
        return False


def get_unit_category(unit: str) -> str | None:  # type: ignore[no-redef]  # noqa: F811
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


def are_units_compatible(unit1: str | None, unit2: str | None) -> bool:  # type: ignore[no-redef]  # noqa: F811
    if unit1 is None and unit2 is None:
        return True
    if unit1 is None or unit2 is None:
        return False
    try:
        return parse_unit_expression(unit1).dimension == parse_unit_expression(unit2).dimension
    except (TypeError, ValueError):
        return False


def get_conversion_factor(from_unit: str, to_unit: str) -> float:  # type: ignore[no-redef]  # noqa: F811
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


def convert_temperature(value: float, from_unit: str, to_unit: str) -> float:  # type: ignore[no-redef]  # noqa: F811
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


def _simplify_unit_string(unit: str | None) -> str | None:  # type: ignore[no-redef]
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


def _pow_unit_string(unit: str, exp: int) -> str | None:  # type: ignore[no-redef]
    try:
        return render_expression(power_expression(parse_unit_expression(unit), exp))
    except ValueError:
        return None


def _structural_dimension(unit: str) -> Dimension | None:  # type: ignore[no-redef]
    try:
        return parse_unit_expression(unit).dimension
    except (TypeError, ValueError):
        return None


def _align_compatible_units(left: UnitValue, right: UnitValue) -> tuple[UnitValue, UnitValue]:  # type: ignore[no-redef]
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


def _rebuild_conversions() -> None:  # type: ignore[no-redef]
    """Compatibility hook; conversion behavior remains registry-owned."""
    global UNIT_CONVERSIONS
    registry = _get_unit_registry()
    if registry is not None:
        # Recreate the immutable adapter from the declarations only.
        UNIT_CONVERSIONS = MappingProxyType({})  # type: ignore[assignment]
