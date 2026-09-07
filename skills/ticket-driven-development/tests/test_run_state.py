#!/usr/bin/env python3

from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path

from test_helpers import SCRIPTS, git, run


class RunStateTransitionTests(unittest.TestCase):
    def make_initialized_state(self, root: Path) -> Path:
        repo = root / "repo"
        repo.mkdir()
        git(repo, "init")
        git(repo, "config", "user.email", "test@example.com")
        git(repo, "config", "user.name", "Test User")
        (repo / "app.txt").write_text("base\n", encoding="utf-8")
        git(repo, "add", ".")
        git(repo, "commit", "-m", "base")

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
                str(root / "worktree"),
            ]
        )
        return state

    def transition(self, state: Path, *extra: str, expected: int = 0):
        return run(
            ["python3", str(SCRIPTS / "run_state.py"), "transition", "--state", str(state), "--ticket", "01", *extra],
            expected=expected,
        )

    def read(self, state: Path) -> dict:
        return json.loads(state.read_text(encoding="utf-8"))

    def test_integrated_without_commit_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            state = self.make_initialized_state(root)
            result = self.transition(state, "--status", "integrated", expected=2)
            self.assertIn("requires a commit reachable", result.stderr)
            self.assertIn("'verified'", result.stderr)
            # State file must be untouched by the rejected transition.
            self.assertIsNone(self.read(state)["tickets"]["01"]["integrated_sha"])

    def test_verified_terminal_allows_unversioned_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            state = self.make_initialized_state(root)
            self.transition(state, "--status", "running")
            self.transition(state, "--status", "verified", "--review-verdict", "pass")
            ticket = self.read(state)["tickets"]["01"]
            self.assertEqual(ticket["status"], "verified")
            self.assertIsNone(ticket["integrated_sha"])

    def test_duration_derived_from_timestamps(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            state = self.make_initialized_state(root)
            self.transition(state, "--status", "running")
            time.sleep(0.02)
            self.transition(state, "--status", "integrated", "--integrated-sha", "abc1234")
            ticket = self.read(state)["tickets"]["01"]
            self.assertIsInstance(ticket["duration_ms"], int)
            self.assertGreaterEqual(ticket["duration_ms"], 20)
            self.assertIsNotNone(ticket["finished_at"])

    def test_explicit_duration_takes_precedence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            state = self.make_initialized_state(root)
            self.transition(state, "--status", "running")
            time.sleep(0.02)
            self.transition(
                state,
                "--status",
                "integrated",
                "--integrated-sha",
                "abc1234",
                "--duration-ms",
                "4242",
            )
            self.assertEqual(self.read(state)["tickets"]["01"]["duration_ms"], 4242)

    def test_resolved_error_archived_to_repair_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            state = self.make_initialized_state(root)
            self.transition(state, "--status", "running")
            self.transition(
                state,
                "--status",
                "implemented",
                "--error",
                "P1: wired per-entity generation",
                "--increment-retry",
            )
            ticket = self.read(state)["tickets"]["01"]
            self.assertEqual(ticket["last_error"], "P1: wired per-entity generation")
            self.assertEqual(ticket["retry_count"], 1)
            self.assertEqual(ticket.get("repair_history"), [])

            self.transition(
                state,
                "--status",
                "integrated",
                "--integrated-sha",
                "abc1234",
                "--review-verdict",
                "pass",
            )
            ticket = self.read(state)["tickets"]["01"]
            self.assertIsNone(ticket["last_error"], "resolved findings must not persist as an open error")
            history = ticket["repair_history"]
            self.assertEqual(len(history), 1)
            self.assertEqual(history[0]["error"], "P1: wired per-entity generation")
            self.assertEqual(history[0]["retry_count"], 1)
            self.assertIn("at", history[0])

    def test_non_sha_commit_value_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            state = self.make_initialized_state(root)
            result = self.transition(
                state,
                "--status",
                "integrated",
                "--integrated-sha",
                "main",
                expected=2,
            )
            self.assertIn("7-40 hex commit SHA", result.stderr)
            self.assertNotEqual(self.read(state)["tickets"]["01"]["status"], "integrated")

    def test_review_value_with_whitespace_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            state = self.make_initialized_state(root)
            result = self.transition(
                state,
                "--status",
                "implemented",
                "--review",
                "reviews/01.md PASS",
                expected=2,
            )
            self.assertIn("single filesystem path", result.stderr)
            self.assertIsNone(self.read(state)["tickets"]["01"]["review_path"])

    def test_review_verdict_persists(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            state = self.make_initialized_state(root)
            self.transition(state, "--status", "implemented", "--review-verdict", "pass")
            self.assertEqual(self.read(state)["tickets"]["01"]["review_verdict"], "pass")

    def test_guidance_path_recorded_and_whitespace_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            state = self.make_initialized_state(root)
            self.transition(state, "--status", "running", "--guidance", str(root / "guidance" / "01.md"))
            ticket = self.read(state)["tickets"]["01"]
            self.assertEqual(ticket["guidance_path"], str(root / "guidance" / "01.md"))
            self.transition(
                state,
                "--status",
                "running",
                "--guidance",
                "path with spaces.md",
                expected=2,
            )
            self.assertEqual(
                self.read(state)["tickets"]["01"]["guidance_path"],
                str(root / "guidance" / "01.md"),
            )

    def test_full_sha_and_plain_path_still_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            state = self.make_initialized_state(root)
            self.transition(
                state,
                "--status",
                "integrated",
                "--integrated-sha",
                "88ecb7f4abbc6c0ed02ca2b3d3af1495f6160fc8",
                "--report",
                "reports/01.md",
            )
            ticket = self.read(state)["tickets"]["01"]
            self.assertEqual(ticket["status"], "integrated")
            self.assertEqual(ticket["integrated_sha"], "88ecb7f4abbc6c0ed02ca2b3d3af1495f6160fc8")

    def test_quiet_transition_prints_compact_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            state = self.make_initialized_state(root)
            result = self.transition(state, "--status", "running", "--quiet")
            summary = json.loads(result.stdout)
            self.assertEqual(summary["command"], "transition")
            self.assertEqual(summary["ticket"], "01")
            self.assertEqual(summary["to"], "running")
            self.assertIn("ready_frontier", summary)
            # Compact means one line: at N tickets the full state is O(N) per call,
            # the quiet summary must stay O(1).
            self.assertNotIn("\n", result.stdout.strip())
            self.assertLess(len(result.stdout), 400)
            # The durable file still receives the full transition.
            self.assertEqual(self.read(state)["tickets"]["01"]["status"], "running")

    def test_quiet_init_prints_compact_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            repo.mkdir()
            git(repo, "init")
            git(repo, "config", "user.email", "test@example.com")
            git(repo, "config", "user.name", "Test User")
            (repo / "app.txt").write_text("base\n", encoding="utf-8")
            git(repo, "add", ".")
            git(repo, "commit", "-m", "base")

            issues = root / "issues"
            issues.mkdir()
            (issues / "01-change.md").write_text(
                "# 01: Change app\n\n**What to build:** App changes.\n\n"
                "**Blocked by:** None\n\n- [ ] Change is visible.\n",
                encoding="utf-8",
            )
            index = root / "ticket-index.json"
            run(["python3", str(SCRIPTS / "index_tickets.py"), str(issues), "--output", str(index)])

            result = run(
                [
                    "python3",
                    str(SCRIPTS / "run_state.py"),
                    "init",
                    "--index",
                    str(index),
                    "--state",
                    str(root / "state.json"),
                    "--ledger",
                    str(root / "ledger.md"),
                    "--repo",
                    str(repo),
                    "--base",
                    "HEAD",
                    "--integration-branch",
                    "agent/demo/integration",
                    "--integration-worktree",
                    str(root / "worktree"),
                    "--quiet",
                ]
            )
            summary = json.loads(result.stdout)
            self.assertEqual(summary["command"], "init")
            self.assertEqual(summary["tickets"], 1)
            self.assertEqual(summary["ready_frontier"], ["01"])
            self.assertNotIn("\n", result.stdout.strip())


if __name__ == "__main__":
    unittest.main()
