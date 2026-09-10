#!/usr/bin/env python3

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from test_helpers import SCRIPTS, git, run


def make_repo(root: Path) -> Path:
    repo = root / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test")
    return repo


def commit(repo: Path, path: str, content: str, message: str) -> str:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", message)
    return git(repo, "rev-parse", "HEAD")


def write_guidance(root: Path, base: str, body: str = "1. `src/a.ts` — change the thing\n") -> Path:
    guidance = root / "guidance.md"
    guidance.write_text(f"# Ticket 01 guidance\n\nBase: {base}\n\n## Steps\n{body}", encoding="utf-8")
    return guidance


def run_drift(repo: Path, guidance: Path, actual_base: str, *extra: str, expected: int = 0):
    return run(
        [
            "python3",
            str(SCRIPTS / "guidance_drift.py"),
            "--repo",
            str(repo),
            "--guidance",
            str(guidance),
            "--actual-base",
            actual_base,
            *extra,
        ],
        expected=expected,
    )


class GuidanceDriftTests(unittest.TestCase):
    def test_identical_base_is_not_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = make_repo(root)
            base = commit(repo, "src/a.ts", "original\n", "init")
            guidance = write_guidance(root, base)
            data = json.loads(run_drift(repo, guidance, base).stdout)
            self.assertFalse(data["regenerate"])
            self.assertEqual(data["stale_paths"], [])
            self.assertEqual(data["changed_path_count"], 0)

    def test_immaterial_drift_keeps_plan_and_patch_base_repins(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = make_repo(root)
            base = commit(repo, "src/a.ts", "original\n", "init")
            guidance = write_guidance(root, base)
            moved = commit(repo, "docs/x.md", "notes\n", "docs only")
            data = json.loads(run_drift(repo, guidance, moved).stdout)
            self.assertFalse(data["regenerate"])
            self.assertIn("Base: " + base, guidance.read_text(encoding="utf-8"))
            run_drift(repo, guidance, moved, "--patch-base")
            self.assertIn("Base: " + moved, guidance.read_text(encoding="utf-8"))
            self.assertNotIn("Base: " + base, guidance.read_text(encoding="utf-8"))

    def test_material_drift_names_stale_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = make_repo(root)
            base = commit(repo, "src/a.ts", "original\n", "init")
            guidance = write_guidance(root, base)
            moved = commit(repo, "src/a.ts", "changed\n", "touch the named path")
            data = json.loads(run_drift(repo, guidance, moved).stdout)
            self.assertTrue(data["regenerate"])
            self.assertIn("src/a.ts", data["stale_paths"])

    def test_domain_glob_catches_unnamed_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = make_repo(root)
            base = commit(repo, "src/other.ts", "original\n", "init")
            guidance = write_guidance(root, base, body="1. `src/other.ts` — change the other thing\n")
            moved = commit(repo, "src/api/new.ts", "handler\n", "add endpoint")
            data = json.loads(run_drift(repo, guidance, moved, "--domain", "src/api/**").stdout)
            self.assertTrue(data["regenerate"])
            self.assertIn("src/api/new.ts", data["stale_paths"])

    def test_pathless_guidance_without_domains_is_conservative(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = make_repo(root)
            base = commit(repo, "src/a.ts", "original\n", "init")
            guidance = write_guidance(root, base, body="1. Do the thing described in the ticket.\n")
            moved = commit(repo, "docs/x.md", "notes\n", "docs only")
            data = json.loads(run_drift(repo, guidance, moved).stdout)
            self.assertTrue(data["regenerate"])
            self.assertEqual(data["stale_paths"], ["docs/x.md"])

    def test_missing_base_line_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = make_repo(root)
            base = commit(repo, "src/a.ts", "original\n", "init")
            guidance = root / "guidance.md"
            guidance.write_text("# Ticket 01 guidance\n\n## Steps\n1. Do it.\n", encoding="utf-8")
            data = json.loads(run_drift(repo, guidance, base, expected=2).stdout)
            self.assertTrue(data["regenerate"])
            self.assertEqual(data["reason"], "no valid Base line")


if __name__ == "__main__":
    unittest.main()
