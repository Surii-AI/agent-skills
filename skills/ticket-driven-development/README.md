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

Design and benchmark evidence: 18/18 assertion passes across 4 evals vs the prior version; per-ticket pipelined scheduling measured 33% faster wall time on the 4-ticket reference graph with zero assertion loss.
