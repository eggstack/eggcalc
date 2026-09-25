# MCP Protocol and Agent-Surface Closure Pass

Status: partially complete; protocol gate passed, agent_core recommendation gate not met
Repository: `eggstack/eggcalc`  
Baseline reviewed: `e093bfb3e675e486cc7c8bf3299c168088e87e35`  
Date: 2026-09-10  
Parent roadmap: `plans/037-mcp-protocol-and-agent-surface-roadmap.md`  
Closes: Plans 038-041

## 1. Goal

Close the remaining evidence and interoperability gaps after implementation of Plans 038-041 without reopening the MCP architecture or expanding eggcalc's scope.

The implementation is substantially landed:

- MCP `2026-07-28` modern/stateless support exists alongside legacy `2025-11-25` / `2024-11-05` sessions;
- structured tool results, output validation, annotations, deterministic ordering, shared server instructions, and conservative cache hints exist;
- tool catalog/handler/profile authority has been consolidated;
- all 83 tools remain available;
- `agent_core` and deterministic lexical discovery exist;
- compact descriptions use authored selection summaries;
- deterministic surface measurement shows `agent_core/compact` at roughly 11.7 KB versus roughly 118.4 KB for `full/full` (about a 90% reduction);
- the repository's primary CI and compatibility matrix are green on the reviewed baseline, including Windows, macOS, Ubuntu, package checks, and generated single-file checks.

The remaining work is evidence closure, not feature development:

1. verify legacy and modern stdio behavior against current official MCP tooling/SDK behavior;
2. execute the held-out multi-model agent evaluation required by Plan 041;
3. make only evidence-driven selection/profile corrections if those evaluations expose regressions;
4. repair status/documentation wording so the repository accurately distinguishes implemented, validated, and still-pending work;
5. rerun canonical repository and compatibility verification.

This plan must remain narrow. If the evidence passes, the correct implementation outcome may be almost entirely reports/documentation with no production code changes.

## 2. Why a closure pass is still needed

### 2.1 Plan 041 implementation is ahead of its final evidence gate

At plan start, `evals/mcp_tool_selection/reports/baseline_2026_09_10.md`
recorded strong deterministic results but explicitly stated that external
held-out rollouts on at least two materially different model families were
pending. This closure report records those rollouts and their outcome.

The deterministic lexical proxy currently reports approximately:

```text
all recall@5                 0.932
held-out recall@5            0.862
held-out core+discovery      0.845
agent_core/compact footprint -90.1% vs full/full
```

This is enough to justify the candidate mechanism and the substantial context reduction. It is not enough to claim that `agent_core` is empirically validated as the best general-agent exposure. Plan 041 explicitly requires held-out agent evidence before final recommendation.

### 2.2 Modern MCP stdio needs official interoperability evidence

Eggcalc's modern protocol implementation is well-covered by literal transcript tests, but Plan 038 also required verification with current official MCP client/Inspector behavior.

The current MCP TypeScript SDK/Inspector generation is era-aware. For stdio, its server/client helpers pin an era for a connection after the opening exchange, while eggcalc deliberately classifies each request from its explicit modern `_meta` envelope and permits modern/legacy traffic to coexist in one stdio process without state bleed.

Do not assume this difference is a defect. The modern wire protocol is self-describing and normal clients consistently speak one era. However, the difference is important enough that closure requires an actual interoperability run and a check of the current normative specification.

Decision rule:

- if the finalized MCP specification explicitly requires connection-era pinning for stdio, align eggcalc with the specification while preserving legacy behavior;
- if an official Tier-1 client/Inspector fails against eggcalc because of eggcalc's dispatch behavior, make the smallest compatibility correction and add a regression test;
- if official clients interoperate and the difference is only an SDK implementation policy, preserve eggcalc's simpler request-local classifier and document the intentional behavior rather than adding connection state merely for imitation.

## 3. Constraints

- Standard library only for eggcalc production/runtime code.
- Do not add the MCP SDK, Inspector, model-provider SDKs, Node packages, or network dependencies to runtime/package dependencies.
- External SDK/Inspector/model evaluation is dev/release evidence only.
- Preserve all 83 existing tool names and their direct availability through `full`/appropriate profiles.
- Preserve `full` as the compatibility default unless a separate compatibility decision explicitly changes it.
- Preserve existing legacy MCP lifecycle behavior unless the official interoperability check demonstrates a real defect.
- Do not replace `ToolRegistry.search_tools()` with embeddings, BM25 infrastructure, a vector database, or an external search service.
- Do not add a model-visible `tool_search` MCP tool as part of this closure pass.
- Do not add front-door/composite tools unless held-out evidence demonstrates a repeated selection/call-path failure that cannot be solved cleanly with metadata/profile tuning.
- Do not tune held-out expected answers to make a preferred design pass.
- Do not redesign already-correct tool implementations.
- Keep generated single-file parity.
- Keep reports bounded; do not create an indefinitely growing benchmark archive.

## 4. Workstream A — official MCP interoperability closure

### 4.1 Verify current normative behavior first

Before changing code, re-read the current `2026-07-28` specification and current official TypeScript SDK migration/protocol-version documentation, focusing only on:

- stdio modern-era negotiation/bootstrap;
- whether stdio connections are normatively required to pin an era or whether connection pinning is SDK policy;
- required `server/discover` request/response shape;
- required request `_meta` fields;
- modern `tools/list` shape and cache fields;
- modern `tools/call` structured result/error behavior;
- server identity placement;
- behavior of removed legacy methods in the modern era;
- unsupported-version error semantics.

Record exact source URLs and the SDK/Inspector versions used in the closure report. Do not copy implementation behavior from an SDK when it conflicts with the protocol specification.

### 4.2 Use the official MCP Inspector as the first interoperability probe

The current Inspector provides a scriptable CLI and supports stdio plus legacy/modern protocol-era negotiation. Use the current published Inspector as an ephemeral developer tool; do not install it into eggcalc's package metadata.

Exercise `python -m eggcalc --mcp` (or the repository's canonical MCP entry point) through the Inspector in both eras.

At minimum verify:

```text
legacy connection
  connect/initialize succeeds
  tools/list succeeds
  tools/call math_eval succeeds
  structured/text result remains consumable

modern connection
  server/discover succeeds
  selected protocol is 2026-07-28
  tools/list succeeds
  tools/call math_eval succeeds
  structuredContent is visible/accepted
  server identity/cache/resultType metadata is accepted
```

Use the Inspector's current documented configuration/flags rather than checking a fragile command string into the plan. After a successful run, put the exact reproducible commands or config snippet in the closure report or `evals/mcp_tool_selection/README.md` as appropriate.

### 4.3 Cross-check with one Tier-1 SDK harness

Create a temporary/out-of-tree or explicitly dev-only minimal client harness using a current Tier-1 MCP SDK, preferably the current TypeScript SDK because its migration documentation defines the modern/legacy stdio negotiation behavior precisely.

Verify at least:

- legacy/default connection;
- modern `auto` negotiation;
- modern pinned `2026-07-28` negotiation if the SDK exposes it;
- `tools/list` and one successful `tools/call` in each era;
- one domain/tool error result;
- one malformed or unsupported modern request if the SDK exposes a raw request path cleanly.

Do not commit `node_modules`, lockfiles, SDK source, or provider dependencies merely to retain this evidence. A tiny checked-in transcript/report is preferable to carrying a second toolchain as a repository dependency.

### 4.4 Determine whether connection-era pinning needs a code change

Explicitly test the point of uncertainty rather than reasoning from SDK internals alone.

If normal official modern and legacy clients both work against the current per-request classifier, leave production behavior unchanged unless the normative spec says otherwise.

If a correction is required, prefer the minimum mechanism:

- keep `protocol_era()` as the sole version-to-era authority;
- keep `McpSession` as legacy-only state;
- if stdio connection era truly must be pinned, put that state at the stdio connection boundary, not into `ToolRegistry`, `ToolExecutor`, or global process state;
- modern request metadata must remain request-local;
- do not create fake READY sessions for modern traffic;
- add focused tests demonstrating the official-client failure before the fix and the corrected behavior after it.

### 4.5 Record interoperability evidence

Add one bounded report, for example:

```text
evals/mcp_tool_selection/reports/closure_2026_09_10.md
```

or a more specific MCP interoperability report if that keeps the agent-evaluation report clearer.

Record:

- eggcalc commit SHA;
- Inspector version;
- SDK package/version;
- Node/runtime version used externally;
- legacy result;
- modern result;
- whether connection-era pinning required a change;
- any deviations from official tooling and why they are acceptable;
- exact regression test(s) added if code changed.

Do not claim interoperability from unit transcripts alone.

## 5. Workstream B — execute Plan 041 held-out agent evaluation

### 5.1 Freeze evaluation inputs before running held-out

Before the first final held-out run, record:

- eggcalc commit SHA;
- `cases.json` SHA;
- current `agent_core` membership;
- current search weights;
- current `selection_summary`/keyword metadata state;
- serialized footprint for every compared catalog configuration.

Do not modify held-out prompts or acceptable-tool expectations after seeing model results unless a case is objectively erroneous. Any such correction must be separately justified in the report and applied before rerunning all affected configurations.

### 5.2 Use at least two materially different current model families

Run the held-out corpus with at least two materially different agent/model families. Prefer one OpenAI-family coding/general agent and one non-OpenAI family such as Anthropic or Google so tool-description/profile effects are not optimized for one model implementation.

Record exact provider/model identifiers and date. Do not encode provider API dependencies into eggcalc.

The runner may live in codegg, Codex, another harness, or an ephemeral external script. Its output must be converted to the provider-neutral JSONL format already accepted by `scripts/score_mcp_tool_selection.py`.

### 5.3 Compare the same surfaces for each model

At minimum compare:

```text
A. full/full
B. full/compact
C. default/compact
D. agent_core/compact
E. agent_core/compact + discovered specialist definitions
```

If cost makes every baseline impractical for repeated runs, `full/full`, `default/compact`, and `agent_core + discovery` are the minimum decision-critical comparison, but the report must state what was omitted and why.

The discovery configuration must use the actual `ToolRegistry.search_tools()` behavior and names-filtered schema injection pattern, not an idealized manually chosen specialist set.

### 5.4 Metrics

Use the existing scorer and report, per model/configuration:

- final task correctness/completion when available;
- acceptable first-tool selection rate;
- acceptable tool used at any point;
- invalid tool-name count/rate;
- invalid-argument count/rate;
- irrelevant tool-call count;
- redundant repeated-call count;
- total tool calls per task;
- initial serialized catalog bytes;
- dynamically injected specialist-schema bytes;
- provider-reported input/output tokens when available;
- latency when available.

Also inspect failures qualitatively. In particular, separate:

```text
selection failure
  right capability existed but model chose the wrong tool

discovery failure
  search shortlist did not contain an acceptable specialist

invocation failure
  right tool selected but arguments were malformed

task-reasoning failure
  tool selection was acceptable but the overall task still failed

no-tool failure
  model called a tool when the case should require none
```

This prevents solving a reasoning problem by needlessly changing the catalog.

### 5.5 Variance policy

Do not invent a statistically elaborate benchmark framework for 60 held-out cases. Keep the closure practical.

Preferred approach:

- run one complete held-out pass for every model/configuration;
- rerun failures/disagreements and borderline comparisons when model nondeterminism makes the decision unclear;
- if repeated runs are used, report the number of runs and observed range rather than presenting one cherry-picked value;
- do not require network/model calls in CI.

## 6. Workstream C — evidence-driven corrections only

Make no catalog/profile/search change merely because the deterministic held-out lexical proxy is below 1.0. Real-agent behavior is the decision gate.

### 6.1 Pass condition

If the external held-out results satisfy Plan 041's gates, do not tune further. Mark the current profile/discovery design validated and proceed to documentation/closure.

The intended acceptance interpretation remains:

- initial tool-definition bytes reduced by at least about 70% versus `full/full` (already comfortably met deterministically);
- common-task first-tool selection and final correctness non-inferior to the best practical compact/profile baseline within observed run variance;
- `agent_core + discovery` recovers specialist-task performance close to `full` while retaining substantially lower initial context;
- invalid-argument and redundant-call rates do not materially worsen;
- no new front-door tool is required unless it shows a measured held-out benefit.

### 6.2 If selection/discovery fails materially

Apply corrections in this order, stopping as soon as the evidence is adequate:

1. `selection_summary` wording that fails to distinguish adjacent tools;
2. small keyword/synonym corrections based on development-language evidence and observed failure categories;
3. simple integer search-weight adjustment if the same ranking error recurs across multiple cases/models;
4. `agent_core` membership adjustment if a tool repeatedly earns permanent context or an existing member does not;
5. only then evaluate a narrowly scoped front-door composite when the same ambiguity repeatedly causes failed/redundant multi-tool paths.

Do not:

- fit keywords directly to individual held-out sentences;
- add every missed specialist to `agent_core`;
- create domain umbrella tools merely to reduce the apparent tool count;
- add embeddings/vector search;
- add model-specific branches;
- change tool semantics during a selection evaluation.

After a correction, tune/inspect on development cases first. Freeze the change, then rerun the affected held-out comparison across both model families. Keep the pre-change result in the closure report so the reason for the correction remains auditable.

### 6.3 Front-door tool bar remains high

The default outcome should remain zero new tools.

A new composite is allowed only if external held-out traces show a recurring cross-model failure pattern and the proposed composite:

- improves final or tool-selection correctness measurably;
- reduces redundant calls or ambiguity;
- delegates to existing primitives rather than copying implementation logic;
- has a small unambiguous schema;
- leaves all specialist primitives directly callable;
- earns its context/discovery cost.

Otherwise document the hypothesis as rejected and add nothing.

## 7. Workstream D — recommendation wording and plan-state repair

### 7.1 Correct `agent_core` wording based on evidence

Until Workstream B passes, documentation should not overstate validation.

Before final agent evidence, use wording equivalent to:

```text
candidate/recommended opt-in general-agent profile pending held-out agent validation
```

After the held-out gates pass, it is appropriate to call `agent_core` the recommended general-agent exposure.

Do not change `full` as the default in this closure pass. `agent_core` is an efficiency recommendation for aware hosts/harnesses, not a silent compatibility change.

### 7.2 Repair plan statuses

Update the recent plan headers/status notes so repository history reflects reality.

Expected final state:

```text
037  implemented / roadmap complete, with future standardized MCP discovery tracked externally or in docs
038  complete after official interoperability evidence
039  complete
040  complete
041  complete only after held-out multi-model agent evidence passes
042  complete after all closure acceptance criteria pass
```

Use the repository's existing status convention if one is already established. Do not rewrite historical plan bodies merely to make them look current; update status/evidence notes narrowly.

### 7.3 Update bounded evidence references

Update relevant current docs only where needed:

```text
README.md
docs/mcp.md
docs/tool_inventory.md          # generated only
architecture/mcp.md
architecture/authority_inventory.md
AGENTS.md / AGENTS.override.md   # only if operational guidance changes
evals/mcp_tool_selection/README.md
evals/mcp_tool_selection/reports/...
```

Ensure the docs clearly say:

- `full` remains compatibility default;
- `agent_core/compact` saves context only when the host opts into it;
- specialist discovery is a host/library mechanism using `ToolRegistry.search_tools()` and names-filtered schema loading;
- all 83 tools remain accessible;
- eggcalc is not claiming a private `tool_search` RPC as standardized MCP progressive discovery;
- the exact agent-evaluation date/models/results supporting the recommendation;
- the exact official MCP interoperability evidence supporting `2026-07-28` claims.

Regenerate `docs/tool_inventory.md`; never hand-edit generated inventory output.

## 8. Workstream E — final regression and packaging closure

After any code/metadata/doc changes, run the narrow suites first:

```bash
python -m pytest \
  tests/test_mcp_modern.py \
  tests/test_mcp_structured_results.py \
  tests/test_mcp_tool_discovery.py \
  tests/test_tool_inventory.py \
  tests/test_mcp_schema_lint.py \
  tests/test_mcp_stdio_smoke.py -v

python scripts/measure_mcp_tool_surface.py
python scripts/score_mcp_tool_selection.py --help
python scripts/generate_mcp_docs.py --check
python build_single.py --validate
```

Then run canonical closure:

```bash
make check
make package-check
```

Push only after those pass locally or in the implementation environment.

After push, require green GitHub Actions for:

- primary CI correctness/package validation;
- compatibility Windows/Python 3.11;
- compatibility macOS/Python 3.11;
- compatibility Ubuntu/current-newest configured Python;
- generated single-file checks exercised by those workflows.

If the compatibility workflow matrix changes between this plan and implementation, use the then-current minimum-supported cross-platform jobs rather than preserving obsolete version labels solely to match this document.

## 9. Files likely to change

Evidence-only successful closure may touch only:

```text
evals/mcp_tool_selection/reports/...
evals/mcp_tool_selection/README.md
plans/037-mcp-protocol-and-agent-surface-roadmap.md
plans/038-mcp-2026-07-28-dual-era-conformance.md
plans/039-mcp-structured-results-annotations-and-cache-hints.md
plans/040-mcp-tool-catalog-authority-consolidation.md
plans/041-agent-tool-discovery-and-selection-evaluation.md
plans/042-mcp-agent-surface-closure-pass.md
docs/mcp.md
architecture/mcp.md
architecture/authority_inventory.md
```

If interoperability or held-out evaluation exposes a real defect, narrowly affected files may also include:

```text
eggcalc/_protocol.py
eggcalc/mcp/server.py
eggcalc/mcp/schemas.py
tests/test_mcp_modern.py
tests/test_mcp_stdio_smoke.py
tests/test_mcp_tool_discovery.py
scripts/score_mcp_tool_selection.py
scripts/measure_mcp_tool_surface.py
```

Do not treat this list as a requirement to modify production code.

## 10. Implementation sequence

1. Freeze/record baseline commit and evaluation corpus/catalog state.
2. Recheck final MCP `2026-07-28` normative stdio semantics.
3. Run official Inspector legacy interoperability.
4. Run official Inspector modern interoperability.
5. Cross-check both eras with one current Tier-1 SDK harness.
6. Resolve the stdio connection-era question using the decision rule in section 4.4; change no code if official interoperability is already correct and the spec does not require pinning.
7. Record interoperability evidence.
8. Run held-out agent evaluation across at least two materially different model families for the required catalog configurations.
9. Score and classify failures with the existing provider-neutral scorer/report contract.
10. If gates pass, freeze the current catalog/profile/search design. If not, make the smallest evidence-driven metadata/search/profile correction and rerun the affected evaluation.
11. Add a front-door composite only if repeated held-out evidence clears the bar in section 6.3; zero new tools is preferred if adequate.
12. Repair `agent_core` recommendation wording and Plans 037-041 status notes according to actual evidence.
13. Regenerate docs/inventory and run focused MCP/discovery tests.
14. Run `make check`, `make package-check`, and single-file validation.
15. Push and verify the primary + compatibility GitHub Actions workflows.
16. Record Plan 042's outcome after both gates are exercised; do not mark the
    agent surface recommended when the held-out gate fails.

## 11. Acceptance criteria

This closure pass is complete when all of the following are true:

1. Current official MCP Inspector interoperability has been demonstrated against eggcalc over stdio for both legacy and modern eras.
2. At least one current Tier-1 SDK has independently exercised legacy and modern `tools/list` / `tools/call` against eggcalc.
3. The stdio connection-era behavior has been checked against the finalized specification; any difference from SDK connection pinning is either corrected because required or explicitly documented as a compatible implementation choice.
4. No fake modern `McpSession` or mutable global client state has been introduced.
5. Modern `server/discover`, `tools/list`, `tools/call`, structured results, error behavior, cache fields, and server metadata remain accepted by official tooling.
6. Legacy `2025-11-25` / `2024-11-05` behavior remains intact.
7. Held-out agent evaluation has been executed on at least two materially different current model families.
8. The final report compares `full/full`, at least one practical compact/profile baseline, `agent_core/compact`, and `agent_core + discovery` (or clearly documents a justified omission).
9. `agent_core` is called recommended only if held-out results satisfy Plan 041's non-inferiority/recovery gates.
10. `agent_core/compact` retains a material initial context reduction versus `full/full` (target >=70%; current deterministic baseline is about 90%).
11. Specialist-task performance under `agent_core + discovery` is close to `full` without materially worsening invalid arguments or redundant/irrelevant calls.
12. All 83 existing tools remain directly accessible through `full`/appropriate profiles.
13. Search remains deterministic, bounded, stdlib-only, and separate from authorization.
14. No provider SDK, MCP SDK, Inspector package, embedding stack, or network dependency is added to eggcalc runtime/required CI.
15. Any catalog/search/profile tuning is traceable to observed evaluation failures rather than aesthetic consolidation.
16. No new front-door tool is added without recorded held-out benefit; zero new tools is explicitly acceptable.
17. Recent plan statuses and current documentation accurately distinguish implemented, validated, recommended, and compatibility-default behavior.
18. Generated inventory/docs are current.
19. Package and generated single-file behavior remain equivalent for the affected MCP/catalog surfaces.
20. Focused MCP/discovery tests, `make check`, `make package-check`, and the repository's cross-platform compatibility workflows are green on the final commit.

## 12. Non-goals

Do not use this closure pass to:

- add more MCP protocol features unrelated to eggcalc's current tool server surface;
- add Streamable HTTP, OAuth, Tasks, resources, prompts, roots, sampling, elicitation, subscriptions, or logging;
- remove legacy protocol support;
- remove or rename specialist tools;
- change the `full` compatibility default;
- build a general search engine for 83 tools;
- add embeddings, vector storage, BM25 dependencies, or provider-specific ranking;
- expose a custom MCP `tool_search` primitive and call it standardized progressive discovery;
- add broad composite/umbrella tools without held-out evidence;
- optimize only for one model family;
- introduce an online evaluation dependency into normal CI;
- refactor evaluator, exact-tool implementations, CLI behavior, or unit semantics unrelated to a demonstrated closure defect.

The desired endpoint is deliberately boring: the same broad deterministic toolbox, a verified modern/legacy MCP wire implementation, a much smaller opt-in agent context surface with evidence that it does not materially degrade task performance, and no additional architectural machinery unless testing proves it necessary.

## 13. Closure outcome (2026-09-10)

The official protocol gate passed. Legacy and modern stdio behavior was
accepted by MCP Inspector 2.6.0, `@modelcontextprotocol/core` 2.0.0, and
`@modelcontextprotocol/client` 2.0.0 using Node 22.19.0; see the raw probe
and [the closure report](../evals/mcp_tool_selection/reports/closure_2026_09_10.md).

The held-out gate was exercised completely on two materially different model
families across all five required catalog configurations. The 90.1%
`agent_core/compact` context reduction passed, but `agent_core/compact` was
below `full/compact` on both families and `agent_core + discovery` did not
recover specialist selection closely enough to pass Plan 041's gate. No
invalid-argument or repeated-call regression justified a catalog correction,
and no new front-door tool was added. Documentation now describes
`agent_core` as an opt-in candidate; `full` remains the compatibility default.
