# MCP Tool Inventory

Canonical reference for all MCP tools exposed by `eggcalc.mcp.server.TOOL_HANDLERS`.

**Total: 77 tools**

> **Auto-generated** -- do not edit manually.
> Run `python scripts/generate_mcp_docs.py` to regenerate.

## Inventory Table

| # | Tool Name | Category | Tier | Implemented | README | docs/mcp.md | Tests | Notes |
|---|-----------|----------|------|-------------|--------|-------------|-------|-------|
| 1 | `argv_compare` | shell | 2 | yes | no | yes | yes | Compare two command strings or argv lists by parsed argv tokens rather than r... |
| 2 | `canonicalize_text` | unicode | 2 | yes | no | yes | yes | Apply a named text canonicalization profile. |
| 3 | `cargo_toml_inspect` | cargo | 3 | yes | no | yes | yes | Inspect Cargo. |
| 4 | `code_fence_extract` | markdown | 2 | yes | no | yes | yes | Extract fenced code blocks from Markdown with exact line ranges, optional lan... |
| 5 | `command_preflight` | shell | 1 | yes | no | yes | yes | Composite: analyze a command before user approval or execution. |
| 6 | `config_preflight` | config | 1 | yes | no | yes | yes | Composite: validate generated config text. |
| 7 | `constant_lookup` | math | 2 | yes | no | yes | yes | Look up physical constant values and symbols (Avogadro, Planck, speed of ligh... |
| 8 | `diff_file_headers` | patch | 2 | yes | no | no | yes | Extract metadata from diff file headers: diff --git line, index hash, mode ch... |
| 9 | `diff_hunk_ranges` | patch | 2 | yes | no | no | yes | Extract hunk ranges per file with line count classification (added/deleted/co... |
| 10 | `diff_touched_paths` | patch | 2 | yes | no | no | yes | Classify files in a unified diff as added, deleted, renamed, or modified. |
| 11 | `dotenv_validate` | config | 2 | yes | no | yes | yes | Validate . |
| 12 | `edit_preflight` | patch | 1 | yes | no | yes | yes | Composite: validate a proposed edit before applying it. |
| 13 | `escape_text` | text | 1 | yes | no | yes | yes | Escape text for various output formats. |
| 14 | `glob_match` | path | 1 | yes | no | yes | yes | Match a glob pattern against a path with explicit semantics: * matches within... |
| 15 | `go_mod_inspect` | manifest | 2 | yes | no | no | yes | Inspect go. |
| 16 | `identifier_analyze` | identifier | 3 | yes | no | yes | yes | Classify and validate identifier naming conventions across languages. |
| 17 | `identifier_inspect` | identifier | 1 | yes | no | yes | yes | Inspect identifiers for validity and collisions. |
| 18 | `identifier_table_inspect` | identifier | 3 | yes | no | yes | yes | Inspect a table of identifiers for casefold collisions, normalization collisi... |
| 19 | `ini_validate` | config | 2 | yes | no | yes | yes | Validate simple INI-style configuration files. |
| 20 | `json_canonicalize` | json | 1 | yes | no | yes | yes | Canonicalize JSON with deterministic formatting, key ordering, duplicate key ... |
| 21 | `json_compare` | json | 1 | yes | no | yes | yes | Compare two JSON documents semantically, ignoring formatting and key order. |
| 22 | `json_extract` | json | 2 | yes | no | yes | yes | Extract a value from JSON using RFC 6901 JSON Pointer (e. |
| 23 | `json_query` | json | 1 | yes | no | yes | yes | Extract a value from JSON using RFC 6901 JSON Pointer. |
| 24 | `json_shape` | json | 3 | yes | no | yes | yes | Analyze the structure of a JSON document without returning values. |
| 25 | `line_range_compare` | text | 2 | yes | no | yes | yes | Compare a line range from two text inputs with exact, trailing-whitespace-ign... |
| 26 | `line_range_extract` | text | 1 | yes | no | yes | yes | Extract exact line ranges from text and return stable offsets, byte positions... |
| 27 | `list_compare` | list | 2 | yes | no | yes | yes | Compare two lists with explicit modes: ordered ( LCS-based alignment), set (p... |
| 28 | `list_dedupe` | list | 1 | yes | no | yes | yes | Remove duplicates from a list while preserving order. |
| 29 | `list_sort` | list | 1 | yes | no | yes | yes | Sort a list of strings with Unicode normalization and casefold support. |
| 30 | `llm_json_output_check` | text | 2 | yes | no | no | yes | Detect and diagnose common LLM JSON output issues: fenced code blocks, leadin... |
| 31 | `lockfile_summary` | manifest | 2 | yes | no | no | yes | Shallow lockfile summary: detect kind (npm/pnpm/yarn/poetry/uv/cargo/go), app... |
| 32 | `markdown_link_check_lexical` | text | 2 | yes | no | no | yes | Lexical markdown link validation (no network). |
| 33 | `markdown_structure` | markdown | 2 | yes | no | yes | yes | Parse Markdown structure with a deterministic line scanner: headings (level, ... |
| 34 | `math_eval` | math | 0 | yes | no | yes | yes | Evaluate arithmetic, unit conversions, constants, and scientific expressions ... |
| 35 | `package_json_inspect` | manifest | 2 | yes | no | no | yes | Inspect package. |
| 36 | `patch_apply_check` | patch | 2 | yes | no | yes | yes | Validate and simulate a unified diff against provided in-memory files/text wi... |
| 37 | `patch_conflict_markers_inspect` | patch | 2 | yes | no | no | yes | Detect and analyze conflict markers (<<<<<<<, =======, >>>>>>>) in text. |
| 38 | `patch_summary` | patch | 2 | yes | no | yes | yes | Summarize a unified diff without applying it. |
| 39 | `path_analyze` | path | 2 | yes | no | yes | yes | Analyze path components, extensions, hidden status, and traversal without fil... |
| 40 | `path_compare` | path | 2 | yes | no | yes | yes | Compare two paths under explicit normalization rules: separator normalization... |
| 41 | `path_normalize` | path | 0 | yes | no | yes | yes | Normalize a path using posixpath or ntpath semantics. |
| 42 | `path_scope_check` | path | 2 | yes | no | yes | yes | Determine whether a target path remains lexically inside a declared root. |
| 43 | `prompt_input_inspect` | text | 2 | yes | no | yes | yes | Deterministically inspect text for red flags that may influence agents or hum... |
| 44 | `pyproject_inspect` | manifest | 2 | yes | no | no | yes | Inspect pyproject. |
| 45 | `regex_finditer` | regex | 1 | yes | no | yes | yes | Find all regex matches in text with positions, line/column info, and capture ... |
| 46 | `regex_safety_check` | regex | 1 | yes | no | yes | yes | Heuristic check for potential catastrophic backtracking risks in regex patterns. |
| 47 | `repo_file_inventory` | repo | 2 | yes | no | no | yes | Analyze file inventory for repo structure signals (no filesystem access). |
| 48 | `requirements_inspect` | manifest | 2 | yes | no | no | yes | Inspect requirements. |
| 49 | `shell_quote_join` | shell | 2 | yes | no | yes | yes | Safely quote a list of argv tokens into a POSIX-like shell string. |
| 50 | `shell_split` | shell | 2 | yes | no | yes | yes | Parse a shell-like command string into argv tokens and report risky lexical f... |
| 51 | `structured_data_compare` | json | 2 | yes | no | yes | yes | Composite: compare structured config/data output. |
| 52 | `text_count` | text | 0 | yes | no | yes | yes | Count exact characters or produce a character frequency table with codepoint ... |
| 53 | `text_diff_explain` | text | 1 | yes | no | yes | yes | Explain why two strings differ, including spans, codepoints, Unicode names, n... |
| 54 | `text_equal` | text | 0 | yes | no | yes | yes | Compare two strings under raw, Unicode-normalized, casefolded, or trimmed mod... |
| 55 | `text_fingerprint` | text | 0 | yes | no | yes | yes | Compute a deterministic SHA-256 fingerprint of text with canonicalization opt... |
| 56 | `text_hash` | text | 2 | yes | no | yes | yes | Compute cryptographic hashes of text for identity checking. |
| 57 | `text_inspect` | text | 1 | yes | no | yes | yes | Inspect a string for hidden characters, Unicode confusables, mixed scripts, n... |
| 58 | `text_measure` | text | 0 | yes | no | yes | yes | Measure exact text properties: UTF-8 byte length, codepoint count, words, lin... |
| 59 | `text_position` | text | 2 | yes | no | yes | yes | Convert between byte offsets, codepoint indices, line/column positions, and U... |
| 60 | `text_replace_check` | text | 1 | yes | no | yes | yes | Check whether a text replacement would apply cleanly before an agent attempts... |
| 61 | `text_security_inspect` | text | 1 | yes | no | yes | yes | Composite security-oriented text hygiene pass. |
| 62 | `text_transform` | text | 2 | yes | no | yes | yes | Apply deterministic text transformations: Unicode normalization (NFC/NFD/NFKC... |
| 63 | `text_truncate` | text | 3 | yes | no | yes | yes | Truncate a string to a specified number of grapheme clusters (user-perceived ... |
| 64 | `text_window` | text | 1 | yes | no | yes | yes | Get a window around a position in text with context lines. |
| 65 | `toml_shape` | toml | 2 | yes | no | yes | yes | Analyze the structure of a TOML document: top-level keys, tables, and nesting... |
| 66 | `unescape_text` | text | 1 | yes | no | yes | yes | Unescape text from various formats. |
| 67 | `unicode_policy_check` | unicode | 2 | yes | no | yes | yes | Apply a named deterministic Unicode safety policy to input text. |
| 68 | `unified_diff_validate` | patch | 2 | yes | no | no | yes | Validate the structural integrity of a unified diff. |
| 69 | `unit_convert` | math | 2 | yes | no | yes | yes | Convert a numeric value from one unit to another using pre-defined conversion... |
| 70 | `unit_info` | math | 2 | yes | no | yes | yes | Get information about a unit including its canonical form and category. |
| 71 | `validate_brackets` | validation | 1 | yes | no | yes | yes | Check whether delimiters are structurally balanced and report unmatched delim... |
| 72 | `validate_json` | validation | 0 | yes | no | yes | yes | Validate JSON and report precise parse errors or top-level structure informat... |
| 73 | `validate_regex` | regex | 1 | yes | no | yes | yes | Test a Python regular expression against sample strings and report match/full... |
| 74 | `validate_schema_light` | validation | 3 | yes | no | yes | yes | Validate JSON against a simple schema format with type, required, enum, patte... |
| 75 | `validate_toml` | validation | 1 | yes | no | yes | yes | Validate TOML configuration files (Cargo. |
| 76 | `version_compare` | version | 2 | yes | no | yes | yes | Compare two version strings with explicit scheme. |
| 77 | `version_constraint_check` | version | 3 | yes | no | yes | yes | Check whether a version satisfies a constraint under a declared versioning sc... |

## Legend

- **Tier 0**: Ultra-common, small-schema tools - always available
- **Tier 1**: Default coding-agent sanity tools - low context, recommended default
- **Tier 2**: Heavier analysis tools - moderate context, opt-in for text/unicode/config work
- **Tier 3**: Domain-specific tools - more context, opt-in for specialized workflows

## Summary Statistics

| Field | Count |
|-------|------:|
| Total tools | 77 |
| Documented in README | 0 |
| Documented in docs/mcp.md | 64 |
| Missing from docs/mcp.md | 13 |
| Have tests | 77 |
| Missing tests | 0 |

## Category Breakdown

| Category | Tools |
|----------|-------|
| cargo | `cargo_toml_inspect` |
| config | `config_preflight`, `dotenv_validate`, `ini_validate` |
| identifier | `identifier_analyze`, `identifier_inspect`, `identifier_table_inspect` |
| json | `json_canonicalize`, `json_compare`, `json_extract`, `json_query`, `json_shape`, `structured_data_compare` |
| list | `list_compare`, `list_dedupe`, `list_sort` |
| manifest | `go_mod_inspect`, `lockfile_summary`, `package_json_inspect`, `pyproject_inspect`, `requirements_inspect` |
| markdown | `code_fence_extract`, `markdown_structure` |
| math | `constant_lookup`, `math_eval`, `unit_convert`, `unit_info` |
| patch | `diff_file_headers`, `diff_hunk_ranges`, `diff_touched_paths`, `edit_preflight`, `patch_apply_check`, `patch_conflict_markers_inspect`, `patch_summary`, `unified_diff_validate` |
| path | `glob_match`, `path_analyze`, `path_compare`, `path_normalize`, `path_scope_check` |
| regex | `regex_finditer`, `regex_safety_check`, `validate_regex` |
| repo | `repo_file_inventory` |
| shell | `argv_compare`, `command_preflight`, `shell_quote_join`, `shell_split` |
| text | `escape_text`, `line_range_compare`, `line_range_extract`, `llm_json_output_check`, `markdown_link_check_lexical`, `prompt_input_inspect`, `text_count`, `text_diff_explain`, `text_equal`, `text_fingerprint`, `text_hash`, `text_inspect`, `text_measure`, `text_position`, `text_replace_check`, `text_security_inspect`, `text_transform`, `text_truncate`, `text_window`, `unescape_text` |
| toml | `toml_shape` |
| unicode | `canonicalize_text`, `unicode_policy_check` |
| validation | `validate_brackets`, `validate_json`, `validate_schema_light`, `validate_toml` |
| version | `version_compare`, `version_constraint_check` |

## Profile Membership

### full (77 tools)

| Category | Tools |
|----------|-------|
| cargo | `cargo_toml_inspect` |
| config | `config_preflight`, `dotenv_validate`, `ini_validate` |
| identifier | `identifier_analyze`, `identifier_inspect`, `identifier_table_inspect` |
| json | `json_canonicalize`, `json_compare`, `json_extract`, `json_query`, `json_shape`, `structured_data_compare` |
| list | `list_compare`, `list_dedupe`, `list_sort` |
| manifest | `go_mod_inspect`, `lockfile_summary`, `package_json_inspect`, `pyproject_inspect`, `requirements_inspect` |
| markdown | `code_fence_extract`, `markdown_structure` |
| math | `constant_lookup`, `math_eval`, `unit_convert`, `unit_info` |
| patch | `diff_file_headers`, `diff_hunk_ranges`, `diff_touched_paths`, `edit_preflight`, `patch_apply_check`, `patch_conflict_markers_inspect`, `patch_summary`, `unified_diff_validate` |
| path | `glob_match`, `path_analyze`, `path_compare`, `path_normalize`, `path_scope_check` |
| regex | `regex_finditer`, `regex_safety_check`, `validate_regex` |
| repo | `repo_file_inventory` |
| shell | `argv_compare`, `command_preflight`, `shell_quote_join`, `shell_split` |
| text | `escape_text`, `line_range_compare`, `line_range_extract`, `llm_json_output_check`, `markdown_link_check_lexical`, `prompt_input_inspect`, `text_count`, `text_diff_explain`, `text_equal`, `text_fingerprint`, `text_hash`, `text_inspect`, `text_measure`, `text_position`, `text_replace_check`, `text_security_inspect`, `text_transform`, `text_truncate`, `text_window`, `unescape_text` |
| toml | `toml_shape` |
| unicode | `canonicalize_text`, `unicode_policy_check` |
| validation | `validate_brackets`, `validate_json`, `validate_schema_light`, `validate_toml` |
| version | `version_compare`, `version_constraint_check` |

### default (26 tools)

| Category | Tools |
|----------|-------|
| identifier | `identifier_inspect` |
| json | `json_canonicalize`, `json_compare` |
| list | `list_dedupe`, `list_sort` |
| math | `math_eval` |
| path | `glob_match`, `path_normalize` |
| regex | `regex_finditer`, `regex_safety_check`, `validate_regex` |
| text | `escape_text`, `line_range_extract`, `llm_json_output_check`, `text_count`, `text_diff_explain`, `text_equal`, `text_fingerprint`, `text_inspect`, `text_measure`, `text_replace_check`, `text_window`, `unescape_text` |
| validation | `validate_brackets`, `validate_json`, `validate_toml` |

### codegg_core_min (6 tools)

| Category | Tools |
|----------|-------|
| config | `config_preflight` |
| patch | `edit_preflight` |
| shell | `command_preflight` |
| text | `text_replace_check`, `text_security_inspect` |
| validation | `validate_json` |

### codegg_core (22 tools)

| Category | Tools |
|----------|-------|
| cargo | `cargo_toml_inspect` |
| config | `config_preflight` |
| identifier | `identifier_inspect` |
| json | `structured_data_compare` |
| manifest | `go_mod_inspect`, `lockfile_summary`, `package_json_inspect`, `pyproject_inspect`, `requirements_inspect` |
| patch | `edit_preflight` |
| path | `path_normalize` |
| shell | `command_preflight` |
| text | `llm_json_output_check`, `markdown_link_check_lexical`, `text_diff_explain`, `text_equal`, `text_fingerprint`, `text_inspect`, `text_replace_check`, `text_security_inspect` |
| validation | `validate_json`, `validate_toml` |

### codegg_preflight (10 tools)

| Category | Tools |
|----------|-------|
| config | `config_preflight` |
| patch | `edit_preflight`, `patch_apply_check` |
| path | `path_scope_check` |
| shell | `command_preflight`, `shell_split` |
| text | `llm_json_output_check`, `prompt_input_inspect`, `text_security_inspect` |
| unicode | `unicode_policy_check` |

### codegg_patch (12 tools)

| Category | Tools |
|----------|-------|
| patch | `diff_file_headers`, `diff_hunk_ranges`, `diff_touched_paths`, `edit_preflight`, `patch_apply_check`, `patch_conflict_markers_inspect`, `patch_summary`, `unified_diff_validate` |
| text | `line_range_compare`, `line_range_extract`, `text_diff_explain`, `text_replace_check` |

### codegg_config (17 tools)

| Category | Tools |
|----------|-------|
| config | `config_preflight`, `dotenv_validate`, `ini_validate` |
| json | `json_canonicalize`, `json_compare`, `json_extract`, `structured_data_compare` |
| manifest | `go_mod_inspect`, `lockfile_summary`, `package_json_inspect`, `pyproject_inspect`, `requirements_inspect` |
| toml | `toml_shape` |
| validation | `validate_json`, `validate_schema_light`, `validate_toml` |
| version | `version_compare` |

### codegg_unicode_security (8 tools)

| Category | Tools |
|----------|-------|
| identifier | `identifier_inspect` |
| text | `prompt_input_inspect`, `text_inspect`, `text_position`, `text_security_inspect`, `text_transform` |
| unicode | `canonicalize_text`, `unicode_policy_check` |

### codegg_shell (5 tools)

| Category | Tools |
|----------|-------|
| regex | `regex_safety_check` |
| shell | `argv_compare`, `command_preflight`, `shell_quote_join`, `shell_split` |

### codegg_repo_audit (18 tools)

| Category | Tools |
|----------|-------|
| cargo | `cargo_toml_inspect` |
| identifier | `identifier_table_inspect` |
| json | `json_shape` |
| manifest | `go_mod_inspect`, `lockfile_summary`, `package_json_inspect`, `pyproject_inspect`, `requirements_inspect` |
| markdown | `code_fence_extract`, `markdown_structure` |
| patch | `diff_file_headers`, `diff_hunk_ranges`, `diff_touched_paths`, `patch_conflict_markers_inspect`, `unified_diff_validate` |
| repo | `repo_file_inventory` |
| text | `markdown_link_check_lexical`, `text_fingerprint` |

### human_math (4 tools)

| Category | Tools |
|----------|-------|
| math | `constant_lookup`, `math_eval`, `unit_convert`, `unit_info` |

## Schema Detail Levels

| Level | Description |
|-------|-------------|
| `compact` | Description + tier + tags only (smallest) |
| `normal` | Adds input types, enums, constraints, output structure |
| `full` | Complete JSON Schema with all property descriptions |

## Source of Truth

The canonical tool list lives in `tests/fixtures/mcp_tool_registry_expected.json`.
The test at `tests/test_tool_inventory.py` enforces that `TOOL_HANDLERS` keys match this fixture.
