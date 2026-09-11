# Agent Surface Corrective / Experimental Pass

Status: planned  
Repository: `eggstack/eggcalc`  
Baseline reviewed: `90137b53fd4fef5c7325f929cf0afe74e7ca1bc5`  
Date: 2026-09-10  
Depends on: Plans 037-042  
Purpose: resolve the failed `agent_core` recommendation gate without reopening completed MCP protocol or catalog architecture work

## 1. Goal

Determine whether eggcalc can retain most of the context-footprint reduction achieved by the current agent-facing MCP work while recovering tool-selection quality to a level that is non-inferior to the practical full/compact baseline.

The previous line of work is not a protocol failure. MCP `2026-07-28` interoperability, structured results, annotations, catalog authority, deterministic lexical discovery, and all 83 tool implementations are in good condition. The unresolved problem is narrower:

- `agent_core/compact` reduces the initial serialized tool surface by about 90.1% versus `full/full`;
- the 10-tool static core materially underperforms the full catalog on held-out tool selection;
- always adding the current top-five lexical discoveries improves selection but does not recover the full baseline;
- the held-out runs showed essentially no invalid-argument or redundant-call pathology, so adding schema complexity or broad composite tools is not justified by the current evidence;
- `full` remains the compatibility default, so this experiment can proceed without changing normal client behavior.

This plan is therefore an evidence-driven corrective experiment, not a redesign. It should answer four questions:

1. Is the permanent 10-tool core simply too small or composed of the wrong tools?
2. Is current lexical discovery failing because acceptable specialists are missing from the shortlist, poorly ranked, or described too weakly once loaded?
3. Does `compact` schema/detail remove selection cues that matter enough to justify a slightly richer initial or discovered representation?
4. Does the one-turn selection benchmark misrepresent the behavior of a real multi-step agent strongly enough that a small end-to-end confirmation changes the recommendation decision?

The preferred outcome is a modest policy/profile correction using the existing 83 tools and existing stdlib-only discovery machinery. New public tools, new protocol features, embeddings, and provider dependencies are out of scope unless the evidence establishes that the existing surface cannot meet the goal.

## 2. Baseline evidence

The closure report at:

```text
evals/mcp_tool_selection/reports/closure_2026_09_10.md
```

records the following initial-surface costs:

```text
full/full             83 tools   118392 bytes
full/compact          83 tools    83966 bytes
default/compact       26 tools    27872 bytes
agent_core/compact    10 tools    11706 bytes
```

`agent_core/compact` therefore passes the footprint objective comfortably.

However, the 60-case held-out selection runs did not pass the recommendation gate.

DeepSeek v3.2:

```text
catalog                    first tool   acceptable anywhere
full/full                     0.2333            0.2500
full/compact                  0.2167            0.2333
default/compact               0.1000            0.1000
agent_core/compact            0.1000            0.1167
agent_core+discovery          0.1667            0.2000
```

GPT-OSS 120B:

```text
catalog                    first tool   acceptable anywhere
full/full                     0.2000            0.2167
full/compact                  0.2333            0.2500
default/compact               0.0833            0.1000
agent_core/compact            0.1000            0.1167
agent_core+discovery          0.1500            0.1500
```

The discovery configuration in that experiment already added the current top five deterministic lexical matches not already present in `agent_core` for each prompt. Therefore this corrective pass must not incorrectly attribute the result to a missing discovery trigger in the evaluation harness.

The important observed pattern is instead:

- shrinking the visible tool surface reduces tool-use/selection substantially;
- top-five lexical expansion recovers part, but not all, of the loss;
- malformed calls were not the dominant issue;
- there is no existing evidence that a new composite would address the failure.

## 3. Constraints

All work under this plan must preserve:

- standard-library-only production/runtime dependencies;
- all 83 existing public tool names and semantics;
- `full` as the compatibility default;
- current MCP protocol behavior from Plans 038-039;
- current catalog authority from Plan 040;
- deterministic, bounded discovery from Plan 041 unless evidence supports a small scoring change;
- generated single-file parity;
- provider-neutral checked-in evaluation data;
- no network/model calls in normal CI;
- no embeddings, vector database, semantic-search service, FTS dependency, or external ranking service;
- no generic tool router / `operation=` mega-tool;
- no proliferation of permanent profiles merely to test candidate set sizes;
- no changes to held-out expected tools after viewing model outcomes except to correct objectively invalid cases, with such corrections documented and all affected comparisons rerun;
- no production code changes whose only purpose is to improve one evaluated model family.

This pass may add evaluation-only candidate-set files or scripts. It should add or modify a permanent profile only after the winning configuration passes the held-out gate.

## 4. First principle: diagnose before tuning

Do not begin by editing keywords, search weights, or `agent_core` membership.

The first implementation task is to produce a per-case failure decomposition from the existing closure rollouts and deterministic catalog search. For each failed held-out case, classify the earliest relevant failure as one of:

```text
A. static-core omission
   An acceptable primary/supporting tool is not in the permanent core.

B. discovery recall failure
   No acceptable tool appears in the discovered top N.

C. discovery ranking/depth failure
   An acceptable tool exists in the deterministic ranking but falls below the injected cutoff.

D. exposed-selection failure
   An acceptable tool is actually visible to the model, but the model selects another tool or no tool.

E. compact-description ambiguity
   The same acceptable tool performs materially better with normal/full descriptive detail than compact detail.

F. no-tool / tool-use propensity failure
   The prompt has an acceptable tool, but the model declines to call any tool despite suitable visible candidates.

G. benchmark-shape limitation
   A one-turn selection probe fails, but a bounded multi-step agent run reaches an acceptable tool naturally.

H. corpus issue
   The expected tool set or prompt is objectively wrong/ambiguous enough that the case should be corrected independently of a preferred configuration.
```

A case may carry secondary labels, but the report should identify one primary cause so changes target the correct layer.

Add a deterministic analysis script if useful, for example:

```text
scripts/analyze_mcp_tool_selection_failures.py
```

It should consume:

- `cases.json`;
- rollout JSONL or a normalized checked-in result file;
- the current `ToolRegistry.search_tools()` ranking;
- a candidate core tool list;

and produce compact JSON/Markdown summaries such as:

- miss count by domain;
- acceptable tool present in static core?;
- first acceptable search rank;
- acceptable tool present at top 3 / 5 / 8 / 10?;
- model called any tool?;
- selected tool acceptable?;
- selected tool category versus expected category.

Keep the script stdlib-only and deterministic. It must not call a model.

## 5. Workstream A — characterize discovery depth and ranking

### 5.1 Measure recall by discovery depth

Before changing the lexical scorer, measure deterministic acceptable-tool recall for at least:

```text
top 1
top 3
top 5
top 8
top 10
```

on development and held-out cases separately.

Report:

- any acceptable primary/supporting tool recall;
- acceptable primary-only recall;
- median and p90 first-acceptable rank;
- domain-level misses;
- cases where no acceptable tool is ranked at all within top 20.

This tells us whether the current top-five injection cutoff itself is a major limitation.

### 5.2 Do not equate lexical recall with model selection

A higher N increases model-visible schemas and choice ambiguity. If top-eight recall is materially higher than top-five recall, that does not automatically justify injecting eight specialists.

Evaluate schema bytes and model selection together. The optimum may be fewer high-confidence matches, a somewhat larger permanent core, or a two-stage category shortlist.

### 5.3 Audit ranking failures qualitatively

For repeated misses, inspect which metadata signal causes the wrong ranking:

- canonical tool name;
- alias;
- keyword;
- category;
- `selection_summary`;
- low-weight full-description/tags fallback.

Only change search weights if the same ranking defect occurs across multiple development cases and has an interpretable correction. Do not fit weights to isolated prompts.

Prefer metadata wording corrections over increasingly complicated ranking math when the tool's intended use is simply poorly expressed.

## 6. Workstream B — evaluate core size/composition without profile sprawl

### 6.1 Treat the current 10-tool `agent_core` as one candidate, not an anchor

The current profile contains ten high-value front doors, but the held-out result shows that permanent exposure may be too sparse.

Build evaluation-only candidate sets rather than immediately adding profiles. Candidate sets should be ordinary sorted tool-name lists stored in a small evaluation data file or emitted by a deterministic script.

Evaluate at least four static sizes:

```text
10 tools   current agent_core baseline
~14-16     modest expansion
~18-22     medium expansion
26         current default profile baseline
```

The exact intermediate membership should be chosen from development evidence, not from these numbers mechanically.

### 6.2 Select additions by marginal development-set value

For each tool outside the core, measure development-set evidence such as:

- frequency as acceptable primary;
- frequency as acceptable supporting tool;
- number of current static-core misses it would cover;
- number of discovery misses it would avoid;
- tool-definition byte cost at compact detail;
- conceptual uniqueness versus already-visible tools;
- whether its visible name/summary provides useful category/intention cues even when not ultimately called.

Use a simple deterministic marginal-coverage report. Do not build an optimizer framework.

A reasonable ranking metric may be reported as data, for example:

```text
covered development misses / added serialized KB
```

but final membership must consider ambiguity as well as coverage. A tool that adds a highly confusable neighboring choice may not be worth permanent exposure even if frequent.

### 6.3 Preserve domain cues

Explicitly test the hypothesis that specialist tool names/descriptions help models recognize that eggcalc has a relevant deterministic capability.

Candidate expanded cores should provide representation across the domains that account for most missed calls. Do not make the set numerically balanced for aesthetic reasons; use development failures.

Potential domain classes to inspect include:

- patch/edit;
- shell;
- structured data / JSON;
- text / Unicode / identifiers;
- paths/globs;
- regex;
- versions;
- package manifests;
- network IP/CIDR;
- datetime/cron;
- encoding/radix;
- repository inspection;
- units/math.

This is an analysis list, not authorization to add one permanent tool per category.

### 6.4 Measure every candidate's footprint

Extend or reuse `scripts/measure_mcp_tool_surface.py` to report candidate-name-list footprint without requiring a permanent profile.

For each candidate report:

- tool count;
- serialized compact bytes;
- reduction versus `full/full`;
- reduction versus `full/compact`;
- largest definitions;
- category distribution.

The preferred solution should still save substantial context. The existing Plan 041 threshold of at least about 70% versus `full/full` remains a useful floor, but selection quality takes priority over preserving the full 90.1% reduction.

## 7. Workstream C — separate core composition from discovery quality

Run development experiments across a small matrix rather than changing several variables at once.

Minimum matrix:

```text
current core10 / compact / no discovery
current core10 / compact / top5 discovery
current core10 / compact / top8 discovery
expanded small core / compact / top5 discovery
expanded medium core / compact / top5 discovery
expanded medium core / compact / top8 discovery
full / compact
full / full
```

Do not create permanent profiles for every row. Use explicit name-filtered tool definitions in the evaluation harness.

For each row report:

- initial schema bytes;
- added discovery bytes;
- first-tool selection;
- acceptable-anywhere selection;
- no-tool rate on cases that expect a tool;
- inappropriate-tool rate on no-tool cases;
- mean calls;
- invalid tool/argument rates;
- domain-level results.

This matrix should identify whether selection recovers primarily from:

- more permanent context;
- deeper discovery;
- both;
- neither.

## 8. Workstream D — test compact versus richer selection detail

The previous implementation replaced arbitrary description truncation with authored `selection_summary`, which is structurally better. The held-out result does not prove that the compact descriptions are sufficient for every neighboring tool pair.

### 8.1 Compare detail levels without changing schemas first

On development cases, compare candidate configurations using:

```text
compact
normal
full description/schema detail where practical
```

Focus especially on cases classified as exposed-selection failure.

Measure incremental bytes as well as selection accuracy.

### 8.2 Prefer targeted richer descriptions over global expansion

If normal detail materially improves only a small set of ambiguous tools, do not globally abandon compact mode.

Prefer one of these, in order:

1. improve that tool's `selection_summary` using development evidence;
2. ensure the critical differentiator is retained in compact mode;
3. if necessary, allow discovered specialist definitions to use `normal` while the permanent core remains `compact`;
4. only use full detail when measured benefits justify its cost.

A mixed policy such as:

```text
permanent core: compact
discovered specialists: normal
```

is acceptable if it materially improves selection while preserving low initial context.

Do not add per-tool bespoke rendering modes unless a general compact/normal policy cannot express the winning strategy.

## 9. Workstream E — evaluate a lightweight domain/intention shortlist

Only pursue this workstream if failure analysis shows that models need broader capability cues but injecting many full schemas is wasteful.

The experiment is a host/library hint layer, not a new MCP protocol or tool.

### 9.1 Candidate form

Construct a compact deterministic domain summary from existing `TOOL_METADATA`, for example:

```text
patch/edit: validate patches, replacements, touched files, diff structure
shell: split/quote argv and preflight commands
structured data: validate/compare/extract JSON/TOML/INI and inspect manifests
network: inspect IPs and CIDRs
versions: compare versions and evaluate constraints
...
```

Keep this bounded and generated from a small authored category-summary authority or existing metadata. Do not expose all 83 names again in prose.

### 9.2 Evaluation use

Test whether giving the model a small category/intention index alongside the permanent core improves:

- tool-use propensity when a specialist exists;
- domain selection;
- final selected specialist after deterministic discovery.

The host can then use the selected/current task domain to narrow lexical search before injecting full definitions.

### 9.3 Do not create a model-visible router tool by default

This category summary is context/harness guidance. It should not become a `choose_category` or `tool_search` MCP tool unless a separate evaluation demonstrates that requiring a model call to discover another tool is superior and interoperable with target hosts.

If plain deterministic host-side search remains better, keep the model out of the discovery plumbing.

## 10. Workstream F — proactive host-side discovery policy

The closure benchmark already performed discovery for every prompt, so this workstream is about defining the correct host integration policy, not claiming that unconditional discovery is a new experiment.

For codegg or another aware harness, document/test these host strategies:

```text
1. static-only
   inject permanent core and nothing else

2. unconditional lexical expansion
   search current user/subtask text before model call and inject top N specialists

3. domain-filtered lexical expansion
   infer a coarse deterministic domain from query/catalog metadata, then search within or boost that domain

4. staged expansion across an agent loop
   start with core + first shortlist; on a new concrete subtask, rerun discovery against the subtask text before the next model call
```

The fourth strategy is the one most likely to differ from the one-turn benchmark in a real coding-agent workflow. It should be evaluated in a bounded end-to-end confirmation after the selection-only experiment identifies a promising core/search policy.

Do not require eggcalc itself to maintain conversation state. Discovery remains a pure registry operation on supplied query text; agent-loop policy belongs in the harness.

## 11. Workstream G — small multi-step end-to-end confirmation

The existing held-out benchmark is intentionally a one-turn tool-selection probe. That is sufficient to reject the current 10-tool recommendation, but a revised strategy should not be promoted solely from another one-turn result.

After development tuning and one frozen held-out selection pass identify a winner, run a smaller bounded end-to-end agentic confirmation.

### 11.1 Case selection

Choose approximately 15-30 cases spanning:

- common core tasks;
- specialist tasks;
- cases where current top-five discovery failed;
- cases where an acceptable tool was visible but not chosen;
- at least several no-tool controls;
- multi-step tasks where the subtask wording changes after the first tool result.

Prefer reusing existing corpus prompts or deriving clearly traceable end-to-end variants. Do not construct only cases favorable to the candidate.

### 11.2 Compare practical finalists only

Compare at most three configurations, for example:

```text
best full/compact baseline
best smaller static+discovery candidate
current core10+discovery baseline
```

Use at least two materially different model families when practical.

### 11.3 Execute tools

Unlike the selection probe, actually execute selected tools and permit a bounded agent loop. Record:

- task completion/correctness;
- first selected tool;
- acceptable tool eventually used;
- number of model turns;
- number of tool calls;
- irrelevant/redundant calls;
- invalid calls;
- initial schema bytes;
- dynamically added bytes across the loop;
- provider tokens/latency where available.

This can remain external/manual/release tooling. Provider SDKs must not become production or CI dependencies.

## 12. Workstream H — scoring and statistical restraint

Do not turn this into a benchmark-science project.

For the 60 held-out selection cases:

- use exact counts/rates;
- show per-model results;
- show domain/failure-class breakdowns;
- repeat only borderline or obviously stochastic comparisons when needed;
- report run count and range if reruns occur;
- do not manufacture confidence intervals whose assumptions are not justified by the evaluation design.

Use practical non-inferiority:

- a candidate should not show a clear consistent selection regression versus the best practical full/compact baseline across both evaluated model families;
- if one family improves and another degrades materially, do not call the profile generally recommended;
- the smaller configuration should preserve a material context advantage, preferably >=70% lower initial serialized bytes than `full/full`;
- end-to-end task correctness should not regress materially in the final confirmation.

A solution that saves 75-85% of initial schema bytes and matches selection quality is preferable to one that saves 90% but fails to expose enough useful capability signal.

## 13. Workstream I — production changes allowed after evidence

After development experiments, freeze one candidate before touching held-out data again.

Permitted production changes, in preferred order:

1. adjust `agent_core` membership;
2. improve bounded `selection_summary` / keyword metadata where development failures justify it;
3. make a small interpretable lexical scoring-weight correction;
4. document a different default discovery depth for aware harnesses;
5. document/use `compact` core plus `normal` discovered specialists if measured superior;
6. add a small generated category/intention summary API only if the domain-hint experiment produces measurable value.

Do not change the server's global `full` default in this plan.

Do not add a new permanent profile unless:

- the existing `agent_core` name cannot reasonably represent the winning small-agent surface; or
- preserving the old candidate is useful for compatibility/research.

Prefer updating `agent_core` after evidence and recording the old membership in the evaluation report rather than accumulating `agent_core_v2`, `agent_core_medium`, etc.

## 14. Workstream J — front-door/composite tools remain a last resort

The closure evaluation found no recurring invalid-call or redundant-call problem that points to missing composites.

Therefore do not add `manifest_inspect`, `network_inspect`, identifier routers, or other front doors during initial experiments.

Reconsider a composite only if the new failure analysis shows a repeated cross-model pattern where:

- several existing neighboring tools are all exposed;
- the model repeatedly cannot select among them;
- lexical discovery already returns the correct family;
- richer summaries/details do not solve the confusion;
- one narrow delegating front door improves held-out and end-to-end outcomes measurably.

If those conditions do not occur, record "no composite justified" and keep the 83-tool surface unchanged.

## 15. Evaluation artifacts

Expected additions/changes may include:

```text
plans/043-agent-surface-corrective-experimental-pass.md

evals/mcp_tool_selection/
    README.md
    candidate_sets.json                     # optional, evaluation-only
    reports/
        corrective_development_YYYY_MM_DD.md
        corrective_held_out_YYYY_MM_DD.md
        corrective_end_to_end_YYYY_MM_DD.md # only if final confirmation run

scripts/
    analyze_mcp_tool_selection_failures.py  # likely useful
    measure_mcp_tool_surface.py              # extend only if needed
    score_mcp_tool_selection.py              # extend only for missing metrics

eggcalc/mcp/schemas.py                      # only evidence-backed metadata/profile changes
eggcalc/mcp/server.py                       # only small search/API changes if justified

tests/test_mcp_tool_discovery.py
tests/test_tool_inventory.py
docs/mcp.md
architecture/mcp.md
AGENTS.md / .skills/mcp_server.md            # only if recommended operational policy changes
```

Keep generated reports bounded. Do not check in raw provider logs containing irrelevant completions or large repeated schema payloads; retain normalized provider-neutral results or concise summaries sufficient to reproduce scoring conclusions.

## 16. Implementation sequence

Implement in this order and avoid skipping diagnosis steps:

1. Freeze the current baseline SHA, corpus SHA, current `agent_core`, search weights, and footprint measurements.
2. Normalize/retain the existing held-out rollout evidence needed for per-case analysis.
3. Add deterministic failure decomposition and discovery-rank/depth reporting.
4. Characterize top-1/3/5/8/10 recall and domain-level misses on development and held-out data without tuning held-out.
5. Use development cases to construct evaluation-only expanded-core candidates around approximately 14-16 and 18-22 tools, plus the existing 10- and 26-tool baselines.
6. Measure every candidate's exact serialized footprint.
7. Run development selection experiments for core-size x discovery-depth combinations.
8. Compare compact versus normal/richer specialist definitions on exposed-selection failures.
9. If justified, test a lightweight category/intention summary and/or domain-filtered search on development cases.
10. Make the smallest development-backed metadata/search/core changes necessary; do not change multiple layers simultaneously without an ablation.
11. Freeze one or at most two finalists before looking again at final held-out outcomes.
12. Run held-out selection comparisons on at least two materially different model families using the frozen configurations.
13. If the recommendation gate passes, run the small multi-step end-to-end confirmation.
14. If held-out fails, classify why; make at most one additional development-driven correction cycle unless a clear implementation bug was discovered. Do not endlessly tune against the held-out set.
15. Promote/update `agent_core` recommendation wording only if both selection and end-to-end evidence support it.
16. Otherwise retain `agent_core` as experimental, document the best observed tradeoff, and close the experiment honestly without forcing a recommendation.
17. Regenerate docs/inventory as needed and run canonical verification.

## 17. Acceptance criteria

This plan is complete when the experiment reaches a defensible stopping decision, not only when a smaller profile wins.

Required closure criteria:

1. Existing closure rollouts have a per-case failure decomposition sufficient to distinguish static omission, discovery recall/rank, exposed selection, compact-description, no-tool propensity, and benchmark-shape problems.
2. Deterministic discovery recall is reported at multiple shortlist depths, including top 5 and at least one deeper cutoff.
3. At least two expanded static-core sizes are evaluated without adding permanent profile sprawl.
4. Every candidate has exact serialized footprint measurements.
5. Core size and discovery depth are varied independently enough to identify their marginal effects.
6. Compact versus richer detail is evaluated where exposed-selection failures justify it.
7. Search weights/metadata are changed only from development-set evidence and remain simple, deterministic, bounded, and stdlib-only.
8. The final held-out comparison uses at least two materially different model families and frozen candidate configuration(s).
9. Held-out expectations are not tuned to make the candidate pass.
10. If a candidate is promoted as recommended, its selection quality is non-inferior in practical terms to the best full/compact baseline across the evaluated model families.
11. A promoted candidate retains a material initial context reduction, with >=70% reduction versus `full/full` as the target floor unless a clearly documented accuracy/context tradeoff justifies otherwise.
12. A promoted candidate receives a bounded multi-step end-to-end agent confirmation with no material task-correctness regression.
13. If no candidate meets the gate, the repository explicitly records that result and keeps `full` as the recommendation/default rather than forcing a smaller surface.
14. No new front-door/composite tool is added without cross-model evidence that simpler exposure/metadata/search corrections fail and the composite improves outcomes.
15. All 83 existing tools remain available through `full`/appropriate profiles.
16. MCP protocol behavior from Plans 038-039 remains unchanged unless an unrelated correctness bug is discovered.
17. No runtime/provider/search dependency is added.
18. Generated single-file parity remains intact.
19. `make check`, package validation, focused discovery/tool-inventory tests, and compatibility checks remain green after any production change.
20. Plan 041/042/043 and current docs accurately reflect whether a smaller general-agent surface is recommended, experimental, or rejected.

## 18. Success states

There are three acceptable outcomes.

### Outcome A — smaller profile validated

A revised `agent_core` (possibly 14-22 tools rather than 10) plus a measured discovery/detail policy matches practical full/compact selection quality, passes the small end-to-end confirmation, and retains substantial context savings.

Then:

- update `agent_core` membership;
- document exact discovery/detail policy;
- mark it recommended for aware general-agent hosts;
- keep `full` as compatibility default unless a later separate compatibility decision changes that.

### Outcome B — discovery policy validated, static core remains secondary

No single small static profile matches full selection by itself, but proactive/staged host discovery with a bounded core matches practical performance while retaining substantial initial context savings.

Then:

- keep the core explicitly coupled to the host discovery policy;
- document that `agent_core` alone is not recommended;
- provide the deterministic eggcalc registry APIs needed by codegg/other hosts;
- do not imply that generic MCP clients receive the same benefit automatically.

### Outcome C — smaller exposure rejected

Neither expanded cores nor existing stdlib discovery/detail policies recover selection without sacrificing most of the context benefit.

Then:

- keep `full`/`full compact` as the practical recommendation;
- retain `agent_core` and search only as experimental/harness facilities if their maintenance cost remains negligible;
- document the negative evidence;
- stop. Do not add architectural machinery merely to force the original hypothesis to succeed.

Outcome C is a valid completion of this plan.

## 19. Verification

At minimum after implementation changes:

```bash
python -m pytest tests/test_mcp_tool_discovery.py tests/test_tool_inventory.py tests/test_mcp_schema_lint.py -v
python scripts/measure_mcp_tool_surface.py
python scripts/score_mcp_tool_selection.py --help
python scripts/generate_mcp_docs.py --check
python build_single.py --validate
make check
make package-check
```

If the compatibility workflow is not automatically run for the final production-change commit, dispatch it explicitly and record the Windows/macOS/Linux result in the final corrective report.

External model runs remain manual/release evidence and must never become required network CI.

## 20. Non-goals

Do not use this pass to:

- change MCP protocol eras or transport;
- add HTTP/OAuth/MCP Apps/Tasks/resources/prompts/sampling/elicitation;
- delete or rename the 83 existing tools;
- change tool semantics unrelated to an identified correctness bug;
- add embeddings/vector search/FTS/external search;
- add a model-provider SDK to eggcalc;
- add model-specific routing logic;
- create dozens of permanent profiles;
- make `agent_core` the server default;
- add a generic router or mega-tool;
- optimize only serialized bytes while ignoring selection/task quality;
- tune repeatedly against held-out failures;
- treat one model family as sufficient proof of general agent behavior;
- add front-door composites merely because they look cleaner architecturally;
- reopen completed protocol/catalog maintenance work from Plans 038-040.

The pass should end with a measured answer to the agent-surface question. The preferred technical result is a slightly larger but still compact initial surface plus simple deterministic host-side discovery if that restores agent behavior. The preferred engineering result, regardless of benchmark outcome, is to stop at the simplest policy supported by evidence.