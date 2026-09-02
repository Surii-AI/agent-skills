# Verification policy

Use this reference when classifying risk, deciding whether a ticket needs independent review, handling review failures, and performing final verification.

## Risk classification

Classify the ticket before dispatch. If evidence spans categories, use the highest applicable risk.

| Risk | Typical changes |
|---|---|
| Low | Small mechanical edits, isolated tests, copy changes, or local refactors with no contract change. |
| Medium | Normal feature behavior, internal interfaces, component state, dependency updates, or moderate data-flow changes. |
| High | Security, authentication, authorization, concurrency, shared persistence, schema migration, public API, build/release infrastructure, destructive operations, or wide cross-cutting changes. |

Treat unknown risk as medium until classified. Treat uncertain security, concurrency, persistence, or release effects as high.

## Service availability preflight

Before the first dispatch, determine whether the repository's checkpoints need external services, using only the repository's own declarations — never an assumed stack:

1. **Discover** the canonical commands from repo tooling: task-runner targets (`justfile`, `Taskfile`), package scripts (`package.json`, `Cargo.toml`, `pyproject.toml`), compose or container configuration, and CI workflows (the service setup steps a CI job runs are the most reliable source of truth).
2. **Skip** the check entirely when those sources show the test suite is self-contained (no service containers, no service-dependent setup steps).
3. **Run** the discovered availability command and record the command plus outcome in run state before dispatching.
4. **Ask the user** only when discovery is ambiguous, multiple conflicting candidates exist, or a check fails — present what you found and let the user pick. Do not invent commands.

When a required service cannot be brought up, either restrict the run to tickets whose checks do not need it or stop and record a ruling before dispatching anything. A worker that cannot run its focused tests will either commit unverified work or grind; both violate the verification contract.

## Required checkpoints

| Checkpoint | Low | Medium | High |
|---|---:|---:|---:|
| Focused tests and self-review | Required | Required | Required |
| Relevant component check before commit | Required | Required | Required |
| Independent ticket diff review | Optional only under the strict skip rule | Required | Required with the strongest appropriate reviewer |
| Integration smoke check | After each integration; gates only that ticket's dependents | After each integration; gates only that ticket's dependents | After every integration, wave-wide barrier before further dispatch |
| Requirements-aware final branch review | Required | Required | Required |
| Full configured suite | Once at branch end unless cheap | Once at branch end | At defined milestones and branch end |

## Strict low-risk review skip

Skip independent ticket review only when all conditions hold:

- The diff is small and mechanical.
- Focused and component checks pass cleanly.
- The worker’s self-review reports no concern.
- The change does not affect a public interface, shared persistence, security, concurrency, build/release behavior, generated contracts, or test infrastructure.
- The diff remains included in the wave review or final branch review.

Record the skip and its reason in the ledger. Ambiguity means review, not skip.

## Review and repair

Give a ticket reviewer the ticket, risk, implementer report, packaged base-to-head diff, relevant specification pointer, and scoped repository instructions. Require evidence tied to acceptance criteria. Do not ask it to rediscover the full codebase or rerun the full suite without a concrete doubt.

Cap ticket repair at two rounds. Follow up with the original worker only when its task-local context and workspace remain valid. Otherwise start a fresh repair worker with the original ticket, implementation report, review file, current integration base, and exact blocking findings.

After each repair, regenerate the diff package and perform a scoped re-review. After two unsuccessful rounds, stop and choose one of these explicitly: split the ticket, route to a more capable model or specialist, record a design decision for the user, or mark the run blocked.

## Final gate

After every ticket is integrated:

1. Package the complete original-base-to-integration-head diff.
2. Run the configured full suite and record exact commands and results.
3. Run one requirements-aware review using `templates/final-review-prompt.md`.
4. If changes are requested, perform one consolidated fix wave and one scoped re-review.
5. Mark the run complete only when Git reachability, tests, and final review all pass.

Do not claim success when a required check was skipped. Report it as unverified with the reason.
