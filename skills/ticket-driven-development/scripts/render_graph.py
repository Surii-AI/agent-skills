#!/usr/bin/env python3
"""Render the ticket dependency graph as a Mermaid diagram.

Reads a ticket-index.json produced by index_tickets.py and writes a Markdown
file containing a Mermaid DAG. Presentation only: the output never feeds back
into scheduling, and discovering a problem in the graph is a signal to surface
it to the user or request ticket shaping — never to rewrite tickets here.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RISK_STYLE = {
    "high": ("fill:#f8d7da,stroke:#dc3545", "high risk"),
    "medium": ("fill:#fff3cd,stroke:#ffc107", "medium risk"),
    "low": ("fill:#d1e7dd,stroke:#198754", "low risk"),
}
COMPLETED_STYLE = "fill:#e9ecef,stroke:#6c757d,text:#6c757d"


def mermaid_label(ticket: dict) -> str:
    parts = [ticket["id"]]
    title = " ".join(ticket.get("title", "").split())
    if title:
        parts.append(f": {title}")
    annotations = []
    if ticket.get("risk"):
        annotations.append(ticket["risk"])
    if ticket.get("status"):
        annotations.append(ticket["status"])
    if annotations:
        parts.append(f" [{', '.join(annotations)}]")
    # Escape characters that would break a Mermaid quoted string.
    text = "".join(parts).replace('"', "'")
    return text


def render(index: dict) -> str:
    tickets = {t["id"]: t for t in index.get("tickets", [])}
    lines = [
        "# Ticket dependency graph",
        "",
        f"{len(tickets)} tickets · "
        f"ready frontier: {', '.join(index.get('ready_frontier', [])) or 'none'} · "
        f"index valid: {index.get('valid')}",
        "",
        "Plan snapshot rendered at preflight; the live frontier is `state.json`. "
        "Presentation only — a problem here is surfaced to the user, not repaired here.",
        "",
        "```mermaid",
        "graph TD",
    ]
    for ticket_id, ticket in tickets.items():
        lines.append(f'    {ticket_id}["{mermaid_label(ticket)}"]')
    for ticket_id, ticket in tickets.items():
        for blocker in ticket.get("blockers", []):
            lines.append(f"    {blocker} --> {ticket_id}")
    lines.append("")
    for ticket_id, ticket in tickets.items():
        style = COMPLETED_STYLE if ticket.get("status") in {
            "done", "complete", "completed", "integrated", "closed",
            "implemented", "shipped",
        } else RISK_STYLE.get(ticket.get("risk"), (None, None))[0]
        if style:
            lines.append(f"    style {ticket_id} {style}")
    lines.extend([
        "```",
        "",
        "Legend: green = low risk, yellow = medium, red = high, "
        "gray = complete by source status (corroborate before trusting).",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("index", type=Path, help="ticket-index.json from index_tickets.py")
    parser.add_argument("--output", type=Path, required=True, help="output Markdown path")
    args = parser.parse_args()

    index = json.loads(args.index.read_text(encoding="utf-8"))
    if "tickets" not in index:
        print("error: input does not look like a ticket-index.json", file=sys.stderr)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(index), encoding="utf-8")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
