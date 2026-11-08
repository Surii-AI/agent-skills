---
name: pkg-scout
description: Deep-dive vetting of npm packages before adoption — license, maintenance and release cadence, downloads trend, repo health, install-script and supply-chain red flags, alternatives, and an ADOPT / ADOPT WITH GUARDRAILS / AVOID / INSUFFICIENT DATA verdict. Use whenever the user is about to adopt or choose an npm package, asks whether a package is maintained, safe, or trustworthy, asks to vet, audit, deep-dive, or evaluate a dependency, asks about a package's license or maintainers, or compares npm packages as candidates — even if they never say "vet" or "scout".
---

# pkg-scout

Vetting workflow for npm packages the user is considering adopting. Produce a grounded verdict — license, maintenance, health, red flags, alternatives, recommended usage — based only on evidence fetched now, never on training-data memory of "what this package is like". Packages rot and get hijacked; a cached impression is worse than no answer.

## Workflow

1. **Pin down what's being vetted.** Exact package name (scoped: `@scope/pkg`), plus the version the user would actually adopt — latest unless they pinned one. The use case (role it fills, runtime/node version, license constraints) sharpens the verdict; don't interrogate the user — if the request comes from inside a codebase, read its `package.json` for the intended version range and neighbors, otherwise mark context as not provided.

2. **Delegate the legwork to the `pkg-scout` agent.** One task per package, all packages in a single batch (parallel). The agent carries its own methodology — this skill is autoloaded into it — so the brief only needs facts:

   ```json
   {
     "context": "Shared use case and constraints, if any.",
     "tasks": [
       {
         "agent": "pkg-scout",
         "task": "Vet npm package <name>[@<version>] for adoption. Context: <what it's for, license/runtime constraints, intended version range>.",
         "solutionSpace": "One package, fixed procedure; findings are whatever the fetches show."
       }
     ]
   }
   ```

   The agent returns the report as its final message and makes no edits. If `pkg-scout` is not in the task tool's agent list (agent file not installed), run the procedure below inline instead.

3. **Inline mode** (no task tool, or a quick in-session look): execute the Procedure yourself and emit the same report template.

4. **Synthesize.** Present each report as-is. For two or more packages, add a comparison table on top:

   | package | verdict | license | last publish | weekly downloads | biggest red flag |
   |---|---|---|---|---|---|

   Never soften or inflate a verdict, and never let a summary contradict its report. If evidence conflicts, re-run the specific check or surface the conflict explicitly.

5. **Offer the usual follow-ups:** alternatives shortlist for a rejected package, exact-pin/lockfile advice, `npm overrides` / `npm audit` suggestions.

## Procedure

### Ground rules

- **Read-only.** No `npm install`, no `npx`, nothing executed from the package or its tarball. Vetting is metadata and archive inspection only.
- **Unauthenticated fetches only.** npm registry, npm downloads API, GitHub API, `npm view`, and web search. No tokens. GitHub unauthenticated allows ~60 req/hr per IP — budget at most ~5 repo calls per package; on 403/429 record `[rate-limited]` and move on, never retry-spam.
- **Evidence over recall.** Every claim cites a fetch made during this task, with its date. A failed fetch or missing field is `[UNKNOWN — reason]`, never a guess.
- **Distrust marketing.** README claims about tests, CI, or maintenance are checked against the actual repo and tarball, not repeated.

### Data sources

| What | How |
|---|---|
| Latest version, license, deprecation | `npm view <pkg> version license deprecated --json` |
| Publish timeline (created / modified / per-version dates) | `npm view <pkg> time --json` |
| Maintainers | `npm view <pkg> maintainers --json` |
| Version list / cadence | `npm view <pkg> versions --json` |
| Full latest manifest (scripts, bin, files, engines, deps, funding) | `curl -s https://registry.npmjs.org/<pkg>/latest` |
| Compact per-version metadata (dist, signatures, sizes, deprecations) | `curl -s -H "Accept: application/vnd.npm.install-v1+json" https://registry.npmjs.org/<pkg>` — prefer over the full packument for large packages |
| Tarball without installing | `curl -sL "$(npm view <pkg>@<ver> dist.tarball)" -o /tmp/<name>.tgz && tar -tzf /tmp/<name>.tgz` — and `tar -xzOf /tmp/<name>.tgz package/package.json` for the packed manifest |
| Weekly downloads | `curl -s https://api.npmjs.org/downloads/point/last-week/<pkg>` |
| Downloads trend (bucket monthly) | `curl -s https://api.npmjs.org/downloads/range/last-year/<pkg>` |
| Repo status | `curl -s https://api.github.com/repos/<owner>/<repo>` (strip `git+` and `.git` from `repository.url`) → `archived`, `pushed_at`, `open_issues_count` (includes PRs), `license`, `stargazers_count` |
| Recent commit activity | `curl -s "https://api.github.com/repos/<owner>/<repo>/commits?per_page=5"` |
| Incidents / advisories | `web_search` for `<pkg> npm advisory OR hijack OR malicious OR deprecated` |

### Checks

Run all of them. Each finding lands in the report with its severity and the evidence that produced it.

**Hard stops — HIGH**

- Latest version carries a `deprecated` message — quote it verbatim.
- Install lifecycle scripts (`preinstall` / `install` / `postinstall` / `prepare`) that exec, curl/wget, eval, or decode blobs. Cosmetic scripts (echo, copying files) are fine but say what they do.
- License absent, `UNLICENSED`, or incompatible with the user's constraint (e.g. GPL family where permissive is required). Cite the SPDX id from the latest manifest.
- Repository URL resolves to nothing (404 / renamed) while the package implies active hosting.

**Care — MEDIUM**

- No publish in ≥18 months, or cadence collapsed (was monthly, now silent) — cross-check open issues and advisories before concluding abandonment.
- Single maintainer (bus factor), or the maintainer set recently changed on an old package — the classic account-takeover pattern (event-stream, ua-parser-js). Compare first-publish date against current maintainer handles.
- Wide production-dependency surface (>20 direct deps): each is attack surface. Report the count; don't recurse the tree.
- License flipped between versions users sit on and latest (e.g. MIT → non-permissive rug-pull).
- Downloads collapsing against the year-ago trend; a prerelease tag sitting in `latest`.
- Typosquat shape: name within a typo of a popular package, created recently, low downloads.
- No test files in the tarball, or unpacked size wildly out of proportion to the stated purpose.

**Weak signals — LOW** (mention, don't doom)

- No npm provenance/signature on `dist` — common and acceptable for pre-2023 publishes, a real gap for brand-new ones.
- No CHANGELOG, sparse README, stale-looking issue count (remember it includes PRs).

Record healthy signals too — steady cadence, multiple maintainers, org-backed repo, provenance, permissive license — so the verdict has both sides.

### Verdicts

- **ADOPT** — compatible license, credible maintenance, no install-script surprises, checks pass.
- **ADOPT WITH GUARDRAILS** — usable, with named mitigations: pin the exact version and commit the lockfile (`npm ci`), `--ignore-scripts` if scripts are cosmetic-but-unexplained, watch advisories, plan an exit to a maintained alternative.
- **AVOID** — any HIGH flag not disproven: deprecation, hostile or obfuscated install scripts, missing/incompatible license, hijack evidence.
- **INSUFFICIENT DATA** — too young/quiet to judge, or fetches failed. List exactly which checks are missing and what would resolve them. Registry 404 also lands here, with near-miss name suggestions.

### Report template

Exactly one per package:

```md
# <name> — adoption report

**Verdict: <ADOPT | ADOPT WITH GUARDRAILS | AVOID | INSUFFICIENT DATA>** — <one-line why>

- Reviewed: `<name>@<version>` (published <date>) · checked <YYYY-MM-DD>
- Context: <use case & constraints, or "not provided">

## License
<SPDX · permissive / copyleft / absent · compatibility note>

## Maintenance
Last publish <age> · <n> versions · cadence <pattern> · maintainers: <handles> · bus factor <ok / low>

## Health & adoption
<last-week> weekly downloads (<trend> vs year ago) · repo <active / archived / stale / 404> · <n>★ · <n> open issues+PRs · unpacked <size> / <fileCount> files

## Red flags
- **[HIGH]** <finding> — evidence: <value, source, date>
- **[MEDIUM]** …
- **[LOW]** …

`None found` when clean — never leave this section implicit.

## Install & dependency surface
<n> prod deps · scripts: <none | what they do> · native build <yes / no> · provenance <yes / no> · engines <note>

## Alternatives
<0–3 credible alternatives, one line each on the tradeoff>

## Recommended usage
<pinning, install flags, monitoring, follow-up checks — or "none needed">

## Sources
<endpoints/commands actually used, each with its fetch date>
```
