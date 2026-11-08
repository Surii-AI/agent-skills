---
name: commit-scribe
description: Turns "I'm done with changes" into a finished git commit by delegating to the commit-scribe agent. Use when the user says "I'm done with changes", "done with my changes", "changes are done", "i'm finished, commit it", "wrap up my changes", "write the commit message", or otherwise signals work is complete and wants a commit message. Pairs with the commit-scribe agent, which owns crafting the message.
---

# commit-scribe

this skill owns the conversation: catch the "done with changes" moment, confirm there's actually something to commit, collect the two preferences that matter, then hand the whole job to the **commit-scribe** agent in a fresh context. the skill never writes the message itself.

## When this triggers
- "i'm done with changes" / "done with my changes" / "changes are done"
- "i'm finished, commit it" / "wrap up my changes" / "commit this"
- "write the commit message" / "what should the commit message be"
- not a bare "i'm done" with no changes context (user may mean something else) — if ambiguous, one quick confirm, then move on.

## Before delegating
run, don't ask:
- `git status --porcelain` and `git diff HEAD --stat` in the current repo.
- clean tree → tell the user there's nothing to commit and stop. no spawn.

interview — only what can't be inferred, at most two questions:
1. scope: the whole working tree (default) or specific paths?
2. commit or draft-only: should the agent commit with the message, or just return the message text? ask once, remember the answer for the session.

never ask about style or emoji — the no-emoji rule is fixed below and house style comes from the repo's own git log.

## Delegation
spawn the **commit-scribe** agent via the task tool:

```
task(context="<shared contract>",
     tasks=[{ agent: "commit-scribe",
              task: "<self-contained assignment>",
              solutionSpace: "<how open-ended the work is>" }])
```

- `context`: goal (commit message for the repo at the current absolute path); hard constraints — zero emoji or decorative unicode in the message, no code changes, no push/amend/rebase, message style follows the repo's recent git log; the return contract (message text + whether it committed).
- `task`: everything the agent needs with no conversation history — repo root, in-scope paths, commit-vs-draft decision, and instruction to inspect the diff and recent log, craft the message, then commit (scoped `git add` only) or return the message. if a required preference is missing it returns questions instead of guessing.
- `solutionSpace`: one fix — the message derives from the actual diff; wording is open but format and voice are pinned by the repo log and the no-emoji rule.

## Done looks like
- a commit message exists: imperative subject ≤72 chars, optional body that explains why — zero emoji.
- either committed (agent reports `git log -1 --stat` proof) or returned as exact text for the user.
- report names which files it inspected; repo is otherwise untouched — no push, no amend, no edits outside the commit itself.

## Anti-jobs
- never lets emoji or decorative unicode into a commit message. non-negotiable, overrides any house style.
- never writes or polishes the message in-session; the commit-scribe agent owns crafting.
- never spawns when the working tree is clean.
- never pushes, amends, rebases, or stages anything outside the agreed scope.
