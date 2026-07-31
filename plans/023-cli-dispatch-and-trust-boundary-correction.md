# CLI Dispatch and Trust-Boundary Correction

Status: implementation handoff  
Repository: `eggstack/eggcalc`  
Baseline reviewed: `8515579e9e64fcb49a3e5b46ac4f0c47e77d8ff1`  
Date: 2026-07-31  
Roadmap: `plans/022-correctness-simplification-and-footprint-roadmap.md`

## 1. Purpose

Correct the CLI mode-selection and trust-boundary defects identified in the repository review without changing the current feature set or adding new architecture.

The pass must ensure that:

- cwd-local configuration is executed only for calculator evaluation modes that require it;
- help, version, capabilities, MCP startup, and exact-text commands do not execute cwd-local configuration as a side effect of dispatch;
- recognized text-command failures are terminal for that command and do not fall through into calculator evaluation;
- legitimate command arguments are not rejected merely because they name existing files;
- constant aliases and compatibility flags are documented according to actual behavior;
- import-time warnings do not write to stderr during ordinary library import;
- documentation accurately describes hosted CI platforms.

This is a focused CLI and documentation correction. It is not a CLI redesign.

## 2. Governing constraints

The implementation must preserve:

- all current CLI options and command names unless a flag is proven to be entirely undocumented and unreachable;
- the current result-only output contract for successful calculator expressions;
- package, module, console-script, REPL, and generated single-file execution;
- current exact-text command functionality;
- current MCP startup syntax;
- current user-config functionality for calculator evaluation and REPL use;
- standard-library-only runtime;
- Python `>=3.11` support;
- required CI and manual release policy from Plans 020 and 021.

Do not:

- replace `argparse`;
- introduce a command framework;
- add a plugin system;
- make MCP load user config to preserve current accidental behavior;
- add a global command registry solely for this correction;
- add subprocess-based tests for every parser branch when direct tests are sufficient;
- add a new CI lane;
- change release behavior;
- remove exact tools or MCP tools;
- redesign configuration loading beyond the dispatch boundary required here.

## 3. Current failure modes

### 3.1 Configuration executes before the selected mode is known

`cli.main()` currently calls `maybe_load_cli_config()` before argument parsing and dispatch.

That ordering allows a cwd-local `eggcalc_config.py` to execute for invocations that do not need calculator configuration, including modes equivalent to:

```text
calc --help
calc --version
calc --capabilities
calc --mcp
```

It may also execute before an exact-text command is classified.

This contradicts the documented expectation that the MCP server does not load user configuration and creates a surprising code-execution boundary for informational commands.

### 3.2 Text-command result conflates “not handled” and “failed”

The current text-command helper returns an integer exit code. The caller interprets a nonzero result as a reason to continue into calculator evaluation.

This means a recognized command with invalid arguments can:

1. print command-specific usage or an error;
2. return nonzero;
3. be parsed again as a calculator expression;
4. print a second unrelated calculator error.

### 3.3 Filesystem-existence heuristic misidentifies shell glob expansion

The CLI attempts to detect unquoted `*` expansion by checking whether positional arguments name existing filesystem entries.

This is not a valid indicator of glob expansion. It can reject legitimate commands such as text counting or analysis against a file-like token that happens to exist in the current directory.

### 3.4 Constant aliases conflict with unit aliases

Name resolution gives unit aliases precedence over constants. Short aliases such as `c`, `h`, `k`, `g`, `G`, or `f` may therefore be shadowed or contextually ambiguous.

The current implementation emits an import-time stderr warning for collisions while documentation may still advertise a shadowed alias as directly usable.

Importing a library must not produce unsolicited stderr output.

### 3.5 Compatibility flags and CI claims are stale or misleading

Some flags such as `--quiet`, `--show`, or `--verbose` may be accepted for compatibility but do not match the behavior described in the README or help text. A `show_expression` value is computed or passed without affecting output.

The README also claims hosted CI coverage that does not match the current simplified workflows.

## 4. Target dispatch model

The implementation should use the existing `argparse` parser and existing command helpers, with one explicit dispatch sequence.

Recommended conceptual order:

```text
1. construct parser
2. parse argv
3. handle parser-owned informational exits
4. classify top-level mode
5. dispatch MCP without user config
6. dispatch capabilities/version/help without user config
7. dispatch exact-text commands without user config unless a specific command explicitly requires calculator config
8. load calculator user config only for expression evaluation or REPL
9. evaluate expression or enter REPL
```

The exact code structure may differ, but the trust boundary must be visible in `main()` or one small mode-classification helper.

Do not load configuration optimistically and attempt to undo it after dispatch.

## 5. Workstream A — defer configuration until calculator evaluation

### A1. Identify configuration-requiring modes

Treat the following as configuration-free:

- help output;
- version output;
- capabilities output;
- MCP startup;
- exact-text commands that operate only on their explicit arguments;
- parse errors generated by `argparse`;
- empty-command help or usage behavior, if the CLI currently chooses help rather than REPL.

Treat the following as configuration-eligible:

- direct calculator expression evaluation;
- REPL startup;
- any existing calculator-specific mode that intentionally uses registered constants, functions, variables, or custom configuration.

If one exact-text command currently depends on calculator configuration, document that exception and test it explicitly. Do not assume all exact tools require config.

### A2. Move the load point

Move `maybe_load_cli_config()` or its equivalent so it is called only after the mode is classified as calculator evaluation or REPL.

The call should occur exactly once per process invocation.

Do not duplicate configuration loading across multiple expression branches unless the helper is idempotent and one shared load point is genuinely impractical.

### A3. Preserve explicit config suppression

Keep existing environment-based config suppression such as `EGGCALC_NO_CONFIG` functional.

The suppression variable should remain useful for tests and release-surface smoke checks, but correct dispatch must not rely on it for MCP/help/version safety.

### A4. Regression tests

Use a temporary directory containing an `eggcalc_config.py` whose only action is observable and harmless, for example writing a sentinel file.

Verify that the sentinel is not created for:

```text
--help
--version
--capabilities
--mcp startup through a bounded handshake or startup probe
one representative exact-text command
```

Verify that the sentinel is created exactly once for:

```text
a calculator expression that uses configuration
REPL startup or a directly testable REPL config path
```

Prefer in-process tests when they can isolate module state safely. Use subprocesses for the executable trust-boundary cases where import and cwd behavior matter.

### A5. Acceptance criteria

- informational modes do not execute cwd config;
- MCP does not execute cwd config;
- representative exact-text dispatch does not execute cwd config;
- calculator evaluation still loads config;
- REPL still loads config;
- explicit config suppression still works;
- config is not loaded twice;
- no new configuration format or search path is introduced.

## 6. Workstream B — introduce an explicit text-command dispatch result

### B1. Required semantic states

The caller must distinguish exactly three states:

1. not a recognized text command;
2. recognized and completed successfully;
3. recognized and completed with an error.

A small private enum, frozen dataclass, or tuple is acceptable. Prefer the smallest readable representation.

Suitable examples include:

```python
class _CommandStatus(Enum):
    NOT_HANDLED = auto()
    SUCCESS = auto()
    ERROR = auto()
```

or:

```python
@dataclass(frozen=True)
class _CommandResult:
    handled: bool
    exit_code: int
```

Do not create a public command-dispatch framework.

### B2. Caller behavior

The top-level caller must:

- continue to calculator evaluation only for `NOT_HANDLED`;
- return zero for recognized success;
- return the command's nonzero exit code for recognized failure;
- avoid printing a second calculator error after a command-specific failure.

### B3. Command-helper behavior

Existing command helpers may continue returning integer exit codes internally. The classifier wrapper can translate them into the explicit result.

Do not rewrite every exact tool merely to adopt the new type.

### B4. Regression cases

Add focused tests for:

- one successful text command;
- one recognized text command with missing required arguments;
- one recognized text command with invalid input;
- one ordinary calculator expression that is not a text command.

For failure cases, assert that:

- the command-specific error or usage appears once;
- no calculator parse/evaluation error is appended;
- the process returns the command-specific nonzero status.

### B5. Acceptance criteria

- “not handled” is no longer encoded as the same value as “handled error”;
- recognized errors are terminal;
- ordinary math still reaches the evaluator;
- successful text commands keep current output;
- no public API change is required.

## 7. Workstream C — remove the false glob detector

### C1. Preferred correction

Remove the heuristic that treats existing filesystem entries as proof of shell glob expansion.

Shell expansion is performed by the shell before Python receives argv. The CLI cannot reliably reconstruct whether a list of arguments came from an unquoted glob.

A warning or special rejection is not required for correctness. Standard CLI quoting documentation is sufficient.

### C2. Narrow fallback only if a real contract depends on it

If an existing test or documented behavior requires a guard, replace it with a strictly bounded check that can only trigger when:

- the original token `*` is present in argv as a literal; or
- a command receives an impossible argument shape that is uniquely attributable to expansion.

Do not use `os.path.exists()`, `Path.exists()`, directory scans, suffix checks, or current-directory contents as a proxy for glob origin.

### C3. Tests

Add a regression using a temporary cwd containing a file such as `README.md` or `sample.txt`.

Invoke a representative text command whose argument equals that filename and verify it is not rejected by glob logic.

Retain any existing documented literal-asterisk behavior.

### C4. Acceptance criteria

- an existing path token is accepted as a normal argument;
- literal `*` behavior remains documented and testable;
- no filesystem scan is added;
- no shell-specific dependency or platform branch is introduced.

## 8. Workstream D — resolve constant/unit alias collisions without import noise

### D1. Preserve deterministic name precedence

Do not silently reverse global name precedence if that would change existing unit expressions.

The preferred compatibility rule is:

- unit aliases continue to resolve as units where currently required;
- long, unambiguous constant names remain directly available;
- shadowed short aliases are not advertised as universally available;
- an explicit constant lookup surface is documented where one already exists;
- if no explicit constant lookup exists, add only the smallest existing-pattern-compatible helper necessary, not a new expression language.

Before adding a helper, confirm whether `constant(...)`, a constants mapping, or long aliases already provide an unambiguous path.

### D2. Remove import-time stderr output

Replace import-time collision printing with one of:

- an internal validation assertion covered by tests;
- a debug-level logger that is silent by default;
- generated documentation metadata;
- a CLI diagnostic shown only when explicitly requested.

Ordinary `import eggcalc` and `import eggcalc.evaluator` must not write to stdout or stderr.

### D3. Documentation alignment

Update help and README examples so they do not claim that a shadowed alias such as `c` is always the speed of light in an expression context.

Prefer examples using unambiguous long names.

Document the resolution rule concisely. Do not add a large collision table to primary help output.

### D4. Tests

Verify:

- ordinary import has no stderr output;
- representative unit aliases retain current behavior;
- unambiguous constant names resolve correctly;
- the documented explicit constant path works;
- collision validation remains deterministic.

### D5. Acceptance criteria

- no import-time warning is printed;
- unit behavior is not broken;
- constant documentation is truthful;
- no public constant is deleted;
- no ambiguous alias is newly given context-sensitive magic.

## 9. Workstream E — align compatibility flags and documentation

### E1. Inventory accepted flags

Review parser definitions and actual output effects for:

```text
--quiet
--show
--verbose
```

and any related `show_expression` plumbing.

For each flag, choose one of two bounded outcomes:

1. implement the already-documented behavior with a small local change; or
2. document it as a compatibility no-op and remove dead internal plumbing.

Do not invent new verbose output or expression echoing that conflicts with the result-only CLI contract.

### E2. Preferred behavior

The result-only output contract is authoritative.

Therefore:

- `--quiet` may remain accepted as a compatibility no-op because successful output is already minimal;
- `--show` must not cause expression echoing unless existing documented consumers rely on it and tests define the exact output;
- `--verbose` should affect only existing diagnostics, not successful expression formatting;
- unused `show_expression` values should be removed if they have no observable effect.

### E3. CI documentation correction

Update README or contributor documentation that claims automatic Linux/macOS/Windows CI coverage.

The accurate statement should reflect:

- required CI: Ubuntu, Python 3.11;
- optional manual compatibility: Windows 3.11 and Ubuntu 3.14;
- local maintainer macOS development is not a hosted CI guarantee.

Do not add macOS CI merely to preserve a stale sentence.

### E4. Acceptance criteria

- help text and README match observable flag behavior;
- dead output-control plumbing is removed where safe;
- successful CLI output remains result-only;
- CI documentation matches workflow files;
- no workflow changes are required.

## 10. Files expected to change

Primary:

```text
eggcalc/cli.py
README.md
docs/installation.md or relevant CLI documentation
AGENTS.md
AGENTS.override.md
tests/test_clicalc.py
```

Possible, only if required for constant documentation or diagnostics:

```text
eggcalc/evaluator.py
eggcalc/__init__.py
tests/test_evaluator.py
tests/test_mcp_stdio_smoke.py
```

Do not touch MCP protocol implementation, unit arithmetic, exact-tool algorithms, workflows, release scripts, or packaging metadata in this phase.

## 11. Verification

Run focused tests first, then canonical checks.

Suggested focused sequence:

```text
python -m pytest tests/test_clicalc.py -q
python -m pytest tests/test_evaluator.py -q
python -m pytest tests/test_mcp_stdio_smoke.py -q
python build_single.py --validate
```

Final required verification:

```text
make check
make package-check
```

Do not add a new verification target or CI job.

## 12. Explicit negative tests

The implementation is incomplete unless tests prove the following do not occur:

1. `--help` creates the config sentinel.
2. `--version` creates the config sentinel.
3. `--capabilities` creates the config sentinel.
4. MCP startup creates the config sentinel.
5. a recognized text-command error is followed by a calculator error.
6. an existing filename is rejected as an inferred glob expansion.
7. importing eggcalc writes a constant/unit collision warning to stderr.
8. help advertises an alias or flag behavior that the implementation does not provide.

## 13. Final acceptance criteria

This plan is complete when:

- CLI mode is classified before user config loading;
- only calculator evaluation and REPL load cwd config;
- informational, MCP, and representative exact-text modes are config-free;
- text-command dispatch has explicit handled semantics;
- recognized command errors do not fall through;
- filesystem existence is not used as a glob detector;
- imports are silent;
- constant/unit alias precedence is documented accurately;
- compatibility flags match documentation;
- CI platform claims are accurate;
- package and single-file CLI behavior remain equivalent;
- runtime remains standard-library-only;
- `make check` and `make package-check` pass;
- no unrelated feature, framework, workflow, or release change is introduced.

After these conditions are met, stop. Do not use this plan to redesign argument parsing, configuration formats, exact-tool APIs, or the expression language.
