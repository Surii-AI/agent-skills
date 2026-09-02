# Integration conflict assignment

Resolve only the demonstrated conflict between the supplied ticket commits. Do not delegate and do not redesign unrelated code.

## Inputs

- Integration workspace: `{{integration_workspace}}`
- Integration head before conflict: `{{integration_head}}`
- Incoming commit or branch: `{{incoming_ref}}`
- Conflicting tickets: `{{ticket_paths}}`
- Worker reports: `{{report_paths}}`
- Conflict evidence: `{{conflict_evidence_path}}`
- Resolution report: `{{resolution_report_path}}`

## Operating rules

1. Confirm the repository is in the expected conflict state or reproduce the conflict with a non-destructive Git operation.
2. Read both ticket contracts and their interface notes. Preserve every compatible acceptance criterion.
3. Change only files necessary to resolve the conflict or the semantic incompatibility it exposed.
4. Run focused checks for both tickets plus the relevant integration smoke check.
5. Commit the resolution on the integration branch. Do not rewrite ticket branches or discard either side without recording why.
6. Write the detailed resolution evidence to `{{resolution_report_path}}`.

## Return contract

```text
STATUS: RESOLVED | BLOCKED | FAILED
COMMIT: <sha or none>
TESTS: <one-line result>
REPORT: {{resolution_report_path}}
DECISION: <one-line description of the compatibility choice>
```
