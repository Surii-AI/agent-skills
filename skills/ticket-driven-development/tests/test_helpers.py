#!/usr/bin/env python3

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_DIR / "scripts"


def run(command: list[str], cwd: Path | None = None, expected: int = 0) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode != expected:
        raise AssertionError(
            f"command returned {result.returncode}, expected {expected}: {' '.join(command)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def git(repo: Path, *args: str) -> str:
    return run(["git", "-C", str(repo), *args]).stdout.strip()


class TicketIndexerTests(unittest.TestCase):
    def test_parses_compact_and_extended_tickets(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            tickets = root / "issues"
            tickets.mkdir()
            (tickets / "01-base.md").write_text(
                """# 01: Establish session boundary

**What to build:** Users receive a stable session.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] Session shape is documented.
""",
                encoding="utf-8",
            )
            (tickets / "02-login.md").write_text(
                """# 02: Add passwordless sign-in

**What to build:** Returning users can sign in with a one-time link.

**Blocked by:** 01: Establish session boundary

**Status:** ready-for-agent

**Risk:** medium

**Conflict domains:** authentication API; session lifecycle

## Acceptance criteria

- [ ] Valid links create a session.

## Context pointers

- `specs/auth.md`
""",
                encoding="utf-8",
            )
            output = root / "index.json"
            run(["python3", str(SCRIPTS / "index_tickets.py"), str(tickets), "--output", str(output)])
            data = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(data["valid"])
            self.assertEqual(data["topological_order"], ["01", "02"])
            self.assertEqual(data["ready_frontier"], ["01"])
            self.assertEqual(data["tickets"][1]["blockers"], ["01"])
            self.assertEqual(data["tickets"][1]["conflict_domains"], ["authentication API", "session lifecycle"])
            self.assertEqual(data["tickets"][1]["context_pointers"], ["specs/auth.md"])

    def test_rejects_cycles(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tickets = Path(temp)
            for ticket_id, blocker in (("01", "02"), ("02", "01")):
                (tickets / f"{ticket_id}-ticket.md").write_text(
                    f"# {ticket_id}: Ticket {ticket_id}\n\n"
                    f"**What to build:** Outcome {ticket_id}.\n\n"
                    f"**Blocked by:** {blocker}\n\n"
                    "- [ ] It works.\n",
                    encoding="utf-8",
                )
            result = run(["python3", str(SCRIPTS / "index_tickets.py"), str(tickets)], expected=2)
            self.assertIn("dependency cycle detected", result.stderr)

    def test_rejects_empty_ticket_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tickets = Path(temp)
            result = run(["python3", str(SCRIPTS / "index_tickets.py"), str(tickets)], expected=2)

    def test_rejects_nested_ticket_layout_with_hint(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tickets = Path(temp)
            nested = tickets / "wave-1"
            nested.mkdir()
            (nested / "01-ticket.md").write_text(
                "# 01: Ticket 01\n\n"
                "**What to build:** Outcome 01.\n\n"
                "**Blocked by:** None\n\n"
                "- [ ] It works.\n",
                encoding="utf-8",
            )
            result = run(["python3", str(SCRIPTS / "index_tickets.py"), str(tickets)], expected=2)
            self.assertIn("no ticket files (*.md) found", result.stderr)
            self.assertIn("exist in subdirectories", result.stderr)
            self.assertIn("01-ticket.md", result.stderr)

    def test_source_complete_status_and_reconcile_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tickets = Path(temp)
            (tickets / "01-done.md").write_text(
                "# 01: Shipped feature\n\n"
                "**What to build:** It works.\n\n"
                "**Blocked by:** None (can start immediately)\n\n"
                "**Status:** implemented\n\n"
                "- [x] It works.\n",
                encoding="utf-8",
            )
            (tickets / "02-followup.md").write_text(
                "# 02: Follow-up\n\n"
                "**What to build:** More of it.\n\n"
                "**Blocked by:** 01 (Shipped feature)\n\n"
                "**Status:** ready-for-agent\n\n"
                "- [ ] More works.\n",
                encoding="utf-8",
            )
            output = tickets.parent / "index.json"
            run(["python3", str(SCRIPTS / "index_tickets.py"), str(tickets), "--output", str(output)])
            data = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(data["valid"])
            # 'implemented' counts as complete: the shipped ticket is never redispatched...
            self.assertNotIn("01", data["ready_frontier"])
            # ...and its dependent's dependency is satisfied.
            self.assertEqual(data["ready_frontier"], ["02"])
            # The completion claim is surfaced for Git reconciliation, not silently trusted.
            self.assertTrue(any("reconcile with Git" in warning for warning in data["warnings"]))
            self.assertTrue(any("'implemented' complete by source status" in warning for warning in data["warnings"]))

    def test_audit_section_status_does_not_corrupt_ticket_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tickets = Path(temp)
            (tickets / "01-audited.md").write_text(
                "# 01: Audited feature\n\n"
                "**What to build:** It works.\n\n"
                "**Blocked by:** None (can start immediately)\n\n"
                "**Status:** implemented\n\n"
                "- [x] It works.\n\n"
                "## Audit findings\n\n"
                "**Status:** partial\n\n"
                "**Evidence:** reviewed in PR #4.\n",
                encoding="utf-8",
            )
            output = tickets.parent / "index.json"
            run(["python3", str(SCRIPTS / "index_tickets.py"), str(tickets), "--output", str(output)])
            data = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(data["valid"])
            self.assertEqual(data["tickets"][0]["status"], "implemented")
            self.assertFalse(any("compound status" in warning for warning in data["warnings"]))

    def test_compound_status_uses_first_component_and_warns(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tickets = Path(temp)
            (tickets / "01-dual.md").write_text(
                "# 01: Dual status\n\n"
                "**What to build:** It works.\n\n"
                "**Blocked by:** None (can start immediately)\n\n"
                "**Status:** shipped\n\n"
                "**Status:** partial\n\n"
                "- [x] It works.\n",
                encoding="utf-8",
            )
            output = tickets.parent / "index.json"
            run(["python3", str(SCRIPTS / "index_tickets.py"), str(tickets), "--output", str(output)])
            data = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(data["tickets"][0]["status"], "shipped")
            self.assertTrue(any("compound status" in warning for warning in data["warnings"]))

    def test_spaced_checkbox_forms_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tickets = Path(temp)
            (tickets / "01-spaced.md").write_text(
                "# 01: Spaced boxes\n\n"
                "**What to build:** It works.\n\n"
                "**Blocked by:** None (can start immediately)\n\n"
                "**Status:** ready-for-agent\n\n"
                "- [ x] First criterion is recorded.\n"
                "- [x ] Second criterion is recorded.\n"
                "- [X  ] Third criterion is recorded.\n",
                encoding="utf-8",
            )
            output = tickets.parent / "index.json"
            run(["python3", str(SCRIPTS / "index_tickets.py"), str(tickets), "--output", str(output)])
            data = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(data["valid"])
            self.assertEqual(data["ready_frontier"], ["01"])
            self.assertEqual(
                data["tickets"][0]["acceptance_criteria"],
                [
                    "First criterion is recorded.",
                    "Second criterion is recorded.",
                    "Third criterion is recorded.",
                ],
            )

    def test_run_state_integrated_blocker_satisfies_dependency(self) -> None:
        import sys

        sys.path.insert(0, str(SCRIPTS))
        try:
            import run_state
        finally:
            sys.path.remove(str(SCRIPTS))
        state = {
            "tickets": {
                "01": {"status": "integrated", "blockers": []},
                "02": {"status": "pending", "blockers": ["01"]},
            }
        }
        ready = run_state.recompute_frontier(state)
        # Regression: 'integrated' previously failed to satisfy a blocker, stranding dependents.
        self.assertEqual(ready, ["02"])
        self.assertEqual(state["tickets"]["02"]["status"], "ready")


class GitHelperTests(unittest.TestCase):
    def make_repo(self, root: Path) -> Path:
        repo = root / "repo"
        repo.mkdir()
        git(repo, "init")
        git(repo, "config", "user.email", "test@example.com")
        git(repo, "config", "user.name", "Test User")
        (repo / ".gitignore").write_text(".runs/\n", encoding="utf-8")
        (repo / "app.txt").write_text("base\n", encoding="utf-8")
        git(repo, "add", ".")
        git(repo, "commit", "-m", "base")
        return repo

    def test_worktree_diff_state_and_reconcile(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = self.make_repo(root)
            worktree = repo / ".runs" / "integration"
            metadata = root / "integration.json"
            branch = "agent/demo/integration"

            run(
                [
                    "python3",
                    str(SCRIPTS / "make_worktree.py"),
                    "--repo",
                    str(repo),
                    "--path",
                    str(worktree),
                    "--branch",
                    branch,
                    "--metadata",
                    str(metadata),
                ]
            )
            self.assertEqual(git(worktree, "branch", "--show-current"), branch)
            base = git(worktree, "rev-parse", "HEAD")

            (worktree / "app.txt").write_text("base\nchange\n", encoding="utf-8")
            git(worktree, "add", "app.txt")
            git(worktree, "commit", "-m", "change")
            head = git(worktree, "rev-parse", "HEAD")

            package = root / "diff.md"
            run(
                [
                    "python3",
                    str(SCRIPTS / "package_diff.py"),
                    "--repo",
                    str(worktree),
                    "--base",
                    base,
                    "--head",
                    head,
                    "--ticket",
                    "01",
                    "--output",
                    str(package),
                ]
            )
            self.assertIn("app.txt", package.read_text(encoding="utf-8"))
            issues = root / "issues"
            issues.mkdir()
            (issues / "01-change.md").write_text(
                "# 01: Change app\n\n**What to build:** App changes.\n\n"
                "**Blocked by:** None\n\n- [ ] Change is visible.\n",
                encoding="utf-8",
            )
            (issues / "02-follow-up.md").write_text(
                "# 02: Use changed app\n\n**What to build:** A dependent behavior uses the change.\n\n"
                "**Blocked by:** 01: Change app\n\n- [ ] Dependent behavior works.\n",
                encoding="utf-8",
            )
            index = root / "ticket-index.json"
            run(["python3", str(SCRIPTS / "index_tickets.py"), str(issues), "--output", str(index)])
            state = root / "state.json"
            ledger = root / "ledger.md"
            run(
                [
                    "python3",
                    str(SCRIPTS / "run_state.py"),
                    "init",
                    "--index",
                    str(index),
                    "--state",
                    str(state),
                    "--ledger",
                    str(ledger),
                    "--repo",
                    str(repo),
                    "--base",
                    base,
                    "--integration-branch",
                    branch,
                    "--integration-worktree",
                    str(worktree),
                ]
            )
            run(
                [
                    "python3",
                    str(SCRIPTS / "run_state.py"),
                    "transition",
                    "--state",
                    str(state),
                    "--ticket",
                    "01",
                    "--status",
                    "implemented",
                    "--branch",
                    branch,
                    "--worktree",
                    str(worktree),
                    "--base-sha",
                    base,
                    "--head-sha",
                    head,
                ]
            )
            result = run(
                ["python3", str(SCRIPTS / "reconcile_run.py"), "--state", str(state), "--apply"]
            )
            report = json.loads(result.stdout)
            self.assertTrue(report["tickets"]["01"]["integrated"])
            updated = json.loads(state.read_text(encoding="utf-8"))
            self.assertEqual(updated["tickets"]["01"]["status"], "integrated")
            # An integrated blocker satisfies its dependents here exactly as a
            # run_state transition would; checkpoint confirmation stays with the
            # controller, so no verified restamp may be required to unlock 02.
            self.assertEqual(updated["ready_frontier"], ["02"])
            self.assertEqual(updated["tickets"]["02"]["status"], "ready")
            self.assertIn("reconciliation", ledger.read_text(encoding="utf-8"))

    def test_worktree_attach_to_existing_branch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = self.make_repo(root)
            branch = "agent/demo/integration"
            run(["python3", str(SCRIPTS / "make_worktree.py"), "--repo", str(repo),
                 "--path", str(root / ".runs/integration"), "--branch", branch,
                 "--metadata", str(root / "first.json")])
            tip = git(repo, "rev-parse", branch)
            git(repo, "worktree", "remove", str(root / ".runs/integration"))

            result = run(["python3", str(SCRIPTS / "make_worktree.py"), "--repo", str(repo),
                          "--path", str(root / ".runs/integration-2"), "--branch", branch,
                          "--metadata", str(root / "attached.json"), "--attach"])
            metadata = json.loads(result.stdout)
            self.assertTrue(metadata["attached"])
            self.assertEqual(metadata["base_sha"], tip)
            self.assertEqual(git(root / ".runs/integration-2", "branch", "--show-current"), branch)

    def test_worktree_attach_requires_existing_branch_and_create_rejects_existing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = self.make_repo(root)
            missing = run(["python3", str(SCRIPTS / "make_worktree.py"), "--repo", str(repo),
                           "--path", str(root / ".runs/wt"), "--branch", "agent/demo/none",
                           "--metadata", str(root / "m.json"), "--attach"], expected=2)
            self.assertIn("branch does not exist", missing.stderr)

            run(["python3", str(SCRIPTS / "make_worktree.py"), "--repo", str(repo),
                 "--path", str(root / ".runs/first"), "--branch", "agent/demo/integration",
                 "--metadata", str(root / "first.json")])
            exists = run(["python3", str(SCRIPTS / "make_worktree.py"), "--repo", str(repo),
                          "--path", str(root / ".runs/second"), "--branch", "agent/demo/integration",
                          "--metadata", str(root / "second.json")], expected=2)
            self.assertIn("--attach", exists.stderr)


    def test_reconcile_cherrypick_evidence_and_artifact_aware_dirty(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = self.make_repo(root)
            integration = repo / ".runs" / "integration"
            child = repo / ".runs" / "t01"
            branch = "agent/demo/integration"
            child_branch = "agent/demo/t01"

            run(
                [
                    "python3",
                    str(SCRIPTS / "make_worktree.py"),
                    "--repo",
                    str(repo),
                    "--path",
                    str(integration),
                    "--branch",
                    branch,
                    "--metadata",
                    str(root / "integration.json"),
                ]
            )
            base = git(integration, "rev-parse", "HEAD")
            run(
                [
                    "python3",
                    str(SCRIPTS / "make_worktree.py"),
                    "--repo",
                    str(repo),
                    "--path",
                    str(child),
                    "--branch",
                    child_branch,
                    "--start",
                    base,
                    "--metadata",
                    str(root / "t01.json"),
                ]
            )

            # A parallel-wave integration: the worker commits on its child branch,
            # and the controller cherry-picks the work, re-committing it under a
            # new SHA that the worker's head cannot prove by ancestry.
            (child / "feature.txt").write_text("feature\n", encoding="utf-8")
            git(child, "add", "feature.txt")
            git(child, "commit", "-m", "feature")
            worker_head = git(child, "rev-parse", "HEAD")
            # Another ticket lands first, so the integration base moves before the
            # cherry-pick — guaranteeing the pick gets a new parent and SHA.
            (integration / "tweak.txt").write_text("tweak\n", encoding="utf-8")
            git(integration, "add", "tweak.txt")
            git(integration, "commit", "-m", "tweak")
            git(integration, "cherry-pick", worker_head)
            pick = git(integration, "rev-parse", "HEAD")
            self.assertNotEqual(worker_head, pick)

            issues = root / "issues"
            issues.mkdir()
            (issues / "01-feature.md").write_text(
                "# 01: Feature\n\n**What to build:** A feature lands.\n\n"
                "**Blocked by:** None\n\n- [ ] It works.\n",
                encoding="utf-8",
            )
            (issues / "02-follow-up.md").write_text(
                "# 02: Follow-up\n\n**What to build:** A dependent behavior.\n\n"
                "**Blocked by:** 01: Feature\n\n- [ ] It works.\n",
                encoding="utf-8",
            )
            index = root / "ticket-index.json"
            run(["python3", str(SCRIPTS / "index_tickets.py"), str(issues), "--output", str(index)])
            state = root / "state.json"
            ledger = root / "ledger.md"
            run(
                [
                    "python3",
                    str(SCRIPTS / "run_state.py"),
                    "init",
                    "--index",
                    str(index),
                    "--state",
                    str(state),
                    "--ledger",
                    str(ledger),
                    "--repo",
                    str(repo),
                    "--base",
                    base,
                    "--integration-branch",
                    branch,
                    "--integration-worktree",
                    str(integration),
                ]
            )
            # Crash between cherry-pick and the integration transition.
            run(
                [
                    "python3",
                    str(SCRIPTS / "run_state.py"),
                    "transition",
                    "--state",
                    str(state),
                    "--ticket",
                    "01",
                    "--status",
                    "implemented",
                    "--branch",
                    child_branch,
                    "--worktree",
                    str(child),
                    "--base-sha",
                    base,
                    "--head-sha",
                    worker_head,
                ]
            )

            # Regenerable artifacts in the child worktree must not read as dirty.
            (child / "__pycache__").mkdir()
            (child / "__pycache__" / "x.pyc").write_text("", encoding="utf-8")
            (child / "node_modules").mkdir()
            (child / "node_modules" / "dep.js").write_text("", encoding="utf-8")

            # The controller records the cherry-picked SHA as the integration
            # evidence. The worker's head cannot prove integration by ancestry,
            # so reconciliation must honor the recorded integrated SHA.
            run(
                [
                    "python3",
                    str(SCRIPTS / "run_state.py"),
                    "transition",
                    "--state",
                    str(state),
                    "--ticket",
                    "01",
                    "--status",
                    "integrated",
                    "--integrated-sha",
                    pick,
                    "--integration-head",
                    pick,
                ]
            )

            report = json.loads(
                run(["python3", str(SCRIPTS / "reconcile_run.py"), "--state", str(state)]).stdout
            )
            self.assertTrue(report["tickets"]["01"]["integrated"])
            self.assertEqual(report["tickets"]["01"]["integration_evidence"], pick)
            self.assertFalse(report["tickets"]["01"]["worktree_dirty"])
            self.assertEqual(report["tickets"]["01"]["recommendations"], [])

            updated = json.loads(state.read_text(encoding="utf-8"))
            self.assertEqual(updated["tickets"]["01"]["status"], "integrated")
            self.assertEqual(updated["ready_frontier"], ["02"])

            # A real untracked file is not an artifact: the worktree reads dirty again.
            (child / "scratch-notes.txt").write_text("salvage me\n", encoding="utf-8")
            report2 = json.loads(
                run(["python3", str(SCRIPTS / "reconcile_run.py"), "--state", str(state)]).stdout
            )
            self.assertTrue(report2["tickets"]["01"]["worktree_dirty"])
            self.assertTrue(
                any("preserve worktree" in rec for rec in report2["tickets"]["01"]["recommendations"])
            )

    def test_reconcile_quiet_prints_exceptions_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = self.make_repo(root)
            integration = repo / ".runs" / "integration"
            run(
                [
                    "python3",
                    str(SCRIPTS / "make_worktree.py"),
                    "--repo",
                    str(repo),
                    "--path",
                    str(integration),
                    "--branch",
                    "agent/demo/integration",
                    "--metadata",
                    str(root / "integration.json"),
                ]
            )
            issues = root / "issues"
            issues.mkdir()
            (issues / "01-change.md").write_text(
                "# 01: Change\n\n**What to build:** It works.\n\n"
                "**Blocked by:** None\n\n- [ ] It works.\n",
                encoding="utf-8",
            )
            index = root / "ticket-index.json"
            run(["python3", str(SCRIPTS / "index_tickets.py"), str(issues), "--output", str(index)])
            state = root / "state.json"
            run(
                [
                    "python3",
                    str(SCRIPTS / "run_state.py"),
                    "init",
                    "--index",
                    str(index),
                    "--state",
                    str(state),
                    "--ledger",
                    str(root / "ledger.md"),
                    "--repo",
                    str(repo),
                    "--base",
                    "HEAD",
                    "--integration-branch",
                    "agent/demo/integration",
                    "--integration-worktree",
                    str(integration),
                ]
            )
            run(
                [
                    "python3",
                    str(SCRIPTS / "reconcile_run.py"),
                    "--state",
                    str(state),
                    "--apply",
                    "--quiet",
                ]
            )
            summary = json.loads(
                run(
                    ["python3", str(SCRIPTS / "reconcile_run.py"), "--state", str(state), "--quiet"]
                ).stdout
            )
            self.assertIn("integration_head", summary)
            self.assertIn("tickets_with_recommendations", summary)
            self.assertEqual(summary["tickets_with_recommendations"], {})


if __name__ == "__main__":
    unittest.main()
