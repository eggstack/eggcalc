# MCP Structured Results, Annotations, and Cache Hints

Status: planned  
Repository: `eggstack/eggcalc`  
Baseline reviewed: `dcd0c5eb427c28712e6fffb75b58b78c8a935494`  
Date: 2026-09-10  
Parent roadmap: `plans/037-mcp-protocol-and-agent-surface-roadmap.md`  
Depends on: Plan 038 protocol-era dispatch available or equivalent modern/legacy request classification established

## 1. Goal

Make eggcalc's existing MCP tool definitions and results conform cleanly to the typed MCP tool contract, while adding low-cost protocol metadata that improves client behavior and agent understanding.

This plan addresses four related concerns:

1. tool definitions already declare `outputSchema`, but successful calls currently return only JSON-serialized text content;
2. the declared output schemas generally describe the semantic payload inside eggcalc's `{ok, tool, result, ...}` success envelope, not the outer compatibility envelope;
3. all current MCP tools are deterministic, in-memory/closed-world operations but omit standard MCP tool annotations, causing clients to fall back to pessimistic defaults;
4. modern MCP list/discovery results can be explicitly deterministic/cacheable and can carry concise server instructions, but the current server does not use those capabilities.

The target is protocol correctness and higher-signal metadata without changing the semantics of the 83 tools or adding a new framework.

## 2. Specification and design basis

Primary references:

- MCP tool schema/annotations: https://modelcontextprotocol.io/specification/2025-11-25/schema
- MCP `2026-07-28` release: https://blog.modelcontextprotocol.io/posts/2026-07-28/
- MCP `2026-07-28` SDK migration guidance: https://ts.sdk.modelcontextprotocol.io/v2/migration/support-2026-07-28
- MCP annotations discussion: https://blog.modelcontextprotocol.io/posts/2026-03-16-tool-annotations/
- Anthropic tool design guidance: https://www.anthropic.com/engineering/writing-tools-for-agents

Important constraints from the protocol:

- when a tool advertises an `outputSchema`, its structured result is expected in `structuredContent` and must conform to the declared schema;
- through the `2025-11-25` era, tool `outputSchema`/`structuredContent` are object-rooted; `2026-07-28` broadens the schema/result contract to full JSON Schema 2020-12 / any conforming JSON value;
- compatibility text content may still be returned alongside structured content;
- annotations are hints rather than security guarantees, but omitted fields have deliberately conservative defaults;
- current annotation fields are `readOnlyHint`, `destructiveHint`, `idempotentHint`, and `openWorldHint` plus optional title;
- modern cacheable list/discovery results use `ttlMs` and `cacheScope`;
- modern server identity belongs in response `_meta`, while concise server `instructions` are part of discovery/initialization information.

## 3. Current repository findings

### 3.1 Success envelope versus output schema

Most handlers use `_success_response()` in `eggcalc/mcp/tools.py`, producing a shape like:

```python
{
    "ok": True,
    "tool": "math_eval",
    "result": {
        "value": "8",
        "type": "int",
    },
}
```

The `math_eval` `outputSchema`, however, describes `value`, `type`, `unit`, and `display` directly. That means the natural MCP structured payload is `envelope["result"]`, not the entire eggcalc compatibility envelope.

The existing text representation should remain the full envelope so older consumers do not break.

### 3.2 Error envelopes

Handlers return standardized `{ok: false, ...}` envelopes for domain/tool errors. `ToolExecutor` translates those into MCP `result.content` plus `isError: true`. Preserve that model. Do not force error envelopes through success `outputSchema` unless a tool explicitly declares an error union in the future.

### 3.3 Output validation is currently absent

The server has a bounded schema validator used for input arguments. The current schema-lint suite walks input schemas but does not prove that successful handler payloads conform to `outputSchema`.

A result-boundary validator should be added, but it must not become a general JSON Schema implementation. Validate only the schema keyword subset eggcalc itself emits/supports unless modern schema expansion is explicitly required by an existing tool.

### 3.4 Tool annotations are absent

The MCP tools operate only on arguments supplied by the caller. They do not perform network access, filesystem writes, external service calls, or destructive mutations. MCP `math_eval` specifically disables state-mutating/random operations. As currently scoped, the common annotation posture is therefore:

```text
readOnlyHint = true
openWorldHint = false
```

For read-only tools, `destructiveHint` and `idempotentHint` are semantically secondary, but emitting truthful explicit values can still improve client interpretation. Use the final protocol semantics and avoid relying on annotations as enforcement.

### 3.5 List ordering

`tools/list` filters against a set of profile names but currently iterates the schema registry's insertion order. Python preserves insertion order, so this is deterministic for a fixed source file, but the protocol goal is stronger: catalog order should remain intentionally stable across unrelated source reordering. Sort by canonical tool name before emitting list results.

## 4. Constraints

- Standard library only.
- Preserve direct handler return contracts.
- Preserve existing JSON text tool content for compatibility.
- Do not move eggcalc warning/finding metadata into the semantic payload merely to make schemas easier.
- Do not rewrite all 83 output schemas as schemas for the outer envelope.
- Do not introduce a full JSON Schema engine.
- Do not turn annotations into authorization/safety decisions.
- Do not claim a tool is closed-world/read-only if implementation inspection finds an exception; exceptions must be explicitly annotated.
- Do not add output fields that materially increase normal tool-result token use without evidence.
- Do not use cache hints to serve stale mutable configuration/profile state.
- Do not change existing tool names or semantics.

## 5. Workstream A — define the MCP structured-result boundary

### 5.1 One extraction helper

Add a small helper owned by the MCP protocol layer that maps a handler return value to:

- compatibility text envelope;
- structured payload, when appropriate;
- error status.

Conceptually:

```python
@dataclass(frozen=True)
class ToolWireResult:
    text_envelope: dict[str, Any]
    structured_content: Any | None
    is_error: bool
```

A dataclass is optional. A private tuple/helper is sufficient if clearer.

Expected mapping:

```text
handler result: {ok: true, result: X, ...}
  -> text content = JSON of full handler envelope
  -> structuredContent = X
  -> isError omitted/false

handler result: {ok: false, ...}
  -> text content = JSON of full error envelope
  -> structuredContent omitted unless the protocol requires otherwise
  -> isError = true
```

If a handler returns a nonstandard success shape, characterize it explicitly and either normalize it through the same helper or document why it cannot advertise `outputSchema`.

### 5.2 Preserve compatibility metadata

The full text envelope may contain `warnings`, `limits_applied`, `findings`, `machine_code`, and `recommended_next_tool`. Keep those fields exactly as today unless a separate compatibility change is justified.

Do not silently drop them from the text compatibility representation.

### 5.3 Avoid double serialization drift

Serialize the text envelope and construct structured content from the same in-memory result object. Do not reconstruct either representation independently from handler-specific knowledge.

## 6. Workstream B — output-schema validation

### 6.1 Validate semantic payloads, not wrappers

For successful results with an `outputSchema`, validate `handler_result["result"]` against the declared output schema before returning it as `structuredContent`.

This establishes a clear authority:

```text
TOOL_SCHEMAS[name]["outputSchema"] describes structuredContent
```

The outer eggcalc success envelope remains a compatibility/text contract and is not what `outputSchema` describes.

### 6.2 Reuse bounded validation machinery

Extend/refactor `_validate_value_against_schema()` only as much as necessary so it can validate both inputs and outputs.

Keep protections already present:

- recursion-depth bound;
- finite numeric checks;
- bounded regex behavior;
- array/object recursion;
- exact required/additional-property semantics appropriate to each schema.

If the modern spec permits schema keywords eggcalc does not emit, do not implement them preemptively.

### 6.3 Decide output additional-properties policy explicitly

Many current output schemas may omit `required` or `additionalProperties`. Before enforcing output validation, audit the actual 83 schema/result pairs to determine whether the existing schemas are intentionally partial descriptive schemas or strict contracts.

Preferred end state:

- each output schema accurately describes the semantic payload actually emitted;
- required fields are declared when genuinely guaranteed;
- optional fields remain optional;
- do not use permissive validation merely to hide schema drift.

If tightening all schemas in one pass would be too large, first validate that emitted fields match declared types/properties and create a bounded follow-up fixture list for intentionally partial schemas. Do not silently mark mismatches as success.

### 6.4 Failure behavior

An output-schema mismatch is a server/tool implementation defect, not a user argument error.

Return a sanitized MCP internal/tool execution error and log enough local detail for tests/debugging. Do not expose a traceback or internal file path.

Add invariant tests so this path should not occur in normal operation.

## 7. Workstream C — protocol-era result shape

### 7.1 Legacy structured content

For supported legacy revisions that define structured tool output, emit object-rooted `structuredContent` when the declared output schema is object-rooted.

All currently advertised output schemas should be audited for compatibility with both retained legacy revisions and the modern revision.

Do not begin emitting modern-only arbitrary root values to legacy clients.

### 7.2 Modern structured content

For `2026-07-28`, emit the structured payload allowed by the modern schema. Current tools should not be redesigned just to exercise arbitrary JSON-root support; retain stable object payloads unless a tool already has a justified non-object result contract.

### 7.3 Size accounting

The current output-size guard measures the serialized handler result. Preserve a single bounded output policy.

When adding `structuredContent`, avoid naively counting the same logical data twice and thereby halving the effective result limit. Define the limit over the canonical handler envelope/semantic payload, then serialize both representations only after the logical result passes the bound.

Also test the final JSON-RPC response against `max_output_bytes` if the existing contract intends a wire-size cap rather than only a handler-payload cap. Document which quantity the limit controls.

## 8. Workstream D — standard MCP tool annotations

### 8.1 Annotation authority

Store annotations in the same selection/catalog metadata authority targeted by Plan 040. If Plan 040 has not landed yet, add them in a structure that can be migrated mechanically rather than duplicating them in server emission code.

A small typed shape is sufficient:

```python
class ToolAnnotations(TypedDict, total=False):
    title: str
    readOnlyHint: bool
    destructiveHint: bool
    idempotentHint: bool
    openWorldHint: bool
```

### 8.2 Current default posture

Audit every MCP handler. For tools with current eggcalc semantics, prefer explicit:

```text
readOnlyHint: true
openWorldHint: false
```

For completeness, where correct:

```text
destructiveHint: false
idempotentHint: true
```

Because `destructiveHint` and `idempotentHint` are primarily meaningful when `readOnlyHint == false`, tests should validate logical consistency rather than pretending those fields provide stronger guarantees than the spec.

### 8.3 Enforcement remains elsewhere

Do not make profile permissions, evaluator side-effect policy, or security controls depend on annotations. Existing deterministic code and server policy remain authoritative.

## 9. Workstream E — concise server instructions

Define one short static instruction string for the MCP server, not a long prompt.

The instruction should communicate relationships that are expensive to repeat in every tool description, for example:

- prefer composite preflight tools for general edit/command/config safety checks;
- use specialist primitives when exact evidence from that domain is required;
- prefer `json_extract` over deprecated `json_query`;
- use `math_eval` for deterministic calculations/unit expressions rather than model arithmetic;
- all tools are local/deterministic and do not access network/filesystem unless a future tool explicitly says otherwise.

Keep this to a few sentences. Do not include a full tool catalog.

Expose the same authority through:

- legacy initialize response if supported by that revision;
- modern `server/discover` result.

Do not maintain two prose copies.

## 10. Workstream F — deterministic list output and cache hints

### 10.1 Canonical ordering

Change `tools/list` emission to iterate canonical sorted tool names after applying visibility/filter rules.

Tests should prove that reordering the underlying source mapping does not change emitted catalog order.

### 10.2 Cache hint policy

Modern `server/discover` and `tools/list` need protocol-correct cache fields.

Start with the smallest safe policy. The recommended implementation sequence is:

1. Plan 038 emits conservative `ttlMs: 0`, `cacheScope: "private"` for conformance.
2. This plan evaluates whether a nonzero TTL is safe for an immutable `McpServer` registry/config/profile.
3. If safe, use one small server-configured/static constant rather than per-tool TTL machinery.

A nonzero `tools/list` TTL is justified only if:

- registry contents are immutable for the lifetime represented by the TTL;
- profile and schema-detail selection are part of the request/config key observed by the client cache;
- explicit compatibility setters that invalidate/recreate the compatibility server cannot cause stale cross-server catalog reuse.

If those conditions are hard to prove, retain `ttlMs: 0`. Protocol correctness is more important than speculative caching.

Use `cacheScope: "private"` by default unless there is a clear reason to declare cross-user/public cacheability. Eggcalc has no user-specific external data, but conservative scope avoids assumptions about host-level configuration.

## 11. Workstream G — schema/detail modes and agent signal

Do not solve catalog bloat by stripping essential discriminators from every schema.

Review `compact_schema()` and `normal_schema()` with these principles:

- required argument names/types/enums/constraints remain available;
- short descriptions should answer when to use the tool, not merely restate its name;
- output structure can remain shallow in compact mode;
- annotations should survive compact/normal/full modes because they are small and useful;
- internal eggcalc metadata (`tier`, category, exposure, cost) may be included only when it helps an aware harness and does not violate the standard tool object shape expected by strict clients.

If current eggcalc-specific keys are emitted directly in standard tool definitions and strict clients reject them, move such data under `_meta` or keep it internal to filtered/custom catalog APIs according to the final MCP schema.

## 12. Tests

Add a representative output-schema corpus covering every result-shape family, then add a generated/invariant test over all tools where deterministic minimal valid arguments are already available.

Required cases:

- `math_eval`: structured payload equals text-envelope `result`;
- unit conversion/info;
- text metric/comparison tool;
- composite tool with `findings`/`warnings` on outer envelope;
- validation failure -> `isError: true`, no false success structured payload;
- timeout error;
- output-too-large error;
- optional output fields omitted legitimately;
- nested object/array output validation;
- legacy structured object result;
- modern structured result;
- output-schema mismatch produces internal/tool error in a synthetic registry test;
- all visible tools emit annotations with allowed values;
- annotation invariants (`readOnlyHint=true` tools do not advertise destructive behavior as a meaningful requirement);
- `tools/list` sort order independent of mapping insertion order;
- server instructions identical across legacy/modern authorities;
- modern cache fields present with the chosen conservative/safe values;
- package and generated-single-file transcripts match semantically.

## 13. Files likely to change

Expected primary files:

```text
eggcalc/mcp/server.py
eggcalc/mcp/schemas.py
eggcalc/mcp/tools.py               # ideally only if result contract characterization finds exceptions
eggcalc/mcp/__init__.py            # only if public metadata types are exported
tests/test_mcp_server.py
tests/test_mcp_schema_lint.py
tests/test_tool_inventory.py
scripts/generate_mcp_docs.py
docs/mcp.md
docs/tool_inventory.md
architecture/mcp.md
architecture/authority_inventory.md
```

Prefer a new focused test module for result-contract tests if that keeps `test_mcp_server.py` manageable.

## 14. Implementation sequence

1. Characterize handler success/error envelopes and identify any exceptions to `_success_response()`.
2. Audit every `outputSchema` against its successful inner `result` payload.
3. Add output-schema validation tests before changing wire output.
4. Introduce one result-boundary mapper in `ToolExecutor`/MCP protocol layer.
5. Emit `structuredContent = success_envelope["result"]` and keep full compatibility JSON text.
6. Add/fix result schema validation until all existing tools satisfy their declared contracts.
7. Add tool annotations from the catalog/metadata authority.
8. Add shared concise server instructions.
9. Make tool-list order explicitly canonical.
10. Centralize modern cache-hint emission and choose conservative/nonzero TTL only with invariants.
11. Regenerate MCP documentation/inventory.
12. Run legacy + modern + single-file parity verification.

## 15. Acceptance criteria

Plan 039 is complete when:

1. Every visible tool with `outputSchema` emits conforming `structuredContent` on successful MCP calls.
2. The structured payload equals the `result` member of the existing text compatibility envelope for standard success handlers.
3. Existing text content remains present and backward compatible.
4. Domain/tool errors remain `isError: true` and are not misrepresented as output-schema success values.
5. Output-schema drift is caught by tests/validation rather than silently serialized.
6. Output size limits remain bounded and documented after dual representation is added.
7. All current read-only/closed-world tools advertise truthful standard annotations.
8. Annotations do not become security-policy authorities.
9. Legacy and modern result shapes respect their protocol-era schema restrictions.
10. `tools/list` ordering is explicitly deterministic by canonical tool name.
11. Modern discover/list cache fields are emitted from one policy authority; conservative zero-TTL is acceptable if safe nonzero caching is not proved.
12. One concise server instruction authority is reused across protocol eras.
13. Compact/normal/full schema modes preserve enough information for correct invocation and do not emit invalid standard tool objects.
14. Generated docs and single-file transcripts are updated.
15. No runtime dependency is added.
16. `make check` and package/single-file validation pass.

## 16. Verification

Run at minimum:

```bash
python -m pytest tests/test_mcp_schema_lint.py tests/test_tool_inventory.py tests/test_mcp_server.py -v
python build_single.py --validate
python scripts/generate_mcp_docs.py --check
make check
make package-check
```

Also run direct transcript checks that parse both the JSON text content and `structuredContent` and assert:

```text
json.loads(content[0].text)["result"] == structuredContent
```

for representative successful tools.

## 17. Non-goals

Do not use this plan to:

- redesign all handler return types;
- remove the eggcalc compatibility envelope;
- rewrite every output schema as an envelope schema;
- implement all of JSON Schema 2020-12;
- add remote/network/file I/O tools;
- add new destructive tools;
- change tool profile membership;
- add dynamic discovery or a tool-search MCP RPC;
- add HTTP/authorization;
- add a result-format negotiation parameter to every tool;
- introduce an external MCP SDK.

This pass should leave the same tools and the same semantic results, but with a protocol-correct structured representation and accurate low-cost metadata.