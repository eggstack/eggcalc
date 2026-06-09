# Architecture Review Plan

## Status: COMPLETED (2026-05-29)

This plan orchestrates a systematic, in-depth review of all architecture documentation modules in the `architecture/` directory. The goal is to verify documentation accuracy against code, identify bugs, and surface improvement opportunities without prescribing direct code changes.

> **Note:** Review outputs are available in `plans/*_review.md`. See stale item detection report below.

All 15 module reviews completed. Documentation discrepancies identified and fixed in commit bdbb668.

## Architecture Modules (15 total, excluding `review_plan.md`)

| Module | Document | Primary Code Location |
|--------|----------|----------------------|
| API | `api.md` | `eggcalc/__init__.py`, `eggcalc/evaluator.py` |
| CLI | `cli.md` | `eggcalc/__main__.py` |
| Confusables | `confusables.md` | `eggcalc/exact/confusables.py` |
| Diff | `diff.md` | `eggcalc/exact/diff.py` |
| Evaluator | `evaluator.md` | `eggcalc/evaluator.py` |
| Exact | `exact.md` | `eggcalc/exact/` (overview) |
| MCP | `mcp.md` | `eggcalc/mcp/` |
| Measure | `measure.md` | `eggcalc/exact/measure.py` |
| Normalize | `normalize.md` | `eggcalc/normalize.py` |
| Overview | `overview.md` | Entire codebase |
| Primitives | `primitives.md` | `eggcalc/exact/primitives.py` |
| Synthesis | `synthesis.md` | `eggcalc/exact/synthesis.py` |
| Unicode Tools | `unicode_tools.md` | `eggcalc/exact/unicode_tools.py` |
| Units | `units.md` | `eggcalc/units.py` |
| Validate | `validate.md` | `eggcalc/exact/validate.py` |

## Review Methodology

Each subagent will follow this methodology for their assigned module:

### Phase 1: Document Analysis
- Read the architecture document thoroughly
- Extract all claims about code structure, functions, constants, behaviors, and relationships
- Note any architectural decisions or design patterns described

### Phase 2: Code Verification
- Locate the corresponding source code(s)
- Map each document claim to the actual implementation
- Mark each claim as: **VERIFIED**, **MISMATCH**, or **MISSING**
- Document any discrepancies between documentation and code

### Phase 3: Bug Interrogation
- Scan for edge cases not handled
- Identify potential exception sources (IndexError, KeyError, TypeError, etc.)
- Verify error handling completeness
- Check for thread-safety concerns where applicable
- Look for input validation gaps

### Phase 4: Improvement Surface
- Identify code complexity that could be reduced
- Note missing or inadequate validation
- Flag performance concerns
- Check for consistency issues across the module
- Surface technical debt observations

### Phase 5: Output Generation
- Write findings to `plans/<module>_review.md` at repository root
- Structure output to highlight verified claims, discrepancies, bugs, and improvements
- Do NOT prescribe specific code changes; describe observations and their significance

## Subagent Dispatch

Subagents will be dispatched in 4 groups, with parallel execution within each group:

### Group 1: Independent Core Modules
- `api` → Review `api.md` → Write to `plans/api_review.md`
- `cli` → Review `cli.md` → Write to `plans/cli_review.md`
- `validate` → Review `validate.md` → Write to `plans/validate_review.md`

### Group 2: Exact/ Submodules
- `primitives` → Review `primitives.md` → Write to `plans/primitives_review.md`
- `confusables` → Review `confusables.md` → Write to `plans/confusables_review.md`
- `unicode_tools` → Review `unicode_tools.md` → Write to `plans/unicode_tools_review.md`
- `measure` → Review `measure.md` → Write to `plans/measure_review.md`
- `diff` → Review `diff.md` → Write to `plans/diff_review.md`
- `synthesis` → Review `synthesis.md` → Write to `plans/synthesis_review.md`

### Group 3: Primary Calculation Modules
- `normalize` → Review `normalize.md` → Write to `plans/normalize_review.md`
- `evaluator` → Review `evaluator.md` → Write to `plans/evaluator_review.md`
- `units` → Review `units.md` → Write to `plans/units_review.md`

### Group 4: Meta and Integration Modules
- `mcp` → Review `mcp.md` → Write to `plans/mcp_review.md`
- `overview` → Review `overview.md` → Write to `plans/overview_review.md`
- `exact` → Review `exact.md` → Write to `plans/exact_review.md`

## Review Output Format

Each subagent will write a structured review to `plans/<module>_review.md`:

```markdown
# <Module> Architecture Review

## Document:<module>.md

## Verified Claims
| Claim | Status | Evidence |
|-------|--------|----------|
| [Description] | VERIFIED/MISMATCH/MISSING | [file:line] |

## Discrepancies
1. **[MISMATCH/MISSING]**: [Description]
   - Document states: [what doc claims]
   - Code actually: [what code does]

## Bugs Identified
| Bug | Location | Severity | Description |
|-----|----------|----------|-------------|
| [Name] | [file:line] | High/Medium/Low | [Description] |

## Improvements Surface
| Area | Priority | Description |
|------|----------|-------------|
| [Category] | High/Medium/Low | [Observation] |

## Notes
[Any additional observations, context, or recommendations]
```

## Stale Item Detection

After all subagent reviews complete, the orchestrator will:

1. **Scan `architecture/` for stale content**:
   - Check for module files that no longer correspond to actual code
   - Identify documentation that describes removed or renamed modules
   - Flag files with outdated architectural descriptions

2. **Scan `plans/` for stale review files**:
   - Identify review outputs from prior runs that are now superseded
   - Note any orphaned improvement files no longer referenced

3. **Report findings**:
   - List stale architecture files recommended for removal
   - List stale review files recommended for removal
   - Do NOT remove automatically; surface for human review

## Execution Order

1. Write this plan to `architecture/review_plan.md`
2. Dispatch Group 1 subagents (3 agents, parallel)
3. Wait for Group 1 completion
4. Dispatch Group 2 subagents (6 agents, parallel)
5. Wait for Group 2 completion
6. Dispatch Group 3 subagents (3 agents, parallel)
7. Wait for Group 3 completion
8. Dispatch Group 4 subagents (3 agents, parallel)
9. Wait for Group 4 completion
10. Perform stale item detection
11. Report stale items found
12. Commit plan and all review outputs to main

## Subagent Instructions Template

Each subagent receives this instruction pattern:

> Review the architecture document at `architecture/<module>.md` and the corresponding code. Verify all claims in the document against the actual implementation. Identify any discrepancies, bugs, or improvement opportunities. Write a structured review to `plans/<module>_review.md` following the format specified in the parent plan. Work only within the repository at `/Users/davidbowman/projects/github/eggstack/eggcalc`. Do not execute any code changes.

## Verification

After all reviews complete, run:
```bash
python3 -m pytest tests/ -v
```

Ensure all tests pass. Review outputs inform future improvement planning but do not directly modify code.

---

## Stale Item Detection Report

### Completed Review Files (15 modules)

| Module | Review File | Status |
|--------|-------------|--------|
| API | `plans/api_review.md` | Complete |
| CLI | `plans/cli_review.md` | Complete |
| Confusables | `plans/confusables_review.md` | Complete |
| Diff | `plans/diff_review.md` | Complete |
| Evaluator | `plans/evaluator_review.md` | Complete |
| Exact | `plans/exact_review.md` | Complete |
| MCP | `plans/mcp_review.md` | Complete |
| Measure | `plans/measure_review.md` | Complete |
| Normalize | `plans/normalize_review.md` | Complete |
| Overview | `plans/overview_review.md` | Complete |
| Primitives | `plans/primitives_review.md` | Complete |
| Synthesis | `plans/synthesis_review.md` | Complete |
| Unicode Tools | `plans/unicode_tools_review.md` | Complete |
| Units | `plans/units_review.md` | Complete |
| Validate | `plans/validate_review.md` | Complete |

### Architecture Files (16 .md files in `architecture/`)

| File | Status | Notes |
|------|--------|-------|
| `api.md` | Valid | Reviewed - discrepancies noted in api_review.md |
| `cli.md` | Valid | Reviewed - output format discrepancies in cli_review.md |
| `confusables.md` | Valid | Reviewed |
| `diff.md` | Valid | Reviewed |
| `evaluator.md` | Valid | Reviewed |
| `exact.md` | Valid | Reviewed |
| `mcp.md` | Valid | Reviewed |
| `measure.md` | Valid | Reviewed |
| `normalize.md` | Valid | Reviewed |
| `overview.md` | Valid | Reviewed |
| `primitives.md` | Valid | Reviewed |
| `synthesis.md` | Valid | Reviewed |
| `unicode_tools.md` | Valid | Reviewed |
| `units.md` | Valid | Reviewed |
| `validate.md` | Valid | Reviewed |
| `diff.md` | Valid | Reviewed |

### Stale Files Found

**None.** All architecture files correspond to actual code modules.

### Stale Review Files

**None.** All 15 review files correspond to current architecture files.

### Test Verification Results

```
1231 passed, 32 skipped, 1 warning in 35.88s
```

All tests pass. No code changes were made as per the plan's scope.

---

## Key Findings Summary

### High Priority Issues Identified

1. **CLI Output Format Mismatch** (`plans/cli_review.md`)
   - Documentation describes `expression -> result` format
   - Code only outputs `result`
   - No stale/removed modules detected

2. **API `normalize_expression` Return Type** (`plans/api_review.md`)
   - Document shows string return, actual is `tuple[str, int]`

3. **`list_sort` stable parameter meaningless** (`plans/validate_review.md`)
   - Python's `sorted()` is always stable
   - Parameter has no effect

### Deferred Items from Prior Plan (plans/plan.md)

| Item | Description | Status |
|------|-------------|--------|
| D3 | `load_user_config_extended` not exported | By design - thread-safety concerns |

### Notes for Future Review Cycles

1. All 15 module reviews completed in single pass
2. No orphaned architecture files detected
3. No orphaned review files detected
4. All tests pass (1231 passed)
5. Reviews did not prescribe code changes - findings are for informational improvement planning
