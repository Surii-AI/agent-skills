---
name: done-with-changes
description: Commit time. Use when the user signals the current changes are finished — "I'm done", "done with changes", "ready to commit" — or asks for the commit message. Gather the git state, then hand off to the commit-scribe agent.
---

The user has finished a change and wants its commit message written. Gather the git state, dispatch the `commit-scribe` agent, and present the returned message. Do not write the message yourself.

## 1. Gather the git state

Run in the repository the user means (their working directory unless they name another):

- `git rev-parse --is-inside-work-tree` — fails: say this is not a git repository and stop.
- `git status --porcelain` — empty: there is nothing to commit; say so and stop.
- `git diff --cached --stat` and `git diff --stat` — pick the scope: something staged means staged-only; otherwise the working tree.
- `git diff --cached` or `git diff` for that scope — the change itself. Too large to pass inline: summarize it faithfully — files touched, intent, notable mechanics — and say in the hand-off that it is a summary.
- `git log --oneline -15` — the repository's message style, for commit-scribe to match.

Done when you hold the scope, the change (or its summary), and the style sample.

## 2. Hand off to commit-scribe

Dispatch one `task` call with `agent: "commit-scribe"`. The `task` text carries everything the agent cannot see: repository root, the scope, the diff or summary, the recent-log sample. `solutionSpace` describes the change in one line; the wording of the message is the only open choice.

Present the returned message to the user verbatim in a fenced code block.

## 3. Commit only on request

The deliverable is the message. Run `git commit` with it only when this request asked for the commit (e.g. "done with changes, commit it"): staged-only scope commits as staged; working-tree scope commits what the user's instruction covers, staging nothing extra on your own.
