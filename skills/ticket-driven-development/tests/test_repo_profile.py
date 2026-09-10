#!/usr/bin/env python3

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from test_helpers import SCRIPTS, run


class RepoProfileTests(unittest.TestCase):
    def make_fixtures(self, temp: str) -> tuple[Path, Path, Path, Path, Path]:
        root = Path(temp)
        repo = root / "repo"
        repo.mkdir()
        lockfile = repo / "pnpm-lock.yaml"
        lockfile.write_text("lockfile: v1\n", encoding="utf-8")
        data = root / "data.json"
        data.write_text(json.dumps({"install": "pnpm install --frozen-lockfile", "full_suite_minutes": 22}), encoding="utf-8")
        profile = root / "repo-profile.json"
        return repo, lockfile, data, profile, root / "missing.json"

    def new_profile(self, repo: Path, data: Path, lockfile: Path, profile: Path):
        return run(
            [
                "python3",
                str(SCRIPTS / "repo_profile.py"),
                "new",
                "--repo",
                str(repo),
                "--data",
                str(data),
                "--fingerprint",
                str(lockfile),
                "--output",
                str(profile),
            ]
        )

    def test_roundtrip_reuse_is_true(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo, lockfile, data, profile, _ = self.make_fixtures(temp)
            self.new_profile(repo, data, lockfile, profile)
            recorded = json.loads(profile.read_text(encoding="utf-8"))
            self.assertEqual(recorded["data"]["install"], "pnpm install --frozen-lockfile")
            self.assertEqual(recorded["fingerprints"], {str(lockfile): recorded["fingerprints"][str(lockfile)]})
            result = run(
                [
                    "python3",
                    str(SCRIPTS / "repo_profile.py"),
                    "reuse",
                    "--profile",
                    str(profile),
                    "--repo",
                    str(repo),
                ]
            )
            verdict = json.loads(result.stdout)
            self.assertTrue(verdict["reusable"])
            self.assertEqual(verdict["changed"], [])

    def test_mutated_fingerprint_file_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo, lockfile, data, profile, _ = self.make_fixtures(temp)
            self.new_profile(repo, data, lockfile, profile)
            lockfile.write_text("lockfile: v2\n", encoding="utf-8")
            result = run(
                [
                    "python3",
                    str(SCRIPTS / "repo_profile.py"),
                    "reuse",
                    "--profile",
                    str(profile),
                    "--repo",
                    str(repo),
                ]
            )
            verdict = json.loads(result.stdout)
            self.assertFalse(verdict["reusable"])
            self.assertEqual(verdict["changed"], [str(lockfile)])

    def test_vanished_fingerprint_file_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo, lockfile, data, profile, _ = self.make_fixtures(temp)
            self.new_profile(repo, data, lockfile, profile)
            lockfile.unlink()
            result = run(
                [
                    "python3",
                    str(SCRIPTS / "repo_profile.py"),
                    "reuse",
                    "--profile",
                    str(profile),
                    "--repo",
                    str(repo),
                ]
            )
            verdict = json.loads(result.stdout)
            self.assertFalse(verdict["reusable"])
            self.assertEqual(verdict["changed"], [str(lockfile)])

    def test_missing_profile_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo, _lockfile, _data, _profile, missing = self.make_fixtures(temp)
            result = run(
                [
                    "python3",
                    str(SCRIPTS / "repo_profile.py"),
                    "reuse",
                    "--profile",
                    str(missing),
                    "--repo",
                    str(repo),
                ],
                expected=2,
            )
            self.assertIn("error", result.stderr)


if __name__ == "__main__":
    unittest.main()
