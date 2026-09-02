# Orchestration adapters

Use this reference during preflight to map the portable workflow onto the active coding-agent environment.

## Portable capability contract

The controller needs only these semantic operations:

| Operation | Required behavior |
|---|---|
| Dispatch worker | Start a fresh task-scoped agent with a self-contained assignment and a known workspace. |
| Collect result | Receive a compact status plus a pointer to durable evidence. |
| Follow up | Resume the same worker when its context and workspace still exist; otherwise start a fresh repair worker. |
| Isolate edits | Give concurrent writers independent Git-visible filesystems based on the same integration commit. |
| Integrate | Apply or cherry-pick successful work into the integration branch with an auditable commit boundary. |
| Stop worker | Terminate unsafe, obsolete, or stuck work without discarding its evidence. |

If an environment lacks one of these operations, emulate it with the bundled scripts and ordinary Git commands. Do not emulate isolation with concurrent writers in one checkout.

## Oh My Pi reference adapter

Oh My Pi is the preferred adapter. Its official documentation is at <https://omp.sh/docs/subagents>, <https://omp.sh/docs/skills>, and <https://github.com/can1357/oh-my-pi/blob/main/docs/tools/task.md>.

For a local installation with enforced explicit-only discovery, run:

```bash
python scripts/install_skill.py --target omp --scope user
```

The installer copies the portable source and adds OMP’s supported top-level `disable-model-invocation: true` field to the installed copy. Use `--scope project --project <repo>` for a repository-local installation. Codex, OpenCode, and generic Agent Skills locations are available through the corresponding `--target` value.

### Preflight

Verify that the skill was explicitly invoked. Open `/settings` and ensure **Tasks → Isolation Mode** is not `none` before requesting isolated tasks. Prefer branch merge strategy when the environment exposes that choice, because branch and commit metadata are easier to reconcile than anonymous patches. Keep the skill’s default maximum active implementers at three even if `task.maxConcurrency` is larger.

Use the built-in `task` agent for implementation and `reviewer` for independent review. Do not require custom `.omp/agents` files in version 0.1; Agent Skills cannot install those definitions portably.

### Dispatch

When two or more tickets are parallel-safe, use one batch call. Put only compact shared invariants in batch `context`; make each item’s `task` self-contained and point it to its ticket, report path, workspace expectations, specification excerpt, and dependency interface notes. Give every item a stable name such as `t02-passwordless-signin`.

Set `isolated: true` for concurrent implementers and request branch integration **only when the parent/controller workspace is the integration worktree**, because OMP bases and reapplies isolated work against the parent checkout. If the active controller remains in the user checkout, create explicit child worktrees from the integration SHA and direct non-isolated workers to those absolute paths instead. Never let native isolation apply a ticket directly to the user checkout merely for convenience.

Use an invocation-specific structured output schema matching the compact implementer contract:

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["status", "ticket", "commit", "tests", "report", "concerns"],
  "properties": {
    "status": {"enum": ["COMPLETE", "BLOCKED", "NEEDS_CONTEXT", "NEEDS_SPLIT", "FAILED"]},
    "ticket": {"type": "string"},
    "commit": {"type": ["string", "null"]},
    "tests": {"type": "string"},
    "report": {"type": "string"},
    "concerns": {"type": "string"}
  }
}
```

Set strict schema mode when available. Keep worker-spawned helpers prohibited: use an agent without `spawns` and without access to recursive task delegation. A normal built-in `task` worker may have broader tools, so state the prohibition explicitly in every assignment.

### Results and repair

Read the compact structured result first, then the report and task artifact only when needed. Record the worker ID, branch or patch metadata, base SHA, head SHA, report path, token/context measurements when available, and verdict in run state.

An OMP isolated worker is torn down after completion and cannot be revived. For review repairs, dispatch a fresh isolated repair worker from the updated integration head with the original ticket, report, review findings, and current diff package. A non-isolated idle or parked worker may be messaged for follow-up if its workspace is still valid.

Do not depend on OMP’s conversation transcript for recovery. Treat `state.json`, `ledger.md`, Git history, and durable evidence files as authoritative.

### Sequential tickets

For a single ready ticket, prefer one fresh non-isolated `task` worker in the already isolated integration worktree. This preserves the option to follow up with the same worker. Assign only one writer at a time in that worktree.

## Generic adapter

If the environment exposes a subagent or task API, map it to the capability contract and use structured results when available. Otherwise, execute sequential tickets in the controller and use fresh subprocess sessions only if the environment supports them safely.

When native isolation is absent or opaque, create the integration and child worktrees with `scripts/make_worktree.py`. Start every parallel child from the exact same integration SHA, require a commit, and cherry-pick clean commits into the integration branch. Never ask a language model to perform a clean cherry-pick that Git can do deterministically.

If the environment cannot launch subagents at all, retain the ticket graph, integration worktree, risk gates, state ledger, and context boundaries, but execute the ready frontier sequentially in the controller. Report that concurrency was unavailable; do not fake parallelism.
