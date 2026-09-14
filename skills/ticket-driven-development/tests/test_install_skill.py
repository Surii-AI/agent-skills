#!/usr/bin/env python3

from __future__ import annotations
import os
import subprocess
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
            outcomes = install_skill.install_agents(source, root / "dest")
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
            install_skill.install_agents(source, dest)
            before = (dest / AGENT_NAMES[0]).stat().st_mtime_ns
            outcomes = install_skill.install_agents(source, dest)
            self.assertEqual(outcomes, [(name, "identical") for name in AGENT_NAMES])
            self.assertEqual((dest / AGENT_NAMES[0]).stat().st_mtime_ns, before)

    def test_differing_existing_file_updated_without_force(self) -> None:
        """Agent definitions are skill payload: an update syncs them, no --force needed."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = make_agents_source(root)
            dest = root / "dest"
            dest.mkdir()
            (dest / AGENT_NAMES[0]).write_text("stale previous version\n", encoding="utf-8")
            outcomes = install_skill.install_agents(source, dest)
            self.assertEqual(outcomes[0], (AGENT_NAMES[0], "updated"))
            self.assertEqual((dest / AGENT_NAMES[0]).read_bytes(), (source / AGENT_NAMES[0]).read_bytes())


class InstallerEndToEndTests(unittest.TestCase):
    def run_installer(
        self, home: Path, *extra: str, expected: int = 0
    ) -> subprocess.CompletedProcess[str]:
        with mock.patch.dict(os.environ, HOME=str(home), OMP_PROFILE="", PI_PROFILE=""):
            return run(
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

    def test_agent_target_uses_agents_dir_and_skips_omp_agents(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            with mock.patch.dict(os.environ, HOME=str(home), OMP_PROFILE="", PI_PROFILE=""):
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
            # The generic agent target must stay on ~/.agents/skills — the
            # cross-tool location ZCode and the skills CLI discover.
            self.assertTrue(
                (home / ".agents" / "skills" / "ticket-driven-development" / "SKILL.md").exists()
            )
            self.assertFalse((home / ".agent").exists())
            self.assertFalse((home / ".omp" / "agent" / "agents").exists())

    def test_zcode_target_prints_role_mapping_hint(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            destination = home / "skill"
            with mock.patch.dict(os.environ, HOME=str(home), OMP_PROFILE="", PI_PROFILE=""):
                result = run(
                    [
                        "python3",
                        str(SCRIPTS / "install_skill.py"),
                        "--target",
                        "zcode",
                        "--scope",
                        "user",
                        "--destination",
                        str(destination),
                    ],
                    expected=0,
                )
            self.assertTrue((destination / "SKILL.md").exists())
            self.assertIn("ZCode adapter", result.stdout)
            self.assertIn("--zcode-agents", result.stdout)
            self.assertFalse((home / ".zcode" / "agents").exists())
            # The hint is zcode-specific: omp installs stay silent about it.
            omp = self.run_installer(home, "--destination", str(home / "omp-skill"))
            self.assertNotIn("ZCode adapter", omp.stdout)

    def test_zcode_agents_installs_converted_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            destination = home / "skill"
            with mock.patch.dict(os.environ, HOME=str(home), OMP_PROFILE="", PI_PROFILE=""):
                result = run(
                    [
                        "python3",
                        str(SCRIPTS / "install_skill.py"),
                        "--target",
                        "zcode",
                        "--scope",
                        "user",
                        "--destination",
                        str(destination),
                        "--zcode-agents",
                        "--zcode-model",
                        "tdd-junior=custom:prov%3Aider:GLM-5.3-Flash",
                    ],
                    expected=0,
                )
            junior = home / ".zcode" / "agents" / "tdd-junior.md"
            text = junior.read_text(encoding="utf-8")
            self.assertIn("name: tdd-junior", text)
            self.assertIn("model: custom:prov%3Aider:GLM-5.3-Flash", text)
            # omp's flash:medium tier maps to high — ZCode has no medium variant.
            self.assertIn("thoughtLevel: high", text)
            # Tool names translate; omp-only tools (lsp, ast_edit) are dropped.
            self.assertIn("tools: [Read, Write, Edit, Bash, Grep, Glob]", text)
            # omp-only frontmatter does not carry over.
            self.assertNotIn("read-summarize", text)
            # The body becomes the system prompt.
            self.assertIn("junior implementer", text)
            # Senior/reviewer get no model pin unless named.
            senior = (home / ".zcode" / "agents" / "tdd-senior.md").read_text(encoding="utf-8")
            self.assertNotIn("model:", senior)
            self.assertIn("thoughtLevel: high", senior)
            self.assertIn("tools: [Read, Grep, Glob, Bash, WebSearch]", senior)
            self.assertIn("agents: tdd-junior.md installed", result.stdout)
            # Re-running is idempotent.
            with mock.patch.dict(os.environ, HOME=str(home), OMP_PROFILE="", PI_PROFILE=""):
                rerun = run(
                    [
                        "python3",
                        str(SCRIPTS / "install_skill.py"),
                        "--target",
                        "zcode",
                        "--scope",
                        "user",
                        "--destination",
                        str(destination),
                        "--force",
                        "--zcode-agents",
                        "--zcode-model",
                        "tdd-junior=custom:prov%3Aider:GLM-5.3-Flash",
                    ],
                    expected=0,
                )
            self.assertIn("agents: tdd-junior.md identical", rerun.stdout)

    def test_zcode_model_requires_zcode_agents_and_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            with mock.patch.dict(os.environ, HOME=str(home), OMP_PROFILE="", PI_PROFILE=""):
                run(
                    [
                        "python3",
                        str(SCRIPTS / "install_skill.py"),
                        "--target",
                        "zcode",
                        "--zcode-model",
                        "tdd-junior=x",
                    ],
                    expected=2,
                )
                run(
                    [
                        "python3",
                        str(SCRIPTS / "install_skill.py"),
                        "--target",
                        "omp",
                        "--zcode-agents",
                    ],
                    expected=2,
                )

    def test_update_refreshes_stale_agents_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            destination = home / "skill"
            self.run_installer(home, "--destination", str(destination))
            agents_dir = home / ".omp" / "agent" / "agents"
            (agents_dir / AGENT_NAMES[0]).write_text("stale previous version\n", encoding="utf-8")
            self.run_installer(home, "--destination", str(destination), "--force")
            source = destination / "agents" / AGENT_NAMES[0]
            self.assertEqual((agents_dir / AGENT_NAMES[0]).read_bytes(), source.read_bytes())


if __name__ == "__main__":
    unittest.main()
