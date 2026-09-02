#!/usr/bin/env python3
"""Create and update durable state for a ticket-driven development run."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

DEPENDENCY_SATISFIED = {"verified", "integrated", "skipped"}

STATUSES = {
    "pending",
    "ready",
    "running",
    "implemented",
    "review-required",
    "repair",
    "approved",
    "integrated",
    "verified",
    "blocked",
    "failed",
    "skipped",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def recompute_frontier(state: dict[str, Any]) -> list[str]:
    tickets = state.get("tickets", {})
    ready: list[str] = []
    for ticket_id, ticket in tickets.items():
        if ticket.get("status") not in {"pending", "ready"}:
            continue
        blockers = ticket.get("blockers", [])
        is_ready = all(tickets.get(blocker, {}).get("status") in DEPENDENCY_SATISFIED for blocker in blockers)
        ticket["status"] = "ready" if is_ready else "pending"
        if is_ready:
            ready.append(ticket_id)
    state["ready_frontier"] = ready
    return ready


def append_ledger(path: Path, kind: str, message: str, metadata: dict[str, Any] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    metadata = metadata or {}
    lines = [f"## {now()} — {kind}", "", message.strip(), ""]
    if metadata:
        lines.extend(["```json", json.dumps(metadata, indent=2, sort_keys=True), "```", ""])
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


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
    return result.stdout.strip()


def init_state(args: argparse.Namespace) -> dict[str, Any]:
    index = read_json(args.index.resolve())
    if not index.get("valid"):
        raise RuntimeError("ticket index is invalid; fix its errors before initializing a run")

    repo_root = Path(git(args.repo, ["rev-parse", "--show-toplevel"])).resolve()
    base_sha = git(repo_root, ["rev-parse", f"{args.base}^{{commit}}"])
    created = now()
    tickets = {}
    for ticket in index["tickets"]:
        status = "ready" if ticket["id"] in index.get("ready_frontier", []) else "pending"
        tickets[ticket["id"]] = {
            "title": ticket["title"],
            "source_path": ticket["path"],
            "blockers": ticket["blockers"],
            "risk": ticket.get("risk"),
            "conflict_domains": ticket.get("conflict_domains", []),
            "status": status,
            "worker_id": None,
            "branch": None,
            "worktree": None,
            "base_sha": None,
            "head_sha": None,
            "report_path": None,
            "review_path": None,
            "review_verdict": None,
            "retry_count": 0,
            "integrated_sha": None,
            "last_error": None,
            "started_at": None,
            "finished_at": None,
            "duration_ms": None,
            "context_tokens": None,
            "requests": None,
        }

    state = {
        "schema_version": 1,
        "run_id": args.run_id or uuid.uuid4().hex[:12],
        "status": "preflight",
        "created_at": created,
        "updated_at": created,
        "repo_root": str(repo_root),
        "base_sha": base_sha,
        "spec_path": str(args.spec.resolve()) if args.spec else None,
        "ticket_index_path": str(args.index.resolve()),
        "ledger_path": str(args.ledger.resolve()),
        "integration": {
            "branch": args.integration_branch,
            "worktree": str(args.integration_worktree.resolve()),
            "base_sha": base_sha,
            "head_sha": base_sha,
        },
        "tickets": tickets,
        "rulings": [],
        "deferred_observations": [],
        "ready_frontier": [],
    }
    recompute_frontier(state)
    atomic_write_json(args.state.resolve(), state)
    append_ledger(
        args.ledger.resolve(),
        "run-initialized",
        f"Initialized run `{state['run_id']}` with {len(tickets)} tickets.",
        {"base_sha": base_sha, "integration_branch": args.integration_branch},
    )
    return state


def transition(args: argparse.Namespace) -> dict[str, Any]:
    state_path = args.state.resolve()
    state = read_json(state_path)
    ticket = state.get("tickets", {}).get(args.ticket)
    if ticket is None:
        raise RuntimeError(f"unknown ticket id: {args.ticket}")

    old_status = ticket["status"]
    ticket["status"] = args.status
    fields = {
        "worker_id": args.worker_id,
        "branch": args.branch,
        "worktree": str(args.worktree.resolve()) if args.worktree else None,
        "base_sha": args.base_sha,
        "head_sha": args.head_sha,
        "report_path": str(args.report.resolve()) if args.report else None,
        "review_path": str(args.review.resolve()) if args.review else None,
        "review_verdict": args.review_verdict,
        "integrated_sha": args.integrated_sha,
        "last_error": args.error,
        "risk": args.risk,
        "duration_ms": args.duration_ms,
        "context_tokens": args.context_tokens,
        "requests": args.requests,
    }
    for key, value in fields.items():
        if value is not None:
            ticket[key] = value
    if args.status == "running" and not ticket.get("started_at"):
        ticket["started_at"] = now()
    if args.status in {"implemented", "blocked", "failed", "verified", "skipped"}:
        ticket["finished_at"] = now()
    if args.conflict_domain:
        ticket["conflict_domains"] = list(dict.fromkeys(args.conflict_domain))
    if args.increment_retry:
        ticket["retry_count"] = int(ticket.get("retry_count", 0)) + 1
    if args.integration_head:
        state["integration"]["head_sha"] = args.integration_head
    if args.run_status:
        state["status"] = args.run_status
    recompute_frontier(state)
    state["updated_at"] = now()
    atomic_write_json(state_path, state)

    metadata = {
        "ticket": args.ticket,
        "from": old_status,
        "to": args.status,
        "worker_id": ticket.get("worker_id"),
        "head_sha": ticket.get("head_sha"),
        "review_verdict": ticket.get("review_verdict"),
        "retry_count": ticket.get("retry_count", 0),
    }
    append_ledger(Path(state["ledger_path"]), "ticket-transition", args.message or f"Ticket {args.ticket}: {old_status} → {args.status}.", metadata)
    return state


def record(args: argparse.Namespace) -> dict[str, Any]:
    state_path = args.state.resolve()
    state = read_json(state_path)
    key = "rulings" if args.kind == "ruling" else "deferred_observations"
    item = {"at": now(), "message": args.message}
    state[key].append(item)
    state["updated_at"] = item["at"]
    atomic_write_json(state_path, state)
    append_ledger(Path(state["ledger_path"]), args.kind, args.message)
    return state


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="Initialize state.json and ledger.md")
    init.add_argument("--index", type=Path, required=True)
    init.add_argument("--state", type=Path, required=True)
    init.add_argument("--ledger", type=Path, required=True)
    init.add_argument("--repo", type=Path, default=Path.cwd())
    init.add_argument("--base", default="HEAD")
    init.add_argument("--integration-branch", required=True)
    init.add_argument("--integration-worktree", type=Path, required=True)
    init.add_argument("--spec", type=Path)
    init.add_argument("--run-id")
    init.set_defaults(handler=init_state)

    change = subparsers.add_parser("transition", help="Update one ticket and append a ledger event")
    change.add_argument("--state", type=Path, required=True)
    change.add_argument("--ticket", required=True)
    change.add_argument("--status", choices=sorted(STATUSES), required=True)
    change.add_argument("--worker-id")
    change.add_argument("--branch")
    change.add_argument("--worktree", type=Path)
    change.add_argument("--base-sha")
    change.add_argument("--head-sha")
    change.add_argument("--report", type=Path)
    change.add_argument("--review", type=Path)
    change.add_argument("--review-verdict", choices=["pass", "changes-requested", "blocked", "skipped"])
    change.add_argument("--integrated-sha")
    change.add_argument("--integration-head")
    change.add_argument("--increment-retry", action="store_true")
    change.add_argument("--error")
    change.add_argument("--risk", choices=["low", "medium", "high"])
    change.add_argument("--conflict-domain", action="append", help="Replace inferred conflict domains; repeat as needed")
    change.add_argument("--duration-ms", type=int)
    change.add_argument("--context-tokens", type=int)
    change.add_argument("--requests", type=int)
    change.add_argument("--run-status", choices=["preflight", "running", "blocked", "failed", "complete"])
    change.add_argument("--message")
    change.set_defaults(handler=transition)

    note = subparsers.add_parser("record", help="Record a ruling or deferred observation")
    note.add_argument("--state", type=Path, required=True)
    note.add_argument("--kind", choices=["ruling", "deferred-observation"], required=True)
    note.add_argument("--message", required=True)
    note.set_defaults(handler=record)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        state = args.handler(args)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(state, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
