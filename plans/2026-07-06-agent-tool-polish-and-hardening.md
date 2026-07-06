# Agent Tool Polish and Hardening Plan

Date: 2026-07-06
Repo: `eggstack/eggcalc`
Target branch: `main`
Scope: correctness fixes, MCP ergonomics, agent-useful deterministic tools, generated documentation, and release-polish validation.

## Context

`eggcalc` has evolved from a natural-language calculator into a standard-library-only CLI/library/MCP utility bundle. The current MCP surface exposes deterministic tools across math, text, JSON, validation, regex, list, path, identifier, shell, markdown, config, version, TOML, Cargo, and Unicode categories. The repo is in good beta shape, but several items should be closed before treating the agent-tool surface as stable.

The goal of this pass is not to broaden the project into a general execution harness. Preserve the existing design constraints:

- Runtime package remains standard-library only.
- MCP tools remain deterministic and side-effect-free unless explicitly documented otherwise.
- Tools should accept caller-provided text/data rather than reading the filesystem.
- Single-file build compatibility must be preserved.
- Capability should not regress for current CLI, library, or MCP consumers.
- Codegg-facing profiles should stay small and useful rather than exposing every niche primitive by default.

## Current Findings to Address

### 1. Windows and UNC path normalization correctness risk

`eggcalc/exact/path_tools.py::path_normalize()` currently selects a separator by platform and then splits the original path directly. For Windows drive-letter paths, the drive prefix can remain in the component list and later be prepended again. UNC handling also appears brittle because the special tracking logic treats literal component strings such as `server` and `share` as sentinels instead of preserving arbitrary server/share names.

Representative cases to cover:

- `C:\foo\..\bar` should normalize to `C:\bar`.
- `C:/foo/../bar` under Windows mode should normalize to `C:\bar`.
- `C:\` should remain `C:\` or an explicitly documented normalized equivalent.
- `C:foo\bar` should be treated consistently as drive-relative, not absolute if that is the chosen policy.
- `\\server\share\dir\..\file` should normalize to `\\server\share\file`.
- `//server/share/dir/../file` under Windows mode should normalize to a UNC path, not collapse the server/share root.
- Relative paths such as `foo\..\bar` should normalize to `bar`.
- Excess leading `..` in relative paths should be preserved, e.g. `..\..\x`.

Implementation plan:

1. Add failing tests first in the existing path-tools test file or a new `tests/test_path_windows_normalize.py`.
2. Introduce a small internal parser such as `_parse_path_root(path, platform) -> tuple[root, tail, is_absolute, root_kind]`.
3. Normalize separators before splitting the tail, not after root detection.
4. For Windows:
   - Detect UNC roots before drive-letter roots.
   - Preserve arbitrary UNC server/share components as the immutable root.
   - Treat `C:\foo` as absolute drive-rooted.
   - Decide and document whether `C:foo` is drive-relative; if supported, preserve `C:` as root-like metadata but do not call it absolute.
5. Collapse `.` and `..` only within the tail. Never pop past an absolute root or UNC share root.
6. Keep `path_analyze()`, `path_compare()`, and `path_scope_check()` behavior compatible unless tests reveal they consume malformed normalization output.
7. Add regression tests for `path_compare()` and `path_scope_check()` on the corrected normalization behavior.

Acceptance criteria:

- All listed Windows/UNC cases pass.
- POSIX behavior is unchanged for existing tests.
- `path_scope_check()` does not incorrectly classify sibling prefixes as inside root.
- Docs explicitly state lexical-only behavior and Windows drive-relative limitations.

### 2. MCP cancellation semantics and worker occupancy

The MCP server records cancelled request IDs and checks them before tool dispatch, but a cancellation notification does not stop a tool that is already running in the thread pool. `Future.cancel()` only succeeds before execution starts. This can leave expensive work occupying a worker until it finishes or reaches timeout.

Implementation plan:

1. Document current cancellation semantics in `docs/mcp.md` and architecture docs: cancellation is best-effort once a tool has started.
2. Add an internal cooperative cancellation registry keyed by JSON-RPC request id.
3. Pass a cancellation-check callback or context object to tool handlers that can benefit from cooperative cancellation.
4. Start with long-iteration tools only:
   - regex scanning tools
   - text diff/window/position tools over large input
   - schema/JSON shape traversal
   - patch/diff tools once added or refactored
5. Do not expose cancellation parameters in public tool schemas unless necessary.
6. For subprocess-backed evaluation/regex paths, ensure cancellation paths terminate child processes promptly where technically feasible.
7. Add tests at the server layer for:
   - cancellation before dispatch
   - cancellation after queueing but before worker begins
   - cancellation during a cooperative long-running mock tool
   - worker pool does not permanently leak capacity after cancellation

Acceptance criteria:

- Existing cancellation behavior remains compatible for clients.
- New docs clearly describe best-effort limits.
- Cooperative tools can exit early when cancelled.
- Timeout and cancellation error envelopes remain sanitized and deterministic.

### 3. MCP limits should be configurable with safe defaults

Several MCP server limits are hardcoded: request bytes, output bytes, requests per second, max tool timeout, and worker pool size. These are sane public defaults but can bottleneck local trusted harnesses such as Codegg.

Implementation plan:

1. Add environment-variable parsing helpers in `eggcalc/mcp/server.py` for positive integers/floats with min/max clamping and warning-free fallback.
2. Proposed environment variables:
   - `EGGCALC_MCP_MAX_REQUEST_BYTES`
   - `EGGCALC_MCP_MAX_OUTPUT_BYTES`
   - `EGGCALC_MCP_MAX_REQUESTS_PER_SECOND`
   - `EGGCALC_MCP_MAX_TOOL_TIMEOUT_SECONDS`
   - `EGGCALC_MCP_MAX_TOOL_WORKERS`
   - `EGGCALC_MCP_MAX_CANCELLED_REQUESTS`
3. Preserve current constants as defaults.
4. Add tests for default values, valid overrides, invalid overrides, too-low overrides, and too-high overrides.
5. Include these settings in `docs/mcp.md`, `README.md` MCP section, and architecture MCP docs.
6. Keep profile and schema-detail env vars documented alongside the new limit env vars.

Acceptance criteria:

- Existing behavior is unchanged without env vars.
- Invalid env vars cannot crash server startup.
- Limits cannot be configured to unsafe zero/negative values.
- Docs include safe examples for local trusted harnesses.

### 4. Implement real `normal` schema detail

`compact_schema()` exists, but `normal_schema()` currently returns the full schema. Since schema detail is part of the public MCP ergonomics surface, `normal` should be meaningfully different from `full` while preserving enough information for model use.

Implementation plan:

1. Define schema-detail semantics:
   - `compact`: smallest practical model-facing schema; preserve argument names, types, enums, required fields, and critical constraints.
   - `normal`: default ergonomic schema; preserve descriptions, required fields, constraints, top-level output schema, and selected nested structure; remove verbose examples and repetitive detail.
   - `full`: complete schema as authored.
2. Implement `normal_schema()` in `eggcalc/mcp/schemas.py`.
3. Update `_handle_list_tools()` to call `normal_schema()` when detail is `normal`; currently non-compact returns the full schema.
4. Add snapshot tests comparing approximate serialized sizes for full > normal > compact on representative tools.
5. Add tests that all required inputs remain present in normal and compact schemas.
6. Update docs to recommend:
   - `compact` for constrained model context.
   - `normal` for default agent discovery.
   - `full` for human debugging and generated reference docs.

Acceptance criteria:

- `tools/list` with `schema_detail=normal` differs from `full`.
- `normal` remains sufficient for agents to call tools correctly.
- No current clients are broken because default env behavior is either preserved or explicitly migrated with tests.

### 5. Generate MCP inventory/reference docs to prevent drift

The repo has `TOOL_SCHEMAS`, `TOOL_METADATA`, `TOOL_PROFILES`, a fixture-backed inventory, README references, and `docs/mcp.md`. Drift is the major long-term maintenance risk.

Implementation plan:

1. Add a standard-library-only script such as `scripts/generate_mcp_docs.py`.
2. Generate at least:
   - tool count
   - category breakdown
   - tool inventory table
   - profile membership table
   - tier/tag table
   - schema-detail explanation
3. Use stable ordering: profile order from `PROFILE_NAMES`, tool order alphabetical within category/profile unless a canonical order already exists.
4. Choose one of two approaches:
   - fully generate `docs/tool_inventory.md`, or
   - generate a checked fragment between markers in `docs/tool_inventory.md`.
5. Add a CI/test command that runs generation in check mode and fails on drift.
6. Add generated-doc instructions to `AGENTS.md` and architecture docs.
7. Remove hardcoded duplicate counts from README and docs where possible; phrase as “see generated inventory” unless a test maintains the number.

Acceptance criteria:

- Adding/removing/renaming a tool requires updating schema/metadata/fixture and regenerated docs, or CI fails.
- `docs/tool_inventory.md` no longer relies on manually maintained counts.
- README remains concise and delegates full catalog details to generated docs.

### 6. Add deterministic package/manifest inspection tools

The current Cargo-focused inspection is useful for Rust agents, but Codegg-style repo work also needs deterministic manifest inspection for Python, Node, and general dependency files. These should be lexical/structural tools only. They must not resolve versions online or execute package managers.

Candidate tools:

1. `pyproject_inspect`
   - Input: TOML text.
   - Output: project name/version, build backend, requires-python, dependencies count, optional dependency groups, scripts, tool sections, package manager signals.
   - Use `tomllib` on Python 3.11+; for Python 3.10 standard-library-only compatibility, either implement a limited fallback or require callers on 3.10 to use `toml_shape` plus clear error. Prefer a limited fallback only if tractable.

2. `requirements_inspect`
   - Input: requirements-style text.
   - Output: package specs, editable refs, direct URLs, VCS refs, comments, constraints/includes, environment markers as raw strings, suspicious lines.
   - Do not implement a full PEP 508 parser unless intentionally scoped.

3. `package_json_inspect`
   - Input: JSON text.
   - Output: name/version/private/type, scripts keys, dependency/dev/peer/optional counts, engines, packageManager, workspaces summary.

4. `go_mod_inspect`
   - Input: `go.mod` text.
   - Output: module path, go version, toolchain, require count, replace directives, exclude directives.

5. `lockfile_summary`
   - Input: text plus optional lockfile kind enum: `auto`, `package-lock`, `pnpm-lock`, `yarn-lock`, `poetry-lock`, `uv-lock`, `cargo-lock`, `go-sum`.
   - Output: detected kind, approximate package count, ecosystem, warnings. Keep intentionally shallow.

Implementation plan:

1. Create focused modules under `eggcalc/exact/`, likely `python_manifest.py`, `node_manifest.py`, `go_manifest.py`, and `lockfiles.py`, or one `manifests.py` if smaller.
2. Add MCP wrappers and schemas.
3. Assign metadata:
   - category: `manifest` or existing `config`; adding `manifest` is cleaner.
   - tier: 2 or 3.
   - profiles: `full`, `codegg_core`, `codegg_repo_audit`; consider `codegg_config` for config-adjacent tools.
   - llm_exposure: `contextual` or `expert_only`, not default for all tools.
4. Add docs and inventory generation support.
5. Add fixture tests with representative real-world snippets.
6. Include failure tests for malformed JSON/TOML and oversized input.

Acceptance criteria:

- Tools are deterministic and do not touch filesystem/network.
- All new tools have schemas, metadata, docs, inventory, tests, and profile placement.
- Codegg can infer likely build/test commands from manifests without model-side brittle parsing.

### 7. Add richer deterministic patch/diff inspection tools

Existing patch support should be extended so agents can reason about diffs without hand-parsing unified diff text.

Candidate tools:

1. `diff_touched_paths`
   - Input: unified diff text.
   - Output: added/modified/deleted/renamed path lists, binary-file markers, mode changes if detectable.

2. `diff_hunk_ranges`
   - Input: unified diff text.
   - Output: per-file hunk old/new ranges, line counts, added/deleted/context counts.

3. `diff_file_headers`
   - Input: unified diff text.
   - Output: parsed `diff --git`, `---`, `+++`, rename/copy/mode/index metadata.

4. `patch_conflict_markers_inspect`
   - Input: text or diff text.
   - Output: locations of `<<<<<<<`, `=======`, `>>>>>>>`, nested/imbalanced markers, file/hunk context if available.

5. `unified_diff_validate`
   - Input: unified diff text.
   - Output: parse_ok, warnings, malformed hunk headers, inconsistent line counts.

Implementation plan:

1. Reuse existing patch parser logic if available; avoid duplicate parsing logic where `patch_apply_check` and `patch_summary` already parse hunks.
2. If current parser is embedded in tool code, extract a shared internal `exact.patch` parser.
3. Keep output size bounded with max files/hunks/findings options.
4. Place tools in `patch` category, tier 2 unless a composite becomes tier 1.
5. Add these tools to `codegg_patch` and `codegg_repo_audit`; expose only composites to `codegg_core_min` if needed.
6. Add tests for normal diffs, renames, deletes, new files, binary markers, malformed hunks, and conflict markers.

Acceptance criteria:

- Agents can ask “what paths did this patch touch?” without model parsing.
- Malformed diffs produce structured warnings, not crashes.
- Existing `patch_summary`, `patch_apply_check`, and `edit_preflight` behavior does not regress.

### 8. Add repository-audit composite tools with caller-provided file inventories

Repo-audit tools should not read the filesystem. They should accept file lists and selected file contents from the harness, then produce deterministic summaries.

Candidate tools:

1. `repo_file_inventory`
   - Input: list of paths plus optional sizes/hashes.
   - Output: language/ecosystem signals, config/doc/test/source counts, hidden/generated/vendor signals, suspicious Unicode/path warnings.

2. `repo_doc_inventory`
   - Input: map/list of doc path to text.
   - Output: heading structure summaries, broken relative markdown link candidates lexically, duplicate title/heading warnings, missing common docs.

3. `repo_release_readiness_check`
   - Input: file inventory plus selected manifest/docs contents.
   - Output: checklist-style findings for package metadata, README, license, changelog, CI, tests, docs, security policy, generated-doc drift hints.

Implementation plan:

1. Start with `repo_file_inventory`; it is lowest risk and broadly useful.
2. Reuse existing path, markdown, config, and manifest helpers internally.
3. Add strict input caps: max path count, max path length, max total doc bytes.
4. Return structured findings with severity and machine-readable codes.
5. Put in `codegg_repo_audit` profile and `full`; do not put all repo-audit tools in minimal profiles by default.

Acceptance criteria:

- Tools are deterministic and side-effect-free.
- Large repos are bounded and return truncation warnings rather than excessive output.
- Findings are actionable enough for an agent to create a follow-up plan.

### 9. Add LLM-output and markdown hygiene tools

The current Unicode/text-security surface is strong. The remaining gap is structured hygiene for common model-generated artifacts.

Candidate tools:

1. `markdown_link_check_lexical`
   - Input: markdown text and optional known path list.
   - Output: malformed links/images, duplicate anchors, unresolved relative-link candidates, external-link count. No network calls.

2. `frontmatter_validate`
   - Input: text and format enum `auto`, `yaml`, `toml`, `json`.
   - Output: frontmatter present, delimiter style, parse result where standard library supports it, suspicious keys, duplicate delimiter issues.

3. `llm_json_output_check`
   - Input: model output text.
   - Output: detects fenced JSON, leading/trailing prose, JSON parse result, likely fix hints, JSON pointer to first error when possible. It should not silently repair output unless a separate future tool is explicitly designed for repair.

Implementation plan:

1. Start with `llm_json_output_check` and `markdown_link_check_lexical` because both are common in agent loops.
2. Keep schemas small and outputs bounded.
3. Reuse `code_fence_extract`, `validate_json`, and markdown structure helpers.
4. Add to `codegg_preflight`, `codegg_repo_audit`, and `full` as appropriate.

Acceptance criteria:

- Agents can validate model-produced JSON before passing it to strict consumers.
- Markdown hygiene checks are lexical and do not imply network reachability.
- Tools have tests covering fenced JSON, prose-wrapped JSON, invalid JSON, duplicate anchors, and malformed links.

### 10. README and docs simplification

The README is useful but dense. It contains installation, CLI, MCP, API, webapp, and performance material. For release polish, README should be optimized for first contact and link deeper material to docs.

Implementation plan:

1. Keep README sections:
   - one-sentence purpose
   - installation
   - 5–8 representative CLI examples
   - Python API mini-example
   - MCP quickstart and profile/schema-detail note
   - safety/trust-boundary summary
   - links to full docs
2. Move or shorten large API reference sections into `docs/api.md` if not already present.
3. Move large MCP catalog details into generated `docs/tool_inventory.md` and `docs/mcp.md`.
4. Ensure all examples are tested or covered by doctest-like smoke tests where practical.
5. Audit for stale names from `clicalc`/`pycalc` and for hardcoded counts.

Acceptance criteria:

- README is concise enough to scan while still accurate.
- Full API/MCP details remain available in docs.
- No stale project names remain.
- Examples align with current CLI output.

### 11. CI and release-readiness verification

Current CI is strong: lint, format, build single-file, smoke test, pytest with coverage, mypy, package build, twine check, clean wheel install. Add targeted checks for the expanded MCP/documentation surface.

Implementation plan:

1. Add generated-doc drift check for MCP inventory/reference docs.
2. Add single-file MCP smoke test:
   - start `python eggcalc.py --mcp`
   - send `initialize`
   - send `tools/list` with `schema_detail=compact`
   - call `math_eval` or `text_measure`
   - assert valid JSON-RPC response
3. Add package-installed MCP smoke test in the package job if not too slow.
4. Add Windows path tests to normal pytest suite; no Windows runner is required if lexical behavior is platform-independent, but consider adding a Windows CI matrix later if installer/path behavior grows.
5. Add targeted tests for env-var parsing of MCP limits.

Acceptance criteria:

- CI fails if generated docs drift.
- CI fails if single-file MCP mode breaks.
- CI covers the newly fixed Windows path semantics.
- Packaging smoke verifies both library and MCP entry behavior.

## Suggested Execution Order

### Phase 1: Correctness and bounded-server hardening

1. Add Windows/UNC path normalization tests.
2. Fix `path_normalize()` root parsing.
3. Add MCP limit env-var parsing with tests.
4. Document current and improved cancellation semantics.
5. Add cooperative cancellation only where the implementation is low-risk.

Why first: these are correctness and operational ergonomics issues. They should land before broadening tool inventory.

### Phase 2: Schema and docs drift control

1. Implement real `normal_schema()`.
2. Update `tools/list` to honor normal detail.
3. Add schema-size/sufficiency tests.
4. Add MCP doc generator or checked generated fragments.
5. Add CI drift check.
6. Simplify README references to tool inventory.

Why second: new tools should land after schema/doc generation is stable, so future additions follow the correct workflow.

### Phase 3: Manifest/package tools

1. Add `pyproject_inspect`.
2. Add `package_json_inspect`.
3. Add `requirements_inspect`.
4. Add `go_mod_inspect` if still within scope.
5. Add shallow `lockfile_summary` only if it can stay simple and deterministic.
6. Update schemas, metadata, profiles, generated docs, and tests.

Why third: these are high-value for Codegg and other coding agents, but should not distract from correctness/docs foundations.

### Phase 4: Diff/patch structural tools

1. Extract shared patch parser if needed.
2. Add `diff_touched_paths` and `diff_hunk_ranges` first.
3. Add `patch_conflict_markers_inspect`.
4. Add `unified_diff_validate` if parser extraction makes it cheap.
5. Add profile placement and tests.

Why fourth: patch/diff tools are agent-useful but can sprawl. Land minimal primitives first.

### Phase 5: Repo audit and LLM-output hygiene composites

1. Add `llm_json_output_check`.
2. Add `markdown_link_check_lexical`.
3. Add `repo_file_inventory`.
4. Consider `repo_doc_inventory` and `repo_release_readiness_check` after evaluating output size and usefulness.

Why fifth: these are composite ergonomics improvements and should be built on stable underlying primitives.

### Phase 6: Final polish and release gate

1. Run full local checks:
   - `ruff check eggcalc tests`
   - `black --check eggcalc tests`
   - `python build_single.py`
   - `python eggcalc.py "5+3"`
   - single-file MCP smoke test
   - `pytest tests/ -v`
   - `mypy eggcalc --ignore-missing-imports`
   - `python -m build`
   - `twine check dist/*`
2. Verify generated docs are clean.
3. Verify README examples match actual CLI output.
4. Verify `docs/tool_inventory.md` count and profile tables match source.
5. Confirm no tool count hardcoding remains outside generated sections unless tests enforce it.

## Non-Goals

- Do not add network-backed package resolution.
- Do not read repository files directly from MCP tools.
- Do not add non-standard-library runtime dependencies.
- Do not expose execution or filesystem mutation tools.
- Do not move every primitive into minimal Codegg profiles; keep minimal profiles curated.
- Do not silently repair model output unless a future repair tool is explicitly scoped and named as such.

## Risk Register

| Risk | Impact | Mitigation |
|---|---:|---|
| Windows path semantics accidentally change POSIX behavior | Medium | Add POSIX regression tests before refactor |
| MCP env vars allow unsafe values | Medium | Clamp values and test invalid/edge cases |
| Generated docs introduce noisy diffs | Low/Medium | Generate stable ordering and only generated sections |
| New manifest parsers become partial reimplementations of package managers | Medium | Keep output lexical/structural and document limitations |
| Tool inventory grows too large for model context | Medium | Use profiles and compact/normal schemas; avoid default exposure |
| Cancellation refactor destabilizes server | Medium | Start with docs and low-risk cooperative hooks; avoid invasive thread-kill designs |
| Single-file build breaks from new modules/imports | High | Update `build_single.py` coverage and add single-file MCP smoke CI |

## Handoff Checklist

For every code change in this line of work:

- Add or update tests first where behavior is changing.
- Update `TOOL_SCHEMAS` for any new MCP tool.
- Update `TOOL_METADATA` and profile membership for any new MCP tool.
- Update inventory fixture/generator output.
- Confirm `docs/mcp.md` and `docs/tool_inventory.md` are generated or manually synchronized according to the final chosen workflow.
- Confirm `build_single.py` includes new runtime modules.
- Run single-file smoke tests.
- Keep error envelopes sanitized and bounded.
- Preserve standard-library-only runtime imports.
