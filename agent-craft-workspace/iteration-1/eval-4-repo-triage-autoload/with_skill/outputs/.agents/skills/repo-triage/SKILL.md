---
name: repo-triage
description: Triage a repository through the repo-triage agent — scans stack, layout, entry points, build/test state, and rot signals, then returns one ranked report. Use for "triage this repo", "repo triage", "what's going on in this codebase", "give me the lay of the land", "assess this repo before we touch it", "onboard me on this codebase", "what state is this repo in", "where's the rot". Pairs with the repo-triage agent.
---

# repo-triage

this skill owns the conversation: it locks scope, packs the assignment, and delegates. the actual scanning happens in the **repo-triage** agent's fresh context — never scan the repo in-session.

## When this triggers
- "triage this repo" / "repo triage"
- "what's going on in this codebase" / "give me the lay of the land"
- "assess this repo before we touch it" / "onboard me on this codebase"
- "what state is this repo in" / "where's the rot"

## Interview
ask only what the user didn't already say:
- **scope** — whole repo, or a named subsystem/path?
- **focus** — default balanced triage, or biased to one of: onboarding (how do i get this running), debt (what's rotten), risk (what breaks easiest)?
- **context** — anything the agent should know: "we're migrating off X", "this module is cursed", upcoming deadline.

if the user just said "triage it" with nothing else — run the default: whole repo, balanced, standard sweep. don't interrogate.

## Delegation
spawn the **repo-triage** agent via the task tool:

```
task(context="<repo root + constraints + report shape>",
    tasks=[{ agent: "repo-triage",
             task: "<self-contained assignment>",
             solutionSpace: "<how open-ended the read is>" }])
```

- `context` (shared contract): repo root as an absolute path or explicit cwd; the read-only constraint — the agent never edits, installs, builds, or commits anything; and the report shape (the six sections under "done looks like"). the agent already carries omp config conventions via its autoloaded `omp-setup` skill — don't re-explain them, just note if the repo is omp-related so it reads config with the right eyes.
- `task` (self-contained): scope (paths or "whole repo"), focus bias, user context flags, and any area the user fears most. the agent has no conversation history — pack everything it needs.
- `solutionSpace`: the method is fixed (standard triage sweep); what counts as a top finding is the agent's judgment. example: "standard sweep; severity calls and what makes the rot list are open judgment; no fixes proposed beyond one-line pointers."

## Done looks like
one triage report in the agent's reply — no files written to the repo:
- **what this is** — one-paragraph purpose + stack.
- **map** — layout, entry points, where the real code lives.
- **run it** — build/test/run commands as found in the repo, flagged if unverified.
- **state** — test shape, CI, obvious gaps.
- **rot list** — top findings ranked, each with a `file:line` pointer and one line on why it matters.
- **first moves** — ≤5 suggested next actions, not implementations.

if the agent returns questions instead (missing scope), collect the answers and re-spawn.

## Anti-jobs
- never scan the repo inside this skill's own session — delegate, always.
- the pair triages; it doesn't fix. no refactors, no dependency bumps, no "while i was in there".
- no new files in the target repo — not even a TRIAGE.md unless the user asks for one.
- don't re-interview once the job is clear; bias to act.
