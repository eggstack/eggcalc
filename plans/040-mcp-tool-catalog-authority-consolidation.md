# MCP Tool Catalog Authority Consolidation

Status: planned  
Repository: `eggstack/eggcalc`  
Baseline reviewed: `dcd0c5eb427c28712e6fffb75b58b78c8a935494`  
Date: 2026-09-10  
Parent roadmap: `plans/037-mcp-protocol-and-agent-surface-roadmap.md`  
Depends on: Plans 038-039 stable enough that protocol-era fields and standard annotations have settled

## 1. Goal

Reduce MCP tool-definition change amplification without replacing the existing simple Python registries with a framework.

The repository currently maintains tool knowledge in several places:

- `TOOL_SCHEMAS` in `eggcalc/mcp/schemas.py`;
- `TOOL_METADATA` in `eggcalc/mcp/schemas.py`;
- a manual `TOOL_HANDLERS` import list and mapping in `eggcalc/mcp/server.py`;
- `TOOL_PROFILES`, derived from metadata;
- `tests/fixtures/mcp_tool_registry_expected.json`, treated by some documentation as the canonical tool list;
- generated `docs/tool_inventory.md`.

Tests catch many forms of drift, so this is primarily a maintenance/change-amplification problem rather than an immediate correctness defect.

The desired model is two authorities representing genuinely different concerns, with everything else derived:

1. **catalog/selection authority**: canonical tool name, handler binding, category/tier/tags/profile/exposure/cost/stability/composite/annotation/discovery metadata;
2. **protocol schema authority**: description, input schema, output schema, deprecation/title fields required to construct an MCP Tool definition.

`TOOL_HANDLERS`, profiles, generated docs, and compatibility snapshots should be derived or verified artifacts, not separately authored full registries.

Do not force handler callables and 4,000+ lines of JSON-like schema literals into one giant `ToolSpec` expression merely to claim there is "one table." The practical objective is one owner per kind of information.

## 2. Current maintenance problems

### 2.1 Handler registration is manually duplicated

`mcp/server.py` explicitly imports a large list of functions from `mcp/tools.py` and then maps public tool names to those functions in `TOOL_HANDLERS`.

This creates two edit sites for each new handler and makes `server.py` aware of the entire tool implementation surface before the server/runtime classes begin.

### 2.2 Tier metadata is duplicated

`TOOL_SCHEMAS` stores nonstandard top-level `tier`/`tags` fields while `TOOL_METADATA` stores `tier` again and related discovery fields. Tests assert that the two tier values agree.

Tier/tags are agent/catalog selection metadata, not part of MCP `inputSchema` or `outputSchema`. They should have one authority.

### 2.3 Fixture authority is ambiguous

`tests/test_tool_inventory.py` describes the fixture as canonical, and `scripts/generate_mcp_docs.py` emits a "Source of Truth" section stating that the canonical tool list lives in the fixture.

The architecture authority inventory instead describes runtime registries as authoritative. Both cannot be the implementation authority.

The fixture is useful: it makes public tool additions/removals explicit in review. Retain that value by treating it as a **compatibility snapshot/golden approval artifact**, not the data used to construct runtime behavior.

### 2.4 Runtime registry is already a good facade

`ToolRegistry` currently deep-freezes handlers, schemas, metadata, and profiles; validates handler/schema/metadata parity; rejects collisions and unknown profile entries; and returns defensive copies.

Keep `ToolRegistry`. The consolidation should simplify what feeds it, not replace it with decorators, metaclasses, or dynamic plugin registration.

## 3. Constraints

- Standard library only.
- Preserve all current public tool names and direct handlers.
- Preserve `TOOL_HANDLERS`, `TOOL_SCHEMAS`, `TOOL_METADATA`, and `TOOL_PROFILES` as importable compatibility views if external callers/tests may rely on them.
- Keep `ToolRegistry` immutable after construction.
- No decorator-based auto-registration.
- No runtime filesystem scanning/import discovery.
- No source-code generation step required before importing the package.
- No plugin framework.
- No reflection based on function docstrings/signatures as the authoritative schema generator.
- Do not move every schema literal to a new file solely to reduce `schemas.py` line count.
- Do not make generated documentation or a JSON fixture construct runtime registries.
- Do not silently change profile membership while consolidating data ownership.
- Preserve deterministic import/startup characteristics and the deferred exact-tool imports already achieved in `mcp/tools.py`.

## 4. Target authority model

### 4.1 Catalog metadata owns names and handler bindings

Extend the existing tool metadata source so each canonical tool name has an explicit handler locator and all agent-selection metadata.

A minimal shape is sufficient:

```python
TOOL_METADATA = {
    "math_eval": {
        "handler": "math_eval",
        "category": "math",
        "tier": 0,
        "tags": ["math", "evaluation", "arithmetic", "units", "constants"],
        "profiles": ["full", "default", "human_math"],
        "aliases": [],
        "llm_exposure": "default",
        "harness_use": ["none"],
        "cost": "moderate",
        "stability": "stable",
        "composite": False,
        "annotations": {...},
    },
    ...
}
```

The handler field is an attribute name in `eggcalc.mcp.tools`, not an arbitrary import path. Restricting resolution to one known module keeps the mechanism simple and auditable.

If Plan 041 adds `selection_summary` and search keywords, they belong here too.

### 4.2 Protocol schemas own only protocol shape

`TOOL_SCHEMAS[name]` should own fields needed to emit/validate a standard tool definition:

- description/title/deprecated as applicable;
- `inputSchema`;
- `outputSchema`;
- standard tool-level fields that genuinely belong to protocol schema rather than selection metadata.

Remove duplicated `tier` from schema literals after consumers are migrated to metadata.

Move `tags` to metadata as well unless a current external compatibility contract explicitly depends on `TOOL_SCHEMAS[name]["tags"]`. If compatibility requires the old view, synthesize it in an adapter/accessor rather than continuing to author two copies.

### 4.3 Derived runtime handlers

Replace the manual per-handler import list/mapping in `server.py` with one resolver:

```python
from . import tools as _tools


def _build_tool_handlers(metadata):
    handlers = {}
    for name, meta in metadata.items():
        attr = meta["handler"]
        handler = getattr(_tools, attr, None)
        if not callable(handler):
            raise ValueError(...)
        handlers[name] = handler
    return handlers


TOOL_HANDLERS = _build_tool_handlers(TOOL_METADATA)
```

The exact function name can differ. Keep lookup eager/deterministic at MCP module initialization so bad catalog bindings fail fast rather than on the first agent call.

Do not support arbitrary dotted module paths or entry points.

### 4.4 Derived profiles

Continue deriving `TOOL_PROFILES` from the profile memberships in metadata. Do not add a second hand-maintained profile table.

### 4.5 Runtime joined view

Optionally introduce a small frozen `ToolDefinition`/`ToolSpec` dataclass **as a derived joined view**, not as another authored registry:

```python
@dataclass(frozen=True)
class ToolSpec:
    name: str
    handler: Callable[..., Any]
    schema: Mapping[str, Any]
    metadata: Mapping[str, Any]
```

`ToolRegistry` may internally construct/freeze these if it simplifies `tools/list`, search, and invariant enforcement.

Do not add this dataclass if it merely duplicates the four existing frozen mappings without simplifying consumers.

## 5. Workstream A — handler-binding consolidation

1. Add `handler` to each metadata entry.
2. Add metadata validation that handler locators are non-empty valid Python attribute identifiers or otherwise match a narrowly documented naming rule.
3. Import `mcp.tools` once in `server.py` rather than importing 80+ handler symbols individually.
4. Derive `TOOL_HANDLERS` from metadata.
5. Fail deterministically at import/registry construction if a handler attribute is absent/non-callable.
6. Preserve the public `TOOL_HANDLERS` mapping name and exact tool-name keys.

Characterize import-time performance before/after. The change should not eagerly import exact implementation modules, because those remain locally imported inside handler functions.

## 6. Workstream B — tier/tag authority consolidation

### 6.1 Move selection data to metadata

Add/confirm these fields in `TOOL_METADATA`:

```text
category
tier
tags
profiles
aliases
llm_exposure
harness_use
cost
stability
composite
annotations
```

`selection_summary`/`keywords` are deferred to Plan 041 unless adding the fields now materially simplifies migration.

### 6.2 Update consumers

Update:

- `tools/list` tier/tag filters;
- compact/normal list rendering;
- doc generator;
- tests;
- any `_get_tool_tier()` helper;

so tier/tags come from metadata.

### 6.3 Compatibility handling

Search repository/public docs for direct use of `TOOL_SCHEMAS[name]["tier"]` and `TOOL_SCHEMAS[name]["tags"]`.

If these were documented public contracts, retain a derived compatibility accessor/view for one deprecation window. If they are internal implementation details, remove them from schema source literals and update tests.

Do not duplicate them merely to avoid touching internal callers.

## 7. Workstream C — standard versus eggcalc-specific Tool fields

The MCP Tool object has a defined standard shape. Eggcalc-specific fields such as category/tier/tags/exposure/cost should not be sprayed into strict standard tool objects if the negotiated schema does not permit them at top level.

For `tools/list`:

- emit standard fields at standard locations;
- place eggcalc-specific catalog hints under `_meta` only if that is valid and useful for aware clients;
- otherwise keep selection metadata internal to `ToolRegistry` and eggcalc-specific filtering APIs;
- preserve existing eggcalc filters independently of whether metadata is echoed in the result.

Add strict fixture tests for the standard Tool object keys under each supported protocol era.

## 8. Workstream D — compatibility fixture reclassification

Keep `tests/fixtures/mcp_tool_registry_expected.json`, but redefine its role.

It should answer:

> Has the reviewed public callable tool-name set changed?

It should not answer:

> What tools should runtime code instantiate?

Update comments/docs so:

- runtime names come from the catalog metadata authority;
- the fixture is a golden compatibility snapshot intentionally updated when tool additions/removals are approved;
- CI compares the runtime derived set against the snapshot;
- generated docs consume runtime catalog data, not the fixture.

Optional improvement: include a small fixture schema version and expected count to make reviews clearer. Do not put descriptions/schemas/metadata copies in the fixture.

Do not auto-update the compatibility fixture during normal test runs. A public-surface change should remain visible in the diff.

## 9. Workstream E — documentation generation

Update `scripts/generate_mcp_docs.py` so it consumes the derived runtime catalog/metadata and describes authorities correctly.

The generated inventory should include fields useful for maintenance/discovery such as:

- name;
- category;
- tier;
- exposure;
- cost;
- stability/deprecated status;
- composite indicator;
- profile membership;
- short selection-oriented description once Plan 041 provides one.

It should no longer state that the JSON fixture constructs or owns the canonical runtime catalog.

Keep generation standard-library-only and deterministic.

## 10. Workstream F — registry invariants

Strengthen `ToolRegistry`/tests around the new ownership model.

Required invariants:

- metadata key set equals schema key set;
- derived handler key set equals metadata key set;
- every handler locator resolves to exactly one callable;
- no two public tool names collide case-insensitively;
- profile entries are derived only from known metadata names;
- every profile is sorted deterministically;
- annotations use only supported standard fields/types;
- metadata tier/category/exposure/cost/stability values come from bounded enums/sets;
- no `tier` drift test remains because there is only one authored tier value;
- compatibility fixture equals the derived public-name snapshot;
- generated docs are derived from runtime catalog information;
- `ToolRegistry` continues to deep-freeze nested schema/metadata structures.

## 11. Workstream G — authority documentation

Update `architecture/authority_inventory.md` to state clearly:

```text
canonical public tool names + handler locators + selection metadata
    -> TOOL_METADATA (or renamed catalog source if implementation chooses one)

protocol input/output schema
    -> TOOL_SCHEMAS

runtime handlers
    -> derived TOOL_HANDLERS compatibility view

profile lists
    -> derived TOOL_PROFILES

public-name golden fixture
    -> compatibility snapshot only

generated inventory
    -> documentation artifact only
```

If implementation chooses to rename `TOOL_METADATA` to `TOOL_CATALOG_SOURCE` or similar, retain `TOOL_METADATA` as a derived compatibility view and update this document accordingly.

## 12. Files likely to change

Expected primary files:

```text
eggcalc/mcp/schemas.py
eggcalc/mcp/server.py
eggcalc/mcp/tools.py              # only helpers such as _get_tool_tier
tests/test_tool_inventory.py
tests/test_mcp_schema_lint.py
tests/fixtures/mcp_tool_registry_expected.json
scripts/generate_mcp_docs.py
docs/tool_inventory.md
architecture/authority_inventory.md
architecture/mcp.md
```

A small `eggcalc/mcp/catalog.py` is acceptable only if it provides a real cycle/ownership benefit. Do not move thousands of schema lines just to create a new module name.

## 13. Implementation sequence

1. Add characterization tests proving current handler/schema/metadata/profile/fixture sets are identical.
2. Add handler locators to metadata and resolver validation while keeping old `TOOL_HANDLERS` temporarily.
3. Compare old and derived handler mappings by identity/name in tests.
4. Switch `TOOL_HANDLERS` to the derived resolver and remove the giant explicit handler import/mapping block.
5. Add `tags` to metadata where not already present.
6. Move tier/tag consumers to metadata.
7. Remove authored tier/tag copies from protocol schemas if compatibility audit permits.
8. Reclassify the golden fixture in tests/docs.
9. Update doc generation and authority inventory.
10. Measure import/MCP startup to ensure no regression from handler resolution.
11. Run generated-single-file build/parity tests.

## 14. Acceptance criteria

Plan 040 is complete when:

1. `server.py` no longer manually imports and separately maps every MCP handler.
2. Public tool name -> handler binding has one authored authority.
3. Tier has one authored authority; tags have one authored authority.
4. `TOOL_SCHEMAS` remains the protocol input/output-schema authority without unnecessary selection-metadata duplication.
5. `TOOL_HANDLERS` remains available as a derived compatibility mapping.
6. `TOOL_PROFILES` remains derived from catalog metadata.
7. `ToolRegistry` still validates/freeze-owns the complete runtime view.
8. The JSON fixture is documented/tested as a compatibility snapshot rather than runtime source of truth.
9. Generated docs consume the runtime/catalog authorities and contain no competing authority statement.
10. All 83 existing tool names and handler identities are preserved.
11. Deferred imports of exact implementation modules remain deferred until tool invocation.
12. MCP startup/import performance has no material regression; if there is a regression, it is measured and corrected before closure.
13. Package and generated-single-file registries contain identical tool sets and profile membership.
14. No runtime dependency or registration framework is added.
15. `make check` and package/single-file validation pass.

## 15. Verification

Run at minimum:

```bash
python -m pytest tests/test_tool_inventory.py tests/test_mcp_schema_lint.py tests/test_import_boundaries.py tests/test_build_single.py -v
python scripts/generate_mcp_docs.py --check
python build_single.py --validate
make check
make package-check
```

Also retain/import a cold-start measurement comparable to the existing footprint work and assert that importing `eggcalc.mcp` still does not import the deferred `eggcalc.exact.*` implementation modules.

## 16. Non-goals

Do not use this plan to:

- merge all schema and metadata literals into one enormous generated object;
- add decorators or metaclasses;
- scan modules/filesystem for tools;
- use Python entry points/plugins;
- remove the compatibility fixture entirely;
- change the public tool set;
- alter profile memberships for agent optimization;
- add discovery search;
- redesign tool descriptions;
- add new composite tools;
- split `mcp/tools.py` or `mcp/schemas.py` solely by size;
- rewrite the MCP server architecture established by Plans 038-039.

The pass should reduce the number of places a maintainer must edit to add/change a tool while keeping the registry explicit, reviewable, stdlib-only, and fail-fast.