# ticket-driven-development

Execute an approved specification through dependency-linked Markdown tickets — bounded fresh workers, senior-guide/junior-implementer pairing, adaptive isolated concurrency, risk-based review, deterministic Git integration, resumable run state.

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

## Pair programming

Medium- and high-risk implementation tickets run as a senior/junior pair: a senior guide (strongest available model) reads the ticket and the code, then writes a bounded, repo-grounded plan shaped by the `i-have-adhd` skill; a junior implementer (fastest write-capable model) executes the plan and records every deviation; one plan-aware review verifies both the plan's soundness and the diff's adherence before integration. Low-risk tickets dispatch directly. A pairing override declared at invocation is authoritative.

## Requirements

The skill is stack-agnostic — checkpoints are discovered from the repository's own tooling (CI workflows, package scripts, task runners), never assumed. It needs:

- **Git** — the run is built on worktrees and an integration branch.
- **Python 3.9+** on `PATH` as `python3` — the bundled scripts use only the standard library.
- **Local Markdown tickets** in the accepted format, with English status keywords (`done`, `complete`, …).
- **The `i-have-adhd` skill** — hard dependency of the guide role; the senior guide shapes every plan by its rules. Unresolvable at preflight, the run stops before dispatch.
- **Optional:** a subagent/task API in the host agent for parallel waves and model-tiered pairing; without one, the skill falls back to sequential execution in the controller with all gates intact.

Design and benchmark evidence, from a measured end-to-end run (4-ticket dependency diamond, live subagent workers, per-phase wall-clock timing): 14/14 contract assertions; parallel implement wave and batched review each ~40% faster than serial; tree-hash smoke elision skipped 3 of 4 checkpoint re-runs; `--quiet` state summaries cut controller-facing script output 44× at 4 tickets and 200×+ at 200 (sub-KiB vs 136,588 B per transition). Script-side numbers are reproducible:

```bash
python3 benchmarks/bench_scripts.py
```
