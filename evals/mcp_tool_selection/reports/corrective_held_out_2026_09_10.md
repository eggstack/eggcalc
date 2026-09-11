# Corrective held-out decision — 2026-09-10

This report records the held-out stopping decision for Plan 043. The prior
closure report remains the source of the two-family model-selection results;
this pass adds deterministic per-case rank/depth and candidate-core evidence
without changing held-out expectations.

## Existing model evidence

The closure run evaluated 60 held-out cases for each configuration and each of
two materially different model families. It found that both `agent_core` and
`agent_core+discovery` trailed the best full-catalog baseline, with zero
invalid arguments and no recurring redundant-call pathology. Those results
remain unchanged:

| model | full/full acceptable anywhere | full/compact acceptable anywhere | agent_core+discovery acceptable anywhere |
|---|---:|---:|---:|
| DeepSeek v3.2 | 0.2500 | 0.2333 | 0.2000 |
| GPT-OSS 120B | 0.2167 | 0.2500 | 0.1500 |

See [`closure_2026_09_10.md`](closure_2026_09_10.md) for the complete
configuration table and protocol evidence.

## New deterministic evidence

Across the 58 held-out cases with an acceptable tool, full-catalog lexical
acceptable recall is 0.8621 at top five, 0.8966 at top eight, and 0.9483 at
top twenty. Three cases have no acceptable tool in the top twenty:
`math-008`, `version-004`, and `network-004`.

The evaluation-only `expanded_small15` and `expanded_medium22` cores cover
28/58 and 35/58 held-out tool cases statically, compared with 21/58 for the
current core. Their compact footprints are 16,499 B and 24,374 B, retaining
86.1% and 79.4% reductions versus `full/full`. This is useful candidate
selection evidence, not a model-selection result.

## Decision

The recommendation gate remains closed. No candidate is promoted, no new MCP
profile is added, and no composite tool is justified. `full` remains the
compatibility default and practical general-agent recommendation; `agent_core`
and deterministic discovery remain opt-in experimental facilities.

The missing per-case normalized closure rollouts prevent a complete corrective
classification of model-visible selection and compact-versus-normal detail.
The analyzer is ready to consume those records via
`scripts/analyze_mcp_tool_selection_failures.py --rollouts ...` when a future
provider run retains the provider-neutral JSONL.

No multi-step end-to-end confirmation is claimed because no finalist passed
the frozen held-out recommendation gate.
