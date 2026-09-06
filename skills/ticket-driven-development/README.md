# ticket-driven-development

Execute an approved specification through dependency-linked Markdown tickets — bounded fresh workers, adaptive isolated concurrency, risk-based review, deterministic Git integration, resumable run state.

Install:

```bash
npx skills add <owner>/agent-skills --skill ticket-driven-development
```

Invoke explicitly in a supported agent:

```
/skill:ticket-driven-development  on  <repo>/.scratch/<phase>/issues
```

The skill **executes** tickets; it refuses to author them. Ticket format: see `references/ticket-format.md` after install (or `skills/ticket-driven-development/references/ticket-format.md` here). Minimal ticket:

```markdown
# 01: Money arithmetic library
**What to build:** ...one paragraph...
**Blocked by:** None
**Status:** ready-for-agent
- [ ] Acceptance criterion
```

## Requirements

The skill is stack-agnostic — checkpoints are discovered from the repository's own tooling (CI workflows, package scripts, task runners), never assumed. It needs:

- **Git** — the run is built on worktrees and an integration branch.
- **Python 3.9+** on `PATH` as `python3` — the bundled scripts use only the standard library.
- **Local Markdown tickets** in the accepted format, with English status keywords (`done`, `complete`, …).
- **Optional:** a subagent/task API in the host agent for parallel waves; without one, the skill falls back to sequential execution in the controller with all gates intact.

Design and benchmark evidence: 18/18 assertion passes across 4 evals vs the prior version; per-ticket pipelined scheduling measured 33% faster wall time on the 4-ticket reference graph with zero assertion loss.
