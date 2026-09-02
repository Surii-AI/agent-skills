# Ticket review assignment

Review one implemented ticket. Remain read-only and do not delegate.

## Inputs

- Ticket: `{{ticket_path}}`
- Risk: `{{risk}}`
- Implementation report: `{{report_path}}`
- Review package: `{{diff_package_path}}`
- Specification or excerpt: `{{spec_pointer}}`
- Repository instructions: `{{repository_instructions}}`
- Review output: `{{review_output_path}}`

## Review method

1. Read the ticket, report, and complete packaged diff. Follow precise specification pointers only when needed to resolve the contract.
2. Verify every acceptance criterion against concrete evidence in the diff and report.
3. Inspect for correctness, regressions, security or concurrency hazards, public-contract drift, missing tests, and violations of repository instructions.
4. Keep scope proportional to risk. Do not crawl the entire repository or repeat the full suite without a concrete doubt. Run only a targeted command required to confirm or refute a suspected defect.
5. Separate merge-blocking findings from nonblocking observations. Do not request unrelated cleanup or stylistic churn.
6. Write the detailed review to `{{review_output_path}}` and return only the compact verdict contract.

## Detailed review

```markdown
# Ticket {{ticket_id}} review

## Verdict
PASS | CHANGES_REQUESTED | BLOCKED

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

## Return contract

```text
VERDICT: PASS | CHANGES_REQUESTED | BLOCKED
TICKET: {{ticket_id}}
BLOCKING_FINDINGS: <count>
REVIEW: {{review_output_path}}
SUMMARY: <one line>
```
