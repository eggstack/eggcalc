# MCP Exposure Profiles and Codegg Reference Implementation Plan

This plan is for the next implementation pass on `eggcalc` as the Python reference implementation for deterministic MCP tooling. The Rust implementation already exists separately, so this repo should focus on defining and validating the reference behavior: stable tool contracts, exposure profiles, metadata, composite workflow tools, and documentation/tests that downstream implementations can mirror.

The goal is not to remove the broad tool inventory. The goal is to make the inventory usable by coding agents through stable profiles, machine-readable metadata, compact tool exposure, composite workflow tools, and a clear split between harness-level automatic checks and model-invoked MCP tools.

## Current state summary

The Python MCP server currently exposes a broad deterministic tool registry through `eggcalc.mcp.server.TOOL_HANDLERS`. The inventory documents 59 tools across math, text, Unicode, JSON, TOML, config, regex, path, shell, patch, identifier, markdown, version, Cargo, list, and validation categories. This is a good capability set for a general deterministic utility server and a strong reference implementation.

For `codegg`, however, all 59 tools should not be exposed to every model session by default. Many tools are better used automatically by the harness at side-effect boundaries. Examples include patch applicability checks before edits, path scope checks before writes, shell parsing before command execution, config validation before accepting generated config, and Unicode/prompt hygiene checks before trusting pasted or generated text.

This repo should therefore model the intended reference behavior: broad primitive coverage internally, but controlled MCP exposure through profiles and compact schemas.

## Design decision

Implement exposure management in this Python reference implementation, while keeping `codegg` responsible for runtime policy.

At the `eggcalc` MCP-server layer, add first-class tool metadata, profiles, and composite workflow tools. This makes the Python reference implementation precise and prevents downstream consumers from guessing which tools belong in default agent contexts.

At the `codegg` layer, a thin wrapper should select profiles, apply user/session/model policy, and perform automatic preflight calls directly through library APIs where possible. `codegg` should decide when a task needs `codegg_core`, `codegg_patch`, `codegg_config`, or `codegg_full`, but it should not maintain a brittle hand-written list of every individual tool unless overriding the defaults.

The intended split is:

```text
eggcalc exact primitives      deterministic functions with no MCP assumptions
eggcalc MCP tools             typed wrappers, schemas, findings, machine codes
eggcalc MCP profiles          metadata, tiers, categories, profiles, aliases
eggcalc MCP server            JSON-RPC / MCP adapter exposing selected profiles
codegg                        task/session policy, preflight orchestration, model exposure
```

The core principle is:

```text
Model-invoked tools are optional reasoning aids.
Harness preflight checks are mandatory safety gates.
```

That distinction should be visible in the metadata, profiles, docs, tests, and example integration guidance.

## Phase 1: Patch existing documentation and inventory inconsistencies

Fix these issues before larger architectural changes so the current repo is internally consistent.

### 1. Update `docs/codegg_integration.md`

Current issue: the document says `prompt_input_inspect` is a future tool, but the tool is already present in `TOOL_HANDLERS` and the inventory marks it implemented.

Required change: replace the future-tense sentence with current guidance. The section should say that `prompt_input_inspect` is available and should be used for untrusted user-pasted content, model-returned markdown, terminal transcript paste-ins, issue/PR text, and other text that may include hidden instructions, ANSI escapes, Unicode controls, or suspicious prompt phrases.

### 2. Update `docs/mcp.md` tier references

Current issue: the docs describe `math_eval`, `text_measure`, `text_equal`, and `text_count` as Tier 1 in places, while `TOOL_SCHEMAS` marks several of these as Tier 0.

Required change: ensure all tier labels in `docs/mcp.md`, `docs/tool_inventory.md`, and `TOOL_SCHEMAS` agree. Treat `TOOL_SCHEMAS` as the source of truth unless there is a deliberate reason to change the schema.

### 3. Fix inventory test-count inconsistency

Current issue: `docs/tool_inventory.md` says total tools = 59, have tests = 52, missing tests = 3 (`constant_lookup`, `list_dedupe`, `list_sort`). Those numbers are inconsistent. If only three tools are missing tests, then 56 tools have tests.

Required change: inspect the inventory generator and test detection logic. Either correct the missing-tests list or correct the count. The inventory should be mechanically generated or mechanically validated so this cannot drift.

### 4. Ensure `docs/tool_inventory.md` is generated from a single source of truth

Required change: add or update a script/test that compares:

- `eggcalc.mcp.server.TOOL_HANDLERS`
- `eggcalc.mcp.schemas.TOOL_SCHEMAS`
- `tests/fixtures/mcp_tool_registry_expected.json`
- `docs/tool_inventory.md`

The test should fail if a tool exists in one but not the others, unless the absence is explicitly annotated as intentional.

### 5. Add missing tests for currently untested tools

Minimum required tests:

- `constant_lookup`: known constants, aliases, unknown constant error, non-string input.
- `list_dedupe`: raw dedupe, normalization-aware dedupe, casefold behavior if supported, order preservation, oversized input error.
- `list_sort`: raw sort, normalization-aware sort, casefold behavior if supported, stable output, oversized input error.

If the inventory count reveals additional untested tools, add basic MCP-level tests for those too.

## Phase 2: Add tool metadata model

Add explicit metadata for each MCP tool. Do not rely only on prose descriptions or ad hoc `tier` fields.

Implement a metadata structure in the Python repo that can serve as the reference contract for downstream implementations:

```python
ToolMetadata = {
    "name": str,
    "category": str,
    "tier": int,
    "profiles": list[str],
    "aliases": list[str],
    "llm_exposure": str,
    "harness_use": list[str],
    "cost": str,
    "stability": str,
    "composite": bool,
}
```

Recommended enum values:

```text
category:
  math, text, unicode, json, toml, config, regex, path, shell,
  patch, identifier, markdown, version, cargo, list, validation

tier:
  0 = ultra-common, compact, safe default
  1 = default coding-agent sanity tool
  2 = contextual/heavier analysis
  3 = specialized or domain-specific

llm_exposure:
  default, contextual, expert_only, harness_only, hidden

harness_use:
  edit_preflight, command_preflight, config_preflight, path_preflight,
  prompt_input_preflight, repo_audit, reasoning_only, none

cost:
  cheap, moderate, heavy

stability:
  stable, experimental, deprecated
```

Rules:

1. Every tool in `TOOL_HANDLERS` must have metadata.
2. Every tool in `TOOL_SCHEMAS` must have metadata.
3. Metadata must be included in the `tools/list` result unless explicitly disabled for MCP compatibility.
4. Metadata must be available internally to profile filtering even if not emitted to clients.
5. Tests must assert complete metadata coverage.
6. Metadata should live close to `TOOL_SCHEMAS`, but avoid duplicating tier/category data if possible.

Suggested initial metadata assignments:

Tier 0 / compact primitives:

- `math_eval` only for general/human profiles, not default `codegg` profile.
- `validate_json`
- `path_normalize`
- `text_fingerprint`
- `text_equal`
- `text_measure` only if compact schema mode is available.
- `text_count` only if needed; otherwise keep contextual.

Tier 1 / default coding sanity:

- `text_diff_explain`
- `text_inspect`
- `validate_brackets`
- `validate_regex`
- `regex_safety_check`
- `regex_finditer`
- `line_range_extract`
- `text_replace_check`
- `text_window`
- `escape_text`
- `unescape_text`
- `json_canonicalize`
- `json_compare`
- `json_query`
- `identifier_inspect`
- `glob_match`
- `list_dedupe`
- `list_sort`

Tier 2 / contextual:

- `unit_convert`
- `unit_info`
- `constant_lookup`
- `json_extract`
- `list_compare`
- `line_range_compare`
- `markdown_structure`
- `code_fence_extract`
- `patch_apply_check`
- `patch_summary`
- `path_analyze`
- `path_compare`
- `path_scope_check`
- `shell_split`
- `shell_quote_join`
- `argv_compare`
- `validate_toml`
- `dotenv_validate`
- `ini_validate`
- `toml_shape`
- `version_compare`
- `unicode_policy_check`
- `canonicalize_text`
- `prompt_input_inspect`
- `text_hash`
- `text_position`
- `text_transform`

Tier 3 / specialized:

- `identifier_analyze`
- `identifier_table_inspect`
- `json_shape`
- `text_truncate`
- `validate_schema_light`
- `version_constraint_check`
- `cargo_toml_inspect`

The exact assignment can be adjusted, but the implementation must make the assignment explicit and testable.

## Phase 3: Add server-side profiles

Implement profile-based exposure in the MCP server.

A profile is a named set of tools computed from metadata. Profiles should be declarative and stable. Add tests that assert the exact tool list for each profile.

Recommended profiles:

```text
full
  All stable non-hidden tools.

default
  General-purpose compact profile for broad agent use.

codegg_core_min
  Very small default profile for codegg model-facing tool exposure.

codegg_core
  Practical default profile for codegg model-facing tool exposure.

codegg_preflight
  Tools intended for automatic harness checks. These may be hidden from the model but available to codegg through direct library calls or explicit MCP calls.

codegg_patch
  Patch, replacement, line-range, fingerprint, and diff tools.

codegg_config
  JSON, TOML, dotenv, INI, Cargo.toml, schema-light, and structured comparison tools.

codegg_unicode_security
  Unicode policy, text inspection, canonicalization, prompt input inspection, identifier inspection.

codegg_shell
  shell_split, shell_quote_join, argv_compare, regex_safety_check.

codegg_repo_audit
  identifier_table_inspect, markdown_structure, code_fence_extract, cargo_toml_inspect, text_fingerprint, json_shape.

human_math
  math_eval, unit_convert, unit_info, constant_lookup.
```

Suggested `codegg_core_min` profile:

```text
validate_json
text_diff_explain
path_scope_check
patch_apply_check
text_replace_check
shell_split
unicode_policy_check
```

Suggested `codegg_core` profile:

```text
validate_json
validate_toml
text_diff_explain
text_inspect
text_equal
path_normalize
path_scope_check
patch_apply_check
text_replace_check
shell_split
regex_safety_check
unicode_policy_check
identifier_inspect
cargo_toml_inspect
```

CLI / MCP server behavior:

1. Add `--mcp-profile <name>` to `calc --mcp`.
2. Add `EGGCALC_MCP_PROFILE=<name>` environment variable.
3. CLI flag wins over environment variable.
4. Default behavior should preserve current compatibility at first. Prefer `full` as the default in this Python reference implementation to avoid breaking existing users, but document that `codegg` should use `codegg_core` or `codegg_core_min`.
5. Add `tools/list` filtering by active profile.
6. Reject calls to tools not in the active profile with a clear `tool_not_available_in_profile` error and a hint naming the active profile.
7. Add an optional MCP method or tool for profile introspection if useful, such as `profiles/list` or `tool_profiles`.

Tests:

1. `tools/list` returns only profile-visible tools.
2. Hidden tools cannot be called through MCP under a restricted profile.
3. `full` exposes all stable non-hidden tools.
4. Unknown profile returns a clear startup or request error.
5. Environment variable and CLI precedence are tested.
6. Profile snapshots are stable and intentionally updated when tool exposure changes.

## Phase 4: Add composite workflow tools

Do not collapse primitives. Keep primitives as the canonical tested functions. Add composite tools above them for common agent workflows and codegg preflight boundaries.

Composite tools should have concise schemas and return a single verdict plus structured findings. The output should be optimized for harness consumption and model self-correction.

### Composite tool rules

1. Composite tools must call primitives, not duplicate logic.
2. Composite tools must return compact, stable verdicts.
3. Composite tools must preserve primitive details under a `details` or `subresults` field when `detail="full"`.
4. Composite tools should be included in `codegg_core` or `codegg_preflight` only after tests are mature.
5. Composite tools must not make side effects.
6. Composite outputs should include `machine_code` values suitable for codegg event logs.

### 1. `text_security_inspect`

Implement this first because it reuses already mature Unicode/prompt primitives.

Purpose: provide one compact security-oriented text hygiene pass.

Inputs:

```json
{
  "text": "string",
  "policy": "source_code|prompt|markdown|identifier|default",
  "normalize": "none|NFC|NFD|NFKC|NFKD",
  "compare_normalized": true,
  "detail": "summary|normal|full"
}
```

Internal tools:

- `text_inspect`
- `unicode_policy_check`
- `canonicalize_text`
- `prompt_input_inspect` for prompt/markdown policies
- `identifier_inspect` for identifier policy

Output should include:

```json
{
  "verdict": "allow|review|block",
  "policy": "source_code",
  "findings": [],
  "machine_code": "TEXT_SECURITY_OK|UNICODE_RISK|PROMPT_INJECTION_RISK|IDENTIFIER_COLLISION_RISK",
  "normalized_changed": false,
  "recommended_action": "string",
  "summary": "string"
}
```

### 2. `edit_preflight`

Purpose: validate a proposed edit before applying it.

Inputs:

```json
{
  "original": "string",
  "replacement_mode": "literal|patch|line_range",
  "old": "string|null",
  "new": "string|null",
  "patch": "string|null",
  "start_line": "integer|null",
  "end_line": "integer|null",
  "expected_fingerprint": "string|null",
  "strict": "boolean"
}
```

Internal tools:

- `text_replace_check`
- `patch_apply_check`
- `line_range_extract`
- `text_fingerprint`
- `text_diff_explain` when helpful

Output:

```json
{
  "ok_to_apply": true,
  "mode": "patch",
  "findings": [],
  "machine_code": "EDIT_OK|PATCH_FAILED|AMBIGUOUS_REPLACEMENT|FINGERPRINT_MISMATCH|LINE_RANGE_INVALID",
  "recommended_next_tool": "text_diff_explain|null",
  "summary": "string"
}
```

### 3. `command_preflight`

Purpose: analyze a command before user approval or execution.

Inputs:

```json
{
  "command": "string",
  "platform": "posix|windows|auto",
  "policy": "default|strict|permissive",
  "working_directory": "string|null"
}
```

Internal tools:

- `shell_split`
- `argv_compare` if expected argv is supplied in a later extension
- `regex_safety_check` only when the command appears to include a regex pattern or when explicitly requested

Output should include parsed argv, shell operators, risk findings, and a verdict such as `allow`, `review`, or `block`. Keep the policy conservative but not destructive. This tool must not execute anything.

### 4. `config_preflight`

Purpose: validate generated config text.

Inputs:

```json
{
  "text": "string",
  "format": "auto|json|toml|dotenv|ini|cargo_toml",
  "schema": "object|null",
  "strict": "boolean"
}
```

Internal tools:

- `validate_json`
- `validate_toml`
- `dotenv_validate`
- `ini_validate`
- `cargo_toml_inspect`
- `validate_schema_light` when a schema is supplied
- `json_canonicalize` optionally for JSON
- `toml_shape` optionally for TOML

Output should include valid/invalid, detected format, parse error location, structural summary, and machine code.

### 5. `structured_data_compare`

Purpose: compare structured config/data output without forcing the model to choose between multiple JSON tools.

Inputs:

```json
{
  "a": "string",
  "b": "string",
  "format": "json",
  "ignore_object_order": true,
  "ignore_array_order": false,
  "max_diffs": 50
}
```

Initial implementation can support JSON only. Later TOML support can be added if needed.

Internal tools:

- `json_compare`
- `json_canonicalize`
- `json_shape`
- `json_query` only if query inputs are added later

## Phase 5: Add compact schema mode for LLM exposure

The current schema descriptions are useful but can be verbose. Add a compact schema/listing mode for model-facing exposure.

Implement one of these options:

Option A: add a profile property `schema_detail` with values `compact`, `normal`, `full`.

Option B: add MCP server setting `--mcp-schema-detail compact|normal|full`.

Option C: have each profile specify whether descriptions are compacted.

Recommended: support B first, then allow profiles to set defaults.

Compact mode should:

1. Preserve tool names, required arguments, types, enums, and short descriptions.
2. Remove long examples and verbose explanation text.
3. Preserve machine-readable metadata.
4. Not alter runtime validation.
5. Be deterministic so downstream implementations can compare generated tool listings.

Tests:

1. Compact schema remains a valid JSON schema subset.
2. Compact schema contains all required fields.
3. Compact schema is materially smaller than full schema.
4. Runtime behavior is identical regardless of schema detail.

## Phase 6: Define codegg integration policy in this repo

Update `docs/codegg_integration.md` after profiles exist.

Required recommendations:

1. `codegg` should call deterministic preflight checks automatically through direct library APIs when linked in-process.
2. `codegg` should use MCP exposure primarily for model-invoked reasoning, debugging, and self-correction.
3. `codegg` should not expose all tools by default.
4. `codegg` should use `codegg_core_min` or `codegg_core` as the default model-facing profile.
5. `codegg` should enable contextual profiles based on task mode:

```text
editing/refactor task      -> codegg_patch
config task                -> codegg_config
shell/terminal task        -> codegg_shell
suspicious paste/input     -> codegg_unicode_security
repo audit/deep review     -> codegg_repo_audit
math/unit work             -> human_math only when relevant
```

6. `codegg` should treat side-effect boundaries as mandatory preflight points:

```text
before applying edits       -> edit_preflight or patch/text primitives
before command execution    -> command_preflight or shell primitives
before accepting config     -> config_preflight or config validators
before resolving write path -> path_scope_check/path_normalize
before trusting pasted text -> text_security_inspect or prompt/unicode primitives
before large rename         -> identifier_inspect/identifier_table_inspect
```

7. `codegg` should store machine codes and findings in its event log so users can audit why a command/edit/config was blocked or flagged.
8. `codegg` should display concise user-facing warnings but keep full structured details available for debugging.
9. `codegg` should be able to override the active profile, but profile defaults should come from this repo’s reference definitions.

## Phase 7: Backward compatibility and deprecation policy

Profiles and composites should not break current users.

1. Keep existing tool names stable.
2. Add aliases only when needed; do not silently rename tools.
3. Keep `full` profile available.
4. Preserve current `calc --mcp` behavior initially, unless release notes clearly announce a default profile change.
5. If a tool becomes `harness_only` or hidden in a restricted profile, it should still be callable under `full` unless genuinely deprecated.
6. Add changelog entries for profile support, compact schemas, and composite tools.
7. Keep primitive tool outputs stable. Composite tools may be marked experimental until their verdicts and machine codes settle.

## Phase 8: Acceptance criteria

This pass is complete when:

1. Documentation inconsistencies are fixed.
2. Inventory count and missing-test list are correct.
3. Missing tests for `constant_lookup`, `list_dedupe`, and `list_sort` are added, plus any other missing tests found by the corrected inventory logic.
4. Every MCP tool has explicit metadata.
5. Server-side profiles exist and are tested.
6. `calc --mcp --mcp-profile codegg_core` or equivalent works.
7. `tools/list` respects the selected profile.
8. Calls to tools outside the active profile return a clear structured error.
9. At least `codegg_core_min`, `codegg_core`, `codegg_preflight`, `codegg_patch`, `codegg_config`, `codegg_unicode_security`, `codegg_shell`, `codegg_repo_audit`, `human_math`, and `full` profiles exist.
10. At least one composite tool is implemented and tested, preferably `text_security_inspect` first.
11. `docs/codegg_integration.md` explains how codegg should combine automatic preflight checks with model-facing MCP exposure.
12. Compact schema mode exists and is tested.
13. CI passes.

## Suggested implementation order for a smaller model

Use this order to minimize breakage:

1. Patch docs and inventory inconsistencies.
2. Add tests for currently missing tool coverage.
3. Add metadata structure without changing runtime behavior.
4. Add tests requiring metadata coverage.
5. Add profile definitions without filtering yet.
6. Add profile snapshot tests.
7. Add profile filtering to `tools/list`.
8. Add profile enforcement to `tools/call`.
9. Add CLI/env profile selection.
10. Add compact schema mode.
11. Add `text_security_inspect` as the first composite tool.
12. Add `edit_preflight` after patch/replacement behavior is verified.
13. Add `command_preflight`, `config_preflight`, and `structured_data_compare` in later passes.
14. Update docs and changelog.

## Notes for implementers

This Python repo is the behavioral reference. Keep the implementation simple, explicit, and testable. Avoid turning profiles into complex dynamic policy. Profiles should answer: “which tools are visible?” Runtime policy should remain with consumers such as `codegg`.

Do not aggressively consolidate primitive tools. Small primitives are easier to test, document, and port. Add composite tools only as workflow-oriented wrappers over those primitives.

When in doubt, prefer stable machine-readable outputs over prose. The main downstream consumer is a coding harness that needs deterministic findings, verdicts, and machine codes more than explanatory text.
