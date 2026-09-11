# Corrective development analysis — 2026-09-10

Status: deterministic analysis complete; no production profile change

This is the reproducible portion of Plan 043. It uses the 121-case corpus,
the current `ToolRegistry.search_tools()` implementation, and the
evaluation-only candidate lists in [`candidate_sets.json`](../candidate_sets.json).
It makes no model or network calls.

## Discovery depth

Recall is measured over cases with at least one acceptable tool (59
development, 58 held-out). “Acceptable” includes both primary and supporting
tools; primary-only recall is included to show the stricter signal.

| split | metric | @1 | @3 | @5 | @8 | @10 | @20 | median first | p90 first |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| development | acceptable | 0.8305 | 0.9492 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1 | 3 |
| development | primary | 0.7797 | 0.9153 | 0.9661 | 0.9661 | 0.9831 | 1.0000 | — | — |
| held_out | acceptable | 0.6724 | 0.7759 | 0.8621 | 0.8966 | 0.9138 | 0.9483 | 1 | 5 |
| held_out | primary | 0.5517 | 0.6552 | 0.7586 | 0.8448 | 0.8448 | 0.9138 | — | — |

Held-out cases with no acceptable result in the top 20 are `math-008`,
`version-004`, and `network-004`. The ranker therefore has both a depth
problem and a small true lexical-recall gap; increasing injection depth alone
cannot guarantee recovery.

## Evaluation-only candidate cores

The candidate lists were selected from development-set static misses and
marginal domain coverage. They are not MCP profiles and do not alter
authorization or the server default.

| candidate | tools | compact bytes | reduction vs full/full | development static acceptable | held-out static acceptable | development core misses avoided |
|---|---:|---:|---:|---:|---:|---:|
| `current_core10` | 10 | 11,706 | 90.1% | 16/59 (0.2712) | 21/58 (0.3621) | 0 |
| `expanded_small15` | 15 | 16,499 | 86.1% | 27/59 (0.4576) | 28/58 (0.4828) | 11 |
| `expanded_medium22` | 22 | 24,374 | 79.4% | 34/59 (0.5763) | 35/58 (0.6034) | 20 |
| `default26` | 26 | 27,872 | 76.5% | 29/59 (0.4915) | 31/58 (0.5345) | 15 |

The medium candidate has better deterministic static coverage than the
existing default candidate on this corpus, but that does not establish better
model selection. Candidate schemas were measured in compact mode only; the
existing full/normal/compact measurements remain in the baseline report.

## Stopping decision

No search weights, catalog metadata, runtime behavior, protocol behavior, or
permanent profile membership changed. The deterministic evidence supports
testing a modestly expanded core with staged top-five/top-eight discovery in a
future provider-run experiment, but does not justify promoting it here.

The repository does not contain the per-case normalized JSONL from the prior
two-family closure run, and no provider gateway is configured in this
environment. Consequently this pass cannot honestly claim exposed-selection,
compact-description, no-tool-propensity, or end-to-end results. The existing
aggregate closure evidence still fails the recommendation gate, so `full`
remains the practical recommendation and `agent_core` remains experimental.
