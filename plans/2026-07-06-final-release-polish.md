# Final Release Polish Plan

Date: 2026-07-06
Repo: `eggstack/eggcalc`
Target branch: `main`
Scope: final non-blocking polish after MCP tool expansion and documentation cleanup.

## Summary

The repo is now in good shape after the MCP tool-polish and post-cleanup passes. The major issues have been addressed: the stale README count was removed, `docs/tool_inventory.md` is established as the complete generated catalog, `docs/mcp.md` now clearly presents protocol/configuration/profile guidance plus selected examples, generated-doc drift is checked in Makefile and CI, and MCP cancellation semantics are documented honestly.

This final pass should be small. Focus on polish and verification only. Do not add new tools or refactor major MCP internals unless a verification step exposes a real defect.

## Current Remaining Items

1. `Makefile` has a `docs-check` target but `.PHONY` does not list `docs-check`.
2. Generated inventory descriptions are improved but still have some awkward truncations ending mid-word or mid-clause.
3. GitHub combined status did not show check statuses for the latest commit from the connector, so CI pass/fail should be verified through Actions UI/logs or a fresh local run.
4. The docs now correctly distinguish complete inventory from selected examples, but there should be one final grep for stale count/catalog wording.
5. The new 77-tool surface should get one final smoke check through single-file MCP mode and installed-package MCP mode.

## Non-Goals

- Do not add new MCP tools.
- Do not redesign schema detail modes.
- Do not implement cooperative cancellation in this pass.
- Do not change profile membership unless a test or generated table exposes a clear mismatch.
- Do not introduce runtime dependencies.
- Do not expand `docs/mcp.md` into a complete hand-written catalog.

## Phase 1: Makefile `.PHONY` Cleanup

### Problem

`docs-check` is now part of `make check`, but `.PHONY` lists `generate-docs` and omits `docs-check`.

### Implementation Steps

1. Update the first line of `Makefile` from approximately:

   ```make
   .PHONY: help install dev test lint format check clean build publish docs generate-docs
   ```

   to:

   ```make
   .PHONY: help install dev test lint format check clean build publish docs generate-docs docs-check
   ```

2. Confirm `make docs-check` still runs:

   ```bash
   python3 scripts/generate_mcp_docs.py --check
   ```

3. Keep the change minimal. No target reordering is necessary.

### Acceptance Criteria

- `docs-check` is listed in `.PHONY`.
- `make check` still includes `docs-check`.
- `make help` still describes generated-doc checking accurately.

## Phase 2: Polish Generated Inventory Description Truncation

### Problem

The generated inventory is semantically correct, but some descriptions still read awkwardly because truncation can cut phrases or words. Examples observed include descriptions ending like:

- `optional...`
- `conte...`
- `ignori...`
- `Extract metadata from diff file headers: diff --git line, index hash, mode...`

This is cosmetic, but the generated inventory is now the canonical catalog, so it should read cleanly.

### Implementation Steps

1. Inspect `scripts/generate_mcp_docs.py` description summarization/truncation helper.

2. Replace the current truncation logic with a deterministic helper that uses these rules:

   - Normalize whitespace to single spaces.
   - Prefer the first complete sentence if it is at least 40 characters and at most the max length.
   - If the first sentence is very short, append the second sentence if the combined result fits.
   - If no sentence-boundary result fits, truncate at a word boundary before `max_len - 3` and append `...`.
   - Never truncate below a minimum useful length unless the source description itself is shorter.
   - Avoid returning strings ending with punctuation fragments such as `e.`, `co...`, or an unmatched open parenthesis.

3. Consider using a larger max length for the inventory notes column if line width remains acceptable. A max around 120–140 characters is acceptable in Markdown tables.

4. Add focused unit tests if the generator has tests. If not, add a small test in `tests/test_tool_inventory.py` that calls the helper directly, or indirectly validates known tool descriptions in generated output.

5. Regenerate the inventory:

   ```bash
   python scripts/generate_mcp_docs.py
   ```

6. Run:

   ```bash
   python scripts/generate_mcp_docs.py --check
   ```

### Acceptance Criteria

- No generated inventory note ends in a visibly cut word fragment like `conte...`, `ignori...`, or `option...`.
- No generated inventory note ends in an incomplete parenthetical.
- The generated file remains deterministic.
- `docs-check` passes.

## Phase 3: Final Stale-Wording Sweep

### Problem

The obvious stale README wording was fixed, but a final sweep should ensure there are no leftover pre-expansion claims.

### Search Terms

Run a repository-wide search for:

```bash
grep -RIn "64 tools\|15 categories\|full tool catalog\|Available Tools\|minimal\|coding-agent-default\|text-unicode-heavy\|config-heavy\|rust-project" README.md docs architecture AGENTS.md .github Makefile scripts tests || true
```

Review each hit manually. Some terms may be valid in historical plan files under `plans/`; exclude `plans/` from this final release check unless intentionally auditing handoff history.

### Implementation Steps

1. Fix stale public docs under:

   - `README.md`
   - `docs/`
   - `architecture/`
   - `AGENTS.md`
   - `.github/workflows/`

2. Do not rewrite historical plan files.

3. If tests contain old names as fixtures, verify whether they are historical compatibility tests or stale expectations.

### Acceptance Criteria

- No public-facing current docs claim 64 tools or 15 categories.
- No current docs call `docs/mcp.md` the full catalog.
- Old profile names are gone from current docs unless explicitly marked legacy.

## Phase 4: Verify CI Visibility and Local Gate

### Problem

The connector did not return combined status entries for the latest cleanup commit. The CI file itself looks correct, but release confidence requires a verified green run.

### Implementation Steps

1. Check GitHub Actions for the latest commit on `main` and record whether the CI workflow passed.

2. If GitHub Actions did not run, determine why:

   - workflow disabled
   - branch/path filters
   - missing Actions permissions
   - commit pushed through contents API but workflow not triggered as expected

3. Run the local gate on a clean checkout:

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

4. If `make check` is intended as the standard local gate, run it too:

   ```bash
   make check
   ```

5. Record results in the final commit message or PR notes.

### Acceptance Criteria

- GitHub Actions status is known and green, or the reason it is unavailable is documented.
- Local full gate passes.
- `make check` includes generated-doc drift checking.

## Phase 5: MCP Smoke Tests

### Goal

Confirm the expanded MCP surface works in both source-tree and single-file modes.

### Source-Tree MCP Smoke Test

```bash
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{"schema_detail":"compact"}}' \
  '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"math_eval","arguments":{"expression":"5+3"}}}' \
  | python -m eggcalc --mcp
```

Expected:

- `initialize` returns protocol and server info.
- `tools/list` returns a compact tool list.
- `math_eval` returns `8`.

### Single-File MCP Smoke Test

```bash
python build_single.py
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{"schema_detail":"compact"}}' \
  '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"pyproject_inspect","arguments":{"content":"[project]\nname = \"demo\"\nversion = \"0.1.0\"\n"}}}' \
  | python eggcalc.py --mcp
```

Expected:

- `pyproject_inspect` is present and callable in single-file mode.
- No `NameError` or missing-module errors from newly added exact modules.
- No stderr noise about config loading.

### Installed Package MCP Smoke Test

In a clean virtualenv after building/installing the wheel:

```bash
python -m build
python -m venv /tmp/eggcalc-smoke
/tmp/eggcalc-smoke/bin/python -m pip install dist/*.whl
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{"schema_detail":"normal","profile":"codegg_repo_audit"}}' \
  | /tmp/eggcalc-smoke/bin/calc --mcp
```

Expected:

- `codegg_repo_audit` profile resolves.
- Representative tools are visible: `repo_file_inventory`, `pyproject_inspect`, `diff_touched_paths`, and `markdown_link_check_lexical`.

### Acceptance Criteria

- Source-tree, single-file, and installed-wheel MCP smoke tests pass.
- New exact modules are included in single-file build.
- Profile filtering works for the expanded tool surface.

## Phase 6: Optional Documentation Micro-Polish

Only do this if the prior phases are clean.

1. In `README.md`, consider linking directly to `docs/tool_inventory.md` from the MCP feature bullet or MCP paragraph only once; avoid duplicate links.
2. In `docs/mcp.md`, keep tier lists short. Since `tool_inventory.md` is authoritative, consider replacing long inline tier lists with a compact summary plus link if they become stale-prone.
3. In `docs/tool_inventory.md`, consider adding a one-line note explaining that `README` coverage is expected to be zero because README intentionally delegates full catalog coverage to generated inventory.

### Acceptance Criteria

- Docs remain concise.
- No new hardcoded counts are introduced outside generated inventory or tested docs.

## Suggested Commit Structure

Prefer one or two small commits:

1. `build: mark docs-check phony and verify generated docs`
2. `docs: polish generated inventory summaries`

If only `.PHONY` and verification notes change, one commit is enough.

## Final Handoff Checklist

- [ ] `docs-check` added to `.PHONY`.
- [ ] Generated inventory notes no longer visibly truncate mid-word.
- [ ] `python scripts/generate_mcp_docs.py --check` passes.
- [ ] Stale wording sweep completed for current docs.
- [ ] GitHub Actions status checked or absence explained.
- [ ] `make check` passes.
- [ ] Full local release gate passes.
- [ ] Source-tree MCP smoke test passes.
- [ ] Single-file MCP smoke test passes.
- [ ] Installed-wheel MCP smoke test passes.
- [ ] Final commit/PR notes record verification results.
