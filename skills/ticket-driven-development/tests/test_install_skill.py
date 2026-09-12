#!/usr/bin/env python3

from __future__ import annotations
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from test_helpers import SCRIPTS, run

sys.path.insert(0, str(SCRIPTS))
try:
    import install_skill
finally:
    pass

AGENT_NAMES = ["tdd-junior.md", "tdd-reviewer.md", "tdd-senior.md"]


def make_agents_source(root: Path) -> Path:
    source = root / "agents"
    source.mkdir()
    for name in AGENT_NAMES:
        (source / name).write_text(f"---\nname: {name[:-3]}\n---\nbody\n", encoding="utf-8")
    return source


class InstallAgentsTests(unittest.TestCase):
    def test_empty_dir_installs_all(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = make_agents_source(root)
            outcomes = install_skill.install_agents(source, root / "dest", force=False)
            self.assertEqual(outcomes, [(name, "installed") for name in AGENT_NAMES])
            for name in AGENT_NAMES:
                self.assertEqual(
                    (root / "dest" / name).read_bytes(), (source / name).read_bytes()
                )

    def test_identical_existing_file_reports_identical_and_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = make_agents_source(root)
            dest = root / "dest"
            install_skill.install_agents(source, dest, force=False)
            before = (dest / AGENT_NAMES[0]).stat().st_mtime_ns
            outcomes = install_skill.install_agents(source, dest, force=False)
            self.assertEqual(outcomes, [(name, "identical") for name in AGENT_NAMES])
            self.assertEqual((dest / AGENT_NAMES[0]).stat().st_mtime_ns, before)

    def test_differing_existing_file_skipped_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = make_agents_source(root)
            dest = root / "dest"
            dest.mkdir()
            (dest / AGENT_NAMES[0]).write_text("user customized\n", encoding="utf-8")
            outcomes = install_skill.install_agents(source, dest, force=False)
            self.assertEqual(outcomes[0], (AGENT_NAMES[0], "skipped-existing"))
            self.assertEqual((dest / AGENT_NAMES[0]).read_bytes(), b"user customized\n")

    def test_differing_existing_file_overwritten_with_force(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = make_agents_source(root)
            dest = root / "dest"
            dest.mkdir()
            (dest / AGENT_NAMES[0]).write_text("user customized\n", encoding="utf-8")
            outcomes = install_skill.install_agents(source, dest, force=True)
            self.assertEqual(outcomes[0], (AGENT_NAMES[0], "installed"))
            self.assertEqual((dest / AGENT_NAMES[0]).read_bytes(), (source / AGENT_NAMES[0]).read_bytes())


class InstallerEndToEndTests(unittest.TestCase):
    def run_installer(self, home: Path, *extra: str, expected: int = 0) -> None:
        with mock.patch.dict(os.environ, HOME=str(home)):
            run(
                [
                    "python3",
                    str(SCRIPTS / "install_skill.py"),
                    "--target",
                    "omp",
                    "--scope",
                    "user",
                    *extra,
                ],
                expected=expected,
            )

    def test_omp_user_installs_skill_and_agents(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            destination = home / "skill"
            self.run_installer(home, "--destination", str(destination))
            self.assertTrue(destination.is_dir())
            for name in AGENT_NAMES:
                self.assertTrue((home / ".omp" / "agent" / "agents" / name).exists(), name)
                # The inert agents/ dir ships inside the skill copy too.
                self.assertTrue((destination / "agents" / name).exists(), name)

    def test_no_agents_flag_skips_agent_installation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            self.run_installer(home, "--no-agents")
            self.assertFalse((home / ".omp" / "agent" / "agents").exists())

    def test_agent_target_does_not_touch_omp_agent_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            with mock.patch.dict(os.environ, HOME=str(home)):
                run(
                    [
                        "python3",
                        str(SCRIPTS / "install_skill.py"),
                        "--target",
                        "agent",
                        "--scope",
                        "user",
                    ],
                    expected=0,
                )
            self.assertFalse((home / ".omp" / "agent" / "agents").exists())


if __name__ == "__main__":
    unittest.main()
