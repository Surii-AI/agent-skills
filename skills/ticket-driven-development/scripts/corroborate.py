#!/usr/bin/env python3
"""Scripted corroboration first pass for completed-ticket claims.

Scans Git history for evidence that a ticket whose source status claims
completion was actually implemented. A commit subject naming the ticket id is
strong evidence; a commit merely touching one of the ticket's conflict
domains is weak evidence, recorded but never sufficient. The controller's
ruling flow stays authoritative — this script only narrows what a human or
controller must adjudicate.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from index_tickets import COMPLETED_STATUSES

SUBJECT_ID_RE = r"(?<![A-Za-z0-9_.-])tickets?[ -]#?{ticket_id}(?![A-Za-z0-9_.-])"


def git(repo: Path, args: list[str]) -> str:
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


def load_history(repo: Path, since: str | None) -> list[tuple[str, str]]:
    if since:
        log_args = ["log", f"{since}..HEAD", "--format=%H%x09%s"]
    else:
        log_args = ["log", "-n", "1000", "--format=%H%x09%s"]
    entries = []
    for line in git(repo, log_args).splitlines():
        if line.strip():
            sha, subject = line.split("\t", 1)
            entries.append((sha, subject))
    return entries


def commit_files(repo: Path, sha: str) -> list[str]:
    return [line for line in git(repo, ["show", "--name-only", "--format=", sha]).splitlines() if line.strip()]


def corroborate_ticket(ticket: dict[str, Any], history: list[tuple[str, str]], files_by_sha: dict[str, list[str]]) -> dict[str, Any]:
    pattern = re.compile(SUBJECT_ID_RE.format(ticket_id=re.escape(ticket["id"])), re.IGNORECASE)
    evidence: list[dict[str, Any]] = []
    for sha, subject in history:
        if pattern.search(subject):
            evidence.append({"sha": sha, "subject": subject, "kind": "subject-id", "weak": False})
            continue
        domains = ticket.get("conflict_domains") or []
        if domains and any(fnmatch(path, glob) for path in files_by_sha[sha] for glob in domains):
            evidence.append({"sha": sha, "subject": subject, "kind": "domain-overlap", "weak": True})
    corroborated = any(not item["weak"] for item in evidence)
    return {
        "id": ticket["id"],
        "status": ticket["status"],
        "corroborated": corroborated,
        "evidence": evidence,
        "needs_review": (not corroborated) and bool(evidence),
    }


def emit(payload: dict[str, Any], output: Path | None) -> None:
    text = json.dumps(payload, indent=2) + "\n"
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path, help="repository whose history corroborates claims")
    parser.add_argument("--index", required=True, type=Path, help="ticket-index.json from index_tickets.py")
    parser.add_argument("--since", help="only inspect commits after this ref (default: last 1000 commits)")
    parser.add_argument("--output", type=Path, help="write the result JSON here instead of stdout")
    args = parser.parse_args()

    try:
        index = json.loads(args.index.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        print(f"error: cannot read index: {error}", file=sys.stderr)
        return 2
    candidates = [ticket for ticket in index.get("tickets", []) if ticket.get("status") in COMPLETED_STATUSES]
    if not candidates:
        emit({"repo": str(args.repo), "since": args.since, "tickets": [], "corroborated_count": 0, "needs_review_count": 0}, args.output)
        return 0

    try:
        history = load_history(args.repo, args.since)
        files_by_sha = {sha: (commit_files(args.repo, sha) if any(t.get("conflict_domains") for t in candidates) else []) for sha, _ in history}
        tickets = [corroborate_ticket(ticket, history, files_by_sha) for ticket in candidates]
    except RuntimeError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    emit(
        {
            "repo": str(args.repo),
            "since": args.since,
            "tickets": tickets,
            "corroborated_count": sum(1 for ticket in tickets if ticket["corroborated"]),
            "needs_review_count": sum(1 for ticket in tickets if ticket["needs_review"]),
        },
        args.output,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
