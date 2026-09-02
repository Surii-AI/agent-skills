#!/usr/bin/env python3
"""Reconcile durable ticket-run state with observable Git state."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def git(repo: Path, args: Sequence[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
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


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)


def recompute_frontier(state: dict[str, Any]) -> list[str]:
    tickets = state.get("tickets", {})
    ready: list[str] = []
    for ticket_id, ticket in tickets.items():
        if ticket.get("status") not in {"pending", "ready"}:
            continue
        blockers = ticket.get("blockers", [])
        is_ready = all(tickets.get(blocker, {}).get("status") in {"verified", "skipped"} for blocker in blockers)
        ticket["status"] = "ready" if is_ready else "pending"
        if is_ready:
            ready.append(ticket_id)
    state["ready_frontier"] = ready
    return ready


def append_ledger(path: Path, report: dict[str, Any]) -> None:
    lines = [
        f"## {now()} — reconciliation",
        "",
        "Reconciled durable run state with the current Git repository.",
        "",
        "```json",
        json.dumps(report, indent=2, sort_keys=True),
        "```",
        "",
    ]
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def worktrees(repo: Path) -> dict[str, dict[str, str]]:
    raw = git(repo, ["worktree", "list", "--porcelain"]).stdout
    found: dict[str, dict[str, str]] = {}
    current: dict[str, str] = {}
    for line in raw.splitlines() + [""]:
        if not line:
            if "worktree" in current:
                found[str(Path(current["worktree"]).resolve())] = dict(current)
            current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value
    return found


def commit_exists(repo: Path, sha: str | None) -> bool:
    if not sha:
        return False
    return git(repo, ["cat-file", "-e", f"{sha}^{{commit}}"], check=False).returncode == 0


def branch_tip(repo: Path, branch: str | None) -> str | None:
    if not branch:
        return None
    result = git(repo, ["rev-parse", "--verify", f"refs/heads/{branch}^{{commit}}"], check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def is_ancestor(repo: Path, ancestor: str | None, descendant: str) -> bool:
    if not ancestor:
        return False
    return git(repo, ["merge-base", "--is-ancestor", ancestor, descendant], check=False).returncode == 0


def is_dirty(path: str | None) -> bool | None:
    if not path or not Path(path).is_dir():
        return None
    result = git(Path(path), ["status", "--porcelain"], check=False)
    if result.returncode != 0:
        return None
    return bool(result.stdout.strip())


def reconcile(state_path: Path, apply: bool) -> dict[str, Any]:
    state = json.loads(state_path.read_text(encoding="utf-8"))
    repo = Path(state["repo_root"])
    known_worktrees = worktrees(repo)
    integration_branch = state["integration"]["branch"]
    integration_head = branch_tip(repo, integration_branch)
    if not integration_head:
        raise RuntimeError(f"integration branch does not exist: {integration_branch}")

    ticket_reports: dict[str, Any] = {}
    changes: list[str] = []
    for ticket_id, ticket in state.get("tickets", {}).items():
        branch_sha = branch_tip(repo, ticket.get("branch"))
        recorded_head = ticket.get("head_sha")
        effective_head = recorded_head if commit_exists(repo, recorded_head) else branch_sha
        recorded_worktree = ticket.get("worktree")
        worktree_present = bool(recorded_worktree and str(Path(recorded_worktree).resolve()) in known_worktrees)
        integrated = is_ancestor(repo, effective_head, integration_head)
        dirty = is_dirty(recorded_worktree) if worktree_present else None

        recommendations: list[str] = []
        if integrated and ticket.get("status") not in {"integrated", "verified", "skipped"}:
            recommendations.append("mark integrated; do not redispatch")
        if ticket.get("status") == "running" and not worktree_present and not integrated:
            recommendations.append("classify stale worker before redispatch")
        if dirty:
            recommendations.append("preserve worktree; inspect uncommitted changes before cleanup")
        if ticket.get("head_sha") and not commit_exists(repo, ticket.get("head_sha")):
            recommendations.append("recorded head commit is missing")

        ticket_reports[ticket_id] = {
            "status": ticket.get("status"),
            "branch_tip": branch_sha,
            "recorded_head": recorded_head,
            "effective_head": effective_head,
            "worktree_present": worktree_present,
            "worktree_dirty": dirty,
            "integrated": integrated,
            "recommendations": recommendations,
        }

        if apply:
            if branch_sha and not recorded_head:
                ticket["head_sha"] = branch_sha
                changes.append(f"{ticket_id}: recorded branch tip as head_sha")
            if integrated and ticket.get("status") not in {"integrated", "verified", "skipped"}:
                ticket["status"] = "integrated"
                ticket["integrated_sha"] = integration_head
                changes.append(f"{ticket_id}: marked integrated")

    report = {
        "schema_version": 1,
        "checked_at": now(),
        "state_path": str(state_path.resolve()),
        "integration_branch": integration_branch,
        "integration_head": integration_head,
        "tickets": ticket_reports,
        "applied": apply,
        "changes": changes,
    }

    if apply:
        state["integration"]["head_sha"] = integration_head
        recompute_frontier(state)
        state["updated_at"] = now()
        state["last_reconciliation"] = report["checked_at"]
        atomic_write_json(state_path, state)
        append_ledger(Path(state["ledger_path"]), report)

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--apply", action="store_true", help="Apply safe state repairs and append a ledger event")
    args = parser.parse_args()

    try:
        report = reconcile(args.state.resolve(), args.apply)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
