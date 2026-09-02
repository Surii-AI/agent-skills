# Final branch review assignment

Review the completed integration branch against the specification and all ticket contracts. Remain read-only and do not delegate.

## Inputs

- Integration workspace: `{{integration_workspace}}`
- Original base: `{{base_sha}}`
- Integration head: `{{integration_head}}`
- Specification: `{{spec_path}}`
- Ticket index: `{{ticket_index_path}}`
- Ticket reports and reviews: `{{evidence_paths}}`
- Consolidated diff package: `{{diff_package_path}}`
- Final review output: `{{final_review_path}}`

## Review method

1. Read the specification, normalized ticket index, evidence files, and complete branch diff.
2. Confirm that every ticket is integrated and every acceptance criterion is satisfied or explicitly ruled out.
3. Check cross-ticket behavior, integration seams, security, migrations, public interfaces, release/build behavior, and untested failure paths.
4. Distinguish pre-existing problems and optional improvements from regressions introduced by this branch.
5. Run a targeted command only when the recorded evidence leaves a material doubt. Do not repeat passing suites merely for ceremony.
6. Write one consolidated review. Prefer one coherent fix wave over one fixer per finding.

## Return contract

```text
VERDICT: PASS | CHANGES_REQUESTED | BLOCKED
BLOCKING_FINDINGS: <count>
REVIEW: {{final_review_path}}
SUMMARY: <one line>
```
