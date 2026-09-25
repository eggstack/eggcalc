# Unit-Aware Function Contracts and Timeout State Parity

Status: implemented  
Repository: `eggstack/eggcalc`  
Baseline reviewed: `8515579e9e64fcb49a3e5b46ac4f0c47e77d8ff1`  
Date: 2026-07-31  
Roadmap: `plans/022-correctness-simplification-and-footprint-roadmap.md`  
Depends on: `plans/023-cli-dispatch-and-trust-boundary-correction.md`

## 1. Purpose

Correct evaluator behavior where function calls silently unwrap `UnitValue` arguments to plain numbers, define bounded dimensional contracts for the existing function set, align timeout evaluation with ordinary evaluator state, and reject invalid custom-unit category declarations.

This plan preserves the current calculator and unit feature set. It does not introduce symbolic algebra, arbitrary dimensional analysis, a new parser, or a physics package.

## 2. Governing constraints

The implementation must preserve:

- current expression syntax;
- current built-in function names and aliases;
- existing valid unit arithmetic and conversions;
- ordinary numeric behavior for dimensionless inputs;
- package, CLI, MCP, async, cached, timeout, and single-file surfaces;
- registered constants, functions, variables, and memory APIs;
- standard-library-only runtime;
- Python `>=3.11` support.

Do not:

- add SymPy, Pint, NumPy, SciPy, Decimal-based external packages, or any runtime dependency;
- redesign `Dimension` into a general tensor/unit algebra unless a narrowly required representation correction is unavoidable;
- add automatic dimensional inference for arbitrary user functions;
- silently preserve invalid results for compatibility;
- add dozens of per-function wrapper classes;
- duplicate the function registry into a second metadata table that can drift;
- create a benchmark or property-testing framework;
- add CI lanes or release evidence.

## 3. Current defect

`Evaluator.visit_Call()` applies explicit unit rejection only to a limited deny-list. For most other functions, a `UnitValue` argument is replaced by its numeric `.value` before invocation.

This creates plausible but incorrect results, for example:

```text
sqrt(4*m)       -> 2, meter dimension lost
sin(90*deg)     -> sin(90 radians), not 1
mean(1*m, 1*s)  -> 1, incompatible dimensions ignored
log(5*kg)       -> log(5), mass discarded
hypot(3*m, 4*s) -> 5, incompatible dimensions ignored
```

The correct default is fail-closed: a function without an explicit unit contract must reject dimensional arguments rather than strip dimensions.

## 4. Target design — one function registry with dimensional policy

Extend the existing built-in function registry so each callable has one colocated dimensional policy.

The implementation may use a frozen dataclass, enum plus metadata mapping, or a compact tuple. The important requirement is one authority.

A suitable conceptual model is:

```python
class UnitPolicy(Enum):
    DIMENSIONLESS = auto()
    ANGLE_INPUT = auto()
    ANGLE_OUTPUT = auto()
    PRESERVE_SINGLE = auto()
    COMPATIBLE_REDUCER = auto()
    ROOT = auto()
    HYPOT = auto()
    CUSTOM = auto()

@dataclass(frozen=True)
class FunctionSpec:
    function: Callable[..., object]
    unit_policy: UnitPolicy
```

The exact categories may differ. Do not create a complex type hierarchy.

Every built-in function exposed by the evaluator must have an explicit policy. Registered user functions default to dimensionless-only unless the public registration API already supports metadata. Do not infer safety from a function name.

## 5. Workstream A — inventory and classify existing functions

### A1. Build the inventory from the current registry

List every current built-in function and assign it to one policy.

The inventory belongs in code near the callable, not in a separate generated document.

At minimum, classify the following behavior families.

### A2. Dimensionless-only functions

Functions that are mathematically defined only for pure numbers must reject dimensional `UnitValue` arguments.

Typical examples include:

```text
log, log10, log2
exp, expm1
sinh, cosh, tanh
asinh, acosh, atanh
gamma, lgamma
erf, erfc
factorial, comb, perm, gcd, lcm
bitwise/integer-only helpers where applicable
```

The exact list must come from the repository's registry.

Boolean and integer-domain validation remains separate from unit validation.

### A3. Angle-input functions

Trigonometric functions must accept:

- dimensionless numeric inputs, interpreted as radians for backward compatibility;
- angle-valued inputs, converted to radians before calling `math`;
- no other dimensions.

Typical examples:

```text
sin, cos, tan
```

For an angle `UnitValue`, conversion must use the unit engine rather than treating the stored display value as radians.

Required behavior examples:

```text
sin(pi / 2)     -> 1
sin(90*deg)     -> 1
cos(180*deg)    -> -1
sin(1*m)        -> EvaluationError
```

### A4. Angle-output functions

Inverse trigonometric functions accept dimensionless inputs and return their existing numeric result in radians unless the current public API already returns an angle `UnitValue`.

Typical examples:

```text
asin, acos, atan, atan2
```

Do not introduce a new output wrapper merely for theoretical purity if that would break the established numeric API.

`atan2(y, x)` must require compatible dimensions when either argument is dimensional. Compatible units are converted to a common basis before computing the ratio. Mixed dimensional/dimensionless arguments are rejected unless both are dimensionless.

Examples:

```text
atan2(1, 1)        -> pi/4
atan2(1*m, 100*cm) -> pi/4
atan2(1*m, 1*s)    -> EvaluationError
atan2(1*m, 1)      -> EvaluationError
```

### A5. Unit-preserving single-value transforms

Functions that transform magnitude without changing physical dimension should preserve the unit representation where practical.

Candidates may include:

```text
abs
round
floor
ceil
trunc
```

The implementation must respect return-type expectations.

For example, if `floor(UnitValue)` currently or naturally returns an integer, wrapping the integer in `UnitValue` may be a public change. Choose and document a consistent rule based on current API contracts.

Preferred rule:

- `abs` preserves `UnitValue`;
- `round` preserves `UnitValue` when called through the evaluator;
- integer-returning functions either preserve a unit-valued integral magnitude or reject dimensional input if preserving type would violate an established API.

Do not silently strip the unit.

### A6. Compatible-unit reducers

Functions that combine comparable quantities must require dimensional compatibility and convert operands to a common unit.

Candidates may include:

```text
min
max
mean or average helpers
median where present
sum-like helpers where present
```

Use the first dimensional argument's display unit as the result unit unless the existing unit engine has a canonical output rule.

Rules:

- all arguments dimensionless -> existing numeric behavior;
- all dimensional and compatible -> convert, compute, return `UnitValue`;
- mixed dimensionless/dimensional -> reject;
- incompatible dimensions -> reject;
- empty-input behavior remains whatever the existing function defines.

Examples:

```text
mean(1*m, 100*cm) -> 1 m
min(1*m, 3*ft)    -> compatible UnitValue
mean(1*m, 1*s)    -> EvaluationError
mean(1*m, 1)      -> EvaluationError
```

### A7. Root functions

`sqrt` must not discard dimensions.

Implement bounded square-root support using the existing structural unit representation:

- dimensionless input -> existing numeric result;
- dimensional input whose unit-factor exponents are all even -> halve exponents and return a `UnitValue`;
- dimensional input without an exact representable square root -> reject clearly;
- negative real input behavior remains consistent with the current evaluator's real/complex policy.

Examples:

```text
sqrt(4)       -> 2
sqrt(4*m**2)  -> 2 m
sqrt(9*m**2/s**2) -> 3 m/s
sqrt(4*m)     -> EvaluationError
```

Do not add fractional unit exponents in this phase.

If current normalization cannot express the compound examples, test the nearest public equivalent and add direct unit-structure tests.

Other root functions, if exposed, must receive explicit equivalent rules or reject dimensional input.

### A8. Hypotenuse and norm-like functions

`hypot` must require all dimensional arguments to be compatible.

Rules:

- all dimensionless -> existing numeric result;
- all dimensional and compatible -> convert to a common unit, compute, return `UnitValue`;
- mixed or incompatible -> reject.

Example:

```text
hypot(3*m, 400*cm) -> 5 m
hypot(3*m, 4*s)    -> EvaluationError
```

### A9. Powers and logarithm-with-base helpers

Any function-form power helper must apply the same dimensional restrictions as the evaluator's power operator.

A dimensional base may only be raised according to the existing bounded exponent rules. A dimensional exponent is always invalid.

Logarithm helpers remain dimensionless-only even when a base is supplied.

### A10. Unknown and registered functions

The default for any function without explicit metadata is:

- accept dimensionless values according to existing callable behavior;
- reject `UnitValue` arguments with a clear error;
- never unwrap units silently.

If `register_function()` is public and currently accepts only `(name, callable)`, preserve that signature.

Optional metadata may be added only as a backward-compatible keyword if there is a concrete use case and the implementation remains small. It is acceptable for all user-registered functions to remain dimensionless-only in this phase.

## 6. Workstream B — implement centralized argument handling

### B1. One unit-policy dispatcher

Add one private helper that applies the policy before invoking the callable.

Conceptual shape:

```python
def _call_with_unit_policy(
    spec: FunctionSpec,
    args: list[object],
    kwargs: dict[str, object],
) -> object:
    ...
```

`visit_Call()` should:

1. resolve the function spec;
2. evaluate arguments;
3. delegate unit handling to the helper;
4. convert policy errors into the evaluator's public error type.

Do not scatter `isinstance(UnitValue)` branches across every function registration.

### B2. Keyword arguments

Unit policy must apply to positional and keyword values.

If a built-in function accepts keyword-only numeric controls such as `ndigits`, those control parameters must remain dimensionless and type-checked separately.

Do not treat every keyword as a physical quantity.

### B3. Error messages

Errors should name:

- the function;
- the unsupported dimension or incompatible units where practical;
- the expected category, such as dimensionless or compatible units.

Avoid leaking internal dataclass representations.

Suggested form:

```text
log() requires a dimensionless argument; received kg
mean() requires compatible units; received length and time
sqrt() cannot represent the square root of unit m with integer exponents
```

## 7. Workstream C — bounded angle-model correction

### C1. Preserve current dimension representation where possible

The current angle marker is limited. This plan does not authorize a general dimension-system rewrite.

Use existing angle-category/unit metadata for direct angle values such as degrees and radians.

### C2. Reject unsupported compound-angle dimensions

If the current `Dimension.angle` boolean cannot faithfully represent compound angle dimensions such as angular velocity, do not rely on XOR/parity behavior to produce a misleading result.

Add explicit validation at the construction or operation boundary so unsupported compound-angle cases are rejected or represented as ordinary dimension factors only if that is already supported correctly.

Examples requiring a defined outcome:

```text
deg / s
rad / s
(deg / s) * s
```

The preferred bounded outcome for this phase is:

- direct angles are supported for conversion and trig input;
- unsupported compound-angle arithmetic raises a clear error;
- no false dimensionless cancellation occurs because of boolean parity.

If the existing structural `UnitExpression` can already represent these cases correctly without redesign, use that representation and add tests.

### C3. Acceptance criteria

- degrees are converted to radians for trig functions;
- non-angle dimensions are rejected by trig functions;
- compound-angle behavior is explicit and tested;
- no broad fractional-dimension model is introduced.

## 8. Workstream D — timeout evaluator state parity

### D1. Define the public contract

`evaluate_with_timeout()` must not silently evaluate under a materially different environment from ordinary evaluation.

Supported state should include, where present in the evaluator instance or public application object:

- numeric/string/bool registered constants;
- variables;
- memory/register values;
- built-in function registry and policies;
- evaluator flags such as random/side-effect permissions;
- custom units that are representable by the existing config model.

### D2. Multiprocessing-safe snapshot

Create one explicit, immutable, serialization-safe state snapshot for timeout workers.

Use only standard-library and pickle-compatible values.

Suggested contents:

```text
constants: plain mapping of supported scalar values
variables: plain mapping of supported scalar or UnitValue values
memory: plain mapping/list state
flags: primitive booleans/integers/strings
custom unit specs: declarative records
```

Do not pass live locks, contexts, bound methods, mapping proxies, or evaluator objects across the process boundary.

### D3. Custom functions

Arbitrary registered callables may not be safely serializable under spawn.

The implementation must choose explicit behavior:

- built-in functions are always available in the worker;
- registered functions that can be represented by an existing approved symbolic identifier may be restored;
- arbitrary custom callables that cannot be serialized cause `evaluate_with_timeout()` to fail immediately with a clear unsupported-state error;
- ordinary `evaluate()` remains able to use those callables.

Do not silently omit custom functions.

Do not switch to `fork` to avoid defining state semantics; Windows and spawn compatibility must remain intact.

### D4. Worker reconstruction

The worker should construct a fresh evaluator, then apply the validated snapshot through existing registration/state APIs where possible.

Avoid a second private state mutation path that bypasses validation.

### D5. Documentation correction

Update the timeout API documentation and examples.

Remove any example that uses unsupported AST constructs such as list comprehensions or `range()` if those constructs are not accepted by the evaluator.

Provide an example that demonstrates a genuinely long or bounded expression supported by the grammar.

Document the custom-callable limitation explicitly.

### D6. Tests

Verify parity for:

```text
registered scalar constant
variable
memory/register value
custom unit if supported
allow-random/side-effect flags
ordinary built-in function
```

Verify explicit failure for an unsupported registered callable.

Verify timeout termination still works and no child process is leaked.

### D7. Acceptance criteria

- ordinary and timeout evaluation agree for supported state;
- unsupported state fails clearly before returning a misleading result;
- spawn remains the portable process model;
- no third-party serialization package is added;
- documentation matches supported syntax and state behavior.

## 9. Workstream E — custom unit category validation

### E1. Current issue

Custom unit registration can accept an explicit category separately from a base unit. Validation checks whether the category is known but may not enforce that the category matches the base unit's dimension.

This allows a unit based on length to be labeled as time or another incompatible category.

### E2. Required rule

Prefer inheriting category from the base unit.

If the public API accepts an explicit category for compatibility:

- normalize it through the existing category aliases;
- derive the base unit's dimension/category;
- require exact semantic consistency;
- reject a mismatch with `ValueError` or the existing config error type;
- preserve valid same-category aliases.

Do not create a second category taxonomy.

### E3. Tests

Add cases for:

- valid inherited category;
- valid explicit matching category;
- invalid explicit mismatched category;
- unknown category;
- base compound unit where category is not singular, if supported;
- package and single-file parity for custom-unit registration if the surface is included in single-file tests.

### E4. Acceptance criteria

- invalid category/dimension combinations cannot be registered;
- existing valid custom units remain valid;
- category derivation has one authority;
- no new unit category is introduced.

## 10. Files expected to change

Primary:

```text
eggcalc/evaluator.py
eggcalc/units.py
tests/test_evaluator.py
tests/test_units.py
```

Possible:

```text
eggcalc/_protocol.py
eggcalc/__init__.py
eggcalc/mcp/server.py
docs/architecture/evaluator.md
docs/architecture/units.md
README.md
AGENTS.md
build_single.py
```

`build_single.py` should change only if new runtime metadata must be included in its existing manifest/rewriting rules. Avoid new special cases.

Do not refactor MCP registry/configuration internals in this phase except for a minimal adaptation needed to consume corrected evaluator behavior.

## 11. Focused test matrix

The implementation should add a compact table-driven test set covering at least:

| Family | Dimensionless | Compatible units | Incompatible units | Mixed scalar/unit |
|---|---|---|---|---|
| trig input | pass | direct angle pass | reject | n/a |
| logarithm | pass | reject | reject | n/a |
| reducer | pass | pass | reject | reject |
| hypot | pass | pass | reject | reject |
| sqrt | pass | exact square pass | non-square reject | n/a |
| abs/round | pass | preserve or defined reject | n/a | n/a |
| atan2 | pass | compatible pass | reject | reject |

Do not create exhaustive tests for every alias when aliases share one registry spec. Test one representative alias plus registry completeness.

Add one registry-completeness test asserting every exposed built-in function has a unit policy.

## 12. Verification

Suggested focused commands:

```text
python -m pytest tests/test_evaluator.py -q
python -m pytest tests/test_units.py -q
python -m pytest tests/test_mcp_server.py -q -k math
python -m pytest tests/test_single_file.py -q
python build_single.py --validate
```

Final required verification:

```text
make check
make package-check
```

The manual Windows compatibility workflow is useful for the timeout/spawn portion but remains optional and non-required.

## 13. Explicit negative tests

The implementation is incomplete unless tests prove that these no longer return a plausible unitless number:

```text
sqrt(4*m)
log(5*kg)
mean(1*m, 1*s)
hypot(3*m, 4*s)
sin(1*m)
atan2(1*m, 1*s)
```

It must also prove:

- `sin(90*deg)` uses degree conversion;
- timeout evaluation does not lose a registered scalar constant;
- timeout evaluation does not silently omit an unsupported custom callable;
- a length-derived custom unit cannot be registered as a time category;
- unsupported compound-angle behavior is rejected or correctly represented.

## 14. Final acceptance criteria

This plan is complete when:

1. every built-in function has an explicit dimensional policy;
2. unknown/user functions default to rejecting dimensional arguments;
3. no function silently unwraps `UnitValue` by default;
4. direct angle values are correctly converted for trig functions;
5. compatible reducers and `hypot` preserve a meaningful result unit;
6. incompatible or mixed dimensions fail clearly;
7. square root preserves exactly representable integer-exponent units and rejects unsupported roots;
8. angle-model limitations are explicit and tested;
9. timeout evaluation reconstructs supported evaluator state;
10. unsupported custom callables fail explicitly under timeout evaluation;
11. custom unit category/dimension mismatches are rejected;
12. all existing valid numeric and unit tests continue to pass;
13. package, MCP, CLI, and single-file surfaces inherit the corrected behavior;
14. runtime remains standard-library-only;
15. no symbolic math framework, dependency, CI expansion, or unrelated feature work is introduced;
16. `make check` and `make package-check` pass.

After these conditions are met, stop. Do not extend this plan into general symbolic dimensional analysis, fractional unit exponents, arbitrary callable serialization, or new scientific functions.
