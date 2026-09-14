#!/usr/bin/env python3
"""Install this skill into a supported coding-agent skill directory.

The portable source keeps validator-compatible frontmatter. Oh My Pi installs add
its supported top-level `disable-model-invocation: true` field so the controller
skill can be invoked explicitly without automatic subagent activation.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

SKILL_NAME = "ticket-driven-development"
def omp_agent_home() -> Path:
    """Active omp user agent dir, honoring OMP_PROFILE/PI_PROFILE relocation."""
    profile = os.environ.get("OMP_PROFILE", os.environ.get("PI_PROFILE", "")).strip()
    if profile and profile != "default":
        return Path("~/.omp") / "profiles" / profile / "agent"
    return Path("~/.omp/agent")


def _omp_targets() -> tuple[dict, dict]:
    home = omp_agent_home()
    targets = {
        "omp": {
            "user": home / "skills",
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
    agent_targets = {
        "omp": {"user": home / "agents", "project": Path(".omp/agents")},
        "zcode": {"user": Path("~/.zcode/agents"), "project": Path(".zcode/agents")},
    }
    return targets, agent_targets


TARGETS, AGENT_TARGETS = _omp_targets()



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
def install_agents(agents_source: Path, agents_dir: Path) -> list[tuple[str, str]]:
    """Install agent definitions as skill-owned payload.

    Agent definitions are version-coupled to the skill (its templates, scripts,
    and guidance flow reference them), so an install or update always syncs
    them; leaving a stale copy behind breaks mixed-version installs. Use
    --no-agents to opt out entirely.
    """
    agents_dir.mkdir(parents=True, exist_ok=True)
    outcomes: list[tuple[str, str]] = []
    for source_file in sorted(agents_source.glob("*.md")):
        dest = agents_dir / source_file.name
        if dest.exists() and dest.read_bytes() == source_file.read_bytes():
            outcomes.append((source_file.name, "identical"))
        elif dest.exists():
            shutil.copyfile(source_file, dest)
            outcomes.append((source_file.name, "updated"))
        else:
            shutil.copyfile(source_file, dest)
            outcomes.append((source_file.name, "installed"))
    return outcomes


OMP_TO_ZCODE_TOOLS = {
    "read": "Read",
    "write": "Write",
    "edit": "Edit",
    "bash": "Bash",
    "grep": "Grep",
    "glob": "Glob",
    "web_search": "WebSearch",
    "web_fetch": "WebFetch",
}
ZCODE_THOUGHT_LEVELS = ("low", "high", "max")


def parse_agent_markdown(text: str) -> dict[str, object]:
    """Split an agent definition into flat frontmatter and body."""
    lines = text.replace("\r\n", "\n").split("\n")
    if not lines or lines[0].strip() != "---":
        raise RuntimeError("agent file has no frontmatter block")
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        raise RuntimeError("agent file has no frontmatter block") from None
    frontmatter: dict[str, object] = {}
    pending: str | None = None
    for line in lines[1:end]:
        stripped = line.strip()
        if not stripped:
            pending = None
            continue
        if stripped.startswith("- ") and pending is not None:
            items = frontmatter[pending]
            if isinstance(items, list):
                items.append(stripped[2:].strip())
            continue
        pending = None
        key, sep, value = line.partition(":")
        if sep and not key.startswith((" ", "\t", "-")):
            name = key.strip()
            if value.strip() == "":
                frontmatter[name] = []
                pending = name
            else:
                frontmatter[name] = value.strip()
    return {"frontmatter": frontmatter, "body": "\n".join(lines[end + 1 :]).strip()}


def render_zcode_agent(agent: dict[str, object], model: str | None) -> str:
    """Render an omp agent definition as a ZCode subagent profile.

    ZCode profiles are Markdown files (user ~/.zcode/agents, workspace
    <repo>/.zcode/agents) with required name and description frontmatter,
    optional model/thoughtLevel/tools/skills, and the body as the system
    prompt. Model ids are machine-specific, so the omp model pin carries over
    only as thoughtLevel; pin models explicitly with --zcode-model name=id.
    omp's autoloadSkills carries over as the ZCode skills allowlist: the
    profile gets the Skill tool and can load only the listed skills.
    """
    frontmatter = agent["frontmatter"]
    assert isinstance(frontmatter, dict)
    name = frontmatter.get("name")
    if not name:
        raise RuntimeError("agent file is missing required frontmatter: name")
    omp_model = frontmatter.get("model", "")
    tier = omp_model.rsplit(":", 1)[-1].lower() if ":" in omp_model else ""
    # ZCode has no medium variant; high keeps a junior able to notice a disproved plan step.
    level = "high" if tier in ("", "medium") else tier
    if level not in ZCODE_THOUGHT_LEVELS:
        raise RuntimeError(f"cannot map omp model tier to a ZCode thought level: {omp_model}")
    tools = [
        OMP_TO_ZCODE_TOOLS[entry.strip()]
        for entry in frontmatter.get("tools", "").split(",")
        if entry.strip() in OMP_TO_ZCODE_TOOLS
    ]
    fields = [f"name: {name}", f"description: {frontmatter.get('description', '')}"]
    if model:
        fields.append(f"model: {model}")
    fields.append(f"thoughtLevel: {level}")
    if tools:
        fields.append("tools: [" + ", ".join(tools) + "]")
    skills = frontmatter.get("autoloadSkills")
    if isinstance(skills, list) and skills:
        fields.append("skills: [" + ", ".join(str(item) for item in skills) + "]")
    body = agent["body"]
    assert isinstance(body, str)
    return "---\n" + "\n".join(fields) + "\n---\n\n" + body + "\n"


def install_zcode_agents(
    agents_source: Path, agents_dir: Path, models: dict[str, str]
) -> list[tuple[str, str]]:
    """Install agent definitions converted to ZCode subagent profiles."""
    agents_dir.mkdir(parents=True, exist_ok=True)
    outcomes: list[tuple[str, str]] = []
    for source_file in sorted(agents_source.glob("*.md")):
        agent = parse_agent_markdown(source_file.read_text(encoding="utf-8"))
        frontmatter = agent["frontmatter"]
        assert isinstance(frontmatter, dict)
        rendered = render_zcode_agent(agent, models.get(frontmatter.get("name", "")))
        dest = agents_dir / source_file.name
        existed = dest.exists()
        if existed and dest.read_text(encoding="utf-8") == rendered:
            outcomes.append((source_file.name, "identical"))
            continue
        dest.write_text(rendered, encoding="utf-8")
        outcomes.append((source_file.name, "updated" if existed else "installed"))
    return outcomes


def parse_zcode_models(pairs: list[str]) -> dict[str, str]:
    models: dict[str, str] = {}
    for pair in pairs:
        name, sep, model = pair.partition("=")
        if not sep or not name.strip() or not model.strip():
            raise RuntimeError(f"--zcode-model expects name=id, got: {pair}")
        models[name.strip()] = model.strip()
    return models



def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=sorted(TARGETS), required=True)
    parser.add_argument("--scope", choices=["user", "project"], default="user")
    parser.add_argument("--project", type=Path, default=Path.cwd(), help="Project root for project-scope installs")
    parser.add_argument("--destination", type=Path, help="Override the standard target directory")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--no-agents", action="store_true", help="Skip omp agent definition installation")
    parser.add_argument(
        "--zcode-agents",
        action="store_true",
        help="Also install the tdd-* definitions as ZCode subagent profiles (requires --target zcode)",
    )
    parser.add_argument(
        "--zcode-model",
        action="append",
        default=[],
        metavar="NAME=ID",
        help="Pin a ZCode model id for one profile, e.g. tdd-junior=custom:...:GLM-5.3-Flash (repeatable; requires --zcode-agents)",
    )

    args = parser.parse_args()

    if args.zcode_agents and args.target != "zcode":
        parser.error("--zcode-agents requires --target zcode")
    if args.zcode_model and not args.zcode_agents:
        parser.error("--zcode-model requires --zcode-agents")

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
    agent_scopes = AGENT_TARGETS.get(args.target, {})
    if args.scope in agent_scopes:
        if args.no_agents:
            return 0
        agent_base = agent_scopes[args.scope]
        agent_dir = agent_base.expanduser() if args.scope == "user" else args.project.resolve() / agent_base
        if args.target == "zcode":
            if not args.zcode_agents:
                print(
                    f'agents: not installed — pass --zcode-agents to add tdd-* profiles to {agent_dir}; '
                    'roles otherwise map to built-in subagents per references/adapters.md "ZCode adapter"'
                )
                return 0
            try:
                models = parse_zcode_models(args.zcode_model)
                outcomes = install_zcode_agents(installed / "agents", agent_dir, models)
            except (OSError, RuntimeError) as exc:
                print(f"ERROR: {exc}", file=sys.stderr)
                return 2
            for name, outcome in outcomes:
                print(f"agents: {name} {outcome}")
            if not models:
                print("agents: model omitted — profiles inherit the session default; pin per-role models with --zcode-model name=id")
        else:
            for name, outcome in install_agents(installed / "agents", agent_dir):
                print(f"agents: {name} {outcome}")
    elif args.target == "omp":
        print("agents: project-scope omp agent directory unverified; use --scope user to install them")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
