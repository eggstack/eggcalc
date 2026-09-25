# Phase 4 Plan — Documentation Drift and Terminology Cleanup

## Objective

Make the user-facing and agent-facing documentation internally consistent after the safety and MCP-profile hardening work. This phase should remove stale wording, clarify the evaluation pipeline, and ensure generated MCP docs remain synchronized with source.

This is a cleanup and accuracy pass. It should not add runtime dependencies or expand the MCP tool inventory.

## Background

The repository now serves several audiences:

- CLI calculator users
- Python library users
- users of the single-file artifact
- MCP clients and coding agents
- maintainers and handoff agents reading `AGENTS.md`

The docs currently overlap across README, `AGENTS.md`, `docs/api.md`, `docs/mcp.md`, generated tool inventory, and architecture docs. Overlap is acceptable only if the core mental model is identical everywhere.

The most important terminology issue is evaluation paths. The correct distinction is not “spaces versus no spaces.” The correct distinction is:

- already-normalized AST-compatible expression path
- full natural-language/unit normalization pipeline

## Constraints

Runtime remains stdlib-only.

Do not add new tools.

Do not edit generated files manually.

Do not change behavior in this phase unless a stale doc reveals a small bug that must be fixed to keep docs truthful.

Do not duplicate the entire generated MCP inventory in README.

## Desired documentation model

### Evaluation APIs

Use this terminology consistently:

- `evaluate()` is the fast path for already-normalized Python-AST-compatible expressions.
- `evaluate_raw()` runs the full normalization pipeline and then evaluates.
- `evaluate_cached()` is the cached full-pipeline API, if current behavior matches that.
- `evaluate_async()` is the async full-pipeline API, if current behavior matches that.
- `evaluate_with_timeout()` should be documented precisely according to its actual path. If it accepts full natural-language/unit expressions, say so. If it only accepts normalized expressions, say so.
- `run()` is a lower-level normalization/evaluation helper used by CLI-compatible paths.
- CLI commands use the full natural-language/unit pipeline.
- MCP `math_eval` uses deterministic defaults and should reject random/stateful functions.

Avoid phrasing such as “no spaces” unless it describes a real parser limitation. Spaces in syntactically valid math expressions are not the central distinction.

### Config loading

After Phase 1, docs must say:

- library import does not execute cwd `eggcalc_config.py`
- CLI config loading behavior is explicit and documented
- `EGGCALC_NO_CONFIG=1` disables CLI config loading
- MCP mode never loads cwd config
- explicit `load_user_config()` is available for library users who want it

### MCP profiles

After Phase 3, docs must say:

- agents should explicitly set `EGGCALC_MCP_PROFILE`
- `codegg_core_min` and `codegg_core` are recommended coding-agent starts
- `full` is compatibility/exploration oriented
- schema detail can be compacted
- `tools/list` can filter by profile/tier/tags/names

## Files to inspect

Review at least:

- `README.md`
- `AGENTS.md`
- `docs/api.md`
- `docs/mcp.md`
- `docs/tool_inventory.md` generation path
- `architecture/overview.md`
- `architecture/api.md`
- `architecture/cli.md`
- `architecture/mcp.md`
- `architecture/evaluator.md`
- `architecture/normalize.md`
- `CHANGELOG.md` if relevant
- `scripts/generate_mcp_docs.py`

Search for stale phrases:

- `no spaces`
- `pure math only`
- `full pipeline`
- `normalize`
- `eggcalc_config.py`
- `EGGCALC_NO_CONFIG`
- `full profile`
- `codegg_core`
- `MCP profile`
- `77 tools`
- `line count`
- `single-file`
- `random`
- `side effects`

## Implementation steps

### 1. Correct `AGENTS.md`

Update the “Two Evaluation Paths” section.

Recommended replacement framing:

| Function | Handles | Input format |
|---|---|---|
| `evaluate(expr)` | direct AST evaluation | already-normalized Python-AST-compatible math expression |
| `evaluate_raw(expr)` | NL + units + math | user-facing expressions such as `five plus three`, `30m + 100ft` |
| `run(expr, NORMALIZE, PATTERNS)` | CLI-compatible normalization path | lower-level helper for NL/unit normalization and evaluation |

Update examples so they are true.

Clarify test guidance:

- Use `evaluate()` for direct AST evaluator behavior.
- Use `evaluate_raw()`, CLI subprocesses, or `run()` for natural-language and unit parsing behavior.

### 2. Update README

Keep README compact.

Recommended structure:

- one-sentence project description
- choose your mode: CLI, Python API, MCP server
- feature summary
- installation
- CLI examples
- Python API examples
- MCP quickstart and profile recommendation
- custom config/security section
- development commands
- links to detailed docs

README should link to generated tool inventory rather than list all tools.

README should not claim every individual tool is referenced in README. If generated inventory tracks README references, either adjust the generator’s interpretation or treat README reference to the inventory as sufficient.

### 3. Update API docs

Ensure `docs/api.md` explains:

- direct evaluator versus full pipeline
- config-loading model after Phase 1
- public API stability expectations
- timeout API semantics
- random/stateful behavior in normal library mode versus MCP mode if relevant

Examples should be executable and match actual return values.

### 4. Update MCP docs

Ensure `docs/mcp.md` explains:

- stdio JSON-RPC model
- deterministic defaults
- random and side-effectful math functions disabled in MCP mode
- profile selection
- schema-detail controls
- environment variables
- resource limits
- error envelope conventions
- generated inventory link

Add examples for:

- `initialize`
- `profiles/list`
- `tools/list` with compact schema
- `tools/list` for a named profile
- `math_eval`
- rejected tool outside active profile

### 5. Review architecture docs

Architecture docs often become stale when they include module line counts. Either remove line counts or clearly mark them as approximate. Prefer durable module responsibilities over exact line counts.

Check for stale references to source layout and single-file assembly behavior. If Phase 1 moved config loading, update architecture docs accordingly.

### 6. Regenerate generated docs

Run:

```bash
python scripts/generate_mcp_docs.py
python scripts/generate_mcp_docs.py --check
```

Do not manually edit `docs/tool_inventory.md` if it is generated. Change generator metadata/source comments if generated output is wrong.

### 7. Add lightweight doc consistency checks if feasible

Consider adding a small stdlib-only script or test that checks:

- `pyproject.toml` version matches `eggcalc.__version__`
- generated tool count matches `TOOL_HANDLERS`
- profile names documented in `docs/mcp.md` match `PROFILE_NAMES`
- README links to docs that exist

Do not overbuild. Prefer tests that catch high-value drift without making docs brittle.

## Test plan

Run normal checks:

```bash
ruff check eggcalc tests
black --check eggcalc tests
python build_single.py
python scripts/generate_mcp_docs.py --check
pytest tests/ -v
mypy eggcalc --ignore-missing-imports
```

Run documentation smoke checks if docs build tooling is available:

```bash
mkdocs build
```

If docs build is not part of the current standard local environment, ensure `make check` still covers generated-doc drift.

## Review checklist

Docs should answer these questions accurately:

- Which API handles natural-language input?
- Which API is the fast direct-evaluator path?
- Does library import execute local config?
- How does CLI config loading work?
- Does MCP load user config?
- Which MCP profile should a coding agent use?
- How does a client reduce schema size?
- What does deterministic mean for MCP math tools?
- What resource limits apply to MCP requests?
- How is the single-file artifact built and tested?

## Acceptance criteria

- Evaluation-path terminology is consistent across README, `AGENTS.md`, API docs, and architecture docs.
- Config-loading docs match Phase 1 behavior.
- MCP profile docs match Phase 3 behavior.
- Generated docs pass `--check`.
- Examples are executable or clearly illustrative.
- README remains compact and does not duplicate generated inventory.
- Stale module line counts are removed, regenerated, or explicitly approximate.
- Runtime remains stdlib-only.
- CI remains green.

## Handoff notes

This phase should be done after Phase 1 and preferably after Phase 3. If implemented earlier, leave TODO markers only where behavior is pending, and remove them once behavior lands. Keep generated-doc edits mechanical and source-driven.
