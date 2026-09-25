# Compatibility Evidence and Normalization Observability

Status: planned  
Repository: `eggstack/eggcalc`  
Baseline reviewed: `55993e58b438f4548c58569248cdada52c099030`  
Date: 2026-09-08  
Parent roadmap: `plans/033-surface-consolidation-and-maintainability-roadmap.md`  
Depends on: Plans 034 and 035 complete or their resulting authorities/lifecycle behavior otherwise stable

## 1. Goal

Close two underdeveloped areas identified in the current repository:

1. Supported-platform/runtime claims are broader than the compatibility evidence produced automatically by CI.
2. The normalization pipeline is large and historically defect-prone but lacks a structured, deterministic explanation/trace surface.

This plan adds bounded recurring compatibility evidence and a minimal normalization observability API without expanding calculator grammar or tool scope.

## 2. Constraints

- Standard library only in production.
- Keep CI deliberately small; do not create a full OS × Python matrix.
- Preserve the repository's current preference for simple GitHub Actions workflows and manual PyPI release.
- Do not make packaging/release dependent on every compatibility job unless the repository explicitly wants that later.
- Do not add runtime telemetry, tracing frameworks, logging dependencies, or persistent diagnostics.
- Normalization trace must be deterministic and side-effect-free.
- Normalization trace must not change normal evaluation results or error semantics.
- Do not expose internal regex match objects or unstable implementation details as a public contract.
- Do not mirror all MCP tools into CLI commands.
- Keep single-file parity as a first-class requirement.

## 3. Workstream A — recurring compatibility evidence

### 3.1 Current evidence gap

The public support contract currently states:

- Python 3.11 or higher;
- Linux;
- macOS;
- Windows;
- complete feature availability on supported runtimes.

Normal push/PR CI currently runs the full correctness gate on Ubuntu with Python 3.11. A separate compatibility workflow is manually triggered and covers Windows 3.11 plus Ubuntu 3.14. macOS is not represented in that compatibility workflow.

This plan should make the support contract evidence-backed without substantially increasing routine CI cost.

### 3.2 Preferred compatibility matrix

Retain the existing fast primary CI job:

```text
ubuntu-latest / Python 3.11 / make check + package validation as currently configured
```

Use a small compatibility workflow with approximately these representatives:

```text
windows-latest / Python 3.11
macos-latest   / Python 3.11
ubuntu-latest  / highest supported Python minor (currently 3.14)
```

This covers:

- minimum supported Python on all three OS families;
- newest supported Python on Linux where Python-version incompatibilities are most cheaply detected.

Do not add 3.12 and 3.13 jobs unless a concrete regression requires them. Python's supported interval is represented by minimum + upper boundary.

### 3.3 Trigger policy

Choose a bounded automatic trigger. Preferred options in order:

1. run compatibility on pull requests/pushes only when relevant files change, plus `workflow_dispatch`;
2. or run on a weekly schedule plus `workflow_dispatch` if path filtering proves awkward;
3. keep primary Ubuntu 3.11 CI on every relevant push/PR.

Relevant paths include at least:

```text
eggcalc/**
tests/**
build_single.py
pyproject.toml
Makefile
.github/workflows/**
```

If scheduled, use a low-frequency weekly cadence. Do not add daily compatibility runs unless failures demonstrate a need.

### 3.4 Compatibility test scope

Compatibility jobs should prove the platform-sensitive surfaces rather than duplicating every expensive developer gate if unnecessary.

Minimum required checks:

- install development/test dependencies;
- run the full test suite, or a documented equivalent if runtime is excessive;
- validate single-file build;
- execute a basic calculator expression through generated `eggcalc.py`;
- execute representative MCP/exact operations;
- exercise multiprocessing-backed timeout/regex behavior;
- run package surface smoke test where supported by the existing scripts.

Windows should retain package-surface/build validation if that is already the designated release-surface job.

macOS must include at least one subprocess/timeout case because process/resource behavior differs materially from Linux.

### 3.5 Support-claim alignment

After CI is updated, review README and support documentation.

Do not weaken the public support statement if the new recurring evidence passes.

If a platform has known reduced behavior, document it explicitly rather than saying all features are fully available. The preferred outcome is to preserve the current complete-capability claim and prove it.

## 4. Workstream B — normalization trace API

### 4.1 Problem statement

`normalize.py` transforms raw natural-language/unit input through multiple semantic stages before AST evaluation. Bugs in this area are hard to diagnose from the final normalized expression alone.

Provide a structured trace that answers:

- what input was received;
- which material transformations changed it;
- what the final normalized expression is;
- where validation/rejection occurred if normalization fails.

The trace is for observability, not for changing normalization behavior.

### 4.2 Public API shape

Prefer a narrow function such as:

```python
trace_normalization(expression: str) -> NormalizationTrace
```

or:

```python
normalize_expression(..., trace=True)
```

The first option is preferred because it avoids widening the normal hot-path API with tracing state unless code reuse strongly favors a private tracing collector.

Use a `TypedDict`/plain-data result consistent with the rest of eggcalc.

A suitable stable contract could contain:

```text
input                original string
steps                ordered list of material transformation records
normalized           final evaluator-ready string or None
exit_code            normal normalization exit code
errored              boolean
error                 stable user-facing error text or None
```

Each step should contain only stable concepts such as:

```text
stage                 short stable stage identifier
before                value before the material rewrite
after                 value after the material rewrite
changed               true
note                   optional short explanation
```

Do not record every internal regex substitution if that exposes unstable implementation detail. Group transformations by meaningful stage.

### 4.3 Stable stage vocabulary

Inspect the live normalization pipeline before committing to names. Candidate stage categories include:

- input sanitation/spacing;
- Unicode/operator normalization where applicable;
- filler/operator word handling;
- number-word conversion;
- function phrase normalization;
- unit tokenization/product insertion;
- conversion phrase handling;
- power/caret normalization;
- final validation.

Only include stages that map cleanly to the current architecture. A stage may be absent when it makes no change.

### 4.4 Implementation approach

Avoid duplicating the normalization algorithm.

Preferred implementation:

- add a private optional trace collector used by the existing normalization stages;
- ordinary `normalize_expression()` calls pass no collector and preserve the current fast path;
- `trace_normalization()` creates the collector and calls the same implementation;
- record only material before/after changes at selected stage boundaries.

If threading an optional collector through the existing pipeline would require a huge signature churn, use a small internal context/local collector only if it remains explicit and testable. Do not introduce global mutable tracing state.

### 4.5 Security/resource behavior

Trace mode must obey the same limits as normal normalization:

- maximum input length;
- maximum normalized length;
- nesting/validation limits;
- config-loading rules.

Bound trace output. Avoid retaining arbitrarily many intermediate copies if a malicious input causes many substitutions. The number of recorded stages should be naturally bounded by the fixed pipeline. If a stage itself iterates, record a stage summary rather than one entry per token.

Do not include local file paths, config source code, function object reprs, or sensitive environment values.

## 5. Workstream C — minimal CLI observability/discovery

### 5.1 Normalization explanation

Add one minimal user-facing entry point if it can be done without complicating argparse dispatch. Preferred form:

```bash
calc --explain "30 km / h in mph"
```

or another clearly named flag consistent with existing CLI conventions.

Output should be human-readable by default. If existing `--json` composition is straightforward, permit JSON output of the structured trace; otherwise keep the first implementation simple and document the Python API.

The flag should explain normalization only. It should not execute the resulting expression unless the existing CLI design makes a combined explain/result output obviously safer and clearer. Preferred behavior is trace + final normalized form, no separate hidden execution side effect.

### 5.2 Command/tool discovery

Review current help output and generated MCP tool inventory. If CLI users cannot easily distinguish the small curated CLI command set from the much larger MCP surface, add a simple generated/listed discovery option such as:

```bash
calc --commands
```

or ensure `--help` already provides sufficient command discovery.

Do not add 83 CLI subcommands.

This item is optional if current `--help` already clearly lists the curated command registry.

## 6. Workstream D — focused documentation drift closure

Correct known stale documentation after Plans 034–035 and the changes above land.

Review at least:

- `architecture/authority_inventory.md`;
- `architecture/overview.md`;
- `architecture/normalize.md`;
- `architecture/api.md`;
- `tests/README.md`;
- `README.md`;
- `docs/api.md` if present;
- generated MCP inventory/docs.

Specific checks:

- `_protocol.py` authority is described correctly;
- JSON extraction and version authorities match Plan 034;
- shared process lifecycle boundary matches Plan 035 if implemented;
- exact export authority is described accurately;
- current exact module count/tool count/categories are generated or current;
- grapheme-count documentation does not describe obsolete segmentation behavior;
- compatibility workflow/support claims match actual automation;
- normalization trace API/CLI behavior is documented;
- tests README is either updated to current major suites or reframed as representative rather than exhaustive.

Do not rewrite prose that is already correct merely for style.

## 7. Testing strategy

### Normalization trace parity

Create a representative corpus covering:

- plain arithmetic that requires no material rewrite;
- number words;
- operator words;
- function phrases;
- exponent/caret normalization;
- simple units;
- compound/spaced units;
- `in`/`to` conversions;
- temperature conversions;
- Unicode spacing variants already supported;
- malformed input;
- overlong input;
- validation failure;
- custom normalization configuration where public behavior supports it.

For every successful trace case:

```text
trace.normalized == normalize_expression(...).normalized result
```

and evaluating the traced normalized expression must match `evaluate_raw()` where applicable.

For failures, trace mode must preserve the same exit/error classification as the normal path.

### Package/single-file parity

Representative trace results must be equivalent between:

- installed/package `eggcalc`;
- generated `eggcalc.py`.

Do not require byte-for-byte JSON ordering unless ordering is already a contract; semantic result equivalence is sufficient.

### CI validation

After workflow changes, ensure YAML/configuration syntax is valid and that all matrix entries invoke commands available on their OS. Avoid POSIX-only shell assumptions in Windows steps unless GitHub's shell is explicitly configured.

## 8. Files likely to change

Expected files may include:

```text
.github/workflows/compatibility.yml
README.md
eggcalc/normalize.py
eggcalc/cli.py
eggcalc/__init__.py              # only if trace API is top-level public
eggcalc/__main__.py              # likely unchanged
build_single.py                  # only if new public symbol/module wiring needs it
architecture/authority_inventory.md
architecture/overview.md
architecture/normalize.md
architecture/api.md
docs/api.md
tests/README.md
tests/test_normalize.py
tests/test_cli_compatibility.py
tests/test_build_single.py
```

No new production module is required unless keeping trace result definitions separate clearly reduces complexity; default is to keep them in `normalize.py`.

## 9. Implementation sequence

1. Finalize the minimal recurring compatibility matrix and trigger policy.
2. Add macOS and automatic recurrence/path-trigger behavior without expanding the primary CI matrix.
3. Add normalization trace characterization tests.
4. Instrument existing normalization stage boundaries without duplicating logic.
5. Add the public trace API.
6. Add minimal CLI explanation support if clean.
7. Validate package/single-file trace parity.
8. Perform focused documentation authority/support drift cleanup.
9. Run full correctness/package checks.
10. Confirm all compatibility matrix jobs pass before marking the plan complete.

## 10. Acceptance criteria

Plan 036 is complete when:

- Linux, Windows, and macOS receive recurring automated compatibility evidence;
- Python 3.11 minimum and the current maximum supported Python minor are both represented;
- CI remains bounded to a small representative matrix;
- platform-sensitive subprocess/single-file surfaces are exercised;
- public support documentation matches the tested support contract;
- a deterministic bounded normalization trace API exists;
- trace mode uses the same implementation as ordinary normalization rather than a duplicate parser;
- normal evaluation behavior and performance path remain unchanged when tracing is not requested;
- representative package and single-file traces match;
- known authority/test documentation drift is corrected;
- no broad CLI tool mirroring is introduced;
- no runtime dependency is added;
- `make check` and `make package-check` pass;
- compatibility workflow jobs pass on their supported runners.

## 11. Verification

Local/canonical verification:

```bash
python -m pytest tests/test_normalize.py tests/test_cli_compatibility.py tests/test_build_single.py -v
python build_single.py --validate
make check
make package-check
```

CI verification:

- Ubuntu / Python 3.11 primary CI green;
- Windows / Python 3.11 compatibility green;
- macOS / Python 3.11 compatibility green;
- Ubuntu / current maximum supported Python green.

Document the actual workflow run URLs/IDs in the implementation commit or closure note if repository conventions normally record such evidence; do not add a new permanent evidence registry solely for this plan.

## 12. Non-goals

Do not use this plan to:

- add Python 3.10 support;
- promise future unreleased Python versions;
- add every supported Python minor to CI;
- add architecture-specific runners;
- add release/publish automation;
- implement runtime telemetry;
- expose every internal normalization regex/pass;
- alter natural-language grammar;
- add an interactive debugger;
- add MCP tracing/protocol extensions;
- add a new MCP normalization tool unless a concrete downstream requirement appears during implementation;
- expand CLI to mirror the complete MCP inventory;
- perform a broad documentation rewrite.

The target is evidence and observability, not feature growth.
