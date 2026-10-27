---
name: omp-setup
description: Configure Oh-My-Pi (omp) for multi-agent work by selecting the default and existing named profiles and setting task.maxRecursionDepth (default 4) with confirmation and verification. Use this skill whenever the user asks to set up, prepare, or tune omp for multi-agent orchestration, nested subagents, agent teams, or recursion depth across profiles, even if they do not name this skill.
---

# omp-setup Skill

Configure Oh-My-Pi (`omp`) for multi-agent work by selecting the default and existing named profiles and setting `task.maxRecursionDepth` (default 4) with confirmation and verification. Use this skill whenever the user asks to set up, prepare, or tune omp for multi-agent orchestration, nested subagents, agent teams, or recursion depth across profiles, even if they do not name this skill.

## Contract

This skill reads existing named profiles and configures `task.maxRecursionDepth` across profiles. It never writes to unrelated settings, does not modify project or credential files, and never relies on `PI_CODING_AGENT_DIR` for profile discovery. Depth accepts only non-negative integers (`0`, `1`, `2`, …). Negative and unlimited values are rejected as outside the skill's contract.

## Workflow

### 1. Preflight

Verify prerequisites without writing:
- Require `omp` executable in PATH.
- Run `omp --profile default config get task.maxRecursionDepth --json`.
- If OMP or the key is unavailable, report prerequisite failure and stop.
- Do not read or modify project settings, credentials, model settings, agent definitions, or unrelated keys.

### 2. Enumerate Existing Named Profiles

Resolve home directory and config-root from the environment (`HOME`, `PI_CONFIG_DIR`; default `.omp`). Read `<HOME>/<PI_CONFIG_DIR>/profiles` and list immediate child directories as named profiles. A missing directory means there are no named profiles. Do not create a requested-but-missing profile. Do not infer named-profile paths from `PI_CODING_AGENT_DIR`.

### 3. Collect Profile Choices

- The `default` profile is mandatory and is not a checkbox.
- Ask which named profiles to add, with none preselected. An empty selection means default-only.
- Use two-option include/skip for one discovered profile and multi-select questions for two or more, batching options at five per question.
- If the invocation already gives a valid selection (e.g., `default and work` or `all existing profiles`), honor it without asking.
- Reject unknown names rather than creating them.

### 4. Collect and Validate Depth

- Ask for `task.maxRecursionDepth` with recommended default `4`. Offer `2` and `6` as additional choices. Allow a custom answer.
- Accept only decimal non-negative integers (`0`, `1`, `2`, …).
- If the invocation already supplies a valid depth, use it without re-asking.
- For an invalid value, request a valid one. If no interactive answer is available, stop with no writes.
- Explain that the value caps task-subagent nesting and that `0` prevents the main agent from spawning task subagents.
- Do not accept OMP's supported negative/unlimited values because this skill's contract intentionally excludes them.

### 5. Preview and Confirm

For each selected profile, read the current value using `omp --profile <name> config get task.maxRecursionDepth --json`, using the literal profile name `default` for the default profile. Present a table of profile, current value, and requested value. Include the zero-depth warning when applicable. Ask Apply/Cancel before the first write. Cancellation makes no changes. If every selected profile already has the requested effective value, report that no write is needed and skip confirmation.

### 6. Write Only the Requested Key

Apply in deterministic order: `default` first, then selected named profiles sorted by name. For each profile whose current effective value differs, run `omp --profile <name> config set task.maxRecursionDepth <depth> --json`. Pass each profile as one literal CLI argument; never evaluate profile text as shell syntax. Use the CLI instead of editing YAML or using session-only settings writes so existing `config.yml`/`config.yaml` files and unrelated settings retain OMP's normal persistence semantics.

### 7. Verify Each Write Immediately

Run the corresponding `config get ... --json` and require the returned `value` to equal the requested integer. A successful save whose effective value remains different is not success: report the override named by the CLI and do not edit project files, overlays, environment variables, or runtime state to force it. On a failed write or verification, stop before unattempted profiles and report successful, failed, and unattempted profiles separately. Do not claim the multi-profile setup is complete and do not attempt an unrequested rollback.

### 8. Report the Result

Return a compact per-profile table with previous, requested, and verified effective values plus status (`unchanged`, `updated`, `already configured`, or `failed`). State that the persisted value applies to subsequent subagent launches and does not restart running subagents. Never print credentials or dump the full config.
