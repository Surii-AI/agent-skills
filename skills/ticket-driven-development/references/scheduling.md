# Scheduling and integration policy

Use this reference whenever the ready frontier contains more than one ticket, a ticket’s conflict domain is uncertain, or integration fails.

## Objective

Optimize the shortest reliable critical path, not worker count. Start with a maximum of four concurrent implementers. A concurrency cap the user declares at invocation is authoritative — honor it without demanding prior-run evidence. Lower the cap when the repository, provider, or test environment is fragile; raise it beyond the user's number only from measured evidence.

## Classify the frontier

A ticket is dependency-ready only after all blockers have been integrated and the applicable checkpoint has passed. Before dispatch, infer risk and conflict domains from the ticket plus a narrow repository scan when metadata is absent.

Treat these as conflict domains: files and directories; public interfaces; schemas and migrations; shared persistence; dependency manifests and lockfiles; generated artifacts; build and release configuration; cross-cutting test fixtures; global styles; and runtime configuration.

The `<run-dir>/ticket-graph.md` Mermaid DAG rendered at frontier time (SKILL.md step 7) is the plan snapshot for the user's orientation, not a scheduling input: dispatch decisions come from durable state and the conflict-domain analysis above, never from the diagram.

| Ready-frontier condition | Action |
|---|---|
| One ticket is ready | Run one fresh worker in the integration worktree. |
| Several tickets share or may share a conflict domain | Run sequentially in the integration worktree. |
| At least two tickets have no dependency edge and confidently disjoint domains | Run a parallel wave in isolated child workspaces based on the same integration SHA. |
| A refactor has a wide blast radius | Use expand–migrate–contract; parallelize only disjoint migrate batches. |
| A ticket changes security, concurrency, a public interface, shared persistence, or release infrastructure | Prefer sequential execution unless independence is explicit. |
| Independence cannot be established cheaply | Choose sequential execution. |

Never parallelize dependent tickets merely because the environment permits more workers. Never run concurrent writers in the same checkout.

## Dispatch a wave

Before starting a wave:

1. Record the exact integration `HEAD` as the wave base.
2. Assign each ticket an explicit conflict domain and file-ownership boundary.
3. Prepare one bounded brief and report path per worker.
4. Ensure all child workspaces start from the same wave base.
5. Record worker IDs and workspace/branch metadata before relying on their output.
6. For parallel waves, provision child workspaces (worktree create plus dependency install via the discovered install command, e.g. `pnpm install --frozen-lockfile --prefer-offline` with a warm store) in the background concurrent with guide dispatch: guides are read-only against the integration worktree and never wait on a child install, and an implementer launches when both its `PLAN_READY` and its provisioned workspace exist. Direct-dispatch (unpaired) tickets provision the same way at wave start.

Dispatch the critical path first: start the longest or highest-risk ready ticket before its siblings, so its review overlaps their implementation and its dependents unblock earliest.

Speculative guidance pre-pinning: while a wave's implementers are in flight, the controller may batch the guides of their known dependents concurrently, pinned to the current integration head as the expected base; record each dispatch in the ledger as speculative with its expected base. The cap is the disjoint-domain rule: pre-pin only when the in-flight blocker's conflict domain is disjoint with the dependent's conflict domain, bounding wasted senior-model tokens — a blocker that cannot touch the guidance's named files cannot force a regeneration. At junior launch, `scripts/guidance_drift.py` adjudicates the moved base: immaterial drift re-pins the plan with `--patch-base`; material drift regenerates the guidance once at the senior tier. Never dispatch an implementer against unadjudicated speculative guidance.

Budget the isolation cost honestly: in dependency-heavy monorepos (gitignored `node_modules`, virtualenvs, build caches) every child worktree needs its own dependency install before it can build or test. With a warm package-manager store this is minutes per workspace, not seconds. When parallel worktrees are right but installs are costly, point each child install at the package manager's shared store — pnpm, cargo, uv, and poetry all reuse a global cache by default or with one setting — so children pay for cold files only. When installs remain expensive, prefer sequential waves in the single integration worktree (one install, reused) over parallel child worktrees — the no-concurrent-writers invariant is preserved either way, and critical-path time often wins sequential. For shared *services* (databases), apply the isolation ladder in `references/verification-policy.md` — a per-workspace namespace before a duplicate instance before suite seats — instead of duplicating containers by default.

The controller owns scheduling and state. Workers must not spawn helpers, modify ticket files, edit run state, or integrate sibling work.

## Integrate results

Batch collection applies to every completed worker (SKILL.md workflow step 9): run the verification, packaging, and transition shell work as one invocation per result:

1. Confirm its report exists and the claimed commit or patch matches the assigned workspace.
2. Confirm focused and component checks passed or classify the result as incomplete.
3. Package the complete base-to-head diff with `scripts/package_diff.py`.
4. Run the risk-required ticket review.
5. Apply or cherry-pick a clean, approved change with deterministic Git commands.
6. Mark the ticket integrated only after its commit is reachable from the integration branch.

Do not launch a merger agent for a clean Git operation. If Git reports a conflict, abort the automatic operation, preserve both sides, save the conflict evidence, and use `templates/conflict-resolver-prompt.md` for one narrow resolver.

Smoke-check each integration per its risk tier — eliding the run only when the worker-verified and integration tree hashes are equal (rule in `references/verification-policy.md`) — then recompute the frontier immediately: a ticket's dependents are gated by that ticket's own checkpoint, never by a sibling still under review. Only high-risk runs keep a wave-wide smoke barrier before further dispatch. Newly unblocked tickets must start from the updated integration branch, never from a sibling branch. Independent ticket reviews are read-only and conflict-free: dispatch them as one parallel batch rather than one at a time.

## Dispatch a fix wave

Final-gate fix requests dispatch under the same frontier discipline as implementation. The default is one consolidated fix wave in the integration worktree: a fix is usually minutes of work, and parallel machinery costs a child workspace per fix.

Go parallel only when both hold:

- At least two fix requests have disjoint conflict domains, classified from each finding's target paths — not from the tickets' domains: two disjoint tickets can produce fix requests touching one shared file.
- The measured child-workspace provisioning cost is smaller than the expected serial fix time; use the recorded duration of a prior fix round when one exists, otherwise stay consolidated.

Before any fix dispatch, true up durable state: run `scripts/reconcile_run.py --state <run-dir>/state.json --apply` so the recorded `integration.head_sha` equals the delivered head — fix commits landing around a stale recorded head are state drift a later resume pays for. Parallel fixes run in child worktrees based on the delivered head, one bounded brief and report path per fix worker, worker and workspace metadata recorded before output is trusted. Integrate each fix with deterministic Git, check elision per fix, and batch the scoped re-reviews as one parallel read-only batch at each ticket's review tier. The two-round repair cap is unchanged.

## Stop conditions

Pause the run and record a ruling when requirements conflict, a required secret or external action is unavailable, the base branch moved incompatibly, or a ticket cannot be safely split without changing user-visible scope. Do not silently choose an irreversible product or architecture decision.
