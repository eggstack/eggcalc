# Evaluator Semantics and Roadmap Closure Pass

Status: implemented  
Repository: `eggstack/eggcalc`  
Baseline reviewed: `ec7816d65658f17ca3040872201540beaef27bd1`  
Date: 2026-08-05  
Roadmap: `plans/022-correctness-simplification-and-footprint-roadmap.md`  
Depends on: `plans/023-cli-dispatch-and-trust-boundary-correction.md`, `plans/024-unit-aware-function-contracts-and-timeout-state-parity.md`, `plans/025-mcp-and-configuration-authority-consolidation.md`, `plans/026-measured-artifact-and-startup-footprint-reduction.md`

## 1. Purpose and disposition

Plans 023–026 have substantially landed. CLI mode selection and configuration trust boundaries are corrected, MCP/configuration authority is materially simpler, unit-aware function dispatch exists, timeout evaluation carries evaluator state, and the footprint pass reduced generated artifact size and eager startup allocation while retaining a standard-library-only runtime.

This is one narrow closure pass for the remaining semantic and verification gaps. It must:

1. correct variance result dimensions;
2. make `sign()` return a dimensionless result;
3. preserve Python's exact `round()` return semantics when `ndigits` is omitted;
4. distinguish canonical built-in callables from user overrides, including overrides that reuse a built-in name;
5. make timeout evaluation reject every unsupported custom callable rather than silently restoring a different built-in;
6. prevent the boolean angle marker from silently representing unsupported powers or inverse-angle dimensions;
7. remove transitional unit-policy machinery that no longer has an active role;
8. verify the deferred exact-import fix on Python 3.11;
9. update Plans 022–026 to accurate final statuses and close this roadmap.

This plan does not authorize another architectural phase. After these items pass focused tests, `make check`, and `make package-check`, the line of work is closed.

## 2. Governing constraints

The implementation must preserve:

- the current calculator, unit conversion, Python library, CLI, exact-tool, MCP, and generated single-file surfaces;
- all current MCP tool names, profiles, schemas, and protocol versions;
- runtime standard-library-only operation and an empty runtime dependency list;
- Python `>=3.11` support;
- the generated `eggcalc.py` distribution;
- the lazy confusables mapping, lazy unit-conversion adapter, and deferred MCP exact imports;
- the one-job required CI topology and manual-only compatibility workflow policy;
- manual PyPI publication;
- ordinary dimensionless behavior of existing functions;
- valid direct-angle and angular-velocity behavior already covered by Plan 024.

Do not:

- add any runtime dependency;
- redesign `Dimension` into a general rational-exponent or symbolic dimension system;
- add a plugin or function-policy registration framework;
- expand the supported function or MCP tool set;
- remove current features;
- reopen MCP server architecture or configuration design;
- replace the single-file distribution with a zipapp or binary;
- add benchmarks, benchmark gates, property-test frameworks, fuzz infrastructure, CI lanes, workflow artifacts, release evidence, automated publication, or GitHub Releases;
- introduce a second public function registry that can drift from `Evaluator.FUNCTIONS`;
- retain incorrect dimensional output for compatibility;
- perform unrelated formatting, dependency, or documentation cleanup.

## 3. Current residual defects

### 3.1 Variance returns the input unit instead of its square

`variance`, `var`, `variance_sample`, `vars`, and `var_sample` currently use the same `COMPATIBLE_REDUCER` handling as mean, standard deviation, minimum, maximum, median, and sum. The reducer converts operands to the first input unit and wraps the numeric result in that same unit. That is correct for mean and standard deviation but incorrect for variance.

Required semantics:

```text
variance(1*m, 2*m, 3*m)        -> UnitValue(..., "m**2")
variance(1*m, 200*cm, 3*m)     -> UnitValue(..., "m**2")
variance_sample(1*ft, 2*ft)    -> UnitValue(..., "ft**2")
std(1*m, 2*m, 3*m)             -> UnitValue(..., "m")
mean(1*m, 2*m, 3*m)            -> UnitValue(..., "m")
variance(1, 2, 3)               -> ordinary numeric result
```

Give the variance family a distinct bounded result-unit transform. A small `VARIANCE` policy or one explicit variance-family branch is acceptable. Do not create a general symbolic result-dimension framework.

Use the existing structural unit expression/power authority to square the first result unit. Do not concatenate unit strings when the validated unit structure can express the result.

Absolute affine temperature variance must not be mislabeled with an ordinary affine temperature unit. If the current unit model cannot correctly represent squared temperature-delta units, reject dimensional affine variance with a clear `EvaluationError`. Do not add a temperature-delta subsystem in this pass.

### 3.2 `sign()` incorrectly preserves physical units

The current `PRESERVE_SINGLE` assignment permits:

```text
sign(-5*m) -> -1 m
```

A sign is dimensionless. Required behavior:

```text
sign(-5*m) -> -1
sign(0*m)  -> 0
sign(5*m)  -> 1
sign(-5)   -> -1
```

The function may inspect a unit-valued magnitude but must return the ordinary scalar result without `UnitValue` wrapping. Use one explicit policy or branch; do not generalize this into an output-type framework.

### 3.3 Omitted `round()` precision is treated as explicit zero

Python distinguishes:

```python
round(3.7)     # 4, int
round(3.7, 0)  # 4.0, float
```

The current dispatcher substitutes `0` when `ndigits` is absent, changing the established return type. Equality-only tests do not detect this.

Required behavior:

```text
round(3.7)               -> 4, type int
round(3.7, 0)            -> 4.0, type float
round(3.7, ndigits=0)    -> 4.0, type float
round(3.14159, 2)        -> 3.14
round(3.7*m)             -> UnitValue(4, "m"), value type int
round(3.7*m, 0)          -> UnitValue(4.0, "m"), value type float
round(3.7*m, ndigits=0)  -> UnitValue(4.0, "m"), value type float
```

Implementation requirements:

- represent omitted `ndigits` with an internal sentinel or argument-count branch, not numeric zero;
- accept the existing positional form and the supported `ndigits=` keyword form;
- reject duplicate positional-and-keyword precision;
- reject unit-valued precision controls;
- preserve units only on the rounded value;
- retain normal conversion of call errors to `EvaluationError`.

### 3.4 Built-in-name overrides inherit stale built-in policies

Policy is selected by function name while invocation uses the callable currently stored in `self.FUNCTIONS[name]`. A user can replace a built-in name and receive the old built-in policy:

```python
ev = Evaluator()
ev.FUNCTIONS["sin"] = custom_callable
```

The governing invariant is:

> A built-in dimensional policy applies only while the active callable is the evaluator instance's canonical built-in callable for that name. Any added or replaced callable is a user callable and defaults to dimensionless-only behavior.

Establish one evaluator-owned canonical callable baseline after instance-specific built-ins have been bound. A suitable small design is:

```python
self.FUNCTIONS = self.__class__.FUNCTIONS.copy()
self._bind_instance_random()
self._builtin_function_baseline = dict(self.FUNCTIONS)
```

Equivalent naming is acceptable. Requirements:

- the baseline includes instance-bound random callables after `_bind_instance_random()`;
- it is private and not a second public registry;
- dispatch compares the active callable by identity with the evaluator's baseline;
- a canonical callable receives its built-in unit policy;
- an added name or replaced callable defaults to dimensionless-only;
- restoring the exact canonical callable restores built-in policy;
- canonical instance-bound random functions are not falsely classified as custom;
- `register_function(name, callable)` remains unchanged;
- direct instance mutation is detected at use time.

Example:

```python
ev = Evaluator()
ev.FUNCTIONS["sin"] = lambda x: x

ev.evaluate("sin(2)")       # allowed
ev.evaluate("sin(2*m)")     # EvaluationError: custom function is dimensionless-only
```

Do not infer policy from a name, module, annotation, signature, or source code.

### 3.5 Timeout detection checks names but not callable identity

`_snapshot_evaluator_state()` currently identifies custom functions by names absent from the class-level built-in mapping. An override using an existing built-in name is not detected. Timeout evaluation can therefore run a different callable from ordinary evaluation by reconstructing the original built-in in the child.

Required invariant:

> `evaluate_with_timeout()` must either reconstruct the same supported evaluator behavior or fail before spawning. It must never silently replace an active custom callable with another callable.

Use the evaluator-owned callable baseline from Section 3.4. Before spawning, unsupported callable state is either:

- a function name absent from the baseline; or
- a name present in the baseline whose active callable is not the exact baseline callable.

Raise `EvaluationError` listing affected names in stable sorted order.

Required cases:

```python
ev = Evaluator()
ev.FUNCTIONS["double"] = lambda x: x * 2
# timeout rejects added "double"

ev = Evaluator()
ev.FUNCTIONS["sin"] = lambda x: x
# timeout rejects overridden "sin"

ev = Evaluator(random_seed=1)
# timeout snapshot accepts canonical instance-bound random functions
```

Continue carrying supported constants, variables, memory values, and evaluator permission flags. Do not pickle arbitrary callables.

## 4. Workstream A — correct reducer result dimensions

### A1. Separate variance-family behavior

Inventory every true variance alias, including at minimum:

```text
variance
var
variance_sample
vars
var_sample
```

Assign those aliases to one explicit squared-result behavior.

Do not change:

- `std`, `std_sample`, and standard-deviation aliases: input unit remains first power;
- mean, median, mode, min, max, and sum: retain current compatible-unit behavior;
- dimensionless return values.

### A2. Common-unit conversion and result construction

For dimensional inputs:

1. require all values to be dimensional;
2. require compatible dimensions;
3. convert all values to the first input's display unit;
4. calculate variance with the existing numeric callable;
5. derive a squared structural unit from the first input unit;
6. return `UnitValue(result, squared_unit)`.

Mixed dimensional and dimensionless arguments remain errors.

### A3. Focused tests

Tests must verify numeric magnitude and exact unit dimension, not only `isinstance(UnitValue)`:

- same-unit population variance;
- mixed-scale population variance;
- sample variance;
- every variance alias returns squared units;
- standard deviation remains first-power;
- incompatible units fail;
- mixed dimensional/dimensionless values fail;
- dimensionless variance remains numeric;
- unsupported affine variance fails clearly if not representable.

## 5. Workstream B — correct scalar-output and rounding contracts

### B1. Dimensionless `sign`

Move `sign` out of `PRESERVE_SINGLE`. Its handler must:

- unwrap a `UnitValue` magnitude for comparison;
- return `-1`, `0`, or `1` without a unit;
- preserve dimensionless behavior;
- enforce normal arity checks.

### B2. Exact `round` invocation

Use explicit omitted-argument detection:

```python
if ndigits_was_omitted:
    result = round(value)
else:
    result = round(value, ndigits)
```

Do not use `kwargs.get("ndigits", 0)` or an equivalent numeric default.

### B3. Type-sensitive tests

Use `type(result) is int` and `type(result) is float` where required. For `UnitValue`, assert the type of `result.value`.

Cover:

- scalar omitted precision;
- scalar positional zero;
- scalar keyword zero;
- dimensional omitted precision;
- dimensional positional zero;
- dimensional keyword zero;
- duplicate precision rejection;
- dimensional precision rejection.

## 6. Workstream C — make callable identity authoritative

### C1. Establish the per-evaluator baseline

Capture canonical function identities only after instance-specific binding. The baseline must not change when `self.FUNCTIONS` is mutated.

### C2. Dispatch decision

Resolve calls in this order:

1. obtain the active callable from `self.FUNCTIONS`;
2. determine whether it is canonical for that evaluator and name;
3. apply built-in policy only when canonical;
4. otherwise apply user-callable dimensionless-only policy;
5. invoke the same callable that was classified.

The policy decision and invocation must refer to the same local callable to avoid check/use drift.

### C3. Tests

Add tests for policy-distinct names:

- override `sin`: no angle-policy leakage;
- override `round`: no preserve-unit or keyword-special-case leakage;
- override `variance`: no squared-unit-policy leakage;
- add `double`: dimensionless-only;
- restore canonical `sin`: angle policy returns;
- canonical random functions remain recognized after binding.

Use public registration where practical and direct instance mutation where needed to cover the path that escaped registration-time tracking.

## 7. Workstream D — close timeout parity

Update `_snapshot_evaluator_state()` to use the same callable-identity authority as ordinary dispatch.

Acceptance requirements:

- added callable fails before process creation;
- overridden built-in fails before process creation;
- errors list all affected names in sorted order;
- canonical built-ins, including bound random functions, are not false positives;
- constants, variables, memory, `allow_random`, and `allow_side_effects` still propagate;
- no callable is serialized;
- no child receives behavior different from the parent's active supported callable set.

Where practical, use a narrow process-start monkeypatch to prove rejection occurs before spawning. Do not create a multiprocessing test framework.

## 8. Workstream E — bound unsupported angle algebra

### E1. Preserve supported cases

These must remain valid:

```text
90*deg
1*rad
30*deg/s
5*rad/s
(30*deg/s) * (2*s)
deg/rad
```

Direct angles remain convertible and accepted by trig functions. Angular velocity remains a compound value rejected by trig until multiplied by time back to a direct angle.

### E2. Reject cases the boolean marker cannot represent

`Dimension.angle: bool` cannot encode angle exponents other than zero or one. Add bounded guards:

- angle-bearing dimension raised to `0` -> dimensionless;
- angle-bearing dimension raised to `1` -> unchanged;
- angle-bearing dimension raised to any other exponent -> clear error;
- multiplying two angle-bearing dimensions -> clear error;
- dividing a non-angle dimension by an angle-bearing dimension -> clear error because inverse angle is not representable;
- dividing angle-bearing by angle-bearing dimensions may produce dimensionless only when current structural operations establish complete compatibility/cancellation;
- multiplying or dividing one angle-bearing dimension by one non-angle dimension remains supported.

Implement at the narrowest shared structural operation boundary. Do not add an angle exponent field, rational dimensions, or symbolic simplifier.

### E3. Tests

Add direct and public-expression tests for:

```text
deg**0             -> dimensionless
deg**1             -> angle
deg**2             -> error
deg**-1            -> error
deg*rad            -> error
1/deg              -> error
deg/rad            -> dimensionless
(deg/s)*s          -> direct angle
(deg/s)*(rad/s)    -> error
sin(deg/s)         -> error
```

Prove errors are intentional semantic guards, not incidental parser failures.

## 9. Workstream F — remove transitional policy debris

While implementing the preceding work, remove only obsolete private machinery:

- `_DIMENSIONLESS_REQUIRED_FUNCTIONS`, if unused after centralized policy dispatch;
- `UnitPolicy.CUSTOM`, if it has no active meaning;
- `FunctionSpec.function`, which must either participate in callable identity authority or be removed;
- duplicate policy assignments such as repeated `expm1` classification;
- unused helpers/imports in `_sqrt_dispatch()`;
- direct `UnitExpression.__new__` plus `object.__setattr__` construction if the validated constructor can express the same result without expanding scope.

Rules:

- prefer deletion over compatibility wrappers for private unused names;
- do not reorganize the evaluator file wholesale;
- do not rename public functions or exceptions;
- do not perform unrelated style cleanup;
- policy machinery should become smaller or remain approximately neutral after correctness additions.

## 10. Workstream G — deferred import regression proof

Commit `ec7816d65658f17ca3040872201540beaef27bd1` changed MCP handler imports from package-level re-exports to explicit implementation submodules after Python 3.11 exposed module/function name collisions.

Add one compact regression proof that:

1. imports same-named `eggcalc.exact` submodules that populate package attributes;
2. constructs or starts the MCP tool surface;
3. invokes representative affected handlers, including `identifier_inspect` and one validation handler;
4. confirms the resolved object is callable and returns the expected envelope;
5. runs on Python 3.11 through the normal suite.

Prefer one parameterized test. Do not add an import-audit framework or eager-import inventory gate.

The optimization invariant remains:

- `import eggcalc.mcp` and `tools/list` do not eagerly import all exact implementation modules;
- first invocation imports only required implementation modules;
- explicit submodule imports avoid package attribute collisions.

## 11. Documentation and plan-state closure

Update existing documentation only where behavior changed:

- variance and `sign` in the unit-aware function contract;
- omitted versus explicit `round` precision if documented;
- bounded angle algebra limitations;
- timeout rejection of added and overridden callables;
- callable identity authority if documented in evaluator architecture.

Do not add a new architecture document.

After implementation and successful canonical verification, update status headers:

- Plan 022 -> `Status: completed`;
- Plan 023 -> `Status: implemented`;
- Plan 024 -> `Status: implemented`;
- Plan 025 remains `Status: implemented`;
- Plan 026 -> `Status: implemented`;
- Plan 027 -> `Status: implemented`.

Add a concise completion note to Plan 022 naming the implementation commit(s) for Plans 023–027. Do not create a registry, closure manifest, evidence JSON, benchmark record, or CI artifact.

## 12. Expected source scope

Expected primary files:

```text
eggcalc/evaluator.py
eggcalc/units.py                         # only if angle/unit-power guards belong here
tests/test_unit_aware_functions.py
an existing MCP-focused test module
existing evaluator/unit architecture documentation
plans/022-correctness-simplification-and-footprint-roadmap.md
plans/023-cli-dispatch-and-trust-boundary-correction.md
plans/024-unit-aware-function-contracts-and-timeout-state-parity.md
plans/025-mcp-and-configuration-authority-consolidation.md
plans/026-measured-artifact-and-startup-footprint-reduction.md
plans/027-evaluator-semantics-and-roadmap-closure.md
```

Files outside this list may change only when directly required for generated single-file parity, generated-document drift, or an existing focused test location.

Do not modify CI workflows, release procedures, dependencies, MCP schemas, tool counts, or package version.

## 13. Required focused tests

Before the full suite, run focused tests covering:

1. variance unit exponent and aliases;
2. standard-deviation unit preservation;
3. dimensionless `sign`;
4. type-sensitive `round` behavior;
5. built-in-name override policy isolation;
6. timeout rejection of added and overridden callables;
7. canonical random callable recognition;
8. supported and rejected angle algebra;
9. lazy exact-import module/function collision regression;
10. package/single-file parity for changed expressions.

If a parameterized single-file parity corpus already exists, extend it rather than creating another harness. Include at least:

```text
variance(1*m,2*m,3*m)
sign(-5*m)
round(3.7)
round(3.7*m)
sin(90*deg)
```

Override and timeout tests may remain package-only because arbitrary callable injection is not a CLI input surface.

## 14. Canonical verification

Run, in order:

```bash
python -m pytest <focused existing modules/cases> -q
make check
make package-check
```

Final requirements:

- focused tests pass on Python 3.11;
- `make check` passes without CI expansion;
- `make package-check` passes for wheel, sdist, installed console, installed MCP, generated single-file CLI, and generated single-file MCP surfaces;
- `build_single.py --validate` passes;
- generated documentation has no drift;
- runtime dependencies remain empty;
- the generated single-file artifact remains functional;
- no publication or release action occurs.

Do not add a permanent performance test. Plan 026 is retained if its lazy implementations remain and no correctness fix requires reverting them. Optional local spot measurements may be included in a commit message but are not acceptance gates.

## 15. Negative acceptance criteria

The pass is not complete if:

- dimensional variance retains the unsquared input unit;
- standard deviation is squared;
- `sign()` returns `UnitValue`;
- omitted `round` precision is replaced by numeric zero;
- a custom callable named `sin`, `round`, or `variance` inherits built-in policy;
- timeout silently substitutes a built-in for an overridden callable;
- canonical bound random functions are falsely rejected as custom;
- `deg**2`, `1/deg`, or `deg*rad` silently produce representable-looking dimensions;
- valid `deg/s` or `(deg/s)*s` behavior breaks;
- lazy imports reintroduce module/function collisions;
- all exact implementation modules load during MCP startup;
- obsolete policy machinery remains unused without a documented active reason;
- a runtime dependency is added;
- CI, release automation, or verification ceremony expands;
- plans are marked complete before canonical verification succeeds.

## 16. Final acceptance criteria

This pass is complete when:

1. Population and sample variance return squared units for compatible non-affine dimensional input.
2. Mean and standard deviation retain first-power units.
3. `sign()` always returns a dimensionless scalar.
4. Omitted and explicit `round` precision preserve Python value and type contracts for scalar and unit-valued input.
5. Each evaluator has one reliable canonical callable identity baseline established after instance binding.
6. Built-in policies apply only to canonical built-in callables.
7. Added and overridden callables default to dimensionless-only in ordinary evaluation.
8. Timeout rejects added and overridden callables before spawning and never substitutes behavior.
9. Canonical bound random functions remain valid.
10. Unsupported angle powers and inverse-angle operations fail clearly without redesigning dimensions.
11. Existing direct-angle and angular-velocity behavior remains functional.
12. Transitional policy debris is removed or made actively authoritative.
13. Deferred MCP imports remain lazy and survive Python 3.11 package/submodule collisions.
14. Focused tests, `make check`, and `make package-check` pass.
15. Runtime dependencies remain empty and standard-library-only operation is unchanged.
16. Required CI remains one Ubuntu/Python 3.11 job and release remains manual.
17. Plans 022–027 have accurate statuses and Plan 022 records final completion.
18. No further corrective plan is required for this roadmap.

## 17. Handoff sequence

Implement in this order:

1. add failing focused tests for variance, `sign`, `round`, overrides, timeout parity, and angle guards;
2. establish evaluator canonical callable identity authority;
3. correct dispatch and timeout detection using that authority;
4. correct variance, `sign`, and `round` semantics;
5. add bounded angle guards;
6. remove transitional private policy debris;
7. add the Python 3.11 deferred-import regression test;
8. run focused tests;
9. update existing documentation and plan statuses;
10. run `make check` and `make package-check`;
11. commit the implementation and stop.

Do not create another roadmap, follow-up plan, evidence commit, or release commit unless canonical verification exposes a new concrete product defect outside the acceptance criteria above.

## 18. Completion note

The original Plan 027 implementation is in commit `3b06d2a`; its final
verified corrective gaps were closed by Plan 028 in commit `53bf2dd`.
The roadmap is closed.
