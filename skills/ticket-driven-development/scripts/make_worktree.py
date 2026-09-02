#!/usr/bin/env python3
"""Create or verify a skill-owned Git worktree safely.

This is the fallback for coding agents that do not provide managed isolated
workspaces with inspectable branch metadata.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


def run_git(repo: Path, args: Sequence[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip() or result.stdout.strip()}")
    return result


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def current_worktrees(repo: Path) -> dict[Path, dict[str, str]]:
    output = run_git(repo, ["worktree", "list", "--porcelain"]).stdout
    records: dict[Path, dict[str, str]] = {}
    current: dict[str, str] = {}
    for line in output.splitlines() + [""]:
        if not line:
            if "worktree" in current:
                records[Path(current["worktree"]).resolve()] = dict(current)
            current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value
    return records


def atomic_write_json(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)


def create_worktree(
    repo: Path,
    worktree: Path,
    branch: str,
    start_point: str,
    owner: str,
    metadata_path: Path,
    reuse: bool,
) -> dict[str, object]:
    repo_root = Path(run_git(repo, ["rev-parse", "--show-toplevel"]).stdout.strip()).resolve()
    base_sha = run_git(repo_root, ["rev-parse", f"{start_point}^{{commit}}"]).stdout.strip()
    worktree = worktree.expanduser().resolve()
    metadata_path = metadata_path.expanduser().resolve()

    existing = current_worktrees(repo_root)
    if worktree in existing:
        if not reuse:
            raise RuntimeError(f"worktree already registered at {worktree}; pass --reuse to verify it")
        actual_branch = existing[worktree].get("branch", "").removeprefix("refs/heads/")
        if actual_branch != branch:
            raise RuntimeError(f"existing worktree uses branch {actual_branch!r}, expected {branch!r}")
        head_sha = run_git(worktree, ["rev-parse", "HEAD"]).stdout.strip()
        metadata = {
            "schema_version": 1,
            "repo_root": str(repo_root),
            "path": str(worktree),
            "branch": branch,
            "base_sha": base_sha,
            "head_sha": head_sha,
            "owner": owner,
            "created_at": None,
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "reused": True,
        }
        atomic_write_json(metadata_path, metadata)
        return metadata

    if worktree.exists() and any(worktree.iterdir()):
        raise RuntimeError(f"refusing to use non-empty path: {worktree}")

    if is_relative_to(worktree, repo_root):
        relative_worktree = worktree.relative_to(repo_root)
        ignored = run_git(repo_root, ["check-ignore", "-q", str(relative_worktree)], check=False)
        if ignored.returncode != 0:
            raise RuntimeError(
                f"worktree path is inside the repository but not ignored: {worktree}. "
                "Add its parent directory to .gitignore or choose a path outside the repository."
            )

    branch_exists = run_git(repo_root, ["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], check=False)
    if branch_exists.returncode == 0:
        raise RuntimeError(f"branch already exists: {branch}; use a new run branch or --reuse its registered worktree")

    worktree.parent.mkdir(parents=True, exist_ok=True)
    run_git(repo_root, ["worktree", "add", "-b", branch, str(worktree), base_sha])
    head_sha = run_git(worktree, ["rev-parse", "HEAD"]).stdout.strip()
    if head_sha != base_sha:
        raise RuntimeError(f"worktree HEAD {head_sha} does not match requested base {base_sha}")

    metadata = {
        "schema_version": 1,
        "repo_root": str(repo_root),
        "path": str(worktree),
        "branch": branch,
        "base_sha": base_sha,
        "head_sha": head_sha,
        "owner": owner,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "reused": False,
    }
    atomic_write_json(metadata_path, metadata)
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="Any path inside the source Git repository")
    parser.add_argument("--path", type=Path, required=True, help="Destination worktree path")
    parser.add_argument("--branch", required=True, help="New or expected local branch name")
    parser.add_argument("--start", default="HEAD", help="Commit-ish from which to create the worktree")
    parser.add_argument("--owner", default="ticket-driven-development", help="Owner recorded in metadata")
    parser.add_argument("--metadata", type=Path, required=True, help="JSON ownership metadata output path")
    parser.add_argument("--reuse", action="store_true", help="Verify and reuse an already registered worktree")
    args = parser.parse_args()

    try:
        metadata = create_worktree(
            args.repo,
            args.path,
            args.branch,
            args.start,
            args.owner,
            args.metadata,
            args.reuse,
        )
    except (OSError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(metadata, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
