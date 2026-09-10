# Agent Tool Discovery and Selection Evaluation

Status: planned  
Repository: `eggstack/eggcalc`  
Baseline reviewed: `dcd0c5eb427c28712e6fffb75b58b78c8a935494`  
Date: 2026-09-10  
Parent roadmap: `plans/037-mcp-protocol-and-agent-surface-roadmap.md`  
Depends on: Plans 038-040 complete or equivalent protocol/catalog authorities stable

## 1. Goal

Reduce the model-visible MCP tool surface and improve tool selection without deleting any of eggcalc's existing capabilities.

Eggcalc currently exposes 83 deterministic tools. The server already supports profiles, tiers, tags, explicit-name filtering, and compact/normal/full schema detail, but ordinary MCP clients generally request `tools/list` once and place the returned definitions into model context. A broad `full` profile therefore still imposes a large up-front decision/context surface.

The solution under this plan is **progressive disclosure by policy and harness integration**, not capability deletion:

- every existing tool remains directly callable through `full` or another appropriate profile;
- general agents get a small, high-value recommended `agent_core` profile;
- specialist tools gain compact selection metadata and deterministic lexical discovery for aware harnesses such as codegg;
- existing `tools/list` `names`/profile/schema-detail filtering becomes the expansion mechanism for those harnesses;
- no proprietary mechanism is presented as the final MCP progressive-discovery standard while the MCP working group is still designing that standard;
- profile membership and any new front-door composite tools are chosen from empirical agent evaluations rather than architectural intuition alone.

## 2. Research basis

Primary references:

- MCP August 2026 roadmap: https://blog.modelcontextprotocol.io/posts/mcp-roadmap/
- Anthropic advanced tool use / Tool Search: https://www.anthropic.com/engineering/advanced-tool-use
- Anthropic tool design/evaluation guidance: https://www.anthropic.com/engineering/writing-tools-for-agents

Relevant conclusions:

1. The MCP maintainers explicitly identify hundred-tool catalogs as a context-cost and tool-selection problem and have started work on standardized progressive discovery.
2. That standardized MCP progressive-discovery mechanism is not yet a stable protocol primitive. Eggcalc should not hard-code an imagined future wire contract.
3. Anthropic's Tool Search/deferred loading work reports roughly 85% lower tool-definition token use in its example and significant accuracy improvements on large-tool MCP evaluations. The mechanism keeps a small core visible and expands specialist tool definitions only when needed.
4. Tool descriptions/specs should be optimized against realistic agent evaluations. Metrics beyond final task accuracy should include tool-call count, errors, token/context use, and redundant calls.
5. More tools and more endpoint-like wrappers are not automatically better. Composite tools are useful when they correspond to real workflows and eliminate common chains, but consolidation should be measured rather than assumed.

## 3. Current repository assets to reuse

Eggcalc already has most of the deterministic infrastructure needed:

- `TOOL_METADATA` with category, tier, profiles, aliases, exposure, harness use, cost, stability, composite status;
- derived `TOOL_PROFILES`;
- `ToolRegistry` with immutable metadata/schema/handler access;
- `tools/list` filters for `tier`, `tags`, `names`, `profile`, and `schema_detail`;
- compact/normal/full schema renderers;
- composite tools including `edit_preflight`, `command_preflight`, `config_preflight`, `structured_data_compare`, and `text_security_inspect`;
- generated `docs/tool_inventory.md`;
- strong per-tool correctness tests.

Do not replace these with a new discovery framework. Extend them minimally.

## 4. Constraints

- Standard library only for production/runtime code.
- No required provider SDK or API key in tests/CI.
- No embeddings, vector database, BM25 dependency, external search index, or network service.
- Preserve all existing tool names and full-profile callability.
- Preserve `full` for backward compatibility.
- Do not change the default profile from `full` in the first implementation pass unless a separate compatibility decision explicitly approves it.
- Do not add dozens of domain profiles merely to reorganize the same catalog.
- Do not expose a new `tool_search` MCP tool as the primary solution unless an evaluation and client-capability analysis prove that common clients can actually load/invoke newly returned definitions dynamically.
- Do not invent a custom protocol and label it MCP progressive discovery.
- Do not shrink full descriptions so aggressively that tool distinction becomes worse.
- Do not add new composite/front-door tools without held-out evaluation evidence.
- Keep discovery deterministic and bounded.
- Keep generated single-file support for any runtime catalog-search API added to eggcalc itself.

## 5. Workstream A — establish a tool-selection evaluation corpus

### 5.1 Corpus location and format

Add a provider-neutral evaluation area, for example:

```text
evals/mcp_tool_selection/
    cases.json
    README.md
    reports/
```

or equivalent under `tests/fixtures` if repository conventions strongly prefer fixtures there.

The corpus should be data, not executable provider-specific prompts hidden in test code.

A case should contain at least:

```json
{
  "id": "patch-001",
  "prompt": "...realistic user task...",
  "domains": ["patch"],
  "acceptable_primary_tools": ["edit_preflight", "unified_diff_validate"],
  "acceptable_supporting_tools": ["patch_summary", "diff_touched_paths"],
  "required_capabilities": ["validate proposed edit"],
  "notes": "Why these paths are acceptable"
}
```

Avoid encoding one rigid expected call sequence where several strategies are valid.

### 5.2 Realistic task distribution

Create enough cases to expose selection ambiguity rather than merely prove obvious names work. Target roughly 100-200 cases before using results to make public-surface decisions.

Cover at least:

- arithmetic/unit tasks where `math_eval` should dominate specialist math helpers;
- patch/edit preflight versus low-level diff primitives;
- shell command safety/parsing/quoting;
- config validation versus format-specific validators/manifest inspectors;
- JSON validation/canonicalization/comparison/extraction/shape;
- text equality/diff/measurement/security/Unicode policies;
- identifier scalar/table inspection distinctions;
- path normalization/comparison/scope/glob tasks;
- regex validation/safety/finditer distinctions;
- version comparison versus constraint checking;
- manifest/ecosystem specialist tasks;
- encoding/radix tools;
- IP/CIDR tools;
- datetime/cron tools;
- repo inventory;
- intentionally ambiguous prompts where the correct behavior may be no tool or a more general composite;
- multi-step cases where one composite should replace several primitive calls;
- multi-step cases where specialist primitives are actually preferable.

Include both common core tasks and specialist tasks so an `agent_core` configuration cannot appear good merely because the evaluation excludes the tools it hides.

### 5.3 Train/tune versus held-out split

Mark cases explicitly as `development` or `held_out`, or store two files.

Use development cases to tune descriptions/profile membership/search weights. Use held-out cases to decide whether the change actually improved selection.

Do not repeatedly edit held-out expected answers to fit the latest tool design.

## 6. Workstream B — deterministic footprint measurement

Before involving an LLM, measure the exact serialized catalog cost for each exposure strategy.

Add a stdlib script, e.g.:

```text
scripts/measure_mcp_tool_surface.py
```

It should be able to produce deterministic measurements for:

- `full/full`;
- `full/normal`;
- `full/compact`;
- `default/{full,normal,compact}`;
- `codegg_core`;
- `codegg_core_min`;
- proposed `agent_core`;
- a names-filtered discovered subset.

Measure at least:

- tool count;
- serialized UTF-8 bytes of the tool definitions;
- description bytes;
- input-schema bytes;
- output-schema bytes;
- annotation/metadata bytes;
- largest individual definitions;
- category/tier distribution.

Do not add a tokenizer dependency. External evaluation reports may record actual model-provider input tokens, but the repository's deterministic metric should remain bytes/characters so CI can reproduce it everywhere.

Store baseline measurements in a small checked-in report only when useful for review. Avoid accumulating timestamped benchmark files indefinitely.

## 7. Workstream C — selection-specific metadata

### 7.1 `selection_summary`

Add a short, authored selection summary to catalog metadata for each tool or at least every tool outside the obvious core.

The summary answers:

> When should an agent choose this tool rather than a neighboring tool?

It should not simply truncate the full description.

Examples of the distinction to capture:

```text
version_compare
    Compare two concrete versions; use version_constraint_check for range/constraint satisfaction.

identifier_inspect
    Inspect one/few identifier strings; use identifier_table_inspect for collision analysis across a table.

json_extract
    Extract one RFC 6901 pointer value; use json_shape for structure-only analysis and json_compare for whole-document semantic comparison.
```

Keep summaries short enough to serve as search/index material and compact descriptions. Set a documented bound (for example <= 180-240 characters) and enforce it in tests.

### 7.2 Keywords/synonyms

Use the existing `aliases` field for true alternate names where appropriate. Add a separate small `keywords` list only if aliases are semantically too strong.

Keywords should contain concepts users/agents actually say, not every word in the full description.

Examples:

```text
patch_apply_check -> ["apply patch", "dry run patch", "patch applicability"]
cidr_inspect      -> ["subnet", "network range", "prefix"]
cron_inspect      -> ["schedule", "cron", "next run"]
```

Bound list length and item length.

### 7.3 Metadata ownership

These fields belong to the catalog authority established by Plan 040. Do not copy them into schemas, docs, and search tables independently.

## 8. Workstream D — deterministic lexical catalog search

### 8.1 Purpose

Add an internal/library/harness discovery function that can rank tools from a natural-language task without loading an embedding model.

Preferred surface:

```python
ToolRegistry.search_tools(
    query: str,
    *,
    profile: str = "full",
    limit: int = 5,
) -> list[ToolMatch]
```

The exact public/private status may be chosen during implementation. If codegg is expected to consume it, make it a small documented public method rather than relying on private internals.

### 8.2 Bounded normalization

Use only stdlib primitives such as:

- `unicodedata.normalize("NFKC", ...)`;
- `casefold()`;
- bounded tokenization on whitespace/punctuation/underscore/hyphen boundaries.

Limit query length (for example 2-4 KiB) and result count (for example 1-20). Tool metadata is fixed and small, so a linear scan across 83 tools is preferable to an index framework.

### 8.3 Simple scoring

Keep ranking interpretable. A representative ordering of evidence is:

1. exact tool-name match;
2. exact alias match;
3. tool-name token/prefix match;
4. exact keyword phrase/token match;
5. category match;
6. selection-summary token overlap;
7. full description/tags as low-weight fallback.

Use integer weights and deterministic tie-breaking by canonical tool name.

Do not build TF-IDF/BM25 infrastructure unless the simple scorer fails held-out evaluation and a more complex stdlib implementation demonstrates a measurable benefit.

### 8.4 Result shape

Return a compact result with enough evidence for a harness to decide which schemas to load, e.g.:

```json
{
  "name": "unified_diff_validate",
  "score": 78,
  "category": "patch",
  "selection_summary": "...",
  "matched_on": ["keyword: unified diff", "category: patch"]
}
```

Do not return full input/output schemas from the search function by default. The aware host can call the existing registry/schema accessor or `tools/list(names=[...])` only for the shortlisted names.

### 8.5 Search/profile relationship

Search defaults to the full callable catalog so specialist tools remain discoverable. Allow a profile restriction when a harness intentionally operates under least privilege.

A search result must never make a tool callable if the server's configured security/exposure profile forbids it. Discovery and call authorization/visibility remain separate concepts.

## 9. Workstream E — harness progressive-disclosure pattern

Document and test the intended aware-harness flow:

```text
1. Host starts with agent_core tool definitions.
2. User task indicates a specialist capability may be needed.
3. Host searches ToolRegistry catalog using the task/subtask text.
4. Host selects top N relevant specialist names.
5. Host requests/constructs only those full tool definitions.
6. Model receives the core tools plus those specialists.
7. Tool call still passes normal server profile/argument validation.
```

For codegg this may be implemented outside eggcalc itself. Eggcalc's responsibility is to expose deterministic metadata/search and names-filtered definitions cleanly.

Do not require the model itself to call a search tool if the host can perform discovery before injecting tool schemas.

## 10. Workstream F — `agent_core` profile

### 10.1 Do not derive it mechanically from tier

A low tier means common/small-schema, not necessarily "worth permanent model context." Conversely a composite Tier-1 tool may eliminate several follow-up calls and deserve permanent exposure.

Create `agent_core` only after baseline evaluation/footprint data exists.

### 10.2 Candidate selection principles

The initial candidate should likely contain on the order of 6-12 tools, emphasizing broad/high-frequency intents and composite front doors. Evaluate, do not hard-code from this prose.

Likely candidates to test include:

```text
math_eval
edit_preflight
command_preflight
config_preflight
text_security_inspect or text_inspect
text_equal
validate_json
path_normalize
text_replace_check or line_range_extract
```

The evaluation may produce a different set. Keep the final list small enough that each permanent tool earns its context cost.

### 10.3 Backward compatibility

- keep `full` available;
- retain current `default`, `codegg_core`, `codegg_core_min`, task-specific profiles;
- do not silently remap existing profile names to `agent_core`;
- document `agent_core` as the recommended general agent exposure once evidence supports it;
- do not change `McpServerConfig(profile="full")` default in this plan unless a separate compatibility review explicitly approves it.

This allows new clients/harnesses to opt into the efficient profile without breaking existing callers that expect all tools from ordinary `tools/list`.

## 11. Workstream G — compact schema behavior

After `selection_summary` exists, stop producing compact descriptions solely by truncating the full description.

Preferred compact tool description:

```text
selection_summary
```

or a short combination of selection summary + critical invocation caveat where needed.

Keep:

- required argument names;
- types;
- enums;
- bounds/constraints required to form valid calls;
- annotations.

Remove only details that do not improve selection/invocation.

Use evaluation results to compare compact/full descriptions. Do not assume fewer bytes always improves accuracy.

## 12. Workstream H — provider-neutral external evaluation runner contract

### 12.1 No provider dependency in eggcalc

Do not add OpenAI/Anthropic/Google SDKs to the project.

Instead define a simple JSONL interchange format so codegg, Codex, Claude Code, or an external script can run the cases and feed results back to the stdlib scorer.

Example rollout record:

```json
{
  "case_id": "patch-001",
  "model": "provider/model-version",
  "catalog_config": "agent_core+discovery",
  "tool_calls": [
    {"name": "edit_preflight", "arguments_valid": true}
  ],
  "completed": true,
  "task_correct": true,
  "input_tokens": 1234,
  "output_tokens": 456,
  "notes": "optional evaluator note"
}
```

The repo scorer should accept missing provider token fields and still compute deterministic call-path metrics.

### 12.2 Metrics

Report at least:

- final task correctness/success when provided by the external evaluator;
- acceptable first-tool selection rate;
- acceptable tool used at any point;
- irrelevant tool-call count;
- redundant repeated-call count;
- invalid tool-name count;
- invalid-argument count;
- total tool calls per task;
- catalog serialized bytes before first call;
- dynamically added schema bytes where applicable;
- provider-reported input/output tokens when available;
- latency when available.

Do not treat one metric as sufficient. A smaller catalog that causes more failed/redundant calls may be worse overall.

### 12.3 Multiple models

When practical, run held-out evaluation on at least two materially different current agent/model families before permanently changing recommended profile membership. Tool naming/description effects are model-dependent.

This is a release/review expectation, not a required online CI job.

Record model identifiers, date, and catalog commit SHA in reports.

## 13. Workstream I — evaluation-gated front-door consolidation

Do not add these automatically. Treat them as hypotheses:

- `manifest_inspect`: auto-select among pyproject/package.json/go.mod/Cargo/requirements/lockfile inspectors based on explicit kind/filename/content;
- `network_inspect`: distinguish IP versus CIDR and delegate to existing exact primitives;
- possible identifier front door if agents repeatedly confuse scalar/table variants.

A new front-door tool is justified only if held-out results show that it:

- improves task/tool-selection correctness or materially reduces redundant calls;
- does not create a substantially more ambiguous parameter schema;
- delegates to existing primitives rather than duplicating semantics;
- keeps the specialist primitives directly callable;
- earns its own permanent/deferred context cost.

If no candidate meets that bar, add no new tools. The best outcome may simply be better exposure/discovery of the 83 existing tools.

## 14. Workstream J — future standardized MCP progressive discovery

Keep the internal catalog/search boundary adaptable.

When MCP publishes a stable progressive-discovery primitive:

- map its search/list semantics onto `ToolRegistry.search_tools()` and existing schema accessors;
- do not fork the catalog or reimplement ranking if the standard supplies host-side selection semantics;
- preserve legacy profile fallback for older clients;
- add the standard adapter as a small protocol-layer change.

Until then, document eggcalc's search as a harness/library facility, not a claim of protocol-standard progressive discovery.

## 15. Tests and deterministic evaluation checks

Add normal CI tests for the pieces that do not require an LLM:

- evaluation corpus parses and has unique ids;
- every referenced acceptable/supporting tool exists;
- development/held-out split is explicit;
- each category/domain has the intended minimum coverage;
- selection summaries respect length bounds and are non-empty for visible tools;
- keyword lists respect length/count bounds;
- catalog search is deterministic;
- exact name/alias lookup outranks weak text overlap;
- profile restriction works;
- hidden/forbidden tools do not become callable through search;
- search output is bounded;
- `agent_core` is a strict subset of `full`;
- every tool excluded from `agent_core` remains present in `full`/appropriate profile;
- compact definitions retain required inputs/types/enums;
- footprint script output is deterministic;
- scorer handles complete and partial JSONL records;
- generated single-file registry search/profile output matches package output if search is part of runtime API.

LLM evaluations remain an explicit external/manual/release experiment. CI should validate the corpus and scorer, not make network calls.

## 16. Evaluation gates

Before declaring `agent_core` recommended, produce a checked-in summary comparing at least:

```text
full/full                         baseline
full/compact                      compression-only baseline
default/compact or current model-facing profile
agent_core/compact                static small surface
agent_core + discovered specialists
```

Use held-out cases for the final comparison.

Recommended decision criteria:

- `agent_core` should reduce initial serialized tool-definition bytes by at least ~70% versus `full/full`; otherwise it is not meaningfully addressing context pollution;
- common-task first-tool selection and final task correctness should be non-inferior to the best current compact/profile baseline within normal run variance;
- `agent_core + discovery` should recover specialist-task performance close to `full` while using substantially fewer initial schema bytes;
- invalid-argument and redundant-call rates should not materially worsen;
- any new composite/front-door tool must show a measurable held-out benefit rather than only reducing tool count aesthetically.

If model variance makes a fixed percentage inappropriate, document confidence intervals/repeated-run variability and make the acceptance decision explicit rather than silently moving the threshold.

## 17. Files likely to change

Expected files may include:

```text
eggcalc/mcp/schemas.py             # selection metadata/profile
 eggcalc/mcp/server.py              # registry search/list behavior only if needed
scripts/measure_mcp_tool_surface.py
scripts/score_mcp_tool_selection.py
evals/mcp_tool_selection/cases.json
evals/mcp_tool_selection/README.md
evals/mcp_tool_selection/reports/...  # bounded summary artifacts only
tests/test_tool_inventory.py
tests/test_mcp_schema_lint.py
tests/test_mcp_tool_discovery.py      # likely new focused module
docs/mcp.md
docs/tool_inventory.md
architecture/mcp.md
architecture/authority_inventory.md
```

Fix the leading path whitespace above if copying this list into implementation; it is illustrative, not a generated manifest.

Do not add provider client modules to `eggcalc/`.

## 18. Implementation sequence

1. Build the evaluation case schema and development/held-out corpus.
2. Add deterministic catalog-footprint measurement.
3. Run baseline external evaluations against current `full`, compact, default/codegg profiles.
4. Add bounded `selection_summary`/keyword metadata.
5. Add deterministic `ToolRegistry.search_tools()` and tests.
6. Re-run development evaluations and tune only simple scoring/description metadata.
7. Create a candidate `agent_core` profile from measured common-task behavior.
8. Evaluate `agent_core` static and `agent_core + discovered specialists` on held-out cases.
9. Adjust compact schema rendering to use selection summaries if evidence supports it.
10. Evaluate proposed front-door composites only where transcripts show recurring ambiguity/redundant calls.
11. Add only the composites that pass the held-out gate; otherwise add none.
12. Document recommended agent profile/harness discovery flow and future MCP progressive-discovery adapter boundary.
13. Regenerate inventory/docs and run canonical verification.

## 19. Acceptance criteria

Plan 041 is complete when:

1. A realistic provider-neutral tool-selection corpus exists with a held-out set.
2. A stdlib-only scorer measures tool selection/call efficiency from provider-neutral JSONL rollouts.
3. A deterministic stdlib-only script measures serialized tool-surface footprint.
4. Catalog metadata includes bounded selection-oriented descriptions/keywords sufficient for deterministic discovery.
5. `ToolRegistry` can deterministically rank relevant specialist tools from query text without external dependencies.
6. Search never bypasses server/profile call visibility.
7. A small `agent_core` profile exists, remains a strict subset of `full`, and is recommended only after held-out evidence.
8. All 83 pre-existing tool names remain directly callable through `full`/appropriate profiles.
9. `full` remains available and existing profile names are not silently repurposed.
10. Initial agent-visible schema bytes are reduced materially (target >=70% versus `full/full`) for the recommended core configuration.
11. Held-out agent results show no material regression in common-task success/selection versus current compact/profile baselines.
12. `agent_core + discovery` recovers specialist capability with substantially less initial catalog context than `full`.
13. New front-door tools are added only with recorded held-out benefit; zero new tools is an acceptable outcome.
14. Compact descriptions use authored selection signal rather than arbitrary truncation if evaluation proves that superior.
15. No provider/network dependency is added to required CI/runtime.
16. The discovery implementation is documented as a harness/library mechanism pending standardized MCP progressive discovery.
17. Package/single-file registry/profile/search behavior remains equivalent where applicable.
18. `make check` and package/single-file validation pass.

## 20. Verification

Run deterministic repository checks at minimum:

```bash
python -m pytest tests/test_tool_inventory.py tests/test_mcp_schema_lint.py tests/test_mcp_tool_discovery.py -v
python scripts/measure_mcp_tool_surface.py
python scripts/score_mcp_tool_selection.py --help
python scripts/generate_mcp_docs.py --check
python build_single.py --validate
make check
make package-check
```

External agent evaluation commands should be documented in `evals/mcp_tool_selection/README.md` but must remain optional and provider-neutral.

## 21. Non-goals

Do not use this plan to:

- delete specialist tools;
- rename the entire tool catalog;
- collapse all tools into one operation-dispatch mega-tool;
- add embeddings or semantic-search infrastructure;
- add an LLM/provider dependency to eggcalc;
- add online evaluation to normal CI;
- change the default `full` profile without a separate compatibility decision;
- create a custom dynamic MCP protocol and call it standardized progressive discovery;
- add a `tool_search` MCP tool merely because Anthropic has a host-level Tool Search feature;
- add front-door composites without measured benefit;
- optimize only for one model family;
- redesign tool implementations that already have clear distinct semantics.

The pass should end with the same broad toolbox, a much smaller recommended initial surface, deterministic specialist discovery for aware harnesses, and evidence showing whether those changes actually improve agent behavior.