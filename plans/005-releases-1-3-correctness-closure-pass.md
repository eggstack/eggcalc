# Releases 1–3 Correctness Closure Pass

Status: ready for implementation handoff  
Repository: `eggstack/eggcalc`  
Depends on:

- `plans/002-release-1-calculator-semantic-correctness.md`
- `plans/003-release-2-mcp-protocol-conformance.md`
- `plans/004-release-3-inspection-tool-correctness.md`

Primary objective: close the remaining correctness, compatibility, terminology, and verification gaps after implementation of Releases 1–3.

## 1. Purpose

The first three correctness releases have substantially landed:

- calculator caret, floor-division, and modulo semantics were corrected;
- the MCP server gained explicit lifecycle handling, protocol negotiation, request validation, session-scoped cancellation, schema linting, and transcript tests;
- Python, Cargo, requirements, JavaScript, Go, and lockfile inspection received structured findings, corrected metadata extraction, richer fixtures, and broad boundary coverage.

The remaining work is not a new feature release. It is a bounded closure pass intended to establish that the implemented behavior is internally consistent, accurately documented, interoperable with the current stable MCP specification, and supported by reproducible release evidence.

This plan must not expand into the later roadmap work on runtime-version policy, broad state isolation, import decoupling, or canonical unit representation.

## 2. Closure outcomes

At completion, the repository must be able to claim all of the following without qualification:

1. Release 1 calculator semantics are consistent across the installed package, CLI, generated single-file build, and documented public APIs.
2. The MCP stdio server supports the current stable `2025-11-25` protocol revision and retains explicitly tested compatibility with `2024-11-05` where practical.
3. MCP initialization validates the required request fields, records negotiated client metadata and capabilities, and cannot be silently bypassed by new embedded integrations.
4. Cargo dependency-name findings distinguish non-ASCII, mixed-script, and actual confusable-name concerns instead of labeling every non-Latin letter as a confusable.
5. Release 3 inspection results preserve their structured finding contract and remain JSON serializable across all fixtures and boundary paths.
6. A reproducible verification record demonstrates lint, formatting, typing, tests, generated-file parity, package installation, CLI operation, and MCP transcript parity.
7. Documentation and changelogs accurately state what protocol versions and syntax contracts are supported.

## 3. Non-goals

The implementation agent must not include the following work in this pass:

- adopting the draft or release-candidate `2026-07-28` stateless MCP protocol;
- implementing HTTP or Streamable HTTP transport;
- adding MCP resources, prompts, sampling, elicitation, or task execution merely because they exist in newer protocol schemas;
- redesigning the complete MCP server architecture;
- removing Python 3.10 support or changing `requires-python`;
- eliminating all process-global state;
- refactoring the entire unit engine;
- adding new inspection ecosystems or package managers;
- adding runtime dependencies solely to simplify tests or protocol parsing;
- changing calculator syntax beyond documented Release 1 behavior.

Any defect discovered outside this scope must be recorded separately unless it directly prevents an acceptance criterion in this plan.

## 4. Workstream A — Stable MCP protocol revision support

### A1. Define the supported revision set

Update the authoritative protocol constants so the server supports at least:

```python
SUPPORTED_PROTOCOL_VERSIONS = (
    "2024-11-05",
    "2025-11-25",
)
LATEST_SUPPORTED_PROTOCOL_VERSION = "2025-11-25"
```

The exact ordering may differ, but the latest stable revision must be unambiguous and selected deterministically.

Protocol strings must have one source of truth. Tests, documentation, server responses, and generated single-file output must derive from or agree with those constants.

### A2. Implement revision-aware initialization

Initialization must:

- require a JSON object for `params`;
- require a non-empty string `protocolVersion`;
- require an object-valued `capabilities` field;
- require object-valued `clientInfo` with at least non-empty string `name` and `version` fields;
- return `-32602` for malformed initialization parameters;
- return the requested revision when it is supported;
- use documented fallback behavior for an unsupported revision;
- record the negotiated revision on the connection/session object;
- include server implementation metadata and declared server capabilities in the response.

Do not infer support for a revision merely because its version string is accepted. Any revision-specific response schema or behavior used by eggcalc must be represented explicitly in code or tests.

### A3. Preserve legacy compatibility deliberately

`2024-11-05` support must be treated as an explicit compatibility path, not an accidental fallback.

Add a small revision-policy abstraction or helper if needed so tests can assert:

- supported revision recognition;
- latest revision selection;
- unsupported revision fallback;
- per-session negotiated revision retention;
- response revision equality with the selected policy.

### A4. Do not pre-adopt the draft stateless redesign

Add a concise architecture note stating that the planned `2026-07-28` revision is intentionally out of scope until final publication and a separate migration plan.

The current stdio lifecycle implementation may remain stateful. Avoid changes that make a future stateless adapter harder, but do not redesign around draft behavior.

## 5. Workstream B — Initialization capability and client metadata handling

### B1. Store negotiated client information

Extend `McpSession` or its associated immutable initialization state to retain:

- requested protocol revision;
- negotiated protocol revision;
- client name;
- client version;
- optional client title or description when present;
- client capabilities as a validated mapping.

This state must be session-local and must not leak between sequential or concurrent sessions.

### B2. Declare only implemented server capabilities

The initialize response must advertise only capabilities actually supported by eggcalc.

For the existing tool-only stdio server, the response should declare tools support and must not advertise resources, prompts, sampling, roots, logging, elicitation, or tasks unless the corresponding behavior exists and is tested.

If tool list-change notifications are not implemented, do not claim them.

### B3. Capability retention tests

Tests must establish that:

- client capability dictionaries are retained without mutation;
- one session’s client metadata does not appear in another session;
- malformed capability shapes return `-32602`;
- unknown capability keys do not crash initialization;
- optional metadata fields are accepted without becoming required;
- initialize responses contain exactly the intended server capabilities.

## 6. Workstream C — Eliminate ambiguous sessionless lifecycle bypass

### C1. Make the compatibility path explicit

Current sessionless `handle_request(request, session=None)` behavior implicitly uses a ready session. Replace this ambiguity with one of the following designs:

Preferred design:

```python
class McpSession:
    def handle_request(self, request: Any) -> dict[str, Any] | None: ...


def handle_request_legacy(request: Any) -> dict[str, Any] | None: ...
```

Acceptable transitional design:

- keep `handle_request(..., session=None)`;
- emit a documented deprecation warning for sessionless calls;
- route it through a clearly named private legacy-ready session;
- prohibit production stdio code from using the compatibility path;
- add a removal milestone to documentation.

Do not silently create a new ready session for every call, because cancellation, initialization metadata, and lifecycle state would become misleading.

### C2. Protect the stdio entry point

The stdio server must always instantiate an uninitialized connection/session and require:

```text
initialize request
→ initialize response
→ notifications/initialized
→ operational requests
```

No environment variable, helper default, or compatibility shim may place the real stdio server into `READY` before the handshake.

### C3. Lifecycle misuse tests

Add tests for:

- tools/list before initialize;
- tools/call before initialize;
- initialized notification before initialize;
- a second initialize request;
- operations during `INITIALIZING` before the initialized notification;
- operations after close;
- sessionless compatibility behavior and warning/deprecation contract;
- the package and single-file stdio entry points independently.

## 7. Workstream D — MCP error and notification consistency audit

### D1. Audit error classification

Review every top-level method and validation failure and enforce:

| Condition | Required code |
|---|---:|
| Invalid JSON | `-32700` |
| Invalid JSON-RPC envelope | `-32600` |
| Unknown request method | `-32601` |
| Invalid method parameters | `-32602` |
| Unexpected internal exception | `-32603` |
| Tool execution failure | documented server error code |

Malformed `initialize`, `tools/list`, and `tools/call` parameter values must return `-32602`, not `-32600`.

### D2. Notification behavior

For every notification:

- never emit a JSON-RPC response;
- do not include an `id` in internal response construction;
- ignore unknown notification methods unless the protocol explicitly requires another action;
- keep cancellation records scoped to the current session;
- apply request ID normalization consistently.

Explicit `id: null` on a request must remain invalid. A notification is defined by the absence of the `id` member, not by a null value.

### D3. Transcript coverage

Add or update raw stdio transcript fixtures for both supported revisions covering:

- valid initialization;
- unsupported-version fallback;
- malformed initialization;
- pre-initialization tool request;
- successful tools/list;
- successful tools/call;
- unknown request method;
- unknown notification method;
- cancellation notification;
- EOF;
- broken pipe where test infrastructure permits.

Package and generated single-file transcripts must be structurally equivalent after excluding intentionally variable metadata.

## 8. Workstream E — Cargo identifier and confusable-policy correction

### E1. Replace the code-point-range heuristic

Remove or narrow any logic equivalent to:

```python
if character_is_letter and ord(character) > 0x024F:
    return confusable
```

This is not a valid confusable-character test and creates false positives for legitimate non-Latin identifiers.

Reuse the repository’s existing Unicode/script/confusable primitives where possible. Do not create a second incompatible confusable database.

### E2. Define separate finding categories

Cargo dependency inspection must distinguish at least:

1. **non-ASCII identifier** — informational unless policy says otherwise;
2. **mixed-script identifier** — warning when multiple relevant scripts appear in one dependency name;
3. **confusable collision** — warning or error when two dependency names normalize or skeletonize to a deceptive collision;
4. **suspicious punctuation/shape** — existing lexical rules such as repeated separators;
5. **renamed dependency** — ordinary Cargo aliasing, not intrinsically suspicious.

Use stable codes, for example:

```text
CARGO_NON_ASCII_DEPENDENCY_NAME
CARGO_MIXED_SCRIPT_DEPENDENCY_NAME
CARGO_CONFUSABLE_DEPENDENCY_COLLISION
CARGO_SUSPICIOUS_DEPENDENCY_NAME
```

Exact names may differ, but categories must remain semantically distinct.

### E3. Required fixtures

Add fixtures and assertions for:

- a legitimate all-Cyrillic identifier;
- a legitimate all-Greek identifier;
- a mixed Latin/Cyrillic lookalike;
- two names that collide under the repository’s confusable skeleton logic;
- uppercase ASCII crate names;
- hyphenated and underscored names;
- a renamed dependency using `package =`;
- target-specific dependencies;
- workspace dependencies.

The test must assert finding codes, not only human-readable messages.

## 9. Workstream F — Release 1 semantic documentation and parity audit

### F1. Audit the caret/XOR contract

Search source, architecture documents, public documentation, generated documentation, examples, and changelogs for statements about:

- `^`;
- exponentiation;
- XOR;
- `xor`;
- `bitxor`;
- unit caret shorthand.

All documentation must agree on this contract:

- direct `evaluate()` uses Python AST semantics, so `^` is bitwise XOR;
- `evaluate_raw()`, CLI, and calculator normalization rewrite calculator caret to exponentiation;
- word-form XOR remains bitwise XOR through the calculator pipeline;
- malformed caret sequences are rejected;
- unit power normalization remains compatible with calculator caret preprocessing.

Correct any inaccurate statement about whether word-form XOR is transformed into a token or function call. Documentation should describe observable behavior unless an internal detail is stable and verified.

### F2. Verify package/single-file equivalence

For both package and generated single-file modes, assert at least:

```text
2 + 3 ^ 2
2 * 3 ^ 2
2 ^ 3 ^ 2
-2 ^ 2
(-2) ^ 2
5 xor 3
5 bitxor 3
5 m % 2 m
1 m % 30 cm
7 m // 2 m
5 m % 2 s  # expected rejection
```

Direct `evaluate()` tests must separately assert Python XOR behavior.

### F3. Preserve resource bounds

Caret rewriting and unit-operation paths must retain:

- maximum expression length enforcement;
- AST depth/node limits;
- exponent/result limits;
- no unbounded regex backtracking;
- useful error locations where available.

## 10. Workstream G — Inspection contract regression audit

### G1. Structured finding invariants

For every inspection tool returning findings, assert:

- every finding is a mapping;
- `code`, `severity`, and `message` are present;
- severity is one of `error`, `warning`, or `info`;
- line and column are positive integers when present;
- findings are capped by the documented maximum;
- results are JSON serializable;
- parse failure produces at least one error finding;
- successful empty input behavior is explicitly defined.

### G2. Public schema parity

Ensure MCP output schemas, TypedDict definitions, architecture documentation, and runtime output agree for:

- `PyprojectInspectResult`;
- `RequirementsInspectResult`;
- `CargoInspectResult`;
- common finding fields.

Schema lint tests must include the new or changed finding codes and fields where schemas enumerate them.

### G3. Regression fixtures

Re-run every ecosystem fixture and add a compact expected-result manifest or parameterized assertion table so future tests do not rely only on broad invariant checks.

At minimum, assert the corrected fields that motivated Release 3:

- build backend;
- build requirements;
- nested tool sections;
- TOML line and column;
- valid extras/specifiers;
- requirement and constraint includes;
- index and hash options;
- virtual Cargo workspaces;
- structured Cargo findings.

## 11. Workstream H — Reproducible verification evidence

### H1. Required local verification sequence

Run the repository’s authoritative checks in documented order. If no single command covers all checks, capture each command separately.

The evidence must include at least:

```bash
ruff check .
black --check .
python build_single.py
python eggcalc.py "5+3"
pytest
mypy eggcalc
python scripts/smoke_release_surfaces.py
```

Use the project’s actual supported command wrappers where they differ, such as `make check` or `python -m pytest`.

### H2. Environment matrix

Record results for every Python version currently advertised and tested by the repository. Do not skip TOML-dependent failures without documenting that they remain part of the later runtime-compatibility roadmap.

The closure record must identify:

- operating system;
- Python version;
- exact commit SHA;
- command;
- pass/fail result;
- skipped-test count and reason;
- generated-file cleanliness after checks.

### H3. Release-surface smoke evidence

Verify independently:

- source checkout;
- editable install;
- wheel install in a clean environment;
- console script;
- `python -m eggcalc`;
- generated `eggcalc.py`;
- package MCP stdio mode;
- single-file MCP stdio mode.

No release surface may use stale generated code.

### H4. Repository cleanliness

After generation and tests:

```bash
git diff --exit-code
git status --short
```

must show no uncommitted generated or fixture drift.

### H5. Persist evidence

Add a concise closure/status document under `plans/` or the repository’s established evidence location recording the verification matrix and any justified residual limitations.

Do not mark this plan complete using commit-message claims alone.

## 12. Workstream I — Documentation and release claims

Update all relevant surfaces:

- `README.md`;
- `docs/mcp.md`;
- `architecture/mcp.md`;
- calculator API and operator documentation;
- inspection architecture documentation;
- `CHANGELOG.md` and any generated changelog mirror;
- `AGENTS.md` where implementation invariants are documented.

Required claims:

- stable MCP support includes `2025-11-25`;
- legacy `2024-11-05` behavior is described accurately;
- the draft `2026-07-28` protocol is not claimed as supported;
- the lifecycle requirements apply to stdio and explicit sessions;
- sessionless compatibility behavior is identified as legacy or deprecated;
- Cargo Unicode findings use the corrected terminology;
- calculator caret and word-form XOR behavior are consistent everywhere.

Generated documentation or inventories must be regenerated and checked into source control when required by repository policy.

## 13. Required test additions

The closure pass is not complete without automated coverage for all of the following.

### MCP revision tests

- initialize with `2024-11-05`;
- initialize with `2025-11-25`;
- unsupported revision fallback;
- missing protocol version;
- non-string protocol version;
- missing capabilities;
- non-object capabilities;
- missing clientInfo;
- missing client name or version;
- per-session metadata isolation;
- exact server capability declaration.

### MCP lifecycle and JSON-RPC tests

- explicit null ID rejection;
- absent ID notification behavior;
- malformed params use `-32602`;
- unknown request method uses `-32601`;
- unknown notification produces no response;
- duplicate initialize rejection;
- operation before `notifications/initialized` rejection;
- sessionless compatibility warning or explicit legacy helper;
- package and single-file transcript parity.

### Cargo Unicode-policy tests

- all-Latin ASCII;
- uppercase ASCII;
- all-Cyrillic;
- all-Greek;
- mixed Latin/Cyrillic;
- real confusable collision;
- ordinary renamed dependencies;
- stable finding code assertions.

### Calculator parity tests

- precedence and associativity cases across package, CLI, and single-file;
- direct API XOR distinction;
- word-form XOR;
- same-unit and cross-unit modulo;
- incompatible-unit rejection;
- malformed caret syntax;
- exact input-boundary cases.

### Inspection invariant tests

- corrected pyproject fields;
- valid requirements forms remain non-suspicious;
- finding structure and severity vocabulary;
- parse line/column presence;
- JSON serialization;
- maximum findings truncation.

## 14. Explicit acceptance criteria

The plan may be marked complete only when every criterion below is satisfied.

### Release 1 closure

- [ ] `evaluate()` treats `^` as bitwise XOR and has regression tests.
- [ ] `evaluate_raw()`, CLI, and generated single-file calculator syntax treat `^` as exponentiation with correct precedence and right associativity.
- [ ] Word-form XOR produces bitwise XOR through the normalized calculator path.
- [ ] Unit floor division and modulo behavior is identical between evaluator and `UnitValue` implementations.
- [ ] Same-unit and compatible cross-unit modulo preserve the divisor unit.
- [ ] Incompatible dimensions are rejected consistently.
- [ ] Package and single-file parity tests cover the full operator matrix.
- [ ] All public and architecture documentation states the same syntax contract.

### Release 2 closure

- [ ] `SUPPORTED_PROTOCOL_VERSIONS` includes `2025-11-25`.
- [ ] `LATEST_SUPPORTED_PROTOCOL_VERSION` resolves to `2025-11-25`.
- [ ] `2024-11-05` remains supported or is explicitly removed with a documented compatibility decision; silent accidental support is not acceptable.
- [ ] Initialization validates `protocolVersion`, `capabilities`, and `clientInfo` and returns `-32602` for malformed values.
- [ ] Negotiated revision, client metadata, and client capabilities are retained per session.
- [ ] Initialize responses advertise only implemented server capabilities.
- [ ] Stdio always begins uninitialized and requires the full handshake.
- [ ] Sessionless request handling is separated, deprecated, or otherwise made explicitly legacy.
- [ ] Notifications never receive responses.
- [ ] Explicit null request IDs are rejected.
- [ ] Error codes match JSON-RPC categories across all handlers.
- [ ] Package and single-file MCP transcripts pass for both supported protocol revisions.
- [ ] Documentation does not claim support for draft `2026-07-28` behavior.

### Release 3 closure

- [ ] `pyproject_inspect()` reports build backend, build requirements, nested tool sections, and parse locations correctly.
- [ ] Valid requirement extras, version specifiers, direct references, VCS references, markers, includes, hashes, and index options are not falsely flagged as suspicious.
- [ ] Cargo findings use the shared structured finding contract.
- [ ] Virtual workspaces do not receive missing-package false positives.
- [ ] Legitimate non-Latin identifiers are not automatically labeled confusable.
- [ ] Mixed-script and actual confusable collisions have distinct stable finding codes.
- [ ] Every inspection result and finding is JSON serializable.
- [ ] Fixture tests assert corrected field values and finding codes, not only parse success.

### Verification closure

- [ ] Ruff passes.
- [ ] Black check passes.
- [ ] Mypy passes under the repository’s declared configuration.
- [ ] Full pytest suite passes on every supported CI Python version, subject only to explicitly documented pre-existing skips.
- [ ] Single-file generation succeeds and leaves no diff.
- [ ] Release-surface smoke tests pass for source, editable, wheel, console, module, single-file, and MCP modes.
- [ ] GitHub CI or equivalent reproducible automation records a successful run for the closure commit.
- [ ] A closure/status document records commands, environments, commit SHA, test counts, skips, and residual limitations.
- [ ] Repository working tree is clean after the complete verification sequence.

## 15. Recommended implementation sequence

Implement this pass in the following order:

1. Add protocol revision constants and revision-aware initialize validation.
2. Add session-local client metadata and capability retention.
3. Separate or deprecate sessionless request handling.
4. Complete error-code and notification audit.
5. Replace Cargo Unicode/confusable heuristic and add stable finding codes.
6. Audit calculator and inspection documentation/contracts.
7. Add package/single-file transcript and operator parity tests.
8. Run the complete verification matrix and fix only failures attributable to this closure scope.
9. Update changelogs and architecture documentation.
10. Commit the closure evidence/status record last.

Recommended commit boundaries:

1. `feat(mcp): support stable 2025-11-25 initialization`
2. `refactor(mcp): make session lifecycle compatibility explicit`
3. `fix(mcp): complete error and notification conformance`
4. `fix(cargo): distinguish unicode and confusable dependency findings`
5. `test: add releases 1-3 closure parity coverage`
6. `docs: align calculator mcp and inspection contracts`
7. `docs(plans): record releases 1-3 closure evidence`

## 16. Handoff notes

The implementation agent should begin by reading the three release plans, current MCP server/session code, existing schema-lint tests, `tests/test_mcp_stdio_smoke.py`, calculator operator tests, Cargo inspection code, and Unicode/confusable primitives.

Prefer small, reviewable corrections over generalized frameworks. The closure pass is successful when the repository can support its existing claims with exact tests and reproducible evidence—not when additional functionality has been added.
