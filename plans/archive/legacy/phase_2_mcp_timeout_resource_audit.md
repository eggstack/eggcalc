# Phase 2 Plan — MCP Timeout and Resource-Control Audit

## Objective

Audit and harden the existing MCP tool surface so every current tool has an explicit resource-bound story. The goal is not to add tools. The goal is to ensure the 77-tool MCP surface remains deterministic, stdlib-only, bounded, and suitable for coding-agent use under malformed, oversized, or adversarial inputs.

## Background

The MCP server already has several important controls:

- request byte limit
- output byte limit
- request rate limit
- bounded thread pool
- cancellation record cap
- spawned-process semaphore
- orphan-process cleanup records
- MCP-safe evaluator defaults

The remaining concern is timeout semantics for already-running thread-pool tasks. A timed-out `Future` cannot forcibly stop a running Python thread. Therefore each tool must either be cheap by construction, strongly pre-bounded, early-exiting, or isolated in a subprocess for expensive execution.

## Constraints

Runtime remains stdlib-only.

Do not add new tool families.

Do not make MCP tools filesystem-mutating.

Do not add network access.

Do not rely on flaky wall-clock sleeps in tests.

Do not broadly rewrite the MCP server unless a concrete resource issue requires it.

## Deliverables

1. A resource audit table for all existing MCP tools.
2. Code changes for any tools with insufficient resource bounds.
3. Tests for oversized, pathological, and bounded-output cases.
4. Documentation updates for MCP resource limits and expected error envelopes.
5. CI-green validation including generated docs check and single-file build.

## Resource audit table

Create a tracked document, preferably `docs/mcp_resource_limits.md` or an appendix in `docs/mcp.md`, with one row per tool.

Recommended columns:

- Tool name
- Category
- Tier
- Primary input fields
- Max text/input length
- Max list length or item count
- Max matches/results/hunks/items returned
- Worst-case algorithmic risk
- Current mitigation
- Needs subprocess isolation: yes/no
- Existing tests
- New tests added in this phase
- Notes

The table should include all tools from `TOOL_HANDLERS`, not just tools exposed by the default profile.

## Audit focus areas

### Regex tools

Inspect:

- `validate_regex`
- `regex_finditer`
- `regex_safety_check`

Confirm pattern length, sample count, sample length, match count, subprocess behavior, queue cleanup, process cleanup, and timeout responses. Ensure catastrophic regex patterns cannot occupy worker resources indefinitely.

### Diff and patch tools

Inspect:

- `patch_apply_check`
- `patch_summary`
- `diff_touched_paths`
- `diff_hunk_ranges`
- `diff_file_headers`
- `unified_diff_validate`
- `patch_conflict_markers_inspect`

Confirm limits on diff size, number of files, number of hunks, line count, output size, and conflict marker reporting. Avoid returning huge per-line structures by default.

### JSON and schema tools

Inspect:

- `validate_json`
- `json_canonicalize`
- `json_compare`
- `json_query`
- `json_extract`
- `json_shape`
- `validate_schema_light`
- `structured_data_compare`

Confirm JSON text size limits, nesting depth limits, array/object traversal bounds, duplicate detection costs, and max output size. Pay particular attention to recursive schema validation and unique-item comparisons.

### Unicode and text tools

Inspect:

- `text_measure`
- `text_count`
- `text_equal`
- `text_diff_explain`
- `text_inspect`
- `text_security_inspect`
- `unicode_policy_check`
- `canonicalize_text`
- `text_transform`
- `text_position`
- `text_window`
- `text_truncate`
- `prompt_input_inspect`

Confirm large Unicode text cannot produce huge codepoint/confusable output unless explicitly capped. Ensure confusable and mixed-script scans are linear and bounded by max text length.

### List and identifier tools

Inspect:

- `list_compare`
- `list_dedupe`
- `list_sort`
- `identifier_inspect`
- `identifier_analyze`
- `identifier_table_inspect`

Confirm item count, item length, pairwise comparison behavior, normalization/casefold costs, and collision reporting bounds. Pairwise near-collision or confusable checks can become quadratic and should have explicit limits.

### Manifest/config/path/shell/version tools

Inspect:

- `pyproject_inspect`
- `package_json_inspect`
- `requirements_inspect`
- `go_mod_inspect`
- `cargo_toml_inspect`
- `lockfile_summary`
- `dotenv_validate`
- `ini_validate`
- `validate_toml`
- `toml_shape`
- `path_*`
- `shell_*`
- `version_*`

Confirm all text input limits are enforced before parsing. Confirm parsed structures cannot generate unbounded output for large lockfiles or manifest files.

## Implementation steps

### 1. Build the audit inventory

Start from `TOOL_HANDLERS` and `TOOL_SCHEMAS`, not manually maintained docs. Ensure the audit table catches schema/handler drift.

For each tool, record:

- where input validation happens
- whether `_require_str`, `_validate_str_list`, or schema validation covers it
- whether handler-specific limits exist
- whether output is naturally bounded or only globally capped by `MAX_OUTPUT_BYTES`

### 2. Identify insufficiently bounded tools

Mark any tool as requiring work if:

- it accepts nested structures without depth/item caps
- it performs pairwise comparison without a size guard
- it can return a list proportional to very large input without a max-results cap
- it can perform regex/diff/schema work with pathological complexity
- it relies only on global output truncation rather than producing a useful bounded response
- it can continue executing long after MCP timeout due to non-killable thread execution

### 3. Add small targeted code fixes

Prefer small fixes:

- enforce existing constants consistently
- add max result counts
- add early exits
- add summary-only output when limits are hit
- reject inputs above tool-specific thresholds
- normalize error envelopes

Use subprocess isolation only for truly risky CPU-bound paths. If adding subprocess isolation, reuse existing semaphore and cleanup patterns.

### 4. Add bounded adversarial tests

Tests should prove behavior without relying on long timeouts.

Good test patterns:

- oversized input returns `input_too_large`
- excessive item count returns `input_too_large`
- max match count truncates output and reports `limits_applied`
- pathological regex returns timeout or safety warning within a small controlled case
- huge diff summary truncates predictably
- schema depth above supported max fails clearly
- output too large produces `output_too_large` envelope

Avoid tests that sleep for many seconds or depend on exact system load.

### 5. Validate cancellation and orphan cleanup

Add or review tests for:

- cancellation record FIFO cap
- orphan process record cap
- process cleanup after regex/evaluator timeout
- spawned-process semaphore acquire failure path
- no unbounded accumulation after repeated timed-out calls

These tests can be unit-level where possible rather than full stdio integration tests.

### 6. Update docs

Update MCP docs to describe:

- request byte limit
- output byte limit
- per-tool timeout
- worker count
- spawned-process limit
- rate limit
- expected error types
- how to tune limits with environment variables
- that already-running Python threads cannot be force-killed, so tool inputs are pre-bounded

If adding an audit table document, link it from `docs/mcp.md`.

## Validation commands

Run:

```bash
ruff check eggcalc tests
black --check eggcalc tests
python build_single.py
python scripts/generate_mcp_docs.py --check
pytest tests/ -v
mypy eggcalc --ignore-missing-imports
```

Add manual MCP smoke tests for:

- `initialize`
- `tools/list`
- valid `math_eval`
- oversized `math_eval`
- oversized text tool call
- regex timeout/safety case if applicable

Run both package MCP mode and single-file MCP mode.

## Acceptance criteria

- Every existing MCP tool appears in the resource audit table.
- Every existing MCP tool has explicit input and output bounds.
- Non-linear or potentially expensive tools have early exits, max result counts, or subprocess isolation as appropriate.
- MCP timeout behavior cannot cause unbounded resource accumulation.
- Pathological inputs return structured MCP errors or bounded results.
- New tests cover the highest-risk tools without flaky sleeps.
- Runtime remains stdlib-only.
- CI remains green.

## Handoff notes

Do not combine this phase with feature additions. Keep the scope strictly on existing tool hardening. The likely highest-value fixes are consistent max-result caps and tests, not a large server rewrite.
