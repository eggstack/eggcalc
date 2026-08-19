# inspect_prompt.py — Prompt Injection Detection

560 lines. Deterministic prompt/input inspection for humans and agents.

## Overview

Surfaces red flags in text that may influence agents or humans unexpectedly: Unicode hidden characters, bidi controls, HTML comments, markdown link mismatches, ANSI escapes, terminal controls, base64 blobs, instruction phrases, long minified lines.

## Key Exports

```python
from eggcalc.exact.inspect_prompt import prompt_input_inspect
```

## Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `prompt_input_inspect(text, checks=None, phrase_patterns=None)` | `PromptInspectionResult` | Inspects text for red flags; returns findings with risk score and recommended next tool |

## Check Categories

| Check | Description |
|-------|-------------|
| `unicode_hidden` | Zero-width spaces, joiners, directional marks |
| `bidi` | Bidirectional control characters |
| `html_comments` | HTML comment blocks |
| `markdown_links` | Markdown link text/target mismatches |
| `ansi_escapes` | ANSI escape sequences |
| `terminal_controls` | Terminal control sequences |
| `base64_blobs` | Long base64-encoded strings |
| `instruction_phrases` | Phrases that attempt to override instructions |
| `long_minified_lines` | Extremely long lines (minified code) |

## Module Dependencies

- `functools`, `re`, `unicodedata`
- `.primitives` (`find_invisibles`)
