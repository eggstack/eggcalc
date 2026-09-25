# Utility Parity Integration and Closure

Status: planned  
Repository: `eggstack/eggcalc`  
Baseline reviewed: `07e0d66c29bdc7a9ab6d5a41033b372b4cec1994`  
Date: 2026-09-04  
Depends on: `plans/029-eggsact-deterministic-utility-parity-roadmap.md`, `plans/030-network-and-encoding-utility-parity.md`, `plans/031-temporal-and-cron-utility-parity.md`

## 1. Purpose

Complete the six-tool eggsact parity line after the direct exact implementations exist. This plan owns the cross-cutting work that turns the primitives into supported eggcalc product surfaces without duplicating authorities:

- lazy exact exports;
- MCP schemas and metadata;
- MCP handlers and registry/profile wiring;
- resource/budget classification;
- single-file build manifest integration;
- package versus generated-single-file parity;
- generated documentation and architecture updates;
- final verification and closure.

This plan must not become a general MCP refactor, CLI expansion, build-system redesign, or broader eggsact synchronization pass.

## 2. Governing constraints

- Runtime remains Python standard-library-only.
- Existing 77 tools, their schemas, profiles, aliases, protocol behavior, and lifecycle remain unchanged except for registry counts caused by the six additions.
- New tools are `full`-profile contextual utilities only, matching eggsact's exposure choice.
- Do not add the tools to `default`, `human_math`, or any `codegg_*` profile unless a separate future plan explicitly justifies that change.
- No new top-level calculator API or calculator CLI syntax is added.
- No duplicate implementations are allowed in MCP handlers; handlers delegate to exact functions.
- `MODULE_MANIFEST` remains the single source of truth for generated-single-file module ownership/dependencies.
- Generated docs must be regenerated from registry/schema truth where the repository already provides a generator.
- No new release automation, CI matrix, benchmark gate, or cross-repository test dependency is added.

## 3. Final tool inventory

Register exactly:

```text
network
    ip_inspect
    cidr_inspect

encoding
    codec_convert
    radix_convert

temporal
    datetime_convert
    cron_inspect
```

If no unrelated registry changes land before implementation, this moves the MCP inventory from 77 to 83 tools and category count from 18 to 21. Code and generated docs must derive the actual counts from current registry truth rather than hard-code these numbers in logic.

## 4. Workstream A - exact package surface

### A1. Lazy imports

Extend `eggcalc/exact/__init__.py` using the package's existing lazy import mechanism so importing `eggcalc` or `eggcalc.cli` does not eagerly import the three new implementation modules.

Expose:

```text
ip_inspect
cidr_inspect
codec_convert
radix_convert
datetime_convert
cron_inspect
```

Do not eagerly import `ipaddress`, temporal regex/parser code, or Base64 helpers at top-level `eggcalc` import time.

### A2. Public boundary

These names belong under `eggcalc.exact`, not the core `eggcalc` calculator API. Do not add them to the core calculator's eager `__init__.py` exports.

If current exact-package conventions intentionally omit some domain-specific functions from `exact.__init__`, direct module imports are acceptable; choose one consistent policy and document it. The preferred outcome for these six standalone utilities is lazy exact re-export because they are deliberate utility features, but preservation of import-cost authority takes precedence over stylistic symmetry.

### A3. Import regression

Add a clean-subprocess test proving:

- `import eggcalc` does not load `eggcalc.exact.network`, `.encoding`, or `.temporal`;
- importing the exact namespace does not eagerly load implementation modules if the package remains fully lazy;
- calling one function loads only the required implementation path where practical.

Do not add brittle assertions for every transitive standard-library module.

## 5. Workstream B - MCP schemas

Add schemas to `eggcalc/mcp/schemas.py` following the existing schema authority and metadata conventions.

### B1. `ip_inspect`

Input:

```json
{
  "type": "object",
  "properties": {
    "address": {"type": "string", "maxLength": 100000}
  },
  "required": ["address"]
}
```

Output properties:

```text
address: string
family: "ipv4" | "ipv6"
bytes_hex: string
numeric: string
special_use: array[string]
ipv4_mapped: object | null
```

### B2. `cidr_inspect`

Input:

```text
cidr: required string, maxLength 100000
contains: optional string, maxLength 100000
```

Output properties:

```text
family
cidr
prefix_length
host_bits
network_address
netmask
first_address
last_address
broadcast_address: string | null
address_count: string
contains: boolean | null
contains_address: string | null
```

### B3. `codec_convert`

Input:

```text
value: required string, maxLength 100000
from: required enum utf8|hex|base64|base64url
to: required enum utf8|hex|base64|base64url
```

Output:

```text
value
from
to
byte_length
```

### B4. `radix_convert`

Input:

```text
value: required string, maxLength 100000
from_base: required integer 2..36
to_base: required integer 2..36
uppercase: optional boolean, default false
```

Output:

```text
value
from_base
to_base
uppercase
negative
magnitude_decimal
```

### B5. `datetime_convert`

Input:

```text
value: required string, maxLength 100000
format: required enum rfc3339|unix_seconds|unix_milliseconds|unix_nanoseconds
output_offset: optional string matching Z or +/-HH:MM
```

Output:

```text
rfc3339
utc_rfc3339
unix_seconds
unix_milliseconds
unix_nanoseconds
offset_seconds
selected_offset
components
```

### B6. `cron_inspect`

Input:

```text
expression: required string, maxLength 100000
after: required RFC3339 string, maxLength 100000
count: optional integer 1..32, default 5
```

Output:

```text
expression
normalized_expression
parsed_values
offset
offset_seconds
satisfiable
next_runs: array[string]
count
```

Use existing schema-detail reduction mechanisms. Do not special-case these six tools in `tools/list` outside ordinary registry metadata.

## 6. Workstream C - metadata, categories, profiles, and cost

Register metadata consistent with eggsact:

| Tool | Category | Tier | Exposure intent | Cost |
|---|---|---:|---|---|
| `ip_inspect` | network | 2 | contextual/full only | cheap |
| `cidr_inspect` | network | 2 | contextual/full only | cheap |
| `codec_convert` | encoding | 2 | contextual/full only | cheap |
| `radix_convert` | encoding | 2 | contextual/full only | cheap |
| `datetime_convert` | temporal | 2 | contextual/full only | cheap |
| `cron_inspect` | temporal | 2 | contextual/full only | moderate |

Do not add aliases unless eggsact exposes a reviewed alias. Current upstream specs have none.

Do not place these tools in codegg profiles simply because they may occasionally be useful to coding agents. Profile expansion is a separate context-budget decision.

The default profile must remain unchanged in membership.

## 7. Workstream D - MCP handlers

Add six thin handlers in `eggcalc/mcp/tools.py` using the current deferred-import pattern.

Handler responsibilities are limited to:

1. schema/argument boundary checks already customary in MCP;
2. input byte/length prechecks required by the existing resource model;
3. lazy import of the exact function;
4. invocation;
5. mapping deterministic exact success/failure into the existing result envelope and machine-code conventions.

Do not duplicate IP classification, Base64 validation, radix parsing, datetime parsing, or cron search logic in `mcp/tools.py`.

For `cron_inspect`, use the existing moderate/heavier timeout budget classification rather than creating an internal worker.

## 8. Workstream E - tool registry authority

Update all registry authorities that currently must agree:

- `TOOL_SCHEMAS` / schema map;
- tool metadata map;
- handler registry;
- category inventory if explicit;
- `full` profile membership;
- generated inventory source structures.

Do not hand-maintain duplicate lists when one can be derived using current repository conventions. If the current MCP consolidation work already established one canonical registry path, add the six tools there and let derived views follow.

Add an invariant test asserting schema and handler sets remain equal after the additions.

## 9. Workstream F - `build_single.py`

### F1. Manifest entries

Add exact modules to `MODULE_MANIFEST`:

```text
exact.network   -> exact/network.py
exact.encoding  -> exact/encoding.py
exact.temporal  -> exact/temporal.py
```

Declare only real internal dependencies. These modules should ideally depend on no other exact module unless implementation proves otherwise.

Add them to `mcp.tools.depends_on` because the generated file's deferred-import rewriting must know those implementation modules exist.

Do not maintain `MODULES_EXACT` manually; it is derived from `MODULE_MANIFEST`.

### F2. Builder rewrite audit

The builder currently performs source rewrites and validates risky literal/comment collisions. After adding the new modules:

- run `python3 build_single.py --validate`;
- ensure no new relative-import shape requires an ad hoc `str.replace` rule if ordinary existing exact imports can be used;
- prefer import style compatible with current flattening rather than adding another builder-specific transform;
- if a builder change is unavoidable, extend its validation to cover the new rewrite and add one focused regression test.

The preferred result is three manifest entries with no new build transformation machinery.

### F3. Generated single-file smoke

The generated file must support all six MCP tools and any promised exact-library surface.

Do not accept a package-only implementation.

## 10. Workstream G - parity fixture strategy

No test may require a checkout, binary, crate, or Python installation of eggsact.

Create a small static fixture corpus sourced from the reviewed upstream behavior. Record source commit IDs in comments/docstrings.

The corpus should be shared where practical by:

- direct exact-function tests;
- MCP handler tests;
- package/generated-single-file transcript tests.

Do not duplicate hundreds of cases across all three layers. Use:

- exhaustive/boundary semantics at direct exact layer;
- representative success/error envelopes at MCP layer;
- a small representative parity sample at generated-single-file layer.

## 11. Workstream H - package versus single-file parity

Add representative parity cases covering every new module and every major semantic risk:

```text
ip_inspect("::ffff:192.0.2.1")
cidr_inspect("2001:db8::1/64", contains="2001:db8::2")
codec_convert("SGVsbG8", base64 -> hex)
radix_convert(max-u128 decimal -> uppercase hex)
datetime_convert("-1", unix_nanoseconds)
cron_inspect("0 0 */1 * MON", fixed after timestamp)
```

Include at least one malformed input case from each module so the generated file proves comparable error handling, not just happy-path values.

The parity comparison should preserve integer/string/boolean/null types. Do not coerce all results to strings or floats merely to make transcripts easier to compare.

## 12. Workstream I - documentation

Update only documentation made stale by the feature addition.

Required targets likely include:

- `README.md` MCP category/tool count language;
- `docs/tool_inventory.md` via generator;
- `docs/mcp.md` selected examples/category descriptions if generation or existing policy requires all tools to be represented;
- `architecture/overview.md` module counts, exact-module table, MCP tool/category counts, dependency graph;
- new deep-dive docs for `architecture/network.md`, `architecture/encoding.md`, and `architecture/temporal.md` if the repository still maintains one architecture document per runtime module;
- `architecture/exact.md` and/or `architecture/mcp.md` where module/category lists are authoritative;
- `AGENTS.md` exact/MCP counts and stdlib examples only if those facts are maintained there;
- `CHANGELOG.md` under `[Unreleased]`.

Do not manually edit generated inventory content. Run the existing generator/check path.

Documentation must state the important limitations:

- no network access for network inspection;
- no named timezones/DST database;
- cron is five-field fixed-offset inspection only;
- radix conversion intentionally caps magnitude at `u128` for eggsact parity.

## 13. Workstream J - capability and import claims

Review `capabilities.py` and initialize-response runtime metadata only if they enumerate exact feature/category availability explicitly. Do not add a new capability-negotiation mechanism for these tools.

Because every supported Python runtime has the required standard-library modules, there should be no reduced feature mode.

Do not make tool registration conditional on platform or Python minor version.

## 14. Workstream K - focused verification

During implementation, run focused tests for each layer:

```text
direct exact utility tests
MCP schema/registry tests
MCP tool-call tests
build manifest validation
generated-single-file parity/smoke
```

Then run canonical gates:

```bash
make check
make package-check
python3 build_single.py --validate
```

If `make package-check` already invokes single-file generation/validation, keep the explicit command as a useful local diagnostic but do not duplicate it in CI.

## 15. Closure checklist

This line is complete only when all are true:

### Runtime and scope

- [ ] no runtime dependency was added;
- [ ] no existing calculator or tool behavior was removed;
- [ ] no network/filesystem/system-clock/timezone-database behavior was introduced;
- [ ] no unrelated eggsact feature was pulled into scope.

### Exact implementation

- [ ] `exact/network.py` owns both network tools;
- [ ] `exact/encoding.py` owns both encoding tools;
- [ ] `exact/temporal.py` owns both temporal tools;
- [ ] no logic is duplicated in MCP handlers.

### Semantics

- [ ] explicit special-use IP classification is stable;
- [ ] IPv6 address counts are exact including `/0` and `/128`;
- [ ] Base64 validation is strict;
- [ ] radix magnitude is capped at `2**128 - 1`;
- [ ] datetime conversion preserves nanoseconds and negative floor semantics;
- [ ] cron uses corrected Vixie/Cronie star-syntax DOM/DOW behavior;
- [ ] cron search is strictly-after and bounded.

### MCP

- [ ] all six schemas exist;
- [ ] all six handlers exist;
- [ ] schema and handler registries agree;
- [ ] all six are tier 2/full-only contextual tools;
- [ ] `cron_inspect` receives moderate cost/budget treatment;
- [ ] default and codegg profile memberships did not change.

### Distribution

- [ ] all three modules are in `MODULE_MANIFEST`;
- [ ] no unnecessary builder rewrite was added;
- [ ] package and single-file representative parity passes;
- [ ] installed-wheel MCP smoke covers at least one new tool or the registry inventory.

### Documentation

- [ ] generated tool inventory is current;
- [ ] architecture module index is current;
- [ ] MCP/category counts are current wherever documented;
- [ ] feature limitations are documented;
- [ ] changelog contains one concise feature entry.

### Verification

- [ ] focused new tests pass;
- [ ] `make check` passes;
- [ ] `make package-check` passes;
- [ ] `build_single.py --validate` passes;
- [ ] no stale plan claim says the line is complete before these gates are satisfied.

## 16. Handoff order

Recommended implementation order for a coding agent:

1. implement Plan 030 direct functions and tests;
2. implement Plan 031 direct functions and tests;
3. add schemas/metadata/handlers for all six in one coherent registry pass;
4. update `MODULE_MANIFEST` and single-file dependency declarations;
5. add package/single-file parity fixtures;
6. regenerate/update docs;
7. run canonical verification;
8. mark Plans 029-032 implemented only after all closure gates pass.

The implementation can land in fewer commits if desired, but review boundaries should follow these phases so defects can be attributed to primitive semantics, temporal semantics, or integration rather than mixed together.

## 17. Stop rule

When the six tools are implemented, integrated, documented, and verified, stop.

Do not use remaining time in this line to add:

- more codecs;
- more IP metadata;
- timezone names;
- cron syntax extensions;
- scheduler execution;
- new coding-agent profile memberships;
- additional eggsact tools;
- new distribution targets;
- general MCP cleanup.

Those require separate justification and planning.
