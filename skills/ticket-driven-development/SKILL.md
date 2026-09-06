---
name: ticket-driven-development
description: Execute an approved specification through dependency-linked Markdown tickets using bounded fresh workers, adaptive isolated concurrency, risk-based review, deterministic Git integration, and resumable run state. Use only when explicitly invoked as /skill:ticket-driven-development; do not use for ticket authoring or ordinary coding requests.
metadata:
  invocation: explicit-only
  omp-frontmatter: disable-model-invocation
---

# Ticket-Driven Development

Act as the **controller**. Convert an approved directory of Markdown tickets into a tested integration branch without expanding worker context unnecessarily. Keep scheduling, integration, state, and final acceptance in the controller; give each implementation or review worker one bounded assignment.

## Non-negotiable invariants

1. Work from one isolated integration branch. Do not implement on the user’s primary branch or modify a dirty checkout.
2. Treat tickets as a dependency graph, not a list. Dispatch only tickets whose blockers have passed the required checkpoint.
3. Parallelize only confidently independent tickets. Never run concurrent writers in one checkout.
4. Give each worker one ticket and file pointers, not the parent conversation or every ticket.
5. Prohibit worker recursion. Only the controller may dispatch implementation, review, or conflict-resolution workers.
6. Require durable report files and compact returns. Keep full diffs and detailed reports out of the controller conversation when file pointers suffice.
7. Use deterministic Git commands for clean integration. Use a conflict agent only after Git demonstrates a conflict.
8. Cap ticket repair at two rounds. Stop, split, escalate, or ask for a decision after the cap.
9. Persist `state.json` and append-only `ledger.md`. Never use conversation memory as the run database.
10. Mark a ticket complete only after its change is reachable from the integration branch and its applicable checkpoint passes. Terminal statuses are canonical, not stylistic: a ticket with a commit ends `integrated` (record checkpoint outcomes in the ledger and review verdict, not by restamping the status); a ticket whose entire output is unversioned artifacts (docs, sign-off packages) ends `verified` with its report as evidence — never `integrated` with no commit, and never by working in the user's checkout.
11. A source status claiming completion is a claim, not evidence. Corroborate it against the repository before trusting it; never redispatch corroborated work, and never schedule dependents on an uncorroborated claim.
12. Mutate the repository only when open work exists. When corroboration leaves no incomplete ticket, end the run with zero repository changes.

## Read references only when needed

| Situation | Read |
|---|---|
| Parse tickets, prepare context, or diagnose graph errors | `references/ticket-format.md` |
| More than one ticket is ready or integration conflicts | `references/scheduling.md` |
| Classify risk, decide review depth, verify service availability, or repair failures | `references/verification-policy.md` |
| Start, resume, reconcile, or clean a run | `references/recovery.md` |
| Map orchestration to Oh My Pi or another environment | `references/adapters.md` |

## Workflow

### 1. Confirm inputs and authority

Require an approved specification or substantial request, a local directory containing one Markdown file per ticket, and a Git repository. Ask only when a missing decision changes behavior, ticket boundaries, acceptance criteria, dependencies, or an irreversible design choice.

Do not author a new ticket plan inside this skill. If tickets are absent or materially incomplete, stop and request ticket shaping. Minor metadata omissions may be inferred conservatively.

### 2. Inspect repository safety

Read applicable repository instruction files. Record the repository root, current branch, current `HEAD`, worktree list, and dirty status. Do not stash, discard, commit, or relocate pre-existing user changes.

Verify the environment can actually run the configured checkpoints before the first dispatch. Discover the repository's own service tooling instead of assuming any particular stack: read its task-runner targets, package scripts, compose or container configuration, and CI workflow to determine (a) whether the test suite needs external services — database, broker, cache — at all, and (b) the repository's canonical command for starting or checking each one. Repositories whose tests are self-contained skip this check. When a service is required, run the discovered availability command and record the result in run state; a worker that cannot run its focused tests will either commit unverified work or grind — both violate the verification contract. Ask the user only when discovery is ambiguous, candidates conflict, or a check fails — never invent or hardcode commands on the user's behalf. When required infrastructure is unreachable, either restrict the run to tickets whose checks do not need it or stop and record a ruling before dispatching anything. See `references/verification-policy.md` for the procedure.

Choose an ignored run directory such as `.scratch/<feature>/runs/<run-id>/`, and verify with `git check-ignore` that it is actually ignored — repositories sometimes track `.scratch/`, in which case pick another ignored path or keep run state outside the repository. Ensure the integration worktree path is outside the repository or ignored before creating it.

### 3. Normalize and validate tickets

Run:

```bash
python3 <skill-dir>/scripts/index_tickets.py <ticket-dir> \
  --output <run-dir>/ticket-index.json
```

Stop on duplicate IDs, missing required fields, unresolved blockers, or dependency cycles. Read `references/ticket-format.md` when repairing input or preparing worker context. Do not begin setup while `valid` is false.

### 4. Corroborate completion claims and compute open work

The index reports every ticket whose source status claims completion as a warning (the exact completed-status set is in `references/ticket-format.md`). Treat each claim as unverified until corroborated against the repository:

- **Corroborated** — commits, merged branches, tags, or changelog entries reachable from the recorded base that plausibly implement the ticket's outcome. Record the evidence (commit SHA or file) with the ticket. A corroborated ticket is complete: never redispatch it, and treat it as satisfying its dependents.
- **Uncorroborated** — the repository shows no trace of the claimed work. This is the user's decision, not the controller's: record a ruling request asking whether to reopen the ticket, and schedule nothing that depends on it until the user rules.

If corroboration leaves no incomplete ticket, stop and report the directory as a historical record: do not create an integration branch, worktree, `state.json`, or ledger, and leave the repository exactly as found. Continue to setup only when open work remains or the user reopens a claim.

### 5. Create the integration branch and worktree

With open work confirmed, create a branch such as `agent/<feature>/integration` at the recorded base SHA. Prefer a real integration worktree that isolates the run from the user checkout:

```bash
python3 <skill-dir>/scripts/make_worktree.py \
  --repo <repo> \
  --path <integration-worktree> \
  --branch agent/<feature>/integration \
  --start <base-sha> \
  --metadata <run-dir>/workspaces/integration.json
```

If the active environment cannot move the controller into that worktree, keep the controller read-only in its original checkout and use absolute paths for all operations in the integration worktree. Use environment-native isolated children only when they are based on this integration worktree; otherwise use explicit child worktrees.

A second checkout is a different environment, not just a different path: tooling keyed to checkout identity — compose project names, fixed ports, per-repo caches — can be healthy in the user checkout yet broken from the integration worktree. After creating it, rerun the service availability command from inside the worktree and record the outcome. When a duplicate service would collide with the healthy one (two compose projects claiming one database port, for example), point the worktree at the already-healthy shared service instead of starting a duplicate, and record that decision.

Any baseline verification — a green base-suite run, a service check, a build probe — happens inside this worktree once it exists, never in the user checkout: even a read-only test run there writes build artifacts into the user's tree and violates the read-only controller.

### 6. Initialize durable state

Run `scripts/run_state.py init` as shown in `references/recovery.md`. Record inferred risk, conflict domains, test commands, review policy, environment adapter, corroboration outcomes, and any ruling before dispatch.

On an existing run, do not initialize again. Follow the resume protocol in `references/recovery.md` and reconcile Git before doing new work.

### 7. Compute and classify the ready frontier

A ticket is ready only when every blocker is integrated and its required checkpoint passed. Infer missing conflict domains from a narrow repository inspection. Read `references/scheduling.md` and choose:

- **Sequential:** one fresh worker in the integration worktree when only one ticket is ready, domains overlap, or risk is high.
- **Parallel:** at most four fresh workers by default — or the concurrency cap the user declared at invocation — in isolated child workspaces when at least two dependency-independent tickets have confidently disjoint conflict domains. A user-declared cap is authoritative: apply it without demanding prior-run evidence, but still lower it when the repository or test environment is fragile, and never exceed the invariants (no concurrent writers in one checkout, disjoint domains only).

Record the chosen wave base. Start every parallel child from that exact integration commit.

### 8. Dispatch bounded implementers

Render `templates/implementer-prompt.md` for each ticket. Supply the full ticket, compact global constraints, precise specification/ADR pointers, relevant repository instructions, dependency commit/interface notes, workspace path, expected base SHA, and report path.

Do not supply the full interview, all tickets, unrelated reports, or accumulated controller history. Target an initial context below approximately 20k tokens when observable; treat 40k as a warning. Prepare a narrower excerpt or split the ticket instead of silently filling a large context window.

Use the adapter in `references/adapters.md`. Prefer structured return fields when supported. A worker may finish as `COMPLETE`, `BLOCKED`, `NEEDS_CONTEXT`, `NEEDS_SPLIT`, or `FAILED`.

If a dispatched worker stalls — no progress and no result — cancel it after a bounded window: twice the median duration of completed workers this run, with a floor of ten minutes; a window the user declared at invocation overrides the default. Preserve any partial workspace for inspection, and either redispatch once from a fresh worker or complete that step yourself in the controller. Record the intervention, its window, and its reason in the ledger either way; a silently absorbed stall is a lost audit event.

### 9. Verify and integrate each result

For a complete result, run the verification, packaging, and state transition as one shell invocation per result rather than separate steps — controller round-trips between collection actions measured roughly a fifth of a four-ticket run's wall time:

1. Confirm the report exists and the claimed commit/patch belongs to the assigned base and workspace.
2. Confirm focused tests, a relevant component check, and self-review are recorded.
3. Package the complete change:

```bash
python3 <skill-dir>/scripts/package_diff.py \
  --repo <workspace> \
  --base <ticket-base-sha> \
  --head <ticket-head-sha> \
  --ticket <ticket-id> \
  --output <run-dir>/diffs/<ticket-id>.md
```

4. Apply the risk policy in `references/verification-policy.md`. Render `templates/reviewer-prompt.md` when review is required.
5. If approved, integrate with deterministic Git. Confirm the ticket head is an ancestor of the integration head, then run the required smoke checkpoint — unless the worker-verified and integration trees are byte-identical (`git rev-parse <sha>^{tree}` equality), in which case record the equal tree hashes as checkpoint evidence per the elision rule in `references/verification-policy.md`.
6. Persist every transition with `scripts/run_state.py transition --quiet`, recording measurements from the worker result at collection time — duration and context size are only reliably observable now, and backfilled numbers are guesses. `--quiet` prints a one-line summary instead of the full state JSON, which at scale is tens of KiB per call; `state.json` and the ledger remain the authoritative record.

A result with no repository change integrates nothing: confirm its artifacts landed at their assigned run-directory paths and transition the ticket to `verified` with the report as evidence. A result with a commit ends `integrated`; do not restamp it `verified` after its checkpoint — record the checkpoint pass in the ledger instead.

For review failure, perform no more than two repair rounds. Resume the original worker only when its workspace survives; otherwise dispatch a fresh repair worker with the exact findings and current evidence.

For a real merge conflict, preserve both sides and render `templates/conflict-resolver-prompt.md`. Do not let a general merger agent reinterpret a clean integration.

### 10. Advance by waves

Advance per ticket, not per wave: as soon as one ticket's integration checkpoint passes, recompute the frontier from durable state and dispatch newly ready work — do not hold a dependent back for a sibling ticket that is still under review. Only high-risk runs keep a wave-wide barrier (smoke before any further dispatch). Reviews of independent tickets are read-only: batch them concurrently instead of serially. Newly unblocked work starts from the updated integration head. Repeat dispatch, verification, and integration until no incomplete ticket remains or the run becomes blocked.

When no ticket is ready but incomplete tickets remain, diagnose an invalid state, unresolved failure, or unrecorded ruling. Do not guess.

### 11. Run the final gate

Package the full original-base-to-integration-head diff. Run the configured full suite and the requirements-aware final branch review (`templates/final-review-prompt.md`) concurrently: both are read-only against the same final head, so there is no reason to serialize them. The full suite must pass at the final head — after a fix wave, rerun it only when the fix changed code.

If changes are requested, perform one consolidated fix wave and one scoped re-review. Mark the run complete only when all intended tickets are integrated, required checks pass, and the final verdict is `PASS`.

### 12. Measure, report, and clean up safely

Measure critical-path wall time per accepted change rather than worker count. Record duration and worker context size at collection time — `run_state.py` derives ticket duration from its recorded timestamps, and the dispatch result (on OMP, the task completion notification) is the only place token totals exist before they are gone. Summarize ticket duration, worker context size, agent seats, repair rounds, merge conflicts, worktree overhead, and human interventions. Treat routine worker context above 64k tokens, mandatory merger agents on clean integrations, or frequent parallel conflicts as policy failures to investigate rather than normal costs.

Report the integration branch and head, completed tickets, exact tests, review outcomes, rulings, corroboration outcomes, deferred observations, unresolved risks, measurements, and workspace disposition. Distinguish passed, failed, and skipped checks.

Offer cleanup. Remove only integrated child worktrees that hold no changes beyond regenerable build artifacts (`__pycache__`, caches, `node_modules`, `dist`, build output) — artifacts are safe to destroy with `git worktree remove --force` once verified as the only residue; a workspace with real uncommitted changes is never force-removed. Never delete the run ledger or branches without explicit user instruction. Keep the run directory in the main checkout's ignored path (or outside the repository) — never inside a worktree that teardown removes — so the ledger, reports, and reviews survive cleanup as the run's audit record.

## Success contract

A successful run produces:

| Artifact | Requirement |
|---|---|
| Integration branch | Contains every accepted ticket commit and no unreviewed conflict resolution. |
| `state.json` and `ledger.md` | Reconcile with Git and support restart without redispatching integrated work. |
| Ticket reports and reviews | Provide acceptance evidence through file pointers. |
| Final diff package | Covers the complete base-to-head change. |
| Verification record | Lists exact commands and truthful outcomes. |
| Final response | States what changed, where it lives, what passed, and what remains. |
