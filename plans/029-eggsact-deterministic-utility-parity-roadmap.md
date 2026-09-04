# Eggsact Deterministic Utility Parity Roadmap

Status: planned  
Repository: `eggstack/eggcalc`  
Baseline reviewed: `07e0d66c29bdc7a9ab6d5a41033b372b4cec1994`  
Date: 2026-09-04  
Upstream reference: `eggstack/eggsact` feature commit `879570ec7cdd962136670f4e4dc0aaeceb384625`, corrective commit `ae2be1d5bb57b9e5cb57588ca2a384b1a645531c`, cron semantics correction `330e7a6c26b5b7a11a8f2674b568bd286628b63f`  
Depends on: existing stdlib-only runtime, `build_single.py` manifest authority, current MCP schema/handler/profile authorities

## 1. Purpose

`eggsact` added six deterministic utility tools after the last eggcalc parity pass:

- `ip_inspect`
- `cidr_inspect`
- `codec_convert`
- `radix_convert`
- `datetime_convert`
- `cron_inspect`

This roadmap ports that bounded feature line into eggcalc without changing eggcalc's product boundary or dependency policy. The target is behavioral parity at the public utility/MCP contract, implemented natively with Python 3.11+ standard-library facilities.

This is not authorization to synchronize every feature now present in `eggsact`. Older or unrelated eggsact coding-agent, repository-analysis, diagnostics, distribution, or server features remain out of scope.

## 2. Non-negotiable constraints

The implementation must preserve all current eggcalc constraints:

- production runtime remains Python standard-library-only;
- no PyPI runtime dependency, vendored package, subprocess dependency, Rust extension, or optional capability package is added;
- the ordinary calculator, unit system, CLI, Python API, MCP lifecycle, current tools, current profiles, and protocol versions are not redesigned;
- the generated single-file `eggcalc.py` remains a first-class supported runtime surface;
- no network I/O, filesystem I/O, system clock lookup, local timezone lookup, or external timezone database is introduced by these utilities;
- behavior must be deterministic for identical inputs;
- inputs and outputs remain bounded by the existing MCP/resource model;
- existing default and coding-agent profiles must not gain these tools implicitly;
- new tools are exposed only through the `full` profile, matching eggsact's contextual exposure decision;
- implementation should add only the minimum new modules and shared helpers needed for the six tools.

Development/test dependencies already used by the repository may remain development-only. No new runtime dependency may be added to `pyproject.toml`.

## 3. Scope and expected repository effect

The implementation should add three small deterministic modules under `eggcalc/exact/`:

```text
eggcalc/exact/network.py
    ip_inspect()
    cidr_inspect()

eggcalc/exact/encoding.py
    codec_convert()
    radix_convert()

eggcalc/exact/temporal.py
    datetime_convert()
    cron_inspect()
    private fixed-offset/RFC3339/cron helpers
```

The six functions should be available through the exact utility surface and through MCP. They should not become top-level calculator built-ins, natural-language calculator functions, or new calculator CLI modes.

If no unrelated tool changes land first, the MCP inventory changes from 77 to 83 tools and from 18 to 21 categories by adding:

- `network`
- `encoding`
- `temporal`

The exact counts are an expected consequence, not a hard-coded acceptance condition; generated documentation must reflect the live registry after implementation.

## 4. Compatibility authority

The eggsact behavior after the September 3-4 corrective commits is the source contract for this feature line. Do not copy known pre-fix behavior.

Parity means:

- same accepted input forms for the six tools;
- same canonicalization rules where observable;
- same important output fields and value meanings;
- same deterministic rejection of malformed input;
- same bounded semantics for cron search and radix magnitude;
- same fixed-offset-only temporal model;
- same corrected Vixie/Cronie DOM/DOW star-syntax behavior.

Implementation-language-specific error wording does not need byte-for-byte identity unless eggcalc already has a machine-code or error-envelope convention that requires stable wording. Prefer eggcalc's existing error/result envelope conventions over imitating Rust internals.

## 5. Standard-library implementation decisions

### 5.1 Network

Use `ipaddress` for parsing, canonical address/network formatting, packed bytes, masks, and containment arithmetic.

Do not delegate the public `special_use` taxonomy to changing `ipaddress.is_private`/`is_global` classifications. Implement the eggsact special-use ranges explicitly so supported Python minor releases cannot change deterministic output because of IANA-table updates in the standard library.

### 5.2 Encoding and radix

Use `base64`/`binascii` only after explicit alphabet, padding, and length validation. Python's permissive Base64 helpers must not silently accept whitespace, mixed alphabets, misplaced padding, or noncanonical malformed inputs that eggsact rejects.

Use Python integer arithmetic for radix conversion, but preserve eggsact's checked `u128` magnitude contract (`0 <= magnitude <= 2**128 - 1`). Python's arbitrary precision is not permission to widen the public contract.

### 5.3 Datetime

Use a signed integer nanosecond count as the authoritative instant representation. Python `datetime` stores only microseconds and therefore cannot be the sole representation if RFC3339 nanosecond parity is required.

Use `datetime`, `date`, `time`, `timezone`, and `timedelta` for bounded calendar arithmetic. Parse and retain fractional seconds explicitly up to nine digits. Avoid float timestamps.

Support only:

- RFC3339 timestamps;
- signed Unix seconds;
- signed Unix milliseconds;
- signed Unix nanoseconds;
- `Z` or explicit `+HH:MM` / `-HH:MM` output offsets.

Do not add IANA names, `zoneinfo`, DST rules, locale parsing, `now`, or local-time inference.

### 5.4 Cron

Implement the small five-field parser directly in `exact/temporal.py`; do not add `croniter` or another scheduler dependency.

Supported fields:

```text
minute        0..59
hour          0..23
day-of-month  1..31
month         1..12 or JAN..DEC
day-of-week   0..7 or SUN..SAT, with 7 normalized to Sunday/0
```

Support lists, ranges, and positive steps. Reject aliases such as `@daily`, six-field forms, timezone prefixes, empty list items, wrapping ranges, and invalid steps.

Preserve the corrected star-syntax rule:

- if either DOM or DOW field starts with `*`, including `*/n`, require both parsed DOM and DOW predicates to match;
- otherwise allow either parsed DOM or DOW predicate to match;
- explicit full ranges/lists are not equivalent to star syntax for this rule.

Search must be strictly after the supplied RFC3339 reference instant, use its fixed offset for results, cap requested result count at 32, and cap calendar scanning at one 400-year Gregorian cycle (146,097 days).

## 6. Implementation sequence

### Phase 1 - network and encoding primitives

Plan: `plans/030-network-and-encoding-utility-parity.md`

Deliver:

- `exact/network.py`;
- `exact/encoding.py`;
- focused unit tests and eggsact-derived regression vectors;
- lazy exact exports as appropriate;
- no MCP registration yet unless it is convenient and does not make the phase partially visible.

Completion condition: all four utility functions have stable package-level behavior and no runtime dependency is introduced.

### Phase 2 - temporal and cron primitives

Plan: `plans/031-temporal-and-cron-utility-parity.md`

Deliver:

- `exact/temporal.py`;
- exact nanosecond/fixed-offset conversion;
- five-field cron parsing and bounded search;
- corrected DOM/DOW semantics from the latest eggsact implementation;
- focused edge/boundary tests.

Completion condition: both temporal functions are deterministic, nanosecond-safe, fixed-offset-only, and bounded.

### Phase 3 - MCP, single-file, docs, and parity closure

Plan: `plans/032-utility-parity-integration-and-closure.md`

Deliver:

- schemas/metadata/handlers/profile wiring for all six tools;
- `build_single.py` manifest/dependency updates;
- package/generated-single-file parity coverage;
- generated MCP inventory/docs refresh;
- architecture/index updates for the three new exact modules;
- canonical verification.

Completion condition: all six tools are usable from installed-package MCP and generated-single-file MCP with the same observable results.

## 7. Public contract summary

### `ip_inspect`

Input: `address: str`.

Return canonical address, family, packed bytes as lowercase hex, numeric value as decimal text, lexicographically stable explicit special-use tags, and optional IPv4-mapped metadata.

### `cidr_inspect`

Input: required `cidr: str`, optional `contains: str`.

Return canonical network CIDR, prefix/host bit counts, network/netmask/first/last addresses, IPv4 broadcast or `None` for IPv6, exact address count as decimal text, and optional same-family containment result.

### `codec_convert`

Input: `value`, `from`, `to`, with formats limited to `utf8`, `hex`, `base64`, `base64url`.

Return canonical converted text plus decoded byte length. Standard Base64 output is padded; Base64URL output is unpadded; hex output is lowercase.

### `radix_convert`

Input: signed-magnitude ASCII integer text, `from_base`, `to_base` in 2..36, optional `uppercase`.

Return canonical converted value, bases, uppercase flag, negative flag, and decimal magnitude string. Reject magnitude above `2**128 - 1`.

### `datetime_convert`

Input: text value, declared format (`rfc3339`, `unix_seconds`, `unix_milliseconds`, `unix_nanoseconds`), optional fixed `output_offset`.

Return selected-offset RFC3339, UTC RFC3339, floor/Euclidean Unix seconds and milliseconds as decimal strings, exact nanoseconds as decimal string, selected offset metadata, and calendar components.

### `cron_inspect`

Input: five-field expression, mandatory RFC3339 `after`, optional count 1..32 (default 5).

Return original and normalized expression, parsed value sets, fixed offset metadata, satisfiability, strictly later run timestamps, and returned count.

## 8. Testing strategy

Do not add a cross-repository runtime/test dependency on eggsact. Instead, transcribe a small static parity fixture set from the reviewed eggsact behavior and include the upstream commit IDs in comments or test documentation.

Required fixture classes include:

- IPv4/IPv6 canonical forms and invalid addresses;
- RFC1918, documentation, shared, loopback, link-local, multicast, unspecified boundaries;
- true `::ffff:0:0/96` IPv4-mapped IPv6 versus visually similar non-mapped addresses;
- CIDR `/0`, host routes, network normalization, same-family containment, cross-family rejection;
- strict hex, standard Base64, Base64URL, padded/unpadded input, malformed padding, mixed alphabets, invalid UTF-8 decode;
- radix bases 2/10/16/36, signed values, negative zero, `2**128 - 1`, overflow, invalid digit/base combinations;
- epoch, positive/negative timestamps, `-1ns`, nine-digit RFC3339 fractions, offset conversion, invalid offsets, calendar boundaries;
- cron names, lists, ranges, steps, Sunday 0/7, impossible calendar dates, strict-after behavior, count bounds, 400-year search cap, and all corrected DOM/DOW star-syntax cases.

Where practical, test both direct exact functions and MCP envelopes without duplicating the entire fixture matrix at both layers.

## 9. Verification and closure

At the end of Plan 032, run the repository's canonical gates:

```bash
make check
make package-check
python3 build_single.py --validate
```

Also run focused new-tool tests separately during development so failures are easy to localize.

Closure requires:

- zero runtime dependency additions;
- all six exact implementations present and deterministic;
- all six MCP tools registered only where intended;
- package and single-file behavior equivalent for representative success/error cases;
- generated docs match registry truth;
- no existing tool/profile/calculator behavior unintentionally changes;
- no named-timezone, external-clock, network, or filesystem behavior is introduced;
- no unfinished compatibility shim or duplicate implementation authority remains.

## 10. Explicit non-goals

Do not use this roadmap to add:

- general IP geolocation, DNS, ASN, WHOIS, socket probing, or network access;
- cryptographic codecs, compression formats, arbitrary byte-file conversion, or streaming APIs;
- arbitrary-precision radix behavior beyond the eggsact contract;
- natural-language date parsing;
- timezone database support or DST scheduling;
- cron seconds/year fields, macros, Quartz syntax, `L`, `W`, `#`, or timezone prefixes;
- scheduler execution or background jobs;
- CLI command proliferation;
- broader eggsact feature synchronization;
- new CI matrices, benchmark gates, evidence registries, or release automation.

The intended end state is six small deterministic utilities, native to eggcalc's existing exact/MCP architecture, with no expansion beyond the reviewed eggsact feature line.
