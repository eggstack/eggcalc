# Post MCP Tool Polish Cleanup Plan

Date: 2026-07-06
Repo: `eggstack/eggcalc`
Target branch: `main`
Context: cleanup pass after the large MCP tool-polish implementation commit that expanded the tool inventory from 64 to 77 tools.

## Summary

The implementation pass appears to have delivered most of the prior roadmap in one large batch: Windows/UNC path normalization, MCP environment-configurable limits, real `normal_schema()` support, generated MCP inventory, 13 new deterministic agent tools, README simplification, and substantial new tests.

This cleanup pass is intentionally narrow. Do not broaden scope into new tools unless tests reveal a correctness issue. The main goal is to remove stale documentation/count drift, ensure generated docs are actually gated, clarify the source-of-truth documentation model, and document remaining cancellation semantics honestly.

## Current State Observations

- `docs/tool_inventory.md` is now auto-generated and reports **77 tools**.
- README still has a stale feature bullet claiming **64 deterministic** tools.
- README says `docs/mcp.md` is the full tool catalog, but generated inventory reports 64 tools documented in `docs/mcp.md` and 13 missing there.
- `Makefile` has `docs-check`, but `make check` does not currently run it.
- MCP cancellation remains best-effort for already-running threadpool tasks. That is acceptable if documented, but it should not be implied to be preemptive cancellation.
- The large implementation commit claims 2,487 tests pass and ruff/black/mypy are clean, but this cleanup should still run the local gates after changes.

## Goals

1. Make README, generated inventory, and MCP docs internally consistent.
2. Establish `docs/tool_inventory.md` as the canonical full catalog unless `docs/mcp.md` is expanded to all 77 tools.
3. Add generated-doc drift checking to the normal local/CI gate.
4. Clarify MCP cancellation semantics in user and architecture docs.
5. Add tests/checks that prevent the same stale-count/catalog drift from recurring.

## Non-Goals

- Do not add additional MCP tools in this pass.
- Do not refactor the large new manifest/diff/repo-audit modules unless tests fail.
- Do not add runtime dependencies.
- Do not implement preemptive Python thread cancellation.
- Do not make MCP tools filesystem-reading or network-backed.
- Do not expand minimal Codegg profiles unless profile tests reveal a clear mistake.

## Phase 1: Fix README Drift and Catalog Wording

### Problem

README contains a stale hardcoded count in the Features section:

- Current stale wording: `MCP Server: 64 deterministic text, JSON, validation, math, and path tools for AI agents`.
- Actual generated inventory: 77 tools across 18 categories.

README also says `docs/mcp.md` is the full tool catalog, while `docs/tool_inventory.md` reports 13 tools missing from `docs/mcp.md`.

### Implementation Steps

1. Update the README feature bullet to avoid a hardcoded count or use generated-safe wording.

   Preferred wording:

   ```markdown
   - **MCP Server**: deterministic text, JSON, validation, math, path, manifest, patch, and repo-audit tools for AI agents
   ```

   Alternative if count is retained:

   ```markdown
   - **MCP Server**: 77 deterministic tools across 18 categories for AI agents
   ```

   Prefer avoiding the count unless README is generated or tested against source.

2. Update the MCP section wording so it accurately names the source of truth:

   ```markdown
   See [docs/tool_inventory.md](docs/tool_inventory.md) for the complete generated tool inventory. See [docs/mcp.md](docs/mcp.md) for protocol usage, configuration, profiles, schema detail, and selected tool examples.
   ```

3. Grep/search for stale `64 tools`, `15 categories`, and `full tool catalog` wording across:

   - `README.md`
   - `docs/mcp.md`
   - `docs/tool_inventory.md`
   - `AGENTS.md`
   - `architecture/mcp.md`
   - `docs/index.md`, if present
   - `docs/cli.md`, if present
   - generated docs and manpage if present

4. Decide one policy:

   - Policy A, preferred: README never hardcodes the tool count; generated inventory owns the count.
   - Policy B: README may hardcode the count only if a test checks it against `len(TOOL_HANDLERS)` or generated inventory.

### Acceptance Criteria

- No stale `64 tools` or `15 categories` claims remain unless intentionally describing historical state.
- README does not describe `docs/mcp.md` as complete if it is not complete.
- README points users to generated inventory for the authoritative tool list.

## Phase 2: Decide and Enforce MCP Documentation Source of Truth

### Problem

`docs/tool_inventory.md` is generated and complete. `docs/mcp.md` is partially hand-written and currently documents only 64 of 77 tools. That is not necessarily wrong, but the semantics need to be explicit.

### Decision Options

#### Option A: Generated Inventory Is the Full Catalog, docs/mcp.md Is Usage/Reference

This is preferred because it minimizes manual drift. Under this model:

- `docs/tool_inventory.md` is the canonical full tool catalog.
- `docs/mcp.md` covers protocol basics, configuration, profiles, schema detail, error envelopes, cancellation semantics, and selected representative tools.
- `docs/mcp.md` should not claim every tool is documented inline.
- The generated inventory may continue reporting `docs/mcp.md` coverage as a useful summary, but the wording should not imply that missing tools are a failure.

#### Option B: docs/mcp.md Must Include All Tools

This is more expensive. Under this model:

- Expand the generator to write a generated full catalog section in `docs/mcp.md` or a companion file included from it.
- `docs/tool_inventory.md` and `docs/mcp.md` both remain complete.
- CI fails if any tool is missing from docs/mcp.md.

### Recommended Implementation: Option A

1. Update `docs/mcp.md` intro to state:

   ```markdown
   This page explains MCP protocol usage, server configuration, profiles, schema-detail controls, and selected examples. The complete generated tool inventory lives in docs/tool_inventory.md.
   ```

2. Rename the `## Available Tools` heading if it implies completeness. Suggested replacements:

   - `## Selected Tool Examples`
   - `## Representative Tools`
   - `## Common Tools`

3. In `scripts/generate_mcp_docs.py`, consider changing summary labels from:

   - `Documented in docs/mcp.md`
   - `Missing from docs/mcp.md`

   to clearer labels if Option A is chosen:

   - `Covered by selected examples in docs/mcp.md`
   - `Not covered by selected examples`

   This avoids making a healthy state look like documentation failure.

4. Update tests that validate tool inventory summary wording if needed.

### Acceptance Criteria

- A reader can tell which file is canonical for the complete catalog.
- `docs/mcp.md` no longer overclaims completeness.
- Generated inventory remains complete and generated.
- The 13 tools missing from `docs/mcp.md` are either documented there or explicitly acceptable as not selected examples.

## Phase 3: Gate Generated Docs in Makefile and CI

### Problem

`Makefile` has a `docs-check` target, but `make check` does not run it. This weakens the generated-doc drift protection.

### Implementation Steps

1. Update `Makefile`:

   ```make
   check: lint format-check typecheck docs-check test
   	@echo "All checks passed!"
   ```

   If docs-check is fast and pure, place it before `test` so drift fails early. If it imports all schema modules and has meaningful startup cost, placing it after typecheck is also acceptable.

2. Update README Development commands if they describe `make check`.

3. Update `AGENTS.md` command section to mention that `make check` includes generated-doc drift.

4. Update CI workflow so generated docs are checked explicitly.

   Preferred explicit step in `.github/workflows/ci.yml`:

   ```yaml
   - name: Check generated docs
     run: python scripts/generate_mcp_docs.py --check
   ```

   Place it after lint/format and before tests.

5. If `make check` is already used in CI in future workflows, the explicit CI step can still remain for clarity.

### Acceptance Criteria

- Running `make check` fails on generated inventory drift.
- CI fails on generated inventory drift.
- Developer docs mention how to regenerate docs.

## Phase 4: Clarify MCP Cancellation Semantics

### Problem

Cancellation is still best-effort. The server checks cancellation records before dispatching tools, but once a tool is running in the thread pool, Python does not preemptively kill the running thread. Timeout handling calls `Future.cancel()`, which only cancels queued work, not already-running work.

### Implementation Steps

1. Add a `## Cancellation and Timeouts` section to `docs/mcp.md`.

   Include these points:

   - `notifications/cancelled` is honored before a queued request starts when possible.
   - Already-running Python tool handlers are not preemptively killed.
   - Tool calls are bounded by `EGGCALC_MCP_MAX_TOOL_TIMEOUT_SECONDS` from the client response perspective.
   - Some child-process-backed operations may continue cleanup after the client receives a timeout response.
   - Tool implementations should remain bounded and deterministic; large inputs should use summary/detail caps.

2. Add/expand `architecture/mcp.md` to explain:

   - threadpool execution model
   - best-effort cancellation
   - timeout response semantics
   - why Python threads are not forcibly killed
   - future path for cooperative cancellation if needed

3. Add a small test if not already present:

   - cancellation before dispatch returns an MCP error result with `error_type=cancelled`.
   - timeout path returns `error_type=timeout` and does not block indefinitely.

4. Do not implement cooperative cancellation in this cleanup unless a minimal hook already exists. Track that as future work if needed.

### Acceptance Criteria

- Docs do not imply preemptive cancellation.
- Cancellation behavior is described accurately enough for Codegg harness expectations.
- Existing cancellation tests pass.

## Phase 5: Inventory Generator Polish

### Problem

Generated inventory is a major improvement, but the output currently truncates several descriptions awkwardly, e.g. `Inspect go.`, `Inspect package.`, `Validate .`, `Extract a value from JSON using RFC 6901 JSON Pointer (e.`. This is not catastrophic, but it looks rough in release docs.

### Implementation Steps

1. Inspect `scripts/generate_mcp_docs.py` description truncation logic.

2. Improve truncation so it does not cut at punctuation artifacts or very short first sentences.

   Reasonable algorithm:

   - Prefer the first sentence if it is between 20 and 100 characters.
   - If the first sentence is too short, include the next sentence until max length.
   - If truncating mid-string, cut at a word boundary and append `...`.
   - Preserve backticked tool terms if possible.

3. Add or update tests for generator summary output if there is an existing test harness.

4. Regenerate `docs/tool_inventory.md`.

### Acceptance Criteria

- Inventory descriptions are readable and not visibly broken.
- The generated file remains deterministic.
- `docs-check` passes after regeneration.

## Phase 6: Verify New Tool Profile Placement

### Problem

The new tools are broadly useful, but profile placement should be checked after the large batch to avoid bloating minimal profiles or hiding tools from intended Codegg workflows.

### Review Checklist

1. `codegg_core_min` should remain small and default-safe.
2. `codegg_core` may include contextual manifest and LLM JSON checks, but should not include heavy repo-audit tools by default unless intentionally chosen.
3. `codegg_repo_audit` should include repo inventory, manifest tools, patch structural tools, and documentation/markdown hygiene tools.
4. `codegg_patch` should include patch structural tools if they are meant for patch workflows.
5. `codegg_config` should include manifest tools only if they are treated as config-like preflight helpers.
6. `default` should not grow unexpectedly with specialized tools unless they are genuinely general-purpose.

### Specific Items to Inspect

- `llm_json_output_check` is in `default`, `codegg_preflight`, and `codegg_core`. This is probably fine because it is cheap and common.
- `repo_file_inventory` is only in `full` and `codegg_repo_audit`. This is good.
- Manifest tools are in `codegg_core`, `codegg_repo_audit`, and `codegg_config`. Confirm this is intentional.
- Patch structural tools should be checked for `codegg_patch` membership.

### Acceptance Criteria

- Profile membership is intentional and documented.
- Generated profile tables reflect expected placement.
- Tests validate profile membership for new tool families.

## Phase 7: Final Verification Gate

After implementing cleanup, run the full suite.

Required local commands:

```bash
ruff check eggcalc tests
black --check eggcalc tests
python scripts/generate_mcp_docs.py --check
python build_single.py
python eggcalc.py "5+3"
pytest tests/ -v
mypy eggcalc --ignore-missing-imports
python -m build
twine check dist/*
```

Recommended MCP smoke test:

```bash
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{"schema_detail":"compact"}}' \
  '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"math_eval","arguments":{"expression":"5+3"}}}' \
  | python eggcalc.py --mcp
```

Expected smoke-test assertions:

- initialize returns server info.
- tools/list returns tools and includes representative new tools such as `pyproject_inspect`, `diff_touched_paths`, and `repo_file_inventory` under full profile.
- math_eval returns `8`.
- No stderr warning about config loading or resource leaks.

## Suggested Commit Structure

Prefer small commits:

1. `docs: fix MCP tool inventory wording drift`
2. `build: include generated docs check in validation gate`
3. `docs: clarify MCP cancellation semantics`
4. `docs: polish generated inventory summaries`
5. `test: assert MCP docs and profile invariants`

## Handoff Checklist

- [ ] README no longer has stale `64 tools` wording.
- [ ] README accurately distinguishes `docs/mcp.md` from `docs/tool_inventory.md`.
- [ ] `docs/mcp.md` clearly states whether it is complete or selected examples.
- [ ] `docs/tool_inventory.md` generated wording is polished and deterministic.
- [ ] `make check` includes `docs-check`.
- [ ] CI includes generated-doc check.
- [ ] Cancellation semantics documented in user docs and architecture docs.
- [ ] New profile membership reviewed and tested.
- [ ] Full verification gate run and results recorded in commit/PR notes.
