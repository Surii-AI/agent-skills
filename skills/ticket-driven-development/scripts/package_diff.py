#!/usr/bin/env python3
"""Package a Git commit range for a scoped ticket review."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


def git(repo: Path, args: Sequence[str]) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout


def fence(text: str, language: str = "text") -> str:
    runs = re.findall(r"`+", text)
    longest = max((len(run) for run in runs), default=0)
    marker = "`" * max(3, longest + 1)
    return f"{marker}{language}\n{text.rstrip()}\n{marker}\n"


def package_diff(repo: Path, base: str, head: str, ticket: str, output: Path, max_inline_bytes: int) -> dict[str, object]:
    repo_root = Path(git(repo, ["rev-parse", "--show-toplevel"]).strip()).resolve()
    base_sha = git(repo_root, ["rev-parse", f"{base}^{{commit}}"]).strip()
    head_sha = git(repo_root, ["rev-parse", f"{head}^{{commit}}"]).strip()

    commits = git(repo_root, ["log", "--reverse", "--format=%H %s", f"{base_sha}..{head_sha}"])
    stat = git(repo_root, ["diff", "--stat", "--find-renames", base_sha, head_sha])
    names = git(repo_root, ["diff", "--name-status", "--find-renames", base_sha, head_sha])
    diff = git(
        repo_root,
        ["diff", "--no-ext-diff", "--find-renames", "--find-copies", "--unified=40", base_sha, head_sha],
    )

    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    diff_bytes = len(diff.encode("utf-8"))
    raw_diff_path: Path | None = None
    if diff_bytes > max_inline_bytes:
        raw_diff_path = output.with_suffix(".diff")
        raw_diff_path.write_text(diff, encoding="utf-8")
        diff_section = (
            f"The contextual diff is {diff_bytes} bytes and is stored separately at "
            f"`{raw_diff_path}`. Read that file for the complete review.\n"
        )
    else:
        diff_section = fence(diff, "diff")

    content = (
        f"# Review package: {ticket}\n\n"
        f"Generated: {datetime.now(timezone.utc).isoformat()}\n\n"
        f"Repository: `{repo_root}`\n\n"
        f"Range: `{base_sha}..{head_sha}`\n\n"
        "## Commits\n\n"
        + fence(commits)
        + "\n## Diff statistics\n\n"
        + fence(stat)
        + "\n## Changed paths\n\n"
        + fence(names)
        + "\n## Contextual diff\n\n"
        + diff_section
    )
    output.write_text(content, encoding="utf-8")

    return {
        "schema_version": 1,
        "ticket": ticket,
        "repo_root": str(repo_root),
        "base_sha": base_sha,
        "head_sha": head_sha,
        "package_path": str(output),
        "raw_diff_path": str(raw_diff_path) if raw_diff_path else None,
        "diff_bytes": diff_bytes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--base", required=True, help="Base commit-ish, excluded from the package")
    parser.add_argument("--head", required=True, help="Head commit-ish, included in the package")
    parser.add_argument("--ticket", required=True, help="Ticket identifier used in the package heading")
    parser.add_argument("--output", type=Path, required=True, help="Markdown package output path")
    parser.add_argument("--max-inline-bytes", type=int, default=5_000_000)
    args = parser.parse_args()

    try:
        result = package_diff(args.repo, args.base, args.head, args.ticket, args.output, args.max_inline_bytes)
    except (OSError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
