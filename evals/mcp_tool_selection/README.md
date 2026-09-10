# MCP Tool-Selection Evaluation (Plan 041)

Provider-neutral tool-selection corpus and deterministic scoring for the
eggcalc MCP tool catalog. No provider SDK, API key, embedding model, or
network access is required or used anywhere in this directory.

## Layout

```text
evals/mcp_tool_selection/
    cases.json   # 121 realistic task cases (development + held_out)
    README.md    # this file
    reports/     # bounded summary artifacts only (no timestamped sprawl)
```

## Case format

```json
{
  "id": "patch-001",
  "prompt": "I want to replace 'foo' with 'bar' in main.py, but only if it occurs exactly once. Is it safe?",
  "domains": ["patch"],
  "acceptable_primary_tools": ["text_replace_check"],
  "acceptable_supporting_tools": ["edit_preflight"],
  "required_capabilities": ["validate proposed edit"],
  "split": "development",
  "notes": "Why these tools are acceptable"
}
```

- `acceptable_primary_tools` — the tools a good agent should reach for first.
  A set, not a sequence: several strategies may be valid.
- `acceptable_supporting_tools` — reasonable follow-ups or heavier alternatives.
- `split` — `development` (tune descriptions/profiles/search weights) or
  `held_out` (final comparison only). Do not edit held-out expectations to
  fit the latest tool design.
- Empty `acceptable_*` lists mean the correct behavior is **no tool call**
  (pure chat, creative work, or a clarifying question).

## Deterministic tooling (stdlib only, CI-safe)

```bash
# Serialized catalog cost per exposure strategy
python scripts/measure_mcp_tool_surface.py
python scripts/measure_mcp_tool_surface.py --json /tmp/surface.json

# Discovery recall proxy over the corpus (no LLM)
.venv/bin/python - <<'EOF'
import json
from eggcalc.mcp.server import ToolRegistry
cases = json.load(open("evals/mcp_tool_selection/cases.json"))["cases"]
r = ToolRegistry()
for c in cases:
    top = [t["name"] for t in r.search_tools(c["prompt"], limit=5)]
    acc = set(c["acceptable_primary_tools"]) | set(c["acceptable_supporting_tools"])
    if acc and not any(t in acc for t in top):
        print("MISS", c["id"], top[:3])
EOF
```

## External agent evaluation (manual / release, never CI)

1. Pick a catalog config, e.g. `agent_core/compact` or `full/full`.
2. For each case, run any agent harness (codegg, Codex, Claude Code, manual)
   with exactly that catalog and record one JSONL line per case:

```json
{"case_id": "patch-001", "model": "provider/model-version",
 "catalog_config": "agent_core+discovery",
 "tool_calls": [{"name": "edit_preflight", "arguments_valid": true}],
 "completed": true, "task_correct": true,
 "input_tokens": 1234, "output_tokens": 456}
```

`input_tokens`/`output_tokens`/`task_correct` are optional; call-path
metrics are always computed. Record model identifiers, date, and catalog
commit SHA alongside the file.

3. Score offline:

```bash
python scripts/score_mcp_tool_selection.py rollouts.jsonl --split held_out
python scripts/score_mcp_tool_selection.py rollouts.jsonl \
    --footprint /tmp/surface.json --json /tmp/score.json
```

When practical, run held-out evaluation on at least two materially
different agent/model families before changing recommended profile
membership. Tool naming effects are model-dependent.

## Decision gates (Plan 041, section 16)

- `agent_core` should cut initial serialized tool-definition bytes by
  >=70% versus `full/full`.
- Common-task first-tool selection and task correctness must be
  non-inferior to the best current compact/profile baseline.
- `agent_core + discovery` should recover specialist-task performance
  close to `full` with substantially fewer initial schema bytes.
- Invalid-argument and redundant-call rates must not materially worsen.
- New composite/front-door tools need measured held-out benefit; zero
  new tools is an acceptable outcome (current status: zero added).

See `reports/` for the checked-in deterministic baseline.
