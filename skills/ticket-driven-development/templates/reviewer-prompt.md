# Ticket review assignment

Review one implemented ticket. Remain read-only and do not delegate.

## Inputs

- Ticket: `{{ticket_path}}`
- Risk: `{{risk}}`
- Senior guidance: `{{guidance_pointer}}`
- Implementation report: `{{report_path}}`
- Review package: `{{diff_package_path}}`
- Specification or excerpt: `{{spec_pointer}}`
- Dependency outputs: `{{dependency_outputs}}`
- Repository instructions: `{{repository_instructions}}`
- Review output: `{{review_output_path}}`

## Review method

1. Read the ticket, report, and complete packaged diff. Follow precise specification pointers only when needed to resolve the contract.
2. Verify every acceptance criterion against concrete evidence in the diff and report.
3. When senior guidance exists, judge the plan before the diff: confirm the plan itself satisfies the ticket's contract — a cleanly executed wrong plan is a blocking finding, not a pass. Then confirm adherence: every deviation the implementer recorded must be justified by code evidence. Label each blocking finding `IMPLEMENTATION` (the diff departs from a sound plan) or `PLAN` (the plan itself is unsound, incomplete, or unverifiable) — the label routes repair to the junior or back to the senior guide.
4. Inspect for correctness, regressions, security or concurrency hazards, public-contract drift, missing tests, and violations of repository instructions.
5. When the ticket builds on a blocker's work, check the integration against the dependency's interface notes — a diff that is internally clean but breaks its blocker's contract is a blocking finding.
6. For logic-bearing outputs (arithmetic, parsing, state transitions), prefer an independent oracle over eyeballing: recompute expected results with a small script or property sweep separate from the implementation's own tests. Trust the implementation's tests to verify intent, and your oracle to verify truth.
7. Keep scope proportional to risk. Do not crawl the entire repository or repeat the full suite without a concrete doubt. Run only a targeted command required to confirm or refute a suspected defect.
8. Separate merge-blocking findings from nonblocking observations. Do not request unrelated cleanup or stylistic churn.
9. Write the detailed review to `{{review_output_path}}` and return only the compact verdict contract.

## Detailed review

```markdown
# Ticket {{ticket_id}} review

## Verdict
PASS | CHANGES_REQUESTED | BLOCKED

## Acceptance criteria
- <criterion>: SATISFIED | NOT SATISFIED | NOT PROVEN — <evidence>

## Findings
### Blocking
- [severity][IMPLEMENTATION|PLAN] `<path:line>` — <problem, consequence, and required correction>

### Nonblocking
- `<path:line>` — <observation>

## Verification notes
<Commands inspected or run, and why.>
```

If there are no findings in a subsection, write `None`.

## Re-review after repair

When this assignment is a re-review, you additionally receive the prior review file and the repair diff package (blocker-to-current-head). Judge only whether the blocking findings are resolved and whether the repair introduced new defects; do not relitigate accepted nonblocking observations. Record each prior blocking finding as RESOLVED or UNRESOLVED with evidence. When the repair followed a revised plan, also confirm the revised plan resolves the original `PLAN` finding rather than working around it.

## Return contract

```text
VERDICT: PASS | CHANGES_REQUESTED | BLOCKED
TICKET: {{ticket_id}}
BLOCKING_FINDINGS: <count>
REVIEW: {{review_output_path}}
SUMMARY: <one line>
```
