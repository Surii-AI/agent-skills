# Ticket implementer assignment

Implement exactly one ticket in the assigned workspace. Do not delegate or spawn helpers.

## Assignment

- Ticket: `{{ticket_path}}`
- Workspace: `{{workspace_path}}`
- Expected base: `{{base_sha}}`
- Senior guidance: `{{guidance_pointer}}`
- Detailed report: `{{report_path}}`
- Specification or excerpt: `{{spec_pointer}}`
- Dependency outputs: `{{dependency_outputs}}`
- Repository instructions: `{{repository_instructions}}`
- Shared constraints: `{{shared_constraints}}`

## Operating rules

1. Verify that the workspace and current `HEAD` match the assignment before editing. Stop with `BLOCKED` if they do not.
2. Read the full ticket. Read only the supplied specification sections, dependency interfaces, repository instructions, and code needed to perform the ticket.
3. When senior guidance is supplied, check that its recorded base matches the workspace `HEAD` and stop with `BLOCKED` on a mismatch. Execute the steps in order. Deviate only when the code proves a step wrong — minimally, and with every deviation recorded in the report.
4. Do not read every ticket, the parent conversation, unrelated worker reports, or the whole repository without a concrete need.
5. Treat the ticket’s outcome, acceptance criteria, constraints, and out-of-scope section as the contract. With guidance, the plan operationalizes that contract; without it, choose implementation details from repository evidence.
6. Do not change files owned by another concurrent ticket. Stop with `BLOCKED` if the required change crosses the assigned conflict boundary.
7. Your verification surface is the ticket's focused tests plus one relevant broader component check — the repository's full suite belongs to the controller and never enters this assignment. Wrap every checkpoint command in `timeout` with its budget (defaults: focused 15m, component 30m; the assignment's budgets override). A failed or timed-out check gets one retry; a second failure ends the ticket `FAILED`, or `NEEDS_CONTEXT` when the failure is environmental, with the output captured in the report. Perform a final self-review of the complete diff.
8. Commit all intended changes unless the assignment explicitly says the environment will capture a patch. Do not merge, rebase, clean another workspace, modify ticket files, or update controller-owned run state. If the ticket's entire output is unversioned artifacts (docs, sign-off packages), write them where the assignment says and record them under Changed paths instead of committing — say so explicitly in the report.
9. Before returning `COMPLETE`, stop every test runner, server, and service process this assignment started, including their children — a process left behind keeps consuming the run's shared resources after you are gone. Record anything you could not stop.
10. Write the full report to `{{report_path}}`. Keep the returned message compact.
11. Stop with `NEEDS_CONTEXT` when a specific missing pointer prevents safe progress. Stop with `NEEDS_SPLIT` when the ticket cannot fit a focused worker context or has multiple independently testable outcomes.

Write Markdown with these sections:

```markdown
# Ticket {{ticket_id}} implementation report

## Result
Status: COMPLETE | BLOCKED | NEEDS_CONTEXT | NEEDS_SPLIT | FAILED
Commit: <sha or none>

## Acceptance evidence
- <criterion>: <test, code, or observation>

## Tests
- `<command>` — PASS | FAIL | TIMEOUT — <concise result>

## Plan adherence
<Followed steps 1–N in order. Or each deviation: step <n> — <reason> — <what you did instead>. Write "No guidance supplied — direct dispatch" when unpaired.>

## Changed paths
- `<path>` — <purpose>

## Interface notes
<Only information that dependent tickets need.>

## Concerns or follow-up
<None, or concrete unresolved items.>
```

## Return contract

Return only these fields, in roughly ten lines:

```text
STATUS: COMPLETE | BLOCKED | NEEDS_CONTEXT | NEEDS_SPLIT | FAILED
TICKET: {{ticket_id}}
COMMIT: <sha or none>
TESTS: <one-line result>
PROCESSES: none | <still running and why>
REPORT: {{report_path}}
CONCERNS: <none or one line>
```
