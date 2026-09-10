#!/usr/bin/env python3

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from test_helpers import SCRIPTS, git, run


def make_repo_with_history(root: Path, commits: list[tuple[str, dict[str, str], str]]) -> tuple[Path, str]:
    """Create a repo; ``commits`` is a list of (subject, {path: content}, message_unused)."""
    repo = root / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "init")
    base = git(repo, "rev-parse", "HEAD")
    shas = []
    for subject, files, _ in commits:
        for path, content in files.items():
            target = repo / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        git(repo, "add", ".")
        git(repo, "commit", "-q", "-m", subject)
        shas.append(git(repo, "rev-parse", "HEAD"))
    return repo, base, shas


def build_index(root: Path, tickets: list[str]) -> Path:
    ticket_dir = root / "tickets"
    ticket_dir.mkdir()
    for text in tickets:
        heading = text.splitlines()[0]
        ticket_id = heading.split(":")[0].strip()
        (ticket_dir / f"{ticket_id}-ticket.md").write_text(text, encoding="utf-8")
    index_path = root / "ticket-index.json"
    run(["python3", str(SCRIPTS / "index_tickets.py"), str(ticket_dir), "--output", str(index_path)])
    return index_path


def run_corroborate(repo: Path, index_path: Path, *extra: str, expected: int = 0):
    return run(
        [
            "python3",
            str(SCRIPTS / "corroborate.py"),
            "--repo",
            str(repo),
            "--index",
            str(index_path),
            *extra,
        ],
        expected=expected,
    )


def ticket_text(ticket_id: str, status: str, domains: str = "") -> str:
    domain_field = f"\n**Conflict domains:** {domains}\n" if domains else ""
    return (
        f"# {ticket_id}: Ticket {ticket_id}\n\n"
        f"**What to build:** Outcome {ticket_id}.\n\n"
        f"**Blocked by:** None (can start immediately)\n\n"
        f"**Status:** {status}\n"
        f"{domain_field}\n"
        "- [ ] It works.\n"
    )


class CorroborateTests(unittest.TestCase):
    def test_subject_naming_ticket_id_corroborates(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo, base, shas = make_repo_with_history(
                root,
                [("feat: W6 P.N.D.50 workpaper (ticket 10)", {"src/w6.py": "x = 1\n"}, "")],
            )
            index_path = build_index(root, [ticket_text("10", "done")])
            data = json.loads(run_corroborate(repo, index_path, "--since", base).stdout)
            self.assertEqual(len(data["tickets"]), 1)
            result = data["tickets"][0]
            self.assertTrue(result["corroborated"])
            self.assertFalse(result["needs_review"])
            self.assertEqual(result["evidence"][0]["sha"], shas[0])
            self.assertEqual(result["evidence"][0]["kind"], "subject-id")
            self.assertFalse(result["evidence"][0]["weak"])

    def test_domain_overlap_alone_needs_review(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo, _base, _shas = make_repo_with_history(
                root,
                [("feat: add endpoint", {"src/api/new.py": "handler\n"}, "")],
            )
            index_path = build_index(root, [ticket_text("11", "done", domains="src/api/**")])
            data = json.loads(run_corroborate(repo, index_path).stdout)
            result = data["tickets"][0]
            self.assertFalse(result["corroborated"])
            self.assertTrue(result["needs_review"])
            self.assertEqual(result["evidence"][0]["kind"], "domain-overlap")
            self.assertTrue(result["evidence"][0]["weak"])

    def test_no_matching_commit_leaves_both_false(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo, _base, _shas = make_repo_with_history(root, [("chore: unrelated", {"docs/note.md": "hi\n"}, "")])
            index_path = build_index(root, [ticket_text("12", "done", domains="src/api/**")])
            data = json.loads(run_corroborate(repo, index_path).stdout)
            result = data["tickets"][0]
            self.assertFalse(result["corroborated"])
            self.assertFalse(result["needs_review"])
            self.assertEqual(result["evidence"], [])

    def test_zero_completed_tickets_yields_empty_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo, _base, _shas = make_repo_with_history(root, [])
            index_path = build_index(root, [ticket_text("13", "ready-for-agent")])
            data = json.loads(run_corroborate(repo, index_path).stdout)
            self.assertEqual(data["tickets"], [])
            self.assertEqual(data["corroborated_count"], 0)


if __name__ == "__main__":
    unittest.main()
