# Evaluator Semantics and Roadmap Closure Pass

Status: implementation handoff  
Repository: `eggstack/eggcalc`  
Baseline reviewed: `ec7816d65658f17ca3040872201540beaef27bd1`  
Date: 2026-08-05  
Roadmap: `plans/022-correctness-simplification-and-footprint-roadmap.md`  
Depends on: `plans/023-cli-dispatch-and-trust-boundary-correction.md`, `plans/024-unit-aware-function-contracts-and-timeout-state-parity.md`, `plans/025-mcp-and-configuration-authority-consolidation.md`, `plans/026-measured-artifact-and-startup-footprint-reduction.md`

## 1. Purpose and disposition

Plans 023–026 have substantially landed. CLI mode selection and configuration trust boundaries are corrected, MCP/configuration authority is materially simpler, unit-aware function dispatch exists, timeout evaluation carries evaluator state, and the footprint pass reduced generated artifact size and eager startup allocation while retaining a standard-library-only runtime.

This is one narrow closure pass for the remaining semantic and evidence gaps. It must:

1. correct variance result dimensions;
2. make `sign()` return a dimensionless result;
3. preserve Python's exact `round()` return semantics when `ndigits` is omitted;
4. distinguish canonical built-in callables from user overrides, including overrides that reuse a built-in name;
5. make timeout evaluation reject every unsupported custom callable rather than silently restoring a different built-in;
6. prevent the boolean angle marker from silently representing unsupported powers or inverse-angle dimensions;
7. remove transitional unit-policy machinery that no longer has an active role;
8. verify the deferred exact-import fix on Python 3.11;
9. update Plans 022–026 to their accurate final statuses and close this roadmap.

This plan does not authorize another architectural phase. After these items pass focused tests, `make check`, and `make package-check`, the line of work is closed.

## 2. Governing constraints

The implementation must preserve:

- the current public calculator, unit conversion, Python library, CLI, exact-tool, MCP, and generated single-file surfaces;
- all current tool names, profiles, schemas, and protocol versions;
- runtime standard-library-only operation;
- Python `>=3.11` support;
- the current generated `eggcalc.py` distribution;
- the current lazy confusables mapping, lazy unit-conversion adapter, and deferred MCP exact imports;
- the current one-job required CI topology;
- optional/manual compatibility workflow policy;
- manual PyPI publication;
- ordinary dimensionless behavior of existing mathematical functions;
- valid direct-angle and angular-velocity examples already covered by Plan 024.

Do not:

- add a runtime or optional runtime dependency;
- redesign `Dimension` into a general rational-exponent or symbolic dimension system;
- add a plugin framework or function-policy registration framework;
- expand the supported function set;
- remove current product features;
- reopen MCP server architecture or configuration design;
- replace the generated single-file distribution with a zipapp or binary;
- add benchmarks, benchmark gates, property-test frameworks, fuzz infrastructure, CI lanes, workflow artifacts, release evidence, automated publication, or GitHub Releases;
- introduce a second function registry that can drift from `Evaluator.FUNCTIONS`;
- retain incorrect dimensional output for compatibility;
- perform unrelated formatting, documentation, or dependency cleanup.

## 3. Current residual defects

### 3.1 Variance is returned in the input unit instead of the squared unit

`variance`, `var`, `variance_sample`, `vars`, and `var_sample` currently use the same `COMPATIBLE_REDUCER` handling as `mean`, `median`, standard deviation, `min`, `max`, and `sum`.

That generic reducer converts compatible operands to the first input unit and wraps the numeric result in that same unit. This is correct for mean and standard deviation but incorrect for variance.

Required semantics:

```text
variance(1*m, 2*m, 3*m)        -> UnitValue(..., "m**2")
variance(1*m, 200*cm, 3*m)     -> UnitValue(..., "m**2")
variance_sample(1*ft, 2*ft)    -> UnitValue(..., "ft**2")
std(1*m, 2*m, 3*m)             -> UnitValue(..., "m")
mean(1*m, 2*m, 3*m)            -> UnitValue(..., "m")
variance(1, 2, 3)               -> ordinary numeric result
```

The implementation must give variance a distinct bounded result-unit transform. A small `VARIANCE` policy or one explicit variance-family branch is acceptable. Do not create a generic symbolic result-dimension framework.

Use the existing structural unit expression/power authority to square the first result unit. Do not concatenate strings when the unit engine already provides a validated expression operation.

Absolute affine temperature variance must not be silently labeled with an ordinary affine temperature unit. If the existing unit engine cannot correctly represent a squared temperature-delta unit through its current public structures, reject that dimensional variance with a clear `EvaluationError`. Do not add a new temperature-delta subsystem in this pass.

### 3.2 `sign()` incorrectly preserves physical units

The current `PRESERVE_SINGLE` assignment makes results such as the following possible:

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

The function may inspect a unit-valued magnitude, but it must return the same scalar type/shape that ordinary `sign()` returns and must not wrap that result in `UnitValue`.

Use a small explicit policy or branch. Do not generalize this into an output-type framework.

### 3.3 Omitted `round()` precision is being treated as explicit zero

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
- accept the existing positional form and the newly supported `ndigits=` keyword form;
- reject duplicate positional-and-keyword `ndigits` in the same manner as an ordinary invalid call;
- reject a unit-valued `ndigits` control argument as dimensionally invalid;
- preserve units only on the rounded value, never on the precision control;
- retain existing error conversion to `EvaluationError`.

### 3.4 Built-in-name overrides inherit stale built-in dimensional policies

Unit policy is currently selected by function name while invocation uses the callable currently stored in `self.FUNCTIONS[name]`. A user can replace a built-in name and receive the old built-in policy:

```python
ev = Evaluator()
ev.FUNCTIONS["sin"] = custom_callable
```

The custom callable can then be treated as angle-aware merely because it occupies the name `sin`.

The governing invariant is:

> A built-in dimensional policy applies only while the active callable is the evaluator instance's canonical built-in callable for that name. Any added or replaced callable is a user callable and defaults to dimensionless-only behavior.

Implement one evaluator-owned canonical callable baseline after instance-specific built-ins have been bound. A suitable small design is:

```python
self.FUNCTIONS = self.__class__.FUNCTIONS.copy()
self._bind_instance_random()
self._builtin_function_baseline = dict(self.FUNCTIONS)
```

Equivalent naming is acceptable. The requirements are:

- the baseline includes instance-bound random callables after `_bind_instance_random()`;
- it is private and not exposed as a second public registry;
- call dispatch determines whether the active callable is canonical by identity against that evaluator's baseline;
- a canonical callable uses its built-in unit policy;
- an added name or replaced callable defaults to dimensionless-only;
- replacing a callable and later restoring the exact canonical callable restores the built-in policy;
- instance-bound random functions are not falsely classified as custom;
- the public `register_function(name, callable)` signature remains unchanged;
- direct instance mutation remains correctly detected because detection occurs at use/snapshot time rather than only inside `register_function()`.

Examples:

```python
ev = Evaluator()
ev.FUNCTIONS["sin"] = lambda x: x

ev.evaluate("sin(2)")       # allowed
nev.evaluate("sin(2*m)")     # EvaluationError: custom function is dimensionless-only
```

Do not infer policy from function names, module names, annotations, signatures, or callable source.

### 3.5 Timeout custom-callable detection checks names but not callable identity

`_snapshot_evaluator_state()` currently identifies custom functions by names absent from the class-level built-in mapping. An override using an existing built-in name is not detected. Timeout evaluation can therefore run a different callable from ordinary evaluation by reconstructing the original built-in in the child.

Required invariant:

> `evaluate_with_timeout()` must either reconstruct the same supported evaluator behavior or fail before spawning. It must never silently replace an active custom callable with another callable.

Use the evaluator-owned canonical callable baseline from Section 3.4.

Before spawning, identify unsupported callable state as:

- a function name absent from the baseline; or
- a function name present in the baseline whose active callable is not the exact baseline callable.

If either condition exists, raise `EvaluationError` listing the affected names in stable sorted order.

Required tests:

```python
ev = Evaluator()
ev.FUNCTIONS["double"] = lambda x: x * 2
# timeout rejects "double"

ev = Evaluator()
ev.FUNCTIONS["sin"] = lambda x: x
# timeout rejects overridden "sin"

ev = Evaluator(random_seed=1)
# timeout snapshot does not falsely reject canonical instance-bound random functions
```

The snapshot must continue carrying supported constants, variables, memory values, and evaluator permission flags. Do not attempt to pickle arbitrary callables.

## 4. Workstream A — correct reducer result dimensions

### A1. Separate variance-family behavior

Inventory the aliases that return variance rather than standard deviation. At minimum inspect:

```text
variance
var
variance_sample
vars
var_sample
```

Assign all true variance aliases to the same explicit result-unit behavior.

Do not change:

- `std`, `std_sample`, and standard-deviation aliases: result unit remains the input unit;
- `mean`, `median`, `mode`, `min`, `max`, and `sum`: retain their existing compatible-unit behavior;
- dimensionless return values.

### A2. Common-unit conversion

For dimensional inputs:

1. require all values to be dimensional;
2. require dimensions to be compatible;
3. convert all values to the first input's display unit;
4. calculate variance with the existing numeric callable;
5. derive the squared structural unit from the first input unit;
6. return `UnitValue(result, squared_unit)`.

Mixed dimensional and dimensionless arguments remain errors.

### A3. Tests

Add focused tests that verify both numeric magnitude and exact structural dimension/unit compatibility. Do not assert only `isinstance(UnitValue)`.

Required cases:

- same-unit population variance;
- mixed-scale compatible population variance;
- sample variance;
- each variance alias maps to squared units;
- standard deviation remains first-power unit;
- incompatible units fail;
- mixed dimensional/dimensionless fails;
- dimensionless variance remains numeric;
- unsupported affine variance fails clearly if not representable.

## 5. Workstream B — correct scalar-output and rounding contracts

### B1. Dimensionless `sign`

Move `sign` out of `PRESERVE_SINGLE`. Add the smallest explicit handling that:

- unwraps a `UnitValue` magnitude for comparison;
- returns `-1`, `0`, or `1` without a unit;
- preserves existing dimensionless behavior;
- applies ordinary arity validation.

### B2. Exact `round` invocation

Implement omitted-argument detection explicitly.

Conceptual shape:

```python
if ndigits_was_omitted:
    result = round(value)
else:
    result = round(value, ndigits)
```

Do not use `kwargs.get("ndigits", 0)` or an equivalent numeric default.

### B3. Type-sensitive tests

Use `type(result) is int` / `type(result) is float` where the contract depends on type. For unit-valued results, assert the type of `result.value`.

Include:

- scalar omitted `ndigits`;
- scalar positional zero;
- scalar keyword zero;
- dimensional omitted `ndigits`;
- dimensional positional zero;
- dimensional keyword zero;
- duplicate `ndigits` rejection;
- dimensional `ndigits` rejection.

## 6. Workstream C — make callable identity authoritative

### C1. Establish the per-evaluator baseline

Capture canonical function identities only after instance-specific binding is complete. Do not compare against `Evaluator.FUNCTIONS` directly for instance-bound random functions.

The baseline must not be mutated when callers mutate `self.FUNCTIONS`.

### C2. Dispatch decision

Resolve each function call in this order:

1. obtain the active callable from `self.FUNCTIONS`;
2. determine whether it is the evaluator's canonical callable for that name;
3. if canonical, apply the built-in policy;
4. otherwise, apply the default user-callable policy: dimensionless-only;
5. invoke the same active callable that was classified.

The policy decision and callable invocation must refer to the same callable. Avoid time-of-check/time-of-use drift inside one call.

### C3. Tests

Add tests for overrides of policy-distinct names:

- override `sin`: no angle policy leakage;
- override `round`: no preserve-unit/keyword special handling leakage;
- override `variance`: no squared-unit policy leakage;
- add new `double`: dimensionless-only;
- restore canonical `sin`: built-in angle policy returns;
- canonical random functions remain recognized after instance binding.

Use public APIs where practical, but include direct instance mutation because it is already supported by current tests and is the path that previously escaped registration-time tracking.

## 7. Workstream D — close timeout parity

Update `_snapshot_evaluator_state()` to use the same callable-identity authority as ordinary dispatch.

Acceptance requirements:

- added custom callable fails before process creation;
- overridden built-in callable fails before process creation;
- error lists all custom/overridden names in sorted order;
- canonical built-ins, including instance-bound random functions, do not trigger false positives;
- constants, variables, memory, `allow_random`, and `allow_side_effects` still propagate;
- no callable is serialized;
- no child silently receives a different callable from the parent's active callable set.

Use an existing process-spawn mock/counter or a narrowly scoped monkeypatch to prove failure occurs before `Process.start()` if that can be done without brittle implementation coupling.

## 8. Workstream E — bound unsupported angle algebra

### E1. Preserve supported cases

The following must remain valid:

```text
90*deg
1*rad
30*deg/s
5*rad/s
(30*deg/s) * (2*s)
deg/rad
```

Direct angles remain convertible and accepted by `sin`, `cos`, and `tan`. Angular velocity remains a non-angle compound value for trig-input purposes until multiplied by time back to a direct angle.

### E2. Reject cases the boolean marker cannot faithfully represent

The current `Dimension.angle: bool` cannot encode angle exponents other than zero or one. Prevent silent parity behavior for unsupported cases.

Required bounded rules:

- angle-bearing dimension raised to `0` -> dimensionless;
- angle-bearing dimension raised to `1` -> unchanged;
- angle-bearing dimension raised to any other exponent -> clear error;
- multiplying two angle-bearing dimensions -> clear error rather than silent angle cancellation;
- dividing a non-angle dimension by an angle-bearing dimension -> clear error because inverse angle is not representable;
- dividing angle-bearing by angle-bearing dimensions may produce dimensionless only where the existing structural unit operation can establish complete compatibility/cancellation;
- multiplying or dividing one angle-bearing dimension by one non-angle dimension remains supported.

Implement the guard at the narrowest shared structural operation boundary. Do not add an integer angle exponent field, rational dimensions, or symbolic simplifier in this pass.

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

Tests must prove the error is intentional and not an incidental parser failure.

## 9. Workstream F — remove transitional policy debris

While implementing Sections 4–8, remove only now-obsolete local machinery.

Review and resolve:

- `_DIMENSIONLESS_REQUIRED_FUNCTIONS`, which should not remain as an unused pre-policy deny-list;
- `UnitPolicy.CUSTOM`, if it has no active dispatch meaning;
- `FunctionSpec.function`, which must either participate in the canonical callable authority or be removed;
- duplicate/unreachable policy assignments such as repeated `expm1` classification;
- unused helper/imports in `_sqrt_dispatch()`;
- direct `UnitExpression.__new__` plus `object.__setattr__` construction if the normal validated constructor can express the same result without expanding scope.

Rules:

- prefer deletion over adding compatibility wrappers for private unused names;
- do not reorganize the whole evaluator file;
- do not rename public functions or error classes;
- do not perform unrelated style cleanup;
- total policy machinery should become smaller or remain approximately neutral after correctness additions.

## 10. Workstream G — deferred import regression proof

Commit `ec7816d65658f17ca3040872201540beaef27bd1` changed MCP local imports from package-level re-exports to explicit implementation submodules after Python 3.11 exposed module/function name collisions.

Add one focused regression proof that:

1. imports same-named `eggcalc.exact` implementation submodules that can populate package attributes;
2. starts or constructs the MCP tool surface;
3. invokes representative affected handlers, including `identifier_inspect` and one validation handler;
4. confirms the resolved object is callable and the tool returns the expected envelope;
5. runs on Python 3.11 through the normal suite.

Prefer a compact parameterized test over one test per import. Do not add an import-audit framework or eager-import inventory gate.

The optimization invariant remains:

- `import eggcalc.mcp` and `tools/list` do not eagerly import all exact implementation modules;
- first tool invocation imports only the required implementation module(s);
- explicit submodule imports avoid package attribute collisions.

## 11. Documentation and plan-state closure

Update documentation only where behavior changed:

- unit-aware function contract table/examples for variance and `sign`;
- `round()` omitted-versus-explicit precision behavior if documented;
- angle algebra limitation and supported cases;
- timeout custom-callable limitation, including built-in-name overrides;
- private architecture notes if callable identity authority is documented.

Do not add a new architecture document.

After implementation and verification, update plan status headers:

- `plans/022-correctness-simplification-and-footprint-roadmap.md` -> `Status: completed`;
- `plans/023-cli-dispatch-and-trust-boundary-correction.md` -> `Status: implemented`;
- `plans/024-unit-aware-function-contracts-and-timeout-state-parity.md` -> `Status: implemented`;
- `plans/025-mcp-and-configuration-authority-consolidation.md` remains `Status: implemented`;
- `plans/026-measured-artifact-and-startup-footprint-reduction.md` -> `Status: implemented`;
- this plan -> `Status: implemented`.

Add a concise completion note to Plan 022 naming the implementation commit(s) for Plans 023–027. Do not create a registry, closure manifest, evidence JSON, benchmark record, or CI artifact.

## 12. Expected source scope

Expected primary files:

```text
eggcalc/evaluator.py
eggcalc/units.py                         # only if angle guards/unit-power helper belong here
tests/test_unit_aware_functions.py
tests/test_mcp_server.py or one existing MCP-focused test module
AGENTS.md and/or existing architecture evaluator/unit docs
plans/022-correctness-simplification-and-footprint-roadmap.md
plans/023-cli-dispatch-and-trust-boundary-correction.md
plans/024-unit-aware-function-contracts-and-timeout-state-parity.md
plans/025-mcp-and-configuration-authority-consolidation.md
plans/026-measured-artifact-and-startup-footprint-reduction.md
plans/027-evaluator-semantics-and-roadmap-closure.md
```

Files outside this list may be changed only when directly required for generated single-file parity, generated documentation drift, or an existing focused test location.

Do not modify CI workflows, release procedures, package dependencies, MCP schemas, tool counts, or release version.

## 13. Required focused tests

Before the full suite, run the smallest relevant tests covering:

1. variance unit exponent and aliases;
2. standard-deviation unit preservation;
3. dimensionless `sign`;
4. type-sensitive `round` behavior;
5. built-in-name override policy isolation;
6. timeout rejection of added and overridden callables;
7. canonical random callable recognition;
8. supported and rejected angle algebra;
9. lazy exact-import module/function collision regression;
10. package/single-file evaluator parity for the changed expressions.

If single-file parity already has a parameterized expression corpus, extend that corpus rather than creating a second parity harness.

Required single-file examples should include at least:

```text
variance(1*m,2*m,3*m)
sign(-5*m)
round(3.7)
round(3.7*m)
sin(90*deg)
```

Override and timeout tests may remain package-only because arbitrary callable injection is not a CLI/single-file public input surface.

## 14. Canonical verification

Run, in this order:

```bash
python -m pytest <focused existing test modules/cases> -q
make check
make package-check
```

The final verification requirements are:

- focused tests pass on Python 3.11;
- `make check` passes without adding or changing CI lanes;
- `make package-check` passes for wheel, sdist, installed console entry point, installed MCP smoke, generated single-file CLI, and generated single-file MCP smoke;
- `build_single.py --validate` passes;
- generated documentation has no drift;
- runtime dependency list remains empty;
- the generated single-file artifact remains functional;
- no automated publication or release action occurs.

Do not add a permanent performance test. The Plan 026 optimization is considered retained if the lazy implementations remain in place and no regression requires reverting them. Optional local spot measurements may be recorded in the implementation commit message but are not acceptance gates.

## 15. Negative acceptance criteria

The pass is not complete if any of the following is true:

- variance of dimensional input is returned in the unsquared input unit;
- standard deviation is incorrectly squared;
- `sign()` returns a `UnitValue`;
- `round(x)` and `round(x, 0)` have the same return type solely because omitted precision is replaced with zero;
- a custom callable named `sin`, `round`, or `variance` inherits the built-in unit policy;
- timeout evaluation silently substitutes a built-in for an overridden callable;
- canonical instance-bound random functions are falsely rejected as custom;
- `deg**2`, `1/deg`, or `deg*rad` silently produce representable-looking but incorrect dimensions;
- valid `deg/s` or `(deg/s)*s` behavior is broken;
- package-level lazy imports reintroduce module/function collisions;
- all exact implementation modules are imported during MCP startup;
- obsolete policy machinery remains unused without an explicit reason;
- a new runtime dependency is added;
- CI, release automation, or verification ceremony expands;
- plans are marked completed before canonical verification succeeds.

## 16. Final acceptance criteria

This closure pass is complete when all of the following hold:

1. Population and sample variance return squared units for compatible non-affine dimensional inputs.
2. Mean and standard deviation retain first-power units.
3. `sign()` always returns a dimensionless scalar.
4. Omitted and explicit `round()` precision preserve Python's value and type contracts for scalar and unit-valued inputs.
5. Each evaluator has one reliable canonical callable identity baseline established after instance binding.
6. Built-in policies apply only to canonical built-in callables.
7. Added and overridden callables default to dimensionless-only in ordinary evaluation.
8. Timeout evaluation rejects added and overridden callables before spawning and never substitutes behavior silently.
9. Canonical instance-bound random functions remain valid and are not false positives.
10. Unsupported angle powers and inverse-angle operations fail clearly without redesigning the dimension model.
11. Existing direct-angle and angular-velocity behavior remains functional.
12. Transitional policy debris is removed or made actively authoritative.
13. Deferred MCP imports remain lazy and survive Python 3.11 package/submodule name collisions.
14. Focused tests, `make check`, and `make package-check` pass.
15. Runtime dependencies remain empty and the standard-library-only guarantee is unchanged.
16. Required CI remains one Ubuntu/Python 3.11 job and release remains manual.
17. Plans 022–027 have accurate status headers and Plan 022 records final completion.
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