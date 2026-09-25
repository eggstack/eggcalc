# Interim Planning Archive

This directory retains completed, superseded, rejected, or abandoned interim planning for traceability. Adapted from `codegg/plans/archive/README.md`.

The archive is not an active work queue. Agents MUST use `plans/registry.md` and current subsystem roadmaps to identify executable work.

## What belongs here

- completed milestone implementation plans after closure;
- superseded subsystem roadmaps;
- corrective plans whose closure is complete;
- rejected interim proposals worth retaining for historical context;
- status documents no longer needed in active directories;
- `legacy/` — the pre-adoption flat `plans/*.md` files (001–043 plus dated/phase files), moved verbatim with `git mv` to preserve history.

## What does not belong here

- canonical long-term specification, terminology, roadmap, or planning governance;
- accepted ADRs;
- active subsystem roadmaps;
- ready or active implementation plans;
- unresolved closure records.

## Archive layout

Preserve the original planning category and subsystem where practical:

```text
archive/
    legacy/<original-flat-filename>.md
    subsystems/<subsystem>-roadmap.md
    implementation/<subsystem>/NNN-short-title.md
    closure/<subsystem>/NNN-status.md
```

When moving a document into the archive:

1. update inbound links from `plans/registry.md` and the current subsystem roadmap;
2. add a short archival note to the document stating its final status and replacement, if any;
3. preserve Git history through a move rather than recreating unrelated content where possible;
4. do not rewrite historical conclusions to match later implementation;
5. ensure active documents link to the replacement or later milestone.

Archived plans may be useful evidence, but they are not authoritative over current canonical documents, accepted ADRs, active subsystem roadmaps, or current repository behavior.

## Legacy note

The `legacy/` files predate `plans/000-long-term-specification.md`, `plans/001-terminology-and-domain-model.md`, `plans/002-long-term-roadmap.md`, and `plans/003-planning-process.md`. They use older status headers, flat numbering, and date-encoded names. Do not retrofit them to the new templates; read them as historical evidence only.
