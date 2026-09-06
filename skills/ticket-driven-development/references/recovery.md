# Durable state and recovery

Use this reference when starting a run, resuming after interruption or context compaction, classifying stale workers, and cleaning workspaces.

## Run directory

Create a run-owned directory ignored by Git, for example `.scratch/<feature>/runs/<run-id>/`, containing:

```text
state.json
ledger.md
ticket-index.json
workspaces/
reports/
reviews/
diffs/
conflicts/
```

The controller is the only writer of `state.json` and `ledger.md`. Workers receive read-only pointers and write only their assigned report files inside the run directory.

Place the run directory in the main checkout's ignored path or outside the repository — never inside the integration worktree or a child workspace that teardown removes. Workspaces are disposable once integrated; the ledger, reports, and reviews are the audit record and must survive cleanup.

Initialize state after the integration worktree exists:

```bash
python scripts/run_state.py init \
  --index <run-dir>/ticket-index.json \
  --state <run-dir>/state.json \
  --ledger <run-dir>/ledger.md \
  --repo <repo> \
  --base <base-sha> \
  --integration-branch agent/<feature>/integration \
  --integration-worktree <integration-worktree> \
  --spec <spec-path>
```

Update a ticket at every durable boundary: dispatched, implemented, reviewed, repair requested, integrated, checkpoint passed, or failed. Use `scripts/run_state.py transition`; record assumptions or deliberately deferred findings with its `record` command.

`transition` enforces the terminal-status contract so state cannot lie: it derives `duration_ms` from the ticket's start/finish timestamps unless given an explicit value, archives a resolved `last_error` into `repair_history` when a ticket reaches `integrated`, `verified`, or `skipped`, and rejects `integrated` without a reachable commit (`--integrated-sha` or `--head-sha`). A ticket whose entire output is unversioned artifacts — docs, sign-off packages, reports — ends `verified` with its report path as evidence, never `integrated`.

## Resume protocol

Do not infer status from the conversation. On every resume:

1. Read `state.json`, `ledger.md`, and `ticket-index.json`.
2. Run `scripts/reconcile_run.py --state <run-dir>/state.json` without `--apply`.
3. Inspect every warning, dirty worktree, missing commit, and branch mismatch.
4. If the report is correct, rerun with `--apply` to make only safe repairs.
5. Recompute the ready frontier from the reconciled state.

A commit already reachable from the integration branch must never be redispatched. A ticket marked `running` whose worker or workspace disappeared is stale, not automatically failed; inspect its report, branch, patch, and Git status before deciding whether to recover, integrate, or replace it.

## Failure handling

Preserve failed or dirty workspaces until classified. Record the error and choose among:

| Condition | Action |
|---|---|
| Worker returned a usable commit but delivery failed | Package and review the commit; do not rerun implementation. |
| Worker returned a patch but automatic apply failed | Preserve the patch and use a narrow conflict-resolution path. |
| Worker stopped with `NEEDS_CONTEXT` | Add only the named missing context and follow up or replace. |
| Worker stopped with `NEEDS_SPLIT` | Split the ticket contract with user approval when scope changes; do not improvise hidden subtickets. |
| Worker vanished with dirty changes | Preserve the workspace, inspect the diff, and decide whether to salvage or discard explicitly. |
| Dispatched worker stalls (no progress, no result) | Cancel it, preserve any partial workspace, redispatch once fresh or complete the step controller-side; record the intervention in the ledger. |
| Base or integration branch moved unexpectedly | Stop, record both SHAs, and reconcile before any new dispatch. |

## Cleanup

Remove a child workspace only after its intended commits are integrated, applicable checks pass, and the workspace is clean. Never force-remove a worktree with uncommitted changes. Keep failed, disputed, or unintegrated workspaces until the final report identifies their disposition.

At completion, offer to remove clean child worktrees and the integration worktree. Do not delete branches or the run ledger unless the user explicitly requests it. Preserve enough evidence to audit the final branch. Before removing the integration worktree, confirm the run directory is not inside it; if it is, move the run directory out first — its teardown would otherwise destroy the audit record.
