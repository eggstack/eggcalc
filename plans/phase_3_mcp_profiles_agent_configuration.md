# Phase 3 Plan — MCP Profiles and Agent Configuration

## Objective

Make the existing MCP profile system operationally clear for coding agents while preserving backward compatibility. The phase should improve documentation, tests, and examples around existing profiles. It should not add new tool families or runtime dependencies.

## Background

The MCP server supports profiles and schema-detail controls. The current default profile is `full`, primarily for backward compatibility and exploration. For production coding-agent use, narrower profiles such as `codegg_core_min` and `codegg_core` are better defaults because they reduce tool-list context, reduce accidental tool selection, and make tool exposure easier to reason about.

The repo should make this guidance explicit and test that profile definitions do not drift from schemas or handlers.

## Constraints

Runtime remains stdlib-only.

Do not add new tools under this phase.

Do not remove existing profiles without a separate compatibility/deprecation decision.

Do not break existing clients that rely on `full` unless an explicit breaking-change release is approved.

Do not make MCP write to filesystem or use network access.

## Desired profile model

Document profiles with this conceptual model:

- `full`: compatibility and human exploration. Exposes the broad stable surface except hidden tools.
- `default`: general-purpose compact profile if currently present and intended for default use.
- `codegg_core_min`: safest low-context coding-agent default.
- `codegg_core`: recommended normal coding-agent profile.
- `codegg_preflight`: preflight checks for generated outputs, commands, configs, and edits.
- `codegg_patch`: patch and diff workflows.
- `codegg_config`: configuration and structured data workflows.
- `codegg_unicode_security`: Unicode, confusable, and prompt/input hygiene workflows.
- `codegg_shell`: shell parsing and command preflight workflows.
- `codegg_repo_audit`: repo inventory and manifest inspection workflows.
- `human_math`: calculator/unit/constant profile for human calculation tasks.

Adjust exact descriptions to match the actual `TOOL_PROFILES` definitions in source.

## Implementation steps

### 1. Inspect profile definitions

Review `eggcalc/mcp/schemas.py` for:

- `TOOL_PROFILES`
- `PROFILE_NAMES`
- `TOOL_METADATA`
- `TOOL_SCHEMAS`
- `compact_schema()`
- `normal_schema()`

Review `eggcalc/mcp/server.py` for:

- default profile selection
- `get_profile_tools()`
- profile enforcement in `tools/call`
- profile filtering in `tools/list`
- schema-detail handling

Confirm whether `full` is intentionally omitted from `TOOL_PROFILES` but supported specially, and document this behavior if so.

### 2. Validate schema/handler/profile consistency

Add tests that assert:

- every `TOOL_PROFILES` entry refers to a tool in `TOOL_SCHEMAS`
- every `TOOL_PROFILES` entry refers to a tool in `TOOL_HANDLERS`
- every public `TOOL_HANDLERS` entry has a schema, unless intentionally hidden and documented
- every schema tool intended for exposure has a handler
- `get_profile_tools("full")` excludes tools whose metadata says `llm_exposure == "hidden"`
- `tools/list` with a profile only returns that profile's tools
- `tools/call` rejects a tool outside the active profile
- `tools/list` supports `profile`, `tier`, `tags`, `names`, and `schema_detail` together

Keep these as deterministic unit tests against server functions where possible.

### 3. Review profile contents for agent ergonomics

Without adding new tools, review whether each profile is coherent:

- Does `codegg_core_min` include only ultra-common low-context deterministic tools?
- Does `codegg_core` include enough tools for normal coding-agent text/config/path/math use?
- Are patch tools grouped coherently in patch profiles?
- Are shell tools separated enough to avoid exposing them by accident?
- Are Unicode/security tools available through a focused profile?
- Are manifest/repo-audit tools not accidentally included in the minimal profile unless intended?

If profile membership changes, update tests and generated docs together.

### 4. Document profile selection

Update `docs/mcp.md` with a dedicated profile section.

For each profile, document:

- purpose
- recommended consumer
- rough size/context cost: minimal, normal, broad, specialized
- example `EGGCALC_MCP_PROFILE` value
- when not to use it

Make the recommendation explicit:

- production coding agents should start with `codegg_core_min` or `codegg_core`
- use specialized profiles for focused workflows
- use `full` for exploration, compatibility, or human inspection

### 5. Add MCP client examples

Add copy-paste examples using only generic MCP environment variables and stdio command forms. Avoid vendor-specific claims unless already documented.

Examples to include:

```bash
EGGCALC_MCP_PROFILE=codegg_core_min calc --mcp
EGGCALC_MCP_PROFILE=codegg_core EGGCALC_MCP_SCHEMA_DETAIL=normal calc --mcp
EGGCALC_MCP_PROFILE=codegg_patch EGGCALC_MCP_SCHEMA_DETAIL=compact calc --mcp
EGGCALC_MCP_PROFILE=codegg_unicode_security calc --mcp
```

Also include JSON-RPC examples:

- `tools/list` default active profile
- `tools/list` with `profile`
- `tools/list` with `schema_detail=compact`
- `tools/list` with `tier=0`
- rejected `tools/call` outside active profile

### 6. Consider default-profile behavior

Evaluate whether to keep `full` as default for compatibility. The recommended conservative choice is to keep it for now but document that agents should set `EGGCALC_MCP_PROFILE` explicitly.

If adding a warning for implicit `full`, do it carefully. MCP clients can be sensitive to stderr. Prefer docs over runtime warnings unless there is already a safe logging pattern.

If changing the default profile is desired, that should be a separate breaking-change plan with changelog entry and migration note.

### 7. Regenerate docs

Run the MCP doc generator after any schema/profile/doc changes:

```bash
python scripts/generate_mcp_docs.py
python scripts/generate_mcp_docs.py --check
```

Commit generated changes together with source changes.

## Tests to add or update

Recommended test names:

- `test_all_profile_tools_have_schemas_and_handlers`
- `test_full_profile_excludes_hidden_tools`
- `test_tools_list_profile_filter_returns_only_profile_tools`
- `test_tools_call_rejects_tool_outside_active_profile`
- `test_tools_list_schema_detail_compact_is_smaller_than_full`
- `test_profile_names_are_documented_or_generated`

If docs cannot be tested directly, ensure generated inventory catches drift.

## Documentation acceptance criteria

Docs should answer these questions without requiring source inspection:

- Which MCP profile should a coding agent use first?
- What is the difference between `codegg_core_min` and `codegg_core`?
- What is `full` for?
- How does a user set a profile?
- How can a client list tools for a profile without switching the active profile?
- How can schema detail be reduced?
- What happens if a client calls a tool outside the active profile?

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

Manual MCP smoke tests:

```bash
EGGCALC_MCP_PROFILE=codegg_core_min calc --mcp
EGGCALC_MCP_PROFILE=codegg_core calc --mcp
EGGCALC_MCP_PROFILE=codegg_patch calc --mcp
```

For each, send `initialize`, `profiles/list`, `tools/list`, and one allowed `tools/call`. Also send one disallowed `tools/call` and verify a clear JSON-RPC error.

## Acceptance criteria

- Profile definitions are covered by consistency tests.
- Docs clearly recommend `codegg_core_min` or `codegg_core` for coding agents.
- `full` remains documented as compatibility/exploration unless a separate breaking-change decision changes it.
- JSON-RPC examples show profile and schema-detail use.
- No new runtime dependencies are introduced.
- Existing tools remain available under intended profiles.
- CI remains green.

## Handoff notes

Keep this phase mostly docs and tests. Avoid expanding the tool inventory. If profile membership changes, keep those changes small and justify each move in commit text or PR notes.
