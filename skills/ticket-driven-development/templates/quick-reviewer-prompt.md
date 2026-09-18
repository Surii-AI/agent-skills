# Quick ticket review assignment

Quick review of one low-risk, direct-dispatch ticket. Remain read-only, never delegate, and never run the full suite — this is a fast decisive check against the acceptance criteria, not a deep audit.

## Inputs

- Ticket: `{{ticket_path}}`
- Implementation report: `{{report_path}}`
- Review package: `{{diff_package_path}}`
- Specification or excerpt: `{{spec_pointer}}`
- Dependency outputs: `{{dependency_outputs}}`
- Repository instructions: `{{repository_instructions}}`
- Guidance (paired tickets only; context, not a plan judgment): {{guidance_pointer}}
- Review output: `{{review_output_path}}`

## Code locator

{{code_locator}}

## Review method

1. Read the ticket, the implementer's report, and the complete packaged diff. Use the Code locator section's tool for any code lookup rather than crawling.
2. Verify each acceptance criterion against concrete evidence in the diff and report. A criterion with no evidence is NOT PROVEN, not assumed satisfied.
3. Scan the diff for regressions, missing tests, public-contract drift, and violations of repository instructions.
4. When the ticket builds on a blocker, check the diff against the dependency's interface notes — an internally clean diff that breaks its blocker's contract is a blocking finding.
5. Run at most one targeted command, only to confirm or refute a specific suspected defect — never the full suite.
6. Write the detailed review to `{{review_output_path}}` and return only the compact verdict contract.

## Escalate instead of guessing

Return ESCALATE, with the reason named, when:

- The diff is larger or more entangled than a low-risk mechanical change should be.
- An acceptance criterion cannot be verified from the diff, report, or spec excerpt.
- You suspect a design-level, security, concurrency, shared-persistence, or broken-dependency-contract problem that cannot be confirmed cheaply.

A wrong confident verdict costs more than an escalation.

## Detailed review

```markdown
# Ticket {{ticket_id}} quick review

## Verdict
PASS | CHANGES_REQUESTED | BLOCKED | ESCALATE

## Acceptance criteria
- <criterion>: SATISFIED | NOT SATISFIED | NOT PROVEN — <evidence>

## Findings
### Blocking
- [severity] `<path:line>` — <problem, consequence, and required correction>

### Nonblocking
- `<path:line>` — <observation>

## Verification notes
<Commands inspected or run, and why.>
```

If there are no findings in a subsection, write `None`.

## Re-review after repair

When this assignment is a re-review, you additionally receive the prior review file and the repair diff package. Judge only whether each blocking finding is resolved — RESOLVED or UNRESOLVED with evidence — and whether the repair introduced new defects. Do not relitigate accepted nonblocking observations.

## Return contract

```text
VERDICT: PASS | CHANGES_REQUESTED | BLOCKED | ESCALATE
TICKET: {{ticket_id}}
BLOCKING_FINDINGS: <count>
REVIEW: {{review_output_path}}
ESCALATION: <only when ESCALATE — one line naming why the full reviewer is needed; omit otherwise>
SUMMARY: <one line>
```
