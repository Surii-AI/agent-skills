#!/usr/bin/env python3
"""Regression tests for reconcile_run.py integration evidence."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from test_helpers import SCRIPTS, git, run


def reconcile(state: Path, *extra: str):
    return run(["python3", str(SCRIPTS / "reconcile_run.py"), "--state", str(state), *extra])


def patch_state(state: Path, ticket_id: str, **fields) -> None:
    data = json.loads(state.read_text(encoding="utf-8"))
    data["tickets"][ticket_id].update(fields)
    state.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


class ReconcileIntegrationEvidenceTests(unittest.TestCase):
    def make_run(self, root: Path) -> tuple[Path, Path, str]:
        """Repo with a base commit, an integration branch at the base, and a one-ticket state."""
        repo = root / "repo"
        repo.mkdir()
        git(repo, "init")
        git(repo, "config", "user.email", "test@example.com")
        git(repo, "config", "user.name", "Test User")
        (repo / "app.txt").write_text("base\n", encoding="utf-8")
        git(repo, "add", ".")
        git(repo, "commit", "-m", "base")
        base = git(repo, "rev-parse", "HEAD")
        git(repo, "branch", "agent/demo/integration")

        issues = root / "issues"
        issues.mkdir()
        (issues / "01-change.md").write_text(
            "# 01: Change app\n\n**What to build:** App changes.\n\n"
            "**Blocked by:** None\n\n- [ ] Change is visible.\n",
            encoding="utf-8",
        )
        index = root / "ticket-index.json"
        run(["python3", str(SCRIPTS / "index_tickets.py"), str(issues), "--output", str(index)])

        state = root / "state.json"
        run([
            "python3", str(SCRIPTS / "run_state.py"), "init",
            "--index", str(index),
            "--state", str(state),
            "--ledger", str(root / "ledger.md"),
            "--repo", str(repo),
            "--base", base,
            "--integration-branch", "agent/demo/integration",
            "--integration-worktree", str(root / "worktree"),
        ])
        return repo, state, base

    def test_blocked_ticket_with_base_pinned_shas_is_never_integrated(self) -> None:
        """The eval-4 incident: blocked ticket, unmoved branches, head/integrated sha = base.

        The base commit is trivially reachable from the integration branch, so
        it proves nothing landed; --apply must leave the ticket blocked.
        """
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo, state, base = self.make_run(root)
            git(repo, "branch", "agent/demo/t01")
            patch_state(
                state, "01",
                status="blocked",
                branch="agent/demo/t01",
                head_sha=base,
                integrated_sha=base,
            )

            report = json.loads(reconcile(state).stdout)
            ticket = report["tickets"]["01"]
            self.assertFalse(ticket["integrated"])
            self.assertNotIn("mark integrated; do not redispatch", ticket["recommendations"])

            result = reconcile(state, "--apply")
            self.assertEqual(result.returncode, 0)
            data = json.loads(state.read_text(encoding="utf-8"))
            self.assertEqual(data["tickets"]["01"]["status"], "blocked")
            self.assertNotIn("01: marked integrated", json.loads(result.stdout)["changes"])

    def test_sequential_tip_fallback_still_marks_implemented_ticket_integrated(self) -> None:
        """Sequential flow: implemented ticket committed on the integration branch itself."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo, state, _base = self.make_run(root)
            git(repo, "checkout", "-q", "agent/demo/integration")
            (repo / "app.txt").write_text("base\nchanged\n", encoding="utf-8")
            git(repo, "add", ".")
            git(repo, "commit", "-m", "ticket 01 work")

            patch_state(state, "01", status="implemented", branch="agent/demo/integration", head_sha=None)

            report = json.loads(reconcile(state).stdout)
            self.assertTrue(report["tickets"]["01"]["integrated"])
            self.assertIn("mark integrated; do not redispatch", report["tickets"]["01"]["recommendations"])

            result = reconcile(state, "--apply")
            data = json.loads(state.read_text(encoding="utf-8"))
            self.assertEqual(data["tickets"]["01"]["status"], "integrated")
            self.assertIn("01: marked integrated", json.loads(result.stdout)["changes"])

    def test_cherry_picked_explicit_sha_proves_integration(self) -> None:
        """Parallel flow: worker head is not an ancestor, the recorded integrated sha is."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo, state, _base = self.make_run(root)

            git(repo, "checkout", "-q", "-b", "agent/demo/t01")
            (repo / "app.txt").write_text("base\nworker\n", encoding="utf-8")
            git(repo, "add", ".")
            git(repo, "commit", "-m", "worker commit")
            worker_head = git(repo, "rev-parse", "HEAD")

            git(repo, "checkout", "-q", "agent/demo/integration")
            git(repo, "cherry-pick", worker_head)
            picked = git(repo, "rev-parse", "agent/demo/integration")

            patch_state(
                state, "01",
                status="implemented",
                branch="agent/demo/t01",
                head_sha=worker_head,
                integrated_sha=picked,
            )

            report = json.loads(reconcile(state).stdout)
            ticket = report["tickets"]["01"]
            self.assertTrue(ticket["integrated"])
            self.assertEqual(ticket["integration_evidence"], picked)
            self.assertIn("mark integrated; do not redispatch", ticket["recommendations"])

    def test_blocked_ticket_with_tip_beyond_base_is_not_marked_integrated(self) -> None:
        """A non-implementing status may not use the branch-tip fallback even past base."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo, state, _base = self.make_run(root)

            git(repo, "checkout", "-q", "-b", "agent/demo/t01")
            (repo / "app.txt").write_text("base\nwip\n", encoding="utf-8")
            git(repo, "add", ".")
            git(repo, "commit", "-m", "wip")
            wip = git(repo, "rev-parse", "HEAD")
            git(repo, "checkout", "-q", "agent/demo/integration")
            git(repo, "cherry-pick", wip)

            patch_state(state, "01", status="failed", branch="agent/demo/t01", head_sha=None)

            report = json.loads(reconcile(state).stdout)
            ticket = report["tickets"]["01"]
            self.assertFalse(ticket["integrated"])
            self.assertNotIn("mark integrated; do not redispatch", ticket["recommendations"])


if __name__ == "__main__":
    unittest.main()
