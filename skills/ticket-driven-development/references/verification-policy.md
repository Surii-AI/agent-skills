# Verification policy

Use this reference when classifying risk, deciding whether a ticket needs independent review, handling review failures, and performing final verification.

## Risk classification

Classify the ticket before dispatch. If evidence spans categories, use the highest applicable risk.

| Risk | Typical changes |
|---|---|
| Low | Small mechanical edits, isolated tests, copy changes, or local refactors with no contract change. |
| Medium | Normal feature behavior, internal interfaces, component state, dependency updates, or moderate data-flow changes. |
| High | Security, authentication, authorization, concurrency, shared persistence, schema migration, public API, build/release infrastructure, destructive operations, or wide cross-cutting changes. |

Treat unknown risk as medium until classified. Treat uncertain security, concurrency, persistence, or release effects as high.

## Pair treatment gate

Pairing splits judgment from execution: the senior guide and the plan-aware reviewer run on the strongest available model, where reasoning quality pays; the junior implementer runs on the fastest write-capable model, where token bulk lives. Apply the gate during preflight, per ticket:

| Risk | Treatment |
|---|---|
| Low | Direct dispatch: one implementer on the default tier, existing flow unchanged. |
| Medium, High | Senior guide first (`templates/guide-prompt.md`), then a junior implementer executing the guidance, then one plan-aware review. |

A pairing override the user declared at invocation is authoritative in either direction. Tickets whose entire output is unversioned artifacts skip the pair — there is no implementation to plan. Record the pairing decision for every ticket in the ledger before dispatch.

Guide dispatches are read-only: batch the guides of independent ready tickets concurrently, exactly like reviews. Guidance is pinned to the junior's start SHA; a moved base regenerates the plan only on **material drift** — changed paths between the guidance base and the actual base that touch the guidance's named files or the ticket's conflict domains. `scripts/guidance_drift.py` decides and `--patch-base` re-pins a still-valid plan; regenerating on every base move re-buys the senior model's whole investigation each time the integration head advances, which per-ticket pipelining makes routine. A guide may stop with `NEEDS_CONTEXT`, `NEEDS_SPLIT`, or `BLOCKED` — handle those exactly like implementer stops (`references/recovery.md`), at guide prices instead of implementer prices: the gate exists to catch malformed tickets before a build agent burns a workspace on them.

## Service availability preflight

Before the first dispatch, determine whether the repository's checkpoints need external services, using only the repository's own declarations — never an assumed stack:

1. **Discover** the canonical commands from repo tooling: task-runner targets (`justfile`, `Taskfile`), package scripts (`package.json`, `Cargo.toml`, `pyproject.toml`), compose or container configuration, and CI workflows (the service setup steps a CI job runs are the most reliable source of truth). Discover code-location tooling in the same pass: a `.codegraph/` directory (verify the `codegraph` binary is on PATH and run `codegraph sync` once — a stale index misroutes every worker) or an equivalent locator rule in the repository's instruction files.
2. **Skip** the check entirely when those sources show the test suite is self-contained (no service containers, no service-dependent setup steps).
3. **Run** the discovered availability command and record the command plus outcome in run state before dispatching.
4. **Ask the user** only when discovery is ambiguous, multiple conflicting candidates exist, or a check fails — present what you found and let the user pick. Do not invent commands.
5. **Re-check from the integration worktree** once it exists, before the first dispatch. Services keyed to checkout identity — compose project names, fixed ports, per-repo caches — can be healthy in the user checkout yet broken from a second checkout (a compose project-name collision over one database port is the canonical example). Rerun the availability command from inside the worktree. When a duplicate service would collide with a healthy one, point the worktree at the shared service rather than starting a second one, and record the decision in run state. Sharing is sound while the checks are read-only or cheap; when the checkpoints themselves write to the shared service — one database node serving parallel worktrees is the canonical case — descend the isolation ladder cheapest-first: (a) a **per-workspace namespace on the shared service** — its own database name on the shared Postgres node, its own keyspace prefix — provisioned by the controller with a deterministic command (e.g. `createdb`), recorded in run state, dropped at cleanup, and pointed at by the workspace's environment (a `DATABASE_URL` with the workspace's database-name suffix); (b) when the service cannot namespace, a disposable per-worktree service instance (its own compose project, port, and volume) so parallel writers get parallel infrastructure; (c) where neither is possible, suite executions take a **suite seat**: at most one or two full-suite or migration-heavy commands running anywhere in the run at a time. Code writing parallelizes; a shared database node does not, and a queue of suites on one is wall time spent at zero throughput.
6. **Measure** what each checkpoint costs: time one focused check and one full configured suite from the integration worktree, abandoning the suite probe after fifteen minutes and recording it as `> 15 min`. Availability stays blocking before the first dispatch; the cost measurement launches in the background from the integration worktree as soon as it exists, overlapping ticket indexing, corroboration, and guide dispatch. The controller awaits it only before the first decision that needs it — the first integration-smoke scoping or final-gate scheduling; until the number arrives, the default table below applies (scoped smoke per integration, full suite at the final gate). Once measured, the numbers decide schedule shape: a suite over fifteen minutes runs at the final gate and risk-tiered milestones only, and per-ticket smoke stays scoped to the focused suite plus affected components. Record both numbers in run state as the run's checkpoint budget. A preflight that records only availability has learned nothing about the run it is about to schedule.

When a required service cannot be brought up, either restrict the run to tickets whose checks do not need it or stop and record a ruling before dispatching anything. A worker that cannot run its focused tests will either commit unverified work or grind; both violate the verification contract.

## Required checkpoints

| Checkpoint | Low | Medium | High |
|---|---:|---:|---:|
| Focused tests and self-review | Required | Required | Required |
| Relevant component check before commit | Required | Required | Required |
| Independent ticket diff review | Optional only under the strict skip rule | Required | Required with the strongest appropriate reviewer |
| Integration smoke check (scoped to the ticket: focused suite + affected components; elision checked first) | After each integration; gates only that ticket's dependents | After each integration; gates only that ticket's dependents | After every integration, wave-wide barrier before further dispatch |
| Requirements-aware final branch review | Required | Required | Required |
| Full configured suite | Once at branch end unless cheap | Once at branch end | At defined milestones and branch end |

## Strict low-risk review skip

Skip independent ticket review only when all conditions hold:

- The diff is small and mechanical.
- Focused and component checks pass cleanly.
- The worker’s self-review reports no concern.
- The change does not affect a public interface, shared persistence, security, concurrency, build/release behavior, generated contracts, or test infrastructure.
- The diff remains included in the wave review or final branch review.

Record the skip and its reason in the ledger. Ambiguity means review, not skip.

## Eliding redundant smoke checks

After a clean apply or cherry-pick, compare the tree the worker verified with the tree integration produced:

```bash
git rev-parse <worker-head-sha>^{tree}
git rev-parse <integration-head-sha>^{tree}
```

Check elision before scheduling any smoke command — it is the cheapest checkpoint that exists. When the two tree hashes are equal, the integration head is byte-identical to the tree whose component check already passed — a smoke run would re-execute the exact same code. Record both tree hashes in the ledger as the checkpoint evidence and treat the checkpoint as passed. This arises routinely in per-ticket pipelined scheduling, where a single-ticket integration onto an unmoved base reproduces the worker's tree exactly.

The elision is void whenever the trees differ: the integration base moved, another ticket landed first, or a conflict was resolved. Then run the smoke checkpoint normally. High-risk runs may keep a wave-wide smoke barrier by choice even when trees match; record that choice as a ruling.

## Affected-check selection

Scope the per-ticket smoke deterministically: prefer the repository's own affected-test selector discovered at preflight and recorded in run state (vitest: `vitest run --changed <base>` or `pnpm --filter <owner-package> exec vitest run <files>`; turbo/nx: `affected`; Go: package paths); otherwise map the diff's changed paths to their owning workspace packages and run those packages' suites. Per-integration judgment calls are controller tokens and variance; a selector is a command.

## Review and repair
Give a ticket reviewer the ticket, risk, the senior guidance when the ticket was guided, implementer report, packaged base-to-head diff, relevant specification pointer, the interface notes of any blockers it builds on, and scoped repository instructions. Require evidence tied to acceptance criteria. Do not ask it to rediscover the full codebase or rerun the full suite without a concrete doubt.

Route repair by finding label. `IMPLEMENTATION` findings go to a repair worker with the unchanged guidance, the exact findings, and the current base. `PLAN` findings go back to the senior guide for one revision, after which the junior re-executes the affected steps from the revised guidance. A plan revision consumes one of the repair rounds, and a paired ticket accumulates at most three senior touches — guide, plan-aware review, and one revision or re-review — before the cap forces a stop-and-choose.

Cap ticket repair at two rounds. Follow up with the original worker only when its task-local context and workspace remain valid. Otherwise start a fresh repair worker with the original ticket, implementation report, review file, current integration base, and exact blocking findings.

After each repair, regenerate the diff package and perform a scoped re-review. After two unsuccessful rounds, stop and choose one of these explicitly: split the ticket, route to a more capable model or specialist, record a design decision for the user, or mark the run blocked.

## Final gate

After every ticket is integrated:

1. Package the complete original-base-to-integration-head diff.
2. Run the configured full suite and the requirements-aware review (`templates/final-review-prompt.md`) concurrently — both are read-only against the same final head. Record exact commands and results.
3. If changes are requested, perform one consolidated fix wave and one scoped re-review. The full suite must pass at the final head: rerun it after the fix wave only when the fix changed code; documentation-only fixes need no rerun.
4. Mark the run complete only when Git reachability, tests, and final review all pass.

**Ambient failure adjudication.** A failing full suite is a regression until proven otherwise. Reclassify a failure as pre-existing ambient flake only when all of these hold: the failing files are untouched by the base-to-head diff; the same suite fails nondeterministically across reruns (different tests or orderings each run); and the failing tests pass in isolation and at the exact final head. Then record the evidence as a deferred observation, report those tests as pre-existing and unverified — never as passing — and proceed. A failure in a file the branch touches, or any deterministic failure, blocks completion.

Do not claim success when a required check was skipped. Report it as unverified with the reason.
