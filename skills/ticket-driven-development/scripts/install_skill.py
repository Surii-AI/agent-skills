#!/usr/bin/env python3
"""Install this skill into a supported coding-agent skill directory.

The portable source keeps validator-compatible frontmatter. Oh My Pi installs add
its supported top-level `disable-model-invocation: true` field so the controller
skill can be invoked explicitly without automatic subagent activation.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

SKILL_NAME = "ticket-driven-development"
TARGETS = {
    "omp": {
        "user": Path("~/.omp/agent/skills"),
        "project": Path(".omp/skills"),
    },
    "codex": {
        "user": Path("~/.codex/skills"),
        "project": Path(".codex/skills"),
    },
    "opencode": {
        "user": Path("~/.config/opencode/skills"),
        "project": Path(".opencode/skills"),
    },
    "zcode": {
        "user": Path("~/.zcode/skills"),
        "project": Path(".zcode/skills"),
    },
    "agent": {
        "user": Path("~/.agents/skills"),
        "project": Path(".agents/skills"),
    },
}
AGENT_TARGETS = {"omp": {"user": Path("~/.omp/agent/agents"), "project": Path(".omp/agents")}}



def inject_omp_explicit_only(skill_file: Path) -> None:
    text = skill_file.read_text(encoding="utf-8")
    if "\ndisable-model-invocation:" in text:
        return
    marker = "\n---\n"
    end = text.find(marker, 4)
    if not text.startswith("---\n") or end == -1:
        raise RuntimeError("SKILL.md has no valid YAML frontmatter block")
    updated = text[:end] + "\ndisable-model-invocation: true" + text[end:]
    skill_file.write_text(updated, encoding="utf-8")


def default_destination(target: str, scope: str, project: Path) -> Path:
    base = TARGETS[target][scope]
    if scope == "user":
        return base.expanduser() / SKILL_NAME
    return project.resolve() / base / SKILL_NAME


def install(source: Path, destination: Path, target: str, force: bool) -> Path:
    if destination.exists():
        if not force:
            raise RuntimeError(f"destination exists: {destination}; pass --force to replace it")
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    if target == "omp":
        inject_omp_explicit_only(destination / "SKILL.md")
    return destination
def install_agents(agents_source: Path, agents_dir: Path, force: bool) -> list[tuple[str, str]]:
    agents_dir.mkdir(parents=True, exist_ok=True)
    outcomes: list[tuple[str, str]] = []
    for source_file in sorted(agents_source.glob("*.md")):
        dest = agents_dir / source_file.name
        if not dest.exists():
            shutil.copyfile(source_file, dest)
            outcomes.append((source_file.name, "installed"))
        elif dest.read_bytes() == source_file.read_bytes():
            outcomes.append((source_file.name, "identical"))
        elif force:
            shutil.copyfile(source_file, dest)
            outcomes.append((source_file.name, "installed"))
        else:
            outcomes.append((source_file.name, "skipped-existing"))
    return outcomes



def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=sorted(TARGETS), required=True)
    parser.add_argument("--scope", choices=["user", "project"], default="user")
    parser.add_argument("--project", type=Path, default=Path.cwd(), help="Project root for project-scope installs")
    parser.add_argument("--destination", type=Path, help="Override the standard target directory")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--no-agents", action="store_true", help="Skip omp agent definition installation")

    args = parser.parse_args()

    source = Path(__file__).resolve().parents[1]
    destination = (args.destination or default_destination(args.target, args.scope, args.project)).expanduser().resolve()
    if destination == source:
        print("ERROR: destination cannot be the source skill directory", file=sys.stderr)
        return 2

    try:
        installed = install(source, destination, args.target, args.force)
    except (OSError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(installed)
    if args.target == "omp":
        print("OMP explicit-only frontmatter enabled. Start a new session or run /reload-plugins.")
    agent_scopes = AGENT_TARGETS.get(args.target, {})
    if args.scope in agent_scopes:
        if args.no_agents:
            return 0
        agent_base = agent_scopes[args.scope]
        agent_dir = agent_base.expanduser() if args.scope == "user" else args.project.resolve() / agent_base
        for name, outcome in install_agents(installed / "agents", agent_dir, args.force):
            if outcome == "skipped-existing":
                print(f"agents: {name} skipped (exists and differs; rerun with --force)")
            else:
                print(f"agents: {name} {outcome}")
    elif args.target == "omp":
        print("agents: project-scope omp agent directory unverified; use --scope user to install them")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
