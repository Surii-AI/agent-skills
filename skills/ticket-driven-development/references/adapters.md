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
python3 <skill-dir>/scripts/install_skill.py --target omp --scope user
```

The installer copies the portable source and adds OMP’s supported top-level `disable-model-invocation: true` field to the installed copy. Use `--scope project --project <repo>` for a repository-local installation. Codex, OpenCode, ZCode (`--target zcode`), and generic Agent Skills locations are available through the corresponding `--target` value.
For `--target omp --scope user`, the installer also copies the three agent definitions — `tdd-senior`, `tdd-junior`, `tdd-reviewer` — into `~/.omp/agent/agents/` (`--scope project` targets the repository's `.omp/agents/`). Differing files already present are skipped unless `--force` is passed; `--no-agents` skips agent installation entirely. The `tdd-senior` definition autoloads the `i-have-adhd` skill via OMP's `autoloadSkills` frontmatter; the rendered guide prompt still passes the resolved `{{adhd_skill_path}}` as the portable fallback. The definition's body itself also instructs the guide to load the skill, so the dependency travels with the agent on platforms that have neither autoload nor a skills allowlist.

### Preflight

Verify that the skill was explicitly invoked. Open `/settings` and ensure **Tasks → Isolation Mode** is not `none` before requesting isolated tasks. Prefer branch merge strategy when the environment exposes that choice, because branch and commit metadata are easier to reconcile than anonymous patches. Keep active implementers within the concurrency policy of `references/scheduling.md`, even if `task.maxConcurrency` is larger.

Use the built-in `task` agent for implementation and `reviewer` for independent review: they remain the portable baseline, and a run never depends on custom agents. When the installed `tdd-*` definitions are present (`~/.omp/agent/agents/tdd-junior.md`, `tdd-senior.md`, `tdd-reviewer.md` exist), prefer them per the model-tier table below — they pin per-role model tiers and tool restrictions the `task` tool cannot express. If they are absent, fall back to the built-ins; this is never a run-stopper.

The guide role adds a hard preflight dependency: the `i-have-adhd` skill whose rules shape every guidance document. Resolve its file before the first dispatch — in OMP, `skill://i-have-adhd/SKILL.md`, typically installed at `~/.agents/skills/i-have-adhd/SKILL.md` in user scope or the repository-local equivalent — verify it is readable, and pass the resolved absolute path as `{{adhd_skill_path}}` in every guide dispatch. If it cannot be resolved, stop before dispatching anything and report the missing dependency; do not silently substitute an unshaped guide.

### Dispatch

When two or more tickets are parallel-safe, use one batch call. Put only compact shared invariants in batch `context`; make each item’s `task` self-contained and point it to its ticket, report path, workspace expectations, specification excerpt, and dependency interface notes. Give every item a stable name such as `t02-passwordless-signin`.

Render each brief with `scripts/render_brief.py` (template + context JSON); the renderer errors on missing placeholders, so the compact-brief boundary is enforced by the tool, not discipline.

Set `isolated: true` for concurrent implementers and request branch integration **only when the parent/controller workspace is the integration worktree**, because OMP bases and reapplies isolated work against the parent checkout. If the active controller remains in the user checkout, create explicit child worktrees from the integration SHA and direct non-isolated workers to those absolute paths instead. Never let native isolation apply a ticket directly to the user checkout merely for convenience. Guides are read-only against the integration worktree: batch a wave's guides concurrently with each other without isolation.

Steering a worker that is already running is a bounded follow-up, never a broadcast: one message naming the exact missing check and its timeout budget, or the controller runs that scoped check itself in the worker's workspace at collection. On OMP, a running task worker keeps its context, and each steering message expands it — hold to one follow-up per collection cycle. Worker assignments cover focused and component checks; the repository's full suite executes from the controller at the final gate or a milestone seat, because N parallel workers each asked to run it are N concurrent suites contending for the same infrastructure.

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

Use the same mechanism for ticket reviewers with this schema, so verdicts reach the controller as data instead of prose to parse:

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["verdict", "ticket", "blocking_findings", "review", "summary"],
  "properties": {
    "verdict": {"enum": ["PASS", "CHANGES_REQUESTED", "BLOCKED"]},
    "ticket": {"type": "string"},
    "blocking_findings": {"type": "integer"},
    "review": {"type": "string"},
    "summary": {"type": "string"}
  }
}
```

And for senior guide dispatches with this schema, so plan readiness reaches the controller as data:

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["status", "ticket", "guidance", "steps", "concerns"],
  "properties": {
    "status": {"enum": ["PLAN_READY", "NEEDS_CONTEXT", "NEEDS_SPLIT", "BLOCKED"]},
    "ticket": {"type": "string"},
    "guidance": {"type": "string"},
    "steps": {"type": "integer"},
    "concerns": {"type": "string"}
  }
}
```

Set strict schema mode when available. Keep worker-spawned helpers prohibited: use an agent without `spawns` and without access to recursive task delegation. A normal built-in `task` worker may have broader tools, so state the prohibition explicitly in every assignment.

### Model tiers and the guide role

Paired tickets split judgment from execution, so role selection is part of dispatch:

| Role | Model tier | Assignment shape |
|---|---|---|
| Senior guide | Strongest available (extended-thinking tier) | Read-only; renders `templates/guide-prompt.md`; returns the guide contract. |
| Junior implementer | Fastest write-capable (flash/mini tier) | Standard implementer assignment plus the guidance pointer. |
| Plan-aware reviewer | Strongest available review agent | Standard reviewer assignment plus the guidance pointer. |

When the environment exposes per-task model selection, map the tiers explicitly — for example `opus`-class for the senior roles and `haiku`-class for the junior, or GLM-5.3 at `:high` thinking for the senior roles and GLM-5.3-flash at `:medium` for the junior (medium, not low: the junior must still notice when the code proves a plan step wrong). When it does not (OMP's task tool today exposes agent types, not per-task models), run both senior and junior roles on the default `task` agent and use `reviewer` for the plan-aware review: the pair still earns its keep through context isolation, because the guide's investigation never enters the junior's context window and the plan is re-derived from repository evidence instead of conversation memory.

On OMP, per-dispatch models are expressed through the installed agent definitions rather than dispatch flags: `tdd-senior` and `tdd-reviewer` pin GLM-5.3 `:high` with read-only tool sets, and `tdd-junior` pins GLM-5.3-flash `:medium`. Without them, default to `task` + `reviewer` as above.

### Results and repair

Read the compact structured result first, then the report and task artifact only when needed. Record the worker ID, branch or patch metadata, base SHA, head SHA, report path, guidance path, token/context measurements when available, and verdict in run state.

Capture measurements at collection time: the task completion notification carries `total_tokens` and `duration_ms` in its result metadata — the line the notification prints alongside the output (not the worker's own report, which cannot see it). Extract them at delivery; the worker is torn down afterward and its transcript is not a durable source. Pass them to the same `run_state.py transition --quiet` call that records the result (`--context-tokens`, `--duration-ms`, `--requests`). The script derives duration from timestamps when the flag is omitted, but it cannot invent token counts after the fact.

An OMP isolated worker is torn down after completion and cannot be revived. For review repairs, dispatch a fresh isolated repair worker from the updated integration head with the original ticket, report, review findings, and current diff package. A non-isolated idle or parked worker may be messaged for follow-up if its workspace is still valid.

Do not depend on OMP’s conversation transcript for recovery. Treat `state.json`, `ledger.md`, Git history, and durable evidence files as authoritative.

### Sequential tickets

For a single ready ticket, prefer one fresh non-isolated `task` worker in the already isolated integration worktree. This preserves the option to follow up with the same worker. Assign only one writer at a time in that worktree.

## ZCode adapter

ZCode exposes an Agent tool whose input carries `subagent_type` and `run_in_background`; its built-in types are `general-purpose` (all tools) and `Explore` (read-only). Install the skill with `python3 <skill-dir>/scripts/install_skill.py --target zcode --scope user` — the installer copies the skill only, because the bundled `agents/*.md` definitions target Oh My Pi and ZCode never loads them.

### Preflight

ZCode has no isolation setting to verify because it offers no native task isolation: concurrency always runs through explicit `make_worktree.py` child worktrees based on the recorded integration commit, per the generic-adapter isolation rules. Resolve `i-have-adhd` at `~/.agents/skills/i-have-adhd/SKILL.md` or `~/.zcode/skills/i-have-adhd/SKILL.md` (repository-local equivalents likewise) and verify it is readable before the first dispatch.

Read the Agent tool's own available-types list. When `tdd-senior`, `tdd-junior`, or `tdd-reviewer` profiles are configured, prefer them per the model-tier table below. When they are absent, dispatch the built-ins; this is never a run-stopper — role discipline comes from the rendered assignment templates, and a run never depends on custom agents. Profiles load at session start, so a definition added mid-session is invisible until the next session; dispatching an unknown type errors recoverably and lists the available agents.

### Dispatch

There is no batch primitive: dispatch one Agent call per worker and issue a wave's calls together in a single turn; `run_in_background: true` gives concurrent implementers async execution with a completion notification. Concurrent implementers each receive an explicit child worktree and an assignment pointing at that absolute path — ZCode has no `isolated` equivalent, so never point two writers at one checkout. The Agent tool takes no structured-output schema, so the templates' compact text return contracts are the return channel.

Under built-ins, every role dispatches as `general-purpose`: the Agent input deliberately omits per-call model selection (the profile or Settings decides model and thinking tier), so record the effective tier from the dispatch result instead of assuming one. `Explore` is read-only but typically pinned to a faster, cheaper tier; it is not a substitute for the senior guide's strong tier.

The recursion prohibition must be stated in every assignment, because a built-in `general-purpose` worker carries every tool, including subagent spawning and skills. The rendered templates already carry the prohibition; `tdd-*` profiles that omit those tools make it structural.

### Results, follow-up, and stopping

A foreground call returns the worker's final message; a background worker notifies on completion. Both carry `totalTokens`, `usage`, and `totalDurationMs` in the result metadata — the only place token totals exist before they are gone; pass them to the same `run_state.py transition --quiet` call that records the result (`--context-tokens`, `--duration-ms`). Agent records persist under `~/.zcode/cli/agents/<session>/<agentId>/` as durable pointers, but recovery trusts `state.json`, `ledger.md`, and Git history — never transcripts.

Follow up by messaging the worker's `agentId` via `SendMessage`: it resumes the same worker with its context intact, matching the bounded one-follow-up-per-collection-cycle rule. Stop a wedged worker with `TaskStop` by task id, then confirm no checkpoint process outlived it before redispatching.

For a single ready ticket, prefer one foreground worker in the already isolated integration worktree — the follow-up channel keeps that same worker reachable.

### Model tiers and custom profiles

ZCode pins model and thinking tier per profile, not per dispatch. The built-in baseline runs every role on `general-purpose` — senior- and reviewer-correct, junior-costly. The optional `tdd-*` profiles recover the tier split. A profile is one Markdown file under `~/.zcode/agents/` (user scope) or `<repo>/.zcode/agents/` (workspace scope) — the same files that Settings → Subagents edits — with required `name` and `description` frontmatter, optional `model`, `thoughtLevel`, `tools`, `disallowedTools`, `maxTurns`, and `injectAgentsMd`, and the body serving as the system prompt:

```markdown
---
name: tdd-junior
description: Junior implementer for ticket-driven development — executes a senior guide's plan verbatim in an assigned workspace, with focused tests and self-review.
model: <model id as the client writes it, e.g. custom:builtin%3Azai-coding-plan:GLM-5.3-Flash>
thoughtLevel: high
tools: [Read, Write, Edit, Bash, Grep, Glob]
---

<system prompt — the body of the skill's `agents/tdd-junior.md`>
```

Install the three files with `python3 <skill-dir>/scripts/install_skill.py --target zcode --scope user --zcode-agents`; add `--zcode-model tdd-junior=<id>` (repeatable) to pin per-role models. The `model:` value is the machine-specific identifier the client's model picker uses — copy it from there or from `~/.zcode/v2/agents-state.json`; omitting `model` inherits the session default, which keeps the tool restriction and system prompt but not the tier split. Target shape:

| Profile | Model | Thinking | Tools | Skills |
|---|---|---|---|---|
| `tdd-senior` | GLM-5.3 | high | Read, Grep, Glob, Bash, WebSearch | i-have-adhd |
| `tdd-junior` | GLM-5.3-Flash | high | Read, Write, Edit, Bash, Grep, Glob | — |
| `tdd-reviewer` | GLM-5.3 | high | Read, Grep, Glob, Bash | — |

ZCode's reasoning variants are low, high, and max — there is no medium, so Oh My Pi's junior `flash:medium` maps to Flash at high, never low: the junior must still notice when the code proves a plan step wrong. Omitting the subagent and skill tools from each profile makes the no-recursion invariant structural.

A profile's `skills:` frontmatter is the ZCode counterpart of Oh My Pi's `autoloadSkills`, as a least-privilege allowlist: ZCode auto-provisions the Skill tool for that profile and filters its skill discovery to exactly the named skills — nothing else is visible. Give `tdd-senior` `skills: [i-have-adhd]` so the guide can load the reader-shaping rules itself; the rendered guide assignment still passes the resolved `{{adhd_skill_path}}` and the guide reads the file directly when the profile is absent, which is the portable path.

## Generic adapter

If the environment exposes a subagent or task API, map it to the capability contract and use structured results when available. Otherwise, execute sequential tickets in the controller and use fresh subprocess sessions only if the environment supports them safely.

When native isolation is absent or opaque, create the integration and child worktrees with `scripts/make_worktree.py`. Start every parallel child from the exact same integration SHA, require a commit, and cherry-pick clean commits into the integration branch. Never ask a language model to perform a clean cherry-pick that Git can do deterministically.

If the environment cannot launch subagents at all, retain the ticket graph, integration worktree, risk gates, pairing decisions, state ledger, and context boundaries, but execute the ready frontier sequentially in the controller — the controller itself then acts as senior guide and junior in one seat, writing the guidance document before implementing from it. Report that concurrency was unavailable; do not fake parallelism.
