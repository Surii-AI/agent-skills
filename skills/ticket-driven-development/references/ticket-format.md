# Ticket format and normalization

Use this reference when parsing tickets, diagnosing graph errors, or preparing a bounded worker brief.

## Accepted local format

Accept one Markdown file per ticket. Preserve the source files; normalize them into JSON rather than rewriting them.

```markdown
# 02: Add passwordless sign-in

**What to build:** A returning user can request a one-time sign-in link and reach the existing authenticated home screen after using it.

**Blocked by:** 01: Establish session boundary

**Status:** ready-for-agent

**Risk:** medium

**Conflict domains:** authentication API; session lifecycle

## Acceptance criteria

- [ ] A valid link creates the same session shape as existing login.
- [ ] Expired and reused links fail without revealing account existence.
- [ ] Focused automated tests cover success, expiry, and replay.

## Constraints

Use the existing email delivery abstraction. Do not add another identity provider.

## Context pointers

- `specs/passwordless-sign-in.md`
- `docs/adr/0012-session-boundary.md`

## Out of scope

Account recovery and changing the primary email address.
```

The required content is the ticket identifier/title, outcome, an explicit blocker declaration (including `None`), and at least one acceptance checkbox. The parser accepts Matt Pocock’s compact local-ticket shape, where acceptance checkboxes immediately follow the status field, and the extended sectioned shape above.

Risk, conflict domains, constraints, context pointers, and out of scope are optional. Infer missing risk and conflict domains conservatively during preflight; do not modify the ticket solely to add inferred metadata.

## Completed statuses and repeated declarations

Completed statuses are exactly `done`, `complete`, `completed`, `implemented`, `integrated`, `closed`, and `shipped`. Anything else — including `partial` — leaves the ticket open work for scheduling. The parser reads status only from preamble fields: a `## section` that restates `**Status:**` is section content and never corrupts the ticket status, and duplicate preamble status declarations use the first component and warn.

A completed status in the source is a claim the controller must corroborate against the repository (workflow step 4) before treating the ticket as done. During a run, `run_state.py` treats a blocker that is `verified`, `integrated`, or `skipped` as satisfied; confirming the blocker's required checkpoint actually passed remains the controller's responsibility before dispatching a dependent.

## Normalize and validate

Run:

```bash
python3 scripts/index_tickets.py .scratch/<feature>/issues \
  --output <run-dir>/ticket-index.json
```

The command exits with status `2` for missing required fields, duplicate IDs, unresolved blocker declarations, missing blockers, dependency cycles, or a directory containing no ticket files at all; a layout that nests tickets in subdirectories is reported with their paths so the user can decide the correct directory. `valid: false` is a hard stop: report the errors and the named directory, and let the user correct the invocation — never locate a different ticket directory and continue.

`ready_frontier` reflects source statuses only at initial indexing. During a run, compute readiness from controller-owned `state.json`: a ticket is ready when it is not complete and every blocker is `verified`, `integrated` with its required checkpoint passed, or explicitly `skipped` by an approved ruling.

## Worker brief boundary

Include the entire current ticket. Add only:

| Context item | Rule |
|---|---|
| Specification | Pass precise section pointers or a prepared excerpt; include the whole file only when already small. |
| Dependency output | Pass commit IDs and concise interface notes, never implementation transcripts. |
| Other tickets | Include only a ticket whose public contract directly binds the current work. |
| Repository instructions | Include every instruction file scoped to the paths the worker may touch. |
| Code context | Let the worker inspect relevant code from its workspace; provide a code map only when discovery would be unusually expensive. |
| Code location | When preflight found a code-location tool, include the repository's locator rule so the worker queries it before crawling. |
| Prior conversation | Do not pass it. Persist durable decisions as rulings, ADRs, or run context. |

Tickets often cite specification artifacts inline — "§22", "ADR-9", "P12", a table row — without naming the document they belong to. Resolve those citations to concrete file paths (plus section anchors when the file is large) before dispatch: a worker that receives "§22" without knowing which document holds section 22 cannot verify its own contract and will guess. When a citation cannot be resolved to a file in the repository, treat it as missing context for the controller to clarify, not something for the worker to invent.

Target an initial package below about 20,000 tokens when the environment reports usage. Treat 40,000 as a warning: prepare a smaller excerpt, a code map, or split the ticket. If the ticket still requires broad unrelated exploration, stop with `NEEDS_SPLIT` rather than allowing unbounded context growth.
