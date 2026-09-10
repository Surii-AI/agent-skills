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
guidance/
reviews/
diffs/
conflicts/
```

The controller is the only writer of `state.json` and `ledger.md`. Workers receive read-only pointers and write only their assigned report files inside the run directory.

Place the run directory in the main checkout's ignored path or outside the repository — never inside the integration worktree or a child workspace that teardown removes. Workspaces are disposable once integrated; the ledger, reports, and reviews are the audit record and must survive cleanup.

A finished run's `repo-profile.json` can seed the next run's preflight (`scripts/repo_profile.py reuse`) when phases repeat in one repository; `state.json` remains the authority for resuming *this* run.

Initialize state after the integration worktree exists:

```bash
python3 scripts/run_state.py init \
  --index <run-dir>/ticket-index.json \
  --state <run-dir>/state.json \
  --ledger <run-dir>/ledger.md \
  --repo <repo> \
  --base <base-sha> \
  --integration-branch agent/<feature>/integration \
  --integration-worktree <integration-worktree> \
  --spec <spec-path>
```
Update a ticket at every durable boundary: dispatched, guided, implemented, reviewed, repair requested, integrated, checkpoint passed, or failed. Use `scripts/run_state.py transition`; pass `--guidance <path>` when a senior guide produced the ticket's plan, so state records where the plan lives. Record assumptions or deliberately deferred findings with its `record` command. Pass `--quiet` to either command to print a one-line summary instead of the full state JSON — at scale the full JSON is tens of KiB per call and the durable files remain the authoritative record.

`transition` enforces the terminal-status contract so state cannot lie: it derives `duration_ms` from the ticket's start/finish timestamps unless given an explicit value, archives a resolved `last_error` into `repair_history` when a ticket reaches `integrated`, `verified`, or `skipped`, and rejects `integrated` without a reachable commit (`--integrated-sha` or `--head-sha`). Terminal statuses are canonical: a ticket with a commit ends `integrated`; a ticket whose entire output is unversioned artifacts — docs, sign-off packages, reports — ends `verified` with its report path as evidence. Record post-integration checkpoint outcomes in the ledger rather than restamping a code ticket `verified`.

## Resume protocol

Do not infer status from the conversation. On every resume:

1. Read `state.json`, `ledger.md`, and `ticket-index.json`.
2. Run `scripts/reconcile_run.py --state <run-dir>/state.json` without `--apply` (`--quiet` prints only the tickets carrying recommendations and any applied changes, which at scale is the inspection list).
3. Inspect every warning, dirty worktree, missing commit, and branch mismatch.
4. If the report is correct, rerun with `--apply` to make only safe repairs.
5. Recreate the integration worktree if teardown or interruption removed it: the branch survived, so attach a worktree to it rather than recreating history —

   ```bash
   python3 scripts/make_worktree.py \
     --repo <repo> \
     --path <integration-worktree> \
     --branch agent/<feature>/integration \
     --attach \
     --metadata <run-dir>/workspaces/integration.json
   ```

   `--attach` checks out the existing branch at its tip and records `attached: true` in the metadata; without it the script refuses to touch an existing branch (a new run's `--start` create cannot resume). Then rerun the service availability check from inside the re-created worktree, since a second checkout is a different environment.
6. Recompute the ready frontier from the reconciled state.

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
| Guide stopped with `NEEDS_CONTEXT` or `NEEDS_SPLIT` | Same handling as implementer stops, before any implementer is dispatched: add only the named context, or split the ticket contract with user approval. |
| Dispatched worker stalls (no progress, no result) | Cancel it after the bounded stall window — 2× the median duration of completed workers this run, floor ten minutes, unless the user declared one — then preserve any partial workspace, redispatch once fresh or complete the step controller-side; record the intervention in the ledger. |
| Base or integration branch moved unexpectedly | Stop, record both SHAs, and reconcile before any new dispatch. |

## Cleanup

Remove a child workspace only after its intended commits are integrated, applicable checks pass, and the workspace holds nothing beyond regenerable build artifacts — `__pycache__`, `*.pyc`, caches, `node_modules`, `dist`, `build`, `target`, virtualenvs. Artifacts are regenerated, not evidence: a worktree whose only residue is artifacts is clean for removal purposes, and `git worktree remove --force` is safe there only after confirming (`git status --porcelain`, or reconcile's artifact-aware dirty flag) that nothing else is uncommitted. Never force-remove a worktree with real uncommitted changes — modifications to tracked files or untracked files that are not artifacts. Keep failed, disputed, or unintegrated workspaces until the final report identifies their disposition.

At completion, offer to remove clean child worktrees and the integration worktree. Do not delete branches or the run ledger unless the user explicitly requests it. Preserve enough evidence to audit the final branch. Before removing the integration worktree, confirm the run directory is not inside it; if it is, move the run directory out first — its teardown would otherwise destroy the audit record.
