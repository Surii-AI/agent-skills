---
name: pkg-vetting
description: Runs due diligence on npm packages before you adopt them — license, maintenance, last release, red flags — and returns an adopt/caution/avoid verdict. Use when the user says "should i use package X", "is X still maintained", "when did X last release", "vet this npm package", "any red flags in X", "safe to adopt X?", "deep-dive this package before i add it", "due diligence on X", or names an npm package with "before i adopt/switch/add". Pairs with the pkg-scout agent.
---

# pkg-vetting

This skill owns the conversation: it catches "should i use X" style asks, interviews for the context that actually changes the verdict, then hands the whole dossier to the **pkg-scout** agent via the task tool. The skill never researches packages itself — that's the agent's isolated job.

## When this triggers
- "should i use <pkg>?" / "is <pkg> safe to adopt?"
- "is <pkg> still maintained?" / "when did <pkg> last release?"
- "vet <pkg>" / "due diligence on <pkg>" / "deep-dive <pkg> before i commit to it"
- "any red flags in <pkg>?" / "why is everyone dropping <pkg>?"
- "i'm torn between <pkg-a> and <pkg-b>" (vet both, compare)

## Interview
One round, only what changes the verdict, then delegate:
1. which package(s), and pinning? — exact version, semver range, or "latest"
2. where does it run? — node backend, browser bundle, edge, or cli (changes what "heavy" and "risky" mean)
3. dealbreakers? — license policy (e.g. "no GPL"), "nothing below 1.0", "last release within 12 months", "no install scripts", bundle-size cap
Skip anything already answered. If the user just drops a package name and nothing else, do NOT stall: assume latest, general node+browser use, no stated dealbreakers, and say those assumptions in the handoff.

## Delegation
Spawn the **pkg-scout** agent via the task tool:
- `context`: the shared contract — "due diligence on npm package(s) before adoption. Verdict-first report with fixed sections: license, maintenance, last release, red flags, bottom line. Research only — never install the package or write adoption code. Cite the source of every claim (registry JSON, repo, advisory DB)."
- `task`: the self-contained assignment — package name(s) + version pin if any, where it runs, the user's dealbreakers, and depth (quick screen vs full deep-dive). pkg-scout has no conversation history, so everything it needs goes here.
- `solutionSpace`: "open-ended research — the findings are unknown up front; only the report format is fixed by the context contract."

Vetting two packages to compare = ONE spawn with the comparison named in `task`, not two.

## Done looks like
A verdict-first report the user can act on: adopt / caution / avoid up top with a one-line reason, then license (plus conflict risk), maintenance signals (commit/release cadence, issue pileup, maintainer bus factor), last release date, an explicit red-flags list ("none found" if clean), and a bottom line tied to the user's stated dealbreakers. Every claim has a source.

## Anti-jobs
- never installs the package or scaffolds adoption code — research only
- no generic "best npm packages for X" listicles — this fires for a named package
- doesn't dump raw npmjs.com stats at the user — pkg-scout distills
- doesn't keep interviewing when only a package name was given
