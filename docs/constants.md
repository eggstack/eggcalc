# Constants

eggcalc includes mathematical and physical constants.

## Mathematical Constants

| Constant | Value | Description |
|----------|-------|-------------|
| `pi` | 3.14159... | π |
| `e` | 2.71828... | Euler's number |
| `tau` | 6.28318... | 2π |
| `i` | 1j | Imaginary unit |
| `j` | 1j | Imaginary unit (alias for `i`) |

```bash
calc "pi"             # 3.14159...
calc "e"              # 2.71828...
calc "tau"            # 6.28318...
calc "e^(i*pi)"       # -1+0j
```

## Physical Constants

| Constant | Symbol | Value | Unit |
|----------|--------|-------|------|
| `avogadro` | Nₐ | 6.022e+23 | mol⁻¹ |
| `boltzmann` | k | 1.381e-23 | J/K |
| `planck` | h | 6.626e-34 | J·s |
| `hbar` | ℏ | 1.055e-34 | J·s |
| `planckbar` | ℏ | 1.055e-34 | J·s |
| `c` | c | 299792458 | m/s |
| `elementarycharge` | e | 1.602e-19 | C |
| `amu` | u | 1.661e-27 | kg |
| `epsilon0` | ε₀ | 8.854e-12 | F/m |
| `mu0` | μ₀ | 1.257e-6 | H/m |
| `G` | G | 6.674e-11 | m³/(kg·s²) |
| `standardgravity` | gₙ | 9.80665 | m/s² |
| `r` | R | 8.314462618 | J/(mol·K) |
| `faraday` | F | 96485 | C/mol |
| `stefan` | σ | 5.670e-8 | W/(m²·K⁴) |
| `rydberg` | R∞ | 1.097e7 | m⁻¹ |
| `me` | mₑ | 9.109e-31 | kg |
| `mp` | mₚ | 1.673e-27 | kg |
| `mn` | mₙ | 1.675e-27 | kg |
| `re` | rₑ | 2.818e-15 | m |
| `alpha` | α | 7.297e-3 | - |
| `wien` | b | 2.898e-3 | m·K |

### Natural Language Aliases

| Constant | Aliases |
|----------|---------|
| `avogadro` | na, avogadros, avogadro number |
| `boltzmann` | k, boltzmann constant |
| `planck` | h, planck constant, planckconstant |
| `c` | speed of light, speed of light in vacuum, c zero |
| `elementarycharge` | echarge, elementary charge, e charge |
| `amu` | u, atomic mass, atomic mass unit, atomicmassunit |
| `epsilon0` | vacuum permittivity, permittivity of free space |
| `mu0` | vacuum permeability, permeability of free space, magnetic constant |
| `G` | gravitational constant, newton constant, big g |
| `standardgravity` | gravity, standard gravity, earth gravity |
| `r` | gas constant, ideal gas constant, molar gas constant, gasconstant, idealgasconstant |
| `faraday` | f, faraday constant, faradayconstant |
| `hbar` | planckbar, reducedplanck |
| `me` | electron mass |
| `mp` | proton mass |
| `mn` | neutron mass |
| `re` | electron radius, classical electron radius |
| `alpha` | fine structure constant, sommerfeld |
| `rydberg` | rydberg constant |
| `stefan` | stefan boltzmann, stefan-boltzmann constant |
| `wien` | wien constant, wien displacement |

## Usage

### Basic

```bash
calc "pi"
# 3.141592653589793

calc "avogadro"
# 6.022e+23

calc "speed of light"
# 299792458
```

### In Expressions

```bash
calc "2 * pi"
# 6.283185307179586

calc "5 * avogadro"
# 3.01e+24

calc "h * c / 500nm"   # Photon energy
# 3.97e-19
```

### Natural Language

```bash
calc "pi times two"
# 6.283...

calc "five times avogadro"
# 3.01e+24
```

## Custom Constants

Define custom constants in `eggcalc_config.py`:

```python
# eggcalc_config.py
CUSTOM_CONSTANTS = {
    "earth_radius": 6371,      # km
    "solar_mass": 1.989e30,    # kg
    "light_year": 9.461e15,    # m
}
```

Then use them:

```bash
calc "earth_radius"
# 6371

calc "2 * pi * earth_radius"
# 40030
```

## Python API

```python
from eggcalc import evaluate_raw, register_constant

# Use constants
result = evaluate_raw("pi * 2")
print(result)  # 6.283...

# Register custom constant
register_constant("my_constant", 42)
result = evaluate_raw("my_constant")
print(result)  # 42
```
