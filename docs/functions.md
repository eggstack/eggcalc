# Functions

eggcalc supports a wide range of mathematical functions.

## Trigonometric

All trigonometric functions handle both real and complex arguments:

| Function | Description |
|----------|-------------|
| `sin(x)` | Sine (complex-aware) |
| `cos(x)` | Cosine (complex-aware) |
| `tan(x)` | Tangent (complex-aware) |
| `asin(x)` | Arcsine (complex-aware) |
| `acos(x)` | Arccosine (complex-aware) |
| `atan(x)` | Arctangent (complex-aware) |
| `atan2(y, x)` | Arctangent of y/x |

```bash
calc "sin(pi/2)"      # 1.0
calc "cos(0)"         # 1.0
calc "tan(pi/4)"      # 1.0
```

**Complex numbers work too:**

```bash
calc "sin(1+2j)"      # (3.165...+1.959i)
calc "log(-1)"        # 3.14159...j (πi)
```

## Hyperbolic

| Function | Description |
|----------|-------------|
| `sinh(x)` | Hyperbolic sine |
| `cosh(x)` | Hyperbolic cosine |
| `tanh(x)` | Hyperbolic tangent |
| `asinh(x)` | Inverse hyperbolic sine |
| `acosh(x)` | Inverse hyperbolic cosine |
| `atanh(x)` | Inverse hyperbolic tangent |

## Logarithmic & Exponential

| Function | Description |
|----------|-------------|
| `log(x)` | Natural logarithm |
| `ln(x)` | Natural logarithm (alias for `log`) |
| `log10(x)` | Base-10 logarithm |
| `log2(x)` | Base-2 logarithm |
| `log1p(x)` | log(1+x) |
| `exp(x)` | e^x |
| `expm1(x)` | e^x - 1 |

```bash
calc "log(e)"         # 1.0
calc "log10(100)"     # 2.0
calc "log2(8)"        # 3.0
calc "exp(1)"         # 2.718...
```

## Roots & Powers

| Function | Description |
|----------|-------------|
| `sqrt(x)` | Square root |
| `cbrt(x)` | Cube root |
| `pow(x, y)` | x^y |

```bash
calc "sqrt(16)"       # 4
calc "cbrt(27)"       # 3
calc "pow(2, 10)"     # 1024
```

## Rounding & Absolute

| Function | Description |
|----------|-------------|
| `abs(x)` | Absolute value |
| `floor(x)` | Floor |
| `ceil(x)` | Ceiling |
| `trunc(x)` | Truncate |
| `round(x, n)` | Round to n decimal places |
| `sign(x)` | Sign (-1, 0, or 1) |

```bash
calc "abs(-5)"        # 5
calc "floor(3.7)"     # 3
calc "ceil(3.2)"      # 4
calc "round(3.14159, 2)"  # 3.14
```

## Factorial & Combinatorics

| Function | Description |
|----------|-------------|
| `factorial(n)` | n! |
| `fact(n)` | n! (alias for `factorial`) |
| `gcd(a, b, ...)` | Greatest common divisor |
| `lcm(a, b, ...)` | Least common multiple |
| `perm(n, r)` | Permutations P(n,r) |
| `comb(n, r)` | Combinations C(n,r) |
| `nPr(n, r)` | Alias for perm |
| `nCr(n, r)` | Alias for comb |

```bash
calc "factorial(5)"   # 120
calc "gcd(12, 18)"    # 6
calc "lcm(4, 6)"      # 12
calc "perm(5, 3)"     # 60
calc "comb(5, 3)"     # 10
```

## Complex Numbers

| Function | Description |
|----------|-------------|
| `real(z)` | Real part |
| `imag(z)` | Imaginary part |
| `conj(z)` | Complex conjugate |
| `conjugate(z)` | Complex conjugate (alias) |
| `phase(z)` | Phase angle |
| `polar(z)` | Polar coordinates |
| `rect(r, phi)` | Rectangular form |

```bash
calc "sqrt(-1)"       # 1j
calc "abs(3+4i)"      # 5
calc "conj(3+4i)"     # 3-4j
```

## Statistics

| Function | Description |
|----------|-------------|
| `mean(x, ...)` | Arithmetic mean |
| `median(x, ...)` | Median |
| `mode(x, ...)` | Mode |
| `std(x, ...)` | Standard deviation |
| `variance(x, ...)` | Population variance |
| `var(x, ...)` | Population variance (alias) |
| `variance_sample(x, ...)` | Sample variance (n-1) |
| `vars(x, ...)` | Sample variance (alias for `variance_sample`) |
| `var_sample(x, ...)` | Sample variance (alias for `variance_sample`) |
| `sum(x, ...)` | Sum |
| `min(x, ...)` | Minimum |
| `max(x, ...)` | Maximum |

```bash
calc "mean(1, 2, 3, 4, 5)"      # 3.0
calc "median(1, 2, 3, 4)"       # 2.5
calc "std(1, 2, 3, 4, 5)"       # 1.414...
```

## Prime Numbers

| Function | Description |
|----------|-------------|
| `isprime(n)` | Check if prime |
| `is_prime(n)` | Check if prime (alias) |
| `primefactors(n)` | Prime factorization |
| `prime_factors(n)` | Prime factorization (alias for `primefactors`) |
| `nextprime(n)` | Next prime after n |
| `next_prime(n)` | Next prime after n (alias for `nextprime`) |
| `prevprime(n)` | Previous prime before n |
| `prev_prime(n)` | Previous prime before n (alias for `prevprime`) |

```bash
calc "isprime(17)"    # True
calc "primefactors(84)"  # "2^2 × 3 × 7"
calc "nextprime(17)"  # 19
```

## Random

| Function | Description |
|----------|-------------|
| `random()` | Random float [0, 1) |
| `randint(a, b)` | Random integer [a, b] |
| `randrange(a, b)` | Random integer [a, b) |
| `uniform(a, b)` | Random float [a, b] |
| `randn()` | Standard normal |
| `gauss(mu, sigma)` | Normal distribution |
| `seed(n)` | Set random seed |

```bash
calc "seed(42); random()"  # Reproducible random
calc "randint(1, 100)"     # Random 1-100
```

## Bitwise

| Function | Description |
|----------|-------------|
| `bitand(a, b)` | Bitwise AND |
| `bitor(a, b)` | Bitwise OR |
| `bitxor(a, b)` | Bitwise XOR |
| `bitnot(a)` | Bitwise NOT |
| `bitlshift(a, b)` | Left shift (a << b) |
| `bitrshift(a, b)` | Right shift (a >> b) |
| `bin(n)` | Binary string |
| `hex(n)` | Hexadecimal string |
| `oct(n)` | Octal string |

```bash
calc "bitand(5, 3)"   # 1
calc "bin(10)"        # '0b1010'
calc "hex(255)"       # '0xff'
```

## Memory

| Function | Description |
|----------|-------------|
| `store(x)` | Store in memory |
| `recall()` | Recall from memory |
| `MR` | Alias for recall |
| `M` | Alias for recall (memory register) |
| `Mplus(x)` | Add to memory |
| `Mminus(x)` | Subtract from memory |
| `MC` | Clear memory |

```bash
calc "store(42)"      # 42
calc "recall()"       # 42
calc "Mplus(8)"       # 50
```

## Variables

| Function | Description |
|----------|-------------|
| `setvar(name, value)` | Set variable |
| `getvar(name)` | Get variable |
| `delvar(name)` | Delete variable |
| `listvars()` | List all variables |
| `clearvars()` | Clear all variables |

```bash
calc 'setvar("x", 10)'
calc "x + 5"          # 15
```

## Operators

eggcalc supports standard arithmetic, power, bitwise, floor division, and modulo operators. Operator semantics differ between the direct `evaluate()` function and the user-facing `evaluate_raw()` / CLI pipeline.

### Arithmetic

| Operator | Description | Example |
|----------|-------------|---------|
| `+` | Addition | `5 + 3` → `8` |
| `-` | Subtraction | `5 - 3` → `2` |
| `*` | Multiplication | `5 * 3` → `15` |
| `/` | Division | `10 / 3` → `3.333...` |

### Power (`^` / `**`)

The caret (`^`) has different semantics depending on the evaluation path:

**`evaluate()` (direct AST evaluation):**

- `^` is **bitwise XOR** (Python semantics): `5 ^ 3` → `6`
- `**` is exponentiation: `2 ** 10` → `1024`

**`evaluate_raw()` and CLI (user-facing):**

- `^` is **rewritten to `**`** (exponentiation): `2 ^ 10` → `1024`
- `**` is exponentiation: `2 ** 10` → `1024`
- Malformed caret sequences (`^^`, `^*`, `*^`) are rejected

```bash
calc "2 ^ 10"          # 1024 (caret = exponentiation)
calc "2 + 3 ^ 2"       # 11 (^ has higher precedence)
calc "2 ^ 3 ^ 2"       # 512 (right-associative)
```

To perform bitwise XOR through the user-facing pipeline, use the `xor` or `bitxor` word forms:

```bash
calc "5 xor 3"         # 6
calc "5 bitxor 3"      # 6
```

### Bitwise XOR (direct `evaluate()`)

When using `evaluate()` directly, `^` is bitwise XOR:

```python
from eggcalc import evaluate
evaluate("5 ^ 3")      # 6 (bitwise XOR)
evaluate("2 ** 10")    # 1024 (exponentiation)
```

### Floor Division

| Operator | Description |
|----------|-------------|
| `//` | Floor division |

For plain numbers, `//` returns the floor quotient:

```bash
calc "7 // 2"          # 3
```

For quantities, floor division returns a **dimensionless** result:

```bash
calc "6 m // 3 m"      # 2
calc "1 m // 30 cm"    # 3 (converts to same unit first)
```

Incompatible units are rejected:

```bash
calc "5 m // 2 s"      # Error (incompatible dimensions)
```

### Modulo

| Operator | Description |
|----------|-------------|
| `%` | Modulo (remainder) |

For plain numbers, `%` returns the remainder:

```bash
calc "10 % 3"          # 1
```

For quantities, modulo returns a result **in the divisor unit**:

```bash
calc "5 m % 2 m"       # 1 m
calc "1 m % 30 cm"     # 10 cm (converts to divisor unit)
```

Incompatible units are rejected:

```bash
calc "5 m % 2 s"       # Error (incompatible dimensions)
```

### Precedence

Operators follow standard mathematical precedence:

1. `()` — Parentheses
2. `**` / `^` — Power (right-associative)
3. `*`, `/`, `//`, `%` — Multiplicative
4. `+`, `-` — Additive

```bash
calc "2 + 3 * 4"       # 14 (multiplication first)
calc "(2 + 3) * 4"     # 20 (parentheses override)
calc "2 + 3 ^ 2"       # 11 (power before addition)
calc "2 * 3 ^ 2"       # 18 (power before multiplication)
```

## Utility

| Function | Description |
|----------|-------------|
| `clamp(x, lo, hi)` | Clamp value in range [lo, hi] |
| `hypot(x, y, ...)` | Hypotenuse sqrt(x^2 + y^2 + ...) |
| `percentof(p, total)` | p% of total (p/100 * total) |
| `percent_of(p, total)` | p% of total (alias for `percentof`) |
| `aspercent(x, total)` | x as percentage of total (x/total * 100) |
| `as_percent(x, total)` | x as percentage of total (alias for `aspercent`) |
| `temp(value, from_unit, to_unit)` | Temperature conversion |
| `degrees(x)` | Radians to degrees |
| `radians(x)` | Degrees to radians |

```bash
calc "clamp(15, 0, 10)"       # 10
calc "hypot(3, 4)"            # 5.0
calc "percentof(20, 100)"    # 20.0 (20% of 100)
calc "aspercent(25, 100)"    # 25.0 (25 as % of 100)
calc "degrees(pi)"           # 180.0
calc "radians(180)"          # 3.14159...
calc "temp(100, C, F)"       # 212.0 (C to F)
```
