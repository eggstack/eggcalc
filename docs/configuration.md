# Configuration

## Configuration File

Create `eggcalc_config.py` in your working directory to customize eggcalc.

### Custom Constants

```python
# eggcalc_config.py

CUSTOM_CONSTANTS = {
    "earth_radius": 6371,      # km
    "solar_mass": 1.989e30,    # kg
    "light_year": 9.461e15,    # m
    "golden_ratio": 1.618033988749895,
}
```

Usage:

```bash
calc "earth_radius"
# 6371

calc "2 * pi * earth_radius"
# 40030
```

### Custom Functions

```python
# eggcalc_config.py

def celsius_to_fahrenheit(c):
    return c * 9/5 + 32

def body_mass_index(weight_kg, height_m):
    return weight_kg / (height_m ** 2)

CUSTOM_FUNCTIONS = {
    "ctof": celsius_to_fahrenheit,
    "bmi": body_mass_index,
}
```

Usage:

```bash
calc "ctof(100)"
# 212

calc "bmi(70, 1.75)"
# 22.857
```

### Custom Units

```python
# eggcalc_config.py

CUSTOM_UNITS = {
    "m": {
        "nmi": 1852.0,  # nautical miles
    },
}

CUSTOM_ALIASES = {
    "nautical_mile": "nmi",
    "nautical_miles": "nmi",
}
```

### Custom Number Words

```python
# eggcalc_config.py

CUSTOM_NUMBER_WORDS = {
    "1000000000000000": ["quadrillion"],
    "1000000000000000000": ["quintillion"],
}
```

### Custom Operators

```python
# eggcalc_config.py

CUSTOM_OPERATOR_WORDS = {
    "+": ["plus", "add", "and"],
    "-": ["minus", "subtract", "less"],
    "*": ["times", "multiplied by", "of"],
    "/": ["divided by", "over", "per"],
}
```

### Temperature Conversions

```python
# eggcalc_config.py

CUSTOM_TEMP_CONVERSIONS = {
    ("C", "R"): (1.0, 491.67),  # Celsius to Rankine
    ("F", "R"): (1.0, 459.67),  # Fahrenheit to Rankine
}
```

## Environment Variables

eggcalc does not read environment variables for calculator input length or cache size. MCP server mode supports `EGGCALC_MCP_PROFILE` and `EGGCALC_MCP_SCHEMA_DETAIL`; see [MCP Server](mcp.md) for those settings.

## Python Configuration

### Register at Runtime

```python
from eggcalc import (
    register_constant,
    register_function,
    EggCalcApp,
)

# Global registration
register_constant("my_const", 42)

def my_func(x):
    return x ** 2

register_function("mysquare", my_func)

# Per-instance (recommended for webapps)
app = EggCalcApp()
app.register_constant("my_const", 42)
app.register_function("mysquare", my_func)
```

### Modify Security Limits

```python
from eggcalc import (
    MAX_INPUT_LENGTH,
    MAX_NESTING_DEPTH,
    MAX_EXPONENT,
    MAX_FACTORIAL,
)

# Increase limits (use with caution)
import eggcalc.evaluator as ev
ev.MAX_EXPONENT = 100000
```

## Complete Example

```python
# eggcalc_config.py

# Custom constants
CUSTOM_CONSTANTS = {
    "earth_radius": 6371,
    "pi_approx": 3.14159,
}

# Custom functions
def circle_area(radius):
    import math
    return math.pi * radius ** 2

def sphere_volume(radius):
    import math
    return (4/3) * math.pi * radius ** 3

CUSTOM_FUNCTIONS = {
    "area": circle_area,
    "volume": sphere_volume,
}

# Custom units
CUSTOM_UNITS = {
    "m": {
        "nmi": 1852.0,
    },
}

# Custom aliases
CUSTOM_ALIASES = {
    "nautical_mile": "nmi",
}
```

## Security Considerations

- `eggcalc_config.py` is imported from the working directory
- In production, ensure this file is not user-writable
- Consider disabling config loading in high-security environments
- Only register trusted functions
