# Documentation Maintenance Skill

## Purpose
Guide agents on keeping documentation accurate and up-to-date across the codebase.

## Documentation Locations

| Location | Purpose | Update Trigger |
|----------|---------|----------------|
| `AGENTS.md` | Agent-facing conventions and quick reference | Any convention change |
| `README.md` | User-facing project overview and API reference | Feature/usage changes |
| `architecture/*.md` | Module-level developer docs (38 files) | Code changes to any module |
| `docs/*.md` | User documentation (MkDocs site) | Feature/usage/API changes |
| `.skills/*.md` | Agent task guides | Workflow or tooling changes |

## Verification Checklist

When updating code, always check if documentation needs updating:

1. **Line counts** — Update in `AGENTS.md` Module Map and `architecture/overview.md`
2. **Test count** — Update in `AGENTS.md`, `.skills/testing.md`, `.skills/architecture_review.md`
3. **Public API** — Check `architecture/api.md` and `docs/api.md` for new/changed exports
4. **Module structure** — Check `architecture/overview.md` dependency tree
5. **Function lists** — Check `architecture/evaluator.md` and `docs/functions.md`
6. **MCP tools** — Check `architecture/mcp.md` and `docs/mcp.md` for tool count/names
7. **Unit categories** — Check `architecture/units.md` and `docs/units.md`
8. **Constants** — Check `architecture/evaluator.md` and `docs/constants.md`
9. **Version** — Update in `eggcalc/_version.py` and `docs/installation.md`
10. **Profile counts** — Update tool counts per profile in `docs/mcp.md` and `architecture/mcp.md`

## Common Documentation Issues

### Stale Line Counts
Line counts drift as code evolves. Update these locations:
- `AGENTS.md` Module Map table
- `architecture/overview.md` (all module line counts and Deep Dive Index)
- Individual `architecture/<module>.md` file headers

### Stale Test Count
Run `pytest --co -q | tail -1` to get current count, then update:
- `.skills/testing.md` Current Test Count section
- `.skills/architecture_review.md` Note section

### TypedDict Changes
When modifying TypedDict classes in `exact/`:
1. Update `architecture/<module>.md` TypedDict definitions
2. Update `architecture/exact.md` if the type is cross-referenced
3. Check `AGENTS.md` TypedDict Field Conventions section

### MCP Tool Changes
When adding/removing MCP tools:
1. Update `architecture/mcp.md` TOOL_HANDLERS map
2. Update `docs/mcp.md` tool reference
3. Update `docs/tool_inventory.md` inventory table
4. Update tool count in `README.md` and `docs/index.md`
5. Run `tests/test_tool_inventory.py` to verify consistency

## Documentation Accuracy Rules

1. **Never cite line numbers for code that changes frequently** — use function/class names instead
2. **Always verify TypedDict fields against actual code** — fields are often renamed
3. **Check that example code actually works** — run snippets before documenting
4. **Keep performance numbers in one place** —prefer `docs/api.md` as source of truth
5. **Use `file:line` references only for stable landmarks** — class definitions, constants

## When to Prune Documentation

Remove or update documentation when:
- A function is removed (delete from all docs)
- A feature is deprecated (mark as deprecated, keep for one release)
- A section is no longer relevant (remove entirely)
- Line counts are off by >10% (update)
- Test count is stale (update)
