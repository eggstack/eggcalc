# eggcalc

[![PyPI](https://img.shields.io/pypi/v/eggcalc)](https://pypi.org/project/eggcalc/)
[![Python](https://img.shields.io/pypi/pyversions/eggcalc)](https://pypi.org/project/eggcalc/)
[![License](https://img.shields.io/pypi/l/eggcalc)](https://github.com/eggstack/eggcalc/blob/main/LICENSE)
[![CI](https://github.com/eggstack/eggcalc/actions/workflows/ci.yml/badge.svg)](https://github.com/eggstack/eggcalc/actions/workflows/ci.yml)
[![PyPI Downloads](https://static.pepy.tech/personalized-badge/eggcalc?period=total&units=INTERNATIONAL_SYSTEM&left_color=BLACK&right_color=GREEN&left_text=downloads)](https://pepy.tech/projects/eggcalc)

CLI calculator accepting natural language and unit conversion. Standard library only.

Install with `pip install eggcalc` and run it like `calc 2 meters plus 2ft`. It is spacing-tolerant and normalizes operator-adjacent spacing before parsing, including unit forms like `30 km / h in mph`, `5 in in cm`, and spaced unit products like `5 N m` or `5 m s`.

Written in pure Python with no external dependencies, it can be used as a CLI tool, a Python library, or an MCP server for AI agents.

## Features

- **Natural Language Input**: `"five plus three times two"` → `11`
- **Unit Conversions**: `"30m + 100ft"` → `60.48 m`
- **Complex Numbers**: `"sqrt(-1)"` → `1j`
- **Safe Evaluation**: AST-based parsing, no `eval()`, blocks dangerous operations
- **MCP Server**: deterministic text, JSON, validation, math, path, manifest, patch, repo, network, encoding, and temporal tools for AI agents
- **Pure Python**: Standard library only, no dependencies

## Requirements

- **Python 3.11 or higher** (3.10 is no longer supported)
- **Operating systems:** Linux, macOS, Windows
- All tools and features are fully available on every supported runtime — no reduced capability set
- Compatibility evidence: primary CI runs the full gate on Ubuntu / Python 3.11; a recurring compatibility workflow covers Windows / Python 3.11, macOS / Python 3.11, and Ubuntu / Python 3.14 (path-filtered on push/PR plus a weekly schedule)

## Installation

```bash
pip install eggcalc
```

Or from source:

```bash
git clone https://github.com/eggstack/eggcalc.git && cd eggcalc
pip install -e .
```

Or run directly without installing:

```bash
python -m eggcalc "five plus two"
```

## CLI Usage

```bash
calc "five plus two"                    # 7
calc "(twenty + five) * 3"              # 75
calc "30m + 100ft"                      # 60.48 m
calc "sin of 3.14159"                   # 2.653e-06
calc "5 times avogadro"                 # 3.011e+24
calc -e "5 + 3"                         # 8 (quiet mode)
calc -i                                 # Interactive REPL
calc --mcp                              # MCP server mode
```

### CLI Options

| Option | Description |
|--------|-------------|
| `-e`, `--expression` | Evaluate a single expression (quiet mode) |
| `-q`, `--quiet` | Suppress expression in output |
| `--json` | Output result as JSON |
| `--explain` | Show the normalization trace for the expression and exit without evaluating |
| `--commands` | List curated CLI text commands and exit |
| `-i`, `--interactive` | Start interactive REPL |
| `--mcp` | Run as MCP server |
| `--capabilities` | Show runtime capabilities as JSON and exit |

See [docs/cli.md](docs/cli.md) for the full option reference (including `--usage`, `--verbose`, `-s`/`--show`, `--mcp-profile`, and `--mcp-schema-detail`).

## Python API

```python
from eggcalc import evaluate_raw, evaluate

# Full pipeline (natural language, spaces, units)
result = evaluate_raw("five plus three")    # 8
result = evaluate_raw("30m + 100ft")        # 60.48 m

# Fast path (pre-normalized expressions only; skips the full pipeline)
result = evaluate("5+3")                     # 8
```

**Caret (`^`) semantics differ between the two paths:**
- `evaluate()` treats `^` as **bitwise XOR** (Python AST semantics).
- `evaluate_raw()` and CLI normalize `^` as **exponentiation** (rewritten to `**` before parsing). Use `xor`/`bitxor` word forms for bitwise XOR through the full pipeline.

See [docs/api.md](docs/api.md) for the full API reference including `EggCalcApp`, `evaluate_cached()`, `evaluate_async()`, `evaluate_with_timeout()`, `trace_normalization()`, custom constants/functions, and performance benchmarks.

To inspect how an expression is normalized without evaluating it:

```python
from eggcalc import trace_normalization

trace = trace_normalization("five plus three")
# trace["normalized"] == "5+3"; trace["steps"] lists material rewrites per stage
```

or from the CLI: `calc --explain "five plus three"` (add `--json` for machine-readable output).

Evaluator built-ins preserve their dimensional contracts only while their
canonical evaluator callables are active. Replacing a built-in name uses the
generic dimensionless custom-callable rules. Canonical `round()` accepts
`round(number)`, `round(number, ndigits)`, or the equivalent `ndigits=` form;
omitted precision returns an `int`, while explicit precision returns a
`float`. Timeout evaluation rejects added, deleted, or overridden callables
before starting a worker process.

## MCP Server

eggcalc runs as an MCP server exposing deterministic tools across 21 categories (math, text, json, validation, regex, list, path, identifier, shell, markdown, config, version, toml, cargo, unicode, manifest, patch, repo, network, encoding, temporal). All results are deterministic — same input always produces the same output.

**Protocol version:** Dual-era MCP over stdio — finalized `2026-07-28` stateless requests (per-request `params._meta` envelope, `server/discover` bootstrap, no handshake) plus legacy `2025-11-25` / `2024-11-05` handshake sessions (`initialize` before tools; pre-init tool requests are rejected). Successful `tools/call` results on both eras carry typed `structuredContent` (equal to the text envelope's `result`) alongside backward-compatible text; all tools advertise read-only/closed-world annotations and share one concise server instruction text. See [docs/mcp.md](docs/mcp.md) for protocol details and lifecycle requirements.

```bash
calc --mcp
```

**Programmatic multi-instance usage:** Each `McpServer` instance owns its own `McpServerConfig`, `ToolRegistry`, `ToolExecutor`, evaluator, and session set. Multiple servers in one process are fully isolated. See [docs/mcp.md](docs/mcp.md#programmatic-multi-instance-usage) for embedding examples.

**Agent exposure:** `agent_core` is an opt-in 10-tool experimental surface with deterministic specialist discovery via `ToolRegistry.search_tools()` plus `tools/list(names=[...])` — see [docs/mcp.md](docs/mcp.md#progressive-disclosure-for-agents). Held-out cross-model evaluation shows that its current selection quality is below the full compact baseline, and the corrective pass did not promote an expanded candidate without per-case rollout evidence. `full` remains the default and practical general-agent recommendation. Exposure costs and the evidence live in the [closure report](evals/mcp_tool_selection/reports/closure_2026_09_10.md) and [corrective reports](evals/mcp_tool_selection/reports/corrective_development_2026_09_10.md) (`agent_core/compact` ≈ 11.7 KB vs `full/full` ≈ 118.4 KB).

See [docs/tool_inventory.md](docs/tool_inventory.md) for the complete generated tool inventory. See [docs/mcp.md](docs/mcp.md) for protocol usage, configuration, profiles, schema detail, and selected tool examples.

### Runtime Capabilities

Query runtime capabilities (Python version, platform, feature detection, eggcalc version, supported protocol modes) from the CLI or Python API:

```bash
calc --capabilities          # JSON output
python -c "from eggcalc import detect_capabilities; print(detect_capabilities().to_json(indent=2))"
```

The MCP server's `initialize` response also includes a `runtime` key with capability information.

## Supported Operations

**Arithmetic**: `+`, `-`, `*`, `/`, `**` · **Bitwise**: `&`, `|`, `^`, `~`, `<<`, `>>` · **Bases**: `0x` hex, `0b` binary, `0o` octal · **Complex**: `3+4i`, `5j` · **Percentage**: `50%` = 0.5

**Functions**: trig (`sin`, `cos`, `tan`), hyperbolic, math (`sqrt`, `log`, `exp`), combinatorics (`perm`, `comb`, `gcd`, `lcm`), prime (`isprime`, `primefactors`), statistics (`mean`, `median`, `std`), random, memory registers, variables, and more. See [docs/functions.md](docs/functions.md).

**Units**: length, time, data, data_rate, mass, volume, pressure, energy, power, force, voltage, current, angle, speed, area, frequency, temperature. Supports metric prefixes and imperial units. See [docs/units.md](docs/units.md).

**Number words**: zero through quintillion, fractions (half, quarter, thousandth, etc.).

**Constants**: `pi`, `e`, `tau`, `i`, `avogadro`, `c`, `planck`, `boltzmann`, `gas constant`, and more.

## Custom Configuration

Create `eggcalc_config.py` to add custom constants, functions, and units:

```python
CUSTOM_CONSTANTS = {"myconst": 42}
CUSTOM_FUNCTIONS = {"mysquare": lambda x, y: x**2 + y**2}
CUSTOM_UNITS = {"m": {"nm": 1e-9}}
CUSTOM_ALIASES = {"meter": "m", "meters": "m"}
```

## Development

```bash
.venv/bin/python -m pytest tests/ -v     # Run tests
ruff check eggcalc tests                  # Lint
black eggcalc tests                       # Format
mypy eggcalc --ignore-missing-imports     # Type check
mypy --strict --follow-imports=silent --ignore-missing-imports tests/typing/consumer.py    # Strict consumer API check
make check                                # All checks (lint, format, typecheck, docs, test)
python build_single.py                    # Build single-file distribution
```

## Security

eggcalc uses AST-based parsing (no `eval()`) with built-in DoS protection:

| Limit | Default |
|-------|---------|
| `MAX_INPUT_LENGTH` | 10,000 characters |
| `MAX_NESTING_DEPTH` | 100 |
| `MAX_EXPONENT` | 10,000 |
| `MAX_FACTORIAL` | 1,000 |

The MCP server adds additional resource bounds: request/output byte limits, per-tool timeouts, bounded thread pools, and pre-bounded inputs for all 83 tools. See [docs/mcp.md](docs/mcp.md#resource-limits) and [docs/mcp_resource_limits.md](docs/mcp_resource_limits.md) for details.

`eggcalc_config.py` is Python code loaded from the current working directory — only run eggcalc in directories you trust. Library APIs do not load config by default; set `EGGCALC_LOAD_CONFIG=1` to enable. CLI loads config by default. Disable config loading with `EGGCALC_NO_CONFIG=1`.

## License

MIT License
