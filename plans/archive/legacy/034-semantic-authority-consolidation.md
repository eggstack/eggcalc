# Semantic Authority Consolidation

Status: planned  
Repository: `eggstack/eggcalc`  
Baseline reviewed: `55993e58b438f4548c58569248cdada52c099030`  
Date: 2026-09-08  
Parent roadmap: `plans/033-surface-consolidation-and-maintainability-roadmap.md`

## 1. Goal

Remove two concrete semantic duplications from the current codebase while preserving public compatibility:

1. RFC 6901 JSON Pointer extraction currently exists as both `json_query()` and `json_extract()`.
2. SemVer comparison logic exists both in `exact.validate.version_compare()` and in the dedicated `exact.version` module.

The implementation should establish one authority for each behavior and leave old public names as thin compatibility facades where required.

This is a consolidation pass, not a feature redesign.

## 2. Constraints

- Standard library only; no runtime dependency changes.
- Preserve existing public return shapes unless an already-deprecated API explicitly permits a compatibility wrapper.
- Do not delete `json_query` in this pass unless repository evidence proves it has no compatibility obligation. Default is to retain it as a wrapper.
- Preserve `version_compare(..., scheme="loose")` if it is currently public/documented.
- Preserve current MCP JSON-RPC envelopes and error conventions.
- Do not widen supported SemVer syntax during consolidation.
- Do not create a generic semantic-dispatch abstraction.
- Package and generated single-file behavior must remain equivalent.

## 3. Workstream A — RFC 6901 JSON Pointer authority

### 3.1 Establish `json_extract` as canonical

Audit the current bodies of:

- `eggcalc/exact/validate.py::json_query`
- `eggcalc/exact/validate.py::json_extract`
- MCP handlers/schemas for `json_query` and `json_extract`
- exact lazy exports
- docs and tests referencing either function

Move any behavior needed for compatibility into `json_extract` or private helpers used by `json_extract`.

After this change, `json_query` must not contain an independent traversal/parser implementation. It should delegate to the canonical path and translate only the result shape required by its historical contract.

### 3.2 Preserve compatibility shape

If `JsonQueryResult` and `JsonExtractResult` differ, keep the old shape for `json_query` by adapting the canonical extraction result.

Do not make callers of a deprecated API silently receive a different result schema merely to simplify code.

### 3.3 MCP exposure cleanup

Current MCP documentation marks `json_query` deprecated while placing it in the Tier-1/default set. Correct that mismatch.

Required behavior:

- `json_extract` remains available under its intended profile(s);
- `json_query` remains callable if backward compatibility requires it;
- `json_query` must not be preferred/default-exposed over `json_extract`;
- metadata should mark the replacement explicitly where the schema/metadata model supports that without adding a new framework field;
- generated tool inventory/docs must reflect the live registry/profile state.

Do not remove unrelated default tools.

### 3.4 Tests

Create a shared RFC 6901 fixture corpus covering at least:

- empty pointer/root;
- object key lookup;
- array indexes;
- `~0` and `~1` escaping;
- empty keys;
- missing object keys;
- invalid array indexes;
- pointer syntax errors;
- scalar traversal failures;
- large output/truncation behavior where `json_extract` supports `max_output_chars`;
- malformed JSON.

For cases representable by both contracts, assert `json_query` behavior is derived from and semantically consistent with `json_extract`.

## 4. Workstream B — SemVer authority

### 4.1 Dedicated authority

`eggcalc/exact/version.py` should own:

- SemVer parsing;
- prerelease parsing;
- SemVer precedence comparison;
- Cargo constraint semantics already implemented there.

`exact.validate.version_compare(..., scheme="semver")` should delegate to this authority rather than parse/compare versions independently.

If the dedicated module lacks a small public/private comparator needed by `version_compare`, add the narrowest helper necessary. Prefer a helper such as comparing two parsed versions or two version strings rather than importing constraint machinery unnecessarily.

### 4.2 Preserve `loose` behavior

If `version_compare(..., scheme="loose")` is part of the current public contract, leave that implementation in `validate.py` or a small private helper there.

Do not force loose-version semantics into the SemVer module.

### 4.3 SemVer correctness corpus

Before changing implementation, capture current intended behavior and compare it to SemVer precedence rules already implemented by `exact.version`.

Tests should include:

- `1.0.0 == 1.0.0`;
- major/minor/patch ordering;
- prerelease lower than release;
- prerelease identifier ordering;
- numeric versus alphanumeric prerelease identifiers;
- multiple prerelease components;
- build metadata ignored for precedence;
- malformed/incomplete versions according to eggcalc's declared contract;
- any accepted leading `v` or shorthand behavior only if currently supported by the dedicated parser;
- versions used by Cargo constraint tests to prevent divergence.

Do not silently broaden acceptance just because one implementation is more permissive.

If the current public `version_compare` contract intentionally differs from strict SemVer, document the difference and make the dedicated module expose that exact declared mode. The implementation still needs one authority.

## 5. Workstream C — Authority documentation and invariants

Correct `architecture/authority_inventory.md` so it states:

- `eggcalc/_protocol.py` is the authority for supported MCP protocol versions;
- `capabilities.py` and `mcp/server.py` import from it;
- no intentional protocol-version duplicate remains.

Review the same document for the two authorities changed in this plan:

- RFC 6901 extraction authority;
- SemVer parser/comparator authority.

Add lightweight invariant tests if there is an obvious stable assertion. Examples:

- server/capabilities protocol tuples equal `_protocol.SUPPORTED_PROTOCOL_VERSIONS`;
- `json_query` has parity with canonical extraction fixtures;
- SemVer `version_compare` agrees with `exact.version` comparator fixtures.

Do not add source-code text inspection unless no behavioral invariant can prove the property.

## 6. Files likely to change

Expected primary files:

```text
eggcalc/exact/validate.py
eggcalc/exact/version.py
eggcalc/exact/__init__.py
eggcalc/mcp/schemas.py
eggcalc/mcp/tools.py
architecture/authority_inventory.md
architecture/version.md
architecture/validate.md
docs/mcp.md
docs/tool_inventory.md   # generated if current generator owns it
tests/...
```

`build_single.py` should change only if module authority/import wiring requires it. Do not reorder or redesign the build manifest unnecessarily.

## 7. Implementation sequence

1. Add/strengthen shared JSON Pointer parity tests before deleting any duplicated body.
2. Make `json_query` delegate to canonical extraction while preserving old result shape.
3. Update MCP metadata/profile exposure for deprecated `json_query`.
4. Add/strengthen SemVer comparison corpus around `exact.version`.
5. Change `version_compare(..., "semver")` to delegate to the dedicated module.
6. Preserve and test `loose` mode separately.
7. Correct authority documentation.
8. Regenerate generated MCP docs.
9. Validate package/single-file parity.

## 8. Acceptance criteria

Plan 034 is complete when:

- there is one RFC 6901 traversal implementation authority;
- `json_query` is a compatibility adapter, not an independent parser/traversal implementation;
- deprecated `json_query` is no longer preferred in default MCP exposure;
- `json_extract` remains the replacement public tool;
- there is one SemVer parsing/precedence authority in `exact.version`;
- `version_compare(..., scheme="semver")` uses that authority;
- `loose` behavior remains backward compatible;
- protocol authority documentation points to `_protocol.py`;
- relevant docs/tool inventory are regenerated and consistent;
- current callers and MCP envelopes remain compatible;
- no runtime dependencies are added;
- focused tests, `make check`, and single-file validation pass.

## 9. Verification

Run at minimum:

```bash
python -m pytest tests/ -k 'json_query or json_extract or version_compare or version_constraint or protocol' -v
python build_single.py --validate
make check
```

Before closure, also execute representative direct package and generated-single-file checks for:

- `json_extract`;
- deprecated `json_query` compatibility if exposed in the single file;
- SemVer comparison with prerelease/build metadata;
- loose comparison.

## 10. Non-goals

Do not use this plan to:

- remove deprecated APIs immediately;
- implement full JSONPath/JMESPath;
- expand JSON Schema support;
- add PEP 440 support;
- implement npm/Maven version semantics;
- broaden Cargo constraint syntax;
- restructure `validate.py` wholesale;
- change MCP JSON-RPC lifecycle or server concurrency;
- redesign tool profiles beyond the specific deprecated replacement correction.

The pass should end with less semantic duplication and the same product behavior.
