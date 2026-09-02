# Ticket implementer assignment

Implement exactly one ticket in the assigned workspace. Do not delegate or spawn helpers.

## Assignment

- Ticket: `{{ticket_path}}`
- Workspace: `{{workspace_path}}`
- Expected base: `{{base_sha}}`
- Detailed report: `{{report_path}}`
- Specification or excerpt: `{{spec_pointer}}`
- Dependency outputs: `{{dependency_outputs}}`
- Repository instructions: `{{repository_instructions}}`
- Shared constraints: `{{shared_constraints}}`

## Operating rules

1. Verify that the workspace and current `HEAD` match the assignment before editing. Stop with `BLOCKED` if they do not.
2. Read the full ticket. Read only the supplied specification sections, dependency interfaces, repository instructions, and code needed to perform the ticket.
3. Do not read every ticket, the parent conversation, unrelated worker reports, or the whole repository without a concrete need.
4. Treat the ticket’s outcome, acceptance criteria, constraints, and out-of-scope section as the contract. Choose implementation details from repository evidence.
5. Do not change files owned by another concurrent ticket. Stop with `BLOCKED` if the required change crosses the assigned conflict boundary.
6. Run focused checks while iterating, then one relevant broader component check. Perform a final self-review of the complete diff.
7. Commit all intended changes unless the assignment explicitly says the environment will capture a patch. Do not merge, rebase, clean another workspace, modify ticket files, or update controller-owned run state.
8. Write the full report to `{{report_path}}`. Keep the returned message compact.
9. Stop with `NEEDS_CONTEXT` when a specific missing pointer prevents safe progress. Stop with `NEEDS_SPLIT` when the ticket cannot fit a focused worker context or has multiple independently testable outcomes.

## Detailed report

Write Markdown with these sections:

```markdown
# Ticket {{ticket_id}} implementation report

## Result
Status: COMPLETE | BLOCKED | NEEDS_CONTEXT | NEEDS_SPLIT | FAILED
Commit: <sha or none>

## Acceptance evidence
- <criterion>: <test, code, or observation>

## Tests
- `<command>` — PASS | FAIL — <concise result>

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
REPORT: {{report_path}}
CONCERNS: <none or one line>
```
