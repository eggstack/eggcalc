# Evaluator Closure Corrective Pass

Status: implementation handoff  
Repository: `eggstack/eggcalc`  
Baseline reviewed: `5d29586c755fa5392bba7afb22acf760d9466605`  
Date: 2026-08-05  
Depends on: `plans/022-correctness-simplification-and-footprint-roadmap.md`, `plans/027-evaluator-semantics-and-roadmap-closure.md`

## 1. Purpose

Plan 027 materially improved evaluator correctness, but the closure review found a small set of concrete gaps between the implemented behavior and the stated acceptance criteria. This plan is the only corrective follow-up required for that roadmap.

The pass must remain narrow. It exists to:

1. make callable identity authoritative before every built-in-specific dispatch path;
2. complete the exact `round()` call contract;
3. make timeout evaluator snapshots reject deleted built-ins as well as added and overridden callables;
4. strengthen the Python 3.11 deferred-import regression proof so it exercises the original failure mode;
5. add the required package/single-file semantic parity cases;
6. remove the small amount of private transitional debris left by Plan 027;
7. run canonical verification and make the roadmap completion notes accurate.

This is not a new roadmap and must not become a general evaluator refactor.

## 2. Governing constraints

Preserve all existing project constraints:

- runtime remains Python standard-library-only;
- no runtime or optional feature dependency is added;
- no public function, exception, CLI command, MCP tool, schema, or package entry point is removed or renamed;
- no unit-dimension redesign is introduced;
- no plugin framework, general callable-policy framework, or new evaluator extension API is introduced;
- required CI remains the existing single Ubuntu/Python 3.11 verification job;
- release remains manual through PyPI;
- no release action is part of this pass;
- no benchmark suite, fuzzing framework, property-test framework, evidence manifest, closure registry, or verification artifact is added;
- do not broaden work into unrelated evaluator, unit, MCP, packaging, or documentation cleanup.

Expected net effect: a small correctness patch, focused tests, and deletion of obsolete private code.

## 3. Verified gaps at the baseline

### 3.1 Built-in-specific dispatch precedes callable identity authority

`Evaluator.visit_Call()` currently returns through special handling for `temp`, `convert`, and variable-management functions before comparing the active callable with `_builtin_function_baseline`.

Consequences:

- a user override under one of those names can inherit canonical argument handling;
- canonical raw-name preservation can leak to an overridden `setvar`, `getvar`, or `delvar`;
- unit-bearing arguments can reach an overridden `convert` or `temp` without the required dimensionless-only fallback;
- keyword rejection can be bypassed because the special branch returns before generic keyword validation.

This violates the Plan 027 rule that built-in behavior applies only when the active callable is the evaluator-owned canonical callable.

### 3.2 `round()` preserves omitted precision type but does not enforce exact arity

The current implementation distinguishes:

```text
round(3.7)      -> int
round(3.7, 0)   -> float
```

but it does not completely enforce Python's call shape. In particular:

- `round()` can fail through incidental indexing rather than a controlled `EvaluationError`;
- `round(3.7, 0, 1)` can ignore surplus positional arguments;
- `round(ndigits=2)` lacks the required value argument;
- the canonical `ndigits=` keyword allowance is selected by function name before callable identity is established;
- unit-valued `ndigits` is not rejected through an explicit evaluator contract.

### 3.3 Timeout state comparison is not symmetric

`_snapshot_evaluator_state()` rejects active function names that are added or whose callable identity differs from the baseline. It does not reject names deleted from the active function map.

A deleted built-in can therefore reappear in the child because the worker constructs a fresh evaluator. Timeout execution must never silently restore behavior removed from the parent evaluator.

### 3.4 Deferred-import regression test does not execute the original collision path

The current regression test verifies that selected entries in the MCP handler map are callable. It does not:

- pre-import the same-named exact submodules that populate package attributes;
- invoke the representative handlers;
- validate the normal MCP result envelope.

The original Python 3.11 module/function collision can only be considered proven closed when those operations are exercised in one clean subprocess.

### 3.5 Required single-file parity cases were not added

Plan 027 required focused package/generated-single-file parity for:

```text
variance(1*m,2*m,3*m)
sign(-5*m)
round(3.7)
round(3.7*m)
sin(90*deg)
```

The existing parity corpus was not extended with those cases. Its result probe also coerces values to `float`, so it cannot prove the type distinction between omitted and explicit `round` precision.

### 3.6 Small private cleanup remains

The following Plan 027 cleanup targets remain:

- unused `funcs = Evaluator.FUNCTIONS` in `_build_function_specs()`;
- duplicate `expm1` policy classification;
- unused `_get_reg()` and duplicate imports in `_sqrt_dispatch()`;
- direct `UnitExpression.__new__` plus `object.__setattr__` construction where the validated constructor can represent the same expression.

These are not independent refactor goals. Remove them only while touching the associated functions.

## 4. Workstream A — establish identity before special dispatch

### A1. Classify the active callable once

After resolving `func_name` and confirming it exists in `self.FUNCTIONS`, establish:

```python
active_callable = self.FUNCTIONS[func_name]
baseline_callable = self._builtin_function_baseline.get(func_name)
is_canonical = active_callable is baseline_callable
```

Do this before any behavior selected because of a built-in name.

The dispatch sequence should make these authorities explicit:

1. resolve and authorize the function name;
2. enforce evaluator random/side-effect policy by name as today;
3. determine canonical callable identity;
4. validate keyword shape under the active callable's authority;
5. if noncanonical, use only the generic custom-callable path;
6. if canonical, use canonical special handling or the unit-policy dispatcher.

Do not distribute identity checks across multiple branches.

### A2. Canonical-only special handling

The following special argument handling must execute only when `is_canonical` is true:

- `temp()` unit-name preservation;
- `convert()` `UnitValue` passthrough;
- raw first-string preservation for `setvar()`, `getvar()`, and `delvar()`;
- canonical `round(..., ndigits=...)` keyword allowance.

An override under one of these names must behave like any other custom callable:

- dimensional `UnitValue` arguments are rejected;
- no canonical conversion, temperature, state-management, or raw-name semantics are inherited;
- no built-in-only keyword exception is inherited;
- ordinary supported scalar and string arguments are passed using the existing custom-callable rules.

Examples that must be covered:

```python
ev = Evaluator()
ev.FUNCTIONS["convert"] = lambda x, y: (x, y)
# convert(1*m, cm) -> EvaluationError: dimensional arguments are not allowed


ev = Evaluator()
ev.FUNCTIONS["setvar"] = lambda x, y: (x, y)
# overridden setvar does not receive canonical raw-name preservation


ev = Evaluator()
ev.FUNCTIONS["round"] = lambda x: x
# round(3.7, ndigits=0) does not inherit the canonical keyword exception
```

Do not add keyword support for arbitrary custom callables as part of this fix.

### A3. Keyword rejection must not be bypassable

For every call path:

- unsupported keywords raise `EvaluationError` before invoking the callable;
- only canonical `round()` accepts the single named keyword `ndigits`;
- `temp`, `convert`, memory functions, variable functions, random functions, and custom callables do not silently ignore keywords;
- duplicate `ndigits` supplied positionally and by keyword raises a stable `EvaluationError`.

Tests must include a canonical special function with an unexpected keyword to prove no early-return branch bypass remains.

## 5. Workstream B — complete exact `round()` semantics

### B1. Enforce call shape

Canonical `round()` must accept only:

```text
round(number)
round(number, ndigits)
round(number, ndigits=...)
```

Reject:

```text
round()
round(ndigits=2)
round(3.7, 0, 1)
round(3.7, 0, ndigits=0)
round(3.7, unexpected=0)
```

Use evaluator-owned `EvaluationError` messages. The text may be concise and Python-like, but tests should primarily assert the failure category and the relevant argument name or arity.

### B2. Preserve value and type behavior

For scalar input:

```text
round(3.7)             -> 4, exact type int
round(3.7, 0)          -> 4.0, exact type float
round(3.7, ndigits=0)  -> 4.0, exact type float
round(3.14159, 2)      -> 3.14
```

For `UnitValue` input:

```text
round(3.7*m)             -> UnitValue(value=4[int], unit="m")
round(3.7*m, 0)          -> UnitValue(value=4.0[float], unit="m")
round(3.7*m, ndigits=0)  -> UnitValue(value=4.0[float], unit="m")
```

Do not replace omitted `ndigits` with numeric zero.

### B3. Validate `ndigits`

A unit-bearing `UnitValue` cannot be used as `ndigits`.

Add focused negative tests for positional and keyword forms, for example:

```text
round(3.7, 1*m)             -> EvaluationError
round(3.7, ndigits=1*m)     -> EvaluationError
```

Do not introduce a general argument-binding subsystem. A narrow canonical `round()` validator is sufficient.

## 6. Workstream C — make timeout callable parity symmetric

### C1. Compare active and baseline key sets

Before snapshotting constants, variables, or memory, compare the active and baseline callable maps in both directions.

Classify at least:

- added names: active but absent from baseline;
- deleted names: baseline but absent from active;
- overridden names: present in both but callable identity differs.

Any of these conditions must reject timeout evaluation before process creation.

The implementation may use one combined sorted name list or separate categories. Error text must be deterministic and include every affected name.

### C2. Preserve supported timeout state

The correction must not regress propagation of:

- scalar constants;
- user variables;
- memory registers;
- `allow_random`;
- `allow_side_effects`.

Canonical evaluator-bound random callables must remain accepted and must not be misclassified because each evaluator has instance-owned closures.

### C3. Prove rejection happens before spawn

Use a narrow monkeypatch around the existing process creation/start boundary to prove that added, overridden, and deleted callable states fail before a child is started.

Do not create a general multiprocessing test harness.

Required timeout cases:

```text
added callable                 -> reject before spawn
overridden built-in            -> reject before spawn
deleted built-in               -> reject before spawn
multiple affected names        -> all listed in sorted order
canonical bound random funcs   -> accepted
ordinary supported state       -> still propagated
```

No callable may be serialized into the snapshot.

## 7. Workstream D — strengthen the deferred-import regression proof

### D1. Reproduce the Python 3.11 collision conditions

In one fresh subprocess:

1. explicitly import the exact implementation submodules associated with `identifier_inspect` and at least one validation handler so package attributes are populated;
2. import or construct the normal MCP tool surface through the production path;
3. resolve the representative handlers;
4. invoke them with valid minimal arguments;
5. assert that invocation succeeds and returns the expected MCP/tool result envelope;
6. confirm the resolved handler objects are callable.

Inspect the current exact module layout and use the actual defining modules. Do not add compatibility re-exports or alter import strategy merely to simplify the test.

Representative coverage must include:

- `identifier_inspect`;
- one validation handler such as `validate_brackets` or the current equivalent.

### D2. Preserve lazy imports

Retain the existing startup invariant:

- `import eggcalc.mcp` does not eagerly load all `eggcalc.exact.*` implementation modules;
- constructing/listing the MCP tool surface does not eagerly load all exact implementations;
- invoking a handler imports only the implementation modules required by that handler and ordinary dependencies.

Do not create an import-audit framework or a permanent exhaustive module inventory.

## 8. Workstream E — complete package/single-file parity

### E1. Extend the existing parity harness

Reuse the existing fresh generated-single-file test path. Do not create a second single-file test framework.

Add at least these expressions:

```text
variance(1*m,2*m,3*m)
sign(-5*m)
round(3.7)
round(3.7*m)
round(3.7,0)
round(3.7*m,0)
sin(90*deg)
```

The extra explicit-zero cases are required to prove the omitted/explicit type distinction across both package and generated artifact surfaces.

### E2. Make parity type-sensitive

The evaluation probe must record enough information to compare:

- success/failure;
- exact result value;
- unit string;
- scalar result type;
- `UnitValue.value` type.

Do not coerce all results to `float` before recording type. For numeric comparison, preserve the raw JSON-representable value where possible and record `type(...).__name__` separately.

Expected examples:

```text
round(3.7)       -> value 4, value_type "int"
round(3.7,0)     -> value 4.0, value_type "float"
round(3.7*m)     -> unit "m", value_type "int"
round(3.7*m,0)   -> unit "m", value_type "float"
variance(...)    -> unit "m**2"
sign(-5*m)       -> no unit, scalar -1
sin(90*deg)      -> approximately 1.0
```

Use an appropriate numeric tolerance only where floating-point computation requires it. Do not weaken exact type assertions.

## 9. Workstream F — remove remaining private debris

While editing the affected functions, perform only these cleanup items:

1. remove the unused `funcs = Evaluator.FUNCTIONS` assignment;
2. remove duplicate `expm1` policy classification;
3. remove `_sqrt_dispatch()`'s unused `_get_reg()` helper and duplicate imports;
4. replace direct `UnitExpression.__new__` plus `object.__setattr__` construction with the validated constructor if the existing constructor accepts the computed factors, dimension, and scale without changing behavior.

For the square-root expression path, prefer the existing validated structural constructor and keep the current public result behavior:

```text
sqrt(4*m**2) -> 2*m
sqrt(4*m)    -> EvaluationError
```

If the validated constructor cannot express the current result without unrelated changes, document that narrow reason in the code and leave the construction unchanged. Do not redesign `UnitExpression` in this pass.

Do not perform unrelated import sorting, naming cleanup, dispatcher decomposition, or file reorganization.

## 10. Required focused tests

Add or extend focused tests for all of the following.

### Callable identity and special dispatch

- canonical `temp`, `convert`, and variable functions retain current behavior;
- overridden `temp` does not inherit canonical unit-name handling;
- overridden `convert` rejects dimensional input through the custom-callable rule;
- overridden `setvar`, `getvar`, or `delvar` does not inherit canonical raw-name handling;
- overridden `round` does not inherit the canonical keyword exception;
- unsupported keyword on a canonical early-special function is rejected rather than ignored.

### Exact `round()` contract

- zero arguments rejected;
- one positional accepted;
- two positional accepted;
- three positional rejected;
- keyword `ndigits` accepted only with one value argument;
- positional plus keyword duplicate rejected;
- unknown keyword rejected;
- unit-valued positional and keyword `ndigits` rejected;
- omitted versus explicit zero preserves exact scalar and `UnitValue.value` types.

### Timeout parity

- added callable rejected before spawn;
- overridden callable rejected before spawn;
- deleted callable rejected before spawn;
- multiple changed names are listed deterministically;
- canonical bound random functions are accepted;
- constants, variables, memory, and policy flags still propagate.

### Deferred imports

- same-named exact submodules are imported before MCP surface construction;
- `identifier_inspect` and one validation handler are invoked successfully;
- handler outputs have the expected envelope;
- ordinary MCP startup remains lazy.

### Package/single-file parity

- all expressions listed in Workstream E execute through package and freshly generated single-file modes;
- units, values, and exact numeric types match;
- existing parity cases remain intact.

Prefer parameterization and extension of existing test classes. Do not create a large new test module unless no existing focused location is suitable.

## 11. Expected source scope

Expected primary files:

```text
eggcalc/evaluator.py
tests/test_unit_aware_functions.py
tests/test_import_boundaries.py
tests/test_final_unit_expression.py
plans/022-correctness-simplification-and-footprint-roadmap.md
plans/027-evaluator-semantics-and-roadmap-closure.md
plans/028-evaluator-closure-corrective-pass.md
```

Potentially permitted only if directly required:

```text
architecture/evaluator.md
architecture/units.md
eggcalc/units.py
```

Do not modify:

- dependency declarations;
- CI workflows;
- release workflows or publishing instructions;
- MCP tool definitions or schemas;
- CLI command definitions;
- package version;
- generated artifacts by hand.

Generated files may change only through the existing generator and freshness process.

## 12. Documentation and plan-state closure

Update existing documentation only if implementation details documented there become inaccurate.

After all focused and canonical verification succeeds:

- set Plan 028 to `Status: implemented`;
- retain Plan 027 as implemented, but amend its completion note to name both the original implementation commit and the Plan 028 corrective commit;
- retain Plan 022 as completed, but amend its completion note to include the corrective commit and state that Plan 028 closed the final verified gaps;
- leave Plans 023–026 unchanged unless a status reference is factually incorrect.

Do not mark Plan 028 implemented before canonical verification succeeds.

Do not add a plan registry, completion manifest, evidence JSON, benchmark record, or additional closure plan.

## 13. Canonical verification

Run in this order:

```bash
python -m pytest tests/test_unit_aware_functions.py tests/test_import_boundaries.py tests/test_final_unit_expression.py -q
make check
make package-check
python build_single.py --validate
```

If the repository's existing `make check` or `make package-check` already invokes `build_single.py --validate`, the explicit final invocation may be retained as a direct closure check; do not add another Make target or CI step.

Verification requirements:

- focused tests pass on Python 3.11;
- all existing tests remain green;
- lint, format, type checking, documentation checks, and generated-file freshness pass through existing commands;
- wheel and sdist package checks pass;
- installed console and MCP surfaces pass;
- freshly generated single-file CLI and MCP surfaces pass;
- runtime dependency list remains empty;
- no publication or release occurs.

Do not add permanent performance gates. Plan 026's lazy implementations must remain intact.

## 14. Negative acceptance criteria

The pass is not complete if any of the following remains true:

- an overridden `temp`, `convert`, variable-management function, or `round` inherits canonical special handling;
- an unsupported keyword is silently ignored by an early-return branch;
- `round()` leaks `IndexError` or another incidental implementation exception;
- surplus positional arguments to `round()` are ignored;
- omitted `ndigits` is treated as explicit zero;
- a unit-bearing `ndigits` is accepted;
- timeout evaluation silently restores a deleted built-in;
- changed callable names are omitted or nondeterministically ordered in the timeout error;
- rejection occurs only after child-process creation;
- the Python 3.11 regression checks only handler existence without invoking the collision-prone path;
- MCP startup eagerly imports all exact implementation modules;
- package/single-file parity still coerces away the `round()` type distinction;
- the required Plan 027 parity expressions are absent;
- unused `_sqrt_dispatch()` or policy debris remains without a documented active reason;
- runtime dependencies, CI lanes, release automation, or verification ceremony expand;
- Plan 022 or Plan 027 claims final closure without naming the corrective implementation commit.

## 15. Final acceptance criteria

This corrective pass is complete when:

1. Callable identity is established before all built-in-name-specific behavior.
2. Canonical-only handling is limited to canonical evaluator-owned callables.
3. Overrides under `temp`, `convert`, variable-management names, and `round` use generic custom-callable rules.
4. Unsupported keywords cannot bypass validation through an early return.
5. Canonical `round()` accepts exactly its supported positional/keyword shapes.
6. Omitted and explicit `ndigits` preserve Python value and exact type semantics for scalar and unit-valued results.
7. Unit-bearing `ndigits` is rejected clearly.
8. Timeout state comparison rejects added, overridden, and deleted callables before spawn.
9. Timeout errors report all affected names deterministically.
10. Canonical bound random callables remain accepted.
11. Supported constants, variables, memory, and evaluator flags still propagate to timeout workers.
12. The Python 3.11 deferred-import test reproduces package/submodule attribute population and successfully invokes representative MCP handlers.
13. MCP startup remains lazy.
14. Package and freshly generated single-file behavior match for variance, sign, round, and angle conversion, including exact result types.
15. Remaining private policy and `_sqrt_dispatch()` debris is removed where the validated existing constructor supports it.
16. Focused tests, `make check`, `make package-check`, and generated-file validation pass.
17. Runtime dependencies remain empty, CI remains minimal, and release remains manual.
18. Plans 022, 027, and 028 accurately identify the final implementation commits.
19. No further corrective roadmap or plan is required for this line of work.

## 16. Implementation sequence

Implement in this order:

1. add failing focused tests for special-name overrides, keywords, `round()` arity, deleted timeout functions, collision-path invocation, and type-sensitive parity;
2. move callable identity classification ahead of built-in-specific dispatch;
3. gate all special handling and the `round` keyword exception on canonical identity;
4. add the narrow canonical `round()` argument validator;
5. make timeout callable comparison symmetric and prove pre-spawn rejection;
6. strengthen the Python 3.11 deferred-import subprocess test;
7. extend the existing package/single-file parity probe and corpus;
8. remove the enumerated private debris;
9. run focused tests;
10. run canonical verification;
11. update Plan 022, Plan 027, and Plan 028 completion notes with the resulting commit SHA;
12. commit and stop.

Do not open a broader cleanup phase after these criteria pass.